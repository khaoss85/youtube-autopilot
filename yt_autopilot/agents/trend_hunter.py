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

from typing import List, Dict, Optional, Callable
import re
import json
from yt_autopilot.core.schemas import TrendCandidate, VideoPlan
from yt_autopilot.core.memory_store import get_banned_topics, get_recent_titles, get_brand_tone
from yt_autopilot.core.logger import logger, log_fallback
from yt_autopilot.io.datastore import is_topic_already_produced


def _detect_language(text: str) -> str:
    """
    Detects language of text using simple heuristics.

    Step 08 Phase A.3: Language detection for workspace preference matching

    Args:
        text: Text to analyze (typically trend title)

    Returns:
        "it" for Italian, "en" for English (default)

    Algorithm:
        - Check for Italian-specific characters (à, è, ì, ò, ù)
        - Check for common Italian words (che, per, con, del, alla, della, delle, degli)
        - Default to English if no Italian markers found

    Example:
        >>> _detect_language("ALLENO LE BRACCIA CON UN 212")
        "it"
        >>> _detect_language("5 Stretches Your Body Needs EVERY Morning")
        "en"
    """
    text_lower = text.lower()

    # Italian-specific characters
    italian_chars = ['à', 'è', 'ì', 'ò', 'ù']
    if any(char in text_lower for char in italian_chars):
        return "it"

    # Common Italian words (case-insensitive word boundaries)
    italian_words = [
        r'\bche\b', r'\bper\b', r'\bcon\b', r'\bdel\b', r'\bdella\b',
        r'\bdelle\b', r'\bdegli\b', r'\balla\b', r'\bdal\b', r'\bdai\b',
        r'\bnel\b', r'\bnella\b', r'\bsul\b', r'\bsulla\b', r'\bquesto\b',
        r'\bquesto\b', r'\bquesta\b', r'\bcome\b', r'\bpiù\b', r'\banche\b'
    ]

    for pattern in italian_words:
        if re.search(pattern, text_lower):
            return "it"

    # Default to English
    return "en"


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
    Phase A.2: Source quality weighting (Reddit 4x > Channels 3x > HN 2x > YouTube 1x)

    Scoring Components:
        - Base momentum (0-1.0)
        - CPM bonus (0-0.3): Higher CPM categories get bonus
        - Competition adjustment (+0.2 low, -0.1 high)
        - Virality bonus (0-0.2): Fast-growing trends
        - Region bonus (+0.1 for IT/US/GLOBAL)
        - Source quality weight: Reddit 0.40, YouTube Channels 0.30, HN 0.20, YouTube Search 0.10

    Args:
        trend: Trend candidate to score
        memory: Channel memory dict

    Returns:
        Priority score (higher is better, typical range 0.5-2.0)
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

    # Step 08 Phase A.3: Language preference boost
    # Bonus for content matching workspace target language
    workspace_language = memory.get("target_language", "en")  # Default English
    detected_language = _detect_language(trend.keyword)

    if detected_language == workspace_language:
        score += 0.15
        logger.debug(f"Language bonus: +0.15 ({detected_language} matches workspace preference)")

    # Step 08.1: Keyword density bonus (more keyword matches = higher relevance)
    # Differentiates trends with same base scores
    keyword_bonus = 0.0
    if hasattr(trend, 'keyword_match_count') and trend.keyword_match_count > 0:
        # Each keyword match adds 0.03 (max 0.15 for 5+ keywords)
        keyword_bonus = min(0.15, trend.keyword_match_count * 0.03)
        logger.debug(f"Keyword density bonus: +{keyword_bonus:.3f} ({trend.keyword_match_count} matches)")

    score += keyword_bonus

    # Phase A.2: Source quality weighting (Reddit 4x > Channels 3x > HN 2x > YouTube 1x)
    # Prioritizes curated communities and influencer content over generic search results
    # Step 08.1: Adjusted weights to boost curated sources
    source_quality = {
        # Reddit: 4x weight (highest quality, community-curated)
        "reddit_hot": 0.45,                # Hot posts = proven engagement (boosted)
        "reddit_rising": 0.50,             # Rising = early viral signals (boosted)
        "reddit": 0.45,                    # Generic reddit fallback (boosted)

        # YouTube Channels: 3x weight (influencer/competitor curated content)
        "youtube_channel": 0.35,           # Curated influencers/competitors (boosted)

        # Hacker News: 2x weight (tech-savvy, high-quality discussions)
        "hackernews_top": 0.20,            # Top stories
        "hackernews_best": 0.22,           # Best = editorial selection (bonus!)
        "hackernews": 0.20,                # Generic HN fallback

        # YouTube Generic: 1x weight (baseline, noisy but high reach)
        "youtube_trending": 0.05,          # Trending = viral but mixed quality (reduced)
        "youtube_search": 0.10,            # Search results = keyword match
        "youtube_scrape": 0.05,            # Scraping = fallback, least reliable

        # Other sources (legacy)
        "google_trends": 0.08,             # Search data
        "mock_youtube": 0.0,               # No bonus for mocks
        "mock_google_trends": 0.0,
        "mock_reddit_trends": 0.0,
        "mock_twitter_trends": 0.0,
    }
    # Match source (handle dynamic channel names like "youtube_channel_athlean-x")
    source_bonus = 0.0
    if trend.source in source_quality:
        source_bonus = source_quality[trend.source]
    elif trend.source.startswith("youtube_channel_"):
        # Any YouTube channel gets the curated influencer bonus
        source_bonus = 0.30
    elif trend.source.startswith("reddit_"):
        # Any Reddit source gets community-curated bonus
        source_bonus = 0.40
    elif trend.source.startswith("hackernews_"):
        # Any Hacker News source gets tech community bonus
        source_bonus = 0.20

    score += source_bonus

    logger.debug(
        f"Trend '{trend.keyword[:40]}' priority score: {score:.3f} "
        f"(momentum:{trend.momentum_score:.2f}, cpm:{trend.cpm_estimate:.1f}, "
        f"comp:{trend.competition_level}, viral:{trend.virality_score:.2f})"
    )

    return score


