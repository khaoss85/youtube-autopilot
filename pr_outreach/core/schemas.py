"""
PR Outreach Core Schemas - Data models for outreach automation.

This module defines all Pydantic models for the PR outreach pipeline.
These are the single source of truth for data contracts.

Mirrors the pattern from yt_autopilot/core/schemas.py
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum


class OutreachStatus(str, Enum):
    """Status states for outreach packages."""
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    SENT = "SENT"
    REPLIED = "REPLIED"
    NO_RESPONSE = "NO_RESPONSE"
    REJECTED = "REJECTED"
    BOUNCED = "BOUNCED"


class EmailAngle(str, Enum):
    """Email approach angles."""
    DIRECT_PITCH = "direct_pitch"
    VALUE_FIRST = "value_first"
    RELATIONSHIP_BUILDING = "relationship_building"
    UPDATE_REQUEST = "update_request"
    RESOURCE_OFFER = "resource_offer"


class InsertionType(str, Enum):
    """Types of product insertion opportunities."""
    LISTICLE_ADDITION = "listicle_addition"
    MENTION_OPPORTUNITY = "mention_opportunity"
    COMPARISON_INCLUSION = "comparison_inclusion"
    EXPERT_QUOTE = "expert_quote"
    RESOURCE_LINK = "resource_link"
    UPDATE_EXISTING = "update_existing"


class ProductInfo(BaseModel):
    """
    Information about the product to promote in outreach.
    """
    name: str = Field(..., description="Product name")
    tagline: str = Field(..., description="Short product tagline/description")
    website_url: str = Field(..., description="Product website URL")
    category: str = Field(..., description="Product category (e.g., 'fitness app', 'AI tool')")
    key_features: List[str] = Field(default_factory=list, description="Key product features/benefits")
    unique_value_prop: str = Field(..., description="What makes this product unique")
    target_audience: str = Field(..., description="Who the product is for")
    pricing_info: Optional[str] = Field(None, description="Pricing information if relevant")
    media_kit_url: Optional[str] = Field(None, description="Link to media kit/press assets")
    founder_name: Optional[str] = Field(None, description="Founder/CEO name for personalization")
    company_story: Optional[str] = Field(None, description="Brief company/founding story")


class ArticleCandidate(BaseModel):
    """
    Represents an article identified as a potential outreach target.

    Similar to TrendCandidate in youtube-autopilot but for articles.
    """
    url: str = Field(..., description="Full article URL")
    title: str = Field(..., description="Article title")
    domain: str = Field(..., description="Publication domain (e.g., 'techcrunch.com')")
    domain_authority: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Domain Authority score (0-100, from Ahrefs/Moz)"
    )
    publication_date: Optional[datetime] = Field(None, description="Article publication date")
    author_name: Optional[str] = Field(None, description="Article author name")
    author_url: Optional[str] = Field(None, description="Author profile URL on the publication")

    # Content analysis
    content_excerpt: str = Field(default="", description="Relevant excerpt from the article")
    full_content: Optional[str] = Field(None, description="Full article content (after scraping)")
    word_count: int = Field(default=0, ge=0, description="Article word count")

    # Scoring
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relevance to product/topic (0-1)"
    )
    recency_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How recent the article is (0-1)"
    )
    opportunity_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Insertion opportunity score (0-1)"
    )
    composite_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall priority score (0-1)"
    )

    # Insertion opportunities
    insertion_opportunities: List[str] = Field(
        default_factory=list,
        description="Identified insertion points in the article"
    )
    insertion_type: Optional[InsertionType] = Field(
        None,
        description="Primary type of insertion opportunity"
    )

    # Source tracking
    source: str = Field(default="google", description="Discovery source (google, ahrefs, manual)")
    discovered_at: datetime = Field(default_factory=datetime.now, description="When this article was discovered")


class AuthorProfile(BaseModel):
    """
    Profile information for an article author.

    Used for personalization and contact discovery.
    """
    name: str = Field(..., description="Author full name")

    # Contact information
    email: Optional[str] = Field(None, description="Author email address")
    email_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in email validity (0-1)"
    )
    email_verified: bool = Field(default=False, description="Whether email was verified")

    # Social profiles
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    twitter_handle: Optional[str] = Field(None, description="Twitter/X handle")
    personal_website: Optional[str] = Field(None, description="Personal website/blog")

    # Professional info
    bio: Optional[str] = Field(None, description="Author bio/description")
    job_title: Optional[str] = Field(None, description="Current job title")
    company: Optional[str] = Field(None, description="Current company/publication")

    # Writing analysis
    recent_articles: List[str] = Field(
        default_factory=list,
        description="URLs of recent articles by this author"
    )
    writing_style: Optional[str] = Field(
        None,
        description="AI analysis of author's writing style"
    )
    topics_covered: List[str] = Field(
        default_factory=list,
        description="Topics this author frequently covers"
    )

    # Scoring
    reachability_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How reachable this author is (0-1)"
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How relevant author is to our product (0-1)"
    )


class PositioningStrategy(BaseModel):
    """
    Strategy for positioning the product within an article.
    """
    insertion_type: InsertionType = Field(..., description="Type of insertion to pursue")
    target_section: str = Field(..., description="Which section of article to target")
    positioning_rationale: str = Field(
        ...,
        description="Why the product belongs in this article"
    )
    suggested_text: str = Field(
        ...,
        description="Suggested text/description for inclusion"
    )
    value_to_readers: str = Field(
        ...,
        description="How this addition benefits the article's readers"
    )
    competitive_context: Optional[str] = Field(
        None,
        description="How product compares to others mentioned"
    )
    reasoning: str = Field(
        ...,
        description="AI reasoning for this positioning strategy"
    )


class OutreachDecision(BaseModel):
    """
    Strategic decision for how to approach the outreach.

    Similar to EditorialDecision in youtube-autopilot.
    """
    email_angle: EmailAngle = Field(..., description="Primary email approach")
    personalization_level: str = Field(
        default="high",
        description="Level of personalization: low|medium|high"
    )
    cta_type: str = Field(
        ...,
        description="Type of call-to-action (update_request, feature_addition, etc.)"
    )
    tone: str = Field(
        default="friendly_professional",
        description="Email tone (friendly_professional, formal, casual)"
    )
    urgency_level: str = Field(
        default="low",
        description="Urgency level: low|medium|high"
    )
    follow_up_strategy: str = Field(
        default="single_followup",
        description="Follow-up plan: none|single_followup|sequence"
    )
    reasoning: str = Field(..., description="AI reasoning for this strategy")


class OutreachEmail(BaseModel):
    """
    Generated outreach email content.

    Similar to VideoScript in youtube-autopilot.
    """
    # Subject options
    subject_line: str = Field(..., description="Primary subject line")
    subject_line_alt: Optional[str] = Field(None, description="Alternative subject for A/B")

    # Email body components
    opening_hook: str = Field(
        ...,
        description="Personalized opening line referencing article/author"
    )
    connection_point: str = Field(
        ...,
        description="Why we're reaching out (connection to their work)"
    )
    value_proposition: str = Field(
        ...,
        description="What's in it for them/their readers"
    )
    insertion_suggestion: str = Field(
        ...,
        description="Specific, helpful suggestion for inclusion"
    )
    call_to_action: str = Field(
        ...,
        description="Soft, non-pushy CTA"
    )

    # Full content
    full_body: str = Field(..., description="Complete email body text")

    # Optional elements
    ps_line: Optional[str] = Field(
        None,
        description="P.S. line for additional engagement"
    )
    signature: str = Field(
        default="",
        description="Email signature"
    )

    # Metadata
    word_count: int = Field(default=0, description="Email word count")
    reading_time_seconds: int = Field(default=0, description="Estimated reading time")


class SenderPersona(BaseModel):
    """
    Persona for the email sender.

    Similar to narrator_persona in youtube-autopilot workspaces.
    """
    enabled: bool = Field(default=True, description="Whether persona is active")
    name: str = Field(..., description="Sender name")
    email: str = Field(..., description="Sender email address")
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")

    # Persona characteristics
    tone_of_address: str = Field(
        default="friendly_professional",
        description="How to address recipients"
    )
    signature_style: str = Field(
        default="warm",
        description="Signature style: formal|warm|casual"
    )

    # Credibility
    credibility_markers: List[str] = Field(
        default_factory=list,
        description="Credentials to include when relevant"
    )

    # Communication style
    preferred_greetings: List[str] = Field(
        default_factory=lambda: ["Hi", "Hello"],
        description="Preferred email greetings"
    )
    preferred_closings: List[str] = Field(
        default_factory=lambda: ["Best", "Thanks", "Cheers"],
        description="Preferred email closings"
    )


class ValidationGate(BaseModel):
    """Configuration for a validation gate."""
    enabled: bool = Field(default=True, description="Whether gate is active")
    blocking: bool = Field(default=True, description="Whether gate blocks on failure")
    threshold: float = Field(default=0.7, description="Minimum score to pass")


class CampaignConfig(BaseModel):
    """
    Configuration for an outreach campaign.

    Similar to workspace config in youtube-autopilot.
    """
    campaign_id: str = Field(..., description="Unique campaign identifier")
    campaign_name: str = Field(..., description="Human-readable campaign name")

    # Target configuration
    niche_id: str = Field(..., description="Target niche (fitness, tech, finance, etc.)")
    target_language: str = Field(default="en", description="Target language code")
    search_queries: List[str] = Field(
        default_factory=list,
        description="Search queries to find articles"
    )

    # Product to promote
    product: ProductInfo = Field(..., description="Product information")

    # Sender persona
    sender_persona: SenderPersona = Field(..., description="Email sender persona")

    # Email configuration
    email_tone: str = Field(
        default="friendly_professional",
        description="Overall email tone"
    )
    avoid_mentions: List[str] = Field(
        default_factory=list,
        description="Topics/words to avoid mentioning"
    )

    # Tracking
    contacted_articles: List[str] = Field(
        default_factory=list,
        description="URLs of already contacted articles (dedup)"
    )

    # Validation gates
    validation_gates: Dict[str, ValidationGate] = Field(
        default_factory=lambda: {
            "post_discovery": ValidationGate(enabled=True, blocking=True),
            "post_analysis": ValidationGate(enabled=True, blocking=True),
            "post_email": ValidationGate(enabled=True, blocking=True),
            "pre_send": ValidationGate(enabled=True, blocking=True),
        },
        description="Validation gate configurations"
    )

    # Limits
    max_articles_per_run: int = Field(default=10, description="Max articles to process per run")
    max_emails_per_day: int = Field(default=20, description="Max emails to send per day")

    # Product context module (for agents to load detailed product info)
    context_module: Optional[str] = Field(
        None,
        description="Python module path for product context (e.g., 'pr_outreach.context.arvo_product_context')"
    )

    # AI authority notice (mirrors youtube-autopilot pattern)
    _ai_authority_notice: Dict = Field(
        default_factory=lambda: {
            "version": "1.0",
            "note": "Email angle, personalization, CTA are decided by AI agents",
            "ai_agents": [
                "OutreachStrategist",
                "EmailWriter",
                "SpamChecker",
                "PersonalizationScorer"
            ]
        }
    )


class OutreachPackage(BaseModel):
    """
    Complete outreach package ready for human review and sending.

    Similar to ContentPackage in youtube-autopilot.
    """
    # Identity
    outreach_id: str = Field(..., description="Unique outreach identifier")
    campaign_id: str = Field(..., description="Parent campaign ID")

    # Status
    status: OutreachStatus = Field(
        default=OutreachStatus.DRAFT,
        description="Current status of this outreach"
    )

    # Core components
    article: ArticleCandidate = Field(..., description="Target article")
    author: AuthorProfile = Field(..., description="Author profile")
    positioning: PositioningStrategy = Field(..., description="Positioning strategy")
    strategy: OutreachDecision = Field(..., description="Outreach strategy")
    email: OutreachEmail = Field(..., description="Generated email")
    product: ProductInfo = Field(..., description="Product being promoted")

    # Quality scores
    spam_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Spam likelihood score (0=not spam, 1=spam)"
    )
    personalization_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Personalization quality score (0-1)"
    )
    overall_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall quality score (0-1)"
    )

    # AI reasoning (for transparency)
    article_selection_reasoning: str = Field(
        default="",
        description="Why this article was selected"
    )
    positioning_reasoning: str = Field(
        default="",
        description="Reasoning for positioning strategy"
    )
    strategy_reasoning: str = Field(
        default="",
        description="Reasoning for outreach strategy"
    )
    email_generation_reasoning: str = Field(
        default="",
        description="Reasoning for email content"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    approved_by: Optional[str] = Field(None, description="Who approved")
    sent_at: Optional[datetime] = Field(None, description="Send timestamp")

    # Response tracking
    opened: bool = Field(default=False, description="Whether email was opened")
    opened_at: Optional[datetime] = Field(None, description="Open timestamp")
    replied: bool = Field(default=False, description="Whether reply was received")
    replied_at: Optional[datetime] = Field(None, description="Reply timestamp")
    reply_sentiment: Optional[str] = Field(
        None,
        description="Sentiment of reply: positive|neutral|negative"
    )

    # Rejection info (if rejected)
    rejection_reason: Optional[str] = Field(None, description="Why this was rejected")


class CampaignStats(BaseModel):
    """Statistics for a campaign."""
    campaign_id: str = Field(..., description="Campaign ID")
    total_articles_discovered: int = Field(default=0)
    total_emails_generated: int = Field(default=0)
    total_emails_sent: int = Field(default=0)
    total_opens: int = Field(default=0)
    total_replies: int = Field(default=0)
    positive_replies: int = Field(default=0)
    neutral_replies: int = Field(default=0)
    negative_replies: int = Field(default=0)

    # Rates
    open_rate: float = Field(default=0.0, description="Open rate (0-1)")
    reply_rate: float = Field(default=0.0, description="Reply rate (0-1)")
    positive_reply_rate: float = Field(default=0.0, description="Positive reply rate (0-1)")

    # Quality metrics
    avg_spam_score: float = Field(default=0.0)
    avg_personalization_score: float = Field(default=0.0)
    avg_quality_score: float = Field(default=0.0)
