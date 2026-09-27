"""
Week 8 Day 2 Group C: AI Engine Cold Start (SG-30) tests.

Tests are SOURCE OF TRUTH. If a test fails, fix the application code.
NEVER modify tests to pass.

Test categories:
- Status Tracking: cold→warm transitions, is_ready per tier, is_any_ready
- Tenant Warmup: mini_parwa=LIGHT only, parwa=LIGHT+MEDIUM, parwa_high=ALL.
                  Fallback when Heavy exceeds 5s
- Cold Fallback: always returns something (BC-008), prefers LIGHT
- Provider Warmup: prewarm_all tries all LIGHT, handles failures
- State Management: invalidate resets, get_all returns overview
- Edge Cases: unknown variant→defaults to mini_parwa, empty company_id→error,
              all timeout→still fallback
"""

import os
import time

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from unittest.mock import patch, MagicMock

import pytest

from backend.app.core.cold_start_service import (
    ColdStartService,
    PREWARM_COMBO,
    PREWARM_COMBOS,
    WarmupStatus,
    VARIANT_TIER_MAP,
    HEAVY_WARMUP_TIMEOUT_MS,
    ModelWarmupState,
    TenantWarmupState,
)
from backend.app.exceptions import ParwaBaseError


# ── Helpers ──────────────────────────────────────────────────────────


def _mock_warmup(service, company_id, variant_type, results=None):
    """
    Mock _simulate_llm_call and run warmup_tenant.
    results: dict mapping model_id -> {"success": bool, "latency_ms": int, ...}
    If results is None, all succeed.
    """
    if results is None:
        results = {}

    def mock_call(self, provider, model_id, query, timeout_ms):
        r = results.get(model_id, {"success": True, "response": "ok"})
        # Simulate minimal latency
        time.sleep(0.001)
        return r

    with patch.object(
        ColdStartService, "_simulate_llm_call", mock_call
    ):
        return service.warmup_tenant(company_id, variant_type)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def service():
    """Fresh ColdStartService instance for each test."""
    return ColdStartService()


# ══════════════════════════════════════════════════════════════════════
# Warmup Status Tracking
# ══════════════════════════════════════════════════════════════════════


