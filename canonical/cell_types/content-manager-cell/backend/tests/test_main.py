"""
Unit tests for content-manager-cell backend.

Tests all three actions (list, load, persist) with various scenarios.
"""

import pytest
import json
import base64
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys

# Add cell scripts to path
cell_scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(cell_scripts_path))

from main import execute_cell, handle_list, handle_load, handle_persist
from storage import LocalStorage, CloudflareR2Storage, StorageBackend
from utils import decode_base64_binary, encode_binary_to_base64, extract_mime_type_from_filename


class TestUtils:
    """Tests for utility functions."""
    
    def test_decode_base64_binary_with_data_uri(self):
        """Test decoding Base64 data URI."""
        test_data = b"Hello, World!"
        encoded = base64.b64encode(test_data).decode('utf-8')
        data_uri = f"data:text/plain;base64,{encoded}"
        
        binary, mime_type = decode_base64_binary(data_uri)
        
        assert binary == test_data
        assert mime_type == "text/plain"
    
    def test_decode_base64_binary_plain_string(self):
        """Test decoding plain Base64 string."""
        test_data = b"Hello, World!"
        encoded = base64.b64encode(test_data).decode('utf-8')
        
        binary, mime_type = decode_base64_binary(encoded)
        
        assert binary == test_data
        assert mime_type == "application/octet-stream"
    
    def test_decode_base64_binary_invalid(self):
        """Test decoding invalid Base64 data."""
        with pytest.raises(ValueError):
            decode_base64_binary("not-valid-base64!!!")
    
    def test_encode_binary_to_base64(self):
        """Test encoding binary to Base64 data URI."""
        test_data = b"Hello, World!"
        mime_type = "text/plain"
        
        result = encode_binary_to_base64(test_data, mime_type)
        
        assert result.startswith("data:text/plain;base64,")
        decoded = base64.b64decode(result.split(",")[1])
        assert decoded == test_data
    
    def test_extract_mime_type_from_filename(self):
        """Test MIME type extraction from filename."""
        assert extract_mime_type_from_filename("test.png") == "image/png"
        assert extract_mime_type_from_filename("test.jpg") == "image/jpeg"
        assert extract_mime_type_from_filename("test.glb") == "model/gltf-binary"
        assert extract_mime_type_from_filename("test.svg") == "image/svg+xml"
        assert extract_mime_type_from_filename("test.unknown") == "application/octet-stream"


