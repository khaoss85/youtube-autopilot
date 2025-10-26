"""
Hacker News Trend Source: Fetches top stories from Hacker News API.

Step 08 Phase 2: Hacker News integration for tech/startup trends

Hacker News (news.ycombinator.com) is a premier source for tech news and trends.
The API is public, free, and requires no authentication.

API Docs: https://github.com/HackerNews/API
"""

from typing import List, Optional
from yt_autopilot.core.schemas import TrendCandidate
from yt_autopilot.core.logger import logger
from yt_autopilot.core.config import get_vertical_config
import requests


# Hacker News API endpoints
HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_TOP_STORIES = f"{HN_BASE_URL}/topstories.json"
HN_BEST_STORIES = f"{HN_BASE_URL}/beststories.json"
HN_ITEM = f"{HN_BASE_URL}/item/{{}}.json"  # Format with item ID


def _fetch_story_details(story_id: int) -> Optional[dict]:
    """
    Fetches details for a single Hacker News story.

    Args:
        story_id: Hacker News story ID

    Returns:
        Story dict or None if fetch failed

    API Response Example:
        {
            "by": "username",
            "descendants": 42,  # Comment count
            "id": 12345,
            "kids": [123, 456, ...],  # Comment IDs
            "score": 234,
            "time": 1234567890,
            "title": "Amazing new tech",
            "type": "story",
            "url": "https://example.com"
        }
    """
    try:
        url = HN_ITEM.format(story_id)
        response = requests.get(url, timeout=5)
        response.raise_for_status()

        story = response.json()
        return story if story else None

    except Exception as e:
        logger.debug(f"Failed to fetch HN story {story_id}: {e}")
        return None


def fetch_hackernews_top(
    vertical_id: str = "tech_ai",
    max_results: int = 20,
    min_score: int = 100
) -> List[TrendCandidate]:
    """
    Fetches top trending stories from Hacker News.

    Step 08 Phase 2: HN top stories for tech trends

    Args:
        vertical_id: Content vertical (only 'tech_ai' and 'education' get HN data)
        max_results: Max number of stories to fetch
        min_score: Minimum score threshold (100+ = trending)

    Returns:
        List of TrendCandidate objects from HN top stories

    Algorithm:
        1. Fetch top story IDs from HN API
        2. Fetch details for each story
        3. Filter by min_score and vertical relevance
        4. Calculate momentum from score
        5. Calculate virality from comments/score ratio
        6. Convert to TrendCandidate

    Note:
        Hacker News is primarily tech/startup focused.
        Only useful for 'tech_ai' and 'education' verticals.

    Example:
        >>> trends = fetch_hackernews_top("tech_ai", max_results=10)
        >>> print(f"Found {len(trends)} HN trending stories")
        Found 10 HN trending stories
    """
    # HN is only relevant for tech and education verticals
    if vertical_id not in ["tech_ai", "education"]:
        logger.debug(f"Hacker News not relevant for vertical '{vertical_id}' - skipping")
        return []

    vertical_config = get_vertical_config(vertical_id)
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0) if vertical_config else 10.0

    try:
        logger.info("Fetching Hacker News top stories...")

        # Fetch top story IDs
        response = requests.get(HN_TOP_STORIES, timeout=10)
        response.raise_for_status()

        story_ids = response.json()[:max_results]  # Limit to max_results

        logger.debug(f"  Retrieved {len(story_ids)} top story IDs from HN")

        # Fetch details for each story
        trends = []
        for story_id in story_ids:
            story = _fetch_story_details(story_id)

            if not story:
                continue

            # Extract story data
            title = story.get("title", "")
            score = story.get("score", 0)
            num_comments = story.get("descendants", 0)
            url = story.get("url", "")

            # Filter by minimum score
            if score < min_score:
                continue

            # Calculate momentum score (0-1)
            # HN top stories typically have 100-500 points
            # 500+ points = 1.0 momentum
            momentum_score = min(1.0, score / 500.0)

            # Calculate virality score
            # High comment/score ratio = high engagement/virality
            if score > 0:
                comment_ratio = num_comments / score
                virality_score = min(1.0, comment_ratio / 0.5)  # 0.5 ratio = 1.0 virality
            else:
                virality_score = 0.5

            # Estimate competition
            # HN stories with >100 comments are heavily discussed (high competition)
            if num_comments > 100:
                competition = "high"
            elif num_comments > 30:
                competition = "medium"
            else:
                competition = "low"

            # Generate why_hot explanation
            why_hot = f"Trending on Hacker News ({score} points, {num_comments} comments)"
            if score > 300:
                why_hot += " - very hot discussion"

            trend = TrendCandidate(
                keyword=title,
                why_hot=why_hot,
                region="GLOBAL",  # HN is global, tech-focused
                language="en",
                momentum_score=momentum_score,
                source="hackernews",
                cpm_estimate=cpm_baseline,  # Tech CPM baseline
                competition_level=competition,
                virality_score=virality_score,
                historical_match=None
            )

            trends.append(trend)

        logger.info(f"✓ Fetched {len(trends)} trending stories from Hacker News")
        return trends

    except requests.exceptions.RequestException as e:
        logger.error(f"Hacker News API request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Error processing Hacker News data: {e}")
        return []


def fetch_hackernews_best(
    vertical_id: str = "tech_ai",
    max_results: int = 15
) -> List[TrendCandidate]:
    """
    Fetches best stories from Hacker News (highest quality, not necessarily newest).

    Step 08 Phase 2: HN best stories for evergreen content ideas

    Args:
        vertical_id: Content vertical
        max_results: Max stories to fetch

    Returns:
        List of TrendCandidate objects from HN best stories

    Note:
        Best stories are curated by HN algorithm for quality.
        Good for evergreen content ideas that have proven engagement.
    """
    if vertical_id not in ["tech_ai", "education"]:
        return []

    vertical_config = get_vertical_config(vertical_id)
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0) if vertical_config else 10.0

    try:
        logger.info("Fetching Hacker News best stories...")

        # Fetch best story IDs
        response = requests.get(HN_BEST_STORIES, timeout=10)
        response.raise_for_status()

        story_ids = response.json()[:max_results]

        trends = []
        for story_id in story_ids:
            story = _fetch_story_details(story_id)

            if not story:
                continue

            title = story.get("title", "")
            score = story.get("score", 0)
            num_comments = story.get("descendants", 0)

            # Best stories are already curated, so lower threshold
            if score < 50:
                continue

            momentum_score = min(1.0, score / 500.0)
            virality_score = min(1.0, (num_comments / score) / 0.5) if score > 0 else 0.5

            competition = "medium" if num_comments > 50 else "low"

            trend = TrendCandidate(
                keyword=title,
                why_hot=f"HN best story ({score} points) - high quality content",
                region="GLOBAL",
                language="en",
                momentum_score=momentum_score,
                source="hackernews_best",
                cpm_estimate=cpm_baseline,
                competition_level=competition,
                virality_score=virality_score,
                historical_match=None
            )

            trends.append(trend)

        logger.info(f"✓ Fetched {len(trends)} best stories from Hacker News")
        return trends

    except Exception as e:
        logger.error(f"Hacker News best stories fetch failed: {e}")
        return []
