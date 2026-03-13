"""
Gemini CLI Router for ScareVerse Backend.

Provides REST API endpoints for Gemini CLI session management:
- POST /prompt - Send prompt to Gemini
- POST /api/gemini/execute - Execute Gemini prompt (alias)
- GET /stats - Session statistics with GPU info

Integrated from ScareRunner into Backend as part of architecture fix.
"""

import asyncio
import logging
import subprocess
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# Global session instance (will be set by lifespan in main.py)
gemini_session: Optional[Any] = None


def set_gemini_session(session):
    """Set the global Gemini session instance (called from main.py lifespan)"""
    global gemini_session
    gemini_session = session


class PromptRequest(BaseModel):
    """Request model for /prompt endpoint"""

    prompt: str = Field(..., min_length=1, description="Prompt text to send to Gemini")
    timeout: int = Field(30, ge=5, le=300, description="Timeout in seconds")


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


@router.post("/prompt")
async def send_prompt(request: PromptRequest):
    """
    Send a prompt to Gemini CLI.

    **Authentication**: Not required (local development)

    This endpoint maintains a persistent Gemini session for zero cold start.

    Args:
        request: PromptRequest with prompt text and timeout

    Returns:
        dict: Response from Gemini with metadata

    Raises:
        HTTPException: If Gemini session not initialized or execution fails
    """
    if not gemini_session:
        raise HTTPException(
            status_code=503,
            detail="Gemini CLI not available - GEMINI_API_KEY not configured",
        )

    try:
        response = await gemini_session.send_prompt(
            request.prompt, timeout=request.timeout
        )
        return response
    except Exception as e:
        logger.error("Error executing prompt: %s", e)
        raise HTTPException(status_code=500, detail=f"Gemini execution error: {str(e)}") from e


@router.post("/api/gemini/execute")
async def execute_gemini(request: PromptRequest):
    """
    Execute Gemini prompt (alias for /prompt).

    **Authentication**: Not required (local development)

    This is an alternative endpoint name for compatibility.

    Args:
        request: PromptRequest with prompt text and timeout

    Returns:
        dict: Response from Gemini with metadata
    """
    return await send_prompt(request)


@router.get("/stats")
async def get_stats():
    """
    Get session statistics with GPU info.

    **Authentication**: Not required (local development)

    Returns:
        dict: Session statistics including:
            - Gemini session stats (prompts processed, chars, etc.)
            - GPU utilization and memory
            - Vite dev server status
    """
    stats = {
        "gemini": {
            "available": gemini_session is not None,
            "initialized": gemini_session.initialized if gemini_session else False,
        },
        "gpu": get_gpu_stats(),
    }

    # Add detailed Gemini stats if session exists
    if gemini_session:
        stats["gemini"].update(
            {
                "model": gemini_session.model,
                "prompts_processed": gemini_session.prompts_processed,
                "total_input_chars": gemini_session.total_input_chars,
                "total_output_chars": gemini_session.total_output_chars,
                "uptime_seconds": (
                    (asyncio.get_event_loop().time() - gemini_session.start_time)
                    if gemini_session.start_time
                    else 0
                ),
                "last_error": gemini_session.last_error,
            }
        )

    return stats
