"""
Comprehensive tests for Week 54 Advanced Security Hardening modules.

Tests cover:
- Compliance Checker (compliance_checker.py)
- Audit Logger (audit_logger.py)
- Policy Enforcer (policy_enforcer.py)
"""

import pytest
from datetime import datetime, timedelta
import json

from enterprise.security_hardening.compliance_checker import (
    ComplianceChecker,
    ComplianceFramework,
    ComplianceStatus,
    ComplianceResult,
    ComplianceRule,
    Finding,
    Severity,
)
from enterprise.security_hardening.audit_logger import (
    AuditLogger,
    AuditEvent,
    AuditLevel,
    AuditAction,
    audit_log,
)
from enterprise.security_hardening.policy_enforcer import (
    PolicyEnforcer,
    Policy,
    PolicyRule,
    PolicyEffect,
    PolicyViolation,
    EnforcementAction,
    EnforcementResult,
    Condition,
    ConditionOperator,
)


# ============================================================
# Compliance Checker Tests
# ============================================================

class TestComplianceFramework:
    """Tests for ComplianceFramework enum."""
    
    def test_framework_values(self):
        """Test that all required frameworks are defined."""
        assert ComplianceFramework.GDPR.value == "GDPR"
        assert ComplianceFramework.HIPAA.value == "HIPAA"
        assert ComplianceFramework.SOC2.value == "SOC2"
        assert ComplianceFramework.PCI_DSS.value == "PCI_DSS"
        assert ComplianceFramework.ISO27001.value == "ISO27001"
    
    def test_framework_count(self):
        """Test that we have exactly 5 frameworks."""
        assert len(ComplianceFramework) == 5


class TestComplianceRule:
    """Tests for ComplianceRule dataclass."""
    
    def test_rule_creation(self):
        """Test creating a compliance rule."""
        rule = ComplianceRule(
            rule_id="TEST-001",
            requirement="Test requirement",
            framework=ComplianceFramework.GDPR,
            severity=Severity.HIGH,
            check_function=lambda ctx: True
        )
        assert rule.rule_id == "TEST-001"
        assert rule.requirement == "Test requirement"
        assert rule.framework == ComplianceFramework.GDPR
    
    def test_rule_check_pass(self):
        """Test rule check that passes."""
        rule = ComplianceRule(
            rule_id="TEST-001",
            requirement="Test",
            framework=ComplianceFramework.GDPR,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("pass", False)
        )
        assert rule.check({"pass": True}) is True
    
    def test_rule_check_fail(self):
        """Test rule check that fails."""
        rule = ComplianceRule(
            rule_id="TEST-001",
            requirement="Test",
            framework=ComplianceFramework.GDPR,
            severity=Severity.HIGH,
            check_function=lambda ctx: ctx.get("pass", False)
        )
        assert rule.check({"pass": False}) is False


class TestComplianceResult:
    """Tests for ComplianceResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a compliance result."""
        result = ComplianceResult(
            framework=ComplianceFramework.GDPR,
            status=ComplianceStatus.COMPLIANT,
            score=100.0
        )
        assert result.framework == ComplianceFramework.GDPR
        assert result.status == ComplianceStatus.COMPLIANT
        assert result.score == 100.0
    
    def test_add_finding(self):
        """Test adding findings to result."""
        result = ComplianceResult(
            framework=ComplianceFramework.GDPR,
            status=ComplianceStatus.COMPLIANT,
            score=100.0
        )
        finding = Finding(
            rule_id="TEST-001",
            status=ComplianceStatus.COMPLIANT,
            message="Test finding",
            severity=Severity.LOW
        )
        result.add_finding(finding)
        assert len(result.findings) == 1
    
    def test_get_critical_findings(self):
        """Test getting critical findings."""
        result = ComplianceResult(
            framework=ComplianceFramework.GDPR,
            status=ComplianceStatus.NON_COMPLIANT,
            score=50.0
        )
        result.add_finding(Finding(
            rule_id="TEST-001",
            status=ComplianceStatus.NON_COMPLIANT,
            message="Critical finding",
            severity=Severity.CRITICAL
        ))
        result.add_finding(Finding(
            rule_id="TEST-002",
            status=ComplianceStatus.COMPLIANT,
            message="Low finding",
            severity=Severity.LOW
        ))
        critical = result.get_critical_findings()
        assert len(critical) == 1
        assert critical[0].severity == Severity.CRITICAL
    
    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ComplianceResult(
            framework=ComplianceFramework.GDPR,
            status=ComplianceStatus.COMPLIANT,
            score=100.0,
            summary="All checks passed"
        )
        data = result.to_dict()
        assert data["framework"] == "GDPR"
        assert data["status"] == "COMPLIANT"
        assert data["score"] == 100.0


