#!/usr/bin/env python
"""
Debug script for HybridDatabase.find_many() with notebook_item_types.

Simulates what happens when frontend calls GET /api/cells/types/list

Run from backend dir:
    python ../tests/debug_hybrid_find.py
"""

import sys
import asyncio
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / ".."))

from app.database import db
from app.models import NotebookItemType, User
from app.database.hybrid.router import HybridDatabase
import logging

# System user for internal operations (bypass RBAC)
SYSTEM_USER = User(
    id="system",
    email="system@scareverse.internal",
    name="System",
    roles=["admin"],
    permissions=["*"],  # Full access
)

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_hybrid_find_many():
    """Test HybridDatabase.find_many() for notebook_item_types."""
    print("\n" + "="*80)
    print("TESTING HybridDatabase.find_many('notebook_item_types')")
    print("="*80)

    # Initialize HybridDatabase manually
    base_path = Path(__file__).parent.parent.parent / "artifacts"
    print(f"\nBase path: {base_path}")

    try:
        db_instance = HybridDatabase(
            base_path=base_path,
            is_test_env=True
        )
        print("[OK] HybridDatabase initialized")
    except Exception as e:
        print(f"[FAIL] Failed to initialize HybridDatabase: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Use the hardcoded SYSTEM_USER
    print(f"\n[INFO] Using SYSTEM_USER: id={SYSTEM_USER.id}, roles={SYSTEM_USER.roles}, permissions={SYSTEM_USER.permissions}")

    # Test find_many
    print("\nCalling db.find_many('notebook_item_types', current_user=SYSTEM_USER)...")
    try:
        results = await db_instance.find_many(
            collection="notebook_item_types",
            current_user=SYSTEM_USER,
            model_class=NotebookItemType
        )

        print(f"\n[OK] find_many returned {len(results)} results")

        if not results:
            print("[WARN] NO RESULTS - This is the problem!")
            print("\nDebugging steps:")
            print("1. Check if CanonicalQueryEngine loaded data")
            print("2. Check if RBAC allows access")
            print("3. Check if MultiSourceSearch is working")
            return False

        # Show sample results
        print(f"\nSample results (first 2):")
        for i, result in enumerate(results[:2]):
            if isinstance(result, NotebookItemType):
                print(f"  {i+1}. {result.id}: {result.name}")
            else:
                print(f"  {i+1}. {result}")

        return True

    except PermissionError as e:
        print(f"[FAIL] PermissionError: {e}")
        print("Likely RBAC blocking access")
        return False
    except Exception as e:
        print(f"[FAIL] Error calling find_many: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_canonical_engine_directly():
    """Test CanonicalQueryEngine directly (what find_many calls)."""
    print("\n" + "="*80)
    print("TESTING CanonicalQueryEngine directly")
    print("="*80)

    from app.database.query_engine.canonical_engine import CanonicalQueryEngine

    base_path = Path(__file__).parent.parent.parent / "artifacts" / "canonical"
    print(f"Base path: {base_path}")

    try:
        engine = CanonicalQueryEngine(base_path=base_path)
        print("[OK] CanonicalQueryEngine initialized")

        # Check table contents
        cursor = engine.conn.execute("SELECT COUNT(*) FROM notebook_item_types")
        count = cursor.fetchone()[0]
        print(f"notebook_item_types rows in DB: {count}")

        if count == 0:
            print("[FAIL] TABLE IS EMPTY - Data loading failed!")
            return False

        # Try find
        results = await engine.find(
            collection="notebook_item_types",
            query={}
        )
        print(f"[OK] CanonicalQueryEngine.find() returned {len(results)} results")
        return True

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "=== DEBUGGING HybridDatabase.find_many() ===" .center(80))

    # Test CanonicalQueryEngine first
    print("\n[STEP 1] Test CanonicalQueryEngine directly")
    ce_ok = await test_canonical_engine_directly()

    if not ce_ok:
        print("\n[FAIL] CanonicalQueryEngine is broken, stopping")
        return False

    # Test HybridDatabase
    print("\n[STEP 2] Test HybridDatabase.find_many()")
    hd_ok = await test_hybrid_find_many()

    # Summary
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"{'[OK]' if ce_ok else '[FAIL]'} CanonicalQueryEngine: {'OK' if ce_ok else 'FAILED'}")
    print(f"{'[OK]' if hd_ok else '[FAIL]'} HybridDatabase: {'OK' if hd_ok else 'FAILED'}")

    if hd_ok:
        print("\n[PASS] notebook_item_types are loading correctly!")
        print("The issue must be elsewhere (maybe endpoint routing)")
    else:
        print("\n[FAIL] Data is not being found")

    return ce_ok and hd_ok


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
