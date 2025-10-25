"""
QualityReviewer Agent: Final quality control and compliance verification.

This agent performs comprehensive review of the complete video package
before production, ensuring brand safety, compliance, and quality standards.

==============================================================================
LLM Integration Strategy (Step 06-pre)
==============================================================================

CURRENT: Rule-based compliance checks (8-point checklist)
FUTURE: LLM-enhanced content analysis via services/llm_router

INTEGRATION APPROACH:
- Pipeline can use llm_router for nuanced content review
- LLM analyzes tone, potential issues, edge cases
- Agent combines deterministic checks + LLM insights
- Final approval remains with agent logic (brand safety)

Example:
    content_review = generate_text(
        role="quality_reviewer",
        task="Analyze content for brand safety and compliance issues",
        context=f"Script: {script.full_voiceover_text}, Title: {publishing.final_title}",
        style_hints={"banned_topics": banned_topics, "brand_tone": brand_tone}
    )
    # Agent uses LLM feedback to enhance its deterministic checks

==============================================================================
"""

from typing import Dict, Tuple, List
from yt_autopilot.core.schemas import VideoPlan, VideoScript, VisualPlan, PublishingPackage
from yt_autopilot.core.memory_store import get_banned_topics, get_brand_tone
from yt_autopilot.core.logger import logger


def _check_banned_topics(
    plan: VideoPlan,
    script: VideoScript,
    publishing: PublishingPackage,
    banned_topics: List[str]
) -> Tuple[bool, str]:
    """
    Checks for presence of banned topics in content.

    Args:
        plan: Video plan
        script: Video script
        publishing: Publishing package
        banned_topics: List of banned topic strings

    Returns:
        (is_compliant, issue_description)
    """
    # Combine all text content to check
    all_text = " ".join([
        plan.working_title,
        plan.strategic_angle,
        script.hook,
        " ".join(script.bullets),
        script.outro_cta,
        publishing.final_title,
        publishing.description
    ]).lower()

    # Check each banned topic
    for banned in banned_topics:
        banned_lower = banned.lower()
        if banned_lower in all_text:
            return False, f"Content contains banned topic: '{banned}'"

    return True, ""


def _check_hate_speech_indicators(text: str) -> Tuple[bool, str]:
    """
    Checks for hate speech indicators.

    Args:
        text: Combined text to check

    Returns:
        (is_clean, issue_description)
    """
    # Simple keyword-based check (in production, use ML model)
    hate_indicators = [
        "odio", "hate", "razzist", "racist", "sessist", "sexist",
        "disgust", "schifo", "morte a", "death to",
        # Add more patterns as needed
    ]

    text_lower = text.lower()
    for indicator in hate_indicators:
        if indicator in text_lower:
            return False, f"Potential hate speech detected: contains '{indicator}'"

    return True, ""


def _check_medical_claims(text: str) -> Tuple[bool, str]:
    """
    Checks for prohibited medical claims.

    Args:
        text: Combined text to check

    Returns:
        (is_compliant, issue_description)
    """
    # Check for guaranteed cure claims
    prohibited_patterns = [
        "cura garantita", "guaranteed cure", "guarigione certa",
        "miracol", "miracle cure", "elimina per sempre",
        "cure permanently", "never return", "100% efficace"
    ]

    text_lower = text.lower()
    for pattern in prohibited_patterns:
        if pattern in text_lower:
            return False, f"Prohibited medical claim detected: '{pattern}'"

    return True, ""


def _check_copyright_violations(text: str) -> Tuple[bool, str]:
    """
    Checks for explicit copyrighted content references.

    Args:
        text: Combined text to check

    Returns:
        (is_compliant, issue_description)
    """
    # Check for explicit music/content usage instructions
    copyright_patterns = [
        "usa la musica di", "use music by", "soundtrack from",
        "play the song", "metti la canzone", "copyright music"
    ]

    text_lower = text.lower()
    for pattern in copyright_patterns:
        if pattern in text_lower:
            return False, f"Potential copyright violation: references '{pattern}'"

    return True, ""


def _check_brand_tone_compliance(script: VideoScript, brand_tone: str) -> Tuple[bool, str]:
    """
    Checks if script respects brand tone guidelines.

    Args:
        script: Video script
        brand_tone: Expected brand tone from memory

    Returns:
        (is_compliant, issue_description)
    """
    # Check for vulgarity (brand tone should be clean)
    if "volgarità" in brand_tone.lower() or "niente volgarità" in brand_tone.lower():
        vulgar_words = [
            "cazzo", "merda", "fuck", "shit", "damn",
            # Add more as needed
        ]

        full_text = script.full_voiceover_text.lower()
        for vulgar in vulgar_words:
            if vulgar in full_text:
                return False, f"Script contains vulgar language: '{vulgar}'"

    # Check for positive/direct tone
    if "positivo" in brand_tone.lower() or "diretto" in brand_tone.lower():
        # Hook should be clear and engaging
        if len(script.hook) < 10:
            return False, "Hook too short - not engaging enough for brand standards"

    return True, ""


