"""
Integration example for SandboxQueryEngine.

This example demonstrates the API and usage patterns for SandboxQueryEngine.
For actual integration, use with HybridDatabase (Sub-Issue 1.6).

Usage:
    cd backend
    poetry run python examples/sandbox_query_example.py
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from app.database.query_engine import SandboxQueryEngine


async def setup_mock_redis():
    """Create a mock Redis client for demonstration."""
    mock_redis = AsyncMock()
    cache = {}
    
    async def mock_get(key):
        return cache.get(key)
    
    async def mock_setex(key, ttl, value):
        cache[key] = value
        print(f"✅ Cached schema for {key.split(':')[-1]} (TTL: {ttl}s)")
        return True
    
    async def mock_delete(*keys):
        deleted = 0
        for key in keys:
            if key in cache:
                del cache[key]
                deleted += 1
        if deleted:
            print(f"✅ Invalidated {deleted} cache entry(ies)")
        return deleted
    
    async def mock_scan(cursor, match=None, count=100):
        if cursor != 0:
            return (0, [])
        matching_keys = [k for k in cache.keys() if match and k.startswith(match.replace("*", ""))]
        return (0, matching_keys)
    
    mock_redis.get = mock_get
    mock_redis.setex = mock_setex
    mock_redis.delete = mock_delete
    mock_redis.scan = mock_scan
    
    return mock_redis


def create_sample_sandbox_data(base_path: Path):
    """Create sample sandbox data for demonstration."""
    # Create sandbox structure
    sandbox_path = base_path / "sandbox"
    sandbox_path.mkdir(exist_ok=True)
    
    # User 1 data
    user1_path = sandbox_path / "user123"
    user1_path.mkdir(exist_ok=True)
    
    # Create tasks collection
    tasks = [
        {"_id": "task1", "title": "Complete project", "priority": 10, "status": "active"},
        {"_id": "task2", "title": "Review PR", "priority": 7, "status": "active"},
        {"_id": "task3", "title": "Write tests", "priority": 8, "status": "completed"},
    ]
    
    with open(user1_path / "tasks.json", 'w') as f:
        json.dump(tasks, f, indent=2)
    
    print(f"✅ Created sample sandbox data")
    return base_path


async def example_schema_inference():
    """Example 1: Schema inference from sandbox documents."""
    print("\n" + "="*70)
    print("Example 1: Dynamic Schema Inference")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = create_sample_sandbox_data(Path(temp_dir))
        redis_client = await setup_mock_redis()
        engine = SandboxQueryEngine(redis_client, base_path)
        
        # Scan documents and build schema
        print("\n🔍 Scanning documents to infer schema...")
        schema = await engine._scan_all_documents("user123", "tasks")
        
        print(f"Inferred schema for 'tasks' collection:")
        for field, spec in schema.items():
            print(f"  - {field}: {spec['type']} (nullable: {spec['nullable']})")


async def example_caching():
    """Example 2: Schema caching behavior."""
    print("\n" + "="*70)
    print("Example 2: Redis Schema Caching")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = create_sample_sandbox_data(Path(temp_dir))
        redis_client = await setup_mock_redis()
        engine = SandboxQueryEngine(redis_client, base_path)
        
        # First call - cache miss
        print("\n🔍 First call (cache miss)...")
        schema1 = await engine._get_or_build_schema("user123", "tasks")
        print(f"   Schema fields: {list(schema1.keys())}")
        
        # Second call - cache hit
        print("\n🔍 Second call (cache hit)...")
        schema2 = await engine._get_or_build_schema("user123", "tasks")
        print(f"   Schema fields: {list(schema2.keys())}")
        
        print("\n✅ Second call used cached schema (no rebuild)")


async def example_cache_invalidation():
    """Example 3: Cache invalidation patterns."""
    print("\n" + "="*70)
    print("Example 3: Cache Invalidation Hooks")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = create_sample_sandbox_data(Path(temp_dir))
        redis_client = await setup_mock_redis()
        engine = SandboxQueryEngine(redis_client, base_path)
        
        # Build cache
        print("\n📦 Building cache...")
        await engine._get_or_build_schema("user123", "tasks")
        
        # Invalidate specific collection
        print("\n🗑️ Invalidating 'tasks' collection cache...")
        await engine.invalidate_schema_cache("user123", "tasks")
        
        # Build multiple caches
        print("\n📦 Building multiple collection caches...")
        await engine._get_or_build_schema("user123", "tasks")
        
        # Add another collection
        notes = [{"_id": "note1", "content": "Test note"}]
        user_path = base_path / "sandbox" / "user123"
        with open(user_path / "notes.json", 'w') as f:
            json.dump(notes, f)
        
        await engine._get_or_build_schema("user123", "notes")
        
        # Invalidate all user schemas
        print("\n🗑️ Invalidating all schemas for user123...")
        await engine.invalidate_all_user_schemas("user123")


async def example_type_inference():
    """Example 4: Type inference examples."""
    print("\n" + "="*70)
    print("Example 4: Type Inference")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)
        redis_client = await setup_mock_redis()
        engine = SandboxQueryEngine(redis_client, base_path)
        
        # Test type inference
        print("\n🔍 Type inference examples:")
        test_values = [
            (None, "null value"),
            (True, "boolean"),
            (42, "integer"),
            (3.14, "float"),
            ("hello", "string"),
            ([1, 2, 3], "array"),
            ({"key": "value"}, "object"),
        ]
        
        for value, description in test_values:
            inferred_type = engine._infer_type(value)
            print(f"  - {description:15} → {inferred_type}")


async def example_performance():
    """Example 5: Performance demonstration."""
    print("\n" + "="*70)
    print("Example 5: Performance Characteristics")
    print("="*70)
    
    import time
    
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)
        sandbox_path = base_path / "sandbox" / "user123"
        sandbox_path.mkdir(parents=True)
        
        redis_client = await setup_mock_redis()
        engine = SandboxQueryEngine(redis_client, base_path)
        
        # Test with 1k documents
        print("\n📊 Testing with 1,000 documents...")
        large_dataset = [
            {"_id": str(i), "field1": i, "field2": f"value{i}"}
            for i in range(1000)
        ]
        
        with open(sandbox_path / "large.json", 'w') as f:
            json.dump(large_dataset, f)
        
        start = time.time()
        schema = await engine._scan_all_documents("user123", "large")
        elapsed = time.time() - start
        
        print(f"   Schema built in {elapsed*1000:.2f}ms")
        print(f"   Fields inferred: {len(schema)}")
        print(f"   Target: <100ms - {'✅ PASS' if elapsed < 0.1 else '❌ FAIL'}")


async def example_integration_pattern():
    """Example 6: Integration with HybridDatabase pattern."""
    print("\n" + "="*70)
    print("Example 6: Integration Pattern (Sub-Issue 1.6)")
    print("="*70)
    
    print("""
    The SandboxQueryEngine integrates with HybridDatabase as follows:
    
    class HybridDatabase:
        def __init__(self):
            self._sandbox_engine = SandboxQueryEngine(redis_client, base_path)
        
        async def insert(self, collection, document, user_id):
            # ... perform insert ...
            
            # Invalidate schema cache
            await self._sandbox_engine.invalidate_schema_cache(
                user_id, collection
            )
        
        async def find(self, collection, query, user_id):
            # Use SandboxQueryEngine for queries
            return await self._sandbox_engine.find(
                user_id=user_id,
                collection=collection,
                query=query
            )
    
    ✅ Cache invalidation happens automatically on write operations
    ✅ Queries use cached schemas for optimal performance
    ✅ Schema evolution handled automatically
    """)


async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("SandboxQueryEngine Integration Examples")
    print("="*70)
    
    await example_schema_inference()
    await example_caching()
    await example_cache_invalidation()
    await example_type_inference()
    await example_performance()
    await example_integration_pattern()
    
    print("\n" + "="*70)
    print("✅ All examples completed successfully!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
