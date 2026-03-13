"""
HybridDatabase Router - RBAC-Mandatory Multi-Source Query Engine (Sub-Issue 1.6).

BREAKING CHANGES: All methods now require `current_user` parameter for RBAC enforcement.

Features:
- Mandatory RBAC validation (TypeError if current_user missing)
- Multi-source search (sandbox + canonical + runtime)
- Result merging with precedence rules
- Cache invalidation on writes
- Support for all 11 collections
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from ...config.database import MONGODB_ENABLED
from ...models.users import User
from ..centralhub_client import CentralHubClient
from ..mongodb.operations import MongoDBOperations
from ..query_engine.cache_manager import CacheManager
from ..query_engine.canonical_engine import CanonicalQueryEngine
from ..query_engine.rbac import RBACValidator
from ..query_engine.sandbox_engine import SandboxQueryEngine
from ..redis_cache import RedisCachedJSONDatabase
from .collections import CANONICAL_COLLECTIONS
from .multi_source_search import MultiSourceSearch
from .tier_operations import TierOperations

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# All 11 supported collections (from Sub-Issue 1.6 spec)
SUPPORTED_COLLECTIONS = {
    "permissions",
    "cells",
    "books",
    "ai_models",
    "content_types",
    "notebook_items",
    "contents",
    "templates",
    "roles",
    "workflows",
    "notebook_item_types",
    "job_types",
}


class HybridDatabase:
    """
    RBAC-mandatory hybrid database router with multi-source search.

    BREAKING CHANGES (Sub-Issue 1.6):
    - All methods require `current_user: User` parameter
    - Methods raise TypeError if current_user missing or wrong type
    - Methods raise PermissionError if user lacks access

    Design:
    - Canonical data → CanonicalQueryEngine
    - Sandbox data → SandboxQueryEngine
    - Runtime data → MongoDB/CentralHub
    - Multi-source with precedence: Sandbox > Canonical > Runtime
    - RBAC validation before all operations
    - L1 Redis caching for query results
    """

    def __init__(
        self,
        base_path: Optional[Path] = None,
        is_test_env: bool = False,
        redis_client=None,
        centralhub_client: Optional[CentralHubClient] = None,
    ):
        """
        Initialize RBAC-mandatory HybridDatabase.

        Args:
            base_path: Base path for artifact storage
            is_test_env: Flag for test environment
            redis_client: Redis client for L1 caching
            centralhub_client: CentralHub HTTP client for MongoDB proxy
        """
        self.is_test_env = is_test_env
        self.base_path = base_path or Path("artifacts")

        # Initialize file-based database (with Redis caching if enabled)
        self._file_db = RedisCachedJSONDatabase(
            base_path=base_path, is_test_env=is_test_env
        )

        # Initialize MongoDB operations (will be None if MongoDB disabled)
        self._mongo_ops: Optional[MongoDBOperations] = None
        if MONGODB_ENABLED:
            self._mongo_ops = MongoDBOperations()
            logger.info("HybridDatabase initialized with MongoDB support")
        else:
            logger.info(
                "HybridDatabase initialized with file-only storage (MongoDB disabled)"
            )

        # Initialize CentralHub client
        self._centralhub_client = centralhub_client

        # Initialize query engines (Sub-Issues 1.1-1.3)
        try:
            self._canonical_engine = CanonicalQueryEngine(
                redis_client=redis_client, base_path=self.base_path / "canonical"
            )
            logger.info("CanonicalQueryEngine initialized")
        except Exception as e:
            logger.error("Failed to initialize CanonicalQueryEngine: %s", e, exc_info=True)
            self._canonical_engine = None

        try:
            self._sandbox_engine = SandboxQueryEngine(
                redis_client=redis_client, base_path=self.base_path / "sandbox"
            )
            logger.info("SandboxQueryEngine initialized")
        except Exception as e:
            logger.warning("Failed to initialize SandboxQueryEngine: %s", e)
            self._sandbox_engine = None

        # Initialize RBAC validator (Sub-Issue 1.4)
        self._rbac = RBACValidator(
            redis_client=redis_client,
            db_client=self._file_db,
        )
        logger.info("RBACValidator initialized")

        # Initialize cache manager (Sub-Issue 1.5)
        self._cache_manager = None
        if redis_client:
            self._cache_manager = CacheManager(redis_client)
            logger.info("CacheManager initialized")

        # Initialize multi-source search handler
        self._multi_source = MultiSourceSearch(
            rbac=self._rbac,
            sandbox_engine=self._sandbox_engine,
            canonical_engine=self._canonical_engine,
            mongo_ops=self._mongo_ops,
            centralhub_client=self._centralhub_client,
            mongodb_enabled=MONGODB_ENABLED,
        )

        # Initialize tier operations handler
        self._tier_ops = TierOperations(
            base_path=self.base_path,
            file_db=self._file_db,
            mongo_ops=self._mongo_ops,
            centralhub_client=self._centralhub_client,
            cache_manager=self._cache_manager,
            canonical_collections=CANONICAL_COLLECTIONS,
            mongodb_enabled=MONGODB_ENABLED,
        )

        logger.info("HybridDatabase Phase 1.6 (RBAC-mandatory) initialized")

    def _validate_access(self, collection: str, current_user: User) -> None:
        """
        Validate user has access to collection. Raises PermissionError if denied.

        Args:
            collection: Collection name
            current_user: User making the request

        Raises:
            TypeError: If current_user is not provided or wrong type
            PermissionError: If user lacks access to collection
        """
        # Validate current_user parameter type
        if current_user is None:
            raise TypeError(
                "current_user parameter is required for all database operations"
            )

        if not isinstance(current_user, User):
            raise TypeError(
                f"current_user must be User type, got {type(current_user).__name__}"
            )

        # Delegate to RBAC module
        self._rbac.validate_access(collection, current_user)

    async def find_one(
        self,
        collection: str,
        doc_id: str,
        current_user: User,  # ← MANDATORY (BREAKING CHANGE)
        model_class: Optional[Type[T]] = None,
        resource_owner_id: Optional[str] = None,
    ) -> Optional[T]:
        """
        Find single document by ID with RBAC + multi-source search.

        BREAKING CHANGE: current_user is now MANDATORY.

        Args:
            collection: Collection name
            doc_id: Document ID
            current_user: User making request (MANDATORY)
            model_class: Pydantic model class for deserialization
            resource_owner_id: Resource owner ID (for sandbox access check)

        Returns:
            Document instance or None if not found

        Raises:
            TypeError: If current_user is missing or wrong type
            PermissionError: If user lacks access to collection
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Multi-source search: Sandbox > Canonical > Runtime
        # Use 'id' field for query (most collections use 'id', not '_id')
        query = {"id": doc_id}
        results = await self._multi_source.find(
            collection=collection,
            query=query,
            current_user=current_user,
            resource_owner_id=resource_owner_id,
            limit=1,
        )

        if not results:
            return None

        # Convert to model if requested
        result = results[0]
        if model_class:
            return model_class(**result) if isinstance(result, dict) else result
        return result

    async def find_many(
        self,
        collection: str,
        current_user: User,  # ← MANDATORY (BREAKING CHANGE)
        query: Optional[Dict] = None,
        limit: Optional[int] = None,
        model_class: Optional[Type[T]] = None,
    ) -> List[T]:
        """
        Find multiple documents with RBAC + multi-source search.

        BREAKING CHANGE: current_user is now MANDATORY.

        Args:
            collection: Collection name
            current_user: User making request (MANDATORY)
            query: Query filter (default: {})
            limit: Maximum number of documents to return
            model_class: Pydantic model class for deserialization

        Returns:
            List of document instances

        Raises:
            TypeError: If current_user is missing or wrong type
            PermissionError: If user lacks access to collection
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Multi-source search
        query = query or {}
        results = await self._multi_source.find(
            collection=collection,
            query=query,
            current_user=current_user,
            limit=limit,
        )

        logger.info(
            "[HybridDatabase.find_many] Collection=%s, Found %s results from multi_source, model_class=%s",
            collection, len(results), model_class
        )

        # Convert to models if requested
        if model_class:
            logger.info("[HybridDatabase.find_many] Converting %s results to %s", len(results), model_class.__name__)
            converted = []
            for i, result in enumerate(results):
                try:
                    if isinstance(result, dict):
                        item = model_class(**result)
                    else:
                        item = result
                    converted.append(item)
                except Exception as e:
                    logger.error(
                        "[HybridDatabase.find_many] Error converting item %s: %s, result keys: %s",
                        i, e, result.keys() if isinstance(result, dict) else type(result)
                    )
                    raise
            logger.info("[HybridDatabase.find_many] Converted %s items successfully, returning", len(converted))
            return converted
        return results

    async def find(
        self,
        collection: str,
        query: Dict,
        current_user: User,  # ← MANDATORY (BREAKING CHANGE)
        limit: Optional[int] = None,
        resource_owner_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Find with complex query, RBAC, and multi-source search.

        BREAKING CHANGE: current_user is now MANDATORY.

        Supports MongoDB operators: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin,
        $and, $or, $not, $all, $elemMatch, $exists, $regex

        Args:
            collection: Collection name
            query: MongoDB-style query dict
            current_user: User making request (MANDATORY)
            limit: Maximum number of documents to return
            resource_owner_id: Resource owner ID (for sandbox access)

        Returns:
            List of matching documents (as dicts)

        Raises:
            TypeError: If current_user is missing or wrong type
            PermissionError: If user lacks access to collection
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Multi-source search with complex query support
        results = await self._multi_source.find(
            collection=collection,
            query=query,
            current_user=current_user,
            resource_owner_id=resource_owner_id,
            limit=limit,
        )

        return results

    async def insert(
        self,
        collection: str,
        document: Dict,
        current_user: User,  # ← MANDATORY (BREAKING CHANGE)
        resource_owner_id: Optional[str] = None,
    ) -> str:
        """
        Unified insert with RBAC and cache invalidation.

        BREAKING CHANGE: current_user is now MANDATORY.

        Routes to appropriate tier based on resource_owner_id:
        - If resource_owner_id provided → sandbox (user-private)
        - Otherwise → canonical or runtime based on collection type

        Cache invalidation:
        - Sandbox writes: invalidates schema cache + L1 Redis
        - Runtime writes: invalidates L1 Redis cache

        Args:
            collection: Collection name
            document: Document to insert (dict or Pydantic model)
            current_user: User making request (MANDATORY)
            resource_owner_id: Resource owner ID (for sandbox insert)

        Returns:
            Inserted document ID

        Raises:
            TypeError: If current_user is missing or wrong type
            PermissionError: If user lacks access to collection
        """
        # Convert Pydantic model to dict if needed
        if isinstance(document, BaseModel):
            document = document.model_dump()

        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Determine target tier and perform insert
        if resource_owner_id:
            # Insert into user's sandbox
            doc_id = await self._tier_ops.insert_to_sandbox(
                resource_owner_id, collection, document
            )

            # Invalidate sandbox schema cache (Sub-Issue 1.3 integration)
            if self._sandbox_engine:
                await self._sandbox_engine.invalidate_schema_cache(
                    resource_owner_id, collection
                )
                logger.debug("Invalidated sandbox schema cache for %s/%s", collection, resource_owner_id)

            # Invalidate L1 Redis cache for sandbox writes
            if self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, resource_owner_id
                )
                logger.debug("Invalidated L1 cache for %s/%s", collection, resource_owner_id)

            return doc_id
        else:
            # Insert into canonical/runtime based on collection type
            doc_id = await self._tier_ops.insert_to_canonical_or_runtime(
                collection, document, current_user
            )

            return doc_id

    async def update(
        self,
        collection: str,
        doc_id: str,
        updates: Dict,
        current_user: User,  # ← MANDATORY (BREAKING CHANGE)
        resource_owner_id: Optional[str] = None,
    ) -> bool:
        """
        Unified update with RBAC and cache invalidation.

        BREAKING CHANGE: current_user is now MANDATORY.

        Args:
            collection: Collection name
            doc_id: Document ID
            updates: Dictionary of field updates
            current_user: User making request (MANDATORY)
            resource_owner_id: Resource owner ID (for sandbox update)

        Returns:
            True if update successful, False otherwise

        Raises:
            TypeError: If current_user is missing or wrong type
            PermissionError: If user lacks access to collection
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Perform update
        if resource_owner_id:
            # Update in user's sandbox
            success = await self._tier_ops.update_in_sandbox(
                resource_owner_id, collection, doc_id, updates
            )

            # Invalidate sandbox schema cache (Sub-Issue 1.3 integration)
            if success and self._sandbox_engine:
                await self._sandbox_engine.invalidate_schema_cache(
                    resource_owner_id, collection
                )
                logger.debug("Invalidated sandbox schema cache for %s/%s", collection, resource_owner_id)

            # Invalidate L1 Redis cache for sandbox writes
            if success and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, resource_owner_id
                )
                logger.debug("Invalidated L1 cache for %s/%s", collection, resource_owner_id)

            return success
        else:
            # Update in canonical/runtime
            success = await self._tier_ops.update_in_canonical_or_runtime(
                collection, doc_id, updates, current_user
            )

            return success

    async def delete(
        self,
        collection: str,
        doc_id: str,
        current_user: User,  # ← MANDATORY (BREAKING CHANGE)
        resource_owner_id: Optional[str] = None,
    ) -> bool:
        """
        Unified delete with RBAC and cache invalidation.

        BREAKING CHANGE: current_user is now MANDATORY.

        Args:
            collection: Collection name
            doc_id: Document ID
            current_user: User making request (MANDATORY)
            resource_owner_id: Resource owner ID (for sandbox delete)

        Returns:
            True if delete successful, False otherwise

        Raises:
            TypeError: If current_user is missing or wrong type
            PermissionError: If user lacks access to collection
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Perform delete
        if resource_owner_id:
            # Delete from user's sandbox
            success = await self._tier_ops.delete_from_sandbox(
                resource_owner_id, collection, doc_id
            )

            # Invalidate sandbox schema cache (Sub-Issue 1.3 integration)
            if success and self._sandbox_engine:
                await self._sandbox_engine.invalidate_schema_cache(
                    resource_owner_id, collection
                )
                logger.debug("Invalidated sandbox schema cache for %s/%s", collection, resource_owner_id)

            # Invalidate L1 Redis cache for sandbox writes
            if success and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, resource_owner_id
                )
                logger.debug("Invalidated L1 cache for %s/%s", collection, resource_owner_id)

            return success
        else:
            # Delete from canonical/runtime
            success = await self._tier_ops.delete_from_canonical_or_runtime(
                collection, doc_id, current_user
            )

            return success

    def get_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration from file-based storage.

        Args:
            config_key: Configuration key (e.g., "oauth", "system")

        Returns:
            Configuration dictionary or None if not found
        """
        return self._file_db.get_config(config_key)

    def set_config(self, config_key: str, config_value: Dict[str, Any]) -> bool:
        """
        Set configuration in file-based storage.

        Args:
            config_key: Configuration key
            config_value: Configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        return self._file_db.set_config(config_key, config_value)

    async def invalidate_cache_l1(self, collection: Optional[str] = None) -> Dict[str, Any]:
        """
        Invalidate L1 Redis cache for a specific collection or all collections.

        This method clears the Redis L1 cache, forcing subsequent queries to
        re-fetch data from the source (canonical, sandbox, or MongoDB).
        Useful for development and when data has been updated externally.

        Args:
            collection: Optional collection name to invalidate.
                       If None, invalidates all collections.

        Returns:
            Dict with invalidation results (keys deleted, collections affected, etc.)

        Example:
            # Invalidate all cache
            result = await db.invalidate_cache_l1()

            # Invalidate specific collection
            result = await db.invalidate_cache_l1(collection="notebook_item_types")
        """
        try:
            if collection:
                # Invalidate specific collection cache
                if collection not in SUPPORTED_COLLECTIONS:
                    logger.warning(
                        f"Attempted to invalidate unknown collection: {collection}"
                    )
                    return {
                        "success": False,
                        "error": f"Unknown collection: {collection}",
                        "supported_collections": list(SUPPORTED_COLLECTIONS),
                    }

                # Use cache manager to invalidate collection
                await self._file_db.cache_manager.invalidate_for_collection(collection)
                logger.info(f"Invalidated L1 cache for collection: {collection}")

                return {
                    "success": True,
                    "invalidated_collection": collection,
                    "message": f"Cache invalidated for {collection}",
                }
            else:
                # Invalidate all collections
                for coll in SUPPORTED_COLLECTIONS:
                    await self._file_db.cache_manager.invalidate_for_collection(coll)

                logger.info(f"Invalidated L1 cache for all {len(SUPPORTED_COLLECTIONS)} collections")

                return {
                    "success": True,
                    "invalidated_collections": list(SUPPORTED_COLLECTIONS),
                    "count": len(SUPPORTED_COLLECTIONS),
                    "message": f"Cache invalidated for all {len(SUPPORTED_COLLECTIONS)} collections",
                }

        except Exception as e:
            logger.error(f"Error invalidating L1 cache: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to invalidate L1 cache",
            }
