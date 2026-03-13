"""
Search Operations Router

Provides endpoints for searching code and files in the repository:
- GET /api/search/grep - Search for text patterns in files
- GET /api/search/find - Find files by name pattern

These endpoints expose existing MCP tools as HTTP APIs for frontend consumption.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user_required
from ..models.users import User

logger = logging.getLogger(__name__)

# Import MCP tools with error handling
try:
    from ..mcp.tools.file_tools import search_files
    from ..mcp.tools.repo_tools import search_code

    logger.info(
        "[SEARCH_ROUTER] Successfully imported MCP tools (search_code, search_files)"
    )
except ImportError as e:
    logger.error("[SEARCH_ROUTER] Failed to import MCP tools: %s", e)
    logger.error("[SEARCH_ROUTER] Search endpoints will not be available")
    # Re-raise to fail fast at startup
    raise RuntimeError(f"MCP tools not available: {e}") from e

# Create router with /search prefix
search_router = APIRouter(prefix="/search", tags=["search"])
logger.info("[SEARCH_ROUTER] Router created with prefix='/search'")


@search_router.get("/grep")
async def grep_endpoint(
    pattern: str = Query(
        ...,
        description="Search pattern (supports regex - auto-detected by metacharacters)",
    ),
    path: str = Query(
        ".", description="Directory to search (relative, supports wildcards: *, ?, [])"
    ),
    file_pattern: Optional[str] = Query(
        None, description="File pattern filter (e.g., '*.py')"
    ),
    case_sensitive: bool = Query(False, description="Case sensitive search"),
    max_results: int = Query(
        100, description="Maximum results to return", ge=1, le=1000
    ),
    _current_user: User = Depends(get_current_user_required),
):
    """
    Search for text patterns in files (grep).

    Required: authenticated user

    Supports:
    - **Regex patterns**: Automatically detected (e.g., "foo|bar", "^import", "\\w+Error")
    - **Path wildcards**: Use *, ?, [] in path parameter (e.g., "backend/*/routers")

    Returns matches with file path, line number, and content.

    Examples:
        - Simple: ?pattern=TODO&path=backend/app
        - Regex OR: ?pattern=foo|bar&path=.
        - Path wildcards: ?pattern=import&path=backend/*/routers
        - Combined: ?pattern=^class\\s+&path=**/models/*.py
    """
    logger.info("[GREP] Request received: pattern=%s, path=%s, file_pattern=%s", pattern, path, file_pattern)

    try:
        params = {
            "query": pattern,
            "path": path,
            "file_pattern": file_pattern,
            "case_sensitive": case_sensitive,
            "max_results": max_results,
        }

        result = await search_code(params)

        logger.info("[GREP] Search completed: found %s matches", result['count'])

        return {
            "status": "ok",
            "pattern": result["query"],
            "matches": result["matches"],
            "count": result["count"],
            "truncated": result["truncated"],
        }

    except ValueError as e:
        logger.error("[GREP] Validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        logger.error("[GREP] Path not found: %s", e)
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("[GREP] Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro ao executar busca: {str(e)}") from e


@search_router.get("/find")
async def find_endpoint(
    pattern: str = Query("*", description="Filename pattern (glob syntax, default: *)"),
    path: str = Query(
        ".", description="Starting directory (relative, supports wildcards: *, ?, [])"
    ),
    recursive: bool = Query(True, description="Recursive search"),
    _current_user: User = Depends(get_current_user_required),
):
    """
    Find files by name pattern (glob).

    Required: authenticated user

    Supports:
    - **Path wildcards**: Use *, ?, [] in path parameter (e.g., "src/*/components")

    Returns matching files with path, name, type, and size.

    Examples:
        - Simple: ?pattern=*.py&path=backend/app
        - Path wildcards: ?pattern=*.json&path=backend/*/config
        - Recursive: ?pattern=test_*.py&path=**/tests&recursive=true
    """
    logger.info("[FIND] Request received: pattern=%s, path=%s, recursive=%s", pattern, path, recursive)

    try:
        params = {"pattern": pattern, "path": path, "recursive": recursive}

        result = await search_files(params)

        logger.info("[FIND] Search completed: found %s matches", result['count'])

        return {
            "status": "ok",
            "pattern": result["pattern"],
            "search_path": result["search_path"],
            "matches": result["matches"],
            "count": result["count"],
        }

    except ValueError as e:
        logger.error("[FIND] Validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        logger.error("[FIND] Path not found: %s", e)
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error("[FIND] Unexpected error: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Erro ao buscar arquivos: {str(e)}"
        )


# Log router information at module level
logger.info("[SEARCH_ROUTER] Module loaded successfully")
logger.info("[SEARCH_ROUTER] Registered routes: %s", [route.path for route in search_router.routes])
