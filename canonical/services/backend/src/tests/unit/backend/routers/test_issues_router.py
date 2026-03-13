"""
Unit tests for issues_router.py

Tests cover:
- POST /issues/ingest - Trigger manual ingestion
- POST /issues/process - Trigger manual processing
- POST /issues/monitoring/start - Start automatic monitoring
- POST /issues/monitoring/stop - Stop automatic monitoring
- POST /issues/processing/pause - Pause queue processing
- POST /issues/processing/resume - Resume queue processing

Technical naming: All functions and variables in English.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path

from app.main import app


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator instance with async methods."""
    orch = Mock()
    orch.force_process_pending_issues = AsyncMock(return_value={
        "status": "processing_triggered",
        "message": "Processing triggered",
        "pending_count": 5
    })
    orch.start_monitoring = AsyncMock(return_value={"status": "monitoring_started"})
    orch.stop_monitoring = AsyncMock(return_value={"status": "monitoring_stopped"})
    orch.pause_processing = AsyncMock(return_value={"status": "processing_paused"})
    orch.resume_processing = AsyncMock(return_value={"status": "processing_resumed"})
    return orch


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up dependency overrides."""
    yield
    app.dependency_overrides.clear()


class TestIngestEndpoint:
    """Tests for POST /issues/ingest endpoint."""
    
    @patch('app.routers.issues_router.BASE_DIR', Path('/test/base'))
    @patch('app.routers.issues_router.subprocess.Popen')
    def test_ingest_success_basic(self, mock_popen, client):
        """Test successful ingest trigger."""
        # Mock the ingest.py file exists
        with patch('app.routers.issues_router.BASE_DIR', Path('/test/base')):
            with patch.object(Path, 'exists', return_value=True):
                mock_process = Mock()
                mock_process.pid = 12345
                mock_popen.return_value = mock_process
                
                response = client.post("/api/issues/ingest", json={
                    "source_dir": None,
                    "dry_run": False
                })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data
        assert "12345" in data["message"]
    
    @patch('app.routers.issues_router.BASE_DIR', Path('/test/base'))
    @patch('app.routers.issues_router.subprocess.Popen')
    def test_ingest_with_source_dir(self, mock_popen, client):
        """Test ingest with custom source directory."""
        with patch.object(Path, 'exists', return_value=True):
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process
            
            response = client.post("/api/issues/ingest", json={
                "source_dir": "/custom/dir",
                "dry_run": False
            })
        
        assert response.status_code == 200
        # Verify Popen was called with source_dir argument
        call_args = mock_popen.call_args[0][0]
        assert "--source-dir" in call_args
        assert "/custom/dir" in call_args
    
    @patch('app.routers.issues_router.BASE_DIR', Path('/test/base'))
    @patch('app.routers.issues_router.subprocess.Popen')
    def test_ingest_dry_run(self, mock_popen, client):
        """Test ingest with dry run enabled."""
        with patch.object(Path, 'exists', return_value=True):
            mock_process = Mock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process
            
            response = client.post("/api/issues/ingest", json={
                "source_dir": None,
                "dry_run": True
            })
        
        assert response.status_code == 200
        # Verify Popen was called with --dry-run argument
        call_args = mock_popen.call_args[0][0]
        assert "--dry-run" in call_args
    
    @patch('app.routers.issues_router.BASE_DIR', Path('/test/base'))
    def test_ingest_script_not_found(self, client):
        """Test ingest when script doesn't exist."""
        with patch.object(Path, 'exists', return_value=False):
            response = client.post("/api/issues/ingest", json={
                "source_dir": None,
                "dry_run": False
            })
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


class TestProcessEndpoint:
    """Tests for POST /issues/process endpoint."""
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_process_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful manual processing trigger."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues/process")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["processed"] == 5
        mock_orchestrator.force_process_pending_issues.assert_called_once()
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_process_no_pending_cells(self, mock_get_orch, mock_orchestrator, client):
        """Test processing with no pending cells."""
        mock_orchestrator.force_process_pending_issues.return_value = {
            "status": "no_pending_cells",
            "message": "No pending cells",
            "pending_count": 0
        }
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues/process")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["processed"] == 0
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_process_orchestrator_not_available(self, mock_get_orch, client):
        """Test processing when orchestrator is not available."""
        mock_get_orch.return_value = None
        
        response = client.post("/api/issues/process")
        
        assert response.status_code == 503
        data = response.json()
        assert "not running" in data["detail"].lower()


class TestMonitoringStartEndpoint:
    """Tests for POST /issues/monitoring/start endpoint."""
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_monitoring_start_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful monitoring start."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues/monitoring/start")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "monitoring_started"
        mock_orchestrator.start_monitoring.assert_called_once()
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_monitoring_start_orchestrator_not_available(self, mock_get_orch, client):
        """Test monitoring start when orchestrator not available."""
        mock_get_orch.return_value = None
        
        response = client.post("/api/issues/monitoring/start")
        
        assert response.status_code == 503
        data = response.json()
        assert "not initialized" in data["detail"].lower()


class TestMonitoringStopEndpoint:
    """Tests for POST /issues/monitoring/stop endpoint."""
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_monitoring_stop_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful monitoring stop."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues/monitoring/stop")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "monitoring_stopped"
        mock_orchestrator.stop_monitoring.assert_called_once()
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_monitoring_stop_orchestrator_not_available(self, mock_get_orch, client):
        """Test monitoring stop when orchestrator not available."""
        mock_get_orch.return_value = None
        
        response = client.post("/api/issues/monitoring/stop")
        
        assert response.status_code == 503


class TestProcessingPauseEndpoint:
    """Tests for POST /issues/processing/pause endpoint."""
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_processing_pause_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful processing pause."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues/processing/pause")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing_paused"
        mock_orchestrator.pause_processing.assert_called_once()
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_processing_pause_orchestrator_not_available(self, mock_get_orch, client):
        """Test processing pause when orchestrator not available."""
        mock_get_orch.return_value = None
        
        response = client.post("/api/issues/processing/pause")
        
        assert response.status_code == 503


class TestProcessingResumeEndpoint:
    """Tests for POST /issues/processing/resume endpoint."""
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_processing_resume_success(self, mock_get_orch, mock_orchestrator, client):
        """Test successful processing resume."""
        mock_get_orch.return_value = mock_orchestrator
        
        response = client.post("/api/issues/processing/resume")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing_resumed"
        mock_orchestrator.resume_processing.assert_called_once()
    
    @patch('app.routers.issues_router.get_orchestrator_instance')
    def test_processing_resume_orchestrator_not_available(self, mock_get_orch, client):
        """Test processing resume when orchestrator not available."""
        mock_get_orch.return_value = None
        
        response = client.post("/api/issues/processing/resume")
        
        assert response.status_code == 503
