#!/usr/bin/env python3
"""
BaseService: Reusable Redis heartbeat registration for ScareVerse services.

Provides self-registration of service availability keys in Redis L1 so that
GateKeeper and service-discovery.py can detect running services.

Usage (fire-and-forget pattern)::

    import asyncio
    from fastapi import FastAPI
    from canonical.shared.services.base_service import BaseService

    app = FastAPI()

    @app.on_event("startup")
    async def startup():
        service = BaseService("backend", service_port=5050)
        asyncio.create_task(service.heartbeat())

Redis key written::

    state:service:{service_name}:available  →  JSON  (TTL = key_ttl seconds)

Heartbeat value format::

    {"port_opened": true|false|null, "timestamp": 1713085200.123}

    - ``port_opened: true``  – HTTP GET /health returned 200 (service healthy)
    - ``port_opened: false`` – Port not responding or health check failed
    - ``port_opened: null``  – No port configured (cannot verify health)
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional

__all__ = ["BaseService"]


class BaseService:
    """
    Registers a Redis L1 availability key for a named service.

    The :meth:`heartbeat` coroutine is designed to be started as a
    fire-and-forget background task via ``asyncio.create_task(service.heartbeat())``.
    It writes ``state:service:{service_name}:available`` every
    ``heartbeat_interval`` seconds with ``key_ttl`` as the Redis TTL.

    The heartbeat value is a JSON object::

        {"port_opened": true|false|null, "timestamp": <unix_float>}

    ``port_opened`` reflects whether an HTTP GET to ``http://localhost:{service_port}/health``
    returned 200.  It is ``null`` when no port is configured.

    Only services with ``port_opened: true`` are included in Traefik routes
    by ``service-discovery.py``.

    If Redis is unavailable the loop logs a warning and retries on the next
    iteration without raising; if ``redis-py`` is not installed the loop
    exits gracefully after logging a warning.

    Args:
        service_name:   Logical service identifier (e.g. ``"backend"``).
        service_port:   Port the service listens on for HTTP health checks.
                        Defaults to ``WORKER_PORT`` env var or ``None``.
                        When ``None``, ``port_opened`` is always ``null``.
        redis_host:     Redis L1 host.  Defaults to ``REDIS_L1_HOST`` env var or
                        ``"redis-local"``.
        redis_port:     Redis L1 port.  Defaults to ``REDIS_L1_PORT`` env var or
                        ``6380``.
        redis_db:       Redis L1 database index.  Defaults to ``REDIS_L1_DB`` env
                        var or ``0``.
        redis_password: Redis password.  Defaults to ``REDIS_L1_PASSWORD``
                        env var or ``"scarerunner"``.  Pass ``None`` to disable auth.
        heartbeat_interval: Seconds between key refreshes.  Defaults to
                        ``HEARTBEAT_INTERVAL`` (Launcher-injected) or ``REDIS_HEARTBEAT_INTERVAL`` env var or ``60``.
        key_ttl:        Redis TTL in seconds for the availability key.  Defaults to
                        ``HEARTBEAT_TTL`` (Launcher-injected) or ``heartbeat_interval * 3`` when ``None``.
        logger:         Optional logger.  Defaults to the module logger.
    """

    def __init__(
        self,
        service_name: str,
        service_port: Optional[int] = None,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_db: Optional[int] = None,
        redis_password: Optional[str] = None,
        heartbeat_interval: Optional[int] = None,
        key_ttl: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.service_name = service_name

        # Resolve service port: explicit arg → WORKER_PORT env var → None
        if service_port is not None:
            self._service_port: Optional[int] = service_port
        else:
            worker_port_env = os.getenv("WORKER_PORT")
            self._service_port = int(worker_port_env) if worker_port_env else None

        self._redis_host = redis_host or os.getenv("REDIS_L1_HOST", "redis-local")
        self._redis_port = redis_port if redis_port is not None else int(
            os.getenv("REDIS_L1_PORT", "6380")
        )
        self._redis_db = redis_db if redis_db is not None else int(
            os.getenv("REDIS_L1_DB", "0")
        )

        # Explicit None means "use env / default"; explicit "" means no password
        if redis_password is None:
            env_val = os.getenv("REDIS_L1_PASSWORD", "scarerunner")
            self._redis_password: Optional[str] = env_val or None
        else:
            self._redis_password = redis_password or None

        # Try HEARTBEAT_INTERVAL (Launcher-injected) first, fall back to REDIS_HEARTBEAT_INTERVAL
        self._heartbeat_interval = heartbeat_interval if heartbeat_interval is not None else int(
            os.getenv("HEARTBEAT_INTERVAL") or os.getenv("REDIS_HEARTBEAT_INTERVAL", "60")
        )
        # Try HEARTBEAT_TTL (Launcher-injected) first, fall back to heartbeat_interval * 3
        self._key_ttl = key_ttl if key_ttl is not None else int(
            os.getenv("HEARTBEAT_TTL") or (self._heartbeat_interval * 3)
        )
        self._availability_key = f"state:service:{service_name}:available"

        self._logger = logger or logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def _check_port_health(self) -> Optional[bool]:
        """
        Perform an HTTP GET to ``http://localhost:{service_port}/health``.

        Returns:
            ``True``  – port responded with HTTP 200.
            ``False`` – port not responding, connection refused, or timeout (2s).
            ``None``  – no port configured (``service_port`` not set).
        """
        if self._service_port is None:
            return None

        try:
            import httpx  # type: ignore[import]
        except ImportError:
            self._logger.warning(
                "httpx not installed – port health check disabled for '%s'",
                self.service_name,
            )
            return None

        url = f"http://localhost:{self._service_port}/health"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception as exc:
            self._logger.debug(
                "Port health check failed for '%s' on port %d: %s",
                self.service_name,
                self._service_port,
                exc,
            )
            return False

    async def heartbeat(self) -> None:
        """
        Infinite heartbeat loop – refresh the availability key in Redis L1.

        Designed to run as a fire-and-forget ``asyncio`` task::

            asyncio.create_task(service.heartbeat())

        The loop:
        1. Connects to Redis L1 (lazy, reconnects on failure).
        2. Checks port health via HTTP GET /health (if port is configured).
        3. Sets ``state:service:{name}:available`` = JSON with ``port_opened``
           and ``timestamp`` with TTL.
        4. Sleeps for ``heartbeat_interval`` seconds.
        5. On any Redis error: logs a warning, resets client, retries next cycle.

        Heartbeat value format::

            {"port_opened": true|false|null, "timestamp": 1713085200.123}

        Returns immediately (without looping) if ``redis-py`` is not installed.
        """
        try:
            import redis.asyncio as aioredis  # type: ignore[import]
        except ImportError:
            self._logger.warning(
                "redis-py not installed – heartbeat registration disabled for '%s'",
                self.service_name,
            )
            return

        connect_kwargs = {
            "host": self._redis_host,
            "port": self._redis_port,
            "db": self._redis_db,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_keepalive": True,
        }
        if self._redis_password:
            connect_kwargs["password"] = self._redis_password

        client = None  # aioredis.Redis instance, recreated on connection failure

        self._logger.info(
            "Heartbeat starting for service '%s' (interval=%ds, ttl=%ds, key=%s, port=%s)",
            self.service_name,
            self._heartbeat_interval,
            self._key_ttl,
            self._availability_key,
            self._service_port,
        )

        while True:
            try:
                if client is None:
                    client = aioredis.Redis(**connect_kwargs)

                port_opened = await self._check_port_health()
                value = json.dumps(
                    {"port_opened": port_opened, "timestamp": time.time()}
                )
                await client.set(self._availability_key, value, ex=self._key_ttl)
                self._logger.debug(
                    "Heartbeat: %s refreshed (TTL %ds, port_opened=%s)",
                    self._availability_key,
                    self._key_ttl,
                    port_opened,
                )
            except Exception as exc:
                self._logger.warning(
                    "Heartbeat failed for '%s': %s – will retry in %ds",
                    self._availability_key,
                    exc,
                    self._heartbeat_interval,
                )
                client = None  # force reconnect on next iteration

            await asyncio.sleep(self._heartbeat_interval)

    async def cleanup(self) -> None:
        """Delete the heartbeat key immediately on shutdown.

        Call this on SIGTERM/SIGINT so that GateKeeper stops routing jobs to
        this service right away instead of waiting up to ``key_ttl`` seconds
        for the Redis TTL to expire.

        Safe to call even when ``redis-py`` is not installed or Redis is
        unreachable; errors are logged as warnings and swallowed.

        Example::

            import signal, asyncio
            service = BaseService("ollama")
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(service.cleanup()),
                )
        """
        try:
            import redis.asyncio as aioredis  # type: ignore[import]
        except ImportError:
            self._logger.warning(
                "redis-py not installed – heartbeat cleanup skipped for '%s'",
                self.service_name,
            )
            return

        connect_kwargs: dict = {
            "host": self._redis_host,
            "port": self._redis_port,
            "db": self._redis_db,
            "decode_responses": True,
            "socket_connect_timeout": 5,
        }
        if self._redis_password:
            connect_kwargs["password"] = self._redis_password

        try:
            client = aioredis.Redis(**connect_kwargs)
            deleted = await client.delete(self._availability_key)
            if deleted:
                self._logger.info(
                    "✅ Heartbeat key deleted: %s", self._availability_key
                )
            else:
                self._logger.debug(
                    "Heartbeat key already absent: %s", self._availability_key
                )
            await client.aclose()
        except Exception as exc:
            self._logger.warning(
                "Heartbeat cleanup failed for '%s': %s",
                self.service_name,
                exc,
            )
