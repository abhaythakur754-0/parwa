# Tests for Week 48 Builder 5 - Notification Analytics
# Unit tests for notification_analytics.py, engagement_tracker.py, notification_reports.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from enterprise.notifications.notification_analytics import (
    NotificationAnalytics,
    NotificationMetrics,
    ChannelMetrics,
    NotificationChannel,
    MetricPeriod
)

from enterprise.notifications.engagement_tracker import (
    EngagementTracker,
    EngagementEvent,
    EngagementType,
    EngagementDevice,
    UserEngagement,
    NotificationEngagement
)

from enterprise.notifications.notification_reports import (
    NotificationReports,
    Report,
    ReportType,
    ReportPeriod,
    ReportFormat
)


# ============== NOTIFICATION ANALYTICS TESTS ==============

class TestChannelMetrics:
    def test_delivery_rate(self):
        metrics = ChannelMetrics(
            channel=NotificationChannel.EMAIL,
            total_sent=100,
            total_delivered=95
        )
        assert metrics.delivery_rate == 95.0

    def test_delivery_rate_zero_sent(self):
        metrics = ChannelMetrics()
        assert metrics.delivery_rate == 0.0

    def test_open_rate(self):
        metrics = ChannelMetrics(
            total_delivered=100,
            total_opened=40
        )
        assert metrics.open_rate == 40.0

    def test_click_rate(self):
        metrics = ChannelMetrics(
            total_opened=50,
            total_clicked=10
        )
        assert metrics.click_rate == 20.0

    def test_bounce_rate(self):
        metrics = ChannelMetrics(
            total_sent=100,
            total_bounced=5
        )
        assert metrics.bounce_rate == 5.0


class TestNotificationAnalytics:
    def test_record_event(self):
        analytics = NotificationAnalytics()
        analytics.record_event(
            tenant_id="t1",
            channel=NotificationChannel.EMAIL,
            event_type="sent",
            notification_id="n1"
        )
        assert len(analytics._events) == 1

    def test_get_channel_metrics(self):
        analytics = NotificationAnalytics()
        analytics.record_event("t1", NotificationChannel.EMAIL, "sent", "n1")
        analytics.record_event("t1", NotificationChannel.EMAIL, "delivered", "n1")
        analytics.record_event("t1", NotificationChannel.EMAIL, "opened", "n1")

        metrics = analytics.get_channel_metrics("t1", NotificationChannel.EMAIL)
        assert metrics.total_sent == 1
        assert metrics.total_delivered == 1
        assert metrics.total_opened == 1

    def test_get_all_channel_metrics(self):
        analytics = NotificationAnalytics()
        analytics.record_event("t1", NotificationChannel.EMAIL, "sent", "n1")
        analytics.record_event("t1", NotificationChannel.SMS, "sent", "n2")

        metrics = analytics.get_all_channel_metrics("t1")
        assert "email" in metrics
        assert "sms" in metrics

    def test_get_metrics_over_time(self):
        analytics = NotificationAnalytics()
        analytics.record_event("t1", NotificationChannel.EMAIL, "sent", "n1")

        points = analytics.get_metrics_over_time(
            "t1", "sent", MetricPeriod.DAY, periods=3
        )
        assert len(points) == 3

    def test_get_delivery_trends(self):
        analytics = NotificationAnalytics()
        analytics.record_event("t1", NotificationChannel.EMAIL, "sent", "n1")
        analytics.record_event("t1", NotificationChannel.EMAIL, "delivered", "n1")

        trends = analytics.get_delivery_trends("t1", days=3)
        assert "daily_stats" in trends
        assert "total_sent" in trends

    def test_get_best_performing_channel(self):
        analytics = NotificationAnalytics()
        # Email has better delivery rate
        analytics.record_event("t1", NotificationChannel.EMAIL, "sent", "n1")
        analytics.record_event("t1", NotificationChannel.EMAIL, "delivered", "n1")
        # SMS has worse
        analytics.record_event("t1", NotificationChannel.SMS, "sent", "n2")
        analytics.record_event("t1", NotificationChannel.SMS, "failed", "n2")

        best = analytics.get_best_performing_channel("t1")
        assert best == NotificationChannel.EMAIL

    def test_get_summary(self):
        analytics = NotificationAnalytics()
        analytics.record_event("t1", NotificationChannel.EMAIL, "sent", "n1")
        analytics.record_event("t1", NotificationChannel.EMAIL, "delivered", "n1")

        summary = analytics.get_summary("t1")
        assert "total_sent" in summary
        assert "by_channel" in summary

    def test_cleanup_old_events(self):
        analytics = NotificationAnalytics()
        analytics.record_event("t1", NotificationChannel.EMAIL, "sent", "n1")

        # Add old event manually
        old_event = {
            "id": "old",
            "tenant_id": "t1",
            "channel": "email",
            "event_type": "sent",
            "notification_id": "old",
            "timestamp": datetime.utcnow() - timedelta(days=100),
            "metadata": {}
        }
        analytics._events.append(old_event)

        removed = analytics.cleanup_old_events(days=30)
        assert removed == 1


