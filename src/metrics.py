"""Run metrics collection and persistence."""

import json
import logging
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path

from .config import DEFAULT_COST_PER_MILLION_TOKENS, MODEL_COST_PER_MILLION_TOKENS

logger = logging.getLogger(__name__)


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Estimate USD cost based on token counts and model pricing."""
    input_rate, output_rate = MODEL_COST_PER_MILLION_TOKENS.get(
        model, DEFAULT_COST_PER_MILLION_TOKENS
    )
    return (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000


@dataclass
class TopicMetrics:
    """Metrics for a single topic within a pipeline run."""

    topic: str
    feeds_total: int = 0
    feeds_succeeded: int = 0
    feeds_failed: int = 0
    articles_fetched: int = 0
    articles_after_dedup: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str | None = None
    cost: float = 0.0


@dataclass
class RunMetrics:
    """Aggregate metrics for an entire pipeline run."""

    run_date: str
    run_timestamp: str
    duration_seconds: float
    model: str
    skipped_summarize: bool
    skipped_dedup: bool
    topics: list[TopicMetrics] = field(default_factory=list)

    @property
    def total_articles_fetched(self) -> int:
        return sum(t.articles_fetched for t in self.topics)

    @property
    def total_articles_after_dedup(self) -> int:
        return sum(t.articles_after_dedup for t in self.topics)

    @property
    def total_tokens(self) -> int:
        return sum(t.total_tokens for t in self.topics)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(t.prompt_tokens for t in self.topics)

    @property
    def total_completion_tokens(self) -> int:
        return sum(t.completion_tokens for t in self.topics)

    @property
    def total_feeds(self) -> int:
        return sum(t.feeds_total for t in self.topics)

    @property
    def successful_feeds(self) -> int:
        return sum(t.feeds_succeeded for t in self.topics)

    @property
    def total_cost(self) -> float:
        return sum(t.cost for t in self.topics)

    @property
    def topic_errors(self) -> int:
        return sum(1 for t in self.topics if t.error is not None)

    def to_dict(self) -> dict:
        """Serialize to a dictionary suitable for JSON output."""
        data = asdict(self)
        data["total_articles_fetched"] = self.total_articles_fetched
        data["total_articles_after_dedup"] = self.total_articles_after_dedup
        data["total_tokens"] = self.total_tokens
        data["total_prompt_tokens"] = self.total_prompt_tokens
        data["total_completion_tokens"] = self.total_completion_tokens
        data["total_feeds"] = self.total_feeds
        data["successful_feeds"] = self.successful_feeds
        data["total_cost"] = self.total_cost
        data["topic_errors"] = self.topic_errors
        return data

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def save_jsonl(self, metrics_file: Path) -> Path:
        """Append one JSON line to the JSONL file. Replaces last line on same-day rerun."""
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        new_line = json.dumps(self.to_dict(), ensure_ascii=False)

        lines: list[str] = []
        if metrics_file.exists():
            lines = [line for line in metrics_file.read_text(encoding="utf-8").splitlines() if line]

        if lines:
            try:
                last_entry = json.loads(lines[-1])
                if last_entry.get("run_date") == self.run_date:
                    lines[-1] = new_line
                else:
                    lines.append(new_line)
            except (json.JSONDecodeError, TypeError):
                lines.append(new_line)
        else:
            lines.append(new_line)

        metrics_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Saved metrics to %s", metrics_file)
        return metrics_file

    @classmethod
    def load_all_jsonl(cls, metrics_file: Path) -> list["RunMetrics"]:
        """Load all runs from a JSONL file. Returns empty list if file is missing."""
        if not metrics_file.exists():
            return []

        metrics: list[RunMetrics] = []
        for i, line in enumerate(metrics_file.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                metrics.append(cls.from_json(line))
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Skipping malformed line %d in %s: %s", i, metrics_file.name, e)
        return metrics

    @classmethod
    def from_json(cls, text: str) -> "RunMetrics":
        """Deserialize from a JSON string."""
        data = json.loads(text)
        topic_keys = {f.name for f in fields(TopicMetrics)}
        topics = [
            TopicMetrics(**{k: v for k, v in t.items() if k in topic_keys})
            for t in data.pop("topics", [])
        ]
        # Only pass keys that match actual constructor fields (ignore computed aggregates
        # and any future keys that may appear in newer JSON versions).
        valid_keys = {f.name for f in fields(cls)} - {"topics"}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(topics=topics, **filtered)

    @classmethod
    def create_now(
        cls,
        duration_seconds: float,
        model: str,
        skipped_summarize: bool,
        skipped_dedup: bool,
        topics: list[TopicMetrics],
    ) -> "RunMetrics":
        """Create a RunMetrics with current date and timestamp."""
        now = datetime.now(UTC)
        return cls(
            run_date=now.strftime("%Y-%m-%d"),
            run_timestamp=now.isoformat(),
            duration_seconds=round(duration_seconds, 1),
            model=model,
            skipped_summarize=skipped_summarize,
            skipped_dedup=skipped_dedup,
            topics=topics,
        )
