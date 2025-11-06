"""
ScriptWriter Agent: Generates engaging video scripts from video plans.

This agent transforms strategic video plans into complete scripts with
hooks, content bullets, CTAs, and full voiceover text.

==============================================================================
LLM Integration Strategy (Step 06-pre)
==============================================================================

CURRENT: Deterministic script generation (local logic)
FUTURE: LLM-powered creative writing via services/llm_router

INTEGRATION APPROACH:
- Pipeline (build_video_package.py) calls llm_router.generate_text()
- LLM generates hook, bullets, CTA based on video plan
- Pipeline passes LLM output to this agent as enriched input
- Agent validates/refines LLM output using deterministic rules
- Maintains architecture: agents do NOT import from services/

Example enhancement:
    llm_script = generate_text(
        role="script_writer",
        task="Write viral hook and bullets for YouTube Short",
        context=f"Topic: {plan.working_title}, Target: {plan.target_cta}",
        style_hints={"brand_tone": memory["brand_tone"]}
    )
    # Pass llm_script to agent for validation and formatting

==============================================================================
Step 07.5: Format Engine Integration
==============================================================================

NEW: Segment-aware script generation
- Accepts SeriesFormat template for structured scriptwriting
- Tags bullets and scenes with segment_type from template
- Maintains backward compatibility (series_format=None → legacy mode)

==============================================================================
"""

from typing import Dict, List, Optional
from yt_autopilot.core.schemas import VideoPlan, VideoScript, SceneVoiceover, SeriesFormat, EditorialDecision
from yt_autopilot.core.memory_store import get_brand_tone
from yt_autopilot.core.logger import logger, log_fallback


def _strip_quotes(text: str) -> str:
    """
    Remove surrounding double quotes from parsed LLM text.

    Step 09: LLMs often wrap content in quotes. This function removes
    only the outer quotes while preserving internal quotes.

    Examples:
        '"Hello, world!"' -> 'Hello, world!'
        '"He said "hi"' -> 'He said "hi"'
        'No quotes here' -> 'No quotes here'

    Args:
        text: Text potentially wrapped in quotes

    Returns:
        Text with outer quotes removed
    """
    text = text.strip()

    # Remove outer quotes if both present
    if text.startswith('"') and text.endswith('"') and len(text) > 2:
        return text[1:-1].strip()

    return text


def _truncate_hook_deterministic(hook: str, max_chars: int = 200) -> str:
    """
    Layer 3: Deterministic hook truncation if AI fails.

    Truncates hook to max_chars while trying to preserve sentence boundaries.
    This is a last-resort fallback when Layer 2 (LLM shortening) fails.

    Args:
        hook: Original hook text
        max_chars: Maximum allowed characters (default 200)

    Returns:
        Truncated hook text (max max_chars)
    """
    if len(hook) <= max_chars:
        return hook

    logger.warning(f"  ⚠️ Hook exceeds {max_chars} chars ({len(hook)} chars), applying Layer 3 truncation...")

    # Try to truncate at sentence boundary
    truncated = hook[:max_chars-3]  # Reserve 3 chars for "..."

    # Find last sentence-ending punctuation
    last_period = truncated.rfind('.')
    last_exclaim = truncated.rfind('!')
    last_question = truncated.rfind('?')

    boundary = max(last_period, last_exclaim, last_question)

    # Only use boundary if it's >70% of max length (avoid cutting too early)
    if boundary > max_chars * 0.7:
        result = hook[:boundary+1]
        logger.info(f"  ✓ Layer 3: Truncated at sentence boundary ({len(result)} chars)")
        return result

    # No good boundary, hard truncate with ellipsis
    result = truncated + "..."
    logger.info(f"  ✓ Layer 3: Hard truncated with ellipsis ({len(result)} chars)")
    return result


def _fix_overlength_hook_with_llm(
    hook: str,
    plan: VideoPlan,
    llm_generate_fn: Optional[callable] = None
) -> str:
    """
    Layer 2: AI-driven hook shortening.

    If hook >200 chars, calls LLM to condense while preserving impact.
    Falls back to Layer 3 (deterministic truncation) if LLM unavailable.

    Args:
        hook: Original hook text (potentially over 200 chars)
        plan: Video plan for context
        llm_generate_fn: Optional LLM function for AI shortening

    Returns:
        Shortened hook (≤200 chars) or original if already short enough
    """
    if len(hook) <= 200:
        return hook

    logger.warning(f"  ⚠️ Hook exceeds 200 chars ({len(hook)} chars), triggering Layer 2 AI shortening...")

    # If LLM not available, fall to Layer 3
    if not llm_generate_fn:
        logger.warning("  ⚠️ Layer 2: No LLM available, falling to Layer 3 truncation")
        return _truncate_hook_deterministic(hook, max_chars=200)

    try:
        prompt = f"""You are a copywriting expert specializing in viral video hooks.

TASK: Shorten this hook to ≤200 characters while preserving maximum impact.

ORIGINAL HOOK ({len(hook)} characters):
"{hook}"

VIDEO TOPIC: {plan.working_title}
TARGET AUDIENCE: {plan.target_audience if hasattr(plan, 'target_audience') else 'General'}

REQUIREMENTS:
1. Maximum 200 characters (including spaces, punctuation, emojis)
2. Preserve the core emotional trigger (shock, curiosity, relatability)
3. Keep the pattern interrupt or open loop if present
4. Maintain urgency and impact
5. Remove filler words but don't sacrifice clarity
6. Optimize for mobile display (short, punchy)

TECHNIQUES TO USE:
- Replace long phrases with power words
- Use contractions (it's vs it is, you're vs you are)
- Remove redundant qualifiers ("really", "actually", "basically")
- Tighten sentence structure

RESPOND WITH THE SHORTENED HOOK ONLY (no explanations, no quotes):
"""

        logger.debug("  Calling LLM for hook shortening...")
        shortened_hook = llm_generate_fn(
            role="script_writer_hook_optimizer",
            task=prompt,
            context="",
            style_hints={"max_tokens": 100, "temperature": 0.7}
        )

        # Clean response
        shortened_hook = shortened_hook.strip().strip('"').strip("'")

        # Validate length
        if len(shortened_hook) <= 200:
            logger.info(f"  ✅ Layer 2: Hook shortened successfully ({len(hook)} → {len(shortened_hook)} chars)")
            return shortened_hook
        else:
            logger.warning(f"  ⚠️ Layer 2: LLM still produced {len(shortened_hook)} chars, falling to Layer 3")
            return _truncate_hook_deterministic(shortened_hook, max_chars=200)

    except Exception as e:
        logger.error(f"  ❌ Layer 2: AI shortening failed: {e}")
        logger.warning("  Falling to Layer 3 deterministic truncation")
        return _truncate_hook_deterministic(hook, max_chars=200)


