"""
Author Profiler Agent - Research and profile article authors.

Gathers information for personalized outreach.
"""

from typing import Dict, Optional, Callable, List

from pr_outreach.core.schemas import ArticleCandidate, AuthorProfile
from pr_outreach.services.author_finder import find_author_contacts, enrich_author_profile
from pr_outreach.services.contact_validator import validate_email
from pr_outreach.services.article_scraper import scrape_article
from yt_autopilot.core.logger import logger, log_fallback


def profile_author(
    article: ArticleCandidate,
    llm_generate_fn: Optional[Callable] = None
) -> AuthorProfile:
    """
    Build a comprehensive profile for an article's author.

    Args:
        article: Article with author information
        llm_generate_fn: LLM function for analysis

    Returns:
        AuthorProfile with contact and background info
    """
    logger.info(f"Profiling author: {article.author_name or 'Unknown'}")

    # Start with basic info from article
    profile = AuthorProfile(
        name=article.author_name or "Unknown Author"
    )

    if not article.author_name:
        logger.warning("  No author name available")
        log_fallback(
            component="AUTHOR_PROFILER",
            fallback_type="NO_AUTHOR_NAME",
            reason="Article has no author attribution",
            impact="MEDIUM"
        )
        return profile

    # Find contact information
    contacts = find_author_contacts(
        author_name=article.author_name,
        domain=article.domain,
        article_url=article.url
    )

    profile.email = contacts.get("email")
    profile.email_confidence = contacts.get("email_confidence", 0.0)
    profile.linkedin_url = contacts.get("linkedin_url")
    profile.twitter_handle = contacts.get("twitter_handle")
    profile.personal_website = contacts.get("personal_website")

    # Validate email if found
    if profile.email:
        is_valid, confidence, reason = validate_email(profile.email)
        profile.email_verified = is_valid
        profile.email_confidence = confidence
        logger.info(f"  Email {profile.email}: {reason}")

    # Try to get bio from author URL
    if article.author_url:
        bio_info = _extract_author_bio(article.author_url)
        if bio_info:
            profile.bio = bio_info.get("bio")
            profile.job_title = bio_info.get("job_title")
            profile.company = bio_info.get("company")

    # Analyze author's writing style if LLM available
    if llm_generate_fn and article.full_content:
        writing_analysis = _analyze_writing_style(
            article.full_content,
            article.author_name,
            llm_generate_fn
        )
        profile.writing_style = writing_analysis.get("style")
        profile.topics_covered = writing_analysis.get("topics", [])

    # Calculate reachability score
    profile.reachability_score = _calculate_reachability(profile)
    profile.relevance_score = 0.5  # Default, would be set by campaign context

    logger.info(f"  Reachability: {profile.reachability_score:.2f}")
    logger.info(f"  Contact sources: {contacts.get('sources', [])}")

    return profile


def _extract_author_bio(author_url: str) -> Optional[Dict]:
    """Extract author bio from their profile page."""
    try:
        scraped = scrape_article(author_url)
        if not scraped["success"]:
            return None

        content = scraped["content"]

        # Look for bio-like content
        bio_info = {
            "bio": None,
            "job_title": None,
            "company": None
        }

        # Extract first paragraph as bio (simplified)
        paragraphs = content.split("\n\n")
        for para in paragraphs[:3]:
            para = para.strip()
            if len(para) > 50 and len(para) < 500:
                bio_info["bio"] = para
                break

        return bio_info

    except Exception as e:
        logger.debug(f"Bio extraction failed: {e}")
        return None


def _analyze_writing_style(
    content: str,
    author_name: str,
    llm_generate_fn: Callable
) -> Dict:
    """Analyze author's writing style using LLM."""
    prompt = f"""Analyze the writing style of author {author_name} based on this article.

Article excerpt:
{content[:2000]}

Identify:
1. WRITING_STYLE: How would you describe their writing? (e.g., "formal and technical", "conversational and accessible", "data-driven", "storytelling-focused")
2. TOPICS: What topics do they seem to focus on? (List 3-5 topics)
3. TONE: What is their general tone? (e.g., "professional", "casual", "authoritative", "friendly")

Respond in this format:
WRITING_STYLE: [style description]
TOPICS: [topic1], [topic2], [topic3]
TONE: [tone description]"""

    try:
        response = llm_generate_fn(
            role="writing_analyst",
            task=prompt,
            context="",
            style_hints={}
        )

        result = {
            "style": "professional",
            "topics": [],
            "tone": "neutral"
        }

        for line in response.strip().split("\n"):
            if line.startswith("WRITING_STYLE:"):
                result["style"] = line.replace("WRITING_STYLE:", "").strip()
            elif line.startswith("TOPICS:"):
                topics_str = line.replace("TOPICS:", "").strip()
                result["topics"] = [t.strip() for t in topics_str.split(",")]
            elif line.startswith("TONE:"):
                result["tone"] = line.replace("TONE:", "").strip()

        return result

    except Exception as e:
        logger.debug(f"Writing style analysis failed: {e}")
        return {"style": "unknown", "topics": [], "tone": "unknown"}


def _calculate_reachability(profile: AuthorProfile) -> float:
    """Calculate how reachable the author is (0-1)."""
    score = 0.0

    # Email is most valuable
    if profile.email:
        if profile.email_verified:
            score += 0.5
        else:
            score += 0.3 * profile.email_confidence

    # LinkedIn provides another channel
    if profile.linkedin_url:
        score += 0.25

    # Twitter can be useful
    if profile.twitter_handle:
        score += 0.15

    # Personal website may have contact form
    if profile.personal_website:
        score += 0.1

    return min(score, 1.0)


def find_alternate_contacts(author_name: str, domain: str) -> List[Dict]:
    """
    Find alternate contacts at the same publication.

    Useful when direct author contact isn't available.
    """
    alternates = []

    # Common editor email patterns
    editor_patterns = [
        f"editor@{domain}",
        f"tips@{domain}",
        f"contact@{domain}",
        f"submissions@{domain}"
    ]

    for email in editor_patterns:
        is_valid, confidence, _ = validate_email(email)
        if is_valid:
            alternates.append({
                "email": email,
                "role": "editor",
                "confidence": confidence
            })

    return alternates


def get_author_summary(profile: AuthorProfile) -> str:
    """Generate a brief summary for the author profile."""
    parts = [f"**{profile.name}**"]

    if profile.job_title and profile.company:
        parts.append(f"{profile.job_title} at {profile.company}")
    elif profile.job_title:
        parts.append(profile.job_title)
    elif profile.company:
        parts.append(f"Writer at {profile.company}")

    if profile.email:
        status = "verified" if profile.email_verified else f"{profile.email_confidence:.0%} confidence"
        parts.append(f"Email: {profile.email} ({status})")

    if profile.linkedin_url:
        parts.append(f"LinkedIn: {profile.linkedin_url}")

    if profile.twitter_handle:
        parts.append(f"Twitter: @{profile.twitter_handle}")

    parts.append(f"Reachability: {profile.reachability_score:.0%}")

    return "\n".join(parts)
