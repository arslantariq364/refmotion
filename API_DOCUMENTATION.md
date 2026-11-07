# Unico REST & SSE API Documentation (`API_DOCUMENTATION.md`)

All endpoints are served under `/api` on `http://<LAN_IP>:8000`. Interactive Swagger UI documentation is available live at `/docs`.

---

## 1. Authentication

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Exchange `username` and `password` for an HMAC bearer token. |
| `GET` | `/api/auth/me` | Return the currently authenticated creator profile. |

---

## 2. Projects (Mode A & Mode B)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/projects` | Create a new Mode A (`edit`) or Mode B (`generate`) project. |
| `GET` | `/api/projects` | List all projects with optional `mode` and `status` filters. |
| `GET` | `/api/projects/{id}` | Retrieve full project details, uploaded files, versioned timelines, and outputs. |
| `DELETE` | `/api/projects/{id}` | Delete a project and its private storage directory. |
| `POST` | `/api/projects/{id}/upload/source` | Stream and validate a raw source video via FFprobe. |
| `POST` | `/api/projects/{id}/upload/reference` | Stream and validate a project-specific custom reference video. |
| `POST` | `/api/projects/{id}/analyze` | Queue or synchronously run source + reference analysis and build a timeline. |
| `POST` | `/api/projects/{id}/edit` | Queue or run Mode A reference-based video editing and MP4 rendering. |
| `POST` | `/api/projects/{id}/generate` | Queue or run Mode B storyboard generation and MP4 rendering. |
| `POST` | `/api/projects/{id}/regenerate-timeline` | Generate a new timeline version (`v+1`) without re-ingesting media. |
| `POST` | `/api/projects/{id}/promote` | Promote a project's video to the shared Reference Library (requires `confirm_consent: true`). |

---

## 3. Jobs & Live Server-Sent Events (SSE)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/jobs` | List recent processing jobs and stage histories. |
| `GET` | `/api/jobs/{id}` | Inspect a specific job and its immutable `job_events` log. |
| `DELETE` | `/api/jobs/{id}` | Safely cancel an active/queued job or delete a finished job record. |
| `GET` | `/api/jobs/{id}/events/stream` | **SSE Stream**: Pushes real-time pipeline stage updates (`Validating`, `Analyzing reference`, `Analyzing source`, `Creating timeline`, `Rendering`, `Validating output`, `Completed`). |

---

## 4. Reference Library

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/reference-library` | List indexed reference assets, category tree, and per-category counts. |
| `GET` | `/api/reference-library/categories` | List dynamic categories and subcategories on disk. |
| `POST` | `/api/reference-library/categories` | Create a new dynamic category/subcategory folder. |
| `POST` | `/api/reference-library/ingest` | Upload a reference video and run the 8-step ingestion pipeline (returns `409` on SHA-256 or perceptual dHash duplicate). |
| `POST` | `/api/reference-library/search` | Top-K multi-criteria retrieval by category, tags, aspect ratio, pacing, color style, duration, and query text. |
| `GET` | `/api/reference-library/{id}` | Retrieve a single reference asset's scenes, keyframes, and JSON style profile. |
| `DELETE` | `/api/reference-library/{id}` | Delete a reference asset and its extracted analysis artifacts. |

---

## 5. System & Media

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/system/health` | Report server health, LAN URL, worker status, job counts, and disk usage. |
| `GET` | `/api/system/capabilities` | Report verified tool paths/versions (`ffmpeg`, `ffprobe`, `melt`, `shotcut`, `remotion`, `recordly`) and AI provider availability. |
| `GET` | `/api/templates` | List reusable Mode B generation templates. |
| `GET/PUT` | `/api/system/settings` | Read or update runtime platform settings in SQLite. |
| `POST` | `/api/system/cleanup` | Safely purge temporary files in `storage/temporary/`. |
| `GET` | `/api/media/{relpath}` | Safely serve validated media inside `storage/` (blocks path traversal). |
