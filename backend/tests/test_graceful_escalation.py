"""
Comprehensive tests for app.core.graceful_escalation module.

Tests run from /home/z/my-project/backend/ with PYTHONPATH=.
Uses pytest with standard unittest class-based test style.
"""

import time
import unittest

from app.core.graceful_escalation import (
    GracefulEscalationManager,
    EscalationTrigger,
    EscalationSeverity,
    EscalationChannel,
    EscalationOutcome,
    EscalationContext,
    EscalationRecord,
    EscalationRule,
    EscalationConfig,
)

COMPANY_ID = "test_company_001"
COMPANY_ID_B = "test_company_002"
TICKET_ID = "ticket_001"
TICKET_ID_B = "ticket_002"


def _make_context(
    company_id=COMPANY_ID,
    ticket_id=TICKET_ID,
    trigger="legal_sensitive",
    severity="high",
    description="Test escalation",
    frustration_score=0.0,
    confidence_score=0.5,
    failure_count=0,
    customer_tier="",
    conversation_turns=0,
    **kwargs,
):
    """Create an EscalationContext with sensible defaults."""
    return EscalationContext(
        company_id=company_id,
        ticket_id=ticket_id,
        trigger=trigger,
        severity=severity,
        description=description,
        frustration_score=frustration_score,
        confidence_score=confidence_score,
        failure_count=failure_count,
        customer_tier=customer_tier,
        conversation_turns=conversation_turns,
        **kwargs,
    )


class TestEscalationConfig(unittest.TestCase):
    """Test config management (4 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_default_config(self):
        """Defaults: default_severity=medium, default_channel=in_app, cooldown=300, max_per_hour=20."""
        config = self.mgr.get_config(COMPANY_ID)
        self.assertEqual(config.default_severity, "medium")
        self.assertEqual(config.default_channel, "in_app")
        self.assertEqual(config.cooldown_seconds, 300.0)
        self.assertEqual(config.max_escalations_per_hour, 20)

    def test_configure_company(self):
        """Custom config stored and returned for the company."""
        custom = EscalationConfig(
            default_severity="critical",
            default_channel="slack",
            cooldown_seconds=600.0,
            max_escalations_per_hour=5,
        )
        self.mgr.configure(COMPANY_ID, custom)
        config = self.mgr.get_config(COMPANY_ID)
        self.assertEqual(config.default_severity, "critical")
        self.assertEqual(config.default_channel, "slack")
        self.assertEqual(config.cooldown_seconds, 600.0)
        self.assertEqual(config.max_escalations_per_hour, 5)

    def test_config_isolation(self):
        """Company A config does not affect company B."""
        custom_a = EscalationConfig(default_severity="critical")
        self.mgr.configure(COMPANY_ID, custom_a)

        config_b = self.mgr.get_config(COMPANY_ID_B)
        self.assertEqual(config_b.default_severity, "medium")

    def test_config_all_fields(self):
        """All EscalationConfig fields are accessible."""
        config = EscalationConfig(
            company_id="co",
            default_severity="high",
            default_channel="email",
            max_active_escalations=10,
            cooldown_seconds=120.0,
            auto_resolve_after_seconds=1800.0,
            enable_rate_limiting=False,
            max_escalations_per_hour=5,
            vip_multiplier=0.5,
            on_call_enabled=True,
            on_call_webhook_url="https://example.com",
        )
        self.assertEqual(config.company_id, "co")
        self.assertEqual(config.default_severity, "high")
        self.assertEqual(config.default_channel, "email")
        self.assertEqual(config.max_active_escalations, 10)
        self.assertEqual(config.cooldown_seconds, 120.0)
        self.assertEqual(config.auto_resolve_after_seconds, 1800.0)
        self.assertFalse(config.enable_rate_limiting)
        self.assertEqual(config.max_escalations_per_hour, 5)
        self.assertEqual(config.vip_multiplier, 0.5)
        self.assertTrue(config.on_call_enabled)
        self.assertEqual(config.on_call_webhook_url, "https://example.com")


class TestRuleManagement(unittest.TestCase):
    """Test rule CRUD (6 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_default_rules_loaded(self):
        """10 default rules exist after initialization."""
        rules = self.mgr.get_rules(COMPANY_ID)
        self.assertEqual(len(rules), 10)

    def test_add_rule(self):
        """Adds a custom rule that appears in get_rules."""
        custom = EscalationRule(
            name="custom_rule",
            trigger="manual_request",
            severity="low",
            condition={},
            channel="email",
            priority=5,
        )
        self.mgr.add_rule(custom)
        rules = self.mgr.get_rules(COMPANY_ID)
        names = [r.name for r in rules]
        self.assertIn("custom_rule", names)

    def test_add_rule_replaces(self):
        """Same name overwrites existing rule."""
        original = EscalationRule(
            name="high_frustration",
            trigger="high_frustration",
            severity="high",
            condition={"frustration_threshold": 80},
            channel="in_app",
            priority=2,
        )
        replacement = EscalationRule(
            name="high_frustration",
            trigger="high_frustration",
            severity="critical",
            condition={"frustration_threshold": 50},
            channel="slack",
            priority=0,
        )
        self.mgr.add_rule(original)
        self.mgr.add_rule(replacement)
        rules = self.mgr.get_rules(COMPANY_ID)
        matched = [r for r in rules if r.name == "high_frustration"]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].severity, "critical")
        self.assertEqual(matched[0].priority, 0)

    def test_remove_rule(self):
        """Removes an existing rule."""
        self.mgr.remove_rule("high_frustration")
        rules = self.mgr.get_rules(COMPANY_ID)
        names = [r.name for r in rules]
        self.assertNotIn("high_frustration", names)

    def test_remove_nonexistent_rule(self):
        """Removing a nonexistent rule is handled gracefully."""
        self.mgr.remove_rule("does_not_exist")
        rules = self.mgr.get_rules(COMPANY_ID)
        self.assertEqual(len(rules), 10)

    def test_get_rules_returns_enabled(self):
        """Only enabled rules are returned."""
        disabled = EscalationRule(
            name="disabled_rule",
            trigger="manual_request",
            severity="low",
            condition={},
            channel="email",
            enabled=False,
        )
        self.mgr.add_rule(disabled)
        rules = self.mgr.get_rules(COMPANY_ID)
        names = [r.name for r in rules]
        self.assertNotIn("disabled_rule", names)


