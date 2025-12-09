"""
Product Positioner Agent - Determine how to position product in articles.

Analyzes article structure and suggests specific insertion strategies.
"""

from typing import Dict, Optional, Callable

from pr_outreach.core.schemas import (
    ArticleCandidate,
    ProductInfo,
    PositioningStrategy,
    InsertionType
)
from yt_autopilot.core.logger import logger, log_fallback


def position_product(
    article: ArticleCandidate,
    product: ProductInfo,
    llm_generate_fn: Optional[Callable] = None
) -> PositioningStrategy:
    """
    Determine optimal positioning for product in article.

    Args:
        article: Target article
        product: Product to position
        llm_generate_fn: LLM function for intelligent positioning

    Returns:
        PositioningStrategy with detailed insertion plan
    """
    logger.info(f"Positioning {product.name} in: {article.title[:50]}...")

    if llm_generate_fn and article.full_content:
        strategy = _position_with_llm(article, product, llm_generate_fn)
    else:
        strategy = _position_with_heuristics(article, product)

    logger.info(f"  Strategy: {strategy.insertion_type.value}")
    logger.info(f"  Target section: {strategy.target_section[:50]}...")

    return strategy


def _position_with_llm(
    article: ArticleCandidate,
    product: ProductInfo,
    llm_generate_fn: Callable
) -> PositioningStrategy:
    """Use LLM for intelligent positioning."""
    prompt = f"""You are a PR strategist helping position a product in an article.

PRODUCT:
- Name: {product.name}
- Tagline: {product.tagline}
- Category: {product.category}
- Key Features: {', '.join(product.key_features[:3])}
- Unique Value: {product.unique_value_prop}
- Target Audience: {product.target_audience}

ARTICLE:
- Title: {article.title}
- Domain: {article.domain} (Authority: {article.domain_authority}/100)
- Current insertion opportunities identified: {article.insertion_opportunities}

Article Content (first 4000 chars):
{article.full_content[:4000] if article.full_content else article.content_excerpt}

TASK:
Create a specific positioning strategy. Be concrete and helpful.

1. INSERTION_TYPE: Choose the best approach
   - listicle_addition: Add to existing list
   - mention_opportunity: Natural mention in text
   - comparison_inclusion: Add to comparison
   - resource_link: Add as resource/tool
   - update_existing: Suggest content update

2. TARGET_SECTION: Which specific section of the article to target
   (Quote or describe the section)

3. POSITIONING_RATIONALE: Why the product belongs here (2-3 sentences)
   Focus on VALUE TO READERS, not self-promotion

4. SUGGESTED_TEXT: Write the exact text/description that should be added
   (Keep it factual, valuable, non-promotional)

5. VALUE_TO_READERS: How this addition helps the article's readers

Respond in this exact format:
INSERTION_TYPE: [type]
TARGET_SECTION: [section description]
POSITIONING_RATIONALE: [why it belongs]
SUGGESTED_TEXT: [exact text to add]
VALUE_TO_READERS: [reader benefit]"""

    try:
        response = llm_generate_fn(
            role="pr_strategist",
            task=prompt,
            context="",
            style_hints={"tone": "professional", "focus": "value_first"}
        )

        return _parse_positioning_response(response, article, product)

    except Exception as e:
        logger.warning(f"LLM positioning failed: {e}")
        log_fallback(
            component="PRODUCT_POSITIONER",
            fallback_type="LLM_POSITIONING_FAILED",
            reason=str(e),
            impact="MEDIUM"
        )
        return _position_with_heuristics(article, product)