def _parse_llm_suggestion(llm_text: str) -> Optional[Dict[str, any]]:
    """
    Parse LLM-generated script suggestion into components.

    Step 07: Extended to support VOICEOVER section

    Expects format:
        HOOK:
        <hook text>

        BULLETS:
        - <bullet 1>
        - <bullet 2>

        CTA:
        <cta text>

        VOICEOVER:
        <complete voiceover text>

    Args:
        llm_text: LLM-generated script text

    Returns:
        Dict with keys 'hook', 'bullets', 'outro_cta', 'full_voiceover_text' if parsing succeeds,
        None if parsing fails
    """
    if not llm_text or len(llm_text.strip()) < 20:
        return None

    try:
        lines = llm_text.strip().split("\n")
        hook = None
        bullets = []
        outro_cta = None
        voiceover_lines = []
        current_section = None

        for line in lines:
            line_stripped = line.strip()

            # Check for section markers (case-insensitive)
            # Step 09: Support format variations (# Hook, **HOOK**, Hook:, etc.)
            line_upper = line_stripped.upper()
            line_clean = line_upper.replace("#", "").replace("*", "").replace(":", "").strip()

            if line_clean.startswith("HOOK") or line_upper.startswith("HOOK:"):
                current_section = "hook"
                # Extract text after marker if present on same line
                if ":" in line_stripped:
                    hook_text = line_stripped.split(":", 1)[1].strip()
                    # Step 09: Only use text from same line if it's actual content (not just formatting chars)
                    # Skip if it's only asterisks, quotes, or other formatting
                    if hook_text and len(hook_text.replace('*', '').replace('"', '').strip()) > 0:
                        hook = _strip_quotes(hook_text)
            elif line_clean.startswith("BULLETS") or line_upper.startswith("BULLETS:"):
                current_section = "bullets"
            elif line_clean.startswith("CTA") or line_clean.startswith("CALL TO ACTION") or line_upper.startswith("CTA:"):
                current_section = "cta"
                # Extract text after marker if present on same line
                if ":" in line_stripped:
                    cta_text = line_stripped.split(":", 1)[1].strip()
                    # Step 09: Only use text from same line if it's actual content
                    if cta_text and len(cta_text.replace('*', '').replace('"', '').strip()) > 0:
                        outro_cta = _strip_quotes(cta_text)
            elif line_clean.startswith("VOICEOVER") or line_clean.startswith("VOICE OVER") or line_upper.startswith("VOICEOVER:"):
                current_section = "voiceover"
                # Extract text after marker if present on same line
                if ":" in line_stripped:
                    vo_text = line_stripped.split(":", 1)[1].strip()
                    if vo_text:
                        voiceover_lines.append(vo_text)
            elif not line_stripped:
                # Empty line - skip
                continue
            elif current_section == "hook" and not hook:
                # Step 09: Strip surrounding quotes from LLM output
                hook = _strip_quotes(line_stripped)
            elif current_section == "bullets":
                # Bullet point
                if line_stripped.startswith("-") or line_stripped.startswith("•"):
                    bullet_text = line_stripped[1:].strip()
                    if bullet_text:
                        # Step 09: Strip surrounding quotes from LLM output
                        bullets.append(_strip_quotes(bullet_text))
                elif line_stripped:  # Non-bullet line in bullets section
                    # Some LLMs might not use dashes
                    # Step 09: Strip surrounding quotes from LLM output
                    bullets.append(_strip_quotes(line_stripped))
            elif current_section == "cta" and not outro_cta:
                # Step 09: Strip surrounding quotes from LLM output
                outro_cta = _strip_quotes(line_stripped)
            elif current_section == "voiceover":
                voiceover_lines.append(line_stripped)

        # Assemble voiceover text
        full_voiceover_text = " ".join(voiceover_lines).strip() if voiceover_lines else None

        # Validate we got required components
        # Step 09: More tolerant parsing - accept 2+ bullets instead of 3+
        if hook and outro_cta and len(bullets) >= 2:
            result = {
                "hook": hook,
                "bullets": bullets,
                "outro_cta": outro_cta
            }

            # Add voiceover if present, otherwise will be composed from hook/bullets/cta
            if full_voiceover_text and len(full_voiceover_text) > 50:
                result["full_voiceover_text"] = full_voiceover_text

            return result

        # Step 09: Enhanced logging to understand why parsing failed
        missing = []
        if not hook:
            missing.append("hook")
        if not outro_cta:
            missing.append("CTA")
        if len(bullets) < 2:
            missing.append(f"bullets (found {len(bullets)}, need 2+)")

        logger.debug(f"Parser validation failed - missing: {', '.join(missing)}")
        return None

    except Exception as e:
        logger.warning(f"Failed to parse LLM suggestion: {e}")
        return None


def _generate_hook(plan: VideoPlan, brand_tone: str) -> str:
    """
    Generates a strong hook for the first 3 seconds.

    Args:
        plan: Video plan with strategic angle
        brand_tone: Channel's brand tone

    Returns:
        Hook text (1-2 sentences)
    """
    # Pattern: Start with attention-grabbing statement based on strategic angle
    title_words = plan.working_title.lower().split()

    # Create urgency/curiosity based hook patterns
    hooks_templates = [
        f"Attenzione! {plan.strategic_angle}",
        f"Non crederai a questo: {plan.working_title} sta esplodendo adesso.",
        f"Tutti stanno parlando di {plan.working_title}. Ecco perché.",
        f"Vuoi sapere il segreto dietro {plan.working_title}? Te lo mostro.",
        f"{plan.working_title}: la verità che nessuno ti dice."
    ]

    # Select first template for consistency (in real impl, could use LLM)
    hook = hooks_templates[0]

    # Ensure brand tone compliance (positive, direct, no vulgarity)
    if "positivo" in brand_tone.lower() or "diretto" in brand_tone.lower():
        hook = hook.replace("Non crederai", "Scopri")

    return hook


