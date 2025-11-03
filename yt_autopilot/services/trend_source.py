"""
Trend Source Service: Fetches trending topics from external APIs.

This service connects to external trend sources (Google Trends, social media APIs,
etc.) to identify hot topics for video creation.

Step 08: Extended with YouTube Data API v3 integration for real trend detection.
"""

from typing import List, Dict, Optional
from yt_autopilot.core.schemas import TrendCandidate
from yt_autopilot.core.logger import logger
from yt_autopilot.core.config import get_youtube_data_api_key, get_vertical_config
import requests

# Step 08 Phase 2: scrapetube fallback
try:
    import scrapetube
    SCRAPETUBE_AVAILABLE = True
except ImportError:
    SCRAPETUBE_AVAILABLE = False
    logger.debug("scrapetube not installed - YouTube scraping fallback disabled")


# ============================================================================
# Step 08: YouTube Data API v3 Integration
# ============================================================================

def _fetch_youtube_trending(
    vertical_id: str = "tech_ai",
    region_code: str = "IT",
    max_results: int = 20
) -> List[TrendCandidate]:
    """
    Fetches trending videos from YouTube Data API v3 filtered by vertical.

    Step 08: Real API integration for trending video discovery

    Args:
        vertical_id: Vertical category ('tech_ai', 'finance', 'gaming', 'education')
        region_code: ISO country code ('IT', 'US', 'GB', etc.)
        max_results: Number of trending videos to fetch (max 50)

    Returns:
        List of TrendCandidate objects from YouTube trending videos

    API Cost:
        - videos.list with chart=mostPopular: 1 quota unit per call
        - Free tier: 10,000 units/day (10,000 calls)

    Docs:
        https://developers.google.com/youtube/v3/docs/videos/list
    """
    api_key = get_youtube_data_api_key()
    if not api_key:
        logger.warning("YouTube Data API key not configured - skipping YouTube trends")
        return []

    vertical_config = get_vertical_config(vertical_id)
    if not vertical_config:
        logger.warning(f"Unknown vertical_id '{vertical_id}' - using generic config")
        vertical_config = {"cpm_baseline": 10.0, "target_keywords": []}

    category_id = vertical_config.get("youtube_category_id", "")
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0)
    target_keywords = vertical_config.get("target_keywords", [])

    # Build API request
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region_code,
        "maxResults": max_results,
        "key": api_key
    }

    # Add category filter if available
    if category_id:
        params["videoCategoryId"] = category_id

    try:
        logger.info(f"Fetching YouTube trending videos (category:{category_id}, region:{region_code})...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        items = data.get("items", [])

        logger.info(f"✓ Retrieved {len(items)} trending videos from YouTube API")

        # Convert YouTube videos to TrendCandidate objects
        trends = []
        for item in items:
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})

            title = snippet.get("title", "")
            description = snippet.get("description", "")
            view_count = int(statistics.get("viewCount", 0))
            published_at = snippet.get("publishedAt", "")

            # Calculate momentum score based on view velocity
            # (simplified: higher view count = higher momentum)
            momentum = min(1.0, view_count / 1000000.0)  # 1M views = 1.0 score

            # Estimate competition level based on view count distribution
            if view_count > 500000:
                competition = "high"
            elif view_count > 100000:
                competition = "medium"
            else:
                competition = "low"

            # Calculate virality score (view count relative to publish date)
            # Simplified: just use momentum for now
            virality = momentum

            # Check keyword relevance
            title_lower = title.lower()
            description_lower = description.lower()
            keyword_matches = sum(
                1 for kw in target_keywords
                if kw.lower() in title_lower or kw.lower() in description_lower
            )

            # Step 08.1 revised: Track keyword matches but don't filter out
            # Scoring function will penalize low keyword match counts
            # This allows YouTube trending to show results while preferring relevant ones

            # Generate "why_hot" explanation
            why_hot = f"Trending on YouTube ({view_count:,} views). "
            if keyword_matches > 0:
                why_hot += f"Relevant to {vertical_id} ({keyword_matches} keyword matches)."

            trend = TrendCandidate(
                keyword=title,
                why_hot=why_hot,
                region=region_code,
                language="it" if region_code == "IT" else "en",
                momentum_score=momentum,
                source="youtube_trending",
                cpm_estimate=cpm_baseline,  # Use vertical baseline
                competition_level=competition,
                virality_score=virality,
                historical_match=None,  # No historical match yet
                keyword_match_count=keyword_matches  # Step 08.1: Track for scoring
            )

            trends.append(trend)

        logger.info(f"✓ Converted {len(trends)} YouTube videos to TrendCandidates")
        return trends

    except requests.exceptions.RequestException as e:
        logger.error(f"YouTube Data API request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Error processing YouTube trending data: {e}")
        return []


