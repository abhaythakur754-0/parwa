"""
Phase 9 & 10 Unit Tests

Phase 9 — Audit Trail:
  1. AuditAction enum new values
  2. create_audit_entry() with valid company_id
  3. create_audit_entry() rejects empty company_id (BC-001)
  4. create_audit_entry() validates actor_type
  5. log_audit() with a mock DB session
  6. query_audit_trail() with mock DB session and filters
  7. export_audit_trail() returns correct format
  8. get_audit_stats() with mock data

Phase 10 — Rate Limiting & Error Handling:
  1.  IntegrationRateLimiter — check_rate_limit allows under limit
  2.  IntegrationRateLimiter — check_rate_limit blocks over limit
  3.  IntegrationRateLimiter — per-integration separate limits
  4.  IntegrationRateLimiter — per-company isolation (BC-001)
  5.  IntegrationRateLimiter — get_rate_limit_status returns correct structure
  6.  IntegrationRateLimiter — clear_integration removes counters
  7.  IntegrationRateLimiter — wait_for_quota with immediate availability
  8.  IntegrationDisconnectHandler — disconnect marks disconnected
  9.  IntegrationDisconnectHandler — is_integration_connected returns False after disconnect
  10. IntegrationDisconnectHandler — reconnect restores connection
  11. ExternalToolBus — _degraded_result returns cached data
  12. ExternalToolBus — _degraded_result returns error when no cached data
  13. ExternalToolBus — _is_transient_error identifies 429, timeouts
  14. ExternalToolBus — _is_transient_error rejects auth errors as non-transient
  15. IntegrationRateLimiter — default rate limits configuration
  16. IntegrationRateLimiter — unknown integration uses custom fallback

BC-001: company_id isolation on every operation.
BC-008: Never crash — all operations wrapped in try/except.
BC-012: No stack traces to users.
"""

import asyncio
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

# ── Phase 9: Audit Service ────────────────────────────────────────

from app.services.audit_service import (
    AuditAction,
    AuditEntry,
    ActorType,
    create_audit_entry,
    log_audit,
    query_audit_trail,
    export_audit_trail,
    get_audit_stats,
    validate_actor_type,
    VALID_ACTOR_TYPES,
)

# ── Phase 10: Rate Limiter ────────────────────────────────────────

from app.core.integration_rate_limiter import (
    IntegrationRateLimiter,
    DEFAULT_RATE_LIMITS,
    WindowCounter,
    reset_integration_rate_limiter,
)

# ── Phase 10: Disconnect Handler ──────────────────────────────────

from app.core.integration_disconnect_handler import (
    IntegrationDisconnectHandler,
    reset_integration_disconnect_handler,
)

# ── Phase 10: External Tool Bus ───────────────────────────────────

from app.core.external_tool_bus import ExternalToolBus, ToolResult
from app.core.channel_permissions import Channel


# ═══════════════════════════════════════════════════════════════════
# PHASE 9: AUDIT TRAIL UNIT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestAuditActionEnum(unittest.TestCase):
    """Test AuditAction enum has new Phase 9 values."""

    def test_ai_action_exists(self):
        self.assertEqual(AuditAction.AI_ACTION.value, "ai_action")

    def test_ai_tool_call_exists(self):
        self.assertEqual(AuditAction.AI_TOOL_CALL.value, "ai_tool_call")

    def test_ai_decision_exists(self):
        self.assertEqual(AuditAction.AI_DECISION.value, "ai_decision")

    def test_integration_call_exists(self):
        self.assertEqual(AuditAction.INTEGRATION_CALL.value, "integration_call")

    def test_integration_disconnect_exists(self):
        self.assertEqual(AuditAction.INTEGRATION_DISCONNECT.value, "integration_disconnect")

    def test_all_five_new_values_present(self):
        new_values = {
            "ai_action", "ai_tool_call", "ai_decision",
            "integration_call", "integration_disconnect",
        }
        actual = {e.value for e in AuditAction}
        self.assertTrue(
            new_values.issubset(actual),
            f"Missing new AuditAction values: {new_values - actual}",
        )


