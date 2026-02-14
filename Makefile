.PHONY: install test lint format run clean

install:
	uv sync

test:
	uv run pytest -v

test-cov:
	uv run pytest --cov=src --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check . --fix
	uv run ruff format .

run-ai:
	uv run get-news --topic ai --skip-summarize

run-cricket:
	uv run get-news --topic cricket --skip-summarize

run-both:
	uv run get-news --topic both --skip-summarize

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
