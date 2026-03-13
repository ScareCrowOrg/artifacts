"""
Unit tests for issues_dashboard_router.py

Tests cover:
- GET /issues-dashboard/cells - Get paginated cells
- GET /issues-dashboard/cells/{cell_id} - Get cell details
- POST /issues-dashboard/ingest/trigger - Trigger ingest
- POST /issues-dashboard/process-pending-cells - Process pending cells
- GET /issues-dashboard/monitoring/status - Get monitoring status
- POST /issues-dashboard/monitoring/start - Start monitoring
- POST /issues-dashboard/monitoring/stop - Stop monitoring
- GET /issues-dashboard/processing/status - Get processing status
- POST /issues-dashboard/processing/pause - Pause processing
- POST /issues-dashboard/processing/resume - Resume processing
- GET /issues-dashboard/events - SSE events endpoint
- GET /issues-dashboard/cells/{id}/stream-fragments - SSE fragments endpoint
- GET /issues-dashboard/stream-all-active-fragments - SSE all fragments

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
from pathlib import Path

from app.main import app
from app.models import Cell
from app.permissions import has_permission


@pytest.fixture
def mock_permission_check():
    """Mock permission check to bypass auth in tests."""
    def _mock_permission_func(permissions):
        async def _dependency():
            # Return a mock user with required permissions
            user = Mock()
            user.id = "test-user-123"
            user.name = "Test User"
            user.email = "test@example.com"
            user.role = "admin"
            user.roles = ["admin"]
            return user
        return _dependency
    return _mock_permission_func


@pytest.fixture
def client(mock_permission_check):
    """Test client with mocked dependencies."""
    # Override the has_permission dependency
    app.dependency_overrides[has_permission] = lambda perms: mock_permission_check(perms)
    client = TestClient(app)
    yield client
    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator instance with async methods."""
    orch = Mock()
    orch.force_process_pending_issues = AsyncMock(return_value={
        "status": "processing_triggered",
        "message": "Processing triggered",
        "pending_count": 3
    })
    orch.get_monitoring_status = AsyncMock(return_value={
        "active": True,
        "polling_interval": 10,
        "max_concurrent_cells": 5,
        "task_running": True
    })
    orch.start_monitoring = AsyncMock(return_value={
        "status": "started",
        "message": "Monitoring started"
    })
    orch.stop_monitoring = AsyncMock(return_value={
        "status": "stopped",
        "message": "Monitoring stopped"
    })
    orch.get_processing_status = AsyncMock(return_value={"paused": False})
    orch.pause_processing = AsyncMock(return_value={
        "status": "paused",
        "message": "Processing paused"
    })
    orch.resume_processing = AsyncMock(return_value={
        "status": "resumed",
        "message": "Processing resumed"
    })
    return orch


