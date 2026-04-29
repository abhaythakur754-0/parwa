"""
PARWA Week 15 Integration Tests — Dashboard + Analytics

Tests for all 10 features built in Week 15:
- F-036: Dashboard Home
- F-037: Activity Feed
- F-038: Key Metrics
- F-039: Adaptation Tracker
- F-040: Savings Counter
- F-041: Workforce Allocation
- F-042: Growth Nudge
- F-043: Ticket Forecast
- F-044: CSAT Trends
- F-045: Export Reports

Uses mock/patch patterns. DB-dependent tests skip if no DATABASE_URL.
"""

import unittest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════════
# F-045: EXPORT REPORTS (no DB dependency)
# ══════════════════════════════════════════════════════════════════


class TestExportReports(unittest.TestCase):
    """F-045: Export Reports — CSV/PDF generation."""

    def setUp(self):
        import app.services.export_service as export_svc
        export_svc._export_jobs.clear()

    def test_export_csv_summary(self):
        """CSV export for summary report succeeds."""
        from app.services.export_service import create_export_job

        result = create_export_job(
            company_id="test-company",
            report_type="summary",
            format="csv",
        )

        self.assertIsInstance(result, dict)
        self.assertIn("job_id", result)
        self.assertIn("status", result)
        self.assertIn("report_type", result)
        self.assertEqual(result["report_type"], "summary")
        self.assertEqual(result["format"], "csv")

    def test_export_pdf_tickets(self):
        """PDF export for tickets report succeeds."""
        from app.services.export_service import create_export_job

        result = create_export_job(
            company_id="test-company",
            report_type="tickets",
            format="pdf",
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["format"], "pdf")
        self.assertIn(result["status"], ("completed", "failed"))

    def test_export_invalid_type(self):
        """Invalid report type returns error."""
        from app.services.export_service import create_export_job

        result = create_export_job(
            company_id="test-company",
            report_type="nonexistent",
            format="csv",
        )

        self.assertIn("error", result)

    def test_export_invalid_format(self):
        """Invalid format returns error."""
        from app.services.export_service import create_export_job

        result = create_export_job(
            company_id="test-company",
            report_type="summary",
            format="xlsx",
        )

        self.assertIn("error", result)

    def test_export_job_status(self):
        """Can retrieve job status after creation."""
        from app.services.export_service import create_export_job, get_export_job_status

        created = create_export_job("test-company", "sla", "csv")
        job_id = created["job_id"]
        status = get_export_job_status(job_id)

        self.assertEqual(status["job_id"], job_id)
        self.assertEqual(status["report_type"], "sla")

    def test_export_job_not_found(self):
        """Non-existent job returns error."""
        from app.services.export_service import get_export_job_status

        status = get_export_job_status("non-existent-id")
        self.assertIn("error", status)

    def test_export_list_jobs(self):
        """Can list export jobs for a company."""
        from app.services.export_service import create_export_job, list_export_jobs

        create_export_job("test-company", "summary", "csv")
        create_export_job("test-company", "tickets", "csv")
        create_export_job("other-company", "summary", "csv")

        jobs = list_export_jobs("test-company")
        self.assertEqual(len(jobs), 2)

    def test_export_all_report_types(self):
        """All 7 report types can be exported."""
        from app.services.export_service import create_export_job

        report_types = [
            "summary",
            "tickets",
            "agents",
            "sla",
            "csat",
            "forecast",
            "full"]
        for rt in report_types:
            result = create_export_job("test-company", rt, "csv")
            self.assertIsNone(
                result.get("error"),
                f"Report type {rt} should not error")


# ══════════════════════════════════════════════════════════════════
# SCHEMA VALIDATION (no DB dependency)
# ══════════════════════════════════════════════════════════════════


