"""
Author Finder Service - Discover author contact information.

Uses multiple sources:
- Hunter.io API for email discovery
- LinkedIn search
- Twitter/X search
- Google search
"""

import re
import os
from typing import Dict, Optional, List
from yt_autopilot.core.logger import logger, log_fallback

import requests


def find_author_contacts(
    author_name: str,
    domain: str,
    article_url: Optional[str] = None
) -> Dict:
    """
    Find contact information for an article author.

    Args:
        author_name: Full name of the author
        domain: Domain of the publication (e.g., "techcrunch.com")
        article_url: URL of the article (for context)

    Returns:
        Dict with:
        - email: Found email address
        - email_confidence: Confidence score (0-1)
        - linkedin_url: LinkedIn profile URL
        - twitter_handle: Twitter handle
        - sources: List of sources used
    """
    logger.info(f"Finding contacts for author: {author_name} @ {domain}")

    # Handle missing author name
    if not author_name or not author_name.strip():
        logger.warning("No author name provided, skipping contact search")
        return {
            "email": None,
            "email_confidence": 0.0,
            "linkedin_url": None,
            "twitter_handle": None,
            "personal_website": None,
            "sources": []
        }

    result = {
        "email": None,
        "email_confidence": 0.0,
        "linkedin_url": None,
        "twitter_handle": None,
        "personal_website": None,
        "sources": []
    }

    # Try Hunter.io first (if API key available)
    hunter_result = _search_hunter(author_name, domain)
    if hunter_result.get("email"):
        result["email"] = hunter_result["email"]
        result["email_confidence"] = hunter_result.get("confidence", 0.5)
        result["sources"].append("hunter.io")
        logger.info(f"  ✓ Found email via Hunter.io: {result['email']}")

    # Try OpenAI Web Search as fallback (uses GPT-5.1 with web_search_preview)
    if not result["email"]:
        openai_result = _search_openai_web(author_name, domain, article_url)
        if openai_result.get("email"):
            result["email"] = openai_result["email"]
            result["email_confidence"] = openai_result.get("confidence", 0.5)
            result["sources"].append("openai_web_search")
            logger.info(f"  ✓ Found email via OpenAI: {result['email']}")

    # Try to find LinkedIn
    linkedin_url = _search_linkedin(author_name, domain)
    if linkedin_url:
        result["linkedin_url"] = linkedin_url
        result["sources"].append("linkedin")
        logger.info(f"  ✓ Found LinkedIn: {linkedin_url}")

    # Try to find Twitter
    twitter_handle = _search_twitter(author_name, domain)
    if twitter_handle:
        result["twitter_handle"] = twitter_handle
        result["sources"].append("twitter")
        logger.info(f"  ✓ Found Twitter: @{twitter_handle}")

    # Generate email pattern guess if no email found
    if not result["email"]:
        guessed_email = _guess_email_pattern(author_name, domain)
        if guessed_email:
            result["email"] = guessed_email
            result["email_confidence"] = 0.3  # Low confidence for guesses
            result["sources"].append("pattern_guess")
            logger.info(f"  ⚠️ Guessed email pattern: {guessed_email}")

    if not result["sources"]:
        log_fallback(
            component="AUTHOR_FINDER",
            fallback_type="NO_CONTACTS_FOUND",
            reason=f"Could not find contacts for {author_name}",
            impact="MEDIUM"
        )
        logger.warning(f"  ✗ No contacts found for {author_name}")

    return result