# ============== ENGAGEMENT TRACKER TESTS ==============

class TestEngagementTracker:
    def test_record_open(self):
        tracker = EngagementTracker()
        event = tracker.record_open(
            notification_id="n1",
            tenant_id="t1",
            user_id="u1"
        )
        assert event.engagement_type == EngagementType.OPEN
        assert tracker._metrics["total_opens"] == 1

    def test_record_click(self):
        tracker = EngagementTracker()
        event = tracker.record_click(
            notification_id="n1",
            tenant_id="t1",
            user_id="u1",
            url="https://example.com"
        )
        assert event.engagement_type == EngagementType.CLICK
        assert event.url == "https://example.com"

    def test_record_unsubscribe(self):
        tracker = EngagementTracker()
        event = tracker.record_unsubscribe("n1", "t1", "u1")
        assert event.engagement_type == EngagementType.UNSUBSCRIBE

    def test_detect_device_mobile(self):
        tracker = EngagementTracker()
        device = tracker._detect_device("Mozilla/5.0 (iPhone; Mobile Safari)")
        assert device == EngagementDevice.MOBILE

    def test_detect_device_desktop(self):
        tracker = EngagementTracker()
        device = tracker._detect_device("Mozilla/5.0 (Windows NT 10.0)")
        assert device == EngagementDevice.DESKTOP

    def test_detect_device_tablet(self):
        tracker = EngagementTracker()
        device = tracker._detect_device("Mozilla/5.0 (iPad; Tablet)")
        assert device == EngagementDevice.TABLET

    def test_get_user_engagement(self):
        tracker = EngagementTracker()
        tracker.record_open("n1", "t1", "u1")
        tracker.record_click("n1", "t1", "u1", "https://example.com")

        engagement = tracker.get_user_engagement("u1", "t1")
        assert engagement is not None
        assert engagement.total_opens == 1
        assert engagement.total_clicks == 1

    def test_get_notification_engagement(self):
        tracker = EngagementTracker()
        tracker.record_open("n1", "t1", "u1")
        tracker.record_open("n1", "t1", "u2")

        engagement = tracker.get_notification_engagement("n1")
        assert engagement is not None
        assert engagement.total_opens == 2

    def test_calculate_unique_opens(self):
        tracker = EngagementTracker()
        tracker.record_open("n1", "t1", "u1")
        tracker.record_open("n1", "t1", "u1")  # Same user
        tracker.record_open("n1", "t1", "u2")

        unique = tracker.calculate_unique_opens("n1")
        assert unique == 2

    def test_calculate_unique_clicks(self):
        tracker = EngagementTracker()
        tracker.record_click("n1", "t1", "u1", "url1")
        tracker.record_click("n1", "t1", "u2", "url1")

        unique = tracker.calculate_unique_clicks("n1")
        assert unique == 2

    def test_get_engagement_timeline(self):
        tracker = EngagementTracker()
        tracker.record_open("n1", "t1", "u1")

        timeline = tracker.get_engagement_timeline("n1", hours=24)
        assert len(timeline) == 24

    def test_get_top_clicked_urls(self):
        tracker = EngagementTracker()
        tracker.record_click("n1", "t1", "u1", "url1")
        tracker.record_click("n1", "t1", "u1", "url1")
        tracker.record_click("n1", "t1", "u1", "url2")

        top_urls = tracker.get_top_clicked_urls("t1")
        assert len(top_urls) == 2
        assert top_urls[0]["url"] == "url1"
        assert top_urls[0]["clicks"] == 2

    def test_get_engagement_by_device(self):
        tracker = EngagementTracker()
        tracker.record_open("n1", "t1", "u1", user_agent="iPhone")
        tracker.record_open("n1", "t1", "u2", user_agent="Windows")

        device_breakdown = tracker.get_engagement_by_device("t1")
        assert "mobile" in device_breakdown
        assert "desktop" in device_breakdown

    def test_get_metrics(self):
        tracker = EngagementTracker()
        tracker.record_open("n1", "t1", "u1")
        tracker.record_click("n1", "t1", "u1", "url")

        metrics = tracker.get_metrics()
        assert metrics["total_opens"] == 1
        assert metrics["total_clicks"] == 1


