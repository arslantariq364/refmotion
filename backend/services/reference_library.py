"""Reference Library Subsystem: Ingestion pipeline, duplicate prevention, Top-K retrieval & privacy promotion."""
from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from backend.config import settings
from backend.models import AssetTag, Project, ProjectFile, ReferenceAnalysis, ReferenceAsset, ReferenceScene
from backend.services.media_inspector import compute_file_sha256, inspect_video_file
from backend.services.storage_manager import storage_manager
from backend.services.video_analyzer import analyze_video_complete


class DuplicateAssetError(ValueError):
    """Raised when an identical or perceptually duplicate video is already in the reference library."""

    def __init__(self, message: str, existing_asset_id: str):
        super().__init__(message)
        self.existing_asset_id = existing_asset_id


def hamming_distance_hex(h1: Optional[str], h2: Optional[str]) -> int:
    if not h1 or not h2 or len(h1) != len(h2):
        return 64
    try:
        v1 = int(h1, 16)
        v2 = int(h2, 16)
        return bin(v1 ^ v2).count("1")
    except ValueError:
        return 64


def cosine_similarity(v1: Optional[List[float]], v2: Optional[List[float]]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.5
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 <= 1e-6 or n2 <= 1e-6:
        return 0.5
    return round(dot / (n1 * n2), 4)


def serialize_reference_asset(asset: ReferenceAsset) -> Dict[str, Any]:
    analysis = asset.analysis
    tags = [t.tag for t in asset.tags]
    scenes = [
        {
            "id": s.id,
            "scene_index": s.scene_index,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "duration": s.duration,
            "representative_frame_url": f"/api/media/{s.representative_frame_relpath}" if s.representative_frame_relpath else None,
            "shot_composition": s.shot_composition,
            "motion_level": s.motion_level,
            "dominant_color": s.dominant_color,
        }
        for s in sorted(asset.scenes, key=lambda x: x.scene_index)
    ]

    return {
        "id": asset.id,
        "original_filename": asset.original_filename,
        "title": asset.title,
        "description": asset.description,
        "category": asset.category,
        "subcategory": asset.subcategory,
        "tags": tags,
        "sha256": asset.sha256,
        "perceptual_hash": asset.perceptual_hash,
        "duration": asset.duration,
        "width": asset.width,
        "height": asset.height,
        "resolution": asset.resolution,
        "fps": asset.fps,
        "aspect_ratio": asset.aspect_ratio,
        "bitrate": asset.bitrate,
        "video_codec": asset.video_codec,
        "audio_codec": asset.audio_codec,
        "has_audio": asset.has_audio,
        "audio_info": asset.audio_info_json,
        "video_url": f"/api/media/{asset.stored_relpath}",
        "thumbnail_url": f"/api/media/{asset.thumbnail_relpath}" if asset.thumbnail_relpath else None,
        "contact_sheet_url": f"/api/media/{asset.contact_sheet_relpath}" if asset.contact_sheet_relpath else None,
        "keyframes": asset.keyframes_json or [],
        "transcript": asset.transcript,
        "analysis_status": asset.analysis_status,
        "source_info": asset.source_info,
        "license_info": asset.license_info,
        "usage_count": asset.usage_count,
        "promoted_from_project_id": asset.promoted_from_project_id,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "style_profile": analysis.style_profile_json if analysis else None,
        "pacing": analysis.pacing if analysis else "moderate",
        "average_shot_duration": analysis.average_shot_duration if analysis else asset.duration,
        "color_style": analysis.color_style if analysis else "natural",
        "motion_intensity": analysis.motion_intensity if analysis else "moderate",
        "zoom_effects": analysis.zoom_effects if analysis else False,
        "scenes": scenes,
    }


def resolve_matching_reference_directory(
    category: str,
    filename_or_title: str = "",
    subcategory: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    Match the attached reference video's filename, title, or requested category against
    existing reference directories so it is always stored in the right category folder.
    """
    combined = f"{category or ''} {filename_or_title or ''} {subcategory or ''}".lower()
    existing_dirs = [c.lower() for c in storage_manager.list_categories()]

    # 1. Exact directory name appearance in filename or title
    for dir_name in existing_dirs:
        if dir_name and dir_name != "general" and dir_name in combined:
            if dir_name == "animals" and any(k in combined for k in ["cat", "kitten", "feline", "kitty"]):
                return "animals", subcategory or "cats"
            return dir_name, subcategory

    # 2. Semantic keyword mapping to respective directory
    if any(w in combined for w in ["cat", "kitten", "feline", "kitty", "lion", "bird", "dog", "wildlife", "pet", "animal"]):
        sub = subcategory or ("cats" if any(k in combined for k in ["cat", "kitten", "feline", "kitty"]) else None)
        return "animals", sub
    if any(w in combined for w in ["forest", "waterfall", "mountain", "ocean", "river", "flower", "nature", "landscape"]):
        return "nature", subcategory
    if any(w in combined for w in ["business", "office", "startup", "founder", "executive", "finance", "strategy"]):
        return "business", subcategory
    if any(w in combined for w in ["tech", "ai", "software", "robot", "code", "hardware", "autonomous", "technology"]):
        return "technology", subcategory
    if any(w in combined for w in ["education", "class", "student", "study", "science", "lesson", "cooking", "learn"]):
        return "education", subcategory
    if any(w in combined for w in ["human", "people", "person", "portrait", "fitness", "lifestyle", "woman", "man"]):
        return "humans", subcategory
    if any(w in combined for w in ["cinematic", "film", "movie", "reel", "story", "dramatic"]):
        return "cinematic", subcategory

    cat_clean = storage_manager.sanitize_category(category or "animals")
    if cat_clean == "general" and "animals" in existing_dirs:
        cat_clean = "animals"
    return cat_clean, subcategory


def ingest_reference_video(
    db: Session,
    source_file_path: Path,
    category: str = "general",
    subcategory: Optional[str] = None,
    title: Optional[str] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
    source_info: str = "local_upload",
    license_info: str = "Authorized Local Reference",
    promoted_from_project_id: Optional[str] = None,
    move_file: bool = False,
) -> ReferenceAsset:
    """Execute the 8-step Reference Ingestion Pipeline and store in the matching category directory."""
    # STEP 1: VALIDATION
    probe = inspect_video_file(source_file_path)

    # STEP 2: VIDEO FINGERPRINTING (SHA-256 duplicate check)
    sha256 = compute_file_sha256(source_file_path)
    existing_exact = db.query(ReferenceAsset).filter(ReferenceAsset.sha256 == sha256).first()
    if existing_exact:
        if move_file and source_file_path.exists():
            source_file_path.unlink(missing_ok=True)
        raise DuplicateAssetError(
            f"Reference video with identical SHA-256 ({sha256[:12]}...) already exists as '{existing_exact.title}'",
            existing_asset_id=existing_exact.id,
        )

    matched_cat, matched_sub = resolve_matching_reference_directory(
        category=category,
        filename_or_title=f"{title or ''} {source_file_path.name}",
        subcategory=subcategory,
    )
    cat_clean = storage_manager.sanitize_category(matched_cat)
    sub_clean = storage_manager.sanitize_category(matched_sub) if matched_sub else None
    cat_dir = storage_manager.ensure_reference_category_dir(cat_clean, sub_clean)

    safe_orig = storage_manager.sanitize_filename(source_file_path.name)
    asset_dest_name = f"{sha256[:10]}_{safe_orig}"
    asset_dest_path = cat_dir / asset_dest_name

    if move_file:
        shutil.move(str(source_file_path), str(asset_dest_path))
    else:
        shutil.copy2(str(source_file_path), str(asset_dest_path))

    # Also mirror into /home/arslan-tariq/Video_Tools/refvideos/references/<cat_clean>/ if that directory tree exists
    try:
        ext_ref_root = Path("/home/arslan-tariq/Video_Tools/refvideos/references")
        if ext_ref_root.exists():
            ext_cat_dir = ext_ref_root / cat_clean
            ext_cat_dir.mkdir(parents=True, exist_ok=True)
            ext_dest = ext_cat_dir / safe_orig
            if not ext_dest.exists():
                shutil.copy2(str(asset_dest_path), str(ext_dest))
    except Exception:
        pass

    meta_dir = cat_dir / "_meta" / sha256[:12]

    # STEPS 3, 4, 5, 6, 7: KEYFRAMES, SCENE DETECTION, AUDIO, VISUAL & STYLE PROFILE
    analysis_bundle = analyze_video_complete(asset_dest_path, meta_dir, category=cat_clean)
    phash = analysis_bundle.get("perceptual_hash")

    # Check perceptual near-duplicate with same duration (+/- 0.5s) and resolution
    if phash:
        candidates = (
            db.query(ReferenceAsset)
            .filter(ReferenceAsset.resolution == probe["resolution"])
            .all()
        )
        for cand in candidates:
            if abs(cand.duration - probe["duration"]) <= 0.5:
                if hamming_distance_hex(phash, cand.perceptual_hash) <= 2:
                    shutil.rmtree(meta_dir, ignore_errors=True)
                    asset_dest_path.unlink(missing_ok=True)
                    raise DuplicateAssetError(
                        f"Perceptually identical reference video already exists as '{cand.title}'",
                        existing_asset_id=cand.id,
                    )

    # STEP 8: INDEXING IN SQLITE
    stored_rel = storage_manager.to_relpath(asset_dest_path)
    asset_title = title or Path(safe_orig).stem.replace("_", " ").title()

    asset = ReferenceAsset(
        original_filename=safe_orig,
        title=asset_title,
        description=description,
        stored_relpath=stored_rel,
        sha256=sha256,
        perceptual_hash=phash,
        metadata_fingerprint=probe["metadata_fingerprint"],
        category=cat_clean,
        subcategory=sub_clean,
        duration=probe["duration"],
        width=probe["width"],
        height=probe["height"],
        resolution=probe["resolution"],
        fps=probe["fps"],
        aspect_ratio=probe["aspect_ratio"],
        bitrate=probe["bitrate"],
        video_codec=probe["video_codec"],
        audio_codec=probe["audio_codec"],
        has_audio=probe["has_audio"],
        audio_info_json=probe["audio_info"],
        thumbnail_relpath=analysis_bundle["thumbnail_relpath"],
        contact_sheet_relpath=analysis_bundle["contact_sheet_relpath"],
        keyframes_json=analysis_bundle["keyframes"],
        analysis_status="completed",
        source_info=source_info,
        license_info=license_info,
        promoted_from_project_id=promoted_from_project_id,
    )
    db.add(asset)
    db.flush()

    ed_style = analysis_bundle["style_profile"]["editing_style"]
    vis_prof = analysis_bundle["visual_profile"]
    aud_prof = analysis_bundle["audio_profile"]

    ref_analysis = ReferenceAnalysis(
        asset_id=asset.id,
        pacing=ed_style["pacing"],
        average_shot_duration=ed_style["average_shot_duration"],
        scene_count=ed_style["scene_count"],
        cut_rate_per_minute=ed_style["cut_rate_per_minute"],
        transitions_json=ed_style["transitions"],
        color_style=vis_prof["color_style"],
        dominant_colors_json=vis_prof["dominant_colors"],
        brightness_avg=vis_prof["brightness_avg"],
        contrast_avg=vis_prof["contrast_avg"],
        saturation_avg=vis_prof["saturation_avg"],
        motion_intensity=vis_prof["motion_intensity"],
        motion_score=vis_prof["motion_score"],
        zoom_effects=vis_prof["zoom_effects"],
        caption_style=ed_style["caption_style"],
        music_style=aud_prof["music_style"],
        loudness_lufs=aud_prof["loudness_lufs"],
        silence_ratio=aud_prof["silence_ratio"],
        speech_detected=aud_prof["speech_detected"],
        style_profile_json=analysis_bundle["style_profile"],
        embedding_json=analysis_bundle["embedding"],
    )
    db.add(ref_analysis)

    for sc in analysis_bundle["scenes"]:
        db.add(
            ReferenceScene(
                asset_id=asset.id,
                scene_index=sc["scene_index"],
                start_time=sc["start_time"],
                end_time=sc["end_time"],
                duration=sc["duration"],
                representative_frame_relpath=sc.get("representative_frame_relpath"),
                shot_composition=sc.get("shot_composition", "medium"),
                motion_level=sc.get("motion_level", "moderate"),
                dominant_color=sc.get("dominant_color"),
            )
        )

    auto_tags = set(
        [
            cat_clean,
            probe["aspect_ratio"],
            ed_style["pacing"],
            vis_prof["color_style"],
            aud_prof["music_style"],
        ]
    )
    if sub_clean:
        auto_tags.add(sub_clean)
    if tags:
        for t in tags:
            clean_t = t.strip().lower()
            if clean_t:
                auto_tags.add(clean_t)

    for t in sorted(auto_tags):
        db.add(AssetTag(asset_id=asset.id, tag=t[:64]))

    db.commit()
    db.refresh(asset)
    return asset


def search_references(
    db: Session,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    tags: Optional[List[str]] = None,
    query: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    pacing: Optional[str] = None,
    color_style: Optional[str] = None,
    min_duration: Optional[float] = None,
    max_duration: Optional[float] = None,
    target_embedding: Optional[List[float]] = None,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """Configurable Top-K reference retrieval engine with multi-criteria scoring."""
    q = db.query(ReferenceAsset).filter(ReferenceAsset.analysis_status == "completed")

    if min_duration is not None:
        q = q.filter(ReferenceAsset.duration >= min_duration)
    if max_duration is not None:
        q = q.filter(ReferenceAsset.duration <= max_duration)

    candidates = q.all()
    scored: List[tuple[float, ReferenceAsset]] = []

    cat_norm = storage_manager.sanitize_category(category) if category else None
    sub_norm = storage_manager.sanitize_category(subcategory) if subcategory else None
    req_tags = {t.strip().lower() for t in (tags or []) if t.strip()}
    q_words = [w.lower() for w in (query or "").split() if len(w) > 1]

    for asset in candidates:
        score = 1.0
        analysis = asset.analysis
        asset_tags = {t.tag.lower() for t in asset.tags}

        if cat_norm and cat_norm != "all":
            if asset.category == cat_norm:
                score += 4.0
            elif cat_norm in asset_tags:
                score += 2.0
            else:
                score -= 1.5

        if sub_norm:
            if asset.subcategory == sub_norm or sub_norm in asset_tags:
                score += 2.5

        if aspect_ratio and asset.aspect_ratio == aspect_ratio:
            score += 2.0

        if analysis:
            if pacing and analysis.pacing.lower() == pacing.lower():
                score += 1.5
            if color_style and analysis.color_style.lower() == color_style.lower():
                score += 1.5
            if target_embedding and analysis.embedding_json:
                sim = cosine_similarity(target_embedding, analysis.embedding_json)
                score += sim * 2.0

        if req_tags:
            matched_tags = len(req_tags.intersection(asset_tags))
            score += matched_tags * 1.2

        if q_words:
            haystack = f"{asset.title} {asset.description or ''} {asset.category} {asset.subcategory or ''} {' '.join(asset_tags)}".lower()
            for w in q_words:
                if w in haystack:
                    score += 1.5

        scored.append((round(score, 4), asset))

    scored.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
    top_items = scored[: max(1, min(top_k, 50))]

    results = []
    for sc, asset in top_items:
        serialized = serialize_reference_asset(asset)
        serialized["relevance_score"] = sc
        results.append(serialized)
    return results


def promote_project_video_to_library(
    db: Session,
    project: Project,
    category: str,
    subcategory: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
    license_info: str = "Creator Authorized Reuse",
    confirm_consent: bool = False,
) -> ReferenceAsset:
    """Explicitly promote a customer project's video to the shared reference library after consent."""
    if not confirm_consent:
        raise ValueError("Explicit owner consent is required before promoting a private video to the shared library.")

    # Prefer final rendered output if available, otherwise source upload
    source_path: Optional[Path] = None
    if project.outputs:
        latest_out = sorted(project.outputs, key=lambda o: o.created_at, reverse=True)[0]
        p = storage_manager.resolve_safe_path(latest_out.stored_relpath)
        if p.exists():
            source_path = p

    if not source_path:
        src_file = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project.id, ProjectFile.file_role == "source")
            .first()
        )
        if src_file:
            p = storage_manager.resolve_safe_path(src_file.stored_relpath)
            if p.exists():
                source_path = p

    if not source_path or not source_path.exists():
        raise ValueError("No valid video file found in project to promote.")

    project.allow_library_promotion = True
    asset = ingest_reference_video(
        db=db,
        source_file_path=source_path,
        category=category,
        subcategory=subcategory,
        title=title or f"{project.title} (Promoted)",
        description=f"Promoted from project '{project.title}' with owner consent.",
        tags=tags or [category, project.visual_style],
        source_info=f"promoted_project:{project.id}",
        license_info=license_info,
        promoted_from_project_id=project.id,
        move_file=False,
    )
    return asset


