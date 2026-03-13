"""
Monitoring Router for Pipeline Monitoring Cell.

Provides REST API endpoints to expose pipeline monitoring data:
- Prerequisites validation status
- Component health checks
- Aggregated metrics
- Real-time alerts
- Alert rules management (Sprint 4)
- RBAC integration (Sprint 4)

Sprint 3: API Integration for Pipeline Monitoring Cell
Sprint 4: Alert Rules Engine and RBAC
"""

import logging
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from scripts.pipeline_monitoring.alert_rules import (
    AlertRule,
    AlertSeverity,
    RuleCondition,
    RuleMetric,
    get_alert_rules_engine,
)
from scripts.pipeline_monitoring.health_checker import HealthChecker
from scripts.pipeline_monitoring.metrics_collector import MetricsCollector
from scripts.pipeline_monitoring.validator import PipelineValidator

from ..models.users import User
from ..permissions import has_permission

logger = logging.getLogger(__name__)

# Create router
monitoring_router = APIRouter(prefix="/monitoring", tags=["monitoring", "pipeline"])

# Global instances (singleton pattern)
_validator: PipelineValidator = None
_health_checker: HealthChecker = None
_metrics_collector: MetricsCollector = None


def get_validator() -> PipelineValidator:
    """Get or create validator instance"""
    global _validator
    if _validator is None:
        _validator = PipelineValidator()
    return _validator


def get_health_checker() -> HealthChecker:
    """Get or create health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(interval_seconds=30)
    return _health_checker


def get_metrics_collector() -> MetricsCollector:
    """Get or create metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(history_size=100)
    return _metrics_collector


@monitoring_router.get(
    "/pipeline/health",
    summary="Get pipeline health status",
    response_description="Health status of all pipeline components",
)
async def get_pipeline_health():
    """
    Get health status of all pipeline components.

    Returns:
        Dict containing health check results for each component:
        - component: Component name
        - status: healthy|degraded|unhealthy|unknown
        - latency_ms: Response time in milliseconds
        - details: Additional diagnostic information
        - timestamp: Unix timestamp of check

    Example Response:
        {
            "status": "healthy",
            "components": [
                {
                    "component": "frontend",
                    "status": "healthy",
                    "latency_ms": 12.5,
                    "details": {},
                    "timestamp": 1735550000.0
                }
            ]
        }
    """
    try:
        health_checker = get_health_checker()
        results = await health_checker.check_all_components()

        # Determine overall status
        statuses = [r.status.value for r in results]
        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses:
            overall_status = "degraded"
        elif "unknown" in statuses:
            overall_status = "unknown"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "components": [r.to_dict() for r in results],
            "timestamp": results[0].timestamp if results else None,
        }

    except Exception as e:
        logger.error("Error getting pipeline health: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pipeline health: {str(e)}",
        )


