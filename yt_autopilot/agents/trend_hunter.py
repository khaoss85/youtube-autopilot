"""
TrendHunter Agent: Selects the best video topic from trending candidates.

This agent analyzes trending topics and chooses the most promising one
based on momentum, brand fit, and content freshness.

Step 08: Enhanced with multi-dimensional scoring (CPM, competition, virality).

==============================================================================
LLM Integration Strategy (Step 06-pre: Future Production)
==============================================================================

CURRENT STATE:
- This agent uses deterministic local logic (scoring, filtering)
- NO LLM calls are made directly from this agent
- Agent remains a PURE FUNCTION with no external dependencies

FUTURE PRODUCTION ENHANCEMENT:
- For production quality, this agent will benefit from LLM-powered analysis
- services/llm_router.generate_text() can enhance trend selection
- The LLM call will happen in the PIPELINE layer (build_video_package.py)
- NOT imported directly here (violates architecture: agents cannot import services)

INTEGRATION PLAN:
1. Pipeline calls llm_router.generate_text() with trend analysis task
2. LLM provides enhanced scoring, relevance analysis, or topic suggestions
3. Pipeline passes LLM output as enriched context to this agent
4. Agent uses both deterministic logic AND LLM insights for selection

Example (in pipeline/build_video_package.py):
    # Before calling trend_hunter agent
    llm_analysis = generate_text(
        role="trend_hunter",
        task="Analyze which trending topic best fits our brand",
        context=str(trends),
        style_hints={"brand_tone": memory["brand_tone"]}
    )
    # Pass llm_analysis as additional parameter to agent
    # Agent combines deterministic scoring + LLM insights

ARCHITECTURE RULE:
- Agents do NOT import from services/
- Pipeline layer orchestrates LLM calls
- Keeps agents testable, predictable, and layering-compliant

==============================================================================
"""

from typing import List, Dict, Optional
from yt_autopilot.core.schemas import TrendCandidate, VideoPlan
from yt_autopilot.core.memory_store import get_banned_topics, get_recent_titles, get_brand_tone
from yt_autopilot.core.logger import logger


def _is_topic_banned(trend: TrendCandidate, banned_topics: List[str]) -> bool:
    """
    Checks if trend keyword contains any banned topics.

    Args:
        trend: Trend candidate to check
        banned_topics: List of banned topic strings

    Returns:
        True if trend contains banned content
    """
    keyword_lower = trend.keyword.lower()
    why_hot_lower = trend.why_hot.lower()

    for banned in banned_topics:
        banned_lower = banned.lower()
        if banned_lower in keyword_lower or banned_lower in why_hot_lower:
            return True

    return False


def _is_too_similar_to_recent(trend: TrendCandidate, recent_titles: List[str]) -> bool:
    """
    Checks if trend is too similar to recently published content.

    Args:
        trend: Trend candidate to check
        recent_titles: List of recent video titles

    Returns:
        True if trend is too similar to recent content
    """
    if not recent_titles:
        return False

    keyword_words = set(trend.keyword.lower().split())

    # Check overlap with recent titles
    for recent_title in recent_titles:
        title_words = set(recent_title.lower().split())
        # If more than 50% words overlap, consider it too similar
        overlap = len(keyword_words & title_words)
        if overlap > 0 and overlap / len(keyword_words) > 0.5:
            logger.debug(f"Trend '{trend.keyword}' too similar to recent title '{recent_title}'")
            return True

    return False


def _calculate_priority_score(trend: TrendCandidate, memory: Dict) -> float:
    """
    Calculates a priority score for ranking trends.

    Step 08: Enhanced with CPM potential, competition level, and virality scoring

    Args:
        trend: Trend candidate to score
        memory: Channel memory dict

    Returns:
        Priority score (higher is better, 0-1+ scale)
    """
    # Base momentum score (0-1)
    score = trend.momentum_score

    # Step 08: CPM bonus (normalize cpm_estimate to 0-0.3 range)
    # CPM of 15+ adds 0.3, CPM of 5 adds 0.1
    cpm_bonus = min(0.3, trend.cpm_estimate / 50.0)
    score += cpm_bonus

    # Step 08: Competition penalty/bonus
    competition_map = {
        "low": 0.2,      # Big bonus for low competition
        "medium": 0.0,   # Neutral
        "high": -0.1     # Penalty for high competition
    }
    score += competition_map.get(trend.competition_level, 0.0)

    # Step 08: Virality bonus (0-0.2 range)
    virality_bonus = trend.virality_score * 0.2
    score += virality_bonus

    # Bonus for certain regions (if targeting specific markets)
    if trend.region.upper() in ["IT", "US", "GLOBAL"]:
        score += 0.1

    # Step 08: Source reliability bonus
    source_reliability = {
        "youtube_trending": 0.15,    # High reliability
        "youtube_search": 0.10,      # Good reliability
        "reddit": 0.12,              # Community-validated
        "google_trends": 0.08,       # Search data
        "hackernews": 0.10,          # Tech-savvy audience
        "mock_youtube": 0.0,         # No bonus for mocks
        "mock_google_trends": 0.0,
        "mock_reddit_trends": 0.0,
        "mock_twitter_trends": 0.0,
    }
    score += source_reliability.get(trend.source, 0.0)

    logger.debug(
        f"Trend '{trend.keyword[:40]}' priority score: {score:.3f} "
        f"(momentum:{trend.momentum_score:.2f}, cpm:{trend.cpm_estimate:.1f}, "
        f"comp:{trend.competition_level}, viral:{trend.virality_score:.2f})"
    )

    return score