class TestEvaluateEscalation(unittest.TestCase):
    """Test escalation evaluation (10 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_high_frustration_triggers(self):
        """frustration_score >= 80 triggers escalation."""
        ctx = _make_context(
            trigger="high_frustration",
            frustration_score=85.0,
        )
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)
        self.assertTrue(len(matched) > 0)
        self.assertEqual(matched[0].name, "high_frustration")

    def test_legal_sensitive_triggers(self):
        """trigger=legal_sensitive always triggers."""
        ctx = _make_context(trigger="legal_sensitive")
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)

    def test_multiple_failures_triggers(self):
        """failure_count >= 3 triggers escalation."""
        ctx = _make_context(
            trigger="multiple_failures",
            failure_count=3,
        )
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)

    def test_no_trigger_when_below_threshold(self):
        """frustration < 80 doesn't trigger frustration rule."""
        ctx = _make_context(
            trigger="high_frustration",
            frustration_score=50.0,
        )
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertFalse(should)

    def test_confidence_low_with_min_turns(self):
        """confidence < 0.3 with enough turns triggers escalation."""
        ctx = _make_context(
            trigger="confidence_low",
            confidence_score=0.2,
            conversation_turns=10,
        )
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)

    def test_confidence_low_without_enough_turns(self):
        """confidence < 0.3 but few turns does not trigger."""
        ctx = _make_context(
            trigger="confidence_low",
            confidence_score=0.1,
            conversation_turns=2,
        )
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertFalse(should)

    def test_vip_customer_triggers(self):
        """customer_tier=vip triggers vip_customer rule."""
        ctx = _make_context(
            trigger="vip_customer",
            customer_tier="vip",
        )
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)

    def test_loop_detected_triggers(self):
        """trigger=loop_detected triggers escalation."""
        ctx = _make_context(trigger="loop_detected")
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)

    def test_timeout_triggers(self):
        """trigger=timeout triggers escalation."""
        ctx = _make_context(trigger="timeout")
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)

    def test_capacity_overflow_triggers(self):
        """trigger=capacity_overflow triggers escalation."""
        ctx = _make_context(trigger="capacity_overflow")
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)

    def test_multiple_rules_match(self):
        """When multiple rules could match the same trigger, the matched list contains them."""
        # Add a second rule for legal_sensitive
        extra = EscalationRule(
            name="legal_sensitive_extra",
            trigger="legal_sensitive",
            severity="critical",
            condition={},
            channel="pagerduty",
            priority=0,
        )
        self.mgr.add_rule(extra)
        ctx = _make_context(trigger="legal_sensitive")
        should, matched, severity = self.mgr.evaluate_escalation(COMPANY_ID, ctx)
        self.assertTrue(should)
        self.assertGreaterEqual(len(matched), 1)
        self.assertEqual(severity, "critical")


