"""
Outreach Datastore - Persistence for PR outreach packages.

Similar to datastore.py in youtube-autopilot.
Uses JSONL format for simple, append-only storage.
"""

import json
import os
from typing import List, Optional, Dict
from datetime import datetime
from pathlib import Path

from pr_outreach.core.schemas import (
    OutreachPackage,
    OutreachStatus,
    CampaignStats
)
from yt_autopilot.core.logger import logger


# Default datastore path
OUTREACH_DATASTORE_PATH = "data/outreach_records.jsonl"
CONTACTED_ARTICLES_PATH = "data/contacted_articles.json"


def _get_datastore_path() -> str:
    """Get path to outreach datastore file."""
    path = os.getenv("OUTREACH_DATASTORE_PATH", OUTREACH_DATASTORE_PATH)
    # Ensure directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def _get_contacted_path() -> str:
    """Get path to contacted articles file."""
    path = os.getenv("CONTACTED_ARTICLES_PATH", CONTACTED_ARTICLES_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def save_outreach_draft(package: OutreachPackage) -> str:
    """
    Save an outreach package to the datastore.

    Args:
        package: OutreachPackage to save

    Returns:
        outreach_id of saved package
    """
    path = _get_datastore_path()

    # Convert to dict for JSON serialization
    record = {
        "outreach_id": package.outreach_id,
        "campaign_id": package.campaign_id,
        "status": package.status.value,

        # Article info
        "article_url": package.article.url,
        "article_title": package.article.title,
        "article_domain": package.article.domain,
        "article_domain_authority": package.article.domain_authority,

        # Author info
        "author_name": package.author.name,
        "author_email": package.author.email,
        "author_email_verified": package.author.email_verified,
        "author_linkedin": package.author.linkedin_url,
        "author_twitter": package.author.twitter_handle,

        # Email content
        "email_subject": package.email.subject_line,
        "email_body": package.email.full_body,

        # Scores
        "spam_score": package.spam_score,
        "personalization_score": package.personalization_score,
        "overall_quality_score": package.overall_quality_score,

        # Reasoning (AI Decision Log)
        "article_selection_reasoning": package.article_selection_reasoning,
        "positioning_reasoning": package.positioning_reasoning,
        "strategy_reasoning": package.strategy_reasoning,
        "email_generation_reasoning": package.email_generation_reasoning,

        # Timestamps
        "created_at": package.created_at.isoformat(),
        "approved_at": package.approved_at.isoformat() if package.approved_at else None,
        "approved_by": package.approved_by,
        "sent_at": package.sent_at.isoformat() if package.sent_at else None,

        # Response tracking
        "opened": package.opened,
        "opened_at": package.opened_at.isoformat() if package.opened_at else None,
        "replied": package.replied,
        "replied_at": package.replied_at.isoformat() if package.replied_at else None,
        "reply_sentiment": package.reply_sentiment,

        # Full objects for reference
        "full_article": package.article.model_dump(),
        "full_author": package.author.model_dump(),
        "full_positioning": package.positioning.model_dump(),
        "full_strategy": package.strategy.model_dump(),
        "full_email": package.email.model_dump(),
        "full_product": package.product.model_dump()
    }

    # Append to JSONL file
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")

    logger.info(f"Saved outreach package: {package.outreach_id}")
    return package.outreach_id


def get_pending_emails(campaign_id: Optional[str] = None) -> List[Dict]:
    """
    Get emails pending human review.

    Args:
        campaign_id: Optional filter by campaign

    Returns:
        List of pending outreach records
    """
    path = _get_datastore_path()
    pending = []

    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get("status") == OutreachStatus.PENDING_REVIEW.value:
                    if campaign_id is None or record.get("campaign_id") == campaign_id:
                        pending.append(record)
            except json.JSONDecodeError:
                continue

    return pending


def get_outreach_by_id(outreach_id: str) -> Optional[Dict]:
    """Get a specific outreach record by ID."""
    path = _get_datastore_path()

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get("outreach_id") == outreach_id:
                    return record
            except json.JSONDecodeError:
                continue

    return None


def approve_email(outreach_id: str, approved_by: str) -> bool:
    """
    Approve an email for sending.

    Args:
        outreach_id: ID of outreach to approve
        approved_by: Who approved (email/name)

    Returns:
        Whether approval succeeded
    """
    return _update_record(
        outreach_id,
        {
            "status": OutreachStatus.APPROVED.value,
            "approved_at": datetime.now().isoformat(),
            "approved_by": approved_by
        }
    )


def reject_email(outreach_id: str, reason: str) -> bool:
    """
    Reject an email.

    Args:
        outreach_id: ID of outreach to reject
        reason: Rejection reason

    Returns:
        Whether rejection succeeded
    """
    return _update_record(
        outreach_id,
        {
            "status": OutreachStatus.REJECTED.value,
            "rejection_reason": reason
        }
    )


def mark_as_sent(
    outreach_id: str,
    message_id: Optional[str] = None
) -> bool:
    """
    Mark an email as sent.

    Args:
        outreach_id: ID of outreach
        message_id: Provider message ID

    Returns:
        Whether update succeeded
    """
    return _update_record(
        outreach_id,
        {
            "status": OutreachStatus.SENT.value,
            "sent_at": datetime.now().isoformat(),
            "message_id": message_id
        }
    )


def update_response_status(
    outreach_id: str,
    opened: bool = False,
    replied: bool = False,
    reply_sentiment: Optional[str] = None
) -> bool:
    """
    Update response tracking for an outreach.

    Args:
        outreach_id: ID of outreach
        opened: Whether email was opened
        replied: Whether reply was received
        reply_sentiment: Sentiment of reply

    Returns:
        Whether update succeeded
    """
    updates = {}

    if opened:
        updates["opened"] = True
        updates["opened_at"] = datetime.now().isoformat()

    if replied:
        updates["replied"] = True
        updates["replied_at"] = datetime.now().isoformat()
        updates["status"] = OutreachStatus.REPLIED.value

    if reply_sentiment:
        updates["reply_sentiment"] = reply_sentiment

    return _update_record(outreach_id, updates)


def _update_record(outreach_id: str, updates: Dict) -> bool:
    """Update a record in the datastore."""
    path = _get_datastore_path()

    if not os.path.exists(path):
        return False

    # Read all records
    records = []
    updated = False

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get("outreach_id") == outreach_id:
                    record.update(updates)
                    updated = True
                records.append(record)
            except json.JSONDecodeError:
                continue

    if not updated:
        return False

    # Write back
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, default=str) + "\n")

    return True


