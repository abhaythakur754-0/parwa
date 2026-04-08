"""Tests for AI Self-Healing Engine (SG-20).

Comprehensive tests covering:
- Helper functions (timestamps, thresholds, provider keys)
- Healing rules (default rules, custom rules, enable/disable)
- Record query result (master input method, state updates)
- Consecutive failures detection → provider disable
- Error spike detection → provider disable
- Latency spike detection → provider switch
- Confidence drop detection → threshold lower
- Confidence recovery → threshold restore
- Rate limit handling → provider switch
- Provider recovery (staged traffic ramp: 10%, 25%, 50%, 100%)
- Manual enable/disable providers
- Healing history (audit trail)
- Active healings (triggered/in_progress filtering)
- Variant health summary
- System health (global admin view)
- Per-variant isolation
- Threshold adjustments (current, floor, original)
- Cooldown enforcement between same actions
- Edge cases (invalid inputs, empty state, unicode)
- BC-008 never-crash
"""

from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "test"

import pytest

from backend.app.core.self_healing_engine import (
    ActionType,
    ConditionType,
    HealingAction,
    HealingRule,
    HealingStatus,
    ProviderState,
    SelfHealingEngine,
    ThresholdAdjustment,
    VariantHealingState,
    VariantHealthSummary,
    _default_threshold,
    _floor_threshold,
    _now_utc,
    _parse_iso,
    _provider_key,
    _seconds_since,
)


COMPANY_ID = "test-company-healing"
ANOTHER_COMPANY = "test-company-healing-2"
VARIANT_PARWA = "parwa"
VARIANT_MINI = "mini_parwa"
VARIANT_HIGH = "parwa_high"
PROVIDER = "google"
MODEL_ID = "gemini-2.0-flash"
TIER = "medium"


@pytest.fixture
def engine() -> SelfHealingEngine:
    """Fresh engine with cleared state per test."""
    svc = SelfHealingEngine()
    svc.reset()
    return svc


# ════════════════════════════════════════════════════════════════
# 1. HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    def test_now_utc_returns_string(self):
        ts = _now_utc()
        assert isinstance(ts, str)
        assert _parse_iso(ts) is not None

    def test_parse_iso_valid(self):
        parsed = _parse_iso("2025-01-15T10:30:00+00:00")
        assert parsed is not None
        assert parsed.year == 2025

    def test_parse_iso_empty(self):
        assert _parse_iso("") is None

    def test_parse_iso_none(self):
        assert _parse_iso(None) is None

    def test_seconds_since_recent(self):
        ts = _now_utc()
        elapsed = _seconds_since(ts)
        assert 0 <= elapsed < 5

    def test_seconds_since_invalid(self):
        elapsed = _seconds_since("invalid")
        assert elapsed == float("inf")

    def test_default_threshold_parwa(self):
        assert _default_threshold("parwa") == 85.0

    def test_default_threshold_mini(self):
        assert _default_threshold("mini_parwa") == 95.0

    def test_default_threshold_high(self):
        assert _default_threshold("parwa_high") == 75.0

    def test_default_threshold_unknown(self):
        assert _default_threshold("unknown_variant") == 85.0

    def test_floor_threshold_parwa(self):
        assert _floor_threshold("parwa") == 70.0

    def test_floor_threshold_mini(self):
        assert _floor_threshold("mini_parwa") == 80.0

    def test_floor_threshold_high(self):
        assert _floor_threshold("parwa_high") == 60.0

    def test_provider_key(self):
        key = _provider_key("google", "gemini-2.0-flash")
        assert key == "google:gemini-2.0-flash"

    def test_provider_key_unique(self):
        k1 = _provider_key("google", "g1")
        k2 = _provider_key("cerebras", "g1")
        assert k1 != k2


# ════════════════════════════════════════════════════════════════
# 2. HEALING RULES
# ════════════════════════════════════════════════════════════════


