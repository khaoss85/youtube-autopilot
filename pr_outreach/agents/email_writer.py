"""
Email Writer Agent - Generate natural, human-like outreach emails.

Philosophy: Real humans write short, direct, slightly imperfect emails.
No templates, no sections, no marketing speak.
"""

import random
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


def _load_product_context(campaign_config: CampaignConfig) -> Optional[str]:
    """
    Load product context from campaign's context module if specified.

    Returns formatted context string for email writer, or None.
    """
    context_module = getattr(campaign_config, 'context_module', None)
    if not context_module:
        return None

    try:
        # Dynamic import of context module
        import importlib
        module = importlib.import_module(context_module)

        # Try to get formatted email context
        if hasattr(module, 'format_for_email_context'):
            return module.format_for_email_context()
        elif hasattr(module, 'ARVO_CONTEXT'):
            # Fallback: build basic context from ARVO_CONTEXT
            ctx = module.ARVO_CONTEXT
            return f"""
PRODOTTO: {ctx['snapshot']['name']}
UVP: {ctx['uvp']['primary']}
TARGET: {ctx['icp']['primary_segment']}
TONO: {ctx['tone']['style']}
""".strip()
        return None

    except Exception as e:
        logger.warning(f"Failed to load product context: {e}")
        return None


# Variability elements - real humans vary their style
OPENING_STYLES = [
    "casual",      # "Hey {name},"
    "friendly",    # "Hi {name}!"
    "professional" # "Hi {name},"
]

EMAIL_LENGTHS = [
    "ultra_short",  # 3-4 sentences
    "short",        # 5-6 sentences
    "medium"        # 7-8 sentences max
]


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
    Write a natural, human-like outreach email.

    Key principles:
    - Short and direct (under 100 words ideal)
    - No marketing buzzwords
    - Genuine value, not flattery
    - Easy to skim in 10 seconds
    """
    logger.info(f"Writing email to: {author.name}")

    sender = campaign_config.sender_persona

    # Load product context if available
    product_context = _load_product_context(campaign_config)
    if product_context:
        logger.info("  Loaded product context for email generation")

    # Add variability - don't use same style every time
    style_hints = {
        "opening_style": random.choice(OPENING_STYLES),
        "length": random.choice(EMAIL_LENGTHS),
        "include_ps": random.random() > 0.6,  # 40% chance of P.S.
    }

    if llm_generate_fn:
        email = _write_natural_email(
            article, author, product, positioning,
            strategy, sender, style_hints, llm_generate_fn,
            product_context=product_context
        )
    else:
        email = _write_simple_fallback(
            article, author, product, positioning, strategy, sender
        )

    # Calculate metadata
    email.word_count = len(email.full_body.split())
    email.reading_time_seconds = email.word_count // 3

    logger.info(f"  Subject: {email.subject_line}")
    logger.info(f"  Word count: {email.word_count}")

    return email


def _write_natural_email(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    strategy: OutreachDecision,
    sender: SenderPersona,
    style_hints: Dict,
    llm_generate_fn: Callable,
    product_context: Optional[str] = None
) -> OutreachEmail:
    """Generate a natural email - no rigid templates."""

    first_name = author.name.split()[0] if author.name else ""

    # Build context section if available
    context_section = ""
    if product_context:
        context_section = f"""
---

CONTESTO PRODOTTO (usa per scrivere email informata):
{product_context}

---
"""

    prompt = f"""Scrivi una email di outreach NATURALE e UMANA.

CHI SEI:
{sender.name}, {sender.title} at {sender.company}

A CHI SCRIVI:
{first_name} - ha scritto "{article.title}"

COSA VUOI:
Suggerire {product.name} per il loro articolo.
Motivo: {positioning.value_to_readers}
{context_section}
---

REGOLE FONDAMENTALI:

1. BREVITÀ ESTREMA
   - Massimo {_get_sentence_limit(style_hints['length'])} frasi nel body
   - Se puoi dirlo in meno parole, fallo
   - Niente paragrafi lunghi

2. TONO CONVERSAZIONALE
   - Scrivi come scriveresti a un collega
   - Opening style: {style_hints['opening_style']}
   - Niente "I hope this email finds you well"
   - Niente "I wanted to reach out"

3. ZERO MARKETING SPEAK
   - NO: "game-changing", "innovative", "cutting-edge", "revolutionary"
   - NO: "I'm a big fan of your work" (falso e ovvio)
   - NO: "I thought you might be interested" (presuntuoso)
   - SÌ: linguaggio semplice e diretto

4. VALORE CONCRETO
   - Spiega in 1 frase perché il loro lettore ne beneficerebbe
   - Sii specifico, non generico

5. CTA SOFT
   - Non chiedere troppo
   - "Fammi sapere se ha senso" > "Would you be open to a call?"
   - Rendi facile dire no

6. IMPERFEZIONI NATURALI
   - Okay usare contrazioni ("I'm", "you're", "it's")
   - Okay frasi brevi incomplete occasionalmente
   - Non deve essere grammaticalmente perfetto

{"7. AGGIUNGI UN P.S." if style_hints['include_ps'] else "7. NIENTE P.S. questa volta"}
   {"- Deve essere casual/personale, non sales" if style_hints['include_ps'] else ""}

