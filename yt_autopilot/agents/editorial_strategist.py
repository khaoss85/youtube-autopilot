"""
Editorial Strategist Agent: AI-driven strategic decision-making for video content.

This agent uses LLM reasoning to transform trends into strategic video plans that:
- Strengthen brand positioning (not just reactive news)
- Monetize effectively (clear next steps)
- Educate the audience (go beyond entertainment)
- Stand out from competitors (unique angles)

Architecture:
- This agent is AI-native, not template-driven
- Uses Chain-of-Thought reasoning for strategic decisions
- Considers workspace config, performance history, and competitive landscape
- NO hardcoded keywords, NO rigid templates
- Learns from performance data over time

Integration:
- Called by pipeline after trend selection, before script writing
- Outputs EditorialDecision which guides downstream agents
- Can suggest new series concepts based on performance patterns
"""

from typing import Dict, Optional, List
import json
from yt_autopilot.core.schemas import TrendCandidate, EditorialDecision
from yt_autopilot.core.logger import logger, truncate_for_log, log_fallback
from yt_autopilot.core.config import LOG_TRUNCATE_REASONING
from yt_autopilot.core.language_validator import validate_and_fix_enum_fields


def _format_performance_insights(performance_history: Optional[List[Dict]]) -> str:
    """
    Formats performance history for LLM context.

    Args:
        performance_history: List of recent videos with performance metrics

    Returns:
        Formatted string for LLM prompt
    """
    if not performance_history or len(performance_history) == 0:
        return "No performance history available yet (new channel)."

    # Take top 10 most recent videos
    recent_videos = performance_history[-10:] if len(performance_history) > 10 else performance_history

    lines = []
    for video in recent_videos:
        title = video.get('title', 'Untitled')[:60]
        views = video.get('views', 0)
        retention = video.get('avg_view_duration_percentage', 0)
        ctr = video.get('ctr', 0)
        serie = video.get('serie_id', 'unknown')
        format_type = video.get('format', 'unknown')

        lines.append(
            f"- '{title}' | Serie: {serie} | Format: {format_type} | "
            f"Views: {views} | Retention: {retention:.1f}% | CTR: {ctr:.1f}%"
        )

    return "\n".join(lines)


def _extract_json_from_llm_response(llm_text: str) -> Optional[Dict]:
    """
    Extracts JSON from LLM response, handling markdown code blocks and extra text.

    Args:
        llm_text: Raw LLM response text

    Returns:
        Parsed JSON dict or None if parsing fails
    """
    # Try to find JSON in markdown code blocks
    if "```json" in llm_text:
        start = llm_text.find("```json") + 7
        end = llm_text.find("```", start)
        json_str = llm_text[start:end].strip()
    elif "```" in llm_text:
        start = llm_text.find("```") + 3
        end = llm_text.find("```", start)
        json_str = llm_text[start:end].strip()
    else:
        # Try to find JSON object by curly braces
        start = llm_text.find("{")
        end = llm_text.rfind("}") + 1
        if start != -1 and end > start:
            json_str = llm_text[start:end]
        else:
            json_str = llm_text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # 🚨 Log JSON parsing failure fallback (returns None)
        log_fallback(
            component="EDITORIAL_STRATEGIST_JSON_PARSE",
            fallback_type="JSON_PARSE_ERROR",
            reason=f"Failed to parse JSON from LLM response: {e}",
            impact="MEDIUM"
        )
        logger.error(f"Failed to parse JSON from LLM response: {e}")
        logger.debug(f"Attempted to parse: {json_str[:200]}")
        return None


