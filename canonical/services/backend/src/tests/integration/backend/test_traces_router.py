"""
Integration tests for Traces API Router.

Tests cover:
- Trace retrieval by conversation ID
- Recent traces listing with pagination
- Authorization and permission checks
- Error handling for missing traces
- Query parameters validation

Technical naming: All test functions in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from app.main import app
from app.models.content import Cell
from app.models.users import User
from app.models.base import CellStatus
from app.auth import get_current_user_required


@pytest.fixture
def mock_user():
    """Create a mock authenticated user."""
    return User(
        id="user_123",
        name="Test User",
        email="test@example.com",
        foto_url=None
    )


@pytest.fixture
def mock_trace_cell():
    """Create a mock trace cell with fragments."""
    return Cell(
        id="trace_cell_123",
        assignee_id="user_123",
        notebook_item_type_id="conversation-trace-item",
        cellTypeId="conversation-trace-item",
        source_book_id="book-conversation-traces-v1",
        initial_data={
            "conversation_id": "conv_abc123",
            "session_id": "sess_789",
            "tracing_enabled": True,
            "user_message": "How do I create a cell?",
            "target_llm": "openai",
            "created_at": "2025-11-18T10:00:00.000000"
        },
        fragments=[
            {
                "timestamp": "2025-11-18T10:00:01.000000",
                "conversation_id": "conv_abc123",
                "stage": "initial_prompt",
                "data": {"user_message": "How do I create a cell?"}
            },
            {
                "timestamp": "2025-11-18T10:00:02.000000",
                "conversation_id": "conv_abc123",
                "stage": "rag_retrieval",
                "data": {"chunks_retrieved": 5, "query": "create cell"}
            },
            {
                "timestamp": "2025-11-18T10:00:03.000000",
                "conversation_id": "conv_abc123",
                "stage": "llm_response",
                "data": {"response": "To create a cell..."}
            }
        ],
        status=CellStatus.PENDING,
        created_at=datetime(2025, 11, 18, 10, 0, 0)
    )


@pytest.fixture
def client(mock_user):
    """Create a test client with authentication override."""
    # Override the auth dependency to return our mock user
    def override_get_current_user():
        return mock_user
    
    app.dependency_overrides[get_current_user_required] = override_get_current_user
    client = TestClient(app)
    yield client
    # Clean up the override after test
    app.dependency_overrides.clear()


class TestGetTraceByConversationId:
    """Test suite for GET /traces/conversation/{conversation_id} endpoint."""
    
    @patch('app.routers.traces_router.db')
    def test_get_trace_success(self, mock_db, client, mock_user, mock_trace_cell):
        """Test successful trace retrieval by conversation ID."""
        # Setup mocks
        mock_db.find_many = AsyncMock(return_value=[mock_trace_cell])
        
        # Make request
        response = client.get(
            "/api/traces/conversation/conv_abc123"
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert data["trace_id"] == "trace_cell_123"
        assert data["conversation_id"] == "conv_abc123"
        assert data["session_id"] == "sess_789"
        assert data["user_message"] == "How do I create a cell?"
        assert data["target_llm"] == "openai"
        assert data["fragments_count"] == 3
        assert len(data["fragments"]) == 3
        
        # Verify fragments structure
        assert data["fragments"][0]["stage"] == "initial_prompt"
        assert data["fragments"][1]["stage"] == "rag_retrieval"
        assert data["fragments"][2]["stage"] == "llm_response"
    
    @patch('app.routers.traces_router.db')
    
    def test_get_trace_not_found(self, mock_db, client, mock_user):
        """Test trace retrieval when conversation ID does not exist."""
        # Setup mocks - return empty list
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        # Make request
        response = client.get(
            "/api/traces/conversation/nonexistent_conv",
            
        )
        
        # Assertions
        assert response.status_code == 404
        assert "No trace found" in response.json()["detail"]
    
    @patch('app.routers.traces_router.db')
    def test_get_trace_unauthorized_user(self, mock_db, mock_trace_cell):
        """Test trace retrieval by unauthorized user (not the owner)."""
        # Setup mocks - different user
        different_user = User(
            id="user_456",  # Different from trace owner
            name="Other User",
            email="other@example.com",
            foto_url=None
        )
        mock_db.find_many = AsyncMock(return_value=[mock_trace_cell])
        
        # Override auth with different user
        app.dependency_overrides[get_current_user_required] = lambda: different_user
        client = TestClient(app)
        
        # Make request
        response = client.get(
            "/api/traces/conversation/conv_abc123"
        )
        
        # Clean up override
        app.dependency_overrides.clear()
        
        # Assertions
        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]
    
    @patch('app.routers.traces_router.db')
    
    def test_get_trace_with_non_trace_cells(self, mock_db, client, mock_user):
        """Test that non-trace cells are ignored when searching."""
        # Setup mocks - include non-trace cells
        
        
        non_trace_cell = Cell(
            id="regular_cell_123",
            assignee_id="user_123",
            notebook_item_type_id="regular-item",  # Not a trace cell
            cellTypeId="regular-item",
            source_book_id="some-book",
            initial_data={"conversation_id": "conv_abc123"},  # Same conv_id
            fragments=[],
            status=CellStatus.PENDING,
            createdAt=datetime.utcnow()
        )
        
        mock_db.find_many = AsyncMock(return_value=[non_trace_cell])
        
        # Make request
        response = client.get(
            "/api/traces/conversation/conv_abc123",
            
        )
        
        # Assertions - should not find trace (non-trace cell is ignored)
        assert response.status_code == 404
    
    @patch('app.routers.traces_router.db')
    
    def test_get_trace_database_error(self, mock_db, client, mock_user):
        """Test error handling when database query fails."""
        # Setup mocks - raise exception
        
        mock_db.find_many.side_effect = Exception("Database connection failed")
        
        # Make request
        response = client.get(
            "/api/traces/conversation/conv_abc123",
            
        )
        
        # Assertions
        assert response.status_code == 500
        assert "Error retrieving trace data" in response.json()["detail"]


class TestGetRecentTraces:
    """Test suite for GET /traces/recent endpoint."""
    
    @patch('app.routers.traces_router.db')
    
    def test_get_recent_traces_default_params(self, mock_db, client, mock_user):
        """Test recent traces with default limit and offset."""
        # Setup mocks - create multiple trace cells
        
        
        traces = []
        for i in range(15):
            trace = Cell(
                id=f"trace_cell_{i}",
                assignee_id="user_123",
                notebook_item_type_id="conversation-trace-item",
                cellTypeId="conversation-trace-item",
                source_book_id="book-conversation-traces-v1",
                initial_data={
                    "conversation_id": f"conv_{i}",
                    "session_id": f"sess_{i}",
                    "user_message": f"Test message {i}",
                    "target_llm": "openai"
                },
                fragments=[{"stage": "test", "data": {}}],
                status=CellStatus.PENDING,
                createdAt=datetime(2025, 11, 18, 10, i, 0)
            )
            traces.append(trace)
        
        mock_db.find_many = AsyncMock(return_value=traces)
        
        # Make request (default limit=10, offset=0)
        response = client.get(
            "/api/traces/recent",
            
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 15  # Total count
        assert data["limit"] == 10  # Default limit
        assert data["offset"] == 0  # Default offset
        assert len(data["traces"]) == 10  # Should return 10 traces
        
        # Verify traces are sorted by date (most recent first)
        # The last trace (index 14) should be first in results
        assert data["traces"][0]["conversation_id"] == "conv_14"
    
    @patch('app.routers.traces_router.db')
    
    def test_get_recent_traces_with_pagination(self, mock_db, client, mock_user):
        """Test recent traces with custom limit and offset."""
        # Setup mocks
        
        
        traces = []
        for i in range(25):
            trace = Cell(
                id=f"trace_cell_{i}",
                assignee_id="user_123",
                notebook_item_type_id="conversation-trace-item",
                cellTypeId="conversation-trace-item",
                source_book_id="book-conversation-traces-v1",
                initial_data={
                    "conversation_id": f"conv_{i}",
                    "user_message": f"Message {i}"
                },
                fragments=[],
                status=CellStatus.PENDING,
                createdAt=datetime(2025, 11, 18, 10, i, 0)
            )
            traces.append(trace)
        
        mock_db.find_many = AsyncMock(return_value=traces)
        
        # Make request with custom pagination
        response = client.get(
            "/api/traces/recent?limit=5&offset=10",
            
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 25
        assert data["limit"] == 5
        assert data["offset"] == 10
        assert len(data["traces"]) == 5
        
        # Verify correct traces returned (sorted desc, then offset 10, limit 5)
        # Should return traces 14, 13, 12, 11, 10 (0-indexed: 24->14, skip 10, take 5)
        assert data["traces"][0]["conversation_id"] == "conv_14"
        assert data["traces"][4]["conversation_id"] == "conv_10"
    
    @patch('app.routers.traces_router.db')
    
    def test_get_recent_traces_empty_result(self, mock_db, client, mock_user):
        """Test recent traces when user has no traces."""
        # Setup mocks - no trace cells
        
        mock_db.find_many = AsyncMock(return_value=[])
        
        # Make request
        response = client.get(
            "/api/traces/recent",
            
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 0
        assert len(data["traces"]) == 0
    
    @patch('app.routers.traces_router.db')
    
    def test_get_recent_traces_filters_by_user(self, mock_db, client, mock_user):
        """Test that only traces for current user are returned."""
        # Setup mocks - mix of user's traces and other user's traces
        
        
        user_traces = [
            Cell(
                id=f"trace_user_123_{i}",
                assignee_id="user_123",
                notebook_item_type_id="conversation-trace-item",
                cellTypeId="conversation-trace-item",
                source_book_id="book-conversation-traces-v1",
                initial_data={"conversation_id": f"conv_user_{i}"},
                fragments=[],
                status=CellStatus.PENDING,
                createdAt=datetime.utcnow()
            )
            for i in range(3)
        ]
        
        other_user_traces = [
            Cell(
                id=f"trace_user_456_{i}",
                assignee_id="user_456",  # Different user
                notebook_item_type_id="conversation-trace-item",
                cellTypeId="conversation-trace-item",
                source_book_id="book-conversation-traces-v1",
                initial_data={"conversation_id": f"conv_other_{i}"},
                fragments=[],
                status=CellStatus.PENDING,
                createdAt=datetime.utcnow()
            )
            for i in range(5)
        ]
        
        mock_db.find_many = AsyncMock(return_value=user_traces + other_user_traces)
        
        # Make request
        response = client.get(
            "/api/traces/recent",
            
        )
        
        # Assertions - should only return current user's traces
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 3  # Only 3 traces for user_123
        assert len(data["traces"]) == 3
        
        # Verify all returned traces belong to current user
        for trace in data["traces"]:
            assert trace["trace_id"].startswith("trace_user_123_")
    
    @patch('app.routers.traces_router.db')
    
    def test_get_recent_traces_truncates_long_message(self, mock_db, client, mock_user):
        """Test that long user messages are truncated in summaries."""
        # Setup mocks
        
        
        long_message = "A" * 150  # 150 character message
        trace = Cell(
            id="trace_long_msg",
            assignee_id="user_123",
            notebook_item_type_id="conversation-trace-item",
            cellTypeId="conversation-trace-item",
            source_book_id="book-conversation-traces-v1",
            initial_data={
                "conversation_id": "conv_long",
                "user_message": long_message
            },
            fragments=[],
            status=CellStatus.PENDING,
            createdAt=datetime.utcnow()
        )
        
        mock_db.find_many = AsyncMock(return_value=[trace])
        
        # Make request
        response = client.get(
            "/api/traces/recent",
            
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Message should be truncated to 100 chars + "..."
        assert len(data["traces"][0]["user_message"]) == 103  # 100 + "..."
        assert data["traces"][0]["user_message"].endswith("...")
    
    def test_get_recent_traces_invalid_limit(self, client):
        """Test validation of limit parameter (must be 1-100)."""
        # Test limit too low
        response = client.get(
            "/api/traces/recent?limit=0",
            
        )
        assert response.status_code == 422  # Validation error
        
        # Test limit too high
        response = client.get(
            "/api/traces/recent?limit=101",
            
        )
        assert response.status_code == 422  # Validation error
    
    def test_get_recent_traces_invalid_offset(self, client):
        """Test validation of offset parameter (must be >= 0)."""
        response = client.get(
            "/api/traces/recent?offset=-1",
            
        )
        assert response.status_code == 422  # Validation error
    
    @patch('app.routers.traces_router.db')
    
    def test_get_recent_traces_database_error(self, mock_db, client, mock_user):
        """Test error handling when database query fails."""
        # Setup mocks - raise exception
        
        mock_db.find_many.side_effect = Exception("Database error")
        
        # Make request
        response = client.get(
            "/api/traces/recent",
            
        )
        
        # Assertions
        assert response.status_code == 500
        assert "Error retrieving recent traces" in response.json()["detail"]
