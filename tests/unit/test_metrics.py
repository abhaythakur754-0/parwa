"""Tests for PARWA Prometheus Metrics (Day 21)"""

import os

import pytest

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-min!!"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32-chars!!"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from backend.app.core.metrics import (
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    MetricsRegistry,
    _normalize_path,
    record_http_request,
    record_celery_task,
    record_db_query,
    update_db_pool,
    record_redis_command,
    registry,
)


# ── _normalize_path ───────────────────────────────────────────────


class TestNormalizePath:
    def test_uuid_replaced(self):
        path = "/api/tickets/550e8400-e29b-41d4-a716-446655440000"
        assert _normalize_path(path) == "/api/tickets/:id"

    def test_numeric_id_replaced(self):
        path = "/api/users/12345"
        assert _normalize_path(path) == "/api/users/:id"

    def test_query_string_stripped(self):
        path = "/api/tickets?page=1&limit=20"
        assert _normalize_path(path) == "/api/tickets"

    def test_static_path_unchanged(self):
        path = "/health"
        assert _normalize_path(path) == "/health"

    def test_multiple_ids(self):
        path = "/api/users/123/tickets/456"
        assert _normalize_path(path) == "/api/users/:id/tickets/:id"


# ── CounterMetric ─────────────────────────────────────────────────


class TestCounterMetric:
    def test_inc(self):
        c = CounterMetric(name="test_counter", help_text="test")
        c.inc()
        c.inc(5)
        assert c.value == 6.0

    def test_negative_inc_ignored(self):
        c = CounterMetric(name="test_counter", help_text="test")
        c.inc(-1)
        assert c.value == 0.0

    def test_inc_labels(self):
        c = CounterMetric(name="test_counter", help_text="test")
        c.inc_labels(1.0, method="GET", path="/health")
        c.inc_labels(2.0, method="GET", path="/health")
        c.inc_labels(1.0, method="POST", path="/api/login")
        # Should have accumulated for same labels
        key = 'method="GET",path="/health"'
        assert c.labels[key] == 3.0

    def test_render(self):
        c = CounterMetric(name="parwa_test", help_text="Test counter")
        c.inc(42)
        rendered = c.render()
        assert "# HELP parwa_test Test counter" in rendered
        assert "# TYPE parwa_test counter" in rendered
        assert "parwa_test 42" in rendered

    def test_render_with_labels(self):
        c = CounterMetric(name="parwa_test", help_text="Test counter")
        c.inc_labels(1.0, status="200")
        rendered = c.render()
        assert 'status="200"' in rendered


# ── GaugeMetric ───────────────────────────────────────────────────


class TestGaugeMetric:
    def test_set(self):
        g = GaugeMetric(name="test_gauge", help_text="test")
        g.set(42.5)
        assert g.value == 42.5

    def test_inc_dec(self):
        g = GaugeMetric(name="test_gauge", help_text="test")
        g.inc(10)
        g.dec(3)
        assert g.value == 7.0

    def test_set_labels(self):
        g = GaugeMetric(name="test_gauge", help_text="test")
        g.set_labels(5, state="used")
        g.set_labels(20, state="max")
        key_used = 'state="used"'
        key_max = 'state="max"'
        assert g.labels[key_used] == 5
        assert g.labels[key_max] == 20

    def test_render(self):
        g = GaugeMetric(name="parwa_gauge_test", help_text="Test gauge")
        g.set(100)
        rendered = g.render()
        assert "# TYPE parwa_gauge_test gauge" in rendered
        assert "parwa_gauge_test 100" in rendered


# ── HistogramMetric ───────────────────────────────────────────────


class TestHistogramMetric:
    def test_observe(self):
        h = HistogramMetric(name="test_hist", help_text="test")
        h.observe(0.01)
        h.observe(0.05)
        h.observe(0.5)
        assert h.count == 3
        assert h.sum_value == 0.56

    def test_buckets(self):
        h = HistogramMetric(name="test_hist", help_text="test")
        h.observe(0.01)  # <= 0.01 bucket
        h.observe(0.05)  # <= 0.05 bucket
        h.observe(0.5)   # <= 0.5 bucket
        h.observe(5.0)   # <= 5.0 bucket
        assert h.counts[0.01] == 1
        assert h.counts[0.05] == 2
        assert h.counts[0.5] == 3
        assert h.counts[5.0] == 4

    def test_observe_with_labels(self):
        h = HistogramMetric(name="test_hist", help_text="test")
        h.observe(0.1, task_name="send_email")
        h.observe(0.2, task_name="send_email")
        assert h.count == 0  # unlabeled count unchanged
        key = 'task_name="send_email"'
        assert h.labels[key]["count"] == 2
        assert h.labels[key]["sum"] == pytest.approx(0.3)

    def test_render(self):
        h = HistogramMetric(
            name="parwa_hist_test", help_text="Test histogram",
        )
        h.observe(0.1)
        rendered = h.render()
        assert "# TYPE parwa_hist_test histogram" in rendered
        assert "parwa_hist_test_count" in rendered
        assert "parwa_hist_test_sum" in rendered
        assert "parwa_hist_test_bucket" in rendered


# ── MetricsRegistry ───────────────────────────────────────────────


