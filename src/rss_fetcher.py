"""Fetch and parse RSS feeds."""

import asyncio
import ipaddress
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final
from urllib.parse import urlparse

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
from .utils import EMOJI_PATTERN

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


def _is_non_routable_host(hostname: str) -> bool:
    """Check if a hostname is a non-globally-routable IP or localhost."""
    if not hostname:
        return True
    hostname = hostname.rstrip(".")
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        return True
    # Strip IPv6 zone ID (e.g. fe80::1%eth0)
    if "%" in hostname:
        hostname = hostname.split("%")[0]
    try:
        return not ipaddress.ip_address(hostname).is_global
    except ValueError:
        pass
    # Bare integers, hex (0x7f000001), and C-style octal (017700000001) are resolved
    # as IPs by glibc on Linux. Python's int(x, 0) handles hex/0o-octal/decimal but
    # not C-style octal (leading zero without 'o'), so we detect that separately.
    try:
        if hostname.startswith(("0x", "0X")):
            numeric = int(hostname, 16)
        elif len(hostname) > 1 and hostname[0] == "0" and hostname.isdigit():
            numeric = int(hostname, 8)
        else:
            numeric = int(hostname)
        return not ipaddress.ip_address(numeric).is_global
    except (ValueError, OverflowError):
        return False  # regular domain name, allow it


def _is_valid_url(url: str) -> bool:
    """Validate that a URL has an allowed scheme and valid structure."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_URL_SCHEMES or not parsed.netloc:
            return False
        if _is_non_routable_host(parsed.hostname or ""):
            return False
        return True
    except (ValueError, AttributeError):
        return False


def _validate_redirect(current_url: str, response: httpx.Response) -> str | None:
    """Validate a redirect response. Returns the target URL or None if blocked."""
    location: str = response.headers.get("location", "")
    if not _is_valid_url(location):
        logger.warning(
            "Redirect to invalid URL blocked: %s -> %s",
            current_url,
            location,
        )
        return None
    return location


def fetch_feed(url: str) -> list[Article]:
    """Fetch and parse a single RSS feed (sync version for testing/standalone use)."""
    if not _is_valid_url(url):
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
    if not _is_valid_url(url):
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
    """Sanitize text and remove emojis."""
    if not text:
        return ""
    # Remove HTML tags, keeping the text content
    sanitized_text = nh3.clean(text, tags=set())
    # Remove emojis
    sanitized_text = EMOJI_PATTERN.sub("", sanitized_text)
    # Normalize whitespace
    sanitized_text = re.sub(r"\s+", " ", sanitized_text)
    return sanitized_text.strip()