class TestCreateEscalation(unittest.TestCase):
    """Test escalation creation (7 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_create_returns_record(self):
        """Returns EscalationRecord with a valid escalation ID."""
        ctx = _make_context(trigger="legal_sensitive")
        record = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(record)
        self.assertIsInstance(record, EscalationRecord)
        self.assertTrue(record.escalation_id.startswith("esc_"))

    def test_create_sets_pending_status(self):
        """Newly created escalation has status='pending'."""
        ctx = _make_context(trigger="legal_sensitive")
        record = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "pending")

    def test_create_sets_cooldown(self):
        """Cooldown is set after escalation creation."""
        ctx = _make_context(trigger="legal_sensitive")
        self.assertFalse(
            self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "legal_sensitive")
        )
        record = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(record)
        self.assertTrue(
            self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "legal_sensitive")
        )

    def test_create_with_channel_override(self):
        """Uses the channel_override when provided."""
        ctx = _make_context(trigger="legal_sensitive")
        record = self.mgr.create_escalation(COMPANY_ID, ctx, channel_override="sms")
        self.assertIsNotNone(record)
        self.assertEqual(record.channel, "sms")

    def test_create_rate_limited(self):
        """Exceeding max_active_escalations returns None."""
        config = EscalationConfig(
            max_active_escalations=2,
            enable_rate_limiting=True,
        )
        self.mgr.configure(COMPANY_ID, config)

        ctx = _make_context(trigger="legal_sensitive")
        r1 = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(r1)

        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        r2 = self.mgr.create_escalation(COMPANY_ID, ctx2)
        self.assertIsNotNone(r2)

        # Third one should be blocked by max_active_escalations
        ctx3 = _make_context(ticket_id="ticket_003", trigger="loop_detected")
        r3 = self.mgr.create_escalation(COMPANY_ID, ctx3)
        self.assertIsNone(r3)

    def test_create_on_cooldown(self):
        """Returns record even when on cooldown (create doesn't check cooldown, only evaluate does)."""
        ctx = _make_context(trigger="legal_sensitive")
        r1 = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(r1)
        # Cooldown is now active, but create_escalation does not block on
        # cooldown
        r2 = self.mgr.create_escalation(COMPANY_ID, ctx)
        # It should still create because legal_sensitive has cooldown_seconds=0
        self.assertIsNotNone(r2)

    def test_create_stores_context(self):
        """Context data is preserved in the record."""
        ctx = _make_context(
            trigger="legal_sensitive",
            frustration_score=42.0,
            customer_tier="enterprise",
        )
        record = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(record)
        self.assertEqual(record.context["frustration_score"], 42.0)
        self.assertEqual(record.context["customer_tier"], "enterprise")
        self.assertEqual(record.context["ticket_id"], TICKET_ID)


class TestEscalationLifecycle(unittest.TestCase):
    """Test acknowledge/resolve/dismiss/reassign (8 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()
        self.ctx = _make_context(trigger="legal_sensitive")
        self.record = self.mgr.create_escalation(COMPANY_ID, self.ctx)
        self.assertIsNotNone(self.record)

    def test_acknowledge_escalation(self):
        """Status becomes 'acknowledged' and acknowledged_at is set."""
        result = self.mgr.acknowledge_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            "agent_001",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "acknowledged")
        self.assertIsNotNone(result.acknowledged_at)

    def test_resolve_escalation(self):
        """Status becomes 'resolved' and resolved_at is set."""
        result = self.mgr.resolve_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            outcome="resolved",
            resolved_by="agent_001",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "resolved")
        self.assertIsNotNone(result.resolved_at)

    def test_dismiss_escalation(self):
        """Status becomes 'resolved' with outcome='dismissed'."""
        result = self.mgr.dismiss_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            reason="not needed",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "resolved")
        self.assertEqual(result.outcome, "dismissed")

    def test_reassign_escalation(self):
        """assigned_to is updated and status changes to 'in_progress'."""
        result = self.mgr.reassign_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            assigned_to="agent_002",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.assigned_to, "agent_002")
        self.assertEqual(result.status, "in_progress")

    def test_resolve_with_outcome(self):
        """Outcome is stored on the record."""
        result = self.mgr.resolve_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            outcome="human_took_over",
            resolved_by="agent_001",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.outcome, "human_took_over")

    def test_double_resolve_handled(self):
        """Second resolve returns record but does not change state."""
        r1 = self.mgr.resolve_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            outcome="resolved",
            resolved_by="agent_001",
        )
        r2 = self.mgr.resolve_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            outcome="expired",
            resolved_by="agent_002",
        )
        self.assertIsNotNone(r2)
        # Should keep original outcome since it was already resolved
        self.assertEqual(r2.outcome, "resolved")
        self.assertEqual(r2.resolved_by, "agent_001")

    def test_acknowledge_sets_user(self):
        """acknowledged_by stored as assigned_to."""
        result = self.mgr.acknowledge_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            "agent_005",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.assigned_to, "agent_005")

    def test_resolve_sets_user(self):
        """resolved_by stored on the record."""
        result = self.mgr.resolve_escalation(
            COMPANY_ID,
            self.record.escalation_id,
            outcome="resolved",
            resolved_by="agent_010",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.resolved_by, "agent_010")


class TestCooldownManagement(unittest.TestCase):
    """Test cooldown system (5 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_check_cooldown_inactive(self):
        """No cooldown returns False."""
        result = self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "legal_sensitive")
        self.assertFalse(result)

    def test_check_cooldown_active(self):
        """After escalation creation, cooldown is active."""
        ctx = _make_context(trigger="timeout")
        self.mgr.create_escalation(COMPANY_ID, ctx)
        result = self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "timeout")
        self.assertTrue(result)

    def test_set_cooldown_manual(self):
        """Manual cooldown can be set."""
        self.mgr.set_cooldown(COMPANY_ID, TICKET_ID, "manual_request", 0.05)
        result = self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "manual_request")
        self.assertTrue(result)

    def test_cooldown_expires(self):
        """After timeout, cooldown becomes inactive."""
        self.mgr.set_cooldown(COMPANY_ID, TICKET_ID, "test_trigger", 0.01)
        self.assertTrue(self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "test_trigger"))
        time.sleep(0.02)
        self.assertFalse(self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "test_trigger"))

    def test_vip_shorter_cooldown(self):
        """VIP gets a shorter cooldown (0.7x multiplier)."""
        config = EscalationConfig(
            cooldown_seconds=1.0,
            vip_multiplier=0.01,
        )
        self.mgr.configure(COMPANY_ID, config)

        ctx = _make_context(
            trigger="timeout",
            customer_tier="enterprise",
        )
        self.mgr.create_escalation(COMPANY_ID, ctx)

        # VIP cooldown = 1.0 * 0.01 = 0.01 seconds, should expire quickly
        time.sleep(0.02)
        result = self.mgr.check_cooldown(COMPANY_ID, TICKET_ID, "timeout")
        self.assertFalse(result)


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting (4 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_under_rate_limit(self):
        """Returns False when under limit (not limited)."""
        config = EscalationConfig(max_escalations_per_hour=20)
        self.mgr.configure(COMPANY_ID, config)
        result = self.mgr.check_rate_limit(COMPANY_ID)
        self.assertFalse(result)

    def test_at_rate_limit(self):
        """At max_per_hour returns True (limited)."""
        config = EscalationConfig(max_escalations_per_hour=1)
        self.mgr.configure(COMPANY_ID, config)

        # Inject a timestamp at the company_id key that check_rate_limit reads
        with self.mgr._lock:
            self.mgr._rate_limit_log[COMPANY_ID].append(time.time())
        result = self.mgr.check_rate_limit(COMPANY_ID)
        self.assertTrue(result)

    def test_rate_limit_window(self):
        """Old escalations outside the 1-hour window don't count."""
        config = EscalationConfig(max_escalations_per_hour=1)
        self.mgr.configure(COMPANY_ID, config)

        # Manually inject an old timestamp
        old_ts = time.time() - 3700.0
        with self.mgr._lock:
            self.mgr._rate_limit_log[COMPANY_ID].append(old_ts)

        result = self.mgr.check_rate_limit(COMPANY_ID)
        self.assertFalse(result)

    def test_rate_limit_disabled(self):
        """When enable_rate_limiting=False, always returns False."""
        config = EscalationConfig(
            max_escalations_per_hour=1,
            enable_rate_limiting=False,
        )
        self.mgr.configure(COMPANY_ID, config)

        ctx = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx)
        result = self.mgr.check_rate_limit(COMPANY_ID)
        self.assertFalse(result)


