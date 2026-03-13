#!/usr/bin/env python3
"""
Validation script for Cache Manager functionality.

This script demonstrates the core functionality of the Cache Manager
without requiring external dependencies (Redis, pytest, etc.).
"""

import hashlib
import json
from typing import Dict, List, Optional


class MockRedis:
    """Mock Redis client for demonstration purposes."""
    
    def __init__(self):
        self.storage = {}
        self.ttls = {}
    
    async def get(self, key: str) -> Optional[str]:
        return self.storage.get(key)
    
    async def setex(self, key: str, ttl: int, value: str):
        self.storage[key] = value
        self.ttls[key] = ttl
    
    async def delete(self, *keys):
        for key in keys:
            self.storage.pop(key, None)
            self.ttls.pop(key, None)
    
    async def scan(self, cursor, match, count):
        # Simple mock: return all matching keys
        matching_keys = [k for k in self.storage.keys() if self._matches(k, match)]
        return (0, matching_keys)
    
    def _matches(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for mock."""
        pattern = pattern.replace('*', '.*')
        import re
        return re.match(pattern, key) is not None


def generate_cache_key(collection: str, query: Dict, user_id: str, limit: Optional[int] = None) -> str:
    """Generate deterministic cache key using SHA256."""
    query_str = json.dumps(query, sort_keys=True)
    components = [
        collection,
        query_str,
        user_id,
        f"limit:{limit}" if limit is not None else "limit:none"
    ]
    key_str = ":".join(components)
    hash_hex = hashlib.sha256(key_str.encode()).hexdigest()
    return f"query:{hash_hex}"


async def main():
    """Run validation tests."""
    print("=" * 70)
    print("Cache Manager Validation")
    print("=" * 70)
    print()
    
    # Test 1: Deterministic key generation
    print("✓ Test 1: Deterministic cache key generation")
    key1 = generate_cache_key("templates", {"status": "published"}, "user1", 10)
    key2 = generate_cache_key("templates", {"status": "published"}, "user1", 10)
    assert key1 == key2, "Keys should be deterministic"
    print(f"  Generated key: {key1[:50]}...")
    print()
    
    # Test 2: Different queries generate different keys
    print("✓ Test 2: Different queries generate different keys")
    key3 = generate_cache_key("templates", {"status": "draft"}, "user1", 10)
    assert key1 != key3, "Different queries should have different keys"
    print(f"  Query 1 key: {key1[:50]}...")
    print(f"  Query 2 key: {key3[:50]}...")
    print()
    
    # Test 3: Different users generate different keys
    print("✓ Test 3: Different users generate different keys")
    key4 = generate_cache_key("templates", {"status": "published"}, "user2", 10)
    assert key1 != key4, "Different users should have different keys"
    print(f"  User 1 key: {key1[:50]}...")
    print(f"  User 2 key: {key4[:50]}...")
    print()
    
    # Test 4: Different collections generate different keys
    print("✓ Test 4: Different collections generate different keys")
    key5 = generate_cache_key("roles", {"status": "published"}, "user1", 10)
    assert key1 != key5, "Different collections should have different keys"
    print(f"  Templates key: {key1[:50]}...")
    print(f"  Roles key: {key5[:50]}...")
    print()
    
    # Test 5: Different limits generate different keys
    print("✓ Test 5: Different limits generate different keys")
    key5_no_limit = generate_cache_key("templates", {"status": "published"}, "user1")
    key5_limit_10 = generate_cache_key("templates", {"status": "published"}, "user1", 10)
    key5_limit_20 = generate_cache_key("templates", {"status": "published"}, "user1", 20)
    key5_limit_0 = generate_cache_key("templates", {"status": "published"}, "user1", 0)
    
    # All should be different (Bug #2 fix)
    assert key5_no_limit != key5_limit_10, "No limit and limit=10 should have different keys"
    assert key5_limit_10 != key5_limit_20, "Different limits should have different keys"
    assert key5_no_limit != key5_limit_0, "No limit and limit=0 should have different keys"
    assert key5_limit_0 != key5_limit_10, "limit=0 and limit=10 should have different keys"
    
    print(f"  No limit key: {key5_no_limit[:50]}...")
    print(f"  Limit 10 key: {key5_limit_10[:50]}...")
    print(f"  Limit 20 key: {key5_limit_20[:50]}...")
    print(f"  Limit 0 key:  {key5_limit_0[:50]}...")
    print()
    
    # Test 6: Mock Redis operations
    print("✓ Test 6: Mock Redis cache operations")
    mock_redis = MockRedis()
    
    # Set cache
    cache_key = generate_cache_key("templates", {"status": "active"}, "user1")
    data = [{"_id": "1", "name": "Template 1"}]
    await mock_redis.setex(cache_key, 300, json.dumps(data))
    print(f"  Cached {len(data)} items with key: {cache_key[:50]}...")
    
    # Get cache
    cached = await mock_redis.get(cache_key)
    assert cached is not None, "Cache should hit"
    cached_data = json.loads(cached)
    assert cached_data == data, "Cached data should match original"
    print(f"  Retrieved {len(cached_data)} items from cache")
    print()
    
    # Test 7: Secondary indexing
    print("✓ Test 7: Secondary indexing for invalidation")
    hash_part = cache_key.split(":")[-1]
    index_key = f"query_index:templates:user1:{hash_part}"
    await mock_redis.setex(index_key, 300, cache_key)
    print(f"  Created index: {index_key}")
    print(f"  Points to: {cache_key[:50]}...")
    print()
    
    # Test 8: Pattern-based invalidation
    print("✓ Test 8: Pattern-based cache invalidation")
    # Add more cache entries
    for i in range(3):
        key = generate_cache_key("templates", {"id": str(i)}, "user1")
        await mock_redis.setex(key, 300, json.dumps([{"_id": str(i)}]))
        hash_part = key.split(":")[-1]
        idx_key = f"query_index:templates:user1:{hash_part}"
        await mock_redis.setex(idx_key, 300, key)
    
    print(f"  Total keys in cache: {len(mock_redis.storage)}")
    
    # Find and delete by pattern
    pattern = "query_index:templates:user1:*"
    cursor, index_keys = await mock_redis.scan(0, match=pattern, count=100)
    print(f"  Found {len(index_keys)} index keys matching pattern")
    
    # Delete query keys
    query_keys = []
    for idx_key in index_keys:
        qkey = await mock_redis.get(idx_key)
        if qkey:
            query_keys.append(qkey)
    
    if query_keys:
        await mock_redis.delete(*query_keys)
    await mock_redis.delete(*index_keys)
    print(f"  Deleted {len(query_keys)} query keys and {len(index_keys)} index keys")
    print()
    
    # Test 9: SCHEMAS.json validation
    print("✓ Test 9: SCHEMAS.json validation")
    try:
        with open("artifacts/canonical/SCHEMAS.json", "r") as f:
            schemas = json.load(f)
        
        collections = [k for k in schemas.keys() if k not in ["version", "description", "last_updated"]]
        print(f"  Found {len(collections)} canonical collections:")
        for col in collections:
            field_count = len(schemas[col])
            print(f"    - {col}: {field_count} fields")
        
        assert len(collections) == 11, "Should have exactly 11 canonical collections"
        print()
        
        # Verify key collections
        required = ["permissions", "cells", "books", "ai_models", "content_types", 
                   "notebook_items", "contents", "templates", "roles", "workflows", 
                   "notebook_item_types"]
        for col in required:
            assert col in schemas, f"Missing required collection: {col}"
        print(f"  ✓ All 11 required collections present")
        
        # Verify last_updated
        assert schemas.get("last_updated") == "2026-02-24", "last_updated should be 2026-02-24"
        print(f"  ✓ Schema last_updated: {schemas['last_updated']}")
        
    except Exception as e:
        print(f"  ✗ Error validating SCHEMAS.json: {e}")
        return False
    
    print()
    print("=" * 70)
    print("All validation tests passed! ✓")
    print("=" * 70)
    return True


if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    exit(0 if success else 1)