def _infer_target_audience_with_llm(
    trend: TrendCandidate,
    workspace: Dict,
    llm_generate_fn: Callable
) -> str:
    """
    AI-driven audience inference using LLM reasoning (Pattern 1).

    Replaces keyword heuristics with contextual understanding.
    Scalable to ANY vertical, ANY language, ANY topic complexity.

    Args:
        trend: Trend candidate
        workspace: Workspace configuration dict
        llm_generate_fn: LLM function for AI reasoning

    Returns:
        Target audience description (1-2 sentences)

    Raises:
        None - Falls back to deterministic inference on LLM failure

    Example:
        >>> audience = _infer_target_audience_with_llm(
        ...     trend=TrendCandidate(keyword="HIIT abs workout", ...),
        ...     workspace={"vertical_id": "fitness", "brand_tone": "Motivational..."},
        ...     llm_generate_fn=generate_text
        ... )
        >>> # Returns: "Pubblico italiano interessato a fitness e allenamento"
    """
    vertical_id = workspace.get('vertical_id', 'general')
    vertical_description = workspace.get('vertical_description', '')
    brand_tone = workspace.get('brand_tone', '')
    target_language = workspace.get('target_language', 'en')

    # Build LLM prompt for audience inference
    prompt = f"""You are an audience targeting specialist analyzing content for a YouTube channel.

CHANNEL CONTEXT:
- Vertical: {vertical_id}
- Description: {vertical_description[:150] if vertical_description else 'General content'}
- Brand Tone: {brand_tone[:200] if brand_tone else 'Professional and engaging'}
- Target Language: {target_language}

TREND ANALYSIS:
- Topic: "{trend.keyword}"
- Why Hot: "{trend.why_hot[:200] if trend.why_hot else 'Trending topic'}"
- Source: {trend.source}
- Momentum: {trend.momentum_score:.2f}/1.0

TASK: Infer the PRIMARY target audience for this content.

Consider:
1. **Topic Intent**: What is the viewer searching for when they find this video?
2. **Vertical Alignment**: Does this align with {vertical_id} vertical's core audience?
3. **Demographics**: Age, interests, psychographics (not just keywords!)
4. **Language/Region**: Audience should match content language and cultural context

RESPOND WITH ONLY THE AUDIENCE DESCRIPTION (1-2 sentences, in {target_language}):
- Format: "[Region/Language] audience interested in [specific interest/problem]"
- Examples:
  * "Pubblico italiano interessato a fitness e allenamento per principianti"
  * "English-speaking tech enthusiasts seeking AI productivity tools"
  * "Pubblico italiano appassionato di finanza personale e investimenti"

OUTPUT (no explanations, only audience description):"""

    try:
        logger.debug(f"  🎯 AI inferring audience for: '{trend.keyword[:50]}...'")

        audience = llm_generate_fn(
            role="audience_inference",
            task=prompt,
            context="",
            style_hints={"temperature": 0.3, "max_tokens": 100}
        ).strip()

        # Validation: Ensure output is not empty and reasonable length
        if not audience or len(audience) < 10 or len(audience) > 250:
            raise ValueError(f"Invalid LLM audience output (length {len(audience)}): {audience[:100]}")

        # Clean potential quotes or extra formatting
        audience = audience.strip('"').strip("'").strip()

        logger.info(f"  ✓ AI inferred audience: {audience[:80]}{'...' if len(audience) > 80 else ''}")
        return audience

    except Exception as e:
        logger.warning(f"  ⚠️ AI audience inference failed: {e}")
        log_fallback(
            component="TREND_HUNTER_AUDIENCE",
            fallback_type="DETERMINISTIC_HEURISTIC",
            reason=f"LLM call failed: {e}",
            impact="MEDIUM"
        )

        # Fallback to deterministic heuristic (existing function)
        logger.info("  → Falling back to deterministic audience inference")
        return _infer_target_audience(trend, workspace)


