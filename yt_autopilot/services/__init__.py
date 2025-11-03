"""
Services module: External integrations for content strategy.

Content Strategy Focus (Phase 1 Refactor):
- This module handles LLM calls, trend detection, and performance analytics
- Video production services removed (use external AI tools)
- Focus: editorial intelligence, not production automation

Services can read from core but NOT from agents.

Available services:
- llm_router: Centralized multi-provider LLM access (Anthropic Claude, OpenAI GPT)
- trend_source: Fetch trending topics from external APIs (Reddit, YouTube, HackerNews)
- youtube_analytics: Fetch video performance metrics for learning loop
- reference_image_generator: Generate visual references with DALL-E 3 (Phase 1)
"""

from yt_autopilot.services.llm_router import generate_text
from yt_autopilot.services.trend_source import fetch_trends
from yt_autopilot.services.youtube_analytics import fetch_video_metrics
from yt_autopilot.services.reference_image_generator import generate_scene_reference_images

__all__ = [
    "generate_text",
    "fetch_trends",
    "fetch_video_metrics",
    "generate_scene_reference_images",
]
