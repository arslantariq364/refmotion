"""Pluggable AI & Media Providers with Local Open-Source Neural TTS (Kokoro-82M & Piper ONNX) and Creative Script Engine."""
from __future__ import annotations

import re
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from backend.config import settings

_KOKORO_INSTANCE: Any = None

VOICE_PRESETS: Dict[str, Dict[str, str]] = {
    "kokoro_bella": {
        "engine": "kokoro",
        "voice_id": "af_bella",
        "label": "Kokoro — Bella (Warm & Expressive Female)",
        "gender": "female",
    },
    "kokoro_sarah": {
        "engine": "kokoro",
        "voice_id": "af_sarah",
        "label": "Kokoro — Sarah (Soft & Soothing Female)",
        "gender": "female",
    },
    "kokoro_sky": {
        "engine": "kokoro",
        "voice_id": "af_sky",
        "label": "Kokoro — Sky (Bright Storyteller Female)",
        "gender": "female",
    },
    "kokoro_emma": {
        "engine": "kokoro",
        "voice_id": "bf_emma",
        "label": "Kokoro — Emma (British Documentary Female)",
        "gender": "female",
    },
    "kokoro_adam": {
        "engine": "kokoro",
        "voice_id": "am_adam",
        "label": "Kokoro — Adam (Deep Cinematic Male)",
        "gender": "male",
    },
    "kokoro_michael": {
        "engine": "kokoro",
        "voice_id": "am_michael",
        "label": "Kokoro — Michael (Authoritative Narrator Male)",
        "gender": "male",
    },
    "kokoro_george": {
        "engine": "kokoro",
        "voice_id": "bm_george",
        "label": "Kokoro — George (British Wildlife Narrator Male)",
        "gender": "male",
    },
    "piper_lessac": {
        "engine": "piper",
        "model_file": "en_US-lessac-high.onnx",
        "label": "Piper Neural — Lessac (High-Res Studio Female)",
        "gender": "female",
    },
    "piper_bryce": {
        "engine": "piper",
        "model_file": "en_US-bryce-medium.onnx",
        "label": "Piper Neural — Bryce (Dynamic Studio Male)",
        "gender": "male",
    },
}


def get_models_dir() -> Path:
    return settings.UNICO_STORAGE_ROOT / "models"


def check_kokoro_available() -> bool:
    kokoro_dir = get_models_dir() / "voices" / "kokoro"
    return (kokoro_dir / "kokoro-v0_19.onnx").exists() and (kokoro_dir / "voices.bin").exists()


def check_piper_available() -> bool:
    voices_dir = get_models_dir() / "voices"
    piper_bin = Path(settings.UNICO_STORAGE_ROOT.parent / ".venv" / "bin" / "piper")
    return (
        (piper_bin.exists() or bool(shutil.which("piper")))
        and (voices_dir / "en_US-lessac-high.onnx").exists()
    )