def _generate_content_bullets(plan: VideoPlan, bullets_count: Optional[int] = None) -> List[str]:
    """
    Generates main content points for the video.

    Sprint 2: Accepts bullets_count from Content Depth Strategist

    Args:
        plan: Video plan with strategic angle and target audience
        bullets_count: Optional recommended bullets count (default: 5)

    Returns:
        List of content bullets (AI-optimized count)
    """
    # In a real implementation, this would use LLM to generate contextual bullets
    # For now, create template-based content structure

    if bullets_count is None:
        bullets_count = 5  # Default fallback

    bullets_pool = [
        f"Cosa rende {plan.working_title} così rilevante adesso",
        f"I dati chiave che devi conoscere su {plan.working_title}",
        f"Come questo impatta {plan.target_audience}",
        f"Perché questo è importante per te",
        f"Cosa fare per sfruttare al meglio questa informazione",
        "Il punto più importante da ricordare",
        f"Gli errori comuni da evitare con {plan.working_title}",
        "Il consiglio finale degli esperti"
    ]

    # Return exactly the requested number of bullets
    return bullets_pool[:bullets_count]


def _generate_outro_cta(plan: VideoPlan) -> str:
    """
    ⚠️ DEPRECATED (Phase B2): Use CTA Strategist instead.

    Legacy fallback CTA generator. Only used when all AI-driven
    CTA sources fail (CTA Strategist, Editorial, Narrative).

    This function violates the "always AI-driven, not hardcoded" principle
    and should only be called as a last resort when:
    - CTA Strategist unavailable
    - Editorial Decision has no CTA
    - Narrative Arc has no CTA
    - LLM suggestion failed
    - Narrator fallback unavailable

    Args:
        plan: Video plan

    Returns:
        Generic CTA text (last resort fallback)
    """
    from yt_autopilot.core.logger import log_fallback

    log_fallback(
        component="SCRIPT_WRITER",
        fallback_type="DETERMINISTIC_CTA",
        reason="All AI-driven CTA sources unavailable (CTA Strategist, Editorial, Narrative, LLM)",
        impact="HIGH"
    )

    logger.warning("⚠️ Using deprecated deterministic CTA generation")
    logger.warning("  This violates AI-driven principle - consider enabling CTA Strategist")

    # Generic safe CTA (works for all content types and languages)
    # Avoids hardcoded Italian templates that don't scale internationally
    return "Iscriviti al canale per altri contenuti come questo!"


def _generate_narrator_aware_fallback(
    plan: VideoPlan,
    narrator_config: Dict,
    content_formula: Dict,
    series_format: Optional[SeriesFormat],
    brand_tone: str,
    recommended_bullets: Optional[int] = None
) -> Dict[str, any]:
    """
    Generates script components with narrator persona integrated (Step 09).

    This is used as intelligent fallback when LLM output parsing fails.
    Unlike pure deterministic generation, this maintains narrator identity.

    Sprint 2: Accepts recommended_bullets from Content Depth Strategist

    Args:
        plan: Video plan
        narrator_config: Narrator persona configuration
        content_formula: Content formula configuration
        series_format: Series format template
        brand_tone: Brand tone string
        recommended_bullets: Optional bullets count from Content Depth Strategist (Sprint 2)

    Returns:
        Dict with keys 'hook', 'bullets', 'outro_cta' including narrator elements
    """
    narrator_name = narrator_config.get('name', '')
    tone_of_address = narrator_config.get('tone_of_address', 'tu_informale')
    signature_phrases = narrator_config.get('signature_phrases', [])
    relationship = narrator_config.get('relationship', 'informative')

    # Determine if we should include narrator name in hook based on format
    format_type = series_format.serie_id if series_format else 'generic'
    include_name_in_hook = format_type in ['tutorial', 'how_to', 'demonstration']

    # Generate hook with narrator identity
    if include_name_in_hook and narrator_name:
        # Tutorial/How-to: Include narrator name to build trust
        hook = f"Ehi, sono {narrator_name}! {plan.strategic_angle}"
    else:
        # Other formats: Use strategic angle directly
        hook = f"Attenzione! {plan.strategic_angle}"

    # Use opening signature phrase if available and format allows
    if len(signature_phrases) > 0 and format_type in ['tutorial', 'challenge', 'motivation']:
        hook = f"{signature_phrases[0]} {hook}"

    # Sprint 2: Use recommended bullets count, fallback to 4
    if recommended_bullets is None:
        recommended_bullets = 4

    # Generate bullets (deterministic but tone-aware) - extend pool to support variable count
    if tone_of_address == 'tu_informale':
        bullets_pool = [
            f"Ti mostro cosa rende {plan.working_title} così importante",
            f"Devi sapere questi dettagli chiave",
            f"Ecco come ti impatta direttamente",
            f"Ti spiego cosa fare con questa informazione",
            f"Ti svelo i trucchi che gli esperti usano",
            "Ti mostro gli errori più comuni da evitare",
            "Ti do il consiglio finale degli esperti"
        ]
    else:  # voi_formale
        bullets_pool = [
            f"Vi mostro cosa rende {plan.working_title} così importante",
            f"Dovete sapere questi dettagli chiave",
            f"Ecco come vi impatta direttamente",
            f"Vi spiego cosa fare con questa informazione",
            f"Vi svelo i trucchi che gli esperti usano",
            "Vi mostro gli errori più comuni da evitare",
            "Vi do il consiglio finale degli esperti"
        ]

    # Return exactly the requested number of bullets
    bullets = bullets_pool[:recommended_bullets]

    # Generate CTA with signature phrase if available
    if len(signature_phrases) >= 3:
        # Use closing signature phrase
        outro_cta = f"{signature_phrases[2]} Iscriviti per altri contenuti!"
    elif len(signature_phrases) > 0:
        # Use last available phrase
        outro_cta = f"{signature_phrases[-1]} Iscriviti per altri contenuti!"
    else:
        # Generic CTA
        outro_cta = "Iscriviti al canale per non perdere i prossimi video!"

    return {
        "hook": hook,
        "bullets": bullets,
        "outro_cta": outro_cta
    }


def _compose_full_voiceover(hook: str, bullets: List[str], outro_cta: str) -> str:
    """
    Composes complete voiceover text from components.

    Args:
        hook: Opening hook
        bullets: Content bullets
        outro_cta: Closing CTA

    Returns:
        Full voiceover text as single string
    """
    # Build narrative flow
    sections = [hook]

    # Add transition after hook
    sections.append("Ecco cosa devi sapere.")

    # Add content bullets with natural transitions
    for i, bullet in enumerate(bullets):
        if i > 0:
            sections.append(f"Inoltre, {bullet.lower()}")
        else:
            sections.append(bullet)

    # Add concluding statement before CTA
    sections.append("Ricorda: l'informazione è potere.")

    # Add CTA
    sections.append(outro_cta)

    # Join with proper spacing
    full_text = " ".join(sections)

    return full_text


