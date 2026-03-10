"""
Unit tests for GateKeeperMetrics (Phase 3).

Validates:
- record_venv_creation stores creation time and size.
- record_venv_rebuild increments rebuild counter.
- record_job_execution tracks time, success, and failure counts.
- get_summary returns structured dict with correct aggregation.
- prometheus_export returns valid Prometheus text format.
- _avg helper handles empty lists safely.
"""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

try:
    from metrics import GateKeeperMetrics, _avg
except ImportError:
    _gk_dir = Path(__file__).resolve().parents[1]
    if str(_gk_dir) not in sys.path:
        sys.path.insert(0, str(_gk_dir))
    from metrics import GateKeeperMetrics, _avg


# ---------------------------------------------------------------------------
# _avg helper
# ---------------------------------------------------------------------------


class TestAvgHelper:
    def test_empty_returns_zero(self):
        assert _avg([]) == 0.0

    def test_single_value(self):
        assert _avg([5.0]) == 5.0

    def test_multiple_values(self):
        assert _avg([1.0, 3.0]) == 2.0


# ---------------------------------------------------------------------------
# Venv metrics
# ---------------------------------------------------------------------------


class TestVenvMetrics:
    def test_record_venv_creation_stores_values(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("rembg", 3.5, 120.0)

        assert "rembg" in m.venv_creation_times
        assert m.venv_creation_times["rembg"] == [3.5]
        assert m.venv_sizes_mb["rembg"] == [120.0]

    def test_record_venv_creation_appends(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("rembg", 3.0, 100.0)
        m.record_venv_creation("rembg", 5.0, 110.0)

        assert len(m.venv_creation_times["rembg"]) == 2
        assert len(m.venv_sizes_mb["rembg"]) == 2

    def test_record_venv_rebuild_increments(self):
        m = GateKeeperMetrics()
        m.record_venv_rebuild("rembg")
        m.record_venv_rebuild("rembg")

        assert m.venv_rebuild_counts["rembg"] == 2

    def test_record_venv_rebuild_starts_from_zero(self):
        m = GateKeeperMetrics()
        m.record_venv_rebuild("new-worker")
        assert m.venv_rebuild_counts["new-worker"] == 1

    def test_multiple_workers_independent(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("worker-a", 2.0, 50.0)
        m.record_venv_creation("worker-b", 4.0, 80.0)

        assert m.venv_creation_times["worker-a"] == [2.0]
        assert m.venv_creation_times["worker-b"] == [4.0]


# ---------------------------------------------------------------------------
# Job metrics
# ---------------------------------------------------------------------------


class TestJobMetrics:
    def test_record_success(self):
        m = GateKeeperMetrics()
        m.record_job_execution("REMOTE_REMBG", 1.5, success=True)

        assert m.job_successes["REMOTE_REMBG"] == 1
        assert m.job_failures["REMOTE_REMBG"] == 0
        assert m.job_execution_times["REMOTE_REMBG"] == [1.5]

    def test_record_failure(self):
        m = GateKeeperMetrics()
        m.record_job_execution("REMOTE_REMBG", 0.8, success=False)

        assert m.job_successes["REMOTE_REMBG"] == 0
        assert m.job_failures["REMOTE_REMBG"] == 1

    def test_cumulative_counts(self):
        m = GateKeeperMetrics()
        m.record_job_execution("jt", 1.0, success=True)
        m.record_job_execution("jt", 2.0, success=True)
        m.record_job_execution("jt", 3.0, success=False)

        assert m.job_successes["jt"] == 2
        assert m.job_failures["jt"] == 1
        assert len(m.job_execution_times["jt"]) == 3

    def test_multiple_job_types_independent(self):
        m = GateKeeperMetrics()
        m.record_job_execution("typeA", 1.0, success=True)
        m.record_job_execution("typeB", 2.0, success=False)

        assert m.job_successes["typeA"] == 1
        assert m.job_failures["typeB"] == 1
        assert "typeA" not in m.job_failures or m.job_failures["typeA"] == 0


# ---------------------------------------------------------------------------
# get_summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_empty_metrics_returns_empty_dicts(self):
        m = GateKeeperMetrics()
        summary = m.get_summary()

        assert summary["venv_stats"] == {}
        assert summary["job_stats"] == {}

    def test_venv_summary_aggregation(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("w", 2.0, 100.0)
        m.record_venv_creation("w", 4.0, 200.0)

        summary = m.get_summary()
        ws = summary["venv_stats"]["w"]

        assert ws["creation_count"] == 2
        assert ws["avg_creation_sec"] == pytest.approx(3.0)
        assert ws["min_creation_sec"] == pytest.approx(2.0)
        assert ws["max_creation_sec"] == pytest.approx(4.0)
        assert ws["avg_size_mb"] == pytest.approx(150.0)

    def test_job_summary_aggregation(self):
        m = GateKeeperMetrics()
        m.record_job_execution("jt", 1.0, success=True)
        m.record_job_execution("jt", 3.0, success=False)

        summary = m.get_summary()
        js = summary["job_stats"]["jt"]

        assert js["successes"] == 1
        assert js["failures"] == 1
        assert js["avg_exec_time_sec"] == pytest.approx(2.0)
        assert js["min_exec_time_sec"] == pytest.approx(1.0)
        assert js["max_exec_time_sec"] == pytest.approx(3.0)

    def test_rebuild_count_in_summary(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("worker", 1.0, 50.0)
        m.record_venv_rebuild("worker")
        m.record_venv_rebuild("worker")

        summary = m.get_summary()
        assert summary["venv_stats"]["worker"]["rebuild_count"] == 2


# ---------------------------------------------------------------------------
# prometheus_export
# ---------------------------------------------------------------------------


class TestPrometheusExport:
    def test_export_contains_venv_metrics(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("rembg", 5.0, 200.0)
        output = m.prometheus_export()

        assert 'venv_creation_time_seconds{worker="rembg"}' in output
        assert 'venv_creation_count{worker="rembg"} 1' in output
        assert 'venv_size_mb{worker="rembg"}' in output

    def test_export_contains_job_metrics(self):
        m = GateKeeperMetrics()
        m.record_job_execution("REMOTE_REMBG", 2.5, success=True)
        m.record_job_execution("REMOTE_REMBG", 1.0, success=False)
        output = m.prometheus_export()

        assert 'job_successes_total{job_type="REMOTE_REMBG"} 1' in output
        assert 'job_failures_total{job_type="REMOTE_REMBG"} 1' in output
        assert 'job_execution_time_seconds{job_type="REMOTE_REMBG"}' in output

    def test_export_contains_rebuild_counter(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("w", 1.0, 10.0)
        m.record_venv_rebuild("w")
        output = m.prometheus_export()

        assert 'venv_rebuild_count{worker="w"} 1' in output

    def test_empty_metrics_no_data_lines(self):
        m = GateKeeperMetrics()
        output = m.prometheus_export()

        # Only HELP and TYPE comment lines should appear.
        data_lines = [
            line
            for line in output.splitlines()
            if line and not line.startswith("#")
        ]
        assert data_lines == []

    def test_export_has_help_and_type_comments(self):
        m = GateKeeperMetrics()
        output = m.prometheus_export()

        assert "# HELP venv_creation_time_seconds" in output
        assert "# TYPE venv_creation_time_seconds gauge" in output
        assert "# HELP job_successes_total" in output
        assert "# TYPE job_successes_total counter" in output

    def test_multiple_workers_in_export(self):
        m = GateKeeperMetrics()
        m.record_venv_creation("worker-a", 2.0, 100.0)
        m.record_venv_creation("worker-b", 4.0, 200.0)
        output = m.prometheus_export()

        assert 'worker="worker-a"' in output
        assert 'worker="worker-b"' in output