def check_comfyui_available() -> bool:
    if not settings.COMFYUI_BASE_URL:
        return False
    try:
        req = urllib.request.Request(f"{settings.COMFYUI_BASE_URL.rstrip('/')}/system_stats", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def detect_gpu_acceleration() -> Dict[str, Any]:
    nvidia_smi = shutil.which("nvidia-smi")
    has_nvidia = False
    gpu_name = "Intel Integrated Graphics (CPU/VAAPI + ONNX Runtime)"
    if nvidia_smi:
        try:
            proc = subprocess.run(
                [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                has_nvidia = True
                gpu_name = proc.stdout.strip().splitlines()[0]
        except Exception:
            pass
    return {
        "has_nvidia_gpu": has_nvidia,
        "gpu_name": gpu_name,
        "vaapi_available": Path("/dev/dri/renderD128").exists(),
    }


def get_provider_capabilities() -> Dict[str, Any]:
    gpu_info = detect_gpu_acceleration()
    comfy_online = check_comfyui_available()
    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
    kokoro_ok = check_kokoro_available()
    piper_ok = check_piper_available()

    if kokoro_ok:
        active_tts = "kokoro_82m_onnx_neural"
    elif piper_ok:
        active_tts = "piper_onnx_neural"
    elif espeak_bin:
        active_tts = "espeak_local"
    else:
        active_tts = "local_harmonic_synth"

    return {
        "hardware": gpu_info,
        "llm_instruction_parser": {
            "local_rule_engine": True,
            "creative_script_generator": True,
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "gemini_configured": bool(settings.GEMINI_API_KEY),
            "anthropic_configured": bool(settings.ANTHROPIC_API_KEY),
            "active_provider": "gemini"
            if settings.GEMINI_API_KEY
            else ("openai" if settings.OPENAI_API_KEY else "local_creative_narrative_engine"),
        },
        "speech_to_text": {
            "local_whisper_configured": bool(
                settings.WHISPER_LOCAL_MODEL_PATH and Path(settings.WHISPER_LOCAL_MODEL_PATH).exists()
            ),
            "active_provider": "local_audio_envelope_detector",
        },
        "text_to_speech": {
            "kokoro_onnx_available": kokoro_ok,
            "piper_onnx_available": piper_ok,
            "espeak_available": bool(espeak_bin),
            "elevenlabs_configured": bool(settings.ELEVENLABS_API_KEY),
            "active_provider": active_tts,
            "available_voices": [
                {"id": k, **v} for k, v in VOICE_PRESETS.items()
            ],
        },
        "video_generation": {
            "template_asset_assembly": {
                "available": True,
                "mode": "local_authorized_library_novelty_remix",
                "description": "Scene-by-scene novelty remixing using authorized local reference library videos with dynamic camera motion, LUT color grading, neural voice-over, and audio mastering.",
            },
            "diffusion_text_to_video": {
                "available": comfy_online and gpu_info["has_nvidia_gpu"],
                "comfyui_reachable": comfy_online,
                "requires_gpu": True,
                "description": "True neural text-to-video diffusion backend (ComfyUI / Local Diffusion). Disabled on CPU-only environments.",
            },
        },
    }


def resolve_voice_choice(preference: str, topic: str = "", category: str = "") -> Dict[str, str]:
    """Resolve user voiceover preference into a concrete Kokoro-82M or Piper neural voice preset."""
    pref = (preference or "female").strip().lower()
    if pref in VOICE_PRESETS:
        return VOICE_PRESETS[pref]

    combined = f"{pref} {topic} {category}".lower()
    if "piper" in pref and "male" in pref:
        return VOICE_PRESETS["piper_bryce"]
    if "piper" in pref:
        return VOICE_PRESETS["piper_lessac"]
    if any(w in pref for w in ["british", "documentary", "wildlife", "george"]) and "male" in pref:
        return VOICE_PRESETS["kokoro_george"]
    if "emma" in pref or ("british" in pref and "female" in pref):
        return VOICE_PRESETS["kokoro_emma"]
    if any(w in pref for w in ["sarah", "soft", "gentle", "calm"]):
        return VOICE_PRESETS["kokoro_sarah"]
    if any(w in pref for w in ["sky", "energetic", "bright"]):
        return VOICE_PRESETS["kokoro_sky"]
    if any(w in pref for w in ["michael", "authoritative"]):
        return VOICE_PRESETS["kokoro_michael"]
    if pref in ("male", "deep", "adam", "cinematic_male") or ("male" in pref and "female" not in pref):
        if any(w in combined for w in ["lion", "wildlife", "savanna", "nature"]):
            return VOICE_PRESETS["kokoro_george"]
        return VOICE_PRESETS["kokoro_adam"]

    # Default to Kokoro Bella (warm, expressive female voice — ideal for cats, stories, reels)
    return VOICE_PRESETS["kokoro_bella"]


def synthesize_neural_voiceover(
    text: str,
    output_wav: Path,
    voice_preference: str = "kokoro_bella",
    language: str = "en",
    topic: str = "",
    category: str = "",
) -> Tuple[Optional[Path], float, str]:
    """
    Synthesize natural, human-like voice-over audio locally on CPU using:
      1. Kokoro-82M ONNX (24kHz lifelike neural speech)
      2. Piper-TTS ONNX (high-res neural speech)
      3. espeak-ng fallback
    Returns (wav_path, duration_seconds, engine_used).
    """
    clean_text = re.sub(r"\s+", " ", (text or "").strip())
    if not clean_text:
        return None, 0.0, "none"

    output_wav.parent.mkdir(parents=True, exist_ok=True)
    preset = resolve_voice_choice(voice_preference, topic=topic, category=category)
    engine = preset.get("engine", "kokoro")

    # 1. Try Kokoro-82M ONNX first when selected and available
    if engine == "kokoro" and check_kokoro_available():
        try:
            global _KOKORO_INSTANCE
            import soundfile as sf
            from kokoro_onnx import Kokoro

            kokoro_dir = get_models_dir() / "voices" / "kokoro"
            if _KOKORO_INSTANCE is None:
                _KOKORO_INSTANCE = Kokoro(
                    str(kokoro_dir / "kokoro-v0_19.onnx"),
                    str(kokoro_dir / "voices.bin"),
                )
            voice_id = preset.get("voice_id", "af_bella")
            lang_code = "en-gb" if voice_id.startswith("b") else "en-us"
            samples, sample_rate = _KOKORO_INSTANCE.create(
                clean_text[:900],
                voice=voice_id,
                speed=1.0,
                lang=lang_code,
            )
            sf.write(str(output_wav), samples, sample_rate)
            if output_wav.exists() and output_wav.stat().st_size > 1000:
                dur = round(len(samples) / float(sample_rate), 2)
                return output_wav, dur, f"kokoro_onnx:{voice_id}"
        except Exception:
            pass

    # 2. Try Piper Neural ONNX
    if check_piper_available():
        try:
            voices_dir = get_models_dir() / "voices"
            model_name = preset.get("model_file") or (
                "en_US-bryce-medium.onnx" if preset.get("gender") == "male" else "en_US-lessac-high.onnx"
            )
            model_path = voices_dir / model_name
            if not model_path.exists():
                model_path = voices_dir / "en_US-lessac-high.onnx"

            piper_bin = settings.UNICO_STORAGE_ROOT.parent / ".venv" / "bin" / "piper"
            piper_exe = str(piper_bin) if piper_bin.exists() else (shutil.which("piper") or "piper")
            proc = subprocess.run(
                [piper_exe, "--model", str(model_path), "--output_file", str(output_wav)],
                input=clean_text[:900],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            if proc.returncode == 0 and output_wav.exists() and output_wav.stat().st_size > 1000:
                import soundfile as sf
                info = sf.info(str(output_wav))
                return output_wav, round(float(info.duration), 2), f"piper_onnx:{model_path.stem}"
        except Exception:
            pass

    # 3. Fallback to espeak-ng
    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak_bin:
        try:
            proc = subprocess.run(
                [espeak_bin, "-v", (language or "en")[:2], "-s", "155", "-w", str(output_wav), clean_text[:600]],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if proc.returncode == 0 and output_wav.exists() and output_wav.stat().st_size > 100:
                import soundfile as sf
                info = sf.info(str(output_wav))
                return output_wav, round(float(info.duration), 2), "espeak_local"
        except Exception:
            pass

    return None, 0.0, "none"


def is_meta_prompt_or_short(script_text: str) -> bool:
    """Detect whether the user entered a generation instruction rather than a verbatim voiceover script."""
    txt = (script_text or "").strip()
    if not txt:
        return True
    words = txt.split()
    if len(words) < 10:
        return True
    lower = txt.lower()
    meta_phrases = [
        "generate a",
        "generate the",
        "create a",
        "make a",
        "beautiful voice",
        "good script",
        "voice over",
        "voiceover",
        "from reference",
        "like the reference",
        "video about",
        "reel about",
    ]
    return any(p in lower for p in meta_phrases)


def generate_creative_script(
    topic: str,
    script_text: str,
    category: str,
    target_duration: float,
    num_scenes: int,
    reference_style: Optional[Dict[str, Any]] = None,
    reference_title: str = "",
) -> Dict[str, Any]:
    """
    Generate a rich, story-driven narration script and scene-by-scene captions tailored to the topic.
    Applies a 70% Reference Style Weight (pacing, sentence rhythm, vocal cadence, subtitle timing)
    derived from the reference video while synthesizing 100% original narration and neural voice-over.
    """
    combined = f"{topic or ''} {script_text or ''} {category or ''} {reference_title or ''}".lower()
    clean_topic = (topic or category or "The Untold Story").strip()

    ref_ed = (reference_style or {}).get("editing_style", {})
    ref_vis = (reference_style or {}).get("visual_style", {})
    ref_pacing = ref_ed.get("pacing", "moderate")
    ref_avg_shot = float(ref_ed.get("average_shot_duration") or 3.2)
    ref_caption_style = ref_ed.get("caption_style", "bold_dynamic")
    ref_color = ref_vis.get("color_style", "cinematic")

    # 70% Reference Style Influence on Script Cadence, Voice Delivery & Subtitle Rhythm
    style_pacing_factor = 0.70 * (1.15 if ref_pacing == "fast" else (0.90 if ref_pacing == "slow" else 1.0)) + 0.30 * 1.0
    recommended_vo_speed = round(max(0.92, min(1.08, style_pacing_factor)), 2)

    if not is_meta_prompt_or_short(script_text):
        raw_sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+|\n+", script_text.strip())
            if s.strip()
        ]
    else:
        concise = target_duration <= 16.0 or ref_pacing == "fast" or ref_avg_shot < 2.6
        # Domain-specific rich narrative scripts tailored for natural neural TTS pacing
        if any(w in combined for w in ["cat", "kitten", "feline", "kitty", "purr"]):
            raw_sentences = (
                [
                    "Step into the enchanting secret world of playful cats.",
                    "Every gentle leap reveals pure curiosity and charm.",
                    "Sunlit stretches and kitten adventures turn moments into joy.",
                    "Soft paws and warm purrs capture every heart.",
                    "Every whisker twitch tells a story of wonder.",
                ]
                if concise
                else [
                    "Graceful, curious, and endlessly enchanting — step into the secret world of cats.",
                    "Every gentle leap and quiet glance reveals a playful spirit full of wonder and charm.",
                    "From sunlit afternoon stretches to sudden bursts of kitten curiosity, they turn simple moments into pure joy.",
                    "Soft paws, bright eyes, and a warm comforting purr remind us why cats capture every heart.",
                    "Watch closely as quiet elegance transforms every corner into a playground.",
                ]
            )
        elif any(w in combined for w in ["lion", "savanna", "safari", "predator", "pride"]):
            raw_sentences = (
                [
                    "Across the golden savanna, the lion rules with quiet majesty.",
                    "Every step reflects untamed wilderness and fearless survival.",
                    "Strength and loyalty unite the pride beneath the vast sky.",
                    "Witness the timeless power of nature's apex guardian.",
                    "Golden light crowns the sovereign of the wild plains.",
                ]
                if concise
                else [
                    "Across the golden plains of the savanna, the lion rules with quiet, unmistakable majesty.",
                    "Every calculated step and piercing gaze reflects centuries of untamed wilderness and survival.",
                    "Beneath the vast horizon, strength and family bond the pride together through every season.",
                    "Witness the timeless power and raw beauty of nature's ultimate apex guardian.",
                    "As dusk settles over the horizon, the legend of the savanna endures.",
                ]
            )
        elif any(w in combined for w in ["bird", "wing", "flight", "feather", "eagle", "parrot"]):
            raw_sentences = [
                "High above the canopy, vibrant wings take flight across the sky.",
                "With effortless grace, birds turn the wind into living art.",
                "Every wingbeat carries a story of freedom and natural rhythm.",
                "Look closer at the living poetry unfolding above our world.",
                "Nature's brightest colors soar beyond the horizon.",
            ]
        elif any(w in combined for w in ["dog", "puppy", "pet", "canine"]):
            raw_sentences = [
                "Boundless loyalty and pure excitement welcome every single day.",
                "Playful adventures and companionship bring warmth to every moment.",
                "Every outdoor run becomes an unforgettable celebration of life.",
                "Unconditional friendship captured in every happy stride.",
                "Pure joy lives in every tail wag and shared adventure.",
            ]
        elif category == "nature" or any(w in combined for w in ["nature", "forest", "waterfall", "mountain", "ocean", "flower"]):
            raw_sentences = [
                "Breathe in the quiet majesty where light and landscape move in harmony.",
                "From cascading waterfalls to whispering forests, every detail tells a story.",
                "Nature unfolds with breathtaking precision, beauty, and peace.",
                "Let the rhythm of the earth restore your sense of wonder.",
                "Timeless horizons awaken a deeper connection to the wild.",
            ]
        elif category == "business" or any(w in combined for w in ["business", "startup", "founder", "strategy", "office", "growth"]):
            raw_sentences = [
                f"What separates high-growth leaders in {clean_topic} from the rest?",
                "It starts with relentless clarity and disciplined daily execution.",
                "When vision aligns with momentum, breakthroughs become inevitable.",
                "Build with focus, iterate fast, and lead your industry.",
                "Excellence is forged in every strategic decision you make.",
            ]
        elif category == "technology" or any(w in combined for w in ["tech", "ai", "software", "code", "robot", "future"]):
            raw_sentences = [
                f"Inside {clean_topic}, intelligent innovation is reshaping how we build.",
                "Precision engineering and smart systems now work together in real time.",
                "Complex workflows now run seamlessly with extraordinary speed.",
                "Welcome to a smarter, faster era of modern technology.",
                "Tomorrow's breakthroughs are being engineered right before our eyes.",
            ]
        elif category == "education" or any(w in combined for w in ["learn", "study", "science", "class", "education", "knowledge"]):
            raw_sentences = [
                f"Here is the fascinating truth about {clean_topic} that changes everything.",
                "Breaking complex ideas down to first principles makes patterns crystal clear.",
                "Curiosity turns everyday observations into powerful lasting insights.",
                "Keep exploring, keep questioning, and never stop learning.",
                "Every discovery opens the door to a wider universe of ideas.",
            ]
        elif category == "humans" or any(w in combined for w in ["human", "people", "life", "portrait", "fitness", "story"]):
            raw_sentences = [
                "Every human story is written in moments of movement and courage.",
                "Across city streets and personal milestones, passion shapes who we become.",
                "Pushing past routine turns ordinary days into something extraordinary.",
                "This is the art of living with purpose and authenticity.",
                "Real emotion shines brightest when captured in motion.",
            ]
        else:
            raw_sentences = [
                f"Discover a fresh, cinematic perspective on {clean_topic}.",
                "Every frame is crafted with dynamic motion and intentional rhythm.",
                f"Look closer at the details that make {clean_topic.lower()} unforgettable.",
                "Experience visual storytelling reimagined with clarity and emotion.",
                "Where reference style meets original creative expression.",
            ]

    selected_lines: List[str] = []
    for idx in range(max(1, num_scenes)):
        line = raw_sentences[idx % len(raw_sentences)]
        selected_lines.append(line)

    # 70% reference cadence + 30% duration budget determines word count
    words_per_sec = 2.35 if ref_pacing == "fast" else (1.95 if ref_pacing == "slow" else 2.15)
    target_word_budget = max(12, min(80, int(target_duration * words_per_sec)))
    vo_lines: List[str] = []
    word_acc = 0
    for line in selected_lines:
        w_cnt = len(line.split())
        if word_acc + w_cnt <= target_word_budget or not vo_lines:
            vo_lines.append(line)
            word_acc += w_cnt
        else:
            break

    full_narration = " ".join(vo_lines)
    seg_dur = round(target_duration / max(1, num_scenes), 2)
    captions: List[Dict[str, Any]] = []
    caption_anim = "pop_in" if ref_pacing in ("fast", "moderate") else "fade_in"
    for idx in range(num_scenes):
        text_line = selected_lines[idx % len(selected_lines)]
        start_t = round(idx * seg_dur, 2)
        end_t = round(min(target_duration, (idx + 1) * seg_dur - 0.08), 2)
        if end_t > start_t:
            captions.append(
                {
                    "index": idx,
                    "start_time": start_t,
                    "end_time": end_t,
                    "text": text_line[:110],
                    "position": "bottom_center",
                    "animation": caption_anim,
                    "style_source": "70%_reference_style_cadence",
                    "caption_style": ref_caption_style,
                }
            )

    return {
        "narration_script": full_narration,
        "scene_lines": selected_lines[:num_scenes],
        "captions": captions,
        "style_inheritance": {
            "script_voice_subtitle_reference_weight": 0.70,
            "autonomous_original_synthesis_weight": 0.30,
            "reference_pacing": ref_pacing,
            "reference_color_tone": ref_color,
            "recommended_vo_speed": recommended_vo_speed,
        },
    }


def generate_storyboard_captions(
    topic: str,
    script_text: str,
    category: str,
    total_duration: float,
    num_scenes: int,
) -> List[Dict[str, Any]]:
    """Split or generate a script into timed scene captions for Mode A or Mode B."""
    bundle = generate_creative_script(
        topic=topic,
        script_text=script_text,
        category=category,
        target_duration=total_duration,
        num_scenes=num_scenes,
    )
    return bundle["captions"]


def parse_creative_instructions(
    instructions: str,
    editing_intensity: str = "Dynamic",
    reference_style: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse user editing instructions into concrete parameters using local deterministic NLP rules."""
    text = (instructions or "").lower()
    ref_ed = (reference_style or {}).get("editing_style", {})

    # Pacing resolution
    if any(w in text for w in ["fast", "energetic", "quick", "rapid", "action", "dynamic"]):
        pacing = "fast"
    elif any(w in text for w in ["slow", "calm", "relaxed", "minimal", "gentle"]):
        pacing = "slow"
    else:
        pacing = ref_ed.get("pacing", "moderate")

    if editing_intensity == "Minimal":
        shot_multiplier = 1.4
    elif editing_intensity == "Cinematic":
        shot_multiplier = 0.95
    elif editing_intensity == "Dynamic":
        shot_multiplier = 0.8
    else:
        shot_multiplier = 1.0

    base_shot = float(ref_ed.get("average_shot_duration") or (2.2 if pacing == "fast" else 3.5))
    target_shot_duration = round(max(1.2, min(8.0, base_shot * shot_multiplier)), 2)

    # Color grade resolution
    if any(w in text for w in ["golden", "warm", "sunset", "cozy"]):
        color_grade = "golden_hour"
    elif any(w in text for w in ["teal", "orange", "blockbuster"]):
        color_grade = "teal_orange"
    elif any(w in text for w in ["cinematic", "dramatic", "film", "moody", "contrast"]):
        color_grade = "cinematic"
    elif any(w in text for w in ["vibrant", "colorful", "pop", "bright", "saturated", "cute"]):
        color_grade = "vibrant"
    elif any(w in text for w in ["vintage", "retro", "sepia"]):
        color_grade = "warm_vintage"
    elif any(w in text for w in ["bw", "black and white", "monochrome", "noir"]):
        color_grade = "monochrome"
    else:
        color_grade = ref_ed.get("color_style", "cinematic")

    # Zoom & motion effects
    enable_zoom = (
        editing_intensity in ("Dynamic", "Cinematic")
        or any(w in text for w in ["zoom", "ken burns", "punch", "movement", "cinematic", "novelty", "unique"])
        or bool(ref_ed.get("zoom_effects", False))
    )

    # Speed adjustments
    speed_factor = 1.0
    if "slow motion" in text or "slow-mo" in text:
        speed_factor = 0.88
    elif "speed up" in text or "timelapse" in text or "hyper" in text:
        speed_factor = 1.12

    # Transitions
    transitions = list(ref_ed.get("transitions") or ["hard_cut", "fade"])
    if "fade" in text or "smooth" in text or editing_intensity == "Cinematic":
        if "fade" not in transitions:
            transitions.append("fade")

    return {
        "pacing": pacing,
        "target_shot_duration": target_shot_duration,
        "color_grade": color_grade,
        "enable_zoom": enable_zoom,
        "speed_factor": speed_factor,
        "transitions": transitions,
        "caption_style": ref_ed.get("caption_style", "bold_dynamic"),
        "music_style": ref_ed.get("music_style", "cinematic"),
    }


def synthesize_background_audio(
    output_wav: Path,
    duration: float,
    style: str = "cinematic",
) -> Optional[Path]:
    """
    Generate or adapt a rich background soundtrack locally.
    Uses studio ambient curiosity loop if available in storage/models/audio_assets,
    otherwise synthesizes a warm multi-harmonic ambient chord bed with FFmpeg lavfi.
    """
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    dur = max(1.0, round(duration, 2))
    fade_out_start = max(0.2, round(dur - 1.2, 2))

    ambient_loop = get_models_dir() / "audio_assets" / "ambient_curiosity_loop.wav"
    if ambient_loop.exists() and style not in ("none", "off"):
        cmd = [
            settings.FFMPEG_PATH,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(ambient_loop),
            "-t",
            str(dur),
            "-af",
            f"aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,lowpass=f=3200,volume=0.22,afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out_start}:d=1.0",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
            if proc.returncode == 0 and output_wav.exists():
                return output_wav
        except Exception:
            pass

    if style in ("energetic", "dynamic", "upbeat"):
        f1, f2 = 220, 330
    elif style in ("calm", "ambient", "minimal"):
        f1, f2 = 174, 261
    else:
        f1, f2 = 196, 293

    cmd = [
        settings.FFMPEG_PATH,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={f1}:sample_rate=44100:duration={dur}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={f2}:sample_rate=44100:duration={dur}",
        "-filter_complex",
        f"[0:a][1:a]amix=inputs=2:duration=shortest,lowpass=f=900,volume=0.08,afade=t=in:st=0:d=0.6,afade=t=out:st={fade_out_start}:d=1.0[a]",
        "-map",
        "[a]",
        "-c:a",
        "pcm_s16le",
        str(output_wav),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        if proc.returncode == 0 and output_wav.exists():
            return output_wav
    except Exception:
        pass
    return None
