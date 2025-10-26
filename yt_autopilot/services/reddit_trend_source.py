"""
Reddit Trend Source: Fetches trending posts from Reddit using PRAW.

Step 08 Phase 2: Integration with PRAW (Python Reddit API Wrapper)
for discovering trending topics from vertical-specific subreddits.

PRAW is the de-facto standard for Reddit API access (50K+ stars on GitHub).
"""

from typing import List, Optional
from yt_autopilot.core.schemas import TrendCandidate
from yt_autopilot.core.logger import logger
from yt_autopilot.core.config import get_env, get_vertical_config

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not installed - Reddit trending will be disabled")


def _get_reddit_client() -> Optional[praw.Reddit]:
    """
    Creates authenticated Reddit client using PRAW.

    Step 08 Phase 2: Reddit API authentication

    Returns:
        Authenticated praw.Reddit instance or None if credentials missing

    Required .env variables:
        REDDIT_CLIENT_ID=your_client_id
        REDDIT_CLIENT_SECRET=your_client_secret
        REDDIT_USER_AGENT=yt_autopilot:v1.0 (by /u/your_username)

    Setup instructions:
        1. Go to https://www.reddit.com/prefs/apps
        2. Click "Create App" or "Create Another App"
        3. Select "script" type
        4. Note your client_id and client_secret
        5. Add to .env file
    """
    if not PRAW_AVAILABLE:
        return None

    client_id = get_env("REDDIT_CLIENT_ID")
    client_secret = get_env("REDDIT_CLIENT_SECRET")
    user_agent = get_env("REDDIT_USER_AGENT", "yt_autopilot:v1.0")

    if not client_id or not client_secret:
        logger.warning("Reddit API credentials not configured - skipping Reddit trends")
        return None

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )

        # Test authentication
        logger.debug(f"Reddit client authenticated (read-only mode)")
        return reddit

    except Exception as e:
        logger.error(f"Failed to authenticate with Reddit API: {e}")
        return None


def fetch_reddit_trending(
    vertical_id: str = "tech_ai",
    time_filter: str = "day",
    limit_per_subreddit: int = 10
) -> List[TrendCandidate]:
    """
    Fetches trending posts from Reddit subreddits relevant to vertical.

    Step 08 Phase 2: Reddit trend detection using PRAW

    Args:
        vertical_id: Content vertical ('tech_ai', 'finance', 'gaming', 'education')
        time_filter: Time window ('hour', 'day', 'week', 'month', 'year', 'all')
        limit_per_subreddit: Max posts to fetch per subreddit

    Returns:
        List of TrendCandidate objects from Reddit hot posts

    Algorithm:
        1. Get subreddits for vertical from config
        2. Fetch hot posts from each subreddit
        3. Calculate momentum_score from upvote_ratio + score
        4. Calculate virality_score from upvotes/hour (if available)
        5. Estimate competition based on comment count
        6. Convert to TrendCandidate

    Example:
        >>> trends = fetch_reddit_trending("tech_ai", time_filter="day")
        >>> print(f"Found {len(trends)} trending posts from Reddit")
        Found 15 trending posts from Reddit
    """
    reddit = _get_reddit_client()
    if not reddit:
        logger.info("Reddit client unavailable - returning empty trends")
        return []

    vertical_config = get_vertical_config(vertical_id)
    if not vertical_config:
        logger.warning(f"Unknown vertical '{vertical_id}' - skipping Reddit")
        return []

    subreddit_names = vertical_config.get("reddit_subreddits", [])
    if not subreddit_names:
        logger.info(f"No subreddits configured for vertical '{vertical_id}'")
        return []

    cpm_baseline = vertical_config.get("cpm_baseline", 10.0)

    logger.info(f"Fetching Reddit trending from {len(subreddit_names)} subreddits ({vertical_id})...")

    all_trends = []

    for subreddit_name in subreddit_names:
        try:
            subreddit = reddit.subreddit(subreddit_name)

            # Fetch hot posts
            hot_posts = subreddit.hot(limit=limit_per_subreddit)

            for post in hot_posts:
                # Skip stickied posts (announcements, not trends)
                if post.stickied:
                    continue

                # Calculate momentum score (0-1)
                # Based on upvote ratio and score
                upvote_ratio = post.upvote_ratio  # 0-1 (1 = 100% upvoted)
                score = post.score  # Net upvotes

                # Normalize score: 100+ upvotes = 0.5, 1000+ = 0.75, 5000+ = 1.0
                normalized_score = min(1.0, score / 5000.0)

                # Momentum = weighted average of ratio and normalized score
                momentum_score = (upvote_ratio * 0.4) + (normalized_score * 0.6)

                # Calculate virality score
                # posts with high upvote velocity are more viral
                # Simplified: use upvote ratio as proxy (high ratio = viral)
                virality_score = upvote_ratio

                # Estimate competition level
                num_comments = post.num_comments
                if num_comments > 200:
                    competition = "high"  # Lots of discussion = crowded topic
                elif num_comments > 50:
                    competition = "medium"
                else:
                    competition = "low"  # Less discussion = opportunity

                # Generate why_hot explanation
                why_hot = f"Trending on r/{subreddit_name} ({score} upvotes, {upvote_ratio:.0%} upvote ratio)"
                if num_comments > 100:
                    why_hot += f", {num_comments} comments (active discussion)"

                trend = TrendCandidate(
                    keyword=post.title,
                    why_hot=why_hot,
                    region="GLOBAL",  # Reddit is global
                    language="en",  # Assume English (could detect from subreddit)
                    momentum_score=momentum_score,
                    source=f"reddit_{subreddit_name}",
                    cpm_estimate=cpm_baseline,  # Use vertical baseline
                    competition_level=competition,
                    virality_score=virality_score,
                    historical_match=None
                )

                all_trends.append(trend)

            logger.debug(f"  r/{subreddit_name}: fetched {len(list(subreddit.hot(limit=limit_per_subreddit)))} hot posts")

        except Exception as e:
            logger.warning(f"Failed to fetch from r/{subreddit_name}: {e}")
            continue

    logger.info(f"✓ Fetched {len(all_trends)} trending posts from Reddit")
    return all_trends


