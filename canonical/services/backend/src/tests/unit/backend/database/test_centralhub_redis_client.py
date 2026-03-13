"""
Unit tests for CentralHubRedisClient – Phase 1.4 brpop via dequeue API.

Tests the HTTP-based Redis interface used by GateKeeper to access Redis L2
through CentralHub without a direct TCP connection.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.clients.centralhub_redis_client import CentralHubRedisClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, body: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.raise_for_status = MagicMock()
    return resp


def _mock_error_response(status_code: int) -> httpx.HTTPStatusError:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = "error"
    return httpx.HTTPStatusError("error", request=MagicMock(), response=resp)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """CentralHubRedisClient with a mocked internal HTTP client."""
    c = CentralHubRedisClient(
        auth_token="test-token",
        base_url="http://centralhub:8080",
    )
    c.client = AsyncMock()
    return c


# ---------------------------------------------------------------------------
# brpop – single queue
# ---------------------------------------------------------------------------


class TestBrpopSingleQueue:
    @pytest.mark.asyncio
    async def test_returns_tuple_on_job_available(self, client):
        """brpop returns (queue_name, raw_json) when a job is available."""
        job_data = {"job_id": "job-001", "type": "ollama_generate"}
        client.client.post.return_value = _mock_response(
            200,
            {"job_id": "job-001", "job_data": job_data},
        )

        result = await client.brpop("scareverse:cpu-jobs:queue", timeout=20)

        assert result is not None
        queue_name, raw = result
        assert queue_name == "scareverse:cpu-jobs:queue"
        parsed = json.loads(raw)
        assert parsed["job_id"] == "job-001"
        assert parsed["type"] == "ollama_generate"

    @pytest.mark.asyncio
    async def test_returns_none_when_queue_empty(self, client):
        """brpop returns None when queue is empty (job_id is None)."""
        client.client.post.return_value = _mock_response(
            200, {"job_id": None, "job_data": None}
        )

        result = await client.brpop("scareverse:cpu-jobs:queue", timeout=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_calls_dequeue_endpoint_with_correct_params(self, client):
        """brpop POSTs to /api/redis/jobs/dequeue with queue_name and timeout."""
        client.client.post.return_value = _mock_response(
            200, {"job_id": None, "job_data": None}
        )

        await client.brpop("scareverse:cpu-jobs:queue", timeout=30)

        client.client.post.assert_called_once_with(
            "/api/redis/jobs/dequeue",
            json={"queue_name": "scareverse:cpu-jobs:queue", "timeout": 30},
        )


# ---------------------------------------------------------------------------
# brpop – list of queues
# ---------------------------------------------------------------------------


class TestBrpopMultipleQueues:
    @pytest.mark.asyncio
    async def test_returns_job_from_first_non_empty_queue(self, client):
        """brpop with list returns from the first queue that yields a job."""
        job_data = {"job_id": "job-3d-001", "type": "instantmesh"}
        # First queue empty, second queue has a job
        client.client.post.side_effect = [
            _mock_response(200, {"job_id": None, "job_data": None}),
            _mock_response(200, {"job_id": "job-3d-001", "job_data": job_data}),
        ]

        result = await client.brpop(
            ["scareverse:cpu-jobs:queue", "scareverse:3d-jobs:queue"],
            timeout=20,
        )

        assert result is not None
        queue_name, raw = result
        assert queue_name == "scareverse:3d-jobs:queue"
        parsed = json.loads(raw)
        assert parsed["job_id"] == "job-3d-001"

    @pytest.mark.asyncio
    async def test_first_queue_checked_non_blocking(self, client):
        """Non-last queues are checked with timeout=0 (non-blocking)."""
        client.client.post.side_effect = [
            _mock_response(200, {"job_id": None, "job_data": None}),
            _mock_response(200, {"job_id": None, "job_data": None}),
        ]

        await client.brpop(
            ["scareverse:cpu-jobs:queue", "scareverse:3d-jobs:queue"],
            timeout=20,
        )

        calls = client.client.post.call_args_list
        # First call: non-blocking (timeout=0)
        assert calls[0][1]["json"]["timeout"] == 0
        # Last call: full timeout
        assert calls[1][1]["json"]["timeout"] == 20

    @pytest.mark.asyncio
    async def test_returns_none_when_all_queues_empty(self, client):
        """brpop returns None when all queues are empty."""
        client.client.post.return_value = _mock_response(
            200, {"job_id": None, "job_data": None}
        )

        result = await client.brpop(
            ["scareverse:cpu-jobs:queue", "scareverse:3d-jobs:queue"],
            timeout=1,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_accepts_tuple_of_keys(self, client):
        """brpop accepts a tuple of queue names, not just a list."""
        client.client.post.return_value = _mock_response(
            200, {"job_id": None, "job_data": None}
        )

        result = await client.brpop(
            ("scareverse:cpu-jobs:queue", "scareverse:3d-jobs:queue"),
            timeout=1,
        )

        assert result is None
        assert client.client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_job_data_as_string_returned_verbatim(self, client):
        """If job_data is already a JSON string, it is returned as-is."""
        job_str = '{"job_id": "job-str", "type": "ollama_generate"}'
        client.client.post.return_value = _mock_response(
            200, {"job_id": "job-str", "job_data": job_str}
        )

        result = await client.brpop("scareverse:cpu-jobs:queue", timeout=1)

        assert result is not None
        queue_name, raw = result
        assert raw == job_str

    @pytest.mark.asyncio
    async def test_brpop_no_double_encoding_for_string_job_data(self, client):
        """brpop must not JSON-encode a job_data value that is already a JSON string.

        CentralHub may return ``job_data`` as a pre-serialised JSON string.
        Applying ``json.dumps()`` again would produce a double-encoded result
        (a JSON string whose value is itself a JSON string), breaking downstream
        ``json.loads()`` calls in the GateKeeper job loop.
        """
        raw_payload = '{"type": "test", "value": "data"}'
        client.client.post.return_value = _mock_response(
            200,
            {"job_id": "job-001", "job_data": raw_payload},
        )

        result = await client.brpop("scareverse:cpu-jobs:queue", timeout=20)
        assert result is not None

        queue_name, raw = result
        # Must be the original string, not double-encoded (not '\"{\\"type\\"...\"')
        assert raw == raw_payload

        # Must be directly parseable without extra unwrapping
        parsed = json.loads(raw)
        assert parsed["type"] == "test"
        assert parsed["value"] == "data"

    @pytest.mark.asyncio
    async def test_http_error_is_propagated(self, client):
        """HTTP errors during dequeue are re-raised to the caller."""
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 503
        error_response.text = "Service Unavailable"
        client.client.post.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=error_response
        )

        with pytest.raises(httpx.HTTPStatusError):
            await client.brpop("scareverse:cpu-jobs:queue", timeout=1)
