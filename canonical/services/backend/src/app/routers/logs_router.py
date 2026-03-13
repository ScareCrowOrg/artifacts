"""
Logs API Router - Centralized log namespace management endpoints.

Provides API endpoints for managing and discovering log namespaces across
the frontend logging system. This eliminates duplication between frontend
and backend namespace lists.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import get_current_user_required
from ..config import BASE_DIR
from ..models import User

logger = logging.getLogger(__name__)

# Create logs router
logs_router = APIRouter(prefix="/logs", tags=["Logs"])


def discover_log_namespaces() -> List[str]:
    """
    Discover log namespaces from the frontend codebase.

    Scans the Vue.js source files to extract namespaces from createLogger() calls.
    This provides a dynamic, single source of truth for available log namespaces.

    Returns:
        List of discovered log namespace strings

    Note:
        This function scans the cockpit-vue/src directory for createLogger calls
        and extracts namespace strings. It includes both explicit and wildcard patterns.
    """
    namespaces = set()

    # Known core namespaces that should always be available
    core_namespaces = {
        "app",
        "auth",
        "api",
        "store",
        "router",
        "debug",
    }
    namespaces.update(core_namespaces)

    try:
        # Path to frontend source code
        frontend_src = Path(BASE_DIR) / "cockpit-vue" / "src"

        if not frontend_src.exists():
            logger.warning("Frontend source directory not found: %s", frontend_src)
            return sorted(list(namespaces))

        # Pattern to match createLogger('namespace') calls
        # Supports single quotes, double quotes, and template literals
        logger_pattern = re.compile(r"createLogger\(['\"`]([^'\"`]+)['\"` ]?\)")

        # Scan Vue, JS, and TS files
        for extension in ["*.vue", "*.js", "*.ts"]:
            for file_path in frontend_src.rglob(extension):
                try:
                    # Skip large files to prevent memory issues
                    file_size = file_path.stat().st_size
                    if file_size > 1_000_000:  # Skip files larger than 1MB
                        logger.debug("Skipping large file: %s (%s bytes)", file_path, file_size)
                        continue

                    with open(file_path, "r", encoding="utf-8") as f:
                        # Read line by line to avoid loading entire file in memory
                        for line in f:
                            matches = logger_pattern.findall(line)
                            namespaces.update(matches)
                except Exception as e:
                    logger.debug("Error reading %s: %s", file_path, e)
                    continue

        logger.info("Discovered %s log namespaces from frontend", len(namespaces))

    except Exception as e:
        logger.error("Error discovering log namespaces: %s", e, exc_info=True)

    return sorted(list(namespaces))


def get_default_log_namespaces() -> List[str]:
    """
    Get the default list of log namespaces.

    This provides a fallback list in case namespace discovery fails.
    Based on common ScareVerse frontend patterns.

    Returns:
        List of default log namespace strings
    """
    return [
        # Core application namespaces
        "app",
        "auth",
        "auth:login",
        "auth:logout",
        "auth:token",
        # API communication
        "api",
        "api:cells",
        "api:books",
        "api:users",
        "api:system",
        # Store/state management
        "store",
        "store:cells",
        "store:books",
        "store:auth",
        "store:ui",
        # Components
        "component:cell",
        "component:book",
        "component:chat",
        "component:layout",
        # Services
        "service:websocket",
        "service:http",
        "service:extension",
        # Features
        "feature:transmutation",
        "feature:discovery",
        "feature:registry",
        # Infrastructure
        "router",
        "debug",
    ]


@logs_router.get("/namespaces", response_model=List[str])
async def get_log_namespaces(
    discover: bool = False, _current_user: User = Depends(get_current_user_required)
):
    """
    Get available log namespaces for the frontend logging system.

    This endpoint provides a centralized list of log namespaces that can be
    used by the log-toggle-cell and other debugging tools.

    Args:
        discover: If True, scans the codebase to discover namespaces dynamically.
                 If False (default), returns a curated default list.
        current_user: Authenticated user (required)

    Returns:
        List of available log namespace strings

    Example Response:
        ```json
        [
            "app",
            "auth",
            "auth:login",
            "api",
            "api:cells",
            "store",
            "store:cells",
            "component:cell",
            "service:websocket",
            "router",
            "debug"
        ]
        ```
    """
    try:
        if discover:
            namespaces = discover_log_namespaces()
        else:
            namespaces = get_default_log_namespaces()

        logger.info("Returned %s log namespaces (discover=%s)", len(namespaces), discover)

        return namespaces

    except Exception as e:
        logger.error("Error getting log namespaces: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting log namespaces: {str(e)}",
        )


@logs_router.get("/namespaces/stats", response_model=Dict[str, Any])
async def get_log_namespaces_stats(
    _current_user: User = Depends(get_current_user_required),
):
    """
    Get statistics about log namespaces.

    Provides information about both default and discovered namespaces,
    useful for debugging and monitoring.

    Args:
        current_user: Authenticated user (required)

    Returns:
        Dictionary with namespace statistics

    Example Response:
        ```json
        {
            "default_count": 28,
            "discovered_count": 45,
            "default_namespaces": ["app", "auth", ...],
            "discovered_namespaces": ["app", "auth", "feature:new", ...]
        }
        ```
    """
    try:
        default_namespaces = get_default_log_namespaces()
        discovered_namespaces = discover_log_namespaces()

        return {
            "default_count": len(default_namespaces),
            "discovered_count": len(discovered_namespaces),
            "default_namespaces": default_namespaces,
            "discovered_namespaces": discovered_namespaces,
        }

    except Exception as e:
        logger.error("Error getting log namespace stats: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting log namespace stats: {str(e)}",
        )
