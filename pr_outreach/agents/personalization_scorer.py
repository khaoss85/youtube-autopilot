"""
Personalization Scorer Agent - Evaluate email personalization quality.

Ensures emails feel personal and human, not templated.
"""

import re
from typing import Dict, Tuple, Optional, Callable

from pr_outreach.core.schemas import (
    OutreachEmail,
    ArticleCandidate,
    AuthorProfile
)
from yt_autopilot.core.logger import logger


def score_personalization(
    email: OutreachEmail,
    article: ArticleCandidate,
    author: AuthorProfile,
    llm_generate_fn: Optional[Callable] = None
) -> Tuple[float, str, Dict]:
    """
    Score how personalized an email is.

    Args:
        email: Email to evaluate
        article: Target article for context
        author: Author profile for context
        llm_generate_fn: LLM for advanced evaluation

    Returns:
        Tuple of (score, summary, details)
        - score: 0.0 (generic) to 1.0 (highly personalized)
        - summary: Brief explanation
        - details: Breakdown of personalization elements
    """
    logger.info("Scoring email personalization...")

    details = {
        "author_references": [],
        "article_references": [],
        "specific_details": [],
        "generic_phrases": [],
        "personalization_elements": 0,
        "generic_elements": 0
    }

    score = 0.0

    # Check for author name usage
    author_score, author_refs = _check_author_references(email, author)
    score += author_score * 0.25
    details["author_references"] = author_refs

    # Check for article references
    article_score, article_refs = _check_article_references(email, article)
    score += article_score * 0.30
    details["article_references"] = article_refs

    # Check for specific details
    specific_score, specific_details = _check_specific_details(email, article, author)
    score += specific_score * 0.25
    details["specific_details"] = specific_details

    # Check for generic phrases (negative score)
    generic_score, generic_phrases = _check_generic_phrases(email)
    score -= generic_score * 0.20
    details["generic_phrases"] = generic_phrases

    # Use LLM for advanced evaluation if available
    if llm_generate_fn:
        llm_score = _llm_evaluate_personalization(
            email, article, author, llm_generate_fn
        )
        # Blend LLM score with heuristic score
        score = (score * 0.6) + (llm_score * 0.4)

    # Normalize score
    score = max(0.0, min(1.0, score))

    # Count elements
    details["personalization_elements"] = (
        len(author_refs) + len(article_refs) + len(specific_details)
    )
    details["generic_elements"] = len(generic_phrases)

    # Generate summary
    if score >= 0.8:
        summary = "Excellent - Highly personalized"
    elif score >= 0.6:
        summary = "Good - Well personalized"
    elif score >= 0.4:
        summary = "Fair - Some personalization"
    elif score >= 0.2:
        summary = "Weak - Needs more personalization"
    else:
        summary = "Poor - Too generic"

    logger.info(f"  Personalization score: {score:.2f} - {summary}")

    return (score, summary, details)


def _check_author_references(
    email: OutreachEmail,
    author: AuthorProfile
) -> Tuple[float, list]:
    """Check for references to the author."""
    references = []
    score = 0.0

    body_lower = email.full_body.lower()
    opening_lower = email.opening_hook.lower()

    # Check for author's name
    if author.name:
        first_name = author.name.split()[0].lower()
        if first_name in opening_lower:
            references.append(f"Uses first name '{first_name}' in greeting")
            score += 0.3
        if author.name.lower() in body_lower:
            references.append(f"Mentions full name")
            score += 0.1

    # Check for job title reference
    if author.job_title and author.job_title.lower() in body_lower:
        references.append(f"References job title")
        score += 0.2

    # Check for company reference
    if author.company and author.company.lower() in body_lower:
        references.append(f"References company/publication")
        score += 0.15

    # Check for reference to their work/writing
    work_references = ["your article", "your piece", "your work", "you wrote", "you covered"]
    for ref in work_references:
        if ref in body_lower:
            references.append(f"References their work: '{ref}'")
            score += 0.25
            break

    return (min(score, 1.0), references)


