"""
Spam Checker Agent - Validate emails don't trigger spam filters.

Checks for common spam indicators and scores email deliverability.
"""

import re
from typing import Dict, Tuple, Optional, Callable

from pr_outreach.core.schemas import OutreachEmail
from yt_autopilot.core.logger import logger


# Common spam trigger words/phrases
SPAM_TRIGGERS = {
    "high": [
        "free money", "winner", "congratulations", "limited time",
        "act now", "urgent", "click here", "buy now", "order now",
        "100% free", "no obligation", "risk free", "guarantee",
        "million dollars", "lottery", "prize", "selected"
    ],
    "medium": [
        "deal", "offer", "discount", "promotion", "special",
        "exclusive", "incredible", "amazing", "best price",
        "lowest price", "compare rates", "bargain"
    ],
    "low": [
        "free", "new", "important", "reminder", "update",
        "opportunity", "solution", "results", "success"
    ]
}

# Patterns that look spammy
SPAM_PATTERNS = [
    r'!!!+',  # Multiple exclamation marks
    r'\$\d+',  # Dollar amounts
    r'%\s*off',  # Percentage off
    r'[A-Z]{5,}',  # ALL CAPS words
    r'click\s+here',  # "Click here"
    r're:\s*re:',  # Fake reply chain
    r'fwd:\s*fwd:',  # Fake forward chain
]


def check_spam_score(
    email: OutreachEmail,
    llm_generate_fn: Optional[Callable] = None
) -> Tuple[float, str, Dict]:
    """
    Check email for spam indicators.

    Args:
        email: Email to check
        llm_generate_fn: LLM function for advanced checking

    Returns:
        Tuple of (spam_score, summary, details)
        - spam_score: 0.0 (clean) to 1.0 (definitely spam)
        - summary: Brief explanation
        - details: Detailed breakdown
    """
    logger.info("Checking email for spam indicators...")

    details = {
        "subject_issues": [],
        "body_issues": [],
        "structural_issues": [],
        "trigger_words": [],
        "pattern_matches": []
    }

    score = 0.0

    # Check subject line
    subject_score, subject_issues = _check_subject(email.subject_line)
    score += subject_score * 0.3
    details["subject_issues"] = subject_issues

    # Check body
    body_score, body_issues, triggers, patterns = _check_body(email.full_body)
    score += body_score * 0.5
    details["body_issues"] = body_issues
    details["trigger_words"] = triggers
    details["pattern_matches"] = patterns

    # Check structure
    structure_score, structure_issues = _check_structure(email)
    score += structure_score * 0.2
    details["structural_issues"] = structure_issues

    # Normalize score
    score = min(score, 1.0)

    # Generate summary
    if score < 0.2:
        summary = "Clean - Low spam risk"
    elif score < 0.4:
        summary = "Minor issues - Generally safe"
    elif score < 0.6:
        summary = "Moderate risk - Review recommended"
    elif score < 0.8:
        summary = "High risk - Needs revision"
    else:
        summary = "Very high risk - Major revision needed"

    logger.info(f"  Spam score: {score:.2f} - {summary}")

    return (score, summary, details)


def _check_subject(subject: str) -> Tuple[float, list]:
    """Check subject line for spam indicators."""
    issues = []
    score = 0.0

    # Check length
    if len(subject) < 10:
        issues.append("Subject too short")
        score += 0.1
    elif len(subject) > 60:
        issues.append("Subject too long (may be truncated)")
        score += 0.05

    # Check for ALL CAPS
    caps_ratio = sum(1 for c in subject if c.isupper()) / max(len(subject), 1)
    if caps_ratio > 0.5:
        issues.append("Too many capital letters")
        score += 0.2

    # Check for spam triggers
    subject_lower = subject.lower()
    for word in SPAM_TRIGGERS["high"]:
        if word in subject_lower:
            issues.append(f"High-risk word: '{word}'")
            score += 0.3

    for word in SPAM_TRIGGERS["medium"]:
        if word in subject_lower:
            issues.append(f"Medium-risk word: '{word}'")
            score += 0.15

    # Check for spam patterns
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, subject, re.IGNORECASE):
            issues.append(f"Spam pattern detected")
            score += 0.2

    # Check for RE:/FWD: fake
    if re.match(r'^(re|fwd):', subject, re.IGNORECASE):
        if "re:" not in subject.lower() or "fwd:" not in subject.lower():
            pass  # Legitimate
        else:
            issues.append("Suspicious RE:/FWD: pattern")
            score += 0.3

    return (min(score, 1.0), issues)


