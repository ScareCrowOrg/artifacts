"""
Standalone CentralHub HTTP Client for artifacts/canonical.

Adapted from backend/app/clients/centralhub_client.py to be self-contained
(no relative imports from the backend package).

Provides an interface for communicating with the CentralHub service:
  - Health checks
  - MongoDB proxy operations (find_one, find_many, insert_one, update_one, delete_one)
"""

import logging
import os
from typing import Any, Dict, List, Optional

from httpx import AsyncClient, HTTPError, TimeoutException

logger = logging.getLogger(__name__)


class CentralHubClient:
    """
    HTTP client for communicating with CentralHub service.

    CentralHub handles system-wide operations including MongoDB proxy
    with L2 caching and RBAC enforcement.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url or os.getenv("CENTRALHUB_URL", "http://localhost:5051")
        self.timeout = timeout
        self._client: Optional[AsyncClient] = None
        logger.info("CentralHub client configured for: %s", self.base_url)

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> Dict[str, Any]:
        """Check CentralHub health status."""
        try:
            client = await self._get_client()
            response = await client.get("/health")
            response.raise_for_status()
            return response.json()
        except TimeoutException as exc:
            logger.error("CentralHub health check timeout: %s", exc)
            raise
        except HTTPError as exc:
            logger.error("CentralHub health check failed: %s", exc)
            raise

    async def is_available(self) -> bool:
        """Check if CentralHub is reachable and healthy."""
        try:
            result = await self.health_check()
            return result.get("status") in ["healthy", "degraded"]
        except Exception as exc:
            logger.warning("CentralHub not available: %s", exc)
            return False

    async def find_one(
        self,
        collection: str,
        query: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> Optional[Dict[str, Any]]:
        """Find a single document via CentralHub proxy."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/find_one",
                json={"collection": collection, "query": query, "user_id": user_id, "caller": caller},
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data")
        except HTTPError as exc:
            logger.error("CentralHub find_one failed: %s", exc)
            if exc.response and exc.response.status_code == 403:
                return None
            raise

    async def find_many(
        self,
        collection: str,
        query: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = 0,
        sort: Optional[List[tuple]] = None,
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> List[Dict[str, Any]]:
        """Find multiple documents via CentralHub proxy."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/find_many",
                json={
                    "collection": collection,
                    "query": query or {},
                    "limit": limit,
                    "skip": skip,
                    "sort": sort,
                    "user_id": user_id,
                    "caller": caller,
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("data", [])
        except HTTPError as exc:
            logger.error("CentralHub find_many failed: %s", exc)
            if exc.response and exc.response.status_code == 403:
                return []
            raise

    async def insert_one(
        self,
        collection: str,
        document: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> Dict[str, Any]:
        """Insert a document via CentralHub proxy."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/insert_one",
                json={"collection": collection, "document": document, "user_id": user_id, "caller": caller},
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except HTTPError as exc:
            logger.error("CentralHub insert_one failed: %s", exc)
            raise

    async def update_one(
        self,
        collection: str,
        query: Dict[str, Any],
        update: Dict[str, Any],
        upsert: bool = False,
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> Dict[str, Any]:
        """Update a document via CentralHub proxy."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/update_one",
                json={
                    "collection": collection,
                    "query": query,
                    "update": update,
                    "upsert": upsert,
                    "user_id": user_id,
                    "caller": caller,
                },
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except HTTPError as exc:
            logger.error("CentralHub update_one failed: %s", exc)
            raise

    async def delete_one(
        self,
        collection: str,
        query: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> int:
        """Delete a document via CentralHub proxy."""
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/delete_one",
                json={"collection": collection, "query": query, "user_id": user_id, "caller": caller},
            )
            response.raise_for_status()
            return response.json().get("data", {}).get("deleted_count", 0)
        except HTTPError as exc:
            logger.error("CentralHub delete_one failed: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------

_centralhub_client: Optional[CentralHubClient] = None


def get_centralhub_client() -> CentralHubClient:
    """Get global CentralHub client singleton."""
    global _centralhub_client
    if _centralhub_client is None:
        _centralhub_client = CentralHubClient()
    return _centralhub_client


async def close_centralhub_client() -> None:
    """Close global CentralHub client."""
    global _centralhub_client
    if _centralhub_client:
        await _centralhub_client.close()
        _centralhub_client = None
