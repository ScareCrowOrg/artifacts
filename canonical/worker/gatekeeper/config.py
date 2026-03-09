"""
Configuration module for GateKeeper Worker.

Manages dual-source Redis configuration (L1 owner + L2 global),
multi-source pooling strategy, and HTTP routing to atomic workers.

Job types are loaded dynamically from artifacts/canonical/job-types/*.json,
eliminating the need to hard-code worker endpoints in this file.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ============================================================================
# Base Paths
# ============================================================================

BASE_DIR = Path(__file__).parent.absolute()

# ============================================================================
# Redis L1 Configuration (Owner/Local - ScareRunner)
# ============================================================================

REDIS_L1_HOST = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
REDIS_L1_DB = int(os.getenv("REDIS_L1_DB", "0"))

# ============================================================================
# CentralHub Configuration (L2 access via HTTP – no direct Redis credentials)
# ============================================================================

CENTRALHUB_URL = os.getenv("CENTRALHUB_URL", "http://centralhub:8080")
CENTRALHUB_SERVICE_TOKEN = os.getenv(
    "CENTRALHUB_SERVICE_TOKEN",
    "internal-gatekeeper-token",
)

# ============================================================================
# Multi-Source Pooling Strategy
# ============================================================================

# Owner-first scheduling: L1 checked first, then L2
QUEUE_PRIORITY = os.getenv("QUEUE_PRIORITY", "owner_first")

# L1 timeout: short (non-blocking owner check)
BRPOP_L1_TIMEOUT = int(os.getenv("BRPOP_L1_TIMEOUT", "1"))

# L2 timeout: longer (blocking global queue wait)
BRPOP_L2_TIMEOUT = int(os.getenv("BRPOP_L2_TIMEOUT", "20"))

# ============================================================================
# Queue Names
# ============================================================================

# Consolidated queues (Phase 2.2): all CPU/GPU jobs share cpu-jobs queue,
# 3D mesh jobs use 3d-jobs queue.
CPU_JOBS_QUEUE_L1 = os.getenv("CPU_JOBS_QUEUE_L1", "scareverse:cpu-jobs:queue")
CPU_JOBS_QUEUE_L2 = os.getenv("CPU_JOBS_QUEUE_L2", "scareverse:cpu-jobs:queue")

THREE_D_JOBS_QUEUE_L1 = os.getenv("THREE_D_JOBS_QUEUE_L1", "scareverse:3d-jobs:queue")
THREE_D_JOBS_QUEUE_L2 = os.getenv("THREE_D_JOBS_QUEUE_L2", "scareverse:3d-jobs:queue")

# Dead-letter queue for permanently failed jobs
DEAD_LETTER_QUEUE = os.getenv("DEAD_LETTER_QUEUE", "scareverse:dead-letter:queue")

# Commands queue (for Phase 2 launcher)
COMMANDS_QUEUE = os.getenv("COMMANDS_QUEUE", "commands:gatekeeper:queue")

# ============================================================================
# Job Routing: Dynamic Job Type → Atomic Worker HTTP Endpoint
# ============================================================================

def _load_job_types_from_artifacts(
    job_types_dir: "Path | None" = None,
) -> Dict[str, Any]:
    """
    Load job-type definitions from artifacts/canonical/job-types/*.json.

    Each JSON file defines a job type with its routing configuration.
    The ``name`` field is used as the primary key. Endpoints can be overridden
    at runtime via environment variables of the form
    ``WORKER_{NAME_UPPER}_ENDPOINT``.

    Args:
        job_types_dir: Optional explicit path to the job-types directory.
            Defaults to ``<project_root>/artifacts/canonical/job-types/``,
            where the project root is resolved relative to this file:
            ``artifacts/canonical/worker/gatekeeper/config.py`` → 4 parents up.

    Returns:
        Dict mapping each job-type name to its full definition dict.
    """
    if job_types_dir is None:
        # Resolve job-types directory.
        # In Docker (/app/config.py): /app/artifacts/canonical/job-types
        # In development (artifacts/canonical/worker/gatekeeper/config.py): up 4 parents
        current = Path(__file__).resolve()

        # Try Docker path first: /app/artifacts/canonical/job-types
        job_types_dir = Path("/app/artifacts/canonical/job-types")
        if not job_types_dir.exists():
            # Try local development: up 4 parents from gatekeeper/config.py
            try:
                project_root = current.parents[4]
                job_types_dir = project_root / "artifacts" / "canonical" / "job-types"
            except IndexError:
                # Last resort: try parent directory
                job_types_dir = current.parent / "artifacts" / "canonical" / "job-types"

    if not job_types_dir.exists():
        logger.warning("job-types directory not found: %s", job_types_dir)
        return {}

    job_types: Dict[str, Any] = {}
    for json_file in sorted(job_types_dir.glob("*.json")):
        try:
            with open(json_file, encoding="utf-8") as fh:
                definition = json.load(fh)

            name = definition.get("name")
            if not name:
                logger.warning("Job type file missing 'name' field: %s", json_file)
                continue

            # Allow env var override of endpoint
            env_key = f"WORKER_{name.upper().replace('-', '_')}_ENDPOINT"
            definition["endpoint"] = os.getenv(env_key, definition.get("endpoint"))

            job_types[name] = definition
            logger.debug("Loaded job-type: %s", name)
        except Exception as exc:
            logger.error("Failed to load job-type from %s: %s", json_file, exc)

    return job_types


def _build_job_types_config(
    job_types_dir: "Path | None" = None,
) -> Dict[str, Any]:
    """
    Build JOB_TYPES_CONFIG from loaded job-type definitions.

    Each entry in the returned dict follows the structure expected by the
    GateKeeper dispatcher. Aliases defined in each job-type JSON file are
    expanded as additional keys so that legacy job-type names (e.g.
    ``REMOTE_REMBG``, ``background_removal``) continue to resolve correctly.

    Args:
        job_types_dir: Optional path passed through to
            ``_load_job_types_from_artifacts``. Defaults to the canonical
            artifacts directory.

    Returns:
        Dict mapping every job-type name (and alias) to its routing config.
    """
    loaded = _load_job_types_from_artifacts(job_types_dir)
    config: Dict[str, Any] = {}

    for name, job_type in loaded.items():
        entry: Dict[str, Any] = {
            "worker_name": job_type.get("worker_type", name),
            "endpoint": job_type.get("endpoint"),
            "queue_l1": job_type.get("queue_l1"),
            "queue_l2": job_type.get("queue_l2"),
            "timeout": int(job_type.get("timeout", 60)),
            "result_storage": job_type.get("result_storage", "rpush_l1"),
            "result_key_prefix": job_type.get("result_key_prefix"),
            "result_key_ttl": int(job_type.get("result_key_ttl", 120)),
        }
        config[name] = entry

        # Expand aliases so legacy job-type names still route correctly.
        for alias in job_type.get("aliases", []):
            if alias != name:
                config[alias] = entry

    return config


# Load job-types at module init (single source of truth)
JOB_TYPES_CONFIG = _build_job_types_config()

if not JOB_TYPES_CONFIG:
    logger.warning("⚠️ No job-types loaded from artifacts/canonical/job-types/")
    logger.warning("   GateKeeper will start without configured workers")
    logger.warning("   Add JSON files to artifacts/canonical/job-types/ and restart")

# All queues monitored by this GateKeeper (derived from JOB_TYPES_CONFIG – single source of truth)
ALL_QUEUES_L1 = list({
    cfg.get("queue_l1")
    for cfg in JOB_TYPES_CONFIG.values()
    if cfg.get("queue_l1")
})
ALL_QUEUES_L2 = list({
    cfg.get("queue_l2")
    for cfg in JOB_TYPES_CONFIG.values()
    if cfg.get("queue_l2")
})

# ============================================================================
# Worker Configuration
# ============================================================================

WORKER_ID = os.getenv("WORKER_ID", "gatekeeper-01")
WORKER_HEARTBEAT_INTERVAL = int(os.getenv("WORKER_HEARTBEAT_INTERVAL", "30"))
WORKER_MAX_RETRIES = int(os.getenv("WORKER_MAX_RETRIES", "3"))
WORKER_RETRY_DELAY = float(os.getenv("WORKER_RETRY_DELAY", "2.0"))

# ============================================================================
# Telemetry & Orchestration
# ============================================================================

TELEMETRY_KEY = os.getenv("TELEMETRY_KEY", "state:host:telemetry")
TELEMETRY_STALE_AFTER_SECONDS = int(os.getenv("TELEMETRY_STALE_AFTER_SECONDS", "15"))

# Resource thresholds for scale decisions
SCALE_UP_VRAM_MIN_MB = int(os.getenv("SCALE_UP_VRAM_MIN_MB", "3000"))
SCALE_UP_RAM_MIN_MB = int(os.getenv("SCALE_UP_RAM_MIN_MB", "2000"))
SCALE_UP_QUEUE_DEPTH = int(os.getenv("SCALE_UP_QUEUE_DEPTH", "5"))
SCALE_DOWN_IDLE_SECONDS = int(os.getenv("SCALE_DOWN_IDLE_SECONDS", "300"))

# Worker state keys in Redis L1
WORKER_STATE_KEY_PREFIX = os.getenv("WORKER_STATE_KEY_PREFIX", "workers:state")

# ============================================================================
# HTTP Client Configuration
# ============================================================================

HTTP_REQUEST_TIMEOUT = int(os.getenv("HTTP_REQUEST_TIMEOUT", "60"))
HTTP_CONNECT_TIMEOUT = int(os.getenv("HTTP_CONNECT_TIMEOUT", "10"))

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ============================================================================
# Result Storage
# ============================================================================

JOB_STATE_KEY_PREFIX = os.getenv("JOB_STATE_KEY_PREFIX", "state:job")
JOB_STATE_TTL_SECONDS = int(os.getenv("JOB_STATE_TTL_SECONDS", "3600"))
