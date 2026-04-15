#!/usr/bin/env python3
"""
Service Discovery Daemon for Traefik.

Scans Redis L1 every SERVICE_DISCOVERY_INTERVAL seconds for services that have
registered a heartbeat with ``port_opened: true`` and generates a Traefik
dynamic YAML configuration at TRAEFIK_CONFIG_PATH.

Traefik's File provider watches that config file and hot-reloads routes
automatically when it changes.  This daemon replaces the Docker socket
provider for service discovery.

Invoked by:
    entrypoint.sh line ~7 (background daemon)

Redis key pattern scanned:
    state:service:{name}:available  →  JSON  {"port_opened": true|false|null, "timestamp": float}

Only services with ``port_opened: true`` are added to the Traefik config.
Config is written atomically (temp file + os.replace) and only when routes
actually change to avoid unnecessary Traefik hot-reloads.
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from typing import Dict, Optional, Set

import yaml

# ---------------------------------------------------------------------------
# Path setup: ensure canonical.shared resolves when run inside the container
# ---------------------------------------------------------------------------

if "/app/artifacts" not in sys.path:
    sys.path.insert(0, "/app/artifacts")

# ---------------------------------------------------------------------------
# Configuration (all configurable via environment variables)
# ---------------------------------------------------------------------------

SERVICE_DISCOVERY_INTERVAL: int = int(os.getenv("SERVICE_DISCOVERY_INTERVAL", "15"))
TRAEFIK_CONFIG_PATH: str = os.getenv("TRAEFIK_CONFIG_PATH", "/app/traefik-services.yml")

REDIS_L1_HOST: str = os.getenv("REDIS_L1_HOST", "redis-local")
REDIS_L1_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_L1_DB: int = int(os.getenv("REDIS_L1_DB", "0"))
REDIS_L1_PASSWORD: Optional[str] = os.getenv("REDIS_L1_PASSWORD", "scarerunner") or None

# ---------------------------------------------------------------------------
# Service routing configuration (consolidated)
# ---------------------------------------------------------------------------
# Each entry: service name → {port, rule, priority}
# Services not listed here are skipped (no port known → cannot route).
# Technical Debt: Port mapping and route rules are hardcoded.
# Phase 2: Could read from env var SERVICE_ROUTES_JSON or Redis values.

SERVICE_ROUTES: Dict[str, Dict] = {
    "backend": {
        "port": 5050,
        "rule": "PathPrefix(`/api`)",
        "priority": 50,
    },
    "vite": {
        "port": 5052,
        "rule": "PathPrefix(`/`)",
        "priority": 1,
    },
    "auth-proxy": {
        "port": 5055,
        "rule": "PathPrefix(`/artifacts`)",
        "priority": 100,
    },
}

# Backwards-compatible aliases kept for service_discovery helpers
SERVICE_PORT_MAPPING: Dict[str, int] = {
    name: cfg["port"] for name, cfg in SERVICE_ROUTES.items()
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("service-discovery")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _build_traefik_config(healthy_services: Set[str]) -> dict:
    """
    Build a Traefik dynamic YAML config dict from the set of healthy services.

    Services not present in SERVICE_ROUTES are logged and skipped.

    Args:
        healthy_services: Set of service names with ``port_opened: true``.

    Returns:
        Dict suitable for ``yaml.dump()`` as a Traefik File provider config.
    """
    routers: dict = {}
    services: dict = {}

    for name in sorted(healthy_services):
        route_cfg = SERVICE_ROUTES.get(name)
        if route_cfg is None:
            logger.warning(
                "No route config for service '%s' – skipping route generation", name
            )
            continue

        routers[name] = {
            "rule": route_cfg["rule"],
            "service": name,
            "entryPoints": ["http"],
            "priority": route_cfg["priority"],
        }
        services[name] = {
            "loadBalancer": {
                "servers": [{"url": f"http://{name}:{route_cfg['port']}"}]
            }
        }

    return {"http": {"routers": routers, "services": services}}


def _write_config_atomic(config: dict, path: str, max_retries: int = 5) -> None:
    """
    Write *config* as YAML to *path* using an atomic temp→rename pattern.

    This prevents Traefik from reading a partially-written file.

    Retries on EBUSY (file locking contention with Traefik File Provider)
    with exponential backoff.

    Args:
        config: Dict to serialise as YAML.
        path:   Destination file path (e.g. ``/app/traefik-services.yml``).
        max_retries: Max attempts before giving up.
    """
    import time

    dir_path = os.path.dirname(os.path.abspath(path))

    for attempt in range(max_retries):
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=dir_path, suffix=".tmp", delete=False
            ) as fh:
                yaml.dump(config, fh, default_flow_style=False, allow_unicode=True)
                tmp_path = fh.name
            os.replace(tmp_path, path)
            return  # Success
        except OSError as exc:
            # EBUSY (errno 16) = device or resource busy (file locking contention)
            if exc.errno == 16 and attempt < max_retries - 1:
                backoff = 0.1 * (2 ** attempt)  # 0.1s, 0.2s, 0.4s, 0.8s, ...
                logger.debug(
                    "Config write retry %d/%d (resource busy, waiting %fs)...",
                    attempt + 1,
                    max_retries,
                    backoff,
                )
                time.sleep(backoff)
                continue
            # Other errors or final retry exhausted
            raise


def _load_current_services(path: str) -> Set[str]:
    """
    Return the set of router names currently in the Traefik config file.

    Returns an empty set if the file is absent, empty, or malformed.

    Args:
        path: Path to the Traefik dynamic config file.

    Returns:
        Set of service/router names defined in the config.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            content = yaml.safe_load(fh)
        if not content or "http" not in content:
            return set()
        routers = content.get("http", {}).get("routers") or {}
        return set(routers.keys())
    except FileNotFoundError:
        return set()
    except (yaml.YAMLError, AttributeError) as exc:
        logger.warning("Cannot parse current config %s: %s", path, exc)
        return set()


