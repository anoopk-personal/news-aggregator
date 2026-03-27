"""Tests for the CLI."""

from datetime import UTC, datetime
from unittest.mock import patch

from click.testing import CliRunner

from src.cli import main
from src.exceptions import NewsAggregatorError
from src.metrics import TopicMetrics
from src.rss_fetcher import Article, FetchResult
from src.summarizer import SummarizeResult


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


def _make_fetch_result(articles: list[Article]) -> FetchResult:
    """Wrap articles in a FetchResult."""
    return FetchResult(
        articles=articles,
        feeds_total=3,
        feeds_succeeded=2 if articles else 0,
        feeds_failed=1 if articles else 3,
    )


def _make_summarize_result(content: str = "Test summary") -> SummarizeResult:
    """Build a SummarizeResult with default token counts."""
    return SummarizeResult(
        content=content,
        prompt_tokens=500,
        completion_tokens=200,
        total_tokens=700,
    )


@patch("src.cli.RunMetrics.save")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_full_pipeline(
    mock_write_markdown,
    mock_summarize_articles,
    mock_deduplicate,
    mock_fetch_all_feeds,
    mock_save_metrics,
):
    """Full pipeline: fetch -> dedup -> summarize -> write."""
    articles = _make_articles(2)
    mock_fetch_all_feeds.return_value = _make_fetch_result(articles)
    mock_deduplicate.return_value = articles
    mock_summarize_articles.return_value = _make_summarize_result()

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai"])

    assert result.exit_code == 0
    assert "Fetching ai news..." in result.output
    assert "Found 2 articles" in result.output
    assert "Saved to" in result.output
    mock_deduplicate.assert_called_once()
    mock_summarize_articles.assert_called_once()
    mock_write_markdown.assert_called_once()
    mock_save_metrics.assert_called_once()


@patch("src.cli.RunMetrics.save")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.write_markdown")
def test_cli_no_articles(mock_write_markdown, mock_fetch_all_feeds, mock_save_metrics):
    """No articles found produces 'No articles found.' and no file write."""
    mock_fetch_all_feeds.return_value = _make_fetch_result([])

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai"])

    assert result.exit_code == 0
    assert "No articles found." in result.output
    mock_write_markdown.assert_not_called()


@patch("src.cli.RunMetrics.save")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_skip_summarize_formats_articles_as_markdown(
    mock_write_markdown,
    mock_summarize_articles,
    mock_deduplicate,
    mock_fetch_all_feeds,
    mock_save_metrics,
):
    """--skip-summarize bypasses LLM and produces plain markdown listing."""
    articles = _make_articles(1)
    mock_fetch_all_feeds.return_value = _make_fetch_result(articles)
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
    """--dry-run prints digest to stdout and does not write a file or metrics."""
    articles = _make_articles(1)
    mock_fetch_all_feeds.return_value = _make_fetch_result(articles)
    mock_deduplicate.return_value = articles

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-summarize", "--dry-run"])

    assert result.exit_code == 0
    assert "# AI News" in result.output
    assert "Saved to" not in result.output
    mock_write_markdown.assert_not_called()


@patch("src.cli.RunMetrics.save")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_skip_dedup_bypasses_deduplication(
    mock_write_markdown,
    mock_summarize_articles,
    mock_deduplicate,
    mock_fetch_all_feeds,
    mock_save_metrics,
):
    """--skip-dedup bypasses deduplication entirely."""
    articles = _make_articles(1)
    mock_fetch_all_feeds.return_value = _make_fetch_result(articles)
    mock_summarize_articles.return_value = _make_summarize_result()

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-dedup"])

    assert result.exit_code == 0
    mock_deduplicate.assert_not_called()
    mock_summarize_articles.assert_called_once()


@patch("src.cli.FEEDS", {"ai": ["https://a.com/f"], "cricket": ["https://b.com/f"]})
@patch("src.cli.RunMetrics.save")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.deduplicate_articles")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_continues_after_topic_error(
    mock_write_markdown,
    mock_summarize_articles,
    mock_deduplicate,
    mock_fetch_all_feeds,
    mock_save_metrics,
):
    """A failing topic should not crash the run; remaining topics still produce output."""
    cricket_articles = _make_articles(1)
    mock_fetch_all_feeds.side_effect = [
        NewsAggregatorError("AI feeds unavailable"),
        _make_fetch_result(cricket_articles),
    ]
    mock_deduplicate.return_value = cricket_articles
    mock_summarize_articles.return_value = _make_summarize_result("Cricket digest")

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "all"])

    assert result.exit_code == 0
    assert "Saved to" in result.output
    mock_write_markdown.assert_called_once()


@patch("src.cli.RunMetrics.save")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.write_markdown")
def test_cli_exits_nonzero_when_all_topics_fail(
    mock_write_markdown,
    mock_fetch_all_feeds,
    mock_save_metrics,
):
    """Exit code 1 when all topics fail with errors (not just empty feeds)."""
    mock_fetch_all_feeds.side_effect = NewsAggregatorError("feeds unavailable")

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai"])

    assert result.exit_code == 1
    mock_write_markdown.assert_not_called()


@patch("src.cli.RunMetrics.save")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_collects_topic_metrics(
    mock_write_markdown,
    mock_summarize_articles,
    mock_fetch_all_feeds,
    mock_save_metrics,
):
    """Verify that topic metrics are collected and passed to RunMetrics.save."""
    articles = _make_articles(3)
    mock_fetch_all_feeds.return_value = FetchResult(
        articles=articles,
        feeds_total=5,
        feeds_succeeded=4,
        feeds_failed=1,
    )
    mock_summarize_articles.return_value = SummarizeResult(
        content="Summary",
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-dedup"])

    assert result.exit_code == 0
    mock_save_metrics.assert_called_once()


@patch("src.cli.RunMetrics.create_now")
@patch("src.cli.fetch_all_feeds")
@patch("src.cli.summarize_articles")
@patch("src.cli.write_markdown")
def test_cli_computes_per_topic_cost(
    mock_write_markdown,
    mock_summarize_articles,
    mock_fetch_all_feeds,
    mock_create_now,
):
    """Verify that per-topic cost is computed from token counts and model."""
    articles = _make_articles(1)
    mock_fetch_all_feeds.return_value = FetchResult(
        articles=articles,
        feeds_total=3,
        feeds_succeeded=2,
        feeds_failed=1,
    )
    mock_summarize_articles.return_value = SummarizeResult(
        content="Summary",
        prompt_tokens=10000,
        completion_tokens=5000,
        total_tokens=15000,
    )
    mock_run = mock_create_now.return_value
    mock_run.save.return_value = None

    runner = CliRunner()
    result = runner.invoke(main, ["--topic", "ai", "--skip-dedup"])

    assert result.exit_code == 0
    mock_create_now.assert_called_once()
    topics_arg = mock_create_now.call_args[1]["topics"]
    assert len(topics_arg) == 1
    topic: TopicMetrics = topics_arg[0]
    assert topic.prompt_tokens == 10000
    assert topic.completion_tokens == 5000
    assert topic.cost > 0
