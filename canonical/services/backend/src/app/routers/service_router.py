"""
Service Info Router for ScareVerse Backend.

Provides REST API endpoints for service information:
- GET / - Root service information
- GET /info - Detailed service information
- GET /vite/status - Vite dev server status

Integrated from ScareRunner into Backend as part of architecture fix.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# Will be set by main.py
_gemini_available: bool = False


def set_gemini_available(available: bool):
    """Set whether Gemini is available (called from main.py)"""
    global _gemini_available
    _gemini_available = available


@router.get("/")
async def root():
    """
    Root endpoint with service info.

    **Authentication**: Not required (public endpoint)

    Returns basic service information including:
    - Service name and version
    - Available features
    - Architecture notes

    Returns:
        dict: Service information
    """
    return {
        "service": "ScareVerse Backend",
        "version": "2.0.0",
        "phase": "Phase 0 - Unified Architecture",
        "status": "running",
        "features": [
            "Original Backend API (/api/*)",
            "Gemini CLI (persistent session)"
            if _gemini_available
            else "Gemini CLI (not configured)",
            "Artifacts discovery (/local/*)",
            "Vite dev server (dynamic compilation)",
            "Health monitoring with GPU stats",
            "CORS enabled for local development",
        ],
        "architecture": "Unified application - Backend + ScareRunner integrated",
        "ports": {"api": 5050, "vite": 5052},
    }


@router.get("/info")
async def info():
    """
    Detailed service information.

    **Authentication**: Not required (public endpoint)

    Returns comprehensive service information including:
    - Service details
    - Available endpoints
    - Configuration

    Returns:
        dict: Detailed service information
    """
    return {
        "service": "ScareVerse Backend",
        "version": "2.0.0",
        "phase": "Phase 0 - Unified Architecture",
        "gemini": {
            "available": _gemini_available,
            "note": "Requires GEMINI_API_KEY environment variable",
        },
        "endpoints": {
            "api": {
                "prefix": "/api",
                "description": "Original Backend API endpoints",
                "examples": [
                    "/api/health",
                    "/api/cells/list",
                    "/api/books/list",
                ],
            },
            "gemini": {
                "endpoints": ["POST /prompt", "POST /api/gemini/execute", "GET /stats"],
                "description": "Gemini CLI persistent session",
            },
            "artifacts": {
                "prefix": "/local",
                "description": "Artifacts discovery and proxy",
                "examples": [
                    "/local/cell-types/",
                    "/local/book-types/",
                    "/local/import-map.json",
                ],
            },
            "health": {
                "endpoints": ["GET /health", "GET /health/live", "GET /health/ready"],
                "description": "Health monitoring endpoints",
            },
            "service": {
                "endpoints": ["GET /", "GET /info", "GET /vite/status"],
                "description": "Service information endpoints",
            },
        },
        "architecture": {
            "approach": "Unified application",
            "description": "Backend and ScareRunner functionality integrated into single app",
            "benefits": [
                "No import conflicts",
                "Clean Python package structure",
                "Single unified API surface",
                "Simplified deployment",
            ],
        },
    }


@router.get("/vite/status")
async def vite_status():
    """
    Get Vite dev server status.

    **Authentication**: Not required (public endpoint)

    Returns status of the Vite dev server that handles
    dynamic compilation of cell and book types.

    Returns:
        dict: Vite server status
    """
    # Vite is now managed by supervisord (entrypoint)
    # No longer managed by Python subprocess
    return {
        "status": "managed_by_supervisord",
        "port": 5052,
        "url": "http://localhost:5052/",
        "managed_by": "docker_entrypoint",
    }
