"""Tests for the dashboard generator."""

from datetime import date

import pytest

from src.dashboard import (
    DASHBOARD_END,
    DASHBOARD_START,
    _build_last_run_summary,
    _format_cost,
    compute_summary,
    load_metrics,
    render_dashboard,
    update_readme,
)
from src.metrics import RunMetrics, TopicMetrics


def _sample_run(run_date: str, **overrides) -> RunMetrics:
    defaults = {
        "run_date": run_date,
        "run_timestamp": f"{run_date}T11:00:00+00:00",
        "duration_seconds": 45.0,
        "model": "gemini-2.5-pro",
        "skipped_summarize": False,
        "skipped_dedup": False,
        "topics": [
            TopicMetrics(
                topic="ai",
                feeds_total=18,
                feeds_succeeded=16,
                feeds_failed=2,
                articles_fetched=60,
                articles_after_dedup=45,
                prompt_tokens=10000,
                completion_tokens=5000,
                total_tokens=15000,
                cost=0.0625,
            ),
        ],
    }
    defaults.update(overrides)
    return RunMetrics(**defaults)


class TestLoadMetrics:
    def test_loads_valid_json_files(self, tmp_path):
        run = _sample_run("2026-03-25")
        (tmp_path / "2026-03-25.json").write_text(run.to_json())
        metrics = load_metrics(tmp_path)
        assert len(metrics) == 1
        assert metrics[0].run_date == "2026-03-25"

    def test_skips_malformed_json(self, tmp_path):
        (tmp_path / "2026-03-25.json").write_text("not valid json")
        (tmp_path / "2026-03-24.json").write_text(_sample_run("2026-03-24").to_json())
        metrics = load_metrics(tmp_path)
        assert len(metrics) == 1

    def test_returns_empty_when_directory_missing(self, tmp_path):
        metrics = load_metrics(tmp_path / "nonexistent")
        assert metrics == []

    def test_returns_empty_for_empty_directory(self, tmp_path):
        metrics = load_metrics(tmp_path)
        assert metrics == []


class TestComputeSummary:
    def test_filters_to_last_n_days(self):
        metrics = [
            _sample_run("2026-03-25"),
            _sample_run("2026-03-20"),
            _sample_run("2026-03-10"),
        ]
        summary = compute_summary(metrics, days=7, label="Last 7 days", today=date(2026, 3, 25))
        assert summary.runs == 2
        assert summary.articles_fetched == 120

    def test_thirty_day_window(self):
        metrics = [
            _sample_run("2026-03-25"),
            _sample_run("2026-03-01"),
            _sample_run("2026-02-20"),
        ]
        summary = compute_summary(metrics, days=30, label="Last 30 days", today=date(2026, 3, 25))
        assert summary.runs == 2

    def test_empty_metrics(self):
        summary = compute_summary([], days=7, label="Last 7 days", today=date(2026, 3, 25))
        assert summary.runs == 0
        assert summary.articles_fetched == 0
        assert summary.feed_success_rate == 0.0
        assert summary.topic_errors == 0

    def test_aggregates_tokens(self):
        metrics = [_sample_run("2026-03-25"), _sample_run("2026-03-24")]
        summary = compute_summary(metrics, days=7, label="Test", today=date(2026, 3, 25))
        assert summary.total_tokens == 30000
        assert summary.prompt_tokens == 20000
        assert summary.completion_tokens == 10000

    def test_feed_success_rate(self):
        metrics = [_sample_run("2026-03-25")]
        summary = compute_summary(metrics, days=7, label="Test", today=date(2026, 3, 25))
        assert summary.feed_success_rate == pytest.approx(88.9, abs=0.1)


