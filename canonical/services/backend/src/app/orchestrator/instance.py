"""
Orchestrator instance management and entry point.

This module provides:
- Global orchestrator instance management
- Main entry point for running the orchestrator

Technical naming: All function names and parameters in English.
"""

import logging
import sys
from typing import Optional

from .core import Orchestrator

logger = logging.getLogger(__name__)

# Global orchestrator instance for API access
_orchestrator_instance: Optional[Orchestrator] = None


def set_orchestrator_instance(orchestrator: Orchestrator) -> None:
    """
    Set the global orchestrator instance.

    Args:
        orchestrator: The orchestrator instance to set
    """
    global _orchestrator_instance
    _orchestrator_instance = orchestrator
    logger.info("Global orchestrator instance set")


def get_orchestrator_instance() -> Optional[Orchestrator]:
    """
    Get the global orchestrator instance.

    Returns:
        The orchestrator instance or None if not set
    """
    return _orchestrator_instance


async def main():
    """Main entry point for the orchestrator."""
    from app.config import BASE_DIR

    logger.info("=" * 60)
    logger.info("Agent Orchestrator for Cell Workflow Execution")
    logger.info("=" * 60)
    logger.info("BASE_DIR: %s", BASE_DIR)
    logger.info("=" * 60)

    try:
        # Initialize orchestrator
        orchestrator = Orchestrator()

        # Initialize async components (load from database)
        await orchestrator.initialize()

        # Set global instance for API access
        set_orchestrator_instance(orchestrator)

        # Start monitoring
        await orchestrator.monitor_queue()

    except Exception as e:
        logger.error("Orchestrator failed: %s", e, exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