@monitoring_router.get(
    "/pipeline/prerequisites",
    summary="Get prerequisites validation status (backend scope only)",
    response_description="Validation status of 10 backend-validatable prerequisites",
)
async def get_prerequisites():
    """
    Get validation status of backend prerequisites.

    **Important**: This endpoint validates only backend-side prerequisites (10 items).
    Frontend/Extension/WASM prerequisites (14 items) are validated client-side
    via useFrontendHealthChecks composable for a total of 24 prerequisites.

    Validates 10 backend prerequisites across 4 categories:
    - Backend (5): Generation Service, Complexity, LLM, Discovery, Event Bus
    - Infrastructure (2): MongoDB, Redis
    - Configuration (2): Environment vars, Feature flags
    - Runtime (1): System resources (server CPU, memory, disk)

    Returns:
        Dict containing:
        - prerequisites: List of prerequisite validation results
        - summary: Aggregate statistics
        - scope: "backend" indicating this is backend-only validation

        Each prerequisite includes:
        - id: Unique prerequisite identifier
        - name: Human-readable name
        - category: Category (backend, infrastructure, configuration, runtime)
        - status: healthy|degraded|unhealthy|unknown
        - criticality: critical|high|medium|low
        - validation_method: How it was validated
        - monitoring_available: Whether continuous monitoring is available
        - details: Additional diagnostic information
        - timestamp: Unix timestamp of validation

    Example Response:
        {
            "prerequisites": [
                {
                    "id": "backend.cell_generation_service",
                    "name": "Cell Generation Service",
                    "category": "backend",
                    "status": "healthy",
                    "criticality": "critical",
                    "validation_method": "import_check",
                    "monitoring_available": true,
                    "details": {"available": true},
                    "timestamp": 1735550000.0
                }
            ],
            "summary": {
                "total": 10,
                "healthy": 9,
                "degraded": 1,
                "unhealthy": 0,
                "unknown": 0
            },
            "scope": "backend"
        }

    Note:
        For complete system monitoring (all 24 prerequisites), the frontend
        monitoring cell aggregates both backend (this endpoint) and frontend
        (useFrontendHealthChecks) results.
    """
    try:
        validator = get_validator()
        results = await validator.validate_all()

        # Calculate summary
        summary = {
            "total": len(results),
            "healthy": sum(1 for r in results if r.status.value == "healthy"),
            "degraded": sum(1 for r in results if r.status.value == "degraded"),
            "unhealthy": sum(1 for r in results if r.status.value == "unhealthy"),
            "unknown": sum(1 for r in results if r.status.value == "unknown"),
        }

        return {
            "prerequisites": [r.to_dict() for r in results],
            "summary": summary,
            "scope": "backend",  # NEW: Clarify this is backend-only validation
        }

    except Exception as e:
        logger.error("Error getting prerequisites: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prerequisites: {str(e)}",
        )


@monitoring_router.get(
    "/pipeline/metrics",
    summary="Get aggregated pipeline metrics",
    response_description="Aggregated metrics for dashboard visualization",
)
async def get_metrics():
    """
    Get aggregated pipeline metrics.

    Provides metrics for dashboard visualization:
    - Generation metrics: Total, success rate, avg time, active count
    - Component health: Status of each component
    - Latency metrics: p50, p95, p99 latencies
    - Resource metrics: OPFS quota usage

    Returns:
        Dict containing:
        - generation_metrics: Code generation statistics
        - component_health: Component status map
        - latency_metrics: Latency percentiles
        - resource_metrics: Resource usage statistics
        - timestamp: Unix timestamp of metrics snapshot

    Example Response:
        {
            "generation_metrics": {
                "total_generations": 150,
                "success_rate": 95.5,
                "avg_generation_time_ms": 2450.0,
                "active_generations": 3
            },
            "component_health": {
                "frontend": "healthy",
                "extension": "healthy",
                "backend": "degraded"
            },
            "latency_metrics": {
                "extension_latency_p50_ms": 45.2,
                "extension_latency_p95_ms": 120.5,
                "extension_latency_p99_ms": 250.0
            },
            "resource_metrics": {
                "opfs_quota_used_percent": 35.5,
                "opfs_available_mb": 512.0
            },
            "timestamp": 1735550000.0
        }
    """
    try:
        metrics_collector = get_metrics_collector()
        aggregated = metrics_collector.get_aggregated_metrics()

        return aggregated.to_dict()

    except Exception as e:
        logger.error("Error getting metrics: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}",
        )