class TestFormatCost:
    def test_zero_cost(self):
        assert _format_cost(0) == "$0.00"

    def test_shows_actual_precision(self):
        assert _format_cost(0.2912) == "$0.2912"

    def test_sub_cent_precision(self):
        assert _format_cost(0.009) == "$0.009"

    def test_even_dollar_keeps_two_decimals(self):
        assert _format_cost(1.50) == "$1.50"

    def test_small_fraction(self):
        assert _format_cost(0.0015) == "$0.0015"

    def test_aggregates_stored_cost(self):
        metrics = [_sample_run("2026-03-25"), _sample_run("2026-03-24")]
        summary = compute_summary(metrics, days=7, label="Test", today=date(2026, 3, 25))
        assert summary.total_cost == pytest.approx(0.125)


class TestBuildLastRunSummary:
    def test_uses_most_recent_run(self):
        metrics = [_sample_run("2026-03-20"), _sample_run("2026-03-25")]
        summary = _build_last_run_summary(metrics)
        assert summary.label == "Last run"
        assert summary.runs == 1
        assert summary.articles_fetched == 60

    def test_empty_metrics(self):
        summary = _build_last_run_summary([])
        assert summary.label == "Last run"
        assert summary.runs == 0
        assert summary.articles_fetched == 0
        assert summary.total_cost == 0.0
        assert summary.topic_errors == 0

    def test_counts_errors_from_last_run(self):
        error_topics = [
            TopicMetrics(topic="ai", error="feed failure"),
            TopicMetrics(topic="cricket"),
        ]
        metrics = [_sample_run("2026-03-25", topics=error_topics)]
        summary = _build_last_run_summary(metrics)
        assert summary.topic_errors == 1


class TestRenderDashboard:
    def test_produces_markdown_table(self):
        metrics = [_sample_run("2026-03-25"), _sample_run("2026-03-20")]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        assert DASHBOARD_START in dashboard
        assert DASHBOARD_END in dashboard
        assert "Pipeline Health" in dashboard
        assert "**Last run**" in dashboard
        assert "**30 days**" in dashboard
        assert "**All time**" in dashboard
        assert "Errors" in dashboard
        assert "Avg time" not in dashboard
        assert "gemini-2.5-pro" in dashboard

    def test_empty_metrics(self):
        dashboard = render_dashboard([], today=date(2026, 3, 25))
        assert "**Last run**" in dashboard
        assert "**30 days**" in dashboard
        assert "**All time**" in dashboard

    def test_cost_footnote_includes_model(self):
        metrics = [_sample_run("2026-03-25", model="gpt-4o")]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        assert "`gpt-4o`" in dashboard
        assert "$2.5/1M in" in dashboard

    def test_errors_column_shows_topic_errors(self):
        error_topics = [
            TopicMetrics(topic="ai", error="timeout"),
            TopicMetrics(topic="cricket", error="dns failure"),
            TopicMetrics(topic="finance"),
        ]
        metrics = [_sample_run("2026-03-25", topics=error_topics)]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        assert "| 2 |" in dashboard


class TestUpdateReadme:
    def test_replaces_between_markers(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            f"# Title\n\n{DASHBOARD_START}\nold dashboard\n{DASHBOARD_END}\n\n## License\n"
        )
        update_readme("NEW DASHBOARD CONTENT", readme)
        content = readme.read_text()
        assert "NEW DASHBOARD CONTENT" in content
        assert "old dashboard" not in content
        assert "## License" in content

    def test_inserts_before_license_when_no_markers(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n\nSome content.\n\n## License\n\nMIT\n")
        update_readme("NEW DASHBOARD", readme)
        content = readme.read_text()
        assert "NEW DASHBOARD" in content
        assert content.index("NEW DASHBOARD") < content.index("## License")

    def test_appends_when_no_markers_no_license(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n\nSome content.\n")
        update_readme("NEW DASHBOARD", readme)
        content = readme.read_text()
        assert content.endswith("NEW DASHBOARD\n")

    def test_skips_when_readme_missing(self, tmp_path, caplog):
        update_readme("DASHBOARD", tmp_path / "nonexistent.md")
        assert "not found" in caplog.text
