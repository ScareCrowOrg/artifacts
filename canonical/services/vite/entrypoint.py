#!/usr/bin/env python3
"""
Vite service entrypoint.

Starts a Redis L1 heartbeat in a background daemon thread, then runs
``npm run dev`` in the foreground as PID 1.

The heartbeat writes ``state:service:vite:available`` to Redis L1 every
``heartbeat_interval`` seconds (default: 60s, TTL: 180s).  If Redis is
unavailable the heartbeat logs a warning and retries — it never blocks Vite startup.

Dependencies:
  - redis (pip)  — installed at image build time
  - canonical.shared.services.base_service  — from /app/artifacts mount

Usage (set in Dockerfile CMD):
  CMD ["python", "/app/entrypoint.py"]
"""

import asyncio
import logging
import os
import sys
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vite-entrypoint")


def _run_heartbeat() -> None:
    """Run the BaseService heartbeat loop in a dedicated event loop (daemon thread)."""
    import os
    import sys

    # Ensure /app/artifacts is in sys.path so canonical.shared can be imported
    _artifacts = "/app/artifacts"
    if _artifacts not in sys.path:
        sys.path.insert(0, _artifacts)

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        logger.warning("BaseService unavailable – heartbeat disabled: %s", exc)
        return

    async def _loop() -> None:
        service = BaseService("vite", logger=logger)
        await service.heartbeat()  # runs forever

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_loop())
    except Exception as exc:
        logger.warning("Heartbeat loop exited: %s", exc)
    finally:
        loop.close()


def main() -> None:
    logger.info("🚀 Starting Vite service...")

    heartbeat_thread = threading.Thread(target=_run_heartbeat, daemon=True, name="heartbeat")
    heartbeat_thread.start()
    logger.info("✅ Heartbeat thread started: state:service:vite:available")

    # Debug: check if VITE_TRACE is in environment
    vite_trace = os.environ.get("VITE_TRACE", "NOT_FOUND")
    vite_debug = os.environ.get("VITE_DEBUG", "NOT_FOUND")
    logger.info("Environment check: VITE_TRACE=%s, VITE_DEBUG=%s", vite_trace, vite_debug)

    # Change to artifacts directory and replace this process with npm run dev
    # Using os.execvpe() with os.environ ensures npm dev runs as PID 1 with FULL environment inheritance
    logger.info("Starting npm run dev (/app/artifacts)...")
    os.chdir("/app/artifacts")
    os.execvpe("npm", ["npm", "run", "dev"], os.environ)


if __name__ == "__main__":
    main()
