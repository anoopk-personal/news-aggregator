"""Tests for shared utility helpers."""

from src.utils import escape_markdown_url


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
