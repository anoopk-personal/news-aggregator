"""CLI interface for the news aggregator."""

import logging
import time
from pathlib import Path

import click
from dotenv import load_dotenv

from .config import (
    CONTENT_SEPARATOR,
    DEFAULT_METRICS_DIR,
    DEFAULT_OUTPUT_DIR,
    FEEDS,
    LLM_MODEL_DEFAULT,
    get_llm_config,
)
from .deduplicator import deduplicate_articles
from .exceptions import NewsAggregatorError, SummarizationError
from .markdown_generator import get_output_path, write_markdown
from .metrics import RunMetrics, TopicMetrics
from .rss_fetcher import Article, fetch_all_feeds
from .summarizer import summarize_articles

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALID_TOPICS = list(FEEDS.keys()) + ["all"]


def _format_articles_as_markdown(articles: list[Article], topic: str) -> str:
    """Format articles as markdown without LLM summarization."""
    lines = [f"# {topic.upper()} News\n"]
    for article in articles:
        lines.append(f"### {article.title}")
        lines.append(f"**Source:** {article.source}\n")
        if article.summary:
            lines.append(f"{article.summary}\n")
        lines.append(f"[Read more]({article.link})\n")
    return "\n".join(lines)


@click.command()
@click.option(
    "--topic",
    type=click.Choice(VALID_TOPICS, case_sensitive=False),
    required=True,
    help="News topic to fetch (use 'all' for all topics)",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUTPUT_DIR,
    help="Output directory for markdown files",
)
@click.option(
    "--skip-summarize",
    is_flag=True,
    default=False,
    help="Skip LLM summarization and output raw articles as markdown",
)
@click.option(
    "--skip-dedup",
    is_flag=True,
    default=False,
    help="Skip article deduplication",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview digest to stdout without writing a file",
)
def main(
    topic: str,
    output_dir: Path,
    skip_summarize: bool,
    skip_dedup: bool,
    dry_run: bool,
) -> None:
    """Fetch and summarize news for a given topic."""
    start_time = time.monotonic()
    topics = list(FEEDS.keys()) if topic == "all" else [topic]
    all_summaries = []
    all_topic_metrics: list[TopicMetrics] = []
    topic_errors = 0
    if not skip_summarize:
        try:
            _, _, model = get_llm_config()
        except Exception:
            model = LLM_MODEL_DEFAULT
    else:
        model = LLM_MODEL_DEFAULT

    for t in topics:
        click.echo(f"Fetching {t} news...")
        tm = TopicMetrics(topic=t)
        try:
            fetch_result = fetch_all_feeds(t)
            articles = fetch_result.articles
            tm.feeds_total = fetch_result.feeds_total
            tm.feeds_succeeded = fetch_result.feeds_succeeded
            tm.feeds_failed = fetch_result.feeds_failed
            tm.articles_fetched = len(articles)
            click.echo(f"Found {len(articles)} articles")

            if articles and not skip_dedup:
                before_count = len(articles)
                articles = deduplicate_articles(articles)
                removed = before_count - len(articles)
                if removed:
                    logger.info(
                        "Deduplicated %d articles to %d (%d duplicates removed)",
                        before_count,
                        len(articles),
                        removed,
                    )
            tm.articles_after_dedup = len(articles)

            if articles:
                if skip_summarize:
                    summary = _format_articles_as_markdown(articles, t)
                else:
                    click.echo("Summarizing...")
                    summarize_result = summarize_articles(articles, t)
                    summary = summarize_result.content
                    tm.prompt_tokens = summarize_result.prompt_tokens
                    tm.completion_tokens = summarize_result.completion_tokens
                    tm.total_tokens = summarize_result.total_tokens
                all_summaries.append(summary)
        except (NewsAggregatorError, SummarizationError) as e:
            logger.error("Error fetching %s: %s", t, e)
            tm.error = str(e)
            topic_errors += 1
        finally:
            all_topic_metrics.append(tm)

    duration = time.monotonic() - start_time

    if not dry_run:
        run_metrics = RunMetrics.create_now(
            duration_seconds=duration,
            model=model,
            skipped_summarize=skip_summarize,
            skipped_dedup=skip_dedup,
            topics=all_topic_metrics,
        )
        run_metrics.save(DEFAULT_METRICS_DIR)

    if not all_summaries:
        if topic_errors > 0:
            raise SystemExit(1)
        click.echo("No articles found.")
        return

    combined_content = CONTENT_SEPARATOR.join(all_summaries)

    if dry_run:
        click.echo(combined_content)
        return

    output_path = get_output_path(output_dir)
    write_markdown(combined_content, output_path)
    click.echo(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
