"""
Trend Scorer Service: Multi-dimensional scoring for trend prioritization.

Step 08: Intelligent trend ranking based on revenue potential, brand fit,
competition level, and historical performance.

This service analyzes TrendCandidate objects and assigns a composite score
that helps prioritize which trends are most likely to generate revenue for
the channel while maintaining brand consistency.
"""

from typing import List, Dict, Optional
from yt_autopilot.core.schemas import TrendCandidate
from yt_autopilot.core.logger import logger


def calculate_trend_score(
    trend: TrendCandidate,
    vertical_config: Dict,
    memory: Dict,
    historical_data: Optional[List[Dict]] = None
) -> float:
    """
    Calculates composite score for a trend candidate (0-100 scale).

    Formula:
        SCORE = (momentum * 0.30) + (cpm * 0.25) + (brand_fit * 0.20) +
                (competition * 0.15) + (historical * 0.10)

    Args:
        trend: TrendCandidate to score
        vertical_config: Vertical-specific configuration from config.py
        memory: Channel memory with brand_tone, recent_titles, etc.
        historical_data: Optional list of past video performance data

    Returns:
        Composite score from 0-100 (higher is better)

    Example:
        >>> score = calculate_trend_score(trend, vertical_config, memory)
        >>> print(f"Trend score: {score:.1f}/100")
        Trend score: 78.5/100
    """
    # Component 1: Momentum Score (0-100, weight 30%)
    momentum_component = trend.momentum_score * 100 * 0.30

    # Component 2: CPM Potential (0-100, weight 25%)
    cpm_component = _score_cpm_potential(trend, vertical_config) * 0.25

    # Component 3: Brand Fit (0-100, weight 20%)
    brand_fit_component = _score_brand_fit(trend, vertical_config, memory) * 0.20

    # Component 4: Competition Level (0-100, weight 15%)
    # Lower competition = higher score
    competition_component = _score_competition(trend) * 0.15

    # Component 5: Historical Performance (0-100, weight 10%)
    historical_component = _score_historical_match(trend, historical_data) * 0.10

    # Total composite score
    total_score = (
        momentum_component +
        cpm_component +
        brand_fit_component +
        competition_component +
        historical_component
    )

    logger.debug(
        f"Trend '{trend.keyword[:40]}' scored {total_score:.1f}/100 "
        f"(momentum:{momentum_component:.1f}, cpm:{cpm_component:.1f}, "
        f"brand:{brand_fit_component:.1f}, comp:{competition_component:.1f}, "
        f"hist:{historical_component:.1f})"
    )

    return total_score


def _score_cpm_potential(trend: TrendCandidate, vertical_config: Dict) -> float:
    """
    Scores CPM potential relative to vertical baseline (0-100 scale).

    Args:
        trend: TrendCandidate with cpm_estimate
        vertical_config: Contains cpm_baseline for vertical

    Returns:
        Score 0-100 (100 = 2x baseline or higher, 50 = at baseline)
    """
    baseline_cpm = vertical_config.get("cpm_baseline", 10.0)
    trend_cpm = trend.cpm_estimate

    if baseline_cpm == 0:
        return 50.0  # Neutral score if no baseline

    # Ratio: 2x baseline = 100 score, 1x baseline = 50 score, 0.5x = 25 score
    ratio = trend_cpm / baseline_cpm
    score = min(100.0, ratio * 50.0)  # Cap at 100

    return score