class TestQueryMethods(unittest.TestCase):
    """Test query methods (7 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_get_escalation(self):
        """Returns escalation record by ID."""
        ctx = _make_context(trigger="legal_sensitive")
        created = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(created)
        result = self.mgr.get_escalation(COMPANY_ID, created.escalation_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.escalation_id, created.escalation_id)

    def test_get_active_escalations(self):
        """Only non-resolved escalations are returned."""
        ctx1 = _make_context(trigger="legal_sensitive")
        r1 = self.mgr.create_escalation(COMPANY_ID, ctx1)
        self.assertIsNotNone(r1)

        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        r2 = self.mgr.create_escalation(COMPANY_ID, ctx2)
        self.assertIsNotNone(r2)

        self.mgr.resolve_escalation(
            COMPANY_ID,
            r1.escalation_id,
            "resolved",
            "agent_001",
        )

        active = self.mgr.get_active_escalations(COMPANY_ID)
        ids = [r.escalation_id for r in active]
        self.assertNotIn(r1.escalation_id, ids)
        self.assertIn(r2.escalation_id, ids)

    def test_get_ticket_escalations(self):
        """Filtered by ticket_id."""
        ctx1 = _make_context(trigger="legal_sensitive")
        r1 = self.mgr.create_escalation(COMPANY_ID, ctx1)
        self.assertIsNotNone(r1)

        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        r2 = self.mgr.create_escalation(COMPANY_ID, ctx2)
        self.assertIsNotNone(r2)

        ticket_esc = self.mgr.get_ticket_escalations(COMPANY_ID, TICKET_ID)
        ids = [r.escalation_id for r in ticket_esc]
        self.assertIn(r1.escalation_id, ids)
        self.assertNotIn(r2.escalation_id, ids)

    def test_get_escalations_by_severity(self):
        """Filtered by severity."""
        ctx_high = _make_context(trigger="legal_sensitive", severity="high")
        r1 = self.mgr.create_escalation(COMPANY_ID, ctx_high)
        self.assertIsNotNone(r1)

        ctx_med = _make_context(
            ticket_id=TICKET_ID_B, trigger="timeout", severity="medium"
        )
        r2 = self.mgr.create_escalation(COMPANY_ID, ctx_med)
        self.assertIsNotNone(r2)

        high_esc = self.mgr.get_escalations_by_severity(COMPANY_ID, "high")
        ids = [r.escalation_id for r in high_esc]
        self.assertIn(r1.escalation_id, ids)
        self.assertNotIn(r2.escalation_id, ids)

    def test_empty_queries(self):
        """Returns empty list when no escalations exist."""
        active = self.mgr.get_active_escalations(COMPANY_ID)
        self.assertEqual(active, [])

        ticket_esc = self.mgr.get_ticket_escalations(COMPANY_ID, TICKET_ID)
        self.assertEqual(ticket_esc, [])

        sev_esc = self.mgr.get_escalations_by_severity(COMPANY_ID, "high")
        self.assertEqual(sev_esc, [])

    def test_resolved_not_active(self):
        """Resolved escalation not in active list."""
        ctx = _make_context(trigger="legal_sensitive")
        r = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(r)

        self.assertEqual(len(self.mgr.get_active_escalations(COMPANY_ID)), 1)

        self.mgr.resolve_escalation(
            COMPANY_ID,
            r.escalation_id,
            "resolved",
            "agent_001",
        )
        self.assertEqual(len(self.mgr.get_active_escalations(COMPANY_ID)), 0)

    def test_get_nonexistent(self):
        """Returns None for nonexistent escalation ID."""
        result = self.mgr.get_escalation(COMPANY_ID, "nonexistent_id")
        self.assertIsNone(result)


class TestAutoResolution(unittest.TestCase):
    """Test auto-resolve stale (4 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_auto_resolve_expired(self):
        """Escalations past auto_resolve_after_seconds are resolved."""
        config = EscalationConfig(auto_resolve_after_seconds=0.01)
        self.mgr.configure(COMPANY_ID, config)

        ctx = _make_context(trigger="legal_sensitive")
        r = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(r)

        time.sleep(0.02)
        count = self.mgr.auto_resolve_stale(COMPANY_ID)
        self.assertGreaterEqual(count, 1)

        result = self.mgr.get_escalation(COMPANY_ID, r.escalation_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "resolved")

    def test_auto_resolve_preserves_fresh(self):
        """Fresh escalations are not resolved."""
        config = EscalationConfig(auto_resolve_after_seconds=3600.0)
        self.mgr.configure(COMPANY_ID, config)

        ctx = _make_context(trigger="legal_sensitive")
        r = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(r)

        count = self.mgr.auto_resolve_stale(COMPANY_ID)
        self.assertEqual(count, 0)

        result = self.mgr.get_escalation(COMPANY_ID, r.escalation_id)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "pending")

    def test_auto_resolve_with_custom_config(self):
        """Short auto_resolve time leads to auto-resolution."""
        config = EscalationConfig(auto_resolve_after_seconds=0.005)
        self.mgr.configure(COMPANY_ID, config)

        ctx = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx)

        time.sleep(0.01)
        count = self.mgr.auto_resolve_stale(COMPANY_ID)
        self.assertGreaterEqual(count, 1)

    def test_auto_resolve_returns_count(self):
        """Returns number of escalations resolved."""
        config = EscalationConfig(auto_resolve_after_seconds=0.01)
        self.mgr.configure(COMPANY_ID, config)

        ctx1 = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx1)

        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        self.mgr.create_escalation(COMPANY_ID, ctx2)

        time.sleep(0.02)
        count = self.mgr.auto_resolve_stale(COMPANY_ID)
        self.assertEqual(count, 2)