def _search_openai_web(author_name: str, domain: str, article_url: Optional[str] = None) -> Dict:
    """
    Search for author email using OpenAI GPT-5.1 web search.

    Uses Responses API with web_search_preview tool for real-time web search.
    This is a free fallback (only normal OpenAI API costs).
    """
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_OPENAI_API_KEY")
    if not api_key:
        logger.debug("OpenAI API key not configured for web search")
        return {}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # Build search prompt
        search_prompt = f"""Find the email address for author "{author_name}" who writes for {domain}.

Search the web for:
- Author's profile/bio page on {domain}
- Author's LinkedIn profile
- Author's Twitter/X bio
- Author's personal website or blog
- Contact pages mentioning this author

Look for email addresses in the format: name@domain.com

Return ONLY a valid JSON object with this exact structure:
{{"email": "found@email.com", "confidence": 0.8, "source": "where you found it"}}

If no email found after searching, return:
{{"email": null, "confidence": 0, "source": null}}

Do NOT explain or add any text outside the JSON."""

        response = client.responses.create(
            model="gpt-5.1",
            tools=[{"type": "web_search_preview"}],
            input=search_prompt,
            reasoning={"effort": "low"},
            text={"verbosity": "low"}
        )

        # Parse response - extract text from output messages
        result_text = ""
        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'content') and item.content:
                    for content in item.content:
                        if hasattr(content, 'text'):
                            result_text += content.text + " "

        if not result_text:
            result_text = str(response)

        logger.debug(f"OpenAI web search response: {result_text[:200]}...")

        # Extract email from response text
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails_found = re.findall(email_pattern, result_text)

        if emails_found:
            # Take first valid email found
            email = emails_found[0]
            logger.info(f"  ✓ OpenAI web search found email: {email}")
            return {
                "email": email,
                "confidence": 0.7,  # High confidence from web search
                "source": "openai_web_search"
            }

    except ImportError:
        logger.debug("OpenAI package not installed or outdated")
    except Exception as e:
        logger.debug(f"OpenAI web search failed: {e}")

    return {}


def _search_hunter(author_name: str, domain: str) -> Dict:
    """
    Search Hunter.io for author email.

    Requires HUNTER_API_KEY environment variable.
    """
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        logger.debug("Hunter.io API key not configured")
        return {}

    try:
        # Parse first and last name
        name_parts = author_name.strip().split()
        if len(name_parts) < 2:
            return {}

        first_name = name_parts[0]
        last_name = name_parts[-1]

        # Hunter.io email finder endpoint
        url = "https://api.hunter.io/v2/email-finder"
        params = {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": api_key
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", {})
            if data.get("email"):
                return {
                    "email": data["email"],
                    "confidence": data.get("score", 50) / 100.0
                }

    except Exception as e:
        logger.debug(f"Hunter.io search failed: {e}")

    return {}


def _search_linkedin(author_name: str, domain: str) -> Optional[str]:
    """
    Search for LinkedIn profile.

    Note: This is a simplified search. Full implementation would use
    LinkedIn API or a service like Proxycurl.
    """
    # Build search query
    query = f"{author_name} {domain} site:linkedin.com/in"

    # For now, construct a LinkedIn search URL
    # In production, use actual LinkedIn API or scraping service
    linkedin_search_url = f"https://www.linkedin.com/search/results/people/?keywords={author_name}"

    # Return None - would need actual API integration
    # This is a placeholder for the structure
    return None


def _search_twitter(author_name: str, domain: str) -> Optional[str]:
    """
    Search for Twitter handle.

    Note: This is a simplified search. Full implementation would use
    Twitter API.
    """
    # Would need Twitter API integration
    # This is a placeholder for the structure
    return None


def _guess_email_pattern(author_name: str, domain: str) -> Optional[str]:
    """
    Guess email address based on common patterns.

    Common patterns:
    - firstname@domain
    - firstname.lastname@domain
    - firstnamelastname@domain
    - f.lastname@domain
    """
    name_parts = author_name.strip().lower().split()
    if len(name_parts) < 2:
        return None

    first_name = re.sub(r'[^a-z]', '', name_parts[0])
    last_name = re.sub(r'[^a-z]', '', name_parts[-1])

    if not first_name or not last_name:
        return None

    # Most common pattern: firstname.lastname@domain
    return f"{first_name}.{last_name}@{domain}"


def find_author_social_profiles(author_name: str) -> Dict:
    """
    Find social media profiles for an author.

    Returns dict with platform URLs.
    """
    profiles = {
        "linkedin": None,
        "twitter": None,
        "github": None,
        "personal_site": None
    }

    # This would integrate with various APIs/services
    # Placeholder for structure

    return profiles


def enrich_author_profile(
    author_name: str,
    domain: str,
    existing_data: Dict
) -> Dict:
    """
    Enrich existing author data with additional information.

    Combines multiple sources to build complete profile.
    """
    enriched = existing_data.copy()

    # If no email, try to find one
    if not enriched.get("email"):
        contacts = find_author_contacts(author_name, domain)
        enriched.update(contacts)

    # Try to find bio from LinkedIn
    # Would need actual API integration

    return enriched
