"""Intelligent Video Editing Planner (Mode A): Translates Reference Style + Source Analysis into EDL & Timeline JSON."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.models import EditingTimeline, Project, ProjectFile, ReferenceAsset
from backend.services.providers import generate_storyboard_captions, parse_creative_instructions
from backend.services.reference_library import resolve_matching_reference_directory, search_references


def resolve_dimensions(aspect_ratio: str, quality: str = "1080p") -> tuple[int, int]:
    is_720 = quality == "720p"
    if aspect_ratio == "9:16":
        return (720, 1280) if is_720 else (1080, 1920)
    if aspect_ratio == "1:1":
        return (720, 720) if is_720 else (1080, 1080)
    return (1280, 720) if is_720 else (1920, 1080)


def build_editing_timeline(
    db: Session,
    project: Project,
    source_file: ProjectFile,
    source_analysis: Dict[str, Any],
    reference_style_profile: Dict[str, Any],
    reference_asset: Optional[ReferenceAsset] = None,
) -> EditingTimeline:
    """Compare source video analysis and reference style profile to produce an EDL and versioned Timeline JSON."""
    parsed_params = parse_creative_instructions(
        instructions=project.instructions or "",
        editing_intensity=project.editing_intensity,
        reference_style=reference_style_profile,
    )

    source_duration = float(source_file.duration or source_analysis.get("probe", {}).get("duration") or 10.0)
    requested_duration = float(project.target_duration or 15.0)
    target_duration = round(min(requested_duration, max(2.0, source_duration)), 2)

    width, height = resolve_dimensions(project.aspect_ratio, project.video_quality)
    ref_ed = reference_style_profile.get("editing_style", {})
    ref_scenes = reference_style_profile.get("scenes") or []

    # Retrieve Stored Title/Category Vault Reference (50% weight) to blend with Attached Reference (50% weight)
    matched_cat, matched_sub = resolve_matching_reference_directory(
        category=project.category,
        filename_or_title=f"{project.title} {project.instructions or ''}",
    )
    stored_vault_matches = search_references(
        db=db,
        category=matched_cat,
        subcategory=matched_sub,
        query=project.title,
        aspect_ratio=project.aspect_ratio,
        top_k=3,
    )
    if reference_asset:
        stored_vault_matches = [m for m in stored_vault_matches if m["id"] != reference_asset.id] or stored_vault_matches
    stored_vault_ref = stored_vault_matches[0] if stored_vault_matches else None
    stored_vault_style = (stored_vault_ref.get("style_profile") or {}) if stored_vault_ref else {}
    stored_vault_ed = stored_vault_style.get("editing_style", {})
    stored_vault_shot = float(stored_vault_ed.get("average_shot_duration") or parsed_params["target_shot_duration"])
    stored_vault_color = stored_vault_ed.get("color_style") or (stored_vault_ref.get("color_style") if stored_vault_ref else "golden_hour")

    # 50% Attached Reference + 50% Stored Title/Category Vault Reference Shot Duration Blend
    attached_shot = float(parsed_params["target_shot_duration"])
    avg_shot = round(0.50 * attached_shot + 0.50 * stored_vault_shot, 2)
    source_scenes = source_analysis.get("scenes") or [
        {"scene_index": 0, "start_time": 0.0, "end_time": source_duration, "duration": source_duration}
    ]

    # Build Editing Decision List (EDL) selecting optimal sub-segments from the customer's raw video
    edl_decisions: List[Dict[str, Any]] = []
    video_track: List[Dict[str, Any]] = []
    effects_track: List[Dict[str, Any]] = []

    # Decide number of cuts based on reference cut pacing and target duration
    if ref_scenes and len(ref_scenes) > 1:
        ref_total = max(0.5, float(reference_style_profile.get("duration") or target_duration))
        proportional_durations = [
            round(max(1.0, (sc.get("duration", avg_shot) / ref_total) * target_duration), 2)
            for sc in ref_scenes
        ]
    else:
        num_cuts = max(1, min(12, int(round(target_duration / max(1.2, avg_shot)))))
        seg_len = round(target_duration / num_cuts, 2)
        proportional_durations = [seg_len for _ in range(num_cuts)]

    # Normalize proportional durations to sum to target_duration
    total_prop = sum(proportional_durations) or target_duration
    slot_durations = [
        round((d / total_prop) * target_duration, 2) for d in proportional_durations
    ]
    if slot_durations:
        diff = round(target_duration - sum(slot_durations), 2)
        slot_durations[-1] = round(max(0.5, slot_durations[-1] + diff), 2)

    timeline_cursor = 0.0
    num_slots = len(slot_durations)
    source_cursor = 0.0
    source_step = max(0.5, (source_duration - min(slot_durations)) / max(1, num_slots))

    for slot_idx, clip_dur in enumerate(slot_durations):
        if clip_dur <= 0.2:
            continue

        # Pick corresponding source scene or distribute evenly across source video so we never repeat the exact same timestamp
        if slot_idx < len(source_scenes) and source_scenes[slot_idx]["duration"] >= clip_dur:
            sc = source_scenes[slot_idx]
            # Take the most dynamic middle portion of the source scene
            sc_excess = max(0.0, sc["duration"] - clip_dur)
            in_point = round(sc["start_time"] + sc_excess * 0.25, 2)
        else:
            in_point = round(min(max(0.0, source_duration - clip_dur), source_cursor), 2)
            source_cursor = round((source_cursor + source_step) % max(0.5, source_duration), 2)

        out_point = round(min(source_duration, in_point + clip_dur), 2)
        actual_dur = round(max(0.2, out_point - in_point), 2)

        transition_type = "hard_cut"
        if slot_idx > 0 and "fade" in parsed_params["transitions"]:
            transition_type = "fade" if slot_idx % 2 == 1 else "hard_cut"

        zoom_effect = "none"
        if parsed_params["enable_zoom"]:
            zoom_effect = "subtle_zoom_in" if slot_idx % 2 == 0 else "subtle_zoom_out"

        # 50% Attached Reference vs 50% Stored Title/Category Vault Reference alternating style transfer
        is_attached_half = slot_idx % 2 == 0
        blend_source = "50%_attached_reference" if is_attached_half else "50%_stored_title_vault"
        active_grade = parsed_params["color_grade"] if is_attached_half else (stored_vault_color or parsed_params["color_grade"])

        decision = {
            "clip_index": slot_idx,
            "source_file_id": source_file.id,
            "source_relpath": source_file.stored_relpath,
            "source_in": in_point,
            "source_out": out_point,
            "timeline_start": round(timeline_cursor, 2),
            "timeline_end": round(timeline_cursor + actual_dur, 2),
            "duration": actual_dur,
            "speed_factor": parsed_params["speed_factor"],
            "transition_in": transition_type,
            "zoom_effect": zoom_effect,
            "color_grade": active_grade,
            "blend_source": blend_source,
            "rationale": f"[{blend_source}] Shot #{slot_idx + 1} ({actual_dur}s) with {zoom_effect} and {active_grade} grade.",
        }
        edl_decisions.append(decision)
        video_track.append(decision)

        if zoom_effect != "none":
            effects_track.append(
                {
                    "type": "zoom",
                    "effect": zoom_effect,
                    "start_time": round(timeline_cursor, 2),
                    "end_time": round(timeline_cursor + actual_dur, 2),
                }
            )

        timeline_cursor = round(timeline_cursor + actual_dur, 2)

    effects_track.append(
        {
            "type": "color_grade",
            "preset": parsed_params["color_grade"],
            "start_time": 0.0,
            "end_time": timeline_cursor,
        }
    )

    # Captions track
    captions_track: List[Dict[str, Any]] = []
    if project.captions_enabled:
        caption_source = project.caption_text or project.instructions or project.title
        captions_track = generate_storyboard_captions(
            topic=project.title,
            script_text=caption_source,
            category=project.category,
            total_duration=timeline_cursor,
            num_scenes=max(1, min(6, len(video_track))),
        )

    # Audio track
    audio_track: List[Dict[str, Any]] = [
        {
            "role": "source_audio",
            "source_relpath": source_file.stored_relpath,
            "enabled": bool(source_file.has_audio),
            "volume": 0.85,
        }
    ]
    if project.music_preference and project.music_preference.lower() != "none":
        audio_track.append(
            {
                "role": "background_music",
                "style": project.music_preference,
                "volume": 0.20 if source_file.has_audio else 0.65,
                "fade_in": 0.5,
                "fade_out": 1.0,
            }
        )

    existing_versions = (
        db.query(EditingTimeline)
        .filter(EditingTimeline.project_id == project.id)
        .count()
    )
    next_version = existing_versions + 1

    style_comparison = {
        "source_duration": source_duration,
        "source_aspect_ratio": source_file.aspect_ratio,
        "reference_asset_id": reference_asset.id if reference_asset else None,
        "stored_title_vault_asset_id": stored_vault_ref.get("id") if stored_vault_ref else None,
        "stored_title_vault_asset_title": stored_vault_ref.get("title") if stored_vault_ref else None,
        "blend_profile": {
            "attached_reference_weight": 0.50,
            "stored_title_vault_weight": 0.50,
            "matched_directory": matched_cat,
        },
        "reference_pacing": ref_ed.get("pacing", "moderate"),
        "reference_avg_shot_duration": avg_shot,
        "reference_color_style": ref_ed.get("color_style", "cinematic"),
        "applied_pacing": parsed_params["pacing"],
        "applied_color_grade": parsed_params["color_grade"],
        "applied_zoom_effects": parsed_params["enable_zoom"],
        "applied_transitions": parsed_params["transitions"],
        "editing_intensity": project.editing_intensity,
    }

    timeline_doc = {
        "project_id": project.id,
        "version": next_version,
        "mode": "edit",
        "duration": timeline_cursor,
        "aspect_ratio": project.aspect_ratio,
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "fps": 30.0,
        "target_platform": project.target_platform,
        "style_comparison": style_comparison,
        "tracks": {
            "video": video_track,
            "audio": audio_track,
            "captions": captions_track,
            "effects": effects_track,
        },
    }

    planner_notes = (
        f"Generated Hybrid 50/50 Timeline v{next_version}: {len(video_track)} shots totaling {timeline_cursor}s "
        f"[50% Attached Ref + 50% Stored '{matched_cat}' Vault ('{stored_vault_ref.get('title') if stored_vault_ref else 'Category Default'}')] "
        f"transferring '{parsed_params['pacing']}' pacing and '{parsed_params['color_grade']}' grading."
    )

    timeline_row = EditingTimeline(
        project_id=project.id,
        version=next_version,
        duration=timeline_cursor,
        aspect_ratio=project.aspect_ratio,
        resolution=f"{width}x{height}",
        fps=30.0,
        edl_json=edl_decisions,
        timeline_json=timeline_doc,
        planner_notes=planner_notes,
    )
    db.add(timeline_row)
    db.commit()
    db.refresh(timeline_row)
    return timeline_row
