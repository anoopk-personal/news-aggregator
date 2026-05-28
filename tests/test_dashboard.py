"""Tests for the dashboard generator."""

from datetime import date

import pytest

from src.dashboard import (
    DASHBOARD_END,
    DASHBOARD_START,
    _format_cost,
    _format_duration,
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
        "duration_seconds": 120.0,
        "model": "gemini-2.5-pro",
        "skipped_summarize": False,
        "skipped_dedup": False,
        "topics": [
            TopicMetrics(
                topic="ai",
                feeds_total=18,
                feeds_succeeded=13,
                feeds_failed=5,
                articles_fetched=80,
                articles_after_dedup=80,
                prompt_tokens=10000,
                completion_tokens=5000,
                total_tokens=15000,
                cost=0.0625,
            ),
            TopicMetrics(
                topic="cricket",
                feeds_total=3,
                feeds_succeeded=2,
                feeds_failed=1,
                articles_fetched=35,
                articles_after_dedup=35,
                prompt_tokens=3000,
                completion_tokens=2000,
                total_tokens=5000,
                cost=0.02375,
            ),
        ],
    }
    defaults.update(overrides)
    return RunMetrics(**defaults)


class TestLoadMetrics:
    def _write_jsonl(self, path, *runs):
        import json

        lines = [json.dumps(r.to_dict(), ensure_ascii=False) for r in runs]
        path.write_text("\n".join(lines) + "\n")

    def test_loads_valid_jsonl(self, tmp_path):
        jsonl_file = tmp_path / "history.jsonl"
        self._write_jsonl(jsonl_file, _sample_run("2026-03-25"))
        metrics = load_metrics(jsonl_file)
        assert len(metrics) == 1
        assert metrics[0].run_date == "2026-03-25"

    def test_skips_malformed_lines(self, tmp_path):
        import json

        jsonl_file = tmp_path / "history.jsonl"
        good_line = json.dumps(_sample_run("2026-03-24").to_dict(), ensure_ascii=False)
        jsonl_file.write_text(f"not valid json\n{good_line}\n")
        metrics = load_metrics(jsonl_file)
        assert len(metrics) == 1

    def test_returns_empty_when_file_missing(self, tmp_path):
        metrics = load_metrics(tmp_path / "nonexistent.jsonl")
        assert metrics == []

    def test_returns_empty_for_empty_file(self, tmp_path):
        jsonl_file = tmp_path / "history.jsonl"
        jsonl_file.write_text("")
        metrics = load_metrics(jsonl_file)
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
        assert summary.articles_fetched == 230

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

    def test_feed_success_rate(self):
        metrics = [_sample_run("2026-03-25")]
        summary = compute_summary(metrics, days=7, label="Test", today=date(2026, 3, 25))
        # 15 succeeded / 21 total = 71.4%
        assert summary.feed_success_rate == pytest.approx(71.4, abs=0.1)

    def test_aggregates_cost(self):
        metrics = [_sample_run("2026-03-25"), _sample_run("2026-03-24")]
        summary = compute_summary(metrics, days=7, label="Test", today=date(2026, 3, 25))
        assert summary.total_cost == pytest.approx(0.17250)

    def test_seven_day_period(self):
        metrics = [
            _sample_run("2026-03-25"),
            _sample_run("2026-03-22"),
            _sample_run("2026-03-19"),
            _sample_run("2026-03-15"),
        ]
        summary = compute_summary(metrics, days=7, label="7 days", today=date(2026, 3, 25))
        assert summary.runs == 3
        assert summary.label == "7 days"

    def test_seven_day_period_excludes_eighth_calendar_date(self):
        metrics = [
            _sample_run("2026-03-25"),
            _sample_run("2026-03-19"),
            _sample_run("2026-03-18"),
        ]
        summary = compute_summary(metrics, days=7, label="7 days", today=date(2026, 3, 25))
        assert summary.runs == 2


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


class TestFormatDuration:
    def test_seconds_only(self):
        assert _format_duration(45.0) == "45s"

    def test_minutes_and_seconds(self):
        assert _format_duration(159.9) == "2m 39s"

    def test_exact_minutes(self):
        assert _format_duration(120.0) == "2m 0s"

    def test_zero(self):
        assert _format_duration(0.0) == "0s"


class TestRenderDashboard:
    def test_produces_dashboard_structure(self):
        metrics = [_sample_run("2026-03-25"), _sample_run("2026-03-20")]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        assert DASHBOARD_START in dashboard
        assert DASHBOARD_END in dashboard
        assert "Pipeline Health" in dashboard
        # Hero line
        assert "Last run: **Mar 25**" in dashboard
        assert "115 articles" in dashboard
        assert "15/21 feeds" in dashboard
        assert "2m 0s" in dashboard
        # Per-topic table
        assert "| Ai |" in dashboard
        assert "| Cricket |" in dashboard
        # Historical table
        assert "**7 days**" in dashboard
        assert "**30 days**" in dashboard
        assert "**All time**" in dashboard
        # No tokens column
        assert "Tokens" not in dashboard
        assert "gemini-2.5-pro" in dashboard

    def test_empty_metrics(self):
        dashboard = render_dashboard([], today=date(2026, 3, 25))
        assert "Last run: **--**" in dashboard
        assert "**7 days**" in dashboard
        assert "**30 days**" in dashboard
        assert "**All time**" in dashboard
        # No topic table when no data
        assert "| Topic |" not in dashboard

    def test_footer_includes_model_and_avg_cost(self):
        metrics = [_sample_run("2026-03-25", model="gpt-4o")]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        assert "`gpt-4o`" in dashboard
        assert "/run" in dashboard

    def test_per_topic_rows(self):
        run = _sample_run(
            "2026-03-25",
            topics=[
                TopicMetrics(
                    topic="ai",
                    feeds_total=18,
                    feeds_succeeded=13,
                    feeds_failed=5,
                    articles_fetched=87,
                    cost=0.10,
                ),
                TopicMetrics(
                    topic="cricket",
                    feeds_total=3,
                    feeds_succeeded=2,
                    feeds_failed=1,
                    articles_fetched=37,
                    cost=0.07,
                ),
                TopicMetrics(
                    topic="finance",
                    feeds_total=1,
                    feeds_succeeded=1,
                    feeds_failed=0,
                    articles_fetched=10,
                    cost=0.05,
                ),
            ],
        )
        dashboard = render_dashboard([run], today=date(2026, 3, 25))
        assert "| Ai | 13/18 | 87 | $0.10 |" in dashboard
        assert "| Cricket | 2/3 | 37 | $0.07 |" in dashboard
        assert "| Finance | 1/1 | 10 | $0.05 |" in dashboard

    def test_avg_cost_per_run(self):
        metrics = [_sample_run("2026-03-25"), _sample_run("2026-03-24")]
        dashboard = render_dashboard(metrics, today=date(2026, 3, 25))
        # Each run costs 0.08625, avg = 0.08625
        assert "~$0.0862/run" in dashboard


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
