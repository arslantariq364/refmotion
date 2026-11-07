"""SQLite-Backed Background Job Worker with Pipeline Stage Tracking, Cancellation & Recovery."""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import SessionLocal
from backend.models import (
    EditingTimeline,
    Job,
    JobEvent,
    Project,
    ProjectFile,
    ReferenceAsset,
    RenderOutput,
)
from backend.services.editing_planner import build_editing_timeline
from backend.services.generation_engine import build_generation_timeline
from backend.services.reference_library import search_references
from backend.services.renderer import RenderCancelledError, get_renderer_adapter
from backend.services.storage_manager import storage_manager
from backend.services.video_analyzer import analyze_video_complete


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def record_job_stage(
    db: Session,
    job: Job,
    stage: str,
    progress_percent: float,
    message: str,
    status: Optional[str] = None,
) -> None:
    job.stage = stage
    job.progress_percent = round(float(progress_percent), 1)
    if status:
        job.status = status
    job.updated_at = utcnow()
    event = JobEvent(
        job_id=job.id,
        stage=stage,
        status=job.status,
        message=message,
        progress_percent=job.progress_percent,
    )
    db.add(event)
    db.commit()
    db.refresh(job)


def is_cancel_requested(db: Session, job_id: str) -> bool:
    db.expire_all()
    j = db.query(Job).filter(Job.id == job_id).first()
    return bool(j and (j.cancel_requested or j.status == "cancelled"))


