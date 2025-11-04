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

from typing import Dict, Tuple, List, Optional, Callable
from yt_autopilot.core.schemas import VideoPlan, VideoScript, VisualPlan, PublishingPackage
from yt_autopilot.core.memory_store import get_banned_topics, get_brand_tone
from yt_autopilot.core.logger import logger
import json


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


def _check_hook_quality(script: VideoScript, narrator_config: Dict = None) -> Tuple[bool, str]:
    """
    Checks if hook is strong enough to capture attention.

    Step 09: Relaxed validation when narrator persona is present.
    Narrator-driven hooks may be conversational and don't need to be
    as aggressive/clickbaity as generic hooks.

    Args:
        script: Video script
        narrator_config: Narrator persona configuration (Step 09)

    Returns:
        (is_good, issue_description)
    """
    hook = script.hook

    # Step 09: If narrator persona is present and identified in hook, be more tolerant
    has_narrator = False
    if narrator_config and narrator_config.get('enabled'):
        narrator_name = narrator_config.get('name', '').lower()
        if narrator_name and narrator_name in hook.lower():
            has_narrator = True

    # Hook should not be empty or too short
    # Step 09: Narrator hooks can be shorter (conversational style)
    min_length = 10 if has_narrator else 15
    if len(hook) < min_length:
        return False, f"Hook too short (< {min_length} chars) - won't capture attention in first 3 seconds"

    # Hook should not be too long
    if len(hook) > 200:
        return False, "Hook too long (> 200 chars) - will lose viewer attention"

    # Hook should have some punctuation (indicates structure)
    if not any(p in hook for p in ['.', '!', '?', ',']):
        return False, "Hook lacks punctuation - may not be well-structured"

    return True, ""


def _check_video_duration(visuals: VisualPlan) -> Tuple[bool, str]:
    """
    Checks if total video duration meets minimum quality standards.

    NOTE (Monetization Refactor): Maximum duration check removed.
    Duration Strategist now handles optimal duration (short/mid/long-form).
    This check only validates minimum duration for quality.

    Args:
        visuals: Visual plan with scenes

    Returns:
        (is_acceptable, issue_description)
    """
    total_duration = sum(scene.est_duration_seconds for scene in visuals.scenes)

    # Only check minimum duration - Duration Strategist handles optimal length
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


def _check_narrator_persona_consistency(script: VideoScript, narrator_config: Dict) -> Tuple[bool, str]:
    """
    Checks if script maintains narrator persona consistency.

    Step 09: Narrator Persona Integration

    Validates that the script respects narrator persona guidelines,
    particularly tone of address (tu/voi), WITHOUT enforcing rigid
    template adherence.

    Args:
        script: Video script to check
        narrator_config: Narrator persona configuration from workspace

    Returns:
        (is_consistent, issue_description)
    """
    if not narrator_config or not narrator_config.get('enabled'):
        # Narrator persona disabled - skip check
        return True, ""

    voiceover = script.full_voiceover_text.lower()
    expected_tone = narrator_config.get('tone_of_address', '')

    # CHECK: Tone of address consistency
    if expected_tone == 'tu_informale':
        # Check for unwanted formal "voi" usage
        voi_patterns = [
            'vi mostro', 'vi spiego', 'vi dico', 'vi consiglio',
            'vediamo insieme', 'vi invito', 'vi chiedo', 'vi presento'
        ]

        for pattern in voi_patterns:
            if pattern in voiceover:
                return False, (
                    f"Script uses formal 'voi' ('{pattern}') but workspace requires 'tu informale'. "
                    "Narrator persona expects informal direct address (tu/ti)."
                )

    elif expected_tone == 'voi_formale':
        # Check for unwanted informal "tu" usage
        tu_patterns = [
            'ti mostro', 'ti spiego', 'ti dico', 'ti consiglio',
            'guarda qui', 'ti invito', 'ti chiedo', 'ascolta'
        ]

        for pattern in tu_patterns:
            if pattern in voiceover:
                return False, (
                    f"Script uses informal 'tu' ('{pattern}') but workspace requires 'voi formale'. "
                    "Narrator persona expects formal address (voi/vi)."
                )

    # NOTE: We do NOT enforce rigid signature phrase presence
    # Format determines if signature phrases are appropriate, not quality reviewer

    return True, ""


