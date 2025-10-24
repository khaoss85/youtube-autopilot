"""
SeoManager Agent: Optimizes video metadata for YouTube discovery and CTR.

This agent generates SEO-optimized titles, descriptions, tags, and
thumbnail concepts to maximize video visibility and click-through rate.
"""

from typing import List
from yt_autopilot.core.schemas import VideoPlan, VideoScript, PublishingPackage
from yt_autopilot.core.logger import logger


def _optimize_title_for_ctr(plan: VideoPlan) -> str:
    """
    Generates a CTR-optimized YouTube title.

    Balances curiosity, clarity, and keyword optimization while staying
    within YouTube's 100-character limit.

    Args:
        plan: Video plan with working title and strategic angle

    Returns:
        Optimized final title (max 100 chars)
    """
    working_title = plan.working_title

    # CTR optimization patterns
    # Pattern 1: Question format (creates curiosity)
    if "?" not in working_title:
        title_option_1 = f"{working_title}: Cosa Devi Sapere?"

    # Pattern 2: Urgency/FOMO format
    title_option_2 = f"{working_title} - Tutti Ne Parlano!"

    # Pattern 3: Value proposition format
    title_option_3 = f"{working_title}: La Verità Che Nessuno Ti Dice"

    # Pattern 4: Direct benefit format
    title_option_4 = f"Come Capire {working_title} in 60 Secondi"

    # Select based on title length and type
    candidates = [
        title_option_2,  # Default: FOMO works well for trends
        title_option_4,  # Good for educational content
        title_option_3,  # Good for controversial topics
    ]

    # Pick first candidate under 100 chars
    for candidate in candidates:
        if len(candidate) <= 100:
            final_title = candidate
            break
    else:
        # Fallback: truncate working title
        final_title = working_title[:97] + "..." if len(working_title) > 100 else working_title

    logger.debug(f"Optimized title: '{final_title}' ({len(final_title)} chars)")
    return final_title


def _generate_description(plan: VideoPlan, script: VideoScript) -> str:
    """
    Generates SEO-optimized YouTube description.

    Includes:
    - Brief video summary (first 2 lines visible in search)
    - Keyword-rich content description
    - Timestamps (if applicable)
    - Call-to-action
    - Disclaimer/compliance notes

    Args:
        plan: Video plan with context
        script: Video script for content summary

    Returns:
        Complete YouTube description
    """
    # First 2 lines are critical (visible in search results)
    summary_line_1 = f"{plan.working_title}: {plan.strategic_angle}"
    summary_line_2 = f"Tutto quello che devi sapere su {plan.working_title} spiegato in modo semplice e diretto."

    # Main content section
    content_section = f"""
📌 In questo video scoprirai:
{chr(10).join(f'• {bullet}' for bullet in script.bullets[:3])}

🎯 Perché guardare questo video?
{plan.strategic_angle}

👥 Questo video è perfetto per: {plan.target_audience}
"""

    # CTA section
    cta_section = """
🔔 Iscriviti per non perdere i prossimi contenuti!
👍 Lascia un like se il video ti è piaciuto!
💬 Commenta con le tue domande o opinioni!
"""

    # Disclaimer/compliance
    disclaimer = """
⚠️ Disclaimer: Questo video è a scopo informativo.
Verifica sempre le informazioni presso fonti ufficiali.
"""

    # Combine sections
    description = f"""{summary_line_1}

{summary_line_2}

{content_section.strip()}

{cta_section.strip()}

{disclaimer.strip()}

#Shorts #Trending #{plan.working_title.replace(' ', '')}
"""

    return description.strip()


