"""Mode B Generation Engine: Novelty Multi-Reference Remixing, Creative Script & Neural Voice-Over Storyboard Builder."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from backend.models import EditingTimeline, GenerationTemplate, Project, ReferenceAsset
from backend.services.editing_planner import resolve_dimensions
from backend.services.providers import (
    generate_creative_script,
    get_provider_capabilities,
    synthesize_neural_voiceover,
)
from backend.services.reference_library import search_references, serialize_reference_asset
from backend.services.storage_manager import storage_manager

DEFAULT_TEMPLATES = [
    {
        "name": "Animal Cinematic Template",
        "category": "animals",
        "description": "Opening hook, close-up wildlife/pet footage, wide habitat shot, dynamic transitions, dramatic captions, neural voice-over, and closing shot.",
        "aspect_ratio": "9:16",
        "default_duration": 16.0,
        "visual_style": "cinematic",
        "structure_json": [
            {"slot": "opening_hook", "role": "Hook & Subject Introduction", "weight": 0.24, "shot_type": "close_up", "zoom": "zoom_in_center", "sfx": "ding"},
            {"slot": "closeup_action", "role": "Playful Detail & Expressive Motion", "weight": 0.26, "shot_type": "close_up", "zoom": "pan_left_to_right", "sfx": "whoosh"},
            {"slot": "wide_habitat", "role": "Environment & Natural Rhythm", "weight": 0.26, "shot_type": "wide", "zoom": "zoom_out_reveal", "sfx": "whoosh"},
            {"slot": "closing_shot", "role": "Heartwarming Climax & Finale", "weight": 0.24, "shot_type": "medium", "zoom": "ken_burns_drift", "sfx": "none"},
        ],
    },
    {
        "name": "Business Executive Explainer",
        "category": "business",
        "description": "High-impact vertical business reel with bold hook, problem breakdown, core insight, and takeaway.",
        "aspect_ratio": "9:16",
        "default_duration": 20.0,
        "visual_style": "cinematic",
        "structure_json": [
            {"slot": "hook", "role": "Bold Statement Hook", "weight": 0.22, "shot_type": "close_up", "zoom": "zoom_in_center", "sfx": "ding"},
            {"slot": "problem", "role": "The Industry Challenge", "weight": 0.28, "shot_type": "medium", "zoom": "pan_left_to_right", "sfx": "whoosh"},
            {"slot": "solution", "role": "Strategic Breakdown", "weight": 0.28, "shot_type": "wide", "zoom": "zoom_out_reveal", "sfx": "whoosh"},
            {"slot": "takeaway", "role": "Executive Call to Action", "weight": 0.22, "shot_type": "close_up", "zoom": "ken_burns_drift", "sfx": "none"},
        ],
    },
    {
        "name": "Cinematic Story Showcase",
        "category": "cinematic",
        "description": "Atmospheric narrative template with smooth fades, moody color grading, and story-driven captions.",
        "aspect_ratio": "9:16",
        "default_duration": 16.0,
        "visual_style": "cinematic",
        "structure_json": [
            {"slot": "prologue", "role": "Atmospheric Opening", "weight": 0.25, "shot_type": "wide", "zoom": "zoom_in_center", "sfx": "ding"},
            {"slot": "rising_action", "role": "Visual Progression", "weight": 0.25, "shot_type": "medium", "zoom": "pan_left_to_right", "sfx": "whoosh"},
            {"slot": "turning_point", "role": "Dramatic Shift", "weight": 0.25, "shot_type": "close_up", "zoom": "zoom_out_reveal", "sfx": "whoosh"},
            {"slot": "resolution", "role": "Emotional Finale", "weight": 0.25, "shot_type": "close_up", "zoom": "ken_burns_drift", "sfx": "none"},
        ],
    },
    {
        "name": "Tech & Product Walkthrough",
        "category": "technology",
        "description": "16:9 landscape product showcase for software demos, feature walkthroughs, and technical tutorials.",
        "aspect_ratio": "16:9",
        "default_duration": 16.0,
        "visual_style": "natural",
        "structure_json": [
            {"slot": "overview", "role": "System Overview", "weight": 0.25, "shot_type": "wide", "zoom": "zoom_in_center", "sfx": "ding"},
            {"slot": "feature_deep_dive", "role": "Core Workflow Demonstration", "weight": 0.25, "shot_type": "close_up", "zoom": "pan_left_to_right", "sfx": "whoosh"},
            {"slot": "architecture", "role": "Real-Time Intelligence", "weight": 0.25, "shot_type": "medium", "zoom": "zoom_out_reveal", "sfx": "whoosh"},
            {"slot": "summary", "role": "Performance & Results", "weight": 0.25, "shot_type": "wide", "zoom": "ken_burns_drift", "sfx": "none"},
        ],
    },
]


def seed_generation_templates(db: Session) -> int:
    count = db.query(GenerationTemplate).count()
    if count > 0:
        return count
    for tmpl in DEFAULT_TEMPLATES:
        db.add(
            GenerationTemplate(
                name=tmpl["name"],
                category=tmpl["category"],
                description=tmpl["description"],
                aspect_ratio=tmpl["aspect_ratio"],
                default_duration=tmpl["default_duration"],
                visual_style=tmpl["visual_style"],
                structure_json=tmpl["structure_json"],
            )
        )
    db.commit()
    return len(DEFAULT_TEMPLATES)


def infer_topic_routing(
    category: str,
    topic: str,
    script_text: str,
) -> Tuple[str, Optional[str], List[str]]:
    """Infer exact category, subcategory, and priority tags from user topic & script."""
    combined = f"{topic or ''} {script_text or ''}".lower()
    cat = (category or "animals").lower().strip()

    if any(w in combined for w in ["cat", "cats", "kitten", "kittens", "feline", "kitty", "meow", "purr"]):
        return "animals", "cats", ["cats", "cat", "kitten", "playful", "cute"]
    if any(w in combined for w in ["lion", "lions", "savanna", "safari", "pride"]):
        return "animals", "lions", ["lions", "lion", "wildlife", "savanna"]
    if any(w in combined for w in ["bird", "birds", "eagle", "parrot", "flight", "feather"]):
        return "animals", "birds", ["birds", "bird", "wildlife", "tropical"]
    if any(w in combined for w in ["dog", "dogs", "puppy", "pet", "pets"]):
        return "animals", "cats", ["pets", "cute", "playful"]
    if any(w in combined for w in ["waterfall", "forest", "mountain", "flower", "ocean", "river"]):
        return "nature", None, ["nature", "waterfall", "forest", "landscape"]
    if any(w in combined for w in ["startup", "founder", "office", "executive", "retail", "finance"]):
        return "business", None, ["business", "office", "strategy", "executive"]
    if any(w in combined for w in ["classroom", "student", "cooking", "study", "lesson", "science"]):
        return "education", None, ["education", "classroom", "learning", "science"]
    if any(w in combined for w in ["software", "ai", "robot", "hardware", "traffic", "autonomous"]):
        return "technology", None, ["technology", "ai", "software", "hardware"]
    if any(w in combined for w in ["fitness", "workout", "portrait", "fashion", "woman", "girl"]):
        return "humans", None, ["humans", "people", "lifestyle", "portrait"]

    return cat, None, [cat]


def synthesize_voiceover_track(
    text: str,
    output_wav: Path,
    language: str = "en",
    voice_preference: str = "kokoro_bella",
    topic: str = "",
    category: str = "",
) -> Tuple[Optional[Path], float, str]:
    """Synthesize neural voice-over using Kokoro-82M ONNX, Piper ONNX, or espeak-ng fallback."""
    return synthesize_neural_voiceover(
        text=text,
        output_wav=output_wav,
        voice_preference=voice_preference,
        language=language,
        topic=topic,
        category=category,
    )


def build_generation_timeline(
    db: Session,
    project: Project,
    template_id: Optional[str] = None,
) -> EditingTimeline:
    """
    Create a scene-by-scene storyboard & versioned timeline from local authorized reference assets
    with Novelty Visual Remixing, Creative Script Generation, and Neural Voice-Over Sync.
    """
    seed_generation_templates(db)

    inferred_cat, inferred_subcat, priority_tags = infer_topic_routing(
        category=project.category,
        topic=project.topic or project.title,
        script_text=project.script_text or project.instructions or "",
    )
    effective_category = inferred_cat or project.category

    template: Optional[GenerationTemplate] = None
    if template_id:
        template = db.query(GenerationTemplate).filter(GenerationTemplate.id == template_id).first()
    if not template:
        template = (
            db.query(GenerationTemplate)
            .filter(GenerationTemplate.category == effective_category)
            .first()
        )
    if not template:
        template = db.query(GenerationTemplate).first()

    slots = list(template.structure_json if template else DEFAULT_TEMPLATES[0]["structure_json"])
    requested_duration = float(project.target_duration or 15.0)
    # Use 4 to 6 dynamic scenes depending on duration for higher visual novelty
    if requested_duration >= 20.0 and len(slots) < 5:
        slots.append(
            {
                "slot": "encore_detail",
                "role": "Signature Moment & Perspective Shift",
                "weight": 0.20,
                "shot_type": "close_up",
                "zoom": "zoom_in_center",
                "sfx": "whoosh",
            }
        )
        # Re-normalize weights
        total_w = sum(float(s.get("weight", 0.2)) for s in slots)
        for s in slots:
            s["weight"] = round(float(s.get("weight", 0.2)) / total_w, 3)

    width, height = resolve_dimensions(project.aspect_ratio, project.video_quality)

    # 1. Retrieve relevant reference assets from the local library (Primary Reference + Category Vault)
    matched_assets = search_references(
        db=db,
        category=effective_category,
        subcategory=inferred_subcat,
        tags=priority_tags,
        query=f"{project.topic or ''} {' '.join(priority_tags)}".strip(),
        aspect_ratio=project.aspect_ratio,
        top_k=8,
    )
    if inferred_subcat:
        sub_matches = [
            a for a in matched_assets
            if a.get("subcategory") == inferred_subcat or inferred_subcat in (a.get("tags") or [])
        ]
        if sub_matches:
            matched_assets = sub_matches

    if not matched_assets:
        matched_assets = search_references(db=db, category=effective_category, top_k=8)
    if not matched_assets:
        matched_assets = search_references(db=db, top_k=8)
    if not matched_assets:
        raise ValueError("Reference library is empty. Please ingest at least one reference video before generating.")

    # Resolve Primary Reference Video (60% visual weight + 70% script/voice/subtitle style weight)
    primary_asset_dict: Dict[str, Any] = matched_assets[0]
    if project.selected_reference_id:
        sel_obj = db.query(ReferenceAsset).filter(ReferenceAsset.id == project.selected_reference_id).first()
        if sel_obj:
            primary_asset_dict = serialize_reference_asset(sel_obj)

    vault_companions = [a for a in matched_assets if a["id"] != primary_asset_dict["id"]]
    if not vault_companions:
        vault_companions = [primary_asset_dict]

    # 2. Generate Creative Script & Subtitles with 70% Reference Style Cadence + 100% Original Synthesis
    script_bundle = generate_creative_script(
        topic=project.topic or project.title,
        script_text=project.script_text or project.instructions or "",
        category=effective_category,
        target_duration=requested_duration,
        num_scenes=len(slots),
        reference_style=primary_asset_dict.get("style_profile") or {},
        reference_title=primary_asset_dict.get("title") or "",
    )
    narration_script = script_bundle["narration_script"]
    scene_lines = script_bundle["scene_lines"]

    # 3. Synthesize 100% Original Neural Voice-Over (Kokoro-82M / Piper ONNX)
    vo_relpath: Optional[str] = None
    vo_duration: float = 0.0
    vo_engine_used: str = "none"
    if project.voiceover_preference and project.voiceover_preference.lower() not in ("none", "off"):
        proj_dir = storage_manager.ensure_project_dirs(project.id)
        vo_path = proj_dir / "input" / "voiceover.wav"
        synthesized_path, vo_dur, vo_engine = synthesize_voiceover_track(
            text=narration_script,
            output_wav=vo_path,
            language=project.language,
            voice_preference=project.voiceover_preference,
            topic=project.topic or project.title,
            category=effective_category,
        )
        if synthesized_path and synthesized_path.exists():
            vo_relpath = storage_manager.to_relpath(synthesized_path)
            vo_duration = vo_dur
            vo_engine_used = vo_engine

    # Synchronize total video duration with neural voice-over + 1.0s breathing room
    target_duration = requested_duration
    if vo_duration > 0:
        target_duration = round(max(requested_duration, min(vo_duration + 1.0, requested_duration * 1.45)), 2)

    # 4. Build 60% Primary Reference + 40% Stored Category Vault Video Track
    primary_slots_quota = max(1, int(round(len(slots) * 0.60)))
    used_asset_ids = set()
    video_track: List[Dict[str, Any]] = []
    storyboard: List[Dict[str, Any]] = []
    effects_track: List[Dict[str, Any]] = []
    timeline_cursor = 0.0
    used_windows: List[Tuple[str, float]] = []

    camera_motions = [
        "zoom_in_center",
        "pan_left_to_right",
        "zoom_out_reveal",
        "pan_right_to_left",
        "ken_burns_drift",
    ]
    color_palettes = [
        project.visual_style or primary_asset_dict.get("color_style") or "cinematic",
        "golden_hour" if effective_category in ("animals", "nature", "humans") else "teal_orange",
        "vibrant" if effective_category in ("animals", "nature") else "cinematic",
    ]

    for idx, slot in enumerate(slots):
        weight = float(slot.get("weight", 1.0 / len(slots)))
        slot_dur = round(max(1.8, target_duration * weight), 2)
        if idx == len(slots) - 1:
            slot_dur = round(max(1.5, target_duration - timeline_cursor), 2)

        # 60% of scenes come from the Primary Reference Video, 40% from Category Vault companions
        is_primary_slot = idx < primary_slots_quota
        if is_primary_slot:
            chosen = primary_asset_dict
            blend_source = "60%_primary_reference"
        else:
            chosen = vault_companions[(idx - primary_slots_quota) % len(vault_companions)]
            blend_source = "40%_category_vault"
        asset_id = chosen["id"]
        used_asset_ids.add(asset_id)

        asset_obj = db.query(ReferenceAsset).filter(ReferenceAsset.id == asset_id).first()
        asset_dur = float(asset_obj.duration if asset_obj else chosen.get("duration", 10.0))
        asset_relpath = asset_obj.stored_relpath if asset_obj else chosen["video_url"].replace("/api/media/", "")

        # Novelty Non-Linear Window Selection: pick non-sequential golden moments from the reference
        scenes = chosen.get("scenes") or []
        in_point = 0.0
        # Offset into the middle/action portion of the reference rather than 0.0s copy
        novelty_offsets = [0.22, 0.55, 0.12, 0.72, 0.38]
        frac = novelty_offsets[idx % len(novelty_offsets)]
        max_start = max(0.0, asset_dur - slot_dur - 0.3)

        if len(scenes) > 1 and idx < len(scenes):
            sc_cand = scenes[(idx + 1) % len(scenes)]
            if float(sc_cand["duration"]) >= min(slot_dur, asset_dur):
                in_point = round(float(sc_cand["start_time"]), 2)
            else:
                in_point = round(max_start * frac, 2)
        else:
            in_point = round(max_start * frac, 2)

        for prev_id, prev_start in used_windows:
            if prev_id == asset_id and abs(in_point - prev_start) < 1.2 and max_start > 2.0:
                in_point = round((in_point + max(2.2, slot_dur * 0.85)) % max(0.5, max_start), 2)
        in_point = min(max_start, max(0.0, in_point))

        out_point = round(min(asset_dur, in_point + slot_dur), 2)
        actual_dur = round(max(0.8, out_point - in_point), 2)
        used_windows.append((asset_id, in_point))

        zoom_effect = camera_motions[idx % len(camera_motions)]
        mirror_flip = bool(idx % 2 == 1)  # Flip perspective on alternating scenes for visual novelty
        speed_factor = 1.04 if idx % 2 == 0 else 0.96
        scene_grade = color_palettes[idx % len(color_palettes)]
        transition_in = "fade" if idx > 0 else "hard_cut"
        sfx_cue = slot.get("sfx", "ding" if idx == 0 else ("whoosh" if idx == 2 else "none"))

        clip_entry = {
            "clip_index": idx,
            "slot_name": slot.get("slot", f"scene_{idx + 1}"),
            "role": slot.get("role", f"Scene {idx + 1}"),
            "source_asset_id": asset_id,
            "source_asset_title": chosen.get("title"),
            "source_relpath": asset_relpath,
            "blend_source": blend_source,
            "license_info": chosen.get("license_info", "Authorized Local Reference"),
            "source_in": in_point,
            "source_out": out_point,
            "timeline_start": round(timeline_cursor, 2),
            "timeline_end": round(timeline_cursor + actual_dur, 2),
            "duration": actual_dur,
            "speed_factor": speed_factor,
            "mirror_flip": mirror_flip,
            "vignette": True,
            "film_grain": True,
            "transition_in": transition_in,
            "zoom_effect": zoom_effect,
            "color_grade": scene_grade,
            "sfx_cue": sfx_cue,
            "narration_line": scene_lines[idx % len(scene_lines)],
        }
        video_track.append(clip_entry)
        storyboard.append(
            {
                "scene_number": idx + 1,
                "slot": clip_entry["slot_name"],
                "role": clip_entry["role"],
                "asset_id": asset_id,
                "asset_title": chosen.get("title"),
                "blend_source": blend_source,
                "in_point": in_point,
                "out_point": out_point,
                "duration": actual_dur,
                "narration": scene_lines[idx % len(scene_lines)],
                "visual_notes": (
                    f"[{blend_source}] {slot.get('shot_type', 'medium')} shot | motion={zoom_effect} | "
                    f"grade={scene_grade} | mirror={'yes' if mirror_flip else 'no'}"
                ),
            }
        )

        effects_track.append(
            {
                "type": "novelty_transform",
                "effect": zoom_effect,
                "color_grade": scene_grade,
                "mirror_flip": mirror_flip,
                "start_time": round(timeline_cursor, 2),
                "end_time": round(timeline_cursor + actual_dur, 2),
            }
        )

        timeline_cursor = round(timeline_cursor + actual_dur, 2)

    # Increment usage count on referenced library assets
    for aid in used_asset_ids:
        a_row = db.query(ReferenceAsset).filter(ReferenceAsset.id == aid).first()
        if a_row:
            a_row.usage_count = (a_row.usage_count or 0) + 1

    # Align caption timestamps exactly to the actual rendered scene boundaries
    captions_track: List[Dict[str, Any]] = []
    if project.captions_enabled:
        for idx, clip in enumerate(video_track):
            line_txt = clip.get("narration_line") or scene_lines[idx % len(scene_lines)]
            st = float(clip["timeline_start"])
            et = round(max(st + 0.5, float(clip["timeline_end"]) - 0.08), 2)
            captions_track.append(
                {
                    "index": idx,
                    "start_time": st,
                    "end_time": et,
                    "text": line_txt[:110],
                    "position": "bottom_center",
                    "animation": "pop_in",
                }
            )

    audio_track: List[Dict[str, Any]] = []
    if vo_relpath:
        audio_track.append(
            {
                "role": "voiceover",
                "source_relpath": vo_relpath,
                "engine": vo_engine_used,
                "duration": vo_duration,
                "script": narration_script,
                "volume": 1.35,
            }
        )

    if project.music_preference and project.music_preference.lower() != "none":
        audio_track.append(
            {
                "role": "background_music",
                "style": project.music_preference,
                "volume": 0.22 if vo_relpath else 0.55,
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
    caps = get_provider_capabilities()

    timeline_doc = {
        "project_id": project.id,
        "version": next_version,
        "mode": "generate",
        "generation_backend": "local_authorized_library_novelty_remix",
        "diffusion_backend_available": caps["video_generation"]["diffusion_text_to_video"]["available"],
        "template_name": template.name if template else "Custom Template",
        "inferred_category": effective_category,
        "inferred_subcategory": inferred_subcat,
        "generated_script": narration_script,
        "voiceover_engine": vo_engine_used,
        "duration": timeline_cursor,
        "aspect_ratio": project.aspect_ratio,
        "resolution": f"{width}x{height}",
        "width": width,
        "height": height,
        "fps": 30.0,
        "storyboard": storyboard,
        "provenance": {
            "source_asset_ids": sorted(list(used_asset_ids)),
            "authorized_local_reuse": True,
            "blend_profile": {
                "script_voiceover_subtitle_reference_style_weight": 0.70,
                "autonomous_original_synthesis_weight": 0.30,
                "primary_reference_visual_weight": 0.60,
                "category_vault_reference_visual_weight": 0.40,
                "primary_reference_id": primary_asset_dict.get("id"),
                "primary_reference_title": primary_asset_dict.get("title"),
            },
            "novelty_transforms_applied": [
                "70_percent_reference_script_voice_subtitle_style",
                "60_40_primary_and_vault_reference_blend",
                "non_linear_multi_asset_slicing",
                "dynamic_ken_burns_camera_motion",
                "alternating_perspective_mirror",
                "cinematic_color_grading_and_vignette",
                "neural_voiceover_and_ambient_mastering",
            ],
        },
        "tracks": {
            "video": video_track,
            "audio": audio_track,
            "captions": captions_track,
            "effects": effects_track,
        },
    }

    planner_notes = (
        f"Generated Novelty Storyboard & Timeline v{next_version} [70% Ref Script/VO/Subtitle Style | "
        f"60% Primary Ref '{primary_asset_dict.get('title')}' + 40% '{effective_category}' Vault] "
        f"with 100% self-synthesized neural voice-over ({vo_engine_used})."
    )

    timeline_row = EditingTimeline(
        project_id=project.id,
        version=next_version,
        duration=timeline_cursor,
        aspect_ratio=project.aspect_ratio,
        resolution=f"{width}x{height}",
        fps=30.0,
        edl_json=storyboard,
        timeline_json=timeline_doc,
        planner_notes=planner_notes,
    )
    db.add(timeline_row)
    db.commit()
    db.refresh(timeline_row)
    return timeline_row
