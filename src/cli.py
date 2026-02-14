"""CLI interface for the news aggregator."""

import logging
from pathlib import Path

import click
from dotenv import load_dotenv

from .config import CONTENT_SEPARATOR, DEFAULT_OUTPUT_DIR, FEEDS
from .markdown_generator import get_output_path, write_markdown
from .rss_fetcher import Article, fetch_all_feeds
from .summarizer import summarize_articles

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALID_TOPICS = list(FEEDS.keys()) + ["both"]


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
    help="News topic to fetch (use 'both' for all topics)",
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
def main(topic: str, output_dir: Path, skip_summarize: bool) -> None:
    """Fetch and summarize news for a given topic."""
    topics = list(FEEDS.keys()) if topic == "both" else [topic]
    all_summaries = []

    for t in topics:
        click.echo(f"Fetching {t} news...")
        try:
            articles = fetch_all_feeds(t)
            click.echo(f"Found {len(articles)} articles")

            if articles:
                if skip_summarize:
                    summary = _format_articles_as_markdown(articles, t)
                else:
                    click.echo("Summarizing...")
                    summary = summarize_articles(articles, t)
                all_summaries.append(summary)
        except Exception as e:
            logger.error("Error fetching %s: %s", t, e)
            continue

    if not all_summaries:
        click.echo("No articles found.")
        return

    combined_content = CONTENT_SEPARATOR.join(all_summaries)
    output_path = get_output_path(output_dir)
    write_markdown(combined_content, output_path)
    click.echo(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
