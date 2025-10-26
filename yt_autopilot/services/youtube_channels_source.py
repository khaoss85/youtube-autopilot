"""
YouTube Channels Source: Fetches latest videos from specific influencer/competitor channels.

This source allows tracking content from top influencers and competitors in each vertical
for trend discovery and first-mover advantage.

Step 08 Phase A.3: Enhanced with real video statistics for dynamic scoring.

Uses YouTube Data API v3:
- PlaylistItems endpoint (2 points) for video list
- Videos endpoint (1 point) for statistics
- Total: 3 points per batch vs 100 for search (33x more efficient)
"""

from typing import List, Optional
from datetime import datetime, timezone
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


def _calculate_momentum_score(views: int, days_since_published: float, subscriber_count: float) -> float:
    """
    Calculates momentum score based on views, recency, and channel size.

    Step 08 Phase A.3: Dynamic momentum calculation from real data

    Args:
        views: Video view count
        days_since_published: Days since video was published
        subscriber_count: Channel subscriber count (in millions)

    Returns:
        Momentum score (0.5-1.0)

    Algorithm:
        1. Normalize views relative to channel size (views per 1M subscribers)
        2. Apply recency bonus (newer = higher momentum)
        3. Clamp to 0.5-1.0 range (curated channels have high baseline)

    Example:
        - 100K views, 2 days old, 10M subs → 0.85 (strong momentum)
        - 10K views, 7 days old, 1M subs → 0.65 (moderate momentum)
    """
    # Normalize views by subscriber count (per 1M subs)
    if subscriber_count > 0:
        normalized_views = views / subscriber_count
    else:
        normalized_views = views

    # View score: 10K+ views/1M subs = 0.5, 50K+ = 0.75, 100K+ = 1.0
    view_score = min(1.0, normalized_views / 100000.0)

    # Recency bonus: newer videos get boost
    # 0-1 days: +0.15, 1-3 days: +0.10, 3-7 days: +0.05, >7 days: 0
    if days_since_published <= 1:
        recency_bonus = 0.15
    elif days_since_published <= 3:
        recency_bonus = 0.10
    elif days_since_published <= 7:
        recency_bonus = 0.05
    else:
        recency_bonus = 0.0

    # Combine: base 0.5 + view_score (0-0.5) + recency (0-0.15) = 0.5-1.15
    momentum = 0.5 + (view_score * 0.5) + recency_bonus

    # Clamp to 0.5-1.0 range
    return max(0.5, min(1.0, momentum))


def _calculate_virality_score(likes: int, comments: int, views: int) -> float:
    """
    Calculates virality score based on engagement rate.

    Step 08 Phase A.3: Dynamic virality from engagement metrics

    Args:
        likes: Video like count
        comments: Video comment count
        views: Video view count

    Returns:
        Virality score (0-1.0)

    Algorithm:
        Engagement rate = (likes + comments) / views
        - 1%: Low engagement (0.3)
        - 3%: Average engagement (0.5)
        - 5%+: High engagement (0.8-1.0)

    Example:
        - 3K likes, 200 comments, 100K views → 3.2% → 0.64 virality
    """
    if views == 0:
        return 0.5  # Default for videos with no views yet

    engagement_rate = (likes + comments) / views

    # Map engagement rate to virality score
    # 0.01 (1%) → 0.3
    # 0.03 (3%) → 0.5
    # 0.05 (5%) → 0.8
    # 0.10+ (10%+) → 1.0

    if engagement_rate >= 0.10:
        return 1.0
    elif engagement_rate >= 0.05:
        return 0.8 + ((engagement_rate - 0.05) / 0.05) * 0.2  # 0.8-1.0
    elif engagement_rate >= 0.03:
        return 0.5 + ((engagement_rate - 0.03) / 0.02) * 0.3  # 0.5-0.8
    elif engagement_rate >= 0.01:
        return 0.3 + ((engagement_rate - 0.01) / 0.02) * 0.2  # 0.3-0.5
    else:
        return 0.3  # Very low engagement


def _calculate_competition_level(comment_count: int) -> str:
    """
    Calculates competition level based on comment activity.

    Step 08 Phase A.3: Dynamic competition from discussion volume

    Args:
        comment_count: Number of comments

    Returns:
        "low", "medium", or "high"

    Algorithm:
        - <50 comments: "low" (niche/opportunity)
        - 50-200: "medium" (moderate discussion)
        - >200: "high" (crowded/saturated)
    """
    if comment_count > 200:
        return "high"
    elif comment_count >= 50:
        return "medium"
    else:
        return "low"