def _check_article_references(
    email: OutreachEmail,
    article: ArticleCandidate
) -> Tuple[float, list]:
    """Check for references to the specific article."""
    references = []
    score = 0.0

    body_lower = email.full_body.lower()

    # Check for article title
    if article.title:
        # Check for exact title
        if article.title.lower() in body_lower:
            references.append("Mentions exact article title")
            score += 0.4
        else:
            # Check for partial title match (first few words)
            title_words = article.title.lower().split()[:4]
            title_snippet = " ".join(title_words)
            if title_snippet in body_lower:
                references.append("References article title (partial)")
                score += 0.3

    # Check for article URL
    if article.url and article.url in email.full_body:
        references.append("Includes article URL")
        score += 0.1

    # Check for domain reference
    if article.domain and article.domain.lower() in body_lower:
        references.append(f"Mentions publication: {article.domain}")
        score += 0.15

    # Check for content-specific references
    if article.content_excerpt:
        # Check if email references specific content
        excerpt_words = set(article.content_excerpt.lower().split())
        email_words = set(body_lower.split())
        common_specific = excerpt_words & email_words - _get_common_words()
        if len(common_specific) > 5:
            references.append("References specific article content")
            score += 0.2

    return (min(score, 1.0), references)


def _check_specific_details(
    email: OutreachEmail,
    article: ArticleCandidate,
    author: AuthorProfile
) -> Tuple[float, list]:
    """Check for other specific, non-generic details."""
    details = []
    score = 0.0

    body = email.full_body

    # Check for specific numbers/data
    if re.search(r'\d+\s*(users|customers|downloads|%)', body, re.IGNORECASE):
        details.append("Includes specific metrics/data")
        score += 0.15

    # Check for specific dates
    if re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}', body, re.IGNORECASE):
        details.append("References specific dates")
        score += 0.1

    # Check for quote from article
    if '"' in body and article.content_excerpt:
        # Check if there's a quote that might be from the article
        details.append("May include quote from article")
        score += 0.15

    # Check for reference to author's other work
    if author.recent_articles and len(author.recent_articles) > 0:
        for other_article in author.recent_articles[:3]:
            if other_article.lower() in body.lower():
                details.append("References author's other work")
                score += 0.2
                break

    # Check for reference to author's topics
    if author.topics_covered:
        for topic in author.topics_covered[:3]:
            if topic.lower() in body.lower():
                details.append(f"References author's topic: {topic}")
                score += 0.1
                break

    return (min(score, 1.0), details)


def _check_generic_phrases(email: OutreachEmail) -> Tuple[float, list]:
    """Check for generic, templated phrases (negative signal)."""
    generic_phrases = []
    score = 0.0

    body_lower = email.full_body.lower()

    # Common generic phrases
    generic_patterns = [
        ("i hope this email finds you well", 0.15),
        ("i wanted to reach out", 0.05),
        ("i came across your", 0.03),  # Less penalty, often legitimate
        ("i'm reaching out because", 0.03),
        ("hope you're doing well", 0.10),
        ("just wanted to touch base", 0.15),
        ("thought you might be interested", 0.05),
        ("i'm sure you're busy", 0.10),
        ("at your earliest convenience", 0.10),
        ("please don't hesitate", 0.05),
        ("looking forward to hearing", 0.03),
        ("best regards", 0.02),  # Common but acceptable
        ("dear sir/madam", 0.20),
        ("to whom it may concern", 0.25),
    ]

    for phrase, penalty in generic_patterns:
        if phrase in body_lower:
            generic_phrases.append(phrase)
            score += penalty

    # Check for placeholder-looking text
    placeholder_patterns = [
        r'\[.*?\]',  # [Name], [Company], etc.
        r'\{.*?\}',  # {Name}, {Company}, etc.
        r'<.*?>',    # <Name>, <Company>, etc.
    ]

    for pattern in placeholder_patterns:
        matches = re.findall(pattern, email.full_body)
        if matches:
            generic_phrases.extend([f"Placeholder: {m}" for m in matches[:3]])
            score += 0.3

    return (min(score, 1.0), generic_phrases)


