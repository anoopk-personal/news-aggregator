# News Aggregator

[![CI](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml)

RSS news, summarized by an LLM — you bring your own key.

Pulls from multiple feeds per topic, delivers a clean daily digest in markdown.

## What it does

- Fetches recent articles from RSS feeds (last 72 hours)
- Summarizes them with an LLM into a themed markdown digest
- Automatically retries failed feeds to avoid missing articles
- Runs daily via GitHub Actions, or on-demand from the command line

**Built-in topics:** AI (18 sources) and Cricket (3 sources). Add your own topics by editing [`feeds.toml`](feeds.toml).

## Quick start

```bash
uv sync
cp .env.example .env   # Add your API key and base URL
uv run get-news --topic ai
```

**Skip the LLM** for a quick local test (no API key needed):

```bash
uv run get-news --topic ai --skip-summarize
```

**Your API key:** The summarizer works with any OpenAI-compatible API. Set `OPENAI_API_KEY` and `LITELLM_BASE_URL` in `.env`.

## Usage

```bash
uv run get-news --topic ai              # AI digest
uv run get-news --topic cricket          # Cricket digest
uv run get-news --topic both             # Both topics
uv run get-news --topic ai --dry-run     # Preview in terminal, no file written
uv run get-news --topic ai --skip-summarize --dry-run   # Quick preview, no LLM
```

Output goes to `daily-news/` as `news-MM-DD-YY.md`.

## Adding custom topics

Edit [`feeds.toml`](feeds.toml) in the project root — no code changes needed:

```toml
[topics.cybersecurity]
feeds = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://krebsonsecurity.com/feed/",
]
line_limits = [50, 100]   # optional: min/max lines for LLM summary
```

The new topic is available immediately: `uv run get-news --topic cybersecurity`

## GitHub Actions

- **Daily digest** — Runs at 5 AM Central, generates both topics, opens a PR to `dev` with auto-merge
- **CI** — Lint and tests on every PR to `dev`

## Development

```bash
make test       # Run tests
make lint       # Check code style
make format     # Auto-fix formatting
make typecheck  # Type checking
make audit      # Dependency vulnerability scan
```
