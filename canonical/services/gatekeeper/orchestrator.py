"""
Resource Orchestrator for GateKeeper.

Reads host telemetry from Redis L1 and publishes orchestration commands
for scale-up / scale-down decisions. No Docker socket access required –
GateKeeper is a pure decision engine.

Phase 1: Commands are published to Redis L1 for a separate Launcher
         process (Phase 2) to execute.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import redis.asyncio as aioredis

import config

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class ResourceOrchestrator:
    """
    Phase 1 resource orchestrator.

    Reads telemetry published by ``scripts/telemetry_publisher.py`` from
    Redis L1, inspects queue depths, and publishes scale commands to
    ``commands:gatekeeper:queue`` for the Phase 2 Launcher to execute.
    """

    def __init__(self, redis_l1: aioredis.Redis):
        self.redis_l1 = redis_l1
        self.commands_queue = config.COMMANDS_QUEUE

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def monitor_and_publish(self) -> None:
        """
        Continuous monitoring loop.

        Iterates over all known L1 queues (derived from job-type configs),
        reads telemetry + queue depths every 5 seconds and publishes
        orchestration commands when scale-up or scale-down is warranted.
        """
        while True:
            try:
                telemetry = await self.get_telemetry()
                if telemetry is None:
                    logger.warning("No telemetry available yet – waiting...")
                    await asyncio.sleep(2)
                    continue

                vram_free = telemetry.get("vram_free_mb", 0)
                ram_free = telemetry.get("ram_free_mb", 0)

                # Dynamically iterate all queues discovered from job-type configs.
                for queue_name in config.ALL_QUEUES_L1:
                    queue_depth = await self.get_queue_depth(queue_name)

                    logger.info(
                        "Telemetry state: queue=%s depth=%d VRAM=%dMB RAM=%dMB",
                        queue_name,
                        queue_depth,
                        vram_free,
                        ram_free,
                    )

                    await self.orchestrate_workers(queue_name, queue_depth, vram_free, ram_free)

            except Exception as exc:
                logger.error("Monitoring loop error: %s", exc)

            await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Orchestration Decisions
    # ------------------------------------------------------------------

    async def orchestrate_workers(
        self,
        queue_name: str,
        queue_depth: int,
        vram_free: int,
        ram_free: int,
    ) -> None:
        """
        Evaluate resource state for a given queue and publish scale commands.

        Dynamically finds all workers that serve ``queue_name`` by reading
        ``config.JOB_TYPES_CONFIG``.  The ``queue_type`` field on each
        job-type ("cpu" or "gpu") drives which resource threshold is checked:

        - ``queue_type == "gpu"``  → check ``vram_free > SCALE_UP_VRAM_MIN_MB``
        - ``queue_type == "cpu"``  → check ``ram_free > SCALE_UP_RAM_MIN_MB``

        Scale-up criteria:  queue backed up AND sufficient resource available.
        Scale-down criteria: queue empty AND worker idle beyond threshold.
        """
        # Collect unique workers that serve this queue and resolve queue_type.
        workers_for_queue: Set[str] = set()
        queue_type: str = "cpu"  # default if no job-type declares otherwise

        seen_names: Set[str] = set()
        queue_type_resolved: bool = False  # use the first matching entry for queue_type

        for job_name, job_cfg in config.JOB_TYPES_CONFIG.items():
            if job_cfg.get("queue_l1") != queue_name:
                continue

            # Avoid reprocessing the same entry via alias keys.
            canonical_worker = job_cfg.get("worker_name", job_name)
            if canonical_worker in seen_names:
                continue
            seen_names.add(canonical_worker)

            # queue_type is taken from the first matching job-type.  All job-types
            # that share the same queue should declare the same queue_type (cpu vs gpu).
            if not queue_type_resolved:
                queue_type = job_cfg.get("queue_type", "cpu")
                queue_type_resolved = True

            # Resolve the actual worker/service name for START/STOP commands.
            if job_cfg.get("execution_model") == "subprocess":
                # subprocess worker_name is derived from the worker path (e.g. "rembg").
                worker_name = job_cfg.get("worker_name", "")
            else:
                # Service workers: prefer the declared service_name ("ollama",
                # "stable-diffusion", "instantmesh") over the generic job-type name.
                worker_name = job_cfg.get("service_name") or job_cfg.get("worker_name", "")

            if worker_name:
                workers_for_queue.add(worker_name)

        if not workers_for_queue:
            logger.debug("No workers configured for queue %s – skipping", queue_name)
            return

        # Choose resource threshold based on queue_type.
        if queue_type == "gpu":
            resource_ok = vram_free > config.SCALE_UP_VRAM_MIN_MB
        else:
            resource_ok = ram_free > config.SCALE_UP_RAM_MIN_MB

        logger.debug(
            "Orchestrating queue=%s queue_type=%s depth=%d resource_ok=%s workers=%s",
            queue_name,
            queue_type,
            queue_depth,
            resource_ok,
            workers_for_queue,
        )

        for worker_name in workers_for_queue:
            worker_running = await self.is_worker_running(worker_name)

            # Scale up: queue backed up + resources available
            if (
                queue_depth > config.SCALE_UP_QUEUE_DEPTH
                and resource_ok
                and not worker_running
            ):
                logger.info(
                    "Decision: START_WORKER %s (queue=%s depth=%d queue_type=%s)",
                    worker_name,
                    queue_name,
                    queue_depth,
                    queue_type,
                )
                await self.publish_command(
                    {
                        "cmd": "START_WORKER",
                        "worker": worker_name,
                        "reason": f"queue_depth={queue_depth}",
                        "queue_type": queue_type,
                        "resources": {
                            "vram_free_mb": vram_free,
                            "ram_free_mb": ram_free,
                        },
                        "timestamp": _utcnow().isoformat(),
                    }
                )

            # Scale down: queue empty + worker idle beyond threshold
            elif queue_depth == 0 and worker_running:
                last_activity = await self.get_worker_last_activity(worker_name)
                idle_seconds = (_utcnow() - last_activity).total_seconds()

                if idle_seconds > config.SCALE_DOWN_IDLE_SECONDS:
                    logger.info(
                        "Decision: STOP_WORKER %s (idle=%.0fs)", worker_name, idle_seconds
                    )
                    await self.publish_command(
                        {
                            "cmd": "STOP_WORKER",
                            "worker": worker_name,
                            "reason": "idle_timeout",
                            "idle_time_seconds": idle_seconds,
                            "timestamp": _utcnow().isoformat(),
                        }
                    )

    # ------------------------------------------------------------------
    # Redis Helpers
    # ------------------------------------------------------------------

    async def get_telemetry(self) -> Optional[Dict]:
        """
        Fetch host telemetry from Redis L1.

        Returns:
            Parsed telemetry dict, or None if not yet published / stale.
        """
        try:
            raw = await self.redis_l1.get(config.TELEMETRY_KEY)
            if raw:
                return json.loads(raw)
            return None
        except Exception as exc:
            logger.error("Failed to fetch telemetry: %s", exc)
            return None

    async def publish_command(self, cmd: Dict) -> None:
        """Push an orchestration command to Redis L1 for the Launcher."""
        try:
            await self.redis_l1.lpush(self.commands_queue, json.dumps(cmd))
            logger.debug("Command published: %s for %s", cmd["cmd"], cmd["worker"])
        except Exception as exc:
            logger.error("Failed to publish command: %s", exc)

    async def is_worker_running(self, worker_name: str) -> bool:
        """Check worker running status via Redis L1 state key."""
        try:
            raw = await self.redis_l1.get(
                f"{config.WORKER_STATE_KEY_PREFIX}:{worker_name}"
            )
            if raw:
                state = json.loads(raw)
                return state.get("status") == "running"
            return False
        except Exception as exc:
            logger.error("Failed to check worker state for %s: %s", worker_name, exc)
            return False

    async def get_worker_last_activity(self, worker_name: str) -> datetime:
        """
        Get last activity timestamp for a worker from Redis L1.

        Falls back to current UTC time if state is unavailable.
        """
        try:
            raw = await self.redis_l1.get(
                f"{config.WORKER_STATE_KEY_PREFIX}:{worker_name}"
            )
            if raw:
                state = json.loads(raw)
                ts = state.get("last_activity")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                    except ValueError:
                        logger.warning(
                            "Malformed last_activity timestamp for %s: %r",
                            worker_name,
                            ts,
                        )
                        return _utcnow()
                    # Ensure timezone-aware
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
        except Exception as exc:
            logger.error(
                "Failed to get last activity for %s: %s", worker_name, exc
            )
        return _utcnow()

    async def get_queue_depth(self, queue_name: str) -> int:
        """Return the current depth of a Redis list (queue)."""
        try:
            return await self.redis_l1.llen(queue_name)
        except Exception as exc:
            logger.error("Failed to get queue depth for %s: %s", queue_name, exc)
            return 0
