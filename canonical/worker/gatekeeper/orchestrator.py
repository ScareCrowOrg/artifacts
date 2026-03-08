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
from typing import Dict, Optional

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

        Reads telemetry + queue depths every 5 seconds and publishes
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
                queue_depth = await self.get_queue_depth(config.CPU_JOBS_QUEUE_L1)

                logger.info(
                    "Telemetry state: VRAM=%dMB RAM=%dMB queue_depth=%d",
                    vram_free,
                    ram_free,
                    queue_depth,
                )

                await self.orchestrate_workers(queue_depth, vram_free, ram_free)

            except Exception as exc:
                logger.error("Monitoring loop error: %s", exc)

            await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Orchestration Decisions
    # ------------------------------------------------------------------

    async def orchestrate_workers(
        self,
        queue_depth: int,
        vram_free: int,
        ram_free: int,
    ) -> None:
        """
        Evaluate resource state and publish scale commands.

        Scale-up criteria:  queue backed up AND sufficient VRAM and RAM.
        Scale-down criteria: queue empty AND worker idle beyond threshold.
        """
        rembg_running = await self.is_worker_running("rembg")

        # Scale up: queue backed up + resources available
        if (
            queue_depth > config.SCALE_UP_QUEUE_DEPTH
            and vram_free > config.SCALE_UP_VRAM_MIN_MB
            and ram_free > config.SCALE_UP_RAM_MIN_MB
            and not rembg_running
        ):
            logger.info(
                "Decision: START_WORKER rembg (queue_depth=%d, vram=%dMB)",
                queue_depth,
                vram_free,
            )
            await self.publish_command(
                {
                    "cmd": "START_WORKER",
                    "worker": "rembg",
                    "reason": f"queue_depth={queue_depth}",
                    "resources": {
                        "vram_free_mb": vram_free,
                        "ram_free_mb": ram_free,
                    },
                    "timestamp": _utcnow().isoformat(),
                }
            )

        # Scale down: queue empty + worker idle beyond threshold
        elif queue_depth == 0 and rembg_running:
            last_activity = await self.get_worker_last_activity("rembg")
            idle_seconds = (_utcnow() - last_activity).total_seconds()

            if idle_seconds > config.SCALE_DOWN_IDLE_SECONDS:
                logger.info(
                    "Decision: STOP_WORKER rembg (idle=%.0fs)", idle_seconds
                )
                await self.publish_command(
                    {
                        "cmd": "STOP_WORKER",
                        "worker": "rembg",
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