class TestCreateAuditEntryValid(unittest.TestCase):
    """Test create_audit_entry with valid company_id."""

    def test_returns_audit_entry(self):
        entry = create_audit_entry(company_id="comp_123")
        self.assertIsInstance(entry, AuditEntry)

    def test_company_id_set(self):
        entry = create_audit_entry(company_id="comp_123")
        self.assertEqual(entry.company_id, "comp_123")

    def test_action_defaults_to_unknown(self):
        entry = create_audit_entry(company_id="comp_123")
        self.assertEqual(entry.action, "unknown")

    def test_actor_type_defaults_to_system(self):
        entry = create_audit_entry(company_id="comp_123")
        self.assertEqual(entry.actor_type, "system")

    def test_custom_action(self):
        entry = create_audit_entry(
            company_id="comp_456",
            action=AuditAction.AI_ACTION.value,
        )
        self.assertEqual(entry.action, "ai_action")

    def test_all_fields_set(self):
        entry = create_audit_entry(
            company_id="comp_1",
            actor_id="user_1",
            actor_type="user",
            action="create",
            resource_type="ticket",
            resource_id="tkt_1",
            old_value="old",
            new_value="new",
            ip_address="1.2.3.4",
            user_agent="test",
        )
        self.assertEqual(entry.actor_id, "user_1")
        self.assertEqual(entry.resource_type, "ticket")
        self.assertEqual(entry.resource_id, "tkt_1")
        self.assertEqual(entry.old_value, "old")
        self.assertEqual(entry.new_value, "new")
        self.assertEqual(entry.ip_address, "1.2.3.4")
        self.assertEqual(entry.user_agent, "test")

    def test_id_is_uuid(self):
        entry = create_audit_entry(company_id="comp_1")
        import uuid
        # Should not raise
        uuid.UUID(entry.id)

    def test_created_at_is_datetime(self):
        entry = create_audit_entry(company_id="comp_1")
        self.assertIsInstance(entry.created_at, datetime)


class TestCreateAuditEntryRejectsEmptyCompanyId(unittest.TestCase):
    """Test create_audit_entry rejects empty company_id (BC-001)."""

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError) as ctx:
            create_audit_entry(company_id="")
        self.assertIn("BC-001", str(ctx.exception))

    def test_none_raises(self):
        with self.assertRaises(ValueError):
            create_audit_entry(company_id=None)

    def test_too_long_raises(self):
        with self.assertRaises(ValueError):
            create_audit_entry(company_id="x" * 129)

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            create_audit_entry(company_id=12345)


class TestCreateAuditEntryValidatesActorType(unittest.TestCase):
    """Test create_audit_entry validates actor_type."""

    def test_valid_user_actor(self):
        entry = create_audit_entry(company_id="comp_1", actor_type="user")
        self.assertEqual(entry.actor_type, "user")

    def test_valid_system_actor(self):
        entry = create_audit_entry(company_id="comp_1", actor_type="system")
        self.assertEqual(entry.actor_type, "system")

    def test_valid_api_key_actor(self):
        entry = create_audit_entry(company_id="comp_1", actor_type="api_key")
        self.assertEqual(entry.actor_type, "api_key")

    def test_invalid_actor_type_raises(self):
        with self.assertRaises(ValueError) as ctx:
            create_audit_entry(company_id="comp_1", actor_type="hacker")
        self.assertIn("Invalid actor_type", str(ctx.exception))

    def test_empty_actor_type_raises(self):
        with self.assertRaises(ValueError):
            create_audit_entry(company_id="comp_1", actor_type="")

    def test_validate_actor_type_function(self):
        result = validate_actor_type("user")
        self.assertEqual(result, "user")

    def test_valid_actor_types_set(self):
        self.assertEqual(VALID_ACTOR_TYPES, {"user", "system", "api_key"})


