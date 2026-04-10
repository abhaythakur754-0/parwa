"""
Tests for SG-13 AuditLogService — Comprehensive test suite
"""

import threading
from dataclasses import is_dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_logger_and_lock():
    with patch("backend.app.logger.get_logger", return_value=MagicMock()):
        import backend.app.services.audit_log_service as _svc_mod
        _orig_lock = _svc_mod.threading.Lock
        _svc_mod.threading.Lock = _svc_mod.threading.RLock
        try:
            from backend.app.services.audit_log_service import (
                AuditLogService,
                AuditLogError,
                AuditLogConfig,
                AuditLogEntry,
                AuditRetentionPolicy,
                AuditStats,
                AuditIntegrityReport,
                AuditExportResult,
                AuditSeverity,
                AuditCategory,
                ExportFormat,
                IntegrityStatus,
            )
            globals().update({
                "AuditLogService": AuditLogService,
                "AuditLogError": AuditLogError,
                "AuditLogConfig": AuditLogConfig,
                "AuditLogEntry": AuditLogEntry,
                "AuditRetentionPolicy": AuditRetentionPolicy,
                "AuditStats": AuditStats,
                "AuditIntegrityReport": AuditIntegrityReport,
                "AuditExportResult": AuditExportResult,
                "AuditSeverity": AuditSeverity,
                "AuditCategory": AuditCategory,
                "ExportFormat": ExportFormat,
                "IntegrityStatus": IntegrityStatus,
            })
            yield
        finally:
            _svc_mod.threading.Lock = _orig_lock


# ══════════════════════════════════════════════════════════════════
# 1. TestEnums
# ══════════════════════════════════════════════════════════════════


class TestEnums:
    """Verify all enum values exist, have correct string values, and proper behaviour."""

    # -- AuditSeverity --
    def test_severity_info_value(self):
        assert AuditSeverity.INFO.value == "info"

    def test_severity_warning_value(self):
        assert AuditSeverity.WARNING.value == "warning"

    def test_severity_critical_value(self):
        assert AuditSeverity.CRITICAL.value == "critical"

    def test_severity_security_value(self):
        assert AuditSeverity.SECURITY.value == "security"

    def test_severity_is_str_enum(self):
        assert isinstance(AuditSeverity.INFO, str)

    def test_severity_has_four_members(self):
        assert len(AuditSeverity) == 4

    def test_severity_iteration(self):
        levels = list(AuditSeverity)
        assert AuditSeverity.INFO in levels
        assert AuditSeverity.SECURITY in levels

    def test_severity_from_string(self):
        s = AuditSeverity("warning")
        assert s == AuditSeverity.WARNING

    # -- AuditCategory --
    def test_category_authentication_value(self):
        assert AuditCategory.AUTHENTICATION.value == "authentication"

    def test_category_authorization_value(self):
        assert AuditCategory.AUTHORIZATION.value == "authorization"

    def test_category_data_access_value(self):
        assert AuditCategory.DATA_ACCESS.value == "data_access"

    def test_category_data_modification_value(self):
        assert AuditCategory.DATA_MODIFICATION.value == "data_modification"

    def test_category_billing_value(self):
        assert AuditCategory.BILLING.value == "billing"

    def test_category_system_value(self):
        assert AuditCategory.SYSTEM.value == "system"

    def test_category_ai_operation_value(self):
        assert AuditCategory.AI_OPERATION.value == "ai_operation"

    def test_category_integration_value(self):
        assert AuditCategory.INTEGRATION.value == "integration"

    def test_category_is_str_enum(self):
        assert isinstance(AuditCategory.SYSTEM, str)

    def test_category_has_eight_members(self):
        assert len(AuditCategory) == 8

    def test_category_iteration(self):
        cats = list(AuditCategory)
        assert AuditCategory.AUTHENTICATION in cats
        assert AuditCategory.INTEGRATION in cats

    def test_category_from_string(self):
        c = AuditCategory("billing")
        assert c == AuditCategory.BILLING

    # -- ExportFormat --
    def test_export_format_json_value(self):
        assert ExportFormat.JSON.value == "json"

    def test_export_format_csv_value(self):
        assert ExportFormat.CSV.value == "csv"

    def test_export_format_is_str_enum(self):
        assert isinstance(ExportFormat.JSON, str)

    def test_export_format_has_two_members(self):
        assert len(ExportFormat) == 2

    def test_export_format_iteration(self):
        fmts = list(ExportFormat)
        assert ExportFormat.JSON in fmts
        assert ExportFormat.CSV in fmts

    # -- IntegrityStatus --
    def test_integrity_valid_value(self):
        assert IntegrityStatus.VALID.value == "valid"

    def test_integrity_tampered_value(self):
        assert IntegrityStatus.TAMPERED.value == "tampered"

    def test_integrity_partial_value(self):
        assert IntegrityStatus.PARTIAL.value == "partial"

    def test_integrity_unknown_value(self):
        assert IntegrityStatus.UNKNOWN.value == "unknown"

    def test_integrity_is_str_enum(self):
        assert isinstance(IntegrityStatus.VALID, str)

    def test_integrity_has_four_members(self):
        assert len(IntegrityStatus) == 4

    def test_integrity_iteration(self):
        statuses = list(IntegrityStatus)
        assert IntegrityStatus.VALID in statuses
        assert IntegrityStatus.TAMPERED in statuses


# ══════════════════════════════════════════════════════════════════
# 2. TestConfig
# ══════════════════════════════════════════════════════════════════


class TestConfig:
    """Test AuditLogConfig default and custom values."""

    def test_default_retention_days(self):
        cfg = AuditLogConfig()
        assert cfg.default_retention_days == 365

    def test_default_max_batch_size(self):
        cfg = AuditLogConfig()
        assert cfg.max_batch_size == 1000

    def test_default_enable_checksum(self):
        cfg = AuditLogConfig()
        assert cfg.enable_checksum is True

    def test_default_enable_streaming(self):
        cfg = AuditLogConfig()
        assert cfg.enable_streaming is True

    def test_default_sensitive_fields(self):
        cfg = AuditLogConfig()
        assert "password" in cfg.sensitive_fields
        assert "token" in cfg.sensitive_fields
        assert "api_key" in cfg.sensitive_fields
        assert "secret" in cfg.sensitive_fields

    def test_default_sensitive_fields_count(self):
        cfg = AuditLogConfig()
        assert len(cfg.sensitive_fields) == 4

    def test_default_checksum_algorithm(self):
        cfg = AuditLogConfig()
        assert cfg.checksum_algorithm == "sha256"

    def test_custom_retention_days(self):
        cfg = AuditLogConfig(default_retention_days=100)
        assert cfg.default_retention_days == 100

    def test_custom_max_batch_size(self):
        cfg = AuditLogConfig(max_batch_size=500)
        assert cfg.max_batch_size == 500

    def test_custom_enable_checksum_false(self):
        cfg = AuditLogConfig(enable_checksum=False)
        assert cfg.enable_checksum is False

    def test_custom_enable_streaming_false(self):
        cfg = AuditLogConfig(enable_streaming=False)
        assert cfg.enable_streaming is False

    def test_custom_sensitive_fields(self):
        cfg = AuditLogConfig(sensitive_fields=("password", "token"))
        assert cfg.sensitive_fields == ("password", "token")

    def test_custom_checksum_algorithm(self):
        cfg = AuditLogConfig(checksum_algorithm="sha512")
        assert cfg.checksum_algorithm == "sha512"

    def test_custom_all_parameters(self):
        cfg = AuditLogConfig(
            default_retention_days=100,
            max_batch_size=500,
            enable_checksum=False,
            enable_streaming=False,
            sensitive_fields=("password",),
            checksum_algorithm="md5",
        )
        assert cfg.default_retention_days == 100
        assert cfg.max_batch_size == 500
        assert cfg.enable_checksum is False
        assert cfg.enable_streaming is False
        assert cfg.sensitive_fields == ("password",)
        assert cfg.checksum_algorithm == "md5"

    def test_config_is_dataclass(self):
        assert is_dataclass(AuditLogConfig)


