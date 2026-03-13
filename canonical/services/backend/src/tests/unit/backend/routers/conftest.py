"""
Shared fixtures for router unit tests.

Provides common mocks, test clients, and fixtures for testing FastAPI routers
without requiring external dependencies like databases or external APIs.

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
from datetime import datetime


@pytest.fixture
def mock_db():
    """
    Mock database instance for router tests.
    
    Provides basic CRUD operation mocks that return appropriate test data.
    
    Returns:
        Mock database with common methods
    """
    db = Mock()
    db.find_one = AsyncMock(return_value=None)
    db.find_many = AsyncMock(return_value=[])
    db.insert_one = AsyncMock(return_value={"_id": "test-id-123"})
    db.update_one = AsyncMock(return_value={"modified_count": 1})
    db.delete_one = AsyncMock(return_value={"deleted_count": 1})
    db.count = AsyncMock(return_value=0)
    return db


@pytest.fixture
def mock_current_user():
    """
    Mock authenticated user for protected endpoints.
    
    Returns a typical user object with common fields and admin role
    to bypass permission checks in unit tests.
    
    Returns:
        Mock User object with admin privileges
    """
    user = Mock()
    user.id = "test-user-id-123"
    user.name = "Test User"
    user.email = "test@example.com"
    user.authenticated = True
    user.active = True
    user.role = "admin"
    user.roles = ["admin", "user"]  # Admin bypasses all permission checks
    user.created_at = datetime.utcnow()
    return user


@pytest.fixture
def mock_admin_user():
    """
    Mock admin user for admin-protected endpoints.
    
    Returns:
        Mock User object with admin role
    """
    user = Mock()
    user.id = "admin-user-id-123"
    user.name = "Admin User"
    user.email = "admin@example.com"
    user.authenticated = True
    user.active = True
    user.role = "admin"
    user.roles = ["admin", "user"]  # For RBAC system
    user.created_at = datetime.utcnow()
    return user


@pytest.fixture
def mock_session():
    """
    Mock session object for session-related tests.
    
    Returns:
        Mock Session object
    """
    session = Mock()
    session.id = "test-session-id-123"
    session.user_id = "test-user-id-123"
    session.created_at = datetime.utcnow()
    session.last_activity = datetime.utcnow()
    session.active = True
    return session


@pytest.fixture
def mock_celula():
    """
    Mock cell (cell) object for content-related tests.
    
    Returns:
        Mock Cell object
    """
    cell = Mock()
    cell.id = "test-cell-id-123"
    cell.livro_id = "test-book-id-123"
    cell.titulo = "Test Cell"
    cell.content = "Test content"
    cell.type = "markdown"
    cell.criador_id = "test-user-id-123"
    cell.created_at = datetime.utcnow()
    cell.updated_at = datetime.utcnow()
    return cell


@pytest.fixture
def mock_livro():
    """
    Mock book (book/notebook) object for notebook-related tests.
    
    Returns:
        Mock Book object
    """
    book = Mock()
    book.id = "test-book-id-123"
    book.titulo = "Test Notebook"
    book.description = "Test notebook description"
    book.criador_id = "test-user-id-123"
    book.cells = []
    book.created_at = datetime.utcnow()
    book.updated_at = datetime.utcnow()
    return book


@pytest.fixture
def mock_ai_model():
    """
    Mock AI model configuration object.
    
    Returns:
        Mock AIModel object
    """
    model = Mock()
    model.id = "test-model-id-123"
    model.name = "gpt-3.5-turbo"
    model.provider = "openai"
    model.available = True
    model.config = {}
    return model


@pytest.fixture
def test_client():
    """
    FastAPI TestClient for making HTTP requests to routers.
    
    Creates a test client with the full application, suitable for
    integration-style router tests.
    
    Returns:
        TestClient instance
    """
    from app.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_auth_override(mock_current_user):
    """
    Automatically setup authentication override for all router tests.
    
    This fixture runs automatically for all tests in the router suite,
    ensuring that authentication is bypassed by default. Tests can
    override this by using app.dependency_overrides directly if they
    need different authentication behavior.
    
    Returns:
        Mock user that is used for authentication
    """
    from app.main import app
    from app.auth import get_current_user_required
    
    # Override the authentication dependency to return mock user
    app.dependency_overrides[get_current_user_required] = lambda: mock_current_user
    
    yield mock_current_user
    
    # Clean up after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_get_current_user(mock_current_user):
    """
    Mock the get_current_user_required dependency.
    
    Patches the auth dependency to return a mock user without
    requiring actual authentication.
    
    Usage:
        def test_protected_endpoint(test_client, mock_get_current_user):
            response = test_client.get("/api/protected")
            # User is automatically authenticated
    
    Returns:
        Patch context manager
    """
    with patch('app.auth.get_current_user_required', return_value=mock_current_user):
        yield mock_current_user


@pytest.fixture
def mock_get_admin_user(mock_admin_user):
    """
    Mock the get_current_user_required dependency with admin user.
    
    Returns:
        Patch context manager
    """
    from app.main import app
    from app.auth import get_current_user_required
    
    # Override with admin user
    app.dependency_overrides[get_current_user_required] = lambda: mock_admin_user
    
    yield mock_admin_user
    
    # Clean up is handled by setup_auth_override fixture


@pytest.fixture
def sample_chat_request():
    """
    Sample chat request data for chat router tests.
    
    Returns:
        Dict with chat request structure
    """
    return {
        "intencao": "Hello, can you help me?",
        "assignee_id": "test-user-id-123",
        "model": "gpt-3.5-turbo",
        "classificarIntencao": False,
        "historico": [],
        "anexos": []
    }


@pytest.fixture
def sample_trace_data():
    """
    Sample trace data for traces router tests.
    
    Returns:
        Dict with trace structure
    """
    return {
        "conversation_id": "test-conv-id-123",
        "session_id": "test-session-id-123",
        "user_message": "Test message",
        "target_llm": "gpt-3.5-turbo",
        "fragments": {
            "classification": {"intent": "conversar"},
            "rag_retrieval": {"documents": []},
            "llm_response": {"response": "Test response"}
        },
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def mock_orchestrator():
    """
    Mock orchestrator instance for issues processing tests.
    
    Returns:
        Mock Orchestrator object
    """
    orch = Mock()
    orch.force_process_pending_issues = Mock(return_value={
        "status": "processing_triggered",
        "message": "Triggered processing of 3 pending cells",
        "pending_count": 3
    })
    orch.start_monitoring = Mock(return_value={"status": "monitoring_started"})
    orch.stop_monitoring = Mock(return_value={"status": "monitoring_stopped"})
    orch.pause_processing = Mock(return_value={"status": "processing_paused"})
    orch.resume_processing = Mock(return_value={"status": "processing_resumed"})
    return orch


@pytest.fixture
def mock_file_system():
    """
    Mock file system operations for file_ops router tests.
    
    Returns:
        Mock with file operation methods
    """
    fs = Mock()
    fs.exists = Mock(return_value=True)
    fs.is_file = Mock(return_value=True)
    fs.is_dir = Mock(return_value=False)
    fs.read_text = Mock(return_value="Test file content")
    fs.write_text = Mock(return_value=None)
    fs.mkdir = Mock(return_value=None)
    fs.rmdir = Mock(return_value=None)
    fs.unlink = Mock(return_value=None)
    return fs


@pytest.fixture
def mock_config():
    """
    Mock configuration values for config router tests.
    
    Returns:
        Dict with configuration values
    """
    return {
        "BASE_DIR": "/app",
        "SCAREFERA_LAB_DIR": "/app/ScareFeraLab",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "GEMINI_API_KEY": "test-gemini-key",
        "OPENAI_API_KEY": "test-openai-key",
        "DEBUG": True,
        "LOG_LEVEL": "INFO"
    }


@pytest.fixture
def mock_system_info():
    """
    Mock system information for system router tests.
    
    Returns:
        Dict with system info
    """
    return {
        "cpu_percent": 25.5,
        "memory_percent": 60.3,
        "disk_usage": {
            "total": 100000000000,
            "used": 50000000000,
            "free": 50000000000,
            "percent": 50.0
        },
        "python_version": "3.10.12",
        "platform": "Linux"
    }


@pytest.fixture
def mock_service_status():
    """
    Mock service status for services router tests.
    
    Returns:
        Dict with service statuses
    """
    return {
        "ollama": {"status": "available", "url": "http://localhost:11434"},
        "mongodb": {"status": "connected", "version": "6.0.0"},
        "chromadb": {"status": "available", "collections": 5}
    }


@pytest.fixture
def mock_issues_data():
    """
    Mock GitHub issues data for issues router tests.
    
    Returns:
        List of mock issue objects
    """
    return [
        {
            "number": 1,
            "title": "Test Issue 1",
            "state": "open",
            "labels": ["bug"],
            "assignees": ["user1"],
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "number": 2,
            "title": "Test Issue 2",
            "state": "closed",
            "labels": ["enhancement"],
            "assignees": ["user2"],
            "created_at": datetime.utcnow().isoformat()
        }
    ]
