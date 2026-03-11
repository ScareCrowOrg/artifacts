#!/usr/bin/env python3
"""
Ollama FastAPI Wrapper Service

Provides HTTP interface to Ollama LLM service with Redis L1 heartbeat registration.
Supports job types: ollama_generate, ollama_chat.

Endpoints:
- POST /api/generate: Generate text from prompt
- POST /api/chat: Chat interaction with messages
- GET /api/version: Health check endpoint
- GET /health: Health check (FastAPI convention)

Architecture:
- HTTP proxy to raw Ollama container at OLLAMA_HOST
- Redis L1 heartbeat: registers state:service:ollama:available on startup
- Fire-and-forget pattern: heartbeat doesn't block service startup
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Ollama Wrapper API",
    description="HTTP proxy to Ollama LLM service with Redis heartbeat",
    version="1.0.0"
)

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://scareverse-ollama-service:11434")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120"))
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "11434"))
SERVICE_HOST = os.getenv("SERVICE_HOST", "0.0.0.0")

# Redis heartbeat configuration
_REDIS_HEARTBEAT_INTERVAL = int(os.getenv("REDIS_HEARTBEAT_INTERVAL", "60"))
_SERVICE_NAME = "ollama"
_AVAILABILITY_KEY = f"state:service:{_SERVICE_NAME}:available"
_AVAILABILITY_TTL = _REDIS_HEARTBEAT_INTERVAL * 3  # 3× interval for safety margin

# Global HTTP client
_http_client: Optional[httpx.AsyncClient] = None


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    """Request model for /api/generate endpoint."""
    model: str = Field(default="mistral", description="Model name")
    prompt: str = Field(..., description="Prompt text")
    stream: bool = Field(default=False, description="Enable streaming")
    options: Dict[str, Any] = Field(default_factory=dict, description="Generation options")


class ChatMessage(BaseModel):
    """Message in chat history."""
    role: str = Field(..., description="Message role: 'user', 'assistant', etc")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request model for /api/chat endpoint."""
    model: str = Field(default="mistral", description="Model name")
    messages: list[ChatMessage] = Field(..., description="Message history")
    stream: bool = Field(default=False, description="Enable streaming")
    options: Dict[str, Any] = Field(default_factory=dict, description="Chat options")


# ---------------------------------------------------------------------------
# Redis heartbeat – self-registers state:service:ollama:available
# ---------------------------------------------------------------------------

