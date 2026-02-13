# News Aggregator - Copilot Instructions

## Repository Overview

Python CLI that fetches RSS feeds for AI and Cricket news, summarizes them using LLM, and outputs daily markdown files. Runs automatically via GitHub Actions.

- **Organization:** `anoopk-personal` (GitHub Teams)
- **Remote:** `https://github.com/anoopk-personal/news-aggregator.git`
- **Default branch:** `main`

## Tech Stack

- **Python 3.12** with `uv` for dependency management
- **LiteLLM** proxy using Gemini 2.5 Pro
- **OpenAI SDK** configured with custom `base_url` for LiteLLM compatibility
- **httpx** with async support for concurrent feed fetching
- **ruff** for linting and formatting
- **pytest** for testing

## Commands

```bash
uv sync                                    # Install dependencies
uv run get-news --topic ai                 # Generate AI news
uv run get-news --topic cricket            # Generate Cricket news
uv run pytest -v                           # Run tests
uv run ruff check . && uv run ruff format --check .  # Lint check
```

## Project Structure

```
news-aggregator/
├── src/
│   ├── cli.py              # Click CLI (get-news command)
│   ├── config.py           # All settings (feeds, limits, timeouts, LLM config)
│   ├── rss_fetcher.py      # Async RSS fetching with httpx
│   ├── summarizer.py       # LLM summarization with timeout
│   ├── markdown_generator.py
│   ├── utils.py            # Shared utilities (EMOJI_PATTERN)
│   └── exceptions.py       # Custom exceptions
├── tests/
├── daily-news/             # Generated output files
├── pyproject.toml
└── Makefile
```

## Architecture Notes

- **Async feed fetching**: `fetch_all_feeds()` uses `asyncio` + `httpx.AsyncClient` to fetch all RSS feeds concurrently. Sync `fetch_feed()` wrapper exists for testing.
- **Configuration centralized**: All constants in `config.py` - no magic numbers in code
- **Security**: URL validation, HTML sanitization, LLM timeout (180s), sanitized exception messages
- **Shared utilities**: `EMOJI_PATTERN` in `utils.py` to avoid duplication

## Output Rules

- Files named `news-MM-DD-YY.md`, duplicates get `(2)` suffix
- AI: 100-200 lines, Cricket: 20-50 lines
- No emojis in output
- Source attribution with article links for each summary

## Testing Guidelines

- Tests use dynamic dates (relative to `datetime.now()`) to avoid time-dependent failures
- Use `monkeypatch` for environment variables, not direct `os.environ` manipulation
- Mock at the httpx level for RSS fetcher tests

## Git Workflow

**Branch protection on `main`:**
- All changes require PRs (no direct push)
- Required status check: `lint-and-test`
- Required approvals: 0 (solo developer)

**Development process:**
```bash
git checkout main && git pull origin main
git checkout -b feature/name              # or fix/, docs/, test/, chore/
# make changes
git add <files> && git commit -m "feat: description"
git push -u origin feature/name
gh pr create --base main
# Auto-merge enables automatically, wait for CI
```

**Branch naming conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `test/` - Test changes
- `chore/` - Maintenance tasks
- `daily-news/` - Automated daily news (reserved for workflow)

**Auto-merge behavior:**
- PRs to `main` from feature branches automatically enable auto-merge
- Once CI (`lint-and-test`) passes, PR squash-merges automatically
- Feature branch is deleted automatically after merge (GitHub repo setting)

## GitHub Actions

All workflows are at `.github/workflows/`.

### CI (ci.yml)
- Triggers on PRs and pushes to `main`
- Runs: `ruff check`, `ruff format --check`, `pytest`
- Job name `lint-and-test` for branch protection

### Auto Merge (auto-merge.yml)
- Triggers on PR events (opened, synchronize, reopened) to `main`
- Excludes `daily-news/` branches (handled by their own workflow)
- Enables squash merge with `--delete-branch` flag
- Uses `PAT_TOKEN` for authentication

### Daily News (daily-news.yml)
- Schedule: 5 AM Central (11:00 UTC)
- Creates branch `daily-news/YYYY-MM-DD`
- Opens PR to `main` with auto-merge enabled
- Once CI passes, PR merges automatically and branch is deleted

## GitHub Secrets

| Secret | Purpose |
|--------|---------|
| `OPENAI_API_KEY` | LiteLLM API key for AI features |
| `LITELLM_BASE_URL` | LiteLLM proxy base URL |
| `PAT_TOKEN` | Fine-grained PAT for PR creation (org restriction workaround) |

### PAT_TOKEN Minimum Permissions (Fine-grained)
| Permission | Access |
|------------|--------|
| Contents | Read & Write |
| Pull requests | Read & Write |

## Repository Settings Required

- **Actions > Workflow permissions:** Read and write
- **Pull Requests > Allow auto-merge:** Enabled
- **Pull Requests > Automatically delete head branches:** Enabled ✅
- **Branch protection on `main`:** Require PRs, require `lint-and-test` status

## Troubleshooting

**"GitHub Actions is not permitted to create pull requests"**
- Org-level restriction. Use `PAT_TOKEN` secret instead of `github.token`

**"Repository rule violations" on push**
- Branch protection requires PRs. Create feature branch and PR instead.

**"Resource not accessible by personal access token"**
- Fine-grained PAT needs Contents + Pull requests read/write permissions

**CI fails**
```bash
uv run ruff check . --fix    # Auto-fix lint issues
uv run ruff format .         # Fix formatting
uv run pytest -v             # Debug test failures locally
```

**Branch already exists on daily news re-run:**
- Workflow handles this automatically (deletes existing branch before creating new one)
