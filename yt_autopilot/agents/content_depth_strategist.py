"""
Content Depth Strategist - AI-Driven Bullets Count Optimization

Risolve il problema critico: "2 bullets per 8min" (content troppo thin).

Questo agent analizza topic complexity + target duration per determinare:
- Optimal bullets count (AI reasoning, no hardcoded values)
- Time allocation per bullet
- Content depth score (quanto deep deve essere ogni bullet)
- Pacing guidance

Approach:
- LLM Chain-of-Thought reasoning
- Topic complexity analysis
- Duration-based content density calculation
- Narrative arc consideration

Author: YT Autopilot Team
Version: 2.0 (Content Depth Fix - Sprint 2)
"""

from typing import Dict, List, Optional, Callable
from yt_autopilot.core.logger import logger, truncate_for_log, log_fallback
from yt_autopilot.core.config import LOG_TRUNCATE_REASONING


def analyze_content_depth(
    topic: str,
    target_duration: int,
    narrative_arc: Dict,
    editorial_decision: Dict,
    workspace: Dict,
    llm_generate_fn: Callable
) -> Dict:
    """
    Analizza content depth e determina optimal bullets count.

    Args:
        topic: Video topic/title
        target_duration: Target duration in seconds (from reconciled format)
        narrative_arc: Narrative arc da Narrative Architect (acts, emotional beats)
        editorial_decision: Editorial decision (format, angle, serie)
        workspace: Workspace config
        llm_generate_fn: LLM function per AI reasoning

    Returns:
        Dict con:
            - recommended_bullets (int): Optimal bullets count
            - time_per_bullet (List[int]): Time allocation per bullet
            - depth_scores (List[float]): Depth level per bullet (0-1)
            - pacing_guidance (str): Pacing notes
            - reasoning (str): LLM reasoning explanation
            - adequacy_score (float): 0-1 score di content adequacy

    Example:
        {
            "recommended_bullets": 5,
            "time_per_bullet": [60, 90, 100, 80, 70],  # 400s total
            "depth_scores": [0.6, 0.8, 0.9, 0.7, 0.6],
            "pacing_guidance": "Start strong, peak at bullet 3, wind down gracefully",
            "reasoning": "480s duration allows 5-6 bullets with avg 80-100s each...",
            "adequacy_score": 0.85
        }
    """
    logger.info("=" * 70)
    logger.info("CONTENT DEPTH STRATEGIST: AI-Driven Bullets Count Optimization")
    logger.info("=" * 70)
    logger.info(f"  Topic: {topic[:80]}...")
    logger.info(f"  Target duration: {target_duration}s ({target_duration/60:.1f}min)")
    logger.info(f"  Format: {editorial_decision.get('format', 'unknown')}")
    logger.info(f"  Narrative acts: {len(narrative_arc.get('narrative_structure', []))}")

    # Extract context
    format_type = editorial_decision.get('format', 'tutorial')
    angle = editorial_decision.get('angle', 'educational')
    narrative_acts = narrative_arc.get('narrative_structure', [])
    vertical_id = workspace.get('vertical_id', 'general')

    # Build LLM prompt with Chain-of-Thought reasoning
    prompt = f"""
You are a content depth strategist for YouTube videos.

TASK: Determine optimal bullets count and time allocation for this video.

VIDEO CONTEXT:
- Topic: {topic}
- Target duration: {target_duration}s ({target_duration/60:.1f} minutes)
- Format: {format_type}
- Angle: {angle}
- Vertical: {vertical_id}
- Narrative acts: {len(narrative_acts)}

CHAIN-OF-THOUGHT REASONING:

Step 1: TOPIC COMPLEXITY ANALYSIS
- How many distinct insights can this topic sustain?
- Is this a simple concept (2-3 bullets) or complex topic (5-7 bullets)?
- Does audience need background context or can we go straight to insights?

Step 2: AUDIENCE ATTENTION SPAN
- Given {target_duration}s duration, how many content points maintain engagement?
- YouTube retention curve: First 30s critical, engagement drops after 3-4min if no variety
- Optimal bullet frequency: 60-120s per bullet for educational content

Step 3: PACING CALCULATION
- Seconds per bullet needed to avoid:
  a) Padding (content stretched thin, boring)
  b) Rushing (too many points, overwhelming)
- Rule of thumb:
  - Shorts (<60s): 1-2 bullets max
  - Mid-form (60-300s): 3-5 bullets
  - Long-form (300-600s): 5-8 bullets
  - Extended (600s+): 7-10 bullets

Step 4: DEPTH LEVEL PER BULLET
- Each bullet needs a depth score (0.0-1.0):
  - 0.3 = Surface mention (20-40s)
  - 0.5 = Standard explanation (60-80s)
  - 0.7 = Deep dive (90-120s)
  - 1.0 = Comprehensive analysis (150-180s)
- Balance shallow intros with deep insights

Step 5: NARRATIVE PROGRESSION
- Hook → Build → Peak → Wind down
- Allocate more time to peak insights (middle bullets)
- First bullet: Quick context (shorter)
- Last bullet: Action step / takeaway (moderate)

CONSTRAINTS:
- Minimum bullets: 2 (even for Shorts)
- Maximum bullets: 10 (avoid fragmentation)
- Total time across bullets should be ~80-90% of target duration (allow for hook/outro)
- Each bullet needs at least 20s minimum

⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
ALL text fields (pacing_guidance, reasoning) MUST be written in workspace language ({vertical_id} workspace).
This is NOT optional - language compliance is strictly validated.

Example outputs by language:

English example:
{{
  "recommended_bullets": 5,
  "time_per_bullet": [60, 90, 100, 80, 70],
  "depth_scores": [0.6, 0.8, 0.9, 0.7, 0.6],
  "pacing_guidance": "Start with quick context, build to deep insight at bullet 3, then wind down with actionable takeaway",
  "reasoning": "Topic complexity sustains 5 bullets. 480s / 5 = 96s avg per bullet, allowing depth. Allocated more time (100s) to bullet 3 where narrative peaks. First bullet is shorter (60s) for quick engagement hook. Total: 400s (83% of 480s target), leaving 80s for hook/outro.",
  "adequacy_score": 0.85
}}

Italian example:
{{
  "recommended_bullets": 5,
  "time_per_bullet": [60, 90, 100, 80, 70],
  "depth_scores": [0.6, 0.8, 0.9, 0.7, 0.6],
  "pacing_guidance": "Inizia con un contesto rapido, costruisci fino all'insight profondo al punto 3, poi concludi con un takeaway azionabile",
  "reasoning": "La complessità dell'argomento sostiene 5 punti. 480s / 5 = 96s medi per punto, consentendo profondità. Allocato più tempo (100s) al punto 3 dove il picco narrativo avviene. Primo punto più breve (60s) per hook di engagement rapido. Totale: 400s (83% del target 480s), lasciando 80s per hook/outro.",
  "adequacy_score": 0.85
}}

IMPORTANT VALIDATION RULES:
- reasoning and pacing_guidance MUST be in workspace language
- reasoning MUST explain WHY this bullets count is optimal (not just describe numbers)
- time_per_bullet MUST sum to 70-90% of target_duration
- depth_scores MUST match time allocation (more time = higher depth)
- adequacy_score: 0.8+ = excellent, 0.6-0.8 = good, <0.6 = needs revision

OUTPUT:
"""

    try:
        # Call LLM with Chain-of-Thought prompt
        logger.info("  Calling LLM for content depth reasoning...")

        llm_response = llm_generate_fn(
            role="content_depth_strategist",
            task=prompt,
            context="",
            style_hints={"response_format": "json", "temperature": 0.4}
        )

        # Parse JSON response
        import json
        import re

        # Try direct parse
        try:
            strategy = json.loads(llm_response)
        except json.JSONDecodeError:
            # Extract JSON from markdown code blocks if needed
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', llm_response, re.DOTALL)
            if json_match:
                strategy = json.loads(json_match.group(1))
            else:
                # Try finding raw JSON
                json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
                if json_match:
                    strategy = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not extract JSON from LLM response")

        # Validate strategy
        required_keys = ['recommended_bullets', 'time_per_bullet', 'depth_scores', 'pacing_guidance', 'reasoning']
        missing_keys = [k for k in required_keys if k not in strategy]

        if missing_keys:
            raise ValueError(f"LLM response missing keys: {missing_keys}")

        # Validate bullets count reasonable
        bullets = strategy['recommended_bullets']
        if not (2 <= bullets <= 10):
            logger.warning(f"⚠️ Recommended bullets {bullets} outside range [2-10], clamping")
            bullets = max(2, min(10, bullets))
            strategy['recommended_bullets'] = bullets

        # Validate time allocation
        time_allocations = strategy['time_per_bullet']
        if len(time_allocations) != bullets:
            logger.warning(f"⚠️ time_per_bullet length mismatch: {len(time_allocations)} != {bullets}")
            # Pad or trim to match
            if len(time_allocations) < bullets:
                avg_time = target_duration // bullets
                time_allocations.extend([avg_time] * (bullets - len(time_allocations)))
            else:
                time_allocations = time_allocations[:bullets]
            strategy['time_per_bullet'] = time_allocations

        total_time = sum(time_allocations)
        time_utilization = total_time / target_duration

        if time_utilization < 0.6 or time_utilization > 0.95:
            logger.warning(f"⚠️ Time utilization {time_utilization:.1%} outside optimal range [60-95%]")

        # Validate depth scores
        depth_scores = strategy.get('depth_scores', [0.7] * bullets)
        if len(depth_scores) != bullets:
            depth_scores = [0.7] * bullets  # Fallback
            strategy['depth_scores'] = depth_scores

        # Calculate adequacy score if not provided
        if 'adequacy_score' not in strategy:
            adequacy_score = _calculate_adequacy_score(
                bullets=bullets,
                target_duration=target_duration,
                time_utilization=time_utilization,
                depth_scores=depth_scores
            )
            strategy['adequacy_score'] = adequacy_score

        # Log results
        logger.info("=" * 70)
        logger.info("✓ CONTENT DEPTH STRATEGY GENERATED")
        logger.info("=" * 70)
        logger.info(f"  Recommended bullets: {bullets}")
        logger.info(f"  Time allocation: {time_allocations} (total: {total_time}s / {target_duration}s = {time_utilization:.1%})")
        logger.info(f"  Depth scores: {depth_scores}")
        logger.info(f"  Adequacy score: {strategy['adequacy_score']:.2f}")
        logger.info(f"  Pacing guidance: {strategy['pacing_guidance'][:80]}...")
        logger.info(f"  Reasoning: {truncate_for_log(strategy['reasoning'], LOG_TRUNCATE_REASONING)}")
        logger.info("=" * 70)

        return strategy

    except Exception as e:
        logger.error(f"❌ Content Depth Strategist failed: {e}")
        logger.warning("Falling back to deterministic strategy")

        log_fallback(
            component="CONTENT_DEPTH_STRATEGIST",
            fallback_type="DETERMINISTIC_FALLBACK",
            reason=f"LLM call failed: {e}",
            impact="HIGH"
        )

        # Fallback: Deterministic strategy based on duration
        fallback_strategy = _generate_fallback_strategy(
            target_duration=target_duration,
            format_type=format_type
        )

        logger.warning(f"  Using fallback: {fallback_strategy['recommended_bullets']} bullets")
        return fallback_strategy


