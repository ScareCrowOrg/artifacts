"""
Tests for GateKeeper error handling and dead-letter logic.

Note: rembg is now a subprocess worker (execution_model="subprocess").
      HTTP error handling tests use service workers (ollama_generate, sd_generate).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from .. import config
from ..main import GateKeeper
from ..pooling import MultiSourcePooler


@pytest.fixture
def gatekeeper(mock_redis_l1, mock_redis_l2):
    http = AsyncMock(spec=httpx.AsyncClient)
    return GateKeeper(mock_redis_l1, mock_redis_l2, http)


def _mock_response(status: int, body: dict) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


# ---------------------------------------------------------------------------
# Max retries exceeded (service workers)
# ---------------------------------------------------------------------------


class TestMaxRetriesExceeded:
    @pytest.mark.asyncio
    async def test_max_retries_sends_to_dead_letter(
        self, gatekeeper, mock_redis_l1, ollama_generate_job
    ):
        """After exhausting retries, the job is sent to dead-letter."""
        gatekeeper.http.post.return_value = _mock_response(500, {"detail": "boom"})

        with patch.object(config, "WORKER_MAX_RETRIES", 1), \
             patch.object(config, "WORKER_RETRY_DELAY", 0.0):
            await gatekeeper._dispatch("q", json.dumps(ollama_generate_job), ollama_generate_job, "owner")

        # HTTP calls = 1 initial + 1 retry = 2
        assert gatekeeper.http.post.call_count == 2
        # Dead-letter queue called
        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key

    @pytest.mark.asyncio
    async def test_connect_error_triggers_retry(
        self, gatekeeper, mock_redis_l1, ollama_generate_job
    ):
        """Connection errors are retried just like 5xx."""
        success = _mock_response(
            200, {"status": "success", "data": {"response": "hi"}, "error": None}
        )
        gatekeeper.http.post.side_effect = [
            httpx.ConnectError("worker unreachable"),
            success,
        ]

        with patch.object(config, "WORKER_MAX_RETRIES", 2), \
             patch.object(config, "WORKER_RETRY_DELAY", 0.0):
            await gatekeeper._dispatch("q", json.dumps(ollama_generate_job), ollama_generate_job, "owner")

        assert gatekeeper.http.post.call_count == 2


# ---------------------------------------------------------------------------
# Subprocess worker error handling
# ---------------------------------------------------------------------------


class TestSubprocessWorkerErrors:
    @pytest.mark.asyncio
    async def test_subprocess_timeout_sends_to_dead_letter(
        self, gatekeeper, mock_redis_l1, rembg_job
    ):
        """Subprocess TimeoutError results in dead-letter."""
        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = TimeoutError("Worker exceeded 60s timeout")
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key

    @pytest.mark.asyncio
    async def test_subprocess_value_error_sends_to_dead_letter(
        self, gatekeeper, mock_redis_l1, rembg_job
    ):
        """Subprocess ValueError (permanent failure) results in dead-letter."""
        with patch("main.execute_subprocess_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = ValueError("Worker returned invalid JSON")
            await gatekeeper._dispatch("q", json.dumps(rembg_job), rembg_job, "owner")

        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key


# ---------------------------------------------------------------------------
# Malformed job payloads
# ---------------------------------------------------------------------------


class TestMalformedPayloads:
    @pytest.mark.asyncio
    async def test_invalid_json_sent_to_dead_letter(
        self, gatekeeper, mock_redis_l1, mock_redis_l2
    ):
        """Invalid JSON is sent to dead-letter; no worker HTTP call made."""
        raw_invalid = '{"job_id": "broken'
        gatekeeper.pooler.redis_l1.brpop = AsyncMock(
            return_value=("scareverse:rembg-jobs:queue", raw_invalid)
        )
        gatekeeper.pooler.redis_l1.lpush = mock_redis_l1.lpush

        async def run_one_iteration():
            queue, raw, source = await gatekeeper.pooler.next_job()
            if raw is None:
                return
            try:
                job = json.loads(raw)
                job["_source"] = source
                await gatekeeper._dispatch(queue, raw, job, source)
            except json.JSONDecodeError:
                await gatekeeper.pooler.push_to_dead_letter(raw)

        await run_one_iteration()

        mock_redis_l1.lpush.assert_called()
        dl_key = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in dl_key


# ---------------------------------------------------------------------------
# Dead-letter queue structure
# ---------------------------------------------------------------------------


class TestDeadLetterQueue:
    @pytest.mark.asyncio
    async def test_dead_letter_preserves_original_payload(
        self, gatekeeper, mock_redis_l1, unknown_type_job
    ):
        """The raw job payload is preserved verbatim in dead-letter."""
        raw = json.dumps(unknown_type_job)
        await gatekeeper._dispatch("q", raw, unknown_type_job, "owner")

        dl_payload = mock_redis_l1.lpush.call_args[0][1]
        assert dl_payload == raw

    @pytest.mark.asyncio
    async def test_pooler_push_dead_letter(self, mock_redis_l1, mock_redis_l2):
        pooler = MultiSourcePooler(mock_redis_l1, mock_redis_l2)
        raw = '{"job_id": "test"}'
        await pooler.push_to_dead_letter(raw)

        mock_redis_l1.lpush.assert_called_once()
        key_arg = mock_redis_l1.lpush.call_args[0][0]
        assert "dead-letter" in key_arg
        assert mock_redis_l1.lpush.call_args[0][1] == raw