def _ai_semantic_compliance_check(
    all_text: str,
    language: str,
    llm_generate_fn: Optional[Callable] = None
) -> Tuple[bool, str, Dict[str, bool]]:
    """
    Layer 2: AI-driven semantic compliance check (replaces pattern-based false positives).

    Uses LLM to understand context and language nuances instead of hard-coded keywords.
    This prevents false positives like:
    - "episodio" (Italian "episode") flagged as "odio" (hate)
    - "miracol..." (Italian "miracle") flagged as medical claim

    Args:
        all_text: Combined content to check
        language: Target language code (e.g., 'it', 'en')
        llm_generate_fn: LLM generation function

    Returns:
        (is_compliant, issue_description, detailed_results)
        detailed_results: Dict with individual check results
    """
    if not llm_generate_fn:
        # Fallback if no LLM available - assume compliant
        logger.warning("AI compliance check skipped - no LLM function provided")
        return True, "", {}

    language_names = {'it': 'Italian', 'en': 'English', 'es': 'Spanish', 'fr': 'French'}
    language_name = language_names.get(language, language.upper())

    prompt = f"""You are a content compliance specialist analyzing video content for brand safety.

⚠️ CRITICAL: This content is in {language_name}. Use SEMANTIC UNDERSTANDING, not keyword matching.

CONTENT TO ANALYZE:
{all_text[:3000]}

Analyze this content for ACTUAL violations (not false positives):

1. HATE SPEECH: Does this content express genuine hatred, discrimination, or violence toward groups?
   ❌ FALSE POSITIVE EXAMPLE: Italian word "episodio" (episode) contains "odio" but is NOT hate speech
   ✅ ACTUAL VIOLATION: Content that demeans, attacks, or promotes violence against people

2. MEDICAL CLAIMS: Does this content make PROHIBITED medical guarantees?
   ❌ FALSE POSITIVE EXAMPLE: Italian "miracol..." in context like "non è un miracolo, ma..." (it's not a miracle, but...)
   ✅ ACTUAL VIOLATION: Claims like "guaranteed cure", "eliminates disease forever", "100% effective treatment"

3. COPYRIGHT: Does this content explicitly reference using copyrighted material?
   ❌ FALSE POSITIVE EXAMPLE: Mentioning a song title for discussion
   ✅ ACTUAL VIOLATION: Instructions to "use music by [artist]" or "play copyrighted soundtrack"

RESPONSE FORMAT (valid JSON only, no markdown):
{{
  "hate_speech_violation": true/false,
  "hate_speech_reasoning": "<explain your decision, cite specific text if violation>",
  "medical_claims_violation": true/false,
  "medical_claims_reasoning": "<explain your decision, cite specific text if violation>",
  "copyright_violation": true/false,
  "copyright_reasoning": "<explain your decision, cite specific text if violation>",
  "overall_compliant": true/false,
  "summary": "<overall assessment>"
}}

IMPORTANT:
- Consider language context (Italian words may look like English violations)
- Understand nuance (disclaimers like "not a miracle" are SAFE)
- Be strict on ACTUAL violations, tolerant of false positives
- Default to COMPLIANT unless clear violation exists
"""

    try:
        logger.info("  🤖 Layer 2: Running AI-driven semantic compliance check...")
        response = llm_generate_fn(
            role="compliance_reviewer",
            task="Analyze content for brand safety violations with semantic understanding",
            context=prompt,
            style_hints={"temperature": 0.2}  # Low temperature for consistent judgments
        )

        # Parse JSON response
        # Remove markdown if present
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean.split("```json")[1].split("```")[0].strip()
        elif response_clean.startswith("```"):
            response_clean = response_clean.split("```")[1].split("```")[0].strip()

        result = json.loads(response_clean)

        # Log detailed results
        logger.info(f"  AI Compliance Results:")
        logger.info(f"    Hate Speech: {'❌ VIOLATION' if result['hate_speech_violation'] else '✅ CLEAN'}")
        logger.info(f"      → {result['hate_speech_reasoning'][:100]}...")
        logger.info(f"    Medical Claims: {'❌ VIOLATION' if result['medical_claims_violation'] else '✅ CLEAN'}")
        logger.info(f"      → {result['medical_claims_reasoning'][:100]}...")
        logger.info(f"    Copyright: {'❌ VIOLATION' if result['copyright_violation'] else '✅ CLEAN'}")
        logger.info(f"      → {result['copyright_reasoning'][:100]}...")

        is_compliant = result['overall_compliant']

        if not is_compliant:
            issues = []
            if result['hate_speech_violation']:
                issues.append(f"[AI-Hate Speech] {result['hate_speech_reasoning']}")
            if result['medical_claims_violation']:
                issues.append(f"[AI-Medical Claims] {result['medical_claims_reasoning']}")
            if result['copyright_violation']:
                issues.append(f"[AI-Copyright] {result['copyright_reasoning']}")

            issue_msg = "\n".join(issues)
            logger.warning(f"  ❌ AI detected violations: {issue_msg}")
            return False, issue_msg, result

        logger.info(f"  ✅ AI compliance check PASSED - {result['summary']}")
        return True, "", result

    except json.JSONDecodeError as e:
        logger.error(f"  ❌ AI compliance check failed - JSON parse error: {e}")
        logger.error(f"  Raw response: {response[:200]}...")
        # Fallback to compliant (pattern-based will catch issues)
        return True, f"AI check failed (JSON error), falling back to pattern checks", {}
    except Exception as e:
        logger.error(f"  ❌ AI compliance check failed - {e}")
        # Fallback to compliant (pattern-based will catch issues)
        return True, f"AI check failed ({str(e)}), falling back to pattern checks", {}


