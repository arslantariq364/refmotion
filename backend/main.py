"""Unico FastAPI Application Entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from backend.auth import ensure_default_admin
from backend.config import BASE_DIR, settings
from backend.database import Base, SessionLocal, engine
from backend.routers import auth, jobs, projects, reference_library, system
from backend.services.generation_engine import seed_generation_templates
from backend.services.reference_library import seed_initial_reference_library
from backend.services.storage_manager import storage_manager
from backend.services.worker import job_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage_manager.initialize_storage()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_default_admin(db)
        seed_generation_templates(db)
        import os
        if not os.environ.get("UNICO_SKIP_STARTUP_SEED"):
            seed_initial_reference_library(db)
    finally:
        db.close()
    job_worker.start()
    yield
    job_worker.stop()


app = FastAPI(
    title="RefMotion — Open-Source AI Reference-Based Video & Motion Studio",
    description=(
        "Reference-based intelligent video editing (Mode A) and authorized local asset "
        "video generation (Mode B) with FFmpeg, FFprobe, Remotion, MLT, and Neural TTS integration."
    ),
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(jobs.router)
app.include_router(reference_library.router)
app.include_router(system.router)


@app.get("/api/media/{relpath:path}", tags=["Media"])
def serve_safe_media(
    relpath: str,
    download: Optional[int] = Query(default=0),
):
    """Safely stream media files stored inside the Unico storage hierarchy without exposing raw host paths."""
    full_path = storage_manager.resolve_safe_path(relpath)
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{full_path.name}"'
    return FileResponse(path=str(full_path), headers=headers)


FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend_assets")


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def serve_spa(full_path: str):
    if full_path.startswith("api/") or ".." in full_path or full_path.startswith("etc/"):
        raise HTTPException(status_code=404, detail="Endpoint not found")
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and str(candidate).startswith(str(FRONTEND_DIST.resolve()))
            and candidate.is_file()
        ):
            return FileResponse(str(candidate))
        if "." in Path(full_path).name:
            raise HTTPException(status_code=404, detail="Static file not found")
        return FileResponse(str(index_file))
    return HTMLResponse(
        content="<h1>Unico Backend Running</h1><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>",
        status_code=200,
    )