def _fetch_youtube_search(
    query: str,
    vertical_id: str = "tech_ai",
    region_code: str = "IT",
    max_results: int = 10
) -> List[TrendCandidate]:
    """
    Searches YouTube for recent high-performing videos matching a query.

    Step 08: Search-based trend discovery for specific topics

    Args:
        query: Search query (e.g., "ChatGPT tutorial")
        vertical_id: Vertical category for CPM estimation
        region_code: ISO country code
        max_results: Number of results to fetch

    Returns:
        List of TrendCandidate objects from search results

    API Cost:
        - search.list: 100 quota units per call
        - Free tier: 10,000 units/day (100 calls)
    """
    api_key = get_youtube_data_api_key()
    if not api_key:
        return []

    vertical_config = get_vertical_config(vertical_id)
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0) if vertical_config else 10.0

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "viewCount",  # Most viewed first
        "publishedAfter": "2025-01-01T00:00:00Z",  # Recent videos only
        "regionCode": region_code,
        "maxResults": max_results,
        "key": api_key
    }

    try:
        logger.info(f"Searching YouTube for '{query}'...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        items = data.get("items", [])

        logger.info(f"✓ Found {len(items)} videos for query '{query}'")

        trends = []
        for item in items:
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")

            trend = TrendCandidate(
                keyword=title,
                why_hot=f"Popular search result for '{query}' on YouTube",
                region=region_code,
                language="it" if region_code == "IT" else "en",
                momentum_score=0.7,  # Medium momentum for search results
                source="youtube_search",
                cpm_estimate=cpm_baseline,
                competition_level="medium",
                virality_score=0.6,
                historical_match=None,
                keyword_match_count=1  # Step 08.1: Search query = 1 keyword match minimum
            )
            trends.append(trend)

        return trends

    except Exception as e:
        logger.error(f"YouTube search API error: {e}")
        return []


def _fetch_youtube_scrape(
    vertical_id: str = "tech_ai",
    max_results: int = 20
) -> List[TrendCandidate]:
    """
    Scrapes YouTube trending videos using scrapetube (no API key required).

    Step 08 Phase 2: YouTube scraping fallback when API quota exceeded

    Args:
        vertical_id: Vertical category for CPM estimation
        max_results: Number of videos to scrape

    Returns:
        List of TrendCandidate objects from scraped YouTube data

    Note:
        This is a FALLBACK method when YouTube Data API is unavailable.
        Pros: No API quota limits, no authentication
        Cons: Slower, can break if YouTube changes HTML, risk of IP ban

    Warning:
        Use sparingly. Prefer YouTube Data API for production.
    """
    if not SCRAPETUBE_AVAILABLE:
        logger.warning("scrapetube not installed - cannot fallback to scraping")
        return []

    vertical_config = get_vertical_config(vertical_id)
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0) if vertical_config else 10.0

    try:
        logger.info(f"Scraping YouTube trending videos (fallback mode, no API)...")

        # Scrape trending videos (no region/category filter in scrapetube)
        videos = scrapetube.get_channel(channel_url="https://www.youtube.com/feed/trending")

        trends = []
        count = 0

        for video in videos:
            if count >= max_results:
                break

            title = video.get("title", {}).get("runs", [{}])[0].get("text", "")
            if not title:
                continue

            # Extract view count (if available)
            view_text = video.get("viewCountText", {}).get("simpleText", "0 views")
            # Parse "1.2M views" → 1200000
            try:
                view_count_str = view_text.replace(" views", "").replace(",", "")
                if "K" in view_count_str:
                    view_count = int(float(view_count_str.replace("K", "")) * 1000)
                elif "M" in view_count_str:
                    view_count = int(float(view_count_str.replace("M", "")) * 1000000)
                else:
                    view_count = int(view_count_str)
            except:
                view_count = 0

            # Calculate momentum (simplified)
            momentum = min(1.0, view_count / 1000000.0)

            trend = TrendCandidate(
                keyword=title,
                why_hot=f"Scraped from YouTube trending ({view_count:,} views)",
                region="GLOBAL",
                language="en",  # scrapetube doesn't provide language easily
                momentum_score=momentum,
                source="youtube_scrape",
                cpm_estimate=cpm_baseline,
                competition_level="medium",
                virality_score=momentum,
                historical_match=None
            )

            trends.append(trend)
            count += 1

        logger.info(f"✓ Scraped {len(trends)} trending videos from YouTube")
        return trends

    except Exception as e:
        logger.error(f"YouTube scraping failed: {e}")
        return []