class TestComplianceChecker:
    """Tests for ComplianceChecker class."""
    
    def test_initialization(self):
        """Test compliance checker initialization."""
        checker = ComplianceChecker()
        assert checker is not None
        assert len(checker.rules) == 5  # One for each framework
    
    def test_default_rules_loaded(self):
        """Test that default rules are loaded."""
        checker = ComplianceChecker()
        for framework in ComplianceFramework:
            assert len(checker.rules[framework]) > 0
    
    def test_add_rule(self):
        """Test adding a custom rule."""
        checker = ComplianceChecker()
        initial_count = len(checker.rules[ComplianceFramework.GDPR])
        
        rule = ComplianceRule(
            rule_id="CUSTOM-001",
            requirement="Custom requirement",
            framework=ComplianceFramework.GDPR,
            severity=Severity.MEDIUM,
            check_function=lambda ctx: True
        )
        checker.add_rule(rule)
        
        assert len(checker.rules[ComplianceFramework.GDPR]) == initial_count + 1
    
    def test_check_compliance_fully_compliant(self):
        """Test compliance check with fully compliant context."""
        checker = ComplianceChecker()
        context = {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "consent_tracking": True,
            "retention_policy": True,
            "right_to_erasure": True
        }
        result = checker.check_compliance(ComplianceFramework.GDPR, context)
        assert result.status == ComplianceStatus.COMPLIANT
        assert result.score == 100.0
    
    def test_check_compliance_non_compliant(self):
        """Test compliance check with non-compliant context."""
        checker = ComplianceChecker()
        context = {
            "encryption_at_rest": False,
            "encryption_in_transit": False,
            "consent_tracking": False,
            "retention_policy": False,
            "right_to_erasure": False
        }
        result = checker.check_compliance(ComplianceFramework.GDPR, context)
        assert result.status == ComplianceStatus.NON_COMPLIANT
        assert result.score == 0.0
    
    def test_check_all_frameworks(self):
        """Test checking all frameworks."""
        checker = ComplianceChecker()
        context = {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "consent_tracking": True,
            "retention_policy": True,
            "right_to_erasure": True,
            "phi_access_controls": True,
            "phi_audit_logging": True,
            "phi_encryption": True,
            "breach_notification": True,
        }
        results = checker.check_all_frameworks(context)
        assert len(results) == 5
    
    def test_get_overall_score(self):
        """Test calculating overall score."""
        checker = ComplianceChecker()
        context = {"encryption_at_rest": True}
        checker.check_compliance(ComplianceFramework.GDPR, context)
        score = checker.get_overall_score()
        assert score >= 0.0


# ============================================================
# Audit Logger Tests
# ============================================================

