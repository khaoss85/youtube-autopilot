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
            keyword="Gardening Tips Spring 2025",
            why_hot="Seasonal gardening interest peaking with spring approaching",
            region="IT",
            language="it",
            momentum_score=0.92,
            source="mock_google_trends"
        ),
        TrendCandidate(
            keyword="Photography Techniques Night Sky",
            why_hot="Astrophotography gaining popularity among hobbyists",
            region="IT",
            language="it",
            momentum_score=0.85,
            source="mock_twitter_trends"
        ),
        TrendCandidate(
            keyword="Cooking Mediterranean Recipes",
            why_hot="Healthy eating and traditional cuisine trending together",
            region="IT",
            language="it",
            momentum_score=0.88,
            source="mock_reddit_trends"
        ),
    ]

    logger.info(f"✓ Fetched {len(mock_trends)} trend candidates")
    for trend in mock_trends:
        logger.debug(
            f"  - '{trend.keyword}' (score: {trend.momentum_score:.2f}, "
            f"source: {trend.source})"
        )

    return mock_trends
