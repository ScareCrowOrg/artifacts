#!/usr/bin/env python3
"""
CLI script to invalidate L1 Redis cache from command line.

Usage:
    python scripts/invalidate_cache_l1.py              # Invalidate all collections
    python scripts/invalidate_cache_l1.py --collection notebook_item_types
    python scripts/invalidate_cache_l1.py -c cells

Requires: .env file with Redis and database configuration
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.hybrid.router import HybridDatabase
from app.config.database import REDIS_L1_ENABLED, REDIS_L1_HOST, REDIS_L1_PORT


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Invalidate L1 Redis cache for HybridDatabase",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/invalidate_cache_l1.py              # Invalidate all collections
  python scripts/invalidate_cache_l1.py -c notebook_item_types  # Specific collection
  python scripts/invalidate_cache_l1.py --list       # List supported collections
        """,
    )

    parser.add_argument(
        "-c",
        "--collection",
        type=str,
        default=None,
        help="Specific collection to invalidate. If not specified, invalidates all collections.",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all supported collections and exit.",
    )

    args = parser.parse_args()

    # List collections if requested
    if args.list:
        from app.database.hybrid.router import SUPPORTED_COLLECTIONS

        print("Supported collections:")
        for coll in sorted(SUPPORTED_COLLECTIONS):
            print(f"  - {coll}")
        return

    # Check Redis configuration
    print(f"Redis L1 configuration:")
    print(f"  REDIS_L1_ENABLED: {REDIS_L1_ENABLED}")
    print(f"  REDIS_L1_HOST: {REDIS_L1_HOST}")
    print(f"  REDIS_L1_PORT: {REDIS_L1_PORT}")

    if not REDIS_L1_ENABLED:
        print("\n[ERROR] Redis L1 is disabled (REDIS_L1_ENABLED=false)")
        print("   Enable it in .env and try again")
        sys.exit(1)

    # Create HybridDatabase and invalidate cache
    print(f"\nInvalidating cache...")
    if args.collection:
        print(f"  Collection: {args.collection}")
    else:
        print("  Collections: ALL")

    try:
        db = HybridDatabase()
        result = await db.invalidate_cache_l1(collection=args.collection)

        if result.get("success"):
            print(f"\n[SUCCESS] {result.get('message')}")

            if result.get("invalidated_collections"):
                print(f"   Collections: {', '.join(result['invalidated_collections'])}")
            elif result.get("invalidated_collection"):
                print(f"   Collection: {result['invalidated_collection']}")

            print("\n[SUCCESS] Cache invalidated successfully!")
            sys.exit(0)
        else:
            print(f"\n[ERROR] {result.get('error')}")
            print(f"   Message: {result.get('message')}")
            sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        print(f"\nTroubleshooting:")
        print(f"  1. Check Redis is running: redis-cli ping")
        print(f"  2. Verify .env has correct REDIS_HOST and REDIS_PORT")
        print(f"  3. Check HybridDatabase initialization")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
