"""
Shared test fixtures for the Traefik service worker tests.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_service_dir = Path(__file__).resolve().parents[1]
_artifacts_dir = _service_dir.parents[2]  # artifacts/

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
    with patch("heartbeat.BaseService", return_value=mock):
        yield mock
