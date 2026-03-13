"""
Unit tests for monitoring router.

Tests Sprint 3 monitoring endpoints including:
- Pipeline health status
- Prerequisites validation
- Aggregated metrics
- Complete monitoring data
- Health monitoring control
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routers.monitoring_router import monitoring_router
from app.models.users import User
from app.permissions import has_permission
from scripts.pipeline_monitoring.validator import (
    PipelineValidator,
    PrerequisiteResult,
    PrerequisiteStatus,
    Criticality
)
from scripts.pipeline_monitoring.health_checker import (
    HealthChecker,
    HealthCheckResult,
    ComponentHealth
)
from scripts.pipeline_monitoring.metrics_collector import (
    MetricsCollector,
    AggregatedMetrics
)


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user for testing."""
    return User(
        id="test-admin",
        name="Test Admin",
        email="admin@test.com",
        roles=["admin"],  # Admin role bypasses permission checks
        permissions=["*"]
    )


@pytest.fixture
def app(mock_admin_user):
    """Create a test FastAPI application with monitoring router."""
    from app.auth import get_current_user_required
    
    test_app = FastAPI()
    test_app.include_router(monitoring_router, prefix="/api")
    
    # Override auth dependency to return mock admin user
    async def mock_get_current_user():
        return mock_admin_user
    
    test_app.dependency_overrides[get_current_user_required] = mock_get_current_user
    
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_health_results():
    """Mock health check results."""
    return [
        HealthCheckResult(
            component="frontend",
            status=ComponentHealth.HEALTHY,
            latency_ms=12.5,
            details={},
            timestamp=1735550000.0
        ),
        HealthCheckResult(
            component="backend_api",
            status=ComponentHealth.HEALTHY,
            latency_ms=8.3,
            details={},
            timestamp=1735550000.0
        ),
        HealthCheckResult(
            component="mongodb",
            status=ComponentHealth.DEGRADED,
            latency_ms=150.2,
            details={"warning": "high latency"},
            timestamp=1735550000.0
        )
    ]


@pytest.fixture
def mock_prerequisite_results():
    """Mock prerequisite validation results."""
    return [
        PrerequisiteResult(
            id="frontend.use_cell_factory",
            name="useCellFactory Composable",
            category="frontend",
            status=PrerequisiteStatus.HEALTHY,
            criticality=Criticality.CRITICAL,
            validation_method="import_check",
            monitoring_available=True,
            details={"available": True},
            timestamp=1735550000.0
        ),
        PrerequisiteResult(
            id="extension.installed",
            name="Extension Installed",
            category="extension",
            status=PrerequisiteStatus.UNHEALTHY,
            criticality=Criticality.CRITICAL,
            validation_method="ping_check",
            monitoring_available=True,
            details={"error": "Extension not responding"},
            timestamp=1735550000.0
        )
    ]


@pytest.fixture
def mock_metrics():
    """Mock aggregated metrics."""
    return AggregatedMetrics(
        generation_metrics={
            "total_generations": 150,
            "success_rate": 95.5,
            "avg_generation_time_ms": 2450.0,
            "active_generations": 3
        },
        component_health={
            "frontend": "healthy",
            "backend": "healthy",
            "mongodb": "degraded"
        },
        latency_metrics={
            "extension_latency_p50_ms": 45.2,
            "extension_latency_p95_ms": 120.5,
            "extension_latency_p99_ms": 250.0
        },
        resource_metrics={
            "opfs_quota_used_percent": 35.5,
            "opfs_available_mb": 512.0
        },
        timestamp=1735550000.0
    )


class TestPipelineHealthEndpoint:
    """Tests for /api/monitoring/pipeline/health endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_pipeline_health_all_healthy(self, client, mock_health_results):
        """Test health endpoint when all components are healthy."""
        # Modify mock to have all healthy
        for result in mock_health_results:
            result.status = ComponentHealth.HEALTHY
        
        with patch("app.routers.monitoring_router.get_health_checker") as mock_get_hc:
            mock_checker = AsyncMock()
            mock_checker.check_all_components = AsyncMock(return_value=mock_health_results)
            mock_get_hc.return_value = mock_checker
            
            response = client.get("/api/monitoring/pipeline/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "healthy"
            assert "components" in data
            assert len(data["components"]) == 3
            assert data["timestamp"] is not None
    
    @pytest.mark.asyncio
    async def test_get_pipeline_health_with_degraded(self, client, mock_health_results):
        """Test health endpoint when some components are degraded."""
        with patch("app.routers.monitoring_router.get_health_checker") as mock_get_hc:
            mock_checker = AsyncMock()
            mock_checker.check_all_components = AsyncMock(return_value=mock_health_results)
            mock_get_hc.return_value = mock_checker
            
            response = client.get("/api/monitoring/pipeline/health")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "degraded"
            assert "components" in data
            
            # Check that degraded component is included
            degraded_components = [c for c in data["components"] if c["status"] == "degraded"]
            assert len(degraded_components) == 1
            assert degraded_components[0]["component"] == "mongodb"
    
    @pytest.mark.asyncio
    async def test_get_pipeline_health_error_handling(self, client):
        """Test health endpoint error handling."""
        with patch("app.routers.monitoring_router.get_health_checker") as mock_get_hc:
            mock_checker = AsyncMock()
            mock_checker.check_all_components = AsyncMock(side_effect=Exception("Health check failed"))
            mock_get_hc.return_value = mock_checker
            
            response = client.get("/api/monitoring/pipeline/health")
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data


class TestPrerequisitesEndpoint:
    """Tests for /api/monitoring/pipeline/prerequisites endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_prerequisites_success(self, client, mock_prerequisite_results):
        """Test prerequisites endpoint returns validation results."""
        with patch("app.routers.monitoring_router.get_validator") as mock_get_val:
            mock_validator = AsyncMock()
            mock_validator.validate_all = AsyncMock(return_value=mock_prerequisite_results)
            mock_get_val.return_value = mock_validator
            
            response = client.get("/api/monitoring/pipeline/prerequisites")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "prerequisites" in data
            assert "summary" in data
            assert len(data["prerequisites"]) == 2
            
            # Check summary
            summary = data["summary"]
            assert summary["total"] == 2
            assert summary["healthy"] == 1
            assert summary["unhealthy"] == 1
            assert summary["degraded"] == 0
            assert summary["unknown"] == 0
    
    @pytest.mark.asyncio
    async def test_get_prerequisites_with_categories(self, client, mock_prerequisite_results):
        """Test that prerequisites include category information."""
        with patch("app.routers.monitoring_router.get_validator") as mock_get_val:
            mock_validator = AsyncMock()
            mock_validator.validate_all = AsyncMock(return_value=mock_prerequisite_results)
            mock_get_val.return_value = mock_validator
            
            response = client.get("/api/monitoring/pipeline/prerequisites")
            
            assert response.status_code == 200
            data = response.json()
            
            prerequisites = data["prerequisites"]
            categories = set(p["category"] for p in prerequisites)
            
            assert "frontend" in categories
            assert "extension" in categories


