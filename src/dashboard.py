"""Generate a pipeline health dashboard for README.md."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .config import (
    DEFAULT_COST_PER_MILLION_TOKENS,
    DEFAULT_METRICS_DIR,
    MODEL_COST_PER_MILLION_TOKENS,
)
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
    articles_after_dedup: int
    feeds_total: int
    feeds_succeeded: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost: float
    total_duration_seconds: float

    @property
    def feed_success_rate(self) -> float:
        if self.feeds_total == 0:
            return 0.0
        return self.feeds_succeeded / self.feeds_total * 100

    @property
    def avg_duration_seconds(self) -> float:
        if self.runs == 0:
            return 0.0
        return self.total_duration_seconds / self.runs


def load_metrics(metrics_dir: Path = DEFAULT_METRICS_DIR) -> list[RunMetrics]:
    """Load all metrics JSON files from the directory."""
    if not metrics_dir.exists():
        return []

    metrics = []
    for filepath in sorted(metrics_dir.glob("*.json")):
        try:
            text = filepath.read_text(encoding="utf-8")
            metrics.append(RunMetrics.from_json(text))
        except (ValueError, KeyError, TypeError) as e:
            logger.warning("Skipping malformed metrics file %s: %s", filepath.name, e)
    return metrics


def _build_summary(label: str, runs: list[RunMetrics]) -> PeriodSummary:
    """Build a PeriodSummary from a list of RunMetrics."""
    return PeriodSummary(
        label=label,
        runs=len(runs),
        articles_fetched=sum(m.total_articles_fetched for m in runs),
        articles_after_dedup=sum(m.total_articles_after_dedup for m in runs),
        feeds_total=sum(m.total_feeds for m in runs),
        feeds_succeeded=sum(m.successful_feeds for m in runs),
        prompt_tokens=sum(m.total_prompt_tokens for m in runs),
        completion_tokens=sum(m.total_completion_tokens for m in runs),
        total_tokens=sum(m.total_tokens for m in runs),
        total_cost=sum(m.total_cost for m in runs),
        total_duration_seconds=sum(m.duration_seconds for m in runs),
    )


def compute_summary(
    metrics: list[RunMetrics],
    days: int,
    label: str,
    today: date | None = None,
) -> PeriodSummary:
    """Aggregate metrics for the last N days."""
    reference = today or date.today()
    cutoff = reference - timedelta(days=days)

    filtered = [m for m in metrics if m.run_date >= cutoff.isoformat()]
    return _build_summary(label, filtered)


def _format_number(value: int) -> str:
    """Format a number with comma separators."""
    return f"{value:,}"


def _format_tokens(total_tokens: int) -> str:
    """Format token count in thousands."""
    if total_tokens == 0:
        return "0"
    return f"{total_tokens / 1000:,.0f}k"


def _format_duration(seconds: float) -> str:
    """Format duration as a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    return f"{minutes:.1f}m"


def _format_cost(cost: float) -> str:
    """Format cost as a dollar amount with actual precision (no rounding)."""
    if cost == 0:
        return "$0.00"
    integer_part, decimal_part = f"{cost:.4f}".split(".")
    decimal_part = decimal_part.rstrip("0").ljust(2, "0")
    return f"${integer_part}.{decimal_part}"


def render_dashboard(
    metrics: list[RunMetrics],
    today: date | None = None,
) -> str:
    """Render the dashboard markdown table."""
    summary_7 = compute_summary(metrics, days=7, label="7 days", today=today)
    summary_30 = compute_summary(metrics, days=30, label="30 days", today=today)
    summary_all = _build_summary("All time", metrics)

    # Determine model for cost footnote from most recent run.
    model = "unknown"
    if metrics:
        most_recent = max(metrics, key=lambda m: m.run_date)
        model = most_recent.model

    rows = []
    for summary in [summary_7, summary_30, summary_all]:
        rows.append(
            f"| **{summary.label}** | {summary.runs} "
            f"| {_format_number(summary.articles_fetched)} "
            f"| {summary.feed_success_rate:.0f}% "
            f"| {_format_tokens(summary.total_tokens)} "
            f"| {_format_cost(summary.total_cost)} "
            f"| {_format_duration(summary.avg_duration_seconds)} |"
        )

    input_rate, output_rate = MODEL_COST_PER_MILLION_TOKENS.get(
        model, DEFAULT_COST_PER_MILLION_TOKENS
    )
    reference = today or date.today()

    table = "\n".join(
        [
            DASHBOARD_START,
            "",
            "### Pipeline Health",
            "",
            "| | Runs | Articles | Feeds | Tokens | Cost | Avg time |",
            "|---|:---:|:---:|:---:|:---:|:---:|:---:|",
            *rows,
            "",
            f"> Updated {reference.isoformat()}"
            f" | Cost: ${input_rate}/1M in + ${output_rate}/1M out"
            f" (`{model}`)",
            "",
            DASHBOARD_END,
        ]
    )
    return table


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
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    metrics = load_metrics()
    if not metrics:
        logger.info("No metrics found in %s, skipping dashboard update", DEFAULT_METRICS_DIR)
        return
    dashboard = render_dashboard(metrics)
    update_readme(dashboard)


if __name__ == "__main__":
    main()
