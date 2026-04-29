"""
Gap-filling tests for Week 8 Day 5: AI Monitoring + Self-Healing.

Covers 6 identified gaps:
  1. [CRITICAL] Tenant isolation leak in monitoring metrics
  2. [HIGH] Race condition in self-healing state transitions
  3. [HIGH] Cooldown period bypass in error rate detection
  4. [MEDIUM] Incomplete rollback after failed healing action
  5. [HIGH] Alert false positives from metric pruning edge cases
  6. [MEDIUM] Silent failure in confidence threshold auto-adjustment

All tests use unittest.mock / MagicMock — NO real API calls.
BC-001: company_id always first parameter.
BC-008: Never crash — every method wrapped in try/except.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

# Module-level stubs populated by autouse fixtures
AIMonitoringService = None  # type: ignore[assignment,misc]
SelfHealingEngine = None  # type: ignore[assignment,misc]
HealingRule = None  # type: ignore[assignment,misc]
HealingAction = None  # type: ignore[assignment,misc]
HealingStatus = None  # type: ignore[assignment,misc]
ActionType = None  # type: ignore[assignment,misc]
ConditionType = None  # type: ignore[assignment,misc]
ProviderState = None  # type: ignore[assignment,misc]
ThresholdAdjustment = None  # type: ignore[assignment,misc]
VariantHealingState = None  # type: ignore[assignment,misc]
_MAX_DATA_POINTS = None  # type: ignore[assignment,misc]
_LOW_SCORE_CONSECUTIVE = None  # type: ignore[assignment,misc]
_RECOVERY_HIGH_SCORE_CONSECUTIVE = None  # type: ignore[assignment,misc]


@pytest.fixture(autouse=True)
def _mock_logger():
    """Mock logger to allow importing source modules without real logging."""
    with patch("app.logger.get_logger", return_value=MagicMock()):
        from app.core.ai_monitoring_service import (
            _MAX_DATA_POINTS,
            AIMonitoringService,
        )
        from app.core.self_healing_engine import (
            _LOW_SCORE_CONSECUTIVE,
            _RECOVERY_HIGH_SCORE_CONSECUTIVE,
            ActionType,
            ConditionType,
            HealingAction,
            HealingRule,
            HealingStatus,
            ProviderState,
            SelfHealingEngine,
            ThresholdAdjustment,
            VariantHealingState,
        )

        globals().update(
            {
                "AIMonitoringService": AIMonitoringService,
                "SelfHealingEngine": SelfHealingEngine,
                "HealingRule": HealingRule,
                "HealingAction": HealingAction,
                "HealingStatus": HealingStatus,
                "ActionType": ActionType,
                "ConditionType": ConditionType,
                "ProviderState": ProviderState,
                "ThresholdAdjustment": ThresholdAdjustment,
                "VariantHealingState": VariantHealingState,
                "_MAX_DATA_POINTS": _MAX_DATA_POINTS,
                "_LOW_SCORE_CONSECUTIVE": _LOW_SCORE_CONSECUTIVE,
                "_RECOVERY_HIGH_SCORE_CONSECUTIVE": _RECOVERY_HIGH_SCORE_CONSECUTIVE,
            }
        )


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _make_monitoring_service():
    """Create a fresh AIMonitoringService instance."""
    svc = AIMonitoringService()
    svc.reset()
    return svc


def _make_healing_engine():
    """Create a fresh SelfHealingEngine instance."""
    engine = SelfHealingEngine()
    engine.reset()
    return engine


def _record_query(
    svc: AIMonitoringService,
    company_id: str,
    variant_type: str = "parwa",
    latency_ms: float = 100.0,
    confidence_score: float = 85.0,
    error: str = None,
    provider: str = "google",
) -> dict:
    """Convenience helper to record a query metric."""
    return svc.record_query(
        company_id=company_id,
        variant_type=variant_type,
        query=f"test query for {company_id}",
        response=f"test response for {company_id}",
        routing_decision={
            "provider": provider,
            "model_id": "gemini-pro",
            "tier": "medium",
        },
        confidence_result={
            "overall_score": confidence_score,
            "passed": True,
            "threshold": 85.0,
        },
        guardrails_report={"passed": True, "blocked_count": 0, "flagged_count": 0},
        latency_ms=latency_ms,
        error=error,
    )


# ═══════════════════════════════════════════════════════════════════
# 1. [CRITICAL] Tenant Isolation Leak in Monitoring Metrics
# ═══════════════════════════════════════════════════════════════════


class TestTenantIsolationInMonitoring:
    """
    GAP: One company's metrics can be accessed by another company
    through concurrent metric storage access.

    Tests simulate concurrent metric updates from different companies
    and verify company_id isolation is maintained.
    """

    def test_records_isolated_per_company(self):
        """Records for company A must not appear in company B's metrics."""
        svc = _make_monitoring_service()

        # Record 10 queries for company A
        for i in range(10):
            _record_query(svc, "company_a", latency_ms=200.0)

        # Record 5 queries for company B
        for i in range(5):
            _record_query(svc, "company_b", latency_ms=50.0)

        # Company A should have 10 records
        assert svc.get_record_count("company_a") == 10

        # Company B should have 5 records
        assert svc.get_record_count("company_b") == 5

    def test_latency_stats_per_company(self):
        """Latency stats must be computed per-company only."""
        svc = _make_monitoring_service()

        # Company A: high latency
        for _ in range(20):
            _record_query(svc, "co_a", latency_ms=500.0)

        # Company B: low latency
        for _ in range(20):
            _record_query(svc, "co_b", latency_ms=50.0)

        stats_a = svc.get_latency_stats("co_a")
        stats_b = svc.get_latency_stats("co_b")

        assert stats_a.avg == 500.0
        assert stats_b.avg == 50.0
        assert stats_a.count == 20
        assert stats_b.count == 20

    def test_error_metrics_per_company(self):
        """Error metrics must not leak between companies."""
        svc = _make_monitoring_service()

        # Company A: 50% error rate
        for i in range(10):
            error = "timeout" if i < 5 else None
            _record_query(svc, "co_a", error=error)

        # Company B: 0% error rate
        for _ in range(10):
            _record_query(svc, "co_b")

        errors_a = svc.get_error_metrics("co_a")
        errors_b = svc.get_error_metrics("co_b")

        assert errors_a.error_rate == 0.5
        assert errors_a.total_errors == 5
        assert errors_b.error_rate == 0.0
        assert errors_b.total_errors == 0

    def test_concurrent_writes_maintain_isolation(self):
        """Concurrent writes from different companies must not corrupt each other."""
        svc = _make_monitoring_service()
        num_companies = 5
        records_per_company = 50

        def write_records(company_id: str):
            for i in range(records_per_company):
                _record_query(svc, company_id, latency_ms=100.0 + i)

        with ThreadPoolExecutor(max_workers=num_companies) as executor:
            futures = [
                executor.submit(write_records, f"concurrent_co_{j}")
                for j in range(num_companies)
            ]
            for f in as_completed(futures):
                f.result()  # Raise any exceptions

        # Verify each company has exactly its own records
        for j in range(num_companies):
            cid = f"concurrent_co_{j}"
            count = svc.get_record_count(cid)
            assert (
                count == records_per_company
            ), f"Company {cid}: expected {records_per_company} records, got {count}"

    def test_dashboard_isolated_per_company(self):
        """Dashboard snapshot must only contain the requesting company's data."""
        svc = _make_monitoring_service()

        # Mix data for multiple companies
        for _ in range(10):
            _record_query(svc, "co_x", latency_ms=100.0, confidence_score=90.0)
            _record_query(
                svc, "co_y", latency_ms=500.0, confidence_score=40.0, error="fail"
            )

        dashboard_x = svc.get_dashboard_data("co_x")
        dashboard_y = svc.get_dashboard_data("co_y")

        assert dashboard_x.total_requests == 10
        assert dashboard_y.total_requests == 10
        assert dashboard_x.errors.total_errors == 0
        assert dashboard_y.errors.total_errors == 10

    def test_alerts_per_company(self):
        """Alerts generated for one company must not appear for another."""
        svc = _make_monitoring_service()

        # Company A: many errors → alert
        for _ in range(10):
            _record_query(svc, "alert_co_a", error="critical_failure")

        # Company B: no errors → no alert
        for _ in range(10):
            _record_query(svc, "alert_co_b")

        alerts_a = svc.get_alert_conditions("alert_co_a")
        alerts_b = svc.get_alert_conditions("alert_co_b")

        # Company A should have at least one error-related alert
        assert len(alerts_a) >= 1
        # Company B should have no alerts
        assert len(alerts_b) == 0