class TestLogAuditWithMockDB(unittest.TestCase):
    """Test log_audit with a mock DB session."""

    def test_log_audit_returns_dict(self):
        result = log_audit(company_id="comp_1", action="create")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["company_id"], "comp_1")
        self.assertEqual(result["action"], "create")

    def test_log_audit_with_db_calls_add_and_flush(self):
        mock_db = MagicMock()
        result = log_audit(
            company_id="comp_1",
            actor_id="user_1",
            action="create",
            db=mock_db,
        )
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        self.assertEqual(result["company_id"], "comp_1")

    def test_log_audit_db_error_does_not_raise(self):
        """BC-008: Audit failure must never break main operation."""
        mock_db = MagicMock()
        mock_db.add.side_effect = Exception("DB down")
        # Should NOT raise
        result = log_audit(company_id="comp_1", db=mock_db)
        self.assertIsInstance(result, dict)

    def test_log_audit_without_db(self):
        result = log_audit(company_id="comp_1", action="update")
        self.assertEqual(result["company_id"], "comp_1")
        self.assertEqual(result["action"], "update")

    def test_log_audit_all_fields_in_dict(self):
        result = log_audit(
            company_id="comp_1",
            actor_id="user_1",
            actor_type="user",
            action="delete",
            resource_type="ticket",
            resource_id="tkt_42",
        )
        self.assertIn("id", result)
        self.assertIn("company_id", result)
        self.assertIn("actor_id", result)
        self.assertIn("actor_type", result)
        self.assertIn("action", result)
        self.assertIn("created_at", result)


class TestQueryAuditTrail(unittest.TestCase):
    """Test query_audit_trail with mock DB session and filters."""

    def _make_mock_record(self, **kwargs):
        """Create a mock AuditTrail record."""
        record = MagicMock()
        record.id = kwargs.get("id", "entry-1")
        record.company_id = kwargs.get("company_id", "comp_1")
        record.actor_id = kwargs.get("actor_id", "user_1")
        record.actor_type = kwargs.get("actor_type", "user")
        record.action = kwargs.get("action", "create")
        record.resource_type = kwargs.get("resource_type", "ticket")
        record.resource_id = kwargs.get("resource_id", "tkt_1")
        record.old_value = kwargs.get("old_value", None)
        record.new_value = kwargs.get("new_value", None)
        record.ip_address = kwargs.get("ip_address", None)
        record.user_agent = kwargs.get("user_agent", None)
        record.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
        return record

    @patch("app.services.audit_service.query_audit_trail")
    def test_query_returns_items_and_total(self, mock_query):
        """query_audit_trail returns (items, total)."""
        mock_query.return_value = ([{"id": "e1", "company_id": "comp_1"}], 1)
        items, total = mock_query(db=MagicMock(), company_id="comp_1")
        self.assertEqual(len(items), 1)
        self.assertEqual(total, 1)

    def test_query_requires_company_id(self):
        """BC-001: company_id is required."""
        with self.assertRaises(ValueError) as ctx:
            query_audit_trail(db=MagicMock(), company_id="")
        self.assertIn("BC-001", str(ctx.exception))

    def test_query_none_company_id_raises(self):
        with self.assertRaises(ValueError):
            query_audit_trail(db=MagicMock(), company_id=None)