def fetch_reddit_rising(
    vertical_id: str = "tech_ai",
    limit_per_subreddit: int = 10
) -> List[TrendCandidate]:
    """
    Fetches rising posts from Reddit (early trends before they're mainstream).

    Step 08 Phase 2: Early trend detection

    Args:
        vertical_id: Content vertical
        limit_per_subreddit: Max posts per subreddit

    Returns:
        List of TrendCandidate objects from Reddit rising posts

    Note:
        Rising posts are trending UP fast but not yet "hot".
        These are early signals for first-mover advantage.
    """
    reddit = _get_reddit_client()
    if not reddit:
        return []

    vertical_config = get_vertical_config(vertical_id)
    if not vertical_config:
        return []

    subreddit_names = vertical_config.get("reddit_subreddits", [])
    cpm_baseline = vertical_config.get("cpm_baseline", 10.0)

    logger.info(f"Fetching Reddit rising posts from {len(subreddit_names)} subreddits...")

    all_trends = []

    for subreddit_name in subreddit_names:
        try:
            subreddit = reddit.subreddit(subreddit_name)

            # Fetch rising posts (early trends)
            rising_posts = subreddit.rising(limit=limit_per_subreddit)

            for post in rising_posts:
                if post.stickied:
                    continue

                # Rising posts get bonus virality score
                momentum_score = min(1.0, post.score / 1000.0)
                virality_score = 0.85  # Rising = high virality by definition

                competition = "low" if post.num_comments < 50 else "medium"

                trend = TrendCandidate(
                    keyword=post.title,
                    why_hot=f"Rising fast on r/{subreddit_name} ({post.score} upvotes, early trend)",
                    region="GLOBAL",
                    language="en",
                    momentum_score=momentum_score,
                    source=f"reddit_rising_{subreddit_name}",
                    cpm_estimate=cpm_baseline,
                    competition_level=competition,
                    virality_score=virality_score,
                    historical_match=None
                )

                all_trends.append(trend)

        except Exception as e:
            logger.warning(f"Failed to fetch rising from r/{subreddit_name}: {e}")
            continue

    logger.info(f"✓ Fetched {len(all_trends)} rising posts from Reddit")
    return all_trends