# ============================================================================
# Step 08 Phase A: Intelligent Curation - Spam Filtering & Quality Thresholds
# ============================================================================

def _is_spam_keyword(trend: TrendCandidate, vertical_id: str = None) -> bool:
    """
    Detects spam patterns in trend keywords that indicate low-quality content.

    Phase A.1: Pre-filtering layer to remove viral spam before LLM curation
    Extended: Also filters vertical-specific banned topics (e.g., hardware for tech_ai)

    Args:
        trend: TrendCandidate to evaluate
        vertical_id: Optional vertical ID to load vertical-specific banned topics

    Returns:
        True if keyword contains spam patterns or banned topics, False otherwise

    Spam Patterns (YouTube-specific):
        - Product reviews/comparisons: "vs", "review", "unboxing", "compared"
        - Sensational tests: "test", "challenge", "experiment"
        - Clickbait: "shocking", "you won't believe", "insane"
        - Generic tutorials: "how to make", "easy tutorial"

    Quality Content Signals:
        - Educational: "explained", "deep dive", "understanding"
        - News/Analysis: "breaking", "announced", "released"
        - Technical: "API", "architecture", "implementation"
    """
    keyword_lower = trend.keyword.lower()

    # YouTube spam blacklist (common low-quality patterns)
    spam_patterns = [
        # Product reviews (often affiliate spam)
        " vs ", " vs. ", "versus", " review", "unboxing", "compared to",

        # Sensational tests/challenges (viral but low educational value)
        " test", "battery test", "speed test", "durability test",
        "challenge", "experiment", "trying",

        # Clickbait patterns
        "you won't believe", "shocking", "insane", "crazy",
        "this is why", "the truth about", "secret",

        # Generic low-effort tutorials
        "how to make", "easy tutorial", "in 5 minutes",
        "simple trick", "life hack",

        # Spam keywords (common in low-quality content)
        "clickbait", "reaction", "prank", "tiktok compilation",
        "best of", "top 10", "top 5"
    ]

    # Check if keyword contains spam patterns
    for pattern in spam_patterns:
        if pattern in keyword_lower:
            logger.debug(f"Spam detected in '{trend.keyword[:50]}': pattern '{pattern}'")
            return True

    # NEW: Check vertical-specific banned topics
    if vertical_id:
        from yt_autopilot.core.config import get_vertical_config
        vertical_config = get_vertical_config(vertical_id)
        banned_topics = vertical_config.get("banned_topics", [])

        for banned in banned_topics:
            if banned.lower() in keyword_lower:
                logger.debug(f"Vertical banned topic '{banned}' detected in '{trend.keyword[:50]}'")
                return True

    return False


