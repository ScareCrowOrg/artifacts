"""
Shared fixtures for Ollama queue consumer worker tests.
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
def generate_job() -> Dict[str, Any]:
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
def chat_job() -> Dict[str, Any]:
    return {
        "job_id": "job-ollama-002",
        "type": "ollama_chat",
        "payload": {
            "messages": [{"role": "user", "content": "Hello"}],
            "model": "mistral",
            "stream": False,
            "options": {},
        },
        "created_at": 1234567890.0,
        "attempts": 0,
    }


@pytest.fixture
def unknown_type_job() -> Dict[str, Any]:
    return {
        "job_id": "job-ollama-003",
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
# Ollama API responses
# ---------------------------------------------------------------------------


@pytest.fixture
def ollama_generate_response() -> Dict[str, Any]:
    return {
        "model": "mistral",
        "created_at": "2026-01-01T00:00:00Z",
        "response": "ScareVerse is an amazing platform for 3D asset generation.",
        "done": True,
    }


@pytest.fixture
def ollama_chat_response() -> Dict[str, Any]:
    return {
        "model": "mistral",
        "created_at": "2026-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": "Hello there!"},
        "done": True,
    }