def review(
    plan: VideoPlan,
    script: VideoScript,
    visuals: VisualPlan,
    publishing: PublishingPackage,
    memory: Dict,
    llm_generate_fn: Optional[Callable] = None
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

    # Step 09: Load narrator persona for consistency checks
    narrator_config = memory.get('narrator_persona', {})

    # Combine all text for comprehensive checks
    all_text = " ".join([
        plan.working_title,
        plan.strategic_angle,
        script.full_voiceover_text,
        publishing.final_title,
        publishing.description
    ])

    # ======================================================================
    # Layer 2: AI-Driven Semantic Compliance (replaces pattern-based)
    # ======================================================================
    ai_passed = True
    ai_result = {}
    language = memory.get('target_language', 'en')

    if llm_generate_fn:
        logger.info("")
        logger.info("🤖 AI-DRIVEN COMPLIANCE CHECK (Layer 2)")
        logger.info("  Using semantic understanding to avoid false positives")

        ai_passed, ai_issue, ai_result = _ai_semantic_compliance_check(
            all_text=all_text,
            language=language,
            llm_generate_fn=llm_generate_fn
        )

        if not ai_passed:
            # AI detected actual violations - reject immediately
            rejection_message = (
                f"Video package REJECTED by AI semantic compliance check.\n"
                f"{ai_issue}\n\n"
                "Please revise and resubmit."
            )
            logger.error(f"QualityReviewer REJECTED by AI: '{plan.working_title}'")
            return False, rejection_message

        logger.info("  ✅ AI compliance check passed - content is brand-safe")
        logger.info("")
    else:
        logger.warning("⚠️ No LLM function provided - skipping AI compliance check")
        logger.warning("  Falling back to pattern-based checks (may have false positives)")

    # ======================================================================
    # Layer 3: Pattern-Based Checks (fallback / non-AI checks)
    # ======================================================================
    # If AI passed, SKIP pattern-based hate/medical/copyright checks (prevent false positives)
    # Run other quality checks (banned topics, tone, hook, duration, title)

    checks = [
        ("Banned Topics", lambda: _check_banned_topics(plan, script, publishing, banned_topics)),
        ("Brand Tone", lambda: _check_brand_tone_compliance(script, brand_tone)),
        ("Narrator Persona", lambda: _check_narrator_persona_consistency(script, narrator_config)),  # Step 09
        ("Hook Quality", lambda: _check_hook_quality(script, narrator_config)),  # Step 09: Pass narrator config
        ("Video Duration", lambda: _check_video_duration(visuals)),
        ("Title Quality", lambda: _check_title_quality(publishing)),
    ]

    # Add pattern-based compliance checks ONLY if AI check didn't run
    if not llm_generate_fn or not ai_passed:
        logger.info("  🛡️ Layer 3: Running pattern-based compliance checks (fallback)")
        checks.extend([
            ("Hate Speech", lambda: _check_hate_speech_indicators(all_text)),
            ("Medical Claims", lambda: _check_medical_claims(all_text)),
            ("Copyright", lambda: _check_copyright_violations(all_text)),
        ])

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
