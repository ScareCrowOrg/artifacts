"""
Unit tests for the refactored ResourceOrchestrator.

Validates that:
- monitor_and_publish() iterates over ALL_QUEUES_L1 (not a hardcoded queue).
- orchestrate_workers() dynamically finds workers from JOB_TYPES_CONFIG.
- orchestrate_workers() selects the correct resource threshold based on queue_type.
- orchestrate_workers() publishes START_WORKER / STOP_WORKER with the dynamic worker name.
- No hardcoded "rembg" references remain in scaling logic.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_mock() -> AsyncMock:
    """Return an async Redis mock simulating an empty Redis instance.

    - ``get`` returns ``None`` (key not found)
    - ``llen`` returns ``0`` (empty list / queue)
    - ``lpush`` returns ``1`` (successful push)
    """
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.llen = AsyncMock(return_value=0)
    redis.lpush = AsyncMock(return_value=1)
    return redis


def _make_telemetry(vram_mb: int = 8000, ram_mb: int = 16000) -> dict:
    return {"vram_free_mb": vram_mb, "ram_free_mb": ram_mb}


def _make_orchestrator(redis=None):
    """Convenience factory that imports ResourceOrchestrator."""
    from orchestrator import ResourceOrchestrator
    if redis is None:
        redis = _make_redis_mock()
    return ResourceOrchestrator(redis)


# ---------------------------------------------------------------------------
# orchestrate_workers – worker discovery
# ---------------------------------------------------------------------------


class TestOrchestrateWorkersDiscovery:
    """orchestrate_workers finds workers from JOB_TYPES_CONFIG dynamically."""

    async def test_no_workers_for_unknown_queue(self):
        """Unknown queue → no command published."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        with patch("config.JOB_TYPES_CONFIG", {}):
            await orc.orchestrate_workers(
                "scareverse:unknown:queue", queue_depth=5, vram_free=8000, ram_free=16000
            )

        redis.lpush.assert_not_called()

    async def test_finds_subprocess_worker_by_worker_name(self):
        """Subprocess worker: worker_name extracted from path last component."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        fake_config = {
            "rembg_removebackground": {
                "execution_model": "subprocess",
                "queue_type": "cpu",
                "queue_l1": "scareverse:rembg-jobs:queue",
                "worker_name": "rembg",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 0), \
             patch("config.SCALE_UP_RAM_MIN_MB", 1), \
             patch("config.SCALE_UP_VRAM_MIN_MB", 99999):
            await orc.orchestrate_workers(
                "scareverse:rembg-jobs:queue", queue_depth=5, vram_free=0, ram_free=16000
            )

        redis.lpush.assert_called_once()
        published = json.loads(redis.lpush.call_args[0][1])
        assert published["worker"] == "rembg"

    async def test_finds_service_worker_by_service_name(self):
        """Service worker: service_name is used for START_WORKER command."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        fake_config = {
            "sd_generate": {
                "execution_model": "service",
                "queue_type": "gpu",
                "queue_l1": "scareverse:sd-jobs:queue",
                "service_name": "stable-diffusion",
                "worker_name": "sd_generate",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 0), \
             patch("config.SCALE_UP_VRAM_MIN_MB", 1), \
             patch("config.SCALE_UP_RAM_MIN_MB", 1):
            await orc.orchestrate_workers(
                "scareverse:sd-jobs:queue", queue_depth=5, vram_free=8000, ram_free=16000
            )

        redis.lpush.assert_called_once()
        published = json.loads(redis.lpush.call_args[0][1])
        assert published["worker"] == "stable-diffusion"

    async def test_deduplicates_workers_via_aliases(self):
        """Alias keys pointing to the same entry do not produce duplicate commands."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        entry = {
            "execution_model": "subprocess",
            "queue_type": "cpu",
            "queue_l1": "scareverse:rembg-jobs:queue",
            "worker_name": "rembg",
        }
        # Same entry dict referenced from 3 keys (canonical + 2 aliases)
        fake_config = {
            "rembg_removebackground": entry,
            "REMOTE_REMBG": entry,
            "background_removal": entry,
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 0), \
             patch("config.SCALE_UP_RAM_MIN_MB", 1), \
             patch("config.SCALE_UP_VRAM_MIN_MB", 99999):
            await orc.orchestrate_workers(
                "scareverse:rembg-jobs:queue", queue_depth=5, vram_free=0, ram_free=16000
            )

        # Should publish only ONE START_WORKER (worker deduplicated via set)
        assert redis.lpush.call_count == 1


# ---------------------------------------------------------------------------
# orchestrate_workers – resource threshold selection
# ---------------------------------------------------------------------------


class TestOrchestrateWorkersResourceThreshold:
    """orchestrate_workers selects VRAM threshold for GPU jobs, RAM for CPU."""

    async def test_gpu_queue_uses_vram_threshold_scale_up(self):
        """GPU queue: scale up when vram_free > threshold (ram does not matter)."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        fake_config = {
            "sd_generate": {
                "execution_model": "service",
                "queue_type": "gpu",
                "queue_l1": "scareverse:sd-jobs:queue",
                "service_name": "stable-diffusion",
                "worker_name": "sd_generate",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 0), \
             patch("config.SCALE_UP_VRAM_MIN_MB", 4000), \
             patch("config.SCALE_UP_RAM_MIN_MB", 99999):
            # vram_free (8000) > VRAM threshold (4000) → should scale up
            # ram_free (500) < RAM threshold (99999) → would block CPU scaling
            await orc.orchestrate_workers(
                "scareverse:sd-jobs:queue",
                queue_depth=5,
                vram_free=8000,
                ram_free=500,
            )

        redis.lpush.assert_called_once()
        published = json.loads(redis.lpush.call_args[0][1])
        assert published["cmd"] == "START_WORKER"
        assert published["queue_type"] == "gpu"

    async def test_gpu_queue_blocks_scale_up_when_vram_insufficient(self):
        """GPU queue: no scale up when vram_free < threshold."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        fake_config = {
            "sd_generate": {
                "execution_model": "service",
                "queue_type": "gpu",
                "queue_l1": "scareverse:sd-jobs:queue",
                "service_name": "stable-diffusion",
                "worker_name": "sd_generate",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 0), \
             patch("config.SCALE_UP_VRAM_MIN_MB", 4000), \
             patch("config.SCALE_UP_RAM_MIN_MB", 1):
            # vram_free (1000) < VRAM threshold (4000) → should NOT scale up
            await orc.orchestrate_workers(
                "scareverse:sd-jobs:queue",
                queue_depth=5,
                vram_free=1000,
                ram_free=16000,
            )

        redis.lpush.assert_not_called()

    async def test_cpu_queue_uses_ram_threshold_scale_up(self):
        """CPU queue: scale up when ram_free > threshold (vram does not matter)."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        fake_config = {
            "rembg_removebackground": {
                "execution_model": "subprocess",
                "queue_type": "cpu",
                "queue_l1": "scareverse:rembg-jobs:queue",
                "worker_name": "rembg",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 0), \
             patch("config.SCALE_UP_VRAM_MIN_MB", 99999), \
             patch("config.SCALE_UP_RAM_MIN_MB", 4000):
            # ram_free (16000) > RAM threshold (4000) → should scale up
            # vram_free (0) < VRAM threshold (99999) → would block GPU scaling
            await orc.orchestrate_workers(
                "scareverse:rembg-jobs:queue",
                queue_depth=5,
                vram_free=0,
                ram_free=16000,
            )

        redis.lpush.assert_called_once()
        published = json.loads(redis.lpush.call_args[0][1])
        assert published["cmd"] == "START_WORKER"

    async def test_cpu_queue_blocks_scale_up_when_ram_insufficient(self):
        """CPU queue: no scale up when ram_free < threshold."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        fake_config = {
            "rembg_removebackground": {
                "execution_model": "subprocess",
                "queue_type": "cpu",
                "queue_l1": "scareverse:rembg-jobs:queue",
                "worker_name": "rembg",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 0), \
             patch("config.SCALE_UP_VRAM_MIN_MB", 1), \
             patch("config.SCALE_UP_RAM_MIN_MB", 8000):
            # ram_free (2000) < RAM threshold (8000) → should NOT scale up
            await orc.orchestrate_workers(
                "scareverse:rembg-jobs:queue",
                queue_depth=5,
                vram_free=16000,
                ram_free=2000,
            )

        redis.lpush.assert_not_called()


# ---------------------------------------------------------------------------
# orchestrate_workers – scale down
# ---------------------------------------------------------------------------


class TestOrchestrateWorkersScaleDown:
    """Scale-down path: publish STOP_WORKER when queue empty and worker idle."""

    async def test_stop_worker_when_queue_empty_and_idle(self):
        """STOP_WORKER published when queue is empty and worker has been idle."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        # Simulate worker running with last activity 1 hour ago
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        redis.get = AsyncMock(
            return_value=json.dumps({"status": "running", "last_activity": stale_ts})
        )

        fake_config = {
            "rembg_removebackground": {
                "execution_model": "subprocess",
                "queue_type": "cpu",
                "queue_l1": "scareverse:rembg-jobs:queue",
                "worker_name": "rembg",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 5), \
             patch("config.SCALE_DOWN_IDLE_SECONDS", 300):
            await orc.orchestrate_workers(
                "scareverse:rembg-jobs:queue",
                queue_depth=0,
                vram_free=8000,
                ram_free=16000,
            )

        redis.lpush.assert_called_once()
        published = json.loads(redis.lpush.call_args[0][1])
        assert published["cmd"] == "STOP_WORKER"
        assert published["worker"] == "rembg"

    async def test_no_stop_when_worker_not_idle_long_enough(self):
        """STOP_WORKER NOT published when idle_seconds < SCALE_DOWN_IDLE_SECONDS."""
        redis = _make_redis_mock()
        orc = _make_orchestrator(redis)

        # Last activity only 10 seconds ago
        recent_ts = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        redis.get = AsyncMock(
            return_value=json.dumps({"status": "running", "last_activity": recent_ts})
        )

        fake_config = {
            "rembg_removebackground": {
                "execution_model": "subprocess",
                "queue_type": "cpu",
                "queue_l1": "scareverse:rembg-jobs:queue",
                "worker_name": "rembg",
            }
        }
        with patch("config.JOB_TYPES_CONFIG", fake_config), \
             patch("config.SCALE_UP_QUEUE_DEPTH", 5), \
             patch("config.SCALE_DOWN_IDLE_SECONDS", 300):
            await orc.orchestrate_workers(
                "scareverse:rembg-jobs:queue",
                queue_depth=0,
                vram_free=8000,
                ram_free=16000,
            )

        redis.lpush.assert_not_called()


# ---------------------------------------------------------------------------
# monitor_and_publish – queue iteration
# ---------------------------------------------------------------------------


class TestMonitorAndPublish:
    """monitor_and_publish iterates all queues, not a single hardcoded one."""

    async def test_iterates_all_queues_l1(self):
        """monitor_and_publish calls get_queue_depth for every queue in ALL_QUEUES_L1."""
        from orchestrator import ResourceOrchestrator

        redis = _make_redis_mock()
        orc = ResourceOrchestrator(redis)

        queried_queues: list = []
        orchestrated_queues: list = []

        async def fake_get_queue_depth(queue_name: str) -> int:
            queried_queues.append(queue_name)
            return 0

        async def fake_get_telemetry():
            return {"vram_free_mb": 8000, "ram_free_mb": 16000}

        async def fake_orchestrate_workers(queue_name, queue_depth, vram_free, ram_free):
            orchestrated_queues.append(queue_name)

        orc.get_queue_depth = fake_get_queue_depth
        orc.get_telemetry = fake_get_telemetry
        orc.orchestrate_workers = fake_orchestrate_workers

        fake_queues = [
            "scareverse:rembg-jobs:queue",
            "scareverse:ollama-jobs:queue",
            "scareverse:sd-jobs:queue",
            "scareverse:3d-jobs:queue",
        ]

        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                raise asyncio.CancelledError()

        # Run monitor loop for one iteration then cancel via sleep replacement
        with patch("config.ALL_QUEUES_L1", fake_queues), \
             patch("orchestrator.asyncio.sleep", new=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await orc.monitor_and_publish()

        assert set(queried_queues) == set(fake_queues)
        assert set(orchestrated_queues) == set(fake_queues)

    async def test_no_hardcoded_cpu_queue_in_monitor(self):
        """monitor_and_publish does NOT query the old hardcoded CPU_JOBS_QUEUE_L1."""
        from orchestrator import ResourceOrchestrator

        redis = _make_redis_mock()
        orc = ResourceOrchestrator(redis)

        queried_queues: list = []

        async def fake_get_queue_depth(queue_name: str) -> int:
            queried_queues.append(queue_name)
            return 0

        async def fake_get_telemetry():
            return {"vram_free_mb": 8000, "ram_free_mb": 16000}

        async def fake_orchestrate_workers(queue_name, queue_depth, vram_free, ram_free):
            pass

        orc.get_queue_depth = fake_get_queue_depth
        orc.get_telemetry = fake_get_telemetry
        orc.orchestrate_workers = fake_orchestrate_workers

        fake_queues = [
            "scareverse:rembg-jobs:queue",
            "scareverse:ollama-jobs:queue",
        ]

        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                raise asyncio.CancelledError()

        with patch("config.ALL_QUEUES_L1", fake_queues), \
             patch("orchestrator.asyncio.sleep", new=fake_sleep):
            with pytest.raises(asyncio.CancelledError):
                await orc.monitor_and_publish()

        assert "scareverse:cpu-jobs:queue" not in queried_queues
