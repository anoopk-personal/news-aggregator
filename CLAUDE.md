# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python CLI tool that fetches RSS feeds (AI, Cricket, and Finance topics), summarizes articles using any OpenAI-compatible LLM provider (Ollama, OpenAI, OpenRouter, LiteLLM, etc.), and outputs daily markdown digests. Runs on a daily schedule via GitHub Actions.

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
make run-finance    # fetch finance articles (no LLM, skips summarization)
make run-all        # fetch all articles (no LLM, skips summarization)
make install-hooks  # install git pre-commit hook (email validation)
make dashboard      # regenerate pipeline health dashboard in README.md
```

Run a single test file: `uv run pytest tests/test_rss_fetcher.py -v`
Run a single test: `uv run pytest tests/test_rss_fetcher.py::test_sanitize_removes_html_tags -v`

## Architecture

**Data flow:** CLI (`cli.py`) → async RSS fetch (`rss_fetcher.py`) → deduplicate (`deduplicator.py`) → LLM summarize (`summarizer.py`) → write markdown (`markdown_generator.py`) → save metrics (`metrics.py`)

- **cli.py** — Click entry point (`get-news` command), orchestrates the pipeline. `--skip-summarize` flag bypasses LLM and uses `_format_articles_as_markdown()` to produce a plain listing. `--skip-dedup` flag bypasses article deduplication. `--dry-run` flag prints digest to stdout without writing a file or metrics. Collects per-topic metrics (feed stats, token usage, cost, timing) and saves to `metrics/history.jsonl`. Per-topic cost is computed via `estimate_cost()` using that run's model before metrics are saved
- **config.py** — Loads topics/feeds from `feeds.toml` via `_load_feeds_config()` (raises `NewsAggregatorError` if missing). All other constants centralized here (timeouts, retry settings, line limits, dedup threshold, LLM cost table). `get_llm_config()` returns `(api_key, base_url | None, model)` from `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` env vars. No magic numbers elsewhere
- **deduplicator.py** — `deduplicate_articles()` groups near-duplicate articles using `difflib.SequenceMatcher` similarity (threshold: `DEDUP_SIMILARITY_THRESHOLD`). Single-linkage clustering keeps the article with the longest summary from each cluster and adds "Also covered by" attribution
- **rss_fetcher.py** — `fetch_all_feeds(topic)` returns a `FetchResult` dataclass (articles + feed success/failure counts). It is a thin sync wrapper around `fetch_all_feeds_async(topic)`, which is the real implementation and is safe to `await` from inside an existing event loop. Both use `asyncio` + `httpx.AsyncClient` for concurrent fetching with automatic retry (exponential backoff). `Article` dataclass holds parsed data. Filters to last 72 hours, max 25 articles/feed
- **summarizer.py** — `summarize_articles()` returns a `SummarizeResult` dataclass (content + token usage). OpenAI SDK client, optionally configured with a custom `base_url` for non-OpenAI providers. Model name from `LLM_MODEL` env var (default: `gemini-2.5-pro`). Uses topic-specific line limits from `feeds.toml`, defaulting to (50, 100)
- **metrics.py** — `RunMetrics` and `TopicMetrics` dataclasses for per-run pipeline metrics. `TopicMetrics` includes a `cost` field computed at save time via `estimate_cost()` (uses model-specific rates from `config.py`). `RunMetrics.total_cost` aggregates across topics. Stored as JSONL (one JSON line per run) in `metrics/history.jsonl`. Same-day reruns replace the last line. Old JSON entries without `cost` default to 0.0 on load
- **dashboard.py** — Reads metrics from JSONL file (`metrics/history.jsonl`) and injects a three-section dashboard into `README.md` between `<!-- DASHBOARD:START/END -->` markers. Sections: (1) hero line with last run date, total articles, feed success count, cost, and duration; (2) per-topic table (Topic, Feeds X/Y, Articles, Cost) from the most recent run; (3) historical periods table (7 days, 30 days, All time) with Runs, Articles, Feed Health %, and Cost. Footer shows the model name and average cost per run. Runnable standalone: `uv run python -m src.dashboard`
- **markdown_generator.py** — Writes `news-MM-DD-YY.md` to `daily-news/`, duplicates get `(2)` suffix
- **utils.py** — Shared `EMOJI_PATTERN` regex used by fetcher and markdown generator; `escape_markdown_url()` percent-encodes markdown-unsafe characters (`)`, `(`, `[`, `]`, `"`, backslash, whitespace) in URLs before interpolation in `cli.py`, `deduplicator.py`, and `summarizer.py`; `is_valid_url()` and `is_non_routable_host()` provide centralized SSRF validation used by both `config.py` (load-time) and `rss_fetcher.py` (fetch-time + redirect re-validation)
- **logging_config.py** — `configure_logging()` sets up the root logger to write to stderr. Format auto-selects: human-readable (`LEVEL: message`) when stderr is a TTY, JSON (one object per line) when not (CI, redirected output). Called once from `cli.py` and `dashboard.py` entry points. Idempotent. Stdout is left untouched so `--dry-run > digest.md` works cleanly.
- **exceptions.py** — `NewsAggregatorError` base, `SummarizationError` for LLM failures
- **feeds.toml** — User-editable topic/feed configuration loaded by `config.py` at startup

## daily-news/ and metrics/ Output Pattern

`daily-news/` is in `.gitignore` because the generated markdown files are large. In the GitHub Actions daily workflow (`daily-news.yml`), daily-news files are force-added with `git add -f daily-news/`. Metrics are stored in a single JSONL file (`metrics/history.jsonl`) -- one JSON line per daily run, appended on each run (same-day reruns replace the last line). The JSONL file is tracked in git; individual `metrics/*.json` files are gitignored. The workflow also runs `uv run python -m src.dashboard` to regenerate the README dashboard and commits `README.md` alongside the daily output.

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
- CLI tests mock `fetch_all_feeds` (returns `FetchResult`), `summarize_articles` (returns `SummarizeResult`), and `RunMetrics.save` to avoid file I/O
- Dashboard tests use `tmp_path` for README injection and metrics loading

## Git Workflow

All changes go through PRs to `dev`. Branch protection requires the `ci` CI check to pass.

**Branch prefixes:** `feature/`, `fix/`, `docs/`, `test/`, `chore/`. The `daily-news/` prefix is reserved for the automated workflow.

Daily-news PRs require manual merge. Dependabot PRs auto-merge (squash) once CI passes. Other PRs require manual merge.

## GitHub Actions

- **ci.yml** -- Runs lint, format check, type check, dependency audit, and tests on PRs/pushes to `dev`. Jobs: `ci`, `secrets-scan` (gitleaks, requires `GITLEAKS_LICENSE` repo secret)
- **daily-news.yml** — Scheduled at 11:00 UTC (5 AM Central), creates `daily-news/YYYY-MM-DD` branch, generates news, updates the README dashboard from metrics, and opens a PR (manual merge required)
- **dependabot-auto-merge.yml** — Auto-merges Dependabot patch/minor PRs. Triggers on all PRs but skips non-Dependabot actors via job condition

## Security

Feeds are untrusted input. Defenses are layered across the pipeline:

- **SSRF** (`utils.py`, `rss_fetcher.py`, `config.py`): Two-layer defense: (1) pre-flight `is_valid_url()` using `is_non_routable_host()` with `not is_global` (covers private, loopback, link-local, CGN/RFC 6598, documentation, and benchmarking ranges), (2) manual redirect following with `is_valid_url()` validation on each hop (prevents 302-to-private-IP bypass). HTTPS-only scheme enforcement for feed URLs. Also rejects trailing dots, zone IDs, bare integers (hex/octal/decimal), `file://` schemes. Validation functions centralized in `utils.py`, used by both `config.py` (load-time) and `rss_fetcher.py` (fetch-time)
- **Prompt injection** (`summarizer.py`): Articles serialized as JSON (not XML tags) to avoid prompt boundary confusion
- **Config validation** (`config.py`): Feed URLs validated at load time (HTTPS, no private hosts). Env vars stripped of whitespace
- **XSS** (`markdown_generator.py`, `rss_fetcher.py`): nh3 strips HTML; `javascript:`, `data:`, `vbscript:` URI schemes neutralized (case-insensitive)
- **Markdown link injection** (`rss_fetcher.py`, `utils.py`): `_sanitize()` strips `[` and `]` from feed-derived text so hostile source names cannot break out of `[text](url)` link-text slots. `escape_markdown_url()` percent-encodes `)`, `(`, `[`, `]`, `"`, backslash, and whitespace in link URLs before interpolation in `cli.py`, `deduplicator.py`, and `summarizer.py`, preventing URL-slot breakout / nested-link injection
- **Secrets scanning** (`ci.yml`): gitleaks scans full git history on every PR/push
- **XXE**: feedparser does not process external entities
- **Pre-commit hook** (`scripts/pre-commit`): Rejects commits with empty or placeholder git email. Install with `make install-hooks`

## Environment Variables

LLM summarization uses three env vars (set in `.env` or exported):

- `LLM_API_KEY` — API key for the LLM provider. Optional for local Ollama (auto-set to `"ollama"`)
- `LLM_BASE_URL` — Base URL for the provider. Optional for OpenAI direct (SDK default). HTTP allowed for localhost only; HTTPS required for remote
- `LLM_MODEL` — Model name (default: `gemini-2.5-pro`). Provider-specific, e.g. `llama3` for Ollama, `gpt-4o` for OpenAI

None needed for `--skip-summarize` local runs. In CI, `LLM_API_KEY`, `LLM_BASE_URL`, and `PAT_TOKEN` are configured as GitHub secrets.