class TestAuditLevel:
    """Tests for AuditLevel enum."""
    
    def test_level_values(self):
        """Test audit level values."""
        assert AuditLevel.INFO.value == "INFO"
        assert AuditLevel.WARNING.value == "WARNING"
        assert AuditLevel.ERROR.value == "ERROR"
        assert AuditLevel.CRITICAL.value == "CRITICAL"


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""
    
    def test_event_creation(self):
        """Test creating an audit event."""
        event = AuditEvent(
            event_id="TEST-001",
            timestamp=datetime.utcnow(),
            user="test_user",
            action="LOGIN",
            resource="/api/login",
            result="SUCCESS"
        )
        assert event.event_id == "TEST-001"
        assert event.user == "test_user"
    
    def test_compute_hash(self):
        """Test hash computation."""
        event = AuditEvent(
            event_id="TEST-001",
            timestamp=datetime.utcnow(),
            user="test_user",
            action="LOGIN",
            resource="/api/login",
            result="SUCCESS"
        )
        hash1 = event.compute_hash()
        hash2 = event.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex chars
    
    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = AuditEvent(
            event_id="TEST-001",
            timestamp=datetime.utcnow(),
            user="test_user",
            action="LOGIN",
            resource="/api/login",
            result="SUCCESS",
            level=AuditLevel.INFO
        )
        data = event.to_dict()
        assert data["event_id"] == "TEST-001"
        assert data["user"] == "test_user"
        assert data["level"] == "INFO"
    
    def test_from_dict(self):
        """Test creating event from dictionary."""
        data = {
            "event_id": "TEST-001",
            "timestamp": datetime.utcnow().isoformat(),
            "user": "test_user",
            "action": "LOGIN",
            "resource": "/api/login",
            "result": "SUCCESS",
            "level": "INFO",
            "details": {},
            "ip_address": None,
            "user_agent": None,
            "session_id": None,
            "correlation_id": None,
            "previous_hash": None,
            "signature": None
        }
        event = AuditEvent.from_dict(data)
        assert event.event_id == "TEST-001"
        assert event.level == AuditLevel.INFO


