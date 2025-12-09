"""
Article Analyzer Agent - Analyze articles for insertion opportunities.

Extracts content, identifies insertion points, and scores fit.
"""

from typing import List, Dict, Optional, Callable
from datetime import datetime

from pr_outreach.core.schemas import (
    ArticleCandidate,
    ProductInfo,
    InsertionType
)
from pr_outreach.services.article_scraper import scrape_article
from yt_autopilot.core.logger import logger, log_fallback


def analyze_article(
    article: ArticleCandidate,
    product: ProductInfo,
    llm_generate_fn: Optional[Callable] = None
) -> ArticleCandidate:
    """
    Perform deep analysis of an article for PR opportunities.

    Args:
        article: ArticleCandidate to analyze
        product: Product to position
        llm_generate_fn: LLM function for analysis

    Returns:
        ArticleCandidate with enriched analysis data
    """
    logger.info(f"Analyzing article: {article.title[:50]}...")

    # Scrape full content if not already done
    if not article.full_content:
        scraped = scrape_article(article.url)
        if scraped["success"]:
            article.full_content = scraped["content"]
            article.word_count = scraped["word_count"]
            if scraped["author"] and not article.author_name:
                article.author_name = scraped["author"]
            if scraped["publish_date"] and not article.publication_date:
                article.publication_date = scraped["publish_date"]
        else:
            # Use content_excerpt as fallback when scraping fails
            logger.info(f"  ⚠️ Scraping failed, using excerpt for analysis")
            article.full_content = article.content_excerpt or ""

    # Identify insertion opportunities
    if llm_generate_fn and article.full_content:
        opportunities = _identify_opportunities_llm(
            article, product, llm_generate_fn
        )
    else:
        opportunities = _identify_opportunities_heuristic(article, product)

    article.insertion_opportunities = opportunities["opportunities"]
    article.insertion_type = opportunities["primary_type"]
    article.opportunity_score = opportunities["score"]

    logger.info(f"  Found {len(article.insertion_opportunities)} insertion opportunities")
    logger.info(f"  Primary type: {article.insertion_type}")

    return article


def score_articles(
    articles: List[ArticleCandidate],
    product: ProductInfo,
    llm_generate_fn: Optional[Callable] = None
) -> List[ArticleCandidate]:
    """
    Score multiple articles for outreach priority.

    Returns articles sorted by composite score.
    """
    scored = []

    for article in articles:
        # Analyze each article
        analyzed = analyze_article(article, product, llm_generate_fn)

        # Calculate final composite score
        analyzed.composite_score = _calculate_final_score(analyzed, product)
        scored.append(analyzed)

    # Sort by score
    scored.sort(key=lambda x: x.composite_score, reverse=True)

    return scored


def _identify_opportunities_llm(
    article: ArticleCandidate,
    product: ProductInfo,
    llm_generate_fn: Callable
) -> Dict:
    """Use LLM to identify insertion opportunities."""
    prompt = f"""Analyze this article for PR outreach opportunities.

PRODUCT TO PROMOTE:
- Name: {product.name}
- Category: {product.category}
- Tagline: {product.tagline}
- Key Features: {', '.join(product.key_features[:3])}
- Unique Value: {product.unique_value_prop}

ARTICLE:
Title: {article.title}
URL: {article.url}

Content (first 3000 chars):
{article.full_content[:3000] if article.full_content else article.content_excerpt}

TASK:
1. Identify specific places where the product could be naturally mentioned
2. Determine the best insertion type:
   - listicle_addition: Article is a list, product could be added
   - mention_opportunity: Product could be mentioned in passing
   - comparison_inclusion: Product could join a comparison
   - expert_quote: Could offer expert commentary
   - resource_link: Could be added as a resource
   - update_existing: Article outdated, could suggest update

3. List specific opportunities (quote the relevant section)
4. Rate the overall fit (0.0 to 1.0)

Respond in this exact format:
INSERTION_TYPE: [type]
OPPORTUNITIES:
- [opportunity 1]
- [opportunity 2]
FIT_SCORE: [0.0-1.0]
REASONING: [brief explanation]"""

    try:
        response = llm_generate_fn(
            role="article_analyst",
            task=prompt,
            context="",
            style_hints={}
        )

        return _parse_opportunity_response(response)

    except Exception as e:
        logger.warning(f"LLM analysis failed: {e}")
        log_fallback(
            component="ARTICLE_ANALYZER",
            fallback_type="LLM_ANALYSIS_FAILED",
            reason=str(e),
            impact="MEDIUM"
        )
        return _identify_opportunities_heuristic(article, product)


