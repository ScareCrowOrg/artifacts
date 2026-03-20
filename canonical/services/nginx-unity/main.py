#!/usr/bin/env python3
"""
Nginx Unity Service Worker – FastAPI health sidecar.

This sidecar runs in the foreground alongside an Nginx reverse-proxy process
(managed by ``entrypoint.sh``) and exposes HTTP health-check endpoints used by
Launcher and GateKeeper.

Endpoints:
    GET /health             – 200 when sidecar is running.
    GET /health/detailed    – 200 with upstream availability status.

On startup the service registers itself in Redis L1 via the :class:`BaseService`
heartbeat (key ``state:service:nginx-unity:available``).

On SIGTERM / SIGINT the key is deleted immediately so GateKeeper stops routing
before the TTL expires.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx
import uvicorn
from fastapi import FastAPI

import config
from canonical.shared.services.base_service import BaseService

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global state ─────────────────────────────────────────────────────────────

_service: Optional[BaseService] = None
_heartbeat_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
_http_client: Optional[httpx.AsyncClient] = None

# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):  # type: ignore[type-arg]
    """Start heartbeat and HTTP client on startup; clean up on shutdown."""
    global _service, _heartbeat_task, _http_client

    _http_client = httpx.AsyncClient(timeout=config.UPSTREAM_CHECK_TIMEOUT)

    _service = BaseService(
        service_name=config.WORKER_ID,
        redis_host=config.REDIS_L1_HOST,
        redis_port=config.REDIS_L1_PORT,
        redis_db=config.REDIS_L1_DB,
        redis_password=config.REDIS_L1_PASSWORD,
        heartbeat_interval=config.HEARTBEAT_INTERVAL,
        key_ttl=config.HEARTBEAT_TTL,
        logger=logger,
    )
    _heartbeat_task = asyncio.create_task(_service.heartbeat())
    logger.info(
        "✅ Nginx Unity sidecar started – heartbeat key: state:service:%s:available",
        config.WORKER_ID,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if _heartbeat_task and not _heartbeat_task.done():
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass

    if _service:
        await _service.cleanup()

    if _http_client:
        await _http_client.aclose()

    logger.info("Nginx Unity sidecar stopped.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Nginx Unity Health Sidecar",
    description="Health-check sidecar for the Nginx Unity reverse-proxy service worker",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _check_upstream(name: str, address: str) -> str:
    """
    Probe an upstream host and return ``"up"`` or ``"down"``.

    Args:
        name: Human-readable upstream label (for logging).
        address: ``host:port`` string (no scheme).

    Returns:
        ``"up"`` when the upstream responds with any HTTP status;
        ``"down"`` on connection error or timeout.
    """
    if _http_client is None:
        return "down"
    try:
        url = f"http://{address}"
        await _http_client.get(url)
        return "up"
    except Exception as exc:
        logger.debug("Upstream %s (%s) unreachable: %s", name, address, exc)
        return "down"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> Dict[str, str]:
    """Basic liveness probe – returns 200 when the sidecar is running."""
    return {"status": "healthy"}


@app.get("/health/detailed")
async def health_detailed() -> Dict[str, Any]:
    """
    Detailed health report including upstream availability.

    Probes each configured upstream and returns their individual status.

    Returns:
        JSON with overall status and per-upstream ``"up"`` / ``"down"`` values.
    """
    upstream_status: Dict[str, str] = {}
    for name, address in config.UPSTREAMS.items():
        upstream_status[name] = await _check_upstream(name, address)

    return {
        "status": "healthy",
        "upstreams": upstream_status,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        app,
        host=config.SIDECAR_HOST,
        port=config.SIDECAR_PORT,
        log_level=config.LOG_LEVEL,
    )
