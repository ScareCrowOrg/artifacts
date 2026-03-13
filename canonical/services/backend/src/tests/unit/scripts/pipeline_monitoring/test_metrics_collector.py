"""
Unit tests for metrics collector

Path to scripts is configured in tests/unit/scripts/conftest.py
"""

import pytest
import time

from pipeline_monitoring.metrics_collector import (
    MetricsCollector,
    Metric,
    AggregatedMetrics
)


class TestMetricsCollector:
    """Test suite for MetricsCollector"""
    
    @pytest.fixture
    def collector(self):
        """Create a metrics collector instance"""
        return MetricsCollector(history_size=10)
    
    def test_collector_initialization(self, collector):
        """Test metrics collector initializes correctly"""
        assert collector is not None
        assert collector.history_size == 10
        assert len(collector.metrics_history) == 0
        assert collector._generation_count == 0
        assert collector._active_generations == 0
    
    def test_record_metric(self, collector):
        """Test recording a single metric"""
        collector.record_metric("test.metric", 42.0, "ms", {"tag": "value"})
        
        assert "test.metric" in collector.metrics_history
        assert len(collector.metrics_history["test.metric"]) == 1
        
        metric = collector.metrics_history["test.metric"][0]
        assert metric.name == "test.metric"
        assert metric.value == 42.0
        assert metric.unit == "ms"
        assert metric.tags == {"tag": "value"}
        assert metric.timestamp > 0
    
    def test_record_multiple_metrics(self, collector):
        """Test recording multiple metrics"""
        for i in range(5):
            collector.record_metric("test.metric", float(i), "count")
        
        assert len(collector.metrics_history["test.metric"]) == 5
    
    def test_history_size_limit(self, collector):
        """Test metrics history respects size limit"""
        # Record more metrics than the history size
        for i in range(15):
            collector.record_metric("test.metric", float(i), "count")
        
        # Should only keep the last 10
        assert len(collector.metrics_history["test.metric"]) == 10
        
        # Should have the most recent values
        values = [m.value for m in collector.metrics_history["test.metric"]]
        assert values == list(range(5, 15))
    
    def test_record_generation_start(self, collector):
        """Test recording generation start"""
        initial_count = collector._generation_count
        initial_active = collector._active_generations
        
        collector.record_generation_start()
        
        assert collector._generation_count == initial_count + 1
        assert collector._active_generations == initial_active + 1
    
    def test_record_generation_success(self, collector):
        """Test recording successful generation"""
        collector.record_generation_start()
        initial_active = collector._active_generations
        
        collector.record_generation_success(1500.0)
        
        assert collector._generation_success_count == 1
        assert collector._active_generations == initial_active - 1
        assert len(collector._generation_times) == 1
        assert collector._generation_times[0] == 1500.0
        
        # Should also record metric
        assert "generation.duration.ms" in collector.metrics_history
    
    def test_record_generation_failure(self, collector):
        """Test recording failed generation"""
        collector.record_generation_start()
        initial_active = collector._active_generations
        
        collector.record_generation_failure(500.0)
        
        assert collector._generation_failure_count == 1
        assert collector._active_generations == initial_active - 1
    
    def test_record_extension_latency(self, collector):
        """Test recording extension latency"""
        collector.record_extension_latency(120.5, "execute")
        
        assert "extension.latency.ms" in collector.metrics_history
        metric = collector.metrics_history["extension.latency.ms"][0]
        assert metric.value == 120.5
        assert metric.tags["request_type"] == "execute"
    
    def test_record_opfs_usage(self, collector):
        """Test recording OPFS usage"""
        used_bytes = 50 * 1024 * 1024  # 50 MB
        total_bytes = 100 * 1024 * 1024  # 100 MB
        
        collector.record_opfs_usage(used_bytes, total_bytes)
        
        assert "opfs.quota.used.percent" in collector.metrics_history
        assert "opfs.quota.available.mb" in collector.metrics_history
        
        usage_percent = collector.metrics_history["opfs.quota.used.percent"][0].value
        assert usage_percent == 50.0
        
        available_mb = collector.metrics_history["opfs.quota.available.mb"][0].value
        assert abs(available_mb - 50.0) < 0.1  # Allow for floating point precision
    
    def test_get_aggregated_metrics(self, collector):
        """Test getting aggregated metrics"""
        # Record some data
        collector.record_generation_start()
        collector.record_generation_success(1000.0)
        collector.record_extension_latency(100.0, "execute")
        
        metrics = collector.get_aggregated_metrics()
        
        assert isinstance(metrics, AggregatedMetrics)
        assert "total_generations" in metrics.generation_metrics
        assert "extension_latency_p50_ms" in metrics.latency_metrics
        assert "opfs_quota_used_percent" in metrics.resource_metrics
        assert metrics.timestamp > 0
    
    def test_aggregated_metrics_to_dict(self, collector):
        """Test AggregatedMetrics can be converted to dict"""
        metrics = collector.get_aggregated_metrics()
        metrics_dict = metrics.to_dict()
        
        assert isinstance(metrics_dict, dict)
        assert "generation_metrics" in metrics_dict
        assert "component_health" in metrics_dict
        assert "latency_metrics" in metrics_dict
        assert "resource_metrics" in metrics_dict
        assert "timestamp" in metrics_dict
    
    def test_generation_metrics_calculation(self, collector):
        """Test generation metrics are calculated correctly"""
        # Record multiple generations
        for i in range(10):
            collector.record_generation_start()
            if i < 8:
                collector.record_generation_success(1000.0 + i * 100)
            else:
                collector.record_generation_failure()
        
        gen_metrics = collector._get_generation_metrics()
        
        assert gen_metrics["total_generations"] == 10
        assert gen_metrics["success_count"] == 8
        assert gen_metrics["failure_count"] == 2
        assert gen_metrics["success_rate"] == 80.0
        assert gen_metrics["avg_generation_time_ms"] > 0
    
    def test_latency_metrics_calculation(self, collector):
        """Test latency metrics are calculated correctly"""
        # Record various latencies
        latencies = [50, 100, 150, 200, 250, 300, 350, 400]
        for latency in latencies:
            collector.record_extension_latency(float(latency), "execute")
        
        latency_metrics = collector._get_latency_metrics()
        
        assert latency_metrics["extension_latency_p50_ms"] > 0
        assert latency_metrics["extension_latency_p95_ms"] > latency_metrics["extension_latency_p50_ms"]
        assert latency_metrics["extension_latency_p99_ms"] >= latency_metrics["extension_latency_p95_ms"]
        # Mean of 50-400 is 225
        assert abs(latency_metrics["extension_latency_avg_ms"] - 225.0) < 1.0
    
    def test_percentile_calculation(self, collector):
        """Test percentile calculation"""
        values = list(range(1, 101))  # 1 to 100
        
        p50 = collector._calculate_percentile(values, 50)
        p95 = collector._calculate_percentile(values, 95)
        p99 = collector._calculate_percentile(values, 99)
        
        # Percentile calculation rounds to index
        assert p50 == 50 or p50 == 51  # Allow small variance
        assert p95 in [95, 96]
        assert p99 in [99, 100]
    
    def test_percentile_calculation_empty_list(self, collector):
        """Test percentile calculation with empty list"""
        result = collector._calculate_percentile([], 50)
        assert result == 0
    
    def test_get_metric_history(self, collector):
        """Test getting metric history"""
        for i in range(5):
            collector.record_metric("test.metric", float(i), "count")
        
        history = collector.get_metric_history("test.metric")
        
        assert len(history) == 5
        assert all("value" in entry for entry in history)
        assert all("timestamp" in entry for entry in history)
    
    def test_get_metric_history_with_limit(self, collector):
        """Test getting metric history with limit"""
        for i in range(10):
            collector.record_metric("test.metric", float(i), "count")
        
        history = collector.get_metric_history("test.metric", limit=3)
        
        assert len(history) == 3
        # Should return the most recent 3
        assert history[0]["value"] == 7.0
        assert history[-1]["value"] == 9.0
    
    def test_get_metric_history_nonexistent_metric(self, collector):
        """Test getting history for nonexistent metric"""
        history = collector.get_metric_history("nonexistent")
        assert history == []
    
    def test_get_latest_metric_value(self, collector):
        """Test getting latest metric value"""
        collector.record_metric("test.metric", 10.0, "count")
        collector.record_metric("test.metric", 20.0, "count")
        collector.record_metric("test.metric", 30.0, "count")
        
        latest = collector._get_latest_metric_value("test.metric")
        assert latest == 30.0
    
    def test_get_latest_metric_value_nonexistent(self, collector):
        """Test getting latest value for nonexistent metric"""
        latest = collector._get_latest_metric_value("nonexistent")
        assert latest is None
    
    def test_get_all_metrics_summary(self, collector):
        """Test getting summary of all metrics"""
        collector.record_metric("metric1", 10.0, "count")
        collector.record_metric("metric1", 20.0, "count")
        collector.record_metric("metric2", 5.0, "ms")
        
        summary = collector.get_all_metrics_summary()
        
        assert "metric1" in summary
        assert "metric2" in summary
        assert summary["metric1"]["count"] == 2
        assert summary["metric1"]["latest"] == 20.0
        assert summary["metric1"]["avg"] == 15.0
        assert summary["metric1"]["min"] == 10.0
        assert summary["metric1"]["max"] == 20.0
    
    def test_reset_metrics(self, collector):
        """Test resetting metrics"""
        # Record some data
        collector.record_generation_start()
        collector.record_generation_success(1000.0)
        collector.record_metric("test.metric", 42.0, "count")
        
        # Reset
        collector.reset_metrics()
        
        assert len(collector.metrics_history) == 0
        assert collector._generation_count == 0
        assert collector._generation_success_count == 0
        assert collector._generation_failure_count == 0
        assert collector._active_generations == 0
        assert len(collector._generation_times) == 0
    
    def test_export_metrics(self, collector):
        """Test exporting metrics"""
        # Record some data
        collector.record_generation_start()
        collector.record_generation_success(1000.0)
        collector.record_metric("test.metric", 42.0, "count")
        
        export = collector.export_metrics()
        
        assert "generation_stats" in export
        assert "metrics_history" in export
        assert "timestamp" in export
        assert export["generation_stats"]["total"] == 1
        assert "test.metric" in export["metrics_history"]
    
    def test_active_generations_count(self, collector):
        """Test active generations count is tracked correctly"""
        assert collector._active_generations == 0
        
        collector.record_generation_start()
        assert collector._active_generations == 1
        
        collector.record_generation_start()
        assert collector._active_generations == 2
        
        collector.record_generation_success(1000.0)
        assert collector._active_generations == 1
        
        collector.record_generation_failure()
        assert collector._active_generations == 0
    
    def test_active_generations_never_negative(self, collector):
        """Test active generations never goes negative"""
        collector.record_generation_failure()
        assert collector._active_generations == 0
        
        collector.record_generation_success(1000.0)
        assert collector._active_generations == 0
    
    def test_success_rate_with_no_generations(self, collector):
        """Test success rate calculation with no generations"""
        gen_metrics = collector._get_generation_metrics()
        assert gen_metrics["success_rate"] == 0
    
    def test_success_rate_calculation(self, collector):
        """Test success rate is calculated correctly"""
        # 7 success, 3 failure = 70% success rate
        for i in range(10):
            collector.record_generation_start()
            if i < 7:
                collector.record_generation_success(1000.0)
            else:
                collector.record_generation_failure()
        
        gen_metrics = collector._get_generation_metrics()
        assert gen_metrics["success_rate"] == 70.0
    
    def test_generation_times_history_limit(self, collector):
        """Test generation times respects history size"""
        collector_small = MetricsCollector(history_size=5)
        
        for i in range(10):
            collector_small.record_generation_start()
            collector_small.record_generation_success(float(i))
        
        # Should only keep last 5
        assert len(collector_small._generation_times) == 5
        assert list(collector_small._generation_times) == [5.0, 6.0, 7.0, 8.0, 9.0]
