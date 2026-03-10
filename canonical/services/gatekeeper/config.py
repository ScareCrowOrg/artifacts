"""
Configuration module for GateKeeper Service.

Manages dual-source Redis configuration (L1 owner + L2 global),
multi-source pooling strategy, and routing to workers (HTTP services
or subprocess job workers).

Job types are loaded dynamically from artifacts/canonical/job-types/*.json.
Each job type includes an ``execution_model`` field:
  - "service": route via HTTP POST to a long-lived service endpoint.
  - "subprocess": spawn an isolated Python subprocess from artifacts/workers/.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

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

QUEUE_PRIORITY = os.getenv("QUEUE_PRIORITY", "owner_first")
BRPOP_L1_TIMEOUT = int(os.getenv("BRPOP_L1_TIMEOUT", "1"))
BRPOP_L2_TIMEOUT = int(os.getenv("BRPOP_L2_TIMEOUT", "20"))

# ============================================================================
# Queue Names
# ============================================================================

CPU_JOBS_QUEUE_L1 = os.getenv("CPU_JOBS_QUEUE_L1", "scareverse:cpu-jobs:queue")
CPU_JOBS_QUEUE_L2 = os.getenv("CPU_JOBS_QUEUE_L2", "scareverse:cpu-jobs:queue")

THREE_D_JOBS_QUEUE_L1 = os.getenv("THREE_D_JOBS_QUEUE_L1", "scareverse:3d-jobs:queue")
THREE_D_JOBS_QUEUE_L2 = os.getenv("THREE_D_JOBS_QUEUE_L2", "scareverse:3d-jobs:queue")

DEAD_LETTER_QUEUE = os.getenv("DEAD_LETTER_QUEUE", "scareverse:dead-letter:queue")
COMMANDS_QUEUE = os.getenv("COMMANDS_QUEUE", "commands:gatekeeper:queue")

# ============================================================================
# Subprocess Workers Path
# ============================================================================

# Inside Docker: /app/artifacts/canonical/workers (via volume mount ../../:/app/artifacts)
# In development: resolved relative to this file (up 3 levels to canonical/, then workers/)
_default_workers_path = Path("/app/artifacts/canonical/workers")
if not _default_workers_path.exists():
    try:
        # services/gatekeeper/config.py → 3 parents up = canonical/
        _default_workers_path = Path(__file__).resolve().parents[2] / "workers"
    except IndexError:
        _default_workers_path = Path(__file__).parent / "workers"

WORKERS_PATH = Path(os.getenv("WORKERS_PATH", str(_default_workers_path)))

# ============================================================================
# Job Routing: Dynamic Job Type → Configuration
# ============================================================================

def _load_job_types_from_artifacts(
    job_types_dir: "Path | None" = None,
) -> Dict[str, Any]:
    """
    Load job-type definitions from artifacts/canonical/job-types/*.json.

    Endpoint can be overridden via env var ``WORKER_{NAME_UPPER}_ENDPOINT``.
    """
    if job_types_dir is None:
        # Docker path: /app/artifacts/canonical/job-types
        candidate = Path("/app/artifacts/canonical/job-types")
        if not candidate.exists():
            try:
                # services/gatekeeper/config.py → 3 parents = canonical/ → job-types/
                candidate = Path(__file__).resolve().parents[2] / "job-types"
            except IndexError:
                candidate = Path(__file__).parent / "job-types"
        job_types_dir = candidate

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

            # Allow env var override of endpoint for service workers
            env_key = f"WORKER_{name.upper().replace('-', '_')}_ENDPOINT"
            env_endpoint = os.getenv(env_key)
            if env_endpoint:
                if "service" in definition:
                    definition["service"]["endpoint"] = env_endpoint
                else:
                    definition["endpoint"] = env_endpoint

            job_types[name] = definition
            logger.debug("Loaded job-type: %s (execution_model=%s)", name, definition.get("execution_model", "service"))
        except Exception as exc:
            logger.error("Failed to load job-type from %s: %s", json_file, exc)

    return job_types


def _build_job_types_config(
    job_types_dir: "Path | None" = None,
) -> Dict[str, Any]:
    """
    Build JOB_TYPES_CONFIG from loaded job-type definitions.

    Aliases are expanded as additional keys so legacy names continue to work.
    """
    loaded = _load_job_types_from_artifacts(job_types_dir)
    config: Dict[str, Any] = {}

    for name, job_type in loaded.items():
        execution_model = job_type.get("execution_model", "service")

        if execution_model == "subprocess":
            entry: Dict[str, Any] = {
                "execution_model": "subprocess",
                "worker_name": Path(job_type.get("worker", {}).get("path", name)).name,
                "worker": job_type.get("worker", {}),
                "configuration": job_type.get("configuration", {}),
                "queue_l1": job_type.get("queue_l1"),
                "queue_l2": job_type.get("queue_l2"),
                "timeout": int(job_type.get("configuration", {}).get("timeout_seconds", 60)),
                "result_storage": job_type.get("result_storage", "rpush_l1"),
                "result_key_prefix": job_type.get("result_key_prefix"),
                "result_key_ttl": int(job_type.get("result_key_ttl", 120)),
                "dependencies": job_type.get("dependencies", []),
            }
        else:
            # Service execution model (default): HTTP routing
            service_cfg = job_type.get("service", {})
            endpoint = service_cfg.get("endpoint") or job_type.get("endpoint")
            entry = {
                "execution_model": "service",
                "worker_name": job_type.get("worker_type", name),
                "endpoint": endpoint,
                "queue_l1": job_type.get("queue_l1"),
                "queue_l2": job_type.get("queue_l2"),
                "timeout": int(job_type.get("timeout", 60)),
                "result_storage": job_type.get("result_storage", "rpush_l1"),
                "result_key_prefix": job_type.get("result_key_prefix"),
                "result_key_ttl": int(job_type.get("result_key_ttl", 120)),
                "dependencies": job_type.get("dependencies", []),
            }

        config[name] = entry

        for alias in job_type.get("aliases", []):
            if alias != name:
                config[alias] = entry

    return config


# Load job-types at module init (single source of truth)
JOB_TYPES_CONFIG = _build_job_types_config()

if not JOB_TYPES_CONFIG:
    logger.warning("⚠️ No job-types loaded from artifacts/canonical/job-types/")
    logger.warning("   GateKeeper will start without configured workers")

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

SCALE_UP_VRAM_MIN_MB = int(os.getenv("SCALE_UP_VRAM_MIN_MB", "3000"))
SCALE_UP_RAM_MIN_MB = int(os.getenv("SCALE_UP_RAM_MIN_MB", "2000"))
SCALE_UP_QUEUE_DEPTH = int(os.getenv("SCALE_UP_QUEUE_DEPTH", "5"))
SCALE_DOWN_IDLE_SECONDS = int(os.getenv("SCALE_DOWN_IDLE_SECONDS", "300"))

WORKER_STATE_KEY_PREFIX = os.getenv("WORKER_STATE_KEY_PREFIX", "workers:state")

# ============================================================================
# HTTP Client Configuration
# ============================================================================

HTTP_REQUEST_TIMEOUT = int(os.getenv("HTTP_REQUEST_TIMEOUT", "60"))
HTTP_CONNECT_TIMEOUT = int(os.getenv("HTTP_CONNECT_TIMEOUT", "10"))

# ============================================================================
# Venv Health Checks
# ============================================================================

# Interval (seconds) between periodic venv health-check iterations.
VENV_HEALTH_CHECK_INTERVAL = int(os.getenv("VENV_HEALTH_CHECK_INTERVAL", "60"))

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "LOG_FORMAT",
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
# When set to "json", switch to structured JSON log output via JSONFormatter.
LOG_FORMAT_TYPE = os.getenv("LOG_FORMAT_TYPE", "text")

# ============================================================================
# Result Storage
# ============================================================================

JOB_STATE_KEY_PREFIX = os.getenv("JOB_STATE_KEY_PREFIX", "state:job")
JOB_STATE_TTL_SECONDS = int(os.getenv("JOB_STATE_TTL_SECONDS", "3600"))
