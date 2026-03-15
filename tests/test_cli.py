"""Tests for the CLI."""

from datetime import UTC, datetime
from unittest.mock import patch

from click.testing import CliRunner

from src.cli import main
from src.exceptions import NewsAggregatorError
from src.rss_fetcher import Article


def _make_articles(count: int = 1) -> list[Article]:
    """Build a list of test articles."""
    return [
        Article(
            title=f"Article {i}",
            link=f"https://example.com/{i}",
            summary=f"Summary {i}",
            source="Example",
            published=datetime.now(tz=UTC),
        )
        for i in range(count)
    ]


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_full_pipeline(
    mock_write_markdown,
    mock_summarize_articles,
    mock_deduplicate,
    mock_fetch_all_feeds,
):
    """Full pipeline: fetch -> dedup -> summarize -> write."""
    articles = _make_articles(2)
    mock_fetch_all_feeds.return_value = articles
    mock_deduplicate.return_value = articles
    mock_summarize_articles.return_value = "Test summary"

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai"])

    assert result.exit_code == 0
    assert "Fetching ai news..." in result.output
    assert "Found 2 articles" in result.output
    assert "Saved to" in result.output
    mock_deduplicate.assert_called_once()
    mock_summarize_articles.assert_called_once()
    mock_write_markdown.assert_called_once()


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.write_markdown")
def test_cli_no_articles(mock_write_markdown, mock_fetch_all_feeds):
    """No articles found produces 'No articles found.' and no file write."""
    mock_fetch_all_feeds.return_value = []

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai"])

    assert result.exit_code == 0
    assert "No articles found." in result.output
    mock_write_markdown.assert_not_called()


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_skip_summarize_formats_articles_as_markdown(
    mock_write_markdown, mock_summarize_articles, mock_deduplicate, mock_fetch_all_feeds
):
    """--skip-summarize bypasses LLM and produces plain markdown listing."""
    articles = _make_articles(1)
    mock_fetch_all_feeds.return_value = articles
    mock_deduplicate.return_value = articles

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-summarize"])

    assert result.exit_code == 0
    assert "Summarizing..." not in result.output

    mock_summarize_articles.assert_not_called()
    written_content = mock_write_markdown.call_args[0][0]
    assert "# AI News" in written_content
    assert "### Article 0" in written_content
    assert "[Read more](https://example.com/0)" in written_content


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.write_markdown")
def test_cli_dry_run_prints_to_stdout_without_writing(
    mock_write_markdown, mock_deduplicate, mock_fetch_all_feeds
):
    """--dry-run prints digest to stdout and does not write a file."""
    articles = _make_articles(1)
    mock_fetch_all_feeds.return_value = articles
    mock_deduplicate.return_value = articles

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-summarize", "--dry-run"])

    assert result.exit_code == 0
    assert "# AI News" in result.output
    assert "Saved to" not in result.output
    mock_write_markdown.assert_not_called()


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_skip_dedup_bypasses_deduplication(
    mock_write_markdown, mock_summarize_articles, mock_deduplicate, mock_fetch_all_feeds
):
    """--skip-dedup bypasses deduplication entirely."""
    articles = _make_articles(1)
    mock_fetch_all_feeds.return_value = articles
    mock_summarize_articles.return_value = "Test summary"

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-dedup"])

    assert result.exit_code == 0
    mock_deduplicate.assert_not_called()
    mock_summarize_articles.assert_called_once()


@patch("src.cli.FEEDS", {"ai": ["https://a.com/f"], "cricket": ["https://b.com/f"]})
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_continues_after_topic_error(
    mock_write_markdown, mock_summarize_articles, mock_deduplicate, mock_fetch_all_feeds
):
    """A failing topic should not crash the run; remaining topics still produce output."""
    cricket_articles = _make_articles(1)
    mock_fetch_all_feeds.side_effect = [
        NewsAggregatorError("AI feeds unavailable"),
        cricket_articles,
    ]
    mock_deduplicate.return_value = cricket_articles
    mock_summarize_articles.return_value = "Cricket digest"

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "both"])

    assert result.exit_code == 0
    assert "Saved to" in result.output
    mock_write_markdown.assert_called_once()
