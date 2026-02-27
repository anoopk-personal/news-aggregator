# News Aggregator

[![CI](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A CLI tool that turns RSS feeds into concise daily markdown digests — optionally summarized by an LLM. Ships with **AI** and **Cricket** topics; add your own in a TOML file.

## Quick start

```bash
git clone https://github.com/anoopk-personal/news-aggregator.git
cd news-aggregator
uv sync
uv run get-news --topic ai --skip-summarize --dry-run   # no API key needed
```

To enable LLM summarization:

```bash
cp .env.example .env   # set OPENAI_API_KEY and LITELLM_BASE_URL
uv run get-news --topic ai
```

Output lands in `daily-news/news-MM-DD-YY.md` (or stdout with `--dry-run`).

## CLI options

```
uv run get-news [OPTIONS]

  --topic TEXT        Required. ai, cricket, both, or any custom topic
  --output-dir PATH  Output directory (default: daily-news/)
  --skip-summarize   Bypass LLM, list raw articles
  --skip-dedup       Skip article deduplication
  --dry-run          Print to stdout, don't write a file
```

## Custom topics

Add a section to [`feeds.toml`](feeds.toml) — no code changes required:

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
| `make test-cov` | Tests with 80% coverage gate |
| `make lint` | Lint + format check (ruff) |
| `make format` | Auto-fix lint issues |
| `make typecheck` | Type check with mypy |
| `make audit` | Dependency vulnerability scan |
| `make install-hooks` | Install git pre-commit hook |

Run a single test: `uv run pytest tests/test_rss_fetcher.py::test_name -v`

## Automation

A GitHub Actions workflow runs daily at 5 AM Central and opens a PR with the generated digest. Dependabot keeps dependencies up to date with weekly PRs.

**Fork setup:** Add `OPENAI_API_KEY`, `LITELLM_BASE_URL`, and `PAT_TOKEN` as [repository secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions).

## Security

Feeds are untrusted input. Defenses include SSRF protection (private IP rejection), HTML sanitization, prompt injection mitigation (JSON serialization), HTTPS enforcement, and input truncation. See [SECURITY.md](SECURITY.md) for reporting guidelines.

## License

[MIT](LICENSE)
