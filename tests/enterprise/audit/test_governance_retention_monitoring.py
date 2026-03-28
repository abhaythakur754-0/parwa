# Tests for Week 49 Builders 3, 4, 5
# Combined tests for Data Governance, Retention, and Compliance Monitoring

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Builder 3 imports
from enterprise.audit.data_governance import (
    DataGovernance,
    DataAsset,
    GovernancePolicy,
    DataClassification,
    DataCategory
)
from enterprise.audit.data_classifier import (
    DataClassifier,
    ClassificationRule,
    ClassificationResult,
    SensitivityLevel
)
from enterprise.audit.data_lineage import (
    DataLineage,
    LineageNode,
    LineageEdge
)

# Builder 4 imports
from enterprise.audit.retention_manager import (
    RetentionManager,
    RetentionPolicy,
    RetentionItem,
    RetentionAction
)
from enterprise.audit.retention_enforcer import (
    RetentionEnforcer,
    EnforcementJob,
    EnforcementAction
)
from enterprise.audit.retention_reports import (
    RetentionReports,
    RetentionReport,
    ReportType
)

# Builder 5 imports
from enterprise.audit.compliance_monitor import (
    ComplianceMonitor,
    Monitor,
    MonitorCheck,
    CheckResult
)
from enterprise.audit.violation_detector import (
    ViolationDetector,
    Violation,
    ViolationType,
    ViolationSeverity
)
from enterprise.audit.compliance_alerts import (
    ComplianceAlerts,
    Alert,
    AlertPriority,
    AlertStatus
)


# ============== BUILDER 3: DATA GOVERNANCE TESTS ==============

class TestDataGovernance:
    def test_register_asset(self):
        gov = DataGovernance()
        asset = gov.register_asset(
            tenant_id="t1",
            name="Customer Database",
            classification=DataClassification.CONFIDENTIAL,
            category=DataCategory.PII,
            owner="admin"
        )
        assert asset.tenant_id == "t1"
        assert asset.classification == DataClassification.CONFIDENTIAL

    def test_create_policy(self):
        gov = DataGovernance()
        policy = gov.create_policy(
            tenant_id="t1",
            name="PII Policy",
            classification=DataClassification.CONFIDENTIAL
        )
        assert policy.name == "PII Policy"

    def test_get_asset(self):
        gov = DataGovernance()
        created = gov.register_asset("t1", "Test", DataClassification.INTERNAL, DataCategory.OPERATIONAL)
        asset = gov.get_asset(created.id)
        assert asset.id == created.id

    def test_get_assets_by_classification(self):
        gov = DataGovernance()
        gov.register_asset("t1", "Public", DataClassification.PUBLIC, DataCategory.OPERATIONAL)
        gov.register_asset("t1", "Confidential", DataClassification.CONFIDENTIAL, DataCategory.PII)
        
        assets = gov.get_assets_by_classification("t1", DataClassification.CONFIDENTIAL)
        assert len(assets) == 1

    def test_get_assets_by_category(self):
        gov = DataGovernance()
        gov.register_asset("t1", "PII Data", DataClassification.CONFIDENTIAL, DataCategory.PII)
        gov.register_asset("t1", "Financial", DataClassification.RESTRICTED, DataCategory.FINANCIAL)
        
        assets = gov.get_assets_by_category("t1", DataCategory.PII)
        assert len(assets) == 1

    def test_get_compliance_report(self):
        gov = DataGovernance()
        gov.register_asset("t1", "A1", DataClassification.PUBLIC, DataCategory.OPERATIONAL)
        report = gov.get_compliance_report("t1")
        assert report["total_assets"] == 1


class TestDataClassifier:
    def test_classify_email(self):
        classifier = DataClassifier()
        result = classifier.classify("Contact us at test@example.com")
        assert result.matched is True
        assert "email" in result.tags

    def test_classify_ssn(self):
        classifier = DataClassifier()
        result = classifier.classify("SSN: 123-45-6789")
        assert result.matched is True
        assert "ssn" in result.tags

    def test_classify_credit_card(self):
        classifier = DataClassifier()
        result = classifier.classify("Card: 4111-1111-1111-1111")
        assert result.matched is True
        assert "credit_card" in result.tags

    def test_classify_no_match(self):
        classifier = DataClassifier()
        result = classifier.classify("This is just plain text")
        assert result.matched is False

    def test_add_custom_rule(self):
        classifier = DataClassifier()
        rule = ClassificationRule(
            name="Custom ID",
            pattern=r"CUST-\d{6}",
            classification="internal"
        )
        classifier.add_rule(rule)
        result = classifier.classify("ID: CUST-123456")
        assert result.matched is True


class TestDataLineage:
    def test_add_node(self):
        lineage = DataLineage()
        node = lineage.add_node("t1", "Source", "source", "Database")
        assert node.name == "Source"

    def test_add_edge(self):
        lineage = DataLineage()
        source = lineage.add_node("t1", "Source", "source")
        target = lineage.add_node("t1", "Target", "destination")
        
        edge = lineage.add_edge(source.id, target.id, "t1")
        assert edge is not None

    def test_get_upstream(self):
        lineage = DataLineage()
        source = lineage.add_node("t1", "Source", "source")
        target = lineage.add_node("t1", "Target", "destination")
        lineage.add_edge(source.id, target.id, "t1")
        
        upstream = lineage.get_upstream(target.id)
        assert len(upstream) == 1

    def test_get_downstream(self):
        lineage = DataLineage()
        source = lineage.add_node("t1", "Source", "source")
        target = lineage.add_node("t1", "Target", "destination")
        lineage.add_edge(source.id, target.id, "t1")
        
        downstream = lineage.get_downstream(source.id)
        assert len(downstream) == 1


