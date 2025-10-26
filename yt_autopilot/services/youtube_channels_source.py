"""
YouTube Channels Source: Fetches latest videos from specific influencer/competitor channels.

This source allows tracking content from top influencers and competitors in each vertical
for trend discovery and first-mover advantage.

Uses YouTube Data API v3 PlaylistItems endpoint (quota efficient: 2 points vs 100 for search).
"""

from typing import List, Optional
from yt_autopilot.core.schemas import TrendCandidate
from yt_autopilot.core.logger import logger
from yt_autopilot.core.config import get_env, get_vertical_config

try:
    from googleapiclient.discovery import build
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False
    logger.warning("googleapiclient not installed - YouTube channels trending will be disabled")


def _get_youtube_client():
    """
    Creates YouTube Data API v3 client.

    Returns:
        YouTube API client or None if API key missing
    """
    if not YOUTUBE_API_AVAILABLE:
        return None

    api_key = get_env("YOUTUBE_DATA_API_KEY")
    if not api_key:
        logger.warning("YouTube Data API key not configured - skipping YouTube channels")
        return None

    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        return youtube
    except Exception as e:
        logger.error(f"Failed to create YouTube API client: {e}")
        return None


def _channel_id_to_uploads_playlist_id(channel_id: str) -> str:
    """
    Converts channel ID to uploads playlist ID.

    YouTube stores all channel uploads in a special playlist.
    Playlist ID = channel ID with "UU" replacing "UC" prefix.

    Args:
        channel_id: YouTube channel ID (starts with UC)

    Returns:
        Uploads playlist ID (starts with UU)

    Example:
        >>> _channel_id_to_uploads_playlist_id("UC2u8lxKjsJrfuNResAuz3bA")
        "UU2u8lxKjsJrfuNResAuz3bA"
    """
    if channel_id.startswith("UC"):
        return "UU" + channel_id[2:]
    return channel_id  # Already converted or non-standard format


def fetch_channel_latest_videos(
    channel_id: str,
    channel_name: str,
    max_results: int = 10,
    vertical_id: str = "tech_ai"
) -> List[TrendCandidate]:
    """
    Fetches latest videos from a specific YouTube channel.

    Uses PlaylistItems API to get uploads playlist (quota: 2 points per request).

    Args:
        channel_id: YouTube channel ID (e.g., "UC2u8lxKjsJrfuNResAuz3bA")
        channel_name: Channel display name (e.g., "ATHLEAN-X")
        max_results: Number of latest videos to fetch (default: 10)
        vertical_id: Content vertical for CPM estimation

    Returns:
        List of TrendCandidate objects from channel's latest videos

    Algorithm:
        1. Convert channel_id to uploads playlist ID (UC → UU)
        2. Fetch latest videos from uploads playlist
        3. Calculate momentum from view count and publish time
        4. Convert to TrendCandidate with source priority bonus

    Quota Cost: 2 points (vs 100 for search endpoint)
    """
    youtube = _get_youtube_client()
    if not youtube:
        return []

    vertical_config = get_vertical_config(vertical_id)
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0) if vertical_config else 10.0

    # Convert channel ID to uploads playlist ID
    uploads_playlist_id = _channel_id_to_uploads_playlist_id(channel_id)

    try:
        # Fetch latest videos from uploads playlist
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=max_results,
            fields="items(snippet(title,publishedAt,channelTitle),contentDetails(videoId))"
        )
        response = request.execute()

        trends = []
        for item in response.get('items', []):
            snippet = item['snippet']
            video_id = item['contentDetails']['videoId']

            title = snippet['title']
            published_at = snippet['publishedAt']

            # Calculate momentum score
            # For channels, we prioritize recency over view count
            # (competitor channels are high-quality by definition)
            momentum_score = 0.75  # High baseline for curated channels

            # Generate why_hot explanation
            why_hot = f"Latest from {channel_name} (top influencer/competitor in {vertical_id})"

            trend = TrendCandidate(
                keyword=title,
                why_hot=why_hot,
                region="GLOBAL",
                language="en",  # Most fitness/tech channels are English
                momentum_score=momentum_score,
                source=f"youtube_channel_{channel_name.lower().replace(' ', '_')}",
                cpm_estimate=cpm_baseline,
                competition_level="medium",  # Competitor content = medium competition
                virality_score=0.70,  # Channels produce consistent quality
                historical_match=None
            )

            trends.append(trend)

        logger.debug(f"  {channel_name}: fetched {len(trends)} latest videos")
        return trends

    except Exception as e:
        logger.warning(f"Failed to fetch from channel {channel_name} ({channel_id}): {e}")
        return []


def fetch_youtube_channels_trending(
    vertical_id: str = "tech_ai",
    limit_per_channel: int = 5
) -> List[TrendCandidate]:
    """
    Fetches latest videos from all configured YouTube channels for a vertical.

    This provides trend discovery from top influencers and competitors in the vertical,
    enabling first-mover advantage on new formats and topics.

    Args:
        vertical_id: Content vertical ('tech_ai', 'fitness', 'finance', 'gaming')
        limit_per_channel: Max videos to fetch per channel (default: 5)

    Returns:
        List of TrendCandidate objects from configured YouTube channels

    Example:
        >>> trends = fetch_youtube_channels_trending("fitness", limit_per_channel=5)
        >>> print(f"Found {len(trends)} trends from fitness influencers")
        Found 25 trends from fitness influencers (5 channels × 5 videos)

    Configuration:
        Channels are configured in config.py under vertical["youtube_channels"]:
        {
            "channel_id": "UC2u8lxKjsJrfuNResAuz3bA",
            "name": "ATHLEAN-X",
            "subscribers": "14.1M"
        }
    """
    vertical_config = get_vertical_config(vertical_id)
    if not vertical_config:
        logger.warning(f"Unknown vertical '{vertical_id}' - skipping YouTube channels")
        return []

    channels = vertical_config.get("youtube_channels", [])
    if not channels:
        logger.info(f"No YouTube channels configured for vertical '{vertical_id}'")
        return []

    logger.info(f"Fetching YouTube channels from {len(channels)} influencers/competitors ({vertical_id})...")

    all_trends = []

    for channel in channels:
        channel_id = channel.get("channel_id")
        channel_name = channel.get("name", "Unknown Channel")

        if not channel_id:
            logger.warning(f"Channel '{channel_name}' missing channel_id - skipping")
            continue

        trends = fetch_channel_latest_videos(
            channel_id=channel_id,
            channel_name=channel_name,
            max_results=limit_per_channel,
            vertical_id=vertical_id
        )

        all_trends.extend(trends)

    logger.info(f"✓ Fetched {len(all_trends)} videos from {len(channels)} YouTube channels")
    return all_trends
