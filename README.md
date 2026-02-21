# News Aggregator

[![CI](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

RSS feeds in, markdown digest out. Optionally summarized by an LLM.

Fetches articles from RSS feeds, groups them by topic, and either lists them directly or passes them through an LLM (any OpenAI-compatible API) for a concise, themed summary. Ships with AI and Cricket topics; add your own in a TOML file.

---

### Try it now (no API key needed)

```bash
git clone git@github.com:anoopk-personal/news-aggregator.git
cd news-aggregator
uv sync
uv run get-news --topic ai --skip-summarize --dry-run
```

### Full pipeline (with LLM)

```bash
cp .env.example .env   # set OPENAI_API_KEY and LITELLM_BASE_URL
uv run get-news --topic ai
```

---

## What you get

```markdown
## AI News Digest

### New Frontiers in Foundation Models

**Google Releases Gemini 3.1 Pro with 1M Token Context Window**
Google has launched Gemini 3.1 Pro, a significant update focused on
enhancing capabilities for AI agents. The model boasts a 1 million
token context window and improved reasoning stability.
(Source: MarkTechPost, TechCrunch)

**Anthropic Launches Claude Sonnet 4.6 with Opus-Level Coding**
Anthropic released Claude Sonnet 4.6, its latest mainstream model,
which promises coding capabilities nearly on par with its top-tier
Opus model at the Sonnet price point. (Source: The New Stack)
```

Articles from the last 72 hours, grouped into thematic sections, with sources cited. Output lands in `daily-news/news-MM-DD-YY.md`.

## CLI reference

```
uv run get-news [OPTIONS]

Options:
  --topic TEXT        Required. ai, cricket, both, or any custom topic
  --output-dir PATH  Output directory (default: daily-news/)
  --skip-summarize   Bypass LLM, list raw articles
  --dry-run          Print to stdout, don't write a file
```

## Custom topics

Add a section to [`feeds.toml`](feeds.toml):

```toml
[topics.cybersecurity]
feeds = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://krebsonsecurity.com/feed/",
]
line_limits = [50, 100]   # min/max lines for the LLM summary
```

```bash
uv run get-news --topic cybersecurity
```

No code changes required. The topic is picked up automatically.

## Architecture

```
feeds.toml           CLI (click)          LLM (Gemini via LiteLLM)      Output
+-----------+      +------------+        +---------------------+      +----------------+
| RSS feeds | ---> | Async HTTP | -----> | Summarize by topic  | ---> | news-MM-DD-YY  |
| per topic |      | fetch +    |        | (OpenAI-compatible) |      | .md in         |
|           |      | retry      |        |                     |      | daily-news/    |
+-----------+      +------------+        +---------------------+      +----------------+
                   Filters to last                                    Or stdout
                   72h, max 25/feed                                   with --dry-run
```

Configuration is centralized in `config.py`. Feed URLs and topics live in `feeds.toml` (with hardcoded fallbacks). Custom exceptions in `exceptions.py`.

## Automation

**Daily digest:** GitHub Actions runs at 5 AM Central, generates both topics, opens a PR to `dev`, auto-merges when CI passes. Trigger manually from the Actions tab.

**CI:** Every PR runs lint (ruff), type check (mypy), dependency audit (pip-audit), and tests (pytest, 80% coverage minimum).

**Fork setup:** Add `OPENAI_API_KEY`, `LITELLM_BASE_URL`, and `PAT_TOKEN` as repository secrets.

## Development

| Command | What it does |
|---------|-------------|
| `make install` | `uv sync` |
| `make test` | `pytest -v` |
| `make test-cov` | Tests with 80% coverage gate |
| `make lint` | `ruff check` + format check |
| `make format` | Auto-fix with ruff |
| `make typecheck` | `mypy --strict` on `src/` |
| `make audit` | `pip-audit` vulnerability scan |

Single test: `uv run pytest tests/test_rss_fetcher.py::test_sanitize_strips_html -v`

## Security

Feeds are untrusted input. The tool defends at every boundary:

- **SSRF:** Rejects private IPs, localhost, `file://`, and other non-HTTP schemes before fetching
- **XSS:** Strips HTML tags via bleach; neutralizes `javascript:`, `data:`, `vbscript:` URIs (case-insensitive)
- **HTTPS only:** LiteLLM base URL must be HTTPS
- **Input truncation:** Titles (500 chars), summaries (1000), sources (100)
- **Pinned deps:** Exact versions, weekly Dependabot + `pip-audit` in CI
- **No secrets in repo:** `.env` gitignored, `.env.example` provided

## Stack

Python 3.12 | uv | click | httpx | feedparser | openai SDK | bleach | ruff | mypy | pytest

## License

[MIT](LICENSE)
