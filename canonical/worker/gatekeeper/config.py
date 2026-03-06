"""
Configuration module for GateKeeper Worker.

Manages dual-source Redis configuration (L1 owner + L2 global),
multi-source pooling strategy, and HTTP routing to atomic workers.
"""

import os
from pathlib import Path
from typing import Dict, Any

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
# Redis L2 Configuration (Global - CentralHub)
# ============================================================================

REDIS_L2_HOST = os.getenv("REDIS_L2_HOST", "host.docker.internal")
REDIS_L2_PORT = int(os.getenv("REDIS_L2_PORT", "6379"))
REDIS_L2_PASSWORD = os.getenv("REDIS_L2_PASSWORD", "")
REDIS_L2_DB = int(os.getenv("REDIS_L2_DB", "0"))

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

REMBG_QUEUE_L1 = os.getenv("REMBG_QUEUE_L1", "scareverse:rembg-jobs:queue")
REMBG_QUEUE_L2 = os.getenv("REMBG_QUEUE_L2", "scareverse:rembg-jobs:queue")

INSTANTMESH_QUEUE_L1 = os.getenv("INSTANTMESH_QUEUE_L1", "scareverse:3d-jobs:queue")
INSTANTMESH_QUEUE_L2 = os.getenv("INSTANTMESH_QUEUE_L2", "scareverse:3d-jobs:queue")

# Dead-letter queue for permanently failed jobs
DEAD_LETTER_QUEUE = os.getenv("DEAD_LETTER_QUEUE", "scareverse:dead-letter:queue")

# Commands queue (for Phase 2 launcher)
COMMANDS_QUEUE = os.getenv("COMMANDS_QUEUE", "commands:gatekeeper:queue")

# ============================================================================
# Job Routing: Job Type → Atomic Worker HTTP Endpoint
# ============================================================================

JOB_TYPES_CONFIG: Dict[str, Any] = {
    "REMOTE_REMBG": {
        "worker_name": "rembg",
        "endpoint": os.getenv(
            "WORKER_REMBG_ENDPOINT",
            "http://scareverse-worker-rembg:8000"
        ),
        "queue_l1": REMBG_QUEUE_L1,
        "queue_l2": REMBG_QUEUE_L2,
        "timeout": int(os.getenv("REMBG_JOB_TIMEOUT", "60")),
    },
    "background_removal": {
        "worker_name": "rembg",
        "endpoint": os.getenv(
            "WORKER_REMBG_ENDPOINT",
            "http://scareverse-worker-rembg:8000"
        ),
        "queue_l1": REMBG_QUEUE_L1,
        "queue_l2": REMBG_QUEUE_L2,
        "timeout": int(os.getenv("REMBG_JOB_TIMEOUT", "60")),
    },
    # Phase 2 (future)
    "instantmesh": {
        "worker_name": "instantmesh",
        "endpoint": os.getenv(
            "WORKER_INSTANTMESH_ENDPOINT",
            "http://scareverse-worker-instantmesh:8000"
        ),
        "queue_l1": INSTANTMESH_QUEUE_L1,
        "queue_l2": INSTANTMESH_QUEUE_L2,
        "timeout": int(os.getenv("INSTANTMESH_JOB_TIMEOUT", "120")),
    },
}

# All queues monitored by this GateKeeper
ALL_QUEUES_L1 = list({
    cfg.get("queue_l1", REMBG_QUEUE_L1)
    for cfg in JOB_TYPES_CONFIG.values()
    if cfg.get("queue_l1")
})
ALL_QUEUES_L2 = list({
    cfg.get("queue_l2", REMBG_QUEUE_L2)
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
