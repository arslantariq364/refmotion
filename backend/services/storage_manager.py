"""Storage Manager: Structured directories, safe paths, streaming uploads, and disk monitoring."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from backend.config import settings

DEFAULT_REFERENCE_CATEGORIES = {
    "animals": ["cats", "lions", "birds", "wildlife", "pets"],
    "humans": [],
    "nature": [],
    "cinematic": [],
    "business": [],
    "education": [],
    "technology": [],
    "general": [],
}

PROJECT_SUBDIRS = [
    "input",
    "reference",
    "analysis",
    "thumbnails",
    "timeline",
    "previews",
    "output",
    "logs",
]

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


class StorageManager:
    def __init__(self, root: Optional[Path] = None):
        self.root = (root or settings.UNICO_STORAGE_ROOT).resolve()
        self.reference_library_dir = self.root / "reference_library"
        self.customer_projects_dir = self.root / "customer_projects"
        self.generated_content_dir = self.root / "generated_content"
        self.temporary_dir = self.root / "temporary"
        self.database_dir = self.root / "database"

    def initialize_storage(self) -> None:
        """Create the required directory hierarchy."""
        for d in [
            self.reference_library_dir,
            self.customer_projects_dir,
            self.generated_content_dir,
            self.temporary_dir,
            self.database_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
            gitkeep = d / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()

        for category, subcats in DEFAULT_REFERENCE_CATEGORIES.items():
            cat_dir = self.reference_library_dir / self.sanitize_category(category)
            cat_dir.mkdir(parents=True, exist_ok=True)
            for sub in subcats:
                (cat_dir / self.sanitize_category(sub)).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize an uploaded filename to prevent path traversal or shell hazards."""
        base = os.path.basename(filename or "video.mp4")
        name, ext = os.path.splitext(base)
        clean_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name).strip("._")
        if not clean_name:
            clean_name = "media"
        clean_ext = re.sub(r"[^a-zA-Z0-9\.]", "", ext.lower())
        return f"{clean_name[:120]}{clean_ext}"

    @staticmethod
    def sanitize_category(name: str) -> str:
        clean = re.sub(r"[^a-z0-9_\-]", "_", (name or "general").lower().strip()).strip("_")
        return clean or "general"

    def resolve_safe_path(self, relpath: str) -> Path:
        """Resolve a relative path inside storage root and prevent directory traversal."""
        if not relpath or ".." in Path(relpath).parts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage path",
            )
        target = (self.root / relpath).resolve()
        if not str(target).startswith(str(self.root)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access outside storage root is prohibited",
            )
        return target

    def to_relpath(self, full_path: Path) -> str:
        return str(full_path.resolve().relative_to(self.root))

    def ensure_project_dirs(self, project_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", project_id)
        if not safe_id:
            raise ValueError("Invalid project ID")
        proj_root = (self.customer_projects_dir / safe_id).resolve()
        if not str(proj_root).startswith(str(self.customer_projects_dir)):
            raise ValueError("Path traversal detected")
        for sub in PROJECT_SUBDIRS:
            (proj_root / sub).mkdir(parents=True, exist_ok=True)
        return proj_root

    def ensure_reference_category_dir(
        self, category: str, subcategory: Optional[str] = None
    ) -> Path:
        cat_clean = self.sanitize_category(category)
        target = self.reference_library_dir / cat_clean
        if subcategory:
            sub_clean = self.sanitize_category(subcategory)
            target = target / sub_clean
        target.mkdir(parents=True, exist_ok=True)
        return target

    def list_categories(self) -> dict:
        """Dynamically list all categories and subcategories in reference_library."""
        result = {}
        if not self.reference_library_dir.exists():
            return DEFAULT_REFERENCE_CATEGORIES
        for item in sorted(self.reference_library_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                subs = [
                    sub.name
                    for sub in sorted(item.iterdir())
                    if sub.is_dir() and not sub.name.startswith(".") and sub.name != "_meta"
                ]
                result[item.name] = subs
        return result

    async def save_upload_stream(
        self,
        upload: UploadFile,
        dest_dir: Path,
        prefix: str = "",
        max_size_mb: Optional[int] = None,
    ) -> Tuple[Path, str, int, str]:
        """Stream an UploadFile to disk in 1MB chunks while computing SHA-256 and checking limits."""
        orig_name = self.sanitize_filename(upload.filename or "upload.mp4")
        ext = Path(orig_name).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported video file extension '{ext}'. Allowed: {sorted(ALLOWED_VIDEO_EXTENSIONS)}",
            )

        dest_dir.mkdir(parents=True, exist_ok=True)
        final_name = f"{prefix}_{orig_name}" if prefix else orig_name
        dest_path = dest_dir / final_name

        max_bytes = (max_size_mb or settings.UNICO_MAX_UPLOAD_SIZE_MB) * 1024 * 1024
        sha256_hash = hashlib.sha256()
        total_bytes = 0

        try:
            with open(dest_path, "wb") as f:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        f.close()
                        dest_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds maximum allowed size of {max_size_mb or settings.UNICO_MAX_UPLOAD_SIZE_MB} MB",
                        )
                    sha256_hash.update(chunk)
                    f.write(chunk)
        except HTTPException:
            raise
        except Exception as exc:
            dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write uploaded file: {exc}",
            )

        if total_bytes == 0:
            dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes)",
            )

        return dest_path, sha256_hash.hexdigest(), total_bytes, orig_name

    def get_storage_stats(self) -> dict:
        """Compute storage usage per subsystem and overall disk capacity."""
        def dir_size(path: Path) -> int:
            total = 0
            if not path.exists():
                return 0
            for root_p, _, files in os.walk(path):
                for fn in files:
                    fp = Path(root_p) / fn
                    if not fp.is_symlink():
                        try:
                            total += fp.stat().st_size
                        except OSError:
                            pass
            return total

        disk = shutil.disk_usage(self.root if self.root.exists() else Path("/"))
        ref_bytes = dir_size(self.reference_library_dir)
        proj_bytes = dir_size(self.customer_projects_dir)
        gen_bytes = dir_size(self.generated_content_dir)
        temp_bytes = dir_size(self.temporary_dir)
        db_bytes = dir_size(self.database_dir)

        return {
            "storage_root": str(self.root),
            "reference_library_bytes": ref_bytes,
            "customer_projects_bytes": proj_bytes,
            "generated_content_bytes": gen_bytes,
            "temporary_bytes": temp_bytes,
            "database_bytes": db_bytes,
            "total_unico_bytes": ref_bytes + proj_bytes + gen_bytes + temp_bytes + db_bytes,
            "disk_total_bytes": disk.total,
            "disk_used_bytes": disk.used,
            "disk_free_bytes": disk.free,
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        }

    def cleanup_temporary_files(self, max_age_hours: Optional[float] = None) -> dict:
        """Safely delete expired files in storage/temporary."""
        age_limit_sec = (
            max_age_hours if max_age_hours is not None else settings.UNICO_CLEANUP_TEMP_HOURS
        ) * 3600
        now = time.time()
        removed_files = 0
        freed_bytes = 0

        if not self.temporary_dir.exists():
            return {"removed_files": 0, "freed_bytes": 0}

        for item in self.temporary_dir.iterdir():
            if item.name == ".gitkeep":
                continue
            try:
                mtime = item.stat().st_mtime
                if (now - mtime) >= age_limit_sec:
                    if item.is_file() or item.is_symlink():
                        sz = item.stat().st_size
                        item.unlink()
                        removed_files += 1
                        freed_bytes += sz
                    elif item.is_dir():
                        sz = sum(
                            f.stat().st_size for f in item.rglob("*") if f.is_file()
                        )
                        shutil.rmtree(item, ignore_errors=True)
                        removed_files += 1
                        freed_bytes += sz
            except OSError:
                pass

        return {"removed_files": removed_files, "freed_bytes": freed_bytes}


storage_manager = StorageManager()