def fetch_channel_latest_videos(
    channel_id: str,
    channel_name: str,
    max_results: int = 10,
    vertical_id: str = "tech_ai"
) -> List[TrendCandidate]:
    """
    Fetches latest videos from a specific YouTube channel with real statistics.

    Step 08 Phase A.3: Enhanced with real video statistics for dynamic scoring.

    Args:
        channel_id: YouTube channel ID (e.g., "UC2u8lxKjsJrfuNResAuz3bA")
        channel_name: Channel display name (e.g., "ATHLEAN-X")
        max_results: Number of latest videos to fetch (default: 10)
        vertical_id: Content vertical for CPM estimation

    Returns:
        List of TrendCandidate objects from channel's latest videos

    Algorithm:
        1. Convert channel_id to uploads playlist ID (UC → UU)
        2. Fetch latest videos from uploads playlist (2 quota points)
        3. Fetch video statistics in batch (1 quota point)
        4. Calculate dynamic momentum, virality, competition from real data
        5. Convert to TrendCandidate with enhanced scoring

    Quota Cost: 3 points total (vs 100 for search endpoint)
    """
    youtube = _get_youtube_client()
    if not youtube:
        return []

    vertical_config = get_vertical_config(vertical_id)
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0) if vertical_config else 10.0

    # Get subscriber count from config for normalization
    channels_list = vertical_config.get("youtube_channels", []) if vertical_config else []
    subscriber_count_millions = 1.0  # Default
    for ch in channels_list:
        if ch.get("channel_id") == channel_id:
            # Parse subscriber count (e.g., "14.1M" → 14.1)
            subs_str = ch.get("subscribers", "1M")
            try:
                if 'M' in subs_str:
                    subscriber_count_millions = float(subs_str.replace('M', '').replace('K', '000').replace('k', '000'))
                elif 'K' in subs_str or 'k' in subs_str:
                    subscriber_count_millions = float(subs_str.replace('K', '').replace('k', '')) / 1000.0
            except ValueError:
                subscriber_count_millions = 1.0
            break

    # Convert channel ID to uploads playlist ID
    uploads_playlist_id = _channel_id_to_uploads_playlist_id(channel_id)

    try:
        # Step 1: Fetch latest videos from uploads playlist (2 quota points)
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=max_results,
            fields="items(snippet(title,publishedAt,channelTitle),contentDetails(videoId))"
        )
        response = request.execute()

        items = response.get('items', [])
        if not items:
            return []

        # Step 2: Collect video IDs for batch statistics fetch
        video_ids = [item['contentDetails']['videoId'] for item in items]

        # Step 3: Fetch video statistics in batch (1 quota point)
        stats_request = youtube.videos().list(
            part="statistics",
            id=','.join(video_ids),
            fields="items(id,statistics(viewCount,likeCount,commentCount))"
        )
        stats_response = stats_request.execute()

        # Create stats lookup dict
        stats_by_id = {
            item['id']: item['statistics']
            for item in stats_response.get('items', [])
        }

        # Step 4: Build TrendCandidates with real statistics
        trends = []
        for item in items:
            snippet = item['snippet']
            video_id = item['contentDetails']['videoId']

            title = snippet['title']
            published_at = snippet['publishedAt']

            # Parse published date to calculate days since published
            published_dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            now_dt = datetime.now(timezone.utc)
            days_since_published = (now_dt - published_dt).total_seconds() / 86400.0

            # Get video statistics (with defaults if missing)
            stats = stats_by_id.get(video_id, {})
            views = int(stats.get('viewCount', 0))
            likes = int(stats.get('likeCount', 0))
            comments = int(stats.get('commentCount', 0))

            # Calculate dynamic scores using real data
            momentum_score = _calculate_momentum_score(
                views=views,
                days_since_published=days_since_published,
                subscriber_count=subscriber_count_millions
            )

            virality_score = _calculate_virality_score(
                likes=likes,
                comments=comments,
                views=views
            )

            competition_level = _calculate_competition_level(comments)

            # Generate why_hot with real data
            why_hot = f"Latest from {channel_name} ({views:,} views, {days_since_published:.1f} days ago)"
            if views > 0:
                engagement_rate = ((likes + comments) / views * 100)
                why_hot += f", {engagement_rate:.1f}% engagement"

            trend = TrendCandidate(
                keyword=title,
                why_hot=why_hot,
                region="GLOBAL",
                language="en",  # Most fitness/tech channels are English
                momentum_score=momentum_score,
                source=f"youtube_channel_{channel_name.lower().replace(' ', '_')}",
                cpm_estimate=cpm_baseline,
                competition_level=competition_level,
                virality_score=virality_score,
                historical_match=None
            )

            trends.append(trend)

        logger.debug(f"  {channel_name}: fetched {len(trends)} videos with real statistics")
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
