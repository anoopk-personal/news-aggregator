"""Tests for the CLI."""

from unittest.mock import patch

from click.testing import CliRunner

from src.cli import main


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
