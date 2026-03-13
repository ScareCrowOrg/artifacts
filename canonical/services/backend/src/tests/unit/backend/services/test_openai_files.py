"""
Unit tests for OpenAI Files API integration service.

Tests the upload_file_to_openai_api, delete_file_from_openai_api, and
list_files_from_openai_api functions with mocked HTTP client.

Compliance: RULESET.md Rule 3.1 (90% coverage), Rule 3.2 (Unit tests)
"""

import pytest
import httpx
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from tempfile import NamedTemporaryFile

from app.services.openai_files_api import (
    upload_file_to_openai_api,
    delete_file_from_openai_api,
    list_files_from_openai_api
)
from .mocks.openai_mock import (
    MockHttpxAsyncClient,
    create_mock_file_response,
    create_mock_file_list_response,
    create_mock_delete_response
)


class TestUploadFileToOpenAIAPI:
    """Tests for upload_file_to_openai_api function."""
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self):
        """Test successful file upload."""
        # Create temporary test file
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test file content")
            temp_file = Path(f.name)
        
        try:
            # Setup mock client
            mock_client = MockHttpxAsyncClient()
            mock_client.setup_post_response(
                url="/files",
                response_data=create_mock_file_response("file-abc123", "test.txt")
            )
            
            with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
                file_id = await upload_file_to_openai_api(
                    file_path=temp_file,
                    purpose="assistants",
                    api_key="test-key"
                )
            
            assert file_id == "file-abc123"
            assert mock_client.call_count['POST'] == 1
        finally:
            # Cleanup
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_file_with_global_api_key(self):
        """Test file upload using global API key from config."""
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_file = Path(f.name)
        
        try:
            mock_client = MockHttpxAsyncClient()
            mock_client.setup_post_response(
                url="/files",
                response_data=create_mock_file_response("file-xyz")
            )
            
            with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
                with patch('app.services.openai_files_api.OPENAI_API_KEY', "global-key"):
                    file_id = await upload_file_to_openai_api(
                        file_path=temp_file,
                        purpose="assistants"
                    )
            
            assert file_id == "file-xyz"
        finally:
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_file_no_api_key(self):
        """Test error when API key is not configured."""
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            with patch('app.services.openai_files_api.OPENAI_API_KEY', None):
                with pytest.raises(ValueError) as exc_info:
                    await upload_file_to_openai_api(
                        file_path=temp_file,
                        purpose="assistants"
                    )
                
                assert "OpenAI API Key não configurada" in str(exc_info.value)
        finally:
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_file_not_exists(self):
        """Test error when file does not exist."""
        import tempfile
        non_existent_file = Path(tempfile.gettempdir()) / "non_existent_file_123456.txt"
        
        with pytest.raises(ValueError) as exc_info:
            await upload_file_to_openai_api(
                file_path=non_existent_file,
                api_key="test-key"
            )
        
        assert "File not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_upload_directory_instead_of_file(self):
        """Test error when path is a directory instead of a file."""
        import tempfile
        test_dir = Path(tempfile.gettempdir())
        
        with pytest.raises(ValueError) as exc_info:
            await upload_file_to_openai_api(
                file_path=test_dir,
                api_key="test-key"
            )
        
        assert "Path is not a file" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_upload_file_invalid_response(self):
        """Test error handling when API returns invalid response."""
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test")
            temp_file = Path(f.name)
        
        try:
            mock_client = MockHttpxAsyncClient()
            # Response without 'id' field
            mock_client.setup_post_response(
                url="/files",
                response_data={"error": "Invalid"}
            )
            
            with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
                with pytest.raises(ValueError) as exc_info:
                    await upload_file_to_openai_api(
                        file_path=temp_file,
                        api_key="test-key"
                    )
                
                assert "Invalid response from OpenAI Files API" in str(exc_info.value)
        finally:
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_file_http_error(self):
        """Test error handling for HTTP errors."""
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            mock_client = MockHttpxAsyncClient()
            mock_client.setup_post_response(
                url="/files",
                response_data={},
                status_code=500
            )
            
            with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
                with pytest.raises(httpx.HTTPStatusError):
                    await upload_file_to_openai_api(
                        file_path=temp_file,
                        api_key="test-key"
                    )
        finally:
            temp_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_file_timeout(self):
        """Test timeout handling during upload."""
        with NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_file = Path(f.name)
        
        try:
            # Create mock that raises timeout
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")
            
            with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
                with pytest.raises(httpx.TimeoutException):
                    await upload_file_to_openai_api(
                        file_path=temp_file,
                        api_key="test-key"
                    )
        finally:
            temp_file.unlink()


