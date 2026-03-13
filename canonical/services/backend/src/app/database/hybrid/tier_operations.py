"""
Tier-Specific Operations for HybridDatabase.

Provides CRUD operations for all 3 tiers:
- Sandbox: User-private local file storage
- Canonical: Blueprint/schema file storage
- Runtime: Operational MongoDB/CentralHub storage
"""

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from ...models.users import User
    from ..centralhub_client import CentralHubClient
    from ..mongodb.operations import MongoDBOperations
    from ..query_engine.cache_manager import CacheManager
    from ..redis_cache import RedisCachedJSONDatabase

logger = logging.getLogger(__name__)


class TierOperations:
    """
    Tier-specific CRUD operations for HybridDatabase.

    Handles write operations (insert, update, delete) across all 3 tiers:
    1. Sandbox tier - User-private local files
    2. Canonical tier - Blueprint/schema files
    3. Runtime tier - MongoDB/CentralHub

    Features:
    - Automatic cache invalidation on writes
    - Graceful fallback between backends
    - Type conversion for file-based storage
    """

    def __init__(
        self,
        base_path: Path,
        file_db: "RedisCachedJSONDatabase",
        mongo_ops: Optional["MongoDBOperations"],
        centralhub_client: Optional["CentralHubClient"],
        cache_manager: Optional["CacheManager"],
        canonical_collections: set,
        mongodb_enabled: bool,
    ):
        """
        Initialize tier operations handler.

        Args:
            base_path: Base path for sandbox storage
            file_db: File database for canonical storage
            mongo_ops: MongoDB operations (can be None)
            centralhub_client: CentralHub HTTP client (can be None)
            cache_manager: Cache manager for L1 invalidation (can be None)
            canonical_collections: Set of canonical collection names
            mongodb_enabled: Whether MongoDB is enabled
        """
        self.base_path = base_path
        self._file_db = file_db
        self._mongo_ops = mongo_ops
        self._centralhub_client = centralhub_client
        self._cache_manager = cache_manager
        self._canonical_collections = canonical_collections
        self._mongodb_enabled = mongodb_enabled

    # Sandbox Operations (Tier 1 - User-Private)

    async def insert_to_sandbox(
        self, user_id: str, collection: str, document: Dict
    ) -> str:
        """
        Insert document to user's sandbox (local files).

        Args:
            user_id: User ID (sandbox owner)
            collection: Collection name
            document: Document to insert

        Returns:
            Inserted document ID
        """
        # Implementation uses sandbox file storage
        sandbox_path = self.base_path / "sandbox" / user_id / collection
        sandbox_path.mkdir(parents=True, exist_ok=True)

        doc_id = document.get("_id") or document.get("id")
        if not doc_id:
            doc_id = str(uuid.uuid4())
            document["_id"] = doc_id

        file_path = sandbox_path / f"{doc_id}.json"
        file_path.write_text(json.dumps(document, indent=2, default=str))

        logger.debug("Inserted to sandbox: %s/%s (user=%s)", collection, doc_id, user_id)
        return doc_id

    async def update_in_sandbox(
        self, user_id: str, collection: str, doc_id: str, updates: Dict
    ) -> bool:
        """
        Update document in user's sandbox.

        Args:
            user_id: User ID (sandbox owner)
            collection: Collection name
            doc_id: Document ID
            updates: Field updates

        Returns:
            True if update successful, False otherwise
        """
        sandbox_path = self.base_path / "sandbox" / user_id / collection
        file_path = sandbox_path / f"{doc_id}.json"

        if not file_path.exists():
            return False

        document = json.loads(file_path.read_text())
        document.update(updates)
        file_path.write_text(json.dumps(document, indent=2, default=str))

        logger.debug("Updated in sandbox: %s/%s (user=%s)", collection, doc_id, user_id)
        return True

    async def delete_from_sandbox(
        self, user_id: str, collection: str, doc_id: str
    ) -> bool:
        """
        Delete document from user's sandbox.

        Args:
            user_id: User ID (sandbox owner)
            collection: Collection name
            doc_id: Document ID

        Returns:
            True if delete successful, False otherwise
        """
        sandbox_path = self.base_path / "sandbox" / user_id / collection
        file_path = sandbox_path / f"{doc_id}.json"

        if not file_path.exists():
            return False

        file_path.unlink()
        logger.debug("Deleted from sandbox: %s/%s (user=%s)", collection, doc_id, user_id)
        return True

    # Canonical/Runtime Operations (Tier 2 & 3)

    @staticmethod
    def create_dynamic_model(document: Dict) -> BaseModel:
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

    async def insert_to_canonical_or_runtime(
        self, collection: str, document: Dict, current_user: "User"
    ) -> str:
        """
        Insert to canonical (file) or runtime (MongoDB) based on collection.

        Args:
            collection: Collection name
            document: Document to insert
            current_user: User making request

        Returns:
            Inserted document ID

        Raises:
            RuntimeError: If no backend available for collection
        """
        # Canonical collections go to file storage
        if collection in self._canonical_collections:
            # Use file DB for canonical data
            # Convert dict to BaseModel for insert
            model_doc = self.create_dynamic_model(document)

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
        if self._mongo_ops and self._mongodb_enabled:
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

    async def update_in_canonical_or_runtime(
        self, collection: str, doc_id: str, updates: Dict, current_user: "User"
    ) -> bool:
        """
        Update in canonical (file) or runtime (MongoDB) based on collection.

        Args:
            collection: Collection name
            doc_id: Document ID
            updates: Field updates
            current_user: User making request

        Returns:
            True if update successful, False otherwise

        Raises:
            RuntimeError: If no backend available for collection
        """
        # Canonical collections use file storage
        if collection in self._canonical_collections:
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
        if self._mongo_ops and self._mongodb_enabled:
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

    async def delete_from_canonical_or_runtime(
        self, collection: str, doc_id: str, current_user: "User"
    ) -> bool:
        """
        Delete from canonical (file) or runtime (MongoDB) based on collection.

        Args:
            collection: Collection name
            doc_id: Document ID
            current_user: User making request

        Returns:
            True if delete successful, False otherwise

        Raises:
            RuntimeError: If no backend available for collection
        """
        # Canonical collections use file storage
        if collection in self._canonical_collections:
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
        if self._mongo_ops and self._mongodb_enabled:
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
