# News Aggregator

[![CI](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A CLI tool that turns RSS feeds into concise daily markdown digests -- optionally summarized by an LLM. Ships with **AI**, **Cricket**, and **Finance** topics; add your own in a TOML file.

<!-- DASHBOARD:START -->

### Pipeline Health

| | Runs | Articles | Feeds | Tokens | Cost | Avg time |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **7 days** | 8 | 406 | 66% | 28k | $0.14 | 2.3m |
| **30 days** | 31 | 1,362 | 67% | 28k | $0.14 | 2.2m |

> Updated 2026-03-26 | Cost: $1.25/1M in + $10.0/1M out (`gemini-2.5-pro`)

<!-- DASHBOARD:END -->

## Quick start

> Requires [Python 3.12+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/anoopk-personal/news-aggregator.git
cd news-aggregator
uv sync
uv run get-news --topic ai --skip-summarize --dry-run   # no API key needed
```

## LLM setup

To enable LLM-powered summaries, copy `.env.example` to `.env` and uncomment the block for your provider:

```bash
cp .env.example .env
# Edit .env -- uncomment one provider block, fill in your values
```

**Local (Ollama -- free, runs on your machine):**

1. [Install Ollama](https://ollama.com/download) (Mac, Linux, or Windows)
2. Pull a model: `ollama pull llama3`
3. In `.env`, uncomment the Ollama block:
   ```
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_MODEL=llama3
   ```
4. Run: `uv run get-news --topic ai --dry-run`

**Online (OpenAI, OpenRouter, LiteLLM, or any OpenAI-compatible API):**

1. Get an API key from your provider
2. In `.env`, uncomment the matching block and paste your key:
   ```
   LLM_API_KEY=sk-your-key-here
   LLM_MODEL=gpt-4o
   ```
   For providers with a custom endpoint (OpenRouter, LiteLLM), also set `LLM_BASE_URL`.
3. Run: `uv run get-news --topic ai --dry-run`

**CLI flags:**

- `--topic` -- required; any topic defined in `feeds.toml` (`ai`, `cricket`, `finance`), or `all` for all topics
- `--output-dir` -- output directory (default: `daily-news/`)
- `--skip-summarize` -- bypass the LLM, list raw articles
- `--skip-dedup` -- skip article deduplication
- `--dry-run` -- print to stdout, do not write files or metrics

## Custom topics

Add a section to [`feeds.toml`](feeds.toml) -- no code changes required:

```toml
[topics.cybersecurity]
feeds = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://krebsonsecurity.com/feed/",
]
line_limits = [50, 100]   # min/max lines for the LLM summary
```

## Development

| Command | What it does |
|---------|-------------|
| `make install` | Install dependencies (`uv sync`) |
| `make test` | Run tests |
| `make lint` | Lint + format check (ruff) |
| `make format` | Auto-fix lint issues |

Other targets: `make test-cov` (80% coverage gate), `make typecheck`, `make audit`, `make install-hooks`, `make dashboard`.

Run a single test: `uv run pytest tests/test_rss_fetcher.py::test_name -v`

## Automation

A GitHub Actions workflow runs daily at 11:00 UTC and opens a PR with the generated digest. Each run captures pipeline metrics (article counts, feed health, token usage, duration) to `metrics/` and updates the Pipeline Health dashboard at the top of this README. Dependabot keeps dependencies current with weekly PRs.

**Forking?** Add `LLM_API_KEY`, `LLM_BASE_URL`, and `PAT_TOKEN` as [repository secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions). Optionally set `LLM_MODEL` if you use a different model than the default (`gemini-2.5-pro`).

## Security

Feeds are untrusted input. Defenses include SSRF protection (private IP rejection), HTML sanitization, prompt injection mitigation (JSON serialization), HTTPS enforcement, and input truncation. See [SECURITY.md](SECURITY.md) for reporting guidelines.

## License

[MIT](LICENSE)
