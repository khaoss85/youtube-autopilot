"""
Build Outreach Package Pipeline - Main orchestrator for PR outreach.

Similar to build_video_package.py in youtube-autopilot.
Coordinates all agents to produce a complete outreach package.
"""

import uuid
from typing import Optional, List, Tuple, Callable
from datetime import datetime

from pr_outreach.core.schemas import (
    ArticleCandidate,
    AuthorProfile,
    ProductInfo,
    PositioningStrategy,
    OutreachDecision,
    OutreachEmail,
    OutreachPackage,
    OutreachStatus,
    CampaignConfig,
    CampaignStats
)

from pr_outreach.agents.article_hunter import hunt_articles, generate_search_queries
from pr_outreach.agents.article_analyzer import analyze_article, score_articles
from pr_outreach.agents.product_positioner import position_product
from pr_outreach.agents.author_profiler import profile_author
from pr_outreach.agents.outreach_strategist import decide_outreach_strategy
from pr_outreach.agents.email_writer import write_outreach_email
from pr_outreach.agents.spam_checker import check_spam_score
from pr_outreach.agents.personalization_scorer import score_personalization

from pr_outreach.io.outreach_datastore import (
    save_outreach_draft,
    get_contacted_articles,
    add_contacted_article
)

from yt_autopilot.core.logger import logger, log_fallback
from yt_autopilot.services.llm_router import generate_text


def build_outreach_package(
    campaign_config: CampaignConfig,
    article: Optional[ArticleCandidate] = None,
    max_articles_to_process: int = 1,
    use_llm: bool = True,
    dry_run: bool = False
) -> List[OutreachPackage]:
    """
    Build complete outreach packages for a campaign.

    This is the main orchestrator that coordinates all agents.

    Args:
        campaign_config: Campaign configuration
        article: Optional specific article to target (skip discovery)
        max_articles_to_process: Max articles to process in this run
        use_llm: Whether to use LLM for intelligent processing
        dry_run: If True, don't save to datastore

    Returns:
        List of OutreachPackage objects (may be empty if no good targets)
    """
    logger.info("=" * 60)
    logger.info(f"BUILDING OUTREACH PACKAGE")
    logger.info(f"Campaign: {campaign_config.campaign_name}")
    logger.info(f"Product: {campaign_config.product.name}")
    logger.info("=" * 60)

    # Set up LLM function
    llm_fn = generate_text if use_llm else None

    # Get already contacted articles
    contacted = get_contacted_articles(campaign_config.campaign_id)
    logger.info(f"Previously contacted: {len(contacted)} articles")

    packages = []

    # STEP 1: Article Discovery (or use provided article)
    if article:
        articles = [article]
        logger.info(f"Using provided article: {article.title[:50]}")
    else:
        logger.info("\n--- STEP 1: Article Discovery ---")
        articles = _discover_articles(campaign_config, contacted, llm_fn)

    if not articles:
        logger.warning("No suitable articles found")
        return []

    # Process each article (up to max)
    articles_to_process = articles[:max_articles_to_process]
    logger.info(f"Processing {len(articles_to_process)} article(s)")

    for i, target_article in enumerate(articles_to_process):
        logger.info(f"\n{'='*60}")
        logger.info(f"PROCESSING ARTICLE {i+1}/{len(articles_to_process)}")
        logger.info(f"Title: {target_article.title[:60]}")
        logger.info(f"URL: {target_article.url}")
        logger.info(f"{'='*60}")

        try:
            package = _process_single_article(
                target_article,
                campaign_config,
                llm_fn,
                dry_run
            )
            if package:
                packages.append(package)
                logger.info(f"✓ Package created: {package.outreach_id}")
            else:
                logger.warning(f"✗ Failed to create package for article")

        except Exception as e:
            logger.error(f"Error processing article: {e}")
            log_fallback(
                component="BUILD_OUTREACH_PACKAGE",
                fallback_type="ARTICLE_PROCESSING_FAILED",
                reason=str(e),
                impact="MEDIUM"
            )

    logger.info(f"\n{'='*60}")
    logger.info(f"COMPLETED: {len(packages)} package(s) created")
    logger.info(f"{'='*60}")

    return packages


