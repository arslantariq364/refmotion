"""Video Analyzer: Keyframe extraction, scene detection, audio loudness/silence, visual metrics & style profile."""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image
from backend.config import settings
from backend.services.media_inspector import compute_image_dhash, inspect_video_file
from backend.services.storage_manager import storage_manager


def extract_frame_at(video_path: Path, timestamp: float, output_jpg: Path, max_dim: int = 640) -> bool:
    """Extract a single frame at `timestamp` seconds using FFmpeg."""
    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    ts = max(0.0, round(timestamp, 3))
    scale_filter = f"scale='min({max_dim},iw)':-2"
    cmd = [
        settings.FFMPEG_PATH,
        "-y",
        "-ss",
        str(ts),
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        scale_filter,
        "-q:v",
        "4",
        str(output_jpg),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return proc.returncode == 0 and output_jpg.exists() and output_jpg.stat().st_size > 0
    except Exception:
        return False


def build_contact_sheet(frame_paths: List[Path], output_path: Path, cols: int = 3) -> Optional[Path]:
    """Assemble extracted keyframes into a contact sheet grid image."""
    valid_paths = [p for p in frame_paths if p.exists() and p.stat().st_size > 0]
    if not valid_paths:
        return None
    try:
        images = [Image.open(p).convert("RGB") for p in valid_paths[:6]]
        thumb_w, thumb_h = 320, int(320 * (images[0].height / max(images[0].width, 1)))
        thumb_h = max(180, min(thumb_h, 568))
        rows = math.ceil(len(images) / cols)
        sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (18, 18, 24))
        for idx, img in enumerate(images):
            resized = img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            r = idx // cols
            c = idx % cols
            sheet.paste(resized, (c * thumb_w, r * thumb_h))
            img.close()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path, quality=85)
        return output_path
    except Exception:
        return None