def _position_with_heuristics(
    article: ArticleCandidate,
    product: ProductInfo
) -> PositioningStrategy:
    """Create positioning strategy using heuristics."""
    insertion_type = article.insertion_type or InsertionType.MENTION_OPPORTUNITY

    # Determine target section based on insertion type
    if insertion_type == InsertionType.LISTICLE_ADDITION:
        target_section = "Main list section where similar tools/products are mentioned"
        rationale = f"{product.name} fits naturally alongside other {product.category} options in this listicle, offering readers another valuable alternative to consider."
        suggested_text = f"**{product.name}** - {product.tagline}. Key features include {', '.join(product.key_features[:2])}. {product.unique_value_prop}"

    elif insertion_type == InsertionType.COMPARISON_INCLUSION:
        target_section = "Comparison table or comparison section"
        rationale = f"Adding {product.name} to this comparison gives readers a more complete picture of available {product.category} options."
        suggested_text = f"{product.name}: {product.tagline}. Strengths include {product.key_features[0] if product.key_features else 'innovative approach'}."

    elif insertion_type == InsertionType.RESOURCE_LINK:
        target_section = "Resources, tools, or further reading section"
        rationale = f"{product.name} would be a valuable addition to the resources section, helping readers discover a useful {product.category}."
        suggested_text = f"[{product.name}]({product.website_url}) - {product.tagline}"

    elif insertion_type == InsertionType.UPDATE_EXISTING:
        target_section = "Outdated section that could benefit from new information"
        rationale = f"This article could benefit from including {product.name}, which offers {product.unique_value_prop} - something readers are increasingly looking for."
        suggested_text = f"Update: {product.name} has emerged as a notable {product.category}, offering {product.unique_value_prop}."

    else:  # MENTION_OPPORTUNITY
        target_section = "Section discussing similar topics or solutions"
        rationale = f"{product.name} is relevant to this article's topic and would provide additional value to readers interested in {product.category}."
        suggested_text = f"Tools like {product.name} ({product.tagline}) are making this easier for {product.target_audience}."

    value_to_readers = f"Readers will discover {product.name}, which offers {product.unique_value_prop}. This gives them another option to consider for their {product.category} needs."

    return PositioningStrategy(
        insertion_type=insertion_type,
        target_section=target_section,
        positioning_rationale=rationale,
        suggested_text=suggested_text,
        value_to_readers=value_to_readers,
        reasoning=f"Heuristic positioning based on article type: {insertion_type.value}"
    )


def _parse_positioning_response(
    response: str,
    article: ArticleCandidate,
    product: ProductInfo
) -> PositioningStrategy:
    """Parse LLM response into PositioningStrategy."""
    result = {
        "insertion_type": article.insertion_type or InsertionType.MENTION_OPPORTUNITY,
        "target_section": "General content section",
        "positioning_rationale": f"{product.name} is relevant to this article's topic.",
        "suggested_text": f"{product.name} - {product.tagline}",
        "value_to_readers": f"Readers will discover a useful {product.category}.",
        "reasoning": ""
    }

    current_field = None
    current_content = []

    lines = response.strip().split("\n")

    for line in lines:
        line = line.strip()

        if line.startswith("INSERTION_TYPE:"):
            if current_field and current_content:
                result[current_field] = " ".join(current_content)
            current_field = "insertion_type"
            type_str = line.replace("INSERTION_TYPE:", "").strip().lower()
            try:
                result["insertion_type"] = InsertionType(type_str)
            except ValueError:
                pass
            current_content = []

        elif line.startswith("TARGET_SECTION:"):
            if current_field and current_content:
                result[current_field] = " ".join(current_content)
            current_field = "target_section"
            current_content = [line.replace("TARGET_SECTION:", "").strip()]

        elif line.startswith("POSITIONING_RATIONALE:"):
            if current_field and current_content:
                result[current_field] = " ".join(current_content)
            current_field = "positioning_rationale"
            current_content = [line.replace("POSITIONING_RATIONALE:", "").strip()]

        elif line.startswith("SUGGESTED_TEXT:"):
            if current_field and current_content:
                result[current_field] = " ".join(current_content)
            current_field = "suggested_text"
            current_content = [line.replace("SUGGESTED_TEXT:", "").strip()]

        elif line.startswith("VALUE_TO_READERS:"):
            if current_field and current_content:
                result[current_field] = " ".join(current_content)
            current_field = "value_to_readers"
            current_content = [line.replace("VALUE_TO_READERS:", "").strip()]

        elif current_field and line:
            current_content.append(line)

    # Save last field
    if current_field and current_content:
        result[current_field] = " ".join(current_content)

    return PositioningStrategy(
        insertion_type=result["insertion_type"],
        target_section=result["target_section"],
        positioning_rationale=result["positioning_rationale"],
        suggested_text=result["suggested_text"],
        value_to_readers=result["value_to_readers"],
        reasoning="LLM-generated positioning strategy"
    )


def get_positioning_summary(strategy: PositioningStrategy) -> str:
    """Generate a brief summary of the positioning strategy."""
    return f"""
Positioning Strategy:
- Type: {strategy.insertion_type.value}
- Target: {strategy.target_section[:100]}...
- Rationale: {strategy.positioning_rationale[:200]}...
- Reader Value: {strategy.value_to_readers[:150]}...
""".strip()
