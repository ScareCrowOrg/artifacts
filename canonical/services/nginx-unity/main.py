#!/usr/bin/env python3
"""
Nginx Unity Service Worker – heartbeat sidecar.

This sidecar runs in the foreground alongside Nginx Unit (managed by
``entrypoint.sh``) and registers the nginx-unity service in Redis L1 via the
:class:`BaseService` heartbeat mechanism.

Routes are registered dynamically by the Node.js orchestrator sidecar via the
Nginx Unit HTTP API after vite and backend services become available.

On startup the service registers itself in Redis L1:
    key ``state:service:nginx-unity:available``

On SIGTERM / SIGINT the key is deleted immediately so GateKeeper stops routing
before the TTL expires.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

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

_service = None
_heartbeat_task = None


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

    logger.info("Nginx Unity sidecar stopped.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Nginx Unity Heartbeat Sidecar",
    description="Heartbeat sidecar for the Nginx Unity reverse-proxy service worker",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(
        app,
        host=config.SIDECAR_HOST,
        port=config.SIDECAR_PORT,
        log_level=config.LOG_LEVEL,
    )
