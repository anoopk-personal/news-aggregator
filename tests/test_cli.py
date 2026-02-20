"""Tests for the CLI."""

from datetime import UTC, datetime
from unittest.mock import patch

from click.testing import CliRunner

from src.cli import main
from src.rss_fetcher import Article


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_end_to_end(mock_write_markdown, mock_summarize_articles, mock_fetch_all_feeds):
    """Test the CLI end-to-end with mocks."""
    mock_fetch_all_feeds.return_value = ["article1", "article2"]
    mock_summarize_articles.return_value = "Test summary"

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai"])

    assert result.exit_code == 0
    assert "Fetching ai news..." in result.output
    assert "Found 2 articles" in result.output
    assert "Summarizing..." in result.output
    assert "Saved to" in result.output

    mock_fetch_all_feeds.assert_called_once_with("ai")
    mock_summarize_articles.assert_called_once_with(["article1", "article2"], "ai")
    mock_write_markdown.assert_called_once()


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_no_articles(mock_write_markdown, mock_summarize_articles, mock_fetch_all_feeds):
    """Test the CLI when no articles are found."""
    mock_fetch_all_feeds.return_value = []

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai"])

    assert result.exit_code == 0
    assert "No articles found." in result.output

    mock_summarize_articles.assert_not_called()
    mock_write_markdown.assert_not_called()


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_skip_summarize(mock_write_markdown, mock_summarize_articles, mock_fetch_all_feeds):
    """Test --skip-summarize skips LLM and formats articles as markdown."""
    articles = [
        Article(
            title="Test Article",
            link="https://example.com/1",
            summary="A test summary",
            source="Example",
            published=datetime.now(tz=UTC),
        ),
    ]
    mock_fetch_all_feeds.return_value = articles

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-summarize"])

    assert result.exit_code == 0
    assert "Fetching ai news..." in result.output
    assert "Found 1 articles" in result.output
    assert "Summarizing..." not in result.output
    assert "Saved to" in result.output

    mock_summarize_articles.assert_not_called()
    mock_write_markdown.assert_called_once()
    written_content = mock_write_markdown.call_args[0][0]
    assert "# AI News" in written_content
    assert "### Test Article" in written_content
    assert "**Source:** Example" in written_content
    assert "A test summary" in written_content
    assert "[Read more](https://example.com/1)" in written_content


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_skip_summarize_no_articles(
    mock_write_markdown, mock_summarize_articles, mock_fetch_all_feeds
):
    """Test --skip-summarize with no articles still shows 'No articles found.'."""
    mock_fetch_all_feeds.return_value = []

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-summarize"])

    assert result.exit_code == 0
    assert "No articles found." in result.output

    mock_summarize_articles.assert_not_called()
    mock_write_markdown.assert_not_called()


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_skip_summarize_no_summary_field(
    mock_write_markdown, mock_summarize_articles, mock_fetch_all_feeds
):
    """Test --skip-summarize handles articles with empty summary."""
    articles = [
        Article(
            title="No Summary Article",
            link="https://example.com/2",
            summary="",
            source="Example",
        ),
    ]
    mock_fetch_all_feeds.return_value = articles

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "cricket", "--skip-summarize"])

    assert result.exit_code == 0
    mock_write_markdown.assert_called_once()
    written_content = mock_write_markdown.call_args[0][0]
    assert "# CRICKET News" in written_content
    assert "### No Summary Article" in written_content
    # Empty summary should not appear as a blank paragraph
    assert "**Source:** Example" in written_content
    assert "[Read more](https://example.com/2)" in written_content


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_dry_run_prints_to_stdout(
    mock_write_markdown, mock_summarize_articles, mock_fetch_all_feeds
):
    """Test --dry-run prints digest to stdout and does not write a file."""
    articles = [
        Article(
            title="Dry Run Article",
            link="https://example.com/dry",
            summary="Dry run summary",
            source="Example",
            published=datetime.now(tz=UTC),
        ),
    ]
    mock_fetch_all_feeds.return_value = articles

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-summarize", "--dry-run"])

    assert result.exit_code == 0
    assert "# AI News" in result.output
    assert "### Dry Run Article" in result.output
    assert "Saved to" not in result.output
    mock_write_markdown.assert_not_called()


@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_dry_run_no_articles(
    mock_write_markdown, mock_summarize_articles, mock_fetch_all_feeds
):
    """Test --dry-run with no articles shows 'No articles found.'."""
    mock_fetch_all_feeds.return_value = []

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-summarize", "--dry-run"])

    assert result.exit_code == 0
    assert "No articles found." in result.output
    mock_write_markdown.assert_not_called()
