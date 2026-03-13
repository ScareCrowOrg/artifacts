"""
Metrics Collector

Collects and aggregates pipeline metrics.
Addresses GAP-001: No Centralized Dashboard
Addresses GAP-003: No Latency Monitoring
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import deque
import statistics


@dataclass
class Metric:
    """A single metric data point"""
    name: str
    value: float
    unit: str
    tags: Dict[str, str]
    timestamp: float


@dataclass
class AggregatedMetrics:
    """Aggregated metrics for dashboard"""
    generation_metrics: Dict[str, Any]
    component_health: Dict[str, str]
    latency_metrics: Dict[str, Any]
    resource_metrics: Dict[str, Any]
    timestamp: float
    alerts: List[Dict[str, Any]] = field(default_factory=list)  # Sprint 4: Added alerts

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "generation_metrics": self.generation_metrics,
            "component_health": self.component_health,
            "latency_metrics": self.latency_metrics,
            "resource_metrics": self.resource_metrics,
            "timestamp": self.timestamp,
            "alerts": self.alerts
        }


class MetricsCollector:
    """Collects and aggregates pipeline metrics"""
    
    def __init__(self, history_size: int = 100):
        """
        Initialize metrics collector
        
        Args:
            history_size: Maximum number of metrics to keep in history
        """
        self.history_size = history_size
        self.metrics_history: Dict[str, deque] = {}
        
        # Generation tracking
        self._generation_count = 0
        self._generation_success_count = 0
        self._generation_failure_count = 0
        self._consecutive_failures = 0  # Track consecutive failures (resets on success)
        self._active_generations = 0
        self._generation_times: deque = deque(maxlen=history_size)
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Record a single metric
        
        Args:
            name: Metric name (e.g., 'extension.latency.ms')
            value: Metric value
            unit: Unit of measurement (e.g., 'ms', '%', 'count')
            tags: Additional tags for metric categorization
        """
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {},
            timestamp=time.time()
        )
        
        if name not in self.metrics_history:
            self.metrics_history[name] = deque(maxlen=self.history_size)
        
        self.metrics_history[name].append(metric)
    
    def record_generation_start(self):
        """Record that a code generation has started"""
        self._generation_count += 1
        self._active_generations += 1
    
    def record_generation_success(self, duration_ms: float):
        """
        Record a successful code generation
        
        Args:
            duration_ms: Generation duration in milliseconds
        """
        self._generation_success_count += 1
        self._active_generations = max(0, self._active_generations - 1)
        self._generation_times.append(duration_ms)
        self._consecutive_failures = 0  # Reset consecutive failures on success
        
        self.record_metric(
            "generation.duration.ms",
            duration_ms,
            "ms",
            {"status": "success"}
        )
    
    def record_generation_failure(self, duration_ms: Optional[float] = None):
        """
        Record a failed code generation
        
        Args:
            duration_ms: Generation duration before failure (optional)
        """
        self._generation_failure_count += 1
        self._consecutive_failures += 1  # Increment consecutive failures
        self._active_generations = max(0, self._active_generations - 1)
        
        if duration_ms:
            self.record_metric(
                "generation.duration.ms",
                duration_ms,
                "ms",
                {"status": "failure"}
            )
    
    def record_extension_latency(self, latency_ms: float, request_type: str):
        """
        Record extension communication latency
        
        Args:
            latency_ms: Latency in milliseconds
            request_type: Type of request (e.g., 'execute', 'ping', 'credential')
        """
        self.record_metric(
            "extension.latency.ms",
            latency_ms,
            "ms",
            {"request_type": request_type}
        )
    
    def record_opfs_usage(self, used_bytes: int, total_bytes: int):
        """
        Record OPFS quota usage
        
        Args:
            used_bytes: Bytes used
            total_bytes: Total quota in bytes
        """
        usage_percent = (used_bytes / total_bytes) * 100 if total_bytes > 0 else 0
        
        self.record_metric(
            "opfs.quota.used.percent",
            usage_percent,
            "%"
        )
        
        self.record_metric(
            "opfs.quota.available.mb",
            (total_bytes - used_bytes) / (1024 * 1024),
            "MB"
        )
    
    def get_aggregated_metrics(self) -> AggregatedMetrics:
        """
        Get aggregated metrics for dashboard.
        
        Sprint 4: Also evaluates alert rules against current metrics.
        
        Returns:
            AggregatedMetrics object with all current metrics and triggered alerts
        """
        # Collect current metrics
        generation_metrics = self._get_generation_metrics()
        component_health = self._get_component_health_metrics()
        latency_metrics = self._get_latency_metrics()
        resource_metrics = self._get_resource_metrics()
        
        # Sprint 4: Evaluate alert rules
        triggered_alerts = []
        try:
            from .alert_rules import get_alert_rules_engine
            
            # Prepare metrics dict for alert evaluation
            metrics_for_alerts = {
                "latency_p95_ms": latency_metrics.get("extension_latency_p95_ms", 0),
                "latency_p99_ms": latency_metrics.get("extension_latency_p99_ms", 0),
                "avg_generation_time_ms": generation_metrics.get("avg_generation_time_ms", 0),
                "opfs_quota_used_percent": resource_metrics.get("opfs_quota_used_percent", 0),
                "success_rate": generation_metrics.get("success_rate", 100),
                "active_generations": generation_metrics.get("active_generations", 0),
                "consecutive_failures": generation_metrics.get("consecutive_failures", 0)  # Now accurate
            }
            
            alert_engine = get_alert_rules_engine()
            alert_events = alert_engine.evaluate_metrics(metrics_for_alerts)
            triggered_alerts = [event.to_dict() for event in alert_events]
            
            if triggered_alerts:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Triggered {len(triggered_alerts)} alerts")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error evaluating alert rules: {e}", exc_info=True)
        
        return AggregatedMetrics(
            generation_metrics=generation_metrics,
            component_health=component_health,
            latency_metrics=latency_metrics,
            resource_metrics=resource_metrics,
            timestamp=time.time(),
            alerts=triggered_alerts
        )
    
    def _get_generation_metrics(self) -> Dict[str, Any]:
        """Get code generation metrics"""
        total = self._generation_count
        success = self._generation_success_count
        failure = self._generation_failure_count
        
        success_rate = (success / total * 100) if total > 0 else 0
        
        # Calculate generation time statistics
        if self._generation_times:
            avg_time = statistics.mean(self._generation_times)
            p50_time = statistics.median(self._generation_times)
            p95_time = self._calculate_percentile(self._generation_times, 95)
            p99_time = self._calculate_percentile(self._generation_times, 99)
        else:
            avg_time = p50_time = p95_time = p99_time = 0
        
        return {
            "total_generations": total,
            "success_count": success,
            "failure_count": failure,
            "success_rate": success_rate,
            "avg_generation_time_ms": avg_time,
            "p50_generation_time_ms": p50_time,
            "p95_generation_time_ms": p95_time,
            "p99_generation_time_ms": p99_time,
            "active_generations": self._active_generations
        }
    
    def _get_component_health_metrics(self) -> Dict[str, str]:
        """Get component health status"""
        # This would be populated by the HealthChecker
        # For now, return a placeholder
        return {
            "frontend": "unknown",
            "extension": "unknown",
            "wasm_orchestrator": "unknown",
            "backend": "healthy",
            "mongodb": "unknown",
            "redis": "unknown",
            "llm_provider": "unknown"
        }
    
    def _get_latency_metrics(self) -> Dict[str, Any]:
        """Get latency metrics (GAP-003)"""
        extension_latencies = self._get_metric_values("extension.latency.ms")
        
        if extension_latencies:
            return {
                "extension_latency_p50_ms": self._calculate_percentile(extension_latencies, 50),
                "extension_latency_p95_ms": self._calculate_percentile(extension_latencies, 95),
                "extension_latency_p99_ms": self._calculate_percentile(extension_latencies, 99),
                "extension_latency_avg_ms": statistics.mean(extension_latencies)
            }
        
        return {
            "extension_latency_p50_ms": 0,
            "extension_latency_p95_ms": 0,
            "extension_latency_p99_ms": 0,
            "extension_latency_avg_ms": 0
        }
    
    def _get_resource_metrics(self) -> Dict[str, Any]:
        """Get resource usage metrics"""
        # OPFS metrics
        opfs_usage = self._get_latest_metric_value("opfs.quota.used.percent")
        opfs_available = self._get_latest_metric_value("opfs.quota.available.mb")
        
        return {
            "opfs_quota_used_percent": opfs_usage or 0,
            "opfs_available_mb": opfs_available or 0
        }
    
    def _get_metric_values(self, metric_name: str) -> List[float]:
        """
        Get all values for a specific metric
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            List of metric values
        """
        if metric_name not in self.metrics_history:
            return []
        
        return [m.value for m in self.metrics_history[metric_name]]
    
    def _get_latest_metric_value(self, metric_name: str) -> Optional[float]:
        """
        Get the latest value for a specific metric
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            Latest metric value or None
        """
        if metric_name not in self.metrics_history:
            return None
        
        history = self.metrics_history[metric_name]
        if not history:
            return None
        
        return history[-1].value
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """
        Calculate percentile for a list of values
        
        Args:
            values: List of values
            percentile: Percentile to calculate (0-100)
            
        Returns:
            Percentile value
        """
        if not values:
            return 0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    def get_metric_history(
        self,
        metric_name: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get history for a specific metric
        
        Args:
            metric_name: Name of the metric
            limit: Maximum number of entries to return
            
        Returns:
            List of metric data points
        """
        if metric_name not in self.metrics_history:
            return []
        
        history = list(self.metrics_history[metric_name])
        
        if limit:
            history = history[-limit:]
        
        return [
            {
                "value": m.value,
                "unit": m.unit,
                "tags": m.tags,
                "timestamp": m.timestamp
            }
            for m in history
        ]
    
    def get_all_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all tracked metrics
        
        Returns:
            Dictionary with metrics summary
        """
        summary = {}
        
        for metric_name, history in self.metrics_history.items():
            if not history:
                continue
            
            values = [m.value for m in history]
            
            summary[metric_name] = {
                "count": len(values),
                "latest": values[-1] if values else None,
                "avg": statistics.mean(values) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "unit": history[-1].unit if history else ""
            }
        
        return summary
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        self.metrics_history.clear()
        self._generation_count = 0
        self._generation_success_count = 0
        self._generation_failure_count = 0
        self._active_generations = 0
        self._generation_times.clear()
    
    def export_metrics(self) -> Dict[str, Any]:
        """
        Export all metrics for persistence or analysis
        
        Returns:
            Dictionary with all metrics data
        """
        return {
            "generation_stats": {
                "total": self._generation_count,
                "success": self._generation_success_count,
                "failure": self._generation_failure_count,
                "active": self._active_generations,
                "times": list(self._generation_times)
            },
            "metrics_history": {
                name: [
                    {
                        "value": m.value,
                        "unit": m.unit,
                        "tags": m.tags,
                        "timestamp": m.timestamp
                    }
                    for m in history
                ]
                for name, history in self.metrics_history.items()
            },
            "timestamp": time.time()
        }
