"""
GateKeeper Worker – Main Entry Point.

Multi-source job dispatcher with owner-first scheduling.

Responsibilities:
- Connect to Redis L1 (ScareRunner/owner) and Redis L2 (CentralHub/global).
- BRPOP from L1 first (short timeout), then L2 (long timeout).
- Parse job payload and route to the correct atomic worker via HTTP POST.
- Persist job result / error back to Redis L2.
- Run ResourceOrchestrator monitoring loop concurrently.
- Publish heartbeat to Redis L1.
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
import redis.asyncio as aioredis

import config
from centralhub_redis_client import CentralHubRedisClient
from pooling import MultiSourcePooler
from orchestrator import ResourceOrchestrator

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shutdown event (shared across tasks)
# ---------------------------------------------------------------------------

_shutdown_event = asyncio.Event()


def _handle_signal(sig: int, _frame: Any) -> None:
    logger.info("Signal %d received – initiating graceful shutdown", sig)
    _shutdown_event.set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_redis(host: str, port: int, password: str, db: int) -> aioredis.Redis:
    """Construct an async Redis client."""
    kwargs: Dict[str, Any] = {
        "host": host,
        "port": port,
        "db": db,
        "decode_responses": True,
        "socket_connect_timeout": 10,
        "socket_keepalive": True,
    }
    if password:
        kwargs["password"] = password
    return aioredis.Redis(**kwargs)


# ---------------------------------------------------------------------------
# GateKeeper
# ---------------------------------------------------------------------------


class GateKeeper:
    """
    Central dispatcher that pulls jobs from dual Redis sources and routes
    them to stateless atomic workers via HTTP.
    """

    def __init__(
        self,
        redis_l1: aioredis.Redis,
        redis_l2: CentralHubRedisClient,
        http_client: httpx.AsyncClient,
    ):
        self.redis_l1 = redis_l1
        self.redis_l2 = redis_l2
        self.http = http_client
        self.pooler = MultiSourcePooler(redis_l1, redis_l2)
        self.orchestrator = ResourceOrchestrator(redis_l1)
        self.worker_id = config.WORKER_ID

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the dispatcher loop and background tasks."""
        logger.info("GateKeeper %s starting up", self.worker_id)
        logger.info("L1: %s:%d  L2: %s (via CentralHub HTTP)", config.REDIS_L1_HOST, config.REDIS_L1_PORT, config.CENTRALHUB_URL)
        logger.info("Queues L1: %s", config.ALL_QUEUES_L1)
        logger.info("Queues L2: %s", config.ALL_QUEUES_L2)

        tasks = [
            asyncio.create_task(self._job_loop(), name="job_loop"),
            asyncio.create_task(self._heartbeat_loop(), name="heartbeat"),
            asyncio.create_task(
                self.orchestrator.monitor_and_publish(), name="orchestrator"
            ),
        ]
        # Wait until shutdown
        await _shutdown_event.wait()
        logger.info("Shutdown requested – cancelling tasks")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("GateKeeper stopped")

    # ------------------------------------------------------------------
    # Job Loop
    # ------------------------------------------------------------------

    async def _job_loop(self) -> None:
        """Continuously dequeue and dispatch jobs."""
        while not _shutdown_event.is_set():
            queue_name, raw_job, source = await self.pooler.next_job()
            if raw_job is None:
                continue
            try:
                job = json.loads(raw_job)
                job["_source"] = source
                # Support both "job_type" (GateKeeper-native) and "type" (backend router format)
                job_type = job.get("job_type") or job.get("type", "?")
                logger.info(
                    "Dispatching job_id=%s type=%s source=%s",
                    job.get("job_id", "?"),
                    job_type,
                    source,
                )
                await self._dispatch(queue_name, raw_job, job, source)
            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON payload: %s – %s", exc, raw_job[:200])
                await self.pooler.push_to_dead_letter(raw_job)
            except Exception as exc:
                logger.error("Unexpected error processing job: %s", exc, exc_info=True)

    async def _dispatch(
        self,
        queue_name: str,
        raw_job: str,
        job: Dict[str, Any],
        source: str,
    ) -> None:
        """
        Route job to the appropriate atomic worker, handle response,
        and persist result to Redis.

        For standard job types: persists to Redis L2 via HSET (GateKeeper-native).
        For job types with result_storage="rpush_l1": persists to Redis L1 via RPUSH
        so that backend routers can retrieve results via BRPOP.
        """
        # Support both "job_type" (GateKeeper-native) and "type" (backend router format)
        job_type = job.get("job_type") or job.get("type", "")
        job_id = job.get("job_id", "unknown")
        route = config.JOB_TYPES_CONFIG.get(job_type)

        if route is None:
            logger.error("Unknown job_type=%s – sending to dead-letter", job_type)
            await self.pooler.push_to_dead_letter(raw_job)
            return

        endpoint = f"{route['endpoint']}/process"
        timeout = route.get("timeout", config.HTTP_REQUEST_TIMEOUT)
        retries = 0

        while retries <= config.WORKER_MAX_RETRIES:
            try:
                response = await self.http.post(
                    endpoint,
                    json=job,
                    timeout=httpx.Timeout(timeout, connect=config.HTTP_CONNECT_TIMEOUT),
                )

                if response.status_code == 200:
                    await self._persist_success(job_id, response.json(), source, job_type)
                    return

                # 4xx → permanent failure
                if 400 <= response.status_code < 500:
                    logger.error(
                        "Job %s permanent failure (HTTP %d): %s",
                        job_id,
                        response.status_code,
                        response.text[:500],
                    )
                    await self._persist_error(
                        job_id, f"HTTP {response.status_code}", source, job_type
                    )
                    await self.pooler.push_to_dead_letter(raw_job)
                    return

                # 5xx → retriable
                logger.warning(
                    "Job %s worker error (HTTP %d) retry %d/%d",
                    job_id,
                    response.status_code,
                    retries,
                    config.WORKER_MAX_RETRIES,
                )

            except httpx.TimeoutException:
                logger.warning(
                    "Job %s timed out after %ds (retry %d/%d)",
                    job_id,
                    timeout,
                    retries,
                    config.WORKER_MAX_RETRIES,
                )
            except httpx.ConnectError as exc:
                logger.warning(
                    "Cannot reach worker for job %s: %s (retry %d/%d)",
                    job_id,
                    exc,
                    retries,
                    config.WORKER_MAX_RETRIES,
                )

            retries += 1
            if retries <= config.WORKER_MAX_RETRIES:
                delay = min(
                    config.WORKER_RETRY_DELAY * (2 ** (retries - 1)),
                    60.0,  # cap at 60 s
                )
                await asyncio.sleep(delay)

        # Max retries exceeded
        logger.error("Job %s exceeded max retries – dead-letter", job_id)
        await self._persist_error(job_id, "max_retries_exceeded", source, job_type)
        await self.pooler.push_to_dead_letter(raw_job)

    # ------------------------------------------------------------------
    # Result Persistence
    # ------------------------------------------------------------------

    async def _persist_success(
        self,
        job_id: str,
        result: Dict[str, Any],
        source: str,
        job_type: str = "",
    ) -> None:
        """
        Persist a successful job result.

        For job types with result_storage="rpush_l1" (e.g. ollama_generate,
        sd_generate): RPUSH the result JSON to Redis L1 so the backend router
        can BRPOP it directly from the same result key it expects.

        For all other job types: HSET the result to Redis L2 (GateKeeper-native).
        """
        route = config.JOB_TYPES_CONFIG.get(job_type, {})
        result_storage = route.get("result_storage", "hset_l2")

        if result_storage == "rpush_l1":
            prefix = route.get("result_key_prefix", config.JOB_STATE_KEY_PREFIX)
            ttl = route.get("result_key_ttl", config.JOB_STATE_TTL_SECONDS)
            key = f"{prefix}:{job_id}"
            try:
                await self.redis_l1.rpush(key, json.dumps(result))
                await self.redis_l1.expire(key, ttl)
                logger.info(
                    "Job %s completed – result RPUSH to L1 key=%s (TTL %ds)",
                    job_id,
                    key,
                    ttl,
                )
            except Exception as exc:
                logger.error("Failed to RPUSH result for job %s: %s", job_id, exc)
        else:
            key = f"{config.JOB_STATE_KEY_PREFIX}:{job_id}"
            try:
                await self.redis_l2.hset(
                    key,
                    mapping={
                        "status": "completed",
                        "result": json.dumps(result),
                        "timestamp": _utcnow_iso(),
                        "source": source,
                        "worker_id": self.worker_id,
                    },
                )
                await self.redis_l2.expire(key, config.JOB_STATE_TTL_SECONDS)
                logger.info("Job %s completed – result persisted to L2", job_id)
            except Exception as exc:
                logger.error("Failed to persist success for job %s: %s", job_id, exc)

    async def _persist_error(
        self,
        job_id: str,
        error_msg: str,
        source: str,
        job_type: str = "",
    ) -> None:
        """
        Persist a failed job result.

        For job types with result_storage="rpush_l1": RPUSH a structured error
        JSON to Redis L1 so the backend router receives a parseable error response.

        For all other job types: HSET the error to Redis L2.
        """
        route = config.JOB_TYPES_CONFIG.get(job_type, {})
        result_storage = route.get("result_storage", "hset_l2")

        if result_storage == "rpush_l1":
            prefix = route.get("result_key_prefix", config.JOB_STATE_KEY_PREFIX)
            ttl = route.get("result_key_ttl", config.JOB_STATE_TTL_SECONDS)
            key = f"{prefix}:{job_id}"
            error_result = {"status": "error", "error": error_msg}
            try:
                await self.redis_l1.rpush(key, json.dumps(error_result))
                await self.redis_l1.expire(key, ttl)
            except Exception as exc:
                logger.error("Failed to RPUSH error for job %s: %s", job_id, exc)
        else:
            key = f"{config.JOB_STATE_KEY_PREFIX}:{job_id}"
            try:
                await self.redis_l2.hset(
                    key,
                    mapping={
                        "status": "failed",
                        "error": error_msg,
                        "timestamp": _utcnow_iso(),
                        "source": source,
                        "worker_id": self.worker_id,
                    },
                )
                await self.redis_l2.expire(key, config.JOB_STATE_TTL_SECONDS)
            except Exception as exc:
                logger.error("Failed to persist error for job %s: %s", job_id, exc)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Publish heartbeat to Redis L1 at regular intervals."""
        key = f"state:worker:{self.worker_id}:heartbeat"
        while not _shutdown_event.is_set():
            try:
                await self.redis_l1.set(
                    key,
                    json.dumps(
                        {
                            "worker_id": self.worker_id,
                            "status": "running",
                            "timestamp": _utcnow_iso(),
                        }
                    ),
                    ex=config.WORKER_HEARTBEAT_INTERVAL * 3,
                )
            except Exception as exc:
                logger.warning("Heartbeat publish failed: %s", exc)
            await asyncio.sleep(config.WORKER_HEARTBEAT_INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    redis_l1 = _build_redis(
        config.REDIS_L1_HOST,
        config.REDIS_L1_PORT,
        config.REDIS_L1_PASSWORD,
        config.REDIS_L1_DB,
    )
    redis_l2_client = CentralHubRedisClient(
        auth_token=config.CENTRALHUB_SERVICE_TOKEN,
        base_url=config.CENTRALHUB_URL,
        # HTTP client timeout must exceed the BRPOP long-poll timeout so that
        # the underlying connection is never dropped before the server responds.
        # Adding a 10-second buffer accounts for network latency.
        timeout=float(config.BRPOP_L2_TIMEOUT) + 10,
    )

    async with httpx.AsyncClient() as http_client:
        gatekeeper = GateKeeper(redis_l1, redis_l2_client, http_client)
        await gatekeeper.run()

    await redis_l1.aclose()
    await redis_l2_client.close()


if __name__ == "__main__":
    asyncio.run(main())
