"""
Unit tests for file_ops_router.py

Tests cover:
- POST /file-ops/salvar - Save file content
- GET /file-ops/list_arquivos - List files and directories
- GET /file-ops/carregar_arquivo - Load file content
- POST /file-ops/mover_item - Move file or folder
- DELETE /file-ops/delete - Delete file or folder

Note: Endpoint names are in Portuguese to maintain backward compatibility
with the original cockpit/backend implementation.

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import os

from app.main import app


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestSalvarEndpoint:
    """Tests for POST /file-ops/salvar endpoint."""
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.file_utils.validate_filename_extension')
    @patch('app.file_utils.check_file_permissions')
    @patch('app.file_utils.write_file_atomically')
    @patch('app.config.BASE_DIR', Path('/test/base'))
    def test_salvar_success(self, mock_write, mock_perms, mock_validate_ext, 
                           mock_validate_path, client):
        """Test successful file save."""
        # Setup mocks
        mock_validate_ext.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/base/folder/file.txt", None)
        mock_perms.return_value = (True, None)
        mock_write.return_value = (True, None)
        
        response = client.post("/api/salvar", json={
            "folder": "folder",
            "filename": "file.txt",
            "content": "Test content"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "mensagem" in data
        assert "caminho" in data
        mock_write.assert_called_once()
    
    @patch('app.routers.file_ops_router.validate_filename_extension')
    def test_salvar_empty_filename(self, mock_validate_ext, client):
        """Test save with empty filename."""
        response = client.post("/api/salvar", json={
            "folder": "folder",
            "filename": "",
            "content": "Test content"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "required" in data["detalhes"].lower()
    
    @patch('app.routers.file_ops_router.validate_filename_extension')
    def test_salvar_invalid_filename(self, mock_validate_ext, client):
        """Test save with invalid filename."""
        mock_validate_ext.return_value = (False, "Invalid filename")
        
        response = client.post("/api/salvar", json={
            "folder": "folder",
            "filename": "../../../etc/passwd",
            "content": "Test content"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.validate_filename_extension')
    def test_salvar_invalid_path(self, mock_validate_ext, mock_validate_path, client):
        """Test save with invalid path."""
        mock_validate_ext.return_value = (True, None)
        mock_validate_path.return_value = (False, None, "Path traversal detected")
        
        response = client.post("/api/salvar", json={
            "folder": "../../../etc",
            "filename": "file.txt",
            "content": "Test content"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.validate_filename_extension')
    @patch('app.routers.file_ops_router.check_file_permissions')
    def test_salvar_no_write_permission(self, mock_perms, mock_validate_ext,
                                        mock_validate_path, client):
        """Test save without write permission."""
        mock_validate_ext.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/base/folder/file.txt", None)
        mock_perms.return_value = (False, "No write permission")
        
        response = client.post("/api/salvar", json={
            "folder": "folder",
            "filename": "file.txt",
            "content": "Test content"
        })
        
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.validate_filename_extension')
    @patch('app.routers.file_ops_router.check_file_permissions')
    @patch('app.routers.file_ops_router.write_file_atomically')
    def test_salvar_write_failure(self, mock_write, mock_perms, mock_validate_ext,
                                  mock_validate_path, client):
        """Test save with write failure."""
        mock_validate_ext.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/base/folder/file.txt", None)
        mock_perms.return_value = (True, None)
        mock_write.return_value = (False, "Disk full")
        
        response = client.post("/api/salvar", json={
            "folder": "folder",
            "filename": "file.txt",
            "content": "Test content"
        })
        
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"


class TestListarArquivosEndpoint:
    """Tests for GET /file-ops/list_arquivos endpoint."""
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.os.path.isdir')
    @patch('app.routers.file_ops_router.os.listdir')
    @patch('app.routers.file_ops_router.os.path.isfile')
    @patch('app.config.BASE_DIR', Path('/test/base'))
    def test_listar_arquivos_success(self, mock_isfile, mock_listdir, mock_isdir,
                                     mock_validate_path, client):
        """Test successful file listing."""
        mock_validate_path.return_value = (True, "/test/base/folder", None)
        mock_isdir.return_value = True
        mock_listdir.return_value = ["file1.txt", "file2.py", "subdir"]
        
        def is_file_side_effect(path):
            return not path.endswith("subdir")
        
        mock_isfile.side_effect = is_file_side_effect
        
        # Mock os.path.isdir for items check
        with patch('app.routers.file_ops_router.os.path.isdir') as mock_item_isdir:
            mock_item_isdir.side_effect = lambda p: p.endswith("subdir")
            
            response = client.get("/api/list_arquivos?folder=folder")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "arquivos" in data
        assert len(data["arquivos"]) == 3
        # Directories should have trailing slash
        assert "subdir/" in data["arquivos"]
    
    @patch('app.file_utils.validate_and_sanitize_path')
    def test_listar_arquivos_invalid_path(self, mock_validate_path, client):
        """Test listing with invalid path."""
        mock_validate_path.return_value = (False, None, "Invalid path")
        
        response = client.get("/api/list_arquivos?folder=../../../etc")
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.os.path.isdir')
    @patch('app.routers.file_ops_router.os.listdir')
    @patch('app.config.BASE_DIR', Path('/test/base'))
    def test_listar_arquivos_empty_directory(self, mock_listdir, mock_isdir,
                                             mock_validate_path, client):
        """Test listing empty directory."""
        mock_validate_path.return_value = (True, "/test/base/empty", None)
        mock_isdir.return_value = True
        mock_listdir.return_value = []
        
        response = client.get("/api/list_arquivos?folder=empty")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["arquivos"] == []


class TestCarregarArquivoEndpoint:
    """Tests for GET /file-ops/carregar_arquivo endpoint."""
    
    @patch('app.routers.file_ops_router.validate_filename_extension')
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.os.path.isfile')
    @patch('app.routers.file_ops_router.check_file_permissions')
    @patch('builtins.open', new_callable=mock_open, read_data="Test file content")
    @patch('app.config.BASE_DIR', Path('/test/base'))
    def test_carregar_arquivo_success(self, mock_file, mock_perms, mock_isfile,
                                      mock_validate_path, mock_validate_ext, client):
        """Test successful file loading."""
        mock_validate_ext.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/base/folder/file.txt", None)
        mock_isfile.return_value = True
        mock_perms.return_value = (True, None)
        
        response = client.get("/api/carregar_arquivo?folder=folder&filename=file.txt")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["content"] == "Test file content"
        assert "caminho" in data
    
    def test_carregar_arquivo_empty_filename(self, client):
        """Test loading with empty filename."""
        response = client.get("/api/carregar_arquivo?folder=folder&filename=")
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.routers.file_ops_router.validate_filename_extension')
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.os.path.isfile')
    def test_carregar_arquivo_not_found(self, mock_isfile, mock_validate_path,
                                       mock_validate_ext, client):
        """Test loading non-existent file."""
        mock_validate_ext.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/base/folder/missing.txt", None)
        mock_isfile.return_value = False
        
        response = client.get("/api/carregar_arquivo?folder=folder&filename=missing.txt")
        
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.routers.file_ops_router.validate_filename_extension')
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.os.path.isfile')
    @patch('app.routers.file_ops_router.check_file_permissions')
    def test_carregar_arquivo_no_read_permission(self, mock_perms, mock_isfile,
                                                 mock_validate_path, mock_validate_ext, client):
        """Test loading without read permission."""
        mock_validate_ext.return_value = (True, None)
        mock_validate_path.return_value = (True, "/test/base/folder/file.txt", None)
        mock_isfile.return_value = True
        mock_perms.return_value = (False, "No read permission")
        
        response = client.get("/api/carregar_arquivo?folder=folder&filename=file.txt")
        
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "error"


class TestMoverItemEndpoint:
    """Tests for POST /file-ops/mover_item endpoint."""
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.Path')
    @patch('app.routers.file_ops_router.shutil')
    @patch('app.config.BASE_DIR', Path('/test/base'))
    def test_mover_item_success(self, mock_shutil, mock_path_class,
                               mock_validate_path, client):
        """Test successful file move."""
        # Setup mocks
        mock_validate_path.side_effect = [
            (True, "/test/base/source/file.txt", None),  # source
            (True, "/test/base/dest/file.txt", None)     # destination
        ]
        
        # Mock Path objects
        mock_source_path = MagicMock()
        mock_source_path.exists.return_value = True
        
        mock_dest_path = MagicMock()
        mock_dest_path.exists.return_value = False
        mock_dest_path.parent.mkdir = MagicMock()
        
        mock_path_class.side_effect = [mock_source_path, mock_dest_path]
        
        response = client.post("/api/mover_item", json={
            "source": "source/file.txt",
            "destination": "dest/file.txt"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "origem" in data
        assert "destino" in data
        mock_shutil.move.assert_called_once()
    
    def test_mover_item_empty_source(self, client):
        """Test move with empty source."""
        response = client.post("/api/mover_item", json={
            "source": "",
            "destination": "dest/file.txt"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    def test_mover_item_empty_destination(self, client):
        """Test move with empty destination."""
        response = client.post("/api/mover_item", json={
            "source": "source/file.txt",
            "destination": ""
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.Path')
    def test_mover_item_source_not_exists(self, mock_path_class, mock_validate_path, client):
        """Test move with non-existent source."""
        mock_validate_path.side_effect = [
            (True, "/test/base/source/missing.txt", None),
            (True, "/test/base/dest/file.txt", None)
        ]
        
        mock_source_path = MagicMock()
        mock_source_path.exists.return_value = False
        mock_path_class.return_value = mock_source_path
        
        response = client.post("/api/mover_item", json={
            "source": "source/missing.txt",
            "destination": "dest/file.txt"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.routers.file_ops_router.Path')
    def test_mover_item_dest_exists(self, mock_path_class, mock_validate_path, client):
        """Test move with existing destination."""
        mock_validate_path.side_effect = [
            (True, "/test/base/source/file.txt", None),
            (True, "/test/base/dest/file.txt", None)
        ]
        
        mock_source_path = MagicMock()
        mock_source_path.exists.return_value = True
        
        mock_dest_path = MagicMock()
        mock_dest_path.exists.return_value = True
        
        mock_path_class.side_effect = [mock_source_path, mock_dest_path]
        
        response = client.post("/api/mover_item", json={
            "source": "source/file.txt",
            "destination": "dest/file.txt"
        })
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"


class TestDeletarEndpoint:
    """Tests for DELETE /file-ops/delete endpoint."""
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.file_utils.delete_file_or_directory')
    @patch('app.config.BASE_DIR', Path('/test/base'))
    def test_deletar_success(self, mock_delete, mock_validate_path, client):
        """Test successful deletion."""
        mock_validate_path.return_value = (True, "/test/base/folder/file.txt", None)
        mock_delete.return_value = (True, None)
        
        response = client.request(
            "DELETE",
            "/api/files/delete",
            json={"path": "folder/file.txt"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "caminho" in data
        mock_delete.assert_called_once()
    
    def test_deletar_empty_path(self, client):
        """Test deletion with empty path."""
        response = client.request(
            "DELETE",
            "/api/files/delete",
            json={"path": ""}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    def test_deletar_invalid_path(self, mock_validate_path, client):
        """Test deletion with invalid path."""
        mock_validate_path.return_value = (False, None, "Invalid path")
        
        response = client.request(
            "DELETE",
            "/api/files/delete",
            json={"path": "../../../etc/passwd"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    @patch('app.file_utils.validate_and_sanitize_path')
    @patch('app.file_utils.delete_file_or_directory')
    def test_deletar_failure(self, mock_delete, mock_validate_path, client):
        """Test deletion failure."""
        mock_validate_path.return_value = (True, "/test/base/folder/file.txt", None)
        mock_delete.return_value = (False, "Permission denied")
        
        response = client.request(
            "DELETE",
            "/api/files/delete",
            json={"path": "folder/file.txt"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data["status"] == "error"
