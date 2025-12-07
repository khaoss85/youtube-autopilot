"""
Email Writer Agent - Generate personalized outreach emails.

Similar to ScriptWriter in youtube-autopilot.
Creates compelling, human-like outreach emails.
"""

from typing import Dict, Optional, Callable

from pr_outreach.core.schemas import (
    ArticleCandidate,
    AuthorProfile,
    ProductInfo,
    PositioningStrategy,
    OutreachDecision,
    OutreachEmail,
    SenderPersona,
    CampaignConfig
)
from yt_autopilot.core.logger import logger, log_fallback


def write_outreach_email(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    strategy: OutreachDecision,
    campaign_config: CampaignConfig,
    llm_generate_fn: Optional[Callable] = None
) -> OutreachEmail:
    """
    Write a personalized outreach email.

    Args:
        article: Target article
        author: Author profile
        product: Product to promote
        positioning: Positioning strategy
        strategy: Outreach strategy
        campaign_config: Campaign configuration
        llm_generate_fn: LLM function for generation

    Returns:
        OutreachEmail with all components
    """
    logger.info(f"Writing email to: {author.name}")

    sender = campaign_config.sender_persona

    if llm_generate_fn:
        email = _write_with_llm(
            article, author, product, positioning, strategy, sender, llm_generate_fn
        )
    else:
        email = _write_with_templates(
            article, author, product, positioning, strategy, sender
        )

    # Calculate metadata
    email.word_count = len(email.full_body.split())
    email.reading_time_seconds = email.word_count // 3  # ~200 wpm

    logger.info(f"  Subject: {email.subject_line}")
    logger.info(f"  Word count: {email.word_count}")

    return email


def _write_with_llm(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    strategy: OutreachDecision,
    sender: SenderPersona,
    llm_generate_fn: Callable
) -> OutreachEmail:
    """Generate email using LLM."""
    prompt = f"""Write a PR outreach email following these specifications.

RECIPIENT:
- Name: {author.name}
- Job Title: {author.job_title or 'Writer'}
- Their Article: "{article.title}"
- Article URL: {article.url}
- Writing Style: {author.writing_style or 'Professional'}
- Topics They Cover: {', '.join(author.topics_covered[:3]) if author.topics_covered else 'Various'}

PRODUCT TO PROMOTE:
- Name: {product.name}
- Tagline: {product.tagline}
- Key Features: {', '.join(product.key_features[:3])}
- Unique Value: {product.unique_value_prop}
- Website: {product.website_url}

POSITIONING:
- Insertion Type: {positioning.insertion_type.value}
- Target Section: {positioning.target_section[:200]}
- Rationale: {positioning.positioning_rationale}
- Suggested Text: {positioning.suggested_text[:300]}
- Value to Readers: {positioning.value_to_readers}

STRATEGY:
- Angle: {strategy.email_angle.value}
- Personalization: {strategy.personalization_level}
- CTA Type: {strategy.cta_type}
- Tone: {strategy.tone}

SENDER:
- Name: {sender.name}
- Title: {sender.title}
- Company: {sender.company}
- Preferred Greetings: {', '.join(sender.preferred_greetings)}
- Preferred Closings: {', '.join(sender.preferred_closings)}

REQUIREMENTS:
1. Be genuinely helpful, not salesy
2. Keep it short (under 150 words for body)
3. Reference their specific article
4. Explain value to THEIR readers, not just product benefits
5. Soft CTA - make it easy to say yes or no
6. Sound human, not templated
7. No excessive flattery or buzzwords

Write the email in this format:
SUBJECT: [subject line - max 50 chars, no spam words]
SUBJECT_ALT: [alternative subject for A/B testing]

OPENING: [personalized opening line referencing their work]

CONNECTION: [why you're reaching out, the connection to their article]

VALUE_PROP: [what's in it for them/their readers - be specific]

SUGGESTION: [specific, helpful suggestion for how to include product]

CTA: [soft, non-pushy call to action]

PS: [optional P.S. line - conversational, adds personality]

SIGNATURE:
{sender.name}
{sender.title}, {sender.company}"""

    try:
        response = llm_generate_fn(
            role="email_writer",
            task=prompt,
            context="",
            style_hints={"tone": strategy.tone, "brevity": "high"}
        )

        return _parse_email_response(response, sender)

    except Exception as e:
        logger.warning(f"LLM email generation failed: {e}")
        log_fallback(
            component="EMAIL_WRITER",
            fallback_type="LLM_EMAIL_FAILED",
            reason=str(e),
            impact="HIGH"
        )
        return _write_with_templates(
            article, author, product, positioning, strategy, sender
        )


