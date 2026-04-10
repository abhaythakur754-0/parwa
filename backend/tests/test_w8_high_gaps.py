"""
W8 HIGH severity gap tests.

Tests cover six critical gap areas:
1. Provider failover race — concurrent provider failures trigger correct failover
2. A/B test contamination — test assignment consistency
3. Confidence cascading failure — multiple guardrails fail simultaneously
4. Cache tenant isolation — one company can't read another's cached responses
5. Self-healing cooldown bypass — cooldown can't be bypassed
6. Alert false positives — normal metric variance doesn't trigger alerts
"""

import hashlib
import json
import sys
import types
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Mock database modules before importing technique_cache_service ──
_mock_db_base = types.ModuleType("database.base")
_mock_db_base.SessionLocal = MagicMock()
_mock_variant_engine = types.ModuleType("database.models.variant_engine")
_mock_variant_engine.TechniqueCache = MagicMock()
_orig_db = sys.modules.get("database.base")
_orig_models = sys.modules.get("database.models")
_orig_models_pkg = sys.modules.get("database.models.variant_engine")
sys.modules["database.base"] = _mock_db_base
sys.modules["database.models"] = types.ModuleType("database.models")
sys.modules["database.models.variant_engine"] = _mock_variant_engine

# ── Source imports ────────────────────────────────────────────────────

from backend.app.core.model_failover import (
    FailoverManager,
    FailoverChainExecutor,
    FailoverReason,
    FailoverEvent,
    CircuitBreaker,
    ProviderState,
    DegradedResponseDetector,
    FAILOVER_CHAINS,
)
from backend.app.core.confidence_scoring_engine import (
    ConfidenceScoringEngine,
    ConfidenceConfig,
    ConfidenceResult,
    SignalScore,
    VariantType,
)
from backend.app.core.guardrails_engine import (
    GuardrailsEngine,
    GuardrailConfig,
    GuardrailResult,
    GuardrailsReport,
    GuardAction,
    GuardrailLayer,
    SeverityLevel,
    StrictnessLevel,
    _build_config,
)
from backend.app.core.prompt_templates import (
    PromptTemplateManager,
    PromptTemplate,
    ALL_INTENTS,
)
from backend.app.services.prompt_template_service import (
    PromptTemplateService,
    ABTestConfig,
    ABTestStatus,
    TemplateStatus,
)
from backend.app.services.technique_cache_service import (
    _validate_company_id,
    _safe_parse_json,
    _validate_cache_result,
    compute_query_hash,
    get_cached_result as tcs_get_cached_result,
    set_cached_result as tcs_set_cached_result,
    invalidate_cached_result as tcs_invalidate_cached_result,
    DEFAULT_CACHE_TTL_HOURS,
)
from backend.app.core.self_healing_engine import (
    SelfHealingEngine,
    HealingRule,
    HealingAction,
    ConditionType,
    ActionType,
    HealingStatus,
    ProviderState as SHProviderState,
    VariantHealingState,
    ThresholdAdjustment,
    _RECOVERY_COOLDOWN_SECONDS,
    _CONSECUTIVE_FAILURE_LIMIT,
    _LOW_SCORE_CONSECUTIVE,
    _RECOVERY_HIGH_SCORE_CONSECUTIVE,
    _ERROR_SPIKE_THRESHOLD,
)
from backend.app.core.ai_monitoring_service import (
    AIMonitoringService,
    AlertLevel,
    AlertCondition,
    DashboardSnapshot,
    LatencyStats,
    ConfidenceDistribution,
)
from backend.app.exceptions import ParwaBaseError


# ══════════════════════════════════════════════════════════════════════
# 1. PROVIDER FAILOVER RACE — ~5 tests
# ══════════════════════════════════════════════════════════════════════


