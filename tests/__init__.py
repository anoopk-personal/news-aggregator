"""Pytest fixtures for news aggregator tests."""

import pytest

from src.rss_fetcher import Article


@pytest.fixture
def sample_articles() -> list[Article]:
    """Sample articles for testing."""
    return [
        Article(
            title="AI Breakthrough",
            link="https://example.com/ai",
            summary="A major AI advancement was announced.",
            source="Tech News",
        ),
        Article(
            title="Cricket Match Result",
            link="https://example.com/cricket",
            summary="India won the match against Australia.",
            source="Sports Daily",
        ),
    ]
