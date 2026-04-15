#!/usr/bin/env python3
"""
Vite heartbeat registration (fire-and-forget).

Starts BaseService heartbeat as background task and exits immediately.
The heartbeat task runs infinitely in background (daemon mode), registering
state:service:vite:available in Redis L1 every heartbeat_interval seconds.

Called by entrypoint.sh before npm run dev starts.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vite-heartbeat")


def main() -> None:
    """Start heartbeat as background task and exit."""
    # Log env vars for debugging
    import os
    logger.info("=== Vite Heartbeat Env Vars ===")
    logger.info(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'NOT SET')}")
    logger.info(f"WORKER_PORT: {os.getenv('WORKER_PORT', 'NOT SET')}")
    logger.info(f"HEARTBEAT_INTERVAL: {os.getenv('HEARTBEAT_INTERVAL', 'NOT SET')}")
    logger.info(f"HEARTBEAT_TTL: {os.getenv('HEARTBEAT_TTL', 'NOT SET')}")
    logger.info(f"REDIS_L1_HOST: {os.getenv('REDIS_L1_HOST', 'NOT SET')}")
    logger.info(f"REDIS_L1_PORT: {os.getenv('REDIS_L1_PORT', 'NOT SET')}")
    logger.info("================================")

    # Ensure artifacts is in path for canonical.shared imports
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        logger.warning("BaseService unavailable – heartbeat disabled: %s", exc)
        return

    async def keep_alive():
        """Start heartbeat and keep it running (continuous renewal)."""
        service = BaseService("vite", logger=logger)
        # Run heartbeat loop continuously - it will be renewed every heartbeat_interval
        await service.heartbeat()

    logger.info("Starting heartbeat registration...")
    try:
        asyncio.run(keep_alive())
        logger.info("✅ Heartbeat running continuously: state:service:vite:available")
    except Exception as exc:
        logger.warning("Heartbeat startup failed: %s", exc)


if __name__ == "__main__":
    main()
