"""
Owner-First Multi-Source Job Pooling for GateKeeper.

Implements owner-first scheduling: L1 (ScareRunner local/owner) is checked
first with a short timeout. If empty, blocks on L2 (CentralHub global) with
a longer timeout. This ensures the local node's own jobs are prioritised.
"""

import asyncio
import logging
from typing import Any, Optional, Tuple

import redis.asyncio as aioredis

import config

logger = logging.getLogger(__name__)


class MultiSourcePooler:
    """
    Owner-first multi-source job pooler.

    Strategy:
    1. BRPOP L1 (owner queue) with short timeout → fast non-blocking check.
    2. If L1 empty, BRPOP L2 (global queue) with longer timeout → blocks until
       a job arrives from CentralHub.

    This guarantees local (owner) jobs are always processed before global jobs,
    while the worker remains fully blocked/idle when both queues are empty.
    """

    def __init__(
        self,
        redis_l1: aioredis.Redis,
        # redis_l2 accepts either aioredis.Redis (direct TCP) or
        # CentralHubRedisClient (HTTP) – both expose a compatible brpop/lpush
        # interface.  Using Any avoids a circular import; both clients implement
        # the required brpop(keys, timeout) and lpush(key, value) methods.
        redis_l2: Any,
        queues_l1: Optional[list] = None,
        queues_l2: Optional[list] = None,
    ):
        self.redis_l1 = redis_l1
        self.redis_l2 = redis_l2
        self.queues_l1 = queues_l1 or config.ALL_QUEUES_L1
        self.queues_l2 = queues_l2 or config.ALL_QUEUES_L2
        self.brpop_l1_timeout = config.BRPOP_L1_TIMEOUT
        self.brpop_l2_timeout = config.BRPOP_L2_TIMEOUT

    async def next_job(self) -> Tuple[Optional[str], Optional[str], str]:
        """
        Fetch the next job using owner-first scheduling.

        Returns:
            Tuple of (queue_name, raw_job_bytes, source) where source is
            "owner" (L1) or "global" (L2), or (None, None, "") if no job.
        """
        # Step 1: Try L1 (owner/local) – non-blocking short timeout
        try:
            result = await self.redis_l1.brpop(
                self.queues_l1,
                timeout=self.brpop_l1_timeout,
            )
            if result:
                queue_name, raw_job = result
                logger.debug("Job dequeued from L1 (owner): queue=%s", queue_name)
                return queue_name, raw_job, "owner"
        except Exception as exc:
            logger.warning("L1 BRPOP error: %s", exc)

        # Step 2: L1 empty – block on L2 (global)
        try:
            result = await self.redis_l2.brpop(
                self.queues_l2,
                timeout=self.brpop_l2_timeout,
            )
            if result:
                queue_name, raw_job = result
                logger.debug("Job dequeued from L2 (global): queue=%s", queue_name)
                return queue_name, raw_job, "global"
        except Exception as exc:
            logger.warning("L2 BRPOP error: %s", exc)

        return None, None, ""

    async def requeue_job(
        self,
        queue_name: str,
        raw_job: str,
        source: str,
        delay: float = 0.0,
    ) -> None:
        """
        Re-enqueue a job back to its originating Redis instance.

        Args:
            queue_name: Redis list/queue name.
            raw_job: Raw job payload (JSON string).
            source: "owner" (L1) or "global" (L2).
            delay: Optional delay in seconds before re-enqueueing.
        """
        if delay > 0:
            await asyncio.sleep(delay)

        target = self.redis_l1 if source == "owner" else self.redis_l2
        if source not in ("owner", "global"):
            logger.warning(
                "Unexpected source=%r for requeue – defaulting to L2", source
            )
        try:
            await target.lpush(queue_name, raw_job)
            logger.debug("Job requeued to %s queue: %s", source, queue_name)
        except Exception as exc:
            logger.error("Failed to requeue job to %s: %s", source, exc)

    async def push_to_dead_letter(self, raw_job: str) -> None:
        """Send a permanently failed job to the dead-letter queue (L1)."""
        try:
            await self.redis_l1.lpush(config.DEAD_LETTER_QUEUE, raw_job)
            logger.warning("Job sent to dead-letter queue: %s", config.DEAD_LETTER_QUEUE)
        except Exception as exc:
            logger.error("Failed to push to dead-letter: %s", exc)