class TestEscalationMessage(unittest.TestCase):
    """Test message building (3 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()
        self.ctx = _make_context(
            trigger="legal_sensitive",
            severity="high",
            description="Legal inquiry detected",
        )
        self.record = self.mgr.create_escalation(COMPANY_ID, self.ctx)
        self.assertIsNotNone(self.record)

    def test_build_message_basic(self):
        """Returns a string with key escalation info."""
        msg = self.mgr.build_escalation_message(COMPANY_ID, self.record)
        self.assertIsInstance(msg, str)
        self.assertIn(self.record.escalation_id, msg)
        self.assertIn(TICKET_ID, msg)

    def test_build_message_includes_severity(self):
        """Severity level appears in the message."""
        msg = self.mgr.build_escalation_message(COMPANY_ID, self.record)
        self.assertIn("HIGH", msg)

    def test_build_message_includes_trigger(self):
        """Trigger name appears in the message."""
        msg = self.mgr.build_escalation_message(COMPANY_ID, self.record)
        self.assertIn("Legal Sensitive", msg)


class TestEscalationEvents(unittest.TestCase):
    """Test event listeners (4 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_add_listener(self):
        """Callback is invoked on escalation creation."""
        events = []
        self.mgr.add_event_listener(lambda name, data: events.append((name, data)))
        ctx = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "escalation_created")
        self.assertEqual(events[0][1]["company_id"], COMPANY_ID)

    def test_remove_listener(self):
        """Removed listener stops receiving events."""
        events = []

        def callback(name, data):
            return events.append((name, data))

        self.mgr.add_event_listener(callback)
        ctx = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertEqual(len(events), 1)

        self.mgr.remove_event_listener(callback)
        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        self.mgr.create_escalation(COMPANY_ID, ctx2)
        self.assertEqual(len(events), 1)

    def test_listener_error_safe(self):
        """Bad listener does not crash the manager."""

        def bad_listener(name, data):
            raise RuntimeError("listener error")

        good_events = []
        self.mgr.add_event_listener(bad_listener)
        self.mgr.add_event_listener(lambda n, d: good_events.append(n))

        ctx = _make_context(trigger="legal_sensitive")
        record = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(record)
        self.assertEqual(len(good_events), 1)

    def test_events_on_create_and_resolve(self):
        """Both create and resolve emit events."""
        events = []
        self.mgr.add_event_listener(lambda name, data: events.append(name))

        ctx = _make_context(trigger="legal_sensitive")
        record = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(record)

        self.mgr.resolve_escalation(
            COMPANY_ID,
            record.escalation_id,
            "resolved",
            "agent_001",
        )

        event_names = [e for e in events]
        self.assertIn("escalation_created", event_names)
        self.assertIn("escalation_resolved", event_names)


