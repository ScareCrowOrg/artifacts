"""Config Manager – Backend lazy-loading from Redis L1 with env-var fallback.

Provides a unified interface for services to retrieve configuration values.

Phase 1B: Reads from Redis L1 (``settings:{key}`` keys) with a fallback to
          environment variables.
Phase 2:  Will add TOTP-based secret decryption (``get_secret``).

Usage::

    from canonical.shared.config_manager import get_setting

    redis_host = get_setting("redis:host", fallback="redis-local")
    db_url = get_setting("backend:database_url")
"""

import json
import logging
import os
from typing import Any, Optional

__all__ = ["get_redis_client", "get_setting"]

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_L1_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_PASSWORD = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
REDIS_DB = int(os.getenv("REDIS_L1_DB", "0"))


def get_redis_client():
    """
    Return a synchronous Redis L1 client.

    Returns ``None`` when ``redis-py`` is not installed so callers can fall
    back gracefully without raising an import error.
    """
    try:
        import redis  # type: ignore[import]

        return redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=2,
        )
    except ImportError:
        logger.warning("redis-py not installed – Redis config lookup disabled")
        return None


def get_setting(key: str, fallback: Optional[str] = None) -> Any:
    """
    Retrieve a configuration value from Redis L1 with an env-var fallback.

    Lookup order:
      1. ``settings:{key}`` in Redis L1.
      2. Environment variable derived from ``key`` (colon-separated segments
         are joined with underscores and upper-cased, e.g.
         ``redis:password`` → ``REDIS_PASSWORD``).
      3. The explicit ``fallback`` argument (or ``None``).

    JSON-encoded values stored in Redis are automatically decoded.

    Args:
        key:      Dot/colon-separated setting path (e.g. ``"redis"`` or
                  ``"redis:password"``).
        fallback: Value to return when the key is absent everywhere.

    Phase 2:
        A companion ``get_secret(key, totp_seed)`` function will be added
        to decrypt secrets stored in ``secrets:{key}`` using the TOTP seed
        injected by the Launcher at startup.
    """
    client = get_redis_client()
    if client is not None:
        try:
            redis_key = f"settings:{key}"
            value = client.get(redis_key)
            if value is not None:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    return value
        except Exception as exc:  # noqa: BLE001 – redis-py raises varied subclasses
            logger.warning("Redis L1 lookup failed for '%s': %s", key, exc)

    # Fallback: environment variable (UPPER_SNAKE_CASE)
    env_key = key.upper().replace(":", "_")
    env_value = os.getenv(env_key)
    if env_value is not None:
        return env_value

    return fallback


# ---------------------------------------------------------------------------
# Phase 2 placeholder
# ---------------------------------------------------------------------------
# def get_secret(key: str, totp_seed: str) -> str:
#     """Decrypt a secret from Redis L1 using the TOTP seed."""
#     ...
