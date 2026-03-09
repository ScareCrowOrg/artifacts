"""
CentralHub Redis HTTP Client

Provides HTTP-based Redis operations via CentralHub with RBAC.
Implements the same interface as redis-py for easy migration.

Reference: Phase 1B Redis HTTP Abstraction
Usage: docs/issues/redis-survey/DEVELOPER_QUICK_START.md

NOTE: This file is a copy of backend/app/clients/centralhub_redis_client.py
included here so that the GateKeeper Docker image (which only copies
worker/gatekeeper/*.py) can import it without requiring the full backend.
Keep both files in sync when making changes.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

logger = logging.getLogger(__name__)


class CentralHubRedisClient:
    """
    HTTP client for Redis operations via CentralHub.

    Provides redis-py compatible interface using HTTP endpoints.
    Handles authentication, connection pooling, and error handling.
    """

    def __init__(
        self,
        auth_token: str,
        base_url: str = "http://centralhub:8080",
        timeout: float = 310.0,
    ):
        """
        Initialize CentralHub Redis client.

        Args:
            auth_token: JWT token or service account token
            base_url: CentralHub URL (default: http://centralhub:8080)
            timeout: Request timeout in seconds (default: 310s for long-polling)
        """
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

        # Create HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.auth_token}"},
            timeout=self.timeout,
            limits=httpx.Limits(
                max_keepalive_connections=50, max_connections=100, keepalive_expiry=30.0
            ),
        )

        logger.debug("CentralHubRedisClient initialized: %s", self.base_url)

    async def rpush(self, queue_name: str, job_data: Dict[str, Any]) -> str:
        """
        Enqueue job to Redis queue via HTTP.

        Args:
            queue_name: Queue name (e.g., "ollama-jobs", "sd-jobs")
            job_data: Job data dictionary

        Returns:
            job_id: Unique job identifier

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        try:
            response = await self.client.post(
                "/api/redis/jobs/enqueue",
                json={"queue_name": queue_name, "job_data": job_data},
            )
            response.raise_for_status()
            result = response.json()
            return result["job_id"]

        except httpx.HTTPStatusError as e:
            logger.error("Failed to enqueue job: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Failed to enqueue job: %s", e)
            raise

    async def brpop(
        self,
        keys: Union[str, List[str]],
        timeout: int = 300,
    ) -> Optional[Tuple[str, str]]:
        """
        Dequeue the next job from one of the given queue(s) via HTTP.

        Implements the redis-py brpop interface so that callers (e.g.
        MultiSourcePooler) can use the same call pattern for both direct
        Redis L1 (aioredis) and HTTP-based Redis L2 (CentralHub).

        When multiple queue names are provided the method checks each queue
        in order, blocking only on the last one for the full *timeout*
        duration.  All other queues are checked non-blocking (timeout=0).

        Args:
            keys: Queue name or list of queue names.
            timeout: Maximum seconds to block on the last queue (default 300s).

        Returns:
            Tuple of (queue_name, raw_job_json_string) or None if timeout.
        """
        if isinstance(keys, (list, tuple)):
            queue_names = list(keys)
        else:
            queue_names = [keys]

        for i, queue_name in enumerate(queue_names):
            # Non-blocking for all but the last queue; last queue gets full timeout
            check_timeout = timeout if i == len(queue_names) - 1 else 0
            try:
                response = await self.client.post(
                    "/api/redis/jobs/dequeue",
                    json={"queue_name": queue_name, "timeout": check_timeout},
                )
                response.raise_for_status()
                result = response.json()

                if result.get("job_id") is not None:
                    job_data = result.get("job_data", {})
                    raw = job_data if isinstance(job_data, str) else json.dumps(job_data)
                    return (queue_name, raw)

            except httpx.HTTPStatusError as e:
                logger.error(
                    "Failed to dequeue from %s: %s - %s",
                    queue_name,
                    e.response.status_code,
                    e.response.text,
                )
                raise
            except Exception as e:
                logger.error("Failed to dequeue from %s: %s", queue_name, e)
                raise

        return None

    async def hgetall(self, key: str) -> Dict[str, Any]:
        """
        Get all fields of a job status hash via HTTP.

        Args:
            key: Status key or job_id

        Returns:
            Dictionary of hash fields
        """
        try:
            # Extract job_id from key
            if ":" in key:
                job_id = key.split(":")[-1]
            else:
                job_id = key

            response = await self.client.get(f"/api/redis/jobs/{job_id}/status")
            response.raise_for_status()
            result = response.json()
            return result["fields"]

        except httpx.HTTPStatusError as e:
            logger.error("Failed to get status: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Failed to get status: %s", e)
            raise

    async def hset(self, key: str, mapping: Dict[str, Any]) -> None:
        """
        Set hash fields via HTTP (internal worker operation).

        Args:
            key: Status key or job_id
            mapping: Fields to set
        """
        try:
            # Extract job_id from key
            if ":" in key:
                job_id = key.split(":")[-1]
            else:
                job_id = key

            # Determine status from mapping
            job_status = mapping.get("status", "processing")

            response = await self.client.post(
                f"/api/redis/jobs/{job_id}/status",
                json={
                    "status": job_status,
                    "fields": {k: v for k, v in mapping.items() if k != "status"},
                },
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error("Failed to set status: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Failed to set status: %s", e)
            raise

    async def dequeue(
        self, queue_name: str, timeout: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Dequeue next job from queue (worker operation).

        Args:
            queue_name: Queue to dequeue from
            timeout: BRPOP timeout in seconds

        Returns:
            Job data or None if timeout
        """
        try:
            response = await self.client.post(
                "/api/redis/jobs/dequeue",
                json={"queue_name": queue_name, "timeout": timeout},
            )
            response.raise_for_status()
            result = response.json()

            if result["job_id"] is None:
                return None

            return {
                "job_id": result["job_id"],
                "user_id": result["user_id"],
                "data": result["job_data"],
            }

        except httpx.HTTPStatusError as e:
            logger.error("Failed to dequeue job: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Failed to dequeue job: %s", e)
            raise

    async def requeue(
        self, job_id: str, queue_name: str, reason: str = "vram_management"
    ) -> None:
        """
        Requeue job (worker operation for VRAM management).

        Args:
            job_id: Job identifier
            queue_name: Queue to requeue to
            reason: Reason for requeue
        """
        try:
            response = await self.client.post(
                "/api/redis/jobs/requeue",
                json={"job_id": job_id, "queue_name": queue_name, "reason": reason},
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.error("Failed to requeue job: %s - %s", e.response.status_code, e.response.text)
            raise
        except Exception as e:
            logger.error("Failed to requeue job: %s", e)
            raise

    async def delete(self, key: str) -> int:
        """
        Delete key via HTTP.

        Args:
            key: Key to delete

        Returns:
            Number of keys deleted (0 or 1)
        """
        try:
            # For job results, we'll use a DELETE endpoint (to be implemented)
            # For Phase 1B, we'll skip this as results auto-expire
            logger.warning("DELETE operation not yet implemented via HTTP: %s", key)
            return 0

        except Exception as e:
            logger.error("Failed to delete key: %s", e)
            raise

    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set TTL on key via HTTP.

        **Current behaviour**: no-op — TTL is automatically managed by
        CentralHub when ``hset`` is called via ``POST /api/redis/jobs/{id}/status``.
        CentralHub applies a default TTL to every job-status update, so a
        separate ``EXPIRE`` call is not required.

        If CentralHub ever exposes a dedicated ``/api/redis/jobs/{id}/expire``
        endpoint the implementation below can be uncommented and activated:

        .. code-block:: python

            job_id = key.split(":")[-1] if ":" in key else key
            response = await self.client.post(
                f"/api/redis/jobs/{job_id}/expire",
                json={"ttl_seconds": seconds},
            )
            response.raise_for_status()

        Args:
            key: Status key (e.g. ``state:job:<job_id>``).
            seconds: Desired TTL in seconds (informational, not sent to API).

        Returns:
            True (always, for compatibility with redis-py interface).
        """
        # TTL is automatically applied by CentralHub on each hset call.
        logger.debug("EXPIRE no-op – TTL managed by CentralHub: key=%s ttl=%ss", key, seconds)
        return True

    async def close(self):
        """Close HTTP client and release connections."""
        await self.client.aclose()
        logger.debug("CentralHubRedisClient closed")