def _infer_target_audience(trend: TrendCandidate, workspace: Optional[Dict] = None) -> str:
    """
    Deterministic audience inference using keyword heuristics (fallback).

    This is the FALLBACK function when LLM inference fails.
    Pattern 1 enhancement: Now accepts workspace for vertical-based fallback.

    Args:
        trend: Trend candidate
        workspace: Optional workspace config for vertical-based inference

    Returns:
        Target audience description
    """
    # Base audience from region
    if trend.region.upper() == "IT":
        base_audience = "Pubblico italiano"
    else:
        base_audience = "Global audience"

    # Pattern 1 Enhancement: Prioritize workspace vertical if available
    if workspace:
        vertical_id = workspace.get('vertical_id', '').lower()

        # Vertical-to-audience mapping (deterministic fallback)
        vertical_audiences = {
            'fitness': f"{base_audience} interessato a fitness e benessere",
            'tech': f"{base_audience} interessato a tecnologia e innovazione",
            'finance': f"{base_audience} interessato a finanza personale",
            'cooking': f"{base_audience} appassionati di cucina",
            'education': f"{base_audience} interessato a apprendimento e cultura",
            'gaming': f"{base_audience} appassionati di gaming e esports",
            'business': f"{base_audience} interessato a business e imprenditoria",
        }

        if vertical_id in vertical_audiences:
            logger.debug(f"  Fallback: Using vertical-based audience for '{vertical_id}'")
            return vertical_audiences[vertical_id]

    # Original keyword-based heuristic (last resort fallback)
    keyword_lower = trend.keyword.lower()

    if any(word in keyword_lower for word in ["tech", "ai", "software", "coding"]):
        return f"{base_audience} interessato a tecnologia e innovazione"
    elif any(word in keyword_lower for word in ["fitness", "workout", "health", "allenamento"]):
        return f"{base_audience} interessato a salute e fitness"
    elif any(word in keyword_lower for word in ["recipe", "food", "cooking", "ricetta", "cucina"]):
        return f"{base_audience} appassionati di cucina"
    elif any(word in keyword_lower for word in ["money", "finance", "invest"]):
        return f"{base_audience} interessato a finanza personale"
    else:
        return f"{base_audience} generale"


