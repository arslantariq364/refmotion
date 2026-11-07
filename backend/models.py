"""Normalized SQLAlchemy ORM Models for Unico Platform (13 core tables)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="creator", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    mode = Column(String(32), nullable=False, default="edit")  # "edit" (Mode A) or "generate" (Mode B)
    category = Column(String(64), nullable=False, default="general", index=True)
    target_duration = Column(Float, nullable=False, default=15.0)
    aspect_ratio = Column(String(16), nullable=False, default="9:16")
    target_platform = Column(String(64), nullable=False, default="Instagram Reels")
    instructions = Column(Text, nullable=True, default="")
    topic = Column(String(256), nullable=True)
    script_text = Column(Text, nullable=True)
    visual_style = Column(String(64), nullable=False, default="cinematic")
    target_audience = Column(String(128), nullable=True, default="general")
    captions_enabled = Column(Boolean, default=True, nullable=False)
    caption_text = Column(Text, nullable=True)
    music_preference = Column(String(64), default="cinematic", nullable=False)
    voiceover_preference = Column(String(64), default="none", nullable=False)
    language = Column(String(32), default="en", nullable=False)
    video_quality = Column(String(32), default="1080p", nullable=False)
    editing_intensity = Column(String(32), default="Dynamic", nullable=False)  # Minimal, Moderate, Dynamic, Cinematic
    selected_reference_id = Column(
        String(36), ForeignKey("reference_assets.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String(32), default="draft", nullable=False, index=True)
    is_private = Column(Boolean, default=True, nullable=False)
    allow_library_promotion = Column(Boolean, default=False, nullable=False)
    source_analysis_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner = relationship("User", back_populates="projects")
    selected_reference = relationship("ReferenceAsset", foreign_keys=[selected_reference_id])
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    timelines = relationship("EditingTimeline", back_populates="project", cascade="all, delete-orphan")
    outputs = relationship("RenderOutput", back_populates="project", cascade="all, delete-orphan")


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    file_role = Column(String(32), nullable=False)  # "source", "reference", "thumbnail", "audio", "subtitle"
    original_filename = Column(String(256), nullable=False)
    stored_relpath = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    duration = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    fps = Column(Float, nullable=True)
    aspect_ratio = Column(String(32), nullable=True)
    video_codec = Column(String(64), nullable=True)
    audio_codec = Column(String(64), nullable=True)
    has_audio = Column(Boolean, default=False, nullable=False)
    thumbnail_relpath = Column(String(512), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="files")


class ReferenceAsset(Base):
    __tablename__ = "reference_assets"

    id = Column(String(36), primary_key=True, default=new_uuid)
    original_filename = Column(String(256), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, nullable=True, default="")
    stored_relpath = Column(String(512), nullable=False)
    sha256 = Column(String(64), unique=True, nullable=False, index=True)
    perceptual_hash = Column(String(128), nullable=True, index=True)
    metadata_fingerprint = Column(String(128), nullable=True)
    category = Column(String(64), nullable=False, default="general", index=True)
    subcategory = Column(String(64), nullable=True, index=True)
    duration = Column(Float, nullable=False, default=0.0)
    width = Column(Integer, nullable=False, default=0)
    height = Column(Integer, nullable=False, default=0)
    resolution = Column(String(32), nullable=False, default="0x0")
    fps = Column(Float, nullable=False, default=30.0)
    aspect_ratio = Column(String(16), nullable=False, default="16:9", index=True)
    bitrate = Column(Integer, nullable=True)
    video_codec = Column(String(64), nullable=True)
    audio_codec = Column(String(64), nullable=True)
    has_audio = Column(Boolean, default=False, nullable=False)
    audio_info_json = Column(JSON, nullable=True)
    thumbnail_relpath = Column(String(512), nullable=True)
    contact_sheet_relpath = Column(String(512), nullable=True)
    keyframes_json = Column(JSON, nullable=True)
    transcript = Column(Text, nullable=True)
    analysis_status = Column(String(32), default="pending", nullable=False, index=True)
    source_info = Column(String(256), default="local_authorized", nullable=False)
    license_info = Column(String(128), default="CC-BY / Local Authorized Reuse", nullable=False)
    usage_count = Column(Integer, default=0, nullable=False)
    promoted_from_project_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    analysis = relationship(
        "ReferenceAnalysis", back_populates="asset", uselist=False, cascade="all, delete-orphan"
    )
    scenes = relationship("ReferenceScene", back_populates="asset", cascade="all, delete-orphan")
    tags = relationship("AssetTag", back_populates="asset", cascade="all, delete-orphan")


class ReferenceAnalysis(Base):
    __tablename__ = "reference_analysis"

    id = Column(String(36), primary_key=True, default=new_uuid)
    asset_id = Column(
        String(36), ForeignKey("reference_assets.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    pacing = Column(String(32), nullable=False, default="moderate")  # slow, moderate, fast, ultra_fast
    average_shot_duration = Column(Float, nullable=False, default=3.0)
    scene_count = Column(Integer, nullable=False, default=1)
    cut_rate_per_minute = Column(Float, nullable=False, default=10.0)
    transitions_json = Column(JSON, nullable=False, default=list)
    color_style = Column(String(64), nullable=False, default="natural")
    dominant_colors_json = Column(JSON, nullable=True)
    brightness_avg = Column(Float, nullable=True)
    contrast_avg = Column(Float, nullable=True)
    saturation_avg = Column(Float, nullable=True)
    motion_intensity = Column(String(32), nullable=False, default="moderate")
    motion_score = Column(Float, nullable=False, default=0.5)
    zoom_effects = Column(Boolean, default=False, nullable=False)
    caption_style = Column(String(64), nullable=False, default="clean")
    music_style = Column(String(64), nullable=False, default="ambient")
    loudness_lufs = Column(Float, nullable=True)
    silence_ratio = Column(Float, nullable=True)
    speech_detected = Column(Boolean, default=False, nullable=False)
    style_profile_json = Column(JSON, nullable=False)
    embedding_json = Column(JSON, nullable=True)  # Optional feature vector for similarity retrieval
    analyzed_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    asset = relationship("ReferenceAsset", back_populates="analysis")


class ReferenceScene(Base):
    __tablename__ = "reference_scenes"

    id = Column(String(36), primary_key=True, default=new_uuid)
    asset_id = Column(String(36), ForeignKey("reference_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    representative_frame_relpath = Column(String(512), nullable=True)
    shot_composition = Column(String(64), nullable=True, default="medium")
    motion_level = Column(String(32), nullable=True, default="moderate")
    dominant_color = Column(String(32), nullable=True)
    metadata_json = Column(JSON, nullable=True)

    asset = relationship("ReferenceAsset", back_populates="scenes")


class AssetTag(Base):
    __tablename__ = "asset_tags"
    __table_args__ = (UniqueConstraint("asset_id", "tag", name="uq_asset_tag"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    asset_id = Column(String(36), ForeignKey("reference_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    tag = Column(String(64), nullable=False, index=True)

    asset = relationship("ReferenceAsset", back_populates="tags")


class EditingTimeline(Base):
    __tablename__ = "editing_timelines"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    duration = Column(Float, nullable=False)
    aspect_ratio = Column(String(16), nullable=False)
    resolution = Column(String(32), nullable=False, default="1080x1920")
    fps = Column(Float, nullable=False, default=30.0)
    edl_json = Column(JSON, nullable=False)
    timeline_json = Column(JSON, nullable=False)
    planner_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="timelines")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    job_type = Column(String(64), nullable=False, index=True)  # "edit_video", "generate_video", "ingest_reference", "analyze_project"
    status = Column(String(32), nullable=False, default="queued", index=True)  # queued, running, completed, failed, cancelled
    stage = Column(String(64), nullable=False, default="Queued")
    progress_percent = Column(Float, nullable=False, default=0.0)
    rendering_engine = Column(String(32), nullable=False, default="ffmpeg")
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=2)
    cancel_requested = Column(Boolean, default=False, nullable=False)
    payload_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_duration_sec = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("Project", back_populates="jobs")
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan")


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    message = Column(Text, nullable=False)
    progress_percent = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    job = relationship("Job", back_populates="events")


class RenderOutput(Base):
    __tablename__ = "render_outputs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    timeline_id = Column(String(36), ForeignKey("editing_timelines.id", ondelete="SET NULL"), nullable=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    output_type = Column(String(32), nullable=False, default="final")  # "final", "preview"
    rendering_engine = Column(String(32), nullable=False, default="ffmpeg")
    stored_relpath = Column(String(512), nullable=False)
    preview_relpath = Column(String(512), nullable=True)
    thumbnail_relpath = Column(String(512), nullable=True)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    duration = Column(Float, nullable=False, default=0.0)
    width = Column(Integer, nullable=False, default=0)
    height = Column(Integer, nullable=False, default=0)
    fps = Column(Float, nullable=False, default=30.0)
    video_codec = Column(String(64), nullable=True)
    audio_codec = Column(String(64), nullable=True)
    is_valid = Column(Boolean, default=True, nullable=False)
    validation_report_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    project = relationship("Project", back_populates="outputs")


class GenerationTemplate(Base):
    __tablename__ = "generation_templates"

    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(128), unique=True, nullable=False)
    category = Column(String(64), nullable=False, index=True)
    description = Column(Text, nullable=False)
    aspect_ratio = Column(String(16), nullable=False, default="9:16")
    default_duration = Column(Float, nullable=False, default=30.0)
    visual_style = Column(String(64), nullable=False, default="cinematic")
    structure_json = Column(JSON, nullable=False)  # List of slots: hook, closeup, wide, climax, outro
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(128), primary_key=True)
    value_json = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