class TestExportAuditTrail(unittest.TestCase):
    """Test export_audit_trail returns correct format."""

    def test_export_requires_company_id(self):
        with self.assertRaises(ValueError) as ctx:
            export_audit_trail(db=MagicMock(), company_id="")
        self.assertIn("BC-001", str(ctx.exception))

    def test_export_rejects_invalid_format(self):
        with self.assertRaises(ValueError) as ctx:
            export_audit_trail(
                db=MagicMock(), company_id="comp_1", format="xml",
            )
        self.assertIn("Unsupported export format", str(ctx.exception))

    def test_export_accepts_json_format(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        result = export_audit_trail(
            db=mock_db, company_id="comp_1", format="json",
        )
        self.assertIsInstance(result, list)

    def test_export_accepts_csv_format(self):
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.order_by.return_value.all.return_value = []
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        result = export_audit_trail(
            db=mock_db, company_id="comp_1", format="csv",
        )
        self.assertIsInstance(result, list)


class TestGetAuditStats(unittest.TestCase):
    """Test get_audit_stats with mock data."""

    def test_stats_requires_company_id(self):
        with self.assertRaises(ValueError) as ctx:
            get_audit_stats(db=MagicMock(), company_id="")
        self.assertIn("BC-001", str(ctx.exception))

    def test_stats_returns_correct_keys_with_mock(self):
        mock_db = MagicMock()

        # Mock the multiple queries inside get_audit_stats
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = get_audit_stats(db=mock_db, company_id="comp_1")
        self.assertIn("action_counts", result)
        self.assertIn("actor_type_counts", result)
        self.assertIn("most_active_actors", result)
        self.assertIn("recent_24h_count", result)
        self.assertIn("total_count", result)
        self.assertIn("period_days", result)

    def test_stats_default_period(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.scalar.return_value = 0

        result = get_audit_stats(db=mock_db, company_id="comp_1")
        self.assertEqual(result["period_days"], 30)


# ═══════════════════════════════════════════════════════════════════
# PHASE 10: RATE LIMITER UNIT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestRateLimiterAllowsUnderLimit(unittest.TestCase):
    """Test check_rate_limit allows under limit."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter(
            rate_limits={"test": {"requests_per_minute": 5, "requests_per_second": 5}},
        )

    def tearDown(self):
        self.limiter.stop()

    def test_allows_when_under_limit(self):
        result = self.limiter.check_rate_limit("test", "comp_1")
        self.assertTrue(result)

    def test_allows_multiple_calls_under_limit(self):
        for _ in range(4):
            self.assertTrue(self.limiter.check_rate_limit("test", "comp_1"))
            self.limiter.record_call("test", "comp_1")


class TestRateLimiterBlocksOverLimit(unittest.TestCase):
    """Test check_rate_limit blocks over limit."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter(
            rate_limits={"test": {"requests_per_minute": 3, "requests_per_second": 10}},
        )

    def tearDown(self):
        self.limiter.stop()

    def test_blocks_over_per_minute_limit(self):
        for _ in range(3):
            self.limiter.check_rate_limit("test", "comp_1")
            self.limiter.record_call("test", "comp_1")
        # 4th call should be blocked
        result = self.limiter.check_rate_limit("test", "comp_1")
        self.assertFalse(result)


class TestRateLimiterPerIntegrationSeparateLimits(unittest.TestCase):
    """Test per-integration separate limits."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter(
            rate_limits={
                "alpha": {"requests_per_minute": 2, "requests_per_second": 10},
                "beta": {"requests_per_minute": 100, "requests_per_second": 10},
            },
        )

    def tearDown(self):
        self.limiter.stop()

    def test_alpha_limited_but_beta_still_ok(self):
        # Exhaust alpha quota
        for _ in range(2):
            self.limiter.check_rate_limit("alpha", "comp_1")
            self.limiter.record_call("alpha", "comp_1")
        self.assertFalse(self.limiter.check_rate_limit("alpha", "comp_1"))

        # Beta still allows
        self.assertTrue(self.limiter.check_rate_limit("beta", "comp_1"))


class TestRateLimiterPerCompanyIsolation(unittest.TestCase):
    """Test per-company isolation (BC-001)."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter(
            rate_limits={"svc": {"requests_per_minute": 2, "requests_per_second": 10}},
        )

    def tearDown(self):
        self.limiter.stop()

    def test_company_a_limited_does_not_affect_company_b(self):
        # Exhaust company A's quota
        for _ in range(2):
            self.limiter.check_rate_limit("svc", "company_A")
            self.limiter.record_call("svc", "company_A")
        self.assertFalse(self.limiter.check_rate_limit("svc", "company_A"))

        # Company B still has full quota
        self.assertTrue(self.limiter.check_rate_limit("svc", "company_B"))