def generate_video_plan(trends: List[TrendCandidate], memory: Dict) -> VideoPlan:
    """
    Selects the best trending topic and generates a strategic video plan.

    This is the entry point for the TrendHunter agent. It analyzes multiple
    trending topics and picks the most promising one based on:
    - Momentum score
    - Brand safety (no banned topics)
    - Content freshness (not too similar to recent videos)
    - Strategic fit with channel goals

    Args:
        trends: List of trend candidates to evaluate
        memory: Channel memory dict containing brand_tone, banned_topics, recent_titles

    Returns:
        VideoPlan for the selected trend

    Raises:
        ValueError: If no suitable trends found after filtering
    """
    if not trends:
        raise ValueError("Cannot generate video plan: no trends provided")

    logger.info(f"TrendHunter analyzing {len(trends)} trend candidates")

    # Load memory constraints
    banned_topics = get_banned_topics(memory)
    recent_titles = get_recent_titles(memory)
    brand_tone = get_brand_tone(memory)

    # Filter out banned and similar topics
    suitable_trends = []
    for trend in trends:
        if _is_topic_banned(trend, banned_topics):
            logger.debug(f"Filtered out trend '{trend.keyword}': contains banned topic")
            continue

        if _is_too_similar_to_recent(trend, recent_titles):
            logger.debug(f"Filtered out trend '{trend.keyword}': too similar to recent content")
            continue

        suitable_trends.append(trend)

    if not suitable_trends:
        raise ValueError(
            "No suitable trends found after filtering. "
            "All candidates either contained banned topics or were too similar to recent content."
        )

    # Rank by priority score
    ranked_trends = sorted(
        suitable_trends,
        key=lambda t: _calculate_priority_score(t, memory),
        reverse=True
    )

    # Select the best trend
    best_trend = ranked_trends[0]
    logger.info(
        f"TrendHunter selected: '{best_trend.keyword}' "
        f"(momentum: {best_trend.momentum_score:.2f}, source: {best_trend.source}, "
        f"cpm: ${best_trend.cpm_estimate:.1f}, comp: {best_trend.competition_level}, "
        f"virality: {best_trend.virality_score:.2f})"
    )

    # Generate compliance notes
    compliance_notes = [
        "No medical cure claims",
        "No hate speech or targeted harassment",
        "No aggressive political content",
        "No copyrighted music references",
        "Maintain positive and direct brand tone"
    ]

    # Create VideoPlan
    video_plan = VideoPlan(
        working_title=best_trend.keyword,
        strategic_angle=best_trend.why_hot,
        target_audience=_infer_target_audience(best_trend),
        language=best_trend.language,
        compliance_notes=compliance_notes
    )

    logger.info(f"Generated VideoPlan: '{video_plan.working_title}'")
    return video_plan


def _infer_target_audience(trend: TrendCandidate) -> str:
    """
    Infers target audience based on trend characteristics.

    Args:
        trend: Trend candidate

    Returns:
        Target audience description
    """
    # Simple heuristic - could be more sophisticated
    if trend.region.upper() == "IT":
        base_audience = "Pubblico italiano"
    else:
        base_audience = "Global audience"

    # Add demographic hints based on keyword patterns
    keyword_lower = trend.keyword.lower()

    if any(word in keyword_lower for word in ["tech", "ai", "software", "coding"]):
        return f"{base_audience} interessato a tecnologia e innovazione"
    elif any(word in keyword_lower for word in ["fitness", "workout", "health"]):
        return f"{base_audience} interessato a salute e fitness"
    elif any(word in keyword_lower for word in ["recipe", "food", "cooking"]):
        return f"{base_audience} appassionati di cucina"
    elif any(word in keyword_lower for word in ["money", "finance", "invest"]):
        return f"{base_audience} interessato a finanza personale"
    else:
        return f"{base_audience} generale"
