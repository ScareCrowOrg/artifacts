#!/usr/bin/env python3
"""
Traefik heartbeat registration (fire-and-forget).

Starts a BaseService heartbeat task and exits immediately.
The task registers ``state:service:traefik:available`` in Redis L1.

Called by ``entrypoint.sh`` before the container waits::

    python3 /app/artifacts/canonical/services/traefik/heartbeat.py || true
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("traefik-heartbeat")


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

    async def _keep_alive() -> None:
        service = BaseService("traefik", logger=logger)
        await service.heartbeat()

    logger.info("Starting initial heartbeat registration (fire-and-forget)...")
    try:
        asyncio.run(_keep_alive())
        logger.info("✅ Heartbeat running continuously")
    except Exception as exc:
        logger.warning("Heartbeat startup failed: %s", exc)


if __name__ == "__main__":
    main()
