"""
Tests for RembgWorker.

Tests the BaseWorker contract compliance and JSON I/O behaviour without
requiring rembg / ONNX to be installed.
"""

import base64
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Ensure the parent packages are importable
_CANONICAL = Path(__file__).resolve().parents[3]
if str(_CANONICAL.parent) not in sys.path:
    sys.path.insert(0, str(_CANONICAL.parent))

from canonical.workers.rembg.worker import RembgWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_1px_png_b64() -> str:
    """Return a 1x1 white PNG as base64."""
    try:
        from PIL import Image
        img = Image.new("RGB", (1, 1), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        # Minimal valid 1×1 PNG bytes
        _PNG = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        return base64.b64encode(_PNG).decode()


# ---------------------------------------------------------------------------
# Worker contract tests (no rembg required)
# ---------------------------------------------------------------------------


class TestRembgWorkerContract:
    def _make_worker(self, extra_input: Dict[str, Any] = None) -> RembgWorker:
        input_data = {"image_base64": _make_1px_png_b64()}
        if extra_input:
            input_data.update(extra_input)
        return RembgWorker(
            job_id="test-rembg-001",
            job_type="rembg_removebackground",
            input_data=input_data,
        )

    def test_worker_has_correct_attributes(self):
        w = self._make_worker()
        assert w.job_id == "test-rembg-001"
        assert w.job_type == "rembg_removebackground"
        assert "image_base64" in w.input_data

    def test_worker_inherits_base_worker(self):
        from canonical.shared.base_worker import BaseWorker
        w = self._make_worker()
        assert isinstance(w, BaseWorker)

    def test_teardown_safe_when_session_not_set(self):
        """teardown() must not raise if setup() was never called."""
        w = self._make_worker()
        w.teardown()  # Should not raise

    def test_run_outputs_valid_json_on_success(self, capsys):
        """run() writes JSON to stdout on success."""
        w = self._make_worker()

        mock_image = MagicMock()
        mock_image.mode = "RGBA"
        mock_image.size = (1, 1)

        result_buf = io.BytesIO()
        try:
            from PIL import Image
            img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            img.save(result_buf, format="PNG")
        except ImportError:
            result_buf.write(b"PNG_PLACEHOLDER")
        result_buf.seek(0)

        mock_session = MagicMock()
        mock_rembg = MagicMock()
        mock_rembg.new_session.return_value = mock_session
        mock_rembg.remove.return_value = mock_image
        mock_image.save = lambda buf, format: buf.write(b"\x89PNG")
        mock_image.mode = "RGBA"

        import sys
        with (
            patch.dict(sys.modules, {"rembg": mock_rembg}),
            patch("canonical.workers.rembg.worker.Path.mkdir"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                w.run()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert "result" in output

    def test_run_outputs_error_json_on_failure(self, capsys):
        """run() writes error JSON to stdout when execute() raises."""
        w = self._make_worker()

        with patch.object(w, "setup", side_effect=RuntimeError("model load failed")):
            with pytest.raises(SystemExit) as exc_info:
                w.run()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is False
        assert "model load failed" in output["error"]

    def test_execute_strips_data_uri_prefix(self):
        """execute() should strip base64 data-URI prefix before decoding."""
        b64 = _make_1px_png_b64()
        w = RembgWorker(
            job_id="test-002",
            job_type="rembg_removebackground",
            input_data={"image_base64": f"data:image/png;base64,{b64}"},
        )

        mock_session = MagicMock()
        w._session = mock_session

        mock_result = MagicMock()
        mock_result.mode = "RGBA"
        mock_result.size = (1, 1)
        mock_result.save = lambda buf, format: buf.write(b"\x89PNG\r\n")

        mock_rembg = MagicMock()
        mock_rembg.remove.return_value = mock_result

        import sys
        with patch.dict(sys.modules, {"rembg": mock_rembg}):
            result = w.execute()

        assert "image_base64" in result
        mock_rembg.remove.assert_called_once()
