#!/usr/bin/env python3
"""
Backend heartbeat registration (fire-and-forget).

Starts a BaseService heartbeat task and exits immediately.
The task registers ``state:service:backend:available`` in Redis L1, giving
GateKeeper a signal that the backend is alive without probing HTTP endpoints.

The backend's FastAPI startup event (``app.main``) registers a continuous
background heartbeat loop.  This script provides the initial registration
*before* uvicorn finishes loading, so the Launcher's heartbeat check can pass
even during a cold start.

Called by ``entrypoint.sh`` before uvicorn is launched::

    python3 /app/artifacts/canonical/services/backend/heartbeat.py || true
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("backend-heartbeat")


def main() -> None:
    """Start heartbeat as a fire-and-forget task and exit."""
    # Ensure artifacts root is on the module path so canonical.shared resolves.
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        logger.warning("BaseService unavailable – initial heartbeat disabled: %s", exc)
        return

    async def _register() -> None:
        service = BaseService("backend", logger=logger)
        asyncio.create_task(service.heartbeat())
        # Allow the task to complete its first iteration before we exit.
        await asyncio.sleep(1)

    logger.info("Starting initial heartbeat registration (fire-and-forget)...")
    try:
        asyncio.run(_register())
        logger.info("✅ Heartbeat registered: state:service:backend:available")
    except Exception as exc:
        logger.warning("Heartbeat startup failed: %s", exc)


if __name__ == "__main__":
    main()