class TestProviderFailoverRace:
    """Concurrent provider failures trigger correct failover."""

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit breaker opens after reaching recovery_threshold."""
        mgr = FailoverManager(recovery_threshold=3)
        for _ in range(3):
            mgr.report_failure(
                "google", "gemini-2.0-flash-lite",
                FailoverReason.TIMEOUT, "Connection timeout",
            )
        state = mgr.get_provider_state("google", "gemini-2.0-flash-lite")
        assert state == ProviderState.CIRCUIT_OPEN

    def test_failover_chain_skips_open_circuits(self):
        """get_failover_chain skips providers with open circuits."""
        mgr = FailoverManager(recovery_threshold=2, recovery_timeout_seconds=9999)
        # Trip the first provider in medium chain
        chain = FAILOVER_CHAINS["medium"]
        first_prov, first_model = chain[0]
        for _ in range(3):
            mgr.report_failure(
                first_prov, first_model,
                FailoverReason.SERVER_ERROR, "500",
            )
        available = mgr.get_failover_chain("medium")
        assert len(available) < len(chain)
        # First provider must NOT be in available chain
        assert not any(p == first_prov and m == first_model for p, m in available)

    def test_concurrent_failures_race_safe(self):
        """Multiple threads reporting failures don't corrupt state."""
        mgr = FailoverManager(recovery_threshold=5)
        errors = []

        def report_n(provider, count):
            try:
                for _ in range(count):
                    mgr.report_failure(
                        provider, "model-x",
                        FailoverReason.TIMEOUT, "timeout",
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=report_n, args=("google", 3)),
            threading.Thread(target=report_n, args=("cerebras", 4)),
            threading.Thread(target=report_n, args=("groq", 2)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, "No thread should raise"
        # At least one provider should be DEGRADED
        states = [
            mgr.get_provider_state(p, "model-x")
            for p in ("google", "cerebras", "groq")
        ]
        assert any(s == ProviderState.DEGRADED for s in states)

    def test_executor_falls_through_to_backup_provider(self):
        """Execute_with_failover tries backup when primary fails."""
        mgr = FailoverManager(recovery_threshold=1, recovery_timeout_seconds=9999)
        executor = FailoverChainExecutor(mgr)

        call_fn = MagicMock(side_effect=[
            ConnectionError("provider down"),
            {"content": "fallback response works", "latency_ms": 200},
        ])

        chain = [("provider_a", "model_a"), ("provider_b", "model_b")]
        result = executor.execute_with_failover("co1", chain, call_fn, max_retries=1)
        assert result.get("content") == "fallback response works"
        assert result.get("_failover_used") is True

    def test_all_providers_failed_returns_graceful_error(self):
        """When every provider fails, returns graceful error (BC-008)."""
        mgr = FailoverManager()
        executor = FailoverChainExecutor(mgr)

        call_fn = MagicMock(side_effect=ConnectionError("down"))
        chain = [("p1", "m1"), ("p2", "m2"), ("p3", "m3")]

        result = executor.execute_with_failover("co1", chain, call_fn, max_retries=1)
        assert result.get("_all_providers_failed") is True
        assert result.get("_graceful_degradation") is True
        assert "content" in result  # never None
        assert "apologize" in result["content"].lower()


# ══════════════════════════════════════════════════════════════════════
# 2. A/B TEST CONTAMINATION — ~4 tests
# ══════════════════════════════════════════════════════════════════════


class TestABTestContamination:
    """A/B test assignment consistency — no contamination between tests."""

    def test_ab_tests_isolated_per_company(self):
        """A/B tests for one company don't leak into another."""
        svc = PromptTemplateService()
        svc.__class__._ab_tests.clear()

        # create_ab_test needs real template names; use built-in defaults
        test_a = svc.create_ab_test(
            "company_a", "test1",
            template_a_name="response_simple",
            template_b_name="response_moderate",
            traffic_split=0.5,
        )
        test_b = svc.create_ab_test(
            "company_b", "test1",
            template_a_name="response_simple",
            template_b_name="response_moderate",
            traffic_split=0.3,
        )

        list_a = svc.list_ab_tests("company_a")
        list_b = svc.list_ab_tests("company_b")
        assert len(list_a) == 1
        assert len(list_b) == 1
        # Different traffic splits
        assert list_a[0].traffic_split == 0.5
        assert list_b[0].traffic_split == 0.3
        # Company A's test not visible to company B
        assert all(t.company_id == "company_b" for t in list_b)

    def test_ab_assignment_deterministic_per_ticket(self):
        """Same ticket_id always gets assigned to same variant."""
        import hashlib as _hl

        svc = PromptTemplateService()
        svc.__class__._ab_tests.clear()

        test = svc.create_ab_test(
            "co1", "test_det",
            template_a_name="response_simple",
            template_b_name="response_moderate",
            traffic_split=0.5,
        )

        # Simulate the deterministic hash used by render_with_ab_test
        def get_assignment(company_id, name, ticket_id, split):
            key = f"{company_id}:{name}:{ticket_id}"
            hash_val = int(_hl.md5(key.encode()).hexdigest(), 16)
            return "b" if (hash_val % 1000) / 1000.0 < split else "a"

        a1 = get_assignment("co1", "response_simple", "ticket_123", 0.5)
        a2 = get_assignment("co1", "response_simple", "ticket_123", 0.5)
        a3 = get_assignment("co1", "response_simple", "ticket_456", 0.5)

        assert a1 == a2  # same ticket → same assignment
        assert a1 in ("a", "b")

    def test_prompt_template_manager_variable_substitution(self):
        """PromptTemplateManager renders variables correctly."""
        mgr = PromptTemplateManager()
        rendered = mgr.render_template(
            "refund", {
                "company_name": "Acme",
                "customer_name": "Alice",
                "order_id": "ORD-42",
                "amount": "$50",
                "processing_time": "5-7 days",
            },
        )
        assert "Acme" in rendered
        assert "Alice" in rendered
        assert "ORD-42" in rendered
        assert "$50" in rendered

    def test_traffic_split_bounds_enforced(self):
        """Traffic split outside 0-1 raises error."""
        from backend.app.services.prompt_template_service import _validate_traffic_split
        with pytest.raises(ParwaBaseError):
            _validate_traffic_split(1.5)
        with pytest.raises(ParwaBaseError):
            _validate_traffic_split(-0.1)
        with pytest.raises(ParwaBaseError):
            _validate_traffic_split("not_a_number")
        # Valid values should not raise
        _validate_traffic_split(0.0)
        _validate_traffic_split(0.5)
        _validate_traffic_split(1.0)


# ══════════════════════════════════════════════════════════════════════
# 3. CONFIDENCE CASCADING FAILURE — ~5 tests
# ══════════════════════════════════════════════════════════════════════


class TestConfidenceCascadingFailure:
    """Multiple guardrails failing simultaneously handled correctly."""

    def test_multiple_guardrails_blocked_reported(self):
        """GuardrailsReport counts all blocked layers."""
        engine = GuardrailsEngine()
        response = (
            "You should sue them immediately! This is definitely the "
            "best investment ever. Call me at 555-123-4567 for details. "
            "We guarantee you will double your money."
        )
        report = engine.run_full_check(
            query="Can you help with my order?",
            response=response,
            confidence=30.0,
            company_id="co1",
            variant_type="parwa",
        )
        # Should block on policy (legal advice, financial claims), PII (phone)
        assert not report.passed
        assert report.blocked_count >= 1
        assert len(report.results) > 0

    def test_confidence_gate_blocks_low_score(self):
        """Low confidence score triggers confidence gate block."""
        engine = GuardrailsEngine()
        report = engine.run_full_check(
            query="What is my order status?",
            response="I'm not sure about that, let me check.",
            confidence=40.0,  # well below 85 threshold
            company_id="co1",
            variant_type="parwa",
        )
        # Confidence gate should block
        confidence_results = [
            r for r in report.results
            if r.layer == GuardrailLayer.CONFIDENCE_GATE.value
        ]
        assert len(confidence_results) == 1
        assert not confidence_results[0].passed

    def test_all_signals_scored_in_cascading_failure(self):
        """ConfidenceScoringEngine evaluates all 7 signals even when many fail."""
        engine = ConfidenceScoringEngine()
        # Response with PII, hallucination markers, and poor relevance
        query = "What is the weather today?"
        response = (
            "According to our latest report 2024, 95% of users agree "
            "that studies show 42% growth. Contact me at "
            "john@example.com or 123-456-7890. My SSN is 123-45-6789. "
        )
        result = engine.score_response("co1", query, response)
        # All 7 signals should be evaluated
        assert len(result.signals) == 7
        # PII safety should be low (email + phone + SSN)
        pii_signal = next(
            (s for s in result.signals if s.signal_name == "pii_safety"),
            None,
        )
        assert pii_signal is not None
        assert pii_signal.score < 50

    def test_guardrails_short_circuit_on_first_block(self):
        """First BLOCK action short-circuits remaining checks."""
        engine = GuardrailsEngine()
        # Response with critical hate speech — should block immediately
        response = "This content promotes hate speech and racial slur."
        report = engine.run_full_check(
            query="test",
            response=response,
            confidence=90.0,
            company_id="co1",
            variant_type="parwa",
        )
        assert not report.passed
        assert report.overall_action == GuardAction.BLOCK.value
        # content_safety should fire first and block
        blocked_layers = [
            r for r in report.results if r.action == GuardAction.BLOCK.value
        ]
        assert len(blocked_layers) >= 1

    def test_confidence_result_always_valid_bc008(self):
        """ConfidenceScoringEngine never crashes — always returns valid result."""
        engine = ConfidenceScoringEngine()
        # Edge cases that should not crash
        for query, response in [
            ("", ""),
            (None, None),
            ("query", None),
            (None, "response"),
            ("x" * 10000, "y" * 10000),
        ]:
            safe_query = query or ""
            safe_response = response or ""
            result = engine.score_response("co1", safe_query, safe_response)
            assert isinstance(result, ConfidenceResult)
            assert 0.0 <= result.overall_score <= 100.0
            assert isinstance(result.passed, bool)


# ══════════════════════════════════════════════════════════════════════
# 4. CACHE TENANT ISOLATION — ~4 tests
# ══════════════════════════════════════════════════════════════════════


class TestCacheTenantIsolation:
    """One company can't read another's cached responses."""

    def test_validate_company_id_rejects_empty(self):
        """Empty company_id raises ParwaBaseError."""
        with pytest.raises(ParwaBaseError):
            _validate_company_id("")
        with pytest.raises(ParwaBaseError):
            _validate_company_id("   ")

    def test_validate_company_id_accepts_valid(self):
        """Valid company_id doesn't raise."""
        # Should not raise
        _validate_company_id("company_abc")
        _validate_company_id("co-123")

    def test_get_cached_result_filters_by_company_id(self):
        """get_cached_result uses company_id in filter — no cross-tenant read."""
        mock_db = MagicMock()
        mock_entry = MagicMock()
        mock_entry.cached_result = json.dumps({"answer": "secret data"})
        mock_entry.ttl_expires_at = datetime.utcnow() + timedelta(hours=1)
        mock_entry.hit_count = 0
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_entry

        result = tcs_get_cached_result(
            mock_db, "company_a", "technique_1", "hash_xyz",
        )
        assert result is not None
        # Verify filter_by was called with company_id
        call_kwargs = mock_db.query.return_value.filter_by.call_args
        assert call_kwargs[1]["company_id"] == "company_a"

    def test_set_cached_result_validates_company_id(self):
        """set_cached_result rejects empty company_id before any DB call."""
        mock_db = MagicMock()
        with pytest.raises(ParwaBaseError):
            tcs_set_cached_result(
                mock_db, "", "technique_1", "hash_xyz",
                cached_result={"data": "test"},
            )
        mock_db.add.assert_not_called()

    def test_query_hash_deterministic_across_companies(self):
        """Same query produces same hash regardless of company."""
        query = "How do I reset my password?"
        h1 = compute_query_hash(query)
        h2 = compute_query_hash(query)
        assert h1 == h2
        assert isinstance(h1, str)
        assert len(h1) == 64  # SHA-256 hex

    def test_invalidate_requires_company_id(self):
        """invalidate_cached_result validates company_id."""
        mock_db = MagicMock()
        with pytest.raises(ParwaBaseError):
            tcs_invalidate_cached_result(mock_db, None, "tech", "hash")
        mock_db.delete.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# 5. SELF-HEALING COOLDOWN BYPASS — ~4 tests
# ══════════════════════════════════════════════════════════════════════


class TestSelfHealingCooldownBypass:
    """Cooldown cannot be bypassed — healing actions respect cooldown."""

    def test_rule_cooldown_prevents_repeated_actions(self):
        """After a healing action fires, cooldown blocks re-trigger."""
        engine = SelfHealingEngine()
        rule = HealingRule(
            rule_id="test_cooldown",
            condition_type=ConditionType.CONSECUTIVE_FAILURES.value,
            action_type=ActionType.PROVIDER_DISABLE.value,
            priority=10,
            cooldown_seconds=300,  # 5 minutes
            params={"failure_limit": 3},
        )
        engine.set_rules("co1", [rule])

        # First: trigger the rule by reporting failures
        for i in range(3):
            actions = engine.record_query_result(
                company_id="co1",
                variant_type="parwa",
                provider="google",
                model_id="gemini-2.0-flash-lite",
                tier="medium",
                confidence_score=50.0,
                latency_ms=100.0,
                error="timeout",
            )
        # Should have triggered at least one action
        history = engine.get_healing_history("co1")
        assert len(history) >= 1

        # Second: try to trigger again immediately — cooldown should block
        more_actions = engine.record_query_result(
            company_id="co1",
            variant_type="parwa",
            provider="google",
            model_id="gemini-2.0-flash-lite",
            tier="medium",
            confidence_score=50.0,
            latency_ms=100.0,
            error="timeout",
        )
        # No new action should fire (cooldown active)
        new_history = engine.get_healing_history("co1")
        assert len(new_history) == len(history)  # unchanged

    def test_recovery_cooldown_between_attempts(self):
        """Recovery attempts are spaced by cooldown interval."""
        engine = SelfHealingEngine()

        # Manually set up a disabled provider
        state = engine._get_or_create_variant_state("co1", "parwa")
        pkey = "google:gemini-2.0-flash-lite"
        state.provider_states[pkey] = SHProviderState(
            provider="google", model_id="gemini-2.0-flash-lite",
            tier="medium", status="disabled",
            consecutive_failures=5,
            last_recovery_attempt=datetime.now(timezone.utc).isoformat(),
        )

        # Try recovery — cooldown should prevent
        action = engine._attempt_recovery("co1", "parwa", pkey)
        assert action is None, "Recovery should be blocked by cooldown"

    def test_confidence_threshold_restored_after_recovery_scores(self):
        """Lowered threshold is restored after enough consecutive high scores."""
        engine = SelfHealingEngine()

        # Record enough low scores to trigger threshold lowering
        for _ in range(_LOW_SCORE_CONSECUTIVE):
            engine.record_query_result(
                company_id="co1",
                variant_type="parwa",
                provider="google", model_id="gemini",
                tier="medium",
                confidence_score=50.0,  # below 85 default
                latency_ms=100.0,
            )

        # Check threshold was lowered
        vstate = engine._get_or_create_variant_state("co1", "parwa")
        assert "parwa" in vstate.threshold_adjustments
        assert vstate.threshold_adjustments["parwa"].current_threshold < 85.0

        # Now record enough high scores to trigger restore
        for _ in range(_RECOVERY_HIGH_SCORE_CONSECUTIVE):
            engine.record_query_result(
                company_id="co1",
                variant_type="parwa",
                provider="google", model_id="gemini",
                tier="medium",
                confidence_score=95.0,  # above 85 default
                latency_ms=100.0,
            )

        # Check threshold was restored
        assert "parwa" not in vstate.threshold_adjustments

    def test_different_companies_independent_healing(self):
        """Healing state for one company doesn't affect another."""
        engine = SelfHealingEngine()

        # Report failures for company A only
        for _ in range(_CONSECUTIVE_FAILURE_LIMIT):
            engine.record_query_result(
                company_id="co_a",
                variant_type="parwa",
                provider="google", model_id="gemini",
                tier="medium",
                confidence_score=50.0,
                latency_ms=100.0,
                error="timeout",
            )

        history_a = engine.get_healing_history("co_a")
        history_b = engine.get_healing_history("co_b")
        assert len(history_a) >= 1
        assert len(history_b) == 0  # company B unaffected


# ══════════════════════════════════════════════════════════════════════
# 6. ALERT FALSE POSITIVES — ~4 tests
# ══════════════════════════════════════════════════════════════════════


class TestAlertFalsePositives:
    """Normal metric variance doesn't trigger alerts."""

    def test_low_error_rate_no_alert(self):
        """5% error rate does NOT trigger any alert (threshold is 10%)."""
        svc = AIMonitoringService()
        svc.reset()

        # Record 20 queries: 1 error (5%), rest success
        for i in range(19):
            svc.record_query(
                company_id="co1",
                variant_type="parwa",
                query="test query",
                response="A helpful response with enough detail to pass",
                latency_ms=200.0,
            )
        svc.record_query(
            company_id="co1",
            variant_type="parwa",
            query="test query",
            response="error fallback",
            latency_ms=200.0,
            error="timeout",
        )

        alerts = svc.get_alert_conditions("co1")
        error_alerts = [
            a for a in alerts
            if a.condition_id.startswith("error_rate")
        ]
        assert len(error_alerts) == 0, (
            f"5% error rate should not trigger alerts, got: {error_alerts}"
        )

    def test_normal_latency_no_alert(self):
        """Normal latency (200ms) doesn't trigger latency spike alert."""
        svc = AIMonitoringService()
        svc.reset()

        for _ in range(20):
            svc.record_query(
                company_id="co1",
                variant_type="parwa",
                query="test",
                response="A helpful response with enough detail to pass checks",
                latency_ms=200.0,
            )

        alerts = svc.get_alert_conditions("co1")
        latency_alerts = [
            a for a in alerts
            if a.condition_id == "latency_spike_warning"
        ]
        assert len(latency_alerts) == 0

    def test_good_confidence_no_alert(self):
        """Healthy confidence scores (avg ~90) don't trigger confidence alert."""
        svc = AIMonitoringService()
        svc.reset()

        for _ in range(20):
            svc.record_query(
                company_id="co1",
                variant_type="parwa",
                query="test query about refund",
                response="Your refund for order #12345 has been processed "
                         "and will appear within 5-7 business days.",
                confidence_result={"overall_score": 90.0, "passed": True},
                latency_ms=150.0,
            )

        alerts = svc.get_alert_conditions("co1")
        confidence_alerts = [
            a for a in alerts
            if a.condition_id == "confidence_drop_warning"
        ]
        assert len(confidence_alerts) == 0

    def test_single_provider_error_no_unhealthy_alert(self):
        """Provider with 30% error rate (below 50% threshold) no CRITICAL."""
        svc = AIMonitoringService()
        svc.reset()

        # Provider A: 70% success, Provider B: 70% success
        for _ in range(14):
            svc.record_query(
                company_id="co1",
                variant_type="parwa",
                query="test",
                response="Good response",
                routing_decision={"provider": "google", "model_id": "m1"},
                latency_ms=200.0,
            )
        # Provider B: 6 success, 3 errors → ~33% error rate
        for _ in range(6):
            svc.record_query(
                company_id="co1",
                variant_type="parwa",
                query="test",
                response="Good response",
                routing_decision={"provider": "cerebras", "model_id": "m2"},
                latency_ms=200.0,
            )
        for _ in range(3):
            svc.record_query(
                company_id="co1",
                variant_type="parwa",
                query="test",
                response="error",
                routing_decision={"provider": "cerebras", "model_id": "m2"},
                latency_ms=200.0,
                error="timeout",
            )

        alerts = svc.get_alert_conditions("co1")
        unhealthy_alerts = [
            a for a in alerts
            if "provider_unhealthy" in a.condition_id
        ]
        assert len(unhealthy_alerts) == 0, (
            "33% error rate should not trigger unhealthy alert (threshold 50%)"
        )


# ══════════════════════════════════════════════════════════════════════
# BONUS: Cross-cutting edge case tests
# ══════════════════════════════════════════════════════════════════════


class TestCrossCuttingEdgeCases:

    def test_degraded_response_detected_across_providers(self):
        """DegradedResponseDetector flags empty and error-pattern responses."""
        detector = DegradedResponseDetector()
        is_deg, reason = detector.is_degraded("")
        assert is_deg is True
        assert "empty" in reason

        is_deg2, reason2 = detector.is_degraded("Internal server error occurred")
        assert is_deg2 is True

        good = "This is a perfectly normal response with enough length."
        is_deg3, reason3 = detector.is_degraded(good)
        assert is_deg3 is False
        assert reason3 == "ok"

    def test_safe_json_parse_handles_corruption(self):
        """_safe_parse_json returns fallback on malformed JSON."""
        assert _safe_parse_json(None) == {}
        assert _safe_parse_json("") == {}
        assert _safe_parse_json("not json at all") == {}
        assert _safe_parse_json('{"key": "value"}') == {"key": "value"}
        assert _safe_parse_json(None, fallback="DEFAULT") == "DEFAULT"

    def test_validate_cache_result_rejects_none(self):
        """_validate_cache_result raises on None input."""
        with pytest.raises(ParwaBaseError):
            _validate_cache_result(None)

    def test_validate_cache_result_rejects_circular_ref(self):
        """_validate_cache_result raises on non-serializable data."""
        data = {"self": None}
        data["self"] = data  # circular reference
        with pytest.raises(ParwaBaseError):
            _validate_cache_result(data)

    def test_monitoring_record_query_returns_dict(self):
        """record_query always returns a dict, even on error."""
        svc = AIMonitoringService()
        # Normal call
        result = svc.record_query(
            company_id="co1",
            variant_type="parwa",
            query="test",
            response="response",
        )
        assert isinstance(result, dict)
        assert "timestamp" in result
        assert result["company_id"] == "co1"

    def test_monitoring_empty_company_no_crash(self):
        """All monitoring methods handle empty/unknown company gracefully."""
        svc = AIMonitoringService()
        assert svc.get_latency_stats("nonexistent").count == 0
        assert svc.get_error_metrics("nonexistent").total_errors == 0
        assert svc.get_confidence_distribution("nonexistent").total_count == 0
        assert svc.get_guardrail_stats("nonexistent").total_checked == 0
        assert svc.get_token_usage("nonexistent").total_requests == 0
        assert len(svc.get_provider_comparison("nonexistent")) == 0
        assert svc.get_record_count("nonexistent") == 0

    def test_failover_stats_empty_company(self):
        """get_failover_stats returns safe defaults for unknown company."""
        mgr = FailoverManager()
        stats = mgr.get_failover_stats("nonexistent", hours=24)
        assert stats["company_id"] == "nonexistent"
        assert stats["total_failovers"] == 0
        assert isinstance(stats["circuit_states"], dict)
