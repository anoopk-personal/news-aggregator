"""Tests for config module -- TOML feed loading and LLM config handling."""

from pathlib import Path

import pytest

from src.config import (
    _load_feeds_config,
    get_llm_config,
)
from src.exceptions import NewsAggregatorError, SummarizationError


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


def test_load_feeds_raises_when_no_file(tmp_path: Path):
    """Test that NewsAggregatorError is raised when feeds.toml doesn't exist."""
    config = tmp_path / "nonexistent.toml"
    with pytest.raises(NewsAggregatorError, match="feeds.toml not found"):
        _load_feeds_config(config)


def test_load_feeds_raises_on_empty_topics(tmp_path: Path):
    """Test that NewsAggregatorError is raised when TOML has no valid topics."""
    config = tmp_path / "feeds.toml"
    config.write_text("[topics]\n")
    with pytest.raises(NewsAggregatorError, match="No valid topics"):
        _load_feeds_config(config)


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


def test_load_feeds_ignores_non_integer_line_limits(tmp_path: Path):
    """Test that line_limits with non-integer values are ignored."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.test]
feeds = ["https://example.com/feed"]
line_limits = ["ten", "twenty"]
"""
    )
    feeds, limits = _load_feeds_config(config)
    assert "test" in feeds
    assert "test" not in limits


# --- LLM config env var tests ---


def test_get_llm_config_strips_whitespace(monkeypatch):
    """Test that leading/trailing whitespace is stripped from env vars."""
    monkeypatch.setenv("LLM_API_KEY", "  my-key\n")
    monkeypatch.setenv("LLM_BASE_URL", "  https://test.com  ")
    key, url, model = get_llm_config()
    assert key == "my-key"
    assert url == "https://test.com"


def test_get_llm_config_rejects_whitespace_only_key(monkeypatch):
    """Test that whitespace-only LLM_API_KEY is treated as missing."""
    monkeypatch.setenv("LLM_API_KEY", "   \n")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    with pytest.raises(SummarizationError, match="LLM_API_KEY not set"):
        get_llm_config()


def test_get_llm_config_allows_http_localhost(monkeypatch):
    """Test that HTTP is allowed for localhost base URLs (Ollama)."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    key, url, model = get_llm_config()
    assert url == "http://localhost:11434/v1"
    assert key == "test-key"


def test_get_llm_config_allows_http_127_0_0_1(monkeypatch):
    """Test that HTTP is allowed for 127.0.0.1 base URLs."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    key, url, model = get_llm_config()
    assert url == "http://127.0.0.1:11434/v1"


def test_get_llm_config_rejects_http_remote(monkeypatch):
    """Test that HTTP is rejected for non-loopback base URLs."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://insecure.com")
    with pytest.raises(SummarizationError, match="must use HTTPS"):
        get_llm_config()


def test_get_llm_config_no_base_url_returns_none(monkeypatch):
    """Test that omitting LLM_BASE_URL returns None (OpenAI direct mode)."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    key, url, model = get_llm_config()
    assert key == "test-key"
    assert url is None


def test_get_llm_config_no_key_localhost_uses_dummy(monkeypatch):
    """Test that loopback URL without API key uses 'ollama' as dummy key."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    key, url, model = get_llm_config()
    assert key == "ollama"
    assert url == "http://localhost:11434/v1"


def test_get_llm_config_no_key_remote_raises(monkeypatch):
    """Test that missing API key with remote URL raises error."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    with pytest.raises(SummarizationError, match="LLM_API_KEY not set"):
        get_llm_config()


def test_get_llm_config_model_from_env(monkeypatch):
    """Test that LLM_MODEL env var overrides the default model."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    key, url, model = get_llm_config()
    assert model == "gpt-4o"


def test_get_llm_config_model_default(monkeypatch):
    """Test that default model is used when LLM_MODEL is not set."""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    key, url, model = get_llm_config()
    assert model == "gemini-2.5-pro"


def test_get_llm_config_openai_direct(monkeypatch):
    """Test OpenAI direct mode: only API key set, no base URL."""
    monkeypatch.setenv("LLM_API_KEY", "sk-test123")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    key, url, model = get_llm_config()
    assert key == "sk-test123"
    assert url is None
    assert model == "gemini-2.5-pro"


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


def test_load_feeds_rejects_http_urls(tmp_path: Path):
    """Test that HTTP (non-HTTPS) feed URLs are filtered out."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.mixed]
feeds = ["https://secure.com/feed", "http://insecure.com/feed"]
"""
    )
    feeds, _ = _load_feeds_config(config)
    assert "mixed" in feeds
    assert feeds["mixed"] == ["https://secure.com/feed"]


def test_load_feeds_ignores_inverted_line_limits(tmp_path: Path):
    """Test that line_limits with min > max are ignored."""
    config = tmp_path / "feeds.toml"
    config.write_text(
        """
[topics.test]
feeds = ["https://example.com/feed"]
line_limits = [200, 50]
"""
    )
    feeds, limits = _load_feeds_config(config)
    assert "test" in feeds
    assert "test" not in limits
