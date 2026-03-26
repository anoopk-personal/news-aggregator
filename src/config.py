"""Configuration for the news aggregator. Customize topics/sources here."""

import logging
import os
import tomllib
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

from .exceptions import NewsAggregatorError, SummarizationError

logger = logging.getLogger(__name__)

FEEDS_CONFIG_PATH: Final[Path] = Path(__file__).parent.parent / "feeds.toml"


def _validate_feed_url(url: str) -> bool:
    """Lightweight check that a feed URL has a valid scheme and netloc."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("https",) and bool(parsed.netloc)
    except (ValueError, AttributeError):
        return False


def _load_feeds_config(
    config_path: Path = FEEDS_CONFIG_PATH,
) -> tuple[dict[str, list[str]], dict[str, tuple[int, int]]]:
    """Load feeds from TOML config. Raises NewsAggregatorError if missing or empty."""
    if not config_path.exists():
        raise NewsAggregatorError(f"feeds.toml not found at {config_path}")

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    topics = data.get("topics", {})
    feeds: dict[str, list[str]] = {}
    limits: dict[str, tuple[int, int]] = {}

    for name, topic in topics.items():
        if "feeds" not in topic or not isinstance(topic["feeds"], list):
            logger.warning("Topic '%s' in feeds.toml missing 'feeds' list, skipping", name)
            continue
        valid_urls = []
        for url in topic["feeds"]:
            if _validate_feed_url(url):
                valid_urls.append(url)
            else:
                logger.warning("Invalid feed URL in topic '%s', skipping: %s", name, url)
        if not valid_urls:
            logger.warning("Topic '%s' has no valid feed URLs, skipping", name)
            continue
        feeds[name] = valid_urls
        if "line_limits" in topic and len(topic["line_limits"]) == 2:
            min_val, max_val = topic["line_limits"]
            if isinstance(min_val, int) and isinstance(max_val, int):
                if min_val > max_val:
                    logger.warning(
                        "Topic '%s' line_limits min (%d) > max (%d), ignoring",
                        name,
                        min_val,
                        max_val,
                    )
                else:
                    limits[name] = (min_val, max_val)
            else:
                logger.warning("Topic '%s' line_limits must be integers, ignoring", name)

    if not feeds:
        raise NewsAggregatorError(f"No valid topics found in {config_path}")

    return feeds, limits


FEEDS, TOPIC_LINE_LIMITS = _load_feeds_config()
DEFAULT_LINE_LIMITS: Final[tuple[int, int]] = (50, 100)

# --- Deduplication ---
DEDUP_SIMILARITY_THRESHOLD: Final[float] = 0.55

# --- Fetch ---
REQUEST_TIMEOUT: Final[int] = 30
ARTICLES_PER_FEED: Final[int] = 25
MAX_ARTICLE_AGE_HOURS: Final[int] = 72
FETCH_MAX_RETRIES: Final[int] = 2
FETCH_RETRY_BACKOFF: Final[float] = 1.5  # seconds, doubles each retry
ALLOWED_URL_SCHEMES: Final[frozenset[str]] = frozenset({"https"})

# --- Article truncation ---
TITLE_MAX_LENGTH: Final[int] = 500
SUMMARY_MAX_LENGTH: Final[int] = 1000
SOURCE_MAX_LENGTH: Final[int] = 100

# --- LLM ---
LLM_MODEL_DEFAULT: Final[str] = "gemini-2.5-pro"
LLM_MAX_TOKENS: Final[int] = 8000
LLM_TEMPERATURE: Final[float] = 0.3
LLM_TIMEOUT: Final[int] = 180  # seconds


def _is_loopback_url(url: str) -> bool:
    """Return True if the URL points to a loopback address (localhost, 127.0.0.1, ::1)."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return hostname in ("localhost", "127.0.0.1", "::1")


def get_llm_config() -> tuple[str, str | None, str]:
    """Return (api_key, base_url_or_none, model) from env vars.

    Env vars:
        LLM_API_KEY   -- required for remote providers, optional for loopback (Ollama)
        LLM_BASE_URL  -- optional; omit for OpenAI direct
        LLM_MODEL     -- optional; defaults to gemini-2.5-pro

    Raises SummarizationError if required values are missing or invalid.
    """
    key = (os.environ.get("LLM_API_KEY") or "").strip()
    url = (os.environ.get("LLM_BASE_URL") or "").strip()
    model = (os.environ.get("LLM_MODEL") or "").strip() or LLM_MODEL_DEFAULT

    base_url: str | None = url or None

    if base_url is not None:
        is_loopback = _is_loopback_url(base_url)
        if not is_loopback and not base_url.startswith("https://"):
            raise SummarizationError("LLM_BASE_URL must use HTTPS for remote providers")
        if not key and is_loopback:
            key = "ollama"
    if not key:
        raise SummarizationError("LLM_API_KEY not set")

    return key, base_url, model


# --- Metrics ---
DEFAULT_METRICS_DIR: Final[Path] = Path(__file__).parent.parent / "metrics"

# Cost per 1M tokens (input, output) for dashboard estimation only.
MODEL_COST_PER_MILLION_TOKENS: Final[dict[str, tuple[float, float]]] = {
    "gemini-2.5-pro": (1.25, 10.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "llama3": (0.0, 0.0),
}
DEFAULT_COST_PER_MILLION_TOKENS: Final[tuple[float, float]] = (1.00, 3.00)

# --- Output ---
DEFAULT_OUTPUT_DIR: Final[Path] = Path(__file__).parent.parent / "daily-news"
OUTPUT_FILENAME_PREFIX: Final[str] = "news-"
OUTPUT_DATE_FORMAT: Final[str] = "%m-%d-%y"
CONTENT_SEPARATOR: Final[str] = "\n\n---\n\n"

# --- Security (XSS prevention) ---
DANGEROUS_LINK_SCHEMES: Final[tuple[str, ...]] = ("javascript:", "data:", "vbscript:")
