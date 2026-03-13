"""
Unit tests for health checker

Path to scripts is configured in tests/unit/scripts/conftest.py
"""

import pytest
import asyncio
import time

from pipeline_monitoring.health_checker import (
    HealthChecker,
    ComponentHealth,
    HealthCheckResult
)


class TestHealthChecker:
    """Test suite for HealthChecker"""
    
    @pytest.fixture
    def health_checker(self):
        """Create a health checker instance"""
        return HealthChecker(interval_seconds=1)  # Short interval for testing
    
    def test_health_checker_initialization(self, health_checker):
        """Test health checker initializes correctly"""
        assert health_checker is not None
        assert health_checker.interval_seconds == 1
        assert len(health_checker.components) == 7
        assert not health_checker._running
    
    def test_health_checker_components(self, health_checker):
        """Test health checker has all required components"""
        expected_components = [
            "frontend",
            "extension",
            "wasm_orchestrator",
            "backend_api",
            "mongodb",
            "redis",
            "llm_provider"
        ]
        
        assert health_checker.components == expected_components
    
    @pytest.mark.asyncio
    async def test_check_all_components(self, health_checker):
        """Test check_all_components returns results for all components"""
        results = await health_checker.check_all_components()
        
        assert len(results) == 7
        assert all(isinstance(r, HealthCheckResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_check_component(self, health_checker):
        """Test check_component for a specific component"""
        result = await health_checker.check_component("backend_api")
        
        assert isinstance(result, HealthCheckResult)
        assert result.component == "backend_api"
        assert isinstance(result.status, ComponentHealth)
        assert result.latency_ms >= 0
        assert isinstance(result.details, dict)
        assert result.timestamp > 0
    
    @pytest.mark.asyncio
    async def test_health_check_result_structure(self, health_checker):
        """Test HealthCheckResult has correct structure"""
        results = await health_checker.check_all_components()
        
        for result in results:
            assert hasattr(result, "component")
            assert hasattr(result, "status")
            assert hasattr(result, "latency_ms")
            assert hasattr(result, "details")
            assert hasattr(result, "timestamp")
            assert isinstance(result.status, ComponentHealth)
    
    @pytest.mark.asyncio
    async def test_health_check_result_to_dict(self, health_checker):
        """Test HealthCheckResult can be converted to dict"""
        results = await health_checker.check_all_components()
        
        for result in results:
            result_dict = result.to_dict()
            assert isinstance(result_dict, dict)
            assert "component" in result_dict
            assert "status" in result_dict
            assert "latency_ms" in result_dict
            assert "details" in result_dict
            assert "timestamp" in result_dict
            assert isinstance(result_dict["status"], str)
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, health_checker):
        """Test starting and stopping monitoring"""
        assert not health_checker._running
        
        await health_checker.start_monitoring()
        assert health_checker._running
        assert health_checker._task is not None
        
        await asyncio.sleep(0.1)  # Let it run briefly
        
        await health_checker.stop_monitoring()
        assert not health_checker._running
    
    @pytest.mark.asyncio
    async def test_monitoring_loop_collects_results(self, health_checker):
        """Test monitoring loop collects health check results"""
        await health_checker.start_monitoring()
        
        # Wait for a couple of checks
        await asyncio.sleep(2.5)
        
        await health_checker.stop_monitoring()
        
        # Should have collected at least 2 sets of results
        assert len(health_checker._results_history) >= 2
    
    @pytest.mark.asyncio
    async def test_history_size_limit(self, health_checker):
        """Test results history respects size limit"""
        # Override interval for faster testing
        health_checker.interval_seconds = 0.01
        
        await health_checker.start_monitoring()
        
        # Wait long enough to exceed history size
        await asyncio.sleep(1.5)
        
        await health_checker.stop_monitoring()
        
        # History should not exceed 100 entries
        assert len(health_checker._results_history) <= 100
    
    def test_get_health_summary_no_data(self, health_checker):
        """Test get_health_summary with no data"""
        summary = health_checker.get_health_summary()
        
        assert summary["status"] == "no_data"
        assert summary["components"] == {}
        assert summary["last_check"] is None
    
    @pytest.mark.asyncio
    async def test_get_health_summary_with_data(self, health_checker):
        """Test get_health_summary with collected data"""
        # Collect some data
        results = await health_checker.check_all_components()
        health_checker._results_history.append(results)
        
        summary = health_checker.get_health_summary()
        
        assert "status" in summary
        assert "components" in summary
        assert "last_check" in summary
        assert "status_counts" in summary
        assert len(summary["components"]) == 7
    
    @pytest.mark.asyncio
    async def test_alert_callback_registration(self, health_checker):
        """Test registering alert callbacks"""
        callback_called = []
        
        async def test_callback(alert_data):
            callback_called.append(alert_data)
        
        health_checker.register_alert_callback(test_callback)
        
        assert len(health_checker._alert_callbacks) == 1
    
    @pytest.mark.asyncio
    async def test_check_backend_health(self, health_checker):
        """Test backend health check"""
        status, details = await health_checker._check_backend_health()
        
        assert isinstance(status, ComponentHealth)
        assert isinstance(details, dict)
        
        # Backend should be healthy if imports work
        if status == ComponentHealth.HEALTHY:
            assert "services_available" in details
    
    def test_component_health_enum(self):
        """Test ComponentHealth enum values"""
        assert ComponentHealth.HEALTHY.value == "healthy"
        assert ComponentHealth.DEGRADED.value == "degraded"
        assert ComponentHealth.UNHEALTHY.value == "unhealthy"
        assert ComponentHealth.UNKNOWN.value == "unknown"
    
    @pytest.mark.asyncio
    async def test_check_all_components_parallel(self, health_checker):
        """Test check_all_components executes in parallel"""
        start_time = time.time()
        
        results = await health_checker.check_all_components()
        
        elapsed_time = time.time() - start_time
        
        # Parallel execution should be fast
        assert elapsed_time < 2.0
        assert len(results) == 7
    
    @pytest.mark.asyncio
    async def test_latency_measurement(self, health_checker):
        """Test that latency is measured for health checks"""
        results = await health_checker.check_all_components()
        
        for result in results:
            # Latency should be non-negative and reasonable
            assert result.latency_ms >= 0
            assert result.latency_ms < 1000  # Should be less than 1 second
    
    @pytest.mark.asyncio
    async def test_error_handling_in_health_check(self, health_checker):
        """Test error handling in individual health checks"""
        # Override a check method to raise an error
        async def failing_check():
            raise ValueError("Test error")
        
        health_checker._check_backend_health = failing_check
        
        result = await health_checker.check_component("backend_api")
        
        # Should return unhealthy status, not raise exception
        assert result.status == ComponentHealth.UNHEALTHY
        assert "error" in result.details
    
    @pytest.mark.asyncio
    async def test_double_start_monitoring(self, health_checker):
        """Test starting monitoring when already running"""
        await health_checker.start_monitoring()
        assert health_checker._running
        
        # Starting again should be a no-op
        await health_checker.start_monitoring()
        assert health_checker._running
        
        await health_checker.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_stop_monitoring_when_not_running(self, health_checker):
        """Test stopping monitoring when not running"""
        assert not health_checker._running
        
        # Should not raise an error
        await health_checker.stop_monitoring()
        assert not health_checker._running
    
    @pytest.mark.asyncio
    async def test_health_summary_status_calculation(self, health_checker):
        """Test overall status calculation in health summary"""
        from unittest.mock import MagicMock
        
        # Create mock results with different statuses
        mock_results = [
            HealthCheckResult("comp1", ComponentHealth.HEALTHY, 10, {}, time.time()),
            HealthCheckResult("comp2", ComponentHealth.HEALTHY, 10, {}, time.time()),
            HealthCheckResult("comp3", ComponentHealth.DEGRADED, 10, {}, time.time()),
        ]
        
        health_checker._results_history.append(mock_results)
        summary = health_checker.get_health_summary()
        
        # Should be degraded because at least one component is degraded
        assert summary["status"] == "degraded"
        
        # Test with unhealthy component
        mock_results[0] = HealthCheckResult("comp1", ComponentHealth.UNHEALTHY, 10, {}, time.time())
        health_checker._results_history.append(mock_results)
        summary = health_checker.get_health_summary()
        
        # Should be unhealthy
        assert summary["status"] == "unhealthy"
