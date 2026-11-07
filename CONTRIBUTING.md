# Contributing to Unico (`CONTRIBUTING.md`)

Thank you for contributing to **Unico**! To keep the platform modular, fast, and maintainable on CPU hardware, please follow these engineering guidelines.

---

## 1. Architectural Rules

1. **Keep Modules Replaceable**:
   - New rendering engines must subclass `BaseRendererAdapter` in `backend/services/renderer.py`.
   - Optional AI providers (LLM, STT, TTS, Diffusion Video) must live in `backend/services/providers.py` and degrade gracefully when API keys or GPUs are absent.
2. **Never Mutate Original Media**:
   - Customer uploads in `storage/customer_projects/{id}/input/` and reference videos in `storage/reference_library/` must remain read-only during editing and rendering.
3. **Subprocess Safety**:
   - Always invoke `ffmpeg`, `ffprobe`, and `melt` with argument lists (`subprocess.run([...], shell=False)`) and explicit timeouts. Never construct shell commands from untrusted user strings.
4. **No Fake Metrics or Progress**:
   - Style profiles must be computed from actual video/audio inspection. Job progress must reflect real pipeline stage transitions recorded in `job_events`.

---

## 2. Running the Automated Test Suite

Unico includes a comprehensive `pytest` suite (`tests/test_platform.py`) that generates small synthetic videos with FFmpeg and tests real ingestion, duplicate detection, scene analysis, Mode A editing, Mode B generation, crash recovery, cancellation, and path security.

```bash
cd /home/arslan-tariq/unico
.venv/bin/pytest -v tests/test_platform.py
```

All tests must pass before submitting changes.
