"""
Format Reconciler Agent: AI-driven arbitration of duration strategy divergences.

This agent resolves conflicts between Editorial Strategist and Duration Strategist
when they propose different video durations, using LLM reasoning to find the optimal
balance between narrative depth and monetization potential.

Phase 2 - Sprint 1: Revenue-critical agent.

Key Features:
- LLM-powered arbitration of duration conflicts
- Balances editorial intent (narrative depth) with monetization (ad slots)
- Provides transparent reasoning for final decision
- Ensures downstream agents (Narrative, Script, Visual) use unified duration

Example Divergence:
    Editorial Strategist: 240s (4min) - "Needs time for 3-point breakdown"
    Duration Strategist: 600s (10min) - "Topic can sustain long-form for mid-roll ads"

    Format Reconciler: 420s (7min) - "Compromise allows narrative depth + 2 mid-roll slots"
"""

from typing import Dict, Any, Optional
from yt_autopilot.core.schemas import EditorialDecision, Timeline
from yt_autopilot.core.logger import logger, truncate_for_log, log_fallback
from yt_autopilot.core.config import LOG_TRUNCATE_REASONING
import json


def _infer_aspect_ratio(duration_seconds: int, format_type: str) -> str:
    """
    Infers video aspect ratio based on duration and format type.

    Args:
        duration_seconds: Video duration in seconds
        format_type: Format type ('short', 'mid', 'long')

    Returns:
        Aspect ratio string: '9:16' for short-form, '16:9' for long-form
    """
    if format_type == 'short' or duration_seconds < 60:
        return "9:16"  # Vertical for Shorts
    else:
        return "16:9"  # Horizontal for mid/long-form


