"""
Unit tests for CentralHubClient - Phase 1B.

Tests HTTP client for MongoDB proxy operations via CentralHub.
Uses pytest-mock for mocking HTTP requests.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock
from app.database.centralhub_client import CentralHubClient


@pytest.fixture
def centralhub_client():
    """Create CentralHubClient instance for testing."""
    return CentralHubClient(
        base_url="http://localhost:5051",
        api_key="test-api-key",
        enabled=True,
    )


@pytest.fixture
def disabled_client():
    """Create disabled CentralHubClient for testing."""
    return CentralHubClient(
        base_url="http://localhost:5051",
        enabled=False,
    )


class TestCentralHubClient:
    """Test suite for CentralHubClient."""

    def test_init_enabled(self, centralhub_client):
        """Test initialization with enabled=True."""
        assert centralhub_client.enabled is True
        assert centralhub_client.base_url == "http://localhost:5051"
        assert centralhub_client.api_key == "test-api-key"

    def test_init_disabled(self, disabled_client):
        """Test initialization with enabled=False."""
        assert disabled_client.enabled is False

    @pytest.mark.asyncio
    async def test_find_one_success(self, centralhub_client, mocker):
        """Test find_one returns document on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"document": {"_id": "artifact-001", "name": "Test"}}
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.find_one(
            collection="artifacts",
            query={"_id": "artifact-001"},
            user_id="user-123",
        )

        assert result == {"_id": "artifact-001", "name": "Test"}

    @pytest.mark.asyncio
    async def test_find_one_not_found(self, centralhub_client, mocker):
        """Test find_one returns None when document not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"document": None}
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.find_one(
            collection="artifacts",
            query={"_id": "nonexistent"},
            user_id="user-123",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_find_one_when_disabled(self, disabled_client):
        """Test find_one returns None when client is disabled."""
        result = await disabled_client.find_one(
            collection="artifacts",
            query={"_id": "artifact-001"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_find_one_timeout(self, centralhub_client, mocker):
        """Test find_one raises exception on timeout."""
        mock_post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        with pytest.raises(httpx.TimeoutException):
            await centralhub_client.find_one(
                collection="artifacts",
                query={"_id": "artifact-001"},
            )

    @pytest.mark.asyncio
    async def test_find_many_success(self, centralhub_client, mocker):
        """Test find_many returns list of documents."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "documents": [
                {"_id": "artifact-001", "name": "Test 1"},
                {"_id": "artifact-002", "name": "Test 2"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.find_many(
            collection="artifacts",
            query={"type": "cell"},
            user_id="user-123",
        )

        assert len(result) == 2
        assert result[0]["_id"] == "artifact-001"
        assert result[1]["_id"] == "artifact-002"

    @pytest.mark.asyncio
    async def test_find_many_empty(self, centralhub_client, mocker):
        """Test find_many returns empty list when no documents found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"documents": []}
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.find_many(
            collection="artifacts",
            query={"type": "nonexistent"},
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_find_many_when_disabled(self, disabled_client):
        """Test find_many returns empty list when disabled."""
        result = await disabled_client.find_many(
            collection="artifacts",
            query={},
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_insert_one_success(self, centralhub_client, mocker):
        """Test insert_one returns inserted_id on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"inserted_id": "artifact-001"}
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.insert_one(
            collection="artifacts",
            document={"_id": "artifact-001", "name": "Test"},
            user_id="user-123",
        )

        assert result == "artifact-001"

    @pytest.mark.asyncio
    async def test_insert_one_when_disabled(self, disabled_client):
        """Test insert_one returns None when disabled."""
        result = await disabled_client.insert_one(
            collection="artifacts",
            document={"_id": "artifact-001", "name": "Test"},
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_one_success(self, centralhub_client, mocker):
        """Test update_one returns modified_count."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"modified_count": 1}
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.update_one(
            collection="artifacts",
            query={"_id": "artifact-001"},
            update={"$set": {"name": "Updated"}},
            user_id="user-123",
        )

        assert result == 1

    @pytest.mark.asyncio
    async def test_update_one_not_found(self, centralhub_client, mocker):
        """Test update_one returns 0 when document not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"modified_count": 0}
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.update_one(
            collection="artifacts",
            query={"_id": "nonexistent"},
            update={"$set": {"name": "Updated"}},
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_update_one_when_disabled(self, disabled_client):
        """Test update_one returns 0 when disabled."""
        result = await disabled_client.update_one(
            collection="artifacts",
            query={"_id": "artifact-001"},
            update={"$set": {"name": "Updated"}},
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_delete_one_success(self, centralhub_client, mocker):
        """Test delete_one returns deleted_count."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"deleted_count": 1}
        mock_response.raise_for_status = MagicMock()

        mock_post = AsyncMock(return_value=mock_response)
        mocker.patch.object(httpx.AsyncClient, "post", mock_post)

        result = await centralhub_client.delete_one(
            collection="artifacts",
            query={"_id": "artifact-001"},
            user_id="user-123",
        )

        assert result == 1

    @pytest.mark.asyncio
    async def test_delete_one_when_disabled(self, disabled_client):
        """Test delete_one returns 0 when disabled."""
        result = await disabled_client.delete_one(
            collection="artifacts",
            query={"_id": "artifact-001"},
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_close_client(self, centralhub_client):
        """Test closing HTTP client."""
        # Initialize client
        await centralhub_client._get_client()
        assert centralhub_client._client is not None

        # Close client
        await centralhub_client.close()
        assert centralhub_client._client is None
