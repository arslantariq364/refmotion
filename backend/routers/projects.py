"""Projects Router: Mode A (Reference-Based Video Editing) & Mode B (AI Video Generation)."""
from __future__ import annotations

import shutil
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from backend.auth import get_current_user
from backend.database import get_db
from backend.models import (
    EditingTimeline,
    Job,
    JobEvent,
    Project,
    ProjectFile,
    ReferenceAsset,
    RenderOutput,
    User,
)
from backend.schemas import (
    ProjectCreateRequest,
    ProjectEditRequest,
    ProjectGenerateRequest,
    PromoteProjectRequest,
)
from backend.services.editing_planner import build_editing_timeline
from backend.services.generation_engine import build_generation_timeline, infer_topic_routing
from backend.services.media_inspector import MediaInspectionError, inspect_video_file
from backend.services.providers import VOICE_PRESETS, generate_creative_script
from backend.services.reference_library import (
    DuplicateAssetError,
    ingest_reference_video,
    promote_project_video_to_library,
    resolve_matching_reference_directory,
    serialize_reference_asset,
)
from backend.services.storage_manager import storage_manager
from backend.services.video_analyzer import extract_frame_at
from backend.services.worker import execute_job_by_id

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def serialize_project(project: Project) -> Dict[str, Any]:
    files_list = [
        {
            "id": pf.id,
            "file_role": pf.file_role,
            "original_filename": pf.original_filename,
            "file_size_bytes": pf.file_size_bytes,
            "duration": pf.duration,
            "width": pf.width,
            "height": pf.height,
            "resolution": f"{pf.width}x{pf.height}" if pf.width and pf.height else None,
            "fps": pf.fps,
            "aspect_ratio": pf.aspect_ratio,
            "video_codec": pf.video_codec,
            "audio_codec": pf.audio_codec,
            "has_audio": pf.has_audio,
            "video_url": f"/api/media/{pf.stored_relpath}",
            "thumbnail_url": f"/api/media/{pf.thumbnail_relpath}" if pf.thumbnail_relpath else None,
            "created_at": pf.created_at.isoformat() if pf.created_at else None,
        }
        for pf in sorted(project.files, key=lambda x: x.created_at)
    ]

    timelines_list = [
        {
            "id": tl.id,
            "version": tl.version,
            "duration": tl.duration,
            "aspect_ratio": tl.aspect_ratio,
            "resolution": tl.resolution,
            "fps": tl.fps,
            "edl": tl.edl_json,
            "timeline": tl.timeline_json,
            "planner_notes": tl.planner_notes,
            "created_at": tl.created_at.isoformat() if tl.created_at else None,
        }
        for tl in sorted(project.timelines, key=lambda x: x.version, reverse=True)
    ]

    outputs_list = [
        {
            "id": out.id,
            "timeline_id": out.timeline_id,
            "job_id": out.job_id,
            "output_type": out.output_type,
            "rendering_engine": out.rendering_engine,
            "video_url": f"/api/media/{out.stored_relpath}",
            "download_url": f"/api/media/{out.stored_relpath}?download=1",
            "preview_url": f"/api/media/{out.preview_relpath}" if out.preview_relpath else f"/api/media/{out.stored_relpath}",
            "thumbnail_url": f"/api/media/{out.thumbnail_relpath}" if out.thumbnail_relpath else None,
            "file_size_bytes": out.file_size_bytes,
            "duration": out.duration,
            "width": out.width,
            "height": out.height,
            "resolution": f"{out.width}x{out.height}",
            "fps": out.fps,
            "video_codec": out.video_codec,
            "audio_codec": out.audio_codec,
            "is_valid": out.is_valid,
            "created_at": out.created_at.isoformat() if out.created_at else None,
        }
        for out in sorted(project.outputs, key=lambda x: x.created_at, reverse=True)
    ]

    jobs_list = [
        {
            "id": j.id,
            "job_type": j.job_type,
            "status": j.status,
            "stage": j.stage,
            "progress_percent": j.progress_percent,
            "rendering_engine": j.rendering_engine,
            "error_message": j.error_message,
            "processing_duration_sec": j.processing_duration_sec,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in sorted(project.jobs, key=lambda x: x.created_at, reverse=True)
    ]

    return {
        "id": project.id,
        "title": project.title,
        "mode": project.mode,
        "category": project.category,
        "target_duration": project.target_duration,
        "aspect_ratio": project.aspect_ratio,
        "target_platform": project.target_platform,
        "instructions": project.instructions,
        "topic": project.topic,
        "script_text": project.script_text,
        "visual_style": project.visual_style,
        "target_audience": project.target_audience,
        "captions_enabled": project.captions_enabled,
        "caption_text": project.caption_text,
        "music_preference": project.music_preference,
        "voiceover_preference": project.voiceover_preference,
        "language": project.language,
        "video_quality": project.video_quality,
        "editing_intensity": project.editing_intensity,
        "selected_reference_id": project.selected_reference_id,
        "selected_reference": serialize_reference_asset(project.selected_reference)
        if project.selected_reference
        else None,
        "status": project.status,
        "is_private": project.is_private,
        "allow_library_promotion": project.allow_library_promotion,
        "source_analysis": project.source_analysis_json,
        "files": files_list,
        "timelines": timelines_list,
        "outputs": outputs_list,
        "jobs": jobs_list,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.selected_reference_id:
        ref = db.query(ReferenceAsset).filter(ReferenceAsset.id == payload.selected_reference_id).first()
        if not ref:
            raise HTTPException(status_code=404, detail="Selected reference asset not found")

    project = Project(
        user_id=current_user.id,
        title=payload.title.strip(),
        mode=payload.mode,
        category=storage_manager.sanitize_category(payload.category),
        target_duration=payload.target_duration,
        aspect_ratio=payload.aspect_ratio,
        target_platform=payload.target_platform,
        instructions=payload.instructions or "",
        topic=payload.topic or "",
        script_text=payload.script_text or "",
        visual_style=payload.visual_style,
        target_audience=payload.target_audience or "general",
        captions_enabled=payload.captions_enabled,
        caption_text=payload.caption_text,
        music_preference=payload.music_preference,
        voiceover_preference=payload.voiceover_preference,
        language=payload.language,
        video_quality=payload.video_quality,
        editing_intensity=payload.editing_intensity,
        selected_reference_id=payload.selected_reference_id,
        allow_library_promotion=payload.allow_library_promotion,
        status="draft",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    storage_manager.ensure_project_dirs(project.id)
    return serialize_project(project)


@router.get("")
def list_projects(
    mode: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Project)
    if mode:
        q = q.filter(Project.mode == mode)
    if status_filter:
        q = q.filter(Project.status == status_filter)
    projects = q.order_by(Project.created_at.desc()).all()
    return {"projects": [serialize_project(p) for p in projects], "total": len(projects)}


@router.get("/{project_id}")
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return serialize_project(project)


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    proj_dir = storage_manager.customer_projects_dir / project.id
    db.delete(project)
    db.commit()
    if proj_dir.exists() and str(proj_dir.resolve()).startswith(str(storage_manager.customer_projects_dir)):
        shutil.rmtree(proj_dir, ignore_errors=True)
    return {"deleted": True, "project_id": project_id}


async def _handle_project_video_upload(
    project: Project,
    file_role: str,
    file: UploadFile,
    db: Session,
) -> Dict[str, Any]:
    proj_dir = storage_manager.ensure_project_dirs(project.id)
    target_subdir = proj_dir / ("input" if file_role == "source" else "reference")

    saved_path, sha256, total_bytes, orig_name = await storage_manager.save_upload_stream(
        upload=file,
        dest_dir=target_subdir,
        prefix=file_role,
    )

    try:
        probe = inspect_video_file(saved_path)
    except MediaInspectionError as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    thumb_path = proj_dir / "thumbnails" / f"{file_role}_{sha256[:8]}.jpg"
    extract_frame_at(saved_path, probe["duration"] * 0.25, thumb_path)
    thumb_rel = storage_manager.to_relpath(thumb_path) if thumb_path.exists() else None

    pf = ProjectFile(
        project_id=project.id,
        file_role=file_role,
        original_filename=orig_name,
        stored_relpath=storage_manager.to_relpath(saved_path),
        sha256=sha256,
        file_size_bytes=total_bytes,
        duration=probe["duration"],
        width=probe["width"],
        height=probe["height"],
        fps=probe["fps"],
        aspect_ratio=probe["aspect_ratio"],
        video_codec=probe["video_codec"],
        audio_codec=probe["audio_codec"],
        has_audio=probe["has_audio"],
        thumbnail_relpath=thumb_rel,
        metadata_json=probe,
    )
    db.add(pf)
    if file_role == "source":
        project.source_analysis_json = None

    ingested_asset_dict: Optional[Dict[str, Any]] = None
    if file_role == "reference":
        # Automatically route and store the attached reference video in its matching category directory
        matched_cat, matched_sub = resolve_matching_reference_directory(
            category=project.category,
            filename_or_title=f"{project.title} {project.topic or ''} {orig_name}",
        )
        try:
            ref_asset = ingest_reference_video(
                db=db,
                source_file_path=saved_path,
                category=matched_cat,
                subcategory=matched_sub,
                title=f"{orig_name.rsplit('.', 1)[0].replace('_', ' ').title()}",
                description=f"Attached reference video from project '{project.title}'",
                tags=[matched_cat, project.mode],
                source_info="project_reference_attachment",
                move_file=False,
            )
            project.selected_reference_id = ref_asset.id
            project.category = ref_asset.category
            ingested_asset_dict = serialize_reference_asset(ref_asset)
        except DuplicateAssetError as dup:
            existing_ref = db.query(ReferenceAsset).filter(ReferenceAsset.id == dup.existing_asset_id).first()
            if existing_ref:
                project.selected_reference_id = existing_ref.id
                project.category = existing_ref.category
                ingested_asset_dict = serialize_reference_asset(existing_ref)
        except Exception:
            pass

    project.status = "uploaded"
    db.commit()
    db.refresh(pf)

    return {
        "file_id": pf.id,
        "project_id": project.id,
        "file_role": pf.file_role,
        "original_filename": pf.original_filename,
        "file_size_bytes": pf.file_size_bytes,
        "duration": pf.duration,
        "width": pf.width,
        "height": pf.height,
        "resolution": f"{pf.width}x{pf.height}",
        "fps": pf.fps,
        "aspect_ratio": pf.aspect_ratio,
        "video_codec": pf.video_codec,
        "audio_codec": pf.audio_codec,
        "has_audio": pf.has_audio,
        "video_url": f"/api/media/{pf.stored_relpath}",
        "thumbnail_url": f"/api/media/{pf.thumbnail_relpath}" if pf.thumbnail_relpath else None,
        "ingested_reference_asset": ingested_asset_dict,
    }


@router.post("/{project_id}/upload/source")
async def upload_source_video(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _handle_project_video_upload(project, "source", file, db)


@router.post("/{project_id}/upload/reference")
async def upload_reference_video(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _handle_project_video_upload(project, "reference", file, db)


def _enqueue_job(
    db: Session,
    project: Project,
    job_type: str,
    rendering_engine: str = "ffmpeg",
    payload: Optional[Dict[str, Any]] = None,
    sync: bool = False,
) -> Job:
    job = Job(
        project_id=project.id,
        job_type=job_type,
        status="queued",
        stage="Queued",
        progress_percent=0.0,
        rendering_engine=rendering_engine,
        payload_json=payload or {},
    )
    db.add(job)
    db.flush()
    db.add(
        JobEvent(
            job_id=job.id,
            stage="Queued",
            status="queued",
            message=f"Job '{job_type}' queued for processing",
            progress_percent=0.0,
        )
    )
    project.status = "queued"
    db.commit()
    db.refresh(job)

    if sync:
        execute_job_by_id(job.id)
        db.expire_all()
        job = db.query(Job).filter(Job.id == job.id).first()

    return job


@router.post("/{project_id}/analyze")
def analyze_project_endpoint(
    project_id: str,
    sync: bool = Query(default=False, description="Execute synchronously and wait for completion"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    src_exists = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project.id, ProjectFile.file_role == "source")
        .first()
    )
    if not src_exists:
        raise HTTPException(status_code=400, detail="Please upload a raw source video before analyzing")

    job = _enqueue_job(db, project, job_type="analyze_project", sync=sync)
    return {
        "job_id": job.id,
        "project_id": project.id,
        "status": job.status,
        "stage": job.stage,
        "progress_percent": job.progress_percent,
        "result": job.result_json,
    }


@router.post("/{project_id}/edit")
def start_edit_job(
    project_id: str,
    payload: Optional[ProjectEditRequest] = None,
    sync: bool = Query(default=False, description="Execute synchronously and wait for completion"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    src_exists = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project.id, ProjectFile.file_role == "source")
        .first()
    )
    if not src_exists:
        raise HTTPException(status_code=400, detail="Please upload a raw source video before starting an edit job")

    engine_name = "ffmpeg"
    if payload:
        if payload.selected_reference_id is not None:
            project.selected_reference_id = payload.selected_reference_id
        if payload.instructions is not None:
            project.instructions = payload.instructions
        if payload.target_duration is not None:
            project.target_duration = payload.target_duration
        if payload.aspect_ratio is not None:
            project.aspect_ratio = payload.aspect_ratio
        if payload.target_platform is not None:
            project.target_platform = payload.target_platform
        if payload.captions_enabled is not None:
            project.captions_enabled = payload.captions_enabled
        if payload.caption_text is not None:
            project.caption_text = payload.caption_text
        if payload.music_preference is not None:
            project.music_preference = payload.music_preference
        if payload.video_quality is not None:
            project.video_quality = payload.video_quality
        if payload.editing_intensity is not None:
            project.editing_intensity = payload.editing_intensity
        engine_name = payload.rendering_engine
        db.commit()

    job = _enqueue_job(db, project, job_type="edit_video", rendering_engine=engine_name, sync=sync)
    return {
        "job_id": job.id,
        "project_id": project.id,
        "status": job.status,
        "stage": job.stage,
        "progress_percent": job.progress_percent,
        "result": job.result_json,
    }


@router.post("/{project_id}/generate")
def start_generate_job(
    project_id: str,
    payload: Optional[ProjectGenerateRequest] = None,
    sync: bool = Query(default=False, description="Execute synchronously and wait for completion"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.mode = "generate"
    engine_name = "ffmpeg"
    job_payload: Dict[str, Any] = {}

    if payload:
        if payload.topic is not None:
            project.topic = payload.topic
        if payload.script_text is not None:
            project.script_text = payload.script_text
        if payload.category is not None:
            project.category = storage_manager.sanitize_category(payload.category)
        if payload.selected_reference_id is not None:
            project.selected_reference_id = payload.selected_reference_id
        if payload.target_duration is not None:
            project.target_duration = payload.target_duration
        if payload.aspect_ratio is not None:
            project.aspect_ratio = payload.aspect_ratio
        if payload.visual_style is not None:
            project.visual_style = payload.visual_style
        if payload.target_audience is not None:
            project.target_audience = payload.target_audience
        if payload.voiceover_preference is not None:
            project.voiceover_preference = payload.voiceover_preference
        if payload.music_preference is not None:
            project.music_preference = payload.music_preference
        if payload.language is not None:
            project.language = payload.language
        if payload.captions_enabled is not None:
            project.captions_enabled = payload.captions_enabled
        if payload.template_id:
            job_payload["template_id"] = payload.template_id
        engine_name = payload.rendering_engine
        db.commit()

    job = _enqueue_job(
        db,
        project,
        job_type="generate_video",
        rendering_engine=engine_name,
        payload=job_payload,
        sync=sync,
    )
    return {
        "job_id": job.id,
        "project_id": project.id,
        "status": job.status,
        "stage": job.stage,
        "progress_percent": job.progress_percent,
        "result": job.result_json,
    }


@router.post("/{project_id}/regenerate-timeline")
def regenerate_timeline_only(
    project_id: str,
    payload: Optional[ProjectEditRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate a new versioned timeline without repeating reference ingestion."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload:
        if payload.instructions is not None:
            project.instructions = payload.instructions
        if payload.target_duration is not None:
            project.target_duration = payload.target_duration
        if payload.aspect_ratio is not None:
            project.aspect_ratio = payload.aspect_ratio
        if payload.editing_intensity is not None:
            project.editing_intensity = payload.editing_intensity
        if payload.selected_reference_id is not None:
            project.selected_reference_id = payload.selected_reference_id
        db.commit()

    if project.mode == "generate":
        tl = build_generation_timeline(db=db, project=project)
    else:
        source_file = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project.id, ProjectFile.file_role == "source")
            .order_by(ProjectFile.created_at.desc())
            .first()
        )
        if not source_file:
            raise HTTPException(status_code=400, detail="No source video uploaded")
        ref_style = {}
        ref_asset = None
        if project.selected_reference_id:
            ref_asset = db.query(ReferenceAsset).filter(ReferenceAsset.id == project.selected_reference_id).first()
            if ref_asset and ref_asset.analysis:
                ref_style = ref_asset.analysis.style_profile_json
        tl = build_editing_timeline(
            db=db,
            project=project,
            source_file=source_file,
            source_analysis=project.source_analysis_json or {},
            reference_style_profile=ref_style,
            reference_asset=ref_asset,
        )

    return {
        "timeline_id": tl.id,
        "version": tl.version,
        "duration": tl.duration,
        "aspect_ratio": tl.aspect_ratio,
        "resolution": tl.resolution,
        "edl": tl.edl_json,
        "timeline": tl.timeline_json,
        "planner_notes": tl.planner_notes,
    }


@router.post("/{project_id}/promote")
def promote_project_endpoint(
    project_id: str,
    payload: PromoteProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        asset = promote_project_video_to_library(
            db=db,
            project=project,
            category=payload.category,
            subcategory=payload.subcategory,
            title=payload.title,
            tags=payload.tags,
            license_info=payload.license_info,
            confirm_consent=payload.confirm_consent,
        )
        return serialize_reference_asset(asset)
    except DuplicateAssetError as dup:
        raise HTTPException(status_code=409, detail=str(dup))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.get("/meta/voices")
def list_neural_voices():
    """Return available local neural ONNX TTS voices (Kokoro-82M & Piper)."""
    return {
        "voices": [
            {"id": k, **v} for k, v in VOICE_PRESETS.items()
        ]
    }


@router.post("/meta/auto-script")
def generate_auto_script_endpoint(
    payload: Dict[str, Any],
):
    """Generate a creative, topic-aware narration script and scene lines for Mode B."""
    topic = str(payload.get("topic") or "Cats & Playful Kittens")
    category = str(payload.get("category") or "animals")
    duration = float(payload.get("target_duration") or 15.0)
    inferred_cat, inferred_sub, tags = infer_topic_routing(category, topic, "")
    bundle = generate_creative_script(
        topic=topic,
        script_text="",
        category=inferred_cat,
        target_duration=duration,
        num_scenes=4,
    )
    return {
        "topic": topic,
        "inferred_category": inferred_cat,
        "inferred_subcategory": inferred_sub,
        "priority_tags": tags,
        "narration_script": bundle["narration_script"],
        "scene_lines": bundle["scene_lines"],
        "captions": bundle["captions"],
    }