# ══════════════════════════════════════════════════════════════════
# 3. TestDataclasses
# ══════════════════════════════════════════════════════════════════


class TestDataclasses:
    """Test all dataclasses with required fields, defaults, and custom values."""

    # -- AuditLogEntry --
    def test_entry_required_fields(self):
        entry = AuditLogEntry(
            entry_id="e-1",
            company_id="co-1",
            category=AuditCategory.AUTHENTICATION,
            severity=AuditSeverity.INFO,
            action="login",
        )
        assert entry.entry_id == "e-1"
        assert entry.company_id == "co-1"
        assert entry.category == AuditCategory.AUTHENTICATION
        assert entry.severity == AuditSeverity.INFO
        assert entry.action == "login"

    def test_entry_default_actor_type(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.actor_type == "user"

    def test_entry_default_actor_id_none(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.actor_id is None

    def test_entry_default_resource_type_none(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.resource_type is None

    def test_entry_default_resource_id_none(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.resource_id is None

    def test_entry_default_old_value_none(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.old_value is None

    def test_entry_default_new_value_none(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.new_value is None

    def test_entry_default_ip_address_none(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.ip_address is None

    def test_entry_default_user_agent_none(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.user_agent is None

    def test_entry_default_metadata_empty_dict(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.metadata == {}

    def test_entry_default_checksum_empty(self):
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        assert entry.checksum == ""

    def test_entry_default_created_at_utc(self):
        before = datetime.now(timezone.utc)
        entry = AuditLogEntry(
            entry_id="e-1", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO, action="ping",
        )
        after = datetime.now(timezone.utc)
        assert before <= entry.created_at <= after

    def test_entry_custom_all_fields(self):
        ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        entry = AuditLogEntry(
            entry_id="e-99", company_id="co-5",
            category=AuditCategory.BILLING, severity=AuditSeverity.CRITICAL,
            action="charge", actor_id="user-1", actor_type="system",
            resource_type="invoice", resource_id="inv-1",
            old_value="10", new_value="20", ip_address="1.2.3.4",
            user_agent="test-agent", metadata={"key": "val"},
            checksum="abc123", created_at=ts,
        )
        assert entry.entry_id == "e-99"
        assert entry.company_id == "co-5"
        assert entry.category == AuditCategory.BILLING
        assert entry.severity == AuditSeverity.CRITICAL
        assert entry.action == "charge"
        assert entry.actor_id == "user-1"
        assert entry.actor_type == "system"
        assert entry.resource_type == "invoice"
        assert entry.resource_id == "inv-1"
        assert entry.old_value == "10"
        assert entry.new_value == "20"
        assert entry.ip_address == "1.2.3.4"
        assert entry.user_agent == "test-agent"
        assert entry.metadata == {"key": "val"}
        assert entry.checksum == "abc123"
        assert entry.created_at == ts

    def test_entry_is_dataclass(self):
        assert is_dataclass(AuditLogEntry)

    # -- AuditRetentionPolicy --
    def test_retention_policy_required_field(self):
        p = AuditRetentionPolicy(company_id="co-1")
        assert p.company_id == "co-1"

    def test_retention_policy_default_category_retention_empty(self):
        p = AuditRetentionPolicy(company_id="co-1")
        assert p.category_retention_days == {}

    def test_retention_policy_default_max_entries_zero(self):
        p = AuditRetentionPolicy(company_id="co-1")
        assert p.max_entries_per_category == 0

    def test_retention_policy_default_auto_cleanup_true(self):
        p = AuditRetentionPolicy(company_id="co-1")
        assert p.enable_auto_cleanup is True

    def test_retention_policy_default_cleanup_frequency(self):
        p = AuditRetentionPolicy(company_id="co-1")
        assert p.cleanup_frequency_hours == 24

    def test_retention_policy_custom_values(self):
        p = AuditRetentionPolicy(
            company_id="co-1",
            category_retention_days={"system": 30, "authentication": 2555},
            max_entries_per_category=100,
            enable_auto_cleanup=False,
            cleanup_frequency_hours=12,
        )
        assert p.category_retention_days == {"system": 30, "authentication": 2555}
        assert p.max_entries_per_category == 100
        assert p.enable_auto_cleanup is False
        assert p.cleanup_frequency_hours == 12

    def test_retention_policy_is_dataclass(self):
        assert is_dataclass(AuditRetentionPolicy)

    # -- AuditStats --
    def test_stats_required_field(self):
        s = AuditStats(company_id="co-1")
        assert s.company_id == "co-1"

    def test_stats_all_defaults(self):
        s = AuditStats(company_id="co-1")
        assert s.total_entries == 0
        assert s.entries_by_category == {}
        assert s.entries_by_severity == {}
        assert s.entries_last_24h == 0
        assert s.entries_last_7d == 0
        assert s.most_active_actors == []
        assert s.unique_resources == 0
        assert s.period_start is None
        assert s.period_end is None

    def test_stats_custom_values(self):
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        s = AuditStats(
            company_id="co-1",
            total_entries=42,
            entries_by_category={"system": 10},
            entries_by_severity={"info": 20},
            entries_last_24h=5,
            entries_last_7d=15,
            most_active_actors=[{"actor_id": "u1", "count": 10}],
            unique_resources=8,
            period_start=ts,
            period_end=ts + timedelta(days=30),
        )
        assert s.total_entries == 42
        assert s.entries_by_category == {"system": 10}
        assert s.entries_last_24h == 5
        assert s.unique_resources == 8

    def test_stats_is_dataclass(self):
        assert is_dataclass(AuditStats)

    # -- AuditIntegrityReport --
    def test_integrity_report_required_field(self):
        r = AuditIntegrityReport(company_id="co-1")
        assert r.company_id == "co-1"

    def test_integrity_report_default_status(self):
        r = AuditIntegrityReport(company_id="co-1")
        assert r.status == IntegrityStatus.UNKNOWN

    def test_integrity_report_all_defaults(self):
        r = AuditIntegrityReport(company_id="co-1")
        assert r.total_checked == 0
        assert r.valid_count == 0
        assert r.tampered_count == 0
        assert r.missing_count == 0
        assert r.checked_range_start is None
        assert r.checked_range_end is None
        assert r.details == []

    def test_integrity_report_custom_values(self):
        r = AuditIntegrityReport(
            company_id="co-1",
            status=IntegrityStatus.TAMPERED,
            total_checked=10,
            valid_count=8,
            tampered_count=1,
            missing_count=1,
            details=[{"entry_id": "e-1", "status": "tampered"}],
        )
        assert r.status == IntegrityStatus.TAMPERED
        assert r.total_checked == 10
        assert r.valid_count == 8
        assert r.tampered_count == 1
        assert r.missing_count == 1
        assert len(r.details) == 1

    def test_integrity_report_is_dataclass(self):
        assert is_dataclass(AuditIntegrityReport)

    # -- AuditExportResult --
    def test_export_result_required_field(self):
        e = AuditExportResult(company_id="co-1")
        assert e.company_id == "co-1"

    def test_export_result_default_format(self):
        e = AuditExportResult(company_id="co-1")
        assert e.format == ExportFormat.JSON

    def test_export_result_all_defaults(self):
        e = AuditExportResult(company_id="co-1")
        assert e.total_entries == 0
        assert e.file_path_or_data is None
        assert e.export_started_at is None
        assert e.export_completed_at is None
        assert e.entry_count == 0

    def test_export_result_custom_values(self):
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        e = AuditExportResult(
            company_id="co-1",
            format=ExportFormat.CSV,
            total_entries=5,
            file_path_or_data="csv,data",
            export_started_at=ts,
            export_completed_at=ts + timedelta(seconds=1),
            entry_count=5,
        )
        assert e.format == ExportFormat.CSV
        assert e.total_entries == 5
        assert e.file_path_or_data == "csv,data"
        assert e.entry_count == 5

    def test_export_result_is_dataclass(self):
        assert is_dataclass(AuditExportResult)


# ══════════════════════════════════════════════════════════════════
# 4. TestServiceInitialization
# ══════════════════════════════════════════════════════════════════


class TestServiceInitialization:
    """Test service creation with default and custom config."""

    def test_default_config_used_when_none_provided(self):
        svc = AuditLogService()
        assert svc.config is not None
        assert svc.config.default_retention_days == 365

    def test_custom_config_is_used(self):
        cfg = AuditLogConfig(default_retention_days=100)
        svc = AuditLogService(config=cfg)
        assert svc.config.default_retention_days == 100

    def test_empty_entries_on_creation(self):
        svc = AuditLogService()
        assert svc._entries == {}

    def test_empty_retention_policies_on_creation(self):
        svc = AuditLogService()
        assert svc._retention_policies == {}

    def test_empty_alerts_on_creation(self):
        svc = AuditLogService()
        assert svc._alerts == {}

    def test_empty_stream_callbacks_on_creation(self):
        svc = AuditLogService()
        assert svc._stream_callbacks == []

    def test_lock_exists(self):
        svc = AuditLogService()
        assert svc._lock is not None


# ══════════════════════════════════════════════════════════════════
# 5. TestLogEvent
# ══════════════════════════════════════════════════════════════════


class TestLogEvent:
    """Test log_event method — create entries, checksums, alerts."""

    def _make_svc(self):
        svc = AuditLogService()
        svc.reset("co-1")
        return svc

    def test_log_basic_event(self):
        svc = self._make_svc()
        entry = svc.log_event(
            "co-1", "authentication", "info", "user_login",
        )
        assert entry.company_id == "co-1"
        assert entry.category == AuditCategory.AUTHENTICATION
        assert entry.severity == AuditSeverity.INFO
        assert entry.action == "user_login"

    def test_log_generates_entry_id(self):
        svc = self._make_svc()
        entry = svc.log_event("co-1", "system", "info", "ping")
        assert entry.entry_id is not None
        assert len(entry.entry_id) > 0

    def test_log_generates_unique_entry_ids(self):
        svc = self._make_svc()
        e1 = svc.log_event("co-1", "system", "info", "ping")
        e2 = svc.log_event("co-1", "system", "info", "pong")
        assert e1.entry_id != e2.entry_id

    def test_log_generates_checksum(self):
        svc = self._make_svc()
        entry = svc.log_event("co-1", "system", "info", "ping")
        assert entry.checksum is not None
        assert len(entry.checksum) > 0

    def test_log_checksum_disabled(self):
        cfg = AuditLogConfig(enable_checksum=False)
        svc = AuditLogService(config=cfg)
        svc.reset("co-1")
        entry = svc.log_event("co-1", "system", "info", "ping")
        assert entry.checksum == ""

    def test_log_sets_created_at(self):
        svc = self._make_svc()
        before = datetime.now(timezone.utc)
        entry = svc.log_event("co-1", "system", "info", "ping")
        after = datetime.now(timezone.utc)
        assert before <= entry.created_at <= after

    def test_log_stores_entry(self):
        svc = self._make_svc()
        entry = svc.log_event("co-1", "system", "info", "ping")
        entries = svc._get_entries("co-1")
        assert len(entries) == 1
        assert entries[0].entry_id == entry.entry_id

    def test_log_with_enum_category(self):
        svc = self._make_svc()
        entry = svc.log_event(
            "co-1", AuditCategory.BILLING, AuditSeverity.WARNING, "charge_failed",
        )
        assert entry.category == AuditCategory.BILLING

    def test_log_with_enum_severity(self):
        svc = self._make_svc()
        entry = svc.log_event(
            "co-1", "system", AuditSeverity.CRITICAL, "error",
        )
        assert entry.severity == AuditSeverity.CRITICAL

    def test_log_with_all_optional_fields(self):
        svc = self._make_svc()
        entry = svc.log_event(
            "co-1", "data_access", "info", "read_record",
            actor_id="user-1", actor_type="api_key",
            resource_type="document", resource_id="doc-1",
            old_value="v1", new_value="v2",
            metadata={"key": "val"}, ip_address="10.0.0.1",
            user_agent="test-browser",
        )
        assert entry.actor_id == "user-1"
        assert entry.actor_type == "api_key"
        assert entry.resource_type == "document"
        assert entry.resource_id == "doc-1"
        assert entry.old_value == "v1"
        assert entry.new_value == "v2"
        assert entry.metadata == {"key": "val"}
        assert entry.ip_address == "10.0.0.1"
        assert entry.user_agent == "test-browser"

    def test_log_with_metadata_none(self):
        svc = self._make_svc()
        entry = svc.log_event("co-1", "system", "info", "ping", metadata=None)
        assert entry.metadata == {}

    def test_log_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError) as exc:
            svc.log_event("", "system", "info", "ping")
        assert exc.value.error_code == "INVALID_COMPANY_ID"

    def test_log_whitespace_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.log_event("   ", "system", "info", "ping")

    def test_log_invalid_category_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError) as exc:
            svc.log_event("co-1", "not_a_category", "info", "ping")
        assert exc.value.error_code == "INVALID_CATEGORY"

    def test_log_empty_category_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError) as exc:
            svc.log_event("co-1", "", "info", "ping")
        assert exc.value.error_code == "INVALID_CATEGORY"

    def test_log_invalid_severity_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError) as exc:
            svc.log_event("co-1", "system", "not_a_severity", "ping")
        assert exc.value.error_code == "INVALID_SEVERITY"

    def test_log_empty_severity_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError) as exc:
            svc.log_event("co-1", "system", "", "ping")
        assert exc.value.error_code == "INVALID_SEVERITY"

    def test_log_empty_action_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.log_event("co-1", "system", "info", "")

    def test_log_whitespace_action_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.log_event("co-1", "system", "info", "   ")

    def test_log_case_insensitive_category(self):
        svc = self._make_svc()
        entry = svc.log_event("co-1", "AUTHENTICATION", "info", "login")
        assert entry.category == AuditCategory.AUTHENTICATION

    def test_log_case_insensitive_severity(self):
        svc = self._make_svc()
        entry = svc.log_event("co-1", "system", "WARNING", "test")
        assert entry.severity == AuditSeverity.WARNING

    def test_log_creates_alert_for_login_failed(self):
        svc = self._make_svc()
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "audit_login_failed"

    def test_log_creates_alert_for_delete(self):
        svc = self._make_svc()
        svc.log_event("co-1", "data_modification", "critical", "delete")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "audit_delete"

    def test_log_no_alert_for_regular_action(self):
        svc = self._make_svc()
        svc.log_event("co-1", "system", "info", "regular_ping")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 0

    def test_log_multiple_entries_same_company(self):
        svc = self._make_svc()
        svc.log_event("co-1", "system", "info", "ping1")
        svc.log_event("co-1", "system", "info", "ping2")
        svc.log_event("co-1", "billing", "info", "charge")
        assert len(svc._get_entries("co-1")) == 3

    def test_log_action_strips_whitespace(self):
        svc = self._make_svc()
        entry = svc.log_event("co-1", "system", "info", "  ping  ")
        assert entry.action == "ping"

    def test_log_streaming_disabled(self):
        cfg = AuditLogConfig(enable_streaming=False)
        svc = AuditLogService(config=cfg)
        svc.reset("co-1")
        callback = MagicMock()
        svc._stream_callbacks.append(callback)
        svc.log_event("co-1", "system", "info", "ping")
        callback.assert_not_called()

    def test_log_streaming_calls_callbacks(self):
        svc = self._make_svc()
        callback = MagicMock()
        svc._stream_callbacks.append(callback)
        svc.log_event("co-1", "system", "info", "ping")
        callback.assert_called_once()

    def test_log_streaming_callback_error_does_not_crash(self):
        svc = self._make_svc()
        bad_callback = MagicMock(side_effect=RuntimeError("stream error"))
        svc._stream_callbacks.append(bad_callback)
        entry = svc.log_event("co-1", "system", "info", "ping")
        assert entry is not None


# ══════════════════════════════════════════════════════════════════
# 6. TestQueryEvents
# ══════════════════════════════════════════════════════════════════


class TestQueryEvents:
    """Test query_events with filtering and pagination."""

    def _seed_svc(self, company_id="co-1"):
        svc = AuditLogService()
        svc.reset(company_id)
        svc.log_event(company_id, "authentication", "info", "login", actor_id="user-1")
        svc.log_event(company_id, "billing", "warning", "charge", actor_id="user-2")
        svc.log_event(company_id, "authentication", "critical", "login_failed", actor_id="user-1")
        svc.log_event(company_id, "system", "info", "ping", actor_id="user-3")
        svc.log_event(company_id, "data_access", "info", "read_doc", actor_id="user-1",
                      resource_type="document", resource_id="doc-1")
        return svc

    def test_query_empty_company(self):
        svc = AuditLogService()
        svc.reset("co-empty")
        entries, total = svc.query_events("co-empty")
        assert entries == []
        assert total == 0

    def test_query_all_entries(self):
        svc = self._seed_svc()
        entries, total = svc.query_events("co-1")
        assert total == 5
        assert len(entries) == 5

    def test_query_filter_by_category(self):
        svc = self._seed_svc()
        entries, total = svc.query_events("co-1", category="authentication")
        assert total == 2
        assert all(e.category == AuditCategory.AUTHENTICATION for e in entries)

    def test_query_filter_by_severity(self):
        svc = self._seed_svc()
        entries, total = svc.query_events("co-1", severity="critical")
        assert total == 1
        assert entries[0].severity == AuditSeverity.CRITICAL

    def test_query_filter_by_actor_id(self):
        svc = self._seed_svc()
        entries, total = svc.query_events("co-1", actor_id="user-1")
        assert total == 3

    def test_query_filter_by_resource_type(self):
        svc = self._seed_svc()
        entries, total = svc.query_events("co-1", resource_type="document")
        assert total == 1

    def test_query_filter_by_date_from(self):
        svc = self._seed_svc()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        entries, total = svc.query_events("co-1", date_from=future)
        assert total == 0

    def test_query_filter_by_date_to(self):
        svc = self._seed_svc()
        past = datetime.now(timezone.utc) - timedelta(days=1)
        entries, total = svc.query_events("co-1", date_to=past)
        assert total == 0

    def test_query_pagination_offset(self):
        svc = self._seed_svc()
        page, total = svc.query_events("co-1", offset=2, limit=10)
        assert total == 5
        assert len(page) == 3

    def test_query_pagination_limit(self):
        svc = self._seed_svc()
        page, total = svc.query_events("co-1", offset=0, limit=2)
        assert total == 5
        assert len(page) == 2

    def test_query_negative_offset_clamped(self):
        svc = self._seed_svc()
        page, total = svc.query_events("co-1", offset=-5)
        assert total == 5

    def test_query_zero_limit_clamped(self):
        svc = self._seed_svc()
        page, total = svc.query_events("co-1", limit=0)
        assert len(page) >= 1

    def test_query_returns_newest_first(self):
        svc = self._seed_svc()
        entries, total = svc.query_events("co-1")
        if len(entries) >= 2:
            assert entries[0].created_at >= entries[1].created_at

    def test_query_company_isolation(self):
        svc = AuditLogService()
        svc.reset("co-a")
        svc.reset("co-b")
        svc.log_event("co-a", "system", "info", "ping")
        svc.log_event("co-b", "system", "info", "pong")
        entries_a, total_a = svc.query_events("co-a")
        entries_b, total_b = svc.query_events("co-b")
        assert total_a == 1
        assert total_b == 1
        assert entries_a[0].action == "ping"
        assert entries_b[0].action == "pong"

    def test_query_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.query_events("")

    def test_query_combined_filters(self):
        svc = self._seed_svc()
        entries, total = svc.query_events(
            "co-1", category="authentication", actor_id="user-1",
        )
        assert total == 2
        assert all(
            e.category == AuditCategory.AUTHENTICATION and e.actor_id == "user-1"
            for e in entries
        )


# ══════════════════════════════════════════════════════════════════
# 7. TestStatistics
# ══════════════════════════════════════════════════════════════════


class TestStatistics:
    """Test get_statistics aggregated metrics."""

    def _seed_svc(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "authentication", "info", "login", actor_id="user-1",
                      resource_type="session", resource_id="s-1")
        svc.log_event("co-1", "billing", "warning", "charge", actor_id="user-2",
                      resource_type="invoice", resource_id="inv-1")
        svc.log_event("co-1", "authentication", "critical", "login_failed", actor_id="user-1",
                      resource_type="session", resource_id="s-2")
        return svc

    def test_stats_empty_company(self):
        svc = AuditLogService()
        svc.reset("co-empty")
        stats = svc.get_statistics("co-empty")
        assert stats.total_entries == 0
        assert stats.entries_by_category == {}
        assert stats.entries_by_severity == {}

    def test_stats_total_entries(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert stats.total_entries == 3

    def test_stats_category_distribution(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert stats.entries_by_category.get("authentication") == 2
        assert stats.entries_by_category.get("billing") == 1

    def test_stats_severity_distribution(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert stats.entries_by_severity.get("info") == 1
        assert stats.entries_by_severity.get("warning") == 1
        assert stats.entries_by_severity.get("critical") == 1

    def test_stats_most_active_actors(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert len(stats.most_active_actors) > 0
        top = stats.most_active_actors[0]
        assert top["actor_id"] == "user-1"
        assert top["count"] == 2

    def test_stats_unique_resources(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert stats.unique_resources == 3

    def test_stats_entries_last_24h(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert stats.entries_last_24h == 3

    def test_stats_entries_last_7d(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert stats.entries_last_7d == 3

    def test_stats_period_start_and_end(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1", days=30)
        assert stats.period_start is not None
        assert stats.period_end is not None

    def test_stats_company_id(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1")
        assert stats.company_id == "co-1"

    def test_stats_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.get_statistics("")

    def test_stats_days_clamped_min(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1", days=-10)
        assert stats is not None

    def test_stats_days_clamped_max(self):
        svc = self._seed_svc()
        stats = svc.get_statistics("co-1", days=99999)
        assert stats is not None


# ══════════════════════════════════════════════════════════════════
# 8. TestIntegrity
# ══════════════════════════════════════════════════════════════════


class TestIntegrity:
    """Test verify_integrity checksum verification."""

    def _seed_svc(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "system", "info", "ping")
        svc.log_event("co-1", "billing", "warning", "charge")
        return svc

    def test_verify_all_valid(self):
        svc = self._seed_svc()
        report = svc.verify_integrity("co-1")
        assert report.status == IntegrityStatus.VALID
        assert report.valid_count == 2
        assert report.tampered_count == 0

    def test_verify_tampered_entry(self):
        svc = self._seed_svc()
        entries = svc._get_entries("co-1")
        entries[0].action = "TAMPERED"
        entries[0].checksum = "invalid"
        report = svc.verify_integrity("co-1")
        assert report.status == IntegrityStatus.TAMPERED
        assert report.tampered_count == 1
        assert report.valid_count == 1

    def test_verify_empty_range(self):
        svc = AuditLogService()
        svc.reset("co-empty")
        report = svc.verify_integrity("co-empty")
        assert report.status == IntegrityStatus.UNKNOWN
        assert report.total_checked == 0

    def test_verify_date_range_filter(self):
        svc = self._seed_svc()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        report = svc.verify_integrity("co-1", date_from=future)
        assert report.total_checked == 0

    def test_verify_creates_alert_on_tamper(self):
        svc = self._seed_svc()
        entries = svc._get_entries("co-1")
        entries[0].checksum = "tampered"
        report = svc.verify_integrity("co-1")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "integrity_violation"

    def test_verify_report_company_id(self):
        svc = self._seed_svc()
        report = svc.verify_integrity("co-1")
        assert report.company_id == "co-1"

    def test_verify_details_populated_on_tamper(self):
        svc = self._seed_svc()
        entries = svc._get_entries("co-1")
        entries[0].checksum = "bad"
        report = svc.verify_integrity("co-1")
        assert len(report.details) == 1
        assert report.details[0]["status"] == "tampered"

    def test_verify_checksum_disabled(self):
        cfg = AuditLogConfig(enable_checksum=False)
        svc = AuditLogService(config=cfg)
        svc.reset("co-1")
        svc.log_event("co-1", "system", "info", "ping")
        report = svc.verify_integrity("co-1")
        assert report.status == IntegrityStatus.PARTIAL

    def test_verify_missing_checksum(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = AuditLogEntry(
            entry_id="e-no-cs", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO,
            action="ping", checksum="",
        )
        svc._set_entries("co-1", [entry])
        report = svc.verify_integrity("co-1")
        assert report.status == IntegrityStatus.PARTIAL
        assert report.missing_count == 1

    def test_verify_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.verify_integrity("")

    def test_verify_checked_range_set(self):
        svc = self._seed_svc()
        report = svc.verify_integrity("co-1")
        assert report.checked_range_start is not None
        assert report.checked_range_end is not None


# ══════════════════════════════════════════════════════════════════
# 9. TestExport
# ══════════════════════════════════════════════════════════════════


class TestExport:
    """Test export_events JSON/CSV format, filtering, redaction."""

    def _seed_svc(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "system", "info", "ping")
        svc.log_event("co-1", "billing", "warning", "charge",
                      metadata={"password": "secret123"})
        return svc

    def test_export_json_format(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1", format=ExportFormat.JSON)
        assert result.format == ExportFormat.JSON
        assert result.total_entries == 2
        assert result.entry_count == 2

    def test_export_json_has_entries_key(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1", format=ExportFormat.JSON)
        data = result.file_path_or_data
        assert "entries" in data
        assert "export_meta" in data

    def test_export_csv_format(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1", format=ExportFormat.CSV)
        assert result.format == ExportFormat.CSV
        assert result.total_entries == 2

    def test_export_csv_has_header(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1", format=ExportFormat.CSV)
        csv_data = result.file_path_or_data
        assert "entry_id" in csv_data
        assert "company_id" in csv_data

    def test_export_csv_has_rows(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1", format=ExportFormat.CSV)
        lines = result.file_path_or_data.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    def test_export_empty_company(self):
        svc = AuditLogService()
        svc.reset("co-empty")
        result = svc.export_events("co-empty", format=ExportFormat.JSON)
        assert result.total_entries == 0
        assert result.entry_count == 0

    def test_export_empty_csv(self):
        svc = AuditLogService()
        svc.reset("co-empty")
        result = svc.export_events("co-empty", format=ExportFormat.CSV)
        assert result.file_path_or_data == ""

    def test_export_filter_by_category(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1", format=ExportFormat.JSON,
                                   category="system")
        assert result.total_entries == 1

    def test_export_redacts_sensitive_metadata(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1", format=ExportFormat.JSON)
        for entry_dict in result.file_path_or_data["entries"]:
            if "password" in entry_dict.get("metadata", {}):
                val = entry_dict["metadata"]["password"]
                assert "*" in val or val == ""

    def test_export_result_company_id(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1")
        assert result.company_id == "co-1"

    def test_export_sets_timestamps(self):
        svc = self._seed_svc()
        result = svc.export_events("co-1")
        assert result.export_started_at is not None
        assert result.export_completed_at is not None

    def test_export_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.export_events("")

    def test_export_json_meta_has_filters(self):
        svc = self._seed_svc()
        result = svc.export_events(
            "co-1", format=ExportFormat.JSON, category="system",
        )
        meta = result.file_path_or_data["export_meta"]
        assert meta["filters"]["category"] == "system"


# ══════════════════════════════════════════════════════════════════
# 10. TestRetention
# ══════════════════════════════════════════════════════════════════


class TestRetention:
    """Test retention_cleanup, get/set_retention_policy."""

    def _make_svc(self):
        svc = AuditLogService()
        svc.reset("co-1")
        return svc

    def test_get_default_policy(self):
        svc = self._make_svc()
        policy = svc.get_retention_policy("co-1")
        assert policy.company_id == "co-1"
        assert policy.enable_auto_cleanup is True

    def test_get_default_policy_has_category_retention(self):
        svc = self._make_svc()
        policy = svc.get_retention_policy("co-1")
        assert len(policy.category_retention_days) > 0

    def test_get_default_policy_authentication_retention(self):
        svc = self._make_svc()
        policy = svc.get_retention_policy("co-1")
        assert policy.category_retention_days.get("authentication") == 2555

    def test_get_default_policy_system_retention(self):
        svc = self._make_svc()
        policy = svc.get_retention_policy("co-1")
        assert policy.category_retention_days.get("system") == 90

    def test_set_custom_policy(self):
        svc = self._make_svc()
        custom = AuditRetentionPolicy(
            company_id="co-1",
            category_retention_days={"system": 30},
            max_entries_per_category=50,
        )
        result = svc.set_retention_policy("co-1", custom)
        assert result.max_entries_per_category == 50
        assert result.category_retention_days["system"] == 30

    def test_set_policy_persisted(self):
        svc = self._make_svc()
        custom = AuditRetentionPolicy(
            company_id="co-1",
            category_retention_days={"system": 10},
        )
        svc.set_retention_policy("co-1", custom)
        fetched = svc.get_retention_policy("co-1")
        assert fetched.category_retention_days["system"] == 10

    def test_set_policy_company_mismatch_raises(self):
        svc = self._make_svc()
        custom = AuditRetentionPolicy(
            company_id="co-other",
            category_retention_days={"system": 30},
        )
        with pytest.raises(AuditLogError):
            svc.set_retention_policy("co-1", custom)

    def test_set_policy_none_raises(self):
        svc = self._make_svc()
        with pytest.raises(AuditLogError):
            svc.set_retention_policy("co-1", None)

    def test_set_policy_invalid_days_raises(self):
        svc = self._make_svc()
        custom = AuditRetentionPolicy(
            company_id="co-1",
            category_retention_days={"system": -5},
        )
        with pytest.raises(AuditLogError):
            svc.set_retention_policy("co-1", custom)

    def test_set_policy_zero_days_raises(self):
        svc = self._make_svc()
        custom = AuditRetentionPolicy(
            company_id="co-1",
            category_retention_days={"system": 0},
        )
        with pytest.raises(AuditLogError):
            svc.set_retention_policy("co-1", custom)

    def test_cleanup_default_no_removal(self):
        svc = self._make_svc()
        svc.log_event("co-1", "system", "info", "ping")
        removed = svc.retention_cleanup("co-1")
        assert removed == 0

    def test_cleanup_with_max_entries(self):
        svc = self._make_svc()
        custom = AuditRetentionPolicy(
            company_id="co-1",
            category_retention_days={"system": 3650},
            max_entries_per_category=1,
        )
        svc.set_retention_policy("co-1", custom)
        svc.log_event("co-1", "system", "info", "ping1")
        svc.log_event("co-1", "system", "info", "ping2")
        removed = svc.retention_cleanup("co-1")
        assert removed == 1
        remaining = svc._get_entries("co-1")
        assert len(remaining) == 1

    def test_cleanup_with_custom_policy_arg(self):
        svc = self._make_svc()
        svc.log_event("co-1", "system", "info", "ping")
        policy = AuditRetentionPolicy(
            company_id="co-1",
            category_retention_days={"system": 3650},
        )
        removed = svc.retention_cleanup("co-1", policy=policy)
        assert removed == 0

    def test_cleanup_company_scoped(self):
        svc = AuditLogService()
        svc.reset("co-a")
        svc.reset("co-b")
        svc.log_event("co-a", "system", "info", "ping")
        svc.log_event("co-b", "system", "info", "pong")
        removed = svc.retention_cleanup("co-a")
        assert len(svc._get_entries("co-b")) == 1

    def test_cleanup_empty_company(self):
        svc = self._make_svc()
        removed = svc.retention_cleanup("co-1")
        assert removed == 0

    def test_get_policy_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.get_retention_policy("")

    def test_set_policy_empty_company_id_raises(self):
        svc = AuditLogService()
        custom = AuditRetentionPolicy(company_id="", category_retention_days={})
        with pytest.raises(AuditLogError):
            svc.set_retention_policy("", custom)

    def test_cleanup_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.retention_cleanup("")

    def test_policy_company_isolation(self):
        svc = AuditLogService()
        svc.reset("co-a")
        svc.reset("co-b")
        custom_a = AuditRetentionPolicy(
            company_id="co-a",
            category_retention_days={"system": 10},
        )
        svc.set_retention_policy("co-a", custom_a)
        policy_b = svc.get_retention_policy("co-b")
        assert policy_b.category_retention_days.get("system") != 10


# ══════════════════════════════════════════════════════════════════
# 11. TestRedaction
# ══════════════════════════════════════════════════════════════════


class TestRedaction:
    """Test redact_sensitive_data and internal _redact_field."""

    def test_redact_field_short_value(self):
        svc = AuditLogService()
        assert svc._redact_field("ab") == "**"

    def test_redact_field_single_char(self):
        svc = AuditLogService()
        assert svc._redact_field("a") == "*"

    def test_redact_field_empty(self):
        svc = AuditLogService()
        assert svc._redact_field("") == ""

    def test_redact_field_none(self):
        svc = AuditLogService()
        assert svc._redact_field(None) == ""

    def test_redact_field_preserves_first_last(self):
        svc = AuditLogService()
        result = svc._redact_field("abcdef")
        assert result == "a****f"

    def test_redact_field_numeric_string(self):
        svc = AuditLogService()
        result = svc._redact_field("12345")
        assert result == "1***5"

    def test_redact_sensitive_data_password_in_metadata(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event(
            "co-1", "system", "info", "config_change",
            metadata={"password": "mysecret"},
        )
        result = svc.redact_sensitive_data("co-1", entry.entry_id)
        assert result is True
        found = svc._find_entry_by_id("co-1", entry.entry_id)
        assert "*" in found.metadata["password"]

    def test_redact_sensitive_data_token_in_metadata(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event(
            "co-1", "system", "info", "config_change",
            metadata={"token": "bearer_abc"},
        )
        svc.redact_sensitive_data("co-1", entry.entry_id)
        found = svc._find_entry_by_id("co-1", entry.entry_id)
        assert "*" in found.metadata["token"]

    def test_redact_sensitive_data_api_key_in_metadata(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event(
            "co-1", "system", "info", "config_change",
            metadata={"api_key": "key123"},
        )
        svc.redact_sensitive_data("co-1", entry.entry_id)
        found = svc._find_entry_by_id("co-1", entry.entry_id)
        assert "*" in found.metadata["api_key"]

    def test_redact_sensitive_data_secret_in_metadata(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event(
            "co-1", "system", "info", "config_change",
            metadata={"secret": "top_secret"},
        )
        svc.redact_sensitive_data("co-1", entry.entry_id)
        found = svc._find_entry_by_id("co-1", entry.entry_id)
        assert "*" in found.metadata["secret"]

    def test_redact_recomputes_checksum(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event(
            "co-1", "system", "info", "config_change",
            metadata={"password": "mypass"},
        )
        old_checksum = entry.checksum
        svc.redact_sensitive_data("co-1", entry.entry_id)
        found = svc._find_entry_by_id("co-1", entry.entry_id)
        assert found.checksum != old_checksum

    def test_redact_entry_not_found_returns_false(self):
        svc = AuditLogService()
        svc.reset("co-1")
        result = svc.redact_sensitive_data("co-1", "nonexistent")
        assert result is False

    def test_redact_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.redact_sensitive_data("", "entry-id")

    def test_redact_empty_entry_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.redact_sensitive_data("co-1", "")

    def test_redact_if_sensitive_json_blob(self):
        svc = AuditLogService()
        json_val = '{"password": "mysecret", "name": "john"}'
        result = svc._redact_if_sensitive(json_val)
        assert "mysecret" not in result
        assert "*" in result

    def test_redact_if_sensitive_non_json_passthrough(self):
        svc = AuditLogService()
        result = svc._redact_if_sensitive("just plain text")
        assert result == "just plain text"

    def test_redact_if_sensitive_none_passthrough(self):
        svc = AuditLogService()
        assert svc._redact_if_sensitive(None) is None


# ══════════════════════════════════════════════════════════════════
# 12. TestAlerts
# ══════════════════════════════════════════════════════════════════


class TestAlerts:
    """Test get_alerts retrieval and alert generation."""

    def test_get_alerts_empty(self):
        svc = AuditLogService()
        svc.reset("co-1")
        alerts = svc.get_alerts("co-1")
        assert alerts == []

    def test_get_alerts_after_login_failed(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "audit_login_failed"

    def test_get_alerts_newest_first(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        svc.log_event("co-1", "data_modification", "critical", "delete")
        alerts = svc.get_alerts("co-1")
        assert alerts[0]["created_at"] >= alerts[1]["created_at"]

    def test_get_alerts_has_alert_id(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        alerts = svc.get_alerts("co-1")
        assert "alert_id" in alerts[0]

    def test_get_alerts_company_id_in_alert(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        alerts = svc.get_alerts("co-1")
        assert alerts[0]["company_id"] == "co-1"

    def test_get_alerts_acknowledged_false(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        alerts = svc.get_alerts("co-1")
        assert alerts[0]["acknowledged"] is False

    def test_get_alerts_empty_company_id_raises(self):
        svc = AuditLogService()
        with pytest.raises(AuditLogError):
            svc.get_alerts("")

    def test_alerts_multiple_actions(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        svc.log_event("co-1", "data_modification", "critical", "delete")
        svc.log_event("co-1", "authorization", "warning", "permission_change")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 3

    def test_alerts_company_isolation(self):
        svc = AuditLogService()
        svc.reset("co-a")
        svc.reset("co-b")
        svc.log_event("co-a", "authentication", "warning", "login_failed")
        alerts_a = svc.get_alerts("co-a")
        alerts_b = svc.get_alerts("co-b")
        assert len(alerts_a) == 1
        assert len(alerts_b) == 0

    def test_alert_eviction_at_cap(self):
        svc = AuditLogService()
        svc.reset("co-1")
        for i in range(105):
            svc.log_event("co-1", "authentication", "warning", "login_failed")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 100


# ══════════════════════════════════════════════════════════════════
# 13. TestReset
# ══════════════════════════════════════════════════════════════════


class TestReset:
    """Test reset for per-company and global state clearing."""

    def test_reset_per_company_clears_entries(self):
        svc = AuditLogService()
        svc.log_event("co-1", "system", "info", "ping")
        svc.reset("co-1")
        assert len(svc._get_entries("co-1")) == 0

    def test_reset_per_company_clears_alerts(self):
        svc = AuditLogService()
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        svc.reset("co-1")
        assert svc.get_alerts("co-1") == []

    def test_reset_per_company_clears_policies(self):
        svc = AuditLogService()
        svc.log_event("co-1", "system", "info", "ping")
        svc.get_retention_policy("co-1")
        svc.reset("co-1")
        assert "co-1" not in svc._retention_policies

    def test_reset_per_company_does_not_affect_others(self):
        svc = AuditLogService()
        svc.log_event("co-a", "system", "info", "ping")
        svc.log_event("co-b", "system", "info", "pong")
        svc.reset("co-a")
        assert len(svc._get_entries("co-a")) == 0
        assert len(svc._get_entries("co-b")) == 1

    def test_reset_global_clears_all(self):
        svc = AuditLogService()
        svc.log_event("co-a", "system", "info", "ping")
        svc.log_event("co-b", "system", "info", "pong")
        svc.reset("")
        assert len(svc._get_entries("co-a")) == 0
        assert len(svc._get_entries("co-b")) == 0


# ══════════════════════════════════════════════════════════════════
# 14. TestIsHealthy
# ══════════════════════════════════════════════════════════════════


class TestIsHealthy:
    """Test is_healthy health check."""

    def test_healthy_default(self):
        svc = AuditLogService()
        assert svc.is_healthy() is True

    def test_healthy_after_operations(self):
        svc = AuditLogService()
        svc.reset("co-1")
        svc.log_event("co-1", "system", "info", "ping")
        assert svc.is_healthy() is True

    def test_healthy_checks_config_type(self):
        svc = AuditLogService()
        svc.is_healthy()  # Should not raise
        assert isinstance(svc.config, AuditLogConfig)


# ══════════════════════════════════════════════════════════════════
# 15. TestBC008GracefulDegradation
# ══════════════════════════════════════════════════════════════════


class TestBC008GracefulDegradation:
    """BC-008: Methods should not crash on unexpected errors."""

    def test_log_event_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        # Patch _compute_checksum to raise
        with patch.object(svc, "_compute_checksum", side_effect=RuntimeError("boom")):
            result = svc.log_event("co-1", "system", "info", "ping")
        assert result is not None
        assert isinstance(result, AuditLogEntry)

    def test_query_events_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        with patch.object(svc, "_get_entries", side_effect=RuntimeError("boom")):
            entries, total = svc.query_events("co-1")
        assert entries == []
        assert total == 0

    def test_get_statistics_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        with patch.object(svc, "_get_entries", side_effect=RuntimeError("boom")):
            stats = svc.get_statistics("co-1")
        assert isinstance(stats, AuditStats)

    def test_verify_integrity_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        with patch.object(svc, "_get_entries", side_effect=RuntimeError("boom")):
            report = svc.verify_integrity("co-1")
        assert isinstance(report, AuditIntegrityReport)

    def test_export_events_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        with patch.object(svc, "_get_entries", side_effect=RuntimeError("boom")):
            result = svc.export_events("co-1")
        assert isinstance(result, AuditExportResult)

    def test_retention_cleanup_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        with patch.object(svc, "_get_entries", side_effect=RuntimeError("boom")):
            removed = svc.retention_cleanup("co-1")
        assert removed == 0

    def test_get_alerts_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        with patch.object(svc, "_get_entries", side_effect=RuntimeError("boom")):
            alerts = svc.get_alerts("co-1")
        assert alerts == []

    def test_redact_sensitive_data_does_not_crash_on_unexpected(self):
        svc = AuditLogService()
        svc.reset("co-1")
        with patch.object(svc, "_find_entry_by_id", side_effect=RuntimeError("boom")):
            result = svc.redact_sensitive_data("co-1", "e-1")
        assert result is False


# ══════════════════════════════════════════════════════════════════
# 16. TestInternalHelpers
# ══════════════════════════════════════════════════════════════════


class TestInternalHelpers:
    """Test internal helper methods."""

    def test_get_entries_empty_company(self):
        svc = AuditLogService()
        assert svc._get_entries("nonexistent") == []

    def test_find_entry_by_id_found(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event("co-1", "system", "info", "ping")
        found = svc._find_entry_by_id("co-1", entry.entry_id)
        assert found is not None
        assert found.entry_id == entry.entry_id

    def test_find_entry_by_id_not_found(self):
        svc = AuditLogService()
        svc.reset("co-1")
        found = svc._find_entry_by_id("co-1", "nonexistent")
        assert found is None

    def test_compute_checksum_deterministic(self):
        svc = AuditLogService()
        data = {"entry_id": "e-1", "company_id": "c-1",
                "category": "system", "severity": "info",
                "action": "ping", "actor_id": None, "actor_type": "user",
                "resource_type": None, "resource_id": None,
                "old_value": None, "new_value": None, "ip_address": None,
                "metadata": {}, "created_at": "2025-01-01T00:00:00+00:00"}
        cs1 = svc._compute_checksum(data)
        cs2 = svc._compute_checksum(data)
        assert cs1 == cs2
        assert len(cs1) == 64  # SHA-256 hex

    def test_validate_checksum_valid(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event("co-1", "system", "info", "ping")
        assert svc._validate_checksum(entry) is True

    def test_validate_checksum_tampered(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event("co-1", "system", "info", "ping")
        entry.action = "TAMPERED"
        assert svc._validate_checksum(entry) is False

    def test_validate_checksum_disabled(self):
        cfg = AuditLogConfig(enable_checksum=False)
        svc = AuditLogService(config=cfg)
        entry = AuditLogEntry(
            entry_id="e-1", company_id="c-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO,
            action="ping", checksum="invalid",
        )
        assert svc._validate_checksum(entry) is True

    def test_entry_to_dict_without_redact(self):
        svc = AuditLogService()
        entry = AuditLogEntry(
            entry_id="e-1", company_id="c-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO,
            action="ping", metadata={"secret": "value"},
        )
        d = svc._entry_to_dict(entry, redact=False)
        assert d["metadata"]["secret"] == "value"

    def test_entry_to_dict_with_redact(self):
        svc = AuditLogService()
        entry = AuditLogEntry(
            entry_id="e-1", company_id="c-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO,
            action="ping", metadata={"password": "mysecret"},
        )
        d = svc._entry_to_dict(entry, redact=True)
        assert "*" in d["metadata"]["password"]

    def test_should_retain_recent_entry(self):
        svc = AuditLogService()
        svc.reset("co-1")
        entry = svc.log_event("co-1", "system", "info", "ping")
        policy = AuditRetentionPolicy(company_id="co-1")
        assert svc._should_retain(entry, policy) is True

    def test_should_retain_old_system_entry(self):
        svc = AuditLogService()
        svc.reset("co-1")
        old_time = datetime.now(timezone.utc) - timedelta(days=200)
        entry = AuditLogEntry(
            entry_id="e-old", company_id="co-1",
            category=AuditCategory.SYSTEM, severity=AuditSeverity.INFO,
            action="ping", created_at=old_time,
        )
        policy = AuditRetentionPolicy(company_id="co-1")
        assert svc._should_retain(entry, policy) is False


# ══════════════════════════════════════════════════════════════════
# 17. TestAuditLogError
# ══════════════════════════════════════════════════════════════════


class TestAuditLogError:
    """Test custom error class."""

    def test_error_inherits_exception(self):
        assert issubclass(AuditLogError, Exception)

    def test_error_has_message(self):
        err = AuditLogError(
            error_code="TEST",
            message="test message",
            status_code=400,
        )
        assert err.message == "test message"

    def test_error_has_error_code(self):
        err = AuditLogError(
            error_code="INVALID_COMPANY_ID",
            message="test",
            status_code=400,
        )
        assert err.error_code == "INVALID_COMPANY_ID"

    def test_error_has_status_code(self):
        err = AuditLogError(
            error_code="TEST",
            message="test",
            status_code=500,
        )
        assert err.status_code == 500


# ══════════════════════════════════════════════════════════════════
# 18. TestSecurityRelevantActions
# ══════════════════════════════════════════════════════════════════


class TestSecurityRelevantActions:
    """Test that security-relevant actions trigger alerts."""

    def _make_svc(self):
        svc = AuditLogService()
        svc.reset("co-1")
        return svc

    def test_login_failed_creates_alert(self):
        svc = self._make_svc()
        svc.log_event("co-1", "authentication", "warning", "login_failed")
        alerts = svc.get_alerts("co-1")
        assert any(a["alert_type"] == "audit_login_failed" for a in alerts)

    def test_permission_change_creates_alert(self):
        svc = self._make_svc()
        svc.log_event("co-1", "authorization", "warning", "permission_change")
        alerts = svc.get_alerts("co-1")
        assert any(a["alert_type"] == "audit_permission_change" for a in alerts)

    def test_api_key_revoke_creates_alert(self):
        svc = self._make_svc()
        svc.log_event("co-1", "authorization", "info", "api_key_revoke")
        alerts = svc.get_alerts("co-1")
        assert any(a["alert_type"] == "audit_api_key_revoke" for a in alerts)

    def test_api_key_rotate_creates_alert(self):
        svc = self._make_svc()
        svc.log_event("co-1", "authorization", "info", "api_key_rotate")
        alerts = svc.get_alerts("co-1")
        assert any(a["alert_type"] == "audit_api_key_rotate" for a in alerts)

    def test_settings_change_creates_alert(self):
        svc = self._make_svc()
        svc.log_event("co-1", "system", "info", "settings_change")
        alerts = svc.get_alerts("co-1")
        assert any(a["alert_type"] == "audit_settings_change" for a in alerts)

    def test_export_action_creates_alert(self):
        svc = self._make_svc()
        svc.log_event("co-1", "data_access", "info", "export")
        alerts = svc.get_alerts("co-1")
        assert any(a["alert_type"] == "audit_export" for a in alerts)

    def test_non_security_action_no_alert(self):
        svc = self._make_svc()
        svc.log_event("co-1", "system", "info", "health_check")
        alerts = svc.get_alerts("co-1")
        assert len(alerts) == 0
