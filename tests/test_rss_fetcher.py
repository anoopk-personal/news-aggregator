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
    recent = datetime.now(UTC) - timedelta(hours=2)
    date_str = recent.strftime("%a, %d %b %Y %H:%M:%S GMT")
    entry = {"published": date_str}
    result = _parse_date(entry)
    assert result is not None
    assert abs((result - recent).total_seconds()) < 2


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


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/feed",
        "https://news.example.com/rss.xml",
    ],
    ids=["https", "https-subdomain"],
)
def test_is_valid_url_accepts_valid_urls(url):
    assert _is_valid_url(url) is True


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        # Scheme violations
        ("http://example.com/feed", "http-scheme"),
        ("javascript:alert('xss')", "javascript-scheme"),
        ("file:///etc/passwd", "file-scheme"),
        ("", "empty-string"),
        ("/path/to/resource", "relative-path"),
        # Localhost and private ranges
        ("http://localhost/feed", "localhost"),
        ("http://localhost./feed", "localhost-trailing-dot"),
        ("http://192.168.1.1/feed", "private-ip-192"),
        ("http://127.0.0.1/feed", "loopback-ipv4"),
        ("http://0.0.0.0/feed", "zero-quad"),
        ("http://0/feed", "zero-ip"),
        # IPv6
        ("http://[::1]/feed", "ipv6-loopback"),
        ("http://[fe80::1]/feed", "ipv6-link-local"),
        ("http://[fe80::1%25eth0]/feed", "ipv6-zone-id"),
        # Numeric encoding bypass attempts
        ("http://0x7f000001/feed", "hex-loopback"),
        ("http://017700000001/feed", "octal-loopback"),
        ("http://0xC0A80101/feed", "hex-private-ip"),
        # CGN range (RFC 6598)
        ("https://100.64.0.1/feed", "cgn-range"),
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_is_valid_url_rejects_invalid_urls(url, reason):
    assert _is_valid_url(url) is False


@patch("src.rss_fetcher.httpx.get")
def test_fetch_feed_success(mock_get):
    """Test successful feed fetching and parsing."""
    # Use a date within the 72-hour window
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    mock_response = MagicMock()
    mock_response.is_redirect = False
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
    success_response.is_redirect = False
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


# --- Network error subclass retry tests ---


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_retries_on_timeout_exception(mock_sleep):
    """Retry once on TimeoutException, then succeed on second attempt."""
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    success_response = MagicMock()
    success_response.is_redirect = False
    success_response.raise_for_status = MagicMock()
    success_response.text = FEED_XML.format(date_str=date_str)

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[httpx.TimeoutException("read timed out"), success_response],
    )

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert len(articles) == 1
    assert articles[0].title == "Retry Article"
    assert client.get.call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_retries_on_connect_error(mock_sleep):
    """Retry once on ConnectError, then succeed on second attempt."""
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    success_response = MagicMock()
    success_response.is_redirect = False
    success_response.raise_for_status = MagicMock()
    success_response.text = FEED_XML.format(date_str=date_str)

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[httpx.ConnectError("connection refused"), success_response],
    )

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert len(articles) == 1
    assert articles[0].title == "Retry Article"
    assert client.get.call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_retries_on_http_status_error(mock_sleep):
    """Retry once on HTTPStatusError (503), then succeed on second attempt."""
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    success_response = MagicMock()
    success_response.is_redirect = False
    success_response.raise_for_status = MagicMock()
    success_response.text = FEED_XML.format(date_str=date_str)

    error_request = httpx.Request("GET", "https://example.com/feed")
    error_response = httpx.Response(503, request=error_request)

    status_error = httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=error_request,
        response=error_response,
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(
        side_effect=[status_error, success_response],
    )

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert len(articles) == 1
    assert articles[0].title == "Retry Article"
    assert client.get.call_count == 2
    mock_sleep.assert_called_once()


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_no_retry_on_404(mock_sleep):
    """404 is non-retryable: should fail immediately without retry."""
    error_request = httpx.Request("GET", "https://example.com/feed")
    error_response = httpx.Response(404, request=error_request)

    status_error = httpx.HTTPStatusError(
        "404 Not Found",
        request=error_request,
        response=error_response,
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=status_error)

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert articles == []
    assert client.get.call_count == 1
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_no_retry_on_403(mock_sleep):
    """403 is non-retryable: should fail immediately without retry."""
    error_request = httpx.Request("GET", "https://example.com/feed")
    error_response = httpx.Response(403, request=error_request)

    status_error = httpx.HTTPStatusError(
        "403 Forbidden",
        request=error_request,
        response=error_response,
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=status_error)

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert articles == []
    assert client.get.call_count == 1
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_exhausts_retries_on_persistent_timeout(mock_sleep):
    """Exhaust retries on persistent TimeoutException, return []."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.TimeoutException("read timed out"))

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert articles == []
    assert client.get.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_exhausts_retries_on_persistent_connect_error(mock_sleep):
    """Exhaust retries on persistent ConnectError, return []."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert articles == []
    assert client.get.call_count == 3
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


