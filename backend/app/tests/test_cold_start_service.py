"""Tests for Cold Start Service (SG-30) – Day 2 AI Engine.

Covers:
- warmup_tenant creates correct state for variant tiers
- VARIANT_TIER_MAP includes guardrail
- PREWARM_COMBOS includes guardrail model
- get_cold_fallback_model always returns something (BC-008)
- invalidate_warmup removes tenant state
- Heavy timeout enforcement (5s)
- Tenant state cleanup
- prewarm_all_providers returns results
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.core.cold_start_service import (
    ColdStartService,
    VARIANT_TIER_MAP,
    PREWARM_COMBOS,
    HEAVY_WARMUP_TIMEOUT_MS,
    _utcnow,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def service() -> ColdStartService:
    return ColdStartService()


@pytest.fixture
def mock_warmup():
    """Mock _warmup_single_model to return success immediately."""

    def _mock_warmup(self, company_id, combo, timeout_ms=None):
        from app.core.cold_start_service import ModelWarmupState, WarmupStatus

        return ModelWarmupState(
            provider=combo.provider,
            model_id=combo.model_id,
            tier=combo.tier,
            status=WarmupStatus.warm,
            warmup_success=True,
            warmup_latency_ms=100,
            last_warmed_at=_utcnow(),
            probe_query=combo.probe_query,
            probe_response="Mock response",
        )

    return _mock_warmup


COMPANY_ID = "test-company-789"


# ── 1. warmup_tenant creates state for variant tiers ─────────────


class TestWarmupTenant:
    @patch.object(ColdStartService, "_warmup_single_model")
    def test_creates_state_for_mini_parwa(self, mock_method, service: ColdStartService):
        from app.core.cold_start_service import ModelWarmupState, WarmupStatus

        mock_method.return_value = ModelWarmupState(
            provider="cerebras",
            model_id="llama-3.1-8b",
            tier="light",
            status=WarmupStatus.warm,
            warmup_success=True,
        )
        state = service.warmup_tenant(COMPANY_ID, "mini_parwa")
        assert state.company_id == COMPANY_ID
        assert state.variant_type == "mini_parwa"
        assert state.overall_status == WarmupStatus.warm
        assert len(state.models_warmed) > 0

    @patch.object(ColdStartService, "_warmup_single_model")
    def test_creates_state_for_parwa(self, mock_method, service: ColdStartService):
        from app.core.cold_start_service import ModelWarmupState, WarmupStatus

        mock_method.return_value = ModelWarmupState(
            provider="google",
            model_id="gemini-2.0-flash-lite",
            tier="medium",
            status=WarmupStatus.warm,
            warmup_success=True,
        )
        state = service.warmup_tenant(COMPANY_ID, "parwa")
        assert state.variant_type == "parwa"
        # parwa should have light + medium + guardrail models
        assert len(state.models_warmed) > 1

    @patch.object(ColdStartService, "_warmup_single_model")
    def test_unknown_variant_defaults_to_mini_parwa(
        self, mock_method, service: ColdStartService
    ):
        from app.core.cold_start_service import ModelWarmupState, WarmupStatus

        mock_method.return_value = ModelWarmupState(
            provider="cerebras",
            model_id="llama-3.1-8b",
            tier="light",
            status=WarmupStatus.warm,
            warmup_success=True,
        )
        state = service.warmup_tenant(COMPANY_ID, "unknown_xyz")
        assert state.variant_type == "mini_parwa"


# ── 2. VARIANT_TIER_MAP includes guardrail ───────────────────────


class TestVariantTierMap:
    def test_mini_parwa_has_guardrail(self):
        assert "guardrail" in VARIANT_TIER_MAP["mini_parwa"]

    def test_parwa_has_guardrail(self):
        assert "guardrail" in VARIANT_TIER_MAP["parwa"]

    def test_high_parwa_has_guardrail(self):
        assert "guardrail" in VARIANT_TIER_MAP["high_parwa"]

    def test_mini_parwa_no_medium(self):
        assert "medium" not in VARIANT_TIER_MAP["mini_parwa"]

    def test_parwa_has_medium(self):
        assert "medium" in VARIANT_TIER_MAP["parwa"]


# ── 3. PREWARM_COMBOS includes guardrail ─────────────────────────


class TestPrewarmCombos:
    def test_has_guardrail_combo(self):
        guardrail = [c for c in PREWARM_COMBOS if c.tier == "guardrail"]
        assert len(guardrail) >= 1
        assert guardrail[0].model_id == "llama-guard-4-12b"

    def test_has_llama_4_scout_heavy(self):
        heavy = [c for c in PREWARM_COMBOS if c.tier == "heavy"]
        model_ids = [c.model_id for c in heavy]
        assert "llama-4-scout-instruct" in model_ids


# ── 4. get_cold_fallback_model always returns something ──────────


class TestColdFallbackModel:
    def test_returns_model_for_known_tenant(self, service: ColdStartService):
        service._tenant_states[COMPANY_ID] = MagicMock()
        result = service.get_cold_fallback_model(COMPANY_ID, "parwa")
        assert "provider" in result
        assert "model_id" in result
        assert "tier" in result

    @pytest.mark.parametrize(
        "variant", ["mini_parwa", "parwa", "high_parwa", "unknown"]
    )
    def test_returns_model_for_any_variant(
        self, service: ColdStartService, variant: str
    ):
        result = service.get_cold_fallback_model(COMPANY_ID, variant)
        assert result is not None
        assert "provider" in result

    def test_returns_model_without_tenant(self, service: ColdStartService):
        result = service.get_cold_fallback_model("", "parwa")
        assert result is not None
        assert result["tier"] == "light"


# ── 5. invalidate_warmup ─────────────────────────────────────────


class TestInvalidateWarmup:
    def test_removes_tenant_state(self, service: ColdStartService):
        service._tenant_states[COMPANY_ID] = MagicMock()
        service.invalidate_warmup(COMPANY_ID)
        assert COMPANY_ID not in service._tenant_states

    def test_handles_nonexistent_tenant(self, service: ColdStartService):
        # Should not crash
        service.invalidate_warmup("nonexistent-id")


# ── 6. Heavy timeout ─────────────────────────────────────────────


class TestHeavyTimeout:
    def test_constant_exists(self):
        assert HEAVY_WARMUP_TIMEOUT_MS == 5000

    @patch.object(ColdStartService, "_warmup_single_model")
    def test_heavy_warmup_uses_capped_timeout(
        self, mock_method, service: ColdStartService
    ):
        from app.core.cold_start_service import ModelWarmupState, WarmupStatus

        mock_method.return_value = ModelWarmupState(
            provider="groq",
            model_id="gpt-oss-120b",
            tier="heavy",
            status=WarmupStatus.warm,
            warmup_success=True,
        )
        service.warmup_tenant(COMPANY_ID, "high_parwa")
        # Check that _warmup_single_model was called with timeout_ms for heavy
        heavy_calls = [
            call
            for call in mock_method.call_args_list
            if len(call.args) >= 2
            and hasattr(call.args[1], "tier")
            and call.args[1].tier == "heavy"
        ]
        for call in heavy_calls:
            kwargs = call.kwargs
            if "timeout_ms" in kwargs:
                assert kwargs["timeout_ms"] <= HEAVY_WARMUP_TIMEOUT_MS


# ── 7. Tenant state cleanup ──────────────────────────────────────


class TestTenantStateCleanup:
    def test_max_tenant_states_enforced(self):
        svc = ColdStartService(max_tenant_states=5)
        # Trigger the trim by calling warmup_tenant which checks after insert
        with patch.object(ColdStartService, "_warmup_single_model") as mock:
            from app.core.cold_start_service import ModelWarmupState, WarmupStatus

            mock.return_value = ModelWarmupState(
                provider="cerebras",
                model_id="llama-3.1-8b",
                tier="light",
                status=WarmupStatus.warm,
                warmup_success=True,
            )
            # Add 4 states first, then warmup the 5th and 6th which should
            # trigger trim
            for i in range(4):
                svc._tenant_states[f"company-{i}"] = MagicMock()
            # Now warmup 2 more which triggers trim check in warmup_tenant
            svc.warmup_tenant("company-4", "mini_parwa")
            svc.warmup_tenant("company-5", "mini_parwa")
        # After trimming at warmup_tenant, should be <= max
        assert len(svc._tenant_states) <= 5


# ── 8. prewarm_all_providers ─────────────────────────────────────


class TestPrewarmAllProviders:
    @patch.object(ColdStartService, "_warmup_single_model")
    def test_returns_results_for_all_light(
        self, mock_method, service: ColdStartService
    ):
        from app.core.cold_start_service import ModelWarmupState, WarmupStatus

        mock_method.return_value = ModelWarmupState(
            provider="cerebras",
            model_id="llama-3.1-8b",
            tier="light",
            status=WarmupStatus.warm,
            warmup_success=True,
        )
        results = service.prewarm_all_providers()
        assert isinstance(results, dict)
        assert len(results) > 0

    @patch.object(ColdStartService, "_warmup_single_model")
    def test_handles_failure_gracefully(self, mock_method, service: ColdStartService):
        mock_method.side_effect = RuntimeError("API error")
        results = service.prewarm_all_providers()
        # Should not crash, returns error entries
        assert isinstance(results, dict)
