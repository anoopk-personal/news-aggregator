"""CLI interface for the news aggregator."""

import logging
from pathlib import Path

import click
from dotenv import load_dotenv

from .config import CONTENT_SEPARATOR, DEFAULT_OUTPUT_DIR, FEEDS
from .markdown_generator import get_output_path, write_markdown
from .rss_fetcher import fetch_all_feeds
from .summarizer import summarize_articles

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

VALID_TOPICS = list(FEEDS.keys()) + ["both"]


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
def main(topic: str, output_dir: Path) -> None:
    """Fetch and summarize news for a given topic."""
    topics = list(FEEDS.keys()) if topic == "both" else [topic]
    all_summaries = []

    for t in topics:
        click.echo(f"Fetching {t} news...")
        try:
            articles = fetch_all_feeds(t)
            click.echo(f"Found {len(articles)} articles")

            if articles:
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
