"""
Week 41 Builder 2 - Enterprise Analytics Tests
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestExecutiveDashboard:
    """Test executive dashboard"""

    def test_dashboard_exists(self):
        """Test dashboard module exists"""
        from enterprise.analytics.executive_dashboard import ExecutiveDashboard
        assert ExecutiveDashboard is not None

    def test_get_overview(self):
        """Test getting overview"""
        from enterprise.analytics.executive_dashboard import ExecutiveDashboard

        dashboard = ExecutiveDashboard("test_client")
        overview = dashboard.get_overview()

        assert overview["client_id"] == "test_client"
        assert "metrics" in overview

    def test_get_trends(self):
        """Test getting trends"""
        from enterprise.analytics.executive_dashboard import ExecutiveDashboard

        dashboard = ExecutiveDashboard("test_client")
        trends = dashboard.get_trends(days=30)

        assert "tickets" in trends
        assert len(trends["tickets"]) == 30


class TestROICalculator:
    """Test ROI calculator"""

    def test_calculator_exists(self):
        """Test calculator module exists"""
        from enterprise.analytics.roi_calculator import ROICalculator
        assert ROICalculator is not None

    def test_calculate_roi(self):
        """Test ROI calculation"""
        from enterprise.analytics.roi_calculator import ROICalculator

        calc = ROICalculator("test_client")
        result = calc.calculate(
            monthly_tickets=10000,
            avg_resolution_time_minutes=5.0,
            monthly_subscription_cost=5000.0
        )

        assert result.roi_percentage > 0
        assert result.annual_savings > 0


class TestTrendAnalyzer:
    """Test trend analyzer"""

    def test_analyzer_exists(self):
        """Test analyzer module exists"""
        from enterprise.analytics.trend_analyzer import TrendAnalyzer
        assert TrendAnalyzer is not None

    def test_analyze_trend(self):
        """Test trend analysis"""
        from enterprise.analytics.trend_analyzer import TrendAnalyzer, TrendDirection

        analyzer = TrendAnalyzer("test_client")
        result = analyzer.analyze_trend(
            "tickets",
            [100, 110, 120, 130, 140, 150]
        )

        assert result.direction == TrendDirection.UP
        assert result.change_percent > 0

    def test_get_forecast(self):
        """Test forecast"""
        from enterprise.analytics.trend_analyzer import TrendAnalyzer

        analyzer = TrendAnalyzer("test_client")
        forecast = analyzer.get_forecast(
            "tickets",
            [100, 110, 120, 130, 140, 150],
            periods=7
        )

        assert len(forecast) == 7


class TestExportManager:
    """Test export manager"""

    def test_manager_exists(self):
        """Test export manager exists"""
        from enterprise.analytics.export_manager import ExportManager
        assert ExportManager is not None

    def test_export_json(self):
        """Test JSON export"""
        from enterprise.analytics.export_manager import ExportManager, ExportFormat

        manager = ExportManager("test_client")
        data = {"tickets": 100, "resolution_rate": 95.0}
        job = manager.create_export(data, ExportFormat.JSON)

        assert job.format == ExportFormat.JSON


class TestReportScheduler:
    """Test report scheduler"""

    def test_scheduler_exists(self):
        """Test scheduler exists"""
        from enterprise.analytics.report_scheduler import ReportScheduler
        assert ReportScheduler is not None

    def test_create_schedule(self):
        """Test creating schedule"""
        from enterprise.analytics.report_scheduler import ReportScheduler, ScheduleFrequency

        scheduler = ReportScheduler("test_client")
        report = scheduler.create_schedule(
            name="Weekly Report",
            frequency=ScheduleFrequency.WEEKLY,
            recipients=["admin@test.com"],
            metrics=["tickets", "resolution_rate"]
        )

        assert report.frequency == ScheduleFrequency.WEEKLY
        assert len(report.recipients) == 1
