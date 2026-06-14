"""
Tests for Self-Healing Engine (IC-12).

Validates that the SelfHealingEngine can be imported,
record_query_result doesn't crash, and healing rules are defined.
"""

import pytest

from app.core.self_healing_engine import (
    ActionType,
    ConditionType,
    HealingRule,
    SelfHealingEngine,
)


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def engine():
    """Create a fresh SelfHealingEngine instance."""
    return SelfHealingEngine()


# ── Import Tests ───────────────────────────────────────────────────


class TestSelfHealingEngineImport:
    """Test that SelfHealingEngine can be imported."""

    def test_engine_import(self):
        """SelfHealingEngine should be importable."""
        assert SelfHealingEngine is not None

    def test_engine_can_be_instantiated(self, engine):
        """SelfHealingEngine should be instantiable."""
        assert engine is not None

    def test_healing_rule_import(self):
        """HealingRule should be importable."""
        assert HealingRule is not None


# ── Record Query Result Tests ──────────────────────────────────────


class TestRecordQueryResult:
    """Test record_query_result doesn't crash."""

    def test_record_success_does_not_crash(self, engine):
        """Recording a successful query should not crash."""
        actions = engine.record_query_result(
            company_id="company-123",
            variant_type="parwa",
            provider="google",
            model_id="gemini-pro",
            tier="medium",
            confidence_score=90.0,
            latency_ms=500.0,
            error=None,
        )
        assert isinstance(actions, list)

    def test_record_failure_does_not_crash(self, engine):
        """Recording a failed query should not crash."""
        actions = engine.record_query_result(
            company_id="company-123",
            variant_type="parwa",
            provider="groq",
            model_id="llama3-70b",
            tier="medium",
            confidence_score=0.0,
            latency_ms=100.0,
            error="rate_limit_exceeded",
        )
        assert isinstance(actions, list)

    def test_record_with_rate_limit_error(self, engine):
        """Recording a rate limit error should not crash."""
        actions = engine.record_query_result(
            company_id="company-123",
            variant_type="parwa",
            provider="cerebras",
            model_id="llama3.3-70b",
            tier="light",
            confidence_score=0.0,
            latency_ms=50.0,
            error="rate_limit",
        )
        assert isinstance(actions, list)

    def test_record_multiple_times(self, engine):
        """Recording multiple results should not crash."""
        for i in range(10):
            actions = engine.record_query_result(
                company_id="company-123",
                variant_type="parwa",
                provider="google",
                model_id="gemini-pro",
                tier="medium",
                confidence_score=85.0 + i,
                latency_ms=500.0,
                error=None,
            )
        assert isinstance(actions, list)


# ── Healing Rules Tests ───────────────────────────────────────────


class TestHealingRules:
    """Test that healing rules are properly defined."""

    def test_rules_defined(self, engine):
        """Engine should have default healing rules defined."""
        rules = engine.get_rules("company-123")
        assert len(rules) > 0

    def test_rules_have_required_fields(self, engine):
        """Each rule should have required fields."""
        rules = engine.get_rules("company-123")
        for rule in rules:
            assert isinstance(rule, HealingRule)
            assert rule.rule_id
            assert rule.condition_type
            assert rule.action_type
            assert isinstance(rule.priority, int)
            assert isinstance(rule.enabled, bool)

    def test_consecutive_failures_rule_exists(self, engine):
        """A consecutive failures rule should exist."""
        rules = engine.get_rules("company-123")
        rule_ids = [r.rule_id for r in rules]
        assert "consecutive_failures_disable" in rule_ids

    def test_error_spike_rule_exists(self, engine):
        """An error spike rule should exist."""
        rules = engine.get_rules("company-123")
        rule_ids = [r.rule_id for r in rules]
        assert "error_spike_disable" in rule_ids

    def test_confidence_drop_rule_exists(self, engine):
        """A confidence drop rule should exist."""
        rules = engine.get_rules("company-123")
        rule_ids = [r.rule_id for r in rules]
        assert "confidence_drop_lower" in rule_ids

    def test_latency_spike_rule_exists(self, engine):
        """A latency spike rule should exist."""
        rules = engine.get_rules("company-123")
        rule_ids = [r.rule_id for r in rules]
        assert "latency_spike_switch" in rule_ids

    def test_rate_limit_rule_exists(self, engine):
        """A rate limit rule should exist."""
        rules = engine.get_rules("company-123")
        rule_ids = [r.rule_id for r in rules]
        assert "rate_limit_switch" in rule_ids

    def test_rules_have_valid_condition_types(self, engine):
        """Each rule should have a valid condition type."""
        rules = engine.get_rules("company-123")
        valid_conditions = {ct.value for ct in ConditionType}
        for rule in rules:
            assert rule.condition_type in valid_conditions, (
                f"Invalid condition_type: {rule.condition_type}"
            )

    def test_rules_have_valid_action_types(self, engine):
        """Each rule should have a valid action type."""
        rules = engine.get_rules("company-123")
        valid_actions = {at.value for at in ActionType}
        for rule in rules:
            assert rule.action_type in valid_actions, (
                f"Invalid action_type: {rule.action_type}"
            )


# ── BC-008 Compliance ─────────────────────────────────────────────


class TestSelfHealingBC008:
    """Test BC-008 compliance — never crash."""

    def test_get_healing_history_safe(self, engine):
        """get_healing_history should not crash on unknown company."""
        history = engine.get_healing_history("nonexistent-company")
        assert isinstance(history, list)

    def test_get_variant_health_safe(self, engine):
        """get_variant_health should not crash."""
        health = engine.get_variant_health("nonexistent-company")
        assert isinstance(health, list)

    def test_reset_safe(self, engine):
        """reset should not crash."""
        engine.reset()  # Should not raise
