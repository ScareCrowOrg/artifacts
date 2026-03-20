#!/usr/bin/env python3
"""
Configuration for the Nginx Unity service worker.

All values are resolved from environment variables so the container can be
deployed with different settings without rebuilding the image.

Environment variables (all optional with sensible defaults):
- LOG_LEVEL              Logging verbosity: DEBUG, INFO, WARNING, ERROR (default: info)
- NGINX_PORT             HTTP port Nginx listens on (default: 80)
- CENTRALHUB_UPSTREAM    Upstream for CentralHub API (default: centralhub:5051)
- FRONTEND_UPSTREAM      Upstream for Vite frontend (default: vite-frontend:5173)
- SCARERUNNER_UPSTREAM   Upstream for ScareRunner (default: scarerunner:5050)
- GATEKEEPER_UPSTREAM    Upstream for GateKeeper (default: gatekeeper:8000)
- SIDECAR_HOST           Bind address for the FastAPI sidecar (default: 0.0.0.0)
- SIDECAR_PORT           Port the FastAPI health sidecar listens on (default: 9000)
- WORKER_ID              Logical service name for Redis heartbeat (default: nginx-unity)
- REDIS_L1_HOST          Redis L1 host (default: redis-local)
- REDIS_L1_PORT          Redis L1 port (default: 6380)
- REDIS_L1_DB            Redis L1 database index (default: 0)
- REDIS_L1_PASSWORD      Redis L1 password (default: scarerunner)
- HEARTBEAT_INTERVAL     Seconds between heartbeat key refreshes (default: 20)
- HEARTBEAT_TTL          TTL in seconds for the Redis heartbeat key (default: 60)
- UPSTREAM_CHECK_TIMEOUT Seconds to wait when checking upstream health (default: 3)
"""

import os
from typing import Dict

# ── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info").lower()

# ── Nginx ────────────────────────────────────────────────────────────────────

NGINX_PORT: int = int(os.getenv("NGINX_PORT", "80"))

# ── Upstream hosts (host:port, no scheme – Nginx resolves internally) ─────────

CENTRALHUB_UPSTREAM: str = os.getenv("CENTRALHUB_UPSTREAM", "centralhub:5051")
FRONTEND_UPSTREAM: str = os.getenv("FRONTEND_UPSTREAM", "vite-frontend:5173")
SCARERUNNER_UPSTREAM: str = os.getenv("SCARERUNNER_UPSTREAM", "scarerunner:5050")
GATEKEEPER_UPSTREAM: str = os.getenv("GATEKEEPER_UPSTREAM", "gatekeeper:8000")

# ── FastAPI health sidecar ────────────────────────────────────────────────────

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

# ── Upstream health checks ────────────────────────────────────────────────────

UPSTREAM_CHECK_TIMEOUT: float = float(os.getenv("UPSTREAM_CHECK_TIMEOUT", "3"))

# ── Derived: upstream map for health reporting ────────────────────────────────

UPSTREAMS: Dict[str, str] = {
    "centralhub": CENTRALHUB_UPSTREAM,
    "frontend": FRONTEND_UPSTREAM,
    "scarerunner": SCARERUNNER_UPSTREAM,
    "gatekeeper": GATEKEEPER_UPSTREAM,
}