def decide_editorial_strategy(
    trend: TrendCandidate,
    workspace: Dict,
    llm_generate_fn,
    performance_history: Optional[List[Dict]] = None
) -> EditorialDecision:
    """
    Uses LLM reasoning to decide editorial strategy for a trend.

    This is the entry point for the Editorial Strategist agent. It analyzes:
    - The trend's unique characteristics
    - Workspace brand positioning
    - Performance history patterns
    - Monetization opportunities

    And outputs a strategic decision on:
    - Which serie concept to use (existing or new)
    - What format fits best (tutorial/analysis/alert/comparison)
    - What angle to take (risk/opportunity/education/history)
    - Optimal duration and breakdown
    - Monetization path and specific CTA

    Args:
        trend: The selected trend to create content about
        workspace: Workspace configuration dict (brand_tone, vertical_id, etc.)
        llm_generate_fn: Function to call LLM (typically from llm_router.generate_text)
        performance_history: Optional list of recent video performance data

    Returns:
        EditorialDecision with AI-generated strategy

    Example:
        >>> decision = decide_editorial_strategy(
        ...     trend=burry_trend,
        ...     workspace=finance_workspace,
        ...     llm_generate_fn=generate_text,
        ...     performance_history=recent_videos
        ... )
        >>> print(decision.serie_concept)
        "Bubble Alert"
        >>> print(decision.reasoning_summary)
        "Analysis format chosen because Burry's thesis requires context.
        28s duration allows for 3-indicator breakdown. Lead magnet CTA
        capitalizes on actionable checklist desire."
    """
    logger.info("=" * 70)
    logger.info("EDITORIAL STRATEGIST: Analyzing trend with LLM reasoning...")
    logger.info(f"Trend: {trend.keyword}")
    logger.info(f"Vertical: {workspace.get('vertical_id', 'unknown')}")
    logger.info("=" * 70)

    # Format performance insights
    perf_insights = _format_performance_insights(performance_history)

    # Get CPM baseline from workspace
    cpm_baseline = workspace.get('cpm_baseline', 15.0)
    if 'editorial_strategy' in workspace and 'cpm_baseline' in workspace['editorial_strategy']:
        cpm_baseline = workspace['editorial_strategy']['cpm_baseline']

    # Build Chain-of-Thought reasoning prompt
    prompt = f"""You are an editorial strategist for a YouTube finance channel with CPM ${cpm_baseline}.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL: ENUM FIELD REQUIREMENTS ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You MUST respond in the workspace language ({workspace.get('target_language', 'en')}), BUT enum fields below
MUST use EXACT English values. DO NOT TRANSLATE THESE ENUM VALUES.

**REQUIRED ENUM VALUES (copy exactly, case-sensitive):**

1. "format" field - ONE of these EXACT strings:
   ✓ "tutorial"      (step-by-step actionable guide)
   ✓ "analysis"      (context + insight + implication)
   ✓ "alert"         (risk identification + defense)
   ✓ "comparison"    (options breakdown + recommendation)

2. "angle" field - ONE of these EXACT strings:
   ✓ "risk"          (threat identification)
   ✓ "opportunity"   (actionable upside)
   ✓ "education"     (learning layer)
   ✓ "history"       (past context)

3. "monetization_path" field - ONE of these EXACT strings:
   ✓ "lead_magnet"      (downloadable resource)
   ✓ "playlist"         (serie continuation)
   ✓ "comment_trigger"  (engagement keyword)
   ✓ "external"         (tool/partner link)

**EXAMPLES:**
❌ WRONG: "format": "analisi"           (translated to Italian)
✅ CORRECT: "format": "analysis"        (English, copied exactly)

❌ WRONG: "angle": "educazione"         (translated to Italian)
✅ CORRECT: "angle": "education"        (English, copied exactly)

❌ WRONG: "monetization_path": "risorsa_scaricabile"
✅ CORRECT: "monetization_path": "lead_magnet"

**INSTRUCTIONS:**
- COPY the enum values EXACTLY as shown above (case-sensitive)
- DO NOT translate enum values to workspace language
- Other fields (serie_concept, cta_specific, reasoning_summary) can be in workspace language
- If unsure, default to: format="analysis", angle="education", monetization_path="playlist"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHANNEL CONTEXT:
- Vertical: {workspace.get('vertical_id', 'finance')}
- Brand tone: {workspace.get('brand_tone', 'Professional, educational, transparent')}
- Recent videos (last 10): {workspace.get('recent_titles', [])[-10:]}

PERFORMANCE HISTORY (last 10 videos):
{perf_insights}

TREND CANDIDATE:
- Keyword: {trend.keyword}
- Why hot: {trend.why_hot}
- Source: {trend.source}
- Momentum: {trend.momentum_score:.2f}/1.0

TASK: Use Chain-of-Thought reasoning to transform this trend into a strategic video that:
1. Strengthens brand (not just reactive news)
2. Monetizes effectively (has clear next step)
3. Educates audience (goes beyond entertainment)
4. Stands out from competitors (unique angle)

REASONING CHAIN:

<brand_analysis>
Analyze how this trend connects to our channel positioning.
Which series/themes from our brand can this reinforce?
What makes this content "ours" and not just generic news?

Think about:
- Is this a recurring theme we can build a serie around?
- Does it align with our "professional + educational" tone?
- How can we frame it to build brand IP, not just ride the trend?
</brand_analysis>

<audience_value>
What specific question does this video answer for our audience?
What's the insight layer that goes beyond surface-level facts?
Why should the audience watch US and not the other 100 channels covering this?

Think about:
- What's the "non-obvious" insight we can provide?
- What actionable knowledge does the viewer gain?
- What transformation happens (before viewing → after viewing)?
</audience_value>

<format_decision>
Based on performance history, which format maximizes engagement + watch time?

Options:
- TUTORIAL: Step-by-step actionable guide (best when audience needs "how-to")
- ANALYSIS: Context + insight + implication (best for complex topics needing depth)
- ALERT: Risk identification + defense strategy (best for urgent warnings)
- COMPARISON: Options breakdown + recommendation (best for decision-making)

Explain WHY this format fits this specific trend and our performance patterns.
</format_decision>

<monetization_path>
What next step makes sense for THIS video to maximize LTV (lifetime value)?

Options:
- LEAD_MAGNET: Downloadable resource (checklist, template, watchlist) → if educational/actionable
- PLAYLIST: Serie continuation → if part of recurring theme
- COMMENT_TRIGGER: Engagement keyword for resource → if community-building
- EXTERNAL: Tool/resource link → if partnership value

Explain WHY this path creates most value for both viewer and channel.
</monetization_path>

<duration_optimization>
Given CPM ${cpm_baseline} and content type, what's the optimal duration?

Consider:
- Too short (< 20s) loses educational value and revenue
- Too long (> 40s) loses retention in Shorts format
- Finance content needs time for "insight layer" (not just facts)

Breakdown the time:
- HOOK: How many seconds to grab attention?
- CONTEXT: How many seconds to set up the story?
- INSIGHT: How many seconds for the educational layer?
- CTA: How many seconds for the call-to-action?

Explain WHY this duration maximizes revenue for THIS specific video.
</duration_optimization>

OUTPUT (valid JSON only, no markdown formatting):
{{
  "serie_concept": "<name of serie - can be new if performance data suggests it>",
  "format": "<MUST BE ONE OF: tutorial, analysis, alert, comparison - EXACT ENGLISH VALUE>",
  "angle": "<MUST BE ONE OF: risk, opportunity, education, history - EXACT ENGLISH VALUE>",
  "duration_target": <total seconds>,
  "duration_breakdown": {{
    "hook": <seconds>,
    "context": <seconds>,
    "insight": <seconds>,
    "cta": <seconds>
  }},
  "monetization_path": "<MUST BE ONE OF: lead_magnet, playlist, comment_trigger, external - EXACT ENGLISH VALUE>",
  "cta_specific": "<exact CTA text to use - be specific, not template>",
  "reasoning_summary": "<2-3 sentences explaining the key strategic choices>",
  "performance_context": "<optional: insights from performance history that influenced decisions>"
}}

CRITICAL VALIDATION BEFORE RESPONDING:
✓ Check "format" field: Is it EXACTLY one of: tutorial, analysis, alert, comparison?
✓ Check "angle" field: Is it EXACTLY one of: risk, opportunity, education, history?
✓ Check "monetization_path" field: Is it EXACTLY one of: lead_magnet, playlist, comment_trigger, external?
✓ All three enum fields MUST be in English (NOT translated to {workspace.get('target_language', 'en')})

IMPORTANT:
- Think step-by-step through each section
- Base decisions on data (performance history + CPM economics)
- Be specific in CTA (not "like and subscribe" generic)
- Duration breakdown must sum to duration_target
- ⚠️ ENUM FIELDS MUST USE EXACT ENGLISH VALUES FROM LIST ABOVE ⚠️
- Output ONLY valid JSON, no extra text or markdown
"""

    logger.info("Calling LLM for editorial strategy decision...")
    logger.debug(f"Prompt length: {len(prompt)} chars")

    # Call LLM with reasoning prompt
    try:
        llm_response = llm_generate_fn(
            role="editorial_strategist",
            task=f"Decide editorial strategy for trend: {trend.keyword}",
            context=prompt,
            style_hints={"temperature": 0.3}  # Lower temperature for more consistent strategic decisions
        )

        logger.debug(f"LLM response: {llm_response[:200]}...")

        # Parse JSON from response
        decision_data = _extract_json_from_llm_response(llm_response)

        if not decision_data:
            raise ValueError("Failed to extract valid JSON from LLM response")

        # Layer 2: AI-driven enum validation and correction
        enum_specs = {
            "format": ["tutorial", "analysis", "alert", "comparison"],
            "angle": ["risk", "opportunity", "education", "history"],
            "monetization_path": ["lead_magnet", "playlist", "comment_trigger", "external"]
        }

        decision_data = validate_and_fix_enum_fields(
            json_output=decision_data,
            llm_generate_fn=llm_generate_fn,
            target_language=workspace.get('target_language', 'en'),
            enum_specs=enum_specs,
            component_name="editorial_strategist"
        )

        # Create EditorialDecision from parsed data
        decision = EditorialDecision(**decision_data)

        logger.info("✓ Editorial decision generated successfully")
        logger.info(f"  Serie: {decision.serie_concept}")
        logger.info(f"  Format: {decision.format}")
        logger.info(f"  Angle: {decision.angle}")
        logger.info(f"  Duration: {decision.duration_target}s")
        logger.info(f"  Monetization: {decision.monetization_path}")
        logger.info(f"  Reasoning: {truncate_for_log(decision.reasoning_summary, LOG_TRUNCATE_REASONING)}")

        return decision

    except Exception as e:
        logger.error(f"Editorial strategist failed: {e}")
        logger.warning("Falling back to default editorial decision...")

        log_fallback(
            component="EDITORIAL_STRATEGIST",
            fallback_type="DEFAULT_DECISION",
            reason=f"LLM call failed: {e}",
            impact="HIGH"
        )

        # Fallback to safe default decision
        return _create_fallback_decision(trend, workspace, cpm_baseline)


def _create_fallback_decision(
    trend: TrendCandidate,
    workspace: Dict,
    cpm_baseline: float
) -> EditorialDecision:
    """
    Creates a safe fallback editorial decision if LLM fails.

    Args:
        trend: The trend candidate
        workspace: Workspace configuration
        cpm_baseline: CPM baseline for duration calculation

    Returns:
        Conservative EditorialDecision
    """
    logger.info("Creating fallback editorial decision (LLM unavailable)...")

    # Conservative defaults
    duration = 25 if cpm_baseline >= 20 else 20  # Longer for higher CPM

    return EditorialDecision(
        serie_concept="Market Insights",  # Generic serie name
        format="analysis",  # Safe format for most content
        angle="education",  # Safe angle
        duration_target=duration,
        duration_breakdown={
            "hook": 4,
            "context": 8,
            "insight": 10,
            "cta": duration - 22  # Remaining time
        },
        monetization_path="playlist",  # Safe default
        cta_specific=f"Seguici per altre analisi su {workspace.get('vertical_id', 'finance')}",
        reasoning_summary="Fallback decision: LLM reasoning unavailable. Using conservative defaults based on vertical best practices.",
        performance_context="No LLM analysis - fallback mode"
    )