# ============== BUILDER 4: RETENTION TESTS ==============

class TestRetentionManager:
    def test_create_policy(self):
        manager = RetentionManager()
        policy = manager.create_policy(
            tenant_id="t1",
            name="7-Year Retention",
            data_type="financial_records",
            retention_days=2555
        )
        assert policy.retention_days == 2555

    def test_register_item(self):
        manager = RetentionManager()
        policy = manager.create_policy("t1", "Test", "documents", 365)
        item = manager.register_item("t1", policy.id, "document", "doc1")
        assert item is not None

    def test_get_expired_items(self):
        manager = RetentionManager()
        policy = manager.create_policy("t1", "Test", "test", retention_days=0)
        item = manager.register_item("t1", policy.id, "test", "data1")
        item.expires_at = datetime.utcnow() - timedelta(days=1)
        
        expired = manager.get_expired_items("t1")
        assert len(expired) == 1

    def test_legal_hold(self):
        manager = RetentionManager()
        policy = manager.create_policy("t1", "Test", "test", 365)
        manager.apply_legal_hold(policy.id)
        assert policy.legal_hold is True

    def test_get_metrics(self):
        manager = RetentionManager()
        manager.create_policy("t1", "Test", "test", 365)
        metrics = manager.get_metrics()
        assert metrics["total_policies"] == 1


class TestRetentionEnforcer:
    def test_create_job(self):
        enforcer = RetentionEnforcer()
        job = enforcer.create_job("t1", "policy1", EnforcementAction.DELETE)
        assert job.action == EnforcementAction.DELETE

    def test_execute_job(self):
        enforcer = RetentionEnforcer()
        job = enforcer.create_job("t1", "policy1", EnforcementAction.ARCHIVE)
        result = enforcer.execute_job(job.id)
        assert result.status.value == "completed"


class TestRetentionReports:
    def test_generate_summary(self):
        reports = RetentionReports()
        report = reports.generate_summary_report("t1")
        assert report.report_type == ReportType.SUMMARY

    def test_generate_expiring(self):
        reports = RetentionReports()
        report = reports.generate_expiring_report("t1", days=30)
        assert report.report_type == ReportType.EXPIRING


# ============== BUILDER 5: COMPLIANCE MONITORING TESTS ==============

class TestComplianceMonitor:
    def test_create_monitor(self):
        monitor = ComplianceMonitor()
        m = monitor.create_monitor("t1", "Test Monitor")
        assert m.name == "Test Monitor"

    def test_run_check(self):
        monitor = ComplianceMonitor()
        monitor.register_check_handler("test", lambda p: {"pass": True, "score": 100})
        m = monitor.create_monitor("t1", "Test")
        
        check = monitor.run_check(m.id, "test")
        assert check.result == CheckResult.PASS

    def test_get_compliance_score(self):
        monitor = ComplianceMonitor()
        monitor.register_check_handler("test", lambda p: {"pass": True, "score": 100})
        m = monitor.create_monitor("t1", "Test")
        monitor.run_check(m.id, "test")
        
        score = monitor.get_compliance_score(m.id)
        assert score == 100.0


class TestViolationDetector:
    def test_detect_violation(self):
        detector = ViolationDetector()
        v = detector.detect(
            tenant_id="t1",
            type=ViolationType.ACCESS_VIOLATION,
            severity=ViolationSeverity.HIGH,
            description="Unauthorized access"
        )
        assert v.severity == ViolationSeverity.HIGH

    def test_resolve_violation(self):
        detector = ViolationDetector()
        v = detector.detect("t1", ViolationType.POLICY_VIOLATION, ViolationSeverity.LOW, "Test")
        result = detector.resolve_violation(v.id)
        assert result is True
        assert v.resolved is True

    def test_get_critical_violations(self):
        detector = ViolationDetector()
        detector.detect("t1", ViolationType.SECURITY_VIOLATION, ViolationSeverity.CRITICAL, "Critical!")
        detector.detect("t1", ViolationType.POLICY_VIOLATION, ViolationSeverity.LOW, "Minor")
        
        critical = detector.get_critical_violations("t1")
        assert len(critical) == 1


class TestComplianceAlerts:
    def test_create_alert(self):
        alerts = ComplianceAlerts()
        alert = alerts.create_alert(
            tenant_id="t1",
            name="Test Alert",
            message="Test message",
            priority=AlertPriority.HIGH
        )
        assert alert.priority == AlertPriority.HIGH

    def test_acknowledge_alert(self):
        alerts = ComplianceAlerts()
        alert = alerts.create_alert("t1", "Test", "Message")
        result = alerts.acknowledge_alert(alert.id, "admin")
        assert result is True
        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_resolve_alert(self):
        alerts = ComplianceAlerts()
        alert = alerts.create_alert("t1", "Test", "Message")
        result = alerts.resolve_alert(alert.id)
        assert result is True
        assert alert.status == AlertStatus.RESOLVED

    def test_get_critical_alerts(self):
        alerts = ComplianceAlerts()
        alerts.create_alert("t1", "Critical", "Msg", AlertPriority.CRITICAL)
        alerts.create_alert("t1", "Low", "Msg", AlertPriority.LOW)
        
        critical = alerts.get_critical_alerts("t1")
        assert len(critical) == 1

    @pytest.mark.asyncio
    async def test_send_alert(self):
        alerts = ComplianceAlerts()
        alert = alerts.create_alert("t1", "Test", "Message")
        
        handler_called = []
        def handler(a):
            handler_called.append(a.id)
        
        alerts.register_handler(handler)
        await alerts.send_alert(alert.id)
        
        assert alert.status == AlertStatus.SENT
        assert alert.id in handler_called
