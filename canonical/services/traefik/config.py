#!/usr/bin/env python3
"""
Configuration for the Traefik service worker.

All values are resolved from environment variables so the container can be
deployed with different settings without rebuilding the image.

Environment variables (all optional with sensible defaults):
- LOG_LEVEL              Logging verbosity: DEBUG, INFO, WARNING, ERROR (default: INFO)
- WORKER_ID              Logical service name for Redis heartbeat (default: traefik)
- REDIS_L1_HOST          Redis L1 host (default: redis-local)
- REDIS_L1_PORT          Redis L1 port (default: 6380)
- REDIS_L1_DB            Redis L1 database index (default: 0)
- REDIS_L1_PASSWORD      Redis L1 password (default: scarerunner)
- HEARTBEAT_INTERVAL     Seconds between heartbeat key refreshes (default: 20)
- HEARTBEAT_TTL          TTL in seconds for the Redis heartbeat key (default: 60)
"""

import os

# ── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Service identity ──────────────────────────────────────────────────────────

WORKER_ID: str = os.getenv("WORKER_ID", "traefik")

# ── Redis / heartbeat ─────────────────────────────────────────────────────────

REDIS_L1_HOST: str = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB: int = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD: str = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
HEARTBEAT_TTL: int = int(os.getenv("HEARTBEAT_TTL", "60"))
