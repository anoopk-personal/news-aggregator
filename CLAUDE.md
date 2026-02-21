# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python CLI tool that fetches RSS feeds (AI and Cricket topics), summarizes articles using LLM (Gemini 2.5 Pro via LiteLLM proxy), and outputs daily markdown digests. Runs on a daily schedule via GitHub Actions.

- **Default branch:** `dev`
- **Python 3.12**, managed with `uv`

## Commands

```bash
make install        # uv sync
make test           # uv run pytest -v
make test-cov       # pytest with coverage (fails under 80%)
make lint           # ruff check + format check
make format         # ruff fix + format
make typecheck      # mypy type checking on src/
make audit          # pip-audit dependency vulnerability scan
make run-ai         # fetch AI articles (no LLM, skips summarization)
make run-cricket    # fetch cricket articles (no LLM, skips summarization)
make run-both       # fetch all articles (no LLM, skips summarization)
make install-hooks  # install git pre-commit hook (email enforcement)
```

Run a single test file: `uv run pytest tests/test_rss_fetcher.py -v`
Run a single test: `uv run pytest tests/test_rss_fetcher.py::test_sanitize_strips_html -v`

## Architecture

**Data flow:** CLI (`cli.py`) → async RSS fetch (`rss_fetcher.py`) → LLM summarize (`summarizer.py`) → write markdown (`markdown_generator.py`)

- **cli.py** — Click entry point (`get-news` command), orchestrates the pipeline. `--skip-summarize` flag bypasses LLM and uses `_format_articles_as_markdown()` to produce a plain listing. `--dry-run` flag prints digest to stdout without writing a file
- **config.py** — Loads topics/feeds from `feeds.toml` via `_load_feeds_config()` (falls back to hardcoded defaults). All other constants centralized here (timeouts, retry settings, line limits, LLM model). No magic numbers elsewhere
- **rss_fetcher.py** — `fetch_all_feeds()` uses `asyncio` + `httpx.AsyncClient` for concurrent fetching with automatic retry (exponential backoff). `Article` dataclass holds parsed data. Filters to last 72 hours, max 25 articles/feed
- **summarizer.py** — OpenAI SDK configured with LiteLLM `base_url`. Topic-specific line limits (AI: 100-200, Cricket: 20-50)
- **markdown_generator.py** — Writes `news-MM-DD-YY.md` to `daily-news/`, duplicates get `(2)` suffix
- **utils.py** — Shared `EMOJI_PATTERN` regex used by both fetcher and markdown generator
- **exceptions.py** — `NewsAggregatorError` base, `SummarizationError` for LLM failures
- **feeds.toml** — User-editable topic/feed configuration loaded by `config.py` at startup

## Ruff Configuration

Line length 100, double quotes, target py312. Lint rules: `E, F, I, W, UP, S, B` with `S101` ignored (allows assert in tests).

## Testing Conventions

- Tests use dynamic dates relative to `datetime.now()` — no hardcoded dates
- Use `monkeypatch` for environment variables, not direct `os.environ`
- Mock at the `httpx` level for RSS fetcher tests
- Mock OpenAI client for summarizer tests

## Git Workflow

All changes go through PRs to `dev`. Branch protection requires the `lint-and-test` CI check to pass.

**Branch prefixes:** `feature/`, `fix/`, `docs/`, `test/`, `chore/`. The `daily-news/` prefix is reserved for the automated workflow.

Daily-news PRs auto-merge (squash) once CI passes. Other PRs require manual merge.

## GitHub Actions

- **ci.yml** — Runs ruff + pytest on PRs/pushes to `dev`. Job name: `lint-and-test`
- **daily-news.yml** — Scheduled at 11:00 UTC (5 AM Central), creates `daily-news/YYYY-MM-DD` branch, generates news, opens PR, and enables auto-merge

## Environment Variables

`OPENAI_API_KEY` and `LITELLM_BASE_URL` are required for the full summarization pipeline (see `.env.example`). Not needed for `--skip-summarize` local runs. In CI, these plus `PAT_TOKEN` are configured as GitHub secrets.
