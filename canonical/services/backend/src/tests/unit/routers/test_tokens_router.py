"""
Unit tests for the Personal Access Token (PAT) router.

Tests PAT creation, listing, retrieval, revocation, and regeneration endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.tokens import (
    AVAILABLE_SCOPES,
    PersonalAccessToken,
)
from app.models.users import User
from app.routers.tokens_router import tokens_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_db_mock(**async_methods):
    """Create a MagicMock db with async method stubs."""
    mock = MagicMock()
    for name, return_value in async_methods.items():
        setattr(mock, name, AsyncMock(return_value=return_value))
    return mock


@pytest.fixture
def mock_user():
    return User(
        id="user-123",
        name="Test User",
        email="test@scareverse.io",
        user_nickname="testuser",
    )


@pytest.fixture
def sample_pat(mock_user):
    return PersonalAccessToken(
        id="pat-abc",
        user_id=mock_user.id,
        name="runner-prod",
        token_prefix="eyJhbGci",
        jwt_jti="jti-unique-1",
        scopes=["redis.read", "jobs.dispatch"],
        expires_at=datetime.utcnow() + timedelta(days=90),
        environment="production",
    )


@pytest.fixture
def app(mock_user):
    test_app = FastAPI()
    test_app.include_router(tokens_router)

    from app.auth import get_current_user_required

    test_app.dependency_overrides[get_current_user_required] = lambda: mock_user
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /tokens
# ---------------------------------------------------------------------------


class TestCreateToken:
    def test_create_token_success(self, client, mock_user):
        expires_at = datetime.utcnow() + timedelta(days=30)
        mock_db = _make_db_mock(insert=None)
        with patch("app.routers.tokens_router._generate_pat_jwt") as mock_gen, \
             patch("app.routers.tokens_router.db", new=mock_db):
            mock_gen.return_value = ("rawjwttoken", "jti-abc", expires_at)

            response = client.post(
                "/tokens",
                json={
                    "name": "runner-prod",
                    "scopes": ["redis.read"],
                    "expires_in_days": 30,
                    "environment": "production",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["token"].startswith("sv_pat_")
        assert data["token_prefix"] == "rawjwttoken"[:8]
        assert "pat_id" in data
        assert "expires_at" in data
        assert "Copy now" in data["message"]

    def test_create_token_invalid_scope(self, client):
        response = client.post(
            "/tokens",
            json={
                "name": "bad-scope-token",
                "scopes": ["invalid.scope"],
                "expires_in_days": 30,
            },
        )
        assert response.status_code == 422

    def test_create_token_invalid_environment(self, client):
        response = client.post(
            "/tokens",
            json={
                "name": "test",
                "scopes": [],
                "expires_in_days": 30,
                "environment": "not-an-env",
            },
        )
        assert response.status_code == 422

    def test_create_token_jwt_failure_returns_500(self, client):
        mock_db = _make_db_mock()
        with patch(
            "app.routers.tokens_router._generate_pat_jwt",
            side_effect=RuntimeError("key error"),
        ), patch("app.routers.tokens_router.db", new=mock_db):
            response = client.post(
                "/tokens",
                json={"name": "fail", "scopes": [], "expires_in_days": 1},
            )
        assert response.status_code == 500

    def test_create_token_db_failure_returns_500(self, client):
        expires_at = datetime.utcnow() + timedelta(days=1)
        mock_db = MagicMock()
        mock_db.insert = AsyncMock(side_effect=Exception("db error"))
        with patch("app.routers.tokens_router._generate_pat_jwt") as mock_gen, \
             patch("app.routers.tokens_router.db", new=mock_db):
            mock_gen.return_value = ("jwt", "jti", expires_at)
            response = client.post(
                "/tokens",
                json={"name": "fail", "scopes": [], "expires_in_days": 1},
            )
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /tokens
# ---------------------------------------------------------------------------


class TestListTokens:
    def test_list_tokens_returns_user_tokens(self, client, mock_user, sample_pat):
        other_pat = PersonalAccessToken(
            id="pat-other",
            user_id="other-user",
            name="other-token",
            token_prefix="abcdefgh",
            jwt_jti="jti-other",
            scopes=[],
            expires_at=datetime.utcnow() + timedelta(days=10),
            environment="development",
        )
        mock_db = _make_db_mock(find_many=[sample_pat, other_pat])
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.get("/tokens")

        assert response.status_code == 200
        tokens = response.json()
        # Only user's own tokens returned
        assert len(tokens) == 1
        assert tokens[0]["id"] == "pat-abc"
        assert tokens[0]["name"] == "runner-prod"
        assert "token" not in tokens[0]

    def test_list_tokens_empty(self, client):
        mock_db = _make_db_mock(find_many=[])
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.get("/tokens")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_tokens_db_error_returns_500(self, client):
        mock_db = MagicMock()
        mock_db.find_many = AsyncMock(side_effect=Exception("db error"))
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.get("/tokens")
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /tokens/{token_id}
# ---------------------------------------------------------------------------


class TestGetToken:
    def test_get_token_success(self, client, mock_user, sample_pat):
        mock_db = _make_db_mock(find_one=sample_pat)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.get(f"/tokens/{sample_pat.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pat-abc"
        assert "token" not in data

    def test_get_token_not_found(self, client):
        mock_db = _make_db_mock(find_one=None)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.get("/tokens/nonexistent")
        assert response.status_code == 404

    def test_get_token_wrong_owner_returns_403(self, client, mock_user):
        other_pat = PersonalAccessToken(
            id="pat-other",
            user_id="other-user",
            name="other",
            token_prefix="abcdefgh",
            jwt_jti="jti-other",
            scopes=[],
            expires_at=datetime.utcnow() + timedelta(days=10),
            environment="development",
        )
        mock_db = _make_db_mock(find_one=other_pat)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.get(f"/tokens/{other_pat.id}")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /tokens/{token_id}
# ---------------------------------------------------------------------------


class TestRevokeToken:
    def test_revoke_token_success(self, client, sample_pat):
        mock_db = _make_db_mock(find_one=sample_pat, update=True)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.delete(f"/tokens/{sample_pat.id}")

        assert response.status_code == 204

    def test_revoke_token_not_found(self, client):
        mock_db = _make_db_mock(find_one=None)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.delete("/tokens/nonexistent")
        assert response.status_code == 404

    def test_revoke_already_revoked_returns_409(self, client, mock_user):
        revoked_pat = PersonalAccessToken(
            id="pat-rev",
            user_id=mock_user.id,
            name="old",
            token_prefix="abcdefgh",
            jwt_jti="jti-rev",
            scopes=[],
            expires_at=datetime.utcnow() + timedelta(days=10),
            is_active=False,
            environment="development",
        )
        mock_db = _make_db_mock(find_one=revoked_pat)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.delete(f"/tokens/{revoked_pat.id}")
        assert response.status_code == 409

    def test_revoke_wrong_owner_returns_403(self, client):
        other_pat = PersonalAccessToken(
            id="pat-other",
            user_id="other-user",
            name="other",
            token_prefix="abcdefgh",
            jwt_jti="jti-other",
            scopes=[],
            expires_at=datetime.utcnow() + timedelta(days=10),
            environment="development",
        )
        mock_db = _make_db_mock(find_one=other_pat)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.delete(f"/tokens/{other_pat.id}")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /tokens/{token_id}/regenerate
# ---------------------------------------------------------------------------


class TestRegenerateToken:
    def test_regenerate_token_success(self, client, mock_user, sample_pat):
        expires_at = datetime.utcnow() + timedelta(days=90)
        mock_db = _make_db_mock(find_one=sample_pat, update=True, insert=None)
        with patch("app.routers.tokens_router._generate_pat_jwt") as mock_gen, \
             patch("app.routers.tokens_router.db", new=mock_db):
            mock_gen.return_value = ("newrawjwt", "new-jti", expires_at)
            response = client.post(f"/tokens/{sample_pat.id}/regenerate")

        assert response.status_code == 200
        data = response.json()
        assert data["token"].startswith("sv_pat_")

    def test_regenerate_with_custom_expiry(self, client, mock_user, sample_pat):
        expires_at = datetime.utcnow() + timedelta(days=30)
        mock_db = _make_db_mock(find_one=sample_pat, update=True, insert=None)
        with patch("app.routers.tokens_router._generate_pat_jwt") as mock_gen, \
             patch("app.routers.tokens_router.db", new=mock_db):
            mock_gen.return_value = ("newrawjwt", "new-jti", expires_at)
            response = client.post(
                f"/tokens/{sample_pat.id}/regenerate?expires_in_days=30"
            )

        assert response.status_code == 200
        # Confirm the correct expires_in_days was forwarded to the generator
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        assert call_kwargs.kwargs.get("expires_in_days") == 30 or (
            call_kwargs.args and call_kwargs.args[3] == 30
        )

    def test_regenerate_invalid_expiry_returns_422(self, client, mock_user, sample_pat):
        mock_db = _make_db_mock(find_one=sample_pat)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.post(
                f"/tokens/{sample_pat.id}/regenerate?expires_in_days=0"
            )
        assert response.status_code == 422

    def test_regenerate_expiry_too_large_returns_422(self, client, mock_user, sample_pat):
        mock_db = _make_db_mock(find_one=sample_pat)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.post(
                f"/tokens/{sample_pat.id}/regenerate?expires_in_days=366"
            )
        assert response.status_code == 422

    def test_regenerate_not_found(self, client):
        mock_db = _make_db_mock(find_one=None)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.post("/tokens/nonexistent/regenerate")
        assert response.status_code == 404

    def test_regenerate_wrong_owner_returns_403(self, client):
        other_pat = PersonalAccessToken(
            id="pat-other",
            user_id="other-user",
            name="other",
            token_prefix="abcdefgh",
            jwt_jti="jti-other",
            scopes=[],
            expires_at=datetime.utcnow() + timedelta(days=10),
            environment="development",
        )
        mock_db = _make_db_mock(find_one=other_pat)
        with patch("app.routers.tokens_router.db", new=mock_db):
            response = client.post(f"/tokens/{other_pat.id}/regenerate")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestPersonalAccessTokenModel:
    def test_valid_scopes_accepted(self):
        pat = PersonalAccessToken(
            user_id="u1",
            name="test",
            token_prefix="abcdefgh",
            jwt_jti="jti-1",
            scopes=["redis.read", "jobs.dispatch"],
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        assert pat.scopes == ["redis.read", "jobs.dispatch"]

    def test_invalid_scope_raises(self):
        with pytest.raises(Exception):
            PersonalAccessToken(
                user_id="u1",
                name="test",
                token_prefix="abcdefgh",
                jwt_jti="jti-1",
                scopes=["invalid.scope"],
                expires_at=datetime.utcnow() + timedelta(days=30),
            )

    def test_invalid_environment_raises(self):
        with pytest.raises(Exception):
            PersonalAccessToken(
                user_id="u1",
                name="test",
                token_prefix="abcdefgh",
                jwt_jti="jti-1",
                scopes=[],
                expires_at=datetime.utcnow() + timedelta(days=30),
                environment="unknown",
            )

    def test_default_is_active_true(self):
        pat = PersonalAccessToken(
            user_id="u1",
            name="test",
            token_prefix="abcdefgh",
            jwt_jti="jti-1",
            scopes=[],
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        assert pat.is_active is True