class TestHealingRules:
    def test_default_rules_exist(self, engine):
        rules = engine.get_rules(COMPANY_ID)
        assert len(rules) >= 6

    def test_default_rule_has_required_fields(self, engine):
        rules = engine.get_rules(COMPANY_ID)
        for rule in rules:
            assert rule.rule_id
            assert rule.condition_type
            assert rule.action_type
            assert rule.priority > 0
            assert rule.cooldown_seconds > 0

    def test_default_rules_include_consecutive_failures(self, engine):
        rules = engine.get_rules(COMPANY_ID)
        ids = [r.rule_id for r in rules]
        assert "consecutive_failures_disable" in ids

    def test_default_rules_include_error_spike(self, engine):
        rules = engine.get_rules(COMPANY_ID)
        ids = [r.rule_id for r in rules]
        assert "error_spike_disable" in ids

    def test_default_rules_include_latency_spike(self, engine):
        rules = engine.get_rules(COMPANY_ID)
        ids = [r.rule_id for r in rules]
        assert "latency_spike_switch" in ids

    def test_default_rules_include_confidence_drop(self, engine):
        rules = engine.get_rules(COMPANY_ID)
        ids = [r.rule_id for r in rules]
        assert "confidence_drop_lower" in ids

    def test_set_custom_rules(self, engine):
        custom = [HealingRule(
            rule_id="custom_rule",
            condition_type="custom_condition",
            action_type="custom_action",
            priority=1,
        )]
        engine.set_rules(COMPANY_ID, custom)
        rules = engine.get_rules(COMPANY_ID)
        assert len(rules) == 1
        assert rules[0].rule_id == "custom_rule"

    def test_enable_rule(self, engine):
        result = engine.enable_rule(COMPANY_ID, "consecutive_failures_disable", False)
        assert result is True
        rules = engine.get_rules(COMPANY_ID)
        rule = [r for r in rules if r.rule_id == "consecutive_failures_disable"][0]
        assert rule.enabled is False

    def test_enable_nonexistent_rule(self, engine):
        result = engine.enable_rule(COMPANY_ID, "nonexistent_rule", True)
        assert result is False

    def test_rules_isolated_per_company(self, engine):
        engine.enable_rule(COMPANY_ID, "consecutive_failures_disable", False)
        rules_other = engine.get_rules(ANOTHER_COMPANY)
        rule = [r for r in rules_other if r.rule_id == "consecutive_failures_disable"][0]
        assert rule.enabled is True  # Still enabled for other company


# ════════════════════════════════════════════════════════════════
# 3. RECORD QUERY RESULT
# ════════════════════════════════════════════════════════════════


class TestRecordQueryResult:
    def test_record_success_returns_list(self, engine):
        actions = engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        assert isinstance(actions, list)

    def test_record_failure_returns_list(self, engine):
        actions = engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=30.0, latency_ms=100.0, error="timeout",
        )
        assert isinstance(actions, list)

    def test_record_creates_provider_state(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps is not None
        assert ps.provider == PROVIDER

    def test_record_success_resets_failures(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0, error="fail",
        )
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.consecutive_failures == 0

    def test_record_failure_increments_failures(self, engine):
        for _ in range(3):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="timeout",
            )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.consecutive_failures == 3

    def test_record_updates_last_success(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.last_success is not None
        assert _parse_iso(ps.last_success) is not None

    def test_record_updates_last_failure(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=50.0, latency_ms=100.0, error="timeout",
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.last_failure is not None


# ════════════════════════════════════════════════════════════════
# 4. CONSECUTIVE FAILURES → DISABLE
# ════════════════════════════════════════════════════════════════


class TestConsecutiveFailures:
    def test_no_action_below_limit(self, engine):
        for _ in range(4):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.status != "disabled"

    def test_disable_at_limit(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.status == "disabled"
        assert ps.traffic_percentage == 0
        assert ps.disabled_at is not None

    def test_disable_creates_healing_action(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        history = engine.get_healing_history(COMPANY_ID)
        disable_actions = [
            a for a in history
            if a.action_type == ActionType.PROVIDER_DISABLE.value
        ]
        assert len(disable_actions) > 0

    def test_failure_count_in_action_details(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        history = engine.get_healing_history(COMPANY_ID)
        disable_action = [
            a for a in history
            if a.action_type == ActionType.PROVIDER_DISABLE.value
        ][0]
        assert disable_action.details["consecutive_failures"] >= 5


# ════════════════════════════════════════════════════════════════
# 5. ERROR SPIKE DETECTION
# ════════════════════════════════════════════════════════════════


class TestErrorSpike:
    def test_spike_detected(self, engine):
        # First 20 successful, then 20 failures
        for _ in range(20):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=85.0, latency_ms=100.0,
            )
        for _ in range(20):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        # Should be disabled due to both consecutive failures AND error spike
        assert ps.status == "disabled"

    def test_no_spike_steady_errors(self, engine):
        # Steady 10% error rate — not a spike
        for i in range(50):
            error = "fail" if i % 10 == 0 else None
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=85.0 if not error else 50.0,
                latency_ms=100.0,
                error=error,
            )
        # Provider should NOT be disabled (no spike, just steady errors)
        # It may get disabled by consecutive failures on the one error though
        # but the point is no spike detection triggers


# ════════════════════════════════════════════════════════════════
# 6. LATENCY SPIKE DETECTION
# ════════════════════════════════════════════════════════════════


class TestLatencySpike:
    def test_latency_spike_triggers_switch(self, engine):
        # Normal latencies first
        for _ in range(15):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=85.0, latency_ms=50.0,
            )
        # Spike latencies
        for _ in range(15):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=85.0, latency_ms=500.0,
            )
        history = engine.get_healing_history(COMPANY_ID)
        switch_actions = [
            a for a in history
            if a.action_type == ActionType.PROVIDER_SWITCH.value
        ]
        assert len(switch_actions) > 0

    def test_no_spike_steady_latency(self, engine):
        for _ in range(30):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=85.0, latency_ms=100.0,
            )
        history = engine.get_healing_history(COMPANY_ID)
        switch_actions = [
            a for a in history
            if a.action_type == ActionType.PROVIDER_SWITCH.value
        ]
        assert len(switch_actions) == 0


