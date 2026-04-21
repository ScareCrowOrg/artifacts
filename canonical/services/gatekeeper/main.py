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
- Register serving capability (job-types available) to Redis L1.

NOTE: Heartbeat registration moved to heartbeat.py (entrypoint fire-and-forget).

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
    from canonical.shared import redis_client
except ImportError:
    # Fallback for local development (relative import)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))
    from centralhub_redis_client import CentralHubRedisClient
    import redis_client
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
            "L1: %s:%s  L2: %s (via CentralHub HTTP)",
            redis_client.REDIS_L1_HOST,
            redis_client.REDIS_L1_PORT,
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

        # DEBUG: Log complete job structure
        logger.info("[%s] === JOB DISPATCH INSPECTION ===", job_id)
        logger.info("[%s] job_type: %s", job_id, job_type)
        logger.info("[%s] job keys: %s", job_id, list(job.keys()))
        logger.info("[%s] input_data/payload keys: %s", job_id, list(job.get("input_data", job.get("payload", {})).keys()))
        if job.get("input_data"):
            logger.info("[%s] input_data: %s", job_id, json.dumps(job.get("input_data"), default=str)[:1000])
        elif job.get("payload"):
            logger.info("[%s] payload: %s", job_id, json.dumps(job.get("payload"), default=str)[:1000])

        route = config.JOB_TYPES_CONFIG.get(job_type)

        if route is None:
            logger.error("Unknown job_type=%s – sending to dead-letter", job_type)
            await self.pooler.push_to_dead_letter(raw_job)
            return

        execution_model = route.get("execution_model", "service")
        start_time = time.time()

        try:
            if execution_model == "subprocess":
                # Extract input_data from job payload (which may be desempacotar at top level)
                # redis_client.py puts payload keys at top level: {job_id, job_type, user_id, queue, **payload}
                # We need to extract back into input_data for worker_executor
                input_data = job.get("input_data") or job.get("payload") or {}

                # If input_data is empty, try to extract from top-level keys
                # (keys that are not job metadata like job_id, job_type, user_id, queue)
                if not input_data:
                    metadata_keys = {"job_id", "job_type", "user_id", "queue", "_source"}
                    input_data = {k: v for k, v in job.items() if k not in metadata_keys}

                logger.info("[%s] === EXTRACTED INPUT_DATA FOR WORKER ===", job_id)
                logger.info("[%s] extracted input_data keys: %s", job_id, list(input_data.keys()))

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
            # Wrap result in status envelope for backend compatibility
            wrapped_result = {"status": "success", "data": result}
            try:
                await self.redis_l1.rpush(key, json.dumps(wrapped_result))
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
    # Service Availability Check (via Redis L1 heartbeat)
    # ------------------------------------------------------------------

    async def _is_service_available(self, service_name: str) -> bool:
        """Check if a service is available by verifying its heartbeat in Redis L1."""
        try:
            key = f"state:service:{service_name}:available"
            exists = await self.redis_l1.exists(key)
            return bool(exists)
        except Exception as exc:
            logger.warning("Failed to check service availability for %s: %s", service_name, exc)
            return False

    # ------------------------------------------------------------------
    # Service Registry: capability heartbeat
    # ------------------------------------------------------------------

    async def _register_serving_capability(self) -> None:
        """
        Heartbeat: publish which job-types this GateKeeper can execute.

        Checks service job-type availability via Redis L1 heartbeat keys.
        Subprocess job-types are always listed (no heartbeat needed).

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
                        # For service workers: check Redis L1 heartbeat (state:service:{name}:available)
                        service_info = job_config.get("service", {})
                        service_name = service_info.get("name", "")
                        if service_name and await self._is_service_available(service_name):
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

    redis_l1 = await redis_client.get_redis_client()
    # Initialize CentralHub L2 client with resolved token
    logger.info("[main] ▶️ Initializing CentralHubRedisClient...")
    logger.info(f"[main]    URL: {config.CENTRALHUB_URL}")

    token = config.CENTRALHUB_SERVICE_TOKEN
    token_preview = token[:15] if len(token) >= 15 else token
    token_source = "vault" if token != "internal-gatekeeper-token" else "FALLBACK ENV"
    logger.info(f"[main]    Token source: {token_source}")
    logger.info(f"[main]    Token preview (first 15 chars): {token_preview}...")
    logger.info(f"[main]    Token length: {len(token)} chars")

    if token == "internal-gatekeeper-token":
        logger.error("[main] ⚠️ WARNING: Using fallback token - CentralHub will reject requests with 401!")

    redis_l2_client = CentralHubRedisClient(
        auth_token=token,
        base_url=config.CENTRALHUB_URL,
        timeout=float(config.BRPOP_L2_TIMEOUT) + 10,
    )
    logger.info("[main] ✅ CentralHubRedisClient initialized")

    async with httpx.AsyncClient() as http_client:
        gatekeeper = GateKeeper(redis_l1, redis_l2_client, http_client)
        await gatekeeper.run()

    await redis_client.close_redis_client()
    await redis_l2_client.close()


if __name__ == "__main__":
    asyncio.run(main())
