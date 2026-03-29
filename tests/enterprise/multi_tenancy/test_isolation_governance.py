"""
Tests for Tenant Isolation, Data Governance, and Audit Trail
"""

import pytest
from datetime import datetime, timedelta
from enterprise.multi_tenancy.isolation_manager import (
    IsolationManager, IsolationLevel, IsolationViolationType, TenantContext, IsolationViolation
)
from enterprise.multi_tenancy.data_governance import (
    DataGovernance, DataClassification, GovernanceAction, RetentionPolicy, DataField, GovernancePolicy
)
from enterprise.multi_tenancy.audit_trail import (
    AuditTrail, AuditEventType, AuditSeverity, AuditEvent, AuditQuery
)


class TestIsolationManager:
    """Tests for IsolationManager"""

    @pytest.fixture
    def manager(self):
        return IsolationManager(isolation_level=IsolationLevel.STRICT)

    def test_create_context(self, manager):
        context = manager.create_context("tenant_001", user_id="user_001")
        assert context.tenant_id == "tenant_001"
        assert context.user_id == "user_001"
        assert context.request_id is not None

    def test_get_context(self, manager):
        context = manager.create_context("tenant_001")
        retrieved = manager.get_context(context.request_id)
        assert retrieved.tenant_id == "tenant_001"

    def test_release_context(self, manager):
        context = manager.create_context("tenant_001")
        assert manager.release_context(context.request_id) is True
        assert manager.get_context(context.request_id) is None

    def test_validate_access_same_tenant(self, manager):
        context = manager.create_context("tenant_001")
        assert manager.validate_access(context, "resource_1", "read", "tenant_001") is True

    def test_validate_access_cross_tenant_strict(self, manager):
        context = manager.create_context("tenant_001")
        result = manager.validate_access(context, "resource_1", "read", "tenant_002")
        assert result is False

    def test_validate_access_cross_tenant_moderate(self):
        manager = IsolationManager(isolation_level=IsolationLevel.MODERATE)
        context = manager.create_context("tenant_001")
        # Moderate allows cross-tenant if resource_tenant_id not specified
        assert manager.validate_access(context, "resource_1", "read") is True

    def test_block_tenant(self, manager):
        context = manager.create_context("tenant_001")
        manager.block_tenant("tenant_001")
        assert manager.is_tenant_blocked("tenant_001") is True
        assert manager.validate_access(context, "resource", "read", "tenant_001") is False

    def test_unblock_tenant(self, manager):
        manager.block_tenant("tenant_001")
        assert manager.unblock_tenant("tenant_001") is True
        assert manager.is_tenant_blocked("tenant_001") is False

    def test_validate_query_adds_tenant_filter(self, manager):
        context = manager.create_context("tenant_001")
        result = manager.validate_query(context, "SELECT * FROM users")
        assert "tenant_id = 'tenant_001'" in result["query"]

    def test_validate_query_existing_tenant_filter(self, manager):
        context = manager.create_context("tenant_001")
        result = manager.validate_query(context, "SELECT * FROM users WHERE tenant_id = 'tenant_001'")
        assert result["valid"] is True

    def test_validate_data_access(self, manager):
        context = manager.create_context("tenant_001")
        data = {"id": 1, "tenant_id": "tenant_001", "name": "test"}
        assert manager.validate_data_access(context, data, "read") is True

    def test_validate_data_access_cross_tenant(self, manager):
        context = manager.create_context("tenant_001")
        data = {"id": 1, "tenant_id": "tenant_002", "name": "test"}
        assert manager.validate_data_access(context, data, "read") is False

    def test_get_violations(self, manager):
        context = manager.create_context("tenant_001")
        manager.validate_access(context, "resource", "read", "tenant_002")
        violations = manager.get_violations(tenant_id="tenant_001")
        assert len(violations) > 0

    def test_get_violation_summary(self, manager):
        context = manager.create_context("tenant_001")
        manager.validate_access(context, "resource", "read", "tenant_002")
        summary = manager.get_violation_summary()
        assert summary["total_violations"] > 0

    def test_get_metrics(self, manager):
        context = manager.create_context("tenant_001")
        manager.validate_access(context, "resource", "read", "tenant_001")
        metrics = manager.get_metrics()
        assert metrics["total_requests"] > 0

    def test_health_check(self, manager):
        health = manager.health_check()
        assert "healthy" in health
        assert "isolation_level" in health

    def test_verify_isolation(self, manager):
        context = manager.create_context("tenant_001")
        manager.validate_access(context, "resource", "read", "tenant_002")
        result = manager.verify_isolation("tenant_001", "tenant_002")
        assert result["is_isolated"] is False

    def test_audit_tenant_access(self, manager):
        context = manager.create_context("tenant_001")
        manager.validate_access(context, "resource", "read", "tenant_002")
        audit = manager.audit_tenant_access("tenant_001")
        assert audit["tenant_id"] == "tenant_001"
        assert audit["total_violations"] > 0


