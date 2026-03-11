"""
Standalone Redis L1 client for artifacts/canonical.

Adapted from backend/app/core/redis_client.py to be self-contained
(no relative imports from the backend package). Configuration is read
directly from environment variables.

Used by GateKeeper service and can be imported by any component in
artifacts/canonical/ without depending on the backend package.

Also provides ``create_job()`` – the single source of truth for
owner-first job scheduling (L1 vs CentralHub L2).
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------

REDIS_L1_HOST: str = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB: int = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD: Optional[str] = os.getenv("REDIS_L1_PASSWORD", "scarerunner") or None
REDIS_L1_ENABLED: bool = os.getenv("REDIS_L1_ENABLED", "true").lower() == "true"

# CentralHub fallback for L2 enqueue
CENTRALHUB_URL: str = os.getenv("CENTRALHUB_URL", "http://centralhub:8080")
CENTRALHUB_SERVICE_TOKEN: str = os.getenv("CENTRALHUB_SERVICE_TOKEN", "")
CENTRALHUB_TIMEOUT: int = int(os.getenv("CENTRALHUB_TIMEOUT", "10"))

# Worker ID for GateKeeper service registry capability checks
WORKER_ID: str = os.getenv("WORKER_ID", "gatekeeper-01")

# Prefix for service-level availability keys
SERVICE_AVAILABILITY_KEY_PREFIX = "state:service"

# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------

_redis_l1_client: Optional[Redis] = None


async def get_redis_client() -> Optional[Redis]:
    """
    Get or create async Redis L1 client instance.

    Returns:
        Redis client or None if Redis is disabled/unavailable.
    """
    global _redis_l1_client

    if not REDIS_L1_ENABLED:
        logger.debug("Redis L1 is disabled in configuration")
        return None

    if _redis_l1_client is not None:
        return _redis_l1_client

    kwargs: Dict[str, Any] = {
        "host": REDIS_L1_HOST,
        "port": REDIS_L1_PORT,
        "db": REDIS_L1_DB,
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_keepalive": True,
    }
    if REDIS_L1_PASSWORD:
        kwargs["password"] = REDIS_L1_PASSWORD

    try:
        _redis_l1_client = aioredis.Redis(**kwargs)
        await _redis_l1_client.ping()
        logger.info("Redis L1 client initialized: %s:%s", REDIS_L1_HOST, REDIS_L1_PORT)
        return _redis_l1_client
    except Exception as exc:
        logger.warning("Failed to connect to Redis L1: %s. Caching will be disabled.", exc)
        _redis_l1_client = None
        return None


async def close_redis_client() -> None:
    """Close the Redis L1 client connection."""
    global _redis_l1_client
    if _redis_l1_client is not None:
        try:
            await _redis_l1_client.aclose()
            logger.info("Redis L1 client closed")
        except Exception as exc:
            logger.error("Error closing Redis L1 client: %s", exc)
        finally:
            _redis_l1_client = None


def reset_redis_client() -> None:
    """Reset client singleton (useful for testing)."""
    global _redis_l1_client
    _redis_l1_client = None


# ---------------------------------------------------------------------------
# Job-type → queue mapping (loaded from canonical JSON files)
# ---------------------------------------------------------------------------

_JOB_TYPE_MAP: Optional[Dict[str, Dict[str, Any]]] = None


def _load_job_type_map() -> Dict[str, Dict[str, Any]]:
    """
    Build a job_type → {queue, dependencies, execution_model} mapping from canonical JSON files.

    Looks for ``artifacts/canonical/job-types/*.json`` relative to this file.
    Each entry records the queue name, declared service dependencies, and
    execution_model so ``create_job()`` can decide whether to route to L1 or
    CentralHub L2.

    Returns:
        Dict mapping canonical name (and any aliases) to a dict with keys
        ``queue`` (str), ``dependencies`` (List[str]), and
        ``execution_model`` (str: "service" | "subprocess").
    """
    # This file lives at artifacts/canonical/shared/redis_client.py
    # parents[0] = shared/  parents[1] = canonical/
    job_types_dir = Path(__file__).resolve().parents[1] / "job-types"

    if not job_types_dir.exists():
        # Fallback: try BASE_DIR env var
        base_dir = os.getenv("BASE_DIR")
        if base_dir:
            job_types_dir = Path(base_dir) / "artifacts" / "canonical" / "job-types"

    mapping: Dict[str, Dict[str, Any]] = {}

    if not job_types_dir.exists():
        logger.warning("Job-types directory not found: %s", job_types_dir)
        return mapping

    for json_file in sorted(job_types_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as fh:
                definition = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cannot load job-type %s: %s", json_file.name, exc)
            continue

        name = definition.get("name")
        queue = definition.get("queue") or definition.get("queue_l1")
        if not name or not queue:
            logger.warning("Skipping %s: missing 'name' or 'queue' field", json_file.name)
            continue

        entry: Dict[str, Any] = {
            "queue": queue,
            "dependencies": definition.get("dependencies", []),
            "execution_model": definition.get("execution_model", "service"),
        }
        mapping[name] = entry

        for alias in definition.get("aliases", []):
            if alias != name:
                mapping[alias] = entry

    return mapping


def _get_job_type_map() -> Dict[str, Dict[str, Any]]:
    """Return the cached job-type map, loading it on first call."""
    global _JOB_TYPE_MAP
    if _JOB_TYPE_MAP is None:
        _JOB_TYPE_MAP = _load_job_type_map()
    return _JOB_TYPE_MAP


def _reset_job_type_map() -> None:
    """Force-reload the job-type map (useful for testing)."""
    global _JOB_TYPE_MAP
    _JOB_TYPE_MAP = None


# ---------------------------------------------------------------------------
# Service availability helpers
# ---------------------------------------------------------------------------


async def _all_services_available(
    redis_client: Redis, dependencies: List[str]
) -> bool:
    """
    Return True if all listed service dependencies are currently available.

    Availability is signalled via ``state:service:{name}:available`` keys
    in Redis L1. These keys are written by GateKeeper's HTTP health-probe
    loop (for stock services) or by services themselves on startup.

    An empty dependency list (subprocess workers) is always considered
    available – they run locally inside GateKeeper.

    Args:
        redis_client: Connected async Redis L1 client.
        dependencies:  List of service names (e.g. ``["stable-diffusion"]``).

    Returns:
        True if all keys exist; False if any key is missing or on Redis error.
    """
    if not dependencies:
        return True

    for dep in dependencies:
        key = f"{SERVICE_AVAILABILITY_KEY_PREFIX}:{dep}:available"
        try:
            value = await redis_client.get(key)
            if value is None:
                return False
        except Exception as exc:
            logger.warning("Cannot check service availability for %s: %s", dep, exc)
            return False

    return True


async def _check_local_gatekeeper_can_serve(
    redis_l1: Redis,
    job_type: str,
    worker_id: Optional[str] = None,
) -> bool:
    """
    Check if the local GateKeeper can execute this job-type.

    Queries ``state:gatekeeper:{worker_id}:serving_job_types`` to determine
    if the endpoint is available locally. This key is written by GateKeeper's
    ``_register_serving_capability()`` heartbeat loop.

    Args:
        redis_l1:  Connected async Redis L1 client.
        job_type:  Canonical job type to check (e.g. ``"sd_generate"``).
        worker_id: GateKeeper worker ID; defaults to the ``WORKER_ID`` env var.

    Returns:
        True if ``job_type`` is in the serving list, False if missing or on error.
    """
    effective_worker_id = worker_id if worker_id is not None else WORKER_ID
    key = f"state:gatekeeper:{effective_worker_id}:serving_job_types"
    try:
        raw = await redis_l1.get(key)
        if raw is None:
            logger.debug(
                "Capability registry missing for worker %s – falling back to L2",
                effective_worker_id,
            )
            return False
        serving_types: List[str] = json.loads(raw)
        return job_type in serving_types
    except json.JSONDecodeError as exc:
        logger.warning(
            "Cannot parse serving_job_types for worker %s: %s – falling back to L2",
            effective_worker_id,
            exc,
        )
        return False
    except Exception as exc:
        logger.warning(
            "Cannot check GateKeeper capability for %s: %s – falling back to L2",
            job_type,
            exc,
        )
        return False


# ---------------------------------------------------------------------------
# CentralHub L2 fallback
# ---------------------------------------------------------------------------


async def _enqueue_via_centralhub(
    queue: str,
    job_data: Dict[str, Any],
    user_id: str,
) -> None:
    """
    POST the job to CentralHub's queue-based enqueue endpoint (L2 fallback).

    Args:
        queue:    Target Redis queue name.
        job_data: Full job payload (includes job_id, user_id, etc.)
        user_id:  Requesting user's ID.

    Raises:
        RuntimeError: On HTTP error or connection failure.
    """
    import httpx

    url = f"{CENTRALHUB_URL}/api/redis/jobs/enqueue"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if CENTRALHUB_SERVICE_TOKEN:
        headers["Authorization"] = f"Bearer {CENTRALHUB_SERVICE_TOKEN}"

    request_body = {
        "queue_name": queue,
        "job_data": job_data,
        "caller": "canonical_redis_client",
    }

    async with httpx.AsyncClient(timeout=CENTRALHUB_TIMEOUT) as client:
        response = await client.post(url, json=request_body, headers=headers)

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"CentralHub enqueue failed: HTTP {response.status_code} – {response.text[:300]}"
        )


# ---------------------------------------------------------------------------
# Public job-creation API
# ---------------------------------------------------------------------------


async def create_job(
    job_type: str,
    payload: Dict[str, Any],
    owner_user_id: str,
    job_id: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Create a job with owner-first scheduling.

    Checks Redis L1 for service availability based on the job-type's declared
    ``dependencies``. For "service" execution model, also checks that the local
    GateKeeper can serve this job-type via its capability registry. If all checks
    pass, pushes directly to the L1 queue (fast path). Otherwise falls back to
    CentralHub which enqueues to L2 for eventual processing.

    Availability keys (``state:service:{name}:available``) are maintained by:
    - GateKeeper's HTTP health-probe loop (for stock services like Ollama)
    - Services themselves via a startup/heartbeat registration (e.g. SD API)

    Capability keys (``state:gatekeeper:{worker_id}:serving_job_types``) are
    maintained by GateKeeper's ``_register_serving_capability()`` heartbeat.

    Args:
        job_type:      Canonical job type (e.g. ``"sd_generate"``).
        payload:       Job-specific data dict (model, prompt, image, etc.)
        owner_user_id: ID of the requesting user.
        job_id:        Optional pre-generated job ID; a UUID is generated if omitted.

    Returns:
        Tuple of ``(job_id, "l1" | "l2")`` indicating where the job was enqueued.

    Raises:
        ValueError:   If ``job_type`` is unrecognised.
        RuntimeError: If both L1 push and CentralHub fallback fail.
    """
    if job_id is None:
        job_id = str(uuid.uuid4())

    job_type_map = _get_job_type_map()
    job_def = job_type_map.get(job_type)
    if job_def is None:
        raise ValueError(
            f"Unknown job_type: {job_type!r}. "
            f"Supported types: {sorted(job_type_map)}"
        )

    queue: str = job_def["queue"]
    dependencies: List[str] = job_def["dependencies"]
    execution_model: str = job_def.get("execution_model", "service")

    job_data: Dict[str, Any] = {
        "job_id": job_id,
        "job_type": job_type,
        "user_id": owner_user_id,
        "queue": queue,
        **payload,
    }

    redis_l1 = await get_redis_client()

    # ------------------------------------------------------------------
    # Owner-first: try L1 if all service dependencies are available
    # and (for service execution model) the local GateKeeper can serve
    # this job-type.
    # ------------------------------------------------------------------
    route_to_l1 = False
    if redis_l1 is not None and await _all_services_available(redis_l1, dependencies):
        if execution_model == "subprocess":
            # Subprocess job-types bypass capability check (always available locally)
            route_to_l1 = True
        else:
            can_serve_locally = await _check_local_gatekeeper_can_serve(redis_l1, job_type)
            if can_serve_locally:
                route_to_l1 = True
            else:
                logger.info(
                    "Job %s (%s) routing to L2: local GateKeeper cannot serve job-type",
                    job_id, job_type,
                )

    if route_to_l1 and redis_l1 is not None:
        try:
            await redis_l1.lpush(queue, json.dumps(job_data))
            label = "subprocess, always local" if execution_model == "subprocess" else "services available, GateKeeper capable"
            logger.info(
                "Job %s (%s) enqueued to L1 queue=%s (%s)",
                job_id, job_type, queue, label,
            )
            return job_id, "l1"
        except Exception as exc:
            logger.warning(
                "L1 LPUSH failed for job %s: %s – falling back to CentralHub",
                job_id, exc,
            )

    # ------------------------------------------------------------------
    # Fallback: CentralHub enqueues to L2
    # ------------------------------------------------------------------
    try:
        await _enqueue_via_centralhub(queue, job_data, owner_user_id)
        logger.info(
            "Job %s (%s) enqueued via CentralHub L2 (services unavailable or local GateKeeper incapable)",
            job_id, job_type,
        )
        return job_id, "l2"
    except Exception as exc:
        raise RuntimeError(
            f"Failed to enqueue job {job_id!r} ({job_type!r}): {exc}"
        ) from exc
