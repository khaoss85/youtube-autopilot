"""
Domain Analyzer Service - Analyze domain authority and metrics.

Uses Ahrefs, Moz, or fallback estimation.
"""

import os
import re
from typing import Dict, Optional
from urllib.parse import urlparse
from yt_autopilot.core.logger import logger, log_fallback

import requests


def analyze_domain(url_or_domain: str) -> Dict:
    """
    Analyze a domain's authority and metrics.

    Args:
        url_or_domain: Full URL or domain name

    Returns:
        Dict with:
        - domain: Clean domain name
        - domain_authority: DA score (0-100)
        - monthly_traffic: Estimated monthly traffic
        - source: Where metrics came from
        - category: Domain category (news, blog, etc.)
    """
    # Extract domain from URL
    domain = _extract_domain(url_or_domain)
    logger.info(f"Analyzing domain: {domain}")

    result = {
        "domain": domain,
        "domain_authority": 0.0,
        "monthly_traffic": 0,
        "backlinks": 0,
        "source": "unknown",
        "category": "unknown",
        "is_high_authority": False
    }

    # Try Ahrefs API
    ahrefs_result = _get_ahrefs_metrics(domain)
    if ahrefs_result:
        result.update(ahrefs_result)
        result["source"] = "ahrefs"
        logger.info(f"  ✓ Got Ahrefs metrics: DA={result['domain_authority']}")
        return result

    # Try Moz API
    moz_result = _get_moz_metrics(domain)
    if moz_result:
        result.update(moz_result)
        result["source"] = "moz"
        logger.info(f"  ✓ Got Moz metrics: DA={result['domain_authority']}")
        return result

    # Fallback to estimation based on known domains
    estimated = _estimate_domain_authority(domain)
    result.update(estimated)
    result["source"] = "estimation"
    logger.info(f"  ⚠️ Estimated metrics: DA={result['domain_authority']}")

    return result


def _extract_domain(url_or_domain: str) -> str:
    """Extract clean domain from URL or domain string."""
    if "://" in url_or_domain:
        parsed = urlparse(url_or_domain)
        domain = parsed.netloc
    else:
        domain = url_or_domain

    # Remove www.
    domain = re.sub(r'^www\.', '', domain)
    return domain.lower()


def _get_ahrefs_metrics(domain: str) -> Optional[Dict]:
    """
    Get metrics from Ahrefs API.

    Requires AHREFS_API_KEY environment variable.
    """
    api_key = os.getenv("AHREFS_API_KEY")
    if not api_key:
        logger.debug("Ahrefs API key not configured")
        return None

    try:
        # Ahrefs API endpoint
        url = f"https://apiv2.ahrefs.com"
        params = {
            "token": api_key,
            "from": "domain_rating",
            "target": domain,
            "mode": "domain",
            "output": "json"
        }

        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Note: Actual Ahrefs API response structure may differ
            return {
                "domain_authority": data.get("domain_rating", 0),
                "monthly_traffic": data.get("organic_traffic", 0),
                "backlinks": data.get("backlinks", 0),
                "is_high_authority": data.get("domain_rating", 0) >= 50
            }

    except Exception as e:
        logger.debug(f"Ahrefs API failed: {e}")

    return None


def _get_moz_metrics(domain: str) -> Optional[Dict]:
    """
    Get metrics from Moz API.

    Requires MOZ_ACCESS_ID and MOZ_SECRET_KEY environment variables.
    """
    access_id = os.getenv("MOZ_ACCESS_ID")
    secret_key = os.getenv("MOZ_SECRET_KEY")

    if not access_id or not secret_key:
        logger.debug("Moz API credentials not configured")
        return None

    try:
        url = "https://lsapi.seomoz.com/v2/url_metrics"
        data = {
            "targets": [domain]
        }
        auth = (access_id, secret_key)

        response = requests.post(url, json=data, auth=auth, timeout=15)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                metrics = results[0]
                return {
                    "domain_authority": metrics.get("domain_authority", 0),
                    "monthly_traffic": 0,  # Moz doesn't provide traffic
                    "backlinks": metrics.get("external_links_to_root_domain", 0),
                    "is_high_authority": metrics.get("domain_authority", 0) >= 50
                }

    except Exception as e:
        logger.debug(f"Moz API failed: {e}")

    return None


