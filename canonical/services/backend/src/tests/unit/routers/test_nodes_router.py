"""
Unit tests for the Platform Nodes router.

Tests node registration, heartbeat, listing, and deregistration endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.tokens import PlatformNode
from app.models.users import User
from app.routers.nodes_router import nodes_router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_mock(**async_methods):
    """Create a MagicMock db with async method stubs."""
    mock = MagicMock()
    for name, return_value in async_methods.items():
        setattr(mock, name, AsyncMock(return_value=return_value))
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user():
    return User(
        id="user-456",
        name="Node User",
        email="nodes@scareverse.io",
        user_nickname="nodeuser",
    )


@pytest.fixture
def sample_node(mock_user):
    return PlatformNode(
        id="node-abc",
        user_id=mock_user.id,
        node_nickname="runner-prod",
        node_type="runner",
        endpoint_url="https://runner.example.com",
        platform_info={"hostname": "host1", "os": "Linux"},
    )


@pytest.fixture
def app(mock_user):
    test_app = FastAPI()
    test_app.include_router(nodes_router)

    from app.auth import get_current_user_required

    test_app.dependency_overrides[get_current_user_required] = lambda: mock_user
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /nodes
# ---------------------------------------------------------------------------


class TestRegisterNode:
    def test_register_node_success(self, client, mock_user):
        mock_db = _make_db_mock(find_many=[], insert=None)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.post(
                "/nodes",
                json={
                    "node_nickname": "gpu-worker-01",
                    "node_type": "worker",
                    "endpoint_url": "https://worker.example.com",
                    "platform_info": {"hostname": "docker-01"},
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["node_nickname"] == "gpu-worker-01"
        assert data["node_type"] == "worker"
        assert data["is_active"] is True

    def test_register_duplicate_nickname_returns_409(self, client, mock_user, sample_node):
        mock_db = _make_db_mock(find_many=[sample_node])
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.post(
                "/nodes",
                json={
                    "node_nickname": "runner-prod",
                    "node_type": "runner",
                },
            )

        assert response.status_code == 409

    def test_register_node_invalid_nickname_returns_422(self, client):
        response = client.post(
            "/nodes",
            json={
                "node_nickname": "INVALID NICKNAME",
                "node_type": "runner",
            },
        )
        assert response.status_code == 422

    def test_register_node_invalid_type_returns_422(self, client):
        response = client.post(
            "/nodes",
            json={
                "node_nickname": "valid-name",
                "node_type": "invalid-type",
            },
        )
        assert response.status_code == 422

    def test_register_node_nickname_too_long_returns_422(self, client):
        response = client.post(
            "/nodes",
            json={
                "node_nickname": "a" * 65,
                "node_type": "runner",
            },
        )
        assert response.status_code == 422

    def test_register_node_db_error_returns_500(self, client):
        mock_db = MagicMock()
        mock_db.find_many = AsyncMock(return_value=[])
        mock_db.insert = AsyncMock(side_effect=Exception("db fail"))
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.post(
                "/nodes",
                json={"node_nickname": "test-node", "node_type": "runner"},
            )
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /nodes
# ---------------------------------------------------------------------------


class TestListNodes:
    def test_list_nodes_returns_user_nodes(self, client, mock_user, sample_node):
        other_node = PlatformNode(
            id="node-other",
            user_id="other-user",
            node_nickname="their-runner",
            node_type="runner",
        )
        mock_db = _make_db_mock(find_many=[sample_node, other_node])
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.get("/nodes")

        assert response.status_code == 200
        nodes = response.json()
        assert len(nodes) == 1
        assert nodes[0]["node_nickname"] == "runner-prod"

    def test_list_nodes_empty(self, client):
        mock_db = _make_db_mock(find_many=[])
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.get("/nodes")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_nodes_db_error_returns_500(self, client):
        mock_db = MagicMock()
        mock_db.find_many = AsyncMock(side_effect=Exception("db fail"))
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.get("/nodes")
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /nodes/{node_id}/heartbeat
# ---------------------------------------------------------------------------


class TestNodeHeartbeat:
    def test_heartbeat_success(self, client, mock_user, sample_node):
        mock_db = _make_db_mock(find_one=sample_node, update=True)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.post(f"/nodes/{sample_node.id}/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "node-abc"
        assert "last_heartbeat" in data

    def test_heartbeat_not_found(self, client):
        mock_db = _make_db_mock(find_one=None)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.post("/nodes/nonexistent/heartbeat")
        assert response.status_code == 404

    def test_heartbeat_wrong_owner_returns_403(self, client):
        other_node = PlatformNode(
            id="node-other",
            user_id="other-user",
            node_nickname="their-runner",
            node_type="runner",
        )
        mock_db = _make_db_mock(find_one=other_node)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.post(f"/nodes/{other_node.id}/heartbeat")
        assert response.status_code == 403

    def test_heartbeat_inactive_node_returns_409(self, client, mock_user):
        inactive_node = PlatformNode(
            id="node-inactive",
            user_id=mock_user.id,
            node_nickname="old-runner",
            node_type="runner",
            is_active=False,
        )
        mock_db = _make_db_mock(find_one=inactive_node)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.post(f"/nodes/{inactive_node.id}/heartbeat")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# DELETE /nodes/{node_id}
# ---------------------------------------------------------------------------


class TestDeregisterNode:
    def test_deregister_success(self, client, mock_user, sample_node):
        mock_db = _make_db_mock(find_one=sample_node, update=True)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.delete(f"/nodes/{sample_node.id}")
        assert response.status_code == 204

    def test_deregister_not_found(self, client):
        mock_db = _make_db_mock(find_one=None)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.delete("/nodes/nonexistent")
        assert response.status_code == 404

    def test_deregister_wrong_owner_returns_403(self, client):
        other_node = PlatformNode(
            id="node-other",
            user_id="other-user",
            node_nickname="their-runner",
            node_type="runner",
        )
        mock_db = _make_db_mock(find_one=other_node)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.delete(f"/nodes/{other_node.id}")
        assert response.status_code == 403

    def test_deregister_already_inactive_returns_409(self, client, mock_user):
        inactive_node = PlatformNode(
            id="node-inactive",
            user_id=mock_user.id,
            node_nickname="old-runner",
            node_type="runner",
            is_active=False,
        )
        mock_db = _make_db_mock(find_one=inactive_node)
        with patch("app.routers.nodes_router.db", new=mock_db):
            response = client.delete(f"/nodes/{inactive_node.id}")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestPlatformNodeModel:
    def test_valid_node_types_accepted(self):
        for node_type in ["runner", "worker", "launcher", "edge_node"]:
            node = PlatformNode(
                user_id="u1",
                node_nickname="my-node",
                node_type=node_type,
            )
            assert node.node_type == node_type

    def test_invalid_node_type_raises(self):
        with pytest.raises(Exception):
            PlatformNode(
                user_id="u1",
                node_nickname="my-node",
                node_type="invalid",
            )

    def test_valid_nickname_formats(self):
        valid = ["runner", "runner-01", "my-gpu-worker", "a1b2c3"]
        for nickname in valid:
            node = PlatformNode(
                user_id="u1",
                node_nickname=nickname,
                node_type="runner",
            )
            assert node.node_nickname == nickname

    def test_invalid_nickname_uppercase_raises(self):
        with pytest.raises(Exception):
            PlatformNode(
                user_id="u1",
                node_nickname="RunnerProd",
                node_type="runner",
            )

    def test_invalid_nickname_spaces_raises(self):
        with pytest.raises(Exception):
            PlatformNode(
                user_id="u1",
                node_nickname="runner prod",
                node_type="runner",
            )

    def test_nickname_too_long_raises(self):
        with pytest.raises(Exception):
            PlatformNode(
                user_id="u1",
                node_nickname="a" * 65,
                node_type="runner",
            )

    def test_default_is_active_true(self):
        node = PlatformNode(
            user_id="u1",
            node_nickname="test",
            node_type="runner",
        )
        assert node.is_active is True