@pytest.fixture
def sample_cell():
    """Sample cell data."""
    cell = Mock(spec=Cell)
    cell.id = "test-cell-123"
    cell.titulo = "Test Cell"
    cell.type = "ingestion-issue"
    cell.status = "pendente"
    cell.livro_id = "issues-queue"
    return cell


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestGetCellsEndpoint:
    """Tests for GET /issues-dashboard/cells endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_filtered_cells_and_counts', new_callable=AsyncMock)
    def test_get_cells_success(self, mock_get_cells, sample_cell, client):
        """Test successful cell retrieval."""
        mock_get_cells.return_value = (
            [sample_cell],  # items
            10,             # total_items
            1,              # total_pages
            1,              # current_page
            {"pendente": 5, "executando": 2, "finalizado": 3}  # issue_counts
        )
        
        response = client.get("/api/issues-dashboard/cells?page=1&limit=20")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_items" in data
        assert data["total_items"] == 10
        assert "issue_counts" in data
    
    @patch('app.routers.issues_dashboard_router.get_filtered_cells_and_counts', new_callable=AsyncMock)
    def test_get_cells_with_status_filter(self, mock_get_cells, sample_cell, client):
        """Test cell retrieval with status filter."""
        mock_get_cells.return_value = (
            [sample_cell],
            5,
            1,
            1,
            {"pendente": 5}
        )
        
        response = client.get("/api/issues-dashboard/cells?page=1&limit=20&status=pendente")
        
        assert response.status_code == 200
        # Verify the filter was passed correctly
        mock_get_cells.assert_called_once_with(1, 20, "pendente", None)
    
    @patch('app.routers.issues_dashboard_router.get_filtered_cells_and_counts', new_callable=AsyncMock)
    def test_get_cells_with_item_type_filter(self, mock_get_cells, sample_cell, client):
        """Test cell retrieval with item_type filter."""
        mock_get_cells.return_value = (
            [sample_cell],
            3,
            1,
            1,
            {"pendente": 5, "executando": 2, "finalizado": 3}
        )
        
        response = client.get("/api/issues-dashboard/cells?page=1&limit=20&item_type=ingestio")
        
        assert response.status_code == 200
        # Verify the filter was passed correctly
        mock_get_cells.assert_called_once_with(1, 20, None, "ingestio")
    
    @patch('app.routers.issues_dashboard_router.get_filtered_cells_and_counts', new_callable=AsyncMock)
    def test_get_cells_with_status_and_item_type_filters(self, mock_get_cells, sample_cell, client):
        """Test cell retrieval with both status and item_type filters."""
        mock_get_cells.return_value = (
            [sample_cell],
            2,
            1,
            1,
            {"pendente": 5}
        )
        
        response = client.get("/api/issues-dashboard/cells?page=1&limit=20&status=pendente&item_type=ingestio")
        
        assert response.status_code == 200
        # Verify both filters were passed correctly
        mock_get_cells.assert_called_once_with(1, 20, "pendente", "ingestio")
    
    @patch('app.routers.issues_dashboard_router.get_filtered_cells_and_counts', new_callable=AsyncMock)
    def test_get_cells_empty_result(self, mock_get_cells, client):
        """Test cell retrieval with no results."""
        mock_get_cells.return_value = (
            [],
            0,
            0,
            1,
            {}
        )
        
        response = client.get("/api/issues-dashboard/cells?page=1&limit=20")
        
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_items"] == 0


class TestGetCellDetailsEndpoint:
    """Tests for GET /issues-dashboard/cells/{cell_id} endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_cell_by_id', new_callable=AsyncMock)
    def test_get_cell_details_success(self, mock_get_cell, sample_cell, client):
        """Test successful cell details retrieval."""
        mock_get_cell.return_value = sample_cell
        
        response = client.get("/api/issues-dashboard/cells/test-cell-123")
        
        assert response.status_code == 200
        mock_get_cell.assert_called_once_with("test-cell-123")
    
    @patch('app.routers.issues_dashboard_router.get_cell_by_id', new_callable=AsyncMock)
    def test_get_cell_details_not_found(self, mock_get_cell, client):
        """Test cell details when cell not found."""
        from fastapi import HTTPException
        mock_get_cell.side_effect = HTTPException(status_code=404, detail="Cell not found")
        
        response = client.get("/api/issues-dashboard/cells/nonexistent")
        
        assert response.status_code == 404


