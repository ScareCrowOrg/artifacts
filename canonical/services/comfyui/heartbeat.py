#!/usr/bin/env python3
"""
ComfyUI early heartbeat registration (one-shot).

Registers ``state:service:comfyui:available`` in Redis L1 *once* during
container boot with ``port_opened: false`` and a 300s TTL, then exits.
The continuous heartbeat loop is left to the wrapper (``wrapper/main.py``),
which overwrites this key with ``port_opened: true`` when it becomes ready.

This prevents the Launcher's heartbeat poll (120s timeout) from failing,
since the old flow only registered the key after ComfyUI + wrapper finished
starting (~3-5 min).

Called by ``entrypoint.sh`` before ComfyUI starts::

    python3 /app/artifacts/canonical/services/comfyui/heartbeat.py &
"""

import asyncio
import json
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("comfyui-heartbeat")

# One-shot TTL: covers model download (~6.9GB) + ComfyUI boot (~3 min).
# The wrapper's continuous heartbeat takes over well before this expires.
ONE_SHOT_TTL = 300


def main() -> None:
    """Register one-shot heartbeat and exit."""
    # Log env vars for debugging
    logger.info("=== ComfyUI Heartbeat Env Vars ===")
    logger.info(f"PYTHONPATH: {os.getenv('PYTHONPATH', 'NOT SET')}")
    logger.info(f"HEARTBEAT_INTERVAL: {os.getenv('HEARTBEAT_INTERVAL', 'NOT SET')}")
    logger.info(f"HEARTBEAT_TTL: {os.getenv('HEARTBEAT_TTL', 'NOT SET')}")
    logger.info(f"REDIS_L1_HOST: {os.getenv('REDIS_L1_HOST', 'NOT SET')}")
    logger.info(f"REDIS_L1_PORT: {os.getenv('REDIS_L1_PORT', 'NOT SET')}")
    logger.info("===================================")

    # Ensure artifacts root is on the module path so canonical.shared resolves.
    if "/app/artifacts" not in sys.path:
        sys.path.insert(0, "/app/artifacts")

    try:
        from canonical.shared.services.base_service import BaseService
    except ImportError as exc:
        logger.warning("BaseService unavailable – early heartbeat disabled: %s", exc)
        return

    async def _register_once() -> None:
        """Write a single heartbeat entry to Redis, then exit."""
        service = BaseService("comfyui", service_port=9090, logger=logger)
        import redis.asyncio as aioredis  # type: ignore[import]

        client = aioredis.Redis(
            host=service._redis_host,
            port=service._redis_port,
            db=service._redis_db,
            password=service._redis_password,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )
        try:
            value = json.dumps({
                "port_opened": False,
                "timestamp": time.time(),
            })
            await client.set(service._availability_key, value, ex=ONE_SHOT_TTL)
            logger.info(
                "Early heartbeat registered (one-shot, key=%s, TTL=%ds)",
                service._availability_key,
                ONE_SHOT_TTL,
            )
        except Exception as exc:
            logger.warning("Early heartbeat registration failed: %s", exc)
        finally:
            await client.aclose()

    try:
        asyncio.run(_register_once())
    except Exception as exc:
        logger.warning("Early heartbeat startup failed: %s", exc)


if __name__ == "__main__":
    main()