def _meets_quality_threshold(trend: TrendCandidate, vertical_id: str = None) -> bool:
    """
    Enforces minimum quality thresholds based on trend source and vertical.

    Phase A.1: Quality gate to filter out low-engagement content

    Args:
        trend: TrendCandidate to evaluate
        vertical_id: Vertical identifier for vertical-specific thresholds

    Returns:
        True if trend meets quality threshold, False otherwise

    Thresholds by Source (default):
        - Reddit: min 500 upvotes (momentum_score proxy)
        - Hacker News: min 100 points
        - YouTube: min 50K views (filtered by spam patterns instead)

    Note:
        - Reddit rising posts get lower threshold (300) for early signals
        - Business-focused verticals (tech_ai) get 5x lower thresholds for smaller subreddits
    """
    source = trend.source.lower()

    # Business-focused verticals have smaller subreddits = lower engagement
    # Apply 5x lower thresholds for tech_ai (SaaS/startup subreddits)
    is_business_vertical = vertical_id in ["tech_ai"]
    threshold_multiplier = 0.2 if is_business_vertical else 1.0

    # Reddit quality thresholds
    if "reddit" in source:
        # Rising posts = early signals, lower threshold
        if "rising" in source:
            min_momentum = 0.3 * threshold_multiplier  # Default: ~300-500 upvotes, tech_ai: ~60-100 upvotes
            if trend.momentum_score < min_momentum:
                logger.debug(
                    f"Reddit rising trend '{trend.keyword[:50]}' below threshold "
                    f"(momentum: {trend.momentum_score:.2f} < {min_momentum})"
                )
                return False
        else:
            # Hot posts = proven engagement, higher threshold
            min_momentum = 0.5 * threshold_multiplier  # Default: ~500+ upvotes, tech_ai: ~100+ upvotes
            if trend.momentum_score < min_momentum:
                logger.debug(
                    f"Reddit hot trend '{trend.keyword[:50]}' below threshold "
                    f"(momentum: {trend.momentum_score:.2f} < {min_momentum})"
                )
                return False

    # Hacker News quality threshold
    elif "hackernews" in source:
        min_momentum = 0.3 * threshold_multiplier  # Default: ~100+ points, tech_ai: ~20+ points
        if trend.momentum_score < min_momentum:
            logger.debug(
                f"HN trend '{trend.keyword[:50]}' below threshold "
                f"(momentum: {trend.momentum_score:.2f} < {min_momentum})"
            )
            return False

    # YouTube: spam filtering is primary quality gate (view count is noisy)
    # No momentum threshold for YouTube (already trending = high views)

    return True


def _meets_vertical_alignment(trend: TrendCandidate, vertical_id: str) -> bool:
    """
    Enforces minimum keyword relevance for vertical alignment.

    Filters out trends with 0 keyword matches (completely unrelated to vertical).
    Different thresholds for curated vs generic sources.

    Args:
        trend: TrendCandidate to evaluate
        vertical_id: Content vertical (e.g., 'fitness', 'finance')

    Returns:
        True if trend has sufficient keyword matches for its source type

    Thresholds by Source:
        - Curated sources (Reddit, YouTube channels): min 1 keyword required
        - Generic sources (YouTube trending): min 2 keywords required
          (higher threshold to filter sports/off-topic content)

    Example:
        >>> trend = TrendCandidate(keyword="Inter Milan wins", keyword_match_count=0, source="youtube_trending")
        >>> _meets_vertical_alignment(trend, "fitness")
        False  # 0 keywords < 2 required for youtube_trending
    """
    from yt_autopilot.core.config import get_vertical_config

    # Get keyword match count
    keyword_matches = getattr(trend, 'keyword_match_count', 0)

    # Determine minimum keywords required based on source
    source = trend.source.lower()

    # Curated sources (Reddit from vertical subreddits, YouTube from fitness channels): min 1 keyword
    if source.startswith("reddit_") or source.startswith("youtube_channel_"):
        min_keywords = 1
    # Generic sources (YouTube trending): min 1 keyword (lowered from 2 for SaaS/B2B content)
    elif source == "youtube_trending" or source == "youtube_search":
        min_keywords = 1
    # Other sources: min 1 keyword
    else:
        min_keywords = 1

    # Check alignment
    if keyword_matches < min_keywords:
        logger.debug(
            f"Trend '{trend.keyword[:50]}' filtered: {keyword_matches} keywords < {min_keywords} required "
            f"(source: {trend.source}, vertical: {vertical_id})"
        )
        return False

    return True