def _write_with_templates(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    strategy: OutreachDecision,
    sender: SenderPersona
) -> OutreachEmail:
    """Generate email using templates."""
    first_name = author.name.split()[0] if author.name else "there"
    greeting = sender.preferred_greetings[0] if sender.preferred_greetings else "Hi"
    closing = sender.preferred_closings[0] if sender.preferred_closings else "Best"

    # Subject based on strategy
    if strategy.email_angle.value == "direct_pitch":
        subject = f"Quick suggestion for your {product.category} article"
    elif strategy.email_angle.value == "update_request":
        subject = f"Thought for updating your {product.category} piece"
    elif strategy.email_angle.value == "resource_offer":
        subject = f"Resource for your readers on {product.category}"
    else:
        subject = f"Idea for your {article.title[:30]} article"

    # Opening
    opening = f"{greeting} {first_name},"

    # Connection
    connection = f"I came across your article \"{article.title}\" and thought it was a great resource for anyone looking into {product.category}."

    # Value proposition
    value_prop = f"I'm reaching out because I think your readers might find {product.name} helpful - {positioning.value_to_readers}"

    # Suggestion
    suggestion = f"If you're ever updating the article, {product.name} could be a good addition: {positioning.suggested_text[:200]}"

    # CTA
    if strategy.cta_type == "update_article":
        cta = "Would you be open to considering it for a future update?"
    elif strategy.cta_type == "send_info":
        cta = "Happy to send over more details if helpful!"
    else:
        cta = "Just wanted to put it on your radar - no pressure at all."

    # Full body
    full_body = f"""{opening}

{connection}

{value_prop}

{suggestion}

{cta}

{closing},
{sender.name}
{sender.title}, {sender.company}"""

    # P.S.
    ps_line = f"P.S. Big fan of your work on {author.topics_covered[0] if author.topics_covered else 'tech'} topics!"

    # Signature
    signature = f"""{sender.name}
{sender.title}, {sender.company}"""

    return OutreachEmail(
        subject_line=subject,
        subject_line_alt=f"Quick thought on {article.title[:30]}...",
        opening_hook=f"{opening}\n\n{connection}",
        connection_point=connection,
        value_proposition=value_prop,
        insertion_suggestion=suggestion,
        call_to_action=cta,
        full_body=full_body,
        ps_line=ps_line,
        signature=signature
    )


def _parse_email_response(response: str, sender: SenderPersona) -> OutreachEmail:
    """Parse LLM response into OutreachEmail."""
    result = {
        "subject_line": "Quick thought on your article",
        "subject_line_alt": None,
        "opening_hook": "",
        "connection_point": "",
        "value_proposition": "",
        "insertion_suggestion": "",
        "call_to_action": "",
        "full_body": "",
        "ps_line": None,
        "signature": f"{sender.name}\n{sender.title}, {sender.company}"
    }

    current_field = None
    current_content = []

    lines = response.strip().split("\n")

    for line in lines:
        line_stripped = line.strip()

        if line_stripped.startswith("SUBJECT:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = None
            result["subject_line"] = line_stripped.replace("SUBJECT:", "").strip()
            current_content = []

        elif line_stripped.startswith("SUBJECT_ALT:"):
            result["subject_line_alt"] = line_stripped.replace("SUBJECT_ALT:", "").strip()

        elif line_stripped.startswith("OPENING:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = "opening_hook"
            current_content = [line_stripped.replace("OPENING:", "").strip()]

        elif line_stripped.startswith("CONNECTION:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = "connection_point"
            current_content = [line_stripped.replace("CONNECTION:", "").strip()]

        elif line_stripped.startswith("VALUE_PROP:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = "value_proposition"
            current_content = [line_stripped.replace("VALUE_PROP:", "").strip()]

        elif line_stripped.startswith("SUGGESTION:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = "insertion_suggestion"
            current_content = [line_stripped.replace("SUGGESTION:", "").strip()]

        elif line_stripped.startswith("CTA:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = "call_to_action"
            current_content = [line_stripped.replace("CTA:", "").strip()]

        elif line_stripped.startswith("PS:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = None
            result["ps_line"] = line_stripped.replace("PS:", "").strip()
            current_content = []

        elif line_stripped.startswith("SIGNATURE:"):
            if current_field and current_content:
                result[current_field] = "\n".join(current_content).strip()
            current_field = "signature"
            current_content = []

        elif current_field and line_stripped:
            current_content.append(line_stripped)

    # Save last field
    if current_field and current_content:
        result[current_field] = "\n".join(current_content).strip()

    # Build full body
    parts = []
    if result["opening_hook"]:
        parts.append(result["opening_hook"])
    if result["connection_point"] and result["connection_point"] not in result["opening_hook"]:
        parts.append(result["connection_point"])
    if result["value_proposition"]:
        parts.append(result["value_proposition"])
    if result["insertion_suggestion"]:
        parts.append(result["insertion_suggestion"])
    if result["call_to_action"]:
        parts.append(result["call_to_action"])

    body = "\n\n".join(parts)

    if result["ps_line"]:
        body += f"\n\n{result['ps_line']}"

    body += f"\n\n{result['signature']}"

    result["full_body"] = body

    return OutreachEmail(**result)


def get_email_preview(email: OutreachEmail) -> str:
    """Generate a preview of the email."""
    preview = f"""
**Subject:** {email.subject_line}

**Body:**
{email.full_body}

---
Word count: {email.word_count}
Reading time: ~{email.reading_time_seconds}s
""".strip()

    if email.subject_line_alt:
        preview = f"**Alt Subject:** {email.subject_line_alt}\n\n{preview}"

    return preview
