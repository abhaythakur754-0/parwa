# Tests for Builder 2 - Observability Stack
# Week 50: metrics_collector.py, log_aggregator.py, trace_manager.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.ops.metrics_collector import (
    MetricsCollector, Metric, MetricNamespace
)
from enterprise.ops.log_aggregator import (
    LogAggregator, LogEntry, LogLevel
)
from enterprise.ops.trace_manager import (
    TraceManager, Span, SpanStatus
)


# =============================================================================
# METRICS COLLECTOR TESTS
# =============================================================================

class TestMetricsCollector:
    """Tests for MetricsCollector class"""

    def test_init(self):
        """Test collector initialization"""
        collector = MetricsCollector()
        assert collector is not None
        meta = collector.get_meta()
        assert meta["total_collected"] == 0

    def test_counter_increment(self):
        """Test counter increment"""
        collector = MetricsCollector()
        collector.counter("requests")
        assert collector.get_counter("requests") == 1.0

    def test_counter_increment_by_value(self):
        """Test counter increment by value"""
        collector = MetricsCollector()
        collector.counter("requests", 5.0)
        assert collector.get_counter("requests") == 5.0

    def test_counter_multiple_increments(self):
        """Test multiple counter increments"""
        collector = MetricsCollector()
        collector.counter("requests")
        collector.counter("requests")
        collector.counter("requests")
        assert collector.get_counter("requests") == 3.0

    def test_counter_with_tags(self):
        """Test counter with tags"""
        collector = MetricsCollector()
        collector.counter("requests", tags={"endpoint": "/api"})
        collector.counter("requests", tags={"endpoint": "/health"})
        assert collector.get_counter("requests", {"endpoint": "/api"}) == 1.0
        assert collector.get_counter("requests", {"endpoint": "/health"}) == 1.0

    def test_gauge_set(self):
        """Test gauge value"""
        collector = MetricsCollector()
        collector.gauge("temperature", 25.5)
        assert collector.get_gauge("temperature") == 25.5

    def test_gauge_overwrite(self):
        """Test gauge value overwrite"""
        collector = MetricsCollector()
        collector.gauge("temperature", 25.5)
        collector.gauge("temperature", 30.0)
        assert collector.get_gauge("temperature") == 30.0

    def test_histogram_record(self):
        """Test histogram recording"""
        collector = MetricsCollector()
        collector.histogram("latency", 100.0)
        collector.histogram("latency", 200.0)
        collector.histogram("latency", 300.0)
        stats = collector.get_histogram_stats("latency")
        assert stats["count"] == 3
        assert stats["min"] == 100.0
        assert stats["max"] == 300.0

    def test_histogram_stats(self):
        """Test histogram statistics"""
        collector = MetricsCollector()
        for i in range(1, 101):
            collector.histogram("response_time", float(i))
        stats = collector.get_histogram_stats("response_time")
        assert stats["count"] == 100
        assert stats["min"] == 1.0
        assert stats["max"] == 100.0
        assert stats["avg"] == pytest.approx(50.5)

    def test_histogram_empty(self):
        """Test histogram statistics with no data"""
        collector = MetricsCollector()
        stats = collector.get_histogram_stats("nonexistent")
        assert stats["count"] == 0

    def test_get_metrics_by_namespace(self):
        """Test getting metrics by namespace"""
        collector = MetricsCollector()
        collector.counter("app_requests")
        metrics = collector.get_metrics(namespace=MetricNamespace.APPLICATION)
        assert len(metrics) >= 1

    def test_get_metrics_since(self):
        """Test getting metrics since timestamp"""
        collector = MetricsCollector()
        collector.counter("requests")
        time.sleep(0.1)
        since = datetime.utcnow()
        collector.counter("new_requests")
        metrics = collector.get_metrics(since=since)
        assert len(metrics) >= 1

    def test_clear(self):
        """Test clearing metrics"""
        collector = MetricsCollector()
        collector.counter("requests")
        collector.gauge("temperature", 25.0)
        count = collector.clear()
        assert count == 2
        assert collector.get_counter("requests") == 0

    def test_meta_tracking(self):
        """Test metadata tracking"""
        collector = MetricsCollector()
        collector.counter("requests")
        collector.gauge("temperature", 25.0)
        collector.histogram("latency", 100.0)
        meta = collector.get_meta()
        assert meta["total_collected"] == 3