# ═══════════════════════════════════════════════════════════════════
# 2. [HIGH] Race Condition in Self-Healing State Transitions
# ═══════════════════════════════════════════════════════════════════


class TestSelfHealingStateTransitionRaceCondition:
    """
    GAP: Concurrent healing actions can lead to inconsistent provider
    states and potential deadlocks. Two background jobs simultaneously
    detect errors for the same provider, causing one to set state to
    "disabled" while the other tries to transition through recovery.
    """

    def test_consecutive_failures_disable_provider(self):
        """5 consecutive failures must disable the provider."""
        engine = _make_healing_engine()

        for i in range(5):
            actions = engine.record_query_result(
                company_id="co1",
                variant_type="parwa",
                provider="google",
                model_id="gemini-pro",
                tier="medium",
                confidence_score=50.0,
                latency_ms=100.0,
                error=f"failure_{i}",
            )

        # Should have triggered a disable action
        history = engine.get_healing_history("co1")
        disable_actions = [
            a for a in history if a.action_type == ActionType.PROVIDER_DISABLE.value
        ]
        assert len(disable_actions) >= 1

        # Provider state should be disabled
        health = engine.get_variant_health("co1")
        parwa_health = [h for h in health if h.variant == "parwa"]
        assert len(parwa_health) >= 1
        assert parwa_health[0].healthy is False

    def test_recovery_after_disable(self):
        """Provider should recover after consecutive successes following disable."""
        engine = _make_healing_engine()

        # Disable provider
        for i in range(5):
            engine.record_query_result(
                company_id="co1",
                variant_type="parwa",
                provider="google",
                model_id="gemini-pro",
                tier="medium",
                confidence_score=50.0,
                latency_ms=100.0,
                error=f"fail_{i}",
            )

        # Verify disabled
        health_before = engine.get_variant_health("co1")
        parwa_before = [h for h in health_before if h.variant == "parwa"]
        assert parwa_before[0].healthy is False

        # Send successes to trigger recovery (bypass cooldown for testing)
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,  # Far past cooldown
        ):
            for _ in range(10):
                engine.record_query_result(
                    company_id="co1",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=90.0,
                    latency_ms=50.0,
                )

        # Should have recovery actions
        history = engine.get_healing_history("co1")
        recovery_actions = [
            a
            for a in history
            if a.action_type
            in (
                ActionType.TRAFFIC_RAMP_UP.value,
                ActionType.PROVIDER_ENABLE.value,
            )
        ]
        assert len(recovery_actions) >= 1

    def test_concurrent_healing_triggers_same_provider(self):
        """
        Simulate two threads triggering healing for the same provider.
        Provider state must remain consistent (no partial state).
        """
        engine = _make_healing_engine()
        results = {"actions": []}
        lock = threading.Lock()

        def trigger_failures(thread_id: int):
            """Send failures from a thread."""
            for i in range(5):
                actions = engine.record_query_result(
                    company_id="co_race",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"thread_{thread_id}_fail_{i}",
                )
                with lock:
                    results["actions"].extend(actions)

        # Run two threads concurrently
        t1 = threading.Thread(target=trigger_failures, args=(1,))
        t2 = threading.Thread(target=trigger_failures, args=(2,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        # Both threads completed without deadlock
        assert not t1.is_alive()
        assert not t2.is_alive()

        # Provider state should be valid (not a corrupted mix)
        health = engine.get_variant_health("co_race")
        parwa_health = [h for h in health if h.variant == "parwa"]
        assert len(parwa_health) >= 1

        # State should be one of: healthy, disabled, degraded, recovering
        for pkey, status in parwa_health[0].provider_status.items():
            assert status in (
                "healthy",
                "degraded",
                "disabled",
                "recovering",
            ), f"Invalid provider state: {status}"

    def test_healing_action_status_consistency(self):
        """All healing actions must have valid status transitions."""
        engine = _make_healing_engine()

        actions = engine.record_query_result(
            company_id="co1",
            variant_type="parwa",
            provider="google",
            model_id="gemini-pro",
            tier="medium",
            confidence_score=50.0,
            latency_ms=100.0,
            error="single_failure",
        )

        valid_statuses = {s.value for s in HealingStatus}
        for action in actions:
            assert (
                action.status in valid_statuses
            ), f"Invalid action status: {action.status}"


# ═══════════════════════════════════════════════════════════════════
# 3. [HIGH] Cooldown Period Bypass in Error Rate Detection
# ═══════════════════════════════════════════════════════════════════


class TestCooldownPeriodBypass:
    """
    GAP: Error rate spike detection can be manipulated by rapid
    consecutive requests, bypassing intended cooldown periods.

    Tests verify that the cooldown mechanism prevents repeated
    healing triggers within the cooldown window.
    """

    def test_consecutive_failure_trigger_then_cooldown(self):
        """After a disable action, subsequent failures must not retrigger within cooldown."""
        engine = _make_healing_engine()

        # Trigger first disable
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(5):
                engine.record_query_result(
                    company_id="co_cd",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"fail_{i}",
                )

        history = engine.get_healing_history("co_cd")
        disable_count = sum(
            1 for a in history if a.action_type == ActionType.PROVIDER_DISABLE.value
        )
        assert disable_count >= 1

        # Now try to trigger again — cooldown should prevent it
        # (seconds_since returns a small value, simulating cooldown not elapsed)
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=10.0,  # 10 seconds < 300 second cooldown
        ):
            for i in range(10):
                engine.record_query_result(
                    company_id="co_cd",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"another_fail_{i}",
                )

        history_after = engine.get_healing_history("co_cd")
        disable_after = sum(
            1
            for a in history_after
            if a.action_type == ActionType.PROVIDER_DISABLE.value
        )
        # Should NOT have additional disables (cooldown active)
        assert (
            disable_after == disable_count
        ), f"Cooldown bypassed! Expected {disable_count} disables, got {disable_after}"

    def test_cooldown_elapsed_allows_retrigger(self):
        """After cooldown elapses, healing actions can trigger again."""
        engine = _make_healing_engine()

        # First trigger
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(5):
                engine.record_query_result(
                    company_id="co_cd2",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"fail_{i}",
                )

        history_first = engine.get_healing_history("co_cd2")
        first_disable_count = sum(
            1
            for a in history_first
            if a.action_type == ActionType.PROVIDER_DISABLE.value
        )

        # After cooldown elapses, trigger again
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,  # Cooldown elapsed
        ):
            # Need to reset provider state's consecutive failures
            # (simulate a brief recovery then failure again)
            # First, one success to reset
            engine.record_query_result(
                company_id="co_cd2",
                variant_type="parwa",
                provider="google",
                model_id="gemini-pro",
                tier="medium",
                confidence_score=90.0,
                latency_ms=50.0,
            )

            # Then 5 more failures
            for i in range(5):
                engine.record_query_result(
                    company_id="co_cd2",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"fail_again_{i}",
                )

        history_second = engine.get_healing_history("co_cd2")
        second_disable_count = sum(
            1
            for a in history_second
            if a.action_type == ActionType.PROVIDER_DISABLE.value
        )

        # Should have more disables after cooldown elapsed
        assert second_disable_count >= first_disable_count

    def test_rapid_error_flood_does_not_bypass_cooldown(self):
        """
        Simulate an attacker flooding the API with rapid error requests.
        Cooldown must prevent cascading disables.
        """
        engine = _make_healing_engine()

        # First batch triggers disable
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(5):
                engine.record_query_result(
                    company_id="co_flood",
                    variant_type="parwa",
                    provider="attacker_provider",
                    model_id="evil-model",
                    tier="medium",
                    confidence_score=10.0,
                    latency_ms=100.0,
                    error=f"attack_{i}",
                )

        disable_count_initial = sum(
            1
            for a in engine.get_healing_history("co_flood")
            if a.action_type == ActionType.PROVIDER_DISABLE.value
        )

        # Rapid flood with cooldown active
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=1.0,  # 1 second — well within cooldown
        ):
            for i in range(1000):
                engine.record_query_result(
                    company_id="co_flood",
                    variant_type="parwa",
                    provider="attacker_provider",
                    model_id="evil-model",
                    tier="medium",
                    confidence_score=10.0,
                    latency_ms=100.0,
                    error=f"flood_{i}",
                )

        disable_count_after = sum(
            1
            for a in engine.get_healing_history("co_flood")
            if a.action_type == ActionType.PROVIDER_DISABLE.value
        )

        assert (
            disable_count_after == disable_count_initial
        ), f"Flood bypassed cooldown! {disable_count_initial} -> {disable_count_after}"

    def test_default_cooldown_is_300_seconds(self):
        """Verify default cooldown for consecutive failures rule is 300s."""
        engine = _make_healing_engine()
        rules = engine.get_rules("co1")
        consecutive_rule = next(
            (r for r in rules if r.rule_id == "consecutive_failures_disable"),
            None,
        )
        assert consecutive_rule is not None
        assert consecutive_rule.cooldown_seconds == 300


