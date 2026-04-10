"""
Config Manager – Unified configuration resolution for ScareVerse services.

Provides a single ``get_config(key)`` entry point that intelligently routes
configuration lookups to the correct backend:

  1. ``vault.<key>``  → SecretClient (TOTP-authenticated secret from Launcher).
  2. ``<key>``        → Redis L1 ``settings:{key}`` (published by Launcher).
  3. Fallback         → ``os.getenv(KEY_UPPER_SNAKE_CASE)``.
  4. Returns ``None`` when the key is absent from all sources.

In-memory cache (60 s TTL) is applied to **settings** values so that
frequently-accessed non-secret config (e.g. ``api_host``, ``api_port``) does
not incur a Redis round-trip on every call.  Secrets are **never** cached.

Namespaced logging prefix ``[Config]`` allows easy log filtering:

    [Config] Resolving 'api_host'...
    [Config] Found in Redis (settings:api_host). Source: REDIS_L1
    [Config] Resolving 'vault.redis_password'...
    [Config] Detected vault prefix. Requesting from SecretClient...
    [Config] SecretClient: secret retrieved. Source: VAULT

Environment variables required to use Redis / SecretClient:
    REDIS_L1_HOST  – Redis L1 hostname   (default: localhost).
    REDIS_L1_PORT  – Redis L1 port       (default: 6380).
    REDIS_L1_PASSWORD – Redis L1 password (default: scarerunner).
    TOTP_SEED      – 64-char hex seed for SecretClient (injected by Launcher).
    SERVICE_NAME   – Logical service identifier       (default: backend).

Usage::

    from artifacts.shared.config_manager import get_config

    api_host = get_config("api_host")                   # settings or env
    redis_pw = get_config("vault.redis_password")       # SecretClient
"""

import json
import logging
import os
import time
from typing import Any, Optional

__all__ = ["get_config", "clear_cache"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level Redis configuration
# ---------------------------------------------------------------------------

REDIS_HOST: str = os.getenv("REDIS_L1_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_L1_PORT", "6380"))
REDIS_PASSWORD: str = os.getenv("REDIS_L1_PASSWORD", "")
REDIS_DB: int = int(os.getenv("REDIS_L1_DB", "0"))

# Warn if Redis password not set in non-local environments
if not REDIS_PASSWORD and os.getenv("ENV") not in (None, "local", "development"):
    logger.warning("[Config] REDIS_L1_PASSWORD not set – Redis may reject connections")

# ---------------------------------------------------------------------------
# In-memory settings cache (non-secrets only)
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS: int = 60

# Maps cache key → (value, expiry_timestamp)
_cache: dict[str, tuple[Any, float]] = {}


def _cache_get(key: str) -> tuple[bool, Any]:
    """Return (hit, value) from the in-memory cache."""
    entry = _cache.get(key)
    if entry is None:
        return False, None
    value, expiry = entry
    if time.monotonic() > expiry:
        del _cache[key]
        return False, None
    return True, value


def _cache_set(key: str, value: Any) -> None:
    """Store a value in the cache with a 60-second TTL."""
    _cache[key] = (value, time.monotonic() + _CACHE_TTL_SECONDS)


