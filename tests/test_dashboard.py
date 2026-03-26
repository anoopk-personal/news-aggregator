"""Tests for the dashboard generator."""

from datetime import date

import pytest

from src.dashboard import (
    DASHBOARD_END,
    DASHBOARD_START,
    compute_summary,
    estimate_cost,
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
        assert summary.avg_duration_seconds == 0.0

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


class TestEstimateCost:
    def test_known_model(self):
        cost = estimate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            model="gemini-2.5-pro",
        )
        # 1M * $1.25/1M + 500k * $10.00/1M = $1.25 + $5.00 = $6.25
        assert cost == pytest.approx(6.25)

    def test_unknown_model_uses_default(self):
        cost = estimate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            model="some-new-model",
        )
        # 1M * $1.00/1M + 1M * $3.00/1M = $4.00
        assert cost == pytest.approx(4.0)

    def test_zero_tokens(self):
        cost = estimate_cost(prompt_tokens=0, completion_tokens=0, model="gemini-2.5-pro")
        assert cost == 0.0

    def test_local_model_free(self):
        cost = estimate_cost(prompt_tokens=100000, completion_tokens=50000, model="llama3")
        assert cost == 0.0


class TestRenderDashboard:
    def test_produces_markdown_table(self):
        metrics = [_sample_run("2026-03-25"), _sample_run("2026-03-20")]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        assert DASHBOARD_START in dashboard
        assert DASHBOARD_END in dashboard
        assert "Pipeline Health" in dashboard
        assert "**7 days**" in dashboard
        assert "**30 days**" in dashboard
        assert "gemini-2.5-pro" in dashboard

    def test_empty_metrics(self):
        dashboard = render_dashboard([], today=date(2026, 3, 25))
        assert "**7 days**" in dashboard
        assert "**30 days**" in dashboard

    def test_cost_footnote_includes_model(self):
        metrics = [_sample_run("2026-03-25", model="gpt-4o")]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        assert "`gpt-4o`" in dashboard
        assert "$2.5/1M in" in dashboard


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
