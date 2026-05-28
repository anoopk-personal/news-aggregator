"""Generate a pipeline health dashboard for README.md."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .config import DEFAULT_METRICS_FILE
from .logging_config import configure_logging
from .metrics import RunMetrics

logger = logging.getLogger(__name__)

DASHBOARD_START = "<!-- DASHBOARD:START -->"
DASHBOARD_END = "<!-- DASHBOARD:END -->"
README_PATH = Path(__file__).parent.parent / "README.md"


@dataclass
class PeriodSummary:
    """Aggregated metrics for a time period."""

    label: str
    runs: int
    articles_fetched: int
    feeds_total: int
    feeds_succeeded: int
    total_cost: float

    @property
    def feed_success_rate(self) -> float:
        if self.feeds_total == 0:
            return 0.0
        return self.feeds_succeeded / self.feeds_total * 100


def load_metrics(metrics_file: Path = DEFAULT_METRICS_FILE) -> list[RunMetrics]:
    """Load all runs from the JSONL metrics file."""
    return RunMetrics.load_all_jsonl(metrics_file)


def _build_summary(label: str, runs: list[RunMetrics]) -> PeriodSummary:
    """Build a PeriodSummary from a list of RunMetrics."""
    return PeriodSummary(
        label=label,
        runs=len(runs),
        articles_fetched=sum(m.total_articles_fetched for m in runs),
        feeds_total=sum(m.total_feeds for m in runs),
        feeds_succeeded=sum(m.successful_feeds for m in runs),
        total_cost=sum(m.total_cost for m in runs),
    )


def compute_summary(
    metrics: list[RunMetrics],
    days: int,
    label: str,
    today: date | None = None,
) -> PeriodSummary:
    """Aggregate metrics for the last N days."""
    reference = today or datetime.now(UTC).date()
    cutoff = reference - timedelta(days=max(days - 1, 0))

    filtered = [m for m in metrics if m.run_date >= cutoff.isoformat()]
    return _build_summary(label, filtered)


def _format_number(value: int) -> str:
    """Format a number with comma separators."""
    return f"{value:,}"


def _format_cost(cost: float) -> str:
    """Format cost as USD, rounded to 4 decimal places, trailing zeros trimmed."""
    if cost == 0:
        return "$0.00"
    integer_part, decimal_part = f"{cost:.4f}".split(".")
    decimal_part = decimal_part.rstrip("0").ljust(2, "0")
    return f"${integer_part}.{decimal_part}"


def _format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration (e.g. '2m 40s')."""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes == 0:
        return f"{secs}s"
    return f"{minutes}m {secs}s"


def render_dashboard(
    metrics: list[RunMetrics],
    today: date | None = None,
) -> str:
    """Render the dashboard markdown with hero line, per-topic table, and periods table."""
    # --- Hero line (most recent run) ---
    model = "unknown"
    hero_line = "Last run: **--** | 0 articles | 0/0 feeds | $0.00 | 0s"
    topic_rows: list[str] = []

    if metrics:
        most_recent = max(metrics, key=lambda m: m.run_date)
        model = most_recent.model

        run_date = date.fromisoformat(most_recent.run_date)
        date_str = run_date.strftime("%b %-d")
        hero_line = (
            f"Last run: **{date_str}**"
            f" | {_format_number(most_recent.total_articles_fetched)} articles"
            f" | {most_recent.successful_feeds}/{most_recent.total_feeds} feeds"
            f" | {_format_cost(most_recent.total_cost)}"
            f" | {_format_duration(most_recent.duration_seconds)}"
        )

        # Per-topic table rows
        for topic in most_recent.topics:
            topic_rows.append(
                f"| {topic.topic.title()} "
                f"| {topic.feeds_succeeded}/{topic.feeds_total} "
                f"| {_format_number(topic.articles_fetched)} "
                f"| {_format_cost(topic.cost)} |"
            )

    # --- Historical periods table ---
    summary_7 = compute_summary(metrics, days=7, label="7 days", today=today)
    summary_30 = compute_summary(metrics, days=30, label="30 days", today=today)
    summary_all = _build_summary("All time", metrics)

    period_rows = []
    for summary in [summary_7, summary_30, summary_all]:
        period_rows.append(
            f"| **{summary.label}** "
            f"| {summary.runs} "
            f"| {_format_number(summary.articles_fetched)} "
            f"| {summary.feed_success_rate:.0f}% "
            f"| {_format_cost(summary.total_cost)} |"
        )

    # --- Footer ---
    avg_cost = summary_all.total_cost / summary_all.runs if summary_all.runs else 0
    footer = f"> Model: `{model}` | ~{_format_cost(avg_cost)}/run"

    # --- Assemble ---
    sections = [
        DASHBOARD_START,
        "",
        "### Pipeline Health",
        "",
        hero_line,
        "",
    ]

    if topic_rows:
        sections.extend(
            [
                "| Topic | Feeds | Articles | Cost |",
                "|-------|:-----:|:--------:|:----:|",
                *topic_rows,
                "",
            ]
        )

    sections.extend(
        [
            "| Period | Runs | Articles | Feed Health | Cost |",
            "|--------|:----:|:--------:|:-----------:|:----:|",
            *period_rows,
            "",
            footer,
            "",
            DASHBOARD_END,
        ]
    )

    return "\n".join(sections)


def update_readme(
    dashboard_markdown: str,
    readme_path: Path = README_PATH,
) -> None:
    """Inject dashboard markdown into README.md between markers."""
    if not readme_path.exists():
        logger.error("README.md not found at %s", readme_path)
        return

    content = readme_path.read_text(encoding="utf-8")

    start_idx = content.find(DASHBOARD_START)
    end_idx = content.find(DASHBOARD_END)

    if start_idx != -1 and end_idx != -1:
        end_idx += len(DASHBOARD_END)
        new_content = content[:start_idx] + dashboard_markdown + content[end_idx:]
    else:
        license_idx = content.find("## License")
        if license_idx != -1:
            new_content = (
                content[:license_idx] + dashboard_markdown + "\n\n" + content[license_idx:]
            )
        else:
            new_content = content + "\n\n" + dashboard_markdown + "\n"

    readme_path.write_text(new_content, encoding="utf-8")
    logger.info("Updated dashboard in %s", readme_path)


def main() -> None:
    """Load metrics and update README dashboard."""
    configure_logging()
    metrics = load_metrics()
    if not metrics:
        logger.info("No metrics found in %s, skipping dashboard update", DEFAULT_METRICS_FILE)
        return
    dashboard = render_dashboard(metrics)
    update_readme(dashboard)


if __name__ == "__main__":
    main()
