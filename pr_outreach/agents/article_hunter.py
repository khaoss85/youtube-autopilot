"""
Article Hunter Agent - Discover articles for PR outreach.

Similar to TrendHunter in youtube-autopilot.
Searches multiple sources to find relevant articles.

Search priority:
1. OpenAI web search (if available) - FREE with OpenAI API
2. Google Custom Search API
3. SerpAPI (fallback)
"""

import os
import json
from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote_plus

from pr_outreach.core.schemas import ArticleCandidate, ProductInfo, CampaignConfig
from pr_outreach.services.domain_analyzer import analyze_domain
from yt_autopilot.core.logger import logger, log_fallback

import requests


def hunt_articles(
    search_queries: List[str],
    product: ProductInfo,
    campaign_config: CampaignConfig,
    max_results: int = 50,
    contacted_articles: List[str] = None,
    llm_generate_fn: Optional[Callable] = None,
    use_openai_search: bool = True
) -> List[ArticleCandidate]:
    """
    Hunt for articles relevant to the product.

    Args:
        search_queries: List of search queries to use
        product: Product information
        campaign_config: Campaign configuration
        max_results: Maximum articles to return
        contacted_articles: URLs already contacted (to skip)
        llm_generate_fn: LLM function for relevance scoring
        use_openai_search: Use OpenAI's built-in web search (recommended)

    Returns:
        List of ArticleCandidate objects, sorted by composite score
    """
    logger.info(f"Hunting articles for: {product.name}")
    logger.info(f"  Queries: {search_queries}")

    contacted_articles = contacted_articles or []
    all_articles = []

    # Search each query
    for query in search_queries:
        logger.info(f"  Searching: {query}")

        # Try OpenAI web search first (free with API)
        if use_openai_search:
            openai_results = _search_openai_web(query, product, max_results=15)
            if openai_results:
                all_articles.extend(openai_results)
                continue  # Skip other sources if OpenAI worked

        # Fallback: Try Google Custom Search
        google_results = _search_google(query, max_results=20)
        if google_results:
            all_articles.extend(google_results)
            continue

        # Fallback: Try news-specific search
        news_results = _search_news(query, max_results=10)
        if news_results:
            all_articles.extend(news_results)
            continue

        # Final fallback: DuckDuckGo or SerpAPI
        fallback_results = _search_fallback(query, max_results=15)
        all_articles.extend(fallback_results)

    # Deduplicate by URL
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article.url not in seen_urls and article.url not in contacted_articles:
            seen_urls.add(article.url)
            unique_articles.append(article)

    logger.info(f"  Found {len(unique_articles)} unique articles")

    # Enrich with domain analysis
    for article in unique_articles:
        domain_info = analyze_domain(article.url)
        article.domain_authority = domain_info.get("domain_authority", 0)

    # Score articles
    scored_articles = _score_articles(
        unique_articles,
        product,
        campaign_config,
        llm_generate_fn
    )

    # Sort by composite score
    scored_articles.sort(key=lambda x: x.composite_score, reverse=True)

    # Return top results
    top_articles = scored_articles[:max_results]
    logger.info(f"  Returning top {len(top_articles)} articles")

    return top_articles


