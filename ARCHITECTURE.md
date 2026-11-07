# Unico System Architecture (`ARCHITECTURE.md`)

Unico is architected as a modular, local-first platform optimized for CPU environments without requiring external cloud dependencies, Docker containers, or heavyweight infrastructure such as Redis or PostgreSQL.

---

## 1. High-Level Component Diagram

```mermaid
flowchart LR
    subgraph Frontend["Frontend (React + TS + Vite + Tailwind)"]
        DASH["10-Page Creator Dashboard"]
        PLAYER["Video Preview & Scrubber"]
        SSE_CLIENT["Live SSE Stage Tracker"]
    end

    subgraph Backend["FastAPI Backend (backend/)"]
        ROUTERS["REST & SSE Routers"]
        AUTH["Local HMAC Token Auth"]
        STORAGE["StorageManager (Safe Paths)"]
        INSPECT["MediaInspector (FFprobe + dHash)"]
        ANALYZE["VideoAnalyzer (Scenes + Audio + Color)"]
        REFLIB["ReferenceLibrary (8-Step Ingest + Top-K)"]
        PLANNER["EditingPlanner (Mode A EDL/Timeline)"]
        GEN["GenerationEngine (Mode B Storyboard)"]
        RENDER["RendererAdapter (FFmpeg / Remotion / Melt)"]
    end

    subgraph Persistence["Local Persistence (storage/)"]
        SQLITE[("SQLite WAL Database\n13 Normalized Tables")]
        FS[("Structured Media Hierarchy\nreference_library/\ncustomer_projects/")]
    end

    DASH --> ROUTERS
    SSE_CLIENT --> ROUTERS
    ROUTERS --> AUTH
    ROUTERS --> STORAGE
    ROUTERS --> REFLIB
    ROUTERS --> PLANNER
    ROUTERS --> GEN
    REFLIB --> INSPECT
    REFLIB --> ANALYZE
    PLANNER --> RENDER
    GEN --> RENDER
    ROUTERS --> SQLITE
    STORAGE --> FS
```

---

## 2. Normalized Database Schema (13 Tables)

Unico uses SQLite in `WAL` (Write-Ahead Logging) mode with foreign key enforcement (`PRAGMA foreign_keys=ON;`) to allow concurrent reads from the FastAPI web server while the background worker updates job stages.

```mermaid
erDiagram
    users ||--o{ projects : owns
    projects ||--o{ project_files : contains
    projects ||--o{ editing_timelines : versions
    projects ||--o{ jobs : schedules
    projects ||--o{ render_outputs : produces
    jobs ||--o{ job_events : logs
    reference_assets ||--|| reference_analysis : profiles
    reference_assets ||--o{ reference_scenes : segments
    reference_assets ||--o{ asset_tags : tags
    reference_assets ||--o{ projects : referenced_by
```

| Table Name | Primary Responsibility |
| :--- | :--- |
| `users` | Local creator accounts, PBKDF2-HMAC-SHA256 password hashes, and roles |
| `projects` | Mode A (`edit`) and Mode B (`generate`) project state, parameters, and privacy flags |
| `project_files` | Validated customer source uploads, custom references, and thumbnails |
| `jobs` | SQLite-backed background job queue with stage, progress, retry count, and cancellation flags |
| `job_events` | Immutable audit trail of pipeline stage transitions for SSE streaming |
| `reference_assets` | Indexed reference videos with SHA-256, perceptual dHash, codec info, and provenance |
| `reference_analysis` | Extracted style profiles (pacing, avg shot duration, color style, loudness, feature vector) |
| `reference_scenes` | Scene boundary timestamps, durations, representative frames, and shot compositions |
| `asset_tags` | Normalized searchable tags linked to each reference asset |
| `editing_timelines` | Versioned EDL and Timeline JSON documents decoupled from rendering |
| `render_outputs` | Final MP4 and preview proxy metadata validated by FFprobe |
| `generation_templates` | Reusable multi-slot storyboard templates for Mode B generation |
| `system_settings` | Runtime-configurable worker concurrency, preview resolution, and cleanup policies |

---

## 3. Storage Hierarchy & Privacy Boundary

```text
storage/
├── reference_library/           # Shared authorized reference videos (organized dynamically by category/subcategory)
│   ├── animals/
│   │   ├── lions/
│   │   ├── birds/
│   │   ├── wildlife/
│   │   └── pets/
│   ├── humans/
│   ├── nature/
│   ├── cinematic/
│   ├── business/
│   ├── education/
│   ├── technology/
│   └── general/
├── customer_projects/           # Strictly private per-project workspaces
│   └── {project_id}/
│       ├── input/               # Raw customer source video (never modified in place)
│       ├── reference/           # Project-private custom reference uploads
│       ├── analysis/            # Extracted keyframes and source analysis artifacts
│       ├── thumbnails/          # Input and output thumbnails
│       ├── timeline/            # Generated .srt captions and timeline artifacts
│       ├── previews/            # Lightweight 720p/480p proxy previews
│       ├── output/              # Final mastered MP4 exports
│       └── logs/                # Per-project processing logs
├── generated_content/           # Shared generated assets
├── temporary/                   # Ephemeral render segments (auto-cleaned)
└── database/
    └── unico.db                 # SQLite WAL database
```
