"""
Duration Strategist Agent: AI-driven video duration optimization for monetization.

This agent analyzes the topic, vertical, and content potential to determine
the optimal video duration that maximizes both engagement AND revenue.

Phase 1 Refactor: Replaces hardcoded series format durations with AI reasoning.
Key decision: Short-form (viral) vs Long-form (monetization).
"""

from typing import Dict, Any, Optional
from yt_autopilot.services.llm_router import generate_text
from yt_autopilot.core.logger import logger, truncate_for_log, log_fallback
from yt_autopilot.core.config import LOG_TRUNCATE_REASONING


def analyze_duration_strategy(
    topic: str,
    vertical_id: str,
    workspace_config: Dict[str, Any],
    vertical_config: Dict[str, Any],
    trend_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    AI-driven duration strategy for monetization optimization.

    Analyzes the topic and decides optimal video duration based on:
    - Monetization potential (Shorts = no ads, 8+ min = mid-roll ads)
    - Content depth (can topic sustain 8+ min of valuable content?)
    - Viral potential (short explosive content vs educational long-form)
    - Vertical CPM (high CPM = prioritize long-form monetization)
    - Competition analysis (what's working in this niche?)

    Args:
        topic: Video topic/title
        vertical_id: Content vertical (finance, tech, etc.)
        workspace_config: Workspace configuration
        vertical_config: Vertical-specific data (CPM, competition)
        trend_data: Optional trend metrics (upvotes, engagement, source)

    Returns:
        Dict with:
        - target_duration_seconds: int (target duration)
        - format_type: str ("short" <60s, "mid" 3-8min, "long" 8-20min)
        - reasoning: str (AI explanation)
        - monetization_strategy: str (ads, shorts_fund, affiliate, etc.)
        - content_depth_score: float (0-1, can topic sustain duration?)
        - viral_potential_score: float (0-1, short-form viral potential)

    Example:
        >>> strategy = analyze_duration_strategy(
        ...     topic="$6.5M margin call disaster",
        ...     vertical_id="finance",
        ...     workspace_config=workspace,
        ...     vertical_config=vertical
        ... )
        >>> print(strategy['target_duration_seconds'])  # e.g., 420 (7min)
        >>> print(strategy['format_type'])  # "mid"
        >>> print(strategy['reasoning'])  # AI explanation
    """
    logger.info("Duration Strategist analyzing monetization strategy...")
    logger.info(f"  Topic: {topic}")
    logger.info(f"  Vertical: {vertical_id}")

    # Extract context
    cpm_baseline = vertical_config.get('cpm_baseline', 10.0)
    brand_tone = workspace_config.get('brand_tone', '')

    # Build trend context if available
    trend_context = ""
    if trend_data:
        source = trend_data.get('source', 'unknown')
        engagement = trend_data.get('engagement_score', 0)
        virality = trend_data.get('virality_potential', 0)
        trend_context = f"""
Trend Data:
- Source: {source}
- Engagement Score: {engagement:.2f}
- Virality Potential: {virality:.2f}
"""

    # Construct AI prompt for duration strategy
    prompt = f"""You are a YouTube monetization strategist analyzing video duration strategy.

TOPIC: "{topic}"
VERTICAL: {vertical_id}
CPM BASELINE: ${cpm_baseline:.2f}
BRAND TONE: {brand_tone[:200]}
{trend_context}

CRITICAL YOUTUBE MONETIZATION RULES:
1. SHORT-FORM (<60s): YouTube Shorts
   - NO traditional ads (no revenue!)
   - Only Shorts Fund (minimal, unreliable)
   - High viral potential, low monetization
   - Good for: Viral topics, hook testing, brand awareness

2. MID-FORM (60s-8min): Pre-roll ads only
   - Pre-roll skippable ads (some revenue)
   - Better than Shorts, worse than long-form
   - Good for: Educational snippets, quick tutorials

3. LONG-FORM (8-20min): Full monetization
   - Mid-roll ads (maximum revenue!)
   - Pre-roll + mid-roll combinations
   - Best monetization potential
   - Good for: In-depth content, tutorials, analysis

YOUR TASK:
Analyze this topic and decide the OPTIMAL duration strategy that maximizes REVENUE while maintaining engagement.

Consider:
1. Content Depth: Can this topic provide 8+ minutes of VALUABLE content? (Score 0-1)
2. Viral Potential: Would this explode as a <60s Short? (Score 0-1)
3. Monetization Priority: With CPM ${cpm_baseline}, prioritize long-form if content allows
4. Competition: What format dominates this topic in {vertical_id}?

RESPOND IN THIS EXACT JSON FORMAT:
{{
  "target_duration_seconds": <recommended duration in seconds>,
  "format_type": "<short|mid|long>",
  "reasoning": "<2-3 sentences explaining why this duration maximizes revenue + engagement>",
  "monetization_strategy": "<ads|shorts_fund|affiliate|hybrid>",
  "content_depth_score": <0.0-1.0, can topic sustain this duration?>,
  "viral_potential_score": <0.0-1.0, short-form viral potential>,
  "alternative_formats": [
    {{"format": "<format>", "duration_seconds": <int>, "pros": "<benefits>", "cons": "<drawbacks>"}}
  ]
}}

IMPORTANT: Be realistic. Don't force 8+ min if content is thin. But prioritize long-form if content depth allows (revenue > virality for monetization).

⚠️ CRITICAL: YOU MUST RESPOND ONLY WITH VALID JSON ⚠️

DO NOT include any text before or after the JSON.
DO NOT use markdown code blocks.
RESPOND WITH RAW JSON ONLY.
"""

    # Call LLM for AI-driven decision
    try:
        response = generate_text(
            role="duration_strategist",
            task=prompt,
            context="",
            style_hints={"response_format": "json", "max_tokens": 1000}
        )

        # Parse JSON response with robust handling
        import json
        import re

        # Try direct JSON parse first
        try:
            strategy = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: Extract JSON from markdown code blocks or text
            logger.warning("Direct JSON parse failed, attempting extraction...")

            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                strategy = json.loads(json_match.group(1))
                logger.info("Extracted JSON from markdown code block")
            else:
                # Try to find JSON object in text
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
                if json_match:
                    strategy = json.loads(json_match.group(0))
                    logger.info("Extracted JSON from text")
                else:
                    raise ValueError("Could not extract valid JSON from response")

        # Validate and set defaults
        strategy.setdefault('target_duration_seconds', 180)  # 3min default
        strategy.setdefault('format_type', 'mid')
        strategy.setdefault('reasoning', 'AI analysis unavailable, using conservative mid-form default')
        strategy.setdefault('monetization_strategy', 'ads')
        strategy.setdefault('content_depth_score', 0.5)
        strategy.setdefault('viral_potential_score', 0.5)
        strategy.setdefault('alternative_formats', [])

        logger.info(f"✓ Duration Strategy decided:")
        logger.info(f"  Target Duration: {strategy['target_duration_seconds']}s ({strategy['target_duration_seconds'] // 60}min {strategy['target_duration_seconds'] % 60}s)")
        logger.info(f"  Format: {strategy['format_type']}")
        logger.info(f"  Monetization: {strategy['monetization_strategy']}")
        logger.info(f"  Content Depth: {strategy['content_depth_score']:.2f}")
        logger.info(f"  Viral Potential: {strategy['viral_potential_score']:.2f}")
        logger.info(f"  Reasoning: {truncate_for_log(strategy['reasoning'], LOG_TRUNCATE_REASONING)}")

        return strategy

    except Exception as e:
        logger.error(f"Duration Strategist AI failed: {e}")
        logger.warning("Falling back to conservative 3-minute duration")

        log_fallback(
            component="DURATION_STRATEGIST",
            fallback_type="CONSERVATIVE_3MIN",
            reason=f"LLM call failed: {e}",
            impact="HIGH"
        )

        # Fallback: Conservative mid-form for monetization
        return {
            'target_duration_seconds': 180,  # 3 minutes
            'format_type': 'mid',
            'reasoning': f'AI analysis failed ({str(e)}). Using conservative 3-minute duration for pre-roll ads while maintaining engagement.',
            'monetization_strategy': 'ads',
            'content_depth_score': 0.5,
            'viral_potential_score': 0.5,
            'alternative_formats': []
        }
