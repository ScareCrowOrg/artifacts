"""
Redis Cache Read Operations

Provides cached read operations for JSONDatabase including find_one, find_many,
find_by_field, and find_by_fields with automatic cache management.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from .redis_cache_base import RedisCacheBase

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RedisCacheReadOperations(RedisCacheBase):
    """
    Redis-cached read operations for JSONDatabase.

    Implements find operations with transparent caching.
    """

    async def find_one_async(
        self,
        collection: str,
        doc_id: str,
        model_class: Type[T],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by ID with caching.

        Args:
            collection: Collection name
            doc_id: Document ID
            model_class: Pydantic model class to deserialize into
            user_id: User ID (for runtime artifacts)
            session_id: Session ID (for runtime artifacts)
            is_canonical: Whether this is a canonical artifact

        Returns:
            Document instance or None if not found
        """
        redis = await self._ensure_redis()

        # Generate cache key
        cache_key = self._get_cache_key(
            "find_one", collection, doc_id, user_id, session_id, is_canonical
        )

        # Try to get from cache
        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.debug("Cache hit: %s", cache_key)
                    doc_dict = json.loads(cached)
                    return model_class(**doc_dict)
            except Exception as e:
                logger.error("Error reading from cache: %s", e)

        # Cache miss - load from disk
        logger.debug("Cache miss: %s", cache_key)
        doc = self.find_one(
            collection, doc_id, model_class, user_id, session_id, is_canonical
        )

        # Cache the result
        if redis is not None and doc is not None:
            try:
                doc_json = doc.model_dump_json()
                ttl = self._get_ttl(collection, is_canonical)
                await redis.setex(cache_key, ttl, doc_json)
                logger.debug("Cached document with TTL %ss: %s", ttl, cache_key)
            except Exception as e:
                logger.error("Error caching result: %s", e)

        return doc

    async def find_many_async(
        self,
        collection: str,
        model_class: Type[T],
        user_id: Optional[str] = None,
        is_canonical: bool = False,
        limit: Optional[int] = None,
    ) -> List[T]:
        """
        Find multiple documents with caching.

        Args:
            collection: Collection name
            model_class: Pydantic model class to deserialize into
            user_id: User ID to filter by (for runtime artifacts)
            is_canonical: Whether to search canonical artifacts
            limit: Maximum number of documents to return

        Returns:
            List of document instances
        """
        redis = await self._ensure_redis()

        # Generate cache key
        cache_key = self._get_cache_key(
            "find_many", collection, user_id=user_id, is_canonical=is_canonical
        )
        if limit:
            cache_key += f":limit:{limit}"

        # Try to get from cache
        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.debug("Cache hit: %s", cache_key)
                    docs_list = json.loads(cached)
                    return [model_class(**doc_dict) for doc_dict in docs_list]
            except Exception as e:
                logger.error("Error reading from cache: %s", e)

        # Cache miss - load from disk
        logger.debug("Cache miss: %s", cache_key)
        docs = self.find_many(collection, model_class, user_id, is_canonical, limit)

        # Cache the result
        if redis is not None:
            try:
                docs_json = json.dumps([doc.model_dump(mode="json") for doc in docs])
                ttl = self._get_ttl(collection, is_canonical)
                await redis.setex(cache_key, ttl, docs_json)
                logger.debug("Cached %s documents with TTL %ss: %s", len(docs), ttl, cache_key)
            except Exception as e:
                logger.error("Error caching result: %s", e)

        return docs

    async def find_by_field_async(
        self,
        collection: str,
        field: str,
        value: Any,
        model_class: Type[T],
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by a specific field value with caching.

        Args:
            collection: Collection name
            field: Field name to search
            value: Field value to match
            model_class: Pydantic model class
            is_canonical: Whether to search canonical artifacts

        Returns:
            First matching document or None
        """
        redis = await self._ensure_redis()

        # Generate cache key
        cache_key = self._get_cache_key(
            "find_by_field",
            collection,
            field=field,
            value=value,
            is_canonical=is_canonical,
        )

        # Try to get from cache
        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.debug("Cache hit: %s", cache_key)
                    doc_dict = json.loads(cached)
                    return model_class(**doc_dict) if doc_dict else None
            except Exception as e:
                logger.error("Error reading from cache: %s", e)

        # Cache miss - load from disk
        logger.debug("Cache miss: %s", cache_key)
        doc = self.find_by_field(collection, field, value, model_class, is_canonical)

        # Cache the result
        if redis is not None:
            try:
                doc_json = json.dumps(doc.model_dump(mode="json") if doc else None)
                ttl = self._get_ttl(collection, is_canonical)
                await redis.setex(cache_key, ttl, doc_json)
                logger.debug("Cached field query with TTL %ss: %s", ttl, cache_key)
            except Exception as e:
                logger.error("Error caching result: %s", e)

        return doc

    async def find_by_fields_async(
        self,
        collection: str,
        fields: Dict[str, Any],
        model_class: Type[T],
        is_canonical: bool = False,
    ) -> Optional[T]:
        """
        Find a document by matching multiple field values with caching.

        Args:
            collection: Collection name
            fields: Dictionary of field names and values to match
            model_class: Pydantic model class
            is_canonical: Whether to search canonical artifacts

        Returns:
            First matching document or None
        """
        redis = await self._ensure_redis()

        # Generate cache key
        cache_key = self._get_cache_key(
            "find_by_fields", collection, fields=fields, is_canonical=is_canonical
        )

        # Try to get from cache
        if redis is not None:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.debug("Cache hit: %s", cache_key)
                    doc_dict = json.loads(cached)
                    return model_class(**doc_dict) if doc_dict else None
            except Exception as e:
                logger.error("Error reading from cache: %s", e)

        # Cache miss - load from disk
        logger.debug("Cache miss: %s", cache_key)
        doc = self.find_by_fields(collection, fields, model_class, is_canonical)

        # Cache the result
        if redis is not None:
            try:
                doc_json = json.dumps(doc.model_dump(mode="json") if doc else None)
                ttl = self._get_ttl(collection, is_canonical)
                await redis.setex(cache_key, ttl, doc_json)
                logger.debug("Cached fields query with TTL %ss: %s", ttl, cache_key)
            except Exception as e:
                logger.error("Error caching result: %s", e)

        return doc
