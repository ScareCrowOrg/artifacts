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
        self._api_key: Optional[str] = None
        self._client: Optional[AsyncClient] = None
        logger.info("CentralHub client configured for: %s", self.base_url)

    def set_api_key(self, api_key: str) -> None:
        """Define API key for service-level authentication. Optional."""
        self._api_key = api_key

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            request_headers: Dict[str, str] = {}
            if self._api_key:
                request_headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=request_headers,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Generic HTTP request via CentralHub.

        Args:
            method: HTTP method
            path: Request path
            json: JSON body
            params: Query parameters
            headers: Request headers

        Returns:
            httpx.Response object
        """
        client = await self._get_client()
        return await client.request(method, path, json=json, params=params, headers=headers)

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
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find a single document via CentralHub proxy."""
        try:
            resp = await self.request(
                "POST", "/api/proxy/database/find_one",
                json={"collection": collection, "query": query, "user_id": user_id, "caller": caller},
                headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("data")
        except HTTPError as exc:
            logger.error("CentralHub find_one failed: %s", exc)
            if getattr(exc, 'response', None) and exc.response.status_code == 403:
                resp_body = ""
                try:
                    resp_body = exc.response.text
                except Exception:
                    pass
                logger.warning(
                    "CENTRALHUB-CLIENT-DEBUG: find_one 403 — collection=%s, user_id=%s, caller=%s, status=%s, body=%s",
                    collection, user_id, caller, exc.response.status_code, resp_body
                )
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
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Find multiple documents via CentralHub proxy."""
        try:
            resp = await self.request(
                "POST", "/api/proxy/database/find_many",
                json={
                    "collection": collection,
                    "query": query or {},
                    "limit": limit,
                    "skip": skip,
                    "sort": sort,
                    "user_id": user_id,
                    "caller": caller,
                },
                headers=headers,
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("data", [])
        except HTTPError as exc:
            logger.error("CentralHub find_many failed: %s", exc)
            if getattr(exc, 'response', None) and exc.response.status_code == 403:
                resp_body = ""
                try:
                    resp_body = exc.response.text
                except Exception:
                    pass
                logger.warning(
                    "CENTRALHUB-CLIENT-DEBUG: find_many 403 — collection=%s, user_id=%s, caller=%s, status=%s, body=%s, returning_empty_list=True",
                    collection, user_id, caller, exc.response.status_code, resp_body
                )
                return []
            raise

    async def insert_one(
        self,
        collection: str,
        document: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Insert a document via CentralHub proxy."""
        try:
            resp = await self.request(
                "POST", "/api/proxy/database/insert_one",
                json={"collection": collection, "document": document, "user_id": user_id, "caller": caller},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
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
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Update a document via CentralHub proxy."""
        try:
            # Log value types to diagnose serialization issues
            _types = {}
            for _k, _v in update.items():
                if isinstance(_v, dict):
                    _types[_k] = {_kk: type(_vv).__name__ for _kk, _vv in _v.items()}
                else:
                    _types[_k] = type(_v).__name__
            logger.info(
                "[DIAG] CentralHubClient.update_one: update=%s, value_types=%s",
                update, _types,
            )
            resp = await self.request(
                "POST", "/api/proxy/database/update_one",
                json={
                    "collection": collection,
                    "query": query,
                    "update": update,
                    "upsert": upsert,
                    "user_id": user_id,
                    "caller": caller,
                },
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
        except HTTPError as exc:
            logger.error("CentralHub update_one failed: %s", exc)
            raise

    async def delete_one(
        self,
        collection: str,
        query: Dict[str, Any],
        user_id: Optional[str] = None,
        caller: str = "scarerunner",
        headers: Optional[Dict[str, str]] = None,
    ) -> int:
        """Delete a document via CentralHub proxy."""
        try:
            resp = await self.request(
                "POST", "/api/proxy/database/delete_one",
                json={"collection": collection, "query": query, "user_id": user_id, "caller": caller},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("deleted_count", 0)
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