# --- Large feed handling tests ---


def test_parse_feed_caps_then_filters_by_age():
    """30 entries (20 recent + 10 old): cap applies first, then age filter yields 20."""
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    old_date = datetime.now(UTC) - timedelta(hours=96)
    recent_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")
    old_str = old_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    # Build 20 recent entries followed by 10 old entries
    entries = [
        {
            "title": f"Recent Article {i}",
            "link": f"https://example.com/recent-{i}",
            "description": f"Recent summary {i}",
            "pubDate": recent_str,
        }
        for i in range(20)
    ] + [
        {
            "title": f"Old Article {i}",
            "link": f"https://example.com/old-{i}",
            "description": f"Old summary {i}",
            "pubDate": old_str,
        }
        for i in range(10)
    ]
    xml = _build_rss_xml(entries)
    articles = _parse_feed(xml, "https://example.com/feed")
    assert len(articles) == 20
    assert all("Recent" in a.title for a in articles)


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


# --- Redirect SSRF tests ---


@patch("src.rss_fetcher.httpx.get")
def test_fetch_feed_blocks_redirect_to_private_ip(mock_get):
    """302 redirect to a private IP must be blocked."""
    redirect_response = MagicMock()
    redirect_response.is_redirect = True
    redirect_response.headers = {"location": "http://192.168.1.1/"}
    mock_get.return_value = redirect_response

    articles = fetch_feed("https://example.com/feed")
    assert articles == []


@patch("src.rss_fetcher.httpx.get")
def test_fetch_feed_follows_safe_redirect(mock_get):
    """302 redirect to a valid HTTPS URL should be followed and return articles."""
    recent_date = datetime.now(UTC) - timedelta(hours=1)
    date_str = recent_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    redirect_response = MagicMock()
    redirect_response.is_redirect = True
    redirect_response.headers = {"location": "https://cdn.example.com/feed.xml"}

    final_response = MagicMock()
    final_response.is_redirect = False
    final_response.raise_for_status = MagicMock()
    final_response.text = f"""
    <rss version="2.0">
    <channel>
        <title>Redirected Feed</title>
        <item>
            <title>Redirected Article</title>
            <link>https://example.com/article</link>
            <description>Test</description>
            <pubDate>{date_str}</pubDate>
        </item>
    </channel>
    </rss>
    """
    mock_get.side_effect = [redirect_response, final_response]

    articles = fetch_feed("https://example.com/feed")
    assert len(articles) == 1
    assert articles[0].title == "Redirected Article"


@pytest.mark.asyncio
@patch("src.rss_fetcher.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_feed_async_blocks_redirect_to_private_ip(mock_sleep):
    """Async path: 302 redirect to a private IP must be blocked."""
    redirect_response = MagicMock()
    redirect_response.is_redirect = True
    redirect_response.headers = {"location": "http://169.254.169.254/latest/meta-data/"}

    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=redirect_response)

    articles = await _fetch_feed_async("https://example.com/feed", client)
    assert articles == []
    mock_sleep.assert_not_called()


@patch("src.rss_fetcher.httpx.get")
def test_fetch_feed_blocks_excessive_redirects(mock_get):
    """More than _MAX_REDIRECTS hops should return empty list."""
    redirect_response = MagicMock()
    redirect_response.is_redirect = True
    redirect_response.headers = {"location": "https://example.com/feed"}
    mock_get.return_value = redirect_response

    articles = fetch_feed("https://example.com/feed")
    assert articles == []