class TestLocalStorage:
    """Tests for LocalStorage backend."""
    
    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create temporary local storage."""
        return LocalStorage(str(tmp_path / "storage"))
    
    def test_upload_and_download(self, temp_storage):
        """Test uploading and downloading a file."""
        content_id = "test-content-123"
        filename = "test.txt"
        binary = b"Hello, World!"
        mime_type = "text/plain"
        
        # Upload
        data_ref = temp_storage.upload(content_id, binary, filename, mime_type)
        
        assert data_ref.startswith("file://")
        
        # Download
        downloaded = temp_storage.download(content_id, filename)
        
        assert downloaded == binary
    
    def test_download_nonexistent(self, temp_storage):
        """Test downloading non-existent file."""
        result = temp_storage.download("nonexistent", "test.txt")
        
        assert result is None
    
    def test_delete(self, temp_storage):
        """Test deleting a file."""
        content_id = "test-content-123"
        filename = "test.txt"
        binary = b"Hello, World!"
        
        # Upload first
        temp_storage.upload(content_id, binary, filename, "text/plain")
        
        # Delete
        result = temp_storage.delete(content_id, filename)
        
        assert result is True
        
        # Verify deleted
        downloaded = temp_storage.download(content_id, filename)
        assert downloaded is None
    
    def test_delete_nonexistent(self, temp_storage):
        """Test deleting non-existent file."""
        result = temp_storage.delete("nonexistent", "test.txt")
        
        assert result is False
    
    def test_get_presigned_url_not_supported(self, temp_storage):
        """Test that presigned URLs are not supported for local storage."""
        url = temp_storage.get_presigned_url("test-id", "test.txt")
        
        assert url is None


class TestCloudflareR2Storage:
    """Tests for CloudflareR2Storage backend."""
    
    @pytest.fixture
    def mock_boto3(self):
        """Mock boto3 for R2 storage tests."""
        with patch('storage.boto3') as mock:
            # Mock S3 client
            mock_client = MagicMock()
            mock.client.return_value = mock_client
            
            yield mock_client
    
    def test_upload(self, mock_boto3):
        """Test uploading to R2."""
        storage = CloudflareR2Storage(
            account_id="test-account",
            access_key_id="test-key",
            secret_access_key="test-secret",
            bucket_name="test-bucket"
        )
        
        content_id = "test-content-123"
        filename = "test.txt"
        binary = b"Hello, World!"
        mime_type = "text/plain"
        
        data_ref = storage.upload(content_id, binary, filename, mime_type)
        
        # Verify upload was called
        mock_boto3.put_object.assert_called_once()
        call_args = mock_boto3.put_object.call_args
        
        assert call_args[1]['Bucket'] == 'test-bucket'
        assert call_args[1]['Body'] == binary
        assert call_args[1]['ContentType'] == mime_type
        
        assert data_ref.startswith("r2://test-bucket/")
    
    def test_get_presigned_url(self, mock_boto3):
        """Test generating presigned URL."""
        mock_boto3.generate_presigned_url.return_value = "https://example.com/presigned-url"
        
        storage = CloudflareR2Storage(
            account_id="test-account",
            access_key_id="test-key",
            secret_access_key="test-secret",
            bucket_name="test-bucket"
        )
        
        url = storage.get_presigned_url("test-id", "test.txt", expires_in=3600)
        
        assert url == "https://example.com/presigned-url"
        mock_boto3.generate_presigned_url.assert_called_once()
    
    def test_download(self, mock_boto3):
        """Test downloading from R2."""
        # Mock response
        mock_response = {
            'Body': MagicMock()
        }
        mock_response['Body'].read.return_value = b"Hello, World!"
        mock_boto3.get_object.return_value = mock_response
        
        storage = CloudflareR2Storage(
            account_id="test-account",
            access_key_id="test-key",
            secret_access_key="test-secret",
            bucket_name="test-bucket"
        )
        
        binary = storage.download("test-id", "test.txt")
        
        assert binary == b"Hello, World!"
        mock_boto3.get_object.assert_called_once()


class TestExecuteCell:
    """Tests for execute_cell action routing."""
    
    @pytest.mark.asyncio
    async def test_missing_action(self):
        """Test executing without action parameter."""
        result = await execute_cell({})
        
        assert result["success"] is False
        assert "action" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test executing with unknown action."""
        result = await execute_cell({"action": "unknown"})
        
        assert result["success"] is False
        assert "unknown action" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.handle_list')
    async def test_list_action_routing(self, mock_handle_list):
        """Test routing to list action."""
        mock_handle_list.return_value = {"success": True, "action": "list"}
        
        result = await execute_cell({"action": "list"})
        
        assert result["success"] is True
        mock_handle_list.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('main.handle_load')
    async def test_load_action_routing(self, mock_handle_load):
        """Test routing to load action."""
        mock_handle_load.return_value = {"success": True, "action": "load"}
        
        result = await execute_cell({"action": "load"})
        
        assert result["success"] is True
        mock_handle_load.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('main.handle_persist')
    async def test_persist_action_routing(self, mock_handle_persist):
        """Test routing to persist action."""
        mock_handle_persist.return_value = {"success": True, "action": "persist"}
        
        result = await execute_cell({"action": "persist"})
        
        assert result["success"] is True
        mock_handle_persist.assert_called_once()


