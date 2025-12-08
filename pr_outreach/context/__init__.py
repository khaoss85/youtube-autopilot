"""
Product context module for PR outreach.

Provides structured context about products for agents.
"""

from .arvo_product_context import (
    ARVO_CONTEXT,
    get_context_for_agent,
    get_short_pitch,
    get_key_differentiators,
    get_target_audience_description,
    format_for_email_context
)

__all__ = [
    "ARVO_CONTEXT",
    "get_context_for_agent",
    "get_short_pitch",
    "get_key_differentiators",
    "get_target_audience_description",
    "format_for_email_context"
]
