"""
Services module: External integrations and operations.
Handles video generation (Veo), TTS, ffmpeg assembly, YouTube upload/analytics, and data storage.

Services can read from core but NOT from agents.

Available services:
- trend_source: Fetch trending topics from external APIs
- video_gen_service: Generate video clips using Veo API
- tts_service: Convert text to speech for voiceover
- thumbnail_service: Generate thumbnail images
- video_assemble_service: Assemble final video with ffmpeg
- youtube_uploader: Upload and schedule videos on YouTube
- youtube_analytics: Fetch video performance metrics
"""

from yt_autopilot.services.trend_source import fetch_trends
from yt_autopilot.services.video_gen_service import generate_scenes
from yt_autopilot.services.tts_service import synthesize_voiceover
from yt_autopilot.services.thumbnail_service import generate_thumbnail
from yt_autopilot.services.video_assemble_service import assemble_final_video
from yt_autopilot.services.youtube_uploader import upload_and_schedule
from yt_autopilot.services.youtube_analytics import fetch_video_metrics

__all__ = [
    "fetch_trends",
    "generate_scenes",
    "synthesize_voiceover",
    "generate_thumbnail",
    "assemble_final_video",
    "upload_and_schedule",
    "fetch_video_metrics",
]
