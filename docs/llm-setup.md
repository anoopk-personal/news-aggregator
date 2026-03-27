# LLM Setup

The news aggregator works with any OpenAI-compatible LLM provider. Without an LLM configured, you can still fetch and list articles using `--skip-summarize` -- no API key needed.

To enable LLM-powered summaries:

```bash
cp .env.example .env
# Edit .env -- uncomment one provider block, fill in your values
```

## Local (Ollama -- free, runs on your machine)

1. [Install Ollama](https://ollama.com/download) (Mac, Linux, or Windows)
2. Pull a model: `ollama pull llama3`
3. In `.env`, uncomment the Ollama block:
   ```
   LLM_BASE_URL=http://localhost:11434/v1
   LLM_MODEL=llama3
   ```
4. Run: `uv run get-news --topic ai --dry-run`

No API key needed -- the tool detects Ollama automatically.

## Online (OpenAI, OpenRouter, LiteLLM, or any OpenAI-compatible API)

1. Get an API key from your provider
2. In `.env`, uncomment the matching block and paste your key:
   ```
   LLM_API_KEY=sk-your-key-here
   LLM_MODEL=gpt-4o
   ```
   For providers with a custom endpoint (OpenRouter, LiteLLM), also set `LLM_BASE_URL`.
3. Run: `uv run get-news --topic ai --dry-run`

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_API_KEY` | For remote providers | API key. Auto-set for local Ollama |
| `LLM_BASE_URL` | For non-OpenAI providers | Base URL for the API endpoint. HTTP allowed for localhost only |
| `LLM_MODEL` | No | Model name (default: `gemini-2.5-pro`). Provider-specific |

## CLI flags

| Flag | Effect |
|------|--------|
| `--topic` | Required. Any topic in `feeds.toml` (`ai`, `cricket`, `finance`), or `all` |
| `--output-dir` | Output directory (default: `daily-news/`) |
| `--skip-summarize` | Bypass the LLM, list raw articles |
| `--skip-dedup` | Skip article deduplication |
| `--dry-run` | Print to stdout, do not write files or metrics |

## Forking this repo?

Add these as [repository secrets](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions) for the daily GitHub Actions workflow:

- `LLM_API_KEY` -- your LLM provider key
- `LLM_BASE_URL` -- your provider endpoint
- `PAT_TOKEN` -- a GitHub personal access token (for creating PRs)
- `LLM_MODEL` (optional) -- override the default model