def _discover_articles(
    campaign_config: CampaignConfig,
    contacted: List[str],
    llm_fn: Optional[Callable]
) -> List[ArticleCandidate]:
    """Discover and score articles for outreach."""

    # Generate search queries
    if campaign_config.search_queries:
        queries = campaign_config.search_queries
    else:
        queries = generate_search_queries(
            campaign_config.product,
            campaign_config.niche_id
        )

    logger.info(f"Search queries: {queries}")

    # Hunt for articles
    articles = hunt_articles(
        search_queries=queries,
        product=campaign_config.product,
        campaign_config=campaign_config,
        max_results=50,
        contacted_articles=contacted,
        llm_generate_fn=llm_fn
    )

    logger.info(f"Found {len(articles)} candidate articles")

    if not articles:
        return []

    # GATE 1: Post-Discovery Validation
    if _is_gate_enabled(campaign_config, "post_discovery"):
        articles = _validate_discovery(articles, campaign_config)
        logger.info(f"After discovery validation: {len(articles)} articles")

    # Score and rank articles
    scored = score_articles(articles, campaign_config.product, llm_fn)

    # Select top articles
    top_articles = scored[:campaign_config.max_articles_per_run]
    logger.info(f"Selected top {len(top_articles)} articles")

    return top_articles


def _process_single_article(
    article: ArticleCandidate,
    campaign_config: CampaignConfig,
    llm_fn: Optional[Callable],
    dry_run: bool
) -> Optional[OutreachPackage]:
    """Process a single article through the full pipeline."""

    product = campaign_config.product

    # STEP 2: Analyze Article
    logger.info("\n--- STEP 2: Article Analysis ---")
    analyzed_article = analyze_article(article, product, llm_fn)

    # GATE 2: Post-Analysis Validation
    if _is_gate_enabled(campaign_config, "post_analysis"):
        if not _validate_analysis(analyzed_article, campaign_config):
            logger.warning("Article failed post-analysis validation")
            return None

    # STEP 3: Product Positioning
    logger.info("\n--- STEP 3: Product Positioning ---")
    positioning = position_product(analyzed_article, product, llm_fn)

    # STEP 4: Author Research
    logger.info("\n--- STEP 4: Author Research ---")
    author = profile_author(analyzed_article, llm_fn)

    if not author.email and not author.linkedin_url:
        logger.warning("No contact information found for author")
        # Could still proceed with publication contact
        # For now, skip articles without author contact
        return None

    # STEP 5: Outreach Strategy
    logger.info("\n--- STEP 5: Outreach Strategy ---")
    strategy = decide_outreach_strategy(
        analyzed_article, author, product, positioning, campaign_config, llm_fn
    )

    # STEP 6: Email Generation
    logger.info("\n--- STEP 6: Email Generation ---")
    email = write_outreach_email(
        analyzed_article, author, product, positioning, strategy, campaign_config, llm_fn
    )

    # GATE 3: Post-Email Validation
    logger.info("\n--- GATE: Post-Email Validation ---")

    # Spam check
    spam_score, spam_summary, spam_details = check_spam_score(email, llm_fn)
    logger.info(f"Spam score: {spam_score:.2f} - {spam_summary}")

    # Personalization check
    pers_score, pers_summary, pers_details = score_personalization(
        email, analyzed_article, author, llm_fn
    )
    logger.info(f"Personalization: {pers_score:.2f} - {pers_summary}")

    # Overall quality score
    quality_score = _calculate_quality_score(spam_score, pers_score)
    logger.info(f"Overall quality: {quality_score:.2f}")

    # Check thresholds
    if _is_gate_enabled(campaign_config, "post_email"):
        gate_config = campaign_config.validation_gates.get("post_email")
        threshold = gate_config.threshold if gate_config else 0.6

        if quality_score < threshold:
            logger.warning(f"Quality {quality_score:.2f} below threshold {threshold}")
            if gate_config and gate_config.blocking:
                # Try to regenerate email
                email, quality_score = _attempt_email_improvement(
                    email, spam_details, pers_details, analyzed_article, author,
                    product, positioning, strategy, campaign_config, llm_fn
                )
                if quality_score < threshold:
                    logger.warning("Email quality still below threshold after retry")
                    return None

    # STEP 7: Create Outreach Package
    logger.info("\n--- STEP 7: Creating Package ---")

    package = OutreachPackage(
        outreach_id=str(uuid.uuid4()),
        campaign_id=campaign_config.campaign_id,
        status=OutreachStatus.PENDING_REVIEW,
        article=analyzed_article,
        author=author,
        positioning=positioning,
        strategy=strategy,
        email=email,
        product=product,
        spam_score=spam_score,
        personalization_score=pers_score,
        overall_quality_score=quality_score,
        article_selection_reasoning=f"Score: {analyzed_article.composite_score:.2f}, DA: {analyzed_article.domain_authority}",
        positioning_reasoning=positioning.reasoning,
        strategy_reasoning=strategy.reasoning,
        email_generation_reasoning=f"Angle: {strategy.email_angle.value}, Personalization: {strategy.personalization_level}",
        created_at=datetime.now()
    )

    # Save to datastore
    if not dry_run:
        save_outreach_draft(package)
        add_contacted_article(campaign_config.campaign_id, analyzed_article.url)
        logger.info(f"Package saved: {package.outreach_id}")
    else:
        logger.info(f"[DRY RUN] Package would be saved: {package.outreach_id}")

    return package