@monitoring_router.get(
    "/pipeline",
    summary="Get complete pipeline monitoring data",
    response_description="Complete monitoring data (prerequisites, health, metrics)",
)
async def get_complete_monitoring():
    """
    Get complete pipeline monitoring data in a single request.

    Combines prerequisites, health checks, and metrics into one response.
    Optimized for dashboard initial load.

    Returns:
        Dict containing:
        - prerequisites: All prerequisite validation results
        - components: All component health check results
        - metrics: Aggregated metrics
        - summary: Overall summary statistics

    Example Response:
        {
            "prerequisites": [...],
            "components": [...],
            "metrics": {...},
            "summary": {
                "overall_status": "healthy",
                "prerequisites_healthy": 23,
                "prerequisites_total": 24,
                "components_healthy": 7,
                "components_total": 7
            }
        }
    """
    try:
        # Fetch all data in parallel
        import asyncio

        validator = get_validator()
        health_checker = get_health_checker()
        metrics_collector = get_metrics_collector()

        prereq_task = validator.validate_all()
        health_task = health_checker.check_all_components()

        prerequisites, health_results = await asyncio.gather(prereq_task, health_task)

        metrics = metrics_collector.get_aggregated_metrics()

        # Calculate summary
        prereq_healthy = sum(1 for r in prerequisites if r.status.value == "healthy")
        components_healthy = sum(
            1 for r in health_results if r.status.value == "healthy"
        )

        overall_status = "healthy"
        if any(r.status.value == "unhealthy" for r in health_results):
            overall_status = "unhealthy"
        elif any(r.status.value == "degraded" for r in health_results):
            overall_status = "degraded"
        elif any(
            r.status.value == "unhealthy"
            for r in prerequisites
            if r.criticality.value == "critical"
        ):
            overall_status = "unhealthy"

        return {
            "prerequisites": [r.to_dict() for r in prerequisites],
            "components": [r.to_dict() for r in health_results],
            "metrics": metrics.to_dict(),
            "summary": {
                "overall_status": overall_status,
                "prerequisites_healthy": prereq_healthy,
                "prerequisites_total": len(prerequisites),
                "components_healthy": components_healthy,
                "components_total": len(health_results),
            },
        }

    except Exception as e:
        logger.error("Error getting complete monitoring data: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get monitoring data: {str(e)}",
        )


@monitoring_router.post(
    "/pipeline/health/start",
    response_model=Dict[str, Any],
    summary="Start periodic health checks",
    response_description="Confirmation of health check monitoring start",
)
async def start_health_monitoring(
    _interval_seconds: int = 30,
    _user: User = Depends(has_permission(["monitoring.control"])),
):
    """
    Start periodic health checks for all pipeline components.

    **Required Permission**: `monitoring.control`

    Initiates background health checking with configurable interval.
    Health check results will be available via WebSocket streaming.

    Args:
        interval_seconds: Interval between health checks (default: 30s)
        user: Authenticated user (injected by RBAC)

    Returns:
        Confirmation message with monitoring status
    """
    try:
        health_checker = get_health_checker()
        await health_checker.start_monitoring()

        return {
            "status": "started",
            "message": "Health check monitoring started",
            "interval_seconds": health_checker.interval_seconds,
        }

    except Exception as e:
        logger.error("Error starting health monitoring: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start health monitoring: {str(e)}",
        )


@monitoring_router.post(
    "/pipeline/health/stop",
    response_model=Dict[str, Any],
    summary="Stop periodic health checks",
    response_description="Confirmation of health check monitoring stop",
)
async def stop_health_monitoring(
    _user: User = Depends(has_permission(["monitoring.control"])),
):
    """
    Stop periodic health checks for pipeline components.

    **Required Permission**: `monitoring.control`

    Args:
        user: Authenticated user (injected by RBAC)

    Returns:
        Confirmation message
    """
    try:
        health_checker = get_health_checker()
        await health_checker.stop_monitoring()

        return {"status": "stopped", "message": "Health check monitoring stopped"}

    except Exception as e:
        logger.error("Error stopping health monitoring: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop health monitoring: {str(e)}",
        )


# ============================================================================
# SPRINT 4: Alert Rules Management Endpoints (with RBAC)
# ============================================================================


class AlertRuleCreateRequest(BaseModel):
    """Request model for creating alert rules"""

    id: str
    name: str
    metric: str
    condition: str
    threshold: Union[int, float, str]  # More specific than Any
    severity: str
    enabled: bool = True
    description: str = ""
    actions: List[str] = []


