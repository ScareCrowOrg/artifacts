"""
Unit tests for pipeline_items_router.py

Tests cover:
- GET /pipeline-items - List pipeline items from execution records
- GET /pipeline-items/{pipeline_item_id} - Get specific pipeline item

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.main import app
from app.models import User
from app.models.content import Cell, Book
from app.models.execution_models import ExecutionRecord
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
def mock_execution_record():
    """Mock execution record fragment."""
    return {
        "type": "execution_record",
        "pipeline_item_id": "pipeline-123",
        "assignee_id": "test-user-123",
        "status": "completed",
        "initial_data_snapshot": {"key": "value"},
        "fragments": [],
        "error": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }


@pytest.fixture
def mock_celula(mock_execution_record):
    """Mock cell with execution record."""
    cell = Mock(spec=Cell)
    cell.id = "cell-123"
    cell.assignee_id = "test-user-123"
    cell.cellTypeId = "tipo-123"
    cell.notebook_item_type_id = "tipo-123"
    cell.fragments = [mock_execution_record, "some string fragment"]
    return cell


@pytest.fixture
def mock_livro(mock_execution_record):
    """Mock book with execution record."""
    book = Mock(spec=Book)
    book.id = "book-123"
    book.assignee_id = "test-user-123"
    book.notebook_item_type_id = "tipo-123"
    book.fragments = [mock_execution_record]
    return book


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestListPipelineItems:
    """Tests for GET /pipeline-items endpoint."""
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_from_celulas(self, mock_db, client, mock_user, mock_celula):
        """Test listing pipeline items from cells."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=[
            [mock_celula],  # cells
            []  # books
        ])
        
        response = client.get("/api/pipeline-items")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["notebook_item_id"] == "cell-123"
        assert data[0]["status"] == "completed"
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_from_livros(self, mock_db, client, mock_user, mock_livro):
        """Test listing pipeline items from books."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=[
            [],  # cells
            [mock_livro]  # books
        ])
        
        response = client.get("/api/pipeline-items")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["notebook_item_id"] == "book-123"
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_with_notebook_item_id_filter_celula(self, mock_db, client, mock_user, mock_celula):
        """Test listing pipeline items filtered by notebook_item_id (cell)."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(side_effect=[mock_celula, None])
        
        response = client.get("/api/pipeline-items?notebook_item_id=cell-123")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["notebook_item_id"] == "cell-123"
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_with_notebook_item_id_filter_livro(self, mock_db, client, mock_user, mock_livro):
        """Test listing pipeline items filtered by notebook_item_id (book)."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(side_effect=[None, mock_livro])
        
        response = client.get("/api/pipeline-items?notebook_item_id=book-123")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["notebook_item_id"] == "book-123"
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_notebook_item_not_found(self, mock_db, client, mock_user):
        """Test filtering by non-existent notebook_item_id."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(side_effect=[None, None])
        
        response = client.get("/api/pipeline-items?notebook_item_id=nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_with_status_filter(self, mock_db, client, mock_user, mock_celula):
        """Test listing pipeline items filtered by status."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=[
            [mock_celula],  # cells
            []  # books
        ])
        
        response = client.get("/api/pipeline-items?status=completed")
        
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["status"] == "completed"
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_with_pagination(self, mock_db, client, mock_user):
        """Test pagination parameters."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Create multiple cells with execution records
        cells = []
        for i in range(10):
            cell = Mock(spec=Cell)
            cell.id = f"cell-{i}"
            cell.assignee_id = "test-user-123"
            cell.notebook_item_type_id = "tipo-123"
            cell.fragments = [{
                "type": "execution_record",
                "pipeline_item_id": f"pipeline-{i}",
                "assignee_id": "test-user-123",
                "status": "completed",
                "initial_data_snapshot": {},
                "fragments": [],
                "error": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }]
            cells.append(cell)
        
        mock_db.find_many = AsyncMock(side_effect=[cells, []])
        
        response = client.get("/api/pipeline-items?skip=2&limit=3")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_empty_result(self, mock_db, client, mock_user):
        """Test listing when no pipeline items exist."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Create cells with no execution records
        cell = Mock(spec=Cell)
        cell.id = "cell-123"
        cell.assignee_id = "test-user-123"
        cell.fragments = ["string fragment"]  # No execution records
        
        mock_db.find_many = AsyncMock(side_effect=[[cell], []])
        
        response = client.get("/api/pipeline-items")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_invalid_execution_record(self, mock_db, client, mock_user):
        """Test handling of invalid execution records in fragments."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        cell = Mock(spec=Cell)
        cell.id = "cell-123"
        cell.assignee_id = "test-user-123"
        cell.fragments = [{
            "type": "execution_record",
            "pipeline_item_id": "pipeline-123",
            # Missing required fields
        }]
        
        mock_db.find_many = AsyncMock(side_effect=[[cell], []])
        
        response = client.get("/api/pipeline-items")
        
        # Should skip invalid records and return empty list
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('app.routers.pipeline_items_router.db')
    def test_list_pipeline_items_database_error(self, mock_db, client, mock_user):
        """Test database error handling.
        
        Note: The router catches errors per collection, so this returns
        empty result (200) unless the outer exception is triggered.
        """
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Both collections fail but are caught internally
        mock_db.find_many = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.get("/api/pipeline-items")
        
        # Router catches exceptions per collection and returns empty list
        assert response.status_code == 200
        assert response.json() == []


class TestGetPipelineItem:
    """Tests for GET /pipeline-items/{pipeline_item_id} endpoint."""
    
    @patch('app.routers.pipeline_items_router.db')
    def test_get_pipeline_item_from_celula(self, mock_db, client, mock_user, mock_celula):
        """Test getting a pipeline item from cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=[
            [mock_celula],  # cells
            []  # books (won't be reached)
        ])
        
        response = client.get("/api/pipeline-items/pipeline-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pipeline-123"
        assert data["notebook_item_id"] == "cell-123"
        assert data["status"] == "completed"
    
    @patch('app.routers.pipeline_items_router.db')
    def test_get_pipeline_item_from_livro(self, mock_db, client, mock_user, mock_livro):
        """Test getting a pipeline item from book."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        celula_without_match = Mock(spec=Cell)
        celula_without_match.id = "cell-other"
        celula_without_match.fragments = []
        
        mock_db.find_many = AsyncMock(side_effect=[
            [celula_without_match],  # cells (no match)
            [mock_livro]  # books
        ])
        
        response = client.get("/api/pipeline-items/pipeline-123")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pipeline-123"
        assert data["notebook_item_id"] == "book-123"
    
    @patch('app.routers.pipeline_items_router.db')
    def test_get_pipeline_item_not_found(self, mock_db, client, mock_user):
        """Test getting non-existent pipeline item."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        cell = Mock(spec=Cell)
        cell.id = "cell-123"
        cell.fragments = []
        
        mock_db.find_many = AsyncMock(side_effect=[[cell], []])
        
        response = client.get("/api/pipeline-items/nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.pipeline_items_router.db')
    def test_get_pipeline_item_database_error(self, mock_db, client, mock_user):
        """Test database error handling.
        
        Note: The router catches errors per collection search, so this returns
        404 (not found) unless the outer exception is triggered.
        """
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Both collections fail but are caught internally
        mock_db.find_many = AsyncMock(side_effect=Exception("Database error"))
        
        response = client.get("/api/pipeline-items/pipeline-123")
        
        # Router catches exceptions per collection and returns 404
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