class TestEscalationStatistics(unittest.TestCase):
    """Test statistics (4 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_empty_stats(self):
        """Returns zeros when no escalations exist."""
        stats = self.mgr.get_statistics(COMPANY_ID)
        self.assertEqual(stats["total_escalations"], 0)
        self.assertEqual(stats["active_escalations"], 0)
        self.assertEqual(stats["resolved_escalations"], 0)
        self.assertEqual(stats["avg_resolution_time_seconds"], 0.0)

    def test_stats_with_escalations(self):
        """Counts reflect activity."""
        ctx1 = _make_context(trigger="legal_sensitive")
        r1 = self.mgr.create_escalation(COMPANY_ID, ctx1)
        self.assertIsNotNone(r1)

        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        r2 = self.mgr.create_escalation(COMPANY_ID, ctx2)
        self.assertIsNotNone(r2)

        self.mgr.resolve_escalation(
            COMPANY_ID,
            r1.escalation_id,
            "resolved",
            "agent_001",
        )

        stats = self.mgr.get_statistics(COMPANY_ID)
        self.assertEqual(stats["total_escalations"], 2)
        self.assertEqual(stats["active_escalations"], 1)
        self.assertEqual(stats["resolved_escalations"], 1)

    def test_stats_by_trigger(self):
        """Trigger breakdown present in statistics."""
        ctx = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx)
        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        self.mgr.create_escalation(COMPANY_ID, ctx2)

        stats = self.mgr.get_statistics(COMPANY_ID)
        by_trigger = stats["by_trigger"]
        self.assertIn("legal_sensitive", by_trigger)
        self.assertIn("timeout", by_trigger)
        self.assertEqual(by_trigger["legal_sensitive"], 1)
        self.assertEqual(by_trigger["timeout"], 1)

    def test_stats_by_severity(self):
        """Severity breakdown present in statistics."""
        ctx = _make_context(trigger="legal_sensitive", severity="high")
        self.mgr.create_escalation(COMPANY_ID, ctx)
        ctx2 = _make_context(
            ticket_id=TICKET_ID_B, trigger="timeout", severity="medium"
        )
        self.mgr.create_escalation(COMPANY_ID, ctx2)

        stats = self.mgr.get_statistics(COMPANY_ID)
        by_severity = stats["by_severity"]
        self.assertIn("high", by_severity)
        self.assertIn("medium", by_severity)


class TestNotificationLog(unittest.TestCase):
    """Test notification log (3 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_empty_log(self):
        """Returns empty list when no notifications dispatched."""
        log = self.mgr.get_notification_log(COMPANY_ID)
        self.assertEqual(log, [])

    def test_log_populated_on_create(self):
        """Entries appear after escalation creation."""
        ctx = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx)
        log = self.mgr.get_notification_log(COMPANY_ID)
        self.assertGreater(len(log), 0)
        self.assertEqual(log[0]["trigger"], "legal_sensitive")
        self.assertIn("escalation_id", log[0])

    def test_log_respects_limit(self):
        """Returns at most the requested number of entries."""
        ctx = _make_context(trigger="legal_sensitive")
        self.mgr.create_escalation(COMPANY_ID, ctx)

        ctx2 = _make_context(ticket_id=TICKET_ID_B, trigger="timeout")
        self.mgr.create_escalation(COMPANY_ID, ctx2)

        ctx3 = _make_context(ticket_id="ticket_003", trigger="loop_detected")
        self.mgr.create_escalation(COMPANY_ID, ctx3)

        log = self.mgr.get_notification_log(COMPANY_ID, limit=2)
        self.assertEqual(len(log), 2)


