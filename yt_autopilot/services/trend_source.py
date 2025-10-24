"""
Trend Source Service: Fetches trending topics from external APIs.

This service connects to external trend sources (Google Trends, social media APIs,
etc.) to identify hot topics for video creation.
"""

from typing import List
from yt_autopilot.core.schemas import TrendCandidate
from yt_autopilot.core.logger import logger


def fetch_trends() -> List[TrendCandidate]:
    """
    Fetches trending topics from external sources.

    TODO: Integrate with real trend sources:
    - Google Trends API (unofficial: pytrends library)
    - Twitter/X Trends API
    - Reddit Trending Subreddits
    - YouTube Trending API
    - Custom trend aggregation service

    Current implementation returns mock data for testing.

    Returns:
        List of TrendCandidate objects with momentum scores

    Example:
        >>> trends = fetch_trends()
        >>> print(f"Found {len(trends)} trending topics")
        Found 5 trending topics
    """
    logger.info("Fetching trending topics from external sources...")

    # TODO: Replace with real API calls
    # Example integration points:
    # - pytrends: from pytrends.request import TrendReq
    # - Twitter API: import tweepy
    # - Reddit API: import praw
    # - YouTube API: from googleapiclient.discovery import build

    logger.warning("Using mock trend data - integrate real APIs in production")

    mock_trends = [
        TrendCandidate(
            keyword="AI Video Generation 2025",
            why_hot="Google Veo 3.x release making waves in creator community",
            region="global",
            language="it",
            momentum_score=0.92,
            source="mock_google_trends"
        ),
        TrendCandidate(
            keyword="Remote Work Productivity Hacks",
            why_hot="Post-pandemic work-from-home optimization trending",
            region="IT",
            language="it",
            momentum_score=0.78,
            source="mock_twitter_trends"
        ),
        TrendCandidate(
            keyword="Crypto Market Analysis Q1",
            why_hot="Bitcoin volatility and new regulations creating interest",
            region="global",
            language="en",
            momentum_score=0.85,
            source="mock_reddit_trends"
        ),
        TrendCandidate(
            keyword="Plant-Based Diet Benefits",
            why_hot="Health and sustainability trends converging",
            region="IT",
            language="it",
            momentum_score=0.71,
            source="mock_youtube_trends"
        ),
        TrendCandidate(
            keyword="Side Hustle Ideas 2025",
            why_hot="Economic uncertainty driving creator economy",
            region="global",
            language="it",
            momentum_score=0.88,
            source="mock_social_media"
        ),
    ]

    logger.info(f"✓ Fetched {len(mock_trends)} trend candidates")
    for trend in mock_trends:
        logger.debug(
            f"  - '{trend.keyword}' (score: {trend.momentum_score:.2f}, "
            f"source: {trend.source})"
        )

    return mock_trends
