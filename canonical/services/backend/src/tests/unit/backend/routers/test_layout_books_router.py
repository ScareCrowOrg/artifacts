"""
Unit tests for layout_books_router.py

Tests cover:
- POST /layout-books - Create layout book
- GET /layout-books - List layout books with pagination
- GET /layout-books/{id} - Get specific layout book
- PUT /layout-books/{id} - Update layout book
- DELETE /layout-books/{id} - Delete layout book
- PUT /layout-books/{id}/apply - Validate and apply layout book

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.main import app
from app.models import User, Book, Cell, BookType, NotebookItemType
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
    user.roles = ["user"]
    return user


@pytest.fixture
def mock_layout_book_type():
    """Mock layout-book NotebookItemType."""
    nit = Mock(spec=NotebookItemType)
    nit.id = "layout-book"
    nit.name = "Layout Book"
    nit.description = "Save and restore workspace layouts"
    nit.default_initial_data = {
        "layout_version": "1.0.0",
        "cells": [],
        "grid_config": {"cols": 12, "rowHeight": 30, "margin": [10, 10]},
        "metadata": {
            "cell_count": 0,
            "persistent_count": 0,
            "ephemeral_count": 0,
            "last_applied": None,
            "created_from_layout": True
        }
    }
    nit.allow_instance_override_refs = True
    nit.can_render_dynamically = False
    return nit


@pytest.fixture
def mock_layout_book(mock_user, mock_layout_book_type):
    """Mock layout book."""
    book = Mock(spec=Book)
    book.id = "layout-book-123"
    book.assignee_id = mock_user.id
    book.notebook_item_type_id = mock_layout_book_type.id
    book.name = "Python Dev Workspace"
    book.description = "Workspace for Python development"
    book.type = BookType.VOLATILE
    book.source = None
    book.purpose = "Workspace layout template"
    book.created_at = datetime(2025, 12, 19, 10, 0, 0)
    book.updated_at = datetime(2025, 12, 19, 10, 0, 0)
    book.initial_data = {
        "layout_version": "1.0.0",
        "cells": [
            {
                "cellId": "cell-persistent-1",
                "category": "persistent",
                "type": "file-editor",
                "title": "main.py",
                "position": {"x": 0, "y": 0, "w": 6, "h": 10},
                "state": {"isMinimized": False, "isMaximized": False}
            },
            {
                "category": "ephemeral",
                "type": "terminal",
                "title": "Backend Terminal",
                "position": {"x": 6, "y": 0, "w": 6, "h": 10},
                "initialization_data": {
                    "shellType": "bash",
                    "workingDirectory": "/backend"
                },
                "state": {"isMinimized": False, "isMaximized": False}
            }
        ],
        "grid_config": {"cols": 12, "rowHeight": 30, "margin": [10, 10]},
        "metadata": {
            "cell_count": 2,
            "persistent_count": 1,
            "ephemeral_count": 1,
            "last_applied": None,
            "created_from_layout": True
        }
    }
    book.cells = []
    book.children = []
    book.is_canonical_system_book = False
    book.is_unclassified_master_template = False
    book.model_dump = Mock(return_value={
        "id": book.id,
        "assignee_id": book.assignee_id,
        "notebook_item_type_id": book.notebook_item_type_id,
        "name": book.name,
        "description": book.description,
        "type": "VOLATILE",
        "source": None,
        "purpose": book.purpose,
        "initial_data": book.initial_data,
        "refs": {},
        "cells": [],
        "children": [],
        "created_at": book.created_at.isoformat(),
        "updated_at": book.updated_at.isoformat()
    })
    return book


@pytest.fixture
def mock_persistent_cell(mock_user):
    """Mock persistent cell."""
    cell = Mock(spec=Cell)
    cell.id = "cell-persistent-1"
    cell.assignee_id = mock_user.id
    cell.notebook_item_type_id = "file-editor-type"
    cell.title = "main.py"
    cell.category = "persistent"
    return cell


@pytest.fixture(autouse=True)
def cleanup():
    """Reset overrides after each test."""
    yield
    app.dependency_overrides = {}


class TestCreateLayoutBook:
    """Tests for POST /layout-books"""
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_create_layout_book_with_persistent_cells(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test creating a layout book with persistent cells."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.insert = AsyncMock()
        
        request_data = {
            "name": "Python Dev Workspace",
            "description": "Workspace for Python development",
            "cells": [
                {
                    "cellId": "cell-persistent-1",
                    "category": "persistent",
                    "type": "file-editor",
                    "title": "main.py",
                    "position": {"x": 0, "y": 0, "w": 6, "h": 10},
                    "state": {"isMinimized": False, "isMaximized": False}
                }
            ],
            "grid_config": {"cols": 12, "rowHeight": 30, "margin": [10, 10]}
        }
        
        # Execute
        response = client.post("/api/layout-books", json=request_data)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Python Dev Workspace"
        assert data["notebook_item_type_id"] == "layout-book"
        assert data["initial_data"]["metadata"]["cell_count"] == 1
        assert data["initial_data"]["metadata"]["persistent_count"] == 1
        assert data["initial_data"]["metadata"]["ephemeral_count"] == 0
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_create_layout_book_with_ephemeral_cells(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type
    ):
        """Test creating a layout book with ephemeral cells."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.insert = AsyncMock()
        
        request_data = {
            "name": "Terminal Layout",
            "description": "Multiple terminals",
            "cells": [
                {
                    "category": "ephemeral",
                    "type": "terminal",
                    "title": "Terminal 1",
                    "position": {"x": 0, "y": 0, "w": 6, "h": 10},
                    "initialization_data": {"shellType": "bash"},
                    "state": {"isMinimized": False, "isMaximized": False}
                },
                {
                    "category": "ephemeral",
                    "type": "terminal",
                    "title": "Terminal 2",
                    "position": {"x": 6, "y": 0, "w": 6, "h": 10},
                    "initialization_data": {"shellType": "zsh"},
                    "state": {"isMinimized": False, "isMaximized": False}
                }
            ],
            "grid_config": {"cols": 12, "rowHeight": 30, "margin": [10, 10]}
        }
        
        # Execute
        response = client.post("/api/layout-books", json=request_data)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["initial_data"]["metadata"]["cell_count"] == 2
        assert data["initial_data"]["metadata"]["persistent_count"] == 0
        assert data["initial_data"]["metadata"]["ephemeral_count"] == 2
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_create_layout_book_with_mixed_cells(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type
    ):
        """Test creating a layout book with both persistent and ephemeral cells."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.insert = AsyncMock()
        
        request_data = {
            "name": "Mixed Layout",
            "description": "Mix of cells",
            "cells": [
                {
                    "cellId": "cell-persistent-1",
                    "category": "persistent",
                    "type": "file-editor",
                    "title": "main.py",
                    "position": {"x": 0, "y": 0, "w": 6, "h": 10},
                    "state": {"isMinimized": False, "isMaximized": False}
                },
                {
                    "category": "ephemeral",
                    "type": "terminal",
                    "title": "Terminal",
                    "position": {"x": 6, "y": 0, "w": 6, "h": 10},
                    "initialization_data": {"shellType": "bash"},
                    "state": {"isMinimized": False, "isMaximized": False}
                }
            ],
            "grid_config": {"cols": 12, "rowHeight": 30, "margin": [10, 10]}
        }
        
        # Execute
        response = client.post("/api/layout-books", json=request_data)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["initial_data"]["metadata"]["cell_count"] == 2
        assert data["initial_data"]["metadata"]["persistent_count"] == 1
        assert data["initial_data"]["metadata"]["ephemeral_count"] == 1
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_create_layout_book_empty_cells(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type
    ):
        """Test creating a layout book with no cells."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.insert = AsyncMock()
        
        request_data = {
            "name": "Empty Layout",
            "description": "No cells yet",
            "cells": [],
            "grid_config": {"cols": 12, "rowHeight": 30, "margin": [10, 10]}
        }
        
        # Execute
        response = client.post("/api/layout-books", json=request_data)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["initial_data"]["metadata"]["cell_count"] == 0