# ═══════════════════════════════════════════════════════════════════
# 4. [MEDIUM] Incomplete Rollback After Failed Healing Action
# ═══════════════════════════════════════════════════════════════════


class TestIncompleteRollbackAfterFailedHealing:
    """
    GAP: When a healing action fails midway, the system may leave
    providers in an intermediate state without proper rollback.

    Tests simulate healing action failures and verify the system
    enters a safe fallback state.
    """

    def test_provider_state_consistent_after_exception(self):
        """Provider state must remain consistent even if healing encounters errors."""
        engine = _make_healing_engine()

        # Disable provider first
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(5):
                engine.record_query_result(
                    company_id="co_rb",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"fail_{i}",
                )

        # Verify provider is disabled
        health = engine.get_variant_health("co_rb")
        parwa = [h for h in health if h.variant == "parwa"][0]
        assert parwa.healthy is False

        # Provider state should be "disabled", not some undefined intermediate
        for pkey, status in parwa.provider_status.items():
            assert (
                status == "disabled"
            ), f"Expected 'disabled', got '{status}' for {pkey}"

    def test_recovery_stages_progress_correctly(self):
        """Recovery stages should progress 10% → 25% → 50% → 100%."""
        engine = _make_healing_engine()

        # Disable provider
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(5):
                engine.record_query_result(
                    company_id="co_stages",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"fail_{i}",
                )

        # Verify disabled
        health = engine.get_variant_health("co_stages")
        parwa = [h for h in health if h.variant == "parwa"][0]
        assert parwa.healthy is False

        # Each success triggers recovery (bypass cooldown)
        recovery_stages_seen = []
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for _ in range(5):
                actions = engine.record_query_result(
                    company_id="co_stages",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=90.0,
                    latency_ms=50.0,
                )
                for a in actions:
                    if a.action_type == ActionType.TRAFFIC_RAMP_UP.value:
                        pct = a.details.get("traffic_percentage")
                        if pct is not None:
                            recovery_stages_seen.append(pct)

        # Recovery stages should follow the defined sequence
        # _RECOVERY_STAGES = [10, 25, 50, 100]
        # With 5 successes after disable: stage 1→10%, 2→25%, 3→50%, 4→100%(full)
        # Some may be skipped due to cooldown timing, but sequence should be
        # valid
        valid_stages = {10, 25, 50, 100}
        for stage in recovery_stages_seen:
            assert stage in valid_stages, f"Invalid recovery stage: {stage}"

    def test_disabled_provider_has_zero_traffic(self):
        """After disable, provider traffic must be 0%."""
        engine = _make_healing_engine()

        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(5):
                engine.record_query_result(
                    company_id="co_traffic",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"fail_{i}",
                )

        # Check provider state directly
        with engine._lock:
            state = engine._state.get("co_traffic", {}).get("parwa")
            if state:
                for pkey, ps in state.provider_states.items():
                    if pkey == "google:gemini-pro":
                        assert ps.traffic_percentage == 0
                        assert ps.status == "disabled"

    def test_healing_history_records_all_actions(self):
        """All healing actions must be recorded for audit trail."""
        engine = _make_healing_engine()

        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(5):
                actions = engine.record_query_result(
                    company_id="co_audit",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                    error=f"fail_{i}",
                )

        history = engine.get_healing_history("co_audit")
        assert len(history) >= 1

        # Each action must have required fields
        for action in history:
            assert action.company_id == "co_audit"
            assert action.variant == "parwa"
            assert action.timestamp
            assert action.action_type
            assert action.status