def _apply_quality_filters(trends: List[TrendCandidate], vertical_id: str = None) -> List[TrendCandidate]:
    """
    Applies spam filtering and quality thresholds to trend list.

    Phase A.1: Pre-filtering pipeline before LLM curation

    Args:
        trends: List of TrendCandidate objects from all sources

    Returns:
        Filtered list of high-quality TrendCandidate objects

    Filter Pipeline:
        1. Spam detection (removes obvious spam patterns)
        2. Quality thresholds (enforces minimum engagement)
        3. Deduplication (removes near-duplicate keywords)

    Expected Reduction:
        - Input: ~130-150 trends from all sources
        - Output: ~50-70 high-quality trends (~50% reduction)
    """
    logger.info(f"Applying quality filters to {len(trends)} trends...")

    # Step 1: Spam filtering (includes vertical-specific banned topics)
    pre_spam = len(trends)
    trends = [t for t in trends if not _is_spam_keyword(t, vertical_id=vertical_id)]
    spam_removed = pre_spam - len(trends)

    if spam_removed > 0:
        logger.info(f"✓ Removed {spam_removed} spam trends ({spam_removed/pre_spam*100:.1f}%)")

    # Step 2: Quality thresholds
    pre_quality = len(trends)
    trends = [t for t in trends if _meets_quality_threshold(t, vertical_id=vertical_id)]
    quality_removed = pre_quality - len(trends)

    if quality_removed > 0:
        logger.info(f"✓ Removed {quality_removed} low-quality trends ({quality_removed/pre_quality*100:.1f}%)")

    # Step 3: Deduplication (simple: exact keyword match)
    # More sophisticated dedup can use edit distance or embeddings
    seen_keywords = set()
    deduplicated = []
    for trend in trends:
        keyword_normalized = trend.keyword.lower().strip()
        if keyword_normalized not in seen_keywords:
            seen_keywords.add(keyword_normalized)
            deduplicated.append(trend)

    dup_removed = len(trends) - len(deduplicated)
    if dup_removed > 0:
        logger.info(f"✓ Removed {dup_removed} duplicate trends")

    # Step 4: Vertical alignment check (keyword relevance)
    if vertical_id:
        pre_alignment = len(deduplicated)
        deduplicated = [t for t in deduplicated if _meets_vertical_alignment(t, vertical_id)]
        alignment_removed = pre_alignment - len(deduplicated)

        if alignment_removed > 0:
            logger.info(f"✓ Removed {alignment_removed} non-aligned trends ({alignment_removed/pre_alignment*100:.1f}%)")

    logger.info(f"✓ Quality filtering complete: {len(trends)} → {len(deduplicated)} trends ({len(deduplicated)/len(trends)*100:.1f}% retained)")

    return deduplicated