# ============== NOTIFICATION REPORTS TESTS ==============

class TestNotificationReports:
    def test_generate_summary_report(self):
        reports = NotificationReports()
        report = reports.generate_summary_report("t1")
        assert report.tenant_id == "t1"
        assert report.report_type == ReportType.SUMMARY

    def test_generate_summary_report_with_dates(self):
        reports = NotificationReports()
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
        report = reports.generate_summary_report(
            "t1",
            start_time=start,
            end_time=end
        )
        assert report.start_time == start

    def test_generate_engagement_report(self):
        reports = NotificationReports()
        tracker = EngagementTracker()
        reports.set_engagement(tracker)

        report = reports.generate_engagement_report("t1")
        assert report.report_type == ReportType.ENGAGEMENT

    def test_generate_channel_comparison_report(self):
        reports = NotificationReports()
        analytics = NotificationAnalytics()
        reports.set_analytics(analytics)

        report = reports.generate_channel_comparison_report("t1")
        assert report.report_type == ReportType.CHANNEL

    def test_generate_trend_report(self):
        reports = NotificationReports()
        analytics = NotificationAnalytics()
        reports.set_analytics(analytics)

        report = reports.generate_trend_report("t1", days=14)
        assert report.report_type == ReportType.TREND
        assert report.data["period_days"] == 14

    def test_get_report(self):
        reports = NotificationReports()
        created = reports.generate_summary_report("t1")
        report = reports.get_report(created.id)
        assert report.id == created.id

    def test_get_reports_by_tenant(self):
        reports = NotificationReports()
        reports.generate_summary_report("t1")
        reports.generate_summary_report("t1")
        reports.generate_summary_report("t2")

        t1_reports = reports.get_reports_by_tenant("t1")
        assert len(t1_reports) == 2

    def test_export_report_json(self):
        reports = NotificationReports()
        report = reports.generate_summary_report("t1")
        json_export = reports.export_report_json(report.id)
        assert json_export is not None
        assert '"tenant_id": "t1"' in json_export

    def test_export_report_csv(self):
        reports = NotificationReports()
        report = reports.generate_summary_report("t1")
        csv_export = reports.export_report_csv(report.id)
        assert csv_export is not None
        assert "metric,value" in csv_export

    def test_delete_report(self):
        reports = NotificationReports()
        report = reports.generate_summary_report("t1")
        result = reports.delete_report(report.id)
        assert result is True
        assert reports.get_report(report.id) is None

    def test_schedule_report(self):
        reports = NotificationReports()
        result = reports.schedule_report(
            tenant_id="t1",
            report_type=ReportType.SUMMARY,
            period=ReportPeriod.DAILY,
            recipients=["admin@example.com"]
        )
        assert result["scheduled"] is True
        assert "admin@example.com" in result["recipients"]
