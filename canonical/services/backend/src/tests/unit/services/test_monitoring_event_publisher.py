"""
Unit tests for Monitoring Event Publisher.

Tests WebSocket event publishing for real-time monitoring updates.
Sprint 3: WebSocket Streaming for Pipeline Monitoring Cell
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.monitoring_event_publisher import MonitoringEventPublisher
from scripts.pipeline_monitoring.health_checker import HealthCheckResult, ComponentHealth
from app.models.event_bus import EventTopic


@pytest.fixture
def mock_pubsub_service():
    """Mock Redis pub/sub service."""
    mock_service = AsyncMock()
    mock_service.publish = AsyncMock(return_value=True)
    return mock_service


@pytest.fixture
def health_results():
    """Sample health check results."""
    return [
        HealthCheckResult(
            component="frontend",
            status=ComponentHealth.HEALTHY,
            latency_ms=12.5,
            details={},
            timestamp=1735550000.0
        )
    ]


class TestMonitoringEventPublisher:
    """Tests for MonitoringEventPublisher class."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, mock_pubsub_service):
        """Test publisher initialization."""
        with patch("app.services.monitoring_event_publisher.get_pubsub_service") as mock_get_pubsub:
            mock_get_pubsub.return_value = mock_pubsub_service
            
            publisher = MonitoringEventPublisher()
            await publisher.initialize()
            
            assert publisher._initialized is True
    
    @pytest.mark.asyncio
    async def test_publish_health_update(self, mock_pubsub_service, health_results):
        """Test publishing health update events."""
        with patch("app.services.monitoring_event_publisher.get_pubsub_service") as mock_get_pubsub:
            mock_get_pubsub.return_value = mock_pubsub_service
            
            publisher = MonitoringEventPublisher()
            await publisher.initialize()
            await publisher.publish_health_update(health_results)
            
            mock_pubsub_service.publish.assert_called_once()
            call_args = mock_pubsub_service.publish.call_args[0][0]
            assert call_args.topic == EventTopic.MONITORING_HEALTH_UPDATE.value