class TestDeleteFileFromOpenAIAPI:
    """Tests for delete_file_from_openai_api function."""
    
    @pytest.mark.asyncio
    async def test_delete_file_success(self):
        """Test successful file deletion."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_delete_response(
            url="/files/file-abc123",
            response_data=create_mock_delete_response("file-abc123", True)
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            deleted = await delete_file_from_openai_api(
                file_id="file-abc123",
                api_key="test-key"
            )
        
        assert deleted is True
        assert mock_client.call_count['DELETE'] == 1
    
    @pytest.mark.asyncio
    async def test_delete_file_failed(self):
        """Test file deletion returning False."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_delete_response(
            url="/files/file-abc123",
            response_data=create_mock_delete_response("file-abc123", False)
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            deleted = await delete_file_from_openai_api(
                file_id="file-abc123",
                api_key="test-key"
            )
        
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_delete_file_with_global_api_key(self):
        """Test file deletion using global API key."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_delete_response(
            url="/files/file-xyz",
            response_data=create_mock_delete_response("file-xyz", True)
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            with patch('app.services.openai_files_api.OPENAI_API_KEY', "global-key"):
                deleted = await delete_file_from_openai_api(
                    file_id="file-xyz"
                )
        
        assert deleted is True
    
    @pytest.mark.asyncio
    async def test_delete_file_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_files_api.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await delete_file_from_openai_api(
                    file_id="file-abc123"
                )
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_file_http_error(self):
        """Test error handling for HTTP errors during deletion."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_delete_response(
            url="/files/file-abc123",
            response_data={},
            status_code=404
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await delete_file_from_openai_api(
                    file_id="file-abc123",
                    api_key="test-key"
                )


class TestListFilesFromOpenAIAPI:
    """Tests for list_files_from_openai_api function."""
    
    @pytest.mark.asyncio
    async def test_list_files_success(self):
        """Test successful file listing."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/files",
            response_data=create_mock_file_list_response()
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            files = await list_files_from_openai_api(
                api_key="test-key"
            )
        
        assert len(files) == 2
        assert files[0]['id'] == "file-1"
        assert files[1]['id'] == "file-2"
        assert mock_client.call_count['GET'] == 1
    
    @pytest.mark.asyncio
    async def test_list_files_with_purpose_filter(self):
        """Test file listing with purpose filter."""
        mock_client = MockHttpxAsyncClient()
        mock_files = [create_mock_file_response("file-1", "test.txt", "assistants")]
        mock_client.setup_get_response(
            url="/files",
            response_data=create_mock_file_list_response(mock_files)
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            files = await list_files_from_openai_api(
                purpose="assistants",
                api_key="test-key"
            )
        
        assert len(files) == 1
        assert files[0]['purpose'] == "assistants"
    
    @pytest.mark.asyncio
    async def test_list_files_empty_result(self):
        """Test file listing with no files."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/files",
            response_data=create_mock_file_list_response([])
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            files = await list_files_from_openai_api(
                api_key="test-key"
            )
        
        assert len(files) == 0
    
    @pytest.mark.asyncio
    async def test_list_files_with_global_api_key(self):
        """Test file listing using global API key."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/files",
            response_data=create_mock_file_list_response()
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            with patch('app.services.openai_files_api.OPENAI_API_KEY', "global-key"):
                files = await list_files_from_openai_api()
        
        assert len(files) == 2
    
    @pytest.mark.asyncio
    async def test_list_files_no_api_key(self):
        """Test error when API key is not configured."""
        with patch('app.services.openai_files_api.OPENAI_API_KEY', None):
            with pytest.raises(ValueError) as exc_info:
                await list_files_from_openai_api()
            
            assert "OpenAI API Key não configurada" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_list_files_http_error(self):
        """Test error handling for HTTP errors during listing."""
        mock_client = MockHttpxAsyncClient()
        mock_client.setup_get_response(
            url="/files",
            response_data={},
            status_code=500
        )
        
        with patch('app.services.openai_files_api.httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await list_files_from_openai_api(
                    api_key="test-key"
                )