def _extract_tags(plan: VideoPlan, script: VideoScript) -> List[str]:
    """
    Extracts relevant YouTube tags for discoverability.

    Args:
        plan: Video plan with topic
        script: Video script for additional keywords

    Returns:
        List of tags (max 500 chars total per YouTube limits)
    """
    tags = []

    # Primary keyword (topic)
    topic_tag = plan.working_title.lower()
    tags.append(topic_tag)

    # Add word variations
    topic_words = topic_tag.split()
    if len(topic_words) > 1:
        tags.extend(topic_words)

    # Language tag
    if plan.language == "it":
        tags.extend(["italiano", "italy", "italian"])
    else:
        tags.extend(["english", "global"])

    # Format tags
    tags.extend(["shorts", "short video", "vertical video", "trending"])

    # Audience-based tags
    if "tecnologia" in plan.target_audience.lower():
        tags.extend(["tech", "technology", "innovation"])
    elif "fitness" in plan.target_audience.lower():
        tags.extend(["fitness", "health", "workout"])
    elif "finanza" in plan.target_audience.lower():
        tags.extend(["finance", "money", "investing"])

    # Generic engagement tags
    tags.extend(["explained", "tutorial", "guide", "tips"])

    # Deduplicate and ensure max 500 chars total
    unique_tags = []
    total_length = 0
    for tag in tags:
        if tag not in unique_tags:
            tag_length = len(tag) + 1  # +1 for comma separator
            if total_length + tag_length <= 500:
                unique_tags.append(tag)
                total_length += tag_length

    logger.debug(f"Generated {len(unique_tags)} tags ({total_length} chars)")
    return unique_tags


def _generate_thumbnail_concept(plan: VideoPlan, final_title: str) -> str:
    """
    Generates thumbnail concept description.

    Args:
        plan: Video plan for context
        final_title: Final optimized title

    Returns:
        Thumbnail concept description
    """
    # Extract key phrase from title (first 3-4 words or until punctuation)
    title_words = final_title.split()
    key_phrase_words = []
    for word in title_words[:4]:
        key_phrase_words.append(word)
        if word.endswith((':', '!', '?', '-')):
            break

    key_phrase = " ".join(key_phrase_words).rstrip(':!?-')

    # Create thumbnail concept
    concept = (
        f"Thumbnail verticale 9:16 con testo grande e leggibile: '{key_phrase}' "
        f"in caratteri GIALLI o BIANCHI su sfondo scuro ad alto contrasto. "
        f"Visual: immagine dinamica relativa a {plan.working_title} che cattura attenzione. "
        f"Espressione o elemento visivo che crea curiosità. "
        f"Stile moderno, professionale, ottimizzato per mobile. "
        f"Emozione: sorpresa o urgenza."
    )

    return concept


def generate_publishing_package(
    plan: VideoPlan,
    script: VideoScript
) -> PublishingPackage:
    """
    Generates complete publishing metadata package for YouTube.

    This is the entry point for the SeoManager agent. It creates:
    - CTR-optimized title (max 100 chars)
    - SEO-rich description with keywords and CTAs
    - Relevant tags for discoverability (max 500 chars total)
    - Thumbnail concept for visual appeal
    - Placeholder affiliate links

    Args:
        plan: Video plan with topic and context
        script: Complete video script

    Returns:
        PublishingPackage ready for upload

    Raises:
        ValueError: If plan or script is invalid
    """
    if not plan.working_title:
        raise ValueError("Cannot generate publishing package: plan has no working_title")

    if not script.full_voiceover_text:
        raise ValueError("Cannot generate publishing package: script has no voiceover text")

    logger.info(f"SeoManager optimizing metadata for: '{plan.working_title}'")

    # Generate components
    final_title = _optimize_title_for_ctr(plan)
    description = _generate_description(plan, script)
    tags = _extract_tags(plan, script)
    thumbnail_concept = _generate_thumbnail_concept(plan, final_title)

    # Placeholder affiliate links (to be replaced with real links in future)
    affiliate_links = [
        "https://example.com/recommended-product?ref=channel",
        # Add more links based on video topic in real implementation
    ]

    # Create PublishingPackage
    package = PublishingPackage(
        final_title=final_title,
        description=description,
        tags=tags,
        affiliate_links=affiliate_links,
        thumbnail_concept=thumbnail_concept
    )

    logger.info(
        f"Generated PublishingPackage: title='{final_title[:50]}...', "
        f"{len(tags)} tags, {len(description)} chars description"
    )

    return package
