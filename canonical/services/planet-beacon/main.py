#!/usr/bin/env python3
"""
planet-beacon — Entry point.

Dual heartbeat service:
  L1: BaseService heartbeat → Redis L1 (state:service:planet-beacon:available)
  L2: Presence loop         → CentralHub → Redis L2 (planet:presence:{planet_id})

The L1 heartbeat enables GateKeeper service discovery on the local planet.
The L2 presence loop broadcasts planet availability to the Cockpit via CentralHub.
"""

import asyncio
import logging
import signal
import sys

import config
from viewer_scanner import scan_viewers
from presence_client import send_presence

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("planet-beacon")


async def presence_loop() -> None:
    """
    Continuously scan viewers and send presence heartbeats to CentralHub.

    Runs every ``config.BEACON_INTERVAL`` seconds until the event loop is
    stopped or a cancellation is received.
    """
    logger.info(
        "Presence loop starting (planet_id=%s fqdn=%s interval=%ds ttl=%ds)",
        config.PLANET_ID,
        config.TUNNEL_FQDN,
        config.BEACON_INTERVAL,
        config.PRESENCE_TTL,
    )
    while True:
        try:
            viewers = await scan_viewers(config.VIEWERS_BASE_DIR)
            await send_presence(config, viewers)
        except Exception as exc:
            logger.warning("Presence loop iteration failed: %s — retrying in %ds", exc, config.BEACON_INTERVAL)

        await asyncio.sleep(config.BEACON_INTERVAL)


async def main() -> None:
    """Start L1 heartbeat task and run L2 presence loop."""
    # Ensure artifacts root is on path so canonical.shared resolves inside container.
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    # ── L1: BaseService heartbeat (Redis L1) ──────────────────────────────────
    base_service = None
    try:
        from canonical.shared.services.base_service import BaseService  # type: ignore[import]

        base_service = BaseService("planet-beacon", logger=logger)
        asyncio.create_task(base_service.heartbeat())
        logger.info("✅ BaseService L1 heartbeat task started")
    except ImportError as exc:
        logger.warning("BaseService unavailable — L1 heartbeat disabled: %s", exc)

    # ── Handle SIGTERM/SIGINT for graceful shutdown ────────────────────────────
    loop = asyncio.get_running_loop()

    async def _shutdown() -> None:
        logger.info("Shutdown signal received — cleaning up…")
        if base_service is not None:
            await base_service.cleanup()
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    # ── L2: Presence loop (CentralHub → Redis L2) ─────────────────────────────
    await presence_loop()


if __name__ == "__main__":
    asyncio.run(main())