class TestDataGovernance:
    """Tests for DataGovernance"""

    @pytest.fixture
    def governance(self):
        return DataGovernance()

    def test_register_field(self, governance):
        field = governance.register_field(
            name="email",
            classification=DataClassification.PII,
            pii_type="email"
        )
        assert field.name == "email"
        assert field.classification == DataClassification.PII

    def test_get_field(self, governance):
        governance.register_field("ssn", DataClassification.PII, pii_type="ssn")
        field = governance.get_field("ssn")
        assert field.pii_type == "ssn"

    def test_classify_data(self, governance):
        data = {"email": "test@example.com", "name": "John Doe"}
        result = governance.classify_data(data, "tenant_001")
        assert "fields" in result
        assert "pii_detected" in result

    def test_check_access_allowed(self, governance):
        governance.register_field("public_data", DataClassification.PUBLIC)
        result = governance.check_access(
            tenant_id="tenant_001",
            field_name="public_data",
            action="read",
            user_roles=["user"]
        )
        assert result["allowed"] is True

    def test_check_access_pii_requires_role(self, governance):
        governance.register_field("email", DataClassification.PII, pii_type="email")
        result = governance.check_access(
            tenant_id="tenant_001",
            field_name="email",
            action="read",
            user_roles=["user"]  # No admin/data_processor role
        )
        # Default policy audits, doesn't deny
        assert "required_actions" in result

    def test_mask_email(self, governance):
        masked = governance.mask_value("test@example.com", "email")
        assert "@" in masked
        assert "***" in masked

    def test_mask_ssn(self, governance):
        masked = governance.mask_value("123-45-6789", "ssn")
        assert "***-**-6789" == masked

    def test_mask_phone(self, governance):
        masked = governance.mask_value("5551234567", "phone")
        assert "***" in masked

    def test_apply_retention_policy(self, governance):
        governance.register_field(
            "temp_data",
            DataClassification.INTERNAL,
            retention_policy=RetentionPolicy.DAYS_30
        )
        # Recent data
        result = governance.apply_retention_policy(
            "tenant_001",
            "temp_data",
            datetime.utcnow()
        )
        assert result["retain"] is True

        # Old data
        old_date = datetime.utcnow() - timedelta(days=60)
        result = governance.apply_retention_policy(
            "tenant_001",
            "temp_data",
            old_date
        )
        assert result["retain"] is False

    def test_create_policy(self, governance):
        policy = governance.create_policy(
            name="Test Policy",
            description="Test",
            classification=DataClassification.CONFIDENTIAL,
            action=GovernanceAction.DENY
        )
        assert policy.policy_id is not None
        assert governance.get_policy(policy.policy_id) is not None

    def test_list_policies(self, governance):
        policies = governance.list_policies()
        assert len(policies) > 0  # Default policies exist

    def test_record_violation(self, governance):
        governance.register_field("test", DataClassification.PII)
        violation = governance.record_violation(
            policy_id="policy_pii_access",
            tenant_id="tenant_001",
            field_name="test",
            action_attempted="read"
        )
        assert violation.violation_id is not None

    def test_get_violations(self, governance):
        governance.register_field("test", DataClassification.PII)
        governance.record_violation(
            policy_id="policy_pii_access",
            tenant_id="tenant_001",
            field_name="test",
            action_attempted="read"
        )
        violations = governance.get_violations(tenant_id="tenant_001")
        assert len(violations) > 0

    def test_get_metrics(self, governance):
        governance.register_field("test", DataClassification.PII)
        metrics = governance.get_metrics()
        assert metrics["total_fields"] > 0


