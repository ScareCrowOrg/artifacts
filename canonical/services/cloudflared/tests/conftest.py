"""
Shared test fixtures for the cloudflared service worker tests.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# ── Path setup ────────────────────────────────────────────────────────────────
# Allow importing config / main without installing the package.

_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[3]  # artifacts/

for _p in [str(_service_dir), str(_artifacts_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_base_service():
    """Patch BaseService so heartbeat never actually contacts Redis."""
    mock = MagicMock()
    mock.heartbeat = AsyncMock(return_value=None)
    mock.cleanup = AsyncMock(return_value=None)
    with patch("main.BaseService", return_value=mock):
        yield mock


@pytest.fixture()
def app_client(mock_base_service):
    """Synchronous TestClient with lifespan events disabled for simple tests."""
    from main import app

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