class AlertRuleUpdateRequest(BaseModel):
    """Request model for updating alert rules"""

    name: Optional[str] = None
    threshold: Optional[Union[int, float, str]] = None  # More specific than Any
    enabled: Optional[bool] = None
    description: Optional[str] = None
    actions: Optional[List[str]] = None


@monitoring_router.get(
    "/pipeline/alert-rules",
    response_model=List[Dict[str, Any]],
    summary="List alert rules",
    response_description="List of all alert rules",
)
async def list_alert_rules(
    enabled_only: bool = False,
    _user: User = Depends(has_permission(["monitoring.view", "monitoring.configure"])),
):
    """
    List all configured alert rules.

    **Required Permission**: `monitoring.view` or `monitoring.configure`

    Args:
        enabled_only: If True, only return enabled rules
        user: Authenticated user (injected by RBAC)

    Returns:
        List of alert rules with their configuration
    """
    try:
        engine = get_alert_rules_engine()
        rules = engine.list_rules(enabled_only=enabled_only)

        return [
            {
                "id": rule.id,
                "name": rule.name,
                "metric": rule.metric.value,
                "condition": rule.condition.value,
                "threshold": rule.threshold,
                "severity": rule.severity.value,
                "enabled": rule.enabled,
                "description": rule.description,
                "actions": rule.actions,
            }
            for rule in rules
        ]

    except Exception as e:
        logger.error("Error listing alert rules: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alert rules: {str(e)}",
        )


@monitoring_router.get(
    "/pipeline/alert-rules/{rule_id}",
    response_model=Dict[str, Any],
    summary="Get alert rule details",
    response_description="Alert rule configuration",
)
async def get_alert_rule(
    rule_id: str,
    _user: User = Depends(has_permission(["monitoring.view", "monitoring.configure"])),
):
    """
    Get details of a specific alert rule.

    **Required Permission**: `monitoring.view` or `monitoring.configure`

    Args:
        rule_id: Alert rule identifier
        user: Authenticated user (injected by RBAC)

    Returns:
        Alert rule configuration
    """
    try:
        engine = get_alert_rules_engine()
        rule = engine.get_rule(rule_id)

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule '{rule_id}' not found",
            )

        return {
            "id": rule.id,
            "name": rule.name,
            "metric": rule.metric.value,
            "condition": rule.condition.value,
            "threshold": rule.threshold,
            "severity": rule.severity.value,
            "enabled": rule.enabled,
            "description": rule.description,
            "actions": rule.actions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting alert rule: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert rule: {str(e)}",
        )


@monitoring_router.post(
    "/pipeline/alert-rules",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create alert rule",
    response_description="Created alert rule",
)
async def create_alert_rule(
    rule_data: AlertRuleCreateRequest,
    user: User = Depends(has_permission(["monitoring.configure"])),
):
    """
    Create a new alert rule.

    **Required Permission**: `monitoring.configure`

    Args:
        rule_data: Alert rule configuration
        user: Authenticated user (injected by RBAC)

    Returns:
        Created alert rule
    """
    try:
        engine = get_alert_rules_engine()

        # Check if rule ID already exists
        if engine.get_rule(rule_data.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Alert rule with ID '{rule_data.id}' already exists",
            )

        # Create rule
        rule = AlertRule(
            id=rule_data.id,
            name=rule_data.name,
            metric=RuleMetric(rule_data.metric),
            condition=RuleCondition(rule_data.condition),
            threshold=rule_data.threshold,
            severity=AlertSeverity(rule_data.severity),
            enabled=rule_data.enabled,
            description=rule_data.description,
            actions=rule_data.actions,
        )

        engine.add_rule(rule)

        logger.info("Created alert rule: %s by user: %s (ID: %s)", rule.id, user.email, user.id)

        return {
            "id": rule.id,
            "name": rule.name,
            "metric": rule.metric.value,
            "condition": rule.condition.value,
            "threshold": rule.threshold,
            "severity": rule.severity.value,
            "enabled": rule.enabled,
            "description": rule.description,
            "actions": rule.actions,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rule configuration: {str(e)}",
        )
    except Exception as e:
        logger.error("Error creating alert rule: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create alert rule: {str(e)}",
        )


