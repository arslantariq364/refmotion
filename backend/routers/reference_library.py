"""Reference Library Router: Ingest, list, dynamic categories, Top-K search & asset management."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from backend.auth import get_current_user
from backend.database import get_db
from backend.models import ReferenceAsset, User
from backend.schemas import ReferenceSearchRequest
from backend.services.media_inspector import MediaInspectionError
from backend.services.reference_library import (
    DuplicateAssetError,
    ingest_reference_video,
    resolve_matching_reference_directory,
    search_references,
    serialize_reference_asset,
)
from backend.services.storage_manager import storage_manager

router = APIRouter(prefix="/api/reference-library", tags=["Reference Library"])


@router.get("")
def list_reference_assets(
    category: Optional[str] = Query(default=None),
    subcategory: Optional[str] = Query(default=None),
    aspect_ratio: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ReferenceAsset)
    if category and category != "all":
        q = q.filter(ReferenceAsset.category == storage_manager.sanitize_category(category))
    if subcategory:
        q = q.filter(ReferenceAsset.subcategory == storage_manager.sanitize_category(subcategory))
    if aspect_ratio:
        q = q.filter(ReferenceAsset.aspect_ratio == aspect_ratio)

    assets = q.order_by(ReferenceAsset.created_at.desc()).all()
    categories = storage_manager.list_categories()

    cat_counts = {}
    for a in db.query(ReferenceAsset).all():
        cat_counts[a.category] = cat_counts.get(a.category, 0) + 1

    return {
        "assets": [serialize_reference_asset(a) for a in assets],
        "total": len(assets),
        "categories": categories,
        "category_counts": cat_counts,
    }


@router.get("/categories")
def get_categories(current_user: User = Depends(get_current_user)):
    return {"categories": storage_manager.list_categories()}


@router.get("/match-category")
def match_reference_category(
    filename: str = Query(default=""),
    category: str = Query(default="animals"),
    current_user: User = Depends(get_current_user),
):
    matched_cat, matched_sub = resolve_matching_reference_directory(
        category=category,
        filename_or_title=filename,
    )
    return {
        "matched_category": matched_cat,
        "matched_subcategory": matched_sub,
    }


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    category: str = Form(...),
    subcategory: Optional[str] = Form(default=None),
    current_user: User = Depends(get_current_user),
):
    target = storage_manager.ensure_reference_category_dir(category, subcategory)
    return {
        "category": storage_manager.sanitize_category(category),
        "subcategory": storage_manager.sanitize_category(subcategory) if subcategory else None,
        "relpath": storage_manager.to_relpath(target),
        "categories": storage_manager.list_categories(),
    }


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_reference_endpoint(
    file: UploadFile = File(...),
    category: str = Form(default="general"),
    subcategory: Optional[str] = Form(default=None),
    title: Optional[str] = Form(default=None),
    description: str = Form(default=""),
    tags: Optional[str] = Form(default=""),
    source_info: str = Form(default="creator_upload"),
    license_info: str = Form(default="Authorized Local Reference"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    temp_path, _, _, orig_name = await storage_manager.save_upload_stream(
        upload=file,
        dest_dir=storage_manager.temporary_dir,
        prefix="ref_ingest",
    )

    tag_list: List[str] = [t.strip() for t in (tags or "").split(",") if t.strip()]

    try:
        asset = ingest_reference_video(
            db=db,
            source_file_path=temp_path,
            category=category,
            subcategory=subcategory,
            title=title or Path(orig_name).stem.replace("_", " ").title(),
            description=description,
            tags=tag_list,
            source_info=source_info,
            license_info=license_info,
            move_file=True,
        )
        return serialize_reference_asset(asset)
    except DuplicateAssetError as dup:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(dup), "existing_asset_id": dup.existing_asset_id},
        )
    except MediaInspectionError as mie:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(mie))
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/search")
def search_reference_library_endpoint(
    payload: ReferenceSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = search_references(
        db=db,
        category=payload.category,
        subcategory=payload.subcategory,
        tags=payload.tags,
        query=payload.query,
        aspect_ratio=payload.aspect_ratio,
        pacing=payload.pacing,
        color_style=payload.color_style,
        min_duration=payload.min_duration,
        max_duration=payload.max_duration,
        top_k=payload.top_k,
    )
    return {"results": results, "count": len(results), "top_k": payload.top_k}


@router.get("/{asset_id}")
def get_reference_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = db.query(ReferenceAsset).filter(ReferenceAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    return serialize_reference_asset(asset)


@router.delete("/{asset_id}")
def delete_reference_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = db.query(ReferenceAsset).filter(ReferenceAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Reference asset not found")

    try:
        video_file = storage_manager.resolve_safe_path(asset.stored_relpath)
        meta_dir = video_file.parent / "_meta" / asset.sha256[:12]
    except Exception:
        video_file = None
        meta_dir = None

    db.delete(asset)
    db.commit()

    if video_file and video_file.exists():
        video_file.unlink(missing_ok=True)
    if meta_dir and meta_dir.exists():
        import shutil
        shutil.rmtree(meta_dir, ignore_errors=True)

    return {"deleted": True, "asset_id": asset_id}
