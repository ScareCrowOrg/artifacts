"""
Redis Cache Write Operations and Cache Invalidation

Provides cached write operations (insert, update, delete) for JSONDatabase
with automatic cache invalidation to maintain consistency.
"""

import logging
from typing import Any, Dict, Optional

from .redis_cache_read_ops import RedisCacheReadOperations

logger = logging.getLogger(__name__)


class RedisCachedJSONDatabase(RedisCacheReadOperations):
    """
    Complete Redis-cached wrapper for JSONDatabase.

    Provides transparent caching for read operations and automatic
    cache invalidation for write operations, maintaining JSONDatabase
    as the source of truth.
    """

    async def insert_async(
        self,
        collection: str,
        document,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> str:
        """
        Insert a document and invalidate related cache entries.

        Args:
            collection: Collection name
            document: Pydantic model instance to insert
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            Document ID
        """
        # Insert to disk (source of truth)
        doc_id = self.insert(collection, document, user_id, session_id, is_canonical)

        # Invalidate related cache entries
        await self._invalidate_collection_cache(
            collection, user_id, session_id, is_canonical
        )

        return doc_id

    async def update_async(
        self,
        collection: str,
        doc_id: str,
        updates: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Update a document and invalidate related cache entries.

        Args:
            collection: Collection name
            doc_id: Document ID
            updates: Dictionary of fields to update
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            True if updated, False if not found
        """
        # Update on disk (source of truth)
        result = self.update(
            collection, doc_id, updates, user_id, session_id, is_canonical
        )

        # Invalidate related cache entries
        await self._invalidate_collection_cache(
            collection, user_id, session_id, is_canonical, doc_id
        )

        return result

    async def delete_async(
        self,
        collection: str,
        doc_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> bool:
        """
        Delete a document and invalidate related cache entries.

        Args:
            collection: Collection name
            doc_id: Document ID
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            True if deleted, False if not found
        """
        # Delete from disk (source of truth)
        result = self.delete(collection, doc_id, user_id, session_id, is_canonical)

        # Invalidate related cache entries
        await self._invalidate_collection_cache(
            collection, user_id, session_id, is_canonical, doc_id
        )

        return result

    async def _invalidate_collection_cache(
        self,
        collection: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
        doc_id: Optional[str] = None,
    ):
        """
        Invalidate all cache entries for a collection.

        Args:
            collection: Collection name
            user_id: User ID (for targeted invalidation)
            session_id: Session ID (for targeted invalidation)
            is_canonical: Whether this is a canonical artifact
            doc_id: Specific document ID (for targeted invalidation)
        """
        # Build invalidation pattern
        pattern_parts = ["jsondatabase", "*", collection]

        if is_canonical:
            pattern_parts.append("canonical")
        else:
            pattern_parts.append("runtime")

        # Add user/session filters if provided
        if user_id:
            pattern_parts.append(f"user:{user_id}")
        if session_id:
            pattern_parts.append(f"session:{session_id}")
        if doc_id:
            pattern_parts.append(f"id:{doc_id}")

        pattern_parts.append("*")
        pattern = ":".join(pattern_parts)

        await self._invalidate_cache_pattern(pattern)

        # Also invalidate find_many queries for this collection
        find_many_pattern = f"jsondatabase:find_many:{collection}:*"
        await self._invalidate_cache_pattern(find_many_pattern)

    async def find_async(
        self,
        collection: str,
        query: Dict[str, Any],
        model_class=None,
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ):
        """
        Async wrapper for find operation (synchronous underlying call).

        Args:
            collection: Collection name
            query: Query dictionary with field filters
            model_class: Pydantic model class for deserialization
            user_id: User ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact
            limit: Maximum number of documents to return

        Returns:
            List of matching documents
        """
        # Call the synchronous find method from the base JSONDatabase
        return self.find(
            collection=collection,
            query=query,
            model_class=model_class,
            user_id=user_id,
            is_canonical=is_canonical,
            limit=limit,
        )