def _check_hook_quality(script: VideoScript) -> Tuple[bool, str]:
    """
    Checks if hook is strong enough to capture attention.

    Args:
        script: Video script

    Returns:
        (is_good, issue_description)
    """
    hook = script.hook

    # Hook should not be empty or too short
    if len(hook) < 15:
        return False, "Hook too short (< 15 chars) - won't capture attention in first 3 seconds"

    # Hook should not be too long
    if len(hook) > 200:
        return False, "Hook too long (> 200 chars) - will lose viewer attention"

    # Hook should have some punctuation (indicates structure)
    if not any(p in hook for p in ['.', '!', '?', ',']):
        return False, "Hook lacks punctuation - may not be well-structured"

    return True, ""


def _check_video_duration(visuals: VisualPlan, max_duration: int = 90) -> Tuple[bool, str]:
    """
    Checks if total video duration is appropriate for Shorts.

    Args:
        visuals: Visual plan with scenes
        max_duration: Maximum acceptable duration in seconds (default: 90)

    Returns:
        (is_acceptable, issue_description)
    """
    total_duration = sum(scene.est_duration_seconds for scene in visuals.scenes)

    if total_duration > max_duration:
        return False, (
            f"Video too long: {total_duration}s exceeds {max_duration}s limit for Shorts. "
            "Script needs to be condensed."
        )

    if total_duration < 10:
        return False, (
            f"Video too short: {total_duration}s is less than 10s. "
            "Needs more content to be valuable."
        )

    return True, ""


def _check_title_quality(publishing: PublishingPackage) -> Tuple[bool, str]:
    """
    Checks if title meets quality standards.

    Args:
        publishing: Publishing package with title

    Returns:
        (is_good, issue_description)
    """
    title = publishing.final_title

    # Check length (YouTube limit is 100 chars)
    if len(title) > 100:
        return False, f"Title too long: {len(title)} chars exceeds YouTube's 100 char limit"

    # Title should not be too short
    if len(title) < 10:
        return False, "Title too short - won't provide enough context in search results"

    # Check for clickbait spam patterns (ALL CAPS, excessive punctuation)
    if title.isupper():
        return False, "Title is ALL CAPS - appears spammy"

    if title.count('!') > 2 or title.count('?') > 2:
        return False, "Title has excessive punctuation - appears spammy"

    return True, ""


def review(
    plan: VideoPlan,
    script: VideoScript,
    visuals: VisualPlan,
    publishing: PublishingPackage,
    memory: Dict
) -> Tuple[bool, str]:
    """
    Performs comprehensive quality review of complete video package.

    This is the entry point for the QualityReviewer agent. It's the final
    gatekeeper before production, checking:
    - Brand safety (no banned topics, hate speech, prohibited claims)
    - Compliance (medical, copyright, legal)
    - Brand tone consistency
    - Content quality (hook strength, title quality, duration)
    - YouTube platform guidelines

    Args:
        plan: Video plan
        script: Video script
        visuals: Visual plan
        publishing: Publishing package
        memory: Channel memory dict with brand rules

    Returns:
        Tuple of (approved: bool, message: str)
        - If approved: (True, "OK")
        - If rejected: (False, "Detailed explanation of issues")
    """
    logger.info(f"QualityReviewer checking: '{plan.working_title}'")

    # Load memory constraints
    banned_topics = get_banned_topics(memory)
    brand_tone = get_brand_tone(memory)

    # Combine all text for comprehensive checks
    all_text = " ".join([
        plan.working_title,
        plan.strategic_angle,
        script.full_voiceover_text,
        publishing.final_title,
        publishing.description
    ])

    # Run all checks
    checks = [
        ("Banned Topics", lambda: _check_banned_topics(plan, script, publishing, banned_topics)),
        ("Hate Speech", lambda: _check_hate_speech_indicators(all_text)),
        ("Medical Claims", lambda: _check_medical_claims(all_text)),
        ("Copyright", lambda: _check_copyright_violations(all_text)),
        ("Brand Tone", lambda: _check_brand_tone_compliance(script, brand_tone)),
        ("Hook Quality", lambda: _check_hook_quality(script)),
        ("Video Duration", lambda: _check_video_duration(visuals)),
        ("Title Quality", lambda: _check_title_quality(publishing)),
    ]

    # Execute checks
    issues = []
    for check_name, check_func in checks:
        is_passed, issue_msg = check_func()
        if not is_passed:
            logger.warning(f"QualityReviewer: {check_name} check FAILED - {issue_msg}")
            issues.append(f"[{check_name}] {issue_msg}")
        else:
            logger.debug(f"QualityReviewer: {check_name} check PASSED")

    # Determine final verdict
    if issues:
        rejection_message = (
            f"Video package REJECTED. Found {len(issues)} issue(s):\n"
            + "\n".join(f"• {issue}" for issue in issues)
            + "\n\nPlease revise and resubmit."
        )
        logger.error(f"QualityReviewer REJECTED: '{plan.working_title}'")
        return False, rejection_message

    logger.info(f"QualityReviewer APPROVED: '{plan.working_title}' - All checks passed")
    return True, "OK"
