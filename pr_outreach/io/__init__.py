"""PR Outreach IO - Persistence."""
from .outreach_datastore import (
    save_outreach_draft,
    get_pending_emails,
    approve_email,
    mark_as_sent,
    update_response_status,
    get_contacted_articles,
    get_campaign_stats,
)

__all__ = [
    "save_outreach_draft",
    "get_pending_emails",
    "approve_email",
    "mark_as_sent",
    "update_response_status",
    "get_contacted_articles",
    "get_campaign_stats",
]
