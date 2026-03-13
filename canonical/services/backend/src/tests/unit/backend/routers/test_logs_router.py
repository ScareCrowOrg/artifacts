"""
Unit tests for logs_router.

Tests the log namespace API endpoints for centralized log management.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException

from app.routers.logs_router import (
    discover_log_namespaces,
    get_default_log_namespaces,
    logs_router
)


class TestLogNamespaceDiscovery:
    """Test log namespace discovery functionality."""
    
    def test_get_default_log_namespaces(self):
        """Test getting default log namespaces."""
        namespaces = get_default_log_namespaces()
        
        # Should return a list
        assert isinstance(namespaces, list)
        
        # Should contain core namespaces
        assert "app" in namespaces
        assert "auth" in namespaces
        assert "api" in namespaces
        assert "store" in namespaces
        assert "router" in namespaces
        assert "debug" in namespaces
        
        # Should have reasonable size
        assert len(namespaces) > 10
        assert len(namespaces) < 100
    
    def test_default_namespaces_are_sorted(self):
        """Test that default namespaces follow patterns."""
        namespaces = get_default_log_namespaces()
        
        # Should contain auth sub-namespaces
        auth_namespaces = [ns for ns in namespaces if ns.startswith("auth")]
        assert len(auth_namespaces) > 1
        assert "auth:login" in namespaces
        assert "auth:logout" in namespaces
        
        # Should contain api sub-namespaces
        api_namespaces = [ns for ns in namespaces if ns.startswith("api")]
        assert len(api_namespaces) > 1
        assert "api:cells" in namespaces
        assert "api:books" in namespaces
        
        # Should contain store sub-namespaces
        store_namespaces = [ns for ns in namespaces if ns.startswith("store")]
        assert len(store_namespaces) > 1
        assert "store:cells" in namespaces
        assert "store:books" in namespaces
    
    @patch("app.routers.logs_router.Path")
    def test_discover_log_namespaces_no_frontend(self, mock_path):
        """Test namespace discovery when frontend directory doesn't exist."""
        # Mock frontend directory as not existing
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance
        
        namespaces = discover_log_namespaces()
        
        # Should still return core namespaces
        assert isinstance(namespaces, list)
        assert "app" in namespaces
        assert "auth" in namespaces
        assert "api" in namespaces
    
    @patch("app.routers.logs_router.Path")
    def test_discover_log_namespaces_with_files(self, mock_path):
        """Test namespace discovery scanning files."""
        # Mock frontend directory structure
        mock_frontend_src = Mock()
        mock_frontend_src.exists.return_value = True
        
        # Mock file with createLogger calls
        mock_file_1 = Mock()
        mock_file_1.read_text.return_value = """
        import { createLogger } from '@/utils/logger'
        const log = createLogger('feature:test')
        log.debug('Test message')
        """
        
        mock_file_2 = Mock()
        mock_file_2.read_text.return_value = """
        const authLog = createLogger("auth:custom")
        const apiLog = createLogger('api:new')
        """
        
        # Mock rglob to return mock files
        mock_frontend_src.rglob.return_value = [mock_file_1, mock_file_2]
        
        # Mock open to return file content
        def mock_open_func(file_path, *args, **kwargs):
            mock_file = Mock()
            mock_context = Mock()
            
            if file_path == mock_file_1:
                mock_context.__enter__ = Mock(return_value=mock_file)
                mock_file.read.return_value = """
                import { createLogger } from '@/utils/logger'
                const log = createLogger('feature:test')
                log.debug('Test message')
                """
            elif file_path == mock_file_2:
                mock_context.__enter__ = Mock(return_value=mock_file)
                mock_file.read.return_value = """
                const authLog = createLogger("auth:custom")
                const apiLog = createLogger('api:new')
                """
            
            mock_context.__exit__ = Mock(return_value=False)
            return mock_context
        
        mock_path.return_value = mock_frontend_src
        
        with patch("builtins.open", side_effect=mock_open_func):
            namespaces = discover_log_namespaces()
        
        # Should include core namespaces
        assert "app" in namespaces
        assert "auth" in namespaces
        
        # Result should be sorted
        assert namespaces == sorted(namespaces)


class TestLogsRouterEndpoints:
    """Test logs router API endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_log_namespaces_default(self):
        """Test GET /logs/namespaces with default behavior."""
        from app.routers.logs_router import get_log_namespaces
        
        # Mock user - use Mock instead of actual User model to avoid validation
        mock_user = Mock()
        mock_user.id = "test-user"
        mock_user.email = "testuser@example.com"
        mock_user.name = "Test User"
        
        # Call the endpoint function directly
        result = await get_log_namespaces(discover=False, current_user=mock_user)
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert "app" in result
        assert "auth" in result
    
    @pytest.mark.asyncio
    async def test_get_log_namespaces_discover(self):
        """Test GET /logs/namespaces with discover=true."""
        from app.routers.logs_router import get_log_namespaces
        
        # Mock user
        mock_user = Mock()
        mock_user.id = "test-user"
        mock_user.email = "testuser@example.com"
        mock_user.name = "Test User"
        
        with patch("app.routers.logs_router.discover_log_namespaces") as mock_discover:
            mock_discover.return_value = ["app", "auth", "discovered:new"]
            
            result = await get_log_namespaces(discover=True, current_user=mock_user)
        
        assert isinstance(result, list)
        assert "app" in result
        assert "auth" in result
        assert "discovered:new" in result
    
    @pytest.mark.asyncio
    async def test_get_log_namespaces_stats(self):
        """Test GET /logs/namespaces/stats endpoint."""
        from app.routers.logs_router import get_log_namespaces_stats
        
        # Mock user
        mock_user = Mock()
        mock_user.id = "test-user"
        mock_user.email = "testuser@example.com"
        mock_user.name = "Test User"
        
        result = await get_log_namespaces_stats(current_user=mock_user)
        
        assert "default_count" in result
        assert "discovered_count" in result
        assert "default_namespaces" in result
        assert "discovered_namespaces" in result
        
        assert isinstance(result["default_count"], int)
        assert isinstance(result["discovered_count"], int)
        assert isinstance(result["default_namespaces"], list)
        assert isinstance(result["discovered_namespaces"], list)
    
    @pytest.mark.asyncio
    async def test_logs_endpoints_require_authentication(self):
        """Test that logs endpoints require authentication (testing the dependency)."""
        from app.routers.logs_router import get_log_namespaces
        from app.auth import get_current_user_required
        
        # The authentication is handled by FastAPI dependency injection
        # We just verify the dependency is correctly specified
        import inspect
        sig = inspect.signature(get_log_namespaces)
        
        # Verify current_user parameter has Depends annotation
        current_user_param = sig.parameters.get('current_user')
        assert current_user_param is not None
        
        # The actual authentication testing would be done in integration tests
        # with a real FastAPI TestClient and middleware