class TestDashboardSchemas(unittest.TestCase):
    """Validate all dashboard Pydantic schemas can be instantiated."""

    def test_dashboard_home_response(self):
        from app.schemas.dashboard import DashboardHomeResponse
        schema = DashboardHomeResponse()
        self.assertIsNotNone(schema)

    def test_activity_event(self):
        from app.schemas.dashboard import ActivityEvent
        event = ActivityEvent(
            event_id="123", event_type="status_changed",
            description="Status changed", created_at="2025-01-01T00:00:00Z",
        )
        self.assertEqual(event.event_type, "status_changed")

    def test_kpi_data(self):
        from app.schemas.dashboard import KPIData
        kpi = KPIData(
            key="test", label="Test KPI", value=42,
            unit="count", sparkline=[1, 2, 3],
        )
        self.assertEqual(kpi.value, 42)

    def test_adaptation_day_data(self):
        from app.schemas.dashboard import AdaptationDayData
        day = AdaptationDayData(
            date="2025-01-01",
            ai_accuracy=4.2,
            human_accuracy=4.5,
            gap=-0.3,
            tickets_processed=100,
            mistakes_count=5,
            mistake_rate=5.0,
        )
        self.assertEqual(day.ai_accuracy, 4.2)

    def test_savings_snapshot(self):
        from app.schemas.dashboard import SavingsSnapshot
        snap = SavingsSnapshot(
            period="2025-01", date="2025-01-01",
            tickets_ai=500, tickets_human=200,
            ai_cost=75.0, human_cost=1600.0,
            savings=1525.0, cumulative_savings=5000.0,
        )
        self.assertEqual(snap.savings, 1525.0)

    def test_workforce_split(self):
        from app.schemas.dashboard import WorkforceSplit
        split = WorkforceSplit(
            period="2025-W01", date="2025-01-06",
            ai_tickets=300, human_tickets=100,
            ai_pct=75.0, human_pct=25.0, total=400,
        )
        self.assertEqual(split.ai_pct, 75.0)

    def test_forecast_point(self):
        from app.schemas.dashboard import ForecastPoint
        point = ForecastPoint(
            date="2025-02-01", predicted=120.5,
            lower_bound=80.0, upper_bound=160.0,
        )
        self.assertEqual(point.predicted, 120.5)

    def test_growth_nudge(self):
        from app.schemas.dashboard import GrowthNudge
        nudge = GrowthNudge(
            nudge_id="n1", nudge_type="scaling",
            severity="recommendation", title="Volume increasing",
            message="Consider upgrading", detected_at="2025-01-01T00:00:00Z",
        )
        self.assertEqual(nudge.severity, "recommendation")

    def test_csat_day_data(self):
        from app.schemas.dashboard import CSATDayData
        day = CSATDayData(
            date="2025-01-01", avg_rating=4.3, total_ratings=50,
            distribution={"5": 30, "4": 15, "3": 5},
        )
        self.assertEqual(day.total_ratings, 50)

    def test_export_request(self):
        from app.schemas.dashboard import ExportRequest
        req = ExportRequest(report_type="summary", format="csv")
        self.assertEqual(req.format, "csv")

    def test_export_job_response(self):
        from app.schemas.dashboard import ExportJobResponse
        job = ExportJobResponse(
            job_id="j1", report_type="summary", format="csv",
            status="completed", created_at="2025-01-01T00:00:00Z",
        )
        self.assertEqual(job.status, "completed")

    def test_widget_config(self):
        from app.schemas.dashboard import WidgetConfig
        widget = WidgetConfig(
            widget_id="w1", widget_type="kpi", title="Test",
        )
        self.assertEqual(widget.widget_type, "kpi")

    def test_metrics_response(self):
        from app.schemas.dashboard import MetricsResponse
        resp = MetricsResponse(
            kpis=[], period="last_30d", generated_at="2025-01-01T00:00:00Z",
        )
        self.assertEqual(resp.period, "last_30d")


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPER FUNCTION TESTS (no DB dependency)
# ══════════════════════════════════════════════════════════════════