def fetch_trends(vertical_id: str = "tech_ai", use_real_apis: bool = True) -> List[TrendCandidate]:
    """
    Fetches trending topics from external sources (real APIs or mock data).

    Step 08 Phase 2: Multi-source trend aggregation with Reddit, Hacker News, YouTube scraping fallback

    Args:
        vertical_id: Content vertical ('tech_ai', 'finance', 'gaming', 'education')
        use_real_apis: If True, try to use real APIs; if False or APIs unavailable, use mocks

    Returns:
        List of TrendCandidate objects with momentum scores

    Sources (Phase 2 complete):
        - YouTube Data API v3: Trending videos + search results (with scrapetube fallback)
        - Reddit API (PRAW): Hot + rising posts from vertical subreddits
        - Hacker News API: Top + best stories (tech/education only)
        - Mock fallback: If no APIs configured

    Example:
        >>> trends = fetch_trends(vertical_id="tech_ai")
        >>> print(f"Found {len(trends)} trending topics")
        Found 45 trending topics (YouTube + Reddit + HN)
    """
    logger.info(f"Fetching trending topics for vertical '{vertical_id}'...")

    all_trends = []

    if use_real_apis:
        # ========================================================================
        # Source 1: YouTube Data API v3 (Primary)
        # ========================================================================
        # SKIP YouTube trending for specific verticals:
        # - fitness: category "Sports" is too generic (includes soccer, tennis, etc.)
        # - tech_ai: category "Science & Technology" is too generic (includes smartphone reviews, gadgets, gaming)
        if vertical_id not in ["fitness", "tech_ai"]:
            logger.info("Source 1: YouTube Data API v3...")
            youtube_trends = _fetch_youtube_trending(
                vertical_id=vertical_id,
                region_code="IT",
                max_results=20
            )

            # If YouTube API returns nothing (quota exceeded), try scrapetube
            if not youtube_trends and SCRAPETUBE_AVAILABLE:
                logger.warning("YouTube API returned no results - trying scraping fallback")
                youtube_trends = _fetch_youtube_scrape(vertical_id=vertical_id, max_results=15)

            all_trends.extend(youtube_trends)
        else:
            logger.info(f"Source 1: YouTube Trending SKIPPED for {vertical_id} vertical (using curated sources: YouTube Channels + Reddit + HN only)")
            youtube_trends = []

        # Source 1b: YouTube Search for vertical-specific queries
        # SKIP for tech_ai: generic keyword searches return junk content (AI story videos, ChatGPT food videos)
        if vertical_id not in ["tech_ai"]:
            vertical_config = get_vertical_config(vertical_id)
            if vertical_config:
                target_keywords = vertical_config.get("target_keywords", [])
                # Search for top 2 keywords to avoid quota waste
                for keyword in target_keywords[:2]:
                    search_trends = _fetch_youtube_search(
                        query=keyword,
                        vertical_id=vertical_id,
                        region_code="IT",
                        max_results=5
                    )
                    all_trends.extend(search_trends)

        # ========================================================================
        # Source 2: Reddit API (PRAW) - Step 08 Phase 2
        # ========================================================================
        logger.info("Source 2: Reddit API (PRAW)...")
        try:
            from yt_autopilot.services.reddit_trend_source import fetch_reddit_trending, fetch_reddit_rising

            # Fetch hot posts
            reddit_hot = fetch_reddit_trending(vertical_id=vertical_id, limit_per_subreddit=10)
            all_trends.extend(reddit_hot)

            # Fetch rising posts (early signals)
            reddit_rising = fetch_reddit_rising(vertical_id=vertical_id, limit_per_subreddit=5)
            all_trends.extend(reddit_rising)

        except ImportError:
            logger.debug("Reddit trend source not available (import failed)")
        except Exception as e:
            logger.warning(f"Reddit trend fetching failed: {e}")

        # ========================================================================
        # Source 3: Hacker News API - Step 08 Phase 2
        # ========================================================================
        logger.info("Source 3: Hacker News API...")
        try:
            from yt_autopilot.services.hackernews_trend_source import fetch_hackernews_top

            hn_trends = fetch_hackernews_top(vertical_id=vertical_id, max_results=15)
            all_trends.extend(hn_trends)

        except ImportError:
            logger.debug("Hacker News trend source not available (import failed)")
        except Exception as e:
            logger.warning(f"Hacker News trend fetching failed: {e}")

        # ========================================================================
        # Source 4: YouTube Channels (Influencers/Competitors) - NEW
        # ========================================================================
        logger.info("Source 4: YouTube Channels (Influencers/Competitors)...")
        try:
            from yt_autopilot.services.youtube_channels_source import fetch_youtube_channels_trending

            channels_trends = fetch_youtube_channels_trending(
                vertical_id=vertical_id,
                limit_per_channel=5
            )
            all_trends.extend(channels_trends)

        except ImportError:
            logger.debug("YouTube channels source not available (import failed)")
        except Exception as e:
            logger.warning(f"YouTube channels trend fetching failed: {e}")

        # TODO Phase 3: Twitter/X, Google Trends (Glimpse API)

    # Fallback to mock data if no real APIs available or no trends found
    if not all_trends:
        logger.warning("No real API trends available - using mock data for testing")
        all_trends = _get_mock_trends_for_vertical(vertical_id)

    logger.info(f"✓ Fetched {len(all_trends)} total trend candidates from all sources")

    # Log source distribution (before filtering)
    source_counts = {}
    for trend in all_trends:
        source_counts[trend.source] = source_counts.get(trend.source, 0) + 1

    for source, count in source_counts.items():
        logger.info(f"  - {source}: {count} trends")

    # ========================================================================
    # Phase A.1: Apply quality filters (spam detection + thresholds + dedup + vertical alignment)
    # ========================================================================
    all_trends = _apply_quality_filters(all_trends, vertical_id=vertical_id)

    # Log top 5 trends (after filtering)
    logger.debug("Top 5 quality-filtered trends:")
    for i, trend in enumerate(all_trends[:5], 1):
        logger.debug(
            f"  [{i}] '{trend.keyword[:60]}' (momentum: {trend.momentum_score:.2f}, "
            f"source: {trend.source})"
        )

    return all_trends


