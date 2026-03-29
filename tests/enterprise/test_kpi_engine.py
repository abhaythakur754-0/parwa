"""
Tests for KPI Engine
Enterprise Analytics & Reporting - Week 44 Builder 2
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from enterprise.analytics.kpi_engine import (
    KPIEngine,
    KPIDefinition,
    KPIValue,
    KPITarget,
    KPICategory,
    KPITrend,
    KPIStatus,
    KPICalculator
)
from enterprise.analytics.kpi_alerts import (
    KPIAlertManager,
    AlertRule,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertCondition
)


# Test Fixtures
@pytest.fixture
def kpi_engine():
    """Create a test KPI engine"""
    return KPIEngine()


@pytest.fixture
def kpi_target():
    """Create a test KPI target"""
    return KPITarget(
        target_value=100.0,
        warning_threshold=0.9,
        critical_threshold=0.7
    )


@pytest.fixture
def alert_manager(kpi_engine):
    """Create a test alert manager"""
    return KPIAlertManager(kpi_engine)


# KPITarget Tests
class TestKPITarget:
    """Tests for KPITarget"""
    
    def test_target_creation(self, kpi_target):
        """Test target can be created"""
        assert kpi_target.target_value == 100.0
        assert kpi_target.warning_threshold == 0.9
    
    def test_evaluate_on_track(self, kpi_target):
        """Test evaluating on track value"""
        status = kpi_target.evaluate(100.0)
        assert status == KPIStatus.ON_TRACK
    
    def test_evaluate_at_risk(self, kpi_target):
        """Test evaluating at risk value"""
        status = kpi_target.evaluate(90.0)
        assert status == KPIStatus.AT_RISK
    
    def test_evaluate_off_track(self, kpi_target):
        """Test evaluating off track value"""
        status = kpi_target.evaluate(50.0)
        assert status == KPIStatus.OFF_TRACK
    
    def test_less_than_comparison(self):
        """Test less than comparison"""
        target = KPITarget(target_value=10.0, comparison="less_than")
        
        assert target.evaluate(5.0) == KPIStatus.ON_TRACK
        assert target.evaluate(15.0) == KPIStatus.OFF_TRACK


# KPIDefinition Tests
class TestKPIDefinition:
    """Tests for KPIDefinition"""
    
    def test_definition_creation(self):
        """Test KPI definition can be created"""
        definition = KPIDefinition(
            id="test_kpi",
            name="Test KPI",
            description="A test KPI",
            category=KPICategory.PERFORMANCE,
            unit="ms",
            calculation="avg(response_time)"
        )
        
        assert definition.id == "test_kpi"
        assert definition.category == KPICategory.PERFORMANCE
    
    def test_definition_to_dict(self):
        """Test KPI definition serialization"""
        definition = KPIDefinition(
            id="test",
            name="Test",
            description="Test",
            category=KPICategory.QUALITY,
            unit="%",
            calculation="avg"
        )
        
        data = definition.to_dict()
        
        assert data["id"] == "test"
        assert data["category"] == "quality"


# KPIValue Tests
class TestKPIValue:
    """Tests for KPIValue"""
    
    def test_value_creation(self):
        """Test KPI value can be created"""
        value = KPIValue(
            kpi_id="test",
            value=100.0,
            timestamp=datetime.utcnow()
        )
        
        assert value.kpi_id == "test"
        assert value.value == 100.0
    
    def test_calculate_change(self):
        """Test change calculation"""
        value = KPIValue(
            kpi_id="test",
            value=110.0,
            timestamp=datetime.utcnow(),
            previous_value=100.0
        )
        
        change = value.calculate_change()
        assert change == 10.0
    
    def test_calculate_change_no_previous(self):
        """Test change calculation without previous"""
        value = KPIValue(
            kpi_id="test",
            value=100.0,
            timestamp=datetime.utcnow()
        )
        
        change = value.calculate_change()
        assert change is None
    
    def test_value_to_dict(self):
        """Test KPI value serialization"""
        value = KPIValue(
            kpi_id="test",
            value=100.0,
            timestamp=datetime.utcnow(),
            status=KPIStatus.ON_TRACK,
            trend=KPITrend.UP
        )
        
        data = value.to_dict()
        
        assert data["kpi_id"] == "test"
        assert data["status"] == "on_track"
        assert data["trend"] == "up"


# KPIEngine Tests
class TestKPIEngine:
    """Tests for KPIEngine"""
    
    def test_engine_initialization(self, kpi_engine):
        """Test engine initializes with default KPIs"""
        assert kpi_engine is not None
    
    def test_register_kpi(self, kpi_engine):
        """Test registering a new KPI"""
        definition = KPIDefinition(
            id="custom_kpi",
            name="Custom KPI",
            description="Custom",
            category=KPICategory.CUSTOMER,
            unit="score",
            calculation="avg"
        )
        
        kpi_engine.register_kpi(definition)
        
        assert kpi_engine.get_kpi_definition("custom_kpi") is not None
    
    def test_get_kpi_definition(self, kpi_engine):
        """Test getting KPI definition"""
        definition = kpi_engine.get_kpi_definition("ticket_resolution_time")
        
        assert definition is not None
        assert definition.name == "Avg Ticket Resolution Time"
    
    def test_list_kpis(self, kpi_engine):
        """Test listing KPIs"""
        kpis = kpi_engine.list_kpis()
        assert len(kpis) > 0
    
    def test_list_kpis_by_category(self, kpi_engine):
        """Test filtering KPIs by category"""
        kpis = kpi_engine.list_kpis(category=KPICategory.PERFORMANCE)
        
        for kpi in kpis:
            assert kpi.category == KPICategory.PERFORMANCE
    
    def test_record_value(self, kpi_engine):
        """Test recording a KPI value"""
        value = kpi_engine.record_value("ticket_resolution_time", 25.0)
        
        assert value is not None
        assert value.value == 25.0
    
    def test_record_value_with_target(self, kpi_engine):
        """Test recording value with target evaluation"""
        value = kpi_engine.record_value("ticket_resolution_time", 25.0)
        
        # Target is 30 min with less_than comparison, so 25 min is on track
        assert value.status == KPIStatus.ON_TRACK
    
    def test_record_value_at_risk(self, kpi_engine):
        """Test recording at risk value"""
        # Resolution time above target (30 min) - should be at_risk
        # Target is 30 min with less_than comparison, so > 30 triggers warning
        value = kpi_engine.record_value("ticket_resolution_time", 31.0)
        
        assert value.status == KPIStatus.AT_RISK
    
    def test_get_current_value(self, kpi_engine):
        """Test getting current KPI value"""
        kpi_engine.record_value("ticket_resolution_time", 20.0)
        kpi_engine.record_value("ticket_resolution_time", 25.0)
        
        current = kpi_engine.get_current_value("ticket_resolution_time")
        
        assert current.value == 25.0
    
    def test_get_history(self, kpi_engine):
        """Test getting KPI history"""
        kpi_engine.record_value("ticket_resolution_time", 20.0)
        kpi_engine.record_value("ticket_resolution_time", 25.0)
        kpi_engine.record_value("ticket_resolution_time", 30.0)
        
        history = kpi_engine.get_history("ticket_resolution_time")
        
        assert len(history) == 3
    
    def test_calculate_statistics(self, kpi_engine):
        """Test calculating statistics"""
        for i in range(10):
            kpi_engine.record_value("ticket_resolution_time", float(i * 5))
        
        stats = kpi_engine.calculate_statistics("ticket_resolution_time")
        
        assert "min" in stats
        assert "max" in stats
        assert "avg" in stats
    
    def test_get_summary(self, kpi_engine):
        """Test getting KPI summary"""
        kpi_engine.record_value("ticket_resolution_time", 25.0)
        
        summary = kpi_engine.get_summary()
        
        assert "total_kpis" in summary
        assert "by_status" in summary


# KPICalculator Tests
class TestKPICalculator:
    """Tests for KPICalculator"""
    
    def test_average(self):
        """Test average calculation"""
        result = KPICalculator.average([1, 2, 3, 4, 5])
        assert result == 3.0
    
    def test_average_empty(self):
        """Test average with empty list"""
        result = KPICalculator.average([])
        assert result == 0.0
    
    def test_percentage(self):
        """Test percentage calculation"""
        result = KPICalculator.percentage(25, 100)
        assert result == 25.0
    
    def test_percentage_zero_total(self):
        """Test percentage with zero total"""
        result = KPICalculator.percentage(25, 0)
        assert result == 0.0
    
    def test_rate(self):
        """Test rate calculation"""
        result = KPICalculator.rate(10, 100)
        assert result == 10.0
    
    def test_percentile(self):
        """Test percentile calculation"""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        p50 = KPICalculator.percentile(values, 50)
        assert 4.5 <= p50 <= 6.5
        
        p90 = KPICalculator.percentile(values, 90)
        assert 8.5 <= p90 <= 10.0
    
    def test_moving_average(self):
        """Test moving average calculation"""
        values = [1, 2, 3, 4, 5]
        result = KPICalculator.moving_average(values, 3)
        
        assert len(result) == 3
        assert result[0] == 2.0  # (1+2+3)/3
    
    def test_growth_rate(self):
        """Test growth rate calculation"""
        values = [100, 110, 121, 130]
        result = KPICalculator.growth_rate(values)
        
        assert len(result) == 3
        assert result[0] == 10.0  # (110-100)/100 * 100


# AlertRule Tests
class TestAlertRule:
    """Tests for AlertRule"""
    
    def test_rule_creation(self):
        """Test alert rule can be created"""
        rule = AlertRule(
            id="rule-1",
            name="Test Rule",
            kpi_id="test_kpi",
            condition=AlertCondition.GREATER_THAN,
            threshold=100.0,
            severity=AlertSeverity.WARNING
        )
        
        assert rule.id == "rule-1"
        assert rule.enabled is True
    
    def test_rule_to_dict(self):
        """Test alert rule serialization"""
        rule = AlertRule(
            id="rule-1",
            name="Test",
            kpi_id="test",
            condition=AlertCondition.LESS_THAN,
            threshold=50.0,
            severity=AlertSeverity.CRITICAL
        )
        
        data = rule.to_dict()
        
        assert data["id"] == "rule-1"
        assert data["condition"] == "less_than"


# Alert Tests
class TestAlert:
    """Tests for Alert"""
    
    def test_alert_creation(self):
        """Test alert can be created"""
        alert = Alert(
            id="alert-1",
            rule_id="rule-1",
            kpi_id="test_kpi",
            severity=AlertSeverity.WARNING,
            message="Test alert",
            value=120.0,
            threshold=100.0
        )
        
        assert alert.id == "alert-1"
        assert alert.status == AlertStatus.ACTIVE
    
    def test_alert_to_dict(self):
        """Test alert serialization"""
        alert = Alert(
            id="alert-1",
            rule_id="rule-1",
            kpi_id="test",
            severity=AlertSeverity.CRITICAL,
            message="Test",
            value=150.0,
            threshold=100.0
        )
        
        data = alert.to_dict()
        
        assert data["severity"] == "critical"
        assert data["status"] == "active"


# KPIAlertManager Tests
class TestKPIAlertManager:
    """Tests for KPIAlertManager"""
    
    def test_manager_initialization(self, alert_manager):
        """Test manager initializes correctly"""
        assert alert_manager is not None
    
    def test_create_rule(self, alert_manager):
        """Test creating an alert rule"""
        rule = alert_manager.create_rule(
            name="Test Rule",
            kpi_id="ticket_resolution_time",
            condition=AlertCondition.GREATER_THAN,
            threshold=60.0,
            severity=AlertSeverity.WARNING
        )
        
        assert rule is not None
        assert rule.name == "Test Rule"
    
    def test_get_rule(self, alert_manager):
        """Test getting an alert rule"""
        created = alert_manager.create_rule(
            name="Test",
            kpi_id="test",
            condition=AlertCondition.GREATER_THAN,
            threshold=100.0,
            severity=AlertSeverity.INFO
        )
        
        retrieved = alert_manager.get_rule(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
    
    def test_list_rules(self, alert_manager):
        """Test listing alert rules"""
        alert_manager.create_rule(
            name="Rule 1",
            kpi_id="kpi1",
            condition=AlertCondition.GREATER_THAN,
            threshold=100.0,
            severity=AlertSeverity.INFO
        )
        alert_manager.create_rule(
            name="Rule 2",
            kpi_id="kpi2",
            condition=AlertCondition.LESS_THAN,
            threshold=50.0,
            severity=AlertSeverity.WARNING
        )
        
        rules = alert_manager.list_rules()
        assert len(rules) >= 2
    
    def test_delete_rule(self, alert_manager):
        """Test deleting an alert rule"""
        rule = alert_manager.create_rule(
            name="Test",
            kpi_id="test",
            condition=AlertCondition.GREATER_THAN,
            threshold=100.0,
            severity=AlertSeverity.INFO
        )
        
        result = alert_manager.delete_rule(rule.id)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_evaluate_trigger_alert(self, alert_manager):
        """Test evaluating and triggering an alert"""
        alert_manager.create_rule(
            name="High Resolution Time",
            kpi_id="ticket_resolution_time",
            condition=AlertCondition.GREATER_THAN,
            threshold=25.0,
            severity=AlertSeverity.WARNING
        )
        
        alerts = await alert_manager.evaluate("ticket_resolution_time", 30.0)
        
        assert len(alerts) >= 1
        assert alerts[0].value == 30.0
    
    def test_acknowledge_alert(self, alert_manager):
        """Test acknowledging an alert"""
        alert = Alert(
            id="alert-1",
            rule_id="rule-1",
            kpi_id="test",
            severity=AlertSeverity.WARNING,
            message="Test",
            value=100.0,
            threshold=80.0
        )
        alert_manager._alerts.append(alert)
        
        result = alert_manager.acknowledge_alert("alert-1", "user1")
        
        assert result.status == AlertStatus.ACKNOWLEDGED
        assert result.acknowledged_by == "user1"
    
    def test_resolve_alert(self, alert_manager):
        """Test resolving an alert"""
        alert = Alert(
            id="alert-1",
            rule_id="rule-1",
            kpi_id="test",
            severity=AlertSeverity.WARNING,
            message="Test",
            value=100.0,
            threshold=80.0
        )
        alert_manager._alerts.append(alert)
        
        result = alert_manager.resolve_alert("alert-1")
        
        assert result.status == AlertStatus.RESOLVED
    
    def test_snooze_alert(self, alert_manager):
        """Test snoozing an alert"""
        alert = Alert(
            id="alert-1",
            rule_id="rule-1",
            kpi_id="test",
            severity=AlertSeverity.WARNING,
            message="Test",
            value=100.0,
            threshold=80.0
        )
        alert_manager._alerts.append(alert)
        
        result = alert_manager.snooze_alert("alert-1", 30)
        
        assert result.status == AlertStatus.SNOOZED
        assert result.snoozed_until is not None
    
    def test_list_alerts(self, alert_manager):
        """Test listing alerts"""
        alert_manager._alerts = [
            Alert("a1", "r1", "k1", AlertSeverity.INFO, "Test 1", 100, 80),
            Alert("a2", "r1", "k1", AlertSeverity.WARNING, "Test 2", 150, 80),
        ]
        
        alerts = alert_manager.list_alerts()
        assert len(alerts) == 2
    
    def test_get_active_alerts_count(self, alert_manager):
        """Test counting active alerts"""
        alert_manager._alerts = [
            Alert("a1", "r1", "k1", AlertSeverity.INFO, "Test", 100, 80),
            Alert("a2", "r1", "k1", AlertSeverity.WARNING, "Test", 150, 80),
            Alert("a3", "r1", "k1", AlertSeverity.CRITICAL, "Test", 200, 80),
        ]
        
        counts = alert_manager.get_active_alerts_count()
        
        assert counts["info"] == 1
        assert counts["warning"] == 1
        assert counts["critical"] == 1


# Enum Tests
class TestEnums:
    """Tests for enum values"""
    
    def test_kpi_category(self):
        """Test KPICategory enum"""
        assert KPICategory.PERFORMANCE.value == "performance"
        assert KPICategory.CUSTOMER.value == "customer"
    
    def test_kpi_trend(self):
        """Test KPITrend enum"""
        assert KPITrend.UP.value == "up"
        assert KPITrend.DOWN.value == "down"
    
    def test_kpi_status(self):
        """Test KPIStatus enum"""
        assert KPIStatus.ON_TRACK.value == "on_track"
        assert KPIStatus.OFF_TRACK.value == "off_track"
    
    def test_alert_severity(self):
        """Test AlertSeverity enum"""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.CRITICAL.value == "critical"
    
    def test_alert_status(self):
        """Test AlertStatus enum"""
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.RESOLVED.value == "resolved"
    
    def test_alert_condition(self):
        """Test AlertCondition enum"""
        assert AlertCondition.GREATER_THAN.value == "greater_than"
        assert AlertCondition.LESS_THAN.value == "less_than"