class TestHandleList:
    """Tests for list action handler."""
    
    @pytest.mark.asyncio
    @patch('main.ContentManager')
    async def test_list_with_defaults(self, mock_content_manager_class):
        """Test listing with default parameters."""
        # Mock ContentManager
        mock_manager = MagicMock()
        mock_content_manager_class.return_value = mock_manager
        
        # Mock content
        mock_content = MagicMock()
        mock_content.id = "content-1"
        mock_content.content_type_id = "image-png"
        mock_content.filename = "test.png"
        mock_content.size_bytes = 1024
        mock_content.created_at = None
        mock_content.fragments = {"width": 100, "height": 100}
        mock_content.data_ref = "file:///test"
        mock_content.tags = []
        mock_content.version = 1
        mock_content.is_latest = True
        mock_content.origin_cell_id = None
        
        mock_manager.query_contents.return_value = [mock_content]
        
        result = await handle_list({})
        
        assert result["success"] is True
        assert result["action"] == "list"
        assert result["data"]["count"] == 1
        assert result["data"]["total"] == 1
        assert result["data"]["limit"] == 20
        assert result["data"]["offset"] == 0
    
    @pytest.mark.asyncio
    async def test_list_with_invalid_limit(self):
        """Test listing with invalid limit."""
        result = await handle_list({"limit": 0})
        
        assert result["success"] is False
        assert "limit" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_list_with_invalid_offset(self):
        """Test listing with invalid offset."""
        result = await handle_list({"offset": -1})
        
        assert result["success"] is False
        assert "offset" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.ContentManager')
    async def test_list_with_pagination(self, mock_content_manager_class):
        """Test listing with pagination."""
        mock_manager = MagicMock()
        mock_content_manager_class.return_value = mock_manager
        
        # Create 50 mock contents
        mock_contents = []
        for i in range(50):
            mock_content = MagicMock()
            mock_content.id = f"content-{i}"
            mock_content.content_type_id = "image-png"
            mock_content.filename = f"test-{i}.png"
            mock_content.size_bytes = 1024
            mock_content.created_at = None
            mock_content.fragments = {}
            mock_content.data_ref = f"file:///test-{i}"
            mock_content.tags = []
            mock_content.version = 1
            mock_content.is_latest = True
            mock_content.origin_cell_id = None
            mock_contents.append(mock_content)
        
        mock_manager.query_contents.return_value = mock_contents
        
        # Request second page
        result = await handle_list({"limit": 20, "offset": 20})
        
        assert result["success"] is True
        assert result["data"]["count"] == 20
        assert result["data"]["total"] == 50
        assert result["data"]["offset"] == 20


class TestHandleLoad:
    """Tests for load action handler."""
    
    @pytest.mark.asyncio
    async def test_load_missing_content_id(self):
        """Test loading without content_id."""
        result = await handle_load({})
        
        assert result["success"] is False
        assert "content_id" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.ContentManager')
    async def test_load_nonexistent_content(self, mock_content_manager_class):
        """Test loading non-existent content."""
        mock_manager = MagicMock()
        mock_content_manager_class.return_value = mock_manager
        mock_manager.get_content.return_value = None
        
        result = await handle_load({"content_id": "nonexistent"})
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.get_storage_backend')
    @patch('main.ContentManager')
    async def test_load_with_presigned_url(self, mock_content_manager_class, mock_get_storage):
        """Test loading with presigned URL."""
        # Mock content
        mock_content = MagicMock()
        mock_content.id = "content-1"
        mock_content.filename = "test.png"
        mock_content.size_bytes = 1024
        mock_content.fragments = {}
        
        mock_manager = MagicMock()
        mock_content_manager_class.return_value = mock_manager
        mock_manager.get_content.return_value = mock_content
        
        # Mock storage with presigned URL
        mock_storage = MagicMock()
        mock_storage.get_presigned_url.return_value = "https://example.com/presigned"
        mock_get_storage.return_value = mock_storage
        
        result = await handle_load({"content_id": "content-1"})
        
        assert result["success"] is True
        assert "presigned_url" in result["data"]
        assert result["data"]["presigned_url"] == "https://example.com/presigned"
    
    @pytest.mark.asyncio
    @patch('main.get_storage_backend')
    @patch('main.ContentManager')
    async def test_load_with_direct_download(self, mock_content_manager_class, mock_get_storage):
        """Test loading with direct download."""
        # Mock content
        mock_content = MagicMock()
        mock_content.id = "content-1"
        mock_content.filename = "test.png"
        mock_content.size_bytes = 13
        mock_content.fragments = {}
        
        mock_manager = MagicMock()
        mock_content_manager_class.return_value = mock_manager
        mock_manager.get_content.return_value = mock_content
        
        # Mock storage without presigned URL support
        mock_storage = MagicMock()
        mock_storage.get_presigned_url.return_value = None
        mock_storage.download.return_value = b"Hello, World!"
        mock_get_storage.return_value = mock_storage
        
        result = await handle_load({"content_id": "content-1", "direct_download": True})
        
        assert result["success"] is True
        assert "binary" in result["data"]
        assert result["data"]["binary"].startswith("data:")


