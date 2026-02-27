"""Tests for RSS fetcher module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.rss_fetcher import (
    Article,
    _fetch_feed_async,
    _is_valid_url,
    _parse_date,
    _parse_feed,
    _sanitize,
    fetch_all_feeds,
    fetch_feed,
)


def test_sanitize_removes_html_tags():
    text = "<p>Hello <strong>World</strong></p>"
    assert _sanitize(text) == "Hello World"


def test_sanitize_removes_emojis():
    text = "Hello World! 🎉🚀"
    assert _sanitize(text) == "Hello World!"


def test_sanitize_handles_empty_string():
    assert _sanitize("") == ""


def test_sanitize_removes_script_tags():
    text = "Hello <script>alert('xss')</script> World"
    assert "<script>" not in _sanitize(text)


def test_parse_date_success():
    """Test that valid date strings are parsed correctly."""
    entry = {"published": "Tue, 10 Feb 2026 14:00:00 GMT"}
    expected_date = datetime(2026, 2, 10, 14, 0, 0, tzinfo=UTC)
    assert _parse_date(entry) == expected_date


def test_parse_date_no_date():
    """Test that None is returned when no date is present."""
    assert _parse_date({}) is None


def test_parse_date_invalid_date():
    """Test that None is returned for an invalid date string."""
    assert _parse_date({"published": "not a date"}) is None


def test_article_dataclass():
    article = Article(
        title="Test Title",
        link="https://example.com",
        summary="Test summary",
        source="Test Source",
    )
    assert article.title == "Test Title"
    assert article.link == "https://example.com"
    assert article.summary == "Test summary"
    assert article.source == "Test Source"
    assert article.published is None


def test_article_with_published_date():
    pub_date = datetime(2026, 2, 11, 10, 0, 0, tzinfo=UTC)
    article = Article(
        title="Test",
        link="https://example.com",
        summary="Summary",
        source="Source",
        published=pub_date,
    )
    assert article.published == pub_date


def test_is_valid_url_accepts_https():
    assert _is_valid_url("https://example.com/feed") is True


def test_is_valid_url_accepts_http():
    assert _is_valid_url("http://example.com/feed") is True


def test_is_valid_url_rejects_javascript():
    assert _is_valid_url("javascript:alert('xss')") is False


def test_is_valid_url_rejects_file():
    assert _is_valid_url("file:///etc/passwd") is False


def test_is_valid_url_rejects_empty():
    assert _is_valid_url("") is False


def test_is_valid_url_rejects_relative():
    assert _is_valid_url("/path/to/resource") is False


def test_is_valid_url_rejects_localhost():
    assert _is_valid_url("http://localhost/feed") is False


def test_is_valid_url_rejects_private_ip():
    assert _is_valid_url("http://192.168.1.1/feed") is False


def test_is_valid_url_rejects_loopback():
    assert _is_valid_url("http://127.0.0.1/feed") is False


def test_is_valid_url_rejects_localhost_trailing_dot():
    assert _is_valid_url("http://localhost./feed") is False


def test_is_valid_url_rejects_ipv6_loopback():
    assert _is_valid_url("http://[::1]/feed") is False


def test_is_valid_url_rejects_ipv6_private():
    assert _is_valid_url("http://[fe80::1]/feed") is False


def test_is_valid_url_rejects_ipv6_with_zone_id():
    assert _is_valid_url("http://[fe80::1%25eth0]/feed") is False


def test_is_valid_url_rejects_zero_ip():
    assert _is_valid_url("http://0/feed") is False


def test_is_valid_url_rejects_zero_quad():
    assert _is_valid_url("http://0.0.0.0/feed") is False


@patch("src.rss_fetcher.httpx.get")
def test_fetch_feed_success(mock_get):
    """Test successful feed fetching and parsing."""
    # Use a date within the 72-hour window
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = f"""
    <rss version="2.0">
    <channel>
        <title>Test Feed</title>
        <item>
            <title>Test Article</title>
            <link>https://example.com/article</link>
            <description>Test Description</description>
            <pubDate>{date_str}</pubDate>
        </item>
    </channel>
    </rss>
    """
    mock_get.return_value = mock_response

    articles = fetch_feed("https://example.com/feed")
    assert len(articles) == 1
    assert articles[0].title == "Test Article"
    assert articles[0].link == "https://example.com/article"
    assert articles[0].summary == "Test Description"
    assert articles[0].source == "Test Feed"
    assert articles[0].published is not None


@patch("src.rss_fetcher.httpx.get")
def test_fetch_feed_http_error(mock_get):
    """Test that an empty list is returned on HTTP error."""
    mock_get.side_effect = httpx.HTTPError("Test error")
    articles = fetch_feed("https://example.com/feed")
    assert articles == []


# --- Retry tests for async fetching ---

FEED_XML = """
<rss version="2.0">
<channel>
    <title>Test Feed</title>
    <item>
        <title>Retry Article</title>
        <link>https://example.com/retry</link>
        <description>Retry desc</description>
        <pubDate>{date_str}</pubDate>
    </item>
