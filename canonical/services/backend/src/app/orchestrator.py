#!/usr/bin/env python3
"""
Agent Orchestrator for Cell Workflow Execution

This module provides backward compatibility wrapper for the refactored orchestrator.
The actual implementation has been modularized into:
- orchestrator/core.py: Main Orchestrator class
- orchestrator/helpers.py: Helper functions for conversions and Redis
- orchestrator/instance.py: Global instance management

This file re-exports all public API for backward compatibility.

Usage:
    python -m backend.app.orchestrator
"""

import logging
import sys
from pathlib import Path

# Add backend/app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.database import (
    REDIS_L1_DB,
    REDIS_L1_ENABLED,
    REDIS_L1_HOST,
    REDIS_L1_PASSWORD,
    REDIS_L1_PORT,
)

logger = logging.getLogger(__name__)

# Optional Redis L1 support
redis_client = None
if REDIS_L1_ENABLED:
    try:
        import redis

        redis_client = redis.Redis(
            host=REDIS_L1_HOST,
            port=REDIS_L1_PORT,
            db=REDIS_L1_DB,
            password=REDIS_L1_PASSWORD,
            decode_responses=True,
        )
        logger.info("Redis L1 client initialized: %s:%s", REDIS_L1_HOST, REDIS_L1_PORT)
    except ImportError:
        logger.warning("Redis L1 enabled but 'redis' package not installed")
    except Exception as e:
        logger.error("Failed to initialize Redis L1 client: %s", e)

# Import modularized components
from app.orchestrator import (
    Orchestrator,
    cell_to_pipeline_item,
    get_orchestrator_instance,
    main,
    publish_fragment_to_redis,
    publish_pipeline_fragments,
    set_orchestrator_instance,
    set_redis_client,
    update_cell_from_pipeline_item,
)

# Set Redis client in helpers module
set_redis_client(redis_client)


# Export all public API for backward compatibility
__all__ = [
    "Orchestrator",
    "set_orchestrator_instance",
    "get_orchestrator_instance",
    "main",
    "cell_to_pipeline_item",
    "update_cell_from_pipeline_item",
    "publish_fragment_to_redis",
    "publish_pipeline_fragments",
    "redis_client",
]


if __name__ == "__main__":
    sys.exit(main())
