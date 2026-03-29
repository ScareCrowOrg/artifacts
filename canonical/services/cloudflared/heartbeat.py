#!/usr/bin/env python3
"""
Cloudflared heartbeat registration (foreground, keep-alive).

Starts BaseService heartbeat and keeps the container alive indefinitely.
The heartbeat loop runs infinitely in the foreground (PID 1), registering
state:service:cloudflared:available in Redis L1 every heartbeat_interval seconds.

Docker requires PID 1 to stay alive. This process IS PID 1 - if it exits,
the container enters restart loop.

Called by entrypoint.sh (with exec) at container startup.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cloudflared-heartbeat")


async def main() -> None:
    """Start heartbeat and keep it running forever (blocking foreground process)."""
    # Ensure artifacts is in path for canonical.shared imports
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        logger.error("❌ BaseService unavailable – cannot start heartbeat: %s", exc)
        # Exit with error status so container knows something is wrong
        sys.exit(1)

    service = BaseService("cloudflared", logger=logger)

    logger.info("🚀 Starting cloudflared heartbeat (PID 1, foreground)...")
    logger.info("   Registering state:service:cloudflared:available in Redis L1")

    try:
        # Await the heartbeat loop directly - this keeps the process alive forever
        # If heartbeat raises an exception, the container will crash (graceful failure)
        await service.heartbeat()
    except KeyboardInterrupt:
        logger.info("⚙️ Heartbeat interrupted (Ctrl+C)")
        sys.exit(0)
    except Exception as exc:
        logger.error("❌ Heartbeat loop failed: %s", exc, exc_info=True)
        # Exit with error status so Docker knows the service is unhealthy
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚙️ Shutdown requested")
        sys.exit(0)
    except Exception as exc:
        logger.error("❌ Fatal error: %s", exc, exc_info=True)
        sys.exit(1)
