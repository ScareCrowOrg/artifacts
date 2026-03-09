"""
Shared test fixtures and configuration for GateKeeper + Rembg worker tests.
"""

import asyncio
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Event loop (single loop for all async tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Provide a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Sample job payloads
# ---------------------------------------------------------------------------


@pytest.fixture
def rembg_job() -> Dict[str, Any]:
    return {
        "job_id": "job-rembg-001",
        "job_type": "REMOTE_REMBG",
        "image_data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "alpha_matting": True,
    }


@pytest.fixture
def rembg_job_alias() -> Dict[str, Any]:
    return {
        "job_id": "job-rembg-002",
        "job_type": "background_removal",
        "image_data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "alpha_matting": False,
    }


@pytest.fixture
def unknown_type_job() -> Dict[str, Any]:
    return {
        "job_id": "job-unknown-001",
        "job_type": "UNSUPPORTED_TYPE",
        "payload": {},
    }


# Ollama job using backend router format ("type" field, not "job_type")
@pytest.fixture
def ollama_generate_job() -> Dict[str, Any]:
    return {
        "job_id": "job-ollama-001",
        "type": "ollama_generate",
        "payload": {
            "prompt": "Tell me about ScareVerse",
            "model": "mistral",
            "stream": False,
            "options": {},
        },
        "created_at": 1234567890.0,
        "attempts": 0,
    }


@pytest.fixture
def sd_generate_job() -> Dict[str, Any]:
    return {
        "job_id": "job-sd-001",
        "type": "sd_generate",
        "payload": {
            "prompt": "A cute ghost holding a lantern",
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "height": 512,
            "width": 512,
        },
        "created_at": 1234567890.0,
        "attempts": 0,
    }


# ---------------------------------------------------------------------------
# Mock Redis clients
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_l1() -> AsyncMock:
    """Async mock for Redis L1 (ScareRunner/owner)."""
    client = AsyncMock()
    client.brpop = AsyncMock(return_value=None)
    client.lpush = AsyncMock(return_value=1)
    client.rpush = AsyncMock(return_value=1)
    client.llen = AsyncMock(return_value=0)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.hset = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_redis_l2() -> AsyncMock:
    """Async mock for Redis L2 (CentralHub/global)."""
    client = AsyncMock()
    client.brpop = AsyncMock(return_value=None)
    client.lpush = AsyncMock(return_value=1)
    client.rpush = AsyncMock(return_value=1)
    client.llen = AsyncMock(return_value=0)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.hset = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    return client


# ---------------------------------------------------------------------------
# Sample telemetry payload
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_telemetry() -> Dict[str, Any]:
    return {
        "timestamp": "2026-03-05T10:30:00+00:00",
        "vram_free_mb": 8000,
        "vram_total_mb": 12000,
        "ram_free_mb": 16000,
        "ram_total_mb": 32000,
        "cpu_percent_global": 25.5,
        "cpu_count": 8,
    }
