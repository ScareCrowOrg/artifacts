"""
Shared fixtures for Stable Diffusion HTTP worker tests.
"""

import asyncio
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
# Sample job payloads (same format backend router pushes to queue)
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
def sd_generate_job_gk_format() -> Dict[str, Any]:
    """Same job but with GateKeeper-native job_type field."""
    return {
        "job_id": "job-sd-002",
        "job_type": "sd_generate",
        "payload": {
            "prompt": "A spooky castle at night",
            "model": "stabilityai/stable-diffusion-xl-base-1.0",
            "negative_prompt": "",
            "height": 512,
            "width": 512,
            "num_inference_steps": 20,
            "guidance_scale": 7.5,
            "seed": -1,
        },
        "created_at": 1234567890.0,
        "attempts": 0,
    }


@pytest.fixture
def unknown_type_job() -> Dict[str, Any]:
    return {
        "job_id": "job-sd-003",
        "type": "unsupported_type",
        "payload": {},
        "created_at": 1234567890.0,
        "attempts": 0,
    }


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