def _calculate_adequacy_score(
    bullets: int,
    target_duration: int,
    time_utilization: float,
    depth_scores: List[float]
) -> float:
    """
    Calcola adequacy score (0-1) per content depth strategy.

    Factors:
    - Bullets count appropriateness for duration
    - Time utilization efficiency
    - Depth score distribution (peak insight present?)

    Returns:
        Score 0-1 (0.8+ = excellent, 0.6-0.8 = good, <0.6 = needs revision)
    """
    score = 0.5  # Baseline

    # Factor 1: Bullets appropriateness
    optimal_bullets = target_duration // 90  # 90s per bullet is sweet spot
    bullets_deviation = abs(bullets - optimal_bullets) / optimal_bullets

    if bullets_deviation < 0.2:
        score += 0.25  # Excellent bullets count
    elif bullets_deviation < 0.4:
        score += 0.15  # Good bullets count
    else:
        score += 0.05  # Suboptimal bullets count

    # Factor 2: Time utilization
    if 0.75 <= time_utilization <= 0.90:
        score += 0.25  # Excellent utilization
    elif 0.60 <= time_utilization < 0.75 or 0.90 < time_utilization <= 0.95:
        score += 0.15  # Good utilization
    else:
        score += 0.05  # Suboptimal utilization

    # Factor 3: Depth distribution (has peak insight?)
    if depth_scores:
        max_depth = max(depth_scores)
        avg_depth = sum(depth_scores) / len(depth_scores)

        if max_depth >= 0.8 and avg_depth >= 0.6:
            score += 0.2  # Excellent depth distribution
        elif max_depth >= 0.7 and avg_depth >= 0.5:
            score += 0.1  # Good depth distribution
        else:
            score += 0.05  # Suboptimal depth

    return min(1.0, score)


