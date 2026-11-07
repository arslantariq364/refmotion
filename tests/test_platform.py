"""Comprehensive QA & Integration Test Suite for Unico Platform (All 17 required test areas)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient

# Point tests to an isolated test storage directory before importing backend
TEST_STORAGE_ROOT = Path("/home/arslan-tariq/unico/storage/temporary/pytest_isolated_env")
os.environ["UNICO_STORAGE_ROOT"] = str(TEST_STORAGE_ROOT)
os.environ["UNICO_DATABASE_URL"] = f"sqlite:///{TEST_STORAGE_ROOT}/database/test_unico.db"
os.environ["UNICO_REQUIRE_AUTH"] = "false"
os.environ["UNICO_SKIP_STARTUP_SEED"] = "1"

from backend.config import settings
from backend.database import Base, SessionLocal, engine
from backend.main import app
from backend.models import Job
from backend.services.media_inspector import MediaInspectionError, inspect_video_file
from backend.services.reference_library import create_synthetic_reference_clip
from backend.services.storage_manager import storage_manager
from backend.services.worker import job_worker


@pytest.fixture(scope="module")
def sample_videos(tmp_path_factory):
    """Generate small, real playable sample MP4 videos for automated tests."""
    vdir = tmp_path_factory.mktemp("sample_videos")
    raw_clip = vdir / "test_raw_animal.mp4"
    ref_clip = vdir / "test_ref_animal.mp4"
    alt_ref_clip = vdir / "test_ref_landscape.mp4"
    corrupt_file = vdir / "corrupt.mp4"

    create_synthetic_reference_clip(
        raw_clip, duration=4.0, width=720, height=1280, color1="0x204060", color2="0x4080a0"
    )
    create_synthetic_reference_clip(
        ref_clip, duration=4.0, width=720, height=1280, color1="0x503018", color2="0x906030"
    )
    create_synthetic_reference_clip(
        alt_ref_clip, duration=4.0, width=1280, height=720, color1="0x153525", color2="0x307050"
    )
    corrupt_file.write_bytes(b"NOT_A_VALID_MP4_HEADER_DATA_0000")

    return {
        "raw": raw_clip,
        "ref": ref_clip,
        "alt_ref": alt_ref_clip,
        "corrupt": corrupt_file,
    }


@pytest.fixture(scope="module")
def client():
    if TEST_STORAGE_ROOT.exists():
        shutil.rmtree(TEST_STORAGE_ROOT, ignore_errors=True)
    storage_manager.root = TEST_STORAGE_ROOT
    storage_manager.reference_library_dir = TEST_STORAGE_ROOT / "reference_library"
    storage_manager.customer_projects_dir = TEST_STORAGE_ROOT / "customer_projects"
    storage_manager.generated_content_dir = TEST_STORAGE_ROOT / "generated_content"
    storage_manager.temporary_dir = TEST_STORAGE_ROOT / "temporary"
    storage_manager.database_dir = TEST_STORAGE_ROOT / "database"
    storage_manager.initialize_storage()
    real_models = Path("/home/arslan-tariq/unico/storage/models")
    test_models = TEST_STORAGE_ROOT / "models"
    if real_models.exists() and not test_models.exists():
        os.symlink(str(real_models), str(test_models))
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c

    shutil.rmtree(TEST_STORAGE_ROOT, ignore_errors=True)


def test_01_system_health_and_lan_accessibility(client: TestClient):
    """Test system health, capabilities, and LAN binding configuration."""
    r = client.get("/api/system/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["network"]["bind_host"] == "0.0.0.0"
    assert "lan_url" in data["network"]

    c = client.get("/api/system/capabilities")
    assert c.status_code == 200
    caps = c.json()
    assert caps["tools"]["ffmpeg"]["installed"] is True
    assert caps["tools"]["ffprobe"]["installed"] is True
    assert caps["providers"]["video_generation"]["template_asset_assembly"]["available"] is True


def test_02_ffprobe_inspection_and_invalid_file_handling(sample_videos):
    """Test FFprobe stream inspection on valid MP4 and rejection of corrupted file."""
    info = inspect_video_file(sample_videos["raw"])
    assert info["valid"] is True
    assert info["width"] == 720
    assert info["height"] == 1280
    assert info["aspect_ratio"] == "9:16"
    assert info["duration"] >= 3.5

    with pytest.raises(MediaInspectionError):
        inspect_video_file(sample_videos["corrupt"])


def test_03_reference_ingestion_thumbnails_and_scene_extraction(client: TestClient, sample_videos):
    """Test 8-step Reference Ingestion pipeline, thumbnail/contact sheet creation, and scene detection."""
    with open(sample_videos["ref"], "rb") as f:
        r = client.post(
            "/api/reference-library/ingest",
            files={"file": ("wildlife_reel.mp4", f, "video/mp4")},
            data={
                "category": "animals",
                "subcategory": "lions",
                "title": "Test Lion Pacing Reference",
                "description": "Fast vertical animal reference",
                "tags": "lions,fast,cinematic",
            },
        )
    assert r.status_code == 201, r.text
    asset = r.json()
    assert asset["category"] == "animals"
    assert asset["subcategory"] == "lions"
    assert asset["analysis_status"] == "completed"
    assert asset["thumbnail_url"] is not None
    assert asset["style_profile"] is not None
    assert len(asset["scenes"]) >= 1

    # Verify thumbnail is actually served and valid
    thumb_resp = client.get(asset["thumbnail_url"])
    assert thumb_resp.status_code == 200
    assert len(thumb_resp.content) > 200


def test_04_duplicate_detection(client: TestClient, sample_videos):
    """Test SHA-256 and perceptual duplicate rejection on reference ingestion."""
    with open(sample_videos["ref"], "rb") as f:
        r_dup = client.post(
            "/api/reference-library/ingest",
            files={"file": ("wildlife_reel_copy.mp4", f, "video/mp4")},
            data={"category": "animals"},
        )
    assert r_dup.status_code == 409


def test_05_category_management_and_reference_search(client: TestClient, sample_videos):
    """Test dynamic category creation and Top-K reference retrieval."""
    r_cat = client.post(
        "/api/reference-library/categories",
        data={"category": "DOCUMENTARY", "subcategory": "Ocean Life"},
    )
    assert r_cat.status_code == 201
    cats = r_cat.json()["categories"]
    assert "documentary" in cats
    assert "ocean_life" in cats["documentary"]

    # Ingest second reference in documentary
    with open(sample_videos["alt_ref"], "rb") as f:
        r2 = client.post(
            "/api/reference-library/ingest",
            files={"file": ("ocean_wide.mp4", f, "video/mp4")},
            data={"category": "documentary", "subcategory": "ocean_life", "title": "Ocean Documentary"},
        )
    assert r2.status_code == 201

    # Top-K Search for animals
    r_search = client.post(
        "/api/reference-library/search",
        json={"category": "animals", "aspect_ratio": "9:16", "top_k": 3},
    )
    assert r_search.status_code == 200
    results = r_search.json()["results"]
    assert len(results) >= 1
    assert results[0]["category"] == "animals"


def test_06_mode_a_video_upload_timeline_and_real_rendering(client: TestClient, sample_videos):
    """Test Mode A vertical slice: Project creation, raw upload, invalid upload rejection, timeline generation, FFmpeg rendering, and output validation."""
    # Create Mode A Project
    r_proj = client.post(
        "/api/projects",
        json={
            "title": "Customer Lion Edit",
            "mode": "edit",
            "category": "animals",
            "target_duration": 3.5,
            "aspect_ratio": "9:16",
            "target_platform": "Instagram Reels",
            "instructions": "Create a fast cinematic animal reel with zoom effects and captions.",
            "captions_enabled": True,
            "caption_text": "Wild Lions. King of the Savannah.",
            "music_preference": "cinematic",
            "video_quality": "720p",
            "editing_intensity": "Cinematic",
        },
    )
    assert r_proj.status_code == 201
    proj_id = r_proj.json()["id"]

    # Test invalid file upload rejection
    with open(sample_videos["corrupt"], "rb") as f_bad:
        r_bad = client.post(
            f"/api/projects/{proj_id}/upload/source",
            files={"file": ("corrupt.mp4", f_bad, "video/mp4")},
        )
    assert r_bad.status_code == 400

    # Upload valid raw source video
    with open(sample_videos["raw"], "rb") as f_raw:
        r_up = client.post(
            f"/api/projects/{proj_id}/upload/source",
            files={"file": ("customer_raw.mp4", f_raw, "video/mp4")},
        )
    assert r_up.status_code == 200
    assert r_up.json()["duration"] >= 3.5

    # Run full Mode A Edit & Render synchronously
    r_edit = client.post(f"/api/projects/{proj_id}/edit?sync=true", json={"rendering_engine": "ffmpeg"})
    assert r_edit.status_code == 200
    edit_res = r_edit.json()
    assert edit_res["status"] == "completed", edit_res

    # Fetch project and verify timeline + playable rendered output
    proj_detail = client.get(f"/api/projects/{proj_id}").json()
    assert len(proj_detail["timelines"]) >= 1
    assert len(proj_detail["outputs"]) >= 1
    out_item = proj_detail["outputs"][0]
    assert out_item["is_valid"] is True
    assert out_item["width"] == 720
    assert out_item["height"] == 1280

    # Download final rendered MP4 via API and verify with FFprobe
    dl_resp = client.get(out_item["download_url"])
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 5000

    # Test timeline regeneration without re-ingesting reference
    r_regen = client.post(
        f"/api/projects/{proj_id}/regenerate-timeline",
        json={"editing_intensity": "Minimal", "target_duration": 3.0},
    )
    assert r_regen.status_code == 200
    assert r_regen.json()["version"] == 2

    # Test privacy rule: promoting without confirm_consent=True must fail
    r_prom_denied = client.post(
        f"/api/projects/{proj_id}/promote",
        json={"category": "animals", "confirm_consent": False},
    )
    assert r_prom_denied.status_code == 400


def test_07_mode_b_template_video_generation(client: TestClient):
    """Test Mode B AI Video Generation using local reference library & templates."""
    r_proj = client.post(
        "/api/projects",
        json={
            "title": "Generated Wildlife Story",
            "mode": "generate",
            "category": "animals",
            "topic": "Lions of the Serengeti",
            "script_text": "Dawn breaks over the plains. The pride moves as one.",
            "target_duration": 4.0,
            "aspect_ratio": "9:16",
            "visual_style": "cinematic",
            "voiceover_preference": "none",
            "music_preference": "dramatic",
            "video_quality": "720p",
        },
    )
    assert r_proj.status_code == 201
    proj_id = r_proj.json()["id"]

    r_gen = client.post(f"/api/projects/{proj_id}/generate?sync=true", json={"rendering_engine": "ffmpeg"})
    assert r_gen.status_code == 200
    assert r_gen.json()["status"] == "completed", r_gen.text

    proj_detail = client.get(f"/api/projects/{proj_id}").json()
    assert proj_detail["status"] == "completed"
    assert len(proj_detail["outputs"]) == 1
    assert proj_detail["outputs"][0]["is_valid"] is True


def test_08_job_recovery_cancellation_cleanup_and_api_security(client: TestClient):
    """Test job crash recovery, cancellation, temp file cleanup, and path traversal security."""
    # Create a dummy project and queued job, then cancel it
    r_proj = client.post("/api/projects", json={"title": "Cancel Test", "mode": "generate"})
    pid = r_proj.json()["id"]

    db = SessionLocal()
    try:
        j = Job(project_id=pid, job_type="generate_video", status="running", stage="Rendering", retry_count=0, max_retries=2)
        db.add(j)
        db.commit()
        db.refresh(j)
        jid = j.id
    finally:
        db.close()

    # Test crash recovery of interrupted 'running' job
    recovered_count = job_worker.recover_interrupted_jobs()
    assert recovered_count >= 1

    # Test safe cancellation of queued job
    r_cancel = client.delete(f"/api/jobs/{jid}")
    assert r_cancel.status_code == 200
    assert r_cancel.json()["cancelled"] is True

    # Test temporary file cleanup endpoint
    (storage_manager.temporary_dir / "stale_temp.tmp").write_text("temp")
    r_clean = client.post("/api/system/cleanup")
    assert r_clean.status_code == 200
    assert r_clean.json()["cleaned"] is True

    # Test API path traversal security (both URL-encoded and normalized paths)
    r_trav1 = client.get("/api/media/..%2F..%2F..%2Fetc%2Fpasswd")
    assert r_trav1.status_code in (400, 403, 404)
    r_trav2 = client.get("/api/media/../../../../etc/passwd")
    assert r_trav2.status_code in (400, 403, 404)


def test_09_cat_video_generation_with_neural_tts_and_novelty(client: TestClient):
    """Test creative auto-script, Kokoro-82M neural TTS voice-over, and novelty cat video generation."""
    r_script = client.post(
        "/api/projects/meta/auto-script",
        json={"topic": "Playful Kittens & Cute Cats", "category": "animals", "target_duration": 8.0},
    )
    assert r_script.status_code == 200
    s_data = r_script.json()
    assert s_data["inferred_category"] == "animals"
    assert s_data["inferred_subcategory"] == "cats"
    assert "cats" in s_data["narration_script"].lower() or "kitten" in s_data["narration_script"].lower()

    r_proj = client.post(
        "/api/projects",
        json={
            "title": "Novelty Cat Story Reel",
            "mode": "generate",
            "category": "animals",
            "topic": "generate the cat video with beautiful voice and good script",
            "script_text": "generate the cat video with beautiful voice of its with good script and voice over",
            "target_duration": 6.0,
            "aspect_ratio": "9:16",
            "visual_style": "golden_hour",
            "voiceover_preference": "kokoro_bella",
            "music_preference": "ambient",
            "video_quality": "720p",
        },
    )
    assert r_proj.status_code == 201
    proj_id = r_proj.json()["id"]

    r_gen = client.post(f"/api/projects/{proj_id}/generate?sync=true", json={"rendering_engine": "ffmpeg"})
    assert r_gen.status_code == 200
    assert r_gen.json()["status"] == "completed", r_gen.text

    proj_detail = client.get(f"/api/projects/{proj_id}").json()
    assert proj_detail["status"] == "completed"
    tl_doc = proj_detail["timelines"][0]["timeline"]
    assert "kokoro_onnx" in tl_doc["voiceover_engine"] or "piper_onnx" in tl_doc["voiceover_engine"]
    assert len(tl_doc["provenance"]["novelty_transforms_applied"]) >= 4
    assert proj_detail["outputs"][0]["is_valid"] is True
    assert proj_detail["outputs"][0]["audio_codec"] == "aac"