def execute_job_by_id(job_id: str) -> Dict[str, Any]:
    """Execute a queued job end-to-end with real pipeline stages and database transactions."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"error": "Job not found"}
        if job.cancel_requested or job.status == "cancelled":
            record_job_stage(db, job, "Cancelled", job.progress_percent, "Job cancelled before execution", status="cancelled")
            return {"status": "cancelled"}

        start_ts = time.time()
        job.started_at = utcnow()
        record_job_stage(db, job, "Validating", 10.0, "Validating project inputs and media streams", status="running")

        project = db.query(Project).filter(Project.id == job.project_id).first()
        if not project:
            raise ValueError(f"Associated project '{job.project_id}' does not exist")

        project.status = "processing"
        db.commit()

        proj_dir = storage_manager.ensure_project_dirs(project.id)

        if job.job_type in ("analyze_project", "edit_video"):
            # Locate source video
            source_file = (
                db.query(ProjectFile)
                .filter(ProjectFile.project_id == project.id, ProjectFile.file_role == "source")
                .order_by(ProjectFile.created_at.desc())
                .first()
            )
            if not source_file:
                raise ValueError("No raw source video uploaded for this editing project")

            source_path = storage_manager.resolve_safe_path(source_file.stored_relpath)
            if not source_path.exists():
                raise FileNotFoundError(f"Raw source file missing on disk: {source_file.stored_relpath}")

            if is_cancel_requested(db, job.id):
                raise RenderCancelledError("Cancelled during validation")

            # STEP: Analyzing reference
            record_job_stage(db, job, "Analyzing reference", 25.0, "Extracting reference pacing, shot rhythm, and visual style profile")
            reference_style_profile: Dict[str, Any] = {}
            reference_asset: Optional[ReferenceAsset] = None

            if project.selected_reference_id:
                reference_asset = (
                    db.query(ReferenceAsset)
                    .filter(ReferenceAsset.id == project.selected_reference_id)
                    .first()
                )
                if reference_asset and reference_asset.analysis:
                    reference_style_profile = reference_asset.analysis.style_profile_json
                    reference_asset.usage_count = (reference_asset.usage_count or 0) + 1
                    db.commit()

            if not reference_style_profile:
                # Check if user uploaded a custom project-specific reference video
                proj_ref_file = (
                    db.query(ProjectFile)
                    .filter(ProjectFile.project_id == project.id, ProjectFile.file_role == "reference")
                    .order_by(ProjectFile.created_at.desc())
                    .first()
                )
                if proj_ref_file:
                    ref_path = storage_manager.resolve_safe_path(proj_ref_file.stored_relpath)
                    ref_analysis_dir = proj_dir / "analysis" / "reference"
                    ref_bundle = analyze_video_complete(ref_path, ref_analysis_dir, category=project.category)
                    reference_style_profile = ref_bundle["style_profile"]
                else:
                    # Retrieve top matching reference from Reference Library by category
                    matches = search_references(
                        db=db,
                        category=project.category,
                        aspect_ratio=project.aspect_ratio,
                        top_k=1,
                    )
                    if matches and matches[0].get("style_profile"):
                        reference_style_profile = matches[0]["style_profile"]
                        reference_asset = (
                            db.query(ReferenceAsset)
                            .filter(ReferenceAsset.id == matches[0]["id"])
                            .first()
                        )
                        if reference_asset:
                            project.selected_reference_id = reference_asset.id
                            reference_asset.usage_count = (reference_asset.usage_count or 0) + 1
                            db.commit()

            if is_cancel_requested(db, job.id):
                raise RenderCancelledError("Cancelled after reference analysis")

            # STEP: Analyzing source
            record_job_stage(db, job, "Analyzing source", 40.0, "Analyzing customer raw video scenes, motion, and audio envelope")
            if project.source_analysis_json:
                source_analysis = project.source_analysis_json
            else:
                src_analysis_dir = proj_dir / "analysis" / "source"
                source_analysis = analyze_video_complete(source_path, src_analysis_dir, category=project.category)
                project.source_analysis_json = source_analysis
                db.commit()

            if job.job_type == "analyze_project":
                timeline_row = build_editing_timeline(
                    db=db,
                    project=project,
                    source_file=source_file,
                    source_analysis=source_analysis,
                    reference_style_profile=reference_style_profile,
                    reference_asset=reference_asset,
                )
                elapsed = round(time.time() - start_ts, 2)
                job.completed_at = utcnow()
                job.processing_duration_sec = elapsed
                job.result_json = {"timeline_id": timeline_row.id, "version": timeline_row.version}
                project.status = "analyzed"
                record_job_stage(db, job, "Completed", 100.0, "Source & reference analysis completed and timeline generated", status="completed")
                return {"status": "completed", "timeline_id": timeline_row.id}

            # STEP: Creating timeline
            record_job_stage(db, job, "Creating timeline", 50.0, "Building Editing Decision List (EDL) and versioned Timeline JSON")
            timeline_row = build_editing_timeline(
                db=db,
                project=project,
                source_file=source_file,
                source_analysis=source_analysis,
                reference_style_profile=reference_style_profile,
                reference_asset=reference_asset,
            )

        elif job.job_type == "generate_video":
            record_job_stage(db, job, "Analyzing reference", 25.0, "Searching authorized local reference library for category & visual assets")
            if is_cancel_requested(db, job.id):
                raise RenderCancelledError("Cancelled during asset retrieval")

            record_job_stage(db, job, "Creating timeline", 45.0, "Building scene-by-scene storyboard, captions, and audio tracks")
            template_id = (job.payload_json or {}).get("template_id")
            timeline_row = build_generation_timeline(
                db=db,
                project=project,
                template_id=template_id,
            )
        else:
            raise ValueError(f"Unsupported job_type: {job.job_type}")

        if is_cancel_requested(db, job.id):
            raise RenderCancelledError("Cancelled before rendering")

        # STEP: Rendering
        record_job_stage(db, job, "Rendering", 60.0, f"Rendering timeline v{timeline_row.version} via {job.rendering_engine}")
        adapter = get_renderer_adapter(job.rendering_engine)

        def _progress_cb(msg: str, pct: float) -> None:
            record_job_stage(db, job, "Rendering", pct, msg)

        def _cancel_cb() -> bool:
            return is_cancel_requested(db, job.id)

        render_res = adapter.render_timeline(
            project_id=project.id,
            timeline_doc=timeline_row.timeline_json,
            progress_cb=_progress_cb,
            check_cancel_cb=_cancel_cb,
        )

        # STEP: Validating output
        record_job_stage(db, job, "Validating output", 92.0, "Inspecting rendered MP4 streams and metadata with FFprobe")
        val_info = render_res["validation"]

        output_row = RenderOutput(
            project_id=project.id,
            timeline_id=timeline_row.id,
            job_id=job.id,
            output_type="final",
            rendering_engine=render_res["rendering_engine"],
            stored_relpath=render_res["final_relpath"],
            preview_relpath=render_res["preview_relpath"],
            thumbnail_relpath=render_res["thumbnail_relpath"],
            file_size_bytes=val_info["file_size_bytes"],
            duration=val_info["duration"],
            width=val_info["width"],
            height=val_info["height"],
            fps=val_info["fps"],
            video_codec=val_info["video_codec"],
            audio_codec=val_info["audio_codec"],
            is_valid=True,
            validation_report_json=val_info,
        )
        db.add(output_row)
        db.flush()

        elapsed = round(time.time() - start_ts, 2)
        job.completed_at = utcnow()
        job.processing_duration_sec = elapsed
        job.result_json = {
            "output_id": output_row.id,
            "timeline_id": timeline_row.id,
            "timeline_version": timeline_row.version,
            "video_url": f"/api/media/{output_row.stored_relpath}",
            "preview_url": f"/api/media/{output_row.preview_relpath}" if output_row.preview_relpath else None,
            "thumbnail_url": f"/api/media/{output_row.thumbnail_relpath}" if output_row.thumbnail_relpath else None,
            "duration": output_row.duration,
            "resolution": f"{output_row.width}x{output_row.height}",
        }
        project.status = "completed"
        record_job_stage(
            db,
            job,
            "Completed",
            100.0,
            f"Render completed and validated ({output_row.width}x{output_row.height}, {output_row.duration}s) in {elapsed}s",
            status="completed",
        )
        return {"status": "completed", "output_id": output_row.id}

    except RenderCancelledError as cancel_exc:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.completed_at = utcnow()
            if job.project:
                job.project.status = "cancelled"
            record_job_stage(db, job, "Cancelled", job.progress_percent, str(cancel_exc), status="cancelled")
        return {"status": "cancelled"}

    except Exception as exc:
        db.rollback()
        err_msg = f"{type(exc).__name__}: {exc}"
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.error_message = err_msg
            job.completed_at = utcnow()
            if job.project:
                job.project.status = "failed"
            record_job_stage(db, job, "Failed", job.progress_percent, err_msg, status="failed")
        return {"status": "failed", "error": err_msg, "trace": traceback.format_exc()[-400:]}
    finally:
        db.close()


class BackgroundJobWorker:
    """Single-worker background processor polling the SQLite job queue with crash recovery."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.active_job_id: Optional[str] = None

    def recover_interrupted_jobs(self) -> int:
        """Recover jobs left in 'running' state after an unclean shutdown."""
        db = SessionLocal()
        recovered = 0
        try:
            running_jobs = db.query(Job).filter(Job.status == "running").all()
            for j in running_jobs:
                if j.retry_count < j.max_retries and not j.cancel_requested:
                    j.status = "queued"
                    j.stage = "Queued (Recovered)"
                    j.retry_count += 1
                    db.add(
                        JobEvent(
                            job_id=j.id,
                            stage="Queued (Recovered)",
                            status="queued",
                            message=f"Job recovered after server restart (retry {j.retry_count}/{j.max_retries})",
                            progress_percent=0.0,
                        )
                    )
                    recovered += 1
                else:
                    j.status = "failed"
                    j.stage = "Failed"
                    j.error_message = "Interrupted by server shutdown and exceeded retry limit"
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        return recovered

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.recover_interrupted_jobs()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="UnicoJobWorker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            next_job_id: Optional[str] = None
            db = SessionLocal()
            try:
                next_job = (
                    db.query(Job)
                    .filter(Job.status == "queued")
                    .order_by(Job.created_at.asc())
                    .first()
                )
                if next_job:
                    next_job_id = next_job.id
            except Exception:
                pass
            finally:
                db.close()

            if next_job_id:
                self.active_job_id = next_job_id
                try:
                    execute_job_by_id(next_job_id)
                finally:
                    self.active_job_id = None
            else:
                self._stop_event.wait(settings.UNICO_WORKER_POLL_INTERVAL_SEC)


job_worker = BackgroundJobWorker()
