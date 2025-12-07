"""
Outreach Strategist Agent - Decide outreach approach.

Similar to EditorialStrategist in youtube-autopilot.
Determines email angle, personalization level, and CTA type.
"""

from typing import Dict, Optional, Callable

from pr_outreach.core.schemas import (
    ArticleCandidate,
    AuthorProfile,
    ProductInfo,
    PositioningStrategy,
    OutreachDecision,
    EmailAngle,
    CampaignConfig
)
from yt_autopilot.core.logger import logger, log_fallback


def decide_outreach_strategy(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    campaign_config: CampaignConfig,
    llm_generate_fn: Optional[Callable] = None
) -> OutreachDecision:
    """
    Decide the optimal outreach strategy.

    Args:
        article: Target article
        author: Author profile
        product: Product to promote
        positioning: Positioning strategy
        campaign_config: Campaign configuration
        llm_generate_fn: LLM function for strategy

    Returns:
        OutreachDecision with strategy details
    """
    logger.info(f"Deciding outreach strategy for: {article.title[:50]}...")

    if llm_generate_fn:
        strategy = _decide_with_llm(
            article, author, product, positioning, campaign_config, llm_generate_fn
        )
    else:
        strategy = _decide_with_heuristics(
            article, author, product, positioning, campaign_config
        )

    logger.info(f"  Angle: {strategy.email_angle.value}")
    logger.info(f"  Personalization: {strategy.personalization_level}")
    logger.info(f"  CTA: {strategy.cta_type}")

    return strategy


def _decide_with_llm(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    campaign_config: CampaignConfig,
    llm_generate_fn: Callable
) -> OutreachDecision:
    """Use LLM to decide outreach strategy."""
    prompt = f"""You are an expert PR strategist. Decide the best approach for this outreach.

CONTEXT:
- Article: "{article.title}" on {article.domain}
- Author: {author.name} ({author.job_title or 'Writer'})
- Author writing style: {author.writing_style or 'Unknown'}
- Product: {product.name} - {product.tagline}
- Insertion opportunity: {positioning.insertion_type.value}

AUTHOR ANALYSIS:
- Has verified email: {author.email_verified}
- Topics they cover: {', '.join(author.topics_covered[:3]) if author.topics_covered else 'Unknown'}
- Bio: {author.bio[:200] if author.bio else 'Not available'}

CAMPAIGN TONE: {campaign_config.email_tone}

TASK:
Choose the best outreach approach:

1. EMAIL_ANGLE: Choose one
   - direct_pitch: Straightforward product mention request
   - value_first: Lead with value you can provide (data, quote, resource)
   - relationship_building: Build connection before asking
   - update_request: Suggest updating outdated content
   - resource_offer: Offer helpful resource

2. PERSONALIZATION_LEVEL: low, medium, or high
   - Low: Generic, template-based
   - Medium: References article, some customization
   - High: Deep personalization, references author's work

3. CTA_TYPE: What action to request
   - update_article: Ask them to add product to article
   - consider_inclusion: Soft ask to consider for future
   - schedule_call: Request a brief call
   - send_info: Offer to send more information
   - feedback_request: Ask for their opinion

4. TONE: formal, friendly_professional, or casual

5. URGENCY: low, medium, or high

6. FOLLOW_UP: none, single_followup, or sequence

Respond in this format:
EMAIL_ANGLE: [angle]
PERSONALIZATION_LEVEL: [level]
CTA_TYPE: [cta]
TONE: [tone]
URGENCY: [urgency]
FOLLOW_UP: [strategy]
REASONING: [2-3 sentences explaining your choices]"""

    try:
        response = llm_generate_fn(
            role="pr_strategist",
            task=prompt,
            context="",
            style_hints={}
        )

        return _parse_strategy_response(response)

    except Exception as e:
        logger.warning(f"LLM strategy decision failed: {e}")
        log_fallback(
            component="OUTREACH_STRATEGIST",
            fallback_type="LLM_STRATEGY_FAILED",
            reason=str(e),
            impact="MEDIUM"
        )
        return _decide_with_heuristics(
            article, author, product, positioning, campaign_config
        )