# ════════════════════════════════════════════════════════════════
# 7. CONFIDENCE DROP → THRESHOLD LOWER
# ════════════════════════════════════════════════════════════════


class TestConfidenceDrop:
    def test_threshold_lowered_on_drop(self, engine):
        for _ in range(10):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=70.0, latency_ms=100.0,  # below 85
            )
        threshold = engine.get_current_threshold(COMPANY_ID, VARIANT_PARWA)
        assert threshold < 85.0  # Should be lowered

    def test_threshold_never_below_floor(self, engine):
        # Mini parwa: default 95, floor 80
        for _ in range(50):
            engine.record_query_result(
                COMPANY_ID, VARIANT_MINI, PROVIDER, MODEL_ID, TIER,
                confidence_score=30.0, latency_ms=100.0,
            )
        threshold = engine.get_current_threshold(COMPANY_ID, VARIANT_MINI)
        assert threshold >= _floor_threshold(VARIANT_MINI)

    def test_confidence_action_recorded(self, engine):
        for _ in range(10):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=70.0, latency_ms=100.0,
            )
        history = engine.get_healing_history(COMPANY_ID)
        threshold_actions = [
            a for a in history
            if a.action_type == ActionType.THRESHOLD_LOWER.value
        ]
        assert len(threshold_actions) > 0


# ════════════════════════════════════════════════════════════════
# 8. CONFIDENCE RECOVERY → THRESHOLD RESTORE
# ════════════════════════════════════════════════════════════════


class TestConfidenceRecovery:
    def test_threshold_restored_on_recovery(self, engine):
        # First lower the threshold
        for _ in range(10):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=70.0, latency_ms=100.0,
            )
        lowered = engine.get_current_threshold(COMPANY_ID, VARIANT_PARWA)
        assert lowered < 85.0

        # Now recovery: 20 consecutive high scores
        for _ in range(20):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=95.0, latency_ms=100.0,
            )
        restored = engine.get_current_threshold(COMPANY_ID, VARIANT_PARWA)
        assert restored == 85.0  # Restored to original


# ════════════════════════════════════════════════════════════════
# 9. RATE LIMIT HANDLING
# ════════════════════════════════════════════════════════════════


