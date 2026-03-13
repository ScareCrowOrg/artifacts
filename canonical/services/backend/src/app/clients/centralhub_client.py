"""
CentralHub HTTP Client
Provides interface for backend to communicate with CentralHub service

Phase 1: Tiered-Data Architecture
- MongoDB proxy operations (find_one, find_many, insert_one, update_one, delete_one)
- Transparent L2 caching via CentralHub
- RBAC enforcement at Hub level
"""

import logging
import os
from typing import Any, Dict, List, Optional

from httpx import AsyncClient, HTTPError, TimeoutException

logger = logging.getLogger(__name__)


class CentralHubClient:
    """
    HTTP client for communicating with CentralHub service

    CentralHub is the centralized infrastructure service running in Kubernetes
    that handles system-wide operations. This client provides a clean interface
    for the local backend to interact with it.

    Phase 1: MongoDB proxy operations with L2 caching
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize CentralHub client

        Args:
            base_url: CentralHub base URL (default: from CENTRALHUB_URL env var)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv(
            "CENTRALHUB_URL",
            "http://localhost:5051",  # Default to local K8s cluster via port-forward
        )
        self.timeout = timeout
        self._client: Optional[AsyncClient] = None

        logger.info("CentralHub client configured for: %s", self.base_url)

    async def _get_client(self) -> AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = AsyncClient(
                base_url=self.base_url, timeout=self.timeout, follow_redirects=True
            )
        return self._client

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> Dict[str, Any]:
        """
        Check CentralHub health status

        Returns:
            Health status dictionary with service info

        Raises:
            httpx.HTTPError: If request fails
            httpx.TimeoutException: If request times out
        """
        try:
            client = await self._get_client()
            response = await client.get("/health")
            response.raise_for_status()

            data = response.json()
            logger.debug("CentralHub health check: %s", data)
            return data

        except TimeoutException as e:
            logger.error("CentralHub health check timeout: %s", e)
            raise
        except HTTPError as e:
            logger.error("CentralHub health check failed: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error during CentralHub health check: %s", e)
            raise

    async def is_available(self) -> bool:
        """
        Check if CentralHub is available

        Returns:
            True if CentralHub is reachable and healthy, False otherwise
        """
        try:
            result = await self.health_check()
            return result.get("status") in ["healthy", "degraded"]
        except Exception as e:
            logger.warning("CentralHub not available: %s", e)
            return False

    # Phase 1: MongoDB Operations

    async def find_one(
        self,
        collection: str,
        query: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> Optional[Dict[str, Any]]:
        """
        Find single document via CentralHub proxy

        Args:
            collection: Collection name
            query: MongoDB query filter
            user_id: User ID for multi-tenant isolation
            caller: Calling service identifier

        Returns:
            Document if found, None otherwise

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/find_one",
                json={
                    "collection": collection,
                    "query": query,
                    "user_id": user_id,
                    "caller": caller,
                },
            )
            response.raise_for_status()

            result = response.json()
            logger.debug("find_one(%s): from_cache=%s", collection, result.get('from_cache', False))
            return result.get("data")

        except HTTPError as e:
            logger.error("CentralHub find_one failed: %s", e)
            if e.response and e.response.status_code == 403:
                # RBAC denied - propagate as None (caller should handle)
                return None
            raise
        except Exception as e:
            logger.error("Unexpected error in find_one: %s", e)
            raise

    async def find_many(
        self,
        collection: str,
        query: Dict[str, Any] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = 0,
        sort: Optional[List[tuple]] = None,
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> List[Dict[str, Any]]:
        """
        Find multiple documents via CentralHub proxy

        Args:
            collection: Collection name
            query: MongoDB query filter
            limit: Maximum number of results
            skip: Number of results to skip
            sort: Sort specification
            user_id: User ID for multi-tenant isolation
            caller: Calling service identifier

        Returns:
            List of documents

        Raises:
            httpx.HTTPError: If request fails
        """
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
            logger.debug(
                "find_many(%s): %s docs, from_cache=%s",
                collection, len(result.get('data', [])), result.get('from_cache', False)
            )
            return result.get("data", [])

        except HTTPError as e:
            logger.error("CentralHub find_many failed: %s", e)
            if e.response and e.response.status_code == 403:
                # RBAC denied - return empty list
                return []
            raise
        except Exception as e:
            logger.error("Unexpected error in find_many: %s", e)
            raise

    async def insert_one(
        self,
        collection: str,
        document: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> Dict[str, Any]:
        """
        Insert document via CentralHub proxy

        Args:
            collection: Collection name
            document: Document to insert
            user_id: User ID for multi-tenant isolation (will be injected)
            caller: Calling service identifier

        Returns:
            Inserted document with _id

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/insert_one",
                json={
                    "collection": collection,
                    "document": document,
                    "user_id": user_id,
                    "caller": caller,
                },
            )
            response.raise_for_status()

            result = response.json()
            logger.debug("insert_one(%s): inserted", collection)
            return result.get("data", {})

        except HTTPError as e:
            logger.error("CentralHub insert_one failed: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error in insert_one: %s", e)
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
        """
        Update document via CentralHub proxy

        Args:
            collection: Collection name
            query: Query filter to match document
            update: Update operations
            upsert: Create if not exists
            user_id: User ID for multi-tenant isolation
            caller: Calling service identifier

        Returns:
            Update result (matched_count, modified_count, upserted_id)

        Raises:
            httpx.HTTPError: If request fails
        """
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

            result = response.json()
            logger.debug("update_one(%s): matched=%s, modified=%s", collection, result.get('data', {}).get('matched_count', 0), result.get('data', {}).get('modified_count', 0))
            return result.get("data", {})

        except HTTPError as e:
            logger.error("CentralHub update_one failed: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error in update_one: %s", e)
            raise

    async def delete_one(
        self,
        collection: str,
        query: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
    ) -> int:
        """
        Delete document via CentralHub proxy

        Args:
            collection: Collection name
            query: Query filter to match document
            user_id: User ID for multi-tenant isolation
            caller: Calling service identifier

        Returns:
            Number of documents deleted (0 or 1)

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            client = await self._get_client()
            response = await client.post(
                "/api/proxy/database/delete_one",
                json={
                    "collection": collection,
                    "query": query,
                    "user_id": user_id,
                    "caller": caller,
                },
            )
            response.raise_for_status()

            result = response.json()
            deleted_count = result.get("data", {}).get("deleted_count", 0)
            logger.debug("delete_one(%s): deleted=%s", collection, deleted_count)
            return deleted_count

        except HTTPError as e:
            logger.error("CentralHub delete_one failed: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error in delete_one: %s", e)
            raise


# Global client instance
_centralhub_client: Optional[CentralHubClient] = None


def get_centralhub_client() -> CentralHubClient:
    """
    Get global CentralHub client instance (singleton pattern)

    Returns:
        CentralHub client instance
    """
    global _centralhub_client
    if _centralhub_client is None:
        _centralhub_client = CentralHubClient()
    return _centralhub_client


async def close_centralhub_client():
    """Close global CentralHub client"""
    global _centralhub_client
    if _centralhub_client:
        await _centralhub_client.close()
        _centralhub_client = None