def get_contacted_articles(campaign_id: str) -> List[str]:
    """
    Get list of already contacted article URLs for a campaign.

    Used for deduplication.
    """
    path = _get_contacted_path()

    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get(campaign_id, [])
    except (json.JSONDecodeError, IOError):
        return []


def add_contacted_article(campaign_id: str, url: str) -> None:
    """Add an article URL to the contacted list."""
    path = _get_contacted_path()

    data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            data = {}

    if campaign_id not in data:
        data[campaign_id] = []

    if url not in data[campaign_id]:
        data[campaign_id].append(url)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_campaign_stats(campaign_id: str) -> CampaignStats:
    """
    Get statistics for a campaign.

    Aggregates data from all outreach records.
    """
    path = _get_datastore_path()

    stats = CampaignStats(campaign_id=campaign_id)

    if not os.path.exists(path):
        return stats

    total_spam = 0.0
    total_pers = 0.0
    total_quality = 0.0
    count = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get("campaign_id") != campaign_id:
                    continue

                count += 1
                stats.total_emails_generated += 1

                status = record.get("status")

                if status == OutreachStatus.SENT.value:
                    stats.total_emails_sent += 1

                if record.get("opened"):
                    stats.total_opens += 1

                if record.get("replied"):
                    stats.total_replies += 1
                    sentiment = record.get("reply_sentiment")
                    if sentiment == "positive":
                        stats.positive_replies += 1
                    elif sentiment == "negative":
                        stats.negative_replies += 1
                    else:
                        stats.neutral_replies += 1

                # Accumulate scores
                total_spam += record.get("spam_score", 0)
                total_pers += record.get("personalization_score", 0)
                total_quality += record.get("overall_quality_score", 0)

            except json.JSONDecodeError:
                continue

    # Calculate rates
    if stats.total_emails_sent > 0:
        stats.open_rate = stats.total_opens / stats.total_emails_sent
        stats.reply_rate = stats.total_replies / stats.total_emails_sent

    if stats.total_replies > 0:
        stats.positive_reply_rate = stats.positive_replies / stats.total_replies

    # Calculate averages
    if count > 0:
        stats.avg_spam_score = total_spam / count
        stats.avg_personalization_score = total_pers / count
        stats.avg_quality_score = total_quality / count

    return stats


def get_all_outreach(
    campaign_id: Optional[str] = None,
    status: Optional[OutreachStatus] = None
) -> List[Dict]:
    """
    Get all outreach records with optional filters.

    Args:
        campaign_id: Filter by campaign
        status: Filter by status

    Returns:
        List of matching records
    """
    path = _get_datastore_path()
    results = []

    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())

                if campaign_id and record.get("campaign_id") != campaign_id:
                    continue

                if status and record.get("status") != status.value:
                    continue

                results.append(record)

            except json.JSONDecodeError:
                continue

    return results


def reset_campaign_data(campaign_id: str, dry_run: bool = True) -> int:
    """
    Reset all data for a campaign.

    Args:
        campaign_id: Campaign to reset
        dry_run: If True, don't actually delete

    Returns:
        Number of records that would be/were deleted
    """
    path = _get_datastore_path()

    if not os.path.exists(path):
        return 0

    records_to_keep = []
    deleted_count = 0

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get("campaign_id") == campaign_id:
                    deleted_count += 1
                else:
                    records_to_keep.append(record)
            except json.JSONDecodeError:
                continue

    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            for record in records_to_keep:
                f.write(json.dumps(record, default=str) + "\n")

        # Also clear contacted articles
        contacted_path = _get_contacted_path()
        if os.path.exists(contacted_path):
            with open(contacted_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if campaign_id in data:
                del data[campaign_id]

            with open(contacted_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    return deleted_count
