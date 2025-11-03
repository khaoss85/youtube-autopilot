"""
CTA Strategist Agent: AI-driven CTA placement and funnel optimization.

This agent uses LLM reasoning to design strategic Call-To-Action placement that:
- Maximizes conversion rates through optimal timing
- Places mid-roll CTAs at narrative peaks/transitions
- Designs funnel strategy aligned with content goals
- Balances monetization with viewer experience

Phase 2 - Sprint 1: Revenue-critical agent.

Key Features:
- LLM-powered analysis of narrative arc for CTA moments
- Strategic mid-roll placement (not random timestamps)
- Funnel path design (lead_magnet → playlist → community → external)
- CTA type classification (pause_and_reflect, lead_magnet, engagement, external)
- Timestamp-based CTA scheduling for visual layer

Example Output:
    {
        'main_cta': 'Download free workout plan in description',
        'mid_roll_ctas': [
            {'timestamp': 180, 'cta': 'Think about YOUR fitness goal', 'type': 'pause_and_reflect'},
            {'timestamp': 420, 'cta': 'Link in description for free checklist', 'type': 'lead_magnet'}
        ],
        'funnel_path': 'lead_magnet → playlist → community',
        'reasoning': 'Mid-roll at 180s after problem agitation, 420s before payoff...'
    }
"""

from typing import Dict, Any, List, Optional
from yt_autopilot.core.schemas import EditorialDecision
from yt_autopilot.core.logger import logger, truncate_for_log, log_fallback
from yt_autopilot.core.config import LOG_TRUNCATE_REASONING
import json


