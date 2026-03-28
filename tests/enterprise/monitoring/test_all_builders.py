"""
Tests for Monitoring Module - Week 53, Builders 2-5
"""

import pytest
from datetime import datetime, timedelta
import asyncio

from enterprise.monitoring.alert_manager import (
    AlertManager,
    Alert,
    AlertSeverity,
    AlertStatus,
)
from enterprise.monitoring.alert_rules import (
    AlertRuleEngine,
    AlertRule,
    RuleState,
    RuleResult,
    ComparisonOperator,
)
from enterprise.monitoring.notification_router import (
    NotificationRouter,
    NotificationChannel,
    Notification,
    NotificationStatus,
    ChannelType,
)
from enterprise.monitoring.incident_manager import (
    IncidentManager,
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from enterprise.monitoring.incident_tracker import (
    IncidentTracker,
    IncidentMetrics,
    IncidentState,
)
from enterprise.monitoring.escalation_manager import (
    EscalationManager,
    EscalationRule,
    EscalationEvent,
    EscalationLevel,
    EscalationTrigger,
)
from enterprise.monitoring.log_analyzer import (
    LogAnalyzer,
    LogEntry,
    LogLevel,
    AnalysisResult,
)
from enterprise.monitoring.log_parser import (
    LogParser,
    ParseResult,
    LogFormat,
)
from enterprise.monitoring.log_correlator import (
    LogCorrelator,
    CorrelatedGroup,
    CorrelationType,
)
from enterprise.monitoring.dashboard_builder import (
    DashboardBuilder,
    DashboardConfig,
    DashboardType,
    LayoutType,
)
from enterprise.monitoring.widget_factory import (
    WidgetFactory,
    WidgetType,
    WidgetDefinition,
)
from enterprise.monitoring.data_visualizer import (
    DataVisualizer,
    ChartType,
    DataSeries,
)


# ============================================================================
# Alert Manager Tests
# ============================================================================

class TestAlertManager:
    """Tests for AlertManager class"""

    def test_init(self):
        """Test alert manager initialization"""
        manager = AlertManager()
        assert len(manager.alerts) == 0

    def test_create_alert(self):
        """Test creating alert"""
        manager = AlertManager()
        alert = manager.create_alert(
            name="HighCPU",
            severity=AlertSeverity.WARNING,
            message="CPU usage above 80%",
            source="server1",
        )
        assert alert.name == "HighCPU"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.alert_id is not None

    def test_get_alert(self):
        """Test getting alert"""
        manager = AlertManager()
        alert = manager.create_alert("Test", AlertSeverity.INFO, "Test alert")
        retrieved = manager.get_alert(alert.alert_id)
        assert retrieved.alert_id == alert.alert_id

    def test_acknowledge_alert(self):
        """Test acknowledging alert"""
        manager = AlertManager()
        alert = manager.create_alert("Test", AlertSeverity.WARNING, "Test")
        result = manager.acknowledge_alert(alert.alert_id)
        assert result is True
        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_resolve_alert(self):
        """Test resolving alert"""
        manager = AlertManager()
        alert = manager.create_alert("Test", AlertSeverity.ERROR, "Test")
        result = manager.resolve_alert(alert.alert_id)
        assert result is True
        assert alert.status == AlertStatus.RESOLVED

    def test_get_active_alerts(self):
        """Test getting active alerts"""
        manager = AlertManager()
        manager.create_alert("Active1", AlertSeverity.WARNING, "Test")
        manager.create_alert("Active2", AlertSeverity.ERROR, "Test")
        alert = manager.create_alert("Resolved", AlertSeverity.INFO, "Test")
        manager.resolve_alert(alert.alert_id)

        active = manager.get_active_alerts()
        assert len(active) == 2

    def test_get_statistics(self):
        """Test getting statistics"""
        manager = AlertManager()
        manager.create_alert("Test", AlertSeverity.WARNING, "Test")
        stats = manager.get_statistics()
        assert stats["total_alerts"] == 1
        assert stats["active"] == 1


class TestAlertRules:
    """Tests for AlertRuleEngine class"""

    def test_init(self):
        """Test rule engine initialization"""
        engine = AlertRuleEngine()
        assert len(engine.rules) == 0

    def test_add_rule(self):
        """Test adding rule"""
        engine = AlertRuleEngine()
        rule = engine.add_rule(
            name="HighCPU",
            expression="cpu > 80",
            severity="warning",
        )
        assert rule.name == "HighCPU"
        assert len(engine.rules) == 1

    def test_evaluate(self):
        """Test rule evaluation"""
        engine = AlertRuleEngine()
        engine.add_rule("HighCPU", "cpu > 80", "warning")

        result = engine.evaluate("HighCPU", {"cpu": 90})
        assert result is not None
        assert result.is_firing is True

    def test_evaluate_not_firing(self):
        """Test rule not firing"""
        engine = AlertRuleEngine()
        engine.add_rule("HighCPU", "cpu > 80", "warning")

        result = engine.evaluate("HighCPU", {"cpu": 50})
        assert result.is_firing is False


class TestNotificationRouter:
    """Tests for NotificationRouter class"""

    def test_init(self):
        """Test router initialization"""
        router = NotificationRouter()
        assert len(router.channels) == 0

    def test_add_channel(self):
        """Test adding channel"""
        router = NotificationRouter()
        channel = NotificationChannel(
            name="email",
            channel_type=ChannelType.EMAIL,
        )
        router.add_channel(channel)
        assert "email" in router.channels

    def test_remove_channel(self):
        """Test removing channel"""
        router = NotificationRouter()
        router.add_channel(NotificationChannel("email", ChannelType.EMAIL))
        result = router.remove_channel("email")
        assert result is True

    def test_get_statistics(self):
        """Test getting statistics"""
        router = NotificationRouter()
        router.add_channel(NotificationChannel("email", ChannelType.EMAIL))
        stats = router.get_statistics()
        assert stats["channels"] == 1


# ============================================================================
# Incident Manager Tests
# ============================================================================

class TestIncidentManager:
    """Tests for IncidentManager class"""

    def test_init(self):
        """Test incident manager initialization"""
        manager = IncidentManager()
        assert len(manager.incidents) == 0

    def test_create_incident(self):
        """Test creating incident"""
        manager = IncidentManager()
        incident = manager.create_incident(
            title="Database Down",
            severity=IncidentSeverity.CRITICAL,
        )
        assert incident.title == "Database Down"
        assert incident.severity == IncidentSeverity.CRITICAL
        assert incident.status == IncidentStatus.OPEN

    def test_get_incident(self):
        """Test getting incident"""
        manager = IncidentManager()
        incident = manager.create_incident("Test", IncidentSeverity.MEDIUM)
        retrieved = manager.get_incident(incident.incident_id)
        assert retrieved.incident_id == incident.incident_id

    def test_update_status(self):
        """Test updating status"""
        manager = IncidentManager()
        incident = manager.create_incident("Test", IncidentSeverity.HIGH)
        result = manager.update_status(
            incident.incident_id,
            IncidentStatus.INVESTIGATING,
            user="admin",
        )
        assert result is True
        assert incident.status == IncidentStatus.INVESTIGATING

    def test_resolve(self):
        """Test resolving incident"""
        manager = IncidentManager()
        incident = manager.create_incident("Test", IncidentSeverity.HIGH)
        result = manager.resolve(
            incident.incident_id,
            root_cause="Fixed bug",
            user="admin",
        )
        assert result is True
        assert incident.status == IncidentStatus.RESOLVED

    def test_get_open_incidents(self):
        """Test getting open incidents"""
        manager = IncidentManager()
        manager.create_incident("Open1", IncidentSeverity.MEDIUM)
        manager.create_incident("Open2", IncidentSeverity.HIGH)
        incident = manager.create_incident("Resolved", IncidentSeverity.LOW)
        manager.resolve(incident.incident_id)

        open_incidents = manager.get_open_incidents()
        assert len(open_incidents) == 2

    def test_get_statistics(self):
        """Test getting statistics"""
        manager = IncidentManager()
        manager.create_incident("Test", IncidentSeverity.HIGH)
        stats = manager.get_statistics()
        assert stats["total_incidents"] == 1
        assert stats["open"] == 1


class TestIncidentTracker:
    """Tests for IncidentTracker class"""

    def test_init(self):
        """Test tracker initialization"""
        tracker = IncidentTracker()
        assert len(tracker.metrics) == 0

    def test_start_tracking(self):
        """Test start tracking"""
        tracker = IncidentTracker()
        metrics = tracker.start_tracking("INC001")
        assert metrics.incident_id == "INC001"
        assert metrics.created_at is not None

    def test_record_acknowledgement(self):
        """Test recording acknowledgement"""
        tracker = IncidentTracker()
        tracker.start_tracking("INC001")
        tracker.record_acknowledgement("INC001")
        metrics = tracker.get_metrics("INC001")
        assert metrics.acknowledged_at is not None

    def test_record_resolution(self):
        """Test recording resolution"""
        tracker = IncidentTracker()
        tracker.start_tracking("INC001")
        tracker.record_resolution("INC001")
        metrics = tracker.get_metrics("INC001")
        assert metrics.resolved_at is not None

    def test_calculate_mttr(self):
        """Test MTTR calculation"""
        tracker = IncidentTracker()
        tracker.start_tracking("INC001")
        tracker.record_resolution("INC001")

        mttr = tracker.calculate_mttr()
        assert mttr >= 0

    def test_get_summary(self):
        """Test getting summary"""
        tracker = IncidentTracker()
        tracker.start_tracking("INC001")
        summary = tracker.get_summary()
        assert summary["total_tracked"] == 1


class TestEscalationManager:
    """Tests for EscalationManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = EscalationManager()
        assert len(manager.rules) > 0  # Default rules

    def test_start_tracking(self):
        """Test start tracking"""
        manager = EscalationManager()
        manager.start_tracking("INC001")
        level = manager.get_current_level("INC001")
        assert level == EscalationLevel.L1

    def test_manual_escalate(self):
        """Test manual escalation"""
        manager = EscalationManager()
        manager.start_tracking("INC001")
        event = manager.manual_escalate(
            "INC001",
            EscalationLevel.L2,
            reason="Need more expertise",
            user="admin",
        )
        assert event.to_level == EscalationLevel.L2
        assert manager.get_current_level("INC001") == EscalationLevel.L2

    def test_get_statistics(self):
        """Test getting statistics"""
        manager = EscalationManager()
        stats = manager.get_statistics()
        assert "total_escalations" in stats


# ============================================================================
# Log Analyzer Tests
# ============================================================================

class TestLogAnalyzer:
    """Tests for LogAnalyzer class"""

    def test_init(self):
        """Test analyzer initialization"""
        analyzer = LogAnalyzer()
        assert len(analyzer.entries) == 0

    def test_add_entry(self):
        """Test adding entry"""
        analyzer = LogAnalyzer()
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=LogLevel.ERROR,
            message="Test error",
        )
        analyzer.add_entry(entry)
        assert len(analyzer.entries) == 1

    def test_analyze(self):
        """Test analyzing logs"""
        analyzer = LogAnalyzer()
        analyzer.add_entry(LogEntry(
            datetime.utcnow(), LogLevel.ERROR, "Error 1"
        ))
        analyzer.add_entry(LogEntry(
            datetime.utcnow(), LogLevel.WARNING, "Warning 1"
        ))
        analyzer.add_entry(LogEntry(
            datetime.utcnow(), LogLevel.INFO, "Info 1"
        ))

        result = analyzer.analyze()
        assert result.total_entries == 3
        assert result.by_level.get("ERROR", 0) == 1

    def test_search(self):
        """Test searching logs"""
        analyzer = LogAnalyzer()
        analyzer.add_entry(LogEntry(
            datetime.utcnow(), LogLevel.ERROR, "Database connection failed"
        ))
        analyzer.add_entry(LogEntry(
            datetime.utcnow(), LogLevel.INFO, "User logged in"
        ))

        results = analyzer.search("database")
        assert len(results) == 1

    def test_get_error_rate(self):
        """Test error rate calculation"""
        analyzer = LogAnalyzer()
        analyzer.add_entry(LogEntry(datetime.utcnow(), LogLevel.ERROR, "Error"))
        analyzer.add_entry(LogEntry(datetime.utcnow(), LogLevel.INFO, "Info"))

        rate = analyzer.get_error_rate()
        assert rate == 0.5


class TestLogParser:
    """Tests for LogParser class"""

    def test_init(self):
        """Test parser initialization"""
        parser = LogParser()
        assert len(parser.parsers) > 0

    def test_parse_json(self):
        """Test JSON parsing"""
        parser = LogParser()
        result = parser.parse('{"level": "ERROR", "message": "Test error"}')
        assert result.success is True
        assert result.entry["level"] == "ERROR"

    def test_parse_common_log(self):
        """Test common log format parsing"""
        parser = LogParser()
        line = '127.0.0.1 - - [10/Oct/2000:13:55:36 +0000] "GET / HTTP/1.0" 200 2326'
        result = parser.parse(line)
        assert result.success is True

    def test_parse_fallback(self):
        """Test fallback parsing"""
        parser = LogParser()
        result = parser.parse("This is a simple log line")
        assert result.success is True


class TestLogCorrelator:
    """Tests for LogCorrelator class"""

    def test_init(self):
        """Test correlator initialization"""
        correlator = LogCorrelator()
        assert len(correlator.groups) == 0

    def test_correlate(self):
        """Test correlation"""
        correlator = LogCorrelator()
        entry = {
            "message": "Test",
            "extra": {"request_id": "req123"},
        }
        group = correlator.correlate(entry)
        assert group is not None
        assert group.correlation_type == CorrelationType.REQUEST_ID

    def test_get_group(self):
        """Test getting group"""
        correlator = LogCorrelator()
        entry = {"message": "Test", "extra": {"trace_id": "trace123"}}
        group = correlator.correlate(entry)
        retrieved = correlator.get_group(group.correlation_id)
        assert retrieved is not None


# ============================================================================
# Dashboard Builder Tests
# ============================================================================

class TestDashboardBuilder:
    """Tests for DashboardBuilder class"""

    def test_init(self):
        """Test builder initialization"""
        builder = DashboardBuilder()
        assert len(builder.dashboards) == 0

    def test_create_dashboard(self):
        """Test creating dashboard"""
        builder = DashboardBuilder()
        dashboard = builder.create_dashboard(
            name="System Dashboard",
            dashboard_type=DashboardType.OPERATIONAL,
        )
        assert dashboard.name == "System Dashboard"
        assert dashboard.dashboard_id is not None

    def test_add_widget(self):
        """Test adding widget"""
        builder = DashboardBuilder()
        dashboard = builder.create_dashboard("Test")
        widget = builder.add_widget(
            dashboard.dashboard_id,
            widget_type="gauge",
            title="CPU Usage",
            position={"x": 0, "y": 0, "w": 2, "h": 2},
        )
        assert widget is not None
        assert len(dashboard.widgets) == 1

    def test_remove_widget(self):
        """Test removing widget"""
        builder = DashboardBuilder()
        dashboard = builder.create_dashboard("Test")
        widget = builder.add_widget(
            dashboard.dashboard_id,
            "gauge",
            "Test",
            {"x": 0, "y": 0, "w": 1, "h": 1},
        )
        result = builder.remove_widget(dashboard.dashboard_id, widget["widget_id"])
        assert result is True
        assert len(dashboard.widgets) == 0

    def test_clone_dashboard(self):
        """Test cloning dashboard"""
        builder = DashboardBuilder()
        original = builder.create_dashboard("Original")
        builder.add_widget(
            original.dashboard_id,
            "gauge",
            "Test",
            {"x": 0, "y": 0, "w": 1, "h": 1},
        )
        clone = builder.clone_dashboard(original.dashboard_id, "Clone")
        assert clone is not None
        assert clone.name == "Clone"
        assert len(clone.widgets) == len(original.widgets)

    def test_list_dashboards(self):
        """Test listing dashboards"""
        builder = DashboardBuilder()
        builder.create_dashboard("Dashboard 1")
        builder.create_dashboard("Dashboard 2")
        dashboards = builder.list_dashboards()
        assert len(dashboards) == 2


class TestWidgetFactory:
    """Tests for WidgetFactory class"""

    def test_init(self):
        """Test factory initialization"""
        factory = WidgetFactory()
        assert len(factory._definitions) > 0

    def test_create_widget(self):
        """Test creating widget"""
        factory = WidgetFactory()
        widget = factory.create_widget(
            widget_type=WidgetType.GAUGE,
            title="CPU Usage",
        )
        assert widget is not None
        assert widget["title"] == "CPU Usage"

    def test_get_definition(self):
        """Test getting definition"""
        factory = WidgetFactory()
        definition = factory.get_definition(WidgetType.GAUGE)
        assert definition is not None
        assert definition.type == WidgetType.GAUGE

    def test_list_definitions(self):
        """Test listing definitions"""
        factory = WidgetFactory()
        definitions = factory.list_definitions()
        assert len(definitions) > 0

    def test_validate_widget(self):
        """Test validating widget"""
        factory = WidgetFactory()
        widget = {
            "type": "gauge",
            "position": {"x": 0, "y": 0, "w": 1, "h": 1},
        }
        errors = factory.validate_widget(widget)
        assert len(errors) == 0


class TestDataVisualizer:
    """Tests for DataVisualizer class"""

    def test_init(self):
        """Test visualizer initialization"""
        viz = DataVisualizer()
        assert viz is not None

    def test_create_line_chart(self):
        """Test creating line chart"""
        viz = DataVisualizer()
        data = [
            {"time": "10:00", "value": 50},
            {"time": "11:00", "value": 60},
        ]
        chart = viz.create_line_chart(
            data,
            x_field="time",
            y_field="value",
            title="Performance",
        )
        assert chart["type"] == "line"
        assert chart["title"] == "Performance"

    def test_create_bar_chart(self):
        """Test creating bar chart"""
        viz = DataVisualizer()
        data = [
            {"category": "A", "value": 100},
            {"category": "B", "value": 200},
        ]
        chart = viz.create_bar_chart(
            data,
            x_field="category",
            y_field="value",
            title="Sales",
        )
        assert chart["type"] == "column"

    def test_create_gauge(self):
        """Test creating gauge"""
        viz = DataVisualizer()
        gauge = viz.create_gauge(
            value=75,
            min_val=0,
            max_val=100,
            title="CPU",
            thresholds={"warning": 70, "critical": 90},
        )
        assert gauge["type"] == "gauge"
        assert gauge["status"] == "warning"

    def test_calculate_statistics(self):
        """Test statistics calculation"""
        viz = DataVisualizer()
        values = [10, 20, 30, 40, 50]
        stats = viz.calculate_statistics(values)
        assert stats["count"] == 5
        assert stats["mean"] == 30

    def test_format_value(self):
        """Test value formatting"""
        viz = DataVisualizer()
        assert viz.format_value(1500, "number") == "1.50K"
        assert viz.format_value(0.75, "percent") == "0.75%"
        assert viz.format_value(1234, "currency") == "$1,234.00"
