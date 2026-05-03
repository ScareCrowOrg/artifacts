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

Redis key patterns scanned:
    state:service:{name}:available  →  JSON  {"port_opened": true|false|null, "timestamp": float}
    state:service:{name}:routing    →  JSON  {"wss": {"enabled": bool, "alias": str,
                                                       "upstream_port": int, "path": str}}

Services with ``port_opened: true`` are added to the Traefik config.
Services that also have a ``state:service:{name}:routing`` key with
``routing.wss.enabled: true`` get an additional WSS route with priority 110.
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
    # Auth Proxy is the ONLY ingress gatekeeper — no service has a direct Traefik route.
    # All traffic (HTTP, WebSocket, and /artifacts/*) goes through auth-proxy first:
    # - /artifacts/*: require valid sessionId → proxy to vite:5052 (RBAC enforced)
    # - /api/v1/auth/session-bind: bypass to backend (no auth required)
    # - /api/*, /viewers/*, /: require sessionId → proxy to backend or vite
    # - /wss/*: require sessionId → WebSocket tunnel to upstream
    # Vite (port 5052) has NO direct Traefik route — accessed only via auth-proxy.
    "auth-proxy": {
        "port": 5055,
        "rule": "PathPrefix(`/`)",
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
    level=logging.DEBUG,  # DEBUG to show all trace logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("service-discovery")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _build_traefik_config(healthy_services: Set[str], wss_routes: Optional[Dict[str, Dict]] = None) -> dict:
    """
    Build a Traefik dynamic YAML config dict from the set of healthy services.

    Services not present in SERVICE_ROUTES are logged and skipped.
    For each entry in *wss_routes* (service_name → routing.wss dict), an
    additional router/service is generated with priority 110 so it takes
    precedence over the auth-proxy catch-all (priority 100).

    Args:
        healthy_services: Set of service names with ``port_opened: true``.
        wss_routes: Optional mapping of service_name → routing.wss config dict.
                    Example: {"backend": {"alias": "events", "upstream_port": 5050,
                                          "path": "/wss/events"}}

    Returns:
        Dict suitable for ``yaml.dump()`` as a Traefik File provider config.
    """
    logger.debug("🔨 Building config for %d healthy services", len(healthy_services))
    routers: dict = {}
    services: dict = {}

    for name in sorted(healthy_services):
        route_cfg = SERVICE_ROUTES.get(name)
        if route_cfg is None:
            logger.debug(
                "  ⏭️  No static route config for service '%s' – skipping base route", name
            )
        else:
            logger.debug(
                "  ➕ Adding route for %s: rule=%s, port=%d, priority=%d",
                name,
                route_cfg["rule"],
                route_cfg["port"],
                route_cfg["priority"],
            )
            routers[name] = {
                "rule": route_cfg["rule"],
                "service": name,
                "entryPoints": ["http", "websecure"],
                "priority": route_cfg["priority"],
            }
            services[name] = {
                "loadBalancer": {
                    "servers": [{"url": f"http://{name}:{route_cfg['port']}"}]
                }
            }

    # ── WSS dynamic routes (priority 110) ────────────────────────────────────
    if wss_routes:
        for service_name, wss_cfg in sorted(wss_routes.items()):
            alias = wss_cfg.get("alias", "")
            upstream_port = wss_cfg.get("upstream_port")
            wss_path = wss_cfg.get("path", f"/wss/{alias}")

            if not alias or not upstream_port:
                logger.warning(
                    "  ⚠️  WSS config for '%s' missing alias or upstream_port – skipping",
                    service_name,
                )
                continue

            router_name = f"{service_name}-wss-{alias}"
            logger.debug(
                "  ➕ Adding WSS route '%s': PathPrefix(%s) → %s:%d (priority 110)",
                router_name, wss_path, service_name, upstream_port,
            )
            routers[router_name] = {
                "rule": f"PathPrefix(`{wss_path}`)",
                "service": router_name,
                "entryPoints": ["http", "websecure"],
                "priority": 110,
            }
            services[router_name] = {
                "loadBalancer": {
                    "servers": [{"url": f"http://{service_name}:{upstream_port}"}]
                }
            }

    logger.debug("✓ Config built with %d routers", len(routers))
    return {"http": {"routers": routers, "services": services}}


def _write_config_atomic(config: dict, path: str, max_retries: int = 20) -> None:
    """
    Write *config* as YAML to *path* using an atomic temp→rename pattern.

    This prevents Traefik from reading a partially-written file.

    Retries on EBUSY (file locking contention with Traefik File Provider)
    with exponential backoff. When mounted as volume from host, file locking
    can be severe; higher retry count needed.

    Args:
        config: Dict to serialise as YAML.
        path:   Destination file path (e.g. ``/app/traefik-services.yml``).
        max_retries: Max attempts before giving up (default 20 for volume mounts).
    """
    import time

    dir_path = os.path.dirname(os.path.abspath(path))
    logger.debug("💾 Starting atomic write to %s (max_retries=%d)", path, max_retries)

    for attempt in range(max_retries):
        try:
            logger.debug("  [attempt %d/%d] Creating temp file...", attempt + 1, max_retries)
            with tempfile.NamedTemporaryFile(
                mode="w", dir=dir_path, suffix=".tmp", delete=False
            ) as fh:
                logger.debug("  [attempt %d] Writing YAML to %s", attempt + 1, fh.name)
                yaml.dump(config, fh, default_flow_style=False, allow_unicode=True)
                tmp_path = fh.name
                logger.debug("  [attempt %d] YAML written (%d bytes)", attempt + 1, fh.tell())

            logger.debug("  [attempt %d] Renaming %s → %s", attempt + 1, tmp_path, path)
            os.replace(tmp_path, path)
            logger.debug("✅ Config written successfully on attempt %d/%d", attempt + 1, max_retries)
            return  # Success
        except OSError as exc:
            # EBUSY (errno 16) = device or resource busy (file locking contention)
            if exc.errno == 16 and attempt < max_retries - 1:
                backoff = 0.05 * (2 ** attempt)  # 0.05s, 0.1s, 0.2s, 0.4s, 0.8s, ...
                logger.debug(
                    "  [attempt %d] 🔄 Resource busy (EBUSY), retrying in %.2fs...",
                    attempt + 1,
                    backoff,
                )
                time.sleep(backoff)
                continue
            # Other errors or final retry exhausted
            logger.error(
                "❌ Config write FAILED after %d attempts: errno=%s, %s",
                attempt + 1,
                exc.errno,
                exc,
            )
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
    logger.debug("📂 Loading current config from %s...", path)
    try:
        with open(path, encoding="utf-8") as fh:
            content = yaml.safe_load(fh)
        if not content or "http" not in content:
            logger.debug("  📄 File exists but empty or no 'http' section")
            return set()
        routers = content.get("http", {}).get("routers") or {}
        current = set(routers.keys())
        logger.debug("  ✓ Loaded %d current routes: %s", len(current), sorted(current))
        return current
    except FileNotFoundError:
        logger.debug("  📄 File not found (first run?)")
        return set()
    except (yaml.YAMLError, AttributeError) as exc:
        logger.warning("  ⚠️  Cannot parse current config %s: %s", path, exc)
        return set()


async def scan_wss_routes(redis_client) -> Dict[str, Dict]:
    """
    Scan Redis L1 for WSS routing metadata published by the Launcher (Phase 8.1).

    Key pattern: ``state:service:{name}:routing``
    Value format: JSON ``{"wss": {"enabled": bool, "alias": str,
                                   "upstream_port": int, "path": str}}``

    Only entries with ``wss.enabled: true`` are returned.

    Args:
        redis_client: Connected ``redis.asyncio.Redis`` instance.

    Returns:
        Dict mapping service_name → routing.wss config for services that have
        WSS routing enabled.
    """
    wss_routes: Dict[str, Dict] = {}
    logger.debug("🔍 Scanning Redis for state:service:*:routing keys...")

    async for key in redis_client.scan_iter(
        match="state:service:*:routing", count=100
    ):
        key_str = key if isinstance(key, str) else key.decode()
        parts = key_str.split(":")
        # Expected: ['state', 'service', '{name}', 'routing']
        if len(parts) < 4:
            logger.debug("  ⚠️  Invalid routing key format: %s", key_str)
            continue
        service_name = parts[2]

        value = await redis_client.get(key)
        if value is None:
            continue

        try:
            data = json.loads(value)
            wss_cfg = data.get("wss")
            if not wss_cfg:
                logger.debug("  ⏭️  %s: no 'wss' key in routing data", service_name)
                continue
            if not wss_cfg.get("enabled"):
                logger.debug("  ⏭️  %s: wss.enabled=false – skipping", service_name)
                continue
            logger.debug(
                "  ✅ %s: WSS routing enabled (alias=%s, port=%s, path=%s)",
                service_name,
                wss_cfg.get("alias"),
                wss_cfg.get("upstream_port"),
                wss_cfg.get("path"),
            )
            wss_routes[service_name] = wss_cfg
        except (json.JSONDecodeError, AttributeError) as e:
            logger.debug("  ❌ %s: invalid routing JSON – %s", service_name, e)

    logger.debug("✓ WSS scan complete: found %d WSS routes", len(wss_routes))
    return wss_routes


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
    logger.debug("🔍 Scanning Redis for state:service:*:available keys...")

    async for key in redis_client.scan_iter(
        match="state:service:*:available", count=100
    ):
        key_str = key if isinstance(key, str) else key.decode()
        parts = key_str.split(":")
        # Expected: ['state', 'service', '{name}', 'available']
        if len(parts) < 4:
            logger.debug("  ⚠️  Invalid key format: %s", key_str)
            continue
        service_name = parts[2]
        if service_name == "traefik":
            logger.debug("  ⏭️  Skipping traefik (doesn't discover itself)")
            continue  # Traefik discovers others, not itself

        value = await redis_client.get(key)
        if value is None:
            logger.debug("  ❌ %s: no value in Redis", service_name)
            continue

        try:
            data = json.loads(value)
            port_opened = data.get("port_opened")
            timestamp = data.get("timestamp", "?")
            logger.debug(
                "  📌 %s: port_opened=%s (timestamp=%.1f)",
                service_name,
                port_opened,
                timestamp if isinstance(timestamp, (int, float)) else 0,
            )
        except (json.JSONDecodeError, AttributeError) as e:
            logger.debug(
                "  ❌ %s: invalid JSON – %s", service_name, e
            )
            continue

        if port_opened is True:
            logger.debug("  ✅ %s: HEALTHY (will route)", service_name)
            healthy_services.add(service_name)
        else:
            logger.debug("  ❌ %s: unhealthy (port_opened=%s)", service_name, port_opened)

    logger.debug("✓ Scan complete: found %d healthy services", len(healthy_services))
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
    cycle = 0

    while True:
        cycle += 1
        logger.debug("=" * 80)
        logger.debug("🔄 DISCOVERY CYCLE #%d (every %ds)", cycle, SERVICE_DISCOVERY_INTERVAL)
        logger.debug("=" * 80)

        try:
            if redis_client is None:
                logger.debug("📡 Connecting to Redis L1 (%s:%d)...", REDIS_L1_HOST, REDIS_L1_PORT)
                redis_client = aioredis.Redis(**connect_kwargs)
                logger.debug("✓ Redis connection established")

            healthy_services = await scan_healthy_services(redis_client)
            wss_routes = await scan_wss_routes(redis_client)

            # Build the canonical set of router names that *should* exist
            # (base services + WSS sub-routes) so change detection is accurate.
            # This logic must mirror the validation inside _build_traefik_config()
            # so expected_router_names matches the config file that will be written.
            expected_router_names: Set[str] = set()
            for name in healthy_services:
                if name in SERVICE_ROUTES:
                    expected_router_names.add(name)
            for svc_name, wss_cfg in wss_routes.items():
                alias = wss_cfg.get("alias", "")
                upstream_port = wss_cfg.get("upstream_port")
                # Only count this WSS route if _build_traefik_config() would generate it.
                if alias and upstream_port:
                    expected_router_names.add(f"{svc_name}-wss-{alias}")

            current_services = _load_current_services(TRAEFIK_CONFIG_PATH)
            logger.debug("Current config routes: %s", sorted(current_services))

            if expected_router_names != current_services:
                added = expected_router_names - current_services
                removed = current_services - expected_router_names
                logger.info(
                    "Route changes detected: +%s -%s → writing config",
                    sorted(added),
                    sorted(removed),
                )
                logger.debug("Building config for services: %s", sorted(healthy_services))
                config = _build_traefik_config(healthy_services, wss_routes)
                logger.debug("Config built, attempting atomic write to %s", TRAEFIK_CONFIG_PATH)
                try:
                    _write_config_atomic(config, TRAEFIK_CONFIG_PATH)
                    logger.info(
                        "✅ Config updated: active routes = %s",
                        sorted(expected_router_names),
                    )
                except Exception as exc:
                    logger.error(
                        "❌ Config write FAILED (exception): %s",
                        exc,
                        exc_info=True,
                    )
                    # Don't re-raise - continue to next cycle
                    continue
            else:
                logger.debug(
                    "No route changes (routers: %s)", sorted(expected_router_names)
                )

        except Exception as exc:
            logger.warning(
                "⚠️  Discovery cycle #%d failed: %s – retrying in %ds",
                cycle,
                exc,
            )
            redis_client = None  # force reconnect on next cycle

        logger.debug("⏳ Sleeping %ds until next cycle...", SERVICE_DISCOVERY_INTERVAL)
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
