#!/usr/bin/env python3
"""
Ollama heartbeat registration (fire-and-forget).

Starts a BaseService heartbeat task and exits immediately.
The task registers ``state:service:ollama:available`` in Redis L1, giving
GateKeeper a signal that Ollama is alive without probing HTTP endpoints.

Called by ``entrypoint.sh`` before Ollama starts.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ollama-heartbeat")


def main() -> None:
    """Start heartbeat as a fire-and-forget task and exit."""
    import os
    logger.info("=== Ollama Heartbeat Env Vars ===")
    logger.info(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'NOT SET')}")
    logger.info(f"OLLAMA_HOST: {os.getenv('OLLAMA_HOST', 'NOT SET')}")
    logger.info(f"HEARTBEAT_INTERVAL: {os.getenv('HEARTBEAT_INTERVAL', 'NOT SET')}")
    logger.info(f"HEARTBEAT_TTL: {os.getenv('HEARTBEAT_TTL', 'NOT SET')}")
    logger.info(f"REDIS_L1_HOST: {os.getenv('REDIS_L1_HOST', 'NOT SET')}")
    logger.info(f"REDIS_L1_PORT: {os.getenv('REDIS_L1_PORT', 'NOT SET')}")
    logger.info("==================================")

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
        service = BaseService("ollama", service_port=11434, logger=logger)
        # Run heartbeat loop continuously - it will be renewed every heartbeat_interval
        await service.heartbeat()

    logger.info("Starting Ollama heartbeat registration...")
    try:
        asyncio.run(keep_alive())
        logger.info("✅ Heartbeat running continuously: state:service:ollama:available")
    except Exception as exc:
        logger.warning("Heartbeat startup failed: %s", exc)


if __name__ == "__main__":
    main()
