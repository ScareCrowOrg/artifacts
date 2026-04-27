#!/usr/bin/env python3
"""
ScareRegistryGate heartbeat registration (fire-and-forget).

Starts a BaseService heartbeat task and keeps it running continuously.
The task registers ``state:service:scare-registry-gate:available`` in Redis L1,
giving GateKeeper a signal that the registry gateway is alive without probing
HTTP endpoints.

Called by ``entrypoint.sh`` before the Rust binary starts.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("scare-registry-gate-heartbeat")

HEARTBEAT_KEY = "state:service:scare-registry-gate:available"


def main() -> None:
    """Start heartbeat as a continuous background task."""
    import os

    logger.info("=== ScareRegistryGate Heartbeat Env Vars ===")
    logger.info(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'NOT SET')}")
    logger.info(f"WORKER_PORT: {os.getenv('WORKER_PORT', 'NOT SET')}")
    logger.info(f"HEARTBEAT_INTERVAL: {os.getenv('HEARTBEAT_INTERVAL', 'NOT SET')}")
    logger.info(f"HEARTBEAT_TTL: {os.getenv('HEARTBEAT_TTL', 'NOT SET')}")
    logger.info(f"REDIS_L1_HOST: {os.getenv('REDIS_L1_HOST', 'NOT SET')}")
    logger.info(f"REDIS_L1_PORT: {os.getenv('REDIS_L1_PORT', 'NOT SET')}")
    logger.info("=============================================")

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
        service = BaseService(
            "scare-registry-gate",
            service_port=5678,
            logger=logger,
        )
        await service.heartbeat()

    logger.info("Starting heartbeat registration for key: %s", HEARTBEAT_KEY)
    try:
        asyncio.run(keep_alive())
        logger.info("✅ Heartbeat running continuously: %s", HEARTBEAT_KEY)
    except Exception as exc:
        logger.warning("Heartbeat startup failed: %s", exc)


if __name__ == "__main__":
    main()