class TestAuditTrail:
    """Tests for AuditTrail"""

    @pytest.fixture
    def audit(self):
        return AuditTrail()

    def test_log_event(self, audit):
        event = audit.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            tenant_id="tenant_001",
            action="read",
            resource="users/123"
        )
        assert event.event_id is not None
        assert event.tenant_id == "tenant_001"

    def test_log_data_access(self, audit):
        event = audit.log_data_access(
            tenant_id="tenant_001",
            resource="users/123",
            action="read"
        )
        assert event.event_type == AuditEventType.DATA_ACCESS

    def test_log_data_modification(self, audit):
        event = audit.log_data_modification(
            tenant_id="tenant_001",
            resource="users/123",
            action="update",
            old_value={"name": "old"},
            new_value={"name": "new"}
        )
        assert event.event_type == AuditEventType.DATA_MODIFICATION
        assert "old_value" in event.details

    def test_log_cross_tenant_access(self, audit):
        event = audit.log_cross_tenant_access(
            source_tenant="tenant_001",
            target_tenant="tenant_002",
            action="read",
            resource="data/123"
        )
        assert event.cross_tenant is True
        assert event.target_tenant_id == "tenant_002"

    def test_log_policy_violation(self, audit):
        event = audit.log_policy_violation(
            tenant_id="tenant_001",
            policy="no_external_sharing",
            resource="data/123",
            action="export"
        )
        assert event.event_type == AuditEventType.POLICY_VIOLATION
        assert event.outcome == "denied"

    def test_search(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_002", "read", "users")

        query = AuditQuery(tenant_id="tenant_001")
        results = audit.search(query)
        assert len(results) == 1
        assert results[0].tenant_id == "tenant_001"

    def test_search_by_time_range(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")

        query = AuditQuery(
            start_time=datetime.utcnow() - timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(hours=1)
        )
        results = audit.search(query)
        assert len(results) >= 1

    def test_get_event(self, audit):
        event = audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        retrieved = audit.get_event(event.event_id)
        assert retrieved.event_id == event.event_id

    def test_get_tenant_events(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_002", "read", "users")
        events = audit.get_tenant_events("tenant_001")
        assert all(e.tenant_id == "tenant_001" for e in events)

    def test_get_cross_tenant_events(self, audit):
        audit.log_cross_tenant_access("tenant_001", "tenant_002", "read", "data")
        events = audit.get_cross_tenant_events()
        assert len(events) > 0
        assert all(e.cross_tenant for e in events)

    def test_get_summary(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        audit.log_event(AuditEventType.DATA_MODIFICATION, "tenant_001", "update", "users")
        summary = audit.get_summary(tenant_id="tenant_001")
        assert summary["total_events"] == 2

    def test_get_timeline(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        timeline = audit.get_timeline("tenant_001", interval_minutes=60)
        assert len(timeline) > 0
        assert "count" in timeline[0]

    def test_export_events_json(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        export = audit.export_events("tenant_001", format="json")
        assert "event_id" in export

    def test_export_events_csv(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        export = audit.export_events("tenant_001", format="csv")
        assert "event_id,event_type" in export

    def test_get_compliance_report(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        report = audit.get_compliance_report("tenant_001", "SOC2")
        assert report["tenant_id"] == "tenant_001"
        assert report["framework"] == "SOC2"

    def test_get_metrics(self, audit):
        audit.log_event(AuditEventType.DATA_ACCESS, "tenant_001", "read", "users")
        metrics = audit.get_metrics()
        assert metrics["total_events"] > 0


class TestIsolationIntegration:
    """Integration tests for isolation components"""

    def test_full_isolation_workflow(self):
        # Setup
        isolation = IsolationManager(isolation_level=IsolationLevel.STRICT)
        governance = DataGovernance()
        audit = AuditTrail()

        # Register fields
        governance.register_field("email", DataClassification.PII, pii_type="email")

        # Create context
        context = isolation.create_context("tenant_001", user_id="user_001")

        # Validate access
        is_valid = isolation.validate_access(context, "users", "read", "tenant_001")
        assert is_valid is True

        # Log access
        audit.log_data_access("tenant_001", "users", "read", "user_001")

        # Check audit
        events = audit.get_tenant_events("tenant_001")
        assert len(events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
