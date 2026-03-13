"""
Monitoring Event Publisher.

Publishes monitoring events to the event bus for real-time WebSocket streaming.
Sprint 3: WebSocket Streaming for Pipeline Monitoring Cell
"""

import logging
from typing import Any, Dict, List, Optional

from scripts.pipeline_monitoring.health_checker import HealthCheckResult
from scripts.pipeline_monitoring.metrics_collector import AggregatedMetrics
from scripts.pipeline_monitoring.validator import PrerequisiteResult

from ..models.event_bus import EventTopic, MessageEnvelope
from ..services.redis_pubsub_service import get_pubsub_service

logger = logging.getLogger(__name__)


class MonitoringEventPublisher:
    """
    Publishes monitoring events to Redis pub/sub for WebSocket streaming.

    Events:
    - monitoring/health/update: Component health check results
    - monitoring/metrics/update: Aggregated metrics updates
    - monitoring/prerequisite/update: Prerequisite validation results
    - monitoring/alert/triggered: Alert triggered notifications
    - monitoring/alert/resolved: Alert resolved notifications
    """

    def __init__(self):
        """Initialize the monitoring event publisher"""
        self._pubsub_service = None
        self._initialized = False

    async def initialize(self):
        """Initialize connection to pub/sub service"""
        if not self._initialized:
            try:
                self._pubsub_service = await get_pubsub_service()
                self._initialized = True
                logger.info("Monitoring event publisher initialized")
            except Exception as e:
                logger.error("Failed to initialize monitoring event publisher: %s", e)
                raise

    async def publish_health_update(self, health_results: List[HealthCheckResult]):
        """
        Publish component health update event.

        Args:
            health_results: List of health check results
        """
        if not self._initialized:
            await self.initialize()

        try:
            message = MessageEnvelope(
                source="monitoring-health-checker",
                topic=EventTopic.MONITORING_HEALTH_UPDATE.value,
                payload={
                    "components": [r.to_dict() for r in health_results],
                    "timestamp": health_results[0].timestamp
                    if health_results
                    else None,
                },
            )

            await self._pubsub_service.publish(message)
            logger.debug("Published health update: %s components", len(health_results))

        except Exception as e:
            logger.error("Error publishing health update: %s", e, exc_info=True)

    async def publish_metrics_update(self, metrics: AggregatedMetrics):
        """
        Publish aggregated metrics update event.

        Args:
            metrics: Aggregated metrics data
        """
        if not self._initialized:
            await self.initialize()

        try:
            message = MessageEnvelope(
                source="monitoring-metrics-collector",
                topic=EventTopic.MONITORING_METRICS_UPDATE.value,
                payload=metrics.to_dict(),
            )

            await self._pubsub_service.publish(message)
            logger.debug("Published metrics update")

        except Exception as e:
            logger.error("Error publishing metrics update: %s", e, exc_info=True)

    async def publish_prerequisite_update(
        self, prerequisite_results: List[PrerequisiteResult]
    ):
        """
        Publish prerequisite validation update event.

        Args:
            prerequisite_results: List of prerequisite validation results
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Calculate summary
            summary = {
                "total": len(prerequisite_results),
                "healthy": sum(
                    1 for r in prerequisite_results if r.status.value == "healthy"
                ),
                "degraded": sum(
                    1 for r in prerequisite_results if r.status.value == "degraded"
                ),
                "unhealthy": sum(
                    1 for r in prerequisite_results if r.status.value == "unhealthy"
                ),
                "unknown": sum(
                    1 for r in prerequisite_results if r.status.value == "unknown"
                ),
            }

            message = MessageEnvelope(
                source="monitoring-validator",
                topic=EventTopic.MONITORING_PREREQUISITE_UPDATE.value,
                payload={
                    "prerequisites": [r.to_dict() for r in prerequisite_results],
                    "summary": summary,
                },
            )

            await self._pubsub_service.publish(message)
            logger.debug("Published prerequisite update: %s prerequisites", len(prerequisite_results))

        except Exception as e:
            logger.error("Error publishing prerequisite update: %s", e, exc_info=True)

    async def publish_alert_triggered(
        self,
        alert_id: str,
        severity: str,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Publish alert triggered event.

        Args:
            alert_id: Unique alert identifier
            severity: Alert severity (critical, warning, info)
            title: Alert title
            message: Alert message
            details: Additional alert details
        """
        if not self._initialized:
            await self.initialize()

        try:
            alert_message = MessageEnvelope(
                source="monitoring-alerting",
                topic=EventTopic.MONITORING_ALERT_TRIGGERED.value,
                payload={
                    "alert_id": alert_id,
                    "severity": severity,
                    "title": title,
                    "message": message,
                    "details": details or {},
                    "triggered_at": None,  # Will be set by MessageEnvelope timestamp
                },
            )

            await self._pubsub_service.publish(alert_message)
            logger.info("Published alert triggered: %s (%s)", alert_id, severity)

        except Exception as e:
            logger.error("Error publishing alert triggered: %s", e, exc_info=True)

    async def publish_alert_resolved(
        self, alert_id: str, resolution_details: Optional[Dict[str, Any]] = None
    ):
        """
        Publish alert resolved event.

        Args:
            alert_id: Alert identifier that was resolved
            resolution_details: Details about how alert was resolved
        """
        if not self._initialized:
            await self.initialize()

        try:
            message = MessageEnvelope(
                source="monitoring-alerting",
                topic=EventTopic.MONITORING_ALERT_RESOLVED.value,
                payload={
                    "alert_id": alert_id,
                    "resolution_details": resolution_details or {},
                    "resolved_at": None,  # Will be set by MessageEnvelope timestamp
                },
            )

            await self._pubsub_service.publish(message)
            logger.info("Published alert resolved: %s", alert_id)

        except Exception as e:
            logger.error("Error publishing alert resolved: %s", e, exc_info=True)


# Global singleton instance
_publisher: Optional[MonitoringEventPublisher] = None


async def get_monitoring_publisher() -> MonitoringEventPublisher:
    """
    Get or create the global monitoring event publisher instance.

    Returns:
        MonitoringEventPublisher instance
    """
    global _publisher

    if _publisher is None:
        _publisher = MonitoringEventPublisher()
        await _publisher.initialize()

    return _publisher
