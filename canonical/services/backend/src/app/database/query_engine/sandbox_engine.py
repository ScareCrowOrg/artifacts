"""
SandboxQueryEngine - Dynamic schema inference for user sandbox data.

This engine extends CanonicalQueryEngine but infers schemas dynamically
by scanning all documents in a user's sandbox collection. Inferred schemas
are cached in Redis with 1-hour TTL for performance.

Key features:
- Dynamic schema inference from sandbox documents (READ-ONLY)
- Redis caching with 1-hour TTL
- Cache invalidation hooks for unified write operations
- Support for all MongoDB operators inherited from CanonicalQueryEngine
- Type inference for Python to SQLite mapping

Architecture:
    SandboxQueryEngine (CanonicalQueryEngine)
    ├── _scan_all_documents() - Build schema by scanning all docs
    ├── _infer_type() - Infer SQLite type from Python value
    ├── _get_or_build_schema() - Get from cache or build new
    ├── invalidate_schema_cache() - Invalidate specific collection cache
    └── invalidate_all_user_schemas() - Invalidate all user caches

Integration:
    - Cache invalidation hooks called by HybridDatabase (Sub-Issue 1.6)
    - Write operations use unified API, not separate methods in this engine
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .canonical_engine import CanonicalQueryEngine

logger = logging.getLogger(__name__)


class SandboxQueryEngine(CanonicalQueryEngine):
    """
    Query engine for Sandbox data with dynamic schema inference.

    Unlike CanonicalQueryEngine which uses predefined schemas from JSON,
    this engine infers schemas by scanning all documents in a user's
    sandbox collection and caches the result in Redis.

    Example:
        engine = SandboxQueryEngine(redis_client, base_path)

        # Query user's sandbox data
        results = await engine.find(
            user_id="user123",
            collection="documents",
            query={"status": "active"}
        )

        # Invalidate cache after mutation (called by HybridDatabase)
        await engine.invalidate_schema_cache("user123", "documents")
    """

    def __init__(self, redis_client, base_path: Path):
        """
        Initialize SandboxQueryEngine without predefined schemas.

        Args:
            redis_client: Redis client for caching (must support async methods)
            base_path: Base path to artifacts directory

        Note:
            Unlike CanonicalQueryEngine, this engine does not load schemas
            from a JSON file. Schemas are inferred dynamically from documents.
        """
        self.redis = redis_client
        self.base_path = base_path

        # Initialize parent WITHOUT loading schemas from file
        # We override schemas_path to None to skip schema loading
        super().__init__(schemas_path=None)

        # Clear any schemas that might have been loaded
        self.schemas = {}

        logger.info("SandboxQueryEngine initialized with dynamic schema inference")

    async def find(
        self,
        user_id: str,
        collection: str,
        query: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
        sort: Optional[List[tuple]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find documents in user's sandbox with dynamic schema.

        Args:
            user_id: User ID (owner of sandbox data)
            collection: Collection name
            query: MongoDB-style query
            projection: Fields to include/exclude (not implemented yet)
            sort: Sort specification (not implemented yet)
            limit: Maximum number of results
            skip: Number of results to skip

        Returns:
            List of dictionaries representing query results

        Raises:
            ValidationException: If query is invalid
            CompilationException: If query compilation fails

        Example:
            results = await engine.find(
                user_id="user123",
                collection="tasks",
                query={"status": "active", "priority": {"$gte": 5}},
                limit=10
            )
        """
        # Validate query syntax
        self._validate_query(query)

        # Get or build schema for this user's collection
        schema = await self._get_or_build_schema(user_id, collection)

        if not schema:
            # Empty collection - return empty results
            logger.debug("Empty schema for %s/%s, returning []", user_id, collection)
            return []

        # Temporarily set schema for compilation
        self.schemas[collection] = schema

        try:
            # Use parent class compilation logic
            sql = self._compile_query(collection, query, projection, sort, limit, skip)

            # Execute query
            cursor = self.conn.execute(sql)
            results = [dict(row) for row in cursor.fetchall()]

            # Parse JSON fields
            for result in results:
                for field_name, field_spec in schema.items():
                    if field_spec.get("type") == "JSON" and result.get(field_name):
                        try:
                            result[field_name] = json.loads(result[field_name])
                        except (json.JSONDecodeError, TypeError):
                            pass

            logger.debug("Found %s documents in %s/%s", len(results), user_id, collection)
            return results
        finally:
            # Clean up temporary schema
            self.schemas.pop(collection, None)

    async def _get_or_build_schema(
        self, user_id: str, collection: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get schema from Redis cache or build by scanning documents.

        Args:
            user_id: User ID (owner of sandbox data)
            collection: Collection name

        Returns:
            Schema dictionary mapping field names to type specifications

        Example:
            schema = await engine._get_or_build_schema("user123", "tasks")
            # Returns: {
            #     "_id": {"type": "TEXT", "nullable": False},
            #     "title": {"type": "TEXT", "nullable": False},
            #     "priority": {"type": "INTEGER", "nullable": False}
            # }
        """
        cache_key = f"sandbox_schema:{user_id}:{collection}"

        # Try Redis cache first (1 hour TTL)
        try:
            cached_schema = await self.redis.get(cache_key)
            if cached_schema:
                logger.debug("Schema cache HIT for %s", cache_key)
                return json.loads(cached_schema)
        except Exception as e:
            logger.warning("Redis cache error (falling back to rebuild): %s", e)

        # Cache miss - scan all documents to build schema
        logger.debug("Schema cache MISS for %s, scanning documents", cache_key)
        schema = await self._scan_all_documents(user_id, collection)

        # Cache for 1 hour (3600 seconds)
        if schema:
            try:
                await self.redis.setex(cache_key, 3600, json.dumps(schema))
                logger.debug("Cached schema for %s (TTL: 3600s)", cache_key)
            except Exception as e:
                logger.warning("Failed to cache schema: %s", e)

        return schema

    async def _scan_all_documents(
        self, user_id: str, collection: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Scan ALL documents in sandbox to build complete schema.

        This method reads all documents from the user's sandbox collection
        and builds a unified schema by taking the union of all fields
        across all documents.

        Args:
            user_id: User ID (owner of sandbox data)
            collection: Collection name

        Returns:
            Schema dictionary mapping field names to type specifications

        Example:
            schema = await engine._scan_all_documents("user123", "tasks")
            # Scans: artifacts/sandbox/user123/tasks.json
        """
        sandbox_path = self.base_path / "sandbox" / user_id / f"{collection}.json"

        if not sandbox_path.exists():
            logger.debug("Sandbox file not found: %s", sandbox_path)
            return {}  # Empty schema for non-existent collection

        # Load all documents
        try:
            with open(sandbox_path, "r", encoding="utf-8") as f:
                documents = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to load sandbox documents from %s: %s", sandbox_path, e)
            return {}

        if not documents or not isinstance(documents, list):
            logger.debug("No documents found in %s", sandbox_path)
            return {}

        # Build schema by union of all fields across all docs
        schema: Dict[str, Dict[str, Any]] = {}

        for doc in documents:
            if not isinstance(doc, dict):
                continue

            for field, value in doc.items():
                if field not in schema:
                    # First time seeing this field
                    schema[field] = {"type": self._infer_type(value), "nullable": False}
                else:
                    # Field seen before - check if type matches
                    inferred_type = self._infer_type(value)
                    if inferred_type != schema[field]["type"]:
                        # Type mismatch - use TEXT (most flexible)
                        logger.debug(
                            "Type conflict for %s: %s vs %s, using TEXT",
                            field, schema[field]['type'], inferred_type
                        )
                        schema[field]["type"] = "TEXT"
                        schema[field]["nullable"] = True

        logger.info(
            "Built schema for %s/%s with %s fields from %s documents",
            user_id, collection, len(schema), len(documents)
        )
        return schema

    def _infer_type(self, value: Any) -> str:
        """
        Infer SQLite type from Python value.

        Args:
            value: Python value to infer type from

        Returns:
            SQLite type string (TEXT, INTEGER, REAL, JSON)

        SQLite type mapping:
        - None -> TEXT (default for nulls)
        - bool -> INTEGER (SQLite stores booleans as 0/1)
        - int -> INTEGER
        - float -> REAL
        - str -> TEXT
        - list/dict -> JSON (stored as JSON string)
        - other -> TEXT (fallback)

        Example:
            engine._infer_type(42) == "INTEGER"
            engine._infer_type("hello") == "TEXT"
            engine._infer_type([1, 2, 3]) == "JSON"
        """
        if value is None:
            return "TEXT"  # Default for nulls
        elif isinstance(value, bool):
            # Must check bool before int (bool is subclass of int)
            return "INTEGER"  # SQLite stores bool as int
        elif isinstance(value, int):
            return "INTEGER"
        elif isinstance(value, float):
            return "REAL"
        elif isinstance(value, str):
            return "TEXT"
        elif isinstance(value, (list, dict)):
            return "JSON"
        else:
            # Fallback for unknown types
            return "TEXT"

    async def invalidate_schema_cache(self, user_id: str, collection: str):
        """
        Invalidate cached schema for specific collection.

        This method is called by HybridDatabase's unified write methods
        (insert, update, delete) to ensure schema cache stays fresh
        after mutations.

        Args:
            user_id: User ID (owner of sandbox data)
            collection: Collection name

        Example:
            # Called by HybridDatabase after insert
            await engine.invalidate_schema_cache("user123", "tasks")
        """
        cache_key = f"sandbox_schema:{user_id}:{collection}"

        try:
            deleted = await self.redis.delete(cache_key)
            if deleted:
                logger.debug("Invalidated schema cache for %s", cache_key)
            else:
                logger.debug("No cache to invalidate for %s", cache_key)
        except Exception as e:
            logger.warning("Failed to invalidate schema cache: %s", e)

    async def invalidate_all_user_schemas(self, user_id: str):
        """
        Invalidate all cached schemas for a user.

        This method is useful when bulk operations affect multiple
        collections or when a user is deleted.

        Args:
            user_id: User ID (owner of sandbox data)

        Example:
            # Invalidate all schemas for user
            await engine.invalidate_all_user_schemas("user123")
        """
        pattern = f"sandbox_schema:{user_id}:*"

        try:
            cursor = 0
            total_deleted = 0

            # Use SCAN to avoid blocking Redis
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

                if keys:
                    deleted = await self.redis.delete(*keys)
                    total_deleted += deleted

                # cursor == 0 means we've scanned all keys
                if cursor == 0:
                    break

            logger.info("Invalidated %s schema caches for user %s", total_deleted, user_id)
        except Exception as e:
            logger.warning("Failed to invalidate all user schemas: %s", e)


__all__ = ["SandboxQueryEngine"]