def generate_video_plan(
    trends: List[TrendCandidate],
    memory: Dict,
    return_top_candidates: int = 0,
    llm_generate_fn: Optional[Callable] = None
):
    """
    Selects the best trending topic and generates a strategic video plan.

    This is the entry point for the TrendHunter agent. It analyzes multiple
    trending topics and picks the most promising one based on:
    - Momentum score
    - Brand safety (no banned topics)
    - Content freshness (not too similar to recent videos)
    - Strategic fit with channel goals

    Step 08 Phase A.3: Added support for returning top N candidates for AI-assisted selection
    Pattern 1: Enhanced with AI-driven audience inference (scalable to any vertical)

    Args:
        trends: List of trend candidates to evaluate
        memory: Channel memory dict containing brand_tone, banned_topics, recent_titles
        return_top_candidates: If > 0, also return top N ranked trends (default: 0)
        llm_generate_fn: Optional LLM function for AI-driven audience inference (Pattern 1)

    Returns:
        If return_top_candidates == 0: VideoPlan for the selected trend
        If return_top_candidates > 0: Tuple of (VideoPlan, List[top N TrendCandidates])

    Raises:
        ValueError: If no suitable trends found after filtering

    Example:
        >>> plan = generate_video_plan(trends, memory)  # Returns VideoPlan only
        >>> plan, top5 = generate_video_plan(trends, memory, return_top_candidates=5)  # Returns both
        >>> # Pattern 1: With AI-driven audience inference
        >>> plan = generate_video_plan(trends, memory, llm_generate_fn=generate_text)
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
    workspace_id = memory.get("workspace_id")  # For workspace-scoped duplicate check

    for trend in trends:
        if _is_topic_banned(trend, banned_topics):
            logger.debug(f"Filtered out trend '{trend.keyword}': contains banned topic")
            continue

        if _is_too_similar_to_recent(trend, recent_titles):
            logger.debug(f"Filtered out trend '{trend.keyword}': too similar to recent content")
            continue

        # Step 08 Phase 3: Check if already produced (fuzzy match with datastore)
        if is_topic_already_produced(trend.keyword, workspace_id=workspace_id):
            logger.debug(f"Filtered out trend '{trend.keyword}': already produced/scheduled")
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

    # Pattern 1: AI-driven audience inference (with fallback)
    if llm_generate_fn:
        logger.info("  Using AI-driven audience inference (Pattern 1)")
        target_audience = _infer_target_audience_with_llm(
            trend=best_trend,
            workspace=memory,
            llm_generate_fn=llm_generate_fn
        )
    else:
        logger.debug("  Using deterministic audience inference (no LLM provided)")
        target_audience = _infer_target_audience(best_trend, workspace=memory)

    # Create VideoPlan
    video_plan = VideoPlan(
        working_title=best_trend.keyword,
        strategic_angle=best_trend.why_hot,
        target_audience=target_audience,
        language=best_trend.language,
        compliance_notes=compliance_notes
    )

    logger.info(f"Generated VideoPlan: '{video_plan.working_title}'")

    # Return top candidates if requested (for AI-assisted selection)
    if return_top_candidates > 0:
        top_n = min(return_top_candidates, len(ranked_trends))
        logger.info(f"  Also returning top {top_n} ranked candidates for AI selection")
        return video_plan, ranked_trends[:top_n]

    return video_plan