def _search_openai_web(
    query: str,
    product: ProductInfo,
    max_results: int = 15
) -> List[ArticleCandidate]:
    """
    Search using OpenAI's built-in web search tool.

    This uses the Responses API with web_search_preview tool.
    FREE with OpenAI API - no additional subscription needed.
    """
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_OPENAI_API_KEY")
    if not api_key:
        logger.debug("OpenAI API key not configured")
        return []

    articles = []

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        # Use Responses API with web search tool
        response = client.responses.create(
            model="gpt-5.1",  # Latest model with native web search
            tools=[{"type": "web_search_preview"}],
            input=f"""Search the web for: {query}

Find articles that could mention {product.name} ({product.category}).

For each relevant article found, extract:
- URL
- Title
- Author name (if visible)
- Brief description/excerpt

Focus on:
- Listicle articles ("Best X", "Top 10", etc.)
- Review/comparison articles
- Guide articles
- Recent articles (2024-2025)

Return results as JSON array:
[
  {{"url": "...", "title": "...", "author": "...", "excerpt": "..."}},
  ...
]

Return ONLY the JSON array, no other text.""",
            reasoning={"effort": "low"},
            text={"verbosity": "low"}
        )

        # Parse the response - extract text and URL annotations from output
        result_text = ""
        url_annotations = []

        if hasattr(response, 'output') and response.output:
            for item in response.output:
                if hasattr(item, 'content') and item.content:
                    for content in item.content:
                        if hasattr(content, 'text'):
                            result_text += content.text + " "
                        # Extract URL citations from annotations
                        if hasattr(content, 'annotations') and content.annotations:
                            for ann in content.annotations:
                                if hasattr(ann, 'url') and ann.url:
                                    url_annotations.append({
                                        'url': ann.url.split('?')[0],  # Remove tracking params
                                        'title': getattr(ann, 'title', '')
                                    })

        # First try to parse JSON from response
        try:
            import re
            # Match JSON array - greedy to get full array
            json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', result_text)
            if json_match:
                json_str = json_match.group()
                results = json.loads(json_str)
                for item in results[:max_results]:
                    url = item.get("url", "")
                    if not url:
                        continue
                    article = ArticleCandidate(
                        url=url,
                        title=item.get("title", ""),
                        domain=urlparse(url).netloc,
                        author_name=item.get("author"),
                        content_excerpt=item.get("excerpt", ""),
                        source="openai_web"
                    )
                    articles.append(article)
                logger.debug(f"Parsed {len(articles)} articles from JSON")
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"JSON parse failed: {e}")

        # If no JSON results, use URL annotations directly
        if not articles and url_annotations:
            for ann in url_annotations[:max_results]:
                url = ann['url']
                # Skip non-article URLs
                if any(skip in url for skip in ['google.com', 'youtube.com', 'facebook.com', 'twitter.com']):
                    continue
                article = ArticleCandidate(
                    url=url,
                    title=ann.get('title', ''),
                    domain=urlparse(url).netloc,
                    source="openai_web"
                )
                articles.append(article)

        logger.info(f"    OpenAI web search found {len(articles)} articles")

    except ImportError:
        logger.debug("OpenAI package not installed or outdated")
    except Exception as e:
        logger.debug(f"OpenAI web search failed: {e}")
        # Don't log as error - just fall back to other methods

    return articles


def _search_google(query: str, max_results: int = 20) -> List[ArticleCandidate]:
    """
    Search using Google Custom Search API.

    Requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX environment variables.
    """
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX")

    if not api_key or not cx:
        logger.debug("Google Search API not configured, using fallback")
        return _search_fallback(query, max_results)

    articles = []

    try:
        # Google Custom Search API
        url = "https://www.googleapis.com/customsearch/v1"

        # Search in batches of 10 (API limit)
        for start in range(1, max_results + 1, 10):
            params = {
                "key": api_key,
                "cx": cx,
                "q": query,
                "start": start,
                "num": min(10, max_results - start + 1)
            }

            response = requests.get(url, params=params, timeout=15)
            if response.status_code != 200:
                break

            data = response.json()
            items = data.get("items", [])

            for item in items:
                article = ArticleCandidate(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    domain=urlparse(item.get("link", "")).netloc,
                    content_excerpt=item.get("snippet", ""),
                    source="google"
                )
                articles.append(article)

    except Exception as e:
        logger.warning(f"Google search failed: {e}")
        log_fallback(
            component="ARTICLE_HUNTER",
            fallback_type="GOOGLE_SEARCH_FAILED",
            reason=str(e),
            impact="MEDIUM"
        )

    return articles