def _get_mock_trends_for_vertical(vertical_id: str) -> List[TrendCandidate]:
    """
    Returns mock trend data tailored to the specified vertical.

    Step 08: Vertical-specific mock data for testing without API keys

    Args:
        vertical_id: Content vertical

    Returns:
        List of mock TrendCandidate objects
    """
    vertical_config = get_vertical_config(vertical_id)
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0) if vertical_config else 10.0

    mock_data = {
        "tech_ai": [
            TrendCandidate(
                keyword="ChatGPT automation tips for productivity 2025",
                why_hot="AI automation tools exploding in popularity, high CPM niche",
                region="IT",
                language="it",
                momentum_score=0.92,
                source="mock_youtube",
                cpm_estimate=cpm_baseline,
                competition_level="medium",
                virality_score=0.88
            ),
            TrendCandidate(
                keyword="Python tutorial for beginners - AI projects",
                why_hot="Evergreen content with high search volume, stable CPM",
                region="IT",
                language="it",
                momentum_score=0.85,
                source="mock_google_trends",
                cpm_estimate=cpm_baseline,
                competition_level="high",
                virality_score=0.75
            ),
            TrendCandidate(
                keyword="Claude AI vs ChatGPT comparison 2025",
                why_hot="New AI model launches driving comparison content interest",
                region="IT",
                language="it",
                momentum_score=0.88,
                source="mock_reddit",
                cpm_estimate=cpm_baseline,
                competition_level="low",
                virality_score=0.90
            ),
        ],
        "finance": [
            TrendCandidate(
                keyword="Passive income strategies 2025 - make money online",
                why_hot="Financial freedom content trending, ultra-high CPM",
                region="IT",
                language="it",
                momentum_score=0.95,
                source="mock_youtube",
                cpm_estimate=cpm_baseline,
                competition_level="high",
                virality_score=0.92
            ),
        ],
        "gaming": [
            TrendCandidate(
                keyword="Valorant pro tips and tricks - rank up fast",
                why_hot="Esports content trending, high volume compensates lower CPM",
                region="IT",
                language="it",
                momentum_score=0.90,
                source="mock_youtube",
                cpm_estimate=cpm_baseline,
                competition_level="high",
                virality_score=0.85
            ),
        ],
        "education": [
            TrendCandidate(
                keyword="Learn programming in 60 seconds - quick tutorial",
                why_hot="Educational shorts trending, strong CPM for education niche",
                region="IT",
                language="it",
                momentum_score=0.87,
                source="mock_youtube",
                cpm_estimate=cpm_baseline,
                competition_level="medium",
                virality_score=0.80
            ),
        ]
    }

    return mock_data.get(vertical_id, mock_data["tech_ai"])