def _estimate_speaking_duration(text: str) -> int:
    """
    Estimates speaking duration in seconds based on text length.

    Step 07.3: Used for scene-level voiceover timing.

    Args:
        text: Text to estimate duration for

    Returns:
        Estimated duration in seconds (minimum 3 seconds)
    """
    word_count = len(text.split())
    # Average speaking rate: ~150 words/minute = 2.5 words/second
    duration = max(3, int(word_count / 2.5))
    return duration


def _create_scene_voiceover_map(
    hook: str,
    bullets: List[str],
    outro_cta: str,
    series_format: Optional[SeriesFormat] = None
) -> List[SceneVoiceover]:
    """
    Creates scene-by-scene voiceover breakdown for precise audio/visual sync.

    Step 07.3: Maps script components to scenes with timing.
    Step 07.5: Segment-aware mapping using series format template.

    LEGACY MODE (series_format=None):
    - Scene 1: Hook (opening)
    - Scene 2-N: Content bullets (one per scene if ≤3, grouped if >3)
    - Last scene: CTA (outro)

    SEGMENT-AWARE MODE (series_format provided):
    - Maps bullets to template segments
    - Tags each scene with segment_type
    - Respects segment count from template

    Args:
        hook: Opening hook text
        bullets: List of content bullet points
        outro_cta: Closing call-to-action
        series_format: Optional series format template (Step 07.5)

    Returns:
        List of SceneVoiceover objects with scene_id, text, duration, and segment_type
    """
    scene_map = []
    scene_id = 1

    if series_format:
        # Step 07.5: Segment-aware mode
        logger.info(f"  Creating segment-aware scene map from template ({len(series_format.segments)} segments)")

        # Scene 1: Hook (always first)
        hook_duration = _estimate_speaking_duration(hook)
        hook_segment = series_format.segments[0] if series_format.segments else None
        scene_map.append(SceneVoiceover(
            scene_id=scene_id,
            voiceover_text=hook,
            est_duration_seconds=hook_duration,
            segment_type=hook_segment.type if hook_segment else "hook"
        ))
        scene_id += 1

        # Content scenes: map bullets to remaining segments (excluding hook and CTA)
        content_segments = series_format.segments[1:-1] if len(series_format.segments) > 2 else []

        if content_segments:
            # Distribute bullets across content segments
            bullets_per_segment = max(1, len(bullets) // len(content_segments))

            for i, segment in enumerate(content_segments):
                # Get bullets for this segment
                start_idx = i * bullets_per_segment
                end_idx = start_idx + bullets_per_segment if i < len(content_segments) - 1 else len(bullets)
                segment_bullets = bullets[start_idx:end_idx]

                # Combine bullets for this segment
                segment_text = " ".join(segment_bullets)
                segment_duration = _estimate_speaking_duration(segment_text)

                scene_map.append(SceneVoiceover(
                    scene_id=scene_id,
                    voiceover_text=segment_text,
                    est_duration_seconds=segment_duration,
                    segment_type=segment.type
                ))
                scene_id += 1

        # Last scene: CTA
        cta_duration = _estimate_speaking_duration(outro_cta)
        cta_segment = series_format.segments[-1] if series_format.segments else None
        scene_map.append(SceneVoiceover(
            scene_id=scene_id,
            voiceover_text=outro_cta,
            est_duration_seconds=cta_duration,
            segment_type=cta_segment.type if cta_segment else "cta"
        ))

    else:
        # Legacy mode (backward compatibility)
        logger.info("  Creating legacy scene map (no series format)")

        # Scene 1: Hook
        hook_duration = _estimate_speaking_duration(hook)
        scene_map.append(SceneVoiceover(
            scene_id=scene_id,
            voiceover_text=hook,
            est_duration_seconds=hook_duration,
            segment_type="hook"  # Default segment type
        ))
        scene_id += 1

        # Content scenes: bullets
        if len(bullets) <= 3:
            # One scene per bullet if few bullets
            for i, bullet in enumerate(bullets):
                bullet_duration = _estimate_speaking_duration(bullet)
                scene_map.append(SceneVoiceover(
                    scene_id=scene_id,
                    voiceover_text=bullet,
                    est_duration_seconds=bullet_duration,
                    segment_type=f"content_{i+1}"  # Default segment type
                ))
                scene_id += 1
        else:
            # Group bullets into 2-3 scenes if many bullets
            mid_point = len(bullets) // 2

            # First group
            first_group = " ".join(bullets[:mid_point])
            first_duration = _estimate_speaking_duration(first_group)
            scene_map.append(SceneVoiceover(
                scene_id=scene_id,
                voiceover_text=first_group,
                est_duration_seconds=first_duration,
                segment_type="content_1"
            ))
            scene_id += 1

            # Second group
            second_group = " ".join(bullets[mid_point:])
            second_duration = _estimate_speaking_duration(second_group)
            scene_map.append(SceneVoiceover(
                scene_id=scene_id,
                voiceover_text=second_group,
                est_duration_seconds=second_duration,
                segment_type="content_2"
            ))
            scene_id += 1

        # Last scene: CTA
        cta_duration = _estimate_speaking_duration(outro_cta)
        scene_map.append(SceneVoiceover(
            scene_id=scene_id,
            voiceover_text=outro_cta,
            est_duration_seconds=cta_duration,
            segment_type="cta"
        ))

    return scene_map


def _build_persona_aware_prompt(
    plan: VideoPlan,
    narrator: Dict,
    content_formula: Dict,
    series_format: Optional[SeriesFormat],
    brand_tone: str,
    target_language: str = "en",
    recommended_bullets: Optional[int] = None
) -> str:
    """
    Builds LLM prompt enhanced with narrator persona guidelines.

    Step 09: Narrator Persona Integration
    Step 10: Explicit language directive for consistent output
    Sprint 2: Content Depth integration - uses AI-driven bullets count

    This function creates a comprehensive prompt that:
    1. Provides narrator identity and signature phrases
    2. Respects video format as primary driver
    3. Gives creative freedom to adapt guidelines appropriately
    4. Maintains brand tone consistency
    5. Enforces language consistency (Step 10)
    6. Uses Content Depth Strategist's recommended bullets count (Sprint 2)

    Args:
        plan: Video plan with topic and strategic angle
        narrator: Narrator persona config from workspace
        content_formula: Content formula config from workspace
        series_format: Optional series format template
        brand_tone: Brand tone from workspace
        target_language: Target language code (e.g., "it", "en") - Step 10
        recommended_bullets: Optional bullets count from Content Depth Strategist (Sprint 2)

    Returns:
        Enhanced LLM prompt string
    """
    format_name = series_format.serie_id if series_format else 'generic'
    format_style = series_format.description if series_format else 'engaging, concise'
    target_duration = content_formula.get('target_duration_seconds', 60)

    # Sprint 2: Use Content Depth Strategist's recommendation, or fallback to duration-based heuristic
    if recommended_bullets is None:
        # Fallback: duration-based heuristic (legacy behavior)
        if target_duration <= 60:
            recommended_bullets = 3
        elif target_duration <= 180:
            recommended_bullets = 4
        elif target_duration <= 480:
            recommended_bullets = 5
        else:
            recommended_bullets = 6

    # Build signature phrases section
    signature_phrases_text = ""
    if narrator.get('signature_phrases'):
        phrases = narrator.get('signature_phrases', [])
        signature_phrases_text = f"""
Signature phrases (use strategically if format allows):
  Opening phrase: "{phrases[0] if len(phrases) > 0 else ''}"
  Mid-content phrase: "{phrases[1] if len(phrases) > 1 else ''}"
  Closing phrase: "{phrases[2] if len(phrases) > 2 else phrases[-1]}"
"""

    # Build credibility markers section
    credibility_text = ""
    if narrator.get('credibility_markers'):
        markers = narrator.get('credibility_markers', [])
        credibility_text = f"""
Credibility markers (mention when relevant):
{chr(10).join([f'  - {marker}' for marker in markers])}
"""

    # Language name mapping for clear instructions
    language_names = {
        "it": "ITALIAN (Italiano)",
        "en": "ENGLISH",
        "es": "SPANISH (Español)",
        "fr": "FRENCH (Français)",
        "de": "GERMAN (Deutsch)",
        "pt": "PORTUGUESE (Português)"
    }
    language_name = language_names.get(target_language.lower(), target_language.upper())

    prompt = f"""⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
═══════════════════════════════════════════════════════════════
ALL OUTPUT MUST BE IN {language_name}
DO NOT MIX LANGUAGES. EVERY SINGLE WORD MUST BE IN {language_name}.
═══════════════════════════════════════════════════════════════

Write a script for YouTube Shorts about: {plan.working_title}

Strategic angle: {plan.strategic_angle}

─────────────────────────────────────────────
BRAND IDENTITY (interpret appropriately for format):
─────────────────────────────────────────────
Narrator: {narrator.get('name', 'Host')} - {narrator.get('identity', 'Content creator')}
Relationship with audience: {narrator.get('relationship', 'informative')}
Tone of address: {narrator.get('tone_of_address', 'tu_informale')}
{signature_phrases_text}{credibility_text}
Brand tone: {brand_tone}

─────────────────────────────────────────────
VIDEO FORMAT (primary structure driver):
─────────────────────────────────────────────
Format: {format_name}
Style: {format_style}
Target duration: {target_duration} seconds
Target audience: {plan.target_audience}

─────────────────────────────────────────────
ADAPTATION GUIDELINES:
─────────────────────────────────────────────
1. FORMAT drives structure - let the format dictate pacing and flow
2. NARRATOR PERSONA drives tone and credibility anchoring
3. Signature phrases: Use ONLY if they enhance the format naturally
   - Tutorial/How-to: YES (establish authority at start)
   - News/Breaking: MINIMAL or NO (urgency > personality)
   - Story-driven: YES in closing (emotional anchor)
   - Quick Tips (<30s): NO (too brief)

4. Narrator name in hook:
   - Tutorial/How-to: YES (builds trust)
   - News/Breaking: NO (focus on facts)
   - Story: DEPENDS (1st person = yes, 3rd person = no)
   - Quick Tips: NO (brevity first)

5. Tone of address: ALWAYS maintain "{narrator.get('tone_of_address', 'tu_informale')}"

6. Credibility: Reference subtly when it strengthens the point

─────────────────────────────────────────────
CREATIVE FREEDOM:
─────────────────────────────────────────────
You have FULL AUTONOMY to interpret these guidelines.
Prioritize: VIEWER RETENTION > BRAND CONSISTENCY > RIGID TEMPLATE

- If signature phrase doesn't fit → skip it
- If narrator name slows hook → omit it
- If credibility helps trust → mention it naturally
- Make it feel NATURAL, not forced

Goal: Maximum watch time + subtle brand consistency

─────────────────────────────────────────────
OUTPUT FORMAT:
─────────────────────────────────────────────
⚠️ REMEMBER: Write EVERYTHING in {language_name} ⚠️

HOOK:
[Engaging opening - consider narrator introduction if appropriate for format]
⚠️ CRITICAL: Hook MUST be ≤200 characters (strict limit for mobile display)
⚠️ Count characters including spaces, punctuation, and emojis BEFORE responding
⚠️ If your hook exceeds 200 chars, SHORTEN it while preserving impact

Hook Examples:
- English: "This mistake cost $2M. Here's what happened..."
- Italian: "Questo errore è costato 2 milioni. Ecco cosa è successo..."
- English: "Want to lose belly fat? This changes everything."
- Italian: "Vuoi perdere grasso addominale? Questo cambia tutto."

BULLETS:
{chr(10).join([f'- [Main point {i+1}]' for i in range(recommended_bullets)])}

⚠️ CRITICAL: Provide EXACTLY {recommended_bullets} bullets (AI-optimized count for {target_duration}s duration)

Bullet Examples:
- English: "The secret lies in timing your workouts"
- Italian: "Il segreto sta nel timing degli allenamenti"
- English: "Research shows this technique works 3x faster"
- Italian: "La ricerca mostra che questa tecnica funziona 3 volte più velocemente"

CTA:
[Call to action - consider signature closing if appropriate]

CTA Examples:
- English: "Drop a comment with your biggest challenge!"
- Italian: "Scrivi un commento con la tua sfida più grande!"
- English: "Follow for more tips like this!"
- Italian: "Seguimi per altri consigli come questo!"

VOICEOVER:
[Complete narration text combining all sections naturally]

⚠️ FINAL CHECK: Verify ALL text above is in {language_name} ⚠️
"""

    return prompt


def _normalize_segment_type(act_name: str) -> str:
    """
    Normalizes act names from Narrative Architect to standard segment types for Visual Planner.

    Task 1.3.a: Fixes segment type naming mismatch between Narrative and Visual agents.

    Mappings:
    - "Hook" → "hook"
    - "Content_N" / "Content" / "Agitation" / "Solution" → "content"
    - "Payoff_CTA" / "CTA" / "Outro" → "cta"
    - "Intro" → "intro"

    Args:
        act_name: Act name from Narrative Architect (e.g., "Payoff_CTA", "Content_1")

    Returns:
        Normalized segment type (e.g., "cta", "content")
    """
    act_lower = act_name.lower()

    # Hook segment
    if act_lower == 'hook':
        return 'hook'

    # CTA variants (most critical fix for Task 1.3.a)
    if any(keyword in act_lower for keyword in ['payoff_cta', 'cta', 'outro', 'call_to_action']):
        return 'cta'

    # Intro segment
    if act_lower == 'intro':
        return 'intro'

    # Content segments (default for everything else)
    # Handles: "Content_1", "Content_2", "Agitation", "Solution", etc.
    return 'content'


def write_script(
    plan: VideoPlan,
    memory: Dict,
    llm_suggestion: Optional[str] = None,
    series_format: Optional[SeriesFormat] = None,
    editorial_decision: Optional[EditorialDecision] = None,
    narrative_arc: Optional[Dict] = None,
    content_depth_strategy: Optional[Dict] = None,
    cta_strategy: Optional[Dict] = None,
    forced_cta: Optional[str] = None,
    llm_generate_fn: Optional[callable] = None  # Layer 2: Hook length validation
) -> VideoScript:
    """
    Generates a complete video script from a video plan.

    This is the entry point for the ScriptWriter agent. It creates:
    - A strong hook for the first 3 seconds
    - Content bullets covering key points
    - A clear call-to-action
    - Complete voiceover text

    The script respects the channel's brand tone and targets the specified audience.

    NEW (Step 06-fullrun): Accepts optional LLM-generated suggestion from pipeline.
    If provided, attempts to use LLM's creative output while applying safety rules.

    NEW (Step 07.5): Accepts optional series format for segment-aware generation.
    If provided, structures script according to template and tags scenes with segment_type.

    NEW (Step 11): Accepts optional editorial_decision from Editorial Strategist.
    If provided, uses AI-driven strategy for format, angle, duration, and specific CTA.

    NEW (Monetization Refactor): Accepts optional narrative_arc from Narrative Architect.
    If provided, uses AI-driven emotional storytelling instead of template-based generation.
    Priority: narrative_arc > llm_suggestion > fallback

    NEW (Sprint 2): Accepts optional content_depth_strategy from Content Depth Strategist.
    If provided, uses AI-driven bullets count optimization for content adequacy.

    NEW (FASE 3): Accepts optional forced_cta for quality retry mechanism.
    If provided, overrides all other CTA sources to ensure exact match with CTA Strategist.

    NEW (PHASE B2): Accepts optional cta_strategy from CTA Strategist.
    If provided, uses AI-driven CTA placement strategy as primary CTA source.

    CTA Priority Hierarchy (7 levels, highest to lowest):
    1. forced_cta (quality retry override)
    2. cta_strategy.main_cta (CTA Strategist - AI-driven strategic placement)
    3. editorial_decision.cta_specific (Editorial Strategist - high-level strategy)
    4. narrative_arc CTA (Narrative Architect - emotional storytelling)
    5. llm_suggestion CTA (LLM-generated creative)
    6. narrator_fallback (maintains brand voice if narrator enabled)
    7. deterministic (deprecated last resort)

    Args:
        plan: Video plan with topic, angle, and audience
        memory: Channel memory dict containing brand_tone
        llm_suggestion: Optional LLM-generated script suggestion from pipeline
                        (Step 06-fullrun: enables real LLM integration)
        series_format: Optional series format template for structured generation
                       (Step 07.5: enables format engine)
        editorial_decision: Optional AI-driven editorial strategy
                           (Step 11: enables strategic script generation)
        narrative_arc: Optional AI-driven narrative structure from Narrative Architect
                      (Monetization: emotional storytelling for retention)
        content_depth_strategy: Optional AI-driven bullets count from Content Depth Strategist
                               (Sprint 2: content adequacy optimization)
        cta_strategy: Optional AI-driven CTA placement strategy from CTA Strategist
                     (Phase B2: strategic CTA optimization for monetization)
        forced_cta: Optional specific CTA text to force (FASE 3: quality retry for CTA validation)

    Returns:
        VideoScript with all components

    Raises:
        ValueError: If plan is invalid
    """
    if not plan.working_title:
        raise ValueError("Cannot write script: VideoPlan has no working_title")

    logger.info(f"ScriptWriter generating script for: '{plan.working_title}'")

    if series_format:
        logger.info(f"  Using series format: {series_format.name} ({series_format.serie_id})")

    if editorial_decision:
        logger.info(f"  Using editorial strategy: {editorial_decision.serie_concept}")
        logger.info(f"    Format: {editorial_decision.format} | Angle: {editorial_decision.angle}")
        logger.info(f"    Duration target: {editorial_decision.duration_target}s")
        logger.info(f"    CTA: {editorial_decision.cta_specific[:50]}...")

    # Sprint 2: Extract Content Depth Strategy
    recommended_bullets = None
    if content_depth_strategy:
        recommended_bullets = content_depth_strategy.get('recommended_bullets')
        adequacy_score = content_depth_strategy.get('adequacy_score', 0.0)
        logger.info(f"  ✓ Content Depth Strategy applied:")
        logger.info(f"    Recommended bullets: {recommended_bullets}")
        logger.info(f"    Adequacy score: {adequacy_score:.2f}")
        logger.info(f"    Pacing: {content_depth_strategy.get('pacing_guidance', 'N/A')[:60]}...")

    # Load brand tone
    brand_tone = get_brand_tone(memory)

    # Step 09: Load narrator persona and content formula
    narrator = memory.get('narrator_persona', {})
    content_formula = memory.get('content_formula', {})
    narrator_enabled = narrator.get('enabled', False)

    if narrator_enabled:
        logger.info(f"  Narrator persona enabled: {narrator.get('name', 'Unknown')}")
        logger.info(f"  Relationship: {narrator.get('relationship', 'Unknown')}")
        logger.info(f"  Tone of address: {narrator.get('tone_of_address', 'Unknown')}")

    # Track source for control flow
    used_narrative_arc = False
    llm_parsed = None

    # PRIORITY 1: Use Narrative Arc if available (Monetization Refactor)
    if narrative_arc and narrative_arc.get('narrative_structure'):
        used_narrative_arc = True  # WEEK 2 Task 2.2: Critical flag to preserve Narrative's scene map
        logger.info("  ✓ Using Narrative Architect's emotional storytelling")
        logger.info(f"  Voice personality: {narrative_arc.get('voice_personality', 'Unknown')}")
        logger.info(f"  Acts: {len(narrative_arc['narrative_structure'])}")

        # Extract script components from narrative arc
        acts = narrative_arc['narrative_structure']
        full_voiceover_text = narrative_arc.get('full_voiceover', '')

        # Extract hook from first act
        hook_act = acts[0] if acts else {}
        hook = hook_act.get('voiceover', '')

        # Extract bullets from middle acts (skip Hook and CTA acts)
        bullets = []
        for act in acts[1:-1]:  # Skip first (hook) and last (CTA)
            act_name = act.get('act_name', '')
            if act_name.lower() not in ['hook', 'payoff_cta', 'cta', 'outro']:
                bullets.append(act.get('voiceover', ''))

        # CRITICAL FIX: Validate bullets count matches Content Depth Strategy recommendation
        if content_depth_strategy:
            recommended_bullets = content_depth_strategy.get('recommended_bullets')
            if recommended_bullets and len(bullets) != recommended_bullets:
                logger.error(
                    f"❌ CONTENT DEPTH MISMATCH: Narrative Arc has {len(bullets)} content bullets "
                    f"but Content Depth Strategist recommends {recommended_bullets}. "
                    f"This will cause inadequate content."
                )

                # 🚨 STANDARDIZED FALLBACK LOGGING (DEVELOPMENT_CONVENTIONS.md)
                log_fallback(
                    component="SCRIPT_WRITER",
                    fallback_type="DETERMINISTIC_GENERATION",
                    reason=f"Narrative Arc bullet mismatch: {len(bullets)} vs {recommended_bullets}",
                    impact="HIGH"
                )

                # Reset to trigger fallback to deterministic generation that respects recommended_bullets
                used_narrative_arc = False
                bullets = []
                hook = ""
                outro_cta = ""
                full_voiceover_text = ""
                scene_voiceover_map = []

        # Extract CTA from last act (only if narrative arc is still being used)
        if used_narrative_arc:
            cta_act = acts[-1] if acts else {}
            outro_cta = cta_act.get('voiceover', '')

            # PHASE B2: Note - CTA priority hierarchy will be applied later (lines 1077+)
            # Don't override here, just log what sources are available
            if cta_strategy and cta_strategy.get('main_cta'):
                logger.info(f"  ℹ️ CTA Strategist available - will take priority over Narrative CTA")
            elif editorial_decision and editorial_decision.cta_specific:
                logger.info(f"  ℹ️ Editorial Decision available - will take priority over Narrative CTA")
            else:
                logger.info(f"  ℹ️ Narrative Arc CTA will be used (no higher priority source)")

            # Create scene_voiceover_map from narrative acts
            from yt_autopilot.core.schemas import SceneVoiceover
            scene_voiceover_map = []
            for i, act in enumerate(acts, start=1):  # Start from 1, not 0
                act_name = act.get('act_name', 'content')
                scene_voiceover_map.append(SceneVoiceover(
                    scene_id=i,
                    voiceover_text=act.get('voiceover', ''),
                    est_duration_seconds=act.get('duration_seconds', 3),
                    segment_type=_normalize_segment_type(act_name),  # Task 1.3.a: Use normalization
                    emotional_beat=act.get('emotional_beat')  # Task 1.3.b: Pass emotion from Narrative
                ))

            logger.info(f"  ✓ Narrative arc converted: hook + {len(bullets)} bullets + CTA")
            logger.info(f"  ✓ Scene map: {len(scene_voiceover_map)} scenes")
            # used_narrative_arc is already True, no need to set again

    # PRIORITY 2: Try to use LLM suggestion if provided
    elif llm_suggestion:
        logger.info("  LLM suggestion received - attempting to parse...")
        llm_parsed = _parse_llm_suggestion(llm_suggestion)

        if llm_parsed:
            logger.info("  ✓ LLM suggestion parsed successfully")
        else:
            log_fallback(
                component="SCRIPT_WRITER",
                fallback_type="NARRATOR_AWARE_GENERATION",
                reason="LLM suggestion parsing failed",
                impact="MEDIUM"
            )
            logger.warning("  ✗ LLM suggestion parsing failed - using deterministic generation")

    # Generate script components (skip if narrative_arc already provided them)
    if not used_narrative_arc:
        if llm_parsed:
            # Use LLM-generated components
            hook = llm_parsed["hook"]
            bullets = llm_parsed["bullets"]
            outro_cta = llm_parsed["outro_cta"]

            # Use LLM voiceover if present, otherwise compose from components
            if "full_voiceover_text" in llm_parsed:
                full_voiceover_text = llm_parsed["full_voiceover_text"]
                logger.info("  Using LLM-generated hook, bullets, CTA, and voiceover")
            else:
                full_voiceover_text = _compose_full_voiceover(hook, bullets, outro_cta)
                logger.info("  Using LLM-generated hook, bullets, CTA (voiceover composed)")
        else:
            # Fallback generation
            # Step 09: Use narrator-aware fallback if narrator enabled, otherwise use generic deterministic
            if narrator_enabled:
                log_fallback(
                    component="SCRIPT_WRITER",
                    fallback_type="NARRATOR_AWARE_GENERATION",
                    reason="No LLM suggestion provided",
                    impact="LOW"
                )
                logger.info("  Using narrator-aware fallback generation")
                fallback_components = _generate_narrator_aware_fallback(
                    plan=plan,
                    narrator_config=narrator,
                    content_formula=content_formula,
                    series_format=series_format,
                    brand_tone=brand_tone,
                    recommended_bullets=recommended_bullets  # Sprint 2: AI-driven bullets count
                )
                hook = fallback_components["hook"]
                bullets = fallback_components["bullets"]
                outro_cta = fallback_components["outro_cta"]
                full_voiceover_text = _compose_full_voiceover(hook, bullets, outro_cta)
            else:
                # Generic deterministic generation (backward compatibility)
                log_fallback(
                    component="SCRIPT_WRITER",
                    fallback_type="DETERMINISTIC_GENERATION",
                    reason="No narrator persona configured",
                    impact="MEDIUM"
                )
                logger.info("  Using deterministic script generation")
                hook = _generate_hook(plan, brand_tone)
                bullets = _generate_content_bullets(plan, bullets_count=recommended_bullets)  # Sprint 2
                outro_cta = _generate_outro_cta(plan)
                full_voiceover_text = _compose_full_voiceover(hook, bullets, outro_cta)

    # Apply safety rules (regardless of source)
    # TODO: Add explicit safety checks here in future:
    # - No medical claims guarantees
    # - No hate speech
    # - No copyright violations
    # - Brand tone compliance
    # For now, we trust QualityReviewer to catch issues

    # Step 07.3/07.5: Create scene-by-scene voiceover map for audio/visual sync
    # Skip if narrative_arc already created the scene map
    if not used_narrative_arc:
        # Step 07.5: Pass series_format for segment-aware tagging
        scene_voiceover_map = _create_scene_voiceover_map(hook, bullets, outro_cta, series_format)

    total_scene_duration = sum(s.est_duration_seconds for s in scene_voiceover_map)
    logger.info(f"  Scene voiceover map: {len(scene_voiceover_map)} scenes, ~{total_scene_duration}s total")

    # PHASE B2: CTA Priority Hierarchy (7 levels, highest to lowest)
    # Apply final CTA selection based on explicit priority order
    logger.info("Applying CTA Priority Hierarchy...")

    # Determine current CTA source before hierarchy application
    cta_source_before = None
    if used_narrative_arc:
        cta_source_before = "NARRATIVE_ARC"
    elif llm_suggestion:
        # Check if LLM parsing was successful
        llm_parsed_test = _parse_llm_suggestion(llm_suggestion)
        if llm_parsed_test and llm_parsed_test.get('outro_cta'):
            cta_source_before = "LLM_SUGGESTION"

    # Apply priority hierarchy
    if forced_cta:
        # PRIORITY 1: Quality retry override (highest priority)
        logger.info(f"  ✓ CTA Source: FORCED_CTA (quality retry override)")
        logger.info(f"    Text: '{forced_cta[:60]}...'")
        outro_cta = forced_cta
        cta_source = "FORCED_CTA"

    elif cta_strategy and cta_strategy.get('main_cta'):
        # PRIORITY 2: CTA Strategist (AI-driven strategic placement)
        logger.info(f"  ✓ CTA Source: CTA_STRATEGIST (AI-driven)")
        logger.info(f"    Main CTA: '{cta_strategy['main_cta'][:60]}...'")
        if cta_strategy.get('funnel_path'):
            logger.info(f"    Funnel Path: {cta_strategy['funnel_path']}")
        if cta_strategy.get('mid_roll_ctas'):
            logger.info(f"    Mid-roll CTAs: {len(cta_strategy['mid_roll_ctas'])} planned")
        outro_cta = cta_strategy['main_cta']
        cta_source = "CTA_STRATEGIST"

        # Log CTA Strategist reasoning (truncated for readability)
        from yt_autopilot.core.logger import truncate_for_log
        from yt_autopilot.core.config import LOG_TRUNCATE_REASONING
        if cta_strategy.get('reasoning'):
            logger.info(f"    Reasoning: {truncate_for_log(cta_strategy['reasoning'], LOG_TRUNCATE_REASONING)}")

    elif editorial_decision and editorial_decision.cta_specific:
        # PRIORITY 3: Editorial Decision (strategic directive)
        logger.info(f"  ✓ CTA Source: EDITORIAL_DECISION (strategic directive)")
        logger.info(f"    Text: '{editorial_decision.cta_specific[:60]}...'")
        outro_cta = editorial_decision.cta_specific
        cta_source = "EDITORIAL_DECISION"

    elif cta_source_before == "NARRATIVE_ARC" and outro_cta:
        # PRIORITY 4: Narrative Arc (already set earlier, emotional storytelling)
        logger.info(f"  ✓ CTA Source: NARRATIVE_ARC (emotional storytelling)")
        logger.info(f"    Text: '{outro_cta[:60]}...'")
        cta_source = "NARRATIVE_ARC"

    elif cta_source_before == "LLM_SUGGESTION" and outro_cta:
        # PRIORITY 5: LLM Suggestion (creative LLM-generated)
        logger.info(f"  ✓ CTA Source: LLM_SUGGESTION (creative generation)")
        logger.info(f"    Text: '{outro_cta[:60]}...'")
        cta_source = "LLM_SUGGESTION"

    else:
        # PRIORITY 6-7: Fallback sources (narrator-aware or deterministic)
        # outro_cta already set by fallback logic in lines 1009-1057
        if narrator and narrator.get('enabled'):
            cta_source = "NARRATOR_FALLBACK"
            logger.info(f"  ✓ CTA Source: NARRATOR_FALLBACK (brand voice maintained)")
        else:
            cta_source = "DETERMINISTIC_FALLBACK"
            logger.info(f"  ✓ CTA Source: DETERMINISTIC_FALLBACK (deprecated last resort)")
        logger.info(f"    Text: '{outro_cta[:60]}...'")

    logger.info(f"Final CTA selected from: {cta_source}")

    # Layer 2/3: Validate and fix hook length (max 200 chars for mobile display)
    if len(hook) > 200:
        logger.info(f"Hook validation: {len(hook)} chars exceeds 200 char limit")
        hook = _fix_overlength_hook_with_llm(hook, plan, llm_generate_fn)
        logger.info(f"✓ Hook adjusted to {len(hook)} chars")
    else:
        logger.info(f"✓ Hook length validated: {len(hook)} chars (within 200 char limit)")

    # Create VideoScript
    script = VideoScript(
        hook=hook,
        bullets=bullets,
        outro_cta=outro_cta,
        full_voiceover_text=full_voiceover_text,
        scene_voiceover_map=scene_voiceover_map
    )

    logger.info(
        f"Generated script: {len(script.bullets)} bullets, "
        f"{len(script.full_voiceover_text)} chars voiceover, "
        f"{len(script.scene_voiceover_map)} scenes"
    )

    return script
