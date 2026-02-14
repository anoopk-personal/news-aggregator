# News Aggregator

[![CI](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml)

RSS news, summarized by an LLM — you bring your own key.

Pull from multiple feeds per topic, get a clean digest in markdown. Everything is configurable in one place.

## What it does

- Fetches articles from RSS (last 72 hours)
- Summarizes with an LLM (you provide the API key)
- Outputs markdown grouped by theme with source attribution
- URL validation and sanitization for security

**Current topics:** AI (18 sources), Cricket (3 sources). Add or change topics in [`src/config.py`](src/config.py).

## Quick start

```bash
uv sync
cp .env.example .env   # Add your API key and base URL
uv run get-news --topic ai
```

**Your API key:** The summarizer uses any OpenAI-compatible API. I used LiteLLM + Gemini by default, but you can point `LITELLM_BASE_URL` at your own proxy or service—OpenAI, Anthropic, local models, etc. Put the key in `.env` as `OPENAI_API_KEY`.

## Configuration

All settings live in [`src/config.py`](src/config.py): topics, RSS feeds, line limits, LLM model, fetch options, output format. Add a topic by adding entries to `FEEDS` and `TOPIC_LINE_LIMITS`.

## Usage

```bash
uv run get-news --topic ai
uv run get-news --topic cricket
uv run get-news --topic both
uv run get-news --topic ai --output-dir /path/to/output
```

## Development

```bash
uv run pytest -v
uv run ruff check . && uv run ruff format .
```

## GitHub Actions

**Daily news:** Runs at 5 AM Central (11:00 UTC), generates both topics, opens a PR to `dev`. Manual trigger via `workflow_dispatch`.

**CI:** Lint and tests on PRs to `dev`.

**Secrets:** `OPENAI_API_KEY`, `LITELLM_BASE_URL`, and `PAT_TOKEN` (for PR creation).

## Output

Files go to `daily-news/` as `news-MM-DD-YY.md` (duplicates get `(2)`, `(3)`, etc.). Each file has summaries grouped by theme with source attribution.
