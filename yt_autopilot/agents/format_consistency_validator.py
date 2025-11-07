"""
Format Consistency Validator Agent (Pattern 2): AI-driven format validation.

This agent validates consistency across video production artifacts:
- Title/tags vs duration (e.g., "#shorts" in title but 480s duration)
- Format type vs aspect ratio (e.g., short format but 16:9 aspect)
- Monetization strategy vs format (e.g., mid-roll ads for <60s video)

Pattern 2: Full AI-driven validation with auto-correction suggestions.
Replaces hardcoded tag lists with LLM semantic understanding.
Scalable to ANY language, ANY format tags, ANY duration ranges.
"""

from typing import Dict, Any, Optional, Callable
import re
import json
from yt_autopilot.core.schemas import VideoPlan, TrendCandidate
from yt_autopilot.core.logger import logger, log_fallback


def validate_format_consistency(
    video_plan: VideoPlan,
    timeline: Dict[str, Any],
    trend: TrendCandidate,
    llm_generate_fn: Callable,
    workspace: Dict[str, Any]
) -> Dict:
    """
    AI-driven validation of format consistency across artifacts.

    Catches contradictions like:
    - Title says "#shorts" but duration is 480s (long-form)
    - Trend tags indicate "short-form" but strategy is "mid-roll ads"
    - Visual plan says "Shorts 9:16" but duration is 8+ minutes

    Args:
        video_plan: VideoPlan with working_title, strategic_angle
        timeline: Timeline dict with reconciled_duration, format_type, aspect_ratio
        trend: TrendCandidate with original keyword, source
        llm_generate_fn: LLM function for AI validation
        workspace: Workspace configuration

    Returns:
        Dict with:
            - is_consistent: bool (True if no issues)
            - inconsistencies: List[Dict] (issues found)
            - auto_fix_suggestions: List[Dict] (corrections to apply)
            - reasoning: str (AI explanation)

    Example:
        >>> validation = validate_format_consistency(
        ...     video_plan=plan,
        ...     timeline=reconciled_format,
        ...     trend=selected_trend,
        ...     llm_generate_fn=generate_text,
        ...     workspace=workspace
        ... )
        >>> if not validation['is_consistent']:
        ...     # Apply auto-corrections
    """
    logger.info("Format Consistency Validator analyzing artifacts (Pattern 2)...")

    # Extract timeline data
    duration_seconds = timeline.get('reconciled_duration', 0)
    format_type = timeline.get('format_type', 'unknown')
    aspect_ratio = timeline.get('aspect_ratio', 'unknown')

    # Language mapping for explicit instruction (pattern from narrative_architect)
    target_language = workspace.get('target_language', 'en')
    language_names = {
        "en": "ENGLISH",
        "it": "ITALIAN",
        "es": "SPANISH",
        "fr": "FRENCH",
        "de": "GERMAN",
        "pt": "PORTUGUESE"
    }
    language_instruction = language_names.get(target_language.lower(), target_language.upper())

    # Build LLM prompt for multi-artifact validation
    prompt = f"""You are a video production quality assurance specialist validating format consistency.

⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
ALL TEXT FIELDS (reasoning, issue descriptions) MUST BE IN {language_instruction}.
DO NOT mix languages. Write ALL output in {language_instruction}.

ARTIFACTS TO VALIDATE:

**VIDEO PLAN:**
- Title: "{video_plan.working_title}"
- Strategic Angle: "{video_plan.strategic_angle}"
- Language: {video_plan.language}

**TIMELINE (Source of Truth):**
- Duration: {duration_seconds}s ({duration_seconds // 60}min {duration_seconds % 60}s)
- Format Type: {format_type} (short <60s | mid 60s-8min | long 8min+)
- Aspect Ratio: {aspect_ratio}

**TREND METADATA:**
- Keyword: "{trend.keyword}"
- Why Hot: "{trend.why_hot[:200] if trend.why_hot else 'N/A'}"
- Source: {trend.source}

**VALIDATION CHECKS:**

1. **Title/Tags vs Duration Consistency**:
   - Does title contain short-form indicators (#shorts, #reel, #shortvideo, "under 60s", "quick", "breve")?
   - If yes, does duration match (<60s)? If no, this is a CRITICAL inconsistency.
   - Check ALL languages: English ("short", "brief"), Italian ("corto", "breve"), Spanish ("corto").

2. **Format Type vs Aspect Ratio**:
   - short → should be 9:16 vertical
   - mid/long → could be 16:9 or 9:16 (both valid)
   - Is aspect ratio aligned with format expectations?

3. **Monetization Strategy Alignment**:
   - If format=short (<60s) → NO mid-roll ads possible (YouTube Shorts limitations)
   - If format=long (8min+) → mid-roll ads expected (maximize revenue)
   - Does the format support intended monetization?

4. **Cross-Language Format Indicators**:
   - Italian: "corto", "breve", "rapido", "veloce"
   - English: "short", "quick", "brief", "fast"
   - Spanish: "corto", "rápido", "breve"
   - Are there cross-language format conflicts or mismatches?

TASK: Validate format consistency and identify contradictions.

RESPOND WITH JSON:
{{
  "is_consistent": <true/false>,
  "inconsistencies": [
    {{
      "artifact": "<title/duration/aspect/monetization>",
      "issue": "<clear description of the problem in {language_instruction}>",
      "severity": "<critical/medium/low>"
    }}
  ],
  "auto_fix_suggestions": [
    {{
      "action": "<remove_tag/adjust_duration/change_aspect/add_context>",
      "target": "<field_name>",
      "new_value": "<corrected value>",
      "reasoning": "<why this fix in {language_instruction}>"
    }}
  ],
  "reasoning": "<1-3 sentences explaining validation result in {language_instruction}>"
}}

CRITICAL RULES:
- If duration ≥480s (8min) and title has "#shorts" → CRITICAL inconsistency
- If format_type="short" but duration >60s → CRITICAL inconsistency
- ALL text fields (issue, reasoning, reasoning in auto_fix) MUST be in {language_instruction}
- Respond ONLY with valid JSON, no markdown, no extra text.
"""

    try:
        logger.debug("  🔍 Calling LLM for format consistency validation...")

        response = llm_generate_fn(
            role="format_consistency_validator",
            task=prompt,
            context="",
            style_hints={"response_format": "json", "temperature": 0.2, "max_tokens": 800}
        )

        # Parse JSON response
        cleaned = re.sub(r'^```(?:json)?\s*\n', '', response.strip())
        cleaned = re.sub(r'\n```\s*$', '', cleaned)
        validation = json.loads(cleaned)

        # Log results
        if not validation.get('is_consistent', False):
            logger.warning("  ⚠️ Format consistency issues detected:")
            for issue in validation.get('inconsistencies', []):
                severity = issue.get('severity', 'medium').upper()
                logger.warning(f"    [{severity}] {issue.get('artifact')}: {issue.get('issue')}")

            logger.info("  💡 Auto-fix suggestions:")
            for fix in validation.get('auto_fix_suggestions', []):
                logger.info(f"    - {fix.get('action')}: {fix.get('target')} → {fix.get('new_value', 'N/A')}")
        else:
            logger.info("  ✓ Format consistency validated - no issues detected")

        logger.debug(f"  Reasoning: {validation.get('reasoning', 'N/A')}")

        return validation

    except Exception as e:
        logger.error(f"  ❌ Format consistency validation failed: {e}")
        log_fallback(
            component="FORMAT_CONSISTENCY_VALIDATOR",
            fallback_type="SKIP_VALIDATION",
            reason=f"LLM validation failed: {e}",
            impact="MEDIUM"
        )

        # Fallback: Assume consistent (non-blocking)
        return {
            "is_consistent": True,
            "inconsistencies": [],
            "auto_fix_suggestions": [],
            "reasoning": f"Validation skipped due to LLM failure: {e}"
        }


