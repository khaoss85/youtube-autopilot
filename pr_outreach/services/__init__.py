"""PR Outreach Services - External integrations."""
from .article_scraper import scrape_article
from .author_finder import find_author_contacts
from .contact_validator import validate_email, validate_contact
from .domain_analyzer import analyze_domain
from .email_sender import send_email
from .response_tracker import track_response, check_responses

__all__ = [
    "scrape_article",
    "find_author_contacts",
    "validate_email",
    "validate_contact",
    "analyze_domain",
    "send_email",
    "track_response",
    "check_responses",
]
