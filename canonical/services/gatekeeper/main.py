"""
GateKeeper Service – Main Entry Point.

Unified job dispatcher supporting two execution models:
  - "service": route job via HTTP POST to a long-lived worker service.
  - "subprocess": spawn an isolated Python subprocess for ephemeral workers.

Responsibilities:
- Connect to Redis L1 (ScareRunner/owner) and Redis L2 (CentralHub/global).
- BRPOP from L1 first (short timeout), then L2 (long timeout).
- Parse job payload, determine execution_model from job-type config.
- For "service": delegate to ServiceExecutor (HTTP POST).
- For "subprocess": delegate to JobExecutor (subprocess runner).
- Persist job result / error back to Redis.
- Run ResourceOrchestrator monitoring loop concurrently.
- Publish heartbeat to Redis L1.

IMPORTANT: GateKeeper is a JOB CONSUMER, not a health checker.
- Services (Ollama, SD, InstantMesh) self-register availability via BaseService
  → write state:service:{name}:available to Redis L1 on startup (every 60s)
- Backend/ScareRunner checks service availability when ENQUEUEING jobs
  → via create_job() which reads state:service:{dep}:available
- GateKeeper only consumes jobs from Redis and executes them
  → does NOT probe services or write availability keys
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import redis.asyncio as aioredis

import config
from job_executor import execute_subprocess_job

# Shared utilities from artifacts/canonical/shared (PYTHONPATH=/app/artifacts in Docker)
try:
    from canonical.shared.centralhub_redis_client import CentralHubRedisClient
except ImportError:
    # Fallback for local development (relative import)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))
    from centralhub_redis_client import CentralHubRedisClient
from json_logger import configure_json_logging
from metrics import GateKeeperMetrics
from orchestrator import ResourceOrchestrator
from pooling import MultiSourcePooler
from service_executor import ServiceExecutor
from venv_manager import VenvManager
from worker_discovery import WorkerDiscovery

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
if config.LOG_FORMAT_TYPE == "json":
    configure_json_logging(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shutdown event
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
    Unified job dispatcher: pulls from Redis L1/L2 and routes to the
    correct execution model (HTTP service or subprocess worker).
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
        self.service_executor = ServiceExecutor(http_client)
        self.worker_id = config.WORKER_ID

        # Metrics collection (venv + job execution).
        self.metrics = GateKeeperMetrics()

        # VenvManager: eager startup setup + periodic health checks.
        self.venv_manager = VenvManager(
            workers_path=config.WORKERS_PATH,
            health_check_interval=config.VENV_HEALTH_CHECK_INTERVAL,
            metrics=self.metrics,
        )

        # Worker discovery: scan workers/ directory on startup.
        # This is a synchronous filesystem scan (no I/O wait) so it's
        # intentionally kept in __init__ to ensure workers are available
        # before the first job loop iteration begins.
        self._worker_discovery = WorkerDiscovery(config.WORKERS_PATH)
        self.discovered_workers = self._worker_discovery.discover()
        self._worker_discovery.log_summary()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        logger.info("GateKeeper %s starting up", self.worker_id)
        logger.info(
            "L1: %s:%d  L2: %s (via CentralHub HTTP)",
            config.REDIS_L1_HOST,
            config.REDIS_L1_PORT,
            config.CENTRALHUB_URL,
        )
        logger.info("Workers path: %s", config.WORKERS_PATH)
        logger.info(
            "🔧 Worker Discovery: %d worker(s) loaded: %s",
            len(self.discovered_workers),
            list(self.discovered_workers.keys()),
        )
        logger.info("Queues L1: %s", config.ALL_QUEUES_L1)
        logger.info("Queues L2: %s", config.ALL_QUEUES_L2)

        # Eagerly set up venvs for all discovered subprocess workers.
        logger.info("⚙️  Setting up venvs for all workers...")
        setup_results = await self.venv_manager.setup_all_venvs(
            self.discovered_workers
        )
        self.venv_manager.log_summary()
        failed = [w for w, ok in setup_results.items() if not ok]
        if failed:
            logger.warning("⚠️  Venv setup failed for: %s", ", ".join(failed))

        tasks = [
            asyncio.create_task(self._job_loop(), name="job_loop"),
            asyncio.create_task(self._heartbeat_loop(), name="heartbeat"),
            asyncio.create_task(
                self.orchestrator.monitor_and_publish(), name="orchestrator"
            ),
            asyncio.create_task(
                self.venv_manager.start_health_checks(), name="venv_health_checks"
            ),
            asyncio.create_task(
                self._register_serving_capability(), name="serving_capability"
            ),
        ]
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
        while not _shutdown_event.is_set():
            queue_name, raw_job, source = await self.pooler.next_job()
            if raw_job is None:
                continue
            try:
                job = json.loads(raw_job)
                job["_source"] = source
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

    # ------------------------------------------------------------------
    # Dispatch – execution_model routing
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        queue_name: str,
        raw_job: str,
        job: Dict[str, Any],
        source: str,
    ) -> None:
        """Route job to service executor or subprocess executor based on execution_model."""
        job_type = job.get("job_type") or job.get("type", "")
        job_id = job.get("job_id", "unknown")
        route = config.JOB_TYPES_CONFIG.get(job_type)

        if route is None:
            logger.error("Unknown job_type=%s – sending to dead-letter", job_type)
            await self.pooler.push_to_dead_letter(raw_job)
            return

        execution_model = route.get("execution_model", "service")
        start_time = time.time()

        try:
            if execution_model == "subprocess":
                # Subprocess workers receive a clean input_data dict via stdin.
                # Support both "input_data" (subprocess contract) and "payload"
                # (legacy backend format) for backward compatibility with queued jobs.
                input_data = job.get("input_data") or job.get("payload") or {}
                result = await execute_subprocess_job(job_type, job_id, input_data, route)
                elapsed = time.time() - start_time
                self.metrics.record_job_execution(job_type, elapsed, success=True)
                await self._persist_success(job_id, result, source, job_type)
            else:
                # "service" model: HTTP POST
                result = await self.service_executor.execute(job_type, job_id, job, route)
                elapsed = time.time() - start_time
                self.metrics.record_job_execution(job_type, elapsed, success=True)
                await self._persist_success(job_id, result, source, job_type)

        except TimeoutError as exc:
            elapsed = time.time() - start_time
            self.metrics.record_job_execution(job_type, elapsed, success=False)
            logger.error("[%s] Timeout: %s", job_id, exc)
            await self._persist_error(job_id, str(exc), source, job_type)
            await self.pooler.push_to_dead_letter(raw_job)
        except ValueError as exc:
            elapsed = time.time() - start_time
            self.metrics.record_job_execution(job_type, elapsed, success=False)
            logger.error("[%s] Permanent failure: %s", job_id, exc)
            await self._persist_error(job_id, str(exc), source, job_type)
            await self.pooler.push_to_dead_letter(raw_job)
        except Exception as exc:
            elapsed = time.time() - start_time
            self.metrics.record_job_execution(job_type, elapsed, success=False)
            logger.error("[%s] Dispatch failed: %s", job_id, exc, exc_info=True)
            await self._persist_error(job_id, str(exc), source, job_type)
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

    # ------------------------------------------------------------------
    # Service Registry: capability heartbeat
    # ------------------------------------------------------------------

    async def _register_serving_capability(self) -> None:
        """
        Heartbeat: publish which job-types this GateKeeper can execute.

        Probes each service job-type endpoint to determine local capability.
        Subprocess job-types are always listed (no endpoint to probe).

        Runs every WORKER_HEARTBEAT_INTERVAL seconds with TTL = 3× interval.
        """
        previous_serving_types: Optional[List[str]] = None

        while not _shutdown_event.is_set():
            try:
                serving_types: List[str] = []

                for job_type, job_config in config.JOB_TYPES_CONFIG.items():
                    execution_model = job_config.get("execution_model", "service")

                    if execution_model == "subprocess":
                        serving_types.append(job_type)
                    else:
                        endpoint = job_config.get("endpoint", "")
                        health_path = job_config.get("health_path", "/health")
                        if endpoint and await self._probe_http_health(
                            f"{endpoint.rstrip('/')}{health_path}"
                        ):
                            serving_types.append(job_type)

                key = f"state:gatekeeper:{self.worker_id}:serving_job_types"
                ttl = config.WORKER_HEARTBEAT_INTERVAL * 3
                await self.redis_l1.set(key, json.dumps(serving_types), ex=ttl)

                if previous_serving_types is None:
                    logger.info(
                        "GateKeeper %s capability registered: %s (TTL %ds)",
                        self.worker_id,
                        serving_types,
                        ttl,
                    )
                else:
                    added = [t for t in serving_types if t not in previous_serving_types]
                    removed = [t for t in previous_serving_types if t not in serving_types]
                    if added or removed:
                        logger.info(
                            "GateKeeper %s capability updated – added: %s, removed: %s",
                            self.worker_id,
                            added,
                            removed,
                        )

                previous_serving_types = serving_types

            except Exception as exc:
                logger.warning("Failed to register serving capability: %s", exc)

            await asyncio.sleep(config.WORKER_HEARTBEAT_INTERVAL)

    # ------------------------------------------------------------------
    # Service Availability
    # ------------------------------------------------------------------



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
        timeout=float(config.BRPOP_L2_TIMEOUT) + 10,
    )

    async with httpx.AsyncClient() as http_client:
        gatekeeper = GateKeeper(redis_l1, redis_l2_client, http_client)
        await gatekeeper.run()

    await redis_l1.aclose()
    await redis_l2_client.close()


if __name__ == "__main__":
    asyncio.run(main())
