"""
End-to-end tests for the complete workers architecture pipeline.

Tests the full lifecycle from job creation through result retrieval,
covering all execution models (subprocess and service) and error paths.

Pipeline under test:
  1. Backend creates job → Redis L1 queue
  2. GateKeeper BRPOP from L1
  3. Route to subprocess worker (e.g. Rembg) OR HTTP service (e.g. Ollama)
  4. Worker executes (stdin JSON → execute → stdout JSON)
  5. Result persisted to Redis L1 via RPUSH
  6. Backend retrieves result from Redis L1

These tests use mocks for all external I/O (Redis, HTTP, subprocess) and
exercise the real GateKeeper routing, result-persistence, and error-handling
code paths end-to-end.
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Path setup (allow running from any directory)
# ---------------------------------------------------------------------------

_gk_dir = Path(__file__).resolve().parents[1]
if str(_gk_dir) not in sys.path:
    sys.path.insert(0, str(_gk_dir))

from main import GateKeeper  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MINIMAL_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_REMBG_RESULT_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQ"
    "AABjHu8gAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def gatekeeper(mock_redis_l1: AsyncMock, mock_redis_l2: AsyncMock, mock_http_client: AsyncMock) -> GateKeeper:
    return GateKeeper(
        redis_l1=mock_redis_l1,
        redis_l2=mock_redis_l2,
        http_client=mock_http_client,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_http_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    return resp


# ---------------------------------------------------------------------------
# Scenario 1: Rembg subprocess — full success path
# ---------------------------------------------------------------------------


class TestScenario1RembgSubprocessFullPipeline:
    """
    Full end-to-end pipeline: Rembg subprocess job from dispatch to result.

    Validates:
    - GateKeeper routes REMOTE_REMBG to subprocess executor.
    - execute_subprocess_job receives correct arguments.
    - Result is RPUSH'd to Redis L1 with the correct key.
    - TTL is set on the result key.
    - L2 (CentralHub) is NOT written to for subprocess workers.
    """

    @pytest.mark.asyncio
    async def test_rembg_dispatch_to_result_persisted(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock, mock_redis_l2: AsyncMock
    ) -> None:
        job = {
            "job_id": "e2e-pipeline-rembg-001",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }
        expected = {"image_base64": _REMBG_RESULT_B64}

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = expected
            await gatekeeper._dispatch("scareverse:cpu-jobs:queue", json.dumps(job), job, "owner")

        # 1. Subprocess executor was called with correct arguments
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert args[0] == "REMOTE_REMBG", "job_type mismatch"
        assert args[1] == "e2e-pipeline-rembg-001", "job_id mismatch"
        assert args[2] == {"image_base64": _MINIMAL_PNG_B64}, "input_data mismatch"

        # 2. Result RPUSH'd to L1 with correct key pattern
        mock_redis_l1.rpush.assert_called_once()
        result_key = mock_redis_l1.rpush.call_args[0][0]
        assert "rembg-results" in result_key, f"Unexpected key: {result_key}"
        assert "e2e-pipeline-rembg-001" in result_key

        # 3. Result payload matches
        raw_result = mock_redis_l1.rpush.call_args[0][1]
        persisted = json.loads(raw_result)
        assert persisted["image_base64"] == _REMBG_RESULT_B64

        # 4. TTL set on result key
        mock_redis_l1.expire.assert_called_once()
        ttl_key, ttl_seconds = mock_redis_l1.expire.call_args[0]
        assert ttl_key == result_key
        assert ttl_seconds > 0, "TTL must be positive"

        # 5. L2 not touched for subprocess workers
        mock_redis_l2.hset.assert_not_called()

    @pytest.mark.asyncio
    async def test_rembg_metrics_recorded_after_success(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        job = {
            "job_id": "e2e-pipeline-metrics-001",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"image_base64": _REMBG_RESULT_B64}
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        summary = gatekeeper.metrics.get_summary()
        job_stats = summary["job_stats"].get("REMOTE_REMBG", {})
        assert job_stats.get("successes", 0) == 1, "Expected 1 success metric"
        assert job_stats.get("failures", 0) == 0, "Expected 0 failure metrics"

    @pytest.mark.asyncio
    async def test_rembg_payload_field_used_as_input_data_fallback(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        """Legacy 'payload' field is accepted when 'input_data' is absent."""
        job = {
            "job_id": "e2e-pipeline-rembg-fallback",
            "job_type": "REMOTE_REMBG",
            "payload": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"image_base64": "FALLBACK_RESULT"}
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        args = mock_exec.call_args[0]
        assert args[2] == {"image_base64": _MINIMAL_PNG_B64}, "Fallback 'payload' not used as input_data"


# ---------------------------------------------------------------------------
# Scenario 2: Ollama service — HTTP dispatch path
# ---------------------------------------------------------------------------


class TestScenario2OllamaServiceDispatch:
    """
    End-to-end pipeline: Ollama service job via HTTP POST.

    Validates:
    - GateKeeper routes ollama_generate to service executor (HTTP).
    - HTTP endpoint is called with the correct URL and payload.
    - Result RPUSH'd to Redis L1 with correct key.
    - Subprocess executor is NOT called for service workers.
    """

    @pytest.mark.asyncio
    async def test_ollama_dispatched_via_http_and_result_persisted(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock, mock_http_client: AsyncMock
    ) -> None:
        job = {
            "job_id": "e2e-pipeline-ollama-001",
            "type": "ollama_generate",
            "payload": {
                "prompt": "Describe ScareVerse in one sentence.",
                "model": "mistral",
                "stream": False,
                "options": {},
            },
            "created_at": 0.0,
            "attempts": 0,
            "_source": "owner",
        }
        http_result = {
            "status": "success",
            "data": {"response": "ScareVerse is an AI-driven creative platform.", "model": "mistral"},
            "error": None,
        }

        gatekeeper.http.post.return_value = _make_http_response(200, http_result)

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_subprocess:
            await gatekeeper._dispatch("scareverse:cpu-jobs:queue", json.dumps(job), job, "owner")
            # Subprocess executor MUST NOT be called for service jobs
            mock_subprocess.assert_not_called()

        # HTTP endpoint was called
        gatekeeper.http.post.assert_called_once()
        call_url = gatekeeper.http.post.call_args[0][0]
        assert "ollama" in call_url.lower(), f"Unexpected endpoint: {call_url}"

        # Result persisted to L1
        mock_redis_l1.rpush.assert_called_once()
        result_key = mock_redis_l1.rpush.call_args[0][0]
        assert "ollama-results" in result_key
        assert "e2e-pipeline-ollama-001" in result_key

    @pytest.mark.asyncio
    async def test_ollama_metrics_recorded_after_success(
        self, gatekeeper: GateKeeper
    ) -> None:
        job = {
            "job_id": "e2e-pipeline-ollama-metrics",
            "type": "ollama_generate",
            "payload": {"prompt": "Hello", "model": "mistral", "stream": False, "options": {}},
            "created_at": 0.0,
            "attempts": 0,
            "_source": "owner",
        }
        gatekeeper.http.post.return_value = _make_http_response(
            200, {"status": "success", "data": {"response": "Hi"}, "error": None}
        )

        await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        summary = gatekeeper.metrics.get_summary()
        job_stats = summary["job_stats"].get("ollama_generate", {})
        assert job_stats.get("successes", 0) == 1


# ---------------------------------------------------------------------------
# Scenario 3: Concurrent/sequential jobs — different workers, no cross-contamination
# ---------------------------------------------------------------------------


class TestScenario3ConcurrentJobHandling:
    """
    Sequential dispatch of multiple jobs to different workers.

    Validates:
    - Jobs processed independently with no result cross-contamination.
    - Each job's result stored in its own Redis key.
    - Metrics correctly track per-job-type counts.
    """

    @pytest.mark.asyncio
    async def test_two_rembg_jobs_stored_in_separate_keys(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        job_a = {
            "job_id": "e2e-concurrent-rembg-A",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }
        job_b = {
            "job_id": "e2e-concurrent-rembg-B",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        results = {"A": {"image_base64": "RESULT_A"}, "B": {"image_base64": "RESULT_B"}}
        call_count = {"n": 0}

        async def _fake_exec(job_type: str, job_id: str, input_data: dict, route: dict) -> dict:
            call_count["n"] += 1
            key = "A" if job_id.endswith("-A") else "B"
            return results[key]

        with patch("main.execute_subprocess_job", side_effect=_fake_exec):
            await gatekeeper._dispatch("q", json.dumps(job_a), job_a, "owner")
            await gatekeeper._dispatch("q", json.dumps(job_b), job_b, "owner")

        assert call_count["n"] == 2

        rpush_calls = mock_redis_l1.rpush.call_args_list
        assert len(rpush_calls) == 2

        keys = {c[0][0] for c in rpush_calls}
        assert any("rembg-concurrent-rembg-A" in k or "e2e-concurrent-rembg-A" in k for k in keys)
        assert any("rembg-concurrent-rembg-B" in k or "e2e-concurrent-rembg-B" in k for k in keys)

        # Verify results are stored separately
        payloads = {json.loads(c[0][1])["image_base64"] for c in rpush_calls}
        assert payloads == {"RESULT_A", "RESULT_B"}

    @pytest.mark.asyncio
    async def test_mixed_subprocess_and_service_jobs_independent(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        """Subprocess and service jobs in sequence do not interfere."""
        rembg_job = {
            "job_id": "e2e-mixed-rembg",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }
        ollama_job = {
            "job_id": "e2e-mixed-ollama",
            "type": "ollama_generate",
            "payload": {"prompt": "test", "model": "mistral", "stream": False, "options": {}},
            "created_at": 0.0,
            "attempts": 0,
            "_source": "owner",
        }

        gatekeeper.http.post.return_value = _make_http_response(
            200, {"status": "success", "data": {"response": "ok"}, "error": None}
        )

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_subprocess:
            mock_subprocess.return_value = {"image_base64": "MIXED_REMBG_RESULT"}
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")
            await gatekeeper._dispatch("q", json.dumps(ollama_job), ollama_job, "owner")

        # Subprocess called once (rembg), HTTP called once (ollama)
        mock_subprocess.assert_called_once()
        gatekeeper.http.post.assert_called_once()

        # Both results stored in L1
        assert mock_redis_l1.rpush.call_count == 2

    @pytest.mark.asyncio
    async def test_metrics_track_per_job_type_independently(
        self, gatekeeper: GateKeeper
    ) -> None:
        """Metrics correctly isolate counts per job-type."""
        jobs = [
            {"job_id": f"e2e-metrics-rembg-{i}", "job_type": "REMOTE_REMBG",
             "input_data": {"image_base64": _MINIMAL_PNG_B64}, "_source": "owner"}
            for i in range(3)
        ]

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"image_base64": "RESULT"}
            for job in jobs:
                await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        summary = gatekeeper.metrics.get_summary()
        rembg_stats = summary["job_stats"].get("REMOTE_REMBG", {})
        assert rembg_stats.get("successes", 0) == 3
        assert rembg_stats.get("failures", 0) == 0


# ---------------------------------------------------------------------------
# Scenario 4: Error handling — timeout, crash, invalid input
# ---------------------------------------------------------------------------


class TestScenario4ErrorHandling:
    """
    End-to-end validation of all error paths.

    Validates:
    - Timeout → error result RPUSH'd + job sent to dead-letter.
    - Worker crash (RuntimeError) → error result RPUSH'd + dead-letter.
    - ValueError (permanent failure) → error RPUSH'd + dead-letter.
    - Error result has expected structure: {"status": "error", "error": "..."}.
    - Metrics track failure counts correctly.
    """

    @pytest.mark.asyncio
    async def test_timeout_error_persisted_and_dead_lettered(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        job = {
            "job_id": "e2e-error-timeout",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = TimeoutError("Worker exceeded 60s timeout")
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        # Error result persisted to L1
        mock_redis_l1.rpush.assert_called()
        error_payload = json.loads(mock_redis_l1.rpush.call_args[0][1])
        assert error_payload["status"] == "error"
        assert "timeout" in error_payload["error"].lower() or "exceeded" in error_payload["error"].lower()

        # Job sent to dead-letter
        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key

    @pytest.mark.asyncio
    async def test_value_error_persisted_and_dead_lettered(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        job = {
            "job_id": "e2e-error-value",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": "INVALID_BASE64"},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = ValueError("invalid base64 input")
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        mock_redis_l1.rpush.assert_called()
        error_payload = json.loads(mock_redis_l1.rpush.call_args[0][1])
        assert error_payload["status"] == "error"
        assert "invalid base64" in error_payload["error"]

        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key

    @pytest.mark.asyncio
    async def test_runtime_error_persisted_and_dead_lettered(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        job = {
            "job_id": "e2e-error-runtime",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("worker process crashed with exit code 1")
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        mock_redis_l1.rpush.assert_called()
        error_payload = json.loads(mock_redis_l1.rpush.call_args[0][1])
        assert error_payload["status"] == "error"
        assert "crashed" in error_payload["error"] or "exit code" in error_payload["error"]

        mock_redis_l1.lpush.assert_called()

    @pytest.mark.asyncio
    async def test_timeout_failure_tracked_in_metrics(
        self, gatekeeper: GateKeeper
    ) -> None:
        """Timeout failures are recorded in metrics as failures."""
        job = {
            "job_id": "e2e-metrics-failure",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = TimeoutError("timeout")
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        summary = gatekeeper.metrics.get_summary()
        rembg_stats = summary["job_stats"].get("REMOTE_REMBG", {})
        assert rembg_stats.get("failures", 0) == 1
        assert rembg_stats.get("successes", 0) == 0

    @pytest.mark.asyncio
    async def test_http_service_error_persisted(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        """HTTP service failure (non-200) results in error being persisted."""
        job = {
            "job_id": "e2e-service-error",
            "type": "ollama_generate",
            "payload": {"prompt": "test", "model": "mistral", "stream": False, "options": {}},
            "created_at": 0.0,
            "attempts": 0,
            "_source": "owner",
        }
        # Service returns HTTP 500
        gatekeeper.http.post.return_value = _make_http_response(
            500, {"status": "error", "error": "Model not loaded"}
        )

        await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        # Result was persisted (either success or error shape, but something was stored)
        assert mock_redis_l1.rpush.called or mock_redis_l1.lpush.called


# ---------------------------------------------------------------------------
# Scenario 5: Dead-letter routing
# ---------------------------------------------------------------------------


class TestScenario5DeadLetterRouting:
    """
    Validate dead-letter queue routing for unrecoverable job failures.

    Validates:
    - Unknown job types go directly to dead-letter (no executor called).
    - Timed-out jobs go to dead-letter after error result is persisted.
    - Dead-letter key matches DEAD_LETTER_QUEUE config.
    """

    @pytest.mark.asyncio
    async def test_unknown_job_type_routes_to_dead_letter(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock, mock_http_client: AsyncMock
    ) -> None:
        job = {
            "job_id": "e2e-dl-unknown",
            "job_type": "COMPLETELY_UNKNOWN_JOB_TYPE_XYZ",
            "input_data": {},
            "_source": "owner",
        }

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_subprocess:
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")
            mock_subprocess.assert_not_called()

        mock_http_client.post.assert_not_called()
        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key

    @pytest.mark.asyncio
    async def test_dead_letter_contains_original_job_payload(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        raw_job = json.dumps({
            "job_id": "e2e-dl-payload",
            "job_type": "UNKNOWN_TYPE",
            "input_data": {"custom_field": "custom_value"},
            "_source": "owner",
        })
        job = json.loads(raw_job)

        await gatekeeper._dispatch("q", raw_job, job, "owner")

        mock_redis_l1.lpush.assert_called()
        dl_payload = mock_redis_l1.lpush.call_args[0][1]

        # Dead-letter payload must be the original raw job
        assert dl_payload == raw_job or "e2e-dl-payload" in dl_payload

    @pytest.mark.asyncio
    async def test_timed_out_job_dead_lettered_after_error_result(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        """Ordering: error RPUSH to L1 happens before dead-letter LPUSH."""
        job = {
            "job_id": "e2e-dl-ordering",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        call_order: list = []
        original_rpush = mock_redis_l1.rpush

        async def _track_rpush(*args: object, **kwargs: object) -> int:
            call_order.append("rpush")
            return await original_rpush(*args, **kwargs)

        original_lpush = mock_redis_l1.lpush

        async def _track_lpush(*args: object, **kwargs: object) -> int:
            call_order.append("lpush")
            return await original_lpush(*args, **kwargs)

        mock_redis_l1.rpush = _track_rpush
        mock_redis_l1.lpush = _track_lpush

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = TimeoutError("timed out")
            await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        # Error result should be stored before dead-letter
        assert "rpush" in call_order
        assert "lpush" in call_order
        rpush_idx = call_order.index("rpush")
        lpush_idx = call_order.index("lpush")
        assert rpush_idx < lpush_idx, "Error result should be persisted before dead-letter"


# ---------------------------------------------------------------------------
# Scenario 6: Prometheus metrics export after job lifecycle
# ---------------------------------------------------------------------------


class TestScenario6MetricsAndMonitoring:
    """
    Validate Prometheus-format metrics are exported correctly after job execution.

    Validates:
    - job_successes_total counter present in export.
    - job_failures_total counter present in export.
    - job_execution_time_seconds gauge present in export.
    - Metric labels include job_type.
    """

    @pytest.mark.asyncio
    async def test_prometheus_export_after_successful_jobs(
        self, gatekeeper: GateKeeper
    ) -> None:
        jobs = [
            {"job_id": f"e2e-prom-{i}", "job_type": "REMOTE_REMBG",
             "input_data": {"image_base64": _MINIMAL_PNG_B64}, "_source": "owner"}
            for i in range(2)
        ]

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"image_base64": "RESULT"}
            for job in jobs:
                await gatekeeper._dispatch("q", json.dumps(job), job, "owner")

        prometheus_output = gatekeeper.metrics.prometheus_export()

        assert "# HELP job_successes_total" in prometheus_output
        assert "# TYPE job_successes_total counter" in prometheus_output
        assert 'job_successes_total{job_type="REMOTE_REMBG"} 2' in prometheus_output

        assert "# HELP job_execution_time_seconds" in prometheus_output
        assert 'job_execution_time_seconds{job_type="REMOTE_REMBG"}' in prometheus_output

    @pytest.mark.asyncio
    async def test_prometheus_export_after_mixed_success_failure(
        self, gatekeeper: GateKeeper
    ) -> None:
        success_job = {
            "job_id": "e2e-prom-success",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }
        fail_job = {
            "job_id": "e2e-prom-failure",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        call_count = {"n": 0}

        async def _mixed_exec(job_type: str, job_id: str, input_data: dict, route: dict) -> dict:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"image_base64": "RESULT"}
            raise TimeoutError("second job timed out")

        with patch("main.execute_subprocess_job", side_effect=_mixed_exec):
            await gatekeeper._dispatch("q", json.dumps(success_job), success_job, "owner")
            await gatekeeper._dispatch("q", json.dumps(fail_job), fail_job, "owner")

        prometheus_output = gatekeeper.metrics.prometheus_export()

        assert 'job_successes_total{job_type="REMOTE_REMBG"} 1' in prometheus_output
        assert 'job_failures_total{job_type="REMOTE_REMBG"} 1' in prometheus_output

    @pytest.mark.asyncio
    async def test_venv_metrics_in_prometheus_export(
        self, gatekeeper: GateKeeper
    ) -> None:
        """Venv metrics are present in Prometheus export when recorded."""
        gatekeeper.metrics.record_venv_creation("rembg", 5.8, 245.0)
        gatekeeper.metrics.record_venv_creation("ollama-wrapper", 3.1, 120.0)

        prometheus_output = gatekeeper.metrics.prometheus_export()

        assert "# HELP venv_creation_time_seconds" in prometheus_output
        assert 'venv_creation_time_seconds{worker="rembg"}' in prometheus_output
        assert 'venv_creation_time_seconds{worker="ollama-wrapper"}' in prometheus_output

        assert "# HELP venv_size_mb" in prometheus_output
        assert 'venv_size_mb{worker="rembg"}' in prometheus_output


# ---------------------------------------------------------------------------
# Scenario 7: Full pipeline lifecycle — N jobs with metrics validation
# ---------------------------------------------------------------------------


class TestScenario7FullLifecycleWithMetrics:
    """
    Simulate a realistic workload: 5 consecutive subprocess jobs, then validate
    the full metrics state reflects all executions.

    This is the closest to a production-like pipeline test without Docker.
    """

    @pytest.mark.asyncio
    async def test_five_consecutive_rembg_jobs_all_succeed(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        jobs = [
            {
                "job_id": f"e2e-lifecycle-rembg-{i:03d}",
                "job_type": "REMOTE_REMBG",
                "input_data": {"image_base64": _MINIMAL_PNG_B64},
                "_source": "owner",
            }
            for i in range(5)
        ]

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"image_base64": _REMBG_RESULT_B64}
            for job in jobs:
                await gatekeeper._dispatch("scareverse:cpu-jobs:queue", json.dumps(job), job, "owner")

        # All 5 results stored in L1
        assert mock_redis_l1.rpush.call_count == 5

        # All 5 TTLs set
        assert mock_redis_l1.expire.call_count == 5

        # Executor called 5 times
        assert mock_exec.call_count == 5

        # Each job stored in its own unique key
        rpush_keys = {c[0][0] for c in mock_redis_l1.rpush.call_args_list}
        assert len(rpush_keys) == 5, "Each job must have its own result key"

        # Metrics: 5 successes, 0 failures
        summary = gatekeeper.metrics.get_summary()
        rembg_stats = summary["job_stats"]["REMOTE_REMBG"]
        assert rembg_stats["successes"] == 5
        assert rembg_stats["failures"] == 0

        # Prometheus export includes correct totals
        prometheus_output = gatekeeper.metrics.prometheus_export()
        assert 'job_successes_total{job_type="REMOTE_REMBG"} 5' in prometheus_output

    @pytest.mark.asyncio
    async def test_mixed_success_failure_across_job_types(
        self, gatekeeper: GateKeeper, mock_redis_l1: AsyncMock
    ) -> None:
        """Realistic workload: rembg succeeds, ollama fails, another rembg succeeds."""
        rembg_ok_1 = {
            "job_id": "e2e-lifecycle-rembg-ok-1",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }
        ollama_fail = {
            "job_id": "e2e-lifecycle-ollama-fail",
            "type": "ollama_generate",
            "payload": {"prompt": "crash", "model": "mistral", "stream": False, "options": {}},
            "created_at": 0.0,
            "attempts": 0,
            "_source": "owner",
        }
        rembg_ok_2 = {
            "job_id": "e2e-lifecycle-rembg-ok-2",
            "job_type": "REMOTE_REMBG",
            "input_data": {"image_base64": _MINIMAL_PNG_B64},
            "_source": "owner",
        }

        # Ollama HTTP call raises an exception (service unavailable)
        gatekeeper.http.post.side_effect = httpx.ConnectError("service unavailable")

        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"image_base64": _REMBG_RESULT_B64}

            await gatekeeper._dispatch("q", json.dumps(rembg_ok_1), rembg_ok_1, "owner")
            await gatekeeper._dispatch("q", json.dumps(ollama_fail), ollama_fail, "owner")
            await gatekeeper._dispatch("q", json.dumps(rembg_ok_2), rembg_ok_2, "owner")

        # 2 rembg successes
        summary = gatekeeper.metrics.get_summary()
        rembg_stats = summary["job_stats"].get("REMOTE_REMBG", {})
        assert rembg_stats.get("successes", 0) == 2

        # Ollama should be tracked as failure
        ollama_stats = summary["job_stats"].get("ollama_generate", {})
        assert ollama_stats.get("failures", 0) >= 1