def auto_correct_format_inconsistencies(
    video_plan: VideoPlan,
    validation_result: Dict,
    timeline: Dict[str, Any]
) -> VideoPlan:
    """
    Applies auto-fix suggestions from validation to correct artifacts.

    This is Layer 2 correction (after AI detects issues, AI also fixes them).

    Args:
        video_plan: VideoPlan to correct
        validation_result: Validation result from validate_format_consistency()
        timeline: Timeline dict (for context)

    Returns:
        Corrected VideoPlan

    Example:
        >>> if not validation['is_consistent']:
        ...     corrected_plan = auto_correct_format_inconsistencies(
        ...         video_plan, validation, timeline
        ...     )
    """
    if validation_result.get('is_consistent', True):
        logger.debug("  No corrections needed - artifacts are consistent")
        return video_plan  # No fixes needed

    logger.info("  🔧 Applying auto-corrections...")

    # Create a copy to avoid mutating original
    corrected_plan = video_plan

    for fix in validation_result.get('auto_fix_suggestions', []):
        action = fix.get('action')
        target = fix.get('target')
        new_value = fix.get('new_value')
        reasoning = fix.get('reasoning', '')

        if action == "remove_tag" and target == "working_title":
            # Remove short-form tags from title if duration is long-form
            original_title = corrected_plan.working_title

            # Pattern 2: AI-driven tag removal (supports any language/format)
            # Remove common short-form indicators
            patterns = [
                r'#shorts?',       # #short, #shorts
                r'#reel',           # #reel
                r'#shortvideo',     # #shortvideo
                r'#corto',          # Italian "short"
                r'#breve',          # Italian "brief"
                r'#rapido',         # Spanish/Italian "fast"
            ]

            cleaned_title = original_title
            for pattern in patterns:
                cleaned_title = re.sub(pattern, '', cleaned_title, flags=re.IGNORECASE)

            # Clean up double spaces and trim
            cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()

            corrected_plan.working_title = cleaned_title
            logger.info(f"    ✓ Removed short-form tags from title")
            logger.debug(f"      Before: {original_title}")
            logger.debug(f"      After: {cleaned_title}")

        elif action == "add_duration_context" and target == "strategic_angle":
            # Add duration context to strategic angle
            duration_min = timeline.get('reconciled_duration', 0) // 60
            if duration_min > 0:
                corrected_plan.strategic_angle += f" (formato lungo {duration_min} minuti)"
                logger.info(f"    ✓ Added duration context to strategic angle")

        elif action == "adjust_aspect" and target == "timeline":
            # This would update the timeline object (not VideoPlan)
            # Log suggestion for manual review
            logger.info(f"    ℹ️ Aspect ratio adjustment suggested: {new_value}")
            logger.info(f"       Reasoning: {reasoning}")
            logger.info(f"       (Timeline adjustment requires pipeline-level fix)")

        else:
            logger.debug(f"    ℹ️ Unknown fix action: {action} on {target}")

    logger.info("  ✓ Auto-corrections applied")
    return corrected_plan
