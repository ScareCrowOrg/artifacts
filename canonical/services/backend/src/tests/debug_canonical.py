#!/usr/bin/env python
"""
Debug script for CanonicalQueryEngine data loading.

Run from project root:
    cd backend && python -m pytest ../tests/debug_canonical.py -v -s

Or run directly:
    cd backend && python ../tests/debug_canonical.py
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / ".."))

from app.database.query_engine.canonical_engine import CanonicalQueryEngine
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_canonical_engine_initialization():
    """Test if CanonicalQueryEngine initializes and loads data."""
    print("\n" + "="*80)
    print("TEST 1: CanonicalQueryEngine Initialization")
    print("="*80)

    # Resolve from project root, not from tests directory
    base_path = Path(__file__).parent.parent.parent / "artifacts" / "canonical"
    print(f"Base path: {base_path}")
    print(f"Path exists: {base_path.exists()}")

    if not base_path.exists():
        print(f"[FAIL] Base path doesn't exist: {base_path}")
        return False, None

    # Check if notebook_item_types directory exists
    nit_dir = base_path / "notebook_item_types"
    print(f"\nnotebook_item_types directory: {nit_dir}")
    print(f"Directory exists: {nit_dir.exists()}")

    if nit_dir.exists():
        json_files = list(nit_dir.glob("*.json"))
        print(f"JSON files found: {len(json_files)}")
        for f in json_files[:3]:
            print(f"  - {f.name}")

    # Initialize engine
    try:
        engine = CanonicalQueryEngine(base_path=base_path)
        print(f"\n[OK] CanonicalQueryEngine initialized successfully")
        return True, engine
    except Exception as e:
        print(f"\n[FAIL] Failed to initialize: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_table_contents(engine):
    """Test if data was loaded into SQLite tables."""
    print("\n" + "="*80)
    print("TEST 2: Table Contents")
    print("="*80)

    # Check notebook_item_types table
    try:
        cursor = engine.conn.execute("SELECT COUNT(*) as cnt FROM notebook_item_types")
        result = cursor.fetchone()
        count = result[0] if result else 0

        print(f"notebook_item_types row count: {count}")

        if count == 0:
            print("[WARN]  Table is EMPTY! Data was not loaded.")
            return False

        # Get sample rows
        cursor = engine.conn.execute("SELECT _id, name FROM notebook_item_types LIMIT 3")
        rows = cursor.fetchall()
        print(f"\nSample rows:")
        for row in rows:
            print(f"  - {row[0]}: {row[1]}")

        return True
    except Exception as e:
        print(f"[FAIL] Error checking table: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_canonical_find(engine):
    """Test CanonicalQueryEngine.find()."""
    print("\n" + "="*80)
    print("TEST 3: CanonicalQueryEngine.find() - Empty Query")
    print("="*80)

    try:
        # Test with empty query (should return all)
        results = engine.find(
            collection="notebook_item_types",
            query={},
            limit=5
        )

        print(f"Results returned: {len(results)}")

        if not results:
            print("[WARN]  No results returned!")
            return False

        # Show sample results
        print(f"\nSample results:")
        for i, result in enumerate(results[:2]):
            print(f"\nResult {i+1}:")
            # Truncate long fields
            for key, value in result.items():
                if isinstance(value, str) and len(str(value)) > 100:
                    print(f"  {key}: {str(value)[:100]}...")
                else:
                    print(f"  {key}: {value}")

        return True
    except Exception as e:
        print(f"[FAIL] Error calling find(): {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schemas(engine):
    """Show what schemas CanonicalQueryEngine has."""
    print("\n" + "="*80)
    print("TEST 4: Available Schemas")
    print("="*80)

    collections = [k for k in engine.schemas.keys() if k not in ["version", "description", "last_updated"]]
    print(f"Collections: {len(collections)}")

    if "notebook_item_types" in collections:
        print("\n[OK] notebook_item_types schema exists")
        print(f"Fields: {list(engine.schemas['notebook_item_types'].keys())}")
    else:
        print("\n[FAIL] notebook_item_types NOT in schemas!")

    return True


async def test_async_find(engine):
    """Test async find (used by actual code)."""
    print("\n" + "="*80)
    print("TEST 5: Async find() - Used by actual code")
    print("="*80)

    try:
        results = await engine.find(
            collection="notebook_item_types",
            query={},
            limit=5
        )

        print(f"Async results returned: {len(results)}")

        if not results:
            print("[WARN]  No async results!")
            return False

        print(f"[OK] First result ID: {results[0].get('_id', 'N/A')}")
        return True
    except Exception as e:
        print(f"[FAIL] Error in async find: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=== DEBUGGING CANONICAL ENGINE DATA LOADING ===".center(80))

    # Test 1: Initialization
    init_ok, engine = test_canonical_engine_initialization()
    if not init_ok or not engine:
        print("\n[FAIL] Initialization failed, stopping tests")
        return False

    # Test 2: Table contents
    table_ok = test_table_contents(engine)

    # Test 3: find() with sync
    find_ok = test_canonical_find(engine)

    # Test 4: Schemas
    schema_ok = test_schemas(engine)

    # Test 5: Async find
    import asyncio
    async_ok = asyncio.run(test_async_find(engine))

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"[OK] Initialization: {'PASS' if init_ok else 'FAIL'}")
    print(f"{'[OK]' if table_ok else '[FAIL]'} Table contents: {'PASS' if table_ok else 'FAIL'}")
    print(f"{'[OK]' if find_ok else '[FAIL]'} find() sync: {'PASS' if find_ok else 'FAIL'}")
    print(f"{'[OK]' if schema_ok else '[FAIL]'} Schemas: {'PASS' if schema_ok else 'FAIL'}")
    print(f"{'[OK]' if async_ok else '[FAIL]'} find() async: {'PASS' if async_ok else 'FAIL'}")

    all_pass = init_ok and table_ok and find_ok and schema_ok and async_ok
    print(f"\n{'[PASS] ALL TESTS PASSED' if all_pass else '[FAIL] SOME TESTS FAILED'}")

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