@monitoring_router.patch(
    "/pipeline/alert-rules/{rule_id}",
    response_model=Dict[str, Any],
    summary="Update alert rule",
    response_description="Updated alert rule",
)
async def update_alert_rule(
    rule_id: str,
    rule_data: AlertRuleUpdateRequest,
    user: User = Depends(has_permission(["monitoring.configure"])),
):
    """
    Update an existing alert rule.

    **Required Permission**: `monitoring.configure`

    Args:
        rule_id: Alert rule identifier
        rule_data: Fields to update
        user: Authenticated user (injected by RBAC)

    Returns:
        Updated alert rule
    """
    try:
        engine = get_alert_rules_engine()
        rule = engine.get_rule(rule_id)

        if not rule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule '{rule_id}' not found",
            )

        # Update fields
        if rule_data.name is not None:
            rule.name = rule_data.name
        if rule_data.threshold is not None:
            rule.threshold = rule_data.threshold
        if rule_data.enabled is not None:
            rule.enabled = rule_data.enabled
        if rule_data.description is not None:
            rule.description = rule_data.description
        if rule_data.actions is not None:
            rule.actions = rule_data.actions

        engine.add_rule(rule)  # This updates the rule

        logger.info("Updated alert rule: %s by user: %s (ID: %s)", rule_id, user.email, user.id)

        return {
            "id": rule.id,
            "name": rule.name,
            "metric": rule.metric.value,
            "condition": rule.condition.value,
            "threshold": rule.threshold,
            "severity": rule.severity.value,
            "enabled": rule.enabled,
            "description": rule.description,
            "actions": rule.actions,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating alert rule: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update alert rule: {str(e)}",
        )


@monitoring_router.delete(
    "/pipeline/alert-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete alert rule",
    response_description="Alert rule deleted",
)
async def delete_alert_rule(
    rule_id: str, user: User = Depends(has_permission(["monitoring.configure"]))
):
    """
    Delete an alert rule.

    **Required Permission**: `monitoring.configure`

    Args:
        rule_id: Alert rule identifier
        user: Authenticated user (injected by RBAC)
    """
    try:
        engine = get_alert_rules_engine()

        if not engine.remove_rule(rule_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule '{rule_id}' not found",
            )

        logger.info("Deleted alert rule: %s by user: %s (ID: %s)", rule_id, user.email, user.id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting alert rule: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete alert rule: {str(e)}",
        )


@monitoring_router.post(
    "/pipeline/alert-rules/{rule_id}/enable",
    response_model=Dict[str, Any],
    summary="Enable/disable alert rule",
    response_description="Updated rule status",
)
async def toggle_alert_rule(
    rule_id: str,
    enabled: bool = True,
    user: User = Depends(has_permission(["monitoring.configure"])),
):
    """
    Enable or disable an alert rule.

    **Required Permission**: `monitoring.configure`

    Args:
        rule_id: Alert rule identifier
        enabled: Whether to enable (True) or disable (False) the rule
        user: Authenticated user (injected by RBAC)

    Returns:
        Updated rule status
    """
    try:
        engine = get_alert_rules_engine()

        if not engine.enable_rule(rule_id, enabled):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert rule '{rule_id}' not found",
            )

        logger.info(
            "%s alert rule: %s by user: %s (ID: %s)",
            'Enabled' if enabled else 'Disabled', rule_id, user.email, user.id
        )

        rule = engine.get_rule(rule_id)

        return {
            "id": rule.id,
            "enabled": rule.enabled,
            "message": f"Rule {'enabled' if enabled else 'disabled'} successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error toggling alert rule: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle alert rule: {str(e)}",
        )


# ============================================================================
# SPRINT 4: Update existing endpoints with RBAC
# ============================================================================

# Update the start/stop health monitoring endpoints to require permissions
