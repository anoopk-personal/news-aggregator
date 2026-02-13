"""Fetch and parse RSS feeds."""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import bleach
import feedparser
import httpx
from dateutil import parser as date_parser

from .config import (
    ALLOWED_URL_SCHEMES,
    ARTICLES_PER_FEED,
    FEEDS,
    MAX_ARTICLE_AGE_HOURS,
    REQUEST_TIMEOUT,
    SOURCE_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
    TITLE_MAX_LENGTH,
)
from .utils import EMOJI_PATTERN

logger = logging.getLogger(__name__)


@dataclass
class Article:
    """Represents a news article."""

    title: str
    link: str
    summary: str
    source: str
    published: datetime | None = None


def _is_valid_url(url: str) -> bool:
    """Validate that a URL has an allowed scheme and valid structure."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ALLOWED_URL_SCHEMES and bool(parsed.netloc)
    except (ValueError, AttributeError):
        return False


def fetch_feed(url: str) -> list[Article]:
    """Fetch and parse a single RSS feed (sync version for testing/standalone use)."""
    if not _is_valid_url(url):
        logger.warning("Invalid URL skipped: %s", url)
        return []

    try:
        response = httpx.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return []

    return _parse_feed(response.text, url)


async def _fetch_feed_async(url: str, client: httpx.AsyncClient) -> list[Article]:
    """Fetch and parse a single RSS feed asynchronously."""
    if not _is_valid_url(url):
        logger.warning("Invalid URL skipped: %s", url)
        return []

    try:
        response = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return []

    return _parse_feed(response.text, url)


def fetch_all_feeds(topic: str) -> list[Article]:
    """Fetch all feeds for a topic concurrently."""
    urls = FEEDS.get(topic.lower(), [])
    if not urls:
        logger.error("Unknown topic: %s", topic)
        return []

    return asyncio.run(_fetch_all_feeds_async(urls, topic))


async def _fetch_all_feeds_async(urls: list[str], topic: str) -> list[Article]:
    """Fetch all feeds concurrently using asyncio."""
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_feed_async(url, client) for url in urls]
        results = await asyncio.gather(*tasks)

    all_articles = []
    successful_feeds = 0
    failed_feeds = 0

    for url, articles in zip(urls, results, strict=True):
        if articles:
            all_articles.extend(articles)
            successful_feeds += 1
            logger.info("Fetched %d articles from %s", len(articles), url)
        else:
            failed_feeds += 1
            logger.warning("No articles from %s", url)

    logger.info(
        "Topic '%s': %d articles from %d feeds (%d failed)",
        topic,
        len(all_articles),
        successful_feeds,
        failed_feeds,
    )
    return all_articles


def _parse_feed(text: str, url: str) -> list[Article]:
    """Parse RSS feed text into articles."""
    feed = feedparser.parse(text)
    source = _sanitize(feed.feed.get("title", ""))[:SOURCE_MAX_LENGTH] or urlparse(url).netloc

    articles = []
    cutoff = datetime.now(UTC) - timedelta(hours=MAX_ARTICLE_AGE_HOURS)

    for entry in feed.entries[:ARTICLES_PER_FEED]:
        title = _sanitize(entry.get("title", ""))
        link = entry.get("link", "")
        summary = _sanitize(entry.get("summary", entry.get("description", "")))
        published = _parse_date(entry)

        if not title or not link:
            continue

        if not _is_valid_url(link):
            continue

        if published and published < cutoff:
            continue

        articles.append(
            Article(
                title=title[:TITLE_MAX_LENGTH],
                link=link,
                summary=summary[:SUMMARY_MAX_LENGTH],
                source=source,
                published=published,
            )
        )
    return articles


def _parse_date(entry: Any) -> datetime | None:
    """Parse publication date from a feed entry using dateutil."""
    date_str = entry.get("published", entry.get("updated"))
    if not date_str:
        return None

    try:
        dt = date_parser.parse(date_str)
        # If the datetime object is naive, assume it's UTC
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (date_parser.ParserError, TypeError):
        logger.warning("Could not parse date: %s", date_str)
        return None


def _sanitize(text: str) -> str:
    """Sanitize text using bleach and remove emojis."""
    if not text:
        return ""
    # Remove HTML tags using bleach, keeping the text content
    sanitized_text = bleach.clean(text, tags=[], strip=True)
    # Remove emojis
    sanitized_text = EMOJI_PATTERN.sub("", sanitized_text)
    # Normalize whitespace
    sanitized_text = re.sub(r"\s+", " ", sanitized_text)
    return sanitized_text.strip()