def create_synthetic_reference_clip(
    output_path: Path,
    duration: float = 6.0,
    width: int = 1080,
    height: int = 1920,
    color1: str = "0x1a3a2a",
    color2: str = "0x2d5a40",
    label: str = "Wildlife Reference",
) -> Path:
    """Create a multi-scene sample reference clip with FFmpeg for categories without local media."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    seg = round(duration / 2.0, 2)
    cmd = [
        settings.FFMPEG_PATH,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color1}:s={width}x{height}:r=30:d={seg}",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=s={width}x{height}:r=30:d={seg}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:sample_rate=44100:duration={duration}",
        "-filter_complex",
        f"[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p[v];[2:a]volume=0.15[a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    return output_path


def seed_initial_reference_library(db: Session) -> int:
    """Seed the reference library from ~/Video_Tools/refvideos/references and create baseline animal/nature references."""
    existing_count = db.query(ReferenceAsset).count()
    if existing_count > 0:
        return existing_count

    seeded = 0
    ref_dir = settings.VIDEO_TOOLS_REFVIDEOS_DIR / "references"
    seed_mappings = [
        (
            ref_dir / "sample_business_reel.mp4",
            "business",
            None,
            "Executive Business Reel Reference",
            "High-retention vertical business explainer with dynamic pacing, hook captions, and structured scene transitions.",
            ["business", "explainer", "vertical", "hook", "captions"],
        ),
        (
            ref_dir / "sample_cinematic_reel.mp4",
            "cinematic",
            None,
            "Cinematic Storytelling Reel Reference",
            "Atmospheric vertical cinematic reel with dramatic color grading and narrative pacing.",
            ["cinematic", "storytelling", "dramatic", "vertical"],
        ),
        (
            ref_dir / "sample_screen_walkthrough.mp4",
            "technology",
            None,
            "Product Walkthrough & Screencast Reference",
            "16:9 landscape desktop walkthrough demonstrating clean UI pacing and tutorial structure.",
            ["technology", "walkthrough", "screencast", "landscape", "tutorial"],
        ),
    ]

    for path, cat, subcat, title, desc, tags in seed_mappings:
        if path.exists():
            try:
                ingest_reference_video(
                    db=db,
                    source_file_path=path,
                    category=cat,
                    subcategory=subcat,
                    title=title,
                    description=desc,
                    tags=tags,
                    source_info="Video_Tools/refvideos",
                    license_info="Local Authorized Reference",
                    move_file=False,
                )
                seeded += 1
            except Exception:
                db.rollback()

    # Also seed an authorized local Animals -> Lions reference clip so Mode A/B Animal workflows work out of the box
    temp_lion = storage_manager.temporary_dir / "seed_animal_lions_cinematic.mp4"
    create_synthetic_reference_clip(
        temp_lion,
        duration=6.0,
        width=1080,
        height=1920,
        color1="0x3b2818",
        color2="0x6e4720",
        label="Lions Wildlife Reel",
    )
    if temp_lion.exists():
        try:
            ingest_reference_video(
                db=db,
                source_file_path=temp_lion,
                category="animals",
                subcategory="lions",
                title="African Lions Cinematic Wildlife Reel",
                description="Fast-paced vertical wildlife reference featuring close-up and wide savannah shots with dramatic pacing.",
                tags=["animals", "lions", "wildlife", "savannah", "cinematic", "nature"],
                source_info="Unico Local Seed Library",
                license_info="CC0 / Public Domain Seed",
                move_file=True,
            )
            seeded += 1
        except Exception:
            db.rollback()
            temp_lion.unlink(missing_ok=True)

    return seeded