# ---------------------------------------------------------------------------
# Redis scanning
# ---------------------------------------------------------------------------


async def scan_healthy_services(redis_client) -> Set[str]:
    """
    Scan Redis L1 for services with ``port_opened: true`` in their heartbeat.

    Key pattern: ``state:service:{name}:available``
    Value format: JSON ``{"port_opened": true|false|null, "timestamp": float}``

    Traefik itself is excluded from results.  Services whose value is not
    valid JSON (old ``"1"`` format) are also excluded.

    Args:
        redis_client: Connected ``redis.asyncio.Redis`` instance.

    Returns:
        Set of service names whose port health check passed.
    """
    healthy_services: Set[str] = set()
    async for key in redis_client.scan_iter(
        match="state:service:*:available", count=100
    ):
        key_str = key if isinstance(key, str) else key.decode()
        parts = key_str.split(":")
        # Expected: ['state', 'service', '{name}', 'available']
        if len(parts) < 4:
            continue
        service_name = parts[2]
        if service_name == "traefik":
            continue  # Traefik discovers others, not itself

        value = await redis_client.get(key)
        if value is None:
            continue

        try:
            data = json.loads(value)
            port_opened = data.get("port_opened")
        except (json.JSONDecodeError, AttributeError):
            logger.debug(
                "Service '%s' has non-JSON heartbeat value – skipping", service_name
            )
            continue

        if port_opened is True:
            healthy_services.add(service_name)

    return healthy_services


# ---------------------------------------------------------------------------
# Main discovery loop
# ---------------------------------------------------------------------------


async def discovery_loop() -> None:
    """
    Infinite loop: scan Redis → compare with current routes → rewrite config if changed.

    Sleeps ``SERVICE_DISCOVERY_INTERVAL`` seconds between cycles.
    Redis connection errors are logged and retried on the next cycle.
    """
    try:
        import redis.asyncio as aioredis  # type: ignore[import]
    except ImportError:
        logger.error("redis-py is not installed – service discovery disabled")
        return

    connect_kwargs = {
        "host": REDIS_L1_HOST,
        "port": REDIS_L1_PORT,
        "db": REDIS_L1_DB,
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_keepalive": True,
    }
    if REDIS_L1_PASSWORD:
        connect_kwargs["password"] = REDIS_L1_PASSWORD

    logger.info(
        "Starting service discovery daemon (interval=%ds, config=%s)",
        SERVICE_DISCOVERY_INTERVAL,
        TRAEFIK_CONFIG_PATH,
    )

    redis_client = None

    while True:
        try:
            if redis_client is None:
                redis_client = aioredis.Redis(**connect_kwargs)

            healthy_services = await scan_healthy_services(redis_client)
            current_services = _load_current_services(TRAEFIK_CONFIG_PATH)

            if healthy_services != current_services:
                added = healthy_services - current_services
                removed = current_services - healthy_services
                logger.info(
                    "Route changes detected: +%s -%s → writing config",
                    sorted(added),
                    sorted(removed),
                )
                config = _build_traefik_config(healthy_services)
                _write_config_atomic(config, TRAEFIK_CONFIG_PATH)
                logger.info(
                    "Config updated: active routes = %s",
                    sorted(healthy_services & set(SERVICE_PORT_MAPPING)),
                )
            else:
                logger.debug(
                    "No route changes (services: %s)", sorted(healthy_services)
                )

        except Exception as exc:
            logger.warning(
                "Discovery cycle failed: %s – retrying in %ds",
                exc,
                SERVICE_DISCOVERY_INTERVAL,
            )
            redis_client = None  # force reconnect on next cycle

        await asyncio.sleep(SERVICE_DISCOVERY_INTERVAL)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the service discovery daemon."""
    logger.info("Service discovery daemon starting...")
    asyncio.run(discovery_loop())


if __name__ == "__main__":
    main()