def _score_brand_fit(
    trend: TrendCandidate,
    vertical_config: Dict,
    memory: Dict
) -> float:
    """
    Scores how well trend aligns with channel brand and vertical (0-100 scale).

    Checks:
    - Keyword overlap with target_keywords
    - Not in banned_topics
    - Language match
    - Region relevance

    Args:
        trend: TrendCandidate to evaluate
        vertical_config: Contains target_keywords
        memory: Contains banned_topics, brand preferences

    Returns:
        Score 0-100 (higher = better brand fit)
    """
    score = 50.0  # Start neutral

    # Check keyword overlap
    target_keywords = vertical_config.get("target_keywords", [])
    trend_words = set(trend.keyword.lower().split())
    target_words = set(kw.lower() for kw in target_keywords)

    overlap = len(trend_words & target_words)
    if overlap > 0:
        # Each overlapping keyword adds 10 points, up to 40 points
        score += min(40.0, overlap * 10.0)

    # Penalty for banned topics
    banned_topics = memory.get("banned_topics", [])
    for banned in banned_topics:
        if banned.lower() in trend.keyword.lower():
            score -= 30.0  # Heavy penalty
            break

    # Bonus for language match
    if trend.language == "it":  # Match channel default
        score += 5.0

    # Bonus for region relevance
    if trend.region.upper() in ["IT", "GLOBAL"]:
        score += 5.0

    # Clamp to 0-100
    return max(0.0, min(100.0, score))


def _score_competition(trend: TrendCandidate) -> float:
    """
    Scores competition level (0-100 scale, higher = less competition).

    Args:
        trend: TrendCandidate with competition_level field

    Returns:
        Score 0-100 (100 = low competition, 50 = medium, 20 = high)
    """
    competition_map = {
        "low": 100.0,     # Great opportunity
        "medium": 50.0,   # Moderate
        "high": 20.0      # Saturated
    }

    return competition_map.get(trend.competition_level, 50.0)


def _score_historical_match(
    trend: TrendCandidate,
    historical_data: Optional[List[Dict]]
) -> float:
    """
    Scores based on performance of similar past videos (0-100 scale).

    Args:
        trend: TrendCandidate with optional historical_match ID
        historical_data: List of past video performance dicts

    Returns:
        Score 0-100 (100 = similar video performed excellently)
    """
    if not historical_data or not trend.historical_match:
        return 50.0  # Neutral if no historical data

    # Find matching historical video
    for video in historical_data:
        if video.get("video_internal_id") == trend.historical_match:
            # Score based on actual CPM performance
            actual_cpm = video.get("cpm_actual", 0.0)
            if actual_cpm > 20.0:
                return 100.0  # Excellent
            elif actual_cpm > 10.0:
                return 75.0   # Good
            elif actual_cpm > 5.0:
                return 50.0   # Average
            else:
                return 25.0   # Below average

    return 50.0  # Neutral if no match found


def rank_trends(
    trends: List[TrendCandidate],
    vertical_config: Dict,
    memory: Dict,
    historical_data: Optional[List[Dict]] = None,
    top_n: int = 10
) -> List[tuple]:
    """
    Ranks trends by composite score and returns top N.

    Args:
        trends: List of TrendCandidate objects to rank
        vertical_config: Vertical-specific configuration
        memory: Channel memory
        historical_data: Optional historical performance data
        top_n: Number of top trends to return

    Returns:
        List of (trend, score) tuples sorted by score descending

    Example:
        >>> ranked = rank_trends(trends, vertical_config, memory, top_n=5)
        >>> for trend, score in ranked:
        ...     print(f"{score:.1f}/100 - {trend.keyword}")
        85.2/100 - ChatGPT automation tips
        78.5/100 - Python AI tutorial
        ...
    """
    logger.info(f"Ranking {len(trends)} trends with multi-dimensional scoring...")

    scored_trends = []
    for trend in trends:
        score = calculate_trend_score(trend, vertical_config, memory, historical_data)
        scored_trends.append((trend, score))

    # Sort by score descending
    ranked = sorted(scored_trends, key=lambda x: x[1], reverse=True)

    # Return top N
    top_trends = ranked[:top_n]

    logger.info(f"✓ Top {len(top_trends)} trends ranked")
    for i, (trend, score) in enumerate(top_trends, 1):
        logger.info(f"  #{i}: {score:.1f}/100 - '{trend.keyword}' (source: {trend.source})")

    return top_trends
