"""
Health check router for ScareVerse Backend API.

Provides comprehensive health status including:
- Application readiness
- Redis connectivity
- Database (TinyDB) accessibility
- GPU statistics (if available)
- Vite dev server status

Enhanced with ScareRunner integration for unified architecture.
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from ..config import SCAREFERA_LAB_DIR
from ..config.database import REDIS_L1_ENABLED
from ..core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter()


def get_gpu_stats() -> Dict[str, Any]:
    """
    Get GPU statistics via nvidia-smi.
    Returns gracefully if nvidia-smi not available.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return {"available": False, "error": "nvidia-smi failed"}

        gpus = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append(
                        {
                            "index": parts[0],
                            "name": parts[1],
                            "utilization_percent": float(parts[2]),
                            "memory_used_mb": int(parts[3]),
                            "memory_total_mb": int(parts[4]),
                        }
                    )

        return {"available": True, "gpus": gpus}
    except FileNotFoundError:
        return {"available": False, "error": "nvidia-smi not found"}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.

    **PUBLIC ENDPOINT** - No authentication required.
    Used by monitoring systems and load balancers.

    Checks:
    - Application status
    - Redis connectivity (if enabled)
    - TinyDB database file accessibility
    - GPU availability
    - Vite dev server status

    Returns:
        dict: Health status with timestamp and check results
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    checks = {}
    overall_status = "healthy"

    # Check application initialization
    checks["app"] = "ready"

    # Check ScareFeraLab directory
    if SCAREFERA_LAB_DIR.exists():
        checks["scarefera_lab"] = "accessible"
    else:
        checks["scarefera_lab"] = "missing"
        overall_status = "degraded"
        logger.warning("ScareFeraLab directory not found: %s", SCAREFERA_LAB_DIR)

    # Check Redis connectivity (if enabled)
    if REDIS_L1_ENABLED:
        try:
            redis_client = await get_redis_client()
            if redis_client is not None:
                await redis_client.ping()
                checks["redis"] = "connected"
            else:
                checks["redis"] = "disabled"
                overall_status = "degraded"
        except Exception as e:
            checks["redis"] = "unreachable"
            overall_status = "degraded"
            logger.error("Redis health check failed: %s", e)
    else:
        checks["redis"] = "disabled"

    # Check TinyDB database file (optional - created on first use)
    try:
        # Database path is relative to the routers directory
        db_path = Path(__file__).parent.parent / "scareverse_tinydb.json"
        if db_path.exists():
            checks["database"] = "accessible"
        else:
            # Database file created on first write - not critical
            checks["database"] = "not_initialized"
    except Exception as e:
        checks["database"] = "error"
        logger.warning("Database check failed: %s", e)

    # Check GPU availability (optional - not critical)
    try:
        gpu_stats = get_gpu_stats()
        checks["gpu"] = "available" if gpu_stats["available"] else "not_available"
    except Exception as e:
        checks["gpu"] = "error"
        logger.warning("GPU check failed: %s", e)

    # Vite dev server is now managed by supervisord (entrypoint)
    # No longer checked by Python code

    return {
        "status": overall_status,
        "timestamp": timestamp,
        "checks": checks,
        "service": "ScareVerse Backend API (Unified Architecture)",
    }


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes liveness probe endpoint.

    **PUBLIC ENDPOINT** - No authentication required.
    Used by Kubernetes liveness probes.

    Simple check that the application is running.
    Should only fail if the application is completely unresponsive.

    Returns:
        dict: Minimal status response
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes readiness probe endpoint.

    **PUBLIC ENDPOINT** - No authentication required.
    Used by Kubernetes readiness probes.

    Checks if the application is ready to serve traffic.
    Includes dependency checks (Redis if enabled).

    Returns:
        dict: Ready status with dependency checks
    """
    checks = {}
    is_ready = True

    # Check Redis connectivity (if enabled and required)
    if REDIS_L1_ENABLED:
        try:
            redis_client = await get_redis_client()
            if redis_client is not None:
                await redis_client.ping()
                checks["redis"] = "ready"
            else:
                checks["redis"] = "disabled"
                # Not blocking readiness if Redis is optional
        except Exception as e:
            checks["redis"] = "not_ready"
            # Optional: Set is_ready = False if Redis is critical
            logger.warning("Redis not ready: %s", e)

    status = "ready" if is_ready else "not_ready"

    return {"status": status, "checks": checks}


@router.get("/stats")
async def get_comprehensive_stats():
    """
    Get comprehensive system statistics.

    **PUBLIC ENDPOINT** - No authentication required.

    Returns detailed statistics including:
    - GPU utilization and memory
    - Vite dev server status
    - Gemini session info (if available)
    - System health metrics

    Returns:
        dict: Comprehensive system statistics
    """
    stats = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "ScareVerse Backend API (Unified Architecture)",
        "gpu": get_gpu_stats(),
    }

    # Add Gemini status (if available)
    try:
        from .gemini_router import gemini_session

        if gemini_session:
            stats["gemini"] = {
                "available": True,
                "initialized": gemini_session.initialized,
                "model": gemini_session.model,
                "prompts_processed": gemini_session.prompts_processed,
                "total_input_chars": gemini_session.total_input_chars,
                "total_output_chars": gemini_session.total_output_chars,
                "last_error": gemini_session.last_error,
            }
        else:
            stats["gemini"] = {"available": False, "note": "Not configured"}
    except Exception as e:
        logger.debug("Could not get Gemini status: %s", e)
        stats["gemini"] = {"available": False, "error": str(e)}

    # Add Redis stats
    if REDIS_L1_ENABLED:
        try:
            redis_client = await get_redis_client()
            if redis_client is not None:
                info = await redis_client.info()
                stats["redis"] = {
                    "connected": True,
                    "used_memory_mb": round(
                        info.get("used_memory", 0) / 1024 / 1024, 2
                    ),
                    "connected_clients": info.get("connected_clients", 0),
                    "uptime_seconds": info.get("uptime_in_seconds", 0),
                }
            else:
                stats["redis"] = {"connected": False, "note": "Disabled"}
        except Exception as e:
            logger.debug("Could not get Redis stats: %s", e)
            stats["redis"] = {"connected": False, "error": str(e)}
    else:
        stats["redis"] = {"connected": False, "note": "Disabled"}

    return stats