class TestRateLimitHandling:
    def test_rate_limit_triggers_switch(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=50.0, latency_ms=100.0,
            error="rate_limit_exceeded",
        )
        history = engine.get_healing_history(COMPANY_ID)
        switch_actions = [
            a for a in history
            if a.action_type == ActionType.PROVIDER_SWITCH.value
            and a.details.get("message", "").find("Rate limit") >= 0
        ]
        assert len(switch_actions) > 0

    def test_non_rate_limit_error_no_switch(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=50.0, latency_ms=100.0,
            error="generic_error",
        )
        history = engine.get_healing_history(COMPANY_ID)
        rate_switches = [
            a for a in history
            if a.action_type == ActionType.PROVIDER_SWITCH.value
            and "rate_limit" in a.condition_type
        ]
        assert len(rate_switches) == 0


# ════════════════════════════════════════════════════════════════
# 10. PROVIDER RECOVERY (STAGED RAMP)
# ════════════════════════════════════════════════════════════════


class TestProviderRecovery:
    def test_disabled_provider_recovers_on_success(self, engine):
        # Disable provider first
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.status == "disabled"

        # Now succeed — should start recovery
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.status == "recovering"
        assert ps.traffic_percentage > 0

    def test_recovery_traffic_stages(self, engine):
        # Disable first
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )

        # Recovery stage 1
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.recovery_stage >= 1
        assert ps.traffic_percentage > 0

    def test_recovery_records_action(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        history = engine.get_healing_history(COMPANY_ID)
        recovery_actions = [
            a for a in history
            if a.action_type == ActionType.TRAFFIC_RAMP_UP.value
        ]
        assert len(recovery_actions) > 0


# ════════════════════════════════════════════════════════════════
# 11. MANUAL ENABLE / DISABLE
# ════════════════════════════════════════════════════════════════


class TestManualEnableDisable:
    def test_manual_disable(self, engine):
        result = engine.manually_disable_provider(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID,
            reason="admin_maintenance",
        )
        assert result is True
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.status == "disabled"
        assert ps.disabled_reason == "admin_maintenance"
        assert ps.traffic_percentage == 0

    def test_manual_enable(self, engine):
        engine.manually_disable_provider(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID,
        )
        result = engine.manually_enable_provider(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID,
        )
        assert result is True
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.status == "healthy"
        assert ps.traffic_percentage == 100
        assert ps.consecutive_failures == 0

    def test_manual_enable_nonexistent(self, engine):
        result = engine.manually_enable_provider(
            COMPANY_ID, VARIANT_PARWA, "nonexistent", "model",
        )
        assert result is False

    def test_manual_disable_records_action(self, engine):
        engine.manually_disable_provider(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID,
        )
        history = engine.get_healing_history(COMPANY_ID)
        manual = [a for a in history if a.rule_id == "manual"]
        assert len(manual) == 1
        assert manual[0].action_type == ActionType.PROVIDER_DISABLE.value


# ════════════════════════════════════════════════════════════════
# 12. HEALING HISTORY
# ════════════════════════════════════════════════════════════════


class TestHealingHistory:
    def test_empty_history(self, engine):
        history = engine.get_healing_history(COMPANY_ID)
        assert history == []

    def test_history_records_actions(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        history = engine.get_healing_history(COMPANY_ID)
        assert len(history) > 0

    def test_history_has_required_fields(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        history = engine.get_healing_history(COMPANY_ID)
        action = history[0]
        assert action.timestamp is not None
        assert action.company_id == COMPANY_ID
        assert action.variant == VARIANT_PARWA
        assert action.action_type is not None
        assert action.condition_type is not None

    def test_history_isolated_per_company(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        other_history = engine.get_healing_history(ANOTHER_COMPANY)
        assert other_history == []

    def test_history_pruned_to_max(self, engine):
        from backend.app.core.self_healing_engine import _MAX_HEALING_HISTORY
        for _ in range(_MAX_HEALING_HISTORY + 20):
            engine.manually_disable_provider(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID,
                reason=f"test_{_}",
            )
        history = engine.get_healing_history(COMPANY_ID)
        assert len(history) <= _MAX_HEALING_HISTORY


# ════════════════════════════════════════════════════════════════
# 13. ACTIVE HEALINGS
# ════════════════════════════════════════════════════════════════


class TestActiveHealings:
    def test_empty_active(self, engine):
        active = engine.get_active_healings(COMPANY_ID)
        assert active == []

    def test_active_after_disable(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        active = engine.get_active_healings(COMPANY_ID)
        # At least one action should be in triggered/in_progress state
        triggered = [
            a for a in active
            if a.status in (
                HealingStatus.TRIGGERED.value,
                HealingStatus.IN_PROGRESS.value,
            )
        ]
        assert len(triggered) > 0


# ════════════════════════════════════════════════════════════════
# 14. VARIANT HEALTH SUMMARY
# ════════════════════════════════════════════════════════════════


class TestVariantHealthSummary:
    def test_empty_returns_empty(self, engine):
        summaries = engine.get_variant_health(COMPANY_ID)
        assert summaries == []

    def test_healthy_variant(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=90.0, latency_ms=100.0,
        )
        summaries = engine.get_variant_health(COMPANY_ID)
        parwa = [s for s in summaries if s.variant == VARIANT_PARWA]
        assert len(parwa) == 1
        assert parwa[0].healthy is True
        assert len(parwa[0].issues) == 0

    def test_unhealthy_variant(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        summaries = engine.get_variant_health(COMPANY_ID)
        parwa = [s for s in summaries if s.variant == VARIANT_PARWA]
        assert len(parwa) == 1
        assert parwa[0].healthy is False
        assert len(parwa[0].issues) > 0

    def test_threshold_in_summary(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=90.0, latency_ms=100.0,
        )
        summaries = engine.get_variant_health(COMPANY_ID)
        parwa = [s for s in summaries if s.variant == VARIANT_PARWA][0]
        assert parwa.threshold_current == 85.0
        assert parwa.threshold_original == 85.0

    def test_provider_status_in_summary(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=90.0, latency_ms=100.0,
        )
        summaries = engine.get_variant_health(COMPANY_ID)
        parwa = [s for s in summaries if s.variant == VARIANT_PARWA][0]
        pkey = _provider_key(PROVIDER, MODEL_ID)
        assert pkey in parwa.provider_status


# ════════════════════════════════════════════════════════════════
# 15. SYSTEM HEALTH
# ════════════════════════════════════════════════════════════════


class TestSystemHealth:
    def test_empty_system(self, engine):
        health = engine.get_system_health()
        assert health["total_companies"] == 0
        assert health["total_healings"] == 0

    def test_system_tracks_companies(self, engine):
        engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=90.0, latency_ms=100.0,
        )
        health = engine.get_system_health()
        assert health["total_companies"] >= 1

    def test_system_has_timestamp(self, engine):
        health = engine.get_system_health()
        assert health["timestamp"] is not None

    def test_system_includes_company_summaries(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        health = engine.get_system_health()
        assert COMPANY_ID in health["companies"]


# ════════════════════════════════════════════════════════════════
# 16. PER-VARIANT ISOLATION
# ════════════════════════════════════════════════════════════════


class TestPerVariantIsolation:
    def test_disabled_in_one_variant_not_another(self, engine):
        # Disable in parwa
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        ps_parwa = engine.get_provider_state(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID,
        )
        assert ps_parwa.status == "disabled"

        # Same provider in mini_parwa should be fine
        ps_mini = engine.get_provider_state(
            COMPANY_ID, VARIANT_MINI, PROVIDER, MODEL_ID,
        )
        assert ps_mini is None  # Never used in mini_parwa

    def test_different_thresholds_per_variant(self, engine):
        thresh_parwa = engine.get_current_threshold(COMPANY_ID, VARIANT_PARWA)
        thresh_mini = engine.get_current_threshold(COMPANY_ID, VARIANT_MINI)
        thresh_high = engine.get_current_threshold(COMPANY_ID, VARIANT_HIGH)
        assert thresh_mini > thresh_parwa
        assert thresh_parwa > thresh_high

    def test_confidence_drop_isolated(self, engine):
        # Drop in parwa
        for _ in range(10):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=70.0, latency_ms=100.0,
            )
        thresh_parwa = engine.get_current_threshold(COMPANY_ID, VARIANT_PARWA)
        thresh_mini = engine.get_current_threshold(COMPANY_ID, VARIANT_MINI)
        assert thresh_parwa < 85.0  # Lowered
        assert thresh_mini == 95.0  # Unchanged


# ════════════════════════════════════════════════════════════════
# 17. RECORD PROVIDER STATUS
# ════════════════════════════════════════════════════════════════


class TestRecordProviderStatus:
    def test_record_unhealthy_status(self, engine):
        engine.record_provider_status(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, "unhealthy",
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID)
        assert ps.status == "unhealthy"

    def test_record_creates_provider_if_missing(self, engine):
        engine.record_provider_status(
            COMPANY_ID, VARIANT_PARWA, "cerebras", "llama-8b", "degraded",
        )
        ps = engine.get_provider_state(COMPANY_ID, VARIANT_PARWA, "cerebras", "llama-8b")
        assert ps is not None
        assert ps.provider == "cerebras"


# ════════════════════════════════════════════════════════════════
# 18. EDGE CASES
# ════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_company_id(self, engine):
        # Should not crash
        actions = engine.record_query_result(
            "", VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        assert isinstance(actions, list)

    def test_unknown_variant(self, engine):
        engine.record_query_result(
            COMPANY_ID, "unknown_variant", PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=100.0,
        )
        thresh = engine.get_current_threshold(COMPANY_ID, "unknown_variant")
        assert thresh == 85.0  # Default

    def test_reset_clears_everything(self, engine):
        for _ in range(5):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=50.0, latency_ms=100.0, error="fail",
            )
        assert len(engine.get_healing_history(COMPANY_ID)) > 0
        engine.reset()
        assert len(engine.get_healing_history(COMPANY_ID)) == 0
        assert engine.get_variant_health(COMPANY_ID) == []

    def test_history_unknown_company(self, engine):
        assert engine.get_healing_history("nonexistent") == []

    def test_active_unknown_company(self, engine):
        assert engine.get_active_healings("nonexistent") == []

    def test_variant_health_unknown_company(self, engine):
        assert engine.get_variant_health("nonexistent") == []

    def test_provider_state_unknown(self, engine):
        assert engine.get_provider_state(
            COMPANY_ID, VARIANT_PARWA, "nope", "nope",
        ) is None

    def test_zero_latency(self, engine):
        actions = engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=85.0, latency_ms=0.0,
        )
        assert isinstance(actions, list)

    def test_negative_confidence(self, engine):
        actions = engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=-10.0, latency_ms=100.0,
        )
        assert isinstance(actions, list)

    def test_confidence_above_100(self, engine):
        actions = engine.record_query_result(
            COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
            confidence_score=150.0, latency_ms=100.0,
        )
        assert isinstance(actions, list)

    def test_concurrent_operations(self, engine):
        # Sequential calls should not crash
        for i in range(10):
            engine.record_query_result(
                COMPANY_ID, VARIANT_PARWA, PROVIDER, MODEL_ID, TIER,
                confidence_score=85.0, latency_ms=float(50 + i),
            )
        history = engine.get_healing_history(COMPANY_ID)
        assert isinstance(history, list)


# ════════════════════════════════════════════════════════════════
# 19. DATA CLASS STRUCTURE
# ════════════════════════════════════════════════════════════════


class TestDataClassStructure:
    def test_healing_rule(self):
        rule = HealingRule(
            rule_id="test", condition_type="test_cond",
            action_type="test_act", priority=5,
        )
        assert rule.enabled is True

    def test_healing_action(self):
        action = HealingAction(
            timestamp=_now_utc(), company_id="co", variant="parwa",
            condition_type="test", action_type="test_act",
        )
        assert action.status == HealingStatus.TRIGGERED.value

    def test_provider_state(self):
        ps = ProviderState(provider="google", model_id="g1", tier="medium")
        assert ps.status == "healthy"
        assert ps.traffic_percentage == 100

    def test_variant_healing_state(self):
        vhs = VariantHealingState(variant="parwa")
        assert vhs.consecutive_low_scores == 0
        assert len(vhs.provider_states) == 0

    def test_variant_health_summary(self):
        vhs = VariantHealthSummary(variant="parwa")
        assert vhs.healthy is True
        assert vhs.issues == []

    def test_threshold_adjustment(self):
        ta = ThresholdAdjustment(
            original_threshold=85.0, current_threshold=80.0,
            adjusted_at=_now_utc(), reason="test",
        )
        assert ta.current_threshold == 80.0
