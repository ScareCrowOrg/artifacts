"""
Unit tests for notebook_item_types_router.py

Tests cover:
- GET /notebook-item-types - List notebook item types
- GET /notebook-item-types/{type_id} - Get specific type
- POST /notebook-item-types - Create new type
- PUT /notebook-item-types/{type_id} - Update type
- DELETE /notebook-item-types/{type_id} - Delete type

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.main import app
from app.models import User, NotebookItemType
from app.auth import get_current_user_required


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.name = "Test User"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_notebook_item_type():
    """Mock notebook item type."""
    nit = Mock(spec=NotebookItemType)
    nit.id = "type-123"
    nit.name = "Test Type"
    nit.description = "Test notebook item type"
    nit.default_initial_data = {"key": "value"}
    nit.default_refs = {"ref1": ["path1"]}
    nit.allow_instance_override_refs = True
    nit.created_at = datetime.utcnow()
    nit.updated_at = datetime.utcnow()
    nit.model_dump = Mock(return_value={
        "id": "type-123",
        "name": "Test Type",
        "description": "Test notebook item type",
        "default_initial_data": {"key": "value"},
        "default_refs": {"ref1": ["path1"]},
        "allow_instance_override_refs": True
    })
    return nit


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestListNotebookItemTypes:
    """Tests for GET /notebook-item-types endpoint."""
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_list_types_success(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test listing notebook item types successfully."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_notebook_item_type])
        
        response = client.get("/api/notebook-item-types")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "type-123"
        assert data[0]["name"] == "Test Type"
        
        mock_db.find_many.assert_called_once_with(
            "notebook_item_types",
            NotebookItemType,
            is_canonical=True
        )
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_list_types_with_name_filter(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test listing types with name filter."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_notebook_item_type])
        
        response = client.get("/api/notebook-item-types?name=Test")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Type"
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_list_types_name_filter_no_match(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test listing types with name filter that doesn't match."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_notebook_item_type])
        
        response = client.get("/api/notebook-item-types?name=NonExistent")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_list_types_with_pagination(self, mock_db, client, mock_user):
        """Test pagination parameters."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Create 10 mock types
        mock_types = []
        for i in range(10):
            mock_type = Mock(spec=NotebookItemType)
            mock_type.id = f"type-{i}"
            mock_type.name = f"Type {i}"
            mock_types.append(mock_type)
        
        mock_db.find_many = AsyncMock(return_value=mock_types)
        
        response = client.get("/api/notebook-item-types?skip=2&limit=3")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["id"] == "type-2"
        assert data[2]["id"] == "type-4"
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_list_types_empty_result(self, mock_db, client, mock_user):
        """Test listing when no types exist."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.get("/api/notebook-item-types")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_list_types_database_error(self, mock_db, client, mock_user):
        """Test database error handling."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.get("/api/notebook-item-types")
        
        assert response.status_code == 500
        assert "Error listing notebook item types" in response.json()["detail"]


class TestGetNotebookItemType:
    """Tests for GET /notebook-item-types/{type_id} endpoint."""
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_get_type_success(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test getting a specific type successfully."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_notebook_item_type)
        
        response = client.get("/api/notebook-item-types/type-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "type-123"
        assert data["name"] == "Test Type"
        
        mock_db.find_one.assert_called_once_with(
            "notebook_item_types",
            "type-123",
            NotebookItemType,
            is_canonical=True
        )
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_get_type_not_found(self, mock_db, client, mock_user):
        """Test getting a non-existent type."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=None)
        
        response = client.get("/api/notebook-item-types/nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_get_type_database_error(self, mock_db, client, mock_user):
        """Test database error handling."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.get("/api/notebook-item-types/type-123")
        
        assert response.status_code == 500
        assert "Error getting notebook item type" in response.json()["detail"]


class TestCreateNotebookItemType:
    """Tests for POST /notebook-item-types endpoint."""
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_create_type_success(self, mock_db, client, mock_user):
        """Test creating a new type successfully."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])  # No existing types
        mock_db.insert = AsyncMock()
        
        type_data = {
            "name": "New Type",
            "description": "New type description",
            "default_initial_data": {"key": "value"},
            "default_refs": {"ref1": ["path1"]},
            "allow_instance_override_refs": True
        }
        
        response = client.post("/api/notebook-item-types", json=type_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Type"
        assert data["description"] == "New type description"
        
        mock_db.insert.assert_called_once()
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_create_type_duplicate_name(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test creating type with duplicate name."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_notebook_item_type.name = "Test Type"
        mock_db.find_many = AsyncMock(return_value=[mock_notebook_item_type])
        
        type_data = {
            "name": "Test Type",
            "description": "Duplicate name"
        }
        
        response = client.post("/api/notebook-item-types", json=type_data)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_create_type_database_error(self, mock_db, client, mock_user):
        """Test database error during creation."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        mock_db.insert = AsyncMock(side_effect=Exception("Database error"))
        
        type_data = {
            "name": "New Type",
            "description": "Description"
        }
        
        response = client.post("/api/notebook-item-types", json=type_data)
        
        assert response.status_code == 500
        assert "Error creating notebook item type" in response.json()["detail"]


class TestUpdateNotebookItemType:
    """Tests for PUT /notebook-item-types/{type_id} endpoint."""
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_update_type_success(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test updating a type successfully."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_notebook_item_type)
        mock_db.update = AsyncMock()
        
        update_data = {
            "name": "Updated Type",
            "description": "Updated description",
            "default_initial_data": {"new_key": "new_value"},
            "default_refs": {},
            "allow_instance_override_refs": False
        }
        
        response = client.put("/api/notebook-item-types/type-123", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "type-123"
        assert data["name"] == "Updated Type"
        
        mock_db.update.assert_called_once()
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_update_type_not_found(self, mock_db, client, mock_user):
        """Test updating non-existent type."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=None)
        
        update_data = {
            "name": "Updated Type",
            "description": "Updated description"
        }
        
        response = client.put("/api/notebook-item-types/nonexistent", json=update_data)
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_update_type_database_error(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test database error during update."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_notebook_item_type)
        mock_db.update = AsyncMock(side_effect=Exception("Database error"))
        
        update_data = {
            "name": "Updated Type",
            "description": "Updated description"
        }
        
        response = client.put("/api/notebook-item-types/type-123", json=update_data)
        
        assert response.status_code == 500
        assert "Error updating notebook item type" in response.json()["detail"]


class TestDeleteNotebookItemType:
    """Tests for DELETE /notebook-item-types/{type_id} endpoint."""
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_delete_type_success(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test deleting a type successfully."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_notebook_item_type)
        mock_db.delete = AsyncMock()
        
        response = client.delete("/api/notebook-item-types/type-123")
        
        assert response.status_code == 204
        
        mock_db.delete.assert_called_once_with(
            "notebook_item_types",
            "type-123",
            is_canonical=True
        )
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_delete_type_not_found(self, mock_db, client, mock_user):
        """Test deleting non-existent type."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=None)
        
        response = client.delete("/api/notebook-item-types/nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.notebook_item_types_router.db')
    def test_delete_type_database_error(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test database error during deletion."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=mock_notebook_item_type)
        mock_db.delete = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.delete("/api/notebook-item-types/type-123")
        
        assert response.status_code == 500
        assert "Error deleting notebook item type" in response.json()["detail"]