async def _redis_heartbeat_loop() -> None:
    """
    Background task: write ``state:service:ollama:available`` to Redis L1
    every ``REDIS_HEARTBEAT_INTERVAL`` seconds with a 3× TTL.

    Services own their availability reporting – this removes the need for
    GateKeeper to probe HTTP endpoints, and is more reliable than external probes.
    """
    redis_host = os.getenv("REDIS_L1_HOST", "redis-local")
    redis_port = int(os.getenv("REDIS_L1_PORT", "6380"))
    redis_db = int(os.getenv("REDIS_L1_DB", "0"))
    redis_password = os.getenv("REDIS_L1_PASSWORD", "scarerunner") or None

    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("redis-py not installed – heartbeat registration disabled")
        return

    kwargs = {
        "host": redis_host,
        "port": redis_port,
        "db": redis_db,
        "decode_responses": True,
        "socket_connect_timeout": 5,
        "socket_keepalive": True,
    }
    if redis_password:
        kwargs["password"] = redis_password

    client = None
    while True:
        try:
            if client is None:
                client = aioredis.Redis(**kwargs)
            await client.set(_AVAILABILITY_KEY, "1", ex=_AVAILABILITY_TTL)
            logger.debug("Heartbeat: %s refreshed (TTL %ds)", _AVAILABILITY_KEY, _AVAILABILITY_TTL)
        except Exception as exc:
            logger.warning("Heartbeat failed for %s: %s", _AVAILABILITY_KEY, exc)
            client = None  # Force reconnect on next iteration
        await asyncio.sleep(_REDIS_HEARTBEAT_INTERVAL)


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize HTTP client and start Redis heartbeat loop on app startup."""
    global _http_client
    _http_client = httpx.AsyncClient(base_url=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT)

    # Start heartbeat as fire-and-forget background task
    asyncio.create_task(_redis_heartbeat_loop())
    logger.info("Ollama wrapper started: proxy=%s, heartbeat=%s", OLLAMA_HOST, _AVAILABILITY_KEY)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up HTTP client on shutdown."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        logger.info("HTTP client closed")


# ---------------------------------------------------------------------------
# Health check endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, str]:
    """Health check endpoint (FastAPI convention)."""
    return {"status": "healthy"}


@app.get("/api/version")
async def version() -> Dict[str, Any]:
    """Health check endpoint matching Ollama interface."""
    if not _http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    try:
        response = await _http_client.get("/api/version")
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.error("Failed to get Ollama version: %s", exc)
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {str(exc)}")


# ---------------------------------------------------------------------------
# Proxy endpoints
# ---------------------------------------------------------------------------

@app.post("/api/generate")
async def generate(request: GenerateRequest) -> Dict[str, Any]:
    """
    Generate text from a prompt via Ollama.

    Args:
        request: GenerateRequest with model, prompt, stream, options

    Returns:
        Response from Ollama /api/generate endpoint
    """
    if not _http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    try:
        body = {
            "model": request.model,
            "prompt": request.prompt,
            "stream": request.stream,
            "options": request.options,
        }
        logger.info("POST /api/generate model=%s", request.model)
        response = await _http_client.post("/api/generate", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        logger.error("Ollama request timeout")
        raise HTTPException(status_code=504, detail="Ollama request timeout")
    except httpx.HTTPError as exc:
        logger.error("Ollama request failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Ollama error: {str(exc)}")
    except Exception as exc:
        logger.error("Unexpected error in /api/generate: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat")
async def chat(request: ChatRequest) -> Dict[str, Any]:
    """
    Chat interaction with Ollama.

    Args:
        request: ChatRequest with model, messages, stream, options

    Returns:
        Response from Ollama /api/chat endpoint
    """
    if not _http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    try:
        # Convert ChatMessage objects to dicts
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        body = {
            "model": request.model,
            "messages": messages,
            "stream": request.stream,
            "options": request.options,
        }
        logger.info("POST /api/chat model=%s messages=%d", request.model, len(messages))
        response = await _http_client.post("/api/chat", json=body)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        logger.error("Ollama request timeout")
        raise HTTPException(status_code=504, detail="Ollama request timeout")
    except httpx.HTTPError as exc:
        logger.error("Ollama request failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Ollama error: {str(exc)}")
    except Exception as exc:
        logger.error("Unexpected error in /api/chat: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Passthrough proxy for other Ollama endpoints
# ---------------------------------------------------------------------------

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request) -> Dict[str, Any]:
    """
    Generic proxy for any Ollama endpoint not explicitly handled above.

    Forwards the request to Ollama and returns the response.
    """
    if not _http_client:
        raise HTTPException(status_code=503, detail="HTTP client not initialized")

    try:
        # Read request body if present
        body = None
        if request.method in ["POST", "PUT"]:
            body = await request.body()

        # Forward to Ollama
        response = await _http_client.request(
            method=request.method,
            url=f"/{path}",
            content=body,
            headers={"content-type": request.headers.get("content-type", "application/json")}
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        logger.error("Ollama proxy timeout for %s", path)
        raise HTTPException(status_code=504, detail="Ollama request timeout")
    except httpx.HTTPError as exc:
        logger.error("Ollama proxy error for %s: %s", path, exc)
        raise HTTPException(status_code=503, detail=f"Ollama error: {str(exc)}")
    except Exception as exc:
        logger.error("Unexpected error in proxy for %s: %s", path, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        log_level=logging.INFO
    )