class TestMetricsEndpoint:
    """Tests for /api/monitoring/pipeline/metrics endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_metrics_success(self, client, mock_metrics):
        """Test metrics endpoint returns aggregated metrics."""
        with patch("app.routers.monitoring_router.get_metrics_collector") as mock_get_mc:
            mock_collector = MagicMock()
            mock_collector.get_aggregated_metrics = MagicMock(return_value=mock_metrics)
            mock_get_mc.return_value = mock_collector
            
            response = client.get("/api/monitoring/pipeline/metrics")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "generation_metrics" in data
            assert "component_health" in data
            assert "latency_metrics" in data
            assert "resource_metrics" in data
            assert "timestamp" in data
            
            # Verify generation metrics
            gen_metrics = data["generation_metrics"]
            assert gen_metrics["total_generations"] == 150
            assert gen_metrics["success_rate"] == 95.5
            assert gen_metrics["active_generations"] == 3


class TestCompleteMonitoringEndpoint:
    """Tests for /api/monitoring/pipeline endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_complete_monitoring_success(
        self, 
        client, 
        mock_health_results, 
        mock_prerequisite_results, 
        mock_metrics
    ):
        """Test complete monitoring endpoint returns all data."""
        with patch("app.routers.monitoring_router.get_validator") as mock_get_val, \
             patch("app.routers.monitoring_router.get_health_checker") as mock_get_hc, \
             patch("app.routers.monitoring_router.get_metrics_collector") as mock_get_mc:
            
            mock_validator = AsyncMock()
            mock_validator.validate_all = AsyncMock(return_value=mock_prerequisite_results)
            mock_get_val.return_value = mock_validator
            
            mock_checker = AsyncMock()
            mock_checker.check_all_components = AsyncMock(return_value=mock_health_results)
            mock_get_hc.return_value = mock_checker
            
            mock_collector = MagicMock()
            mock_collector.get_aggregated_metrics = MagicMock(return_value=mock_metrics)
            mock_get_mc.return_value = mock_collector
            
            response = client.get("/api/monitoring/pipeline")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check all sections present
            assert "prerequisites" in data
            assert "components" in data
            assert "metrics" in data
            assert "summary" in data
            
            # Verify summary
            summary = data["summary"]
            assert "overall_status" in summary
            assert "prerequisites_healthy" in summary
            assert "prerequisites_total" in summary
            assert "components_healthy" in summary
            assert "components_total" in summary
            
            assert summary["prerequisites_total"] == 2
            assert summary["components_total"] == 3


class TestHealthMonitoringControlEndpoints:
    """Tests for health monitoring start/stop endpoints."""
    
    @pytest.mark.asyncio
    async def test_start_health_monitoring(self, client):
        """Test starting periodic health checks."""
        with patch("app.routers.monitoring_router.get_health_checker") as mock_get_hc:
            mock_checker = AsyncMock()
            mock_checker.start_monitoring = AsyncMock()
            mock_checker.interval_seconds = 30
            mock_get_hc.return_value = mock_checker
            
            response = client.post("/api/monitoring/pipeline/health/start")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "started"
            assert data["interval_seconds"] == 30
            mock_checker.start_monitoring.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_health_monitoring(self, client):
        """Test stopping periodic health checks."""
        with patch("app.routers.monitoring_router.get_health_checker") as mock_get_hc:
            mock_checker = AsyncMock()
            mock_checker.stop_monitoring = AsyncMock()
            mock_get_hc.return_value = mock_checker
            
            response = client.post("/api/monitoring/pipeline/health/stop")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "stopped"
            mock_checker.stop_monitoring.assert_called_once()


class TestMonitoringRouterIntegration:
    """Integration tests for monitoring router."""
    
    @pytest.mark.asyncio
    async def test_all_endpoints_accessible(self, client):
        """Test that all monitoring endpoints are accessible."""
        endpoints = [
            "/api/monitoring/pipeline/health",
            "/api/monitoring/pipeline/prerequisites",
            "/api/monitoring/pipeline/metrics",
            "/api/monitoring/pipeline"
        ]
        
        for endpoint in endpoints:
            # Just check that endpoints are registered and accessible
            # They will return errors due to missing mocks, but should not 404
            response = client.get(endpoint)
            assert response.status_code != 404, f"Endpoint {endpoint} returned 404"