def _decide_with_heuristics(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    campaign_config: CampaignConfig
) -> OutreachDecision:
    """Decide strategy using heuristics."""

    # Determine email angle based on insertion type
    if positioning.insertion_type.value == "listicle_addition":
        email_angle = EmailAngle.DIRECT_PITCH
        cta_type = "update_article"
    elif positioning.insertion_type.value == "update_existing":
        email_angle = EmailAngle.UPDATE_REQUEST
        cta_type = "update_article"
    elif positioning.insertion_type.value == "resource_link":
        email_angle = EmailAngle.RESOURCE_OFFER
        cta_type = "consider_inclusion"
    else:
        email_angle = EmailAngle.VALUE_FIRST
        cta_type = "consider_inclusion"

    # Personalization based on author info
    if author.bio and author.topics_covered:
        personalization_level = "high"
    elif author.email_verified:
        personalization_level = "medium"
    else:
        personalization_level = "low"

    # Tone from campaign config
    tone = campaign_config.email_tone

    # Urgency based on article recency
    if article.recency_score > 0.8:
        urgency = "medium"  # Recent article, timely
    else:
        urgency = "low"

    # Follow-up based on domain authority
    if article.domain_authority >= 70:
        follow_up = "single_followup"  # High value, worth following up
    else:
        follow_up = "none"

    reasoning = f"Heuristic strategy: {email_angle.value} approach for {positioning.insertion_type.value} opportunity with {personalization_level} personalization."

    return OutreachDecision(
        email_angle=email_angle,
        personalization_level=personalization_level,
        cta_type=cta_type,
        tone=tone,
        urgency_level=urgency,
        follow_up_strategy=follow_up,
        reasoning=reasoning
    )


def _parse_strategy_response(response: str) -> OutreachDecision:
    """Parse LLM response into OutreachDecision."""
    result = {
        "email_angle": EmailAngle.VALUE_FIRST,
        "personalization_level": "medium",
        "cta_type": "consider_inclusion",
        "tone": "friendly_professional",
        "urgency_level": "low",
        "follow_up_strategy": "single_followup",
        "reasoning": ""
    }

    for line in response.strip().split("\n"):
        line = line.strip()

        if line.startswith("EMAIL_ANGLE:"):
            angle_str = line.replace("EMAIL_ANGLE:", "").strip().lower()
            try:
                result["email_angle"] = EmailAngle(angle_str)
            except ValueError:
                pass

        elif line.startswith("PERSONALIZATION_LEVEL:"):
            level = line.replace("PERSONALIZATION_LEVEL:", "").strip().lower()
            if level in ["low", "medium", "high"]:
                result["personalization_level"] = level

        elif line.startswith("CTA_TYPE:"):
            result["cta_type"] = line.replace("CTA_TYPE:", "").strip().lower()

        elif line.startswith("TONE:"):
            result["tone"] = line.replace("TONE:", "").strip().lower()

        elif line.startswith("URGENCY:"):
            urgency = line.replace("URGENCY:", "").strip().lower()
            if urgency in ["low", "medium", "high"]:
                result["urgency_level"] = urgency

        elif line.startswith("FOLLOW_UP:"):
            follow_up = line.replace("FOLLOW_UP:", "").strip().lower()
            if follow_up in ["none", "single_followup", "sequence"]:
                result["follow_up_strategy"] = follow_up

        elif line.startswith("REASONING:"):
            result["reasoning"] = line.replace("REASONING:", "").strip()

    return OutreachDecision(**result)


def get_strategy_summary(strategy: OutreachDecision) -> str:
    """Generate a summary of the outreach strategy."""
    return f"""
Outreach Strategy:
- Angle: {strategy.email_angle.value}
- Personalization: {strategy.personalization_level}
- CTA: {strategy.cta_type}
- Tone: {strategy.tone}
- Urgency: {strategy.urgency_level}
- Follow-up: {strategy.follow_up_strategy}
- Reasoning: {strategy.reasoning}
""".strip()