class TestListLayoutBooks:
    """Tests for GET /layout-books"""
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_list_layout_books_success(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test listing layout books."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.find_many = AsyncMock(return_value=[mock_layout_book])
        
        # Execute
        response = client.get("/api/layout-books")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Python Dev Workspace"
        assert data["items"][0]["cell_count"] == 2
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_list_layout_books_pagination(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type
    ):
        """Test pagination in list endpoint."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        
        # Create multiple mock books
        books = []
        for i in range(25):
            book = Mock(spec=Book)
            book.id = f"book-{i}"
            book.assignee_id = mock_user.id
            book.notebook_item_type_id = mock_layout_book_type.id
            book.name = f"Book {i}"
            book.description = f"Description {i}"
            book.created_at = datetime(2025, 12, 19, 10, i, 0)
            book.updated_at = datetime(2025, 12, 19, 10, i, 0)
            book.initial_data = {
                "metadata": {"cell_count": i, "persistent_count": 0, "ephemeral_count": i}
            }
            book.is_canonical_system_book = False
            books.append(book)
        
        mock_db.find_many = AsyncMock(return_value=books)
        
        # Execute - first page
        response = client.get("/api/layout-books?skip=0&limit=10")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["skip"] == 0
        assert data["limit"] == 10
        
        # Execute - second page
        response = client.get("/api/layout-books?skip=10&limit=10")
        data = response.json()
        assert len(data["items"]) == 10
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_list_layout_books_filter_by_name(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test filtering by name."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        
        book2 = Mock(spec=Book)
        book2.id = "book-2"
        book2.assignee_id = mock_user.id
        book2.notebook_item_type_id = mock_layout_book_type.id
        book2.name = "Frontend Layout"
        book2.description = "Frontend workspace"
        book2.created_at = datetime(2025, 12, 19, 11, 0, 0)
        book2.updated_at = datetime(2025, 12, 19, 11, 0, 0)
        book2.initial_data = {"metadata": {"cell_count": 1, "persistent_count": 1, "ephemeral_count": 0}}
        book2.is_canonical_system_book = False
        
        mock_db.find_many = AsyncMock(return_value=[mock_layout_book, book2])
        
        # Execute
        response = client.get("/api/layout-books?name=python")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Python Dev Workspace"


class TestGetLayoutBook:
    """Tests for GET /layout-books/{id}"""
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_get_layout_book_success(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test getting a layout book by ID."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        
        # Execute
        response = client.get(f"/api/layout-books/{mock_layout_book.id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_layout_book.id
        assert data["name"] == "Python Dev Workspace"
        assert len(data["initial_data"]["cells"]) == 2
    
    @patch('app.routers.layout_books_router.db')
    def test_get_layout_book_not_found(self, mock_db, client, mock_user):
        """Test getting a non-existent layout book."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_db.find_one = AsyncMock(return_value=None)
        
        # Execute
        response = client.get("/api/layout-books/nonexistent-id")
        
        # Assert
        assert response.status_code == 404
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    @patch('app.routers.layout_books_router.get_user_permissions')
    def test_get_layout_book_forbidden(
        self, mock_get_perms, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test accessing another user's layout book."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_get_perms.return_value = []
        
        # Make the book belong to a different user
        mock_layout_book.assignee_id = "other-user-123"
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        
        # Execute
        response = client.get(f"/api/layout-books/{mock_layout_book.id}")
        
        # Assert
        assert response.status_code == 403


class TestUpdateLayoutBook:
    """Tests for PUT /layout-books/{id}"""
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_update_layout_book_name_and_description(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test updating name and description."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        mock_db.update = AsyncMock(return_value=True)
        
        # Updated book
        updated_book = Mock(spec=Book)
        updated_book.__dict__.update(mock_layout_book.__dict__)
        updated_book.name = "Updated Name"
        updated_book.description = "Updated Description"
        mock_db.find_one = AsyncMock(side_effect=[mock_layout_book, updated_book])
        
        request_data = {
            "name": "Updated Name",
            "description": "Updated Description"
        }
        
        # Execute
        response = client.put(f"/api/layout-books/{mock_layout_book.id}", json=request_data)
        
        # Assert
        assert response.status_code == 200
        assert mock_db.update.called
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_update_layout_book_cells(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test updating cells configuration."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        mock_db.update = AsyncMock(return_value=True)
        
        request_data = {
            "cells": [
                {
                    "cellId": "cell-1",
                    "category": "persistent",
                    "type": "file-editor",
                    "title": "New Cell",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 10},
                    "state": {"isMinimized": False, "isMaximized": False}
                }
            ]
        }
        
        # Execute
        response = client.put(f"/api/layout-books/{mock_layout_book.id}", json=request_data)
        
        # Assert
        assert response.status_code == 200
        # Verify update was called with initial_data containing new cells
        call_args = mock_db.update.call_args
        assert "initial_data" in call_args[0][2]  # Third argument is updates dict
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    @patch('app.routers.layout_books_router.check_resource_ownership')
    def test_update_layout_book_no_fields(self, mock_check_ownership, mock_get_type, mock_db, client, mock_user, mock_layout_book, mock_layout_book_type):
        """Test update with no fields raises error."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        mock_get_type.return_value = mock_layout_book_type
        mock_check_ownership.return_value = AsyncMock()
        
        # Execute
        response = client.put(f"/api/layout-books/{mock_layout_book.id}", json={})
        
        # Assert
        assert response.status_code == 400


class TestDeleteLayoutBook:
    """Tests for DELETE /layout-books/{id}"""
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_delete_layout_book_success(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test deleting a layout book."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        mock_db.delete = AsyncMock(return_value=True)
        
        # Execute
        response = client.delete(f"/api/layout-books/{mock_layout_book.id}")
        
        # Assert
        assert response.status_code == 204
        assert mock_db.delete.called
    
    @patch('app.routers.layout_books_router.db')
    def test_delete_layout_book_not_found(self, mock_db, client, mock_user):
        """Test deleting a non-existent layout book."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_db.find_one = AsyncMock(return_value=None)
        
        # Execute
        response = client.delete("/api/layout-books/nonexistent-id")
        
        # Assert
        assert response.status_code == 404


class TestApplyLayoutBook:
    """Tests for PUT /layout-books/{id}/apply"""
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_apply_layout_book_all_cells_found(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, 
        mock_layout_book, mock_persistent_cell
    ):
        """Test applying layout book when all persistent cells exist."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        mock_db.find_many = AsyncMock(return_value=[mock_persistent_cell])
        mock_db.update = AsyncMock(return_value=True)
        
        # Execute
        response = client.put(f"/api/layout-books/{mock_layout_book.id}/apply")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cells_found"] == 1
        assert data["cells_missing"] == 0
        assert len(data["validation_errors"]) == 0
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_apply_layout_book_cells_missing(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type, mock_layout_book
    ):
        """Test applying layout book when some persistent cells are missing."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        mock_db.find_one = AsyncMock(return_value=mock_layout_book)
        mock_db.find_many = AsyncMock(return_value=[])  # No cells found
        mock_db.update = AsyncMock(return_value=True)
        
        # Execute
        response = client.put(f"/api/layout-books/{mock_layout_book.id}/apply")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["cells_found"] == 0
        assert data["cells_missing"] == 1
        assert len(data["validation_errors"]) > 0
    
    @patch('app.routers.layout_books_router.db')
    @patch('app.routers.layout_books_router.get_layout_book_type')
    def test_apply_layout_book_only_ephemeral_cells(
        self, mock_get_type, mock_db, client, mock_user, mock_layout_book_type
    ):
        """Test applying layout book with only ephemeral cells (no validation needed)."""
        # Setup
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        mock_get_type.return_value = mock_layout_book_type
        
        # Create a book with only ephemeral cells
        book = Mock(spec=Book)
        book.id = "book-ephemeral-only"
        book.assignee_id = mock_user.id
        book.notebook_item_type_id = mock_layout_book_type.id
        book.name = "Ephemeral Only"
        book.initial_data = {
            "cells": [
                {
                    "category": "ephemeral",
                    "type": "terminal",
                    "title": "Terminal",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 10},
                    "initialization_data": {"shellType": "bash"},
                    "state": {"isMinimized": False, "isMaximized": False}
                }
            ],
            "metadata": {"cell_count": 1, "persistent_count": 0, "ephemeral_count": 1}
        }
        
        mock_db.find_one = AsyncMock(return_value=book)
        mock_db.find_many = AsyncMock(return_value=[])
        mock_db.update = AsyncMock(return_value=True)
        
        # Execute
        response = client.put(f"/api/layout-books/{book.id}/apply")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cells_found"] == 0
        assert data["cells_missing"] == 0