def _check_body(body: str) -> Tuple[float, list, list, list]:
    """Check email body for spam indicators."""
    issues = []
    triggers_found = []
    patterns_found = []
    score = 0.0

    body_lower = body.lower()

    # Check for spam trigger words
    for word in SPAM_TRIGGERS["high"]:
        if word in body_lower:
            triggers_found.append(f"HIGH: {word}")
            score += 0.15

    for word in SPAM_TRIGGERS["medium"]:
        if word in body_lower:
            triggers_found.append(f"MEDIUM: {word}")
            score += 0.08

    # Check for spam patterns
    for pattern in SPAM_PATTERNS:
        matches = re.findall(pattern, body, re.IGNORECASE)
        if matches:
            patterns_found.extend(matches[:3])
            score += 0.1

    # Check link ratio
    link_count = len(re.findall(r'https?://', body))
    word_count = len(body.split())
    if word_count > 0:
        link_ratio = link_count / word_count
        if link_ratio > 0.05:
            issues.append(f"High link ratio ({link_count} links)")
            score += 0.2

    # Check for excessive formatting
    caps_words = len(re.findall(r'\b[A-Z]{4,}\b', body))
    if caps_words > 3:
        issues.append(f"Too many ALL CAPS words ({caps_words})")
        score += 0.15

    # Check exclamation marks
    exclamation_count = body.count('!')
    if exclamation_count > 3:
        issues.append(f"Too many exclamation marks ({exclamation_count})")
        score += 0.1

    return (min(score, 1.0), issues, triggers_found, patterns_found)


def _check_structure(email: OutreachEmail) -> Tuple[float, list]:
    """Check email structure for spam indicators."""
    issues = []
    score = 0.0

    # Check word count
    if email.word_count < 50:
        issues.append("Email too short (may look automated)")
        score += 0.1
    elif email.word_count > 500:
        issues.append("Email too long (lower response rate)")
        score += 0.05

    # Check for personalization
    if not email.opening_hook or len(email.opening_hook) < 20:
        issues.append("Weak opening (lacks personalization)")
        score += 0.15

    # Check for clear CTA
    if not email.call_to_action or len(email.call_to_action) < 10:
        issues.append("Missing or weak call-to-action")
        score += 0.05

    # Check subject/body alignment
    # (Would need more sophisticated check)

    return (min(score, 1.0), issues)


def get_spam_report(email: OutreachEmail) -> str:
    """Generate a detailed spam check report."""
    score, summary, details = check_spam_score(email)

    report = f"""
SPAM CHECK REPORT
=================
Score: {score:.2f}/1.0
Status: {summary}

Subject Line Issues:
{_format_issues(details['subject_issues'])}

Body Issues:
{_format_issues(details['body_issues'])}

Trigger Words Found:
{_format_issues(details['trigger_words'])}

Spam Patterns:
{_format_issues(details['pattern_matches'])}

Structural Issues:
{_format_issues(details['structural_issues'])}
""".strip()

    return report


def _format_issues(issues: list) -> str:
    """Format list of issues for display."""
    if not issues:
        return "  None"
    return "\n".join(f"  - {issue}" for issue in issues)


def suggest_improvements(email: OutreachEmail, details: Dict) -> list:
    """Suggest specific improvements based on spam check."""
    suggestions = []

    if details["subject_issues"]:
        suggestions.append("Revise subject line to remove spam triggers")

    if details["trigger_words"]:
        suggestions.append(f"Remove or replace: {', '.join(details['trigger_words'][:3])}")

    if "Too many ALL CAPS" in str(details["body_issues"]):
        suggestions.append("Reduce use of ALL CAPS words")

    if "Too many exclamation marks" in str(details["body_issues"]):
        suggestions.append("Reduce exclamation mark usage")

    if "High link ratio" in str(details["body_issues"]):
        suggestions.append("Reduce number of links")

    if "Weak opening" in str(details["structural_issues"]):
        suggestions.append("Add more personalization to opening")

    return suggestions