</channel>
</rss>
"""


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_retries_on_transient_error(mock_sleep):
    """Test that _fetch_feed_async retries on transient HTTP error and succeeds."""
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    success_response = MagicMock()
    success_response.raise_for_status = MagicMock()
    success_response.text = FEED_XML.format(date_str=date_str)

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=[httpx.HTTPError("timeout"), success_response])

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert len(articles) == 1
    assert articles[0].title == "Retry Article"
    assert client.get.call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_gives_up_after_max_retries(mock_sleep):
    """Test that _fetch_feed_async returns [] after exhausting retries."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.HTTPError("persistent error"))

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert articles == []
    # 1 initial + 2 retries = 3 calls
    assert client.get.call_count == 3
    # sleep called for first 2 attempts (not the last)
    assert mock_sleep.call_count == 2


# --- Helper for _parse_feed tests ---


def _build_rss_xml(entries: list[dict[str, str]], feed_title: str = "Test Feed") -> str:
    """Build a minimal RSS 2.0 XML string for testing."""
    items = []
    for entry in entries:
        parts = []
        if "title" in entry:
            parts.append(f"<title>{entry['title']}</title>")
        if "link" in entry:
            parts.append(f"<link>{entry['link']}</link>")
        if "description" in entry:
            parts.append(f"<description>{entry['description']}</description>")
        if "pubDate" in entry:
            parts.append(f"<pubDate>{entry['pubDate']}</pubDate>")
        items.append(f"<item>{''.join(parts)}</item>")
    return (
        f'<rss version="2.0"><channel><title>{feed_title}</title>{"".join(items)}</channel></rss>'
    )


# --- _parse_feed tests ---


def test_parse_feed_filters_old_articles():
    """Verify articles older than MAX_ARTICLE_AGE_HOURS are excluded."""
    recent = datetime.now(UTC) - timedelta(hours=24)
    old = datetime.now(UTC) - timedelta(hours=96)
    xml = _build_rss_xml(
        [
            {
                "title": "Recent",
                "link": "https://example.com/recent",
                "description": "New stuff",
                "pubDate": recent.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            },
            {
                "title": "Old",
                "link": "https://example.com/old",
                "description": "Stale stuff",
                "pubDate": old.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            },
        ]
    )
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == 1
    assert articles[0].title == "Recent"


def test_parse_feed_truncates_long_fields():
    """Verify title and summary are truncated to configured max lengths."""
    from src.config import SUMMARY_MAX_LENGTH, TITLE_MAX_LENGTH

    recent = datetime.now(UTC) - timedelta(hours=1)
    long_title = "A" * 600
    long_summary = "B" * 1200
    xml = _build_rss_xml(
        [
            {
                "title": long_title,
                "link": "https://example.com/long",
                "description": long_summary,
                "pubDate": recent.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            },
        ]
    )
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == 1
    assert len(articles[0].title) == TITLE_MAX_LENGTH
    assert len(articles[0].summary) == SUMMARY_MAX_LENGTH