class TestWarmupStatusTracking:
    def test_fresh_tenant_is_cold(self, service):
        """Fresh tenant should have no warmup state (None)."""
        status = service.get_tenant_status("comp_1")
        assert status is None

    def test_after_warmup_tenant_is_warm(self, service):
        """After warmup_tenant, status should be warm."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            state = service.warmup_tenant("comp_1", "mini_parwa")

        assert state.overall_status == WarmupStatus.warm

    def test_is_ready_returns_correct_status_per_tier(self, service):
        """is_ready should return True only for warmed tiers."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            service.warmup_tenant("comp_1", "mini_parwa")  # only light

        assert service.is_ready("comp_1", tier="light") is True
        assert service.is_ready("comp_1", tier="medium") is False
        assert service.is_ready("comp_1", tier="heavy") is False

    def test_is_any_ready_returns_true_if_light_warm(self, service):
        """is_any_ready returns True if at least LIGHT is warm."""
        assert service.is_any_ready("comp_1") is False

        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            service.warmup_tenant("comp_1", "mini_parwa")

        assert service.is_any_ready("comp_1") is True

    def test_is_ready_returns_false_for_unknown_tenant(self, service):
        """is_ready should return False for unknown tenants."""
        assert service.is_ready("unknown_comp") is False
        assert service.is_any_ready("unknown_comp") is False

    def test_is_ready_returns_false_for_empty_company_id(self, service):
        """is_ready should return False for empty company_id."""
        assert service.is_ready("") is False
        assert service.is_any_ready("") is False

    def test_cold_to_warm_transition(self, service):
        """Tenant transitions from cold (None) to warm after warmup."""
        assert service.get_tenant_status("comp_1") is None

        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            state = service.warmup_tenant("comp_1", "mini_parwa")

        assert state.overall_status == WarmupStatus.warm
        retrieved = service.get_tenant_status("comp_1")
        assert retrieved is not None
        assert retrieved.overall_status == WarmupStatus.warm

    def test_warming_status_during_warmup(self, service):
        """State should be set to 'warming' initially during warmup."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            state = service.warmup_tenant("comp_1", "mini_parwa")

        # After completion, status should be warm
        assert state.overall_status == WarmupStatus.warm
        # But started_at was set before models were warmed
        assert state.started_at is not None
        assert state.completed_at is not None


# ══════════════════════════════════════════════════════════════════════
# Tenant Warmup
# ══════════════════════════════════════════════════════════════════════


class TestTenantWarmup:
    def test_warmup_mini_parwa_only_warms_light(self, service):
        """mini_parwa should only warm LIGHT models."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ) as mock_call:
            state = service.warmup_tenant("comp_1", "mini_parwa")

        # Only light models should be called
        call_model_ids = {c.kwargs["model_id"] for c in mock_call.call_args_list}
        light_model_ids = {
            c.model_id for c in PREWARM_COMBOS if c.tier == "light"
        }
        assert call_model_ids == light_model_ids
        assert state.variant_type == "mini_parwa"

    def test_warmup_parwa_warms_light_and_medium(self, service):
        """parwa should warm LIGHT + MEDIUM models."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ) as mock_call:
            state = service.warmup_tenant("comp_1", "parwa")

        call_model_ids = {c.kwargs["model_id"] for c in mock_call.call_args_list}
        expected = {
            c.model_id for c in PREWARM_COMBOS if c.tier in ("light", "medium")
        }
        assert call_model_ids == expected
        assert state.variant_type == "parwa"

    def test_warmup_parwa_high_warms_all_tiers(self, service):
        """parwa_high should warm LIGHT + MEDIUM + HEAVY models."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ) as mock_call:
            state = service.warmup_tenant("comp_1", "parwa_high")

        call_model_ids = {c.kwargs["model_id"] for c in mock_call.call_args_list}
        all_model_ids = {c.model_id for c in PREWARM_COMBOS}
        assert call_model_ids == all_model_ids

    def test_warmup_records_latency_for_each_model(self, service):
        """Each model warmup should record latency."""
        call_count = 0

        def mock_call(self, provider, model_id, query, timeout_ms):
            nonlocal call_count
            call_count += 1
            time.sleep(0.01)  # 10ms simulated latency
            return {"success": True, "response": "ok"}

        with patch.object(
            ColdStartService, "_simulate_llm_call", mock_call
        ):
            state = service.warmup_tenant("comp_1", "mini_parwa")

        for model_state in state.models_warmed.values():
            assert model_state.warmup_latency_ms >= 0
            assert model_state.warmup_latency_ms < 10000  # sanity check

    def test_warmup_sets_fallback_if_heavy_fails(self, service):
        """If Heavy model warmup fails, fallback_used should be True."""
        results = {
            "llama-3.1-8b": {"success": True, "response": "ok"},
            "gemma-3-27b-it": {"success": True, "response": "ok"},
            "gemini-2.0-flash-lite": {"success": True, "response": "ok"},
            "llama-3.3-70b-versatile": {"success": True, "response": "ok"},
            "qwen3-32b": {"success": True, "response": "ok"},
            "gpt-oss-120b": {"success": False, "error": "timeout"},
        }

        state = _mock_warmup(service, "comp_1", "parwa_high", results)
        assert state.fallback_used is True

    def test_warmup_all_success_no_fallback(self, service):
        """If all models warm up successfully, fallback_used=False."""
        state = _mock_warmup(service, "comp_1", "mini_parwa")
        assert state.fallback_used is False
        assert state.overall_status == WarmupStatus.warm

    def test_warmup_started_at_and_completed_at_set(self, service):
        """Started_at and completed_at should be ISO-8601 UTC strings."""
        state = _mock_warmup(service, "comp_1", "mini_parwa")
        assert state.started_at is not None
        assert state.completed_at is not None
        assert "T" in state.started_at  # ISO format has T separator

    def test_warmup_time_to_warm_ms_is_positive(self, service):
        """time_to_warm_ms should be >= 0."""
        state = _mock_warmup(service, "comp_1", "mini_parwa")
        assert state.time_to_warm_ms >= 0

    def test_warmup_parwa_high_all_succeed_no_fallback(self, service):
        """All parwa_high models succeed → no fallback needed."""
        state = _mock_warmup(service, "comp_1", "parwa_high")
        assert state.fallback_used is False
        assert state.overall_status == WarmupStatus.warm
        # All 8 combos should be warmed
        assert len(state.models_warmed) == len(PREWARM_COMBOS)

    def test_warmup_partial_failure_marks_fallback(self, service):
        """If some models fail but not all, fallback_used=True."""
        results = {
            "llama-3.1-8b": {"success": True, "response": "ok"},
            "gemma-3-27b-it": {"success": False, "error": "error"},
        }
        state = _mock_warmup(service, "comp_1", "mini_parwa", results)
        # At least one failed, so fallback is used
        assert state.fallback_used is True
        # But overall_status is warm because some succeeded
        assert state.overall_status == WarmupStatus.warm

    def test_warmup_all_failure_marks_cooling(self, service):
        """If all models fail, status should be cooling."""
        results = {
            c.model_id: {"success": False, "error": "timeout"}
            for c in PREWARM_COMBOS
            if c.tier == "light"
        }
        state = _mock_warmup(service, "comp_1", "mini_parwa", results)
        assert state.overall_status == WarmupStatus.cooling
        assert state.fallback_used is True


