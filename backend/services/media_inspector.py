"""Media Inspector: FFprobe validation, stream analysis, SHA-256 & perceptual fingerprinting."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from PIL import Image
import numpy as np
from backend.config import settings


class MediaInspectionError(ValueError):
    """Raised when a media file is invalid, corrupted, or lacks a valid video stream."""


def compute_file_sha256(file_path: Path) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()


def compute_image_dhash(image_path: Path, hash_size: int = 8) -> Optional[str]:
    """Compute a 64-bit difference perceptual hash (dHash) of a frame image."""
    try:
        with Image.open(image_path) as img:
            gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = np.asarray(gray, dtype=np.int16)
            diff = pixels[:, 1:] > pixels[:, :-1]
            bit_string = "".join("1" if b else "0" for b in diff.flatten())
            return f"{int(bit_string, 2):016x}"
    except Exception:
        return None


def classify_aspect_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "16:9"
    ratio = width / height
    if abs(ratio - (9 / 16)) < 0.12 or ratio < 0.75:
        return "9:16"
    if abs(ratio - 1.0) < 0.15:
        return "1:1"
    if abs(ratio - (4 / 5)) < 0.1:
        return "4:5"
    return "16:9"


def parse_fps(r_frame_rate: str) -> float:
    if not r_frame_rate or "/" not in r_frame_rate:
        try:
            return float(r_frame_rate or 30.0)
        except ValueError:
            return 30.0
    num, den = r_frame_rate.split("/", 1)
    try:
        n, d = float(num), float(den)
        if d <= 0:
            return 30.0
        fps = n / d
        return round(min(max(fps, 1.0), 240.0), 2)
    except ValueError:
        return 30.0


def inspect_video_file(file_path: Path) -> Dict[str, Any]:
    """Run FFprobe on a video file and return validated metadata."""
    if not file_path.exists() or not file_path.is_file():
        raise MediaInspectionError(f"Video file does not exist: {file_path.name}")

    file_size = file_path.stat().st_size
    if file_size < 128:
        raise MediaInspectionError(f"File is too small or empty ({file_size} bytes)")

    cmd = [
        settings.FFPROBE_PATH,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(file_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise MediaInspectionError("FFprobe timed out while inspecting media file")
    except Exception as exc:
        raise MediaInspectionError(f"Failed to execute FFprobe: {exc}")

    if proc.returncode != 0 or not proc.stdout.strip():
        err_detail = (proc.stderr or "Corrupted or unsupported media container").strip()[:240]
        raise MediaInspectionError(f"Invalid video file: {err_detail}")

    try:
        probe_data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise MediaInspectionError("FFprobe returned malformed JSON metadata")

    streams = probe_data.get("streams", [])
    fmt = probe_data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise MediaInspectionError("File does not contain a valid video stream")

    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise MediaInspectionError(f"Invalid video dimensions ({width}x{height})")

    duration_raw = (
        video_stream.get("duration")
        or fmt.get("duration")
        or 0.0
    )
    try:
        duration = round(float(duration_raw), 3)
    except (ValueError, TypeError):
        duration = 0.0

    if duration <= 0.05 or math.isnan(duration):
        raise MediaInspectionError("Video duration is zero or unreadable")

    fps = parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "30/1")
    video_codec = video_stream.get("codec_name") or "unknown"
    pix_fmt = video_stream.get("pix_fmt") or "yuv420p"
    aspect_ratio = classify_aspect_ratio(width, height)

    bitrate_raw = fmt.get("bit_rate") or video_stream.get("bit_rate") or 0
    try:
        bitrate = int(bitrate_raw)
    except (ValueError, TypeError):
        bitrate = 0

    audio_info = None
    if audio_stream:
        audio_info = {
            "codec": audio_stream.get("codec_name", "aac"),
            "sample_rate": int(audio_stream.get("sample_rate") or 44100),
            "channels": int(audio_stream.get("channels") or 2),
            "channel_layout": audio_stream.get("channel_layout", "stereo"),
        }

    metadata_fingerprint = f"{video_codec}:{width}x{height}:{fps:.1f}fps:{duration:.2f}s"

    return {
        "valid": True,
        "filename": file_path.name,
        "file_size_bytes": file_size,
        "duration": duration,
        "width": width,
        "height": height,
        "resolution": f"{width}x{height}",
        "fps": fps,
        "aspect_ratio": aspect_ratio,
        "bitrate": bitrate,
        "video_codec": video_codec,
        "pix_fmt": pix_fmt,
        "has_audio": audio_stream is not None,
        "audio_codec": audio_info["codec"] if audio_info else None,
        "audio_info": audio_info,
        "metadata_fingerprint": metadata_fingerprint,
        "format_name": fmt.get("format_name", "mp4"),
    }