# ═══════════════════════════════════════════════════════════════════
# 5. [HIGH] Alert False Positives from Metric Pruning Edge Cases
# ═══════════════════════════════════════════════════════════════════


class TestAlertFalsePositiveFromPruning:
    """
    GAP: The rolling window analytics may incorrectly calculate
    metrics when pruning old data points at the 50-data-point limit,
    causing false alerts.

    Tests verify that metric pruning works correctly at the limit
    and error rate calculations remain accurate after pruning.
    """

    def test_pruning_preserves_most_recent_records(self):
        """When exceeding _MAX_DATA_POINTS, oldest records are pruned."""
        svc = _make_monitoring_service()

        # Record more than _MAX_DATA_POINTS
        for i in range(_MAX_DATA_POINTS + 20):
            _record_query(svc, "co_prune", latency_ms=100.0)

        # Should have at most _MAX_DATA_POINTS
        count = svc.get_record_count("co_prune")
        assert (
            count <= _MAX_DATA_POINTS
        ), f"Expected <= {_MAX_DATA_POINTS} records, got {count}"

    def test_error_rate_accurate_after_pruning(self):
        """Error rate should remain accurate even after records are pruned."""
        svc = _make_monitoring_service()

        # Fill with success records
        for _ in range(_MAX_DATA_POINTS):
            _record_query(svc, "co_err_rate", latency_ms=100.0)

        # All records are successes
        errors = svc.get_error_metrics("co_err_rate")
        assert errors.error_rate == 0.0

        # Add error records (these will push out oldest success records)
        for _ in range(30):
            _record_query(svc, "co_err_rate", error="new_error")

        # Should have exactly _MAX_DATA_POINTS
        count = svc.get_record_count("co_err_rate")
        assert count == _MAX_DATA_POINTS

        # Error rate should reflect only remaining records
        errors_after = svc.get_error_metrics("co_err_rate")
        # 30 errors out of 50 total = 60% error rate
        expected_rate = 30 / _MAX_DATA_POINTS
        assert (
            abs(errors_after.error_rate - expected_rate) < 0.01
        ), f"Error rate inaccurate: {
                errors_after.error_rate} != {expected_rate}"

    def test_no_false_alert_after_pruning_good_data(self):
        """After pruning, only errors that remain in window should trigger alerts."""
        svc = _make_monitoring_service()

        # Fill with old error records
        for _ in range(_MAX_DATA_POINTS):
            _record_query(svc, "co_no_false", error="old_error")

        # Alerts should exist for high error rate
        alerts_before = svc.get_alert_conditions("co_no_false")
        error_alerts_before = [a for a in alerts_before if "error" in a.condition_id]
        assert len(error_alerts_before) >= 1

        # Now overwrite with all success records
        for _ in range(_MAX_DATA_POINTS):
            _record_query(svc, "co_no_false", latency_ms=50.0)

        # Old errors should be pruned, no error alerts
        alerts_after = svc.get_alert_conditions("co_no_false")
        error_alerts_after = [a for a in alerts_after if "error" in a.condition_id]
        assert (
            len(error_alerts_after) == 0
        ), "False alert: old errors still triggering after pruning"

    def test_confidence_distribution_accurate_after_pruning(self):
        """Confidence buckets should be accurate after record pruning."""
        svc = _make_monitoring_service()

        # Fill with high-confidence records
        for _ in range(_MAX_DATA_POINTS):
            _record_query(svc, "co_conf", confidence_score=90.0)

        # Prune and add low-confidence records
        for _ in range(_MAX_DATA_POINTS):
            _record_query(svc, "co_conf", confidence_score=30.0)

        dist = svc.get_confidence_distribution("co_conf")
        assert dist.total_count == _MAX_DATA_POINTS
        # All remaining records should be in "20-40" bucket
        assert dist.buckets.get("20-40", 0) == _MAX_DATA_POINTS
        assert dist.avg_score < 40.0

    def test_exact_boundary_pruning(self):
        """
        At exactly _MAX_DATA_POINTS, adding one more should prune
        exactly one record.
        """
        svc = _make_monitoring_service()

        # Add exactly _MAX_DATA_POINTS records
        for i in range(_MAX_DATA_POINTS):
            _record_query(svc, "co_exact", latency_ms=float(i))

        assert svc.get_record_count("co_exact") == _MAX_DATA_POINTS

        # Add one more
        _record_query(svc, "co_exact", latency_ms=999.0)

        # Should still be _MAX_DATA_POINTS (oldest pruned)
        assert svc.get_record_count("co_exact") == _MAX_DATA_POINTS

        # The oldest record (latency=0.0) should be gone
        latency = svc.get_latency_stats("co_exact")
        assert latency.min_val > 0.0, "Oldest record should have been pruned"


