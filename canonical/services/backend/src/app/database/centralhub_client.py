"""
CentralHub HTTP Client - Proxy for MongoDB Operations.

This client provides HTTP-based access to MongoDB operations via the CentralHub
proxy endpoints. It replaces direct pymongo usage in HybridDatabase with HTTP calls.

Architecture:
- ScareRunner uses this client to communicate with CentralHub
- CentralHub validates requests (RBAC, whitelist) and proxies to MongoDB
- Results are cached in CentralHub's L2 Redis
- Results are returned to ScareRunner for L1 Redis caching

Security:
- All requests authenticated via JWT token
- user_id automatically injected from JWT at CentralHub
- Collection whitelist enforced at CentralHub
- Multi-tenant isolation guaranteed

Performance:
- L1 cache at ScareRunner (this layer checks before calling)
- L2 cache at CentralHub (reduces MongoDB load)
- Async HTTP calls (non-blocking)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, TypeVar

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class CentralHubClient:
    """
    HTTP client for CentralHub proxy operations.

    Provides async methods for database operations routed through CentralHub's
    proxy endpoints (/api/proxy/database/*).
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        enabled: bool = True,
    ):
        """
        Initialize CentralHub client.

        Args:
            base_url: CentralHub base URL (e.g., "http://localhost:5051")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            enabled: Whether CentralHub integration is enabled
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.enabled = enabled

        # Initialize httpx client
        self._client: Optional[httpx.AsyncClient] = None

        if self.enabled:
            logger.info("CentralHubClient initialized (base_url=%s)", self.base_url)
        else:
            logger.info("CentralHubClient disabled (CENTRALHUB_ENABLED=false)")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx client."""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self):
        """Close the HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.debug("CentralHubClient closed")

    def _prepare_jwt_headers_and_user_id(
        self, user_id: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], Dict[str, str]]:
        """
        Extract JWT token from context and prepare headers for CentralHub.

        Args:
            user_id: Optional user_id to use (extracted from JWT if not provided)

        Returns:
            Tuple of (token, user_id, headers):
                - token: JWT token if available, None otherwise
                - user_id: User ID (from argument or extracted from JWT)
                - headers: Dict with Authorization header if token present
        """
        try:
            from ..auth.context import get_current_token, get_user_id_from_token

            token = get_current_token()

            # If no user_id provided, try to extract from JWT
            if not user_id and token:
                user_id = get_user_id_from_token(token)
        except ImportError:
            logger.debug("JWT context not available, proceeding without token")
            token = None

        # Prepare headers with JWT token for CentralHub validation
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.debug("Forwarding JWT to CentralHub for authentication")

        return token, user_id, headers

    async def find_one(
        self,
        collection: str,
        query: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single document via CentralHub proxy.

        Args:
            collection: Collection name
            query: Query filter (e.g., {"_id": "artifact-123"})
            user_id: User ID for multi-tenant isolation

        Returns:
            Document dict or None if not found

        Raises:
            httpx.HTTPStatusError: If request fails
            httpx.TimeoutException: If request times out
        """
        if not self.enabled:
            logger.debug("CentralHub disabled, returning None")
            return None

        client = await self._get_client()

        # Prepare JWT headers and extract user_id if needed
        token, user_id, headers = self._prepare_jwt_headers_and_user_id(user_id)

        payload = {
            "collection": collection,
            "query": query,
        }
        if user_id:
            payload["user_id"] = user_id

        try:
            response = await client.post(
                "/api/proxy/database/find_one",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("document")

        except httpx.TimeoutException:
            logger.warning("CentralHub timeout on find_one: collection=%s, query=%s", collection, query)
            raise

        except httpx.HTTPStatusError as e:
            logger.error(
                "CentralHub HTTP error on find_one: status=%s, collection=%s, query=%s",
                e.response.status_code, collection, query
            )
            raise

    async def find_many(
        self,
        collection: str,
        query: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find multiple documents via CentralHub proxy.

        Args:
            collection: Collection name
            query: Query filter (optional, returns all if None)
            user_id: User ID for multi-tenant isolation
            limit: Maximum number of documents to return

        Returns:
            List of document dicts (may be empty)

        Raises:
            httpx.HTTPStatusError: If request fails
            httpx.TimeoutException: If request times out
        """
        if not self.enabled:
            logger.debug("CentralHub disabled, returning empty list")
            return []

        client = await self._get_client()

        # Prepare JWT headers and extract user_id if needed
        token, user_id, headers = self._prepare_jwt_headers_and_user_id(user_id)

        payload = {
            "collection": collection,
            "query": query or {},
        }
        if user_id:
            payload["user_id"] = user_id
        if limit:
            payload["limit"] = limit

        try:
            response = await client.post(
                "/api/proxy/database/find_many",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("documents", [])

        except httpx.TimeoutException:
            logger.warning("CentralHub timeout on find_many: collection=%s, query=%s", collection, query)
            raise

        except httpx.HTTPStatusError as e:
            logger.error(
                "CentralHub HTTP error on find_many: status=%s, collection=%s, query=%s",
                e.response.status_code, collection, query
            )
            raise

    async def insert_one(
        self,
        collection: str,
        document: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Insert a document via CentralHub proxy.

        Args:
            collection: Collection name
            document: Document dict to insert
            user_id: User ID for multi-tenant isolation

        Returns:
            Inserted document ID or None if insert failed

        Raises:
            httpx.HTTPStatusError: If request fails
            httpx.TimeoutException: If request times out
        """
        if not self.enabled:
            logger.debug("CentralHub disabled, cannot insert")
            return None

        client = await self._get_client()

        # Prepare JWT headers and extract user_id if needed
        token, user_id, headers = self._prepare_jwt_headers_and_user_id(user_id)

        payload = {
            "collection": collection,
            "document": document,
        }
        if user_id:
            payload["user_id"] = user_id

        try:
            response = await client.post(
                "/api/proxy/database/insert_one",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("inserted_id")

        except httpx.TimeoutException:
            logger.warning("CentralHub timeout on insert_one: collection=%s", collection)
            raise

        except httpx.HTTPStatusError as e:
            logger.error(
                "CentralHub HTTP error on insert_one: status=%s, collection=%s",
                e.response.status_code, collection
            )
            raise

    async def update_one(
        self,
        collection: str,
        query: Dict[str, Any],
        update: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> int:
        """
        Update a document via CentralHub proxy.

        Args:
            collection: Collection name
            query: Query filter to find document
            update: Update operations (e.g., {"$set": {"field": "value"}})
            user_id: User ID for multi-tenant isolation

        Returns:
            Number of documents modified (0 or 1)

        Raises:
            httpx.HTTPStatusError: If request fails
            httpx.TimeoutException: If request times out
        """
        if not self.enabled:
            logger.debug("CentralHub disabled, cannot update")
            return 0

        client = await self._get_client()

        # Prepare JWT headers and extract user_id if needed
        token, user_id, headers = self._prepare_jwt_headers_and_user_id(user_id)

        payload = {
            "collection": collection,
            "query": query,
            "update": update,
        }
        if user_id:
            payload["user_id"] = user_id

        try:
            response = await client.post(
                "/api/proxy/database/update_one",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("modified_count", 0)

        except httpx.TimeoutException:
            logger.warning("CentralHub timeout on update_one: collection=%s, query=%s", collection, query)
            raise

        except httpx.HTTPStatusError as e:
            logger.error(
                "CentralHub HTTP error on update_one: status=%s, collection=%s, query=%s",
                e.response.status_code, collection, query
            )
            raise

    async def delete_one(
        self,
        collection: str,
        query: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> int:
        """
        Delete a document via CentralHub proxy.

        Args:
            collection: Collection name
            query: Query filter to find document
            user_id: User ID for multi-tenant isolation

        Returns:
            Number of documents deleted (0 or 1)

        Raises:
            httpx.HTTPStatusError: If request fails
            httpx.TimeoutException: If request times out
        """
        if not self.enabled:
            logger.debug("CentralHub disabled, cannot delete")
            return 0

        client = await self._get_client()

        # Prepare JWT headers and extract user_id if needed
        token, user_id, headers = self._prepare_jwt_headers_and_user_id(user_id)

        payload = {
            "collection": collection,
            "query": query,
        }
        if user_id:
            payload["user_id"] = user_id

        try:
            response = await client.post(
                "/api/proxy/database/delete_one",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("deleted_count", 0)

        except httpx.TimeoutException:
            logger.warning("CentralHub timeout on delete_one: collection=%s, query=%s", collection, query)
            raise

        except httpx.HTTPStatusError as e:
            logger.error(
                "CentralHub HTTP error on delete_one: status=%s, collection=%s, query=%s",
                e.response.status_code, collection, query
            )
            raise