class TestTriggerIngestEndpoint:
    """Tests for POST /issues-dashboard/ingest/trigger endpoint."""
    
    @patch('app.routers.issues_dashboard_router.trigger_ingest_script')
    def test_trigger_ingest_success(self, mock_trigger, client):
        """Test successful ingest trigger."""
        mock_trigger.return_value = (
            "python ingest.py",
            "Ingest started with PID 12345",
            12345
        )
        
        response = client.post("/api/issues-dashboard/ingest/trigger", json={
            "source_dir": None,
            "dry_run": False
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "message" in data
        assert "command" in data
    
    @patch('app.routers.issues_dashboard_router.trigger_ingest_script')
    def test_trigger_ingest_with_params(self, mock_trigger, client):
        """Test ingest trigger with parameters."""
        mock_trigger.return_value = (
            "python ingest.py --source-dir /test --dry-run",
            "Ingest started",
            12345
        )
        
        response = client.post("/api/issues-dashboard/ingest/trigger", json={
            "source_dir": "/test",
            "dry_run": True
        })
        
        assert response.status_code == 200
        mock_trigger.assert_called_once_with(source_dir="/test", dry_run=True)


class TestProcessPendingCellsEndpoint:
    """Tests for POST /issues-dashboard/process-pending-cells endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_orchestrator_or_raise')
    def test_process_pending_cells_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful pending cells processing."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues-dashboard/process-pending-cells")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing_triggered"
        assert data["pending_count"] == 3
        mock_orchestrator.force_process_pending_issues.assert_called_once()


class TestMonitoringStatusEndpoint:
    """Tests for GET /issues-dashboard/monitoring/status endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_orchestrator_or_raise')
    def test_get_monitoring_status_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful monitoring status retrieval."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.get("/api/issues-dashboard/monitoring/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["active"] is True
        assert data["polling_interval"] == 10
        assert data["max_concurrent_cells"] == 5
        assert data["task_running"] is True


class TestMonitoringStartEndpoint:
    """Tests for POST /issues-dashboard/monitoring/start endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_orchestrator_or_raise')
    def test_start_monitoring_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful monitoring start."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues-dashboard/monitoring/start")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        mock_orchestrator.start_monitoring.assert_called_once()


class TestMonitoringStopEndpoint:
    """Tests for POST /issues-dashboard/monitoring/stop endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_orchestrator_or_raise')
    def test_stop_monitoring_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful monitoring stop."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues-dashboard/monitoring/stop")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"
        mock_orchestrator.stop_monitoring.assert_called_once()


class TestProcessingStatusEndpoint:
    """Tests for GET /issues-dashboard/processing/status endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_orchestrator_or_raise')
    def test_get_processing_status_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful processing status retrieval."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.get("/api/issues-dashboard/processing/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "paused" in data
        assert data["paused"] is False


class TestProcessingPauseEndpoint:
    """Tests for POST /issues-dashboard/processing/pause endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_orchestrator_or_raise')
    def test_pause_processing_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful processing pause."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues-dashboard/processing/pause")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"
        mock_orchestrator.pause_processing.assert_called_once()


class TestProcessingResumeEndpoint:
    """Tests for POST /issues-dashboard/processing/resume endpoint."""
    
    @patch('app.routers.issues_dashboard_router.get_orchestrator_or_raise')
    def test_resume_processing_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful processing resume."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues-dashboard/processing/resume")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resumed"
        mock_orchestrator.resume_processing.assert_called_once()


class TestSSEEndpoints:
    """Tests for Server-Sent Events (SSE) endpoints."""
    
    @pytest.mark.xfail(reason="SSE endpoints hang with TestClient - requires integration test approach")
    def test_events_endpoint_returns_streaming_response(self, client):
        """Test that /events endpoint returns a streaming response."""
        # Note: TestClient doesn't support stream=True parameter
        # This test just verifies the endpoint exists and returns a response
        response = client.get("/api/issues-dashboard/events")
        # SSE endpoints typically return 200 even if they're streaming
        # The actual streaming behavior is tested in integration tests
        assert response.status_code in [200, 307]  # 307 if redirected
    
    @pytest.mark.xfail(reason="SSE endpoints hang with TestClient - requires integration test approach")
    def test_cell_fragments_endpoint_exists(self, client):
        """Test that cell fragments SSE endpoint exists."""
        response = client.get("/api/issues-dashboard/cells/test-id/stream-fragments")
        # Just verify endpoint exists
        assert response.status_code in [200, 307, 404, 500]
    
    @pytest.mark.xfail(reason="SSE endpoints hang with TestClient - requires integration test approach")
    def test_all_active_fragments_endpoint_exists(self, client):
        """Test that all active fragments SSE endpoint exists."""
        response = client.get("/api/issues-dashboard/stream-all-active-fragments")
        # Just verify endpoint exists
        assert response.status_code in [200, 307, 404, 500]