def _identify_opportunities_heuristic(
    article: ArticleCandidate,
    product: ProductInfo
) -> Dict:
    """Use heuristics to identify insertion opportunities."""
    opportunities = []
    primary_type = InsertionType.MENTION_OPPORTUNITY
    score = 0.5

    title_lower = article.title.lower()
    content = (article.full_content or article.content_excerpt).lower()

    # Check for listicle format
    import re
    if re.search(r'\d+\s*(best|top|apps|tools|ways)', title_lower):
        primary_type = InsertionType.LISTICLE_ADDITION
        opportunities.append("This is a listicle - product could be added as an entry")
        score = 0.8

    # Check for comparison articles
    elif "vs" in title_lower or "comparison" in title_lower or "alternative" in title_lower:
        primary_type = InsertionType.COMPARISON_INCLUSION
        opportunities.append("This is a comparison article - product could be included")
        score = 0.7

    # Check for outdated content
    if article.publication_date:
        # Handle both timezone-aware and naive datetimes
        pub_date = article.publication_date
        if hasattr(pub_date, 'tzinfo') and pub_date.tzinfo is not None:
            pub_date = pub_date.replace(tzinfo=None)
        age_days = (datetime.now() - pub_date).days
        if age_days > 365:
            primary_type = InsertionType.UPDATE_EXISTING
            opportunities.append(f"Article is {age_days} days old - may need updating")
            score = max(score, 0.6)

    # Check for resource sections
    resource_patterns = ["resources", "tools mentioned", "further reading", "recommended"]
    for pattern in resource_patterns:
        if pattern in content:
            opportunities.append(f"Article has '{pattern}' section - could add product link")
            if primary_type == InsertionType.MENTION_OPPORTUNITY:
                primary_type = InsertionType.RESOURCE_LINK
                score = max(score, 0.6)

    # Check product category mention
    if product.category.lower() in content:
        opportunities.append(f"Article mentions '{product.category}' - natural fit")
        score = max(score, 0.6)

    if not opportunities:
        opportunities.append("General mention opportunity based on topic relevance")

    return {
        "opportunities": opportunities,
        "primary_type": primary_type,
        "score": score
    }


def _parse_opportunity_response(response: str) -> Dict:
    """Parse LLM response into structured data."""
    result = {
        "opportunities": [],
        "primary_type": InsertionType.MENTION_OPPORTUNITY,
        "score": 0.5
    }

    lines = response.strip().split("\n")

    for line in lines:
        line = line.strip()

        if line.startswith("INSERTION_TYPE:"):
            type_str = line.replace("INSERTION_TYPE:", "").strip().lower()
            try:
                result["primary_type"] = InsertionType(type_str)
            except ValueError:
                pass

        elif line.startswith("- "):
            result["opportunities"].append(line[2:])

        elif line.startswith("FIT_SCORE:"):
            try:
                score_str = line.replace("FIT_SCORE:", "").strip()
                result["score"] = float(score_str)
            except ValueError:
                pass

    return result


def _calculate_final_score(article: ArticleCandidate, product: ProductInfo) -> float:
    """Calculate final composite score for article."""
    # Weights for different factors
    weights = {
        "domain_authority": 0.25,
        "recency": 0.15,
        "relevance": 0.25,
        "opportunity": 0.25,
        "reachability": 0.10
    }

    # Domain authority (0-100 -> 0-1)
    da_score = min(article.domain_authority / 100.0, 1.0)

    # Recency
    recency_score = article.recency_score

    # Relevance
    relevance_score = article.relevance_score

    # Opportunity
    opportunity_score = article.opportunity_score

    # Reachability (based on author info)
    reachability_score = 0.5
    if article.author_name:
        reachability_score = 0.7
    if article.author_url:
        reachability_score = 0.9

    # Calculate weighted score
    composite = (
        da_score * weights["domain_authority"] +
        recency_score * weights["recency"] +
        relevance_score * weights["relevance"] +
        opportunity_score * weights["opportunity"] +
        reachability_score * weights["reachability"]
    )

    return composite


def get_article_summary(article: ArticleCandidate) -> str:
    """Generate a brief summary of the article for outreach context."""
    summary_parts = []

    summary_parts.append(f"Title: {article.title}")
    summary_parts.append(f"Domain: {article.domain} (DA: {article.domain_authority})")

    if article.publication_date:
        summary_parts.append(f"Published: {article.publication_date.strftime('%Y-%m-%d')}")

    if article.author_name:
        summary_parts.append(f"Author: {article.author_name}")

    if article.insertion_type:
        summary_parts.append(f"Opportunity: {article.insertion_type.value}")

    summary_parts.append(f"Score: {article.composite_score:.2f}")

    return "\n".join(summary_parts)
