"""Pydantic Request and Response Schemas for Unico API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class ProjectCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    mode: str = Field(default="edit", pattern="^(edit|generate)$")
    category: str = Field(default="general", min_length=1, max_length=64)
    target_duration: float = Field(default=15.0, ge=2.0, le=600.0)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9|1:1)$")
    target_platform: str = Field(default="Instagram Reels", max_length=64)
    instructions: Optional[str] = Field(default="", max_length=4000)
    topic: Optional[str] = Field(default="", max_length=256)
    script_text: Optional[str] = Field(default="", max_length=8000)
    visual_style: str = Field(default="cinematic", max_length=64)
    target_audience: Optional[str] = Field(default="general", max_length=128)
    captions_enabled: bool = True
    caption_text: Optional[str] = Field(default=None, max_length=4000)
    music_preference: str = Field(default="cinematic", max_length=64)
    voiceover_preference: str = Field(default="none", max_length=64)
    language: str = Field(default="en", max_length=32)
    video_quality: str = Field(default="1080p", pattern="^(720p|1080p|4k)$")
    editing_intensity: str = Field(
        default="Dynamic", pattern="^(Minimal|Moderate|Dynamic|Cinematic)$"
    )
    selected_reference_id: Optional[str] = None
    allow_library_promotion: bool = False


class ProjectEditRequest(BaseModel):
    selected_reference_id: Optional[str] = None
    instructions: Optional[str] = None
    target_duration: Optional[float] = Field(default=None, ge=2.0, le=600.0)
    aspect_ratio: Optional[str] = Field(default=None, pattern="^(9:16|16:9|1:1)$")
    target_platform: Optional[str] = None
    captions_enabled: Optional[bool] = None
    caption_text: Optional[str] = None
    music_preference: Optional[str] = None
    video_quality: Optional[str] = Field(default=None, pattern="^(720p|1080p|4k)$")
    editing_intensity: Optional[str] = Field(
        default=None, pattern="^(Minimal|Moderate|Dynamic|Cinematic)$"
    )
    rendering_engine: str = Field(default="ffmpeg", pattern="^(ffmpeg|remotion|melt)$")


class ProjectGenerateRequest(BaseModel):
    topic: Optional[str] = None
    script_text: Optional[str] = None
    category: Optional[str] = None
    selected_reference_id: Optional[str] = None
    template_id: Optional[str] = None
    target_duration: Optional[float] = Field(default=None, ge=2.0, le=600.0)
    aspect_ratio: Optional[str] = Field(default=None, pattern="^(9:16|16:9|1:1)$")
    visual_style: Optional[str] = None
    target_audience: Optional[str] = None
    voiceover_preference: Optional[str] = None
    music_preference: Optional[str] = None
    language: Optional[str] = None
    captions_enabled: Optional[bool] = None
    rendering_engine: str = Field(default="ffmpeg", pattern="^(ffmpeg|remotion|melt)$")


class PromoteProjectRequest(BaseModel):
    category: str = Field(..., min_length=1, max_length=64)
    subcategory: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    license_info: str = Field(default="Creator Authorized Reuse", max_length=128)
    confirm_consent: bool = Field(..., description="Owner must explicitly confirm reuse consent")


class ReferenceSearchRequest(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tags: Optional[List[str]] = None
    query: Optional[str] = None
    aspect_ratio: Optional[str] = None
    pacing: Optional[str] = None
    color_style: Optional[str] = None
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    top_k: int = Field(default=6, ge=1, le=50)


class SettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any]
