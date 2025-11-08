"""
Core data models for yt_autopilot.
All modules must import data models ONLY from this file.
This is the single source of truth for data contracts.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class TrendCandidate(BaseModel):
    """
    Represents a trending topic or keyword identified by trend detection.

    Step 08: Extended with revenue optimization and multi-source scoring fields.
    Step 08.1: Added keyword_match_count for scoring differentiation.
    """
    keyword: str = Field(..., description="Main keyword or phrase trending")
    why_hot: str = Field(..., description="Explanation of why this trend is relevant now")
    region: str = Field(default="IT", description="Geographic region (e.g., 'IT', 'US', 'global')")
    language: str = Field(default="it", description="Language code (e.g., 'it', 'en')")
    momentum_score: float = Field(..., ge=0.0, le=1.0, description="Trend momentum score (0-1)")
    source: str = Field(..., description="Source of trend data (e.g., 'google_trends', 'glimpse_api')")

    # Step 08: Revenue optimization fields
    cpm_estimate: float = Field(
        default=5.0,
        ge=0.0,
        description="Estimated CPM for this trend's category (e.g., Tech=$15, Finance=$30)"
    )
    competition_level: str = Field(
        default="medium",
        description="Content saturation level: 'low' | 'medium' | 'high'"
    )
    virality_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Cross-platform growth velocity (Reddit upvotes/h, Twitter retweets/h)"
    )
    historical_match: Optional[str] = Field(
        None,
        description="video_internal_id of similar past video that performed well"
    )
    keyword_match_count: int = Field(
        default=0,
        ge=0,
        description="Step 08.1: Number of vertical keywords matched (for scoring differentiation)"
    )


class SeriesSegment(BaseModel):
    """
    Defines a segment type in a series format template.

    Step 07.5: Part of format engine for repeatable video structures.
    """
    type: str = Field(..., description="Segment identifier: 'hook' | 'problem' | 'solution' | 'cta' | etc.")
    name: str = Field(..., description="Human-readable segment name")
    target_duration_min: int = Field(..., ge=1, description="Minimum target duration in seconds")
    target_duration_max: int = Field(..., ge=1, description="Maximum target duration in seconds")
    description: str = Field(..., description="Purpose and content guidance for this segment")


class SeriesFormat(BaseModel):
    """
    Format template configuration for a video series.

    Step 07.5: Enables brand consistency and repeatable video structures.
    Each series has intro/outro templates and segment structure.

    Example series: "tech_tutorial", "news_flash", "how_to"
    """
    serie_id: str = Field(..., description="Unique series identifier (e.g., 'tech_tutorial')")
    name: str = Field(..., description="Human-readable series name (e.g., 'Tech Tutorial')")
    description: str = Field(..., description="Purpose and scope of this series")

    # Intro/Outro configuration
    intro_duration_seconds: int = Field(default=2, ge=1, description="Target duration for intro")
    intro_veo_prompt: str = Field(..., description="Sora 2 prompt template for intro generation")
    outro_duration_seconds: int = Field(default=3, ge=1, description="Target duration for outro")
    outro_veo_prompt: str = Field(..., description="Sora 2 prompt template for outro generation")

    # Segment structure
    segments: List[SeriesSegment] = Field(..., description="Ordered list of segment templates")

    # Target metrics
    total_target_duration_min: int = Field(default=20, ge=1, description="Minimum target video duration")
    total_target_duration_max: int = Field(default=30, ge=1, description="Maximum target video duration")


class VideoPlan(BaseModel):
    """
    Strategic video concept and planning.

    Step 07.5: Added series_id for format template application.
    """
    working_title: str = Field(..., description="Internal working title (may differ from final)")
    strategic_angle: str = Field(..., description="Why this topic is relevant NOW and why viewers care")
    target_audience: str = Field(..., description="Who this video is for (demographics/psychographics)")
    language: str = Field(default="it", description="Content language code")
    compliance_notes: List[str] = Field(
        default_factory=list,
        description="Compliance checks passed (e.g., 'no medical claims', 'no hate speech')"
    )
    series_id: Optional[str] = Field(
        None,
        description="Step 07.5: Series format identifier (e.g., 'tech_tutorial', 'news_flash')"
    )


class SceneVoiceover(BaseModel):
    """
    Voiceover text mapped to a specific scene for scene-level synchronization.

    Step 07.3: Enables precise sync between script audio and visual scenes.
    Step 07.5: Added segment_type for format engine integration.
    Task 1.3.b: Added emotional_beat from Narrative Architect for visual energy mapping.
    """
    scene_id: int = Field(..., ge=1, description="Scene number this voiceover belongs to")
    voiceover_text: str = Field(..., description="Text to be spoken during this scene")
    est_duration_seconds: int = Field(..., ge=1, description="Estimated speaking duration for this text")
    segment_type: Optional[str] = Field(
        None,
        description="Step 07.5: Segment type from series template (e.g., 'hook', 'problem', 'solution', 'cta')"
    )
    emotional_beat: Optional[str] = Field(
        None,
        description="Task 1.3.b: Emotional beat from Narrative Architect (e.g., 'shock', 'tension', 'relief', 'curiosity')"
    )


class TextOverlay(BaseModel):
    """
    Text overlay planned by AI based on content analysis.

    Phase B1: AI-driven overlay planning for stats, key points, CTAs, and subtitles.
    The Visual Planner's LLM analyzes scene content and suggests overlays.
    """
    text: str = Field(..., description="Text to display on screen")
    timing_start: int = Field(..., ge=0, description="Start time in seconds from scene start")
    timing_duration: int = Field(..., ge=1, description="Display duration in seconds")
    position: str = Field(..., description="Screen position (AI-selected based on content)")
    style: str = Field(..., description="Visual style (AI-selected: bold, subtle, animated, kinetic)")
    purpose: str = Field(..., description="Why this overlay exists (AI reasoning: stat, key_point, cta, subtitle)")


class BRollNote(BaseModel):
    """
    B-roll insertion planned by AI for visual variety and engagement.

    Phase B1: AI-driven B-roll planning based on content needs.
    The Visual Planner's LLM identifies moments where B-roll enhances the message.
    """
    timing_start: int = Field(..., ge=0, description="Start time in seconds from scene start")
    timing_duration: int = Field(..., ge=1, description="B-roll clip duration in seconds")
    description: str = Field(..., description="What B-roll to show (AI-generated description)")
    source_type: str = Field(..., description="Source type (AI-selected: stock, graphic, screen_recording, animation)")
    purpose: str = Field(..., description="Why this B-roll (AI reasoning: data_viz, engagement_break, visual_proof)")


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
    Single visual scene for video generation with external AI tools.

    Phase 1 Refactor: Updated for external AI tool workflow (not integrated generation).
    Output: Scene prompt ready for copy-paste to RunwayML, Luma, Pika, etc.

    Step 07.3: Added voiceover_text for scene-level audio/visual synchronization.
    Step 07.5: Added segment_type for format engine integration.
                scene_id=0 allowed for intro scenes.
    Phase 1: Renamed prompt_for_veo → prompt_for_ai_tool, added tool_suggestion.
    """
    scene_id: int = Field(..., ge=0, description="Scene number in sequence (0=intro, 1+=content)")
    prompt_for_ai_tool: str = Field(
        ...,
        description="Phase 1: Universal video generation prompt for external AI tools (RunwayML, Luma, Pika)"
    )
    tool_suggestion: Optional[str] = Field(
        None,
        description="Phase 1: Recommended AI tool for this scene (e.g., 'RunwayML Gen-3 Alpha', 'Luma Dream Machine', 'Pika Labs')"
    )
    est_duration_seconds: int = Field(..., ge=1, description="Estimated duration of this scene")
    voiceover_text: str = Field(
        default="",
        description="Step 07.3: Text to be spoken during this scene (synced with script)"
    )
    segment_type: Optional[str] = Field(
        None,
        description="Step 07.5: Segment type from series template (e.g., 'intro', 'hook', 'problem', 'solution', 'cta', 'outro')"
    )
    reference_image_path: Optional[str] = Field(
        None,
        description="Phase 1: Path to reference image for this scene (generated on-demand with export-visual-deck command)"
    )
    # Phase B1: AI-driven overlay and B-roll planning
    text_overlays: List[TextOverlay] = Field(
        default_factory=list,
        description="Phase B1: AI-planned text overlays for stats, key points, CTAs, and subtitles"
    )
    broll_notes: List[BRollNote] = Field(
        default_factory=list,
        description="Phase B1: AI-planned B-roll insertions for visual variety and engagement"
    )


