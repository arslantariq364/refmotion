"""Configuration management for Unico Platform."""
from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


def detect_lan_ip() -> str:
    """Detect primary local network IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    UNICO_HOST: str = "0.0.0.0"
    UNICO_PORT: int = 8000
    UNICO_LAN_IP: str = detect_lan_ip()
    UNICO_ENV: str = "development"

    UNICO_SECRET_KEY: str = "unico-local-hmac-key-9f8e7d6c5b4a3f2e1d"
    UNICO_DEFAULT_ADMIN_USER: str = "creator"
    UNICO_DEFAULT_ADMIN_PASSWORD: str = "unico-local-studio"
    UNICO_REQUIRE_AUTH: bool = False

    UNICO_STORAGE_ROOT: Path = BASE_DIR / "storage"
    UNICO_DATABASE_URL: Optional[str] = None
    UNICO_MAX_UPLOAD_SIZE_MB: int = 500
    UNICO_CLEANUP_TEMP_HOURS: int = 24

    UNICO_WORKER_CONCURRENCY: int = 1
    UNICO_WORKER_POLL_INTERVAL_SEC: float = 1.0
    UNICO_PREVIEW_RESOLUTION: int = 720
    UNICO_FFMPEG_THREADS: int = 4
    UNICO_SUBPROCESS_TIMEOUT_SEC: int = 600

    FFMPEG_PATH: str = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    FFPROBE_PATH: str = shutil.which("ffprobe") or "/usr/bin/ffprobe"
    MELT_PATH: str = shutil.which("melt") or "/usr/bin/melt"
    SHOTCUT_PATH: str = shutil.which("shotcut") or "/usr/bin/shotcut"
    REMOTION_PROJECT_DIR: Path = Path("/home/arslan-tariq/launch-video")
    RECORDLY_PROJECT_DIR: Path = Path("/home/arslan-tariq/recordly")
    VIDEO_TOOLS_REFVIDEOS_DIR: Path = Path("/home/arslan-tariq/Video_Tools/refvideos")

    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""
    COMFYUI_BASE_URL: str = "http://127.0.0.1:8188"
    WHISPER_LOCAL_MODEL_PATH: str = ""
    PIPER_TTS_MODEL_PATH: str = ""

    @property
    def db_url(self) -> str:
        if self.UNICO_DATABASE_URL:
            return self.UNICO_DATABASE_URL
        db_file = self.UNICO_STORAGE_ROOT / "database" / "unico.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_file}"


settings = Settings()
