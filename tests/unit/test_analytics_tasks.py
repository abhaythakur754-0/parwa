"""Tests for Day 22 analytics tasks."""

from tests.unit.test_day22_setup import setup_day22_tests  # noqa: E402
setup_day22_tests()
from backend.app.tasks.analytics_tasks import (  # noqa: E402
    aggregate_metrics,
    calculate_roi,
    drift_detection,
)


class TestAggregateMetrics:
    def test_returns_dict_on_success(self):
        result = aggregate_metrics("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_aggregated(self):
        result = aggregate_metrics("company-123")
        assert result["status"] == "aggregated"

    def test_return_has_period(self):
        result = aggregate_metrics("company-123", period="weekly")
        assert result["period"] == "weekly"

    def test_return_has_metric_date(self):
        result = aggregate_metrics("company-123")
        assert "metric_date" in result
        assert len(result["metric_date"]) == 10

    def test_default_period_is_daily(self):
        result = aggregate_metrics("company-123")
        assert result["period"] == "daily"

    def test_return_has_metrics_count(self):
        result = aggregate_metrics("company-123")
        assert "metrics_count" in result

    def test_queue_is_analytics(self):
        assert aggregate_metrics.queue == "analytics"

    def test_max_retries_is_3(self):
        assert aggregate_metrics.max_retries == 3

    def test_soft_time_limit(self):
        assert aggregate_metrics.soft_time_limit == 60

    def test_time_limit(self):
        assert aggregate_metrics.time_limit == 120

    def test_task_name_registered(self):
        assert "analytics.aggregate_metrics" in aggregate_metrics.name

    def test_hourly_period(self):
        result = aggregate_metrics("c1", period="hourly")
        assert result["period"] == "hourly"

    def test_custom_metric_date(self):
        result = aggregate_metrics("c1", metric_date="2025-01-01")
        assert result["metric_date"] == "2025-01-01"


class TestCalculateROI:
    def test_returns_dict_on_success(self):
        result = calculate_roi("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_calculated(self):
        result = calculate_roi("company-123")
        assert result["status"] == "calculated"

    def test_return_has_company_id(self):
        result = calculate_roi("company-123")
        assert result["company_id"] == "company-123"

    def test_return_has_roi(self):
        result = calculate_roi("company-123")
        assert "roi" in result

    def test_default_period_days(self):
        result = calculate_roi("company-123")
        assert result["period_days"] == 30

    def test_custom_period_days(self):
        result = calculate_roi("company-123", period_days=90)
        assert result["period_days"] == 90

    def test_queue_is_analytics(self):
        assert calculate_roi.queue == "analytics"

    def test_max_retries_is_2(self):
        assert calculate_roi.max_retries == 2

    def test_soft_time_limit(self):
        assert calculate_roi.soft_time_limit == 120

    def test_time_limit(self):
        assert calculate_roi.time_limit == 300

    def test_task_name_registered(self):
        assert "analytics.calculate_roi" in calculate_roi.name

    def test_roi_is_float(self):
        result = calculate_roi("company-123")
        assert isinstance(result["roi"], float)


class TestDriftDetection:
    def test_returns_dict_on_success(self):
        result = drift_detection("company-123")
        assert isinstance(result, dict)

    def test_return_has_status_checked(self):
        result = drift_detection("company-123")
        assert result["status"] == "checked"

    def test_return_has_drift_detected(self):
        result = drift_detection("company-123")
        assert "drift_detected" in result

    def test_return_has_confidence_score(self):
        result = drift_detection("company-123")
        assert "confidence_score" in result

    def test_confidence_score_is_float(self):
        result = drift_detection("company-123")
        assert isinstance(result["confidence_score"], float)

    def test_queue_is_analytics(self):
        assert drift_detection.queue == "analytics"

    def test_max_retries_is_2(self):
        assert drift_detection.max_retries == 2

    def test_soft_time_limit(self):
        assert drift_detection.soft_time_limit == 180

    def test_time_limit(self):
        assert drift_detection.time_limit == 600

    def test_task_name_registered(self):
        assert "analytics.drift_detection" in drift_detection.name

    def test_drift_detected_is_bool(self):
        result = drift_detection("company-123")
        assert isinstance(result["drift_detected"], bool)
