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

    # Log to both logger and stdout so docker logs captures it
    env_msg = f"""
=== Ollama Heartbeat Env Vars ===
PYTHONPATH: {os.getenv('PYTHONPATH', 'NOT SET')}
OLLAMA_HOST: {os.getenv('OLLAMA_HOST', 'NOT SET')}
HEARTBEAT_INTERVAL: {os.getenv('HEARTBEAT_INTERVAL', 'NOT SET')}
HEARTBEAT_TTL: {os.getenv('HEARTBEAT_TTL', 'NOT SET')}
REDIS_L1_HOST: {os.getenv('REDIS_L1_HOST', 'NOT SET')}
REDIS_L1_PORT: {os.getenv('REDIS_L1_PORT', 'NOT SET')}
=================================="""

    print(env_msg, file=sys.stderr)
    logger.info(env_msg)

    # Ensure artifacts is in path for canonical.shared imports
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        error_msg = f"❌ BaseService unavailable – heartbeat disabled: {exc}"
        print(error_msg, file=sys.stderr)
        logger.warning(error_msg)
        return

    async def keep_alive():
        """Start heartbeat and keep it running (continuous renewal)."""
        try:
            msg = "Creating BaseService instance for heartbeat..."
            print(f"[heartbeat] {msg}", file=sys.stderr)
            logger.info(msg)

            service = BaseService("ollama", service_port=11434, logger=logger)

            msg = "✅ BaseService instance created, starting heartbeat loop..."
            print(f"[heartbeat] {msg}", file=sys.stderr)
            logger.info(msg)

            # Run heartbeat loop continuously - it will be renewed every heartbeat_interval
            await service.heartbeat()

            msg = "❌ Heartbeat loop exited unexpectedly"
            print(f"[heartbeat] {msg}", file=sys.stderr)
            logger.warning(msg)
        except Exception as exc:
            error_msg = f"❌ keep_alive() failed: {exc}"
            print(f"[heartbeat] {error_msg}", file=sys.stderr)
            logger.error(error_msg, exc_info=True)
            raise

    startup_msg = "Starting Ollama heartbeat registration..."
    print(startup_msg, file=sys.stderr)
    logger.info(startup_msg)

    try:
        asyncio.run(keep_alive())
        success_msg = "✅ Heartbeat running continuously: state:service:ollama:available"
        print(success_msg, file=sys.stderr)
        logger.info(success_msg)
    except Exception as exc:
        error_msg = f"❌ Heartbeat startup failed: {exc}"
        print(error_msg, file=sys.stderr)
        logger.warning(error_msg)


if __name__ == "__main__":
    main()
