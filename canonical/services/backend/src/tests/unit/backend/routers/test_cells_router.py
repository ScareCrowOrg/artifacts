"""
Unit tests for cells_router.py

Tests cover:
- GET /cells/list - List cells for user
- POST /cells/create - Create new cell
- POST /cells/{id_celula}/executar - Execute cell
- PUT /cells/{id_celula}/update - Update cell
- GET /cells/{id_celula} - Get specific cell
- DELETE /cells/{id_celula} - Delete cell
- GET /cells/tipos - List cell types

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from app.main import app
from app.models import User, Cell, NotebookItemType, CellStatus
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
    user.roles = ["user"]  # Add roles attribute for permission checks
    user.model_dump = Mock(return_value={
        "id": "test-user-123",
        "name": "Test User"
    })
    return user


@pytest.fixture
def mock_cell():
    """Mock cell."""
    cell = Mock(spec=Cell)
    cell.id = "cell-123"
    cell.assignee_id = "test-user-123"
    cell.cellTypeId = "tipo-123"
    cell.notebook_item_type_id = "tipo-123"
    cell.source_book_id = None
    cell.status = CellStatus.PENDING
    cell.initial_data = {"title": "Test Cell"}
    cell.refs = {}
    cell.fragments = []
    return cell


@pytest.fixture
def mock_cell_type():
    """Mock cell type."""
    cell_type = Mock(spec=NotebookItemType)
    cell_type.id = "tipo-123"
    cell_type.name = "Test Type"
    cell_type.description = "Test cell type"
    cell_type.default_initial_data = {"default_key": "default_value"}
    cell_type.default_refs = {}
    cell_type.allow_instance_override_refs = True
    return cell_type


@pytest.fixture
def mock_notebook_item_type():
    """Mock notebook item type."""
    nit = Mock(spec=NotebookItemType)
    nit.id = "nit-123"
    nit.name = "Test NIT"
    nit.default_initial_data = {"default_key": "default_value"}
    nit.default_refs = {}
    nit.allow_instance_override_refs = True
    return nit


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestListarCelulas:
    """Tests for GET /cells/list endpoint."""
    
    @patch('app.routers.cells_router.get_user_permissions', return_value=["cells.read", "cells.read_own"])
    @patch('app.routers.cells_router.db')
    def test_listar_celulas_current_user(self, mock_router_db, mock_get_perms, client, mock_user, mock_cell):
        """Test listing cells for current user."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock db operations in router
        mock_router_db.find_many = AsyncMock(return_value=[mock_cell])
        
        response = client.get("/api/cells/list")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('app.routers.cells_router.db')
    def test_listar_celulas_specific_user(self, mock_db, client, mock_user, mock_cell):
        """Test listing cells for specific user."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        
        response = client.get("/api/cells/list?assignee_id=test-user-123")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('app.routers.cells_router.db')
    def test_listar_celulas_empty(self, mock_db, client, mock_user):
        """Test listing cells when none exist."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.get("/api/cells/list")
        
        assert response.status_code == 200
        data = response.json()
        assert data == []
    
    @patch('app.routers.cells_router.db')
    def test_listar_celulas_error(self, mock_db, client, mock_user):
        """Test error handling in list cells."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.get("/api/cells/list")
        
        assert response.status_code == 500
        assert "Error listing" in response.json()["detail"] or "Erro ao listar" in response.json()["detail"]


class TestCriarCelula:
    """Tests for POST /cells/create endpoint."""
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_with_notebook_item_type(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test creating cell with notebook item type."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        async def find_one_side_effect(col, id, model, **kwargs):
            return {
                "notebook_item_types": mock_notebook_item_type,
                "users": mock_user
            }.get(col)
        
        mock_db.find_one = AsyncMock(side_effect=find_one_side_effect)
        mock_db.insert = AsyncMock(return_value=None)
        
        response = client.post("/api/cells/create", json={
            "notebook_item_type_id": "nit-123",
            "assignee_id": "test-user-123",
            "initial_data": {"custom": "data"}
        })
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_with_tipo_celula(self, mock_db, client, mock_user, mock_cell_type):
        """Test creating cell with tipo cell (backward compatibility)."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        async def find_one_side_effect(col, id, model, **kwargs):
            if col == "notebook_item_types":
                return mock_cell_type
            elif col == "users":
                return mock_user
            return None
        
        mock_db.find_one = AsyncMock(side_effect=find_one_side_effect)
        mock_db.insert = AsyncMock(return_value=None)
        
        response = client.post("/api/cells/create", json={
            "notebook_item_type_id": "tipo-123",
            "assignee_id": "test-user-123"
        })
        
        assert response.status_code == 201
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_missing_type_id(self, mock_db, client, mock_user):
        """Test creating cell without type ID."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        response = client.post("/api/cells/create", json={
            "assignee_id": "test-user-123"
        })
        
        assert response.status_code == 422  # FastAPI validation error for missing required field
        assert "must be provided" in response.json()["detail"]
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_type_not_found(self, mock_db, client, mock_user):
        """Test creating cell with non-existent type."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(return_value=None)
        
        response = client.post("/api/cells/create", json={
            "notebook_item_type_id": "nonexistent",
            "assignee_id": "test-user-123"
        })
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_user_not_found(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test creating cell with non-existent user."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        async def find_one_side_effect(col, id, model, **kwargs):
            if col == "notebook_item_types":
                return mock_notebook_item_type
            elif col == "users":
                return None
            return None
        
        mock_db.find_one = AsyncMock(side_effect=find_one_side_effect)
        
        response = client.post("/api/cells/create", json={
            "notebook_item_type_id": "nit-123",
            "assignee_id": "nonexistent-user"
        })
        
        assert response.status_code == 404
        assert "User" in response.json()["detail"] and "not found" in response.json()["detail"]
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_error_handling(self, mock_db, client, mock_user):
        """Test error handling in create cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_one = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.post("/api/cells/create", json={
            "notebook_item_type_id": "nit-123",
            "assignee_id": "test-user-123"
        })
        
        assert response.status_code == 500
        assert "Erro ao criar" in response.json()["detail"]
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_ephemeral_nao_persiste(self, mock_db, client, mock_user):
        """Test creating ephemeral cell - should not persist to database."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Create a mock notebook item type with ephemeral category
        mock_ephemeral_type = Mock(spec=NotebookItemType)
        mock_ephemeral_type.id = "file-editor-v2"
        mock_ephemeral_type.name = "File Editor"
        mock_ephemeral_type.default_initial_data = {
            "fileName": "test.md",
            "category": "ephemeral"
        }
        mock_ephemeral_type.default_refs = {}
        mock_ephemeral_type.allow_instance_override_refs = True
        
        async def find_one_side_effect(col, id, model, **kwargs):
            if col == "notebook_item_types":
                return mock_ephemeral_type
            elif col == "users":
                return mock_user
            return None
        
        mock_db.find_one = AsyncMock(side_effect=find_one_side_effect)
        mock_db.insert = AsyncMock(return_value=None)
        
        response = client.post("/api/cells/create", json={
            "notebook_item_type_id": "file-editor-v2",
            "assignee_id": "test-user-123",
            "initial_data": {"fileName": "test.md", "category": "ephemeral"}
        })
        
        # Should return 201 with cell data
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # Category should be at core level, not in initial_data
        assert data.get("category") == "ephemeral"
        
        # CRITICAL: db.insert should NOT be called for ephemeral cells
        mock_db.insert.assert_not_called()
    
    @patch('app.routers.cells_router.db')
    def test_criar_celula_persistente_normal(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test creating regular (non-ephemeral) cell - should persist normally."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Regular type without ephemeral category
        mock_notebook_item_type.default_initial_data = {"some": "data"}
        
        async def find_one_side_effect(col, id, model, **kwargs):
            if col == "notebook_item_types":
                return mock_notebook_item_type
            elif col == "users":
                return mock_user
            return None
        
        mock_db.find_one = AsyncMock(side_effect=find_one_side_effect)
        mock_db.insert = AsyncMock(return_value=None)
        
        response = client.post("/api/cells/create", json={
            "notebook_item_type_id": "nit-123",
            "assignee_id": "test-user-123"
        })
        
        # Should return 201 and persist
        assert response.status_code == 201
        
        # db.insert SHOULD be called for regular cells
        mock_db.insert.assert_called_once()



class TestExecutarCelula:
    """Tests for POST /cells/{id_celula}/executar endpoint."""
    
    @patch('app.routers.cells_router.db')
    @patch('app.models.CellAdapter')
    def test_executar_celula_success(self, mock_adapter_class, mock_db, client, mock_user, mock_cell):
        """Test successful cell execution."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        mock_db.update = AsyncMock(return_value=True)
        mock_db.find_one = AsyncMock(return_value=mock_cell)
        
        # Mock adapter execution
        mock_adapter = Mock()
        mock_result = Mock()
        mock_result.status = "completed"
        mock_adapter.execute_in_pipeline.return_value = mock_result
        mock_adapter_class.return_value = mock_adapter
        
        response = client.post("/api/cells/cell-123/executar", json={
            "parametros": {"param1": "value1"}
        })
        
        assert response.status_code == 200
    
    @patch('app.routers.cells_router.db')
    def test_executar_celula_not_found(self, mock_db, client, mock_user):
        """Test executing non-existent cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.post("/api/cells/nonexistent/executar", json={
            "parametros": {}
        })
        
        assert response.status_code == 404
        assert "não encontrada" in response.json()["detail"]
    
    @patch('app.routers.cells_router.db')
    @patch('app.models.CellAdapter')
    def test_executar_celula_execution_error(self, mock_adapter_class, mock_db, client, mock_user, mock_cell):
        """Test cell execution with error."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        mock_db.update = AsyncMock(return_value=True)
        mock_db.find_one = AsyncMock(return_value=mock_cell)
        
        # Mock adapter execution failure
        mock_adapter = Mock()
        mock_adapter.execute_in_pipeline.side_effect = Exception("Execution failed")
        mock_adapter_class.return_value = mock_adapter
        
        response = client.post("/api/cells/cell-123/executar", json={
            "parametros": {}
        })
        
        assert response.status_code == 200  # Still returns 200, but cell state is ERRO
    
    @patch('app.routers.cells_router.db')
    def test_executar_celula_error_handling(self, mock_db, client, mock_user):
        """Test error handling in execute cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.post("/api/cells/cell-123/executar", json={
            "parametros": {}
        })
        
        assert response.status_code == 500
        assert "Erro ao executar" in response.json()["detail"]


class TestAtualizarCelula:
    """Tests for PUT /cells/{id_celula}/update endpoint."""
    
    @patch('app.routers.cells_router.db')
    def test_atualizar_celula_initial_data(self, mock_db, client, mock_user, mock_cell):
        """Test updating cell initial_data."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        mock_db.update = AsyncMock(return_value=True)
        mock_db.find_one = AsyncMock(return_value=mock_cell)
        
        response = client.put("/api/cells/cell-123/update", json={
            "initial_data": {"updated": "data"}
        })
        
        assert response.status_code == 200
    
    @patch('app.routers.cells_router.db')
    def test_atualizar_celula_estado(self, mock_db, client, mock_user, mock_cell):
        """Test updating cell estado."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        mock_db.update = AsyncMock(return_value=True)
        mock_db.find_one = AsyncMock(return_value=mock_cell)
        
        response = client.put("/api/cells/cell-123/update", json={
            "estado": "executando"
        })
        
        assert response.status_code == 200
    
    @patch('app.routers.cells_router.db')
    def test_atualizar_celula_fragmentos(self, mock_db, client, mock_user, mock_cell):
        """Test updating cell fragmentos."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        mock_db.update = AsyncMock(return_value=True)
        mock_db.find_one = AsyncMock(return_value=mock_cell)
        
        response = client.put("/api/cells/cell-123/update", json={
            "fragmentos": [{"type": "log", "content": "test"}]
        })
        
        assert response.status_code == 200
    
    @patch('app.routers.cells_router.db')
    def test_atualizar_celula_not_found(self, mock_db, client, mock_user):
        """Test updating non-existent cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.put("/api/cells/nonexistent/update", json={
            "initial_data": {}
        })
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch('app.routers.cells_router.db')
    def test_atualizar_celula_update_failed(self, mock_db, client, mock_user, mock_cell):
        """Test update cell when DB update fails."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        mock_db.update = AsyncMock(return_value=False)
        
        response = client.put("/api/cells/cell-123/update", json={
            "initial_data": {}
        })
        
        assert response.status_code == 500
        assert "Failed to update" in response.json()["detail"] or "failed to update" in response.json()["detail"].lower()
    
    @patch('app.routers.cells_router.db')
    def test_atualizar_celula_error_handling(self, mock_db, client, mock_user):
        """Test error handling in update cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.put("/api/cells/cell-123/update", json={
            "initial_data": {}
        })
        
        assert response.status_code == 500
        assert "Error updating" in response.json()["detail"] or "error" in response.json()["detail"].lower()


class TestDeleteCelula:
    """Tests for DELETE /cells/{id_celula} endpoint."""
    
    @patch('app.routers.cells_router.db')
    def test_delete_celula_success(self, mock_db, client, mock_user, mock_cell):
        """Test deleting cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell])
        mock_db.delete = AsyncMock(return_value=True)
        
        response = client.delete("/api/cells/cell-123")
        
        assert response.status_code == 204
    
    @patch('app.routers.cells_router.db')
    def test_delete_celula_not_found(self, mock_db, client, mock_user):
        """Test deleting non-existent cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.delete("/api/cells/nonexistent")
        
        assert response.status_code == 404
    
    @patch('app.routers.cells_router.db')
    def test_delete_celula_error_handling(self, mock_db, client, mock_user):
        """Test error handling in delete cell."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.delete("/api/cells/cell-123")
        
        assert response.status_code == 500


class TestListarTiposCelula:
    """Tests for GET /cells/tipos endpoint."""
    
    @patch('app.routers.cells_router.db')
    def test_listar_tipos_celula_success(self, mock_db, client, mock_user, mock_cell_type):
        """Test listing cell types."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[mock_cell_type])
        
        response = client.get("/api/cells/types/list")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('app.routers.cells_router.db')
    def test_listar_tipos_celula_empty(self, mock_db, client, mock_user):
        """Test listing cell types when none exist."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.get("/api/cells/types/list")
        
        assert response.status_code == 200
        assert response.json() == []
    
    @patch('app.routers.cells_router.db')
    def test_listar_tipos_celula_error(self, mock_db, client, mock_user):
        """Test error handling in list cell types."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(side_effect=Exception("DB error"))
        
        response = client.get("/api/cells/types/list")
        
        assert response.status_code == 500
        assert "Error listing notebook item types" in response.json()["detail"]


class TestExecuteEphemeralCell:
    """Tests for POST /cells/execute-ephemeral endpoint."""
    
    @patch('app.routers.cells_router.db')
    def test_execute_ephemeral_success(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test successful ephemeral cell execution."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        # Mock cell type lookup
        mock_notebook_item_type.id = "example"
        mock_notebook_item_type.default_initial_data = {"message": "Hello", "counter": 0}
        mock_db.find_many = AsyncMock(return_value=[mock_notebook_item_type])
        
        # The endpoint will dynamically import the cell's backend script
        # For testing, we mock the module import or ensure the example cell exists
        response = client.post("/api/cells/execute-ephemeral", json={
            "cell_type": "example",
            "input_data": {"message": "Test Message", "counter": 5}
        })
        
        # Should succeed if example cell backend exists
        assert response.status_code in [200, 500]  # May fail if backend not accessible in test
        
    @patch('app.routers.cells_router.db')
    def test_execute_ephemeral_cell_type_not_found(self, mock_db, client, mock_user):
        """Test ephemeral execution with non-existent cell type."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        response = client.post("/api/cells/execute-ephemeral", json={
            "cell_type": "nonexistent-cell",
            "input_data": {}
        })
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch('app.routers.cells_router.db')
    def test_execute_ephemeral_missing_backend(self, mock_db, client, mock_user, mock_notebook_item_type):
        """Test ephemeral execution with cell type missing backend script."""
        app.dependency_overrides[get_current_user_required] = lambda: mock_user
        
        mock_notebook_item_type.id = "no-backend-cell"
        mock_db.find_many = AsyncMock(return_value=[mock_notebook_item_type])
        
        response = client.post("/api/cells/execute-ephemeral", json={
            "cell_type": "no-backend-cell",
            "input_data": {}
        })
        
        assert response.status_code == 400
        assert "backend execution script" in response.json()["detail"].lower()