# ══════════════════════════════════════════════════════════════════════
# Cold Fallback (BC-008)
# ══════════════════════════════════════════════════════════════════════


class TestColdFallback:
    def test_fallback_always_returns_something(self, service):
        """BC-008: get_cold_fallback_model must always return a result."""
        result = service.get_cold_fallback_model("comp_1", "mini_parwa")
        assert "provider" in result
        assert "model_id" in result
        assert "tier" in result
        assert "reason" in result

    def test_fallback_prefers_light_tier(self, service):
        """Fallback should prefer LIGHT tier models."""
        # No warmup done — should still return light
        result = service.get_cold_fallback_model("comp_1", "parwa_high")
        assert result["tier"] == "light"
        assert result["reason"] == "cold_fallback_to_lightest"

    def test_fallback_returns_warm_model_if_available(self, service):
        """If a warm model exists, should return it."""
        _mock_warmup(service, "comp_1", "mini_parwa")
        result = service.get_cold_fallback_model("comp_1", "mini_parwa")
        assert result["reason"] == "warm_model_available"
        assert result["tier"] == "light"

    def test_fallback_returns_correct_provider_and_model(self, service):
        """Fallback should return valid provider+model identifiers."""
        result = service.get_cold_fallback_model("comp_1", "mini_parwa")
        assert result["provider"] in ("cerebras", "groq", "google")
        assert isinstance(result["model_id"], str)
        assert len(result["model_id"]) > 0

    def test_fallback_never_crashes_on_none_company_id(self, service):
        """BC-008: Fallback must not crash even with None company_id."""
        result = service.get_cold_fallback_model(None, "mini_parwa")
        assert result is not None
        assert "provider" in result
        assert "model_id" in result

    def test_fallback_never_crashes_on_empty_company_id(self, service):
        """BC-008: Fallback must not crash even with empty company_id."""
        result = service.get_cold_fallback_model("", "mini_parwa")
        assert result is not None
        assert "provider" in result

    def test_fallback_returns_lightest_when_no_warmup(self, service):
        """Without warmup, fallback returns cerebras/llama-3.1-8b (lightest)."""
        result = service.get_cold_fallback_model("comp_1", "mini_parwa")
        assert result["provider"] == "cerebras"
        assert result["model_id"] == "llama-3.1-8b"
        assert result["tier"] == "light"
        assert result["reason"] == "cold_fallback_to_lightest"

    def test_fallback_returns_warm_medium_if_no_light_warm(self, service):
        """If light failed but medium succeeded, should return medium warm."""
        results = {
            "llama-3.1-8b": {"success": False, "error": "timeout"},
            "gemma-3-27b-it": {"success": False, "error": "timeout"},
            "gemini-2.0-flash-lite": {"success": True, "response": "ok"},
            "llama-3.3-70b-versatile": {"success": True, "response": "ok"},
            "qwen3-32b": {"success": True, "response": "ok"},
        }
        _mock_warmup(service, "comp_1", "parwa", results)
        result = service.get_cold_fallback_model("comp_1", "parwa")
        # Should return first warm model in the fallback chain
        # Since all light failed, it should find medium
        assert result["reason"] == "warm_model_available"
        assert result["tier"] in ("light", "medium")


