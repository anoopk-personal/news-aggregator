"""Tests for config module — TOML feed loading."""

from pathlib import Path

from src.config import _DEFAULT_FEEDS, _DEFAULT_TOPIC_LINE_LIMITS, _load_feeds_config


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
