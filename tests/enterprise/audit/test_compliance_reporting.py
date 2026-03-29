# Tests for Week 49 Builder 2 - Compliance Reporting
# Unit tests for compliance_reporter.py, compliance_rules.py, compliance_scheduler.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from enterprise.audit.compliance_reporter import (
    ComplianceReporter,
    ComplianceReport,
    ComplianceFinding,
    ComplianceFramework,
    ReportStatus,
    ReportFormat
)

from enterprise.audit.compliance_rules import (
    ComplianceRuleEngine,
    ComplianceRule,
    RuleType,
    RuleSeverity,
    RuleStatus,
    RuleEvaluationResult
)

from enterprise.audit.compliance_scheduler import (
    ComplianceScheduler,
    ScheduledCheck,
    CheckExecution,
    ScheduleType,
    ScheduleStatus
)


# ============== COMPLIANCE REPORTER TESTS ==============

class TestComplianceReporter:
    def test_create_report(self):
        reporter = ComplianceReporter()
        report = reporter.create_report(
            tenant_id="t1",
            framework=ComplianceFramework.GDPR,
            name="GDPR Report",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )
        assert report.tenant_id == "t1"
        assert report.framework == ComplianceFramework.GDPR

    def test_add_finding(self):
        reporter = ComplianceReporter()
        report = reporter.create_report(
            tenant_id="t1",
            framework=ComplianceFramework.HIPAA,
            name="HIPAA Report",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow()
        )
        finding = reporter.add_finding(
            report_id=report.id,
            category="privacy",
            requirement="PHI access control",
            status="compliant",
            severity="high"
        )
        assert finding is not None
        assert finding.status == "compliant"
        assert len(report.findings) == 1

    def test_generate_report(self):
        reporter = ComplianceReporter()
        report = reporter.generate_report(
            tenant_id="t1",
            framework=ComplianceFramework.GDPR,
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow()
        )
        assert report.status == ReportStatus.COMPLETED
        assert report.score >= 0

    def test_get_report(self):
        reporter = ComplianceReporter()
        created = reporter.create_report(
            tenant_id="t1",
            framework=ComplianceFramework.SOC2,
            name="SOC2 Report",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow()
        )
        report = reporter.get_report(created.id)
        assert report.id == created.id

    def test_get_reports_by_tenant(self):
        reporter = ComplianceReporter()
        reporter.create_report("t1", ComplianceFramework.GDPR, "R1", datetime.utcnow(), datetime.utcnow())
        reporter.create_report("t1", ComplianceFramework.HIPAA, "R2", datetime.utcnow(), datetime.utcnow())
        reporter.create_report("t2", ComplianceFramework.SOC2, "R3", datetime.utcnow(), datetime.utcnow())

        reports = reporter.get_reports_by_tenant("t1")
        assert len(reports) == 2

    def test_get_reports_by_framework(self):
        reporter = ComplianceReporter()
        reporter.create_report("t1", ComplianceFramework.GDPR, "R1", datetime.utcnow(), datetime.utcnow())
        reporter.create_report("t1", ComplianceFramework.HIPAA, "R2", datetime.utcnow(), datetime.utcnow())

        reports = reporter.get_reports_by_tenant("t1", ComplianceFramework.GDPR)
        assert len(reports) == 1

    def test_export_report(self):
        reporter = ComplianceReporter()
        report = reporter.create_report("t1", ComplianceFramework.GDPR, "Test", datetime.utcnow(), datetime.utcnow())
        exported = reporter.export_report(report.id)
        assert exported["tenant_id"] == "t1"
        assert exported["framework"] == "gdpr"

    def test_delete_report(self):
        reporter = ComplianceReporter()
        report = reporter.create_report("t1", ComplianceFramework.GDPR, "Test", datetime.utcnow(), datetime.utcnow())
        result = reporter.delete_report(report.id)
        assert result is True
        assert reporter.get_report(report.id) is None

    def test_compare_reports(self):
        reporter = ComplianceReporter()
        r1 = reporter.create_report("t1", ComplianceFramework.GDPR, "R1", datetime.utcnow(), datetime.utcnow())
        r1.score = 90.0
        r2 = reporter.create_report("t1", ComplianceFramework.GDPR, "R2", datetime.utcnow(), datetime.utcnow())
        r2.score = 80.0

        comparison = reporter.compare_reports(r1.id, r2.id)
        assert comparison is not None
        assert comparison["score_difference"] == 10.0

    def test_get_metrics(self):
        reporter = ComplianceReporter()
        reporter.create_report("t1", ComplianceFramework.GDPR, "Test", datetime.utcnow(), datetime.utcnow())
        metrics = reporter.get_metrics()
        assert metrics["total_reports"] == 1