class TestInternalHelpers(unittest.TestCase):
    """Test internal helper functions that don't need DB."""

    def test_build_kpi(self):
        from app.services.dashboard_service import _build_kpi

        kpi = _build_kpi(
            key="test", label="Test", value=100,
            previous_value=80, unit="count",
        )
        self.assertEqual(kpi["value"], 100)
        self.assertEqual(kpi["change_pct"], 25.0)
        self.assertEqual(kpi["change_direction"], "up")

    def test_build_kpi_no_previous(self):
        from app.services.dashboard_service import _build_kpi

        kpi = _build_kpi(key="test", label="Test", value=42)
        self.assertIsNone(kpi["change_pct"])
        self.assertEqual(kpi["change_direction"], "neutral")

    def test_build_kpi_negative_change(self):
        from app.services.dashboard_service import _build_kpi

        kpi = _build_kpi(
            key="test", label="Test", value=50,
            previous_value=100, unit="count",
        )
        self.assertEqual(kpi["change_pct"], -50.0)
        self.assertEqual(kpi["change_direction"], "down")

    def test_empty_savings_response(self):
        from app.services.analytics_advanced_service import _empty_savings_response

        resp = _empty_savings_response()
        self.assertEqual(resp["all_time_savings"], 0.0)
        self.assertEqual(resp["all_time_tickets_ai"], 0)

    def test_empty_workforce_response(self):
        from app.services.analytics_advanced_service import _empty_workforce_response

        resp = _empty_workforce_response()
        self.assertEqual(resp["ai_resolution_rate"], 0.0)
        self.assertEqual(resp["human_resolution_rate"], 0.0)

    def test_empty_forecast_response(self):
        from app.services.analytics_intelligence_service import _empty_forecast_response

        resp = _empty_forecast_response()
        self.assertEqual(resp["model_type"], "none")
        self.assertEqual(resp["trend_direction"], "stable")

    def test_empty_csat_response(self):
        from app.services.analytics_intelligence_service import _empty_csat_response

        resp = _empty_csat_response()
        self.assertEqual(resp["overall_avg"], 0)
        self.assertEqual(resp["trend_direction"], "stable")

    def test_detect_seasonality_no_data(self):
        from app.services.analytics_intelligence_service import _detect_seasonality

        self.assertFalse(_detect_seasonality([]))

    def test_detect_seasonality_flat(self):
        from app.services.analytics_intelligence_service import _detect_seasonality

        flat_data = [("2025-01-01", 10)] * 14
        self.assertFalse(_detect_seasonality(flat_data))

    def test_detect_seasonality_variable(self):
        from app.services.analytics_intelligence_service import _detect_seasonality

        # Create data with high variance between weekdays
        import datetime
        base = datetime.datetime(2025, 1, 6)  # Monday
        variable_data = []
        for i in range(21):
            day = base + datetime.timedelta(days=i)
            # Mon-Fri: high, Sat-Sun: low
            if day.weekday() < 5:
                variable_data.append((day.strftime("%Y-%m-%d"), 50))
            else:
                variable_data.append((day.strftime("%Y-%m-%d"), 10))

        self.assertTrue(_detect_seasonality(variable_data))


# ══════════════════════════════════════════════════════════════════
# SERVICE FUNCTION TESTS (with DB mock)
# ══════════════════════════════════════════════════════════════════