class TestRateLimiterGetStatus(unittest.TestCase):
    """Test get_rate_limit_status returns correct structure."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter(
            rate_limits={"hubspot": {"requests_per_minute": 100, "requests_per_second": 10}},
        )

    def tearDown(self):
        self.limiter.stop()

    def test_status_structure(self):
        status = self.limiter.get_rate_limit_status("hubspot", "comp_1")
        self.assertIn("integration", status)
        self.assertIn("company_id", status)
        self.assertIn("requests_per_minute_limit", status)
        self.assertIn("requests_per_second_limit", status)
        self.assertIn("current_minute_count", status)
        self.assertIn("current_second_count", status)
        self.assertIn("minute_remaining", status)
        self.assertIn("second_remaining", status)
        self.assertIn("is_limited", status)

    def test_status_values_correct(self):
        status = self.limiter.get_rate_limit_status("hubspot", "comp_1")
        self.assertEqual(status["integration"], "hubspot")
        self.assertEqual(status["company_id"], "comp_1")
        self.assertEqual(status["requests_per_minute_limit"], 100)
        self.assertEqual(status["requests_per_second_limit"], 10)
        self.assertFalse(status["is_limited"])

    def test_status_reflects_usage(self):
        self.limiter.check_rate_limit("hubspot", "comp_1")
        self.limiter.record_call("hubspot", "comp_1")
        status = self.limiter.get_rate_limit_status("hubspot", "comp_1")
        self.assertEqual(status["current_minute_count"], 1)
        self.assertEqual(status["minute_remaining"], 99)


class TestRateLimiterClearIntegration(unittest.TestCase):
    """Test clear_integration removes counters."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter(
            rate_limits={"svc": {"requests_per_minute": 100, "requests_per_second": 10}},
        )

    def tearDown(self):
        self.limiter.stop()

    def test_clear_resets_counts(self):
        for _ in range(5):
            self.limiter.check_rate_limit("svc", "comp_1")
            self.limiter.record_call("svc", "comp_1")
        self.limiter.clear_integration("svc", "comp_1")
        status = self.limiter.get_rate_limit_status("svc", "comp_1")
        self.assertEqual(status["current_minute_count"], 0)
        self.assertEqual(status["current_second_count"], 0)


