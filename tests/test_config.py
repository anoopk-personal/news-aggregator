"""Tests for config module — TOML feed loading and credential handling."""

from pathlib import Path

import pytest

from src.config import (
    _DEFAULT_FEEDS,
    _DEFAULT_TOPIC_LINE_LIMITS,
    _load_feeds_config,
    get_llm_credentials,
)
from src.exceptions import SummarizationError


def test_load_feeds_from_toml(tmp_path: Path):
    """Test loading feeds from a valid TOML config file."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.security]
feeds = ["https://example.com/sec-feed"]
line_limits = [30, 60]

[topics.python]
feeds = ["https://example.com/py-feed", "https://example.com/py-feed2"]
"""
    )
    feeds, limits = _load_feeds_config(config)
    assert "security" in feeds
    assert feeds["security"] == ["https://example.com/sec-feed"]
    assert limits["security"] == (30, 60)
    assert "python" in feeds
    assert len(feeds["python"]) == 2
    assert "python" not in limits  # no line_limits set


def test_load_feeds_fallback_when_no_file(tmp_path: Path):
    """Test that built-in defaults are used when feeds.toml doesn't exist."""
    config = tmp_path / "nonexistent.toml"
    feeds, limits = _load_feeds_config(config)
    assert feeds == _DEFAULT_FEEDS
    assert limits == _DEFAULT_TOPIC_LINE_LIMITS


def test_load_feeds_fallback_on_empty_topics(tmp_path: Path):
    """Test fallback to defaults when TOML has no valid topics."""
    config = tmp_path / "feeds.toml"
    config.write_text("[topics]\n")
    feeds, limits = _load_feeds_config(config)
    assert feeds == _DEFAULT_FEEDS
    assert limits == _DEFAULT_TOPIC_LINE_LIMITS


def test_load_feeds_skips_topic_without_feeds_key(tmp_path: Path):
    """Test that topics without a 'feeds' list are skipped."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.valid]
feeds = ["https://example.com/feed"]

[topics.invalid]
line_limits = [10, 20]
"""
    )
    feeds, limits = _load_feeds_config(config)
    assert "valid" in feeds
    assert "invalid" not in feeds


def test_load_feeds_ignores_malformed_line_limits(tmp_path: Path):
    """Test that line_limits with wrong length are ignored."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.test]
feeds = ["https://example.com/feed"]
line_limits = [10]
"""
    )
    feeds, limits = _load_feeds_config(config)
    assert "test" in feeds
    assert "test" not in limits


# --- Credential env var tests ---


def test_get_llm_credentials_strips_whitespace(monkeypatch):
    """Test that leading/trailing whitespace is stripped from env vars."""
    monkeypatch.setenv("OPENAI_API_KEY", "  my-key\n")
    monkeypatch.setenv("LITELLM_BASE_URL", "  https://test.com  ")
    key, url = get_llm_credentials()
    assert key == "my-key"
    assert url == "https://test.com"


def test_get_llm_credentials_rejects_whitespace_only(monkeypatch):
    """Test that whitespace-only env vars are treated as missing."""
    monkeypatch.setenv("OPENAI_API_KEY", "   \n")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://test.com")
    with pytest.raises(SummarizationError, match="OPENAI_API_KEY not set"):
        get_llm_credentials()


# --- Feed URL validation tests ---


def test_load_feeds_filters_invalid_urls(tmp_path: Path):
    """Test that invalid feed URLs are filtered out from a topic."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.mixed]
feeds = ["https://valid.com/feed", "ftp://bad.com/feed", "not-a-url"]
"""
    )
    feeds, _ = _load_feeds_config(config)
    assert "mixed" in feeds
    assert feeds["mixed"] == ["https://valid.com/feed"]


def test_load_feeds_skips_topic_with_all_invalid_urls(tmp_path: Path):
    """Test that a topic with only invalid feed URLs is skipped entirely."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.good]
feeds = ["https://valid.com/feed"]

[topics.bad]
feeds = ["ftp://nope.com", "javascript:alert(1)"]
"""
    )
    feeds, _ = _load_feeds_config(config)
    assert "good" in feeds
    assert "bad" not in feeds
