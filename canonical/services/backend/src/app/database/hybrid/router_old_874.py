"""
HybridDatabase Router - RBAC-Mandatory Multi-Source Query Engine (Sub-Issue 1.6).

BREAKING CHANGES: All methods now require `current_user` parameter for RBAC enforcement.
Integrates query engines (canonical, sandbox), RBAC validation, cache manager, and
multi-source search with precedence rules (Sandbox > Canonical > Runtime).

Features:
- Mandatory RBAC validation (TypeError if current_user missing)
- Multi-source search (sandbox + canonical + runtime)
- Result merging with precedence rules
- Cache invalidation on writes
- Support for all 11 collections
- Query engine integration (Sub-Issues 1.1-1.3)
- RBAC infrastructure (Sub-Issue 1.4)
- Cache manager (Sub-Issue 1.5)
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
}


class HybridDatabase:
    """
    RBAC-mandatory hybrid database router with multi-source search.

    BREAKING CHANGES (Sub-Issue 1.6):
    - All methods now require `current_user: User` parameter
    - Methods raise TypeError if current_user is missing or wrong type
    - Methods raise PermissionError if user lacks access

    Design:
    - Canonical data (templates, types, configs) → CanonicalQueryEngine
    - Sandbox data (user-private drafts) → SandboxQueryEngine
    - Runtime data (operational) → MongoDB/CentralHub
    - Multi-source search with precedence: Sandbox > Canonical > Runtime
    - RBAC validation before all operations
    - L1 Redis caching for query results

    Example (NEW API):
        db = HybridDatabase()

        # Find with RBAC (mandatory)
        results = await db.find(
            "templates",
            {"status": "published"},
            current_user=user,  # ← MANDATORY
            limit=10
        )

        # Insert with RBAC (mandatory)
        doc_id = await db.insert(
            "templates",
            template_doc,
            current_user=user,  # ← MANDATORY
        )
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
            self._canonical_engine = CanonicalQueryEngine()
            logger.info("CanonicalQueryEngine initialized")
        except Exception as e:
            logger.warning("Failed to initialize CanonicalQueryEngine: %s", e)
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

        Example:
            user = User(id="user1", roles=["admin"])
            doc = await db.find_one("templates", "tpl-123", current_user=user)
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Multi-source search: Sandbox > Canonical > Runtime
        query = {"_id": doc_id}
        results = await self._multi_source_find(
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

        Example:
            user = User(id="user1", roles=["admin"])
            docs = await db.find_many("templates", current_user=user, limit=10)
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Multi-source search
        query = query or {}
        results = await self._multi_source_find(
            collection=collection,
            query=query,
            current_user=current_user,
            limit=limit,
        )

        # Convert to models if requested
        if model_class:
            return [
                model_class(**result) if isinstance(result, dict) else result
                for result in results
            ]
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

        Supports MongoDB operators:
        - Comparison: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
        - Logical: $and, $or, $not
        - Array: $all, $elemMatch
        - Field: $exists
        - String: $regex

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

        Example:
            user = User(id="user1", roles=["admin"])
            docs = await db.find(
                "templates",
                {"status": "published", "level": {"$gte": 5}},
                current_user=user,
                limit=10
            )
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Multi-source search with complex query support
        results = await self._multi_source_find(
            collection=collection,
            query=query,
            current_user=current_user,
            resource_owner_id=resource_owner_id,
            limit=limit,
        )

        return results

    async def _multi_source_find(
        self,
        collection: str,
        query: Dict,
        current_user: User,
        resource_owner_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Search all 3 sources and merge results with precedence.

        Precedence: Sandbox > Canonical > Runtime

        Args:
            collection: Collection name
            query: Query filter
            current_user: User making request
            resource_owner_id: Resource owner ID (for sandbox)
            limit: Maximum results

        Returns:
            Merged results (de-duplicated by _id)
        """
        results_sandbox = []
        results_canonical = []
        results_runtime = []

        # 1. Check sandbox (if user has access and resource_owner_id provided)
        if resource_owner_id and self._sandbox_engine:
            if self._rbac.check_sandbox_access(resource_owner_id, current_user):
                try:
                    results_sandbox = await self._sandbox_engine.find(
                        user_id=resource_owner_id,
                        collection=collection,
                        query=query,
                        limit=limit,
                    )
                    logger.debug("Sandbox search: %s results", len(results_sandbox))
                except Exception as e:
                    logger.warning("Sandbox search error: %s", e)

        # 2. Check canonical (if user has access)
        if self._rbac.check_canonical_access(collection, current_user):
            if self._canonical_engine:
                try:
                    results_canonical = await self._canonical_engine.find(
                        collection=collection,
                        query=query,
                        limit=limit,
                    )
                    logger.debug("Canonical search: %s results", len(results_canonical))
                except Exception as e:
                    logger.warning("Canonical search error: %s", e)

        # 3. Check runtime/MongoDB (if user has access)
        if self._rbac.check_runtime_access(collection, current_user):
            # Try MongoDB direct connection first
            if self._mongo_ops and MONGODB_ENABLED:
                try:
                    results_runtime = await self._mongo_ops.find(
                        collection=collection,
                        query=query,
                        limit=limit,
                    )
                    logger.debug("MongoDB search: %s results", len(results_runtime))
                except Exception as e:
                    logger.warning("MongoDB search error: %s", e)
            # Fallback to CentralHub HTTP proxy
            elif self._centralhub_client:
                try:
                    results_runtime = await self._centralhub_client.find_many(
                        collection=collection,
                        query=query,
                        user_id=current_user.id,
                        limit=limit,
                    )
                    logger.debug("CentralHub search: %s results", len(results_runtime))
                except Exception as e:
                    logger.warning("CentralHub search error: %s", e)

        # 4. Merge with precedence (Sandbox > Canonical > Runtime)
        merged = self._merge_results(
            results_sandbox, results_canonical, results_runtime
        )

        return merged

    def _merge_results(
        self,
        sandbox_results: List[Dict],
        canonical_results: List[Dict],
        runtime_results: List[Dict],
    ) -> List[Dict]:
        """
        Merge results from 3 sources with precedence rules.

        Precedence: Sandbox > Canonical > Runtime
        De-duplicates by _id field.

        Args:
            sandbox_results: Results from sandbox
            canonical_results: Results from canonical
            runtime_results: Results from runtime

        Returns:
            Merged and de-duplicated results
        """
        # Track seen IDs to avoid duplicates
        seen_ids = set()
        merged = []

        # Priority 1: Sandbox results
        for result in sandbox_results:
            doc_id = result.get("_id") or result.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(result)

        # Priority 2: Canonical results
        for result in canonical_results:
            doc_id = result.get("_id") or result.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(result)

        # Priority 3: Runtime results
        for result in runtime_results:
            doc_id = result.get("_id") or result.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(result)

        logger.debug(
            "Merged results: %s total (sandbox=%s, canonical=%s, runtime=%s)",
            len(merged), len(sandbox_results), len(canonical_results), len(runtime_results)
        )

        return merged

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
        - Sandbox writes: invalidates SandboxQueryEngine schema cache
        - Runtime writes: invalidates L1 Redis cache

        Args:
            collection: Collection name
            document: Document to insert (dict)
            current_user: User making request (MANDATORY)
            resource_owner_id: Resource owner ID (for sandbox insert)

        Returns:
            Inserted document ID

        Raises:
            TypeError: If current_user is missing or wrong type
            PermissionError: If user lacks access to collection

        Example:
            user = User(id="user1", roles=["admin"])
            doc_id = await db.insert(
                "templates",
                {"name": "New Template", "status": "draft"},
                current_user=user
            )
        """
        # Validate RBAC first
        self._validate_access(collection, current_user)

        # Determine target tier and perform insert
        if resource_owner_id:
            # Insert into user's sandbox
            doc_id = await self._insert_to_sandbox(
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
            doc_id = await self._insert_to_canonical_or_runtime(
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
            success = await self._update_in_sandbox(
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
            success = await self._update_in_canonical_or_runtime(
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
            success = await self._delete_from_sandbox(
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
            success = await self._delete_from_canonical_or_runtime(
                collection, doc_id, current_user
            )

            return success

    # Helper methods for tier-specific operations

    async def _insert_to_sandbox(
        self, user_id: str, collection: str, document: Dict
    ) -> str:
        """Insert document to user's sandbox (local files)."""
        # Implementation uses sandbox file storage
        sandbox_path = self.base_path / "sandbox" / user_id / collection
        sandbox_path.mkdir(parents=True, exist_ok=True)

        doc_id = document.get("_id") or document.get("id")
        if not doc_id:
            import uuid

            doc_id = str(uuid.uuid4())
            document["_id"] = doc_id

        file_path = sandbox_path / f"{doc_id}.json"
        import json

        file_path.write_text(json.dumps(document, indent=2, default=str))

        logger.debug("Inserted to sandbox: %s/%s (user=%s)", collection, doc_id, user_id)
        return doc_id

    async def _update_in_sandbox(
        self, user_id: str, collection: str, doc_id: str, updates: Dict
    ) -> bool:
        """Update document in user's sandbox."""
        sandbox_path = self.base_path / "sandbox" / user_id / collection
        file_path = sandbox_path / f"{doc_id}.json"

        if not file_path.exists():
            return False

        import json

        document = json.loads(file_path.read_text())
        document.update(updates)
        file_path.write_text(json.dumps(document, indent=2, default=str))

        logger.debug("Updated in sandbox: %s/%s (user=%s)", collection, doc_id, user_id)
        return True

    async def _delete_from_sandbox(
        self, user_id: str, collection: str, doc_id: str
    ) -> bool:
        """Delete document from user's sandbox."""
        sandbox_path = self.base_path / "sandbox" / user_id / collection
        file_path = sandbox_path / f"{doc_id}.json"

        if not file_path.exists():
            return False

        file_path.unlink()
        logger.debug("Deleted from sandbox: %s/%s (user=%s)", collection, doc_id, user_id)
        return True

    def _create_dynamic_model(self, document: Dict) -> BaseModel:
        """
        Create a dynamic Pydantic model from a document dict.

        Args:
            document: Document dictionary

        Returns:
            Dynamic Pydantic model instance
        """

        # Create a dynamic model class with extra='allow'
        class DynamicModel(BaseModel):
            class Config:
                extra = "allow"

        # Add annotations for all fields
        for key in document.keys():
            DynamicModel.__annotations__[key] = Any

        # Create instance
        return DynamicModel(**document)

    async def _insert_to_canonical_or_runtime(
        self, collection: str, document: Dict, current_user: User
    ) -> str:
        """Insert to canonical (file) or runtime (MongoDB) based on collection."""
        # Canonical collections go to file storage
        if collection in CANONICAL_COLLECTIONS:
            # Use file DB for canonical data
            # Convert dict to BaseModel for insert
            model_doc = self._create_dynamic_model(document)

            doc_id = await self._file_db.insert_async(
                collection=collection,
                document=model_doc,
                is_canonical=True,
            )

            # Invalidate L1 cache
            if self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return doc_id

        # Runtime collections go to MongoDB
        if self._mongo_ops and MONGODB_ENABLED:
            doc_id = await self._mongo_ops.insert(
                collection=collection,
                document=document,
                user_id=current_user.id,
            )

            # Invalidate L1 cache
            if self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return doc_id

        # Fallback to CentralHub
        if self._centralhub_client:
            doc_id = await self._centralhub_client.insert_one(
                collection=collection,
                document=document,
                user_id=current_user.id,
            )

            # Invalidate L1 cache
            if self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return doc_id

        raise RuntimeError(f"No backend available for collection '{collection}'")

    async def _update_in_canonical_or_runtime(
        self, collection: str, doc_id: str, updates: Dict, current_user: User
    ) -> bool:
        """Update in canonical (file) or runtime (MongoDB) based on collection."""
        # Canonical collections use file storage
        if collection in CANONICAL_COLLECTIONS:
            success = await self._file_db.update_async(
                collection=collection,
                doc_id=doc_id,
                updates=updates,
                is_canonical=True,
            )

            # Invalidate L1 cache
            if success and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return success

        # Runtime collections use MongoDB
        if self._mongo_ops and MONGODB_ENABLED:
            success = await self._mongo_ops.update(
                collection=collection,
                doc_id=doc_id,
                updates=updates,
                user_id=current_user.id,
            )

            # Invalidate L1 cache
            if success and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return success

        # Fallback to CentralHub
        if self._centralhub_client:
            modified_count = await self._centralhub_client.update_one(
                collection=collection,
                query={"_id": doc_id},
                update={"$set": updates},
                user_id=current_user.id,
            )

            # Invalidate L1 cache
            if modified_count > 0 and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return modified_count > 0

        raise RuntimeError(f"No backend available for collection '{collection}'")

    async def _delete_from_canonical_or_runtime(
        self, collection: str, doc_id: str, current_user: User
    ) -> bool:
        """Delete from canonical (file) or runtime (MongoDB) based on collection."""
        # Canonical collections use file storage
        if collection in CANONICAL_COLLECTIONS:
            success = await self._file_db.delete_async(
                collection=collection,
                doc_id=doc_id,
                is_canonical=True,
            )

            # Invalidate L1 cache
            if success and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return success

        # Runtime collections use MongoDB
        if self._mongo_ops and MONGODB_ENABLED:
            success = await self._mongo_ops.delete(
                collection=collection,
                doc_id=doc_id,
                user_id=current_user.id,
            )

            # Invalidate L1 cache
            if success and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return success

        # Fallback to CentralHub
        if self._centralhub_client:
            deleted_count = await self._centralhub_client.delete_one(
                collection=collection,
                query={"_id": doc_id},
                user_id=current_user.id,
            )

            # Invalidate L1 cache
            if deleted_count > 0 and self._cache_manager:
                await self._cache_manager.invalidate_for_collection(
                    collection, current_user.id
                )

            return deleted_count > 0

        raise RuntimeError(f"No backend available for collection '{collection}'")
