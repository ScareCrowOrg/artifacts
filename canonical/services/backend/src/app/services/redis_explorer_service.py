"""
Redis Explorer Service - Hierarchical key exploration and state invalidation.

Provides non-blocking Redis operations for exploring keys hierarchically,
inspecting values, and safely deleting key branches with confirmation.

This service implements the Redis Explorer Cell functionality for debugging
and observability of Redis middleware state.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set

from redis.asyncio import Redis

from ..core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class RedisExplorerService:
    """
    Service for exploring Redis keys hierarchically using SCAN.

    Provides methods for:
    - Hierarchical key navigation with prefix-based grouping
    - Non-blocking key scanning using SCAN command
    - Key value inspection with JSON formatting
    - Safe deletion of key branches with confirmation
    """

    def __init__(self):
        """Initialize Redis Explorer Service."""
        self.redis: Optional[Redis] = None
        self.scan_count = 100  # Keys per SCAN iteration

    async def _ensure_redis(self) -> Redis:
        """Ensure Redis client is available."""
        if self.redis is None:
            self.redis = await get_redis_client()
            if self.redis is None:
                raise Exception("Redis is not available")
        return self.redis

    async def scan_keys_by_prefix(
        self, prefix: str = "", delimiter: str = ":", max_depth: int = 1
    ) -> Dict[str, Any]:
        """
        Scan Redis keys hierarchically by prefix using SCAN.

        This method uses SCAN (non-blocking) instead of KEYS to avoid
        blocking the Redis server. It groups keys by their prefix structure
        to enable hierarchical navigation.

        Args:
            prefix: Key prefix to filter by (e.g., "aider:session")
            delimiter: Delimiter for hierarchical structure (default ":")
            max_depth: Maximum depth levels to return from current prefix

        Returns:
            Dict containing:
            - nodes: List of prefix groups (branches)
            - keys: List of final keys at this level
            - total_scanned: Total number of keys scanned
            - prefix: Current prefix being explored

        Example:
            For keys: ["aider:session:123:data", "aider:session:456:data"]
            With prefix="aider", returns nodes=["session"]
            With prefix="aider:session", returns nodes=["123", "456"]
        """
        redis = await self._ensure_redis()

        # Prepare scan pattern
        pattern = f"{prefix}*" if prefix else "*"

        nodes: Set[str] = set()  # Branch prefixes
        keys: Set[str] = set()  # Final keys at this level
        cursor = 0
        total_scanned = 0

        logger.info("Scanning Redis keys with pattern: %s", pattern)

        try:
            # Use SCAN to iterate through keys non-blocking
            while True:
                cursor, batch = await redis.scan(
                    cursor=cursor, match=pattern, count=self.scan_count
                )

                total_scanned += len(batch)

                # Process batch to extract nodes and keys
                for key in batch:
                    # Decode bytes to string if needed
                    if isinstance(key, bytes):
                        key = key.decode("utf-8")

                    # Remove prefix to get relative key
                    if prefix and key.startswith(prefix):
                        relative_key = key[len(prefix) :]
                        if relative_key.startswith(delimiter):
                            relative_key = relative_key[len(delimiter) :]
                    else:
                        relative_key = key

                    # Split by delimiter to find next level
                    parts = relative_key.split(delimiter)

                    if len(parts) > max_depth:
                        # This is a branch node - add next segment
                        next_segment = parts[0]
                        if next_segment:
                            nodes.add(next_segment)
                    else:
                        # This is a final key at current level
                        keys.add(key)

                # SCAN returns 0 when iteration is complete
                if cursor == 0:
                    break

            logger.info(
                "Redis scan complete: %s keys scanned, %s nodes, %s final keys",
                total_scanned, len(nodes), len(keys)
            )

            return {
                "prefix": prefix,
                "delimiter": delimiter,
                "nodes": sorted(list(nodes)),
                "keys": sorted(list(keys)),
                "total_scanned": total_scanned,
            }

        except Exception as e:
            logger.error("Error scanning Redis keys: %s", e)
            raise Exception(f"Failed to scan Redis keys: {str(e)}") from e

    async def get_key_value(self, key: str) -> Dict[str, Any]:
        """
        Get value of a specific Redis key with automatic JSON parsing.

        Args:
            key: Redis key to inspect

        Returns:
            Dict containing:
            - key: The key name
            - type: Redis data type (string, hash, list, set, zset)
            - value: The value (auto-parsed as JSON if possible)
            - ttl: Time-to-live in seconds (-1 if no expiry, -2 if key doesn't exist)
            - size: Memory size in bytes

        Raises:
            Exception: If key doesn't exist or Redis operation fails
        """
        redis = await self._ensure_redis()

        try:
            # Check if key exists
            if not await redis.exists(key):
                raise Exception(f"Key does not exist: {key}")

            # Get key type
            key_type = await redis.type(key)
            key_type = key_type.decode() if isinstance(key_type, bytes) else key_type

            # Get TTL
            ttl = await redis.ttl(key)

            # Get value based on type
            if key_type == "string":
                raw_value = await redis.get(key)
                # Try to parse as JSON
                try:
                    value = json.loads(raw_value)
                except (json.JSONDecodeError, TypeError):
                    value = raw_value

            elif key_type == "hash":
                value = await redis.hgetall(key)
                # Try to parse hash values as JSON
                parsed_value = {}
                for k, v in value.items():
                    try:
                        parsed_value[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        parsed_value[k] = v
                value = parsed_value

            elif key_type == "list":
                value = await redis.lrange(key, 0, -1)

            elif key_type == "set":
                value = list(await redis.smembers(key))

            elif key_type == "zset":
                value = await redis.zrange(key, 0, -1, withscores=True)

            else:
                value = f"<Unsupported type: {key_type}>"

            # Get memory usage (approximate)
            try:
                size = await redis.memory_usage(key)
            except Exception:
                size = None

            logger.info("Retrieved Redis key: %s (type: %s)", key, key_type)

            return {
                "key": key,
                "type": key_type,
                "value": value,
                "ttl": ttl,
                "size": size,
            }

        except Exception as e:
            logger.error("Error getting Redis key value: %s", e)
            raise Exception(f"Failed to get key value: {str(e)}") from e

    async def delete_keys_by_prefix(
        self, prefix: str, dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Delete all Redis keys matching a prefix pattern.

        This operation is used for state invalidation. It uses SCAN to find
        all matching keys and deletes them in a pipeline for efficiency.

        IMPORTANT: This is a destructive operation. Always use with confirmation.

        Args:
            prefix: Key prefix pattern to delete (e.g., "aider:session:test:")
            dry_run: If True, return count without deleting (default: False)

        Returns:
            Dict containing:
            - prefix: The prefix pattern used
            - keys_found: Number of keys matching the pattern
            - keys_deleted: Number of keys actually deleted
            - dry_run: Whether this was a dry run
            - sample_keys: Sample of keys that would be/were deleted (max 10)

        Raises:
            Exception: If Redis operation fails
        """
        redis = await self._ensure_redis()

        pattern = f"{prefix}*"
        keys_to_delete: List[str] = []
        cursor = 0

        logger.info("%s Redis keys with pattern: %s", 'Dry run' if dry_run else 'Deleting', pattern)

        try:
            # Use SCAN to find all matching keys
            while True:
                cursor, batch = await redis.scan(
                    cursor=cursor, match=pattern, count=self.scan_count
                )

                keys_to_delete.extend(batch)

                if cursor == 0:
                    break

            keys_found = len(keys_to_delete)

            if dry_run:
                logger.info("Dry run: Found %s keys matching pattern %s", keys_found, pattern)
                return {
                    "prefix": prefix,
                    "keys_found": keys_found,
                    "keys_deleted": 0,
                    "dry_run": True,
                    "sample_keys": keys_to_delete[:10] if keys_to_delete else [],
                }

            # Delete keys using pipeline for efficiency
            if keys_to_delete:
                pipeline = redis.pipeline()
                for key in keys_to_delete:
                    pipeline.delete(key)
                await pipeline.execute()

                logger.info("Deleted %s keys matching pattern %s", keys_found, pattern)
            else:
                logger.info("No keys found matching pattern %s", pattern)

            return {
                "prefix": prefix,
                "keys_found": keys_found,
                "keys_deleted": keys_found,
                "dry_run": False,
                "sample_keys": keys_to_delete[:10] if keys_to_delete else [],
            }

        except Exception as e:
            logger.error("Error deleting Redis keys: %s", e)
            raise Exception(f"Failed to delete keys: {str(e)}") from e

    async def get_redis_info(self) -> Dict[str, Any]:
        """
        Get Redis server information and statistics.

        Returns:
            Dict containing:
            - version: Redis server version
            - used_memory: Memory used by Redis
            - total_keys: Total number of keys in current database
            - connected_clients: Number of connected clients
            - uptime_seconds: Server uptime in seconds

        Raises:
            Exception: If Redis operation fails
        """
        redis = await self._ensure_redis()

        try:
            info = await redis.info()
            dbsize = await redis.dbsize()

            return {
                "version": info.get("redis_version", "unknown"),
                "used_memory": info.get("used_memory_human", "unknown"),
                "used_memory_bytes": info.get("used_memory", 0),
                "total_keys": dbsize,
                "connected_clients": info.get("connected_clients", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "role": info.get("role", "unknown"),
            }

        except Exception as e:
            logger.error("Error getting Redis info: %s", e)
            raise Exception(f"Failed to get Redis info: {str(e)}") from e