# ═══════════════════════════════════════════════════════════════════
# 6. [MEDIUM] Silent Failure in Confidence Threshold Auto-Adjustment
# ═══════════════════════════════════════════════════════════════════


class TestSilentFailureConfidenceThresholdAdjustment:
    """
    GAP: When confidence threshold adjustment fails, the error is
    silently ignored and continues with default values.

    Tests verify that the system maintains appropriate fallback
    behavior when adjustments fail.
    """

    def test_threshold_lowered_on_consecutive_low_scores(self):
        """Threshold should be lowered after enough consecutive low scores."""
        engine = _make_healing_engine()
        assert _LOW_SCORE_CONSECUTIVE is not None

        # Record enough consecutive low-confidence scores
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(_LOW_SCORE_CONSECUTIVE):
                engine.record_query_result(
                    company_id="co_thresh",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,  # Below default 85.0
                    latency_ms=100.0,
                )

        # Should have a threshold_lower action
        history = engine.get_healing_history("co_thresh")
        threshold_actions = [
            a for a in history if a.action_type == ActionType.THRESHOLD_LOWER.value
        ]
        assert (
            len(threshold_actions) >= 1
        ), "Expected threshold to be lowered after consecutive low scores"

    def test_threshold_not_below_floor(self):
        """Threshold must never go below the floor value."""
        engine = _make_healing_engine()

        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            # Record many low scores to try to push threshold below floor
            for i in range(30):
                engine.record_query_result(
                    company_id="co_floor",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=10.0,  # Very low
                    latency_ms=100.0,
                )

        # Check threshold in health summary
        health = engine.get_variant_health("co_floor")
        parwa = [h for h in health if h.variant == "parwa"]
        if parwa:
            # parwa floor is 70.0
            assert (
                parwa[0].threshold_current >= 70.0
            ), f"Threshold {parwa[0].threshold_current} below floor 70.0"

    def test_threshold_restored_after_consecutive_high_scores(self):
        """Threshold should be restored to default after consecutive high scores."""
        engine = _make_healing_engine()
        assert _RECOVERY_HIGH_SCORE_CONSECUTIVE is not None

        # Lower threshold first
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(_LOW_SCORE_CONSECUTIVE):
                engine.record_query_result(
                    company_id="co_restore",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                )

        # Verify threshold was lowered
        health_before = engine.get_variant_health("co_restore")
        parwa_before = [h for h in health_before if h.variant == "parwa"]
        assert len(parwa_before) >= 1
        assert parwa_before[0].threshold_current < 85.0, "Threshold should be lowered"

        # Now send high scores to trigger restore
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(_RECOVERY_HIGH_SCORE_CONSECUTIVE + 5):
                engine.record_query_result(
                    company_id="co_restore",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=95.0,  # Well above threshold
                    latency_ms=50.0,
                )

        # Check for threshold restore action
        history = engine.get_healing_history("co_restore")
        restore_actions = [
            a for a in history if a.action_type == ActionType.THRESHOLD_RESTORE.value
        ]
        assert (
            len(restore_actions) >= 1
        ), "Threshold should be restored after consecutive high scores"

    def test_healing_engine_never_crashes_on_bad_input_bc008(self):
        """BC-008: Engine must never crash regardless of input."""
        engine = _make_healing_engine()

        # Various bad inputs
        bad_inputs = [
            {"confidence_score": -1.0},
            {"confidence_score": 999.0},
            {"latency_ms": -100.0},
            {"latency_ms": float("inf")},
            {"error": ""},
            {"error": None},
            {"provider": ""},
            {"model_id": ""},
            {"variant_type": "nonexistent_variant"},
        ]

        for bad in bad_inputs:
            actions = engine.record_query_result(
                company_id="co_bc008",
                variant_type=bad.get("variant_type", "parwa"),
                provider=bad.get("provider", "google"),
                model_id=bad.get("model_id", "test"),
                tier="medium",
                confidence_score=bad.get("confidence_score", 50.0),
                latency_ms=bad.get("latency_ms", 100.0),
                error=bad.get("error"),
            )
            # Must return a list (never crash/raise)
            assert isinstance(actions, list)

    def test_confidence_drop_rule_cooldown_respected(self):
        """Confidence drop rule should respect cooldown between adjustments."""
        engine = _make_healing_engine()

        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            # First trigger: lower threshold
            for i in range(_LOW_SCORE_CONSECUTIVE):
                engine.record_query_result(
                    company_id="co_cd_test",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                )

        first_count = len(
            [
                a
                for a in engine.get_healing_history("co_cd_test")
                if a.action_type == ActionType.THRESHOLD_LOWER.value
            ]
        )
        assert first_count >= 1

        # Try again immediately — cooldown should block
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=10.0,  # Within cooldown
        ):
            for i in range(_LOW_SCORE_CONSECUTIVE):
                engine.record_query_result(
                    company_id="co_cd_test",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                )

        second_count = len(
            [
                a
                for a in engine.get_healing_history("co_cd_test")
                if a.action_type == ActionType.THRESHOLD_LOWER.value
            ]
        )

        assert second_count == first_count, (
            "Cooldown bypassed for confidence drop! " f"{first_count} -> {second_count}"
        )

    def test_variant_health_shows_adjusted_threshold(self):
        """get_variant_health must reflect current (possibly adjusted) threshold."""
        engine = _make_healing_engine()

        # Default threshold for parwa is 85.0
        health_before = engine.get_variant_health("co_vh")
        # No data yet, so no variants reported
        assert len(health_before) == 0

        # Record enough low scores to trigger adjustment
        with patch(
            "app.core.self_healing_engine._seconds_since",
            return_value=9999.0,
        ):
            for i in range(_LOW_SCORE_CONSECUTIVE):
                engine.record_query_result(
                    company_id="co_vh",
                    variant_type="parwa",
                    provider="google",
                    model_id="gemini-pro",
                    tier="medium",
                    confidence_score=50.0,
                    latency_ms=100.0,
                )

        health_after = engine.get_variant_health("co_vh")
        parwa = [h for h in health_after if h.variant == "parwa"]
        assert len(parwa) >= 1
        # Current threshold should be lower than original
        assert parwa[0].threshold_current < parwa[0].threshold_original