# =============================================================================
# LOG AGGREGATOR TESTS
# =============================================================================

class TestLogAggregator:
    """Tests for LogAggregator class"""

    def test_init(self):
        """Test aggregator initialization"""
        aggregator = LogAggregator()
        assert aggregator is not None
        metrics = aggregator.get_metrics()
        assert metrics["total_logs"] == 0

    def test_log_info(self):
        """Test info log"""
        aggregator = LogAggregator()
        entry = aggregator.info("Test message", source="app")
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"
        assert entry.source == "app"

    def test_log_debug(self):
        """Test debug log"""
        aggregator = LogAggregator()
        entry = aggregator.debug("Debug message")
        assert entry.level == LogLevel.DEBUG

    def test_log_warning(self):
        """Test warning log"""
        aggregator = LogAggregator()
        entry = aggregator.warning("Warning message")
        assert entry.level == LogLevel.WARNING

    def test_log_error(self):
        """Test error log"""
        aggregator = LogAggregator()
        entry = aggregator.error("Error message")
        assert entry.level == LogLevel.ERROR

    def test_log_critical(self):
        """Test critical log"""
        aggregator = LogAggregator()
        entry = aggregator.critical("Critical message")
        assert entry.level == LogLevel.CRITICAL

    def test_log_with_tenant(self):
        """Test log with tenant ID"""
        aggregator = LogAggregator()
        entry = aggregator.info("Test", tenant_id="tenant_001")
        assert entry.tenant_id == "tenant_001"

    def test_log_with_context(self):
        """Test log with context"""
        aggregator = LogAggregator()
        entry = aggregator.info("Test", context={"user_id": "123", "action": "login"})
        assert entry.context["user_id"] == "123"
        assert entry.context["action"] == "login"

    def test_get_logs_by_level(self):
        """Test getting logs by level"""
        aggregator = LogAggregator()
        aggregator.info("Info 1")
        aggregator.error("Error 1")
        aggregator.info("Info 2")
        logs = aggregator.get_logs(level=LogLevel.ERROR)
        assert len(logs) == 1
        assert logs[0].message == "Error 1"

    def test_get_logs_by_source(self):
        """Test getting logs by source"""
        aggregator = LogAggregator()
        aggregator.info("Test 1", source="api")
        aggregator.info("Test 2", source="worker")
        aggregator.info("Test 3", source="api")
        logs = aggregator.get_logs(source="api")
        assert len(logs) == 2

    def test_get_logs_by_tenant(self):
        """Test getting logs by tenant"""
        aggregator = LogAggregator()
        aggregator.info("Test 1", tenant_id="tenant_001")
        aggregator.info("Test 2", tenant_id="tenant_002")
        logs = aggregator.get_logs(tenant_id="tenant_001")
        assert len(logs) == 1

    def test_get_logs_with_limit(self):
        """Test getting logs with limit"""
        aggregator = LogAggregator()
        for i in range(20):
            aggregator.info(f"Message {i}")
        logs = aggregator.get_logs(limit=5)
        assert len(logs) == 5

    def test_get_errors(self):
        """Test getting error logs"""
        aggregator = LogAggregator()
        aggregator.info("Info message")
        aggregator.error("Error 1")
        aggregator.critical("Critical 1")
        aggregator.warning("Warning")
        errors = aggregator.get_errors()
        assert len(errors) == 2

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        aggregator = LogAggregator()
        aggregator.info("Info", source="api")
        aggregator.error("Error", source="api")
        aggregator.info("Info 2", source="worker")
        metrics = aggregator.get_metrics()
        assert metrics["total_logs"] == 3
        assert metrics["by_level"]["info"] == 2
        assert metrics["by_level"]["error"] == 1

    def test_clear(self):
        """Test clearing logs"""
        aggregator = LogAggregator()
        aggregator.info("Test 1")
        aggregator.info("Test 2")
        count = aggregator.clear()
        assert count == 2
        logs = aggregator.get_logs(limit=100)
        assert len(logs) == 0

    def test_max_entries_limit(self):
        """Test max entries limit"""
        aggregator = LogAggregator(max_entries=5)
        for i in range(10):
            aggregator.info(f"Message {i}")
        logs = aggregator.get_logs(limit=100)
        assert len(logs) == 5


# =============================================================================
# TRACE MANAGER TESTS
# =============================================================================

