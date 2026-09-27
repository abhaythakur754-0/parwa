"""
Tests for backend/app/services/audit_service.py

Tests audit entry creation, actor_type validation, all required fields,
and BC-001 company_id enforcement.
"""

import pytest

from backend.app.services.audit_service import (
    ActorType,
    AuditAction,
    AuditEntry,
    create_audit_entry,
    log_audit,
    validate_actor_type,
    VALID_ACTOR_TYPES,
)


class TestActorType:
    """Tests for ActorType enum."""

    def test_user_value(self):
        assert ActorType.USER.value == "user"

    def test_system_value(self):
        assert ActorType.SYSTEM.value == "system"

    def test_api_key_value(self):
        assert ActorType.API_KEY.value == "api_key"

    def test_all_valid_actor_types(self):
        expected = {"user", "system", "api_key"}
        assert VALID_ACTOR_TYPES == expected

    def test_count(self):
        assert len(ActorType) == 3


class TestAuditAction:
    """Tests for AuditAction enum."""

    def test_create_value(self):
        assert AuditAction.CREATE.value == "create"

    def test_read_value(self):
        assert AuditAction.READ.value == "read"

    def test_update_value(self):
        assert AuditAction.UPDATE.value == "update"

    def test_delete_value(self):
        assert AuditAction.DELETE.value == "delete"

    def test_login_value(self):
        assert AuditAction.LOGIN.value == "login"

    def test_logout_value(self):
        assert AuditAction.LOGOUT.value == "logout"

    def test_login_failed_value(self):
        assert AuditAction.LOGIN_FAILED.value == "login_failed"

    def test_approve_value(self):
        assert AuditAction.APPROVE.value == "approve"

    def test_reject_value(self):
        assert AuditAction.REJECT.value == "reject"

    def test_export_value(self):
        assert AuditAction.EXPORT.value == "export"

    def test_api_key_actions(self):
        assert AuditAction.API_KEY_CREATE.value == "api_key_create"
        assert AuditAction.API_KEY_ROTATE.value == "api_key_rotate"
        assert AuditAction.API_KEY_REVOKE.value == "api_key_revoke"

    def test_webhook_actions(self):
        assert AuditAction.WEBHOOK_DELIVERED.value == "webhook_delivered"
        assert AuditAction.WEBHOOK_FAILED.value == "webhook_failed"

    def test_settings_change(self):
        assert AuditAction.SETTINGS_CHANGE.value == "settings_change"

    def test_permission_change(self):
        assert AuditAction.PERMISSION_CHANGE.value == "permission_change"

    def test_action_count(self):
        assert len(AuditAction) == 17


class TestValidateActorType:
    """Tests for validate_actor_type() function."""

    def test_valid_user(self):
        assert validate_actor_type("user") == "user"

    def test_valid_system(self):
        assert validate_actor_type("system") == "system"

    def test_valid_api_key(self):
        assert validate_actor_type("api_key") == "api_key"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid actor_type"):
            validate_actor_type("admin")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Invalid actor_type"):
            validate_actor_type("")

    def test_none_raises(self):
        with pytest.raises(ValueError, match="Invalid actor_type"):
            validate_actor_type(None)

    def test_random_string_raises(self):
        with pytest.raises(ValueError):
            validate_actor_type("hacker")