def _search_news(query: str, max_results: int = 10) -> List[ArticleCandidate]:
    """
    Search news sources using NewsAPI or similar.

    Requires NEWS_API_KEY environment variable.
    """
    api_key = os.getenv("NEWS_API_KEY")

    if not api_key:
        logger.debug("News API not configured")
        return []

    articles = []

    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "apiKey": api_key,
            "q": query,
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": max_results
        }

        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("articles", []):
                article = ArticleCandidate(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    domain=urlparse(item.get("url", "")).netloc,
                    author_name=item.get("author"),
                    content_excerpt=item.get("description", ""),
                    source="newsapi"
                )
                if item.get("publishedAt"):
                    try:
                        article.publication_date = datetime.fromisoformat(
                            item["publishedAt"].replace("Z", "+00:00")
                        )
                    except:
                        pass
                articles.append(article)

    except Exception as e:
        logger.debug(f"News API search failed: {e}")

    return articles


def _search_fallback(query: str, max_results: int) -> List[ArticleCandidate]:
    """
    Fallback search using DuckDuckGo or SerpAPI.
    """
    # Try DuckDuckGo (free, no API key needed)
    try:
        from ddgs import DDGS
        articles = []

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

            for item in results:
                article = ArticleCandidate(
                    url=item.get("href", ""),
                    title=item.get("title", ""),
                    domain=urlparse(item.get("href", "")).netloc,
                    content_excerpt=item.get("body", ""),
                    source="duckduckgo"
                )
                articles.append(article)

        if articles:
            logger.info(f"    DuckDuckGo found {len(articles)} articles")
            return articles

    except ImportError:
        logger.debug("duckduckgo-search not installed")
    except Exception as e:
        logger.debug(f"DuckDuckGo search failed: {e}")

    # Try SerpAPI as secondary fallback
    serp_key = os.getenv("SERP_API_KEY")
    if serp_key:
        return _search_serpapi(query, serp_key, max_results)

    # No API available
    logger.warning("No search API available")
    return []


def _search_serpapi(query: str, api_key: str, max_results: int) -> List[ArticleCandidate]:
    """Search using SerpAPI (Google search scraping service)."""
    articles = []

    try:
        url = "https://serpapi.com/search"
        params = {
            "api_key": api_key,
            "q": query,
            "num": max_results,
            "engine": "google"
        }

        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("organic_results", []):
                article = ArticleCandidate(
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    domain=urlparse(item.get("link", "")).netloc,
                    content_excerpt=item.get("snippet", ""),
                    source="serpapi"
                )
                articles.append(article)

    except Exception as e:
        logger.debug(f"SerpAPI search failed: {e}")

    return articles


def _score_articles(
    articles: List[ArticleCandidate],
    product: ProductInfo,
    campaign_config: CampaignConfig,
    llm_generate_fn: Optional[Callable]
) -> List[ArticleCandidate]:
    """
    Score articles based on multiple factors.

    Scoring factors:
    - Domain authority (higher = better)
    - Recency (newer = better)
    - Relevance to product (LLM-scored if available)
    - Insertion opportunity (listicle format = better)
    """
    for article in articles:
        # Domain authority score (0-1)
        da_score = min(article.domain_authority / 100.0, 1.0)

        # Recency score (0-1)
        recency_score = _calculate_recency_score(article.publication_date)
        article.recency_score = recency_score

        # Relevance score (0-1)
        relevance_score = _calculate_relevance_score(
            article, product, llm_generate_fn
        )
        article.relevance_score = relevance_score

        # Opportunity score (0-1)
        opportunity_score = _calculate_opportunity_score(article, product)
        article.opportunity_score = opportunity_score

        # Composite score (weighted average)
        article.composite_score = (
            da_score * 0.25 +
            recency_score * 0.15 +
            relevance_score * 0.35 +
            opportunity_score * 0.25
        )

    return articles


