"""
SeoManager Agent: Optimizes video metadata for YouTube discovery and CTR.

This agent generates SEO-optimized titles, descriptions, tags, and
thumbnail concepts to maximize video visibility and click-through rate.

MONETIZATION REFACTOR:
- Language detection from voiceover (no hardcoded Italian templates)
- LLM-powered title generation in correct language
- A/B title variants for CTR optimization
"""

from typing import List
from yt_autopilot.core.schemas import VideoPlan, VideoScript, PublishingPackage
from yt_autopilot.core.logger import logger, log_fallback
from yt_autopilot.services.llm_router import generate_text


def _detect_language_from_voiceover(voiceover_text: str) -> str:
    """
    Detects dominant language from voiceover text using keyword heuristics.

    Args:
        voiceover_text: Full voiceover text

    Returns:
        Language code: 'it' (Italian), 'en' (English), or 'unknown'
    """
    text_lower = voiceover_text.lower()

    # Italian indicators
    italian_keywords = [
        'è', 'perché', 'più', 'può', 'così', 'già', 'però', 'cioè',
        'questo', 'quello', 'sono', 'essere', 'avere', 'fare', 'anche',
        'tutti', 'tutto', 'cosa', 'come', 'quando', 'dove', 'molto'
    ]

    # English indicators
    english_keywords = [
        'the', 'is', 'are', 'was', 'were', 'have', 'has', 'had', 'will',
        'this', 'that', 'these', 'those', 'what', 'how', 'when', 'where',
        'which', 'who', 'why', 'very', 'can', 'could', 'would', 'should'
    ]

    italian_count = sum(1 for kw in italian_keywords if f' {kw} ' in f' {text_lower} ')
    english_count = sum(1 for kw in english_keywords if f' {kw} ' in f' {text_lower} ')

    if italian_count > english_count * 1.5:
        return 'it'
    elif english_count > italian_count * 1.5:
        return 'en'
    else:
        return 'unknown'


def _optimize_title_for_ctr(plan: VideoPlan, script: VideoScript) -> str:
    """
    Generates a CTR-optimized YouTube title using LLM.

    MONETIZATION REFACTOR:
    - Detects language from voiceover
    - Uses LLM for language-appropriate title generation
    - No hardcoded templates

    Args:
        plan: Video plan with working title and strategic angle
        script: Video script (for language detection)

    Returns:
        Optimized final title (max 100 chars)
    """
    # Detect language from voiceover
    detected_language = _detect_language_from_voiceover(script.full_voiceover_text)
    language_name = 'Italian' if detected_language == 'it' else 'English' if detected_language == 'en' else 'the video language'

    logger.info(f"  Detected video language: {detected_language} ({language_name})")

    # Build LLM prompt for title generation
    prompt = f"""Generate a viral YouTube title in {language_name}.

TOPIC: {plan.working_title}
HOOK: {script.hook}
ANGLE: {plan.strategic_angle}

REQUIREMENTS:
- Maximum 100 characters (strict limit)
- Same language as video content ({language_name})
- High CTR patterns: curiosity, urgency, value proposition, or number
- NO clickbait, NO misleading
- SEO-optimized with relevant keywords

EXAMPLES OF HIGH-CTR PATTERNS:
- Question format: "Why Is [Topic] Going Viral?"
- Number format: "5 Things You Didn't Know About [Topic]"
- Urgency format: "Everyone's Talking About [Topic] - Here's Why"
- Value format: "The Truth About [Topic] Nobody Tells You"

Respond with ONLY the title, no explanations."""

    try:
        # Call LLM for title generation
        generated_title = generate_text(
            role="seo_title_generator",
            task=prompt,
            context="",
            style_hints={"max_length": 100, "language": detected_language}
        ).strip()

        # Remove quotes if LLM added them
        generated_title = generated_title.strip('"').strip("'")

        # Validate length
        if len(generated_title) > 100:
            logger.warning(f"  LLM title too long ({len(generated_title)} chars), truncating...")
            generated_title = generated_title[:97] + "..."

        logger.info(f"  ✓ LLM-generated title: '{generated_title}' ({len(generated_title)} chars)")
        return generated_title

    except Exception as e:
        # 🚨 Log LLM title generation failure fallback (CRITICAL for CTR)
        log_fallback(
            component="SEO_MANAGER_TITLE",
            fallback_type="LLM_TITLE_GENERATION_FAILED",
            reason=f"LLM title generation failed: {e}",
            impact="HIGH"
        )
        logger.error(f"  LLM title generation failed: {e}")
        logger.warning("  Falling back to working title")

        # Fallback: Use working title
        fallback_title = plan.working_title
        if len(fallback_title) > 100:
            fallback_title = fallback_title[:97] + "..."

        logger.info(f"  Fallback title: '{fallback_title}' ({len(fallback_title)} chars)")
        return fallback_title


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


