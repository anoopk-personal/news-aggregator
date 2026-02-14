"""Tests for RSS fetcher module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from src.rss_fetcher import Article, _is_valid_url, _parse_date, _sanitize, fetch_feed


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
    import httpx

    mock_get.side_effect = httpx.HTTPError("Test error")
    articles = fetch_feed("https://example.com/feed")
    assert articles == []
