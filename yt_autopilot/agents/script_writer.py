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
        context=f"Topic: {plan.topic}, Target: {plan.target_cta}",
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
from yt_autopilot.core.schemas import VideoPlan, VideoScript, SceneVoiceover, SeriesFormat
from yt_autopilot.core.memory_store import get_brand_tone
from yt_autopilot.core.logger import logger


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
            line_upper = line_stripped.upper()

            if line_upper.startswith("HOOK:"):
                current_section = "hook"
                # Extract text after "HOOK:" if present on same line
                hook_text = line_stripped[5:].strip()
                if hook_text:
                    hook = hook_text
            elif line_upper.startswith("BULLETS:"):
                current_section = "bullets"
            elif line_upper.startswith("CTA:"):
                current_section = "cta"
                # Extract text after "CTA:" if present on same line
                cta_text = line_stripped[4:].strip()
                if cta_text:
                    outro_cta = cta_text
            elif line_upper.startswith("VOICEOVER:"):
                current_section = "voiceover"
                # Extract text after "VOICEOVER:" if present on same line
                vo_text = line_stripped[10:].strip()
                if vo_text:
                    voiceover_lines.append(vo_text)
            elif not line_stripped:
                # Empty line - skip
                continue
            elif current_section == "hook" and not hook:
                hook = line_stripped
            elif current_section == "bullets":
                # Bullet point
                if line_stripped.startswith("-") or line_stripped.startswith("•"):
                    bullet_text = line_stripped[1:].strip()
                    if bullet_text:
                        bullets.append(bullet_text)
                elif line_stripped:  # Non-bullet line in bullets section
                    # Some LLMs might not use dashes
                    bullets.append(line_stripped)
            elif current_section == "cta" and not outro_cta:
                outro_cta = line_stripped
            elif current_section == "voiceover":
                voiceover_lines.append(line_stripped)

        # Assemble voiceover text
        full_voiceover_text = " ".join(voiceover_lines).strip() if voiceover_lines else None

        # Validate we got required components
        if hook and outro_cta and len(bullets) >= 3:
            result = {
                "hook": hook,
                "bullets": bullets,
                "outro_cta": outro_cta
            }

            # Add voiceover if present, otherwise will be composed from hook/bullets/cta
            if full_voiceover_text and len(full_voiceover_text) > 50:
                result["full_voiceover_text"] = full_voiceover_text

            return result

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


def _generate_content_bullets(plan: VideoPlan) -> List[str]:
    """
    Generates main content points for the video.

    Args:
        plan: Video plan with strategic angle and target audience

    Returns:
        List of content bullets (3-5 key points)
    """
    # In a real implementation, this would use LLM to generate contextual bullets
    # For now, create template-based content structure

    bullets = [
        f"Cosa rende {plan.working_title} così rilevante adesso",
        f"I dati chiave che devi conoscere su {plan.working_title}",
        f"Come questo impatta {plan.target_audience}",
        f"Cosa fare per sfruttare al meglio questa informazione",
        "Il punto più importante da ricordare"
    ]

    return bullets


def _generate_outro_cta(plan: VideoPlan) -> str:
    """
    Generates call-to-action for video outro.

    Args:
        plan: Video plan

    Returns:
        CTA text
    """
    ctas = [
        "Se questo video ti è stato utile, iscriviti per non perdere i prossimi contenuti!",
        "Lascia un like se vuoi vedere più video su questo argomento!",
        "Iscriviti al canale per rimanere aggiornato sulle ultime tendenze!",
        "Condividi questo video con chi potrebbe trovarlo utile!"
    ]

    # Select based on audience type
    if "tecnologia" in plan.target_audience.lower():
        return ctas[2]  # Focus on staying updated
    else:
        return ctas[0]  # Generic subscribe CTA


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


def write_script(
    plan: VideoPlan,
    memory: Dict,
    llm_suggestion: Optional[str] = None,
    series_format: Optional[SeriesFormat] = None
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

    Args:
        plan: Video plan with topic, angle, and audience
        memory: Channel memory dict containing brand_tone
        llm_suggestion: Optional LLM-generated script suggestion from pipeline
                        (Step 06-fullrun: enables real LLM integration)
        series_format: Optional series format template for structured generation
                       (Step 07.5: enables format engine)

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

    # Load brand tone
    brand_tone = get_brand_tone(memory)

    # Try to use LLM suggestion if provided
    llm_parsed = None
    if llm_suggestion:
        logger.info("  LLM suggestion received - attempting to parse...")
        llm_parsed = _parse_llm_suggestion(llm_suggestion)

        if llm_parsed:
            logger.info("  ✓ LLM suggestion parsed successfully")
        else:
            logger.warning("  ✗ LLM suggestion parsing failed - using deterministic generation")

    # Generate script components
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
        # Fallback to deterministic generation
        hook = _generate_hook(plan, brand_tone)
        bullets = _generate_content_bullets(plan)
        outro_cta = _generate_outro_cta(plan)
        full_voiceover_text = _compose_full_voiceover(hook, bullets, outro_cta)
        logger.info("  Using deterministic script generation")

    # Apply safety rules (regardless of source)
    # TODO: Add explicit safety checks here in future:
    # - No medical claims guarantees
    # - No hate speech
    # - No copyright violations
    # - Brand tone compliance
    # For now, we trust QualityReviewer to catch issues

    # Step 07.3/07.5: Create scene-by-scene voiceover map for audio/visual sync
    # Step 07.5: Pass series_format for segment-aware tagging
    scene_voiceover_map = _create_scene_voiceover_map(hook, bullets, outro_cta, series_format)
    total_scene_duration = sum(s.est_duration_seconds for s in scene_voiceover_map)
    logger.info(f"  Scene voiceover map: {len(scene_voiceover_map)} scenes, ~{total_scene_duration}s total")

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