def _is_gate_enabled(config: CampaignConfig, gate_name: str) -> bool:
    """Check if a validation gate is enabled."""
    gates = config.validation_gates
    if gate_name not in gates:
        return True  # Default to enabled
    return gates[gate_name].enabled


def _validate_discovery(
    articles: List[ArticleCandidate],
    config: CampaignConfig
) -> List[ArticleCandidate]:
    """Validate discovered articles."""
    valid = []

    for article in articles:
        # Skip very low DA domains
        if article.domain_authority < 20:
            continue

        # Skip very old articles
        if article.recency_score < 0.1:
            continue

        # Skip irrelevant articles
        if article.relevance_score < 0.3:
            continue

        valid.append(article)

    return valid


def _validate_analysis(article: ArticleCandidate, config: CampaignConfig) -> bool:
    """Validate article analysis results."""
    # Must have identified at least one insertion opportunity
    if not article.insertion_opportunities:
        return False

    # Must have reasonable opportunity score
    if article.opportunity_score < 0.3:
        return False

    return True


def _calculate_quality_score(spam_score: float, pers_score: float) -> float:
    """Calculate overall quality score from spam and personalization."""
    # Invert spam score (0 spam = good)
    spam_quality = 1.0 - spam_score

    # Weight: 40% spam-free, 60% personalization
    quality = (spam_quality * 0.4) + (pers_score * 0.6)

    return quality


def _attempt_email_improvement(
    email: OutreachEmail,
    spam_details: dict,
    pers_details: dict,
    article: ArticleCandidate,
    author: AuthorProfile,
    product: ProductInfo,
    positioning: PositioningStrategy,
    strategy: OutreachDecision,
    config: CampaignConfig,
    llm_fn: Optional[Callable]
) -> Tuple[OutreachEmail, float]:
    """Attempt to improve email quality."""
    logger.info("Attempting email improvement...")

    # Regenerate with higher personalization
    strategy.personalization_level = "high"

    improved_email = write_outreach_email(
        article, author, product, positioning, strategy, config, llm_fn
    )

    # Re-check quality
    spam_score, _, _ = check_spam_score(improved_email, llm_fn)
    pers_score, _, _ = score_personalization(improved_email, article, author, llm_fn)
    quality_score = _calculate_quality_score(spam_score, pers_score)

    logger.info(f"Improved quality: {quality_score:.2f}")

    return improved_email, quality_score


def build_outreach_batch(
    campaign_config: CampaignConfig,
    max_packages: int = 5,
    use_llm: bool = True
) -> List[OutreachPackage]:
    """
    Build multiple outreach packages in batch.

    Convenience function for processing multiple articles.
    """
    return build_outreach_package(
        campaign_config=campaign_config,
        max_articles_to_process=max_packages,
        use_llm=use_llm
    )


def get_pipeline_status(campaign_id: str) -> dict:
    """Get status of pipeline for a campaign."""
    from pr_outreach.io.outreach_datastore import get_campaign_stats

    stats = get_campaign_stats(campaign_id)

    return {
        "campaign_id": campaign_id,
        "total_generated": stats.total_emails_generated,
        "pending_review": 0,  # Would query datastore
        "approved": 0,
        "sent": stats.total_emails_sent,
        "replied": stats.total_replies,
        "reply_rate": stats.reply_rate
    }
