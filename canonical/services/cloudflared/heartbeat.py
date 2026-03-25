#!/usr/bin/env python3
"""
Cloudflared heartbeat registration (fire-and-forget).

Starts BaseService heartbeat as background task and exits immediately.
The heartbeat task runs infinitely in background (daemon mode), registering
state:service:cloudflared:available in Redis L1 every heartbeat_interval seconds.

Called by entrypoint.sh at container startup.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("cloudflared-heartbeat")


def main() -> None:
    """Start heartbeat as background task and exit."""
    # Ensure artifacts is in path for canonical.shared imports
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        logger.warning("BaseService unavailable – heartbeat disabled: %s", exc)
        return

    async def start_heartbeat():
        """Start heartbeat and exit (task runs in background)."""
        service = BaseService("cloudflared", logger=logger)
        # Create background task (fire-and-forget)
        asyncio.create_task(service.heartbeat())
        # Give it a moment to initialize
        await asyncio.sleep(1)

    logger.info("Starting heartbeat registration (fire-and-forget)...")
    try:
        asyncio.run(start_heartbeat())
        logger.info("✅ Heartbeat task started: state:service:cloudflared:available")
    except Exception as exc:
        logger.warning("Heartbeat startup failed: %s", exc)


if __name__ == "__main__":
    main()