# ══════════════════════════════════════════════════════════════════════
# Provider Warmup
# ══════════════════════════════════════════════════════════════════════


class TestProviderWarmup:
    def test_prewarm_all_tries_light_models(self, service):
        """prewarm_all_providers should try all LIGHT models."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ) as mock_call:
            result = service.prewarm_all_providers()

        # Should have called each light combo
        call_model_ids = {c.kwargs["model_id"] for c in mock_call.call_args_list}
        light_model_ids = {
            c.model_id for c in PREWARM_COMBOS if c.tier == "light"
        }
        assert call_model_ids == light_model_ids

    def test_prewarm_all_handles_failures_gracefully(self, service):
        """BC-008: prewarm_all_providers should handle failures gracefully."""
        def mock_call(self, provider, model_id, query, timeout_ms):
            if model_id == "llama-3.1-8b" and provider == "cerebras":
                raise RuntimeError("Connection refused")
            return {"success": True, "response": "ok"}

        with patch.object(
            ColdStartService, "_simulate_llm_call", mock_call
        ):
            result = service.prewarm_all_providers()

        # Should have results for all providers
        light_combos = [c for c in PREWARM_COMBOS if c.tier == "light"]
        assert len(result) == len(light_combos)
        # The cerebras one should show failure
        assert result["cerebras/llama-3.1-8b"]["success"] is False

    def test_prewarm_all_returns_status_dict(self, service):
        """prewarm_all_providers should return a dict with status info."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            result = service.prewarm_all_providers()

        assert isinstance(result, dict)
        for key, val in result.items():
            assert "status" in val
            assert "success" in val
            assert isinstance(val["success"], bool)

    def test_prewarm_all_includes_latency(self, service):
        """prewarm_all_providers should include latency in results."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            result = service.prewarm_all_providers()

        for key, val in result.items():
            assert "latency_ms" in val
            assert isinstance(val["latency_ms"], int)

    def test_prewarm_all_never_crashes(self, service):
        """BC-008: prewarm_all_providers must never crash."""
        def mock_call(self, provider, model_id, query, timeout_ms):
            raise RuntimeError("All providers down")

        with patch.object(
            ColdStartService, "_simulate_llm_call", mock_call
        ):
            result = service.prewarm_all_providers()

        # Should still return a dict
        assert isinstance(result, dict)
        assert len(result) > 0


# ══════════════════════════════════════════════════════════════════════
# State Management
# ══════════════════════════════════════════════════════════════════════


class TestStateManagement:
    def test_invalidate_warmup_resets_state(self, service):
        """invalidate_warmup should remove tenant state."""
        _mock_warmup(service, "comp_1", "mini_parwa")
        assert service.get_tenant_status("comp_1") is not None

        service.invalidate_warmup("comp_1")
        assert service.get_tenant_status("comp_1") is None

    def test_invalidate_nonexistent_warmup_no_error(self, service):
        """Invalidating a non-existent tenant should not raise."""
        service.invalidate_warmup("nonexistent")  # Should not raise

    def test_invalidate_empty_company_id_no_error(self, service):
        """Invalidating empty company_id should not raise (BC-008)."""
        service.invalidate_warmup("")  # Should not raise

    def test_get_all_tenant_statuses_overview(self, service):
        """get_all_tenant_statuses should return monitoring overview."""
        _mock_warmup(service, "comp_1", "mini_parwa")
        _mock_warmup(service, "comp_2", "parwa")

        result = service.get_all_tenant_statuses()
        assert "comp_1" in result
        assert "comp_2" in result
        assert result["comp_1"]["variant_type"] == "mini_parwa"
        assert result["comp_2"]["variant_type"] == "parwa"
        assert "overall_status" in result["comp_1"]
        assert "models_count" in result["comp_1"]
        assert "models_ready" in result["comp_1"]
        assert "fallback_used" in result["comp_1"]

    def test_get_all_tenant_statuses_empty(self, service):
        """Empty service should return empty dict."""
        assert service.get_all_tenant_statuses() == {}

    def test_invalidate_then_warmup_again(self, service):
        """After invalidation, warmup can be done again."""
        _mock_warmup(service, "comp_1", "mini_parwa")
        service.invalidate_warmup("comp_1")
        assert service.is_ready("comp_1") is False

        _mock_warmup(service, "comp_1", "mini_parwa")
        assert service.is_ready("comp_1", tier="light") is True

    def test_get_all_includes_started_at_completed_at(self, service):
        """get_all should include timestamps."""
        _mock_warmup(service, "comp_1", "mini_parwa")
        result = service.get_all_tenant_statuses()
        assert result["comp_1"]["started_at"] is not None
        assert result["comp_1"]["completed_at"] is not None

    def test_multiple_tenants_independent(self, service):
        """Tenant states are independent."""
        _mock_warmup(service, "comp_1", "mini_parwa")
        _mock_warmup(service, "comp_2", "parwa_high")

        status_1 = service.get_tenant_status("comp_1")
        status_2 = service.get_tenant_status("comp_2")

        # comp_1 should have only light models
        assert all(ms.tier == "light" for ms in status_1.models_warmed.values())
        # comp_2 should have light + medium + heavy
        tiers_2 = {ms.tier for ms in status_2.models_warmed.values()}
        assert tiers_2 == {"light", "medium", "heavy"}


# ══════════════════════════════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_unknown_variant_type_defaults_to_mini_parwa(self, service):
        """Unknown variant_type should default to mini_parwa."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ) as mock_call:
            state = service.warmup_tenant("comp_1", "unknown_variant")

        # Should only warm light models (mini_parwa default)
        call_model_ids = {c.kwargs["model_id"] for c in mock_call.call_args_list}
        light_model_ids = {
            c.model_id for c in PREWARM_COMBOS if c.tier == "light"
        }
        assert call_model_ids == light_model_ids
        assert state.variant_type == "mini_parwa"

    def test_empty_company_id_raises_parwa_base_error(self, service):
        """Empty company_id should raise ParwaBaseError (BC-001)."""
        with pytest.raises(ParwaBaseError) as exc_info:
            service.warmup_tenant("", "mini_parwa")

        assert exc_info.value.error_code == "COLD_START_INVALID_COMPANY"
        assert exc_info.value.status_code == 400

    def test_none_company_id_raises_parwa_base_error(self, service):
        """None company_id should raise ParwaBaseError (BC-001)."""
        with pytest.raises(ParwaBaseError) as exc_info:
            service.warmup_tenant(None, "mini_parwa")  # type: ignore

        assert exc_info.value.error_code == "COLD_START_INVALID_COMPANY"

    def test_all_models_timeout_still_marks_fallback(self, service):
        """If all models timeout, should still have fallback available."""
        results = {
            c.model_id: {"success": False, "error": "timeout"}
            for c in PREWARM_COMBOS
        }

        state = _mock_warmup(service, "comp_1", "mini_parwa", results)
        # Even with all failures, tenant should have a fallback
        fallback = service.get_cold_fallback_model("comp_1", "mini_parwa")
        assert fallback is not None
        assert fallback["tier"] == "light"
        assert state.fallback_used is True

    def test_check_model_readiness_unknown_model(self, service):
        """Checking readiness for unknown model should return cold state."""
        state = service.check_model_readiness("unknown_provider", "unknown_model")
        assert state.status == WarmupStatus.cold
        assert state.warmup_success is False

    def test_check_model_readiness_warm_model(self, service):
        """Checking readiness for a warmed model should return warm state."""
        _mock_warmup(service, "comp_1", "mini_parwa")

        state = service.check_model_readiness("cerebras", "llama-3.1-8b")
        assert state.status == WarmupStatus.warm
        assert state.warmup_success is True

    def test_warmup_exception_in_single_model_doesnt_crash(self, service):
        """BC-008: Exception in _warmup_single_model should not crash."""
        def mock_call(self, provider, model_id, query, timeout_ms):
            raise RuntimeError("Unexpected API error")

        with patch.object(
            ColdStartService, "_simulate_llm_call", mock_call
        ):
            state = service.warmup_tenant("comp_1", "mini_parwa")

        # Should not crash, all models should have error state
        for model_state in state.models_warmed.values():
            assert model_state.warmup_success is False
            assert model_state.error_message is not None

    def test_get_tenant_status_empty_returns_none(self, service):
        """get_tenant_status with empty string returns None."""
        assert service.get_tenant_status("") is None

    def test_is_ready_case_insensitive_tier(self, service):
        """is_ready should handle tier case-insensitively."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "ok"},
        ):
            service.warmup_tenant("comp_1", "mini_parwa")

        assert service.is_ready("comp_1", tier="LIGHT") is True
        assert service.is_ready("comp_1", tier="Light") is True
        assert service.is_ready("comp_1", tier="light") is True


# ══════════════════════════════════════════════════════════════════════
# PREWARM_COMBOS Data Integrity
# ══════════════════════════════════════════════════════════════════════


class TestPrewarmCombosIntegrity:
    def test_has_8_total_combos(self):
        """PREWARM_COMBOS should have exactly 8 entries (per spec)."""
        assert len(PREWARM_COMBOS) == 8

    def test_has_3_light_combos(self):
        """PREWARM_COMBOS should have 3 light models."""
        light = [c for c in PREWARM_COMBOS if c.tier == "light"]
        assert len(light) == 3

    def test_has_3_medium_combos(self):
        """PREWARM_COMBOS should have 3 medium models."""
        medium = [c for c in PREWARM_COMBOS if c.tier == "medium"]
        assert len(medium) == 3

    def test_has_2_heavy_combos(self):
        """PREWARM_COMBOS should have 2 heavy models."""
        heavy = [c for c in PREWARM_COMBOS if c.tier == "heavy"]
        assert len(heavy) == 2

    def test_all_combos_have_required_fields(self):
        """Every PREWARM_COMBO should have all required fields."""
        for combo in PREWARM_COMBOS:
            assert combo.model_id
            assert combo.provider
            assert combo.tier in ("light", "medium", "heavy")
            assert combo.probe_query
            assert combo.max_acceptable_latency_ms > 0

    def test_light_latency_within_2s(self):
        """All LIGHT combos should have max 2s latency."""
        for combo in PREWARM_COMBOS:
            if combo.tier == "light":
                assert combo.max_acceptable_latency_ms <= 2000

    def test_medium_latency_within_5s(self):
        """All MEDIUM combos should have max 5s latency."""
        for combo in PREWARM_COMBOS:
            if combo.tier == "medium":
                assert combo.max_acceptable_latency_ms <= 5000

    def test_heavy_latency_within_8s(self):
        """All HEAVY combos should have max 8s latency."""
        for combo in PREWARM_COMBOS:
            if combo.tier == "heavy":
                assert combo.max_acceptable_latency_ms <= 8000

    def test_has_cerebras_light(self):
        """Should have cerebras llama-3.1-8b light."""
        found = any(
            c.provider == "cerebras" and c.model_id == "llama-3.1-8b" and c.tier == "light"
            for c in PREWARM_COMBOS
        )
        assert found

    def test_has_groq_light(self):
        """Should have groq llama-3.1-8b light."""
        found = any(
            c.provider == "groq" and c.model_id == "llama-3.1-8b" and c.tier == "light"
            for c in PREWARM_COMBOS
        )
        assert found

    def test_has_google_light(self):
        """Should have google gemma-3-27b-it light."""
        found = any(
            c.provider == "google" and c.model_id == "gemma-3-27b-it" and c.tier == "light"
            for c in PREWARM_COMBOS
        )
        assert found

    def test_has_google_medium(self):
        """Should have google gemini-2.0-flash-lite medium."""
        found = any(
            c.provider == "google" and c.model_id == "gemini-2.0-flash-lite" and c.tier == "medium"
            for c in PREWARM_COMBOS
        )
        assert found

    def test_has_groq_70b_medium(self):
        """Should have groq llama-3.3-70b-versatile medium."""
        found = any(
            c.provider == "groq" and c.model_id == "llama-3.3-70b-versatile" and c.tier == "medium"
            for c in PREWARM_COMBOS
        )
        assert found

    def test_has_groq_qwen3_medium(self):
        """Should have groq qwen3-32b medium."""
        found = any(
            c.provider == "groq" and c.model_id == "qwen3-32b" and c.tier == "medium"
            for c in PREWARM_COMBOS
        )
        assert found

    def test_has_groq_heavy(self):
        """Should have groq gpt-oss-120b heavy."""
        found = any(
            c.provider == "groq" and c.model_id == "gpt-oss-120b" and c.tier == "heavy"
            for c in PREWARM_COMBOS
        )
        assert found

    def test_has_cerebras_heavy(self):
        """Should have cerebras gpt-oss-120b heavy."""
        found = any(
            c.provider == "cerebras" and c.model_id == "gpt-oss-120b" and c.tier == "heavy"
            for c in PREWARM_COMBOS
        )
        assert found


# ══════════════════════════════════════════════════════════════════════
# Model-Level Warmup State
# ══════════════════════════════════════════════════════════════════════


class TestModelWarmupState:
    def test_successful_warmup_records_all_fields(self, service):
        """Successful warmup should populate all ModelWarmupState fields."""
        with patch.object(
            ColdStartService,
            "_simulate_llm_call",
            return_value={"success": True, "response": "probe response"},
        ):
            state = service.warmup_tenant("comp_1", "mini_parwa")

        for key, ms in state.models_warmed.items():
            assert ms.provider in ("cerebras", "groq", "google")
            # key is composite: "provider:model_id"
            assert key == f"{ms.provider}:{ms.model_id}"
            assert ms.status == WarmupStatus.warm
            assert ms.warmup_success is True
            assert ms.last_warmed_at is not None
            assert ms.warmup_latency_ms >= 0
            assert ms.error_message is None
            assert ms.probe_query != ""
            assert ms.probe_response is not None

    def test_failed_warmup_records_error(self, service):
        """Failed warmup should record error details."""
        results = {
            "llama-3.1-8b": {"success": False, "error": "HTTP 429: Rate limited"},
        }
        state = _mock_warmup(service, "comp_1", "mini_parwa", results)

        for ms in state.models_warmed.values():
            if not ms.warmup_success:
                assert ms.error_message is not None
                assert ms.status in (WarmupStatus.cooling, WarmupStatus.cold)

    def test_model_warmup_state_is_dataclass(self):
        """ModelWarmupState should be a dataclass."""
        ms = ModelWarmupState(
            provider="cerebras",
            model_id="llama-3.1-8b",
            tier="light",
        )
        assert ms.provider == "cerebras"
        assert ms.model_id == "llama-3.1-8b"
        assert ms.tier == "light"
        assert ms.status == WarmupStatus.cold
        assert ms.warmup_success is False

    def test_tenant_warmup_state_is_dataclass(self):
        """TenantWarmupState should be a dataclass."""
        ts = TenantWarmupState(
            company_id="comp_1",
            variant_type="mini_parwa",
        )
        assert ts.company_id == "comp_1"
        assert ts.variant_type == "mini_parwa"
        assert ts.overall_status == WarmupStatus.cold
        assert ts.fallback_used is False


# ══════════════════════════════════════════════════════════════════════
# Variant Tier Map
# ══════════════════════════════════════════════════════════════════════


class TestVariantTierMap:
    def test_mini_parwa_has_light_only(self):
        """mini_parwa should have only light tier."""
        assert VARIANT_TIER_MAP["mini_parwa"] == ["light"]

    def test_parwa_has_light_and_medium(self):
        """parwa should have light and medium tiers."""
        assert set(VARIANT_TIER_MAP["parwa"]) == {"light", "medium"}

    def test_parwa_high_has_all_tiers(self):
        """parwa_high should have all tiers."""
        assert set(VARIANT_TIER_MAP["parwa_high"]) == {"light", "medium", "heavy"}

    def test_heavy_warmup_timeout_is_5s(self):
        """HEAVY_WARMUP_TIMEOUT_MS should be 5000."""
        assert HEAVY_WARMUP_TIMEOUT_MS == 5000


# ══════════════════════════════════════════════════════════════════════
# WarmupStatus Enum
# ══════════════════════════════════════════════════════════════════════


class TestWarmupStatusEnum:
    def test_has_all_statuses(self):
        """WarmupStatus should have cold, warming, warm, cooling."""
        assert WarmupStatus.cold.value == "cold"
        assert WarmupStatus.warming.value == "warming"
        assert WarmupStatus.warm.value == "warm"
        assert WarmupStatus.cooling.value == "cooling"

    def test_is_string_enum(self):
        """WarmupStatus should be a string enum."""
        assert isinstance(WarmupStatus.cold, str)
        assert WarmupStatus.cold == "cold"
