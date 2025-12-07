"""
Contact Validator Service - Validate email addresses and contacts.

Uses email verification services to check deliverability.
"""

import re
import os
import dns.resolver
from typing import Dict, Tuple
from yt_autopilot.core.logger import logger, log_fallback

import requests


def validate_email(email: str) -> Tuple[bool, float, str]:
    """
    Validate an email address.

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, confidence, reason)
        - is_valid: Whether email appears valid
        - confidence: Confidence score (0-1)
        - reason: Explanation
    """
    logger.info(f"Validating email: {email}")

    # Step 1: Basic format validation
    if not _is_valid_format(email):
        return (False, 1.0, "Invalid email format")

    # Step 2: Check for disposable/spam domains
    if _is_disposable_domain(email):
        return (False, 0.9, "Disposable email domain")

    # Step 3: MX record check
    domain = email.split("@")[1]
    has_mx = _check_mx_records(domain)
    if not has_mx:
        return (False, 0.8, "Domain has no MX records")

    # Step 4: Try external verification service
    api_result = _verify_with_api(email)
    if api_result is not None:
        return api_result

    # If no API, return based on MX check only
    return (True, 0.6, "Passed basic validation (no API verification)")


def validate_contact(contact_data: Dict) -> Dict:
    """
    Validate all contact information in a profile.

    Args:
        contact_data: Dict with email, linkedin_url, twitter_handle, etc.

    Returns:
        Dict with validation results for each field
    """
    results = {}

    # Validate email
    if contact_data.get("email"):
        is_valid, confidence, reason = validate_email(contact_data["email"])
        results["email"] = {
            "valid": is_valid,
            "confidence": confidence,
            "reason": reason
        }

    # Validate LinkedIn URL
    if contact_data.get("linkedin_url"):
        is_valid = _is_valid_linkedin_url(contact_data["linkedin_url"])
        results["linkedin_url"] = {
            "valid": is_valid,
            "confidence": 0.9 if is_valid else 0.0,
            "reason": "Valid LinkedIn URL format" if is_valid else "Invalid LinkedIn URL"
        }

    # Validate Twitter handle
    if contact_data.get("twitter_handle"):
        is_valid = _is_valid_twitter_handle(contact_data["twitter_handle"])
        results["twitter_handle"] = {
            "valid": is_valid,
            "confidence": 0.9 if is_valid else 0.0,
            "reason": "Valid Twitter handle format" if is_valid else "Invalid Twitter handle"
        }

    return results


def _is_valid_format(email: str) -> bool:
    """Check basic email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def _is_disposable_domain(email: str) -> bool:
    """Check if email uses a disposable domain."""
    disposable_domains = {
        "mailinator.com", "guerrillamail.com", "tempmail.com",
        "throwaway.email", "fakeinbox.com", "temp-mail.org",
        "10minutemail.com", "yopmail.com", "trashmail.com"
    }
    domain = email.split("@")[1].lower()
    return domain in disposable_domains


def _check_mx_records(domain: str) -> bool:
    """Check if domain has MX records."""
    try:
        dns.resolver.resolve(domain, 'MX')
        return True
    except Exception:
        return False


def _verify_with_api(email: str) -> Tuple[bool, float, str]:
    """
    Verify email using external API.

    Supports:
    - ZeroBounce (ZEROBOUNCE_API_KEY)
    - NeverBounce (NEVERBOUNCE_API_KEY)
    """
    # Try ZeroBounce
    zerobounce_key = os.getenv("ZEROBOUNCE_API_KEY")
    if zerobounce_key:
        try:
            url = "https://api.zerobounce.net/v2/validate"
            params = {
                "api_key": zerobounce_key,
                "email": email
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "").lower()

                if status == "valid":
                    return (True, 0.95, "Verified by ZeroBounce")
                elif status == "invalid":
                    return (False, 0.95, f"Invalid: {data.get('sub_status', 'unknown')}")
                elif status == "catch-all":
                    return (True, 0.7, "Catch-all domain (may be valid)")
                else:
                    return (True, 0.5, f"Unknown status: {status}")

        except Exception as e:
            logger.debug(f"ZeroBounce verification failed: {e}")

    # Try NeverBounce
    neverbounce_key = os.getenv("NEVERBOUNCE_API_KEY")
    if neverbounce_key:
        try:
            url = "https://api.neverbounce.com/v4/single/check"
            params = {
                "key": neverbounce_key,
                "email": email
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", "").lower()

                if result == "valid":
                    return (True, 0.95, "Verified by NeverBounce")
                elif result == "invalid":
                    return (False, 0.95, "Invalid email")
                elif result == "catchall":
                    return (True, 0.7, "Catch-all domain")
                else:
                    return (True, 0.5, f"Unknown result: {result}")

        except Exception as e:
            logger.debug(f"NeverBounce verification failed: {e}")

    # No API available
    return None


def _is_valid_linkedin_url(url: str) -> bool:
    """Validate LinkedIn URL format."""
    pattern = r'^https?://(www\.)?linkedin\.com/in/[\w-]+/?$'
    return bool(re.match(pattern, url))


def _is_valid_twitter_handle(handle: str) -> bool:
    """Validate Twitter handle format."""
    # Remove @ if present
    handle = handle.lstrip("@")
    # Twitter handles: 1-15 chars, alphanumeric and underscores
    pattern = r'^[a-zA-Z0-9_]{1,15}$'
    return bool(re.match(pattern, handle))


def bulk_validate_emails(emails: list) -> Dict:
    """
    Validate multiple emails efficiently.

    Returns dict mapping email -> validation result
    """
    results = {}
    for email in emails:
        is_valid, confidence, reason = validate_email(email)
        results[email] = {
            "valid": is_valid,
            "confidence": confidence,
            "reason": reason
        }
    return results