def _calculate_recency_score(publication_date: Optional[datetime]) -> float:
    """Calculate score based on article recency."""
    if not publication_date:
        return 0.5  # Unknown date

    age_days = (datetime.now() - publication_date).days

    if age_days < 7:
        return 1.0
    elif age_days < 30:
        return 0.9
    elif age_days < 90:
        return 0.7
    elif age_days < 180:
        return 0.5
    elif age_days < 365:
        return 0.3
    else:
        return 0.1


def _calculate_relevance_score(
    article: ArticleCandidate,
    product: ProductInfo,
    llm_generate_fn: Optional[Callable]
) -> float:
    """Calculate relevance score using LLM or keywords."""
    if llm_generate_fn:
        return _llm_relevance_score(article, product, llm_generate_fn)
    else:
        return _keyword_relevance_score(article, product)


def _keyword_relevance_score(article: ArticleCandidate, product: ProductInfo) -> float:
    """Calculate relevance using keyword matching."""
    text = f"{article.title} {article.content_excerpt}".lower()

    # Check product keywords
    keywords = [
        product.category.lower(),
        product.name.lower(),
    ] + [f.lower() for f in product.key_features[:3]]

    matches = sum(1 for kw in keywords if kw in text)
    return min(matches / len(keywords), 1.0)


def _llm_relevance_score(
    article: ArticleCandidate,
    product: ProductInfo,
    llm_generate_fn: Callable
) -> float:
    """Calculate relevance using LLM analysis."""
    prompt = f"""Rate the relevance of this article for PR outreach promoting a product.

PRODUCT:
- Name: {product.name}
- Category: {product.category}
- Description: {product.tagline}
- Key features: {', '.join(product.key_features[:3])}

ARTICLE:
- Title: {article.title}
- Excerpt: {article.content_excerpt[:500]}
- Domain: {article.domain}

Rate relevance from 0.0 to 1.0 where:
- 0.0-0.3: Not relevant (different topic entirely)
- 0.4-0.6: Somewhat relevant (related category)
- 0.7-0.8: Relevant (good fit for mention)
- 0.9-1.0: Highly relevant (perfect listicle opportunity)

Respond with just a number between 0.0 and 1.0"""

    try:
        response = llm_generate_fn(
            role="article_analyst",
            task=prompt,
            context="",
            style_hints={"response_format": "number"}
        )
        score = float(response.strip())
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.debug(f"LLM relevance scoring failed: {e}")
        return _keyword_relevance_score(article, product)


def _calculate_opportunity_score(article: ArticleCandidate, product: ProductInfo) -> float:
    """Calculate insertion opportunity score."""
    score = 0.5  # Base score

    title_lower = article.title.lower()
    content_lower = article.content_excerpt.lower()

    # Listicle indicators (best opportunity)
    listicle_patterns = [
        "best", "top", "ultimate", "guide",
        " apps", " tools", " software", " platforms",
        "review", "comparison", "vs", "alternatives"
    ]

    for pattern in listicle_patterns:
        if pattern in title_lower:
            score += 0.1

    # Number in title indicates listicle
    import re
    if re.search(r'\d+\s*(best|top|apps|tools)', title_lower):
        score += 0.2

    # Recent update indicators
    update_patterns = ["2024", "2025", "update", "latest"]
    for pattern in update_patterns:
        if pattern in title_lower or pattern in content_lower:
            score += 0.1

    return min(score, 1.0)


def generate_search_queries(product: ProductInfo, niche: str = "") -> List[str]:
    """
    Generate search queries for a product.

    Returns list of queries optimized for finding listicle opportunities.
    """
    queries = []

    # Basic product queries
    queries.append(f"best {product.category} 2024")
    queries.append(f"top {product.category} apps")
    queries.append(f"{product.category} guide")

    # Feature-based queries
    for feature in product.key_features[:2]:
        queries.append(f"best {feature} {product.category}")

    # Audience-based queries
    if product.target_audience:
        queries.append(f"best {product.category} for {product.target_audience}")

    # Niche-specific
    if niche:
        queries.append(f"{niche} {product.category} recommendations")

    return queries