def detect_scenes_ffmpeg(video_path: Path, duration: float, threshold: float = 0.27) -> List[Dict[str, Any]]:
    """Detect scene boundaries using FFmpeg select='gt(scene,threshold)',showinfo."""
    cmd = [
        settings.FFMPEG_PATH,
        "-nostats",
        "-i",
        str(video_path),
        "-vf",
        f"select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]
    cut_times: List[float] = []
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
        stderr = proc.stderr or ""
        for match in re.finditer(r"pts_time:([0-9]+\.?[0-9]*)", stderr):
            ts = round(float(match.group(1)), 3)
            if 0.25 < ts < (duration - 0.25):
                if not cut_times or (ts - cut_times[-1]) >= 0.35:
                    cut_times.append(ts)
    except Exception:
        pass

    boundaries = [0.0] + cut_times + [round(duration, 3)]
    scenes: List[Dict[str, Any]] = []
    for idx in range(len(boundaries) - 1):
        start_t = round(boundaries[idx], 3)
        end_t = round(boundaries[idx + 1], 3)
        seg_dur = round(max(0.1, end_t - start_t), 3)
        scenes.append(
            {
                "scene_index": idx,
                "start_time": start_t,
                "end_time": end_t,
                "duration": seg_dur,
            }
        )
    return scenes


def analyze_audio_stream(video_path: Path, duration: float, has_audio: bool) -> Dict[str, Any]:
    """Extract loudness and silence characteristics from audio stream."""
    if not has_audio:
        return {
            "has_audio": False,
            "mean_volume_db": -91.0,
            "max_volume_db": -91.0,
            "loudness_lufs": -70.0,
            "silence_ratio": 1.0,
            "speech_detected": False,
            "music_style": "silent",
        }

    cmd = [
        settings.FFMPEG_PATH,
        "-nostats",
        "-i",
        str(video_path),
        "-af",
        "silencedetect=noise=-35dB:d=0.4,volumedetect",
        "-f",
        "null",
        "-",
    ]
    mean_vol = -24.0
    max_vol = -3.0
    silence_total = 0.0

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        stderr = proc.stderr or ""
        m_mean = re.search(r"mean_volume:\s*([-\d\.]+)\s*dB", stderr)
        if m_mean:
            mean_vol = float(m_mean.group(1))
        m_max = re.search(r"max_volume:\s*([-\d\.]+)\s*dB", stderr)
        if m_max:
            max_vol = float(m_max.group(1))
        for m_sil in re.finditer(r"silence_duration:\s*([\d\.]+)", stderr):
            silence_total += float(m_sil.group(1))
    except Exception:
        pass

    silence_ratio = round(min(1.0, max(0.0, silence_total / max(duration, 0.1))), 3)
    loudness_lufs = round(mean_vol, 1)
    is_audible = mean_vol > -55.0 and silence_ratio < 0.92
    speech_detected = is_audible and (0.05 <= silence_ratio <= 0.85 or mean_vol > -32.0)

    if not is_audible:
        music_style = "silent"
    elif mean_vol > -16.0 and silence_ratio < 0.15:
        music_style = "energetic"
    elif mean_vol > -24.0 and silence_ratio < 0.35:
        music_style = "dramatic"
    else:
        music_style = "ambient"

    return {
        "has_audio": True,
        "mean_volume_db": round(mean_vol, 2),
        "max_volume_db": round(max_vol, 2),
        "loudness_lufs": loudness_lufs,
        "silence_ratio": silence_ratio,
        "speech_detected": bool(speech_detected),
        "music_style": music_style,
    }


def analyze_visual_frames(frame_paths: List[Path]) -> Dict[str, Any]:
    """Compute real brightness, contrast, saturation, dominant colors, and inter-frame motion."""
    valid_paths = [p for p in frame_paths if p.exists() and p.stat().st_size > 0]
    if not valid_paths:
        return {
            "brightness_avg": 0.5,
            "contrast_avg": 0.5,
            "saturation_avg": 0.5,
            "color_style": "natural",
            "dominant_colors": ["#202028"],
            "motion_score": 0.3,
            "motion_intensity": "moderate",
            "zoom_effects": False,
        }

    brightness_vals = []
    contrast_vals = []
    saturation_vals = []
    dominant_hexes = []
    gray_arrays = []

    for p in valid_paths:
        try:
            with Image.open(p) as img:
                rgb = img.convert("RGB").resize((160, 160), Image.Resampling.BILINEAR)
                arr = np.asarray(rgb, dtype=np.float32) / 255.0
                r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
                luma = 0.299 * r + 0.587 * g + 0.114 * b
                brightness_vals.append(float(np.mean(luma)))
                contrast_vals.append(float(np.std(luma)))

                cmax = np.maximum(np.maximum(r, g), b)
                cmin = np.minimum(np.minimum(r, g), b)
                delta = cmax - cmin
                sat = np.where(cmax > 1e-4, delta / (cmax + 1e-4), 0.0)
                saturation_vals.append(float(np.mean(sat)))

                mean_rgb = (
                    int(np.clip(np.mean(r) * 255, 0, 255)),
                    int(np.clip(np.mean(g) * 255, 0, 255)),
                    int(np.clip(np.mean(b) * 255, 0, 255)),
                )
                dominant_hexes.append(f"#{mean_rgb[0]:02x}{mean_rgb[1]:02x}{mean_rgb[2]:02x}")
                gray_arrays.append(luma)
        except Exception:
            pass

    b_avg = round(float(np.mean(brightness_vals)) if brightness_vals else 0.5, 3)
    c_avg = round(float(np.mean(contrast_vals)) if contrast_vals else 0.2, 3)
    s_avg = round(float(np.mean(saturation_vals)) if saturation_vals else 0.3, 3)

    diffs = []
    for i in range(len(gray_arrays) - 1):
        diffs.append(float(np.mean(np.abs(gray_arrays[i + 1] - gray_arrays[i]))))
    motion_score = round(min(1.0, (float(np.mean(diffs)) * 3.2) if diffs else 0.3), 3)

    if motion_score >= 0.55:
        motion_intensity = "high"
    elif motion_score >= 0.25:
        motion_intensity = "moderate"
    else:
        motion_intensity = "low"

    if c_avg >= 0.24 and b_avg <= 0.48:
        color_style = "cinematic"
    elif s_avg >= 0.42:
        color_style = "vibrant"
    elif s_avg <= 0.18:
        color_style = "muted"
    elif b_avg >= 0.62:
        color_style = "bright"
    else:
        color_style = "natural"

    unique_colors = list(dict.fromkeys(dominant_hexes))[:5]

    return {
        "brightness_avg": b_avg,
        "contrast_avg": c_avg,
        "saturation_avg": s_avg,
        "color_style": color_style,
        "dominant_colors": unique_colors or ["#222634"],
        "motion_score": motion_score,
        "motion_intensity": motion_intensity,
        "zoom_effects": bool(motion_score >= 0.28 or c_avg >= 0.22),
    }


def analyze_video_complete(
    video_path: Path,
    artifacts_dir: Path,
    category: str = "general",
) -> Dict[str, Any]:
    """Run full video inspection, keyframe extraction, scene detection, audio & visual analysis."""
    probe = inspect_video_file(video_path)
    duration = probe["duration"]
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Extract keyframes: first, middle, last, plus interval frames
    sample_times = sorted(
        list(
            set(
                [
                    round(min(0.15, duration * 0.05), 3),
                    round(duration * 0.25, 3),
                    round(duration * 0.50, 3),
                    round(duration * 0.75, 3),
                    round(max(0.0, duration - 0.2), 3),
                ]
            )
        )
    )

    frame_paths: List[Path] = []
    keyframe_records: List[Dict[str, Any]] = []

    for idx, ts in enumerate(sample_times):
        fp = artifacts_dir / f"keyframe_{idx:02d}_{int(ts * 1000)}ms.jpg"
        if extract_frame_at(video_path, ts, fp):
            frame_paths.append(fp)
            try:
                rel = storage_manager.to_relpath(fp)
            except ValueError:
                rel = str(fp)
            keyframe_records.append({"index": idx, "timestamp": ts, "relpath": rel})

    thumb_path = artifacts_dir / "thumbnail.jpg"
    mid_ts = round(duration * 0.35, 3)
    if not extract_frame_at(video_path, mid_ts, thumb_path) and frame_paths:
        thumb_path = frame_paths[len(frame_paths) // 2]

    perceptual_hash = compute_image_dhash(thumb_path) if thumb_path.exists() else None

    contact_sheet_path = artifacts_dir / "contact_sheet.jpg"
    cs_res = build_contact_sheet(frame_paths, contact_sheet_path)

    # Scene detection
    raw_scenes = detect_scenes_ffmpeg(video_path, duration)
    enriched_scenes: List[Dict[str, Any]] = []
    for sc in raw_scenes[:24]:
        sc_idx = sc["scene_index"]
        mid_sc = round((sc["start_time"] + sc["end_time"]) / 2.0, 3)
        sc_frame = artifacts_dir / f"scene_{sc_idx:02d}.jpg"
        sc_rel = None
        if extract_frame_at(video_path, mid_sc, sc_frame, max_dim=480):
            try:
                sc_rel = storage_manager.to_relpath(sc_frame)
            except ValueError:
                sc_rel = str(sc_frame)
            if sc_frame not in frame_paths and len(frame_paths) < 12:
                frame_paths.append(sc_frame)

        sc_vis = analyze_visual_frames([sc_frame]) if sc_frame.exists() else {}
        enriched_scenes.append(
            {
                "scene_index": sc_idx,
                "start_time": sc["start_time"],
                "end_time": sc["end_time"],
                "duration": sc["duration"],
                "representative_frame_relpath": sc_rel,
                "shot_composition": "close_up" if sc["duration"] < 2.2 else ("wide" if sc["duration"] > 4.5 else "medium"),
                "motion_level": sc_vis.get("motion_intensity", "moderate"),
                "dominant_color": (sc_vis.get("dominant_colors") or ["#303440"])[0],
            }
        )

    audio_profile = analyze_audio_stream(video_path, duration, probe["has_audio"])
    visual_profile = analyze_visual_frames(frame_paths)

    scene_count = max(1, len(enriched_scenes))
    avg_shot_dur = round(duration / scene_count, 2)
    cut_rate_cpm = round((scene_count / max(duration, 1.0)) * 60.0, 1)

    if avg_shot_dur <= 2.2:
        pacing = "fast"
    elif avg_shot_dur <= 4.5:
        pacing = "moderate"
    else:
        pacing = "slow"

    transitions = ["hard_cut"]
    if scene_count >= 2 and avg_shot_dur >= 2.0:
        transitions.append("fade")
    if visual_profile["motion_intensity"] == "high":
        transitions.append("smooth_zoom")

    caption_style = "bold_dynamic" if probe["aspect_ratio"] == "9:16" else "clean_lower_third"

    style_profile = {
        "category": category,
        "duration": duration,
        "aspect_ratio": probe["aspect_ratio"],
        "resolution": probe["resolution"],
        "fps": probe["fps"],
        "editing_style": {
            "pacing": pacing,
            "average_shot_duration": avg_shot_dur,
            "scene_count": scene_count,
            "cut_rate_per_minute": cut_rate_cpm,
            "transitions": transitions,
            "color_style": visual_profile["color_style"],
            "zoom_effects": visual_profile["zoom_effects"],
            "caption_style": caption_style,
            "music_style": audio_profile["music_style"],
        },
        "scenes": enriched_scenes,
        "audio_profile": audio_profile,
        "visual_profile": visual_profile,
    }

    # Feature vector for fast similarity comparison
    aspect_num = 1.0 if probe["aspect_ratio"] == "9:16" else (0.5 if probe["aspect_ratio"] == "1:1" else 0.0)
    pacing_num = 1.0 if pacing == "fast" else (0.5 if pacing == "moderate" else 0.1)
    embedding = [
        round(aspect_num, 4),
        round(pacing_num, 4),
        round(min(1.0, avg_shot_dur / 10.0), 4),
        round(visual_profile["brightness_avg"], 4),
        round(visual_profile["contrast_avg"], 4),
        round(visual_profile["saturation_avg"], 4),
        round(visual_profile["motion_score"], 4),
        round(1.0 - audio_profile["silence_ratio"], 4),
    ]

    try:
        thumb_rel = storage_manager.to_relpath(thumb_path) if thumb_path.exists() else None
    except ValueError:
        thumb_rel = str(thumb_path) if thumb_path.exists() else None

    try:
        cs_rel = storage_manager.to_relpath(cs_res) if cs_res and cs_res.exists() else None
    except ValueError:
        cs_rel = str(cs_res) if cs_res and cs_res.exists() else None

    return {
        "probe": probe,
        "perceptual_hash": perceptual_hash,
        "thumbnail_relpath": thumb_rel,
        "contact_sheet_relpath": cs_rel,
        "keyframes": keyframe_records,
        "scenes": enriched_scenes,
        "audio_profile": audio_profile,
        "visual_profile": visual_profile,
        "style_profile": style_profile,
        "embedding": embedding,
    }
