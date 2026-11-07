"""Jobs Router: Queue inspection, live SSE progress streaming, cancellation & deletion."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.auth import get_current_user
from backend.database import SessionLocal, get_db
from backend.models import Job, JobEvent, User
from backend.services.worker import utcnow

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def serialize_job(job: Job) -> Dict[str, Any]:
    events = [
        {
            "id": ev.id,
            "stage": ev.stage,
            "status": ev.status,
            "message": ev.message,
            "progress_percent": ev.progress_percent,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        for ev in sorted(job.events, key=lambda x: x.created_at)
    ]
    return {
        "id": job.id,
        "project_id": job.project_id,
        "project_title": job.project.title if job.project else None,
        "job_type": job.job_type,
        "status": job.status,
        "stage": job.stage,
        "progress_percent": job.progress_percent,
        "rendering_engine": job.rendering_engine,
        "retry_count": job.retry_count,
        "max_retries": job.max_retries,
        "cancel_requested": job.cancel_requested,
        "payload": job.payload_json,
        "result": job.result_json,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "processing_duration_sec": job.processing_duration_sec,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "events": events,
    }


@router.get("")
def list_jobs(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    project_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Job)
    if status_filter:
        q = q.filter(Job.status == status_filter)
    if project_id:
        q = q.filter(Job.project_id == project_id)
    jobs = q.order_by(Job.created_at.desc()).limit(100).all()
    return {"jobs": [serialize_job(j) for j in jobs], "total": len(jobs)}


@router.get("/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize_job(job)


@router.delete("/{job_id}")
def cancel_or_delete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ("queued", "running"):
        job.cancel_requested = True
        job.status = "cancelled"
        job.stage = "Cancelled"
        job.completed_at = utcnow()
        if job.project:
            job.project.status = "cancelled"
        db.add(
            JobEvent(
                job_id=job.id,
                stage="Cancelled",
                status="cancelled",
                message="User requested safe job cancellation",
                progress_percent=job.progress_percent,
            )
        )
        db.commit()
        db.refresh(job)
        return {"cancelled": True, "job": serialize_job(job)}

    db.delete(job)
    db.commit()
    return {"deleted": True, "job_id": job_id}


@router.get("/{job_id}/events/stream")
async def stream_job_events(job_id: str):
    """Server-Sent Events (SSE) endpoint for real-time pipeline stage updates."""
    async def event_generator():
        terminal_states = {"completed", "failed", "cancelled"}
        for _ in range(600):
            db = SessionLocal()
            try:
                job = db.query(Job).filter(Job.id == job_id).first()
                if not job:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break
                payload = serialize_job(job)
                yield f"data: {json.dumps(payload)}\n\n"
                if job.status in terminal_states:
                    break
            finally:
                db.close()
            await asyncio.sleep(0.8)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