class VisualPlan(BaseModel):
    """
    Complete visual direction for video production.

    Step 09: Added visual context tracking for analytics.
    Step 09.5: Added character consistency tracking.
    Step 09.6: Added faceless video mode support.
    Step 09.7: Added AI-driven format selection tracking.
    """
    aspect_ratio: str = Field(default="9:16", description="Video aspect ratio (e.g., '9:16' for Shorts)")
    style_notes: str = Field(..., description="Visual style guidance (colors, pacing, overlays)")
    scenes: List[VisualScene] = Field(..., description="Ordered list of visual scenes")
    # Step 09: Visual context tracking for retention analytics
    visual_context_id: Optional[str] = Field(default=None, description="ID of visual context used (e.g., 'home_gym')")
    visual_context_name: Optional[str] = Field(default=None, description="Name of visual context used (e.g., 'Home Gym Setting')")
    # Step 09.5: Character consistency tracking
    character_profile_id: Optional[str] = Field(default=None, description="ID of character profile used (e.g., 'marco_trainer')")
    character_description: Optional[str] = Field(default=None, description="Persistent identity anchor used in all scene prompts")
    # Step 09.6: Faceless video mode tracking
    video_style_mode: Optional[str] = Field(default="character_based", description="Video style mode: 'faceless' or 'character_based'")
    # Step 09.7: AI-driven format selection tracking
    ai_selected_format: Optional[str] = Field(default=None, description="AI-selected visual format for faceless videos (e.g., 'whiteboard_animation', 'kinetic_typography')")
    format_rationale: Optional[str] = Field(default=None, description="Why AI chose this format (for analytics and debugging)")


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