def clear_cache() -> None:
    """Flush the in-memory settings cache (useful in tests)."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Redis helper
# ---------------------------------------------------------------------------


def _get_redis_client():
    """Return a synchronous Redis client, or ``None`` if unavailable."""
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
        logger.warning("[Config] redis-py not installed – Redis config lookup disabled")
        return None


# ---------------------------------------------------------------------------
# SecretClient helper (lazy import to avoid circular imports)
# ---------------------------------------------------------------------------


def _get_secret_client():
    """
    Build a SecretClient using the ``TOTP_SEED`` environment variable.

    Returns ``None`` when ``TOTP_SEED`` is not set or the import fails.
    """
    seed = os.getenv("TOTP_SEED")
    if not seed:
        logger.warning("[Config] TOTP_SEED not set – SecretClient unavailable (will fallback to env vars)")
        return None
    try:
        from .secret_client import SecretClient

        return SecretClient(seed)
    except (ImportError, AttributeError, ValueError) as exc:
        logger.warning("[Config] Failed to create SecretClient: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_config(key: str) -> Optional[str]:
    """
    Resolve a configuration value using the following strategy:

    1. If ``key`` starts with ``vault.``:
       Strip the prefix and request the secret from SecretClient (TOTP).
       Falls back to ``os.getenv`` when SecretClient is unavailable.

    2. Otherwise: look up ``settings:{key}`` in Redis L1 (with 60 s cache).
       Falls back to ``os.getenv(KEY)`` when Redis is unavailable or the
       key is absent.

    Args:
        key: Configuration key, e.g. ``"api_host"`` or ``"vault.redis_password"``.

    Returns:
        The resolved value as a string, or ``None`` when not found anywhere.

    Note: During module initialization, connection errors are logged at DEBUG level
    to avoid blocking startup. The fallback to env vars allows app to load even
    if Launcher/Redis are not yet ready.
    """
    logger.debug("[Config] Resolving '%s'...", key)

    # ------------------------------------------------------------------
    # Path 1: vault.* → SecretClient
    # ------------------------------------------------------------------
    if key.startswith("vault."):
        secret_name = key[len("vault."):]
        logger.debug("[Config] Detected vault prefix. Requesting from SecretClient...")
        client = _get_secret_client()
        if client is not None:
            try:
                value = client.request_secret(secret_name)
                if value is not None:
                    logger.debug("[Config] SecretClient: secret retrieved. Source: VAULT")
                    return value
                logger.warning("[Config] SecretClient returned None for '%s'", secret_name)
            except (ConnectionError, TimeoutError, OSError) as exc:
                logger.warning(
                    "[Config] SecretClient error for '%s': %s – falling back to env",
                    secret_name,
                    exc,
                )
        # Fallback: env var with VAULT_ prefix stripped
        env_key = secret_name.upper().replace(":", "_").replace(".", "_").replace("-", "_")
        env_value = os.getenv(env_key)
        if env_value is not None:
            logger.debug("[Config] Found in env (fallback). Source: ENV key=%s", env_key)
            return env_value
        logger.debug("[Config] Key '%s' not found anywhere", key)
        return None

    # ------------------------------------------------------------------
    # Path 2: settings → Redis L1 (with cache) then env fallback
    # ------------------------------------------------------------------

    # Check in-memory cache first.
    hit, cached_value = _cache_get(key)
    if hit:
        logger.debug("[Config] Cache hit for '%s'. Source: CACHE", key)
        return cached_value

    # Try Redis L1.
    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            redis_key = f"settings:{key}"
            raw = redis_client.get(redis_key)
            if raw is not None:
                # JSON-decode if possible (Launcher serializes values as JSON).
                try:
                    value = json.loads(raw)
                    if not isinstance(value, str):
                        value = str(value)
                except (json.JSONDecodeError, ValueError):
                    value = raw
                logger.debug(
                    "[Config] Found in Redis (%s). Source: REDIS_L1", redis_key
                )
                _cache_set(key, value)
                return value
        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
            logger.warning("[Config] Redis L1 lookup failed for '%s': %s", key, exc)
        except Exception as exc:  # noqa: BLE001 – catch redis-version-specific errors
            logger.warning("[Config] Redis L1 lookup failed for '%s': %s", key, exc)

    # Fallback: environment variable (UPPER_SNAKE_CASE).
    env_key = key.upper().replace(":", "_").replace(".", "_").replace("-", "_")
    env_value = os.getenv(env_key)
    if env_value is not None:
        logger.debug("[Config] Found in env. Source: ENV key=%s", env_key)
        _cache_set(key, env_value)
        return env_value

    logger.debug("[Config] Key '%s' not found anywhere", key)
    return None