---

OUTPUT FORMAT (esatto):

SUBJECT: [subject line - max 6 parole, lowercase tranne prima lettera]

BODY:
[email completa qui - greeting, body, closing, firma]

---

ESEMPI DI SUBJECT LINE BUONI:
- Quick thought on your article
- Idea for your {product.category} piece
- Suggestion for {article.title[:20]}...

ESEMPI DI SUBJECT LINE CATTIVI:
- 🚀 Amazing opportunity for you!
- Partnership Proposal - {product.name}
- I loved your article!!!
"""

    try:
        response = llm_generate_fn(
            role="email_writer",
            task=prompt,
            context="",
            style_hints={"natural": True, "brevity": "extreme"}
        )

        return _parse_natural_response(response, sender)

    except Exception as e:
        logger.warning(f"LLM email generation failed: {e}")
        log_fallback(
            component="EMAIL_WRITER",
            fallback_type="LLM_EMAIL_FAILED",
            reason=str(e),
            impact="HIGH"
        )
        return _write_simple_fallback(
            article, author, product, positioning, strategy, sender
        )


def _get_sentence_limit(length: str) -> str:
    """Get sentence limit based on length style."""
    limits = {
        "ultra_short": "3-4",
        "short": "5-6",
        "medium": "7-8"
    }
    return limits.get(length, "5-6")


def _parse_natural_response(response: str, sender: SenderPersona) -> OutreachEmail:
    """Parse natural email response - simple extraction."""

    lines = response.strip().split("\n")
    subject = "Quick thought on your article"
    body_lines = []
    in_body = False

    for line in lines:
        line_stripped = line.strip()

        if line_stripped.upper().startswith("SUBJECT:"):
            subject = line_stripped.split(":", 1)[1].strip()
            # Remove quotes if present
            subject = subject.strip('"\'')

        elif line_stripped.upper().startswith("BODY:"):
            in_body = True
            # Check if body content is on same line
            remainder = line_stripped.split(":", 1)[1].strip() if ":" in line_stripped else ""
            if remainder:
                body_lines.append(remainder)

        elif in_body:
            body_lines.append(line)

    # Clean up body
    full_body = "\n".join(body_lines).strip()

    # If parsing failed, use whole response as body
    if not full_body:
        # Try to extract anything that looks like an email
        full_body = _extract_email_content(response, sender)

    # Extract P.S. if present
    ps_line = None
    if "P.S." in full_body or "PS:" in full_body or "P.S:" in full_body:
        parts = full_body.replace("PS:", "P.S.").replace("P.S:", "P.S.").split("P.S.")
        if len(parts) > 1:
            ps_line = "P.S." + parts[-1].strip()

    return OutreachEmail(
        subject_line=subject,
        subject_line_alt=None,
        opening_hook="",  # Not used in natural style
        connection_point="",
        value_proposition="",
        insertion_suggestion="",
        call_to_action="",
        full_body=full_body,
        ps_line=ps_line,
        signature=f"{sender.name}\n{sender.title}, {sender.company}"
    )


def _extract_email_content(response: str, sender: SenderPersona) -> str:
    """Extract email content from unstructured response."""
    # Remove common LLM artifacts
    content = response

    # Remove markdown code blocks
    if "```" in content:
        parts = content.split("```")
        # Take the part that looks most like an email
        for part in parts:
            if "Hi" in part or "Hey" in part or "@" in part:
                content = part
                break

    # Remove XML-like tags
    import re
    content = re.sub(r'<[^>]+>', '', content)

    # If no signature, add it
    if sender.name not in content:
        content = content.strip() + f"\n\n{sender.name}\n{sender.title}, {sender.company}"

    return content.strip()


def _write_simple_fallback(
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    strategy: OutreachDecision,
    sender: SenderPersona
) -> OutreachEmail:
    """Simple, natural fallback - no LLM needed."""

    first_name = author.name.split()[0] if author.name else "there"

    # Randomize greeting
    greetings = ["Hey", "Hi", "Hi there"]
    greeting = random.choice(greetings)

    # Keep it ultra simple
    subject = f"Quick thought on your {product.category} article"

    # Natural, short body
    body = f"""{greeting} {first_name},

Saw your piece on "{article.title[:50]}". Good stuff.

I work on {product.name} - {product.tagline.lower() if product.tagline else 'a ' + product.category + ' tool'}.

Thought it might be worth mentioning for your readers since {positioning.value_to_readers[:100] if positioning.value_to_readers else 'it fits the topic well'}.

No pressure at all - just wanted to flag it.

{sender.name}
{sender.title}, {sender.company}"""

    return OutreachEmail(
        subject_line=subject,
        subject_line_alt=f"Idea for your {article.title[:25]}... piece",
        opening_hook="",
        connection_point="",
        value_proposition="",
        insertion_suggestion="",
        call_to_action="",
        full_body=body,
        ps_line=None,
        signature=f"{sender.name}\n{sender.title}, {sender.company}"
    )


def get_email_preview(email: OutreachEmail) -> str:
    """Generate a clean preview of the email."""
    return f"""Subject: {email.subject_line}

{email.full_body}

---
{email.word_count} words"""