class ContentPackage(BaseModel):
    """
    Complete content package from AI-driven editorial strategy.

    Phase 1 Refactor: Renamed from ReadyForFactory to better reflect content-first approach.
    Output: Markdown-formatted package with scene prompts for external AI tools.

    Contains:
    - Strategic editorial decision (AI reasoning)
    - Structured script and visual plan
    - SEO-optimized metadata
    - Scene-by-scene prompts for video generation tools

    Step 07: Added audit trail fields for LLM script tracking.
    Step 11: Added editorial_decision for AI strategy tracking and analytics.
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
    editorial_decision: Optional['EditorialDecision'] = Field(
        None,
        description="Step 11: AI-driven editorial strategy used for this video (for performance analytics and learning loop)"
    )
    # AI Decision Rationale - For content_package.md transparency
    duration_strategy_reasoning: Optional[str] = Field(
        None,
        description="Duration Strategist reasoning: Why this duration maximizes revenue + engagement"
    )
    format_reconciliation_reasoning: Optional[str] = Field(
        None,
        description="Format Reconciler reasoning: Why final duration was chosen (arbitration between Editorial and Duration)"
    )
    narrative_design_reasoning: Optional[str] = Field(
        None,
        description="Narrative Architect reasoning: Why this voice personality and arc structure"
    )
    cta_strategy_reasoning: Optional[str] = Field(
        None,
        description="CTA Strategist reasoning: Why CTAs placed at these specific timestamps"
    )
    # Priority 1: Additional reasoning fields for comprehensive AI Decision Log
    editorial_strategy_reasoning: Optional[str] = Field(
        None,
        description="Editorial Strategist reasoning: Why serie/format/angle/CTA chosen for this topic"
    )
    content_depth_reasoning: Optional[str] = Field(
        None,
        description="Content Depth Strategist reasoning: Why this bullets count and time allocation"
    )
    trend_selection_reasoning: Optional[str] = Field(
        None,
        description="Trend Hunter reasoning: Why this trend selected over others (momentum, fit, timeliness)"
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


class VideoPerformance(BaseModel):
    """
    Performance metrics and metadata for learning system.

    Step 08: Tracks actual performance to optimize format selection and trend scoring.
    """
    video_internal_id: str = Field(..., description="Unique internal video identifier")
    youtube_video_id: Optional[str] = Field(None, description="YouTube video ID after publication")
    format_type: str = Field(
        ...,
        description="Content format: 'tutorial' | 'news_reaction' | 'listicle' | 'deep_dive' | 'challenge'"
    )
    trend_source: str = Field(..., description="Primary trend source: 'youtube' | 'reddit' | 'google_trends' | 'hackernews'")
    vertical_category: str = Field(..., description="Content vertical: 'tech_ai' | 'finance' | 'gaming' | 'education'")

    # Performance metrics
    views_24h: int = Field(default=0, ge=0, description="Views in first 24 hours")
    views_7d: int = Field(default=0, ge=0, description="Views in first 7 days")
    ctr: float = Field(default=0.0, ge=0.0, le=1.0, description="Click-through rate")
    avg_watch_time_seconds: float = Field(default=0.0, ge=0.0, description="Average watch time")
    revenue_estimated: float = Field(default=0.0, ge=0.0, description="Estimated revenue from YouTube Analytics")
    cpm_actual: float = Field(default=0.0, ge=0.0, description="Actual CPM from YouTube Analytics")

    # Content metadata
    topic_keywords: List[str] = Field(default_factory=list, description="Main topic keywords for similarity matching")
    is_experiment: bool = Field(default=False, description="True if part of 20% experiment batch")
    published_at: Optional[str] = Field(None, description="ISO 8601 publication timestamp")


class VerticalConfig(BaseModel):
    """
    Configuration for a specific content vertical (Tech, Finance, Gaming, etc.).

    Step 08: Enables multi-account scaling with vertical-specific optimization.
    """
    vertical_id: str = Field(..., description="Unique identifier: 'tech_ai' | 'finance' | 'gaming' | 'education'")
    cpm_baseline: float = Field(..., ge=0.0, description="Expected baseline CPM for this vertical")
    target_keywords: List[str] = Field(..., description="Core keywords for trend filtering")
    reddit_subreddits: List[str] = Field(default_factory=list, description="Relevant subreddits to monitor")
    youtube_category_id: str = Field(..., description="YouTube category ID (e.g., '28' for Science & Tech)")
    competitor_channels: List[str] = Field(default_factory=list, description="Competitor channel IDs to analyze")
    proven_formats: dict = Field(
        default_factory=dict,
        description="Format allocation percentages: {'tutorial': 0.35, 'news_reaction': 0.25, ...}"
    )


class ChannelMemory(BaseModel):
    """
    Persistent channel brand memory and history.

    Step 08: Extended with vertical configuration for multi-account support.
    """
    brand_tone: str = Field(..., description="Channel's consistent tone of voice")
    visual_style: str = Field(..., description="Channel's consistent visual identity")
    banned_topics: List[str] = Field(..., description="Topics to avoid for compliance/brand safety")
    recent_titles: List[str] = Field(
        default_factory=list,
        description="Recent video titles to avoid repetition"
    )

    # Step 08: Multi-vertical support
    vertical_category: str = Field(
        default="tech_ai",
        description="Active vertical category for this channel"
    )
    vertical_config: Optional[dict] = Field(
        None,
        description="Vertical-specific configuration (VerticalConfig as dict)"
    )


class EditorialDecision(BaseModel):
    """
    AI-generated editorial strategy decision for a video.

    This schema captures the strategic reasoning from the Editorial Strategist agent,
    which uses LLM reasoning to determine how to transform a trend into a video that:
    - Strengthens brand positioning (not just reactive news)
    - Monetizes effectively (has clear next step)
    - Educates the audience (goes beyond entertainment)
    - Stands out from competitors (unique angle)

    The decision is AI-driven and context-aware, not based on rigid templates.
    It considers workspace config, performance history, and competitor landscape.
    """
    # Serie & Format Strategy
    serie_concept: str = Field(
        ...,
        description="Serie name that this video belongs to. Can be existing or LLM-suggested new serie. Examples: 'Market Watch', 'Bubble Alert', 'Investor Lessons'"
    )
    format: str = Field(
        ...,
        description="Content format type. Options: 'tutorial' (step-by-step actionable), 'analysis' (context + insight + implication), 'alert' (risk + defense), 'comparison' (options + recommendation)"
    )
    angle: str = Field(
        ...,
        description="Content angle for this video. Options: 'risk' (threat identification), 'opportunity' (actionable upside), 'education' (learning layer), 'history' (past context)"
    )

    # Duration Strategy
    duration_target: int = Field(
        ...,
        ge=15,
        le=1200,  # MONETIZATION REFACTOR: Support up to 20min for long-form monetization
        description="Target video duration in seconds. LLM decides based on CPM baseline, content depth, and format. Short (<60s), Mid (60s-8min), Long (8-20min)."
    )
    duration_breakdown: dict = Field(
        ...,
        description="Time allocation breakdown. Keys: 'hook' (attention grab), 'context' (setup), 'insight' (educational layer), 'cta' (call-to-action). Values in seconds."
    )

    # Monetization Strategy
    monetization_path: str = Field(
        ...,
        description="Monetization next step. Options: 'lead_magnet' (downloadable resource), 'playlist' (serie continuation), 'comment_trigger' (engagement keyword), 'external' (tool/partner link)"
    )
    cta_specific: str = Field(
        ...,
        description="Exact CTA text to use in video. Not a template - specific to this video's monetization path. Example: 'Scrivi BURRY e ti mando i 3 indicatori'"
    )

    # Reasoning & Context
    reasoning_summary: str = Field(
        ...,
        description="2-3 sentence summary of WHY these strategic choices were made. Captures LLM reasoning for analytics and debugging."
    )

    # Optional Performance Context
    performance_context: Optional[str] = Field(
        None,
        description="Performance insights that influenced this decision (e.g., 'Analysis format has 25% higher retention than tutorial for this vertical')"
    )


class Timeline(BaseModel):
    """
    Single source of truth for video duration and temporal structure.

    Created by Format Reconciler after arbitrating between Editorial and Duration
    strategies. All downstream agents (Narrative, Script, Visual) receive this
    object to ensure duration consistency across the entire pipeline.

    Phase C - Sprint 1: Revenue-critical duration management.
    Eliminates "weak agency contract" problem where agents used different duration values.

    Example Usage:
        >>> timeline = Timeline(
        ...     reconciled_duration=420,  # 7 minutes
        ...     format_type='mid',
        ...     arbitration_source='compromise',
        ...     editorial_weight=0.6,
        ...     duration_weight=0.4,
        ...     arbitration_reasoning='Editorial needs 3-point breakdown, Duration wants ad slots',
        ...     editorial_duration_original=240,
        ...     duration_strategy_original=600
        ... )
        >>> print(timeline.reconciled_duration)  # 420 (all agents use this)
    """

    # Core duration fields (single source of truth)
    reconciled_duration: int = Field(
        ...,
        ge=15,
        le=1200,
        description="Final reconciled duration in seconds after Format Reconciler arbitration. This is the single source of truth for all agents."
    )

    format_type: str = Field(
        ...,
        description="Video format tier based on duration: 'short' (<60s), 'mid' (60s-8min), 'long' (8min+). Used for monetization strategy."
    )

    aspect_ratio: str = Field(
        default="9:16",
        description="Video aspect ratio. Typically '9:16' for short, '16:9' for mid/long, but can be overridden by workspace config."
    )

    # Arbitration audit trail (for transparency, analytics, and debugging)
    arbitration_source: str = Field(
        ...,
        description="Which strategy influenced final decision: 'editorial_strategist' | 'duration_strategist' | 'compromise' | 'duration_strategist_fallback'"
    )

    editorial_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How much Editorial Strategist influenced final duration (0-1). Should sum with duration_weight to 1.0."
    )

    duration_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="How much Duration Strategist influenced final duration (0-1). Should sum with editorial_weight to 1.0."
    )

    arbitration_reasoning: str = Field(
        ...,
        description="LLM explanation of why this duration was chosen. Used for analytics, debugging, and audit trail."
    )

    # Original strategy durations (for comparison, analytics, and debugging)
    editorial_duration_original: int = Field(
        ...,
        ge=15,
        le=1200,
        description="Original duration proposed by Editorial Strategist (before arbitration)."
    )

    duration_strategy_original: int = Field(
        ...,
        ge=15,
        le=1200,
        description="Original duration proposed by Duration Strategist (before arbitration)."
    )

    # Optional: Segment-level timing constraints (from Editorial Strategist)
    duration_breakdown: Optional[Dict[str, int]] = Field(
        default=None,
        description="Time allocation by segment: {'hook': 3, 'context': 8, 'insight': 10, 'cta': 5}. Total should match reconciled_duration. Useful for segment-aware validation."
    )

    # Metadata
    created_at_step: str = Field(
        default="format_reconciler",
        description="Pipeline step where Timeline was created (always 'format_reconciler' in current architecture)."
    )
