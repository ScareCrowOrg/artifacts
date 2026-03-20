#!/usr/bin/env python3
"""
Configuration for the Cloudflared service worker.

All values are resolved from environment variables so that the container can
be deployed with different settings without rebuilding the image.

Environment variables (all optional with sensible defaults):
- LOG_LEVEL         Logging verbosity: DEBUG, INFO, WARNING, ERROR (default: INFO)
- TUNNEL_TOKEN      Cloudflare tunnel authentication token (required for tunnel)
- TUNNEL_NAME       Human-readable tunnel identifier (default: scareverse-tunnel)
- HEALTH_PORT       Port the FastAPI health sidecar listens on (default: 8000)
- INGRESS_RULES     JSON array of ingress rule objects (default: [])
- WORKER_ID         Logical service name for Redis heartbeat (default: cloudflared)
- REDIS_L1_HOST     Redis L1 host (default: redis-local)
- REDIS_L1_PORT     Redis L1 port (default: 6380)
- REDIS_L1_DB       Redis L1 database index (default: 0)
- REDIS_L1_PASSWORD Redis L1 password (default: scarerunner)
- HEARTBEAT_INTERVAL Seconds between heartbeat key refreshes (default: 20)
- HEARTBEAT_TTL     TTL in seconds for the Redis heartbeat key (default: 60)
"""

import json
import logging
import os
from typing import Any, List

# ── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Cloudflare tunnel ────────────────────────────────────────────────────────

TUNNEL_TOKEN: str = os.getenv("TUNNEL_TOKEN", "")
TUNNEL_NAME: str = os.getenv("TUNNEL_NAME", "scareverse-tunnel")

# ── FastAPI health sidecar ───────────────────────────────────────────────────

HEALTH_HOST: str = os.getenv("HEALTH_HOST", "0.0.0.0")
HEALTH_PORT: int = int(os.getenv("HEALTH_PORT", "8000"))

# ── Ingress rules (JSON array) ───────────────────────────────────────────────

def _parse_ingress_rules() -> List[Any]:
    raw = os.getenv("INGRESS_RULES", "[]")
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return value
        logging.getLogger(__name__).warning(
            "INGRESS_RULES must be a JSON array; got %s – using []", type(value).__name__
        )
        return []
    except json.JSONDecodeError as exc:
        logging.getLogger(__name__).warning(
            "INGRESS_RULES is not valid JSON (%s) – using []", exc
        )
        return []


INGRESS_RULES: List[Any] = _parse_ingress_rules()

# ── Service identity ─────────────────────────────────────────────────────────

WORKER_ID: str = os.getenv("WORKER_ID", "cloudflared")

# ── Redis / heartbeat ────────────────────────────────────────────────────────

REDIS_L1_HOST: str = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB: int = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD: str = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
HEARTBEAT_INTERVAL: int = int(os.getenv("HEARTBEAT_INTERVAL", "20"))
HEARTBEAT_TTL: int = int(os.getenv("HEARTBEAT_TTL", "60"))