class TestEscalationCleanup(unittest.TestCase):
    """Test data cleanup (3 tests)."""

    def setUp(self):
        self.mgr = GracefulEscalationManager()

    def test_clear_company_data(self):
        """All data removed for the company."""
        ctx = _make_context(trigger="legal_sensitive")
        r = self.mgr.create_escalation(COMPANY_ID, ctx)
        self.assertIsNotNone(r)

        self.mgr.clear_company_data(COMPANY_ID)

        self.assertEqual(self.mgr.get_active_escalations(COMPANY_ID), [])
        self.assertIsNone(self.mgr.get_escalation(COMPANY_ID, r.escalation_id))
        self.assertEqual(self.mgr.get_notification_log(COMPANY_ID), [])

    def test_clear_isolation(self):
        """Other companies unaffected by clear."""
        ctx_a = _make_context(trigger="legal_sensitive")
        r_a = self.mgr.create_escalation(COMPANY_ID, ctx_a)
        self.assertIsNotNone(r_a)

        ctx_b = _make_context(
            company_id=COMPANY_ID_B,
            ticket_id=TICKET_ID_B,
            trigger="timeout",
        )
        r_b = self.mgr.create_escalation(COMPANY_ID_B, ctx_b)
        self.assertIsNotNone(r_b)

        self.mgr.clear_company_data(COMPANY_ID)

        # Company B data should remain
        active_b = self.mgr.get_active_escalations(COMPANY_ID_B)
        self.assertEqual(len(active_b), 1)
        self.assertIsNotNone(
            self.mgr.get_escalation(COMPANY_ID_B, r_b.escalation_id),
        )

    def test_clear_nonexistent(self):
        """Clearing data for nonexistent company handled gracefully."""
        self.mgr.clear_company_data("nonexistent_company")
        # No exception should be raised


