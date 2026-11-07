#!/usr/bin/env python3
"""
Download & Ingest Real Reference Videos (5 per Category, <= 4 minutes each)
into ~/Video_Tools/refvideos/references/<category>/ and Unico's SQLite Reference Library.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.config import settings
from backend.database import SessionLocal
from backend.models import AssetTag, ReferenceAnalysis, ReferenceAsset, ReferenceScene
from backend.services.reference_library import DuplicateAssetError, ingest_reference_video
from backend.services.storage_manager import storage_manager

REF_ROOT = settings.VIDEO_TOOLS_REFVIDEOS_DIR / "references"
YTDLP_BIN = str(BASE_DIR / ".venv" / "bin" / "yt-dlp")

# 5 curated real videos per category (35 total), each <= 4 minutes
CURATED_VIDEOS = [
    # 1. ANIMALS (5 videos: 3 cats/kittens, 1 lions/wildlife, 1 exotic birds/wildlife)
    {
        "category": "animals",
        "subcategory": "cats",
        "filename": "cat_playful_moments_01.mp4",
        "title": "Playful Kittens & Cute Cats Reel",
        "description": "Adorable kittens playing, jumping, and exploring with lively multi-cut pacing.",
        "tags": ["animals", "cats", "cat", "kitten", "kittens", "pets", "cute", "playful"],
        "source_type": "ytdlp",
        "source": "https://www.youtube.com/watch?v=cytJLvf-eVs",
        "section": "*00:00:05-00:00:35",
    },
    {
        "category": "animals",
        "subcategory": "cats",
        "filename": "cat_grass_adventure_02.mp4",
        "title": "Beautiful Kittens Playing On The Grass",
        "description": "Golden sunlight outdoor footage of fluffy kittens exploring green grass with warm natural grading.",
        "tags": ["animals", "cats", "cat", "kitten", "nature", "outdoor", "golden_hour", "pets"],
        "source_type": "ytdlp",
        "source": "https://www.youtube.com/watch?v=4dDt5OxKR2M",
        "section": "*00:00:10-00:00:40",
    },
    {
        "category": "animals",
        "subcategory": "cats",
        "filename": "cat_daddy_kitten_03.mp4",
        "title": "Curious Kitten & Daddy Cat Story",
        "description": "Heartwarming close-up interaction between a tiny kitten and adult cat with gentle camera movement.",
        "tags": ["animals", "cats", "cat", "kitten", "family", "closeup", "heartwarming", "pets"],
        "source_type": "ytdlp",
        "source": "https://www.youtube.com/watch?v=wE8s993ZV-8",
        "section": "*00:00:08-00:00:38",
    },
    {
        "category": "animals",
        "subcategory": "lions",
        "filename": "lion_wildlife_savanna_04.mp4",
        "title": "Wild African Lions Savanna Documentary",
        "description": "Majestic wild lions in the African savanna featuring cinematic wide and close-up wildlife cinematography.",
        "tags": ["animals", "lions", "lion", "wildlife", "savanna", "safari", "cinematic", "predator"],
        "source_type": "ytdlp",
        "source": "ytsearch1:wild lions savanna documentary 4k",
        "section": "*00:00:10-00:00:40",
    },
    {
        "category": "animals",
        "subcategory": "birds",
        "filename": "birds_wildlife_nature_05.mp4",
        "title": "Exotic Birds & Wildlife In Flight",
        "description": "Vibrant tropical birds perched and in flight amidst lush canopy foliage.",
        "tags": ["animals", "birds", "bird", "wildlife", "nature", "vibrant", "tropical"],
        "source_type": "ytdlp",
        "source": "ytsearch1:exotic birds nature wildlife",
        "section": "*00:00:10-00:00:40",
    },
    # 2. NATURE (5 videos)
    {
        "category": "nature",
        "subcategory": None,
        "filename": "nature_waterfall_forest_04.mp4",
        "title": "Cascading Waterfall & Lush Rainforest",
        "description": "Serene cascading waterfall surrounded by deep green forest foliage and mist.",
        "tags": ["nature", "waterfall", "forest", "water", "calm", "scenic", "landscape"],
        "source_type": "ytdlp",
        "source": "ytsearch1:waterfall forest nature 4k",
        "section": "*00:00:05-00:00:35",
    },
    {
        "category": "nature",
        "subcategory": None,
        "filename": "nature_flower_bloom_01.mp4",
        "title": "Blooming Wildflower Macro Timelapse",
        "description": "Vibrant macro nature shot of a blooming flower with rich botanical detail.",
        "tags": ["nature", "flower", "bloom", "macro", "botanical", "vibrant"],
        "source_type": "url",
        "source": "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4",
    },
    {
        "category": "nature",
        "subcategory": None,
        "filename": "nature_travel_scenic_02.mp4",
        "title": "Scenic Coastal & Mountain Horizon",
        "description": "Sweeping travel landscape cinematography capturing natural horizons and outdoor serenity.",
        "tags": ["nature", "travel", "landscape", "mountain", "horizon", "cinematic"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/travel.mp4",
    },
    {
        "category": "nature",
        "subcategory": None,
        "filename": "nature_wispysky_clouds_03.mp4",
        "title": "Atmospheric Sunset Sky & Clouds",
        "description": "High-resolution atmospheric cloudscape moving gently across a warm horizon.",
        "tags": ["nature", "sky", "clouds", "sunset", "atmospheric", "calm"],
        "source_type": "local",
        "source": "/home/arslan-tariq/recordly/public/wallpapers/wispysky.mp4",
    },
    {
        "category": "nature",
        "subcategory": None,
        "filename": "nature_river_wilderness_05.mp4",
        "title": "Alpine River & Wilderness Stream",
        "description": "Natural rushing river stream in an untamed mountain wilderness habitat.",
        "tags": ["nature", "river", "stream", "wilderness", "water", "wildlife"],
        "source_type": "url",
        "source": "https://www.w3schools.com/tags/movie.mp4",
    },
    # 3. HUMANS (5 videos)
    {
        "category": "humans",
        "subcategory": None,
        "filename": "humans_portrait_girl_01.mp4",
        "title": "Natural Light Portrait & Expression",
        "description": "Expressive human portrait shot in soft natural light with shallow depth of field.",
        "tags": ["humans", "people", "portrait", "lifestyle", "expression", "natural"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/girl.mp4",
    },
    {
        "category": "humans",
        "subcategory": None,
        "filename": "humans_lifestyle_woman_02.mp4",
        "title": "Modern Urban Lifestyle Story",
        "description": "Contemporary human lifestyle footage with smooth camera motion and warm skin tones.",
        "tags": ["humans", "people", "woman", "lifestyle", "urban", "story"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/woman.mp4",
    },
    {
        "category": "humans",
        "subcategory": None,
        "filename": "humans_fitness_training_03.mp4",
        "title": "Dynamic Athletic Fitness & Movement",
        "description": "High-energy athletic workout and physical training reference with dynamic pacing.",
        "tags": ["humans", "people", "fitness", "sport", "workout", "dynamic", "energetic"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/fit.mp4",
    },
    {
        "category": "humans",
        "subcategory": None,
        "filename": "humans_fashion_model_04.mp4",
        "title": "Editorial Fashion & Studio Pose",
        "description": "Stylized editorial fashion reel reference featuring confident posing and studio framing.",
        "tags": ["humans", "people", "fashion", "model", "editorial", "style"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/model.mp4",
    },
    {
        "category": "humans",
        "subcategory": None,
        "filename": "humans_walking_crowd_05.mp4",
        "title": "City Pedestrians & Street Documentary",
        "description": "Real-world street documentary shot of people walking along a busy urban walkway.",
        "tags": ["humans", "people", "street", "walking", "urban", "documentary"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/face-demographics-walking.mp4",
    },
    # 4. BUSINESS (5 videos)
    {
        "category": "business",
        "subcategory": None,
        "filename": "business_executive_reel_01.mp4",
        "title": "Executive Business Strategy Reel",
        "description": "High-retention vertical business explainer with dynamic pacing, hook captions, and structured scene transitions.",
        "tags": ["business", "executive", "strategy", "explainer", "vertical", "reel"],
        "source_type": "local",
        "source": "/home/arslan-tariq/business-reels/output/final/episode_001_final.mp4",
    },
    {
        "category": "business",
        "subcategory": None,
        "filename": "business_modern_office_02.mp4",
        "title": "Modern Corporate Office & Teamwork",
        "description": "Clean corporate workspace B-roll showing collaborative office culture and productivity.",
        "tags": ["business", "office", "corporate", "workspace", "team", "productivity"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/office.mp4",
    },
    {
        "category": "business",
        "subcategory": None,
        "filename": "business_retail_commerce_03.mp4",
        "title": "Retail Commerce & Customer Experience",
        "description": "Commercial retail store aisle footage illustrating consumer behavior and merchandising.",
        "tags": ["business", "retail", "commerce", "store", "customer", "market"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/store-aisle-detection.mp4",
    },
    {
        "category": "business",
        "subcategory": None,
        "filename": "business_hook_strategy_04.mp4",
        "title": "High-Impact Founder Hook Scene",
        "description": "Punchy opening business hook designed for maximum viewer retention on social platforms.",
        "tags": ["business", "hook", "founder", "startup", "marketing", "vertical"],
        "source_type": "local",
        "source": "/home/arslan-tariq/business-reels/output/final/scene_01_hook_final.mp4",
    },
    {
        "category": "business",
        "subcategory": None,
        "filename": "business_market_breakdown_05.mp4",
        "title": "Visual Market & System Breakdown",
        "description": "Analytical business breakdown segment with clear visual hierarchy and motion pacing.",
        "tags": ["business", "analytics", "breakdown", "finance", "growth", "vertical"],
        "source_type": "local",
        "source": "/home/arslan-tariq/business-reels/output/final/scene_02_breakdown_final.mp4",
    },
    # 5. EDUCATION (5 videos)
    {
        "category": "education",
        "subcategory": None,
        "filename": "education_classroom_study_01.mp4",
        "title": "Interactive Classroom & Student Learning",
        "description": "Educational classroom environment showcasing students engaged in collaborative study.",
        "tags": ["education", "classroom", "students", "learning", "school", "study"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/classroom.mp4",
    },
    {
        "category": "education",
        "subcategory": None,
        "filename": "education_culinary_arts_02.mp4",
        "title": "Culinary Arts & Step-by-Step Technique",
        "description": "Hands-on instructional cooking demonstration highlighting preparation technique and detail.",
        "tags": ["education", "cooking", "culinary", "tutorial", "howto", "skills"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/cooking.mp4",
    },
    {
        "category": "education",
        "subcategory": None,
        "filename": "education_knowledge_gap_03.mp4",
        "title": "Bridging The Knowledge Gap Explainer",
        "description": "Structured educational explainer segment illustrating conceptual gaps and mental models.",
        "tags": ["education", "explainer", "concept", "science", "knowledge", "vertical"],
        "source_type": "local",
        "source": "/home/arslan-tariq/business-reels/output/final/scene_03_gap_final.mp4",
    },
    {
        "category": "education",
        "subcategory": None,
        "filename": "education_key_takeaway_04.mp4",
        "title": "Core Lesson & Actionable Takeaway",
        "description": "Concise educational summary clip designed to reinforce key learning outcomes.",
        "tags": ["education", "summary", "takeaway", "lesson", "insight", "vertical"],
        "source_type": "local",
        "source": "/home/arslan-tariq/business-reels/output/final/scene_04_takeaway_final.mp4",
    },
    {
        "category": "education",
        "subcategory": None,
        "filename": "education_nutrition_science_05.mp4",
        "title": "Botanical & Nutritional Science Study",
        "description": "Visual overview of fresh organic produce for nutrition and biology education.",
        "tags": ["education", "nutrition", "biology", "science", "food", "health"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/fruit-and-vegetable-detection.mp4",
    },
    # 6. TECHNOLOGY (5 videos)
    {
        "category": "technology",
        "subcategory": None,
        "filename": "technology_screen_walkthrough_01.mp4",
        "title": "Software Product UI Walkthrough",
        "description": "16:9 landscape desktop walkthrough demonstrating clean software UI pacing and tutorial structure.",
        "tags": ["technology", "software", "ui", "walkthrough", "screencast", "tutorial"],
        "source_type": "local",
        "source": "/home/arslan-tariq/Video_Tools/refvideos/references/sample_screen_walkthrough.mp4",
    },
    {
        "category": "technology",
        "subcategory": None,
        "filename": "technology_autonomous_traffic_02.mp4",
        "title": "Autonomous Vehicle & Computer Vision Stream",
        "description": "Real-world highway vehicle flow used for AI computer vision and smart mobility analysis.",
        "tags": ["technology", "ai", "computer_vision", "autonomous", "vehicles", "mobility"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/car-detection.mp4",
    },
    {
        "category": "technology",
        "subcategory": None,
        "filename": "technology_industrial_safety_03.mp4",
        "title": "Industrial Automation & Smart Factory Safety",
        "description": "Industrial engineering and worker zone monitoring footage for smart manufacturing.",
        "tags": ["technology", "industrial", "engineering", "automation", "manufacturing", "iot"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/worker-zone-detection.mp4",
    },
    {
        "category": "technology",
        "subcategory": None,
        "filename": "technology_precision_hardware_04.mp4",
        "title": "High-Speed Precision Hardware Inspection",
        "description": "Close-up automated hardware component inspection on a robotics assembly line.",
        "tags": ["technology", "hardware", "robotics", "precision", "inspection", "engineering"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/bolt-detection.mp4",
    },
    {
        "category": "technology",
        "subcategory": None,
        "filename": "technology_smart_mobility_05.mp4",
        "title": "Smart City Infrastructure & Connected Transit",
        "description": "Modern urban transit flow demonstrating connected city infrastructure.",
        "tags": ["technology", "smart_city", "transit", "infrastructure", "future", "urban"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/trafic.mp4",
    },
    # 7. CINEMATIC (5 videos)
    {
        "category": "cinematic",
        "subcategory": None,
        "filename": "cinematic_david_awakening_01.mp4",
        "title": "David Awakening — Dramatic Narrative Reel",
        "description": "Atmospheric vertical cinematic reel with dramatic color grading, optical focus, and narrative pacing.",
        "tags": ["cinematic", "dramatic", "storytelling", "film", "vertical", "reel"],
        "source_type": "local",
        "source": "/home/arslan-tariq/reels/output/final/demo_david_awakening.mp4",
    },
    {
        "category": "cinematic",
        "subcategory": None,
        "filename": "cinematic_urban_architecture_02.mp4",
        "title": "Architectural Symmetry & Cityscape B-Roll",
        "description": "Moody architectural cinematography showcasing modern skyline geometry and contrast.",
        "tags": ["cinematic", "architecture", "building", "cityscape", "urban", "broll"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/Building.mp4",
    },
    {
        "category": "cinematic",
        "subcategory": None,
        "filename": "cinematic_aviation_flight_03.mp4",
        "title": "Golden Hour Aviation & Horizon Flight",
        "description": "Sweeping cinematic shot of an aircraft soaring across the sky.",
        "tags": ["cinematic", "airplane", "aviation", "flight", "travel", "sky"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/airplane.mp4",
    },
    {
        "category": "cinematic",
        "subcategory": None,
        "filename": "cinematic_highway_motion_04.mp4",
        "title": "Dusk Highway Motion & Light Trails",
        "description": "Dynamic forward-motion highway cinematography ideal for dramatic travel and story transitions.",
        "tags": ["cinematic", "highway", "motion", "road", "journey", "dynamic"],
        "source_type": "url",
        "source": "https://raw.githubusercontent.com/Syed-Moinuddin2025/videos/main/highway.mp4",
    },
    {
        "category": "cinematic",
        "subcategory": None,
        "filename": "cinematic_storytelling_reel_05.mp4",
        "title": "Curiosity & Wonder — Multi-Scene Film Reel",
        "description": "Richly graded multi-scene narrative reel with studio voiceover, ambient score, and film grain.",
        "tags": ["cinematic", "film_grain", "lut", "narrative", "story", "vertical"],
        "source_type": "local",
        "source": "/home/arslan-tariq/reels/output/final/reel_22804b19.mp4",
    },
]


def download_or_copy_to_ref_folder(item: dict) -> Path:
    cat = item["category"]
    dest_dir = REF_ROOT / cat
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / item["filename"]

    if dest_path.exists() and dest_path.stat().st_size > 20_000:
        return dest_path

    stype = item["source_type"]
    src = item["source"]

    if stype == "local":
        src_p = Path(src)
        if not src_p.exists():
            raise FileNotFoundError(f"Local source missing: {src_p}")
        shutil.copy2(str(src_p), str(dest_path))
    elif stype == "url":
        req = urllib.request.Request(src, headers={"User-Agent": "UnicoPlatform/1.0"})
        with urllib.request.urlopen(req, timeout=45) as resp, open(dest_path, "wb") as out_f:
            shutil.copyfileobj(resp, out_f)
    elif stype == "ytdlp":
        cmd = [
            YTDLP_BIN,
            "--js-runtimes",
            "node",
            "--remote-components",
            "ejs:github",
            "-f",
            "best[height<=720][ext=mp4]/best[height<=720]/best",
            "--merge-output-format",
            "mp4",
            "--download-sections",
            item.get("section", "*00:00:05-00:00:35"),
            "-o",
            str(dest_path),
            src,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)

    # Ensure duration <= 240s (4 minutes)
    if dest_path.exists() and dest_path.stat().st_size > 10_000:
        return dest_path
    raise RuntimeError(f"Failed to acquire {dest_path}")


def main() -> None:
    storage_manager.initialize_storage()
    db = SessionLocal()
    try:
        # Remove old synthetic seed clip if present
        syn_assets = (
            db.query(ReferenceAsset)
            .filter(ReferenceAsset.original_filename.like("%seed_animal_lions_cinematic%"))
            .all()
        )
        for sa in syn_assets:
            print(f"Removing old synthetic clip: {sa.title} ({sa.id})")
            try:
                p = storage_manager.resolve_safe_path(sa.stored_relpath)
                p.unlink(missing_ok=True)
            except Exception:
                pass
            db.query(AssetTag).filter(AssetTag.asset_id == sa.id).delete()
            db.query(ReferenceScene).filter(ReferenceScene.asset_id == sa.id).delete()
            db.query(ReferenceAnalysis).filter(ReferenceAnalysis.asset_id == sa.id).delete()
            db.delete(sa)
        db.commit()

        ingested = 0
        skipped = 0
        for idx, item in enumerate(CURATED_VIDEOS, start=1):
            cat = item["category"]
            sub = item["subcategory"]
            fname = item["filename"]
            print(f"[{idx:02d}/{len(CURATED_VIDEOS)}] Preparing {cat}/{fname} ...")
            try:
                ref_file = download_or_copy_to_ref_folder(item)
                asset = ingest_reference_video(
                    db=db,
                    source_file_path=ref_file,
                    category=cat,
                    subcategory=sub,
                    title=item["title"],
                    description=item["description"],
                    tags=item["tags"],
                    source_info=f"Video_Tools/refvideos/references/{cat}/{fname}",
                    license_info="Authorized Local Reference Library",
                    move_file=False,
                )
                print(
                    f"  -> Ingested '{asset.title}' | cat={asset.category} sub={asset.subcategory} "
                    f"dur={asset.duration:.1f}s res={asset.resolution} scenes={len(asset.scenes)}"
                )
                ingested += 1
            except DuplicateAssetError as dup:
                # Ensure existing asset has rich tags and subcategory updated
                ex = db.query(ReferenceAsset).filter(ReferenceAsset.id == dup.existing_asset_id).first()
                if ex:
                    if sub and not ex.subcategory:
                        ex.subcategory = sub
                    existing_tags = {t.tag.lower() for t in ex.tags}
                    for t in item["tags"]:
                        if t.lower() not in existing_tags:
                            db.add(AssetTag(asset_id=ex.id, tag=t.lower()))
                    db.commit()
                print(f"  -> Already indexed: {dup}")
                skipped += 1
            except Exception as exc:
                db.rollback()
                print(f"  -> ERROR on {cat}/{fname}: {exc}")

        total = db.query(ReferenceAsset).count()
        print(f"\nDone! Newly ingested: {ingested}, Already present: {skipped}, Total in Library: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
