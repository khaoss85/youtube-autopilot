"""
ScriptWriter Agent: Generates engaging video scripts from video plans.

This agent transforms strategic video plans into complete scripts with
hooks, content bullets, CTAs, and full voiceover text.
"""

from typing import Dict, List
from yt_autopilot.core.schemas import VideoPlan, VideoScript
from yt_autopilot.core.memory_store import get_brand_tone
from yt_autopilot.core.logger import logger


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


def write_script(plan: VideoPlan, memory: Dict) -> VideoScript:
    """
    Generates a complete video script from a video plan.

    This is the entry point for the ScriptWriter agent. It creates:
    - A strong hook for the first 3 seconds
    - Content bullets covering key points
    - A clear call-to-action
    - Complete voiceover text

    The script respects the channel's brand tone and targets the specified audience.

    Args:
        plan: Video plan with topic, angle, and audience
        memory: Channel memory dict containing brand_tone

    Returns:
        VideoScript with all components

    Raises:
        ValueError: If plan is invalid
    """
    if not plan.working_title:
        raise ValueError("Cannot write script: VideoPlan has no working_title")

    logger.info(f"ScriptWriter generating script for: '{plan.working_title}'")

    # Load brand tone
    brand_tone = get_brand_tone(memory)

    # Generate script components
    hook = _generate_hook(plan, brand_tone)
    bullets = _generate_content_bullets(plan)
    outro_cta = _generate_outro_cta(plan)

    # Compose full voiceover
    full_voiceover_text = _compose_full_voiceover(hook, bullets, outro_cta)

    # Create VideoScript
    script = VideoScript(
        hook=hook,
        bullets=bullets,
        outro_cta=outro_cta,
        full_voiceover_text=full_voiceover_text
    )

    logger.info(
        f"Generated script: {len(script.bullets)} bullets, "
        f"{len(script.full_voiceover_text)} chars voiceover"
    )

    return script
