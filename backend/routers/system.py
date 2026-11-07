"""System Health, Capabilities, Templates & Settings Router."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.auth import get_current_user
from backend.config import detect_lan_ip, settings
from backend.database import get_db
from backend.models import GenerationTemplate, Job, Project, ReferenceAsset, SystemSetting, User
from backend.schemas import SettingsUpdateRequest
from backend.services.generation_engine import seed_generation_templates
from backend.services.providers import get_provider_capabilities
from backend.services.storage_manager import storage_manager
from backend.services.worker import job_worker

router = APIRouter(prefix="/api", tags=["System"])


def _get_tool_version(cmd_path: str, version_arg: str = "-version") -> dict:
    path = shutil.which(cmd_path) or (cmd_path if Path(cmd_path).exists() else None)
    if not path:
        return {"installed": False, "path": None, "version": None}
    try:
        proc = subprocess.run(
            [path, version_arg],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        out = (proc.stdout or proc.stderr or "").strip().splitlines()
        ver_line = out[0][:120] if out else "Installed"
        return {"installed": True, "path": str(path), "version": ver_line}
    except Exception as exc:
        return {"installed": True, "path": str(path), "version": f"Available ({exc})"}


@router.get("/system/health")
def system_health(db: Session = Depends(get_db)):
    storage_stats = storage_manager.get_storage_stats()
    queued_jobs = db.query(Job).filter(Job.status == "queued").count()
    running_jobs = db.query(Job).filter(Job.status == "running").count()
    completed_jobs = db.query(Job).filter(Job.status == "completed").count()
    failed_jobs = db.query(Job).filter(Job.status == "failed").count()
    ref_count = db.query(ReferenceAsset).count()
    proj_count = db.query(Project).count()

    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)

    return {
        "status": "healthy",
        "service": "Unico Open-Source AI Video Platform",
        "version": "1.0.0",
        "network": {
            "bind_host": settings.UNICO_HOST,
            "port": settings.UNICO_PORT,
            "lan_ip": detect_lan_ip(),
            "lan_url": f"http://{detect_lan_ip()}:{settings.UNICO_PORT}",
        },
        "worker": {
            "running": job_worker.is_running,
            "concurrency": settings.UNICO_WORKER_CONCURRENCY,
            "active_job_id": job_worker.active_job_id,
        },
        "counts": {
            "reference_assets": ref_count,
            "projects": proj_count,
            "jobs_queued": queued_jobs,
            "jobs_running": running_jobs,
            "jobs_completed": completed_jobs,
            "jobs_failed": failed_jobs,
        },
        "system": {
            "os": f"{platform.system()} {platform.release()}",
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count() or 1,
            "load_average_1m": round(load_avg[0], 2),
        },
        "storage": storage_stats,
    }


@router.get("/system/capabilities")
def system_capabilities():
    ffmpeg_info = _get_tool_version(settings.FFMPEG_PATH, "-version")
    ffprobe_info = _get_tool_version(settings.FFPROBE_PATH, "-version")
    melt_info = _get_tool_version(settings.MELT_PATH, "-version")
    shotcut_info = _get_tool_version(settings.SHOTCUT_PATH, "--version")

    remotion_bin = settings.REMOTION_PROJECT_DIR / "node_modules" / ".bin" / "remotion"
    remotion_pkg = settings.REMOTION_PROJECT_DIR / "package.json"
    recordly_pkg = settings.RECORDLY_PROJECT_DIR / "package.json"

    return {
        "tools": {
            "ffmpeg": {
                **ffmpeg_info,
                "role": "Primary backend rendering, trimming, scaling, audio mixing & subtitle engine",
                "mandatory": True,
            },
            "ffprobe": {
                **ffprobe_info,
                "role": "Media stream validation & metadata inspection engine",
                "mandatory": True,
            },
            "melt": {
                **melt_info,
                "role": "Optional MLT command-line timeline composition backend",
                "mandatory": False,
            },
            "remotion": {
                "installed": remotion_bin.exists() or remotion_pkg.exists(),
                "path": str(settings.REMOTION_PROJECT_DIR),
                "version": "Remotion 4.0.x (Local Project Dependency)",
                "role": "Programmatic React motion graphics & animated composition engine",
                "mandatory": False,
            },
            "shotcut": {
                **shotcut_info,
                "role": "Desktop GUI Non-Linear Editor for optional manual timeline refinement",
                "mandatory": False,
            },
            "recordly": {
                "installed": recordly_pkg.exists(),
                "path": str(settings.RECORDLY_PROJECT_DIR),
                "version": "Recordly 1.4.0 (Desktop Screen Recording Studio Project)",
                "role": "Optional creator screen recording & annotation application (not a headless backend renderer)",
                "mandatory": False,
            },
        },
        "rendering_engines": ["ffmpeg", "remotion", "melt"],
        "default_rendering_engine": "ffmpeg",
        "providers": get_provider_capabilities(),
    }


@router.get("/templates")
def list_generation_templates(db: Session = Depends(get_db)):
    seed_generation_templates(db)
    templates = db.query(GenerationTemplate).order_by(GenerationTemplate.name.asc()).all()
    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category,
                "description": t.description,
                "aspect_ratio": t.aspect_ratio,
                "default_duration": t.default_duration,
                "visual_style": t.visual_style,
                "structure": t.structure_json,
            }
            for t in templates
        ]
    }


@router.get("/system/settings")
def get_system_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.query(SystemSetting).all()
    custom = {r.key: r.value_json for r in rows}
    defaults = {
        "worker_concurrency": settings.UNICO_WORKER_CONCURRENCY,
        "preview_resolution": settings.UNICO_PREVIEW_RESOLUTION,
        "max_upload_size_mb": settings.UNICO_MAX_UPLOAD_SIZE_MB,
        "cleanup_temp_hours": settings.UNICO_CLEANUP_TEMP_HOURS,
        "default_rendering_engine": "ffmpeg",
        "require_auth": settings.UNICO_REQUIRE_AUTH,
    }
    defaults.update(custom)
    return {"settings": defaults}


@router.put("/system/settings")
def update_system_settings(
    payload: SettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for k, v in payload.settings.items():
        row = db.query(SystemSetting).filter(SystemSetting.key == k).first()
        if row:
            row.value_json = v
        else:
            db.add(SystemSetting(key=k, value_json=v))
    db.commit()
    return get_system_settings(db=db, current_user=current_user)


@router.post("/system/cleanup")
def trigger_cleanup(current_user: User = Depends(get_current_user)):
    res = storage_manager.cleanup_temporary_files(max_age_hours=0.0)
    return {"cleaned": True, **res}


@router.get("/system/onboarding")
def get_onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.query(SystemSetting).filter(SystemSetting.key == "onboarding_complete").first()
    is_complete = bool(row.value_json) if row is not None else False
    assets = db.query(ReferenceAsset).all()
    ref_count = len(assets)
    cat_counts: dict[str, int] = {}
    for a in assets:
        cat_counts[a.category] = cat_counts.get(a.category, 0) + 1
    categories = storage_manager.list_categories()
    return {
        "onboarding_complete": is_complete,
        "reference_count": ref_count,
        "should_show_onboarding": (not is_complete) or (ref_count == 0),
        "categories": categories,
        "category_counts": cat_counts,
    }


@router.put("/system/onboarding")
def update_onboarding_status(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    completed_val = bool(payload.get("onboarding_complete", True))
    row = db.query(SystemSetting).filter(SystemSetting.key == "onboarding_complete").first()
    if row:
        row.value_json = completed_val
    else:
        db.add(SystemSetting(key="onboarding_complete", value_json=completed_val))
    db.commit()
    return get_onboarding_status(db=db, current_user=current_user)