class TestAuditEntry:
    """Tests for AuditEntry class."""

    def test_creation_with_required_fields(self):
        entry = AuditEntry(
            company_id="comp-123",
            action="create",
        )
        assert entry.company_id == "comp-123"
        assert entry.action == "create"
        assert entry.id is not None
        assert len(entry.id) == 36  # UUID format

    def test_creation_with_all_fields(self):
        entry = AuditEntry(
            company_id="comp-123",
            actor_id="user-456",
            actor_type="user",
            action="update",
            resource_type="ticket",
            resource_id="ticket-789",
            old_value='{"status": "open"}',
            new_value='{"status": "closed"}',
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert entry.company_id == "comp-123"
        assert entry.actor_id == "user-456"
        assert entry.actor_type == "user"
        assert entry.action == "update"
        assert entry.resource_type == "ticket"
        assert entry.resource_id == "ticket-789"
        assert entry.old_value == '{"status": "open"}'
        assert entry.new_value == '{"status": "closed"}'
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "Mozilla/5.0"

    def test_default_actor_type_is_system(self):
        entry = AuditEntry(company_id="comp-123")
        assert entry.actor_type == ActorType.SYSTEM.value

    def test_default_action_is_unknown(self):
        entry = AuditEntry(company_id="comp-123")
        assert entry.action == "unknown"

    def test_created_at_is_set(self):
        from datetime import datetime, timezone
        before = datetime.now(timezone.utc)
        entry = AuditEntry(company_id="comp-123")
        after = datetime.now(timezone.utc)
        assert before <= entry.created_at <= after

    def test_created_at_is_timezone_aware(self):
        entry = AuditEntry(company_id="comp-123")
        assert entry.created_at.tzinfo is not None

    def test_invalid_actor_type_raises(self):
        with pytest.raises(ValueError, match="Invalid actor_type"):
            AuditEntry(company_id="comp-123", actor_type="invalid")

    def test_unique_ids(self):
        entry1 = AuditEntry(company_id="comp-123")
        entry2 = AuditEntry(company_id="comp-123")
        assert entry1.id != entry2.id

    def test_to_dict_has_all_fields(self):
        entry = AuditEntry(
            company_id="comp-123",
            actor_id="user-456",
            actor_type="user",
            action="delete",
            resource_type="subscription",
            resource_id="sub-789",
        )
        d = entry.to_dict()
        expected_keys = {
            "id", "company_id", "actor_id", "actor_type", "action",
            "resource_type", "resource_id", "old_value", "new_value",
            "ip_address", "user_agent", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_values_match(self):
        entry = AuditEntry(
            company_id="comp-abc",
            actor_type="api_key",
            action="create",
        )
        d = entry.to_dict()
        assert d["company_id"] == "comp-abc"
        assert d["actor_type"] == "api_key"
        assert d["action"] == "create"
        assert d["actor_id"] is None
        assert d["resource_type"] is None

    def test_to_dict_old_new_values_none(self):
        entry = AuditEntry(company_id="comp-123")
        d = entry.to_dict()
        assert d["old_value"] is None
        assert d["new_value"] is None

    def test_empty_company_id_raises_on_entry(self):
        """AuditEntry should validate company_id — not bypassable."""
        with pytest.raises(ValueError, match="company_id is required"):
            AuditEntry(company_id="")

    def test_none_company_id_raises_on_entry(self):
        """AuditEntry should reject None company_id."""
        with pytest.raises(ValueError, match="company_id is required"):
            AuditEntry(company_id=None)

    def test_long_company_id_raises_on_entry(self):
        """AuditEntry should reject company_id over 128 chars."""
        with pytest.raises(ValueError, match="must not exceed 128"):
            AuditEntry(company_id="x" * 129)

    def test_max_length_company_id_accepted(self):
        """company_id at exactly 128 chars should be accepted."""
        entry = AuditEntry(company_id="x" * 128)
        assert entry.company_id == "x" * 128

    def test_non_string_company_id_raises(self):
        """company_id must be a string."""
        with pytest.raises(ValueError, match="company_id is required"):
            AuditEntry(company_id=12345)


class TestCreateAuditEntry:
    """Tests for create_audit_entry() function."""

    def test_basic_creation(self):
        entry = create_audit_entry(
            company_id="comp-123",
            action="login",
        )
        assert isinstance(entry, AuditEntry)
        assert entry.company_id == "comp-123"
        assert entry.action == "login"

    def test_returns_audit_entry_object(self):
        entry = create_audit_entry(company_id="comp-123")
        assert isinstance(entry, AuditEntry)

    def test_missing_company_id_raises(self):
        with pytest.raises(ValueError, match="company_id is required"):
            create_audit_entry(company_id="")

    def test_none_company_id_raises(self):
        with pytest.raises(ValueError, match="company_id is required"):
            create_audit_entry(company_id=None)

    def test_all_parameters_passed_through(self):
        entry = create_audit_entry(
            company_id="comp-123",
            actor_id="user-456",
            actor_type="user",
            action="update",
            resource_type="agent",
            resource_id="agent-789",
            old_value='{"name": "old"}',
            new_value='{"name": "new"}',
            ip_address="10.0.0.1",
            user_agent="curl/7.0",
        )
        assert entry.actor_id == "user-456"
        assert entry.actor_type == "user"
        assert entry.resource_type == "agent"
        assert entry.ip_address == "10.0.0.1"
        assert entry.user_agent == "curl/7.0"


class TestLogAudit:
    """Tests for log_audit() function."""

    def test_returns_dict(self):
        result = log_audit(company_id="comp-123", action="create")
        assert isinstance(result, dict)

    def test_dict_has_all_keys(self):
        result = log_audit(company_id="comp-123", action="delete")
        expected_keys = {
            "id", "company_id", "actor_id", "actor_type", "action",
            "resource_type", "resource_id", "old_value", "new_value",
            "ip_address", "user_agent", "created_at",
        }
        assert set(result.keys()) == expected_keys

    def test_values_correct(self):
        result = log_audit(
            company_id="comp-xyz",
            actor_id="system-001",
            actor_type="system",
            action="webhook_delivered",
            resource_type="webhook",
            resource_id="wh-123",
        )
        assert result["company_id"] == "comp-xyz"
        assert result["actor_id"] == "system-001"
        assert result["action"] == "webhook_delivered"
        assert result["resource_type"] == "webhook"

    def test_missing_company_id_raises(self):
        with pytest.raises(ValueError, match="company_id is required"):
            log_audit(company_id="")

    def test_invalid_actor_type_raises(self):
        with pytest.raises(ValueError, match="Invalid actor_type"):
            log_audit(company_id="comp-123", actor_type="hacker")

    def test_dict_matches_entry_to_dict(self):
        entry = create_audit_entry(
            company_id="comp-123",
            action="read",
            actor_type="user",
            actor_id="user-1",
        )
        result = log_audit(
            company_id="comp-123",
            action="read",
            actor_type="user",
            actor_id="user-1",
        )
        # Both should have same structure (except IDs will differ)
        assert set(entry.to_dict().keys()) == set(result.keys())
