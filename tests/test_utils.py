"""Tests for shared utility helpers."""

import pytest

from src.utils import escape_markdown_url, is_non_routable_host, is_valid_url

HTTPS_ONLY = frozenset({"https"})


def test_escape_markdown_url_encodes_closing_paren():
    """`)` would close a markdown `(url)` slot early; must be percent-encoded."""
    hostile = "https://evil.example/a)[click](https://phish.example/x"
    escaped = escape_markdown_url(hostile)
    assert ")" not in escaped
    assert "%29" in escaped


def test_escape_markdown_url_encodes_double_quote():
    """`"` would introduce a markdown link title attribute; must be percent-encoded."""
    hostile = 'https://evil.example/a" title="Click'
    escaped = escape_markdown_url(hostile)
    assert '"' not in escaped
    assert "%22" in escaped


def test_escape_markdown_url_encodes_whitespace_and_backslash():
    """Whitespace and backslash in URLs are percent-encoded."""
    escaped = escape_markdown_url("https://a.com/ b\tc\nd\\e")
    for raw in (" ", "\t", "\n", "\\"):
        assert raw not in escaped


def test_escape_markdown_url_leaves_normal_urls_untouched():
    """A normal URL should pass through unchanged."""
    url = "https://example.com/path?q=value&other=1#frag"
    assert escape_markdown_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/feed",
        "https://news.example.com/rss.xml",
    ],
    ids=["https", "https-subdomain"],
)
def test_is_valid_url_accepts_valid_urls(url):
    assert is_valid_url(url, HTTPS_ONLY) is True


@pytest.mark.parametrize(
    "url",
    [
        # Scheme violations
        "http://example.com/feed",
        "javascript:alert('xss')",
        "file:///etc/passwd",
        "",
        "/path/to/resource",
        # Localhost and private ranges
        "http://localhost/feed",
        "http://localhost./feed",
        "http://192.168.1.1/feed",
        "http://127.0.0.1/feed",
        "http://0.0.0.0/feed",
        "http://0/feed",
        # IPv6
        "http://[::1]/feed",
        "http://[fe80::1]/feed",
        "http://[fe80::1%25eth0]/feed",
        # Numeric encoding bypass attempts
        "http://0x7f000001/feed",
        "http://017700000001/feed",
        "http://0xC0A80101/feed",
        # CGN range (RFC 6598)
        "https://100.64.0.1/feed",
    ],
    ids=lambda x: x if isinstance(x, str) else None,
)
def test_is_valid_url_rejects_invalid_urls(url):
    assert is_valid_url(url, HTTPS_ONLY) is False


def test_is_non_routable_host_catches_numeric_bypass():
    """glibc resolves 0x7f000001 as 127.0.0.1; reject it."""
    assert is_non_routable_host("0x7f000001") is True
    assert is_non_routable_host("017700000001") is True


def test_is_non_routable_host_allows_normal_domain():
    assert is_non_routable_host("example.com") is False


def test_is_non_routable_host_rejects_empty_hostname():
    assert is_non_routable_host("") is True