def reconcile_format_strategies(
    editorial_decision: EditorialDecision,
    duration_strategy: Dict[str, Any],
    llm_generate_fn,
    workspace_config: Dict[str, Any]
) -> Timeline:
    """
    Arbitrates duration divergences between Editorial and Duration Strategist.

    Uses LLM reasoning to find optimal balance between:
    - Editorial intent (narrative structure, content depth)
    - Monetization goals (ad slots, watch time)
    - Audience engagement (retention, pacing)

    Phase C - P0: Returns Timeline object (single source of truth for duration).
    All downstream agents receive this Timeline to ensure duration consistency.

    Args:
        editorial_decision: Editorial Strategist's decision (includes duration_target)
        duration_strategy: Duration Strategist's output (includes target_duration_seconds)
        llm_generate_fn: Function to call LLM (from llm_router.generate_text)
        workspace_config: Workspace configuration (for CPM, brand tone context)

    Returns:
        Timeline object with:
        - reconciled_duration: int (single source of truth for all agents)
        - format_type: str (short/mid/long)
        - aspect_ratio: str (9:16 for short, 16:9 for mid/long)
        - arbitration_source: str (which strategy won, or "compromise")
        - editorial_weight: float (how much editorial influenced final decision, 0-1)
        - duration_weight: float (how much duration influenced final decision, 0-1)
        - arbitration_reasoning: str (LLM explanation)
        - editorial_duration_original: int (original editorial proposal)
        - duration_strategy_original: int (original duration proposal)
        - duration_breakdown: dict (optional segment timing from editorial)

    Example:
        >>> timeline = reconcile_format_strategies(
        ...     editorial_decision=EditorialDecision(duration_target=240, ...),
        ...     duration_strategy={'target_duration_seconds': 600, 'format_type': 'long'},
        ...     llm_generate_fn=generate_text,
        ...     workspace_config=workspace
        ... )
        >>> print(timeline.reconciled_duration)  # 420 (compromise)
        >>> print(timeline.arbitration_reasoning)  # "Editorial wants depth, Duration wants revenue..."
    """
    logger.info("Format Reconciler arbitrating duration strategies...")

    editorial_duration = editorial_decision.duration_target
    duration_duration = duration_strategy.get('target_duration_seconds', 180)

    # Calculate divergence percentage
    divergence_pct = abs(editorial_duration - duration_duration) / max(editorial_duration, duration_duration) * 100

    logger.info(f"  Editorial Strategist: {editorial_duration}s ({editorial_duration // 60}min {editorial_duration % 60}s)")
    logger.info(f"  Duration Strategist: {duration_duration}s ({duration_duration // 60}min {duration_duration % 60}s)")
    logger.info(f"  Divergence: {divergence_pct:.1f}%")

    # If divergence is small (<15%), no arbitration needed
    if divergence_pct < 15:
        logger.info("  Divergence <15%, using Duration Strategist (monetization priority)")
        format_type = duration_strategy.get('format_type', 'mid')
        return Timeline(
            reconciled_duration=duration_duration,
            format_type=format_type,
            aspect_ratio=_infer_aspect_ratio(duration_duration, format_type),
            arbitration_source='duration_strategist',
            editorial_weight=0.3,
            duration_weight=0.7,
            arbitration_reasoning=f"Editorial ({editorial_duration}s) and Duration ({duration_duration}s) strategies closely aligned. Using Duration Strategist for monetization optimization.",
            editorial_duration_original=editorial_duration,
            duration_strategy_original=duration_duration,
            duration_breakdown=editorial_decision.duration_breakdown if hasattr(editorial_decision, 'duration_breakdown') else None
        )

    # Significant divergence - use LLM arbitration
    logger.info("  Significant divergence detected, calling LLM for arbitration...")

    # Extract context for LLM
    cpm_baseline = workspace_config.get('cpm_baseline', 12.0)
    vertical_id = workspace_config.get('vertical_id', 'unknown')
    brand_tone = workspace_config.get('brand_tone', 'Professional, educational')
    target_language = workspace_config.get('target_language', 'en')

    # Language mapping for explicit instruction (pattern from narrative_architect)
    language_names = {
        "en": "ENGLISH",
        "it": "ITALIAN",
        "es": "SPANISH",
        "fr": "FRENCH",
        "de": "GERMAN",
        "pt": "PORTUGUESE"
    }
    language_instruction = language_names.get(target_language.lower(), target_language.upper())

    # Build LLM arbitration prompt
    prompt = f"""You are a YouTube strategy arbitrator resolving a duration conflict.

⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
ALL TEXT FIELDS (reasoning) MUST BE IN {language_instruction}.
DO NOT mix languages. If you see examples in other languages below, IGNORE their language and write in {language_instruction}.

**EDITORIAL STRATEGIST DECISION:**
- Target Duration: {editorial_duration}s ({editorial_duration // 60}min {editorial_duration % 60}s)
- Serie: {editorial_decision.serie_concept}
- Format: {editorial_decision.format}
- Angle: {editorial_decision.angle}
- Reasoning: {editorial_decision.reasoning_summary}
- Duration Breakdown:
  * Hook: {editorial_decision.duration_breakdown.get('hook', 0)}s
  * Context: {editorial_decision.duration_breakdown.get('context', 0)}s
  * Insight: {editorial_decision.duration_breakdown.get('insight', 0)}s
  * CTA: {editorial_decision.duration_breakdown.get('cta', 0)}s

**DURATION STRATEGIST DECISION:**
- Target Duration: {duration_duration}s ({duration_duration // 60}min {duration_duration % 60}s)
- Format Type: {duration_strategy.get('format_type', 'mid')}
- Monetization Strategy: {duration_strategy.get('monetization_strategy', 'ads')}
- Content Depth Score: {duration_strategy.get('content_depth_score', 0.5):.2f} (0=thin, 1=deep)
- Viral Potential Score: {duration_strategy.get('viral_potential_score', 0.5):.2f}
- Reasoning: {duration_strategy.get('reasoning', 'No reasoning provided')}

**CHANNEL CONTEXT:**
- Vertical: {vertical_id}
- CPM Baseline: ${cpm_baseline:.2f}
- Brand Tone: {brand_tone[:100]}

**YOUR TASK:**
Arbitrate this conflict by finding the optimal duration that:
1. Respects editorial narrative structure (adequate time for story)
2. Maximizes monetization (ad slots, watch time)
3. Maintains audience retention (not too long = drop-off)

**MONETIZATION RULES:**
- Short (<60s): No ads, viral potential only
- Mid (60s-8min): Pre-roll ads only
- Long (8min+): Pre-roll + mid-roll ads (best revenue)

**ARBITRATION OPTIONS:**
A. Use Editorial duration (prioritize narrative depth)
B. Use Duration duration (prioritize monetization)
C. Compromise (find middle ground that satisfies both)

ENGLISH example response:
{{
  "final_duration": 420,
  "format_type": "long",
  "reasoning": "Chose 420s as compromise. Editorial needs 3-point breakdown, Duration wants mid-roll ad slots. This duration allows both. Sacrificing 1 mid-roll slot for narrative clarity.",
  "arbitration_source": "compromise",
  "editorial_weight": 0.6,
  "duration_weight": 0.4
}}

ITALIAN example response:
{{
  "final_duration": 420,
  "format_type": "long",
  "reasoning": "Scelto 420s come compromesso. Editorial necessita articolazione a 3 punti, Duration vuole slot pubblicitari mid-roll. Questa durata permette entrambi. Sacrificando 1 slot mid-roll per chiarezza narrativa.",
  "arbitration_source": "compromise",
  "editorial_weight": 0.6,
  "duration_weight": 0.4
}}

IMPORTANT:
- reasoning field MUST be in {language_instruction}
- Be specific about WHY you chose this duration
- Explain trade-offs clearly
- Weights should sum to 1.0
"""

    logger.debug(f"Arbitration prompt length: {len(prompt)} chars")

    # Call LLM for arbitration
    try:
        response = llm_generate_fn(
            role="format_reconciler",
            task=prompt,
            context="",
            style_hints={"response_format": "json", "temperature": 0.3}  # Lower temp for consistent decisions
        )

        # Parse JSON response
        import re

        try:
            reconciled = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: Extract JSON with regex
            logger.warning("Direct JSON parse failed, attempting extraction...")
            json_match = re.search(r'\{[^{}]*"final_duration"[^{}]*\}', response, re.DOTALL)
            if json_match:
                reconciled = json.loads(json_match.group(0))
                logger.info("Extracted JSON from LLM response")
            else:
                raise ValueError("Could not extract valid JSON from LLM response")

        # Validate response
        reconciled.setdefault('final_duration', duration_duration)  # Fallback to Duration
        reconciled.setdefault('format_type', duration_strategy.get('format_type', 'mid'))
        reconciled.setdefault('reasoning', 'LLM arbitration unavailable, using Duration Strategist')
        reconciled.setdefault('arbitration_source', 'duration_strategist')
        reconciled.setdefault('editorial_weight', 0.3)
        reconciled.setdefault('duration_weight', 0.7)

        # Create Timeline object from LLM response
        final_duration = reconciled['final_duration']
        format_type = reconciled['format_type']
        timeline = Timeline(
            reconciled_duration=final_duration,
            format_type=format_type,
            aspect_ratio=_infer_aspect_ratio(final_duration, format_type),
            arbitration_source=reconciled['arbitration_source'],
            editorial_weight=reconciled['editorial_weight'],
            duration_weight=reconciled['duration_weight'],
            arbitration_reasoning=reconciled['reasoning'],
            editorial_duration_original=editorial_duration,
            duration_strategy_original=duration_duration,
            duration_breakdown=editorial_decision.duration_breakdown if hasattr(editorial_decision, 'duration_breakdown') else None
        )

        logger.info("✓ Format Reconciler decision:")
        logger.info(f"  Final Duration: {timeline.reconciled_duration}s ({timeline.reconciled_duration // 60}min {timeline.reconciled_duration % 60}s)")
        logger.info(f"  Format Type: {timeline.format_type}")
        logger.info(f"  Arbitration Source: {timeline.arbitration_source}")
        logger.info(f"  Editorial Weight: {timeline.editorial_weight:.2f} | Duration Weight: {timeline.duration_weight:.2f}")
        logger.info(f"  Reasoning: {truncate_for_log(timeline.arbitration_reasoning, LOG_TRUNCATE_REASONING)}")

        return timeline

    except Exception as e:
        logger.error(f"Format Reconciler LLM failed: {e}")
        logger.warning("Falling back to Duration Strategist (monetization priority)")

        log_fallback(
            component="FORMAT_RECONCILER",
            fallback_type="DURATION_STRATEGIST_FALLBACK",
            reason=f"LLM call failed: {e}",
            impact="MEDIUM"
        )

        # Fallback: Use Duration Strategist (prioritize monetization)
        format_type = duration_strategy.get('format_type', 'mid')
        return Timeline(
            reconciled_duration=duration_duration,
            format_type=format_type,
            aspect_ratio=_infer_aspect_ratio(duration_duration, format_type),
            arbitration_source='duration_strategist_fallback',
            editorial_weight=0.0,
            duration_weight=1.0,
            arbitration_reasoning=f"LLM arbitration failed ({str(e)}). Defaulting to Duration Strategist for monetization optimization.",
            editorial_duration_original=editorial_duration,
            duration_strategy_original=duration_duration,
            duration_breakdown=editorial_decision.duration_breakdown if hasattr(editorial_decision, 'duration_breakdown') else None
        )
