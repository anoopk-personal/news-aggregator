"""Tests for markdown generator module."""

from datetime import datetime
from pathlib import Path

from src.markdown_generator import _sanitize_markdown, get_output_path


def test_get_output_path_creates_dated_filename(tmp_path: Path):
    date = datetime(2026, 2, 10)
    path = get_output_path(tmp_path, date)
    assert path.name == "news-02-10-26.md"


def test_get_output_path_handles_duplicates(tmp_path: Path):
    date = datetime(2026, 2, 10)
    first = get_output_path(tmp_path, date)
    first.write_text("content")

    second = get_output_path(tmp_path, date)
    assert second.name == "news-02-10-26(2).md"


def test_get_output_path_handles_multiple_duplicates(tmp_path: Path):
    date = datetime(2026, 2, 10)
    for i in range(3):
        path = get_output_path(tmp_path, date)
        path.write_text(f"content {i}")

    assert (tmp_path / "news-02-10-26.md").exists()
    assert (tmp_path / "news-02-10-26(2).md").exists()
    assert (tmp_path / "news-02-10-26(3).md").exists()


def test_sanitize_markdown_removes_emojis():
    text = "# News 🎉\n- Item 🚀"
    result = _sanitize_markdown(text)
    assert "🎉" not in result
    assert "🚀" not in result


def test_sanitize_markdown_removes_script_tags():
    text = "Hello <script>alert('xss')</script> World"
    result = _sanitize_markdown(text)
    assert "<script>" not in result


def test_sanitize_markdown_preserves_markdown():
    """Output remains markdown (not converted to HTML)."""
    text = "### Title\n**Bold** and *italic*"
    result = _sanitize_markdown(text)
    assert "### Title" in result
    assert "**Bold**" in result
    assert "*italic*" in result


def test_sanitize_markdown_neutralizes_dangerous_links():
    """Dangerous URL schemes in links are neutralized (XSS prevention)."""
    text = "Click [here](javascript:alert(1)) or [there](data:text/html,<script>x</script>)"
    result = _sanitize_markdown(text)
    assert "javascript:" not in result
    assert "data:" not in result
    assert "](#" in result


def test_sanitize_markdown_neutralizes_mixed_case_schemes():
    """Mixed-case dangerous schemes are neutralized (case-insensitive)."""
    text = "Click [here](JavaScript:alert(1)) or [there](JAVASCRIPT:alert(1))"
    result = _sanitize_markdown(text)
    assert "JavaScript:" not in result
    assert "JAVASCRIPT:" not in result
    assert "](#" in result


def test_sanitize_markdown_neutralizes_vbscript():
    """vbscript: scheme is neutralized."""
    text = "Click [here](vbscript:MsgBox)"
    result = _sanitize_markdown(text)
    assert "vbscript:" not in result
    assert "](#" in result
