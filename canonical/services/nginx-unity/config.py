#!/usr/bin/env python3
"""
Configuration for the Nginx Unity service worker.

All values are resolved from environment variables so the container can be
deployed with different settings without rebuilding the image.

Environment variables (all optional with sensible defaults):
- LOG_LEVEL              Logging verbosity: DEBUG, INFO, WARNING, ERROR (default: info)
- SIDECAR_HOST           Bind address for the FastAPI sidecar (default: 0.0.0.0)
- SIDECAR_PORT           Port the FastAPI heartbeat sidecar listens on (default: 9000)
- WORKER_ID              Logical service name for Redis heartbeat (default: nginx-unity)
- REDIS_L1_HOST          Redis L1 host (default: redis-local)
- REDIS_L1_PORT          Redis L1 port (default: 6380)
- REDIS_L1_DB            Redis L1 database index (default: 0)
- REDIS_L1_PASSWORD      Redis L1 password (default: scarerunner)
- HEARTBEAT_INTERVAL     Seconds between heartbeat key refreshes (default: 20)
- HEARTBEAT_TTL          TTL in seconds for the Redis heartbeat key (default: 60)
"""

import os

# ── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info").lower()

# ── FastAPI heartbeat sidecar ────────────────────────────────────────────────

SIDECAR_HOST: str = os.getenv("SIDECAR_HOST", "0.0.0.0")
SIDECAR_PORT: int = int(os.getenv("SIDECAR_PORT", "9000"))

# ── Service identity ──────────────────────────────────────────────────────────

WORKER_ID: str = os.getenv("WORKER_ID", "nginx-unity")

# ── Redis / heartbeat ─────────────────────────────────────────────────────────

REDIS_L1_HOST: str = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB: int = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD: str = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
HEARTBEAT_TTL: int = int(os.getenv("HEARTBEAT_TTL", "60"))
