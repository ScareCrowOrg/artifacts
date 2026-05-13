#!/usr/bin/env python3
"""
Configuration for the planet-beacon service.

All values are resolved from environment variables so the container can be
deployed with different settings without rebuilding the image.

Environment variables:
- LOG_LEVEL                  Logging verbosity: DEBUG, INFO, WARNING, ERROR (default: INFO)
- PLANET_ID                  Unique planet identifier (required, injected by Launcher)
- PLANET_NAME                Human-readable planet name (required, injected by Launcher)
- TUNNEL_FQDN                Fully-qualified domain name of this planet (required, injected by Launcher)
- CENTRALHUB_URL             CentralHub base URL (default: https://hub.scareverse.net)
- CENTRALHUB_SERVICE_TOKEN   Bearer token for CentralHub auth (required, injected by Launcher)
- BEACON_INTERVAL            Seconds between presence heartbeats (default: 60)
- PRESENCE_TTL               Redis TTL in seconds for the presence key (default: 90)
- VIEWERS_BASE_DIR           Path to scan for viewers (default: /app/artifacts/canonical/viewers)
- REDIS_L1_HOST              Redis L1 host for BaseService heartbeat (default: redis-local)
- REDIS_L1_PORT              Redis L1 port (default: 6380)
- REDIS_L1_DB                Redis L1 database index (default: 0)
- REDIS_L1_PASSWORD          Redis L1 password (default: scarerunner)
"""

import os

# ── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Planet identity ───────────────────────────────────────────────────────────

PLANET_ID: str = os.getenv("PLANET_ID", "")
PLANET_NAME: str = os.getenv("PLANET_NAME", "")
TUNNEL_FQDN: str = os.getenv("TUNNEL_FQDN", "")

# ── CentralHub connection ─────────────────────────────────────────────────────

CENTRALHUB_URL: str = os.getenv("CENTRALHUB_URL", "https://hub.scareverse.net")
CENTRALHUB_SERVICE_TOKEN: str = os.getenv("CENTRALHUB_SERVICE_TOKEN", "")

# ── Beacon timings ────────────────────────────────────────────────────────────

BEACON_INTERVAL: int = int(os.getenv("BEACON_INTERVAL", "60"))
PRESENCE_TTL: int = int(os.getenv("PRESENCE_TTL", "90"))

# ── Viewer scan path ──────────────────────────────────────────────────────────

VIEWERS_BASE_DIR: str = os.getenv(
    "VIEWERS_BASE_DIR",
    "/app/artifacts/canonical/viewers",
)

# ── Redis L1 (BaseService heartbeat) ─────────────────────────────────────────

REDIS_L1_HOST: str = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB: int = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD: str = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
