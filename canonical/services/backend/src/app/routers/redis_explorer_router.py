"""
Redis Explorer API Router - RESTful endpoints for Redis exploration.

Provides endpoints for hierarchical Redis key navigation, value inspection,
and safe state invalidation with confirmation.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import get_current_user_required
from ..models import User
from ..services.redis_explorer_service import RedisExplorerService

logger = logging.getLogger(__name__)

# Create redis_explorer router
redis_explorer_router = APIRouter(prefix="/redis-explorer", tags=["RedisExplorer"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ScanKeysRequest(BaseModel):
    """Request model for scanning Redis keys."""

    prefix: str = Field(
        default="", description="Key prefix to filter by (e.g., 'aider:session')"
    )
    delimiter: str = Field(
        default=":", description="Delimiter for hierarchical structure"
    )
    max_depth: int = Field(
        default=1, ge=1, le=10, description="Maximum depth levels to return"
    )


class DeleteKeysRequest(BaseModel):
    """Request model for deleting Redis keys by prefix."""

    prefix: str = Field(
        ...,
        min_length=1,
        description="Key prefix pattern to delete (e.g., 'aider:session:test:')",
    )
    dry_run: bool = Field(
        default=True, description="If true, return count without deleting"
    )
    confirm: bool = Field(
        default=False, description="Must be true to actually delete keys (safety check)"
    )


# ============================================================================
# Service Instance
# ============================================================================

_explorer_service: Optional[RedisExplorerService] = None


def get_explorer_service() -> RedisExplorerService:
    """Get or create Redis Explorer Service instance."""
    global _explorer_service
    if _explorer_service is None:
        _explorer_service = RedisExplorerService()
    return _explorer_service


# ============================================================================
# Endpoints
# ============================================================================


@redis_explorer_router.get("/info")
async def get_redis_info(
    current_user: User = Depends(get_current_user_required),
) -> Dict[str, Any]:
    """
    Get Redis server information and statistics.

    Returns Redis version, memory usage, key count, and other metrics.
    """
    try:
        service = get_explorer_service()
        info = await service.get_redis_info()

        logger.info("User %s retrieved Redis info: %s keys", current_user.id, info['total_keys'])

        return info

    except Exception as e:
        logger.error("Error getting Redis info: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Redis info: {str(e)}",
        )


@redis_explorer_router.post("/scan")
async def scan_keys(
    request: ScanKeysRequest, current_user: User = Depends(get_current_user_required)
) -> Dict[str, Any]:
    """
    Scan Redis keys hierarchically by prefix using SCAN (non-blocking).

    Returns nodes (branch prefixes) and keys (final keys) at the current level.
    This enables hierarchical navigation through the Redis keyspace.

    Example:
        POST /scan with prefix="" returns top-level prefixes (e.g., ["aider", "ollama"])
        POST /scan with prefix="aider" returns sub-prefixes (e.g., ["session", "job"])
        POST /scan with prefix="aider:session" returns session IDs or final keys
    """
    try:
        service = get_explorer_service()
        result = await service.scan_keys_by_prefix(
            prefix=request.prefix,
            delimiter=request.delimiter,
            max_depth=request.max_depth,
        )

        logger.info(
            "User %s scanned Redis keys with prefix '%s': %s nodes, %s keys",
            current_user.id, request.prefix, len(result['nodes']), len(result['keys'])
        )

        return result

    except Exception as e:
        logger.error("Error scanning Redis keys: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan Redis keys: {str(e)}",
        )


@redis_explorer_router.get("/key/{key:path}")
async def get_key_value(
    key: str, current_user: User = Depends(get_current_user_required)
) -> Dict[str, Any]:
    """
    Get value of a specific Redis key with automatic JSON parsing.

    Supports all Redis data types (string, hash, list, set, zset).
    Automatically parses JSON values when possible.

    Returns key metadata including type, value, TTL, and memory size.
    """
    try:
        service = get_explorer_service()
        result = await service.get_key_value(key)

        logger.info("User %s retrieved Redis key: %s (type: %s)", current_user.id, key, result['type'])

        return result

    except Exception as e:
        logger.error("Error getting Redis key value: %s", e)

        if "does not exist" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get key value: {str(e)}",
        )


@redis_explorer_router.post("/delete")
async def delete_keys_by_prefix(
    request: DeleteKeysRequest, current_user: User = Depends(get_current_user_required)
) -> Dict[str, Any]:
    """
    Delete Redis keys matching a prefix pattern (state invalidation).

    **DESTRUCTIVE OPERATION** - Use with caution!

    Two-step safety process:
    1. First call with dry_run=true to preview keys to be deleted
    2. Second call with dry_run=false and confirm=true to actually delete

    The confirm flag must be explicitly set to true for actual deletion.
    This prevents accidental deletion via API exploration or automation.

    Example workflow:
        1. POST {"prefix": "aider:session:test:", "dry_run": true}
           -> Returns count and sample of keys to be deleted
        2. Review the preview
        3. POST {"prefix": "aider:session:test:", "dry_run": false, "confirm": true}
           -> Actually deletes the keys
    """
    try:
        # Safety check: require explicit confirmation for actual deletion
        if not request.dry_run and not request.confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must set 'confirm: true' to delete keys. "
                "Use 'dry_run: true' to preview first.",
            )

        service = get_explorer_service()
        result = await service.delete_keys_by_prefix(
            prefix=request.prefix, dry_run=request.dry_run
        )

        if request.dry_run:
            logger.info(
                "User %s previewed deletion of keys with prefix '%s': %s keys found",
                current_user.id, request.prefix, result['keys_found']
            )
        else:
            logger.warning(
                "User %s DELETED %s keys with prefix '%s'",
                current_user.id, result['keys_deleted'], request.prefix
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting Redis keys: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete keys: {str(e)}",
        )


@redis_explorer_router.get("/health")
async def redis_health_check() -> Dict[str, Any]:
    """
    Check Redis connection health (no authentication required).

    Returns connection status and basic info if Redis is available.
    """
    try:
        service = get_explorer_service()
        info = await service.get_redis_info()

        return {
            "status": "healthy",
            "redis_available": True,
            "version": info.get("version", "unknown"),
            "total_keys": info.get("total_keys", 0),
        }

    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return {"status": "unhealthy", "redis_available": False, "error": str(e)}