def design_cta_strategy(
    duration_strategy: Dict[str, Any],
    editorial_decision: EditorialDecision,
    narrative_arc: Dict[str, Any],
    workspace_config: Dict[str, Any],
    llm_generate_fn
) -> Dict[str, Any]:
    """
    Designs strategic CTA placement and funnel optimization using LLM reasoning.

    Uses AI to find optimal moments for CTAs based on:
    - Narrative arc emotional beats (hook → agitation → solution → payoff)
    - Video duration and format (short/mid/long)
    - Editorial intent (monetization path from Editorial Strategist)
    - Audience engagement patterns (retention curves)

    Args:
        duration_strategy: Duration Strategist's output (target_duration_seconds, format_type)
        editorial_decision: Editorial Strategist's decision (monetization_path, cta_specific)
        narrative_arc: Narrative Architect's output (4-act structure with timestamps)
        workspace_config: Workspace configuration (brand_tone, vertical_id)
        llm_generate_fn: Function to call LLM (from llm_router.generate_text)

    Returns:
        Dict with:
        - main_cta: str (end-of-video call-to-action)
        - mid_roll_ctas: List[Dict] (timestamp-based CTAs for long-form)
            Each dict: {'timestamp': int, 'cta': str, 'type': str}
        - funnel_path: str (conversion funnel strategy)
        - reasoning: str (LLM explanation of placement decisions)
        - cta_count: int (total number of CTAs)

    Example:
        >>> cta_strategy = design_cta_strategy(
        ...     duration_strategy={'target_duration_seconds': 600, 'format_type': 'long'},
        ...     editorial_decision=EditorialDecision(monetization_path='lead_magnet', ...),
        ...     narrative_arc={'acts': [...], 'emotional_beats': [...]},
        ...     workspace_config=workspace,
        ...     llm_generate_fn=generate_text
        ... )
        >>> print(cta_strategy['mid_roll_ctas'])
        [{'timestamp': 180, 'cta': 'Pause and think...', 'type': 'pause_and_reflect'}]
    """
    logger.info("CTA Strategist designing call-to-action placement...")

    target_duration = duration_strategy.get('target_duration_seconds', 180)
    format_type = duration_strategy.get('format_type', 'short')
    monetization_path = editorial_decision.monetization_path
    editorial_cta = editorial_decision.cta_specific

    logger.info(f"  Duration: {target_duration}s ({format_type} format)")
    logger.info(f"  Monetization Path: {monetization_path}")
    logger.info(f"  Editorial CTA: {editorial_cta[:60]}...")

    # Short-form videos (<60s): No mid-roll CTAs (too disruptive)
    if format_type == 'short' or target_duration < 60:
        logger.info("  Short format detected - using single end-of-video CTA only")
        return _create_short_form_cta(editorial_cta, monetization_path)

    # Mid/Long-form videos: Use LLM for strategic mid-roll placement
    logger.info("  Mid/long format detected - calling LLM for strategic CTA placement...")

    # Extract narrative arc structure for LLM context
    acts = narrative_arc.get('acts', [])
    emotional_beats = narrative_arc.get('emotional_beats', [])

    # Format acts for prompt
    acts_summary = []
    for i, act in enumerate(acts, 1):
        act_name = act.get('name', f'Act {i}')
        act_duration = act.get('duration', 0)
        act_purpose = act.get('purpose', '')
        acts_summary.append(f"  Act {i} ({act_name}): {act_duration}s - {act_purpose}")

    acts_text = "\n".join(acts_summary) if acts_summary else "No act structure available"

    # Format emotional beats
    beats_text = ", ".join([f"{beat.get('timestamp', 0)}s: {beat.get('emotion', 'unknown')}" for beat in emotional_beats[:5]]) if emotional_beats else "No beats available"

    # Get brand context
    vertical_id = workspace_config.get('vertical_id', 'unknown')
    brand_tone = workspace_config.get('brand_tone', 'Professional, educational')

    # Build LLM prompt for CTA strategy
    prompt = f"""You are a conversion optimization specialist designing CTA placement for a YouTube video.

**VIDEO CONTEXT:**
- Duration: {target_duration}s ({target_duration // 60}min {target_duration % 60}s)
- Format: {format_type}
- Vertical: {vertical_id}
- Brand Tone: {brand_tone[:100]}

**NARRATIVE STRUCTURE:**
{acts_text}

**EMOTIONAL BEATS:**
{beats_text}

**EDITORIAL STRATEGY:**
- Monetization Path: {monetization_path}
- Suggested CTA: {editorial_cta}

**YOUR TASK:**
Design strategic CTA placement that maximizes conversion while maintaining viewer experience.

**CTA PLACEMENT RULES:**
1. **Mid-roll CTAs** should be placed at:
   - Natural transition points (between acts)
   - Emotional peaks/valleys (after agitation, before solution)
   - Pause moments (after key insight, before payoff)

2. **CTA Types**:
   - pause_and_reflect: Ask viewer to think (builds engagement)
   - lead_magnet: Offer downloadable resource (builds list)
   - engagement: Request like/comment (boosts algorithm)
   - external: Link to tool/resource (partnership/affiliate)

3. **Frequency**:
   - Mid-form (60s-8min): 1-2 mid-roll CTAs max
   - Long-form (8min+): 2-3 mid-roll CTAs max
   - Never place CTAs in first 15s (kills retention)
   - Never place CTAs in last 15s (too late, use main_cta)

4. **Timing Strategy**:
   - First mid-roll: After problem agitation (viewer emotionally invested)
   - Second mid-roll: Before solution reveal (curiosity peak)
   - Third mid-roll: After solution, before final payoff (credibility established)

**MONETIZATION PATH MAPPING:**
- lead_magnet → Primary CTA: "Download [resource] in description", Mid-roll: "Think about YOUR [problem]"
- playlist → Primary CTA: "Watch next video in serie", Mid-roll: "Pause if you need to take notes"
- comment_trigger → Primary CTA: "Comment [keyword] for resource", Mid-roll: "What's YOUR biggest [challenge]?"
- external → Primary CTA: "Link in description for [tool]", Mid-roll: "This is how [tool] solves it"

**FUNNEL PATH DESIGN:**
Design a conversion funnel that guides viewer from video → next action → long-term engagement.

Examples:
- lead_magnet → playlist → community (educational funnel)
- engagement → external → community (affiliate funnel)
- playlist → lead_magnet → external (nurture funnel)

RESPOND ONLY WITH VALID JSON:
{{
  "main_cta": "<end-of-video call-to-action, specific and actionable>",
  "mid_roll_ctas": [
    {{
      "timestamp": <seconds from start, integer>,
      "cta": "<specific CTA text, max 80 chars>",
      "type": "pause_and_reflect|lead_magnet|engagement|external"
    }}
  ],
  "funnel_path": "<step1 → step2 → step3>",
  "reasoning": "<2-3 sentences explaining placement strategy and expected impact>",
  "cta_count": <total number of CTAs including main_cta>
}}

IMPORTANT:
- Be specific in CTA text (not generic "like and subscribe")
- Explain WHY each mid-roll is placed at its timestamp
- Respect narrative flow (don't interrupt climax moments)
- Timestamps must be between 15s and {target_duration - 15}s
- mid_roll_ctas should be sorted by timestamp (ascending)
"""

    logger.debug(f"CTA strategy prompt length: {len(prompt)} chars")

    # Call LLM for CTA strategy
    try:
        response = llm_generate_fn(
            role="cta_strategist",
            task=prompt,
            context="",
            style_hints={"response_format": "json", "temperature": 0.3}  # Lower temp for consistent decisions
        )

        # Parse JSON response
        import re

        try:
            cta_strategy = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: Extract JSON with regex (handle nested objects)
            logger.warning("Direct JSON parse failed, attempting extraction...")

            # Try to find JSON in markdown code blocks first
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                # Find outermost JSON object by brace matching
                start = response.find("{")
                if start == -1:
                    raise ValueError("No JSON object found in LLM response")

                brace_count = 0
                end = start
                for i in range(start, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end = i + 1
                            break

                if brace_count != 0:
                    raise ValueError("Unmatched braces in JSON response")

                json_str = response[start:end]

            try:
                cta_strategy = json.loads(json_str)
                logger.info("Extracted JSON from LLM response")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse extracted JSON: {e}")
                logger.debug(f"Extracted string: {json_str[:200]}...")
                raise ValueError("Could not extract valid JSON from LLM response")

        # Validate and sanitize response
        cta_strategy.setdefault('main_cta', editorial_cta)
        cta_strategy.setdefault('mid_roll_ctas', [])
        cta_strategy.setdefault('funnel_path', 'engagement → playlist → community')
        cta_strategy.setdefault('reasoning', 'LLM-generated CTA strategy')

        # Filter invalid mid-roll timestamps (must be 15s < timestamp < duration-15s)
        valid_mid_rolls = []
        for cta in cta_strategy.get('mid_roll_ctas', []):
            ts = cta.get('timestamp', 0)
            if 15 <= ts <= target_duration - 15:
                valid_mid_rolls.append(cta)
            else:
                logger.warning(f"  Filtered invalid mid-roll CTA at {ts}s (out of valid range)")

        cta_strategy['mid_roll_ctas'] = sorted(valid_mid_rolls, key=lambda x: x.get('timestamp', 0))
        cta_strategy['cta_count'] = len(cta_strategy['mid_roll_ctas']) + 1  # +1 for main_cta

        logger.info("✓ CTA Strategist decision:")
        logger.info(f"  Main CTA: {cta_strategy['main_cta'][:60]}...")
        logger.info(f"  Mid-roll CTAs: {len(cta_strategy['mid_roll_ctas'])}")
        for mid_cta in cta_strategy['mid_roll_ctas']:
            logger.info(f"    - {mid_cta['timestamp']}s ({mid_cta['type']}): {mid_cta['cta'][:50]}...")
        logger.info(f"  Funnel Path: {cta_strategy['funnel_path']}")
        logger.info(f"  Reasoning: {truncate_for_log(cta_strategy['reasoning'], LOG_TRUNCATE_REASONING)}")

        return cta_strategy

    except Exception as e:
        logger.error(f"CTA Strategist LLM failed: {e}")
        logger.warning("Falling back to editorial CTA strategy...")

        log_fallback(
            component="CTA_STRATEGIST",
            fallback_type="EDITORIAL_CTA_FALLBACK",
            reason=f"LLM call failed: {e}",
            impact="HIGH"
        )

        # Fallback: Use editorial CTA with simple mid-roll if long-form
        return _create_fallback_cta(editorial_cta, monetization_path, target_duration, format_type)


def _create_short_form_cta(editorial_cta: str, monetization_path: str) -> Dict[str, Any]:
    """
    Creates simple CTA strategy for short-form videos (<60s).

    Short-form has no mid-roll CTAs to avoid disrupting retention.

    Args:
        editorial_cta: CTA text from Editorial Strategist
        monetization_path: Monetization path from Editorial Strategist

    Returns:
        CTA strategy dict with only main_cta
    """
    logger.info("Creating short-form CTA strategy (no mid-roll)")

    return {
        'main_cta': editorial_cta,
        'mid_roll_ctas': [],  # No mid-roll for shorts
        'funnel_path': _default_funnel_for_path(monetization_path),
        'reasoning': 'Short-form video: single end-screen CTA to maximize retention.',
        'cta_count': 1
    }


def _create_fallback_cta(
    editorial_cta: str,
    monetization_path: str,
    target_duration: int,
    format_type: str
) -> Dict[str, Any]:
    """
    Creates fallback CTA strategy when LLM fails.

    Uses conservative mid-roll placement based on format type.

    Args:
        editorial_cta: CTA text from Editorial Strategist
        monetization_path: Monetization path from Editorial Strategist
        target_duration: Video duration in seconds
        format_type: short/mid/long

    Returns:
        Fallback CTA strategy dict
    """
    logger.info("Creating fallback CTA strategy (LLM unavailable)...")

    mid_roll_ctas = []

    # Conservative mid-roll placement for mid/long-form
    if format_type == 'mid' and target_duration >= 180:
        # Single mid-roll at 60% mark
        mid_roll_ctas.append({
            'timestamp': int(target_duration * 0.6),
            'cta': 'Link in description for more resources',
            'type': 'lead_magnet'
        })
    elif format_type == 'long' and target_duration >= 480:
        # Two mid-rolls at 40% and 70% marks
        mid_roll_ctas.append({
            'timestamp': int(target_duration * 0.4),
            'cta': 'What\'s YOUR biggest challenge with this?',
            'type': 'pause_and_reflect'
        })
        mid_roll_ctas.append({
            'timestamp': int(target_duration * 0.7),
            'cta': 'Link in description for free checklist',
            'type': 'lead_magnet'
        })

    return {
        'main_cta': editorial_cta,
        'mid_roll_ctas': mid_roll_ctas,
        'funnel_path': _default_funnel_for_path(monetization_path),
        'reasoning': f'Fallback strategy: Conservative {format_type} mid-roll placement at narrative transitions.',
        'cta_count': len(mid_roll_ctas) + 1
    }


def _default_funnel_for_path(monetization_path: str) -> str:
    """
    Returns default funnel path for a given monetization strategy.

    Args:
        monetization_path: lead_magnet, playlist, comment_trigger, external

    Returns:
        Funnel path string (e.g., "lead_magnet → playlist → community")
    """
    funnel_map = {
        'lead_magnet': 'lead_magnet → playlist → community',
        'playlist': 'playlist → lead_magnet → community',
        'comment_trigger': 'engagement → community → external',
        'external': 'external → playlist → community'
    }

    return funnel_map.get(monetization_path, 'engagement → playlist → community')
