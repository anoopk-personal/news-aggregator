# News Aggregator

[![CI](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml/badge.svg)](https://github.com/anoopk-personal/news-aggregator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)

Get a daily briefing on **AI**, **Cricket**, and **Finance** -- from 40+ sources, distilled into one readable page. Add your own topics in a TOML file. Optionally powered by any OpenAI-compatible LLM (Ollama, OpenAI, OpenRouter, etc.) for intelligent summaries.

**Sample output** (from a real daily run):

> ### New Models & Major Research
>
> **Google Previews Gemini 3.1 Flash Live for Real-Time Interaction**
> Google has released Gemini 3.1 Flash Live in a developer preview, describing it as its
> highest-quality audio and speech model for real-time, low-latency interactions. The model
> natively processes multimodal streams and supports tool use, providing a foundation for
> building more natural AI agents and voice interfaces. *(Source: [Google](https://blog.google/technology/developers/gemini-3-1-flash-live/), [MarkTechPost](https://www.marktechpost.com/gemini-3-1-flash-live-preview/))*

<!-- DASHBOARD:START -->

### Pipeline Health

Last run: **Apr 26** | 120 articles | 16/22 feeds | $0.1781 | 2m 27s

| Topic | Feeds | Articles | Cost |
|-------|:-----:|:--------:|:----:|
| Ai | 13/18 | 68 | $0.0906 |
| Cricket | 2/3 | 42 | $0.0508 |
| Finance | 1/1 | 10 | $0.0367 |

| Period | Runs | Articles | Feed Health | Cost |
|--------|:----:|:--------:|:-----------:|:----:|
| **7 days** | 7 | 857 | 70% | $1.1886 |
| **30 days** | 28 | 3,181 | 63% | $3.8704 |
| **All time** | 69 | 4,923 | 65% | $5.8003 |

> Model: `gemini-2.5-pro` | ~$0.0841/run

<!-- DASHBOARD:END -->

## Quick start

> Requires [Python 3.12+](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/anoopk-personal/news-aggregator.git
cd news-aggregator
uv sync
uv run get-news --topic ai --skip-summarize --dry-run   # no API key needed
```

Want LLM-powered summaries instead of raw article listings? See the [LLM setup guide](docs/llm-setup.md) -- works with Ollama (free, local) or any cloud provider.

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

**Stack:** Python 3.12, uv, ruff, mypy, pytest, httpx, Click

| Command | What it does |
|---------|-------------|
| `make install` | Install dependencies (`uv sync`) |
| `make test` | Run tests (`pytest`) |
| `make test-cov` | Tests with 80% coverage gate |
| `make lint` | Lint + format check (`ruff`) |
| `make typecheck` | Type check (`mypy`) |
| `make format` | Auto-fix lint issues |

Run a single test: `uv run pytest tests/test_rss_fetcher.py::test_name -v`

## Contributing

Contributions are welcome! Please ensure all tests pass (`make test-cov` requires 80%+ coverage) and code is formatted (`make format`) before submitting a PR.

## Automation

A GitHub Actions workflow runs daily at 11:00 UTC and opens a PR with the generated digest. Each run captures pipeline metrics (article counts, feed health, token usage, cost) and updates the dashboard above. Dependabot keeps dependencies current with weekly PRs.

**Forking?** See the [LLM setup guide](docs/llm-setup.md#forking-this-repo) for required repository secrets.

## Security

Feeds are untrusted input. Defenses include SSRF protection (private IP rejection), HTML sanitization, prompt injection mitigation (JSON serialization), HTTPS enforcement, and input truncation. See [SECURITY.md](SECURITY.md) for reporting guidelines.

## License

[MIT](LICENSE)