def _generate_fallback_strategy(
    target_duration: int,
    format_type: str
) -> Dict:
    """
    Genera fallback strategy deterministica se LLM fails.

    Args:
        target_duration: Target duration in seconds
        format_type: Format type (tutorial, analysis, etc.)

    Returns:
        Fallback strategy dict
    """
    # Deterministic bullets count based on duration
    if target_duration <= 60:
        bullets = 2
    elif target_duration <= 120:
        bullets = 3
    elif target_duration <= 300:
        bullets = 4
    elif target_duration <= 480:
        bullets = 5
    else:
        bullets = 6

    # Equal time allocation (simple)
    avg_time = int(target_duration * 0.80 / bullets)  # 80% utilization
    time_per_bullet = [avg_time] * bullets

    # Standard depth scores
    depth_scores = [0.6, 0.7, 0.8, 0.7, 0.6, 0.6][:bullets]

    adequacy_score = 0.65  # Fallback is "good enough" but not excellent

    return {
        'recommended_bullets': bullets,
        'time_per_bullet': time_per_bullet,
        'depth_scores': depth_scores,
        'pacing_guidance': f"Standard {bullets}-bullet structure with equal time allocation",
        'reasoning': f"Fallback strategy: {target_duration}s duration → {bullets} bullets (deterministic rule)",
        'adequacy_score': adequacy_score,
        '_fallback': True  # Flag per analytics
    }


# Example usage
if __name__ == '__main__':
    # Mock LLM function
    def mock_llm(role, task, context, style_hints=None):
        return '''{
            "recommended_bullets": 5,
            "time_per_bullet": [60, 90, 100, 80, 70],
            "depth_scores": [0.6, 0.8, 0.9, 0.7, 0.6],
            "pacing_guidance": "Start with quick context, peak at bullet 3",
            "reasoning": "Topic sustains 5 bullets with 480s duration.",
            "adequacy_score": 0.85
        }'''

    # Test
    strategy = analyze_content_depth(
        topic="How to master Python programming in 2025",
        target_duration=480,
        narrative_arc={'narrative_structure': [{'act': 1}, {'act': 2}, {'act': 3}, {'act': 4}]},
        editorial_decision={'format': 'tutorial', 'angle': 'educational'},
        workspace={'vertical_id': 'tech_ai'},
        llm_generate_fn=mock_llm
    )

    print(f"\n✓ Strategy: {strategy['recommended_bullets']} bullets")
    print(f"  Time: {strategy['time_per_bullet']}")
    print(f"  Adequacy: {strategy['adequacy_score']:.2f}")