class TestEnumValues(unittest.TestCase):
    """Test enum completeness (4 tests)."""

    def test_escalation_trigger_values(self):
        """12 trigger values defined."""
        self.assertEqual(len(EscalationTrigger), 12)
        expected = {
            "high_frustration",
            "legal_sensitive",
            "multiple_failures",
            "collision_conflict",
            "stale_session",
            "timeout",
            "confidence_low",
            "vip_customer",
            "manual_request",
            "loop_detected",
            "capacity_overflow",
            "partial_failure_critical",
        }
        actual = {t.value for t in EscalationTrigger}
        self.assertEqual(actual, expected)

    def test_escalation_severity_values(self):
        """4 severity levels defined."""
        self.assertEqual(len(EscalationSeverity), 4)
        expected = {"low", "medium", "high", "critical"}
        actual = {s.value for s in EscalationSeverity}
        self.assertEqual(actual, expected)

    def test_escalation_channel_values(self):
        """6 channel values defined."""
        self.assertEqual(len(EscalationChannel), 6)
        expected = {"in_app", "email", "webhook", "slack", "sms", "pagerduty"}
        actual = {c.value for c in EscalationChannel}
        self.assertEqual(actual, expected)

    def test_escalation_outcome_values(self):
        """6 outcome values defined."""
        self.assertEqual(len(EscalationOutcome), 6)
        expected = {
            "resolved",
            "human_took_over",
            "auto_resolved",
            "dismissed",
            "expired",
            "reassigned",
        }
        actual = {o.value for o in EscalationOutcome}
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
