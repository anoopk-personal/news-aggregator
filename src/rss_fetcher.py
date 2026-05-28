"""Fetch and parse RSS feeds."""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
import nh3
from dateutil import parser as date_parser

from .config import (
    ALLOWED_URL_SCHEMES,
    ARTICLES_PER_FEED,
    FEEDS,
    FETCH_MAX_RETRIES,
    FETCH_RETRY_BACKOFF,
    MAX_ARTICLE_AGE_HOURS,
    REQUEST_TIMEOUT,
    SOURCE_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
    TITLE_MAX_LENGTH,
)
from .utils import EMOJI_PATTERN, is_valid_url

logger = logging.getLogger(__name__)

_MAX_REDIRECTS: Final[int] = 10


@dataclass
class Article:
    """Represents a news article."""

    title: str
    link: str
    summary: str
    source: str
    published: datetime | None = None


@dataclass
class FetchResult:
    """Result of fetching all feeds for a topic."""

    articles: list[Article]
    feeds_total: int
    feeds_succeeded: int
    feeds_failed: int


def _validate_redirect(current_url: str, response: httpx.Response) -> str | None:
    """Validate a redirect response. Returns the target URL or None if blocked."""
    location: str = response.headers.get("location", "").strip()
    target_url = urljoin(current_url, location)
    if not is_valid_url(target_url, ALLOWED_URL_SCHEMES, resolve_dns=True):
        logger.warning(
            "Redirect to invalid URL blocked: %s -> %s",
            current_url,
            location,
        )
        return None
    return target_url


def fetch_feed(url: str) -> list[Article]:
    """Fetch and parse a single RSS feed (sync version for testing/standalone use)."""
    if not is_valid_url(url, ALLOWED_URL_SCHEMES, resolve_dns=True):
        logger.warning("Invalid URL skipped: %s", url)
        return []

    try:
        current_url = url
        for _ in range(_MAX_REDIRECTS):
            response = httpx.get(current_url, timeout=REQUEST_TIMEOUT, follow_redirects=False)
            if response.is_redirect:
                target = _validate_redirect(current_url, response)
                if target is None:
                    return []
                current_url = target
                continue
            response.raise_for_status()
            return _parse_feed(response.text, url)
        logger.warning("Too many redirects for %s", url)
        return []
    except httpx.HTTPError as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return []


async def _fetch_feed_async(url: str, client: httpx.AsyncClient) -> list[Article]:
    """Fetch and parse a single RSS feed asynchronously with retry."""
    if not is_valid_url(url, ALLOWED_URL_SCHEMES, resolve_dns=True):
        logger.warning("Invalid URL skipped: %s", url)
        return []

    last_error: httpx.HTTPError | None = None
    for attempt in range(FETCH_MAX_RETRIES + 1):
        try:
            current_url = url
            for _ in range(_MAX_REDIRECTS):
                response = await client.get(
                    current_url,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=False,
                )
                if response.is_redirect:
                    target = _validate_redirect(current_url, response)
                    if target is None:
                        return []
                    current_url = target
                    continue
                response.raise_for_status()
                return _parse_feed(response.text, url)
            logger.warning("Too many redirects for %s", url)
            return []
        except httpx.HTTPStatusError as e:
            last_error = e
            if 400 <= e.response.status_code < 500:
                logger.warning("Non-retryable %d for %s: %s", e.response.status_code, url, e)
                break
        except httpx.HTTPError as e:
            last_error = e
        if last_error and attempt < FETCH_MAX_RETRIES:
            wait = FETCH_RETRY_BACKOFF * (2**attempt)
            logger.info(
                "Retry %d/%d for %s in %.1fs",
                attempt + 1,
                FETCH_MAX_RETRIES,
                url,
                wait,
            )
            await asyncio.sleep(wait)

    logger.warning(
        "Failed to fetch %s after %d attempts: %s",
        url,
        FETCH_MAX_RETRIES + 1,
        last_error,
    )
    return []


def fetch_all_feeds(topic: str) -> FetchResult:
    """Fetch all feeds for a topic concurrently (sync wrapper).

    Convenience entry point for synchronous callers (CLI, scripts).
    Library users in an existing event loop should call
    :func:`fetch_all_feeds_async` directly instead.

    Raises ``RuntimeError`` if called from within a running event loop;
    use :func:`fetch_all_feeds_async` in that case.
    """
    return asyncio.run(fetch_all_feeds_async(topic))


async def fetch_all_feeds_async(topic: str) -> FetchResult:
    """Fetch all feeds for a topic concurrently (async).

    Looks up feed URLs from the loaded ``feeds.toml`` config (case-insensitive
    topic match). Returns an empty :class:`FetchResult` with ``feeds_total=0``
    for unknown topics. Individual feed failures are logged and reflected in
    ``feeds_failed`` without aborting the batch.
    """
    urls = FEEDS.get(topic.lower(), [])
    if not urls:
        logger.error("Unknown topic: %s", topic)
        return FetchResult(articles=[], feeds_total=0, feeds_succeeded=0, feeds_failed=0)

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
    return FetchResult(
        articles=all_articles,
        feeds_total=len(urls),
        feeds_succeeded=successful_feeds,
        feeds_failed=failed_feeds,
    )


def _parse_feed(text: str, url: str) -> list[Article]:
    """Parse RSS feed text into articles."""
    # feedparser uses html.parser/sgmllib backends that don't process external entities (XXE-safe)
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

        if not is_valid_url(link, ALLOWED_URL_SCHEMES):
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
    """Sanitize text and remove emojis."""
    if not text:
        return ""
    # Remove HTML tags, keeping the text content
    sanitized_text = nh3.clean(text, tags=set())
    # Remove emojis
    sanitized_text = EMOJI_PATTERN.sub("", sanitized_text)
    # Strip markdown link metacharacters so the text is safe to embed inside
    # `[text](url)` sinks without enabling link-text breakout attacks from
    # hostile feed titles.
    sanitized_text = sanitized_text.translate(str.maketrans("", "", "[]"))
    # Normalize whitespace
    sanitized_text = re.sub(r"\s+", " ", sanitized_text)
    return sanitized_text.strip()
