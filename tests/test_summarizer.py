"""Tests for the summarizer module."""

from unittest.mock import MagicMock, patch

import pytest

from src.exceptions import SummarizationError
from src.rss_fetcher import Article
from src.summarizer import summarize_articles


@pytest.fixture
def mock_openai_client():
    """Fixture to patch the OpenAI client."""
    with patch("src.summarizer.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "Test summary"
        mock_client.chat.completions.create.return_value = mock_completion
        yield mock_openai


def test_summarize_articles_success(mock_openai_client, monkeypatch):
    """Test successful summarization."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://test.com")
    articles = [Article(title="Title", link="Link", summary="Summary", source="Source")]
    summary = summarize_articles(articles, "ai")
    assert summary == "Test summary"
    mock_openai_client.return_value.chat.completions.create.assert_called_once()


def test_summarize_articles_no_api_key(monkeypatch):
    """Test that SummarizationError is raised if OPENAI_API_KEY is not set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    articles = [Article(title="Title", link="Link", summary="Summary", source="Source")]
    with pytest.raises(SummarizationError, match="OPENAI_API_KEY not set"):
        summarize_articles(articles, "ai")


def test_summarize_articles_no_base_url(monkeypatch):
    """Test that SummarizationError is raised if LITELLM_BASE_URL is not set."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    articles = [Article(title="Title", link="Link", summary="Summary", source="Source")]
    with pytest.raises(SummarizationError, match="LITELLM_BASE_URL not set"):
        summarize_articles(articles, "ai")


def test_summarize_articles_no_articles(monkeypatch):
    """Test summarization with no articles."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://test.com")
    summary = summarize_articles([], "ai")
    assert summary == "No articles found for ai."


def test_summarize_rejects_http_base_url(monkeypatch):
    """Test that SummarizationError is raised for HTTP (non-HTTPS) base URL."""
    monkeypatch.setenv("OPENAI_API_KEY", "test_key")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://insecure.com")
    articles = [Article(title="Title", link="Link", summary="Summary", source="Source")]
    with pytest.raises(SummarizationError, match="LITELLM_BASE_URL must use HTTPS"):
        summarize_articles(articles, "ai")
