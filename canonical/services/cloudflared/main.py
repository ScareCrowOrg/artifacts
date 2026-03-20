#!/usr/bin/env python3
"""
Cloudflared Service Worker – FastAPI health sidecar.

This sidecar runs alongside the ``cloudflare/cloudflared`` binary (managed
by the Dockerfile CMD / supervisor) and exposes HTTP health-check endpoints
so Launcher and GateKeeper can monitor tunnel availability.

Endpoints:
    GET /health             – 200 when sidecar is running.
    GET /health/detailed    – 200 with tunnel process status and config summary.

On startup the service registers itself in Redis L1 via the :class:`BaseService`
heartbeat (key ``state:service:cloudflared:available``).

On SIGTERM / SIGINT the key is deleted immediately so GateKeeper stops routing
before the TTL expires.
"""

import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI

import config
from canonical.shared.services.base_service import BaseService

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global state ─────────────────────────────────────────────────────────────

_service: Optional[BaseService] = None
_heartbeat_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):  # type: ignore[type-arg]
    """Start heartbeat on startup; clean up on shutdown."""
    global _service, _heartbeat_task

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
        "✅ Cloudflared sidecar started – heartbeat key: state:service:%s:available",
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

    logger.info("Cloudflared sidecar stopped.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cloudflared Health Sidecar",
    description="Health-check sidecar for the Cloudflare tunnel service worker",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _cloudflared_process_running() -> bool:
    """Return True if a ``cloudflared`` process is found in the process table."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "cloudflared"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> Dict[str, str]:
    """Basic liveness probe – returns 200 when the sidecar is running."""
    return {"status": "healthy"}


@app.get("/health/detailed")
async def health_detailed() -> Dict[str, Any]:
    """
    Detailed health report including tunnel process status and config summary.

    Returns:
        JSON object with status, tunnel process state, tunnel name, and ingress
        rule count.
    """
    tunnel_running = _cloudflared_process_running()
    tunnel_token_configured = bool(config.TUNNEL_TOKEN)

    return {
        "status": "healthy",
        "tunnel": {
            "name": config.TUNNEL_NAME,
            "process_running": tunnel_running,
            "token_configured": tunnel_token_configured,
            "ingress_rules_count": len(config.INGRESS_RULES),
        },
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        app,
        host=config.HEALTH_HOST,
        port=config.HEALTH_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