def _estimate_domain_authority(domain: str) -> Dict:
    """
    Estimate domain authority based on known domains and heuristics.

    This is a fallback when no API is available.
    """
    # Known high-authority domains
    high_authority_domains = {
        # Major publications (DA 90+)
        "nytimes.com": 95,
        "washingtonpost.com": 94,
        "theguardian.com": 94,
        "bbc.com": 95,
        "cnn.com": 94,
        "forbes.com": 94,
        "bloomberg.com": 93,

        # Tech publications (DA 80-95)
        "techcrunch.com": 93,
        "theverge.com": 92,
        "wired.com": 93,
        "engadget.com": 91,
        "arstechnica.com": 90,
        "venturebeat.com": 89,
        "zdnet.com": 92,
        "cnet.com": 93,
        "mashable.com": 92,
        "gizmodo.com": 91,

        # Business (DA 85-95)
        "businessinsider.com": 92,
        "entrepreneur.com": 88,
        "inc.com": 91,
        "fastcompany.com": 90,
        "hbr.org": 91,

        # Tech blogs (DA 60-80)
        "producthunt.com": 85,
        "medium.com": 94,
        "dev.to": 75,
        "hackernoon.com": 78,
        "freecodecamp.org": 82,

        # Fitness/Health (DA 70-90)
        "healthline.com": 91,
        "webmd.com": 93,
        "menshealth.com": 88,
        "womenshealthmag.com": 87,
        "shape.com": 84,
        "self.com": 86,
        "bodybuilding.com": 80,
        "myfitnesspal.com": 82,

        # General high authority
        "wikipedia.org": 100,
        "github.com": 96,
        "reddit.com": 97,
        "quora.com": 93,
        "linkedin.com": 98,
    }

    # Check exact match
    if domain in high_authority_domains:
        da = high_authority_domains[domain]
        return {
            "domain_authority": da,
            "monthly_traffic": _estimate_traffic_from_da(da),
            "backlinks": 0,
            "is_high_authority": da >= 50,
            "category": _guess_category(domain)
        }

    # Check subdomain of known domain
    for known_domain, da in high_authority_domains.items():
        if domain.endswith(f".{known_domain}"):
            # Subdomains typically have lower DA
            adjusted_da = max(da - 15, 30)
            return {
                "domain_authority": adjusted_da,
                "monthly_traffic": _estimate_traffic_from_da(adjusted_da),
                "backlinks": 0,
                "is_high_authority": adjusted_da >= 50,
                "category": _guess_category(domain)
            }

    # Unknown domain - estimate based on TLD and structure
    estimated_da = _estimate_unknown_domain_da(domain)
    return {
        "domain_authority": estimated_da,
        "monthly_traffic": _estimate_traffic_from_da(estimated_da),
        "backlinks": 0,
        "is_high_authority": estimated_da >= 50,
        "category": _guess_category(domain)
    }


def _estimate_unknown_domain_da(domain: str) -> float:
    """Estimate DA for unknown domains based on heuristics."""
    da = 30.0  # Base DA for unknown domains

    # TLD bonus
    if domain.endswith(".edu"):
        da += 20
    elif domain.endswith(".gov"):
        da += 25
    elif domain.endswith(".org"):
        da += 5
    elif domain.endswith(".io"):
        da += 5  # Tech startups

    # Structure hints
    if "blog" in domain:
        da -= 5
    if "news" in domain:
        da += 10

    return min(max(da, 10), 80)  # Clamp between 10-80


def _estimate_traffic_from_da(da: float) -> int:
    """Estimate monthly traffic from DA."""
    if da >= 90:
        return 10_000_000
    elif da >= 80:
        return 1_000_000
    elif da >= 70:
        return 500_000
    elif da >= 60:
        return 100_000
    elif da >= 50:
        return 50_000
    elif da >= 40:
        return 10_000
    else:
        return 1_000


def _guess_category(domain: str) -> str:
    """Guess domain category from name."""
    tech_keywords = ["tech", "code", "dev", "software", "digital", "cyber", "data", "ai"]
    health_keywords = ["health", "fitness", "wellness", "medical", "body", "diet"]
    business_keywords = ["business", "entrepreneur", "startup", "invest", "finance"]
    news_keywords = ["news", "times", "post", "journal", "tribune", "herald"]

    domain_lower = domain.lower()

    for kw in tech_keywords:
        if kw in domain_lower:
            return "technology"

    for kw in health_keywords:
        if kw in domain_lower:
            return "health_fitness"

    for kw in business_keywords:
        if kw in domain_lower:
            return "business"

    for kw in news_keywords:
        if kw in domain_lower:
            return "news"

    return "general"


def get_domain_category(domain: str) -> str:
    """Get domain category."""
    result = analyze_domain(domain)
    return result.get("category", "unknown")


def is_high_authority_domain(domain: str, threshold: float = 50) -> bool:
    """Check if domain is high authority."""
    result = analyze_domain(domain)
    return result.get("domain_authority", 0) >= threshold
