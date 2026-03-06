"""
Tests for GateKeeper multi-source pooling (owner-first scheduling).
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Make gatekeeper module importable without a package install
sys.path.insert(0, str(Path(__file__).parent.parent / "gatekeeper"))

from pooling import MultiSourcePooler  # noqa: E402


@pytest.fixture
def pooler(mock_redis_l1, mock_redis_l2):
    return MultiSourcePooler(
        redis_l1=mock_redis_l1,
        redis_l2=mock_redis_l2,
        queues_l1=["scareverse:rembg-jobs:queue"],
        queues_l2=["scareverse:rembg-jobs:queue"],
    )


# ---------------------------------------------------------------------------
# Owner-first scheduling
# ---------------------------------------------------------------------------


class TestOwnerFirstScheduling:
    """L1 is always checked before L2."""

    @pytest.mark.asyncio
    async def test_l1_job_returned_when_available(self, pooler, mock_redis_l1, rembg_job):
        """When L1 has a job, return it as 'owner' without touching L2."""
        raw = json.dumps(rembg_job)
        mock_redis_l1.brpop.return_value = ("scareverse:rembg-jobs:queue", raw)

        queue, job_raw, source = await pooler.next_job()

        assert source == "owner"
        assert queue == "scareverse:rembg-jobs:queue"
        assert job_raw == raw
        # L2 must NOT have been consulted
        pooler.redis_l2.brpop.assert_not_called()

    @pytest.mark.asyncio
    async def test_l2_job_returned_when_l1_empty(self, pooler, mock_redis_l1, mock_redis_l2, rembg_job):
        """When L1 is empty, fall through to L2 and return 'global'."""
        mock_redis_l1.brpop.return_value = None  # L1 empty
        raw = json.dumps(rembg_job)
        mock_redis_l2.brpop.return_value = ("scareverse:rembg-jobs:queue", raw)

        queue, job_raw, source = await pooler.next_job()

        assert source == "global"
        assert job_raw == raw

    @pytest.mark.asyncio
    async def test_no_job_when_both_empty(self, pooler, mock_redis_l1, mock_redis_l2):
        """When both L1 and L2 are empty, return (None, None, '')."""
        mock_redis_l1.brpop.return_value = None
        mock_redis_l2.brpop.return_value = None

        queue, job_raw, source = await pooler.next_job()

        assert queue is None
        assert job_raw is None
        assert source == ""

    @pytest.mark.asyncio
    async def test_l1_error_falls_through_to_l2(self, pooler, mock_redis_l1, mock_redis_l2, rembg_job):
        """L1 connection error should not crash – falls through to L2."""
        mock_redis_l1.brpop.side_effect = ConnectionError("L1 down")
        raw = json.dumps(rembg_job)
        mock_redis_l2.brpop.return_value = ("scareverse:rembg-jobs:queue", raw)

        queue, job_raw, source = await pooler.next_job()

        assert source == "global"
        assert job_raw == raw

    @pytest.mark.asyncio
    async def test_both_errors_return_empty(self, pooler, mock_redis_l1, mock_redis_l2):
        """Both L1 and L2 errors return empty tuple without raising."""
        mock_redis_l1.brpop.side_effect = ConnectionError("L1 down")
        mock_redis_l2.brpop.side_effect = ConnectionError("L2 down")

        queue, job_raw, source = await pooler.next_job()

        assert queue is None
        assert job_raw is None


# ---------------------------------------------------------------------------
# Requeue
# ---------------------------------------------------------------------------


class TestRequeue:
    @pytest.mark.asyncio
    async def test_owner_job_requeued_to_l1(self, pooler, mock_redis_l1):
        """Owner jobs are always requeued back to L1."""
        await pooler.requeue_job("scareverse:rembg-jobs:queue", '{"job_id":"x"}', "owner")
        mock_redis_l1.lpush.assert_called_once_with(
            "scareverse:rembg-jobs:queue", '{"job_id":"x"}'
        )

    @pytest.mark.asyncio
    async def test_global_job_requeued_to_l2(self, pooler, mock_redis_l1, mock_redis_l2):
        """Global jobs are always requeued back to L2."""
        await pooler.requeue_job("scareverse:rembg-jobs:queue", '{"job_id":"y"}', "global")
        mock_redis_l2.lpush.assert_called_once_with(
            "scareverse:rembg-jobs:queue", '{"job_id":"y"}'
        )

    @pytest.mark.asyncio
    async def test_push_to_dead_letter(self, pooler, mock_redis_l1):
        """Dead-letter jobs land on the configured dead-letter queue in L1."""
        raw = '{"job_id":"dead"}'
        await pooler.push_to_dead_letter(raw)
        # lpush called with the dead-letter queue name
        call_args = mock_redis_l1.lpush.call_args
        assert "dead-letter" in call_args[0][0]
        assert call_args[0][1] == raw
