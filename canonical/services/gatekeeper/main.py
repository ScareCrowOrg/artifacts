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

# Convert string log level to logging constant (e.g. "DEBUG" → logging.DEBUG)
log_level_str = config.LOG_LEVEL
log_level = getattr(logging, log_level_str.upper(), logging.INFO)

logging.basicConfig(level=log_level, format=config.LOG_FORMAT)
if config.LOG_FORMAT_TYPE == "json":
    configure_json_logging(level=log_level_str)
logger = logging.getLogger(__name__)
logger.info("GateKeeper logging initialized: level=%s", log_level_str)

# Wire persistent file logging when SCARE_LOG_DESTINATION is injected by the builder
try:
    from canonical.shared.log_destination import configure_log_destination as _configure_log_dest
    if not _configure_log_dest(use_json=(config.LOG_FORMAT_TYPE == "json")):
        logger.debug("configure_log_destination returned False — SCARE_LOG_DESTINATION not set or already configured")
except ImportError:
    logger.debug("log_destination utility not available — file logging skipped")

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

        # ── Resource-aware scheduling counters ──
        self._active_gpu_jobs = 0
        self._active_cpu_jobs = 0
        self._max_concurrent_gpu = int(os.environ.get("MAX_CONCURRENT_GPU_JOBS", "1"))
        logger.info(
            "Resource-aware scheduling: MAX_CONCURRENT_GPU_JOBS=%d",
            self._max_concurrent_gpu,
        )

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
            poll_start = time.time()
            queue_name, raw_job, source = await self.pooler.next_job()
            poll_elapsed = time.time() - poll_start

            if raw_job is None:
                logger.warning("⏳ Polling: no jobs available (%.3fs) – waiting 1s before next cycle...", poll_elapsed)
                await asyncio.sleep(1)
                continue

            try:
                parse_start = time.time()
                job = json.loads(raw_job)
                job["_source"] = source
                parse_elapsed = time.time() - parse_start

                job_id = job.get("job_id", "?")
                job_type = job.get("job_type") or job.get("type", "?")

                logger.info(
                    "⏱️  Job polling=%0.3fs parse=%0.3fs | Dispatching job_id=%s type=%s source=%s",
                    poll_elapsed,
                    parse_elapsed,
                    job_id,
                    job_type,
                    source,
                )

                dispatch_start = time.time()
                await self._dispatch(queue_name, raw_job, job, source)
                dispatch_elapsed = time.time() - dispatch_start

                total_elapsed = time.time() - poll_start
                logger.info(
                    "✅ Job %s completed in %.3fs (polling=%.3fs parse=%.3fs dispatch=%.3fs)",
                    job_id,
                    total_elapsed,
                    poll_elapsed,
                    parse_elapsed,
                    dispatch_elapsed,
                )
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
        # Extract user_id for JobConsumer notification — prioritize payload.assignee_id
        # (real UUID) over top-level job.user_id (which may be "cell-script" fixed string).
        user_id = (
            job.get("payload", {}).get("assignee_id")
            or job.get("assignee_id")          # top-level: create_job() spreads **payload into top-level
            or job.get("user_id")
            or ""
        )
        logger.warning(
            "GATEKEEPER-PERMANENTE: extracted user_id='%s' from job. "
            "payload.assignee_id='%s' (preferred), job.user_id='%s'. "
            "If user_id is now a real UUID, the fix is working.",
            user_id,
            job.get("payload", {}).get("assignee_id", "N/A"),
            job.get("user_id", "N/A"),
        )

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

        # ── Cancel check: verify job wasn't cancelled by user ──
        try:
            cancelled = await self.redis_l1.sismember("scareverse:cancelled-jobs", job_id)
            if cancelled:
                logger.info(
                    "PERMANENTE [%s] Job was cancelled by user — skipping execution",
                    job_id,
                )
                await self.redis_l1.srem("scareverse:cancelled-jobs", job_id)  # cleanup
                # Don't persist — job status already "cancelled" in MongoDB
                self.metrics.record_job_execution(job_type, 0, success=False)
                return
        except Exception as _exc:
            # Fail-open: if Redis is unavailable, proceed with execution
            logger.warning(
                "[%s] Failed to check cancelled-jobs set (fail-open) — proceeding: %s",
                job_id, _exc,
            )

        # ── Resource-aware scheduling: check queue_type ──
        queue_type = route.get("queue_type", "cpu")
        if queue_type == "gpu" and self._active_gpu_jobs >= self._max_concurrent_gpu:
            logger.info(
                "PERMANENTE [%s] GPU slot occupied (active=%d, max=%d) — re-enqueueing job=%s",
                job_id, self._active_gpu_jobs, self._max_concurrent_gpu, job_id,
            )
            # Re-enqueue at the end of the queue for later retry
            try:
                await self.redis_l1.rpush(queue_name, raw_job)
                self.metrics.record_job_backpressure(job_type)
                logger.info(
                    "[%s] Job re-enqueued due to GPU backpressure — queue=%s",
                    job_id, queue_name,
                )
            except Exception as _re_exc:
                logger.error(
                    "[%s] Failed to re-enqueue GPU job (discarding): %s",
                    job_id, _re_exc,
                )
            return

        execution_model = route.get("execution_model", "service")
        total_start = time.time()

        # Increment resource counter (decremented in finally)
        _is_gpu = queue_type == "gpu"
        if _is_gpu:
            self._active_gpu_jobs += 1
        else:
            self._active_cpu_jobs += 1

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

                exec_start = time.time()
                result = await execute_subprocess_job(job_type, job_id, input_data, route)
                exec_elapsed = time.time() - exec_start
                logger.info("[%s] ⚙️  Subprocess execution: %.3fs", job_id, exec_elapsed)

                persist_start = time.time()
                self.metrics.record_job_execution(job_type, time.time() - total_start, success=True)
                await self._persist_success(job_id, result, source, job_type, user_id)
                persist_elapsed = time.time() - persist_start
                logger.info("[%s] 💾 Result persistence: %.3fs", job_id, persist_elapsed)
            else:
                # "service" model: HTTP POST
                exec_start = time.time()
                result = await self.service_executor.execute(job_type, job_id, job, route)
                exec_elapsed = time.time() - exec_start
                logger.info("[%s] 🌐 Service execution: %.3fs", job_id, exec_elapsed)

                persist_start = time.time()
                self.metrics.record_job_execution(job_type, time.time() - total_start, success=True)
                await self._persist_success(job_id, result, source, job_type, user_id)
                persist_elapsed = time.time() - persist_start
                logger.info("[%s] 💾 Result persistence: %.3fs", job_id, persist_elapsed)

        except TimeoutError as exc:
            elapsed = time.time() - total_start
            self.metrics.record_job_execution(job_type, elapsed, success=False)
            logger.error("[%s] ⏱️  Timeout: %s (after %.3fs)", job_id, exc, elapsed)
            await self._persist_error(job_id, str(exc), source, job_type, user_id)
            await self.pooler.push_to_dead_letter(raw_job)
        except ValueError as exc:
            elapsed = time.time() - total_start
            self.metrics.record_job_execution(job_type, elapsed, success=False)
            logger.error("[%s] 🚨 Permanent failure: %s (after %.3fs)", job_id, exc, elapsed)
            await self._persist_error(job_id, str(exc), source, job_type, user_id)
            await self.pooler.push_to_dead_letter(raw_job)
        except Exception as exc:
            elapsed = time.time() - total_start
            self.metrics.record_job_execution(job_type, elapsed, success=False)
            logger.error("[%s] ❌ Dispatch failed: %s (after %.3fs)", job_id, exc, elapsed, exc_info=True)
            await self._persist_error(job_id, str(exc), source, job_type, user_id)
            await self.pooler.push_to_dead_letter(raw_job)
        finally:
            # Decrement resource counter (guaranteed even on exception)
            if _is_gpu:
                self._active_gpu_jobs = max(0, self._active_gpu_jobs - 1)
            else:
                self._active_cpu_jobs = max(0, self._active_cpu_jobs - 1)

    # ------------------------------------------------------------------
    # Result Persistence
    # ------------------------------------------------------------------

    async def _persist_success(
        self,
        job_id: str,
        result: Dict[str, Any],
        source: str,
        job_type: str = "",
        user_id: str = "",
    ) -> None:
        route = config.JOB_TYPES_CONFIG.get(job_type, {})
        result_storage = route.get("result_storage", "hset_l2")

        if result_storage == "rpush_l1":
            prefix = route.get("result_key_prefix", config.JOB_STATE_KEY_PREFIX)
            ttl = route.get("result_key_ttl", config.JOB_STATE_TTL_SECONDS)
            key = f"{prefix}:{job_id}"
            # Wrap result in status envelope for backend compatibility
            wrapped_result = {"status": "success", "data": result}
            # PERMANENTE: Log result size to monitor Redis Magro adoption
            # When worker returns content_ref (~200B) instead of base64 (~300KB),
            # this log will show ~99.9% reduction in payload size.
            result_json = json.dumps(wrapped_result)
            has_content_ref = "relative_url" in result or "content_id" in result
            logger.info(
                "[%s] GATEKEEPER-PERSIST: result_size=%d bytes, has_content_ref=%s, job_type=%s",
                job_id, len(result_json), has_content_ref, job_type
            )
            try:
                rpush_start = time.time()
                await self.redis_l1.rpush(key, result_json)
                await self.redis_l1.expire(key, ttl)
                rpush_elapsed = time.time() - rpush_start
                logger.info(
                    "[%s] 📦 RPUSH to L1: %.3fs – key=%s (TTL %ds)",
                    job_id,
                    rpush_elapsed,
                    key,
                    ttl,
                )
            except Exception as exc:
                logger.error("Failed to RPUSH result for job %s: %s", job_id, exc)

            # ── PUBLISH notification for JobConsumer ─────────────────────
            # Non-blocking: if Redis PUBLISH fails, JobConsumer reconciliation
            # loop will recover via periodic scan of stuck "processing" jobs.
            try:
                publish_payload = json.dumps({
                    "job_id": job_id,
                    "result_key": key,
                    "job_type": job_type,
                    "user_id": user_id,
                    "timestamp": time.time(),
                })
                logger.debug(
                    "GATEKEEPER-DIAG: Publishing notification payload: %s",
                    publish_payload,
                )
                await self.redis_l1.publish("scareverse:job-results", publish_payload)
                logger.debug(
                    "[%s] 📢 PUBLISHED job result notification for consumer",
                    job_id,
                )
            except Exception as exc:
                logger.warning(
                    "[%s] ⚠️  Failed to PUBLISH job result notification: %s "
                    "(non-critical — reconciliation loop will recover)",
                    job_id,
                    exc,
                )
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
        user_id: str = "",
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