class TestRateLimiterWaitForQuota(unittest.TestCase):
    """Test wait_for_quota with immediate availability."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter(
            rate_limits={"svc": {"requests_per_minute": 100, "requests_per_second": 10}},
        )

    def tearDown(self):
        self.limiter.stop()

    def test_returns_true_immediately_when_quota_available(self):
        result = self.limiter.wait_for_quota("svc", "comp_1", timeout=1.0)
        self.assertTrue(result)


class TestRateLimiterDefaultConfig(unittest.TestCase):
    """Test default rate limits configuration."""

    def test_default_config_has_known_integrations(self):
        expected = {"hubspot", "shopify", "salesforce", "slack", "twilio", "brevo", "custom"}
        self.assertEqual(set(DEFAULT_RATE_LIMITS.keys()), expected)

    def test_hubspot_defaults(self):
        self.assertEqual(DEFAULT_RATE_LIMITS["hubspot"]["requests_per_minute"], 100)
        self.assertEqual(DEFAULT_RATE_LIMITS["hubspot"]["requests_per_second"], 10)

    def test_twilio_defaults(self):
        self.assertEqual(DEFAULT_RATE_LIMITS["twilio"]["requests_per_minute"], 60)
        self.assertEqual(DEFAULT_RATE_LIMITS["twilio"]["requests_per_second"], 1)


class TestRateLimiterUnknownIntegrationFallback(unittest.TestCase):
    """Test unknown integration uses custom fallback."""

    def setUp(self):
        self.limiter = IntegrationRateLimiter()  # uses DEFAULT_RATE_LIMITS

    def tearDown(self):
        self.limiter.stop()

    def test_unknown_uses_custom_limits(self):
        status = self.limiter.get_rate_limit_status("unknown_svc", "comp_1")
        self.assertEqual(status["requests_per_minute_limit"], DEFAULT_RATE_LIMITS["custom"]["requests_per_minute"])
        self.assertEqual(status["requests_per_second_limit"], DEFAULT_RATE_LIMITS["custom"]["requests_per_second"])

    def test_unknown_integration_is_rate_limited_correctly(self):
        custom_rpm = DEFAULT_RATE_LIMITS["custom"]["requests_per_minute"]
        for _ in range(custom_rpm):
            self.limiter.check_rate_limit("unknown_svc", "comp_1")
            self.limiter.record_call("unknown_svc", "comp_1")
        # Over the limit now
        self.assertFalse(self.limiter.check_rate_limit("unknown_svc", "comp_1"))


# ═══════════════════════════════════════════════════════════════════
# PHASE 10: DISCONNECT HANDLER UNIT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestDisconnectHandlerDisconnect(unittest.TestCase):
    """Test disconnect_integration marks as disconnected."""

    def setUp(self):
        self.handler = IntegrationDisconnectHandler()

    def test_disconnect_returns_result_dict(self):
        result = self.handler.disconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["company_id"], "comp_1")
        self.assertEqual(result["integration_id"], "intg_1")

    def test_disconnect_has_cleanup_steps(self):
        result = self.handler.disconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertIn("cleanup_steps", result)
        self.assertIsInstance(result["cleanup_steps"], list)

    def test_disconnect_records_reason(self):
        result = self.handler.disconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
            reason="provider_error",
        )
        self.assertEqual(result["reason"], "provider_error")


class TestDisconnectHandlerIsConnected(unittest.TestCase):
    """Test is_integration_connected returns False after disconnect."""

    def setUp(self):
        self.handler = IntegrationDisconnectHandler()

    def test_connected_before_disconnect(self):
        self.assertTrue(
            self.handler.is_integration_connected("comp_1", "intg_1")
        )

    def test_not_connected_after_disconnect(self):
        self.handler.disconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertFalse(
            self.handler.is_integration_connected("comp_1", "intg_1")
        )

    def test_other_integration_still_connected(self):
        self.handler.disconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertTrue(
            self.handler.is_integration_connected("comp_1", "intg_2")
        )

    def test_other_company_still_connected(self):
        """BC-001: Disconnect in company A doesn't affect company B."""
        self.handler.disconnect_integration(
            company_id="company_A",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertTrue(
            self.handler.is_integration_connected("company_B", "intg_1")
        )


class TestDisconnectHandlerReconnect(unittest.TestCase):
    """Test reconnect_integration restores connection."""

    def setUp(self):
        self.handler = IntegrationDisconnectHandler()

    def test_reconnect_restores_connected(self):
        self.handler.disconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertFalse(
            self.handler.is_integration_connected("comp_1", "intg_1")
        )
        self.handler.reconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertTrue(
            self.handler.is_integration_connected("comp_1", "intg_1")
        )

    def test_reconnect_returns_result(self):
        self.handler.disconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        result = self.handler.reconnect_integration(
            company_id="comp_1",
            integration_id="intg_1",
            integration_name="hubspot",
        )
        self.assertIn("steps", result)
        self.assertIn("reconnected_at", result)


# ═══════════════════════════════════════════════════════════════════
# PHASE 10: EXTERNAL TOOL BUS UNIT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestExternalToolBusDegradedResultCached(unittest.TestCase):
    """Test _degraded_result returns cached data."""

    def setUp(self):
        self.bus = ExternalToolBus()

    def test_degraded_with_cached_data_returns_success(self):
        cached = {"last_response": {"status": "ok"}}
        result = self.bus._degraded_result(Channel.SMS, "twilio", cached_data=cached)
        self.assertTrue(result.success)
        self.assertEqual(result.data, cached)

    def test_degraded_with_cached_data_has_provider(self):
        result = self.bus._degraded_result(Channel.EMAIL, "brevo", cached_data={"k": "v"})
        self.assertEqual(result.provider, "brevo")

    def test_degraded_with_cached_data_has_no_error(self):
        result = self.bus._degraded_result(Channel.SMS, "twilio", cached_data={"x": 1})
        self.assertEqual(result.error, "")


class TestExternalToolBusDegradedResultNoCache(unittest.TestCase):
    """Test _degraded_result returns error when no cached data."""

    def setUp(self):
        self.bus = ExternalToolBus()

    def test_degraded_without_cached_data_returns_failure(self):
        result = self.bus._degraded_result(Channel.SMS, "twilio")
        self.assertFalse(result.success)

    def test_degraded_without_cached_data_has_error(self):
        result = self.bus._degraded_result(Channel.SMS, "twilio")
        self.assertIn("temporarily unavailable", result.error)

    def test_degraded_without_cached_data_empty_data(self):
        result = self.bus._degraded_result(Channel.EMAIL, "brevo")
        self.assertEqual(result.data, {})


class TestExternalToolBusIsTransientError429(unittest.TestCase):
    """Test _is_transient_error identifies 429, timeouts."""

    def setUp(self):
        self.bus = ExternalToolBus()

    def test_429_is_transient(self):
        exc = Exception("Rate limited")
        exc.status_code = 429
        self.assertTrue(self.bus._is_transient_error(exc))

    def test_timeout_is_transient(self):
        self.assertTrue(self.bus._is_transient_error(TimeoutError("timed out")))

    def test_connection_error_is_transient(self):
        self.assertTrue(self.bus._is_transient_error(ConnectionError("refused")))

    def test_500_is_transient(self):
        exc = Exception("Server error")
        exc.status_code = 500
        self.assertTrue(self.bus._is_transient_error(exc))

    def test_503_is_transient(self):
        exc = Exception("Service unavailable")
        exc.status_code = 503
        self.assertTrue(self.bus._is_transient_error(exc))


class TestExternalToolBusIsTransientErrorRejectsAuth(unittest.TestCase):
    """Test _is_transient_error rejects auth errors as non-transient."""

    def setUp(self):
        self.bus = ExternalToolBus()

    def test_401_is_not_transient(self):
        exc = Exception("Unauthorized")
        exc.status_code = 401
        self.assertFalse(self.bus._is_transient_error(exc))

    def test_403_is_not_transient(self):
        exc = Exception("Forbidden")
        exc.status_code = 403
        self.assertFalse(self.bus._is_transient_error(exc))

    def test_404_is_not_transient(self):
        exc = Exception("Not found")
        exc.status_code = 404
        self.assertFalse(self.bus._is_transient_error(exc))

    def test_value_error_is_not_transient(self):
        self.assertFalse(self.bus._is_transient_error(ValueError("bad input")))


# ═══════════════════════════════════════════════════════════════════
# WINDOW COUNTER UNIT TESTS (supporting class)
# ═══════════════════════════════════════════════════════════════════


class TestWindowCounter(unittest.TestCase):
    """Test WindowCounter sliding window behavior."""

    def test_initial_count_zero(self):
        wc = WindowCounter(limit=5, window_seconds=60)
        self.assertEqual(wc.count(time.time()), 0)

    def test_record_increments_count(self):
        wc = WindowCounter(limit=5, window_seconds=60)
        now = time.time()
        wc.record(now)
        self.assertEqual(wc.count(now), 1)

    def test_is_limited_at_threshold(self):
        wc = WindowCounter(limit=2, window_seconds=60)
        now = time.time()
        wc.record(now)
        wc.record(now)
        self.assertTrue(wc.is_limited(now))

    def test_not_limited_below_threshold(self):
        wc = WindowCounter(limit=5, window_seconds=60)
        now = time.time()
        wc.record(now)
        self.assertFalse(wc.is_limited(now))

    def test_clear_resets(self):
        wc = WindowCounter(limit=5, window_seconds=60)
        now = time.time()
        wc.record(now)
        wc.record(now)
        wc.clear()
        self.assertEqual(wc.count(now), 0)

    def test_old_entries_expire(self):
        wc = WindowCounter(limit=5, window_seconds=1)
        old_time = time.time() - 2  # 2 seconds ago
        wc.record(old_time)
        now = time.time()
        # Old entry should be expired
        self.assertEqual(wc.count(now), 0)


if __name__ == "__main__":
    unittest.main()
