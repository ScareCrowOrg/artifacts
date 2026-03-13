"""
Phase 1B Client Initialization - Redis L1 and CentralHub.

This module provides initialization functions for Phase 1B components:
- Redis L1 client (unified local cache)
- CentralHub HTTP client (MongoDB proxy)

Configuration is loaded from environment variables defined in docker-compose.scarerunner.yml.
"""

import logging
import os
from typing import Optional

import redis.asyncio as aioredis

from .centralhub_client import CentralHubClient

logger = logging.getLogger(__name__)


def get_redis_l1_client() -> Optional[aioredis.Redis]:
    """
    Initialize Redis L1 (local) client for unified cache.

    Reads configuration from environment variables:
    - REDIS_L1_ENABLED (default: true)
    - REDIS_L1_HOST (default: redis-local)
    - REDIS_L1_PORT (default: 6379)
    - REDIS_L1_DB (default: 0)
    - REDIS_L1_PASSWORD (default: scarerunner)

    Returns:
        Redis async client or None if disabled/unavailable
    """
    enabled = os.getenv("REDIS_L1_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.info("Redis L1 disabled (REDIS_L1_ENABLED=false)")
        return None

    host = os.getenv("REDIS_L1_HOST", "redis-local")
    port = int(os.getenv("REDIS_L1_PORT", "6379"))
    db = int(os.getenv("REDIS_L1_DB", "0"))
    password = os.getenv("REDIS_L1_PASSWORD", "scarerunner")

    try:
        client = aioredis.Redis(
            host=host,
            port=port,
            db=db,
            password=password if password else None,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

        # Test connection (blocking, but fast)
        # Note: In production, this should be async, but for initialization we block
        import asyncio

        try:
            asyncio.get_event_loop().run_until_complete(client.ping())
            logger.info("Redis L1 client initialized (host=%s, port=%s)", host, port)
            return client
        except RuntimeError:
            # No event loop - this is okay, just skip ping
            logger.info("Redis L1 client initialized (host=%s, port=%s) - skipped ping", host, port)
            return client

    except Exception as e:
        logger.warning("Failed to initialize Redis L1 client: %s", e)
        return None


def get_centralhub_client() -> Optional[CentralHubClient]:
    """
    Initialize CentralHub HTTP client for MongoDB proxy.

    Reads configuration from environment variables:
    - CENTRALHUB_ENABLED (default: false)
    - CENTRALHUB_URL (default: http://host.docker.internal:5051)

    Returns:
        CentralHubClient or None if disabled/unavailable
    """
    enabled = os.getenv("CENTRALHUB_ENABLED", "false").lower() == "true"
    if not enabled:
        logger.info("CentralHub disabled (CENTRALHUB_ENABLED=false)")
        return None

    base_url = os.getenv("CENTRALHUB_URL", "http://host.docker.internal:5051")

    try:
        client = CentralHubClient(
            base_url=base_url,
            enabled=True,
            timeout=30.0,
        )
        logger.info("CentralHub client initialized (base_url=%s)", base_url)
        return client
    except Exception as e:
        logger.warning("Failed to initialize CentralHub client: %s", e)
        return None