def _get_common_words() -> set:
    """Get set of common words to exclude from analysis."""
    return {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "this", "that", "these",
        "those", "i", "you", "he", "she", "it", "we", "they", "what", "which",
        "who", "when", "where", "why", "how", "all", "each", "every", "both",
        "few", "more", "most", "other", "some", "such", "no", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "also", "now"
    }


def _llm_evaluate_personalization(
    email: OutreachEmail,
    article: ArticleCandidate,
    author: AuthorProfile,
    llm_generate_fn: Callable
) -> float:
    """Use LLM to evaluate personalization quality."""
    prompt = f"""Evaluate the personalization quality of this PR outreach email.

CONTEXT:
- Recipient: {author.name} ({author.job_title or 'Writer'})
- Their Article: "{article.title}"
- Publication: {article.domain}

EMAIL:
Subject: {email.subject_line}

{email.full_body}

EVALUATE:
Does this email feel personalized and human, or generic and templated?

Consider:
1. Does it reference the specific article meaningfully?
2. Does it show knowledge of the author's work?
3. Does it avoid generic phrases like "I hope this finds you well"?
4. Does it feel like a genuine human wrote it for this specific person?

Rate the personalization from 0.0 to 1.0:
- 0.0-0.3: Generic template, could be sent to anyone
- 0.4-0.6: Some personalization but feels formulaic
- 0.7-0.8: Well personalized, references specific details
- 0.9-1.0: Excellent, feels like genuine personal outreach

Respond with just a number between 0.0 and 1.0"""

    try:
        response = llm_generate_fn(
            role="email_evaluator",
            task=prompt,
            context="",
            style_hints={"response_format": "number"}
        )
        return float(response.strip())
    except Exception as e:
        logger.debug(f"LLM personalization evaluation failed: {e}")
        return 0.5  # Default to neutral


def get_personalization_report(
    email: OutreachEmail,
    article: ArticleCandidate,
    author: AuthorProfile
) -> str:
    """Generate a detailed personalization report."""
    score, summary, details = score_personalization(email, article, author)

    report = f"""
PERSONALIZATION REPORT
======================
Score: {score:.2f}/1.0
Status: {summary}

Author References ({len(details['author_references'])}):
{_format_list(details['author_references'])}

Article References ({len(details['article_references'])}):
{_format_list(details['article_references'])}

Specific Details ({len(details['specific_details'])}):
{_format_list(details['specific_details'])}

Generic Phrases Found ({len(details['generic_phrases'])}):
{_format_list(details['generic_phrases'])}

Summary:
- Personalization elements: {details['personalization_elements']}
- Generic elements: {details['generic_elements']}
""".strip()

    return report


def _format_list(items: list) -> str:
    """Format list for display."""
    if not items:
        return "  None"
    return "\n".join(f"  - {item}" for item in items)


def suggest_personalization_improvements(
    email: OutreachEmail,
    article: ArticleCandidate,
    author: AuthorProfile,
    details: Dict
) -> list:
    """Suggest ways to improve personalization."""
    suggestions = []

    if not details["author_references"]:
        suggestions.append(f"Add a personal reference to {author.name}'s work")

    if not details["article_references"]:
        suggestions.append(f"Reference the specific article: \"{article.title}\"")

    if details["generic_phrases"]:
        suggestions.append(
            f"Remove generic phrases: {', '.join(details['generic_phrases'][:3])}"
        )

    if len(details["specific_details"]) < 2:
        suggestions.append("Add more specific details about their content")

    if author.topics_covered and not any(
        topic.lower() in email.full_body.lower()
        for topic in author.topics_covered[:3]
    ):
        suggestions.append(
            f"Reference topics they cover: {', '.join(author.topics_covered[:3])}"
        )

    return suggestions
