"""
Core data models for yt_autopilot.
All modules must import data models ONLY from this file.
This is the single source of truth for data contracts.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TrendCandidate(BaseModel):
    """
    Represents a trending topic or keyword identified by trend detection.
    """
    keyword: str = Field(..., description="Main keyword or phrase trending")
    why_hot: str = Field(..., description="Explanation of why this trend is relevant now")
    region: str = Field(default="IT", description="Geographic region (e.g., 'IT', 'US', 'global')")
    language: str = Field(default="it", description="Language code (e.g., 'it', 'en')")
    momentum_score: float = Field(..., ge=0.0, le=1.0, description="Trend momentum score (0-1)")
    source: str = Field(..., description="Source of trend data (e.g., 'google_trends', 'glimpse_api')")


class VideoPlan(BaseModel):
    """
    Strategic video concept and planning.
    """
    working_title: str = Field(..., description="Internal working title (may differ from final)")
    strategic_angle: str = Field(..., description="Why this topic is relevant NOW and why viewers care")
    target_audience: str = Field(..., description="Who this video is for (demographics/psychographics)")
    language: str = Field(default="it", description="Content language code")
    compliance_notes: List[str] = Field(
        default_factory=list,
        description="Compliance checks passed (e.g., 'no medical claims', 'no hate speech')"
    )


class SceneVoiceover(BaseModel):
    """
    Voiceover text mapped to a specific scene for scene-level synchronization.

    Step 07.3: Enables precise sync between script audio and visual scenes.
    """
    scene_id: int = Field(..., ge=1, description="Scene number this voiceover belongs to")
    voiceover_text: str = Field(..., description="Text to be spoken during this scene")
    est_duration_seconds: int = Field(..., ge=1, description="Estimated speaking duration for this text")


class VideoScript(BaseModel):
    """
    Complete script with hook, body, and CTA.

    Step 07.3: Added scene_voiceover_map for scene-level audio/visual sync.
    """
    hook: str = Field(..., description="Opening hook (first 3-5 seconds) to grab attention")
    bullets: List[str] = Field(..., description="Main content points in order")
    outro_cta: str = Field(..., description="Call-to-action at the end")
    full_voiceover_text: str = Field(..., description="Complete narration text for TTS")
    scene_voiceover_map: List[SceneVoiceover] = Field(
        default_factory=list,
        description="Step 07.3: Scene-by-scene voiceover breakdown for precise sync"
    )


class VisualScene(BaseModel):
    """
    Single visual scene for video generation.

    Step 07.3: Added voiceover_text for scene-level audio/visual synchronization.
    """
    scene_id: int = Field(..., ge=1, description="Scene number in sequence")
    prompt_for_veo: str = Field(..., description="Text prompt for Veo 3.x video generation API")
    est_duration_seconds: int = Field(..., ge=1, description="Estimated duration of this scene")
    voiceover_text: str = Field(
        default="",
        description="Step 07.3: Text to be spoken during this scene (synced with script)"
    )


class VisualPlan(BaseModel):
    """
    Complete visual direction for video production.
    """
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio (e.g., '9:16' for Shorts)")
    style_notes: str = Field(..., description="Visual style guidance (colors, pacing, overlays)")
    scenes: List[VisualScene] = Field(..., description="Ordered list of visual scenes")


class PublishingPackage(BaseModel):
    """
    Final metadata package for YouTube upload.
    """
    final_title: str = Field(..., max_length=100, description="SEO-optimized YouTube title")
    description: str = Field(..., description="YouTube video description with timestamps/links")
    tags: List[str] = Field(..., description="YouTube tags for discoverability")
    affiliate_links: List[str] = Field(
        default_factory=list,
        description="Affiliate links to include in description"
    )
    thumbnail_concept: str = Field(..., description="Concept for thumbnail image generation")


class ReadyForFactory(BaseModel):
    """
    Complete editorial package approved for production.
    Output of the editorial brain (agents layer).

    Step 07: Added audit trail fields for LLM script tracking.
    """
    status: str = Field(..., description="'APPROVED' or 'REJECTED'")
    video_plan: VideoPlan
    script: VideoScript
    visuals: VisualPlan
    publishing: PublishingPackage
    rejection_reason: Optional[str] = Field(
        None,
        description="If REJECTED, explanation of why (e.g., compliance issue)"
    )
    llm_raw_script: Optional[str] = Field(
        None,
        description="Step 07: Raw LLM output for audit trail (unprocessed suggestion from LLM)"
    )
    final_script_text: Optional[str] = Field(
        None,
        description="Step 07: Final validated voiceover text for audit trail"
    )


class UploadResult(BaseModel):
    """
    Result of successful YouTube upload.
    """
    youtube_video_id: str = Field(..., description="YouTube video ID (e.g., 'dQw4w9WgXcQ')")
    published_at: str = Field(..., description="ISO 8601 timestamp of when video goes live")
    title: str = Field(..., description="Final title used for upload")
    upload_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp when upload occurred"
    )


class VideoMetrics(BaseModel):
    """
    Performance metrics collected from YouTube Analytics API.
    """
    video_id: str = Field(..., description="YouTube video ID")
    views: int = Field(default=0, ge=0, description="Total view count")
    watch_time_seconds: float = Field(default=0.0, ge=0.0, description="Total watch time in seconds")
    average_view_duration_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Average time viewers watched"
    )
    ctr: float = Field(default=0.0, ge=0.0, le=1.0, description="Click-through rate (0-1)")
    collected_at_iso: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp when metrics were collected"
    )


class AssetPaths(BaseModel):
    """
    Tracks file paths for all generated assets of a video.

    Step 07.4: Enables organized asset management without overwriting.
    Each video gets its own unique output directory.
    """
    video_id: str = Field(..., description="Unique video identifier (script_internal_id)")
    output_dir: str = Field(..., description="Base output directory for this video")
    final_video_path: Optional[str] = Field(None, description="Path to final assembled video")
    thumbnail_path: Optional[str] = Field(None, description="Path to thumbnail image")
    voiceover_path: Optional[str] = Field(None, description="Path to voiceover audio file")
    scene_video_paths: List[str] = Field(
        default_factory=list,
        description="Paths to individual scene videos in order"
    )
    metadata_path: Optional[str] = Field(None, description="Path to metadata JSON file")


class ChannelMemory(BaseModel):
    """
    Persistent channel brand memory and history.
    """
    brand_tone: str = Field(..., description="Channel's consistent tone of voice")
    visual_style: str = Field(..., description="Channel's consistent visual identity")
    banned_topics: List[str] = Field(..., description="Topics to avoid for compliance/brand safety")
    recent_titles: List[str] = Field(
        default_factory=list,
        description="Recent video titles to avoid repetition"
    )