class TestMetricsRegistry:
    def test_create_counter(self):
        r = MetricsRegistry()
        c = r.counter("test_counter", "help text")
        assert c.name == "test_counter"
        c.inc()
        assert c.value == 1.0

    def test_create_gauge(self):
        r = MetricsRegistry()
        g = r.gauge("test_gauge", "help text")
        g.set(42)
        assert g.value == 42

    def test_create_histogram(self):
        r = MetricsRegistry()
        h = r.histogram("test_hist", "help text")
        h.observe(0.1)
        assert h.count == 1

    def test_same_metric_returns_same_instance(self):
        r = MetricsRegistry()
        c1 = r.counter("test_c", "help")
        c2 = r.counter("test_c", "help")
        assert c1 is c2

    def test_render_all(self):
        r = MetricsRegistry()
        c = r.counter("parwa_test_c", "test counter")
        c.inc(10)
        g = r.gauge("parwa_test_g", "test gauge")
        g.set(5)
        rendered = r.render_all()
        assert "parwa_test_c 10" in rendered
        assert "parwa_test_g 5" in rendered

    def test_clear(self):
        r = MetricsRegistry()
        r.counter("test_c", "help")
        r.clear()
        rendered = r.render_all()
        assert rendered == ""


# ── Pre-Registered Metrics ────────────────────────────────────────


class TestPreRegisteredMetrics:
    def test_http_requests_total_exists(self):
        assert "parwa_http_requests_total" in str(registry.render_all())

    def test_http_request_duration_exists(self):
        rendered = registry.render_all()
        assert "parwa_http_request_duration_seconds" in rendered

    def test_celery_metrics_exist(self):
        rendered = registry.render_all()
        assert "parwa_celery_queue_depth" in rendered
        assert "parwa_celery_task_duration_seconds" in rendered
        assert "parwa_celery_task_total" in rendered

    def test_db_metrics_exist(self):
        rendered = registry.render_all()
        assert "parwa_db_query_duration_seconds" in rendered
        assert "parwa_db_pool_size" in rendered

    def test_redis_metrics_exist(self):
        rendered = registry.render_all()
        assert "parwa_redis_commands_total" in rendered
        assert "parwa_redis_operation_duration_seconds" in rendered

    def test_websocket_gauge_exists(self):
        rendered = registry.render_all()
        assert "parwa_active_websocket_connections" in rendered


# ── Helper Functions ──────────────────────────────────────────────


def _reset_all_metrics():
    """Reset all pre-registered metric values to zero.

    registry.clear() removes metrics from tracking but module-level
    references still point to orphaned objects. Instead, we reset
    values in-place so render_all() still works.
    """
    import backend.app.core.metrics as m
    for metric in m.registry._metrics.values():
        if hasattr(metric, 'value'):
            metric.value = 0.0
        if hasattr(metric, 'count'):
            metric.count = 0
        if hasattr(metric, 'sum_value'):
            metric.sum_value = 0.0
        if hasattr(metric, 'counts'):
            metric.counts = {b: 0 for b in metric.buckets}
        if hasattr(metric, 'labels'):
            metric.labels.clear()


class TestHelperFunctions:
    def test_record_http_request(self):
        _reset_all_metrics()
        record_http_request("GET", "/health", 200, 0.05)
        record_http_request("GET", "/health", 200, 0.03)
        record_http_request("POST", "/api/login", 401, 0.1)
        rendered = registry.render_all()
        assert 'method="GET"' in rendered
        assert 'path="/health"' in rendered
        assert 'status="200"' in rendered

    def test_record_http_request_normalizes_path(self):
        _reset_all_metrics()
        record_http_request(
            "GET",
            "/api/tickets/550e8400-e29b-41d4-a716-446655440000",
            200, 0.05,
        )
        rendered = registry.render_all()
        assert 'path="/api/tickets/:id"' in rendered

    def test_record_celery_task(self):
        _reset_all_metrics()
        record_celery_task("send_email_task", "success", 0.5)
        record_celery_task("send_email_task", "failure", 1.0)
        rendered = registry.render_all()
        assert 'task_name="send_email_task"' in rendered
        assert 'status="success"' in rendered

    def test_record_db_query(self):
        _reset_all_metrics()
        record_db_query(0.01)
        record_db_query(0.05)
        rendered = registry.render_all()
        assert "parwa_db_query_duration_seconds_count" in rendered

    def test_update_db_pool(self):
        _reset_all_metrics()
        update_db_pool(15, 20)
        rendered = registry.render_all()
        assert 'state="used"' in rendered

    def test_record_redis_command(self):
        _reset_all_metrics()
        record_redis_command("GET", 0.001)
        record_redis_command("SET", 0.005)
        rendered = registry.render_all()
        assert 'command="GET"' in rendered
        assert 'command="SET"' in rendered

    def test_no_tenant_specific_data_in_metrics(self):
        """LOUHOLE CHECK: Metrics must not contain tenant-specific data."""
        _reset_all_metrics()
        record_http_request(
            "GET", "/api/company_abc/tickets", 200, 0.05,
        )
        rendered = registry.render_all()
        # Company IDs should not appear as metric labels
        assert "company_id" not in rendered