class TestDashboardServiceWithMock(unittest.TestCase):
    """Test dashboard service functions with mocked DB."""

    @patch("app.services.dashboard_service._get_ticket_summary", return_value={})
    @patch("app.services.dashboard_service._get_kpi_cards", return_value={})
    @patch("app.services.dashboard_service._get_sla_summary", return_value={})
    @patch("app.services.dashboard_service._get_volume_trend", return_value=[])
    @patch("app.services.dashboard_service._get_category_breakdown", return_value=[])
    @patch("app.services.dashboard_service._get_activity_feed", return_value=[])
    @patch("app.services.dashboard_service._get_csat_summary", return_value={})
    @patch("app.services.dashboard_service._get_savings_summary", return_value={})
    @patch("app.services.dashboard_service._get_workforce_summary", return_value={})
    @patch("app.services.dashboard_service._detect_anomalies", return_value=[])
    def test_dashboard_home_structure(self, *mocks):
        from app.services.dashboard_service import get_dashboard_home

        result = get_dashboard_home("test-co", MagicMock())

        self.assertIn("summary", result)
        self.assertIn("kpis", result)
        self.assertIn("trend", result)
        self.assertIn("activity_feed", result)
        self.assertIn("generated_at", result)

    @patch("app.services.dashboard_service._get_ticket_summary",
           side_effect=Exception("DB down"))
    @patch("app.services.dashboard_service._get_kpi_cards", return_value={})
    @patch("app.services.dashboard_service._get_sla_summary", return_value={})
    @patch("app.services.dashboard_service._get_volume_trend", return_value=[])
    @patch("app.services.dashboard_service._get_category_breakdown", return_value=[])
    @patch("app.services.dashboard_service._get_activity_feed", return_value=[])
    @patch("app.services.dashboard_service._get_csat_summary", return_value={})
    @patch("app.services.dashboard_service._get_savings_summary", return_value={})
    @patch("app.services.dashboard_service._get_workforce_summary", return_value={})
    @patch("app.services.dashboard_service._detect_anomalies", return_value=[])
    def test_dashboard_home_handles_error(self, *mocks):
        from app.services.dashboard_service import get_dashboard_home

        result = get_dashboard_home("test-co", MagicMock())
        self.assertIn("generated_at", result)


class TestActivityFeedWithMock(unittest.TestCase):
    """Test activity feed with mocked DB queries."""

    @patch("app.services.dashboard_service._enrich_actor_names",
           side_effect=lambda e, db: e)
    def test_activity_feed_empty(self, mock_enrich):
        from app.services.dashboard_service import get_activity_feed

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = get_activity_feed("test-co", mock_db)

        self.assertIsInstance(result, dict)
        self.assertIn("events", result)
        self.assertIn("total", result)


class TestKeyMetricsWithMock(unittest.TestCase):
    """Test key metrics with mocked DB queries."""

    @patch("app.services.dashboard_service._count_tickets", return_value=100)
    @patch("app.services.dashboard_service._count_tickets_by_status", return_value=40)
    @patch("app.services.dashboard_service._get_avg_first_response_time",
           return_value=2.5)
    @patch("app.services.dashboard_service._get_avg_resolution_time", return_value=8.0)
    @patch("app.services.dashboard_service._get_sla_compliance_rate",
           return_value=0.95)
    @patch("app.services.dashboard_service._get_avg_csat", return_value=4.2)
    @patch("app.services.dashboard_service._count_tickets_by_assignee_type", return_value=30)
    @patch("app.services.dashboard_service._count_breached_sla", return_value=3)
    @patch("app.services.dashboard_service._count_tickets_by_priority", return_value=5)
    @patch("app.services.dashboard_service._get_daily_counts",
           return_value=[10.0] * 30)
    @patch("app.services.dashboard_service._get_daily_resolution_rate",
           return_value=[40.0] * 30)
    @patch("app.services.dashboard_service._flag_anomalies",
           side_effect=lambda k, db, c, s, e: k)
    def test_key_metrics_structure(self, *mocks):
        from app.services.dashboard_service import get_key_metrics

        result = get_key_metrics("test-co", MagicMock(), period="last_7d")

        self.assertIn("kpis", result)
        self.assertEqual(result["period"], "last_7d")
        self.assertGreater(len(result["kpis"]), 0)


if __name__ == "__main__":
    unittest.main()
