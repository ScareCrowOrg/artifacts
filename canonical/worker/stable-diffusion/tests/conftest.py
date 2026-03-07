"""
Shared fixtures for Stable Diffusion queue consumer worker tests.
"""

import asyncio
import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Sample job payloads
# ---------------------------------------------------------------------------


@pytest.fixture
def sd_generate_job() -> Dict[str, Any]:
    return {
        "job_id": "job-sd-001",
        "type": "sd_generate",
        "payload": {
            "prompt": "A cute ghost holding a lantern, flat lighting, white background",
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "negative_prompt": "blur, shadow, realistic",
            "height": 512,
            "width": 512,
            "num_inference_steps": 20,
            "guidance_scale": 7.5,
            "seed": 42,
        },
        "created_at": 1234567890.0,
        "attempts": 0,
    }


@pytest.fixture
def unknown_type_job() -> Dict[str, Any]:
    return {
        "job_id": "job-sd-002",
        "type": "unsupported_type",
        "payload": {},
        "created_at": 1234567890.0,
        "attempts": 0,
    }


# ---------------------------------------------------------------------------
# Mock Redis client
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Async mock for Redis client."""
    client = AsyncMock()
    client.brpop = AsyncMock(return_value=None)
    client.rpush = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    client.ping = AsyncMock(return_value=True)
    client.aclose = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# SD API responses
# ---------------------------------------------------------------------------


@pytest.fixture
def sd_api_success_response() -> Dict[str, Any]:
    return {
        "status": "success",
        "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "model": "stabilityai/stable-diffusion-xl-base-1.0",
    }


@pytest.fixture
def sd_api_error_response() -> Dict[str, Any]:
    return {
        "status": "error",
        "image_base64": None,
        "model": None,
        "error": "GPU out of memory",
    }
