"""
Tests for TemplateWorker.

Copy and adapt this file when creating a new worker.
Replace TemplateWorker with your worker class name.
"""

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

# Ensure canonical package is importable from the test runner context
_CANONICAL = Path(__file__).resolve().parents[3]
if str(_CANONICAL.parent) not in sys.path:
    sys.path.insert(0, str(_CANONICAL.parent))

from canonical.workers.TEMPLATE.worker import TemplateWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_worker(extra_input: Dict[str, Any] = None) -> TemplateWorker:
    input_data = {"example_field": "test-value"}
    if extra_input:
        input_data.update(extra_input)
    return TemplateWorker(
        job_id="test-template-001",
        job_type="template_job",
        input_data=input_data,
    )


# ---------------------------------------------------------------------------
# BaseWorker contract compliance
# ---------------------------------------------------------------------------


class TestTemplateWorkerContract:
    def test_worker_has_correct_attributes(self):
        w = _make_worker()
        assert w.job_id == "test-template-001"
        assert w.job_type == "template_job"
        assert "example_field" in w.input_data

    def test_worker_inherits_base_worker(self):
        from canonical.shared.base_worker import BaseWorker
        w = _make_worker()
        assert isinstance(w, BaseWorker)

    def test_teardown_is_safe_when_setup_not_called(self):
        """teardown() must never raise even if setup() was skipped."""
        w = _make_worker()
        w.teardown()  # Should not raise


# ---------------------------------------------------------------------------
# Execute logic
# ---------------------------------------------------------------------------


class TestTemplateWorkerExecute:
    def test_execute_returns_output_key(self):
        w = _make_worker()
        result = w.execute()
        assert "output" in result

    def test_execute_processes_example_field(self):
        w = _make_worker({"example_field": "hello"})
        result = w.execute()
        assert "hello" in result["output"]

    def test_execute_raises_value_error_on_missing_field(self):
        w = TemplateWorker(
            job_id="test",
            job_type="template_job",
            input_data={},  # missing example_field
        )
        with pytest.raises(ValueError, match="example_field"):
            w.execute()


# ---------------------------------------------------------------------------
# JSON I/O via run()
# ---------------------------------------------------------------------------


class TestTemplateWorkerJsonIO:
    def test_run_outputs_success_json(self, capsys):
        w = _make_worker()
        with pytest.raises(SystemExit) as exc_info:
            w.run()
        assert exc_info.value.code == 0
        import json
        output = json.loads(capsys.readouterr().out)
        assert output["success"] is True
        assert "result" in output

    def test_run_outputs_error_json_on_failure(self, capsys):
        w = _make_worker()
        with patch.object(w, "execute", side_effect=ValueError("test error")):
            with pytest.raises(SystemExit) as exc_info:
                w.run()
        assert exc_info.value.code == 1
        import json
        output = json.loads(capsys.readouterr().out)
        assert output["success"] is False
        assert "test error" in output["error"]