class TestAuditLogger:
    """Tests for AuditLogger class."""
    
    def test_initialization(self):
        """Test audit logger initialization."""
        logger = AuditLogger()
        assert logger is not None
        assert len(logger.events) == 0
    
    def test_log_event(self):
        """Test logging an event."""
        logger = AuditLogger()
        event = logger.log(
            user="test_user",
            action="LOGIN",
            resource="/api/login",
            result="SUCCESS"
        )
        assert event.event_id is not None
        assert event.user == "test_user"
        assert len(logger.events) == 1
    
    def test_log_with_details(self):
        """Test logging with additional details."""
        logger = AuditLogger()
        event = logger.log(
            user="test_user",
            action="DELETE",
            resource="/api/users/123",
            result="SUCCESS",
            level=AuditLevel.WARNING,
            details={"reason": "User request"},
            ip_address="192.168.1.1"
        )
        assert event.level == AuditLevel.WARNING
        assert event.ip_address == "192.168.1.1"
        assert event.details["reason"] == "User request"
    
    def test_query_events(self):
        """Test querying events."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS")
        logger.log(user="user2", action="LOGIN", resource="/api/login", result="FAILURE")
        logger.log(user="user1", action="DELETE", resource="/api/users/1", result="SUCCESS")
        
        user1_events = logger.query_events(user="user1")
        assert len(user1_events) == 2
        
        login_events = logger.query_events(action="LOGIN")
        assert len(login_events) == 2
    
    def test_query_with_time_filter(self):
        """Test querying events with time filter."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS")
        
        # Query with future start time
        future = datetime.utcnow() + timedelta(hours=1)
        events = logger.query_events(start_time=future)
        assert len(events) == 0
    
    def test_get_events_by_user(self):
        """Test getting events by user."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS")
        logger.log(user="user2", action="LOGIN", resource="/api/login", result="SUCCESS")
        
        events = logger.get_events_by_user("user1")
        assert len(events) == 1
        assert events[0].user == "user1"
    
    def test_get_failed_events(self):
        """Test getting failed events."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS")
        logger.log(user="user2", action="LOGIN", resource="/api/login", result="FAILURE")
        
        failed = logger.get_failed_events()
        assert len(failed) == 1
        assert failed[0].result == "FAILURE"
    
    def test_export_logs_json(self):
        """Test exporting logs as JSON."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS")
        
        exported = logger.export_logs(format="json")
        data = json.loads(exported)
        assert len(data) == 1
        assert data[0]["user"] == "user1"
    
    def test_export_logs_csv(self):
        """Test exporting logs as CSV."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS")
        
        exported = logger.export_logs(format="csv")
        lines = exported.split("\n")
        assert len(lines) >= 2  # Header + data
        assert "event_id" in lines[0]
    
    def test_verify_integrity(self):
        """Test log integrity verification."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS")
        logger.log(user="user2", action="DELETE", resource="/api/users/1", result="SUCCESS")
        
        result = logger.verify_integrity()
        assert result["valid"] is True
        assert result["events_checked"] == 2
    
    def test_get_statistics(self):
        """Test getting log statistics."""
        logger = AuditLogger()
        logger.log(user="user1", action="LOGIN", resource="/api/login", result="SUCCESS", level=AuditLevel.INFO)
        logger.log(user="user2", action="DELETE", resource="/api/users/1", result="FAILURE", level=AuditLevel.ERROR)
        
        stats = logger.get_statistics()
        assert stats["total_events"] == 2
        assert "INFO" in stats["by_level"]
        assert "ERROR" in stats["by_level"]


# ============================================================
# Policy Enforcer Tests
# ============================================================

class TestCondition:
    """Tests for Condition dataclass."""
    
    def test_equals_condition(self):
        """Test equals operator."""
        condition = Condition(
            field="user.role",
            operator=ConditionOperator.EQUALS,
            value="admin"
        )
        assert condition.evaluate({"user": {"role": "admin"}}) is True
        assert condition.evaluate({"user": {"role": "user"}}) is False
    
    def test_in_condition(self):
        """Test in operator."""
        condition = Condition(
            field="user.role",
            operator=ConditionOperator.IN,
            value=["admin", "manager"]
        )
        assert condition.evaluate({"user": {"role": "admin"}}) is True
        assert condition.evaluate({"user": {"role": "user"}}) is False
    
    def test_greater_than_condition(self):
        """Test greater_than operator."""
        condition = Condition(
            field="request.rate",
            operator=ConditionOperator.GREATER_THAN,
            value=100
        )
        assert condition.evaluate({"request": {"rate": 150}}) is True
        assert condition.evaluate({"request": {"rate": 50}}) is False
    
    def test_matches_condition(self):
        """Test regex matches operator."""
        condition = Condition(
            field="user.email",
            operator=ConditionOperator.MATCHES,
            value=r".*@company\.com$"
        )
        assert condition.evaluate({"user": {"email": "admin@company.com"}}) is True
        assert condition.evaluate({"user": {"email": "admin@other.com"}}) is False


class TestPolicyRule:
    """Tests for PolicyRule dataclass."""
    
    def test_rule_creation(self):
        """Test creating a policy rule."""
        rule = PolicyRule(
            rule_id="RULE-001",
            name="Test Rule",
            description="Test rule description",
            effect=PolicyEffect.DENY,
            conditions=[
                Condition(
                    field="user.role",
                    operator=ConditionOperator.EQUALS,
                    value="guest"
                )
            ],
            actions=[EnforcementAction.DENY]
        )
        assert rule.rule_id == "RULE-001"
        assert rule.effect == PolicyEffect.DENY
    
    def test_rule_evaluate_all_conditions(self):
        """Test rule evaluation with multiple conditions."""
        rule = PolicyRule(
            rule_id="RULE-001",
            name="Test Rule",
            effect=PolicyEffect.DENY,
            conditions=[
                Condition(field="a", operator=ConditionOperator.EQUALS, value=1),
                Condition(field="b", operator=ConditionOperator.EQUALS, value=2)
            ]
        )
        assert rule.evaluate({"a": 1, "b": 2}) is True
        assert rule.evaluate({"a": 1, "b": 3}) is False
    
    def test_rule_disabled(self):
        """Test disabled rule."""
        rule = PolicyRule(
            rule_id="RULE-001",
            name="Test Rule",
            effect=PolicyEffect.DENY,
            conditions=[
                Condition(field="a", operator=ConditionOperator.EQUALS, value=1)
            ],
            enabled=False
        )
        assert rule.enabled is False


class TestPolicy:
    """Tests for Policy dataclass."""
    
    def test_policy_creation(self):
        """Test creating a policy."""
        policy = Policy(
            policy_id="POLICY-001",
            name="Test Policy",
            description="Test policy description"
        )
        assert policy.policy_id == "POLICY-001"
        assert len(policy.rules) == 0
    
    def test_add_rule(self):
        """Test adding rules to policy."""
        policy = Policy(
            policy_id="POLICY-001",
            name="Test Policy"
        )
        rule = PolicyRule(
            rule_id="RULE-001",
            name="Test Rule",
            effect=PolicyEffect.DENY
        )
        policy.add_rule(rule)
        assert len(policy.rules) == 1
    
    def test_remove_rule(self):
        """Test removing rules from policy."""
        policy = Policy(
            policy_id="POLICY-001",
            name="Test Policy"
        )
        rule = PolicyRule(
            rule_id="RULE-001",
            name="Test Rule",
            effect=PolicyEffect.DENY
        )
        policy.add_rule(rule)
        assert policy.remove_rule("RULE-001") is True
        assert len(policy.rules) == 0
        assert policy.remove_rule("NONEXISTENT") is False


class TestPolicyEnforcer:
    """Tests for PolicyEnforcer class."""
    
    def test_initialization(self):
        """Test policy enforcer initialization."""
        enforcer = PolicyEnforcer()
        assert enforcer is not None
        assert len(enforcer.policies) > 0  # Default policies loaded
    
    def test_default_policies_loaded(self):
        """Test that default policies are loaded."""
        enforcer = PolicyEnforcer()
        assert "POLICY-DATA-001" in enforcer.policies
        assert "POLICY-RATE-001" in enforcer.policies
    
    def test_add_policy(self):
        """Test adding a custom policy."""
        enforcer = PolicyEnforcer()
        policy = Policy(
            policy_id="CUSTOM-POLICY-001",
            name="Custom Policy"
        )
        enforcer.add_policy(policy)
        assert "CUSTOM-POLICY-001" in enforcer.policies
    
    def test_enforce_allow(self):
        """Test enforcement that allows the request."""
        enforcer = PolicyEnforcer()
        context = {
            "user": {"role": "admin"},
            "resource": {"sensitivity": "HIGH"},
            "action": "READ"
        }
        result = enforcer.enforce(context)
        assert isinstance(result, EnforcementResult)
    
    def test_enforce_deny(self):
        """Test enforcement that denies the request."""
        enforcer = PolicyEnforcer()
        context = {
            "user": {"role": "guest"},
            "resource": {"sensitivity": "CRITICAL"},
            "action": "READ"
        }
        result = enforcer.enforce(context)
        assert result.allowed is False
        assert result.effect == PolicyEffect.DENY
    
    def test_violation_tracking(self):
        """Test that violations are tracked."""
        enforcer = PolicyEnforcer()
        initial_count = enforcer.get_violation_count()
        
        context = {
            "user": {"role": "guest"},
            "resource": {"sensitivity": "CRITICAL"},
            "action": "READ"
        }
        enforcer.enforce(context)
        
        assert enforcer.get_violation_count() > initial_count
    
    def test_get_violations(self):
        """Test getting violations."""
        enforcer = PolicyEnforcer()
        context = {
            "user": {"role": "guest"},
            "resource": {"sensitivity": "CRITICAL"},
            "action": "READ"
        }
        enforcer.enforce(context)
        
        violations = enforcer.get_violations()
        assert len(violations) > 0
        assert isinstance(violations[0], PolicyViolation)
    
    def test_get_violation_statistics(self):
        """Test getting violation statistics."""
        enforcer = PolicyEnforcer()
        context = {
            "user": {"role": "guest"},
            "resource": {"sensitivity": "CRITICAL"},
            "action": "READ"
        }
        enforcer.enforce(context)
        
        stats = enforcer.get_violation_statistics()
        assert stats["total"] > 0
        assert "by_policy" in stats
    
    def test_clear_violations(self):
        """Test clearing violations."""
        enforcer = PolicyEnforcer()
        context = {
            "user": {"role": "guest"},
            "resource": {"sensitivity": "CRITICAL"},
            "action": "READ"
        }
        enforcer.enforce(context)
        
        count = enforcer.clear_violations()
        assert count > 0
        assert enforcer.get_violation_count() == 0
    
    def test_get_policies_by_tag(self):
        """Test getting policies by tag."""
        enforcer = PolicyEnforcer()
        policies = enforcer.get_policies_by_tag("security")
        assert len(policies) > 0
    
    def test_create_policy_from_dict(self):
        """Test creating policy from dictionary."""
        enforcer = PolicyEnforcer()
        policy_data = {
            "policy_id": "POLICY-FROM-DICT",
            "name": "Policy From Dict",
            "description": "Created from dictionary",
            "default_effect": "DENY",
            "tags": ["test"],
            "rules": [
                {
                    "rule_id": "RULE-001",
                    "name": "Test Rule",
                    "effect": "ALLOW",
                    "conditions": [
                        {
                            "field": "user.role",
                            "operator": "equals",
                            "value": "admin"
                        }
                    ],
                    "actions": ["ALLOW"]
                }
            ]
        }
        policy = enforcer.create_policy_from_dict(policy_data)
        assert policy.policy_id == "POLICY-FROM-DICT"
        assert len(policy.rules) == 1
    
    def test_export_policies(self):
        """Test exporting policies."""
        enforcer = PolicyEnforcer()
        exported = enforcer.export_policies()
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) > 0


class TestEnforcementResult:
    """Tests for EnforcementResult dataclass."""
    
    def test_result_creation(self):
        """Test creating an enforcement result."""
        result = EnforcementResult(
            allowed=True,
            effect=PolicyEffect.ALLOW,
            actions=[EnforcementAction.ALLOW, EnforcementAction.LOG]
        )
        assert result.allowed is True
        assert result.effect == PolicyEffect.ALLOW
        assert len(result.actions) == 2
    
    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = EnforcementResult(
            allowed=False,
            effect=PolicyEffect.DENY,
            actions=[EnforcementAction.DENY]
        )
        data = result.to_dict()
        assert data["allowed"] is False
        assert data["effect"] == "DENY"


# ============================================================
# Integration Tests
# ============================================================

class TestIntegration:
    """Integration tests combining multiple modules."""
    
    def test_compliance_with_audit_logging(self):
        """Test compliance checking with audit logging."""
        checker = ComplianceChecker()
        logger = AuditLogger()
        
        context = {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "consent_tracking": False,
            "retention_policy": True,
            "right_to_erasure": True
        }
        
        result = checker.check_compliance(ComplianceFramework.GDPR, context)
        
        # Log the compliance check
        logger.log(
            user="compliance_system",
            action="COMPLIANCE_CHECK",
            resource="GDPR",
            result="SUCCESS" if result.status == ComplianceStatus.COMPLIANT else "FAILURE",
            level=AuditLevel.WARNING if result.score < 100 else AuditLevel.INFO,
            details={"score": result.score}
        )
        
        assert len(logger.events) == 1
        assert result.score < 100  # consent_tracking is False
    
    def test_policy_enforcement_with_audit(self):
        """Test policy enforcement with audit logging."""
        enforcer = PolicyEnforcer()
        logger = AuditLogger()
        
        context = {
            "user": {"role": "guest"},
            "resource": {"sensitivity": "CRITICAL"},
            "action": "READ"
        }
        
        result = enforcer.enforce(context)
        
        # Log the enforcement action
        logger.log(
            user=context["user"]["role"],
            action="POLICY_ENFORCEMENT",
            resource=context["resource"]["sensitivity"],
            result="DENIED" if not result.allowed else "ALLOWED",
            level=AuditLevel.WARNING if not result.allowed else AuditLevel.INFO
        )
        
        assert len(logger.events) == 1
    
    def test_full_security_workflow(self):
        """Test complete security workflow."""
        # Initialize all components
        checker = ComplianceChecker()
        logger = AuditLogger()
        enforcer = PolicyEnforcer()
        
        # Check compliance
        context = {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "consent_tracking": True,
            "retention_policy": True,
            "right_to_erasure": True
        }
        compliance_result = checker.check_compliance(ComplianceFramework.GDPR, context)
        
        # Log compliance check
        logger.log(
            user="system",
            action="COMPLIANCE_CHECK",
            resource="GDPR",
            result="SUCCESS",
            details={"score": compliance_result.score}
        )
        
        # Enforce policy
        request_context = {
            "user": {"role": "admin"},
            "resource": {"sensitivity": "HIGH"},
            "action": "READ"
        }
        enforcement_result = enforcer.enforce(request_context)
        
        # Log enforcement
        logger.log(
            user="admin",
            action="ACCESS_REQUEST",
            resource="HIGH_SENSITIVITY",
            result="ALLOWED" if enforcement_result.allowed else "DENIED"
        )
        
        # Verify audit trail
        stats = logger.get_statistics()
        assert stats["total_events"] == 2
        
        # Verify log integrity
        integrity = logger.verify_integrity()
        assert integrity["valid"] is True
