"""Configuration for the news aggregator. Customize topics/sources here."""

import os
from pathlib import Path
from typing import Final

from .exceptions import SummarizationError

# --- Topics & sources ---
FEEDS: Final[dict[str, list[str]]] = {
    "ai": [
        "https://news.mit.edu/rss/topic/artificial-intelligence2",
        "https://bair.berkeley.edu/blog/feed.xml",
        "https://openai.com/blog/rss.xml",
        "https://blog.google/technology/ai/rss/",
        "https://huggingface.co/blog/feed.xml",
        "https://thegradient.pub/rss/",
        "https://www.marktechpost.com/feed/",
        "https://syncedreview.com/feed/",
        "https://www.artificialintelligence-news.com/feed/",
        "https://venturebeat.com/category/ai/feed/",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "https://feed.infoq.com/ai-ml-data-eng/",
        "https://thenewstack.io/ai/feed/",
        "https://pub.towardsai.net/feed",
        "https://www.kdnuggets.com/feed",
        "https://machinelearningmastery.com/feed/",
    ],
    "cricket": [
        "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
        "https://feeds.bbci.co.uk/sport/cricket/rss.xml",
        "https://cricketweb.net/feed",
    ],
}

TOPIC_LINE_LIMITS: Final[dict[str, tuple[int, int]]] = {
    "ai": (100, 200),
    "cricket": (20, 50),
}
DEFAULT_LINE_LIMITS: Final[tuple[int, int]] = (50, 100)

# --- Fetch ---
REQUEST_TIMEOUT: Final[int] = 30
ARTICLES_PER_FEED: Final[int] = 25
MAX_ARTICLE_AGE_HOURS: Final[int] = 72
FETCH_MAX_RETRIES: Final[int] = 2
FETCH_RETRY_BACKOFF: Final[float] = 1.5  # seconds, doubles each retry
ALLOWED_URL_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})

# --- Article truncation ---
TITLE_MAX_LENGTH: Final[int] = 500
SUMMARY_MAX_LENGTH: Final[int] = 1000
SOURCE_MAX_LENGTH: Final[int] = 100

# --- LLM ---
LITELLM_MODEL: Final[str] = "gemini-2.5-pro"
LITELLM_MAX_TOKENS: Final[int] = 8000
LITELLM_TEMPERATURE: Final[float] = 0.3
LITELLM_TIMEOUT: Final[int] = 180  # seconds


def get_llm_credentials() -> tuple[str, str]:
    """Return (api_key, base_url) from env. Raises SummarizationError if missing."""
    key = os.environ.get("OPENAI_API_KEY")
    url = os.environ.get("LITELLM_BASE_URL")
    if not key:
        raise SummarizationError("OPENAI_API_KEY not set")
    if not url:
        raise SummarizationError("LITELLM_BASE_URL not set")
    if not url.startswith("https://"):
        raise SummarizationError("LITELLM_BASE_URL must use HTTPS")
    return key, url


# --- Output ---
DEFAULT_OUTPUT_DIR: Final[Path] = Path(__file__).parent.parent / "daily-news"
OUTPUT_FILENAME_PREFIX: Final[str] = "news-"
OUTPUT_DATE_FORMAT: Final[str] = "%m-%d-%y"
CONTENT_SEPARATOR: Final[str] = "\n\n---\n\n"

# --- Security (XSS prevention) ---
DANGEROUS_LINK_SCHEMES: Final[tuple[str, ...]] = ("javascript:", "data:", "vbscript:")
