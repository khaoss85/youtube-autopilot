"""
Article Scraper Service - Extract content from URLs.

Uses newspaper3k and trafilatura for robust article extraction.
Fallback chain: newspaper3k -> trafilatura -> basic requests
"""

import re
from typing import Dict, Optional, Tuple
from datetime import datetime
from yt_autopilot.core.logger import logger, log_fallback

# Optional imports with fallbacks
try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    logger.warning("newspaper3k not available, will use fallback scraper")

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("trafilatura not available, will use basic scraper")

import requests
from bs4 import BeautifulSoup


def scrape_article(url: str, timeout: int = 30) -> Dict:
    """
    Scrape article content from URL.

    Args:
        url: Article URL to scrape
        timeout: Request timeout in seconds

    Returns:
        Dict with keys:
        - title: Article title
        - content: Full article text
        - author: Author name (if found)
        - publish_date: Publication date (if found)
        - excerpt: First 500 chars
        - word_count: Total word count
        - success: Whether scraping succeeded
        - method: Which method was used
    """
    logger.info(f"Scraping article: {url}")

    # Try newspaper3k first
    if NEWSPAPER_AVAILABLE:
        result = _scrape_with_newspaper(url, timeout)
        if result["success"]:
            logger.info(f"  ✓ Scraped with newspaper3k: {result['word_count']} words")
            return result

    # Try trafilatura as fallback
    if TRAFILATURA_AVAILABLE:
        result = _scrape_with_trafilatura(url, timeout)
        if result["success"]:
            logger.info(f"  ✓ Scraped with trafilatura: {result['word_count']} words")
            return result

    # Basic fallback
    result = _scrape_with_beautifulsoup(url, timeout)
    if result["success"]:
        logger.info(f"  ✓ Scraped with BeautifulSoup: {result['word_count']} words")
    else:
        log_fallback(
            component="ARTICLE_SCRAPER",
            fallback_type="ALL_METHODS_FAILED",
            reason=f"Could not scrape {url}",
            impact="HIGH"
        )
        logger.warning(f"  ✗ All scraping methods failed for {url}")

    return result


def _scrape_with_newspaper(url: str, timeout: int) -> Dict:
    """Scrape using newspaper3k."""
    try:
        article = Article(url)
        article.download()
        article.parse()

        content = article.text or ""
        return {
            "title": article.title or "",
            "content": content,
            "author": ", ".join(article.authors) if article.authors else None,
            "publish_date": article.publish_date,
            "excerpt": content[:500] if content else "",
            "word_count": len(content.split()) if content else 0,
            "success": bool(content),
            "method": "newspaper3k"
        }
    except Exception as e:
        logger.debug(f"newspaper3k failed: {e}")
        return _empty_result("newspaper3k", str(e))


def _scrape_with_trafilatura(url: str, timeout: int) -> Dict:
    """Scrape using trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return _empty_result("trafilatura", "Download failed")

        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False
        )

        if not content:
            return _empty_result("trafilatura", "Extraction failed")

        # Try to get metadata
        metadata = trafilatura.extract_metadata(downloaded)

        return {
            "title": metadata.title if metadata else "",
            "content": content,
            "author": metadata.author if metadata else None,
            "publish_date": _parse_date(metadata.date) if metadata and metadata.date else None,
            "excerpt": content[:500],
            "word_count": len(content.split()),
            "success": True,
            "method": "trafilatura"
        }
    except Exception as e:
        logger.debug(f"trafilatura failed: {e}")
        return _empty_result("trafilatura", str(e))


def _scrape_with_beautifulsoup(url: str, timeout: int) -> Dict:
    """Basic scraping with BeautifulSoup."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Get title
        title = ""
        if soup.title:
            title = soup.title.string or ""
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # Get main content
        content = ""
        # Try common article containers
        for selector in ["article", "main", ".post-content", ".article-content", ".entry-content"]:
            container = soup.select_one(selector)
            if container:
                content = container.get_text(separator="\n", strip=True)
                break

        # Fallback to body
        if not content and soup.body:
            content = soup.body.get_text(separator="\n", strip=True)

        # Clean up whitespace
        content = re.sub(r'\n\s*\n', '\n\n', content)

        # Try to find author
        author = None
        author_meta = soup.find("meta", {"name": "author"})
        if author_meta:
            author = author_meta.get("content")

        return {
            "title": title,
            "content": content,
            "author": author,
            "publish_date": None,
            "excerpt": content[:500] if content else "",
            "word_count": len(content.split()) if content else 0,
            "success": bool(content),
            "method": "beautifulsoup"
        }
    except Exception as e:
        logger.debug(f"BeautifulSoup failed: {e}")
        return _empty_result("beautifulsoup", str(e))


def _empty_result(method: str, error: str) -> Dict:
    """Return empty result structure."""
    return {
        "title": "",
        "content": "",
        "author": None,
        "publish_date": None,
        "excerpt": "",
        "word_count": 0,
        "success": False,
        "method": method,
        "error": error
    }


def _parse_date(date_str: str) -> Optional[datetime]:
    """Try to parse a date string."""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%B %d, %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def extract_author_from_page(url: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Try to extract author name and profile URL from article page.

    Returns:
        Tuple of (author_name, author_profile_url) or None
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")

        # Try various author patterns
        author_name = None
        author_url = None

        # Method 1: Schema.org markup
        author_elem = soup.find(itemprop="author")
        if author_elem:
            author_name = author_elem.get_text(strip=True)
            author_link = author_elem.find("a")
            if author_link:
                author_url = author_link.get("href")

        # Method 2: Common class names
        if not author_name:
            for cls in ["author", "byline", "writer", "post-author"]:
                elem = soup.find(class_=re.compile(cls, re.I))
                if elem:
                    author_name = elem.get_text(strip=True)
                    author_link = elem.find("a")
                    if author_link:
                        author_url = author_link.get("href")
                    break

        # Method 3: Meta tags
        if not author_name:
            meta = soup.find("meta", {"name": "author"})
            if meta:
                author_name = meta.get("content")

        # Clean up author name (remove "By", dates, etc.)
        if author_name:
            author_name = re.sub(r'^(by|written by|author:)\s*', '', author_name, flags=re.I)
            author_name = author_name.strip()

        if author_name:
            return (author_name, author_url)

        return None

    except Exception as e:
        logger.debug(f"Author extraction failed: {e}")
        return None
