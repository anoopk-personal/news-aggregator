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
make install-hooks  # install git pre-commit hook (email validation)
```

Run a single test file: `uv run pytest tests/test_rss_fetcher.py -v`
Run a single test: `uv run pytest tests/test_rss_fetcher.py::test_sanitize_removes_html_tags -v`

## Architecture

**Data flow:** CLI (`cli.py`) → async RSS fetch (`rss_fetcher.py`) → deduplicate (`deduplicator.py`) → LLM summarize (`summarizer.py`) → write markdown (`markdown_generator.py`)

- **cli.py** — Click entry point (`get-news` command), orchestrates the pipeline. `--skip-summarize` flag bypasses LLM and uses `_format_articles_as_markdown()` to produce a plain listing. `--skip-dedup` flag bypasses article deduplication. `--dry-run` flag prints digest to stdout without writing a file
- **config.py** — Loads topics/feeds from `feeds.toml` via `_load_feeds_config()` (raises `NewsAggregatorError` if missing). All other constants centralized here (timeouts, retry settings, line limits, dedup threshold, LLM model). No magic numbers elsewhere
- **deduplicator.py** — `deduplicate_articles()` groups near-duplicate articles using `difflib.SequenceMatcher` similarity (threshold: `DEDUP_SIMILARITY_THRESHOLD`). Single-linkage clustering keeps the article with the longest summary from each cluster and adds "Also covered by" attribution
- **rss_fetcher.py** — `fetch_all_feeds()` uses `asyncio` + `httpx.AsyncClient` for concurrent fetching with automatic retry (exponential backoff). `Article` dataclass holds parsed data. Filters to last 72 hours, max 25 articles/feed
- **summarizer.py** — OpenAI SDK configured with LiteLLM `base_url`. Uses topic-specific line limits from `feeds.toml`, defaulting to (50, 100)
- **markdown_generator.py** — Writes `news-MM-DD-YY.md` to `daily-news/`, duplicates get `(2)` suffix
- **utils.py** — Shared `EMOJI_PATTERN` regex used by both fetcher and markdown generator
- **exceptions.py** — `NewsAggregatorError` base, `SummarizationError` for LLM failures
- **feeds.toml** — User-editable topic/feed configuration loaded by `config.py` at startup

## daily-news/ Output Pattern

The `daily-news/` directory is in `.gitignore` because local runs generate files there. In the GitHub Actions daily workflow (`daily-news.yml`), the generated markdown file is force-added with `git add -f daily-news/` so it appears in the PR diff. This lets the automated workflow commit generated output without polluting local development.

## Dedup Threshold

`DEDUP_SIMILARITY_THRESHOLD` (default: `0.55`) in `config.py` controls how aggressively the deduplicator merges articles. It is the minimum `difflib.SequenceMatcher` ratio for two articles to be considered duplicates.

- **Lower** (e.g., 0.4) = more aggressive merging, fewer articles in output
- **Higher** (e.g., 0.7) = more conservative, keeps articles that are only loosely related

To test threshold changes without hitting the LLM or writing files:

```bash
uv run get-news --topic ai --skip-summarize --dry-run
```

Review the console output to see which articles survive deduplication.

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

Daily-news PRs require manual merge. Dependabot PRs auto-merge (squash) once CI passes. Other PRs require manual merge.

## GitHub Actions

- **ci.yml** -- Runs lint, format check, type check, dependency audit, and tests on PRs/pushes to `dev`. Jobs: `lint-and-test`, `secrets-scan` (gitleaks, requires `GITLEAKS_LICENSE` repo secret)
- **daily-news.yml** — Scheduled at 11:00 UTC (5 AM Central), creates `daily-news/YYYY-MM-DD` branch, generates news, and opens a PR (manual merge required)
- **dependabot-auto-merge.yml** — Auto-merges Dependabot patch/minor PRs. Triggers on all PRs but skips non-Dependabot actors via job condition

## Security

Feeds are untrusted input. Defenses are layered across the pipeline:

- **SSRF** (`rss_fetcher.py`): Two-layer defense: (1) pre-flight `_is_valid_url()` using `_is_non_routable_host()` with `not is_global` (covers private, loopback, link-local, CGN/RFC 6598, documentation, and benchmarking ranges), (2) manual redirect following with `_is_valid_url()` validation on each hop (prevents 302-to-private-IP bypass). HTTPS-only scheme enforcement for feed URLs. Also rejects trailing dots, zone IDs, bare integers (hex/octal/decimal), `file://` schemes
- **Prompt injection** (`summarizer.py`): Articles serialized as JSON (not XML tags) to avoid prompt boundary confusion
- **Config validation** (`config.py`): Feed URLs validated at load time (HTTPS, no private hosts). Env vars stripped of whitespace
- **XSS** (`markdown_generator.py`, `rss_fetcher.py`): nh3 strips HTML; `javascript:`, `data:`, `vbscript:` URI schemes neutralized (case-insensitive)
- **Secrets scanning** (`ci.yml`): gitleaks scans full git history on every PR/push
- **XXE**: feedparser does not process external entities
- **Pre-commit hook** (`scripts/pre-commit`): Rejects commits with empty or placeholder git email. Install with `make install-hooks`

## Environment Variables

`OPENAI_API_KEY` and `LITELLM_BASE_URL` are required for the full summarization pipeline (see `.env.example`). Not needed for `--skip-summarize` local runs. In CI, these plus `PAT_TOKEN` are configured as GitHub secrets.