class TestHandlePersist:
    """Tests for persist action handler."""
    
    @pytest.mark.asyncio
    async def test_persist_missing_content_type_id(self):
        """Test persisting without content_type_id."""
        result = await handle_persist({})
        
        assert result["success"] is False
        assert "content_type_id" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_persist_missing_filename(self):
        """Test persisting without filename."""
        result = await handle_persist({"content_type_id": "image-png"})
        
        assert result["success"] is False
        assert "filename" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_persist_missing_binary(self):
        """Test persisting without binary data."""
        result = await handle_persist({
            "content_type_id": "image-png",
            "filename": "test.png"
        })
        
        assert result["success"] is False
        assert "binary" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.db')
    @patch('main.get_storage_backend')
    @patch('main.ContentManager')
    @patch('main.ContentTypeLoader')
    async def test_persist_success(
        self,
        mock_loader_class,
        mock_manager_class,
        mock_get_storage,
        mock_db
    ):
        """Test successful persistence."""
        # Mock ContentTypeLoader
        mock_loader = MagicMock()
        mock_content_type = MagicMock()
        mock_content_type.id = "image-png"
        mock_content_type.max_size_bytes = 10485760
        mock_loader.load_content_type.return_value = mock_content_type
        mock_loader_class.return_value = mock_loader
        
        # Mock ContentManager
        mock_manager = MagicMock()
        mock_content = MagicMock()
        mock_content.id = "new-content-id"
        mock_content.content_type_id = "image-png"
        mock_content.filename = "test.png"
        mock_content.size_bytes = 13
        mock_content.fragments = {"width": 100, "height": 100}
        mock_content.version = 1
        mock_content.created_at = None
        mock_content.tags = []
        mock_content.origin_cell_id = None
        mock_manager.create_content.return_value = mock_content
        mock_manager_class.return_value = mock_manager
        
        # Mock storage
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "r2://bucket/content/new-content-id/test.png"
        mock_get_storage.return_value = mock_storage
        
        # Create test data
        test_binary = b"Hello, World!"
        encoded = base64.b64encode(test_binary).decode('utf-8')
        data_uri = f"data:image/png;base64,{encoded}"
        
        result = await handle_persist({
            "content_type_id": "image-png",
            "filename": "test.png",
            "binary": data_uri,
            "fragments": {"width": 100, "height": 100}
        })
        
        assert result["success"] is True
        assert result["action"] == "persist"
        assert result["data"]["id"] == "new-content-id"
        assert result["data"]["content_type_id"] == "image-png"
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_persist_invalid_content_type(self, mock_loader_class):
        """Test persisting with invalid content type."""
        mock_loader = MagicMock()
        mock_loader.load_content_type.return_value = None
        mock_loader_class.return_value = mock_loader
        
        test_binary = b"Hello"
        encoded = base64.b64encode(test_binary).decode('utf-8')
        
        result = await handle_persist({
            "content_type_id": "invalid-type",
            "filename": "test.txt",
            "binary": encoded,
            "fragments": {}
        })
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.ContentTypeLoader')
    async def test_persist_file_too_large(self, mock_loader_class):
        """Test persisting file that exceeds max size."""
        mock_loader = MagicMock()
        mock_content_type = MagicMock()
        mock_content_type.id = "image-png"
        mock_content_type.max_size_bytes = 10  # Very small limit
        mock_loader.load_content_type.return_value = mock_content_type
        mock_loader_class.return_value = mock_loader
        
        # Create large binary data
        test_binary = b"X" * 1000
        encoded = base64.b64encode(test_binary).decode('utf-8')
        
        result = await handle_persist({
            "content_type_id": "image-png",
            "filename": "test.png",
            "binary": encoded,
            "fragments": {"width": 100, "height": 100}
        })
        
        assert result["success"] is False
        assert "too large" in result["error"].lower()
    
    @pytest.mark.asyncio
    @patch('main.get_storage_backend')
    @patch('main.ContentTypeLoader')
    async def test_persist_r2_upload_fails(self, mock_loader_class, mock_get_storage):
        """Test R2 upload failure - no cleanup needed."""
        # Mock ContentTypeLoader
        mock_loader = MagicMock()
        mock_content_type = MagicMock()
        mock_content_type.id = "image-png"
        mock_content_type.max_size_bytes = 10485760
        mock_loader.load_content_type.return_value = mock_content_type
        mock_loader_class.return_value = mock_loader
        
        # Mock storage to fail on upload
        mock_storage = MagicMock()
        mock_storage.upload.side_effect = Exception("R2 connection error")
        mock_get_storage.return_value = mock_storage
        
        # Create test data
        test_binary = b"Hello, World!"
        encoded = base64.b64encode(test_binary).decode('utf-8')
        
        result = await handle_persist({
            "content_type_id": "image-png",
            "filename": "test.png",
            "binary": encoded,
            "fragments": {"width": 100, "height": 100},
            "assignee_id": "user-123"
        })
        
        # Verify error response
        assert result["success"] is False
        assert result["error_code"] == "R2_UPLOAD_FAILED"
        assert "Failed to upload content to R2" in result["error"]
        assert result["details"]["status"] == "NO_FILES_CREATED"
        assert result["details"]["cleanup"] == "NONE_NEEDED"
        
        # Verify storage delete was NOT called (nothing to cleanup)
        assert not mock_storage.delete.called
    
    @pytest.mark.asyncio
    @patch('main.db')
    @patch('main.get_storage_backend')
    @patch('main.ContentManager')
    @patch('main.ContentTypeLoader')
    async def test_persist_mongodb_fails_cleanup_succeeds(
        self,
        mock_loader_class,
        mock_manager_class,
        mock_get_storage,
        mock_db
    ):
        """Test MongoDB insert failure after R2 success - cleanup succeeds."""
        # Mock ContentTypeLoader
        mock_loader = MagicMock()
        mock_content_type = MagicMock()
        mock_content_type.id = "image-png"
        mock_content_type.max_size_bytes = 10485760
        mock_content_type.expected_fragments = {"width": int, "height": int}
        mock_loader.load_content_type.return_value = mock_content_type
        mock_loader_class.return_value = mock_loader
        
        # Mock ContentManager
        mock_manager = MagicMock()
        mock_manager.validate_content_fragments.return_value = True
        mock_manager_class.return_value = mock_manager
        
        # Mock storage - upload succeeds
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "r2://bucket/content/test-id/test.png"
        mock_storage.delete.return_value = True  # Cleanup succeeds
        mock_get_storage.return_value = mock_storage
        
        # Mock DB - insert fails
        mock_db.insert = AsyncMock(side_effect=Exception("MongoDB connection lost"))
        
        # Create test data
        test_binary = b"Hello, World!"
        encoded = base64.b64encode(test_binary).decode('utf-8')
        
        result = await handle_persist({
            "content_type_id": "image-png",
            "filename": "test.png",
            "binary": encoded,
            "fragments": {"width": 100, "height": 100},
            "assignee_id": "user-123"
        })
        
        # Verify error response
        assert result["success"] is False
        assert result["error_code"] == "MONGODB_INSERT_FAILED"
        assert "Failed to save content metadata to MongoDB" in result["error"]
        assert result["details"]["r2_status"] == "UPLOADED_SUCCESSFULLY"
        assert result["details"]["cleanup_status"] == "SUCCESS"
        assert result["details"]["status"] == "ORPHANED_FILE_CLEANED_UP"
        assert result["details"]["action_needed"] == "NONE - file was deleted from R2"
        
        # Verify storage delete WAS called (cleanup executed)
        assert mock_storage.delete.called
    
    @pytest.mark.asyncio
    @patch('main.db')
    @patch('main.get_storage_backend')
    @patch('main.ContentManager')
    @patch('main.ContentTypeLoader')
    async def test_persist_mongodb_fails_cleanup_fails(
        self,
        mock_loader_class,
        mock_manager_class,
        mock_get_storage,
        mock_db
    ):
        """Test MongoDB insert failure AND cleanup fails - CRITICAL alert."""
        # Mock ContentTypeLoader
        mock_loader = MagicMock()
        mock_content_type = MagicMock()
        mock_content_type.id = "image-png"
        mock_content_type.max_size_bytes = 10485760
        mock_content_type.expected_fragments = {"width": int, "height": int}
        mock_loader.load_content_type.return_value = mock_content_type
        mock_loader_class.return_value = mock_loader
        
        # Mock ContentManager
        mock_manager = MagicMock()
        mock_manager.validate_content_fragments.return_value = True
        mock_manager_class.return_value = mock_manager
        
        # Mock storage - upload succeeds, delete fails
        mock_storage = MagicMock()
        data_ref = "r2://bucket/content/test-id/test.png"
        mock_storage.upload.return_value = data_ref
        mock_storage.delete.side_effect = Exception("R2 connection lost during cleanup")
        mock_get_storage.return_value = mock_storage
        
        # Mock DB - insert fails
        mock_db.insert = AsyncMock(side_effect=Exception("MongoDB connection lost"))
        
        # Create test data
        test_binary = b"Hello, World!"
        encoded = base64.b64encode(test_binary).decode('utf-8')
        
        result = await handle_persist({
            "content_type_id": "image-png",
            "filename": "test.png",
            "binary": encoded,
            "fragments": {"width": 100, "height": 100},
            "assignee_id": "user-123"
        })
        
        # Verify CRITICAL error response
        assert result["success"] is False
        assert result["error_code"] == "ORPHANED_FILE_CLEANUP_FAILED"
        assert "CRITICAL: Orphaned file remains in R2" in result["error"]
        assert result["details"]["status"] == "ORPHANED_FILE_IN_R2"
        assert result["details"]["alert_level"] == "CRITICAL"
        assert "MANUAL" in result["details"]["action_needed"]
        assert data_ref in result["details"]["action_needed"]
        
        # Verify storage delete WAS attempted (but failed)
        assert mock_storage.delete.called
    
    @pytest.mark.asyncio
    @patch('main.db')
    @patch('main.get_storage_backend')
    @patch('main.ContentManager')
    @patch('main.ContentTypeLoader')
    async def test_persist_validation_fails_after_upload(
        self,
        mock_loader_class,
        mock_manager_class,
        mock_get_storage,
        mock_db
    ):
        """Test fragment validation failure after R2 upload - cleanup succeeds."""
        # Mock ContentTypeLoader
        mock_loader = MagicMock()
        mock_content_type = MagicMock()
        mock_content_type.id = "image-png"
        mock_content_type.max_size_bytes = 10485760
        mock_content_type.expected_fragments = {"width": int, "height": int, "required_field": str}
        mock_loader.load_content_type.return_value = mock_content_type
        mock_loader_class.return_value = mock_loader
        
        # Mock ContentManager - validation fails
        mock_manager = MagicMock()
        mock_manager.validate_content_fragments.side_effect = ValueError("Missing required fragment: required_field")
        mock_manager_class.return_value = mock_manager
        
        # Mock storage - upload succeeds, delete succeeds
        mock_storage = MagicMock()
        mock_storage.upload.return_value = "r2://bucket/content/test-id/test.png"
        mock_storage.delete.return_value = True
        mock_get_storage.return_value = mock_storage
        
        # Create test data
        test_binary = b"Hello, World!"
        encoded = base64.b64encode(test_binary).decode('utf-8')
        
        result = await handle_persist({
            "content_type_id": "image-png",
            "filename": "test.png",
            "binary": encoded,
            "fragments": {"width": 100, "height": 100},  # Missing required_field
            "assignee_id": "user-123"
        })
        
        # Verify validation error response
        assert result["success"] is False
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "Missing required fragment" in result["error"]
        
        # Verify storage delete WAS called (cleanup after validation failure)
        assert mock_storage.delete.called