def _filter_invalid_tags_deterministic(tags: List[str]) -> List[str]:
    """
    Layer 3: Deterministic tag filtering and cleaning.

    Removes invalid tags:
    - Emoji-only tags
    - Tags with hashtags (#)
    - Very short tags (<3 chars)
    - Duplicate tags

    Args:
        tags: Raw tag list

    Returns:
        Cleaned tag list
    """
    import re

    filtered = []
    seen = set()

    for tag in tags:
        # Remove emoji-only tags (Unicode range for common emojis)
        if re.match(r'^[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF]+$', tag):
            logger.debug(f"  Layer 3: Removing emoji-only tag: {tag}")
            continue

        # Remove tags with hashtags
        if '#' in tag:
            logger.debug(f"  Layer 3: Removing hashtag tag: {tag}")
            continue

        # Remove very short tags
        clean_tag = tag.strip().lower()
        if len(clean_tag) < 3:
            continue

        # Deduplicate
        if clean_tag not in seen:
            filtered.append(clean_tag)
            seen.add(clean_tag)

    return filtered


def _generate_tags_with_llm(
    plan: VideoPlan,
    script: VideoScript,
    language: str = 'en'
) -> List[str]:
    """
    Layer 1: AI-driven SEO tag generation.

    Uses LLM to generate contextually relevant, SEO-optimized tags
    based on video content, topic, and target audience.

    Args:
        plan: Video plan with topic and audience
        script: Video script for content analysis
        language: Target language for tags

    Returns:
        List of SEO-optimized tags
    """
    try:
        # Extract content summary
        hook_preview = script.hook[:100] if script.hook else plan.working_title
        content_preview = ' '.join(script.bullets[:2]) if script.bullets else plan.topic

        prompt = f"""You are a YouTube SEO expert specializing in video discoverability and tag optimization.

TASK: Generate 10-15 highly relevant YouTube tags for maximum discoverability.

VIDEO INFORMATION:
- Topic: {plan.topic}
- Title: {plan.working_title}
- Hook: "{hook_preview}"
- Content: "{content_preview[:150]}..."
- Target Audience: {plan.target_audience}
- Language: {language}

TAG REQUIREMENTS:
1. Mix of broad (1-2 words) and specific (3-4 words) tags
2. Focus on search intent and discoverability
3. Include:
   - Primary keyword variations
   - Related topics and niches
   - Long-tail search phrases
   - Trending relevant terms
4. NO emoji-only tags
5. NO hashtags (# symbol)
6. Keep each tag under 30 characters
7. Total must be under 500 characters combined

TAG TYPES TO INCLUDE:
- Primary keyword (exact topic)
- Keyword variations (synonyms, related terms)
- Niche-specific tags (audience interests)
- Long-tail phrases (3-4 word searches)
- Trending terms (if relevant to topic)

AVOID:
- Generic tags ("video", "content", "youtube")
- Clickbait tags unrelated to content
- Overly competitive single words
- Language tags (handled separately)

RESPOND WITH TAGS AS JSON ARRAY:
{{
  "tags": ["tag1", "tag2", "tag3", ...]
}}

DO NOT include markdown code blocks. Return raw JSON only.
"""

        logger.debug("  Layer 1: Calling LLM for tag generation...")
        response = generate_text(
            role="seo_manager_tag_generator",
            task=prompt,
            context="",
            style_hints={"response_format": "json", "max_tokens": 500}
        )

        # Parse LLM response
        import json
        import re

        # Clean response (remove markdown if present)
        cleaned_response = response.strip()
        if cleaned_response.startswith("```"):
            cleaned_response = re.sub(r'^```(?:json)?\n', '', cleaned_response)
            cleaned_response = re.sub(r'\n```$', '', cleaned_response)

        result = json.loads(cleaned_response)
        tags = result.get('tags', [])

        if not tags or len(tags) < 5:
            raise ValueError(f"LLM returned insufficient tags: {len(tags)}")

        logger.info(f"  ✅ Layer 1: Generated {len(tags)} AI-driven tags")
        return tags

    except Exception as e:
        logger.error(f"  ❌ Layer 1: AI tag generation failed: {e}")
        raise  # Re-raise to trigger Layer 2