class TestTraceManager:
    """Tests for TraceManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = TraceManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_traces"] == 0

    def test_start_trace(self):
        """Test starting a trace"""
        manager = TraceManager()
        span = manager.start_trace("api_request", tags={"endpoint": "/users"})
        assert span is not None
        assert span.operation == "api_request"
        assert span.trace_id != ""
        assert span.parent_id is None
        assert span.status == SpanStatus.STARTED

    def test_start_child_span(self):
        """Test starting a child span"""
        manager = TraceManager()
        parent = manager.start_trace("api_request")
        child = manager.start_span(parent.trace_id, parent.id, "db_query")
        assert child is not None
        assert child.parent_id == parent.id
        assert child.trace_id == parent.trace_id

    def test_start_span_invalid_trace(self):
        """Test starting span with invalid trace"""
        manager = TraceManager()
        span = manager.start_span("invalid_trace", "invalid_parent", "operation")
        assert span is None

    def test_end_span(self):
        """Test ending a span"""
        manager = TraceManager()
        span = manager.start_trace("api_request")
        time.sleep(0.01)
        result = manager.end_span(span.id)
        assert result is True
        assert span.status == SpanStatus.COMPLETED
        assert span.duration_ms > 0

    def test_end_span_with_failure(self):
        """Test ending span with failure"""
        manager = TraceManager()
        span = manager.start_trace("api_request")
        result = manager.end_span(span.id, SpanStatus.FAILED)
        assert result is True
        assert span.status == SpanStatus.FAILED

    def test_end_nonexistent_span(self):
        """Test ending non-existent span"""
        manager = TraceManager()
        result = manager.end_span("nonexistent")
        assert result is False

    def test_log_to_span(self):
        """Test logging to span"""
        manager = TraceManager()
        span = manager.start_trace("api_request")
        result = manager.log_to_span(span.id, "Processing request")
        assert result is True
        assert len(span.logs) == 1

    def test_log_to_nonexistent_span(self):
        """Test logging to non-existent span"""
        manager = TraceManager()
        result = manager.log_to_span("nonexistent", "message")
        assert result is False

    def test_get_trace(self):
        """Test getting all spans for a trace"""
        manager = TraceManager()
        parent = manager.start_trace("api_request")
        child1 = manager.start_span(parent.trace_id, parent.id, "db_query")
        child2 = manager.start_span(parent.trace_id, parent.id, "cache_lookup")
        spans = manager.get_trace(parent.trace_id)
        assert len(spans) == 3

    def test_get_span(self):
        """Test getting a span by ID"""
        manager = TraceManager()
        span = manager.start_trace("api_request")
        retrieved = manager.get_span(span.id)
        assert retrieved is not None
        assert retrieved.id == span.id

    def test_get_nonexistent_span(self):
        """Test getting non-existent span"""
        manager = TraceManager()
        span = manager.get_span("nonexistent")
        assert span is None

    def test_get_slow_traces(self):
        """Test getting slow traces"""
        manager = TraceManager()
        # Fast trace
        fast = manager.start_trace("fast_request")
        manager.end_span(fast.id)

        # Slow trace (simulate with sleep)
        slow = manager.start_trace("slow_request")
        time.sleep(0.05)
        manager.end_span(slow.id)

        slow_traces = manager.get_slow_traces(threshold_ms=10.0)
        assert slow.trace_id in slow_traces

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        manager = TraceManager()
        parent = manager.start_trace("api_request")
        child = manager.start_span(parent.trace_id, parent.id, "db_query")
        metrics = manager.get_metrics()
        assert metrics["total_traces"] == 1
        assert metrics["total_spans"] == 2

    def test_cleanup_old(self):
        """Test cleanup of old traces"""
        manager = TraceManager()
        span = manager.start_trace("api_request")
        manager.end_span(span.id)
        # Cleanup traces older than 0 hours (all)
        removed = manager.cleanup_old(hours=0)
        assert removed >= 1

    def test_nested_spans(self):
        """Test deeply nested spans"""
        manager = TraceManager()
        root = manager.start_trace("request")
        child1 = manager.start_span(root.trace_id, root.id, "child1")
        child2 = manager.start_span(root.trace_id, child1.id, "child2")
        child3 = manager.start_span(root.trace_id, child2.id, "child3")

        assert child1.parent_id == root.id
        assert child2.parent_id == child1.id
        assert child3.parent_id == child2.id

        spans = manager.get_trace(root.trace_id)
        assert len(spans) == 4
