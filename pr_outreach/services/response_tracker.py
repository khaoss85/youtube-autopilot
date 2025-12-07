"""
Response Tracker Service - Track email responses and engagement.

Monitors:
- Email opens (via provider webhooks)
- Email replies (via inbox parsing or webhooks)
- Link clicks
"""

import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from yt_autopilot.core.logger import logger

import requests


def track_response(
    outreach_id: str,
    event_type: str,
    event_data: Dict
) -> bool:
    """
    Record a response event.

    Args:
        outreach_id: ID of the outreach package
        event_type: Type of event (open, click, reply, bounce)
        event_data: Event details

    Returns:
        Whether tracking was successful
    """
    logger.info(f"Tracking {event_type} for outreach: {outreach_id}")

    # This would integrate with the datastore
    # For now, just log the event
    event = {
        "outreach_id": outreach_id,
        "event_type": event_type,
        "event_data": event_data,
        "timestamp": datetime.now().isoformat()
    }

    logger.info(f"  Event: {event}")
    return True


def check_responses(
    outreach_ids: List[str],
    since: Optional[datetime] = None
) -> Dict[str, Dict]:
    """
    Check for responses to multiple outreach emails.

    Args:
        outreach_ids: List of outreach IDs to check
        since: Only check events after this time

    Returns:
        Dict mapping outreach_id to response status
    """
    if since is None:
        since = datetime.now() - timedelta(days=7)

    results = {}

    for outreach_id in outreach_ids:
        results[outreach_id] = {
            "opened": False,
            "opened_at": None,
            "replied": False,
            "replied_at": None,
            "reply_sentiment": None,
            "bounced": False,
            "clicked": False
        }

    # Would integrate with email provider webhooks/API
    # SendGrid Event Webhook, Mailgun Events, etc.

    return results


def setup_webhook_handler():
    """
    Set up webhook handler for email events.

    Would typically be a Flask/FastAPI endpoint that receives:
    - SendGrid Event Webhooks
    - Mailgun Webhooks
    """
    pass


def parse_reply_email(email_content: str, original_subject: str) -> Dict:
    """
    Parse a reply email to extract relevant information.

    Args:
        email_content: Full email content
        original_subject: Original email subject

    Returns:
        Dict with parsed reply data
    """
    result = {
        "is_reply": False,
        "sentiment": "neutral",
        "interested": False,
        "asks_for_more_info": False,
        "declines": False,
        "out_of_office": False
    }

    content_lower = email_content.lower()

    # Check for out of office
    ooo_phrases = ["out of office", "automatic reply", "auto-reply", "away from"]
    if any(phrase in content_lower for phrase in ooo_phrases):
        result["out_of_office"] = True
        return result

    result["is_reply"] = True

    # Sentiment analysis (simple keyword-based)
    positive_phrases = [
        "thank you", "thanks", "interested", "sounds good", "great",
        "love to", "would like", "happy to", "sure", "yes",
        "let's", "can you send", "tell me more"
    ]
    negative_phrases = [
        "not interested", "no thanks", "unsubscribe", "stop",
        "remove me", "don't contact", "not relevant", "pass",
        "decline", "not at this time"
    ]

    positive_count = sum(1 for phrase in positive_phrases if phrase in content_lower)
    negative_count = sum(1 for phrase in negative_phrases if phrase in content_lower)

    if positive_count > negative_count:
        result["sentiment"] = "positive"
        result["interested"] = True
    elif negative_count > positive_count:
        result["sentiment"] = "negative"
        result["declines"] = True
    else:
        result["sentiment"] = "neutral"

    # Check for information requests
    info_requests = ["more info", "tell me more", "can you send", "details", "learn more"]
    if any(phrase in content_lower for phrase in info_requests):
        result["asks_for_more_info"] = True

    return result


def analyze_reply_sentiment(reply_text: str, llm_generate_fn=None) -> str:
    """
    Use LLM to analyze reply sentiment more accurately.

    Args:
        reply_text: Text of the reply
        llm_generate_fn: LLM function for analysis

    Returns:
        Sentiment: positive, neutral, negative
    """
    if not llm_generate_fn:
        # Fall back to keyword-based
        result = parse_reply_email(reply_text, "")
        return result["sentiment"]

    prompt = f"""Analyze the sentiment of this email reply to a PR outreach.
Classify as: positive (interested, wants to learn more), neutral (non-committal, asks questions), or negative (not interested, declines).

Reply text:
{reply_text}

Respond with just one word: positive, neutral, or negative"""

    try:
        response = llm_generate_fn(
            role="response_analyzer",
            task=prompt,
            context="",
            style_hints={"response_format": "single_word"}
        )
        sentiment = response.strip().lower()
        if sentiment in ["positive", "neutral", "negative"]:
            return sentiment
    except Exception as e:
        logger.debug(f"LLM sentiment analysis failed: {e}")

    return "neutral"


def get_engagement_stats(campaign_id: str) -> Dict:
    """
    Get engagement statistics for a campaign.

    Returns aggregated stats on opens, replies, etc.
    """
    return {
        "campaign_id": campaign_id,
        "total_sent": 0,
        "total_delivered": 0,
        "total_opened": 0,
        "total_clicked": 0,
        "total_replied": 0,
        "total_bounced": 0,
        "open_rate": 0.0,
        "reply_rate": 0.0,
        "positive_reply_rate": 0.0
    }


def should_follow_up(outreach_id: str, days_since_sent: int = 3) -> bool:
    """
    Determine if a follow-up email should be sent.

    Args:
        outreach_id: Outreach package ID
        days_since_sent: Days since original email

    Returns:
        Whether follow-up is recommended
    """
    # Would check:
    # 1. Email was delivered (not bounced)
    # 2. Email was opened (shows interest)
    # 3. No reply received yet
    # 4. Within follow-up window (e.g., 3-7 days)

    return False  # Placeholder