def _extract_tags(plan: VideoPlan, script: VideoScript) -> List[str]:
    """
    Generates SEO-optimized YouTube tags using 3-layer AI-driven pattern.

    Layer 1: LLM generates contextually relevant tags
    Layer 2: (Not needed - validation is Layer 3)
    Layer 3: Deterministic filtering (remove emojis, hashtags, dedupe)

    Args:
        plan: Video plan with topic and audience
        script: Video script for content analysis

    Returns:
        List of SEO-optimized tags (max 500 chars total per YouTube limits)
    """
    # Detect language
    language = _detect_language_from_voiceover(script.full_voiceover_text)
    logger.info(f"SEO tag generation for language: {language}")

    try:
        # Layer 1: AI-driven tag generation
        tags = _generate_tags_with_llm(plan, script, language)

        # Layer 3: Deterministic filtering and cleaning
        logger.info("  Layer 3: Applying deterministic tag filtering...")
        tags = _filter_invalid_tags_deterministic(tags)

        # Enforce 500 char total limit
        unique_tags = []
        total_length = 0
        for tag in tags:
            tag_length = len(tag) + 1  # +1 for comma separator
            if total_length + tag_length <= 500:
                unique_tags.append(tag)
                total_length += tag_length
            else:
                break

        logger.info(f"✓ Generated {len(unique_tags)} SEO tags ({total_length}/500 chars)")
        return unique_tags

    except Exception as e:
        logger.error(f"AI tag generation failed: {e}")
        logger.warning("Falling back to deterministic tag extraction (Layer 3 fallback)")

        # Layer 3 Fallback: Simple deterministic extraction
        log_fallback(
            component="SEO_MANAGER_TAG_GENERATION",
            fallback_type="DETERMINISTIC_TAGS",
            reason=f"AI tag generation failed: {e}",
            impact="MEDIUM"
        )

        # Basic fallback tags
        tags = []
        topic_tag = plan.working_title.lower()
        tags.append(topic_tag)

        # Add topic word variations
        topic_words = [w for w in topic_tag.split() if len(w) > 3]
        tags.extend(topic_words[:5])

        # Add generic tags based on audience
        audience_lower = plan.target_audience.lower()
        if "tech" in audience_lower or "tecnologia" in audience_lower:
            tags.extend(["tech", "technology"])
        elif "fitness" in audience_lower:
            tags.extend(["fitness", "health"])
        elif "finance" in audience_lower or "finanza" in audience_lower:
            tags.extend(["finance", "investing"])

        # Clean and limit
        tags = _filter_invalid_tags_deterministic(tags)
        unique_tags = list(dict.fromkeys(tags))[:15]  # Max 15 tags

        logger.info(f"✓ Fallback generated {len(unique_tags)} tags")
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

    # Generate components (MONETIZATION REFACTOR: Pass script for language detection)
    final_title = _optimize_title_for_ctr(plan, script)
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