def test_parse_feed_caps_articles_per_feed():
    """Verify only ARTICLES_PER_FEED entries are returned from a large feed."""
    from src.config import ARTICLES_PER_FEED

    recent = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent.strftime("%a, %d %b %Y %H:%M:%S GMT")
    entries = [
        {
            "title": f"Article {i}",
            "link": f"https://example.com/article-{i}",
            "description": f"Summary {i}",
            "pubDate": date_str,
        }
        for i in range(30)
    ]
    xml = _build_rss_xml(entries)
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == ARTICLES_PER_FEED


def test_parse_feed_skips_entries_missing_title():
    """Verify entries without a title are excluded."""
    recent = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent.strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = _build_rss_xml(
        [
            {
                "link": "https://example.com/no-title",
                "description": "No title here",
                "pubDate": date_str,
            },
        ]
    )
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == 0


def test_parse_feed_skips_entries_missing_link():
    """Verify entries without a link are excluded."""
    recent = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent.strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = _build_rss_xml(
        [
            {
                "title": "No Link Article",
                "description": "Has title but no link",
                "pubDate": date_str,
            },
        ]
    )
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == 0


def test_parse_feed_skips_entries_with_invalid_link():
    """Verify entries with dangerous URI schemes are excluded."""
    recent = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent.strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = _build_rss_xml(
        [
            {
                "title": "XSS Article",
                "link": "javascript:alert(1)",
                "description": "Dangerous link",
                "pubDate": date_str,
            },
        ]
    )
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == 0


def test_parse_feed_extracts_source_from_feed_title():
    """Verify Article.source comes from the feed title when present."""
    recent = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent.strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = _build_rss_xml(
        [
            {
                "title": "Story",
                "link": "https://example.com/story",
                "description": "Desc",
                "pubDate": date_str,
            },
        ],
        feed_title="My Custom Feed",
    )
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == 1
    assert articles[0].source == "My Custom Feed"


def test_parse_feed_falls_back_to_hostname_for_source():
    """Verify Article.source falls back to URL hostname when feed has no title."""
    recent = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent.strftime("%a, %d %b %Y %H:%M:%S GMT")
    # Build XML with empty feed title so it falls back to hostname
    xml = _build_rss_xml(
        [
            {
                "title": "Story",
                "link": "https://example.com/story",
                "description": "Desc",
                "pubDate": date_str,
            },
        ],
        feed_title="",
    )
    articles = _parse_feed(xml, "https://news.example.com/feed")
    assert len(articles) == 1
    assert articles[0].source == "news.example.com"


# --- fetch_all_feeds tests ---


@patch("src.rss_fetcher._fetch_feed_async", new_callable=AsyncMock)
@patch("src.rss_fetcher.FEEDS", {"testtopic": ["https://example.com/feed1"]})
def test_fetch_all_feeds_returns_articles_for_valid_topic(mock_fetch_async):
    """Verify fetch_all_feeds returns articles for a known topic."""
    article = Article(
        title="Test",
        link="https://example.com/1",
        summary="Summary",
        source="Source",
    )
    mock_fetch_async.return_value = [article]

    articles = fetch_all_feeds("testtopic")
    assert len(articles) == 1
    assert articles[0].title == "Test"


@patch("src.rss_fetcher.FEEDS", {"ai": ["https://example.com/feed"]})
def test_fetch_all_feeds_returns_empty_for_unknown_topic():
    """Verify fetch_all_feeds returns empty list and logs error for unknown topic."""
    articles = fetch_all_feeds("nonexistent")
    assert articles == []


@patch("src.rss_fetcher._fetch_feed_async", new_callable=AsyncMock)
@patch(
    "src.rss_fetcher.FEEDS",
    {"testtopic": ["https://a.com/f", "https://b.com/f", "https://c.com/f"]},
)
def test_fetch_all_feeds_continues_when_some_feeds_fail(mock_fetch_async):
    """Verify articles from successful feeds are returned when others fail."""
    article_a = Article(title="From A", link="https://a.com/1", summary="", source="A")
    article_c = Article(title="From C", link="https://c.com/1", summary="", source="C")
    mock_fetch_async.side_effect = [
        [article_a],
        [],
        [article_c],
    ]

    articles = fetch_all_feeds("testtopic")
    assert len(articles) == 2
    assert articles[0].title == "From A"
    assert articles[1].title == "From C"
