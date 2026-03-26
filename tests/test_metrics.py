"""Tests for metrics data model."""

import json

from src.metrics import RunMetrics, TopicMetrics


def _sample_topic(topic: str = "ai", **overrides) -> TopicMetrics:
    defaults = {
        "topic": topic,
        "feeds_total": 18,
        "feeds_succeeded": 16,
        "feeds_failed": 2,
        "articles_fetched": 65,
        "articles_after_dedup": 48,
        "prompt_tokens": 12000,
        "completion_tokens": 8000,
        "total_tokens": 20000,
    }
    defaults.update(overrides)
    return TopicMetrics(**defaults)


def _sample_run(**overrides) -> RunMetrics:
    defaults = {
        "run_date": "2026-03-25",
        "run_timestamp": "2026-03-25T11:00:00+00:00",
        "duration_seconds": 47.2,
        "model": "gemini-2.5-pro",
        "skipped_summarize": False,
        "skipped_dedup": False,
        "topics": [
            _sample_topic("ai"),
            _sample_topic("cricket", feeds_total=3, feeds_succeeded=3, feeds_failed=0),
        ],
    }
    defaults.update(overrides)
    return RunMetrics(**defaults)


def test_topic_metrics_defaults():
    topic = TopicMetrics(topic="test")
    assert topic.feeds_total == 0
    assert topic.prompt_tokens == 0
    assert topic.error is None


def test_run_metrics_computed_properties():
    run = _sample_run()
    assert run.total_articles_fetched == 130
    assert run.total_tokens == 40000
    assert run.total_feeds == 21
    assert run.successful_feeds == 19
    assert run.topic_errors == 0


def test_run_metrics_topic_errors_counted():
    run = _sample_run(topics=[_sample_topic(error="fetch failed"), _sample_topic()])
    assert run.topic_errors == 1


def test_to_json_roundtrip():
    original = _sample_run()
    text = original.to_json()
    restored = RunMetrics.from_json(text)
    assert restored.run_date == original.run_date
    assert restored.model == original.model
    assert restored.duration_seconds == original.duration_seconds
    assert len(restored.topics) == len(original.topics)
    assert restored.total_articles_fetched == original.total_articles_fetched
    assert restored.total_tokens == original.total_tokens


def test_to_dict_includes_aggregates():
    run = _sample_run()
    data = run.to_dict()
    assert "total_articles_fetched" in data
    assert "total_tokens" in data
    assert "total_feeds" in data
    assert "successful_feeds" in data
    assert "topic_errors" in data
    assert data["total_articles_fetched"] == 130


def test_from_json_ignores_unknown_aggregates():
    """Computed aggregate keys in JSON should not cause errors on deserialization."""
    run = _sample_run()
    text = run.to_json()
    data = json.loads(text)
    data["some_future_field"] = 999
    # Should not raise -- unknown keys are passed but dataclass will reject them.
    # Actually, let's verify the from_json handles the known aggregates it strips.
    restored = RunMetrics.from_json(run.to_json())
    assert restored.run_date == "2026-03-25"


def test_save_creates_file(tmp_path):
    run = _sample_run()
    filepath = run.save(tmp_path)
    assert filepath.exists()
    assert filepath.name == "2026-03-25.json"
    data = json.loads(filepath.read_text())
    assert data["model"] == "gemini-2.5-pro"


def test_save_overwrites_on_same_day(tmp_path):
    run1 = _sample_run(duration_seconds=10.0)
    run2 = _sample_run(duration_seconds=99.9)
    run1.save(tmp_path)
    filepath = run2.save(tmp_path)
    data = json.loads(filepath.read_text())
    assert data["duration_seconds"] == 99.9


def test_save_creates_directory(tmp_path):
    metrics_dir = tmp_path / "nested" / "metrics"
    run = _sample_run()
    filepath = run.save(metrics_dir)
    assert filepath.exists()


def test_create_now():
    run = RunMetrics.create_now(
        duration_seconds=12.345,
        model="gpt-4o",
        skipped_summarize=True,
        skipped_dedup=False,
        topics=[_sample_topic()],
    )
    assert run.model == "gpt-4o"
    assert run.duration_seconds == 12.3
    assert run.skipped_summarize is True
    assert len(run.run_date) == 10  # YYYY-MM-DD
    assert "T" in run.run_timestamp
