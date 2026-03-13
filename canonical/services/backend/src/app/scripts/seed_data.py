"""
Seed data module (DEPRECATED).

⚠️  LEGACY CODE: Canonical data is now served directly from filesystem (artifacts/)
via discovery service. Seed_data.py is kept for backwards compatibility but does nothing.

All canonical artifacts (cell types, book types, etc) are discovered at runtime
from JSON files in artifacts/canonical/* - no database load needed.

See: backend/app/routers/artifacts_router.py for discovery implementation
"""

import logging

logger = logging.getLogger(__name__)


async def init_seed_data():
    """
    Initialize system seed data.

    DEPRECATED: This function does nothing. All canonical data is served
    directly from filesystem via discovery service.
    """
    logger.info(
        "Seed data initialization skipped (legacy - using filesystem discovery instead)"
    )
    return {
        "status": "skipped",
        "reason": "canonical_data_in_filesystem",
        "note": "All canonical artifacts are served via discovery service from artifacts/ directory",
    }


# Backward compatibility alias
init_mvp_data = init_seed_data


if __name__ == "__main__":
    # Allow running this script directly
    import asyncio

    result = asyncio.run(init_seed_data())
    print(f"Seed data result: {result}")