# ============== COMPLIANCE RULES TESTS ==============

class TestComplianceRuleEngine:
    def test_create_rule(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule(
            tenant_id="t1",
            name="Data Access Rule",
            rule_type=RuleType.ACCESS_CONTROL,
            severity=RuleSeverity.HIGH,
            description="Check data access controls"
        )
        assert rule.tenant_id == "t1"
        assert rule.rule_type == RuleType.ACCESS_CONTROL

    def test_create_rule_with_condition(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule(
            tenant_id="t1",
            name="Encryption Rule",
            rule_type=RuleType.ENCRYPTION,
            condition={"encryption_enabled": True}
        )
        assert rule.condition == {"encryption_enabled": True}

    def test_evaluate_rule(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule(
            tenant_id="t1",
            name="Test Rule",
            rule_type=RuleType.ACCESS_CONTROL,
            condition={"access_control": "enabled"}
        )
        result = engine.evaluate_rule(rule.id, context={"access_control": "enabled"})
        assert result is not None
        assert result.passed is True

    def test_evaluate_rule_failing(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule(
            tenant_id="t1",
            name="Test Rule",
            rule_type=RuleType.ACCESS_CONTROL,
            condition={"access_control": "enabled"}
        )
        result = engine.evaluate_rule(rule.id, context={"access_control": "disabled"})
        assert result.passed is False

    def test_evaluate_disabled_rule(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        rule.status = RuleStatus.DISABLED
        result = engine.evaluate_rule(rule.id)
        assert result is None

    def test_get_rule(self):
        engine = ComplianceRuleEngine()
        created = engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        rule = engine.get_rule(created.id)
        assert rule.id == created.id

    def test_get_rules_by_tenant(self):
        engine = ComplianceRuleEngine()
        engine.create_rule("t1", "R1", RuleType.ACCESS_CONTROL)
        engine.create_rule("t1", "R2", RuleType.ENCRYPTION)
        engine.create_rule("t2", "R3", RuleType.ACCESS_CONTROL)

        rules = engine.get_rules_by_tenant("t1")
        assert len(rules) == 2

    def test_get_rules_by_type(self):
        engine = ComplianceRuleEngine()
        engine.create_rule("t1", "R1", RuleType.ACCESS_CONTROL)
        engine.create_rule("t1", "R2", RuleType.ENCRYPTION)
        engine.create_rule("t1", "R3", RuleType.ACCESS_CONTROL)

        rules = engine.get_rules_by_tenant("t1", RuleType.ACCESS_CONTROL)
        assert len(rules) == 2

    def test_update_rule(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        updated = engine.update_rule(rule.id, name="Updated Name")
        assert updated.name == "Updated Name"

    def test_enable_disable_rule(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        
        engine.disable_rule(rule.id)
        assert rule.status == RuleStatus.DISABLED
        
        engine.enable_rule(rule.id)
        assert rule.status == RuleStatus.ENABLED

    def test_delete_rule(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        result = engine.delete_rule(rule.id)
        assert result is True
        assert engine.get_rule(rule.id) is None

    def test_add_exception(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        engine.add_exception(rule.id, "admin_user")
        assert "admin_user" in rule.exceptions

    def test_remove_exception(self):
        engine = ComplianceRuleEngine()
        rule = engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        engine.add_exception(rule.id, "admin_user")
        engine.remove_exception(rule.id, "admin_user")
        assert "admin_user" not in rule.exceptions

    def test_get_compliance_score(self):
        engine = ComplianceRuleEngine()
        engine.create_rule("t1", "R1", RuleType.ACCESS_CONTROL, condition={"check": "pass"})
        engine.create_rule("t1", "R2", RuleType.ACCESS_CONTROL, condition={"check": "fail"})

        score = engine.get_compliance_score("t1", context={"check": "pass"})
        assert score["passed"] == 1
        assert score["failed"] == 1

    def test_register_handler(self):
        engine = ComplianceRuleEngine()
        def handler(rule, context):
            return {"passed": True, "score": 100.0}
        
        engine.register_evaluation_handler(RuleType.ACCESS_CONTROL, handler)
        assert "access_control" in engine._evaluation_handlers

    def test_get_metrics(self):
        engine = ComplianceRuleEngine()
        engine.create_rule("t1", "Test", RuleType.ACCESS_CONTROL)
        metrics = engine.get_metrics()
        assert metrics["total_rules"] == 1


# ============== COMPLIANCE SCHEDULER TESTS ==============

class TestComplianceScheduler:
    def test_create_schedule(self):
        scheduler = ComplianceScheduler()
        schedule = scheduler.create_schedule(
            tenant_id="t1",
            name="Daily Check",
            schedule_type=ScheduleType.DAILY,
            check_type="compliance_check"
        )
        assert schedule.tenant_id == "t1"
        assert schedule.schedule_type == ScheduleType.DAILY

    def test_create_schedule_with_start_time(self):
        scheduler = ComplianceScheduler()
        start_time = datetime.utcnow() + timedelta(hours=1)
        schedule = scheduler.create_schedule(
            tenant_id="t1",
            name="Scheduled Check",
            schedule_type=ScheduleType.WEEKLY,
            check_type="audit",
            start_time=start_time
        )
        assert schedule.next_run == start_time

    def test_register_handler(self):
        scheduler = ComplianceScheduler()
        handler = MagicMock()
        scheduler.register_handler("audit", handler)
        assert "audit" in scheduler._handlers

    def test_execute_check(self):
        scheduler = ComplianceScheduler()
        handler = MagicMock(return_value={"status": "passed"})
        scheduler.register_handler("audit", handler)

        schedule = scheduler.create_schedule(
            tenant_id="t1",
            name="Test",
            schedule_type=ScheduleType.ONCE,
            check_type="audit",
            start_time=datetime.utcnow() - timedelta(minutes=1)
        )

        execution = scheduler.execute_check(schedule.id)
        assert execution is not None
        assert execution.status == "completed"

    def test_execute_nonexistent_schedule(self):
        scheduler = ComplianceScheduler()
        execution = scheduler.execute_check("nonexistent")
        assert execution is None

    def test_get_due_schedules(self):
        scheduler = ComplianceScheduler()
        scheduler.create_schedule(
            tenant_id="t1",
            name="Due",
            schedule_type=ScheduleType.ONCE,
            check_type="audit",
            start_time=datetime.utcnow() - timedelta(minutes=1)
        )
        scheduler.create_schedule(
            tenant_id="t1",
            name="Future",
            schedule_type=ScheduleType.ONCE,
            check_type="audit",
            start_time=datetime.utcnow() + timedelta(hours=1)
        )

        due = scheduler.get_due_schedules()
        assert len(due) == 1

    def test_pause_schedule(self):
        scheduler = ComplianceScheduler()
        schedule = scheduler.create_schedule("t1", "Test", ScheduleType.DAILY, "audit")
        result = scheduler.pause_schedule(schedule.id)
        assert result is True
        assert schedule.status == ScheduleStatus.PAUSED

    def test_resume_schedule(self):
        scheduler = ComplianceScheduler()
        schedule = scheduler.create_schedule("t1", "Test", ScheduleType.DAILY, "audit")
        scheduler.pause_schedule(schedule.id)
        result = scheduler.resume_schedule(schedule.id)
        assert result is True
        assert schedule.status == ScheduleStatus.ACTIVE

    def test_cancel_schedule(self):
        scheduler = ComplianceScheduler()
        schedule = scheduler.create_schedule("t1", "Test", ScheduleType.DAILY, "audit")
        result = scheduler.cancel_schedule(schedule.id)
        assert result is True
        assert schedule.status == ScheduleStatus.CANCELLED

    def test_get_schedule(self):
        scheduler = ComplianceScheduler()
        created = scheduler.create_schedule("t1", "Test", ScheduleType.DAILY, "audit")
        schedule = scheduler.get_schedule(created.id)
        assert schedule.id == created.id

    def test_get_schedules_by_tenant(self):
        scheduler = ComplianceScheduler()
        scheduler.create_schedule("t1", "S1", ScheduleType.DAILY, "audit")
        scheduler.create_schedule("t1", "S2", ScheduleType.DAILY, "audit")
        scheduler.create_schedule("t2", "S3", ScheduleType.DAILY, "audit")

        schedules = scheduler.get_schedules_by_tenant("t1")
        assert len(schedules) == 2

    def test_get_metrics(self):
        scheduler = ComplianceScheduler()
        scheduler.create_schedule("t1", "Test", ScheduleType.DAILY, "audit")
        metrics = scheduler.get_metrics()
        assert metrics["total_schedules"] == 1
