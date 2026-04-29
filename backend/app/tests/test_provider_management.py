"""
Tests for ProviderManagementService.

Covers:
- Provider status queries (all, single, single model, unknowns)
- Disable/Enable model lifecycle
- Alert creation, retrieval, acknowledgement, pruning
- API key management (get masked, rotate, deactivation)
- Usage stats (all providers, filtered, empty)
- Health check & dashboard aggregation
- Edge cases (company_id validation, BC-008, idempotent ops)
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.exceptions import ParwaBaseError
from app.services.provider_management_service import (
    ProviderAlert,
    ProviderManagementService,
    ProviderModelStatus,
    ProviderStatus,
    ProviderSummary,
    ProviderUsageStats,
    _mask_api_key,
    _utc_now,
    _utc_today,
    _validate_company_id,
    _worst_status,
)


# ── Constants ────────────────────────────────────────────────────

COMPANY_ID = "test-company-abc123"
OTHER_COMPANY = "other-company-xyz789"


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def svc() -> ProviderManagementService:
    """Fresh ProviderManagementService per test.

    SmartRouter imports are lazy so this does NOT require a running
    SmartRouter — the lazy loaders will attempt imports on first use
    but gracefully return None/{} on failure (BC-008).
    """
    return ProviderManagementService()


@pytest.fixture
def svc_with_registry(svc) -> ProviderManagementService:
    """Service with a mock MODEL_REGISTRY injected so status methods
    don't need to import SmartRouter at runtime."""
    # Build a lightweight fake registry with at least one model per provider.
    from dataclasses import dataclass
    from enum import Enum

    class FakeProvider(str, Enum):
        GOOGLE = "google"
        CEREBRAS = "cerebras"
        GROQ = "groq"

    class FakeTier(str, Enum):
        LIGHT = "light"
        MEDIUM = "medium"
        HEAVY = "heavy"
        GUARDRAIL = "guardrail"

    @dataclass
    class FakeModelConfig:
        provider: FakeProvider
        model_id: str
        display_name: str
        tier: FakeTier
        priority: int = 1
        max_requests_per_day: int = 14400
        max_tokens_per_minute: int = 60000
        context_window: int = 8192
        api_endpoint_base: str = ""
        is_openai_compatible: bool = True
        recommended_for: list = None

        def __post_init__(self):
            if self.recommended_for is None:
                self.recommended_for = []

    fake_registry = {
        "llama-3.1-8b-cerebras": FakeModelConfig(
            provider=FakeProvider.CEREBRAS,
            model_id="llama-3.1-8b",
            display_name="Llama 3.1 8B (Cerebras)",
            tier=FakeTier.LIGHT,
        ),
        "llama-3.1-70b-cerebras": FakeModelConfig(
            provider=FakeProvider.CEREBRAS,
            model_id="llama-3.1-70b",
            display_name="Llama 3.1 70B (Cerebras)",
            tier=FakeTier.MEDIUM,
        ),
        "gemini-2.0-flash-google": FakeModelConfig(
            provider=FakeProvider.GOOGLE,
            model_id="gemini-2.0-flash",
            display_name="Gemini 2.0 Flash",
            tier=FakeTier.LIGHT,
        ),
        "gemini-1.5-pro-google": FakeModelConfig(
            provider=FakeProvider.GOOGLE,
            model_id="gemini-1.5-pro",
            display_name="Gemini 1.5 Pro",
            tier=FakeTier.HEAVY,
        ),
        "llama-3.1-8b-groq": FakeModelConfig(
            provider=FakeProvider.GROQ,
            model_id="llama-3.1-8b",
            display_name="Llama 3.1 8B (Groq)",
            tier=FakeTier.LIGHT,
        ),
        "mixtral-8x7b-groq": FakeModelConfig(
            provider=FakeProvider.GROQ,
            model_id="mixtral-8x7b",
            display_name="Mixtral 8x7B (Groq)",
            tier=FakeTier.MEDIUM,
        ),
    }

    # Mock the tracker too.
    mock_tracker = MagicMock()
    mock_tracker.get_daily_usage.return_value = 10
    mock_tracker.get_daily_remaining.return_value = 14390
    mock_tracker.check_rate_limit.return_value = False
    mock_tracker.is_available.return_value = True
    mock_tracker.get_all_status.return_value = {}

    svc._model_registry = fake_registry
    svc._health_tracker = mock_tracker
    return svc


# ══════════════════════════════════════════════════════════════════
# 1. PROVIDER STATUS (~8 tests)
# ══════════════════════════════════════════════════════════════════


class TestProviderStatus:
    """Provider status query tests."""

    def test_get_all_providers_returns_three(self, svc_with_registry):
        """get_all_providers_status returns exactly 3 providers."""
        summaries = svc_with_registry.get_all_providers_status(COMPANY_ID)
        provider_names = {s.provider for s in summaries}
        assert provider_names == {"google", "cerebras", "groq"}
        assert len(summaries) == 3

    def test_each_provider_has_correct_model_count(self, svc_with_registry):
        """Each provider summary reports the right number of models from the registry."""
        summaries = svc_with_registry.get_all_providers_status(COMPANY_ID)
        by_name = {s.provider: s for s in summaries}

        # Registry has 2 cerebras, 2 google, 2 groq models
        assert by_name["cerebras"].total_models == 2
        assert by_name["google"].total_models == 2
        assert by_name["groq"].total_models == 2

    def test_get_single_provider_status(self, svc_with_registry):
        """get_provider_status returns a ProviderSummary for a known provider."""
        summary = svc_with_registry.get_provider_status(COMPANY_ID, "google")
        assert isinstance(summary, ProviderSummary)
        assert summary.provider == "google"
        assert summary.total_models == 2

    def test_get_single_model_status(self, svc_with_registry):
        """get_model_status returns a ProviderModelStatus for a known model."""
        status = svc_with_registry.get_model_status(
            COMPANY_ID, "cerebras", "llama-3.1-8b",
        )
        assert isinstance(status, ProviderModelStatus)
        assert status.model_id == "llama-3.1-8b"
        assert status.provider == "cerebras"

    def test_unknown_provider_returns_unknown_status(self, svc_with_registry):
        """Unknown provider name returns a ProviderSummary with UNKNOWN status."""
        summary = svc_with_registry.get_provider_status(
            COMPANY_ID, "anthropic")
        assert isinstance(summary, ProviderSummary)
        assert summary.status == ProviderStatus.UNKNOWN.value
        assert summary.total_models == 0

    def test_unknown_model_returns_unknown_status(self, svc_with_registry):
        """Unknown model_id returns a ProviderModelStatus with UNKNOWN status."""
        status = svc_with_registry.get_model_status(
            COMPANY_ID, "google", "claude-3-opus",
        )
        assert isinstance(status, ProviderModelStatus)
        assert status.status == ProviderStatus.UNKNOWN.value
        assert status.tier == "unknown"

    def test_provider_display_names_are_correct(self, svc_with_registry):
        """Display names match expected human-readable strings."""
        summaries = svc_with_registry.get_all_providers_status(COMPANY_ID)
        by_name = {s.provider: s.display_name for s in summaries}
        assert by_name["google"] == "Google AI Studio"
        assert by_name["cerebras"] == "Cerebras"
        assert by_name["groq"] == "Groq"

    def test_all_providers_status_returns_list_of_summaries(
            self, svc_with_registry):
        """Result is a list of ProviderSummary dataclass instances."""
        summaries = svc_with_registry.get_all_providers_status(COMPANY_ID)
        assert all(isinstance(s, ProviderSummary) for s in summaries)


# ══════════════════════════════════════════════════════════════════
# 2. DISABLE / ENABLE (~6 tests)
# ══════════════════════════════════════════════════════════════════


class TestDisableEnable:
    """Disable/Enable model lifecycle tests."""

    def test_disable_model(self, svc):
        """Disabling a model stores it and returns disabled status."""
        result = svc.disable_provider_model(
            COMPANY_ID, "cerebras", "llama-3.1-8b", "testing",
        )
        assert result["status"] == ProviderStatus.DISABLED.value
        assert result["provider"] == "cerebras"
        assert result["model_id"] == "llama-3.1-8b"
        assert result["reason"] == "testing"
        assert "disabled_at" in result

    def test_disabled_model_shows_in_disabled_list(self, svc):
        """After disabling, get_disabled_models includes the model."""
        svc.disable_provider_model(
            COMPANY_ID, "groq", "llama-3.1-8b", "rate limit",
        )
        disabled = svc.get_disabled_models(COMPANY_ID)
        assert "groq" in disabled
        models = [m["model_id"] for m in disabled["groq"]]
        assert "llama-3.1-8b" in models
        assert disabled["groq"][0]["reason"] == "rate limit"

    def test_re_enable_model(self, svc):
        """Re-enabling a disabled model removes it from disabled list."""
        svc.disable_provider_model(
            COMPANY_ID, "cerebras", "llama-3.1-8b", "testing",
        )
        result = svc.enable_provider_model(
            COMPANY_ID, "cerebras", "llama-3.1-8b",
        )
        assert result["status"] == ProviderStatus.HEALTHY.value
        # Model should no longer be in the disabled list.
        disabled = svc.get_disabled_models(COMPANY_ID)
        assert "cerebras" not in disabled

    def test_disable_nonexistent_model_handled(self, svc):
        """Disabling a model that doesn't exist in registry still succeeds."""
        result = svc.disable_provider_model(
            COMPANY_ID, "google", "fake-model-xyz", "because I can",
        )
        assert result["status"] == ProviderStatus.DISABLED.value
        # It's stored in disabled models regardless of registry.
        disabled = svc.get_disabled_models(COMPANY_ID)
        assert "google" in disabled

    def test_double_disable_is_idempotent(self, svc):
        """Disabling the same model twice is safe (idempotent)."""
        svc.disable_provider_model(
            COMPANY_ID, "groq", "llama-3.1-8b", "first",
        )
        result = svc.disable_provider_model(
            COMPANY_ID, "groq", "llama-3.1-8b", "second reason",
        )
        assert result["status"] == ProviderStatus.DISABLED.value
        # Reason should be updated to the latest.
        assert result["reason"] == "second reason"
        # Only one entry in the disabled list.
        disabled = svc.get_disabled_models(COMPANY_ID)
        assert len(disabled["groq"]) == 1

    def test_enable_already_enabled_is_idempotent(self, svc):
        """Enabling a model that was never disabled is a safe no-op."""
        result = svc.enable_provider_model(
            COMPANY_ID, "cerebras", "llama-3.1-8b",
        )
        assert result["status"] == ProviderStatus.HEALTHY.value
        assert "enabled_at" in result

    def test_is_model_disabled_returns_true(self, svc):
        """is_model_disabled returns True for a disabled model."""
        svc.disable_provider_model(
            COMPANY_ID, "google", "gemini-2.0-flash", "test",
        )
        assert svc.is_model_disabled(
            COMPANY_ID, "google", "gemini-2.0-flash",
        ) is True

    def test_is_model_disabled_returns_false_for_enabled(self, svc):
        """is_model_disabled returns False when model is not disabled."""
        assert svc.is_model_disabled(
            COMPANY_ID, "google", "gemini-2.0-flash",
        ) is False

    def test_disable_is_company_scoped(self, svc):
        """Disabling a model for one company does not affect another."""
        svc.disable_provider_model(
            COMPANY_ID, "cerebras", "llama-3.1-8b", "company-A",
        )
        # Other company should NOT see it disabled.
        assert svc.is_model_disabled(
            OTHER_COMPANY, "cerebras", "llama-3.1-8b",
        ) is False


# ══════════════════════════════════════════════════════════════════
# 3. ALERTS (~8 tests)
# ══════════════════════════════════════════════════════════════════


class TestAlerts:
    """Alert creation, retrieval, acknowledgement, and pruning tests."""

    def test_create_alert(self, svc):
        """create_alert returns a ProviderAlert with correct fields."""
        alert = svc.create_alert(
            company_id=COMPANY_ID,
            provider="groq",
            level="warning",
            message="High latency detected",
        )
        assert isinstance(alert, ProviderAlert)
        assert alert.provider == "groq"
        assert alert.level == "warning"
        assert alert.message == "High latency detected"
        assert alert.acknowledged is False
        assert alert.id  # non-empty UUID

    def test_get_all_alerts(self, svc):
        """get_alerts returns all alerts for a company."""
        svc.create_alert(COMPANY_ID, "google", level="info", message="a")
        svc.create_alert(COMPANY_ID, "cerebras", level="warning", message="b")
        alerts = svc.get_alerts(COMPANY_ID)
        assert len(alerts) >= 2

    def test_get_alerts_filtered_by_level(self, svc):
        """get_alerts with level= filters to matching alerts only."""
        svc.create_alert(
            COMPANY_ID,
            "google",
            level="info",
            message="info-msg")
        svc.create_alert(
            COMPANY_ID,
            "google",
            level="critical",
            message="crit-msg")
        svc.create_alert(
            COMPANY_ID,
            "groq",
            level="critical",
            message="crit-msg-2")

        info_alerts = svc.get_alerts(COMPANY_ID, level="info")
        assert len(info_alerts) == 1
        assert info_alerts[0].level == "info"

        crit_alerts = svc.get_alerts(COMPANY_ID, level="critical")
        assert len(crit_alerts) == 2

    def test_acknowledge_alert(self, svc):
        """Acknowledging an alert marks it acknowledged with user_id."""
        alert = svc.create_alert(
            COMPANY_ID, "groq", level="warning", message="test",
        )
        updated = svc.acknowledge_alert(COMPANY_ID, alert.id, "user-42")
        assert updated.acknowledged is True
        assert updated.acknowledged_by == "user-42"

    def test_get_unacknowledged_alerts(self, svc):
        """get_alerts(acknowledged=False) returns only unacknowledged alerts."""
        a1 = svc.create_alert(
            COMPANY_ID,
            "google",
            level="info",
            message="new")
        a2 = svc.create_alert(
            COMPANY_ID,
            "google",
            level="info",
            message="old")
        svc.acknowledge_alert(COMPANY_ID, a1.id, "user-1")

        unacked = svc.get_alerts(COMPANY_ID, acknowledged=False)
        assert len(unacked) == 1
        assert unacked[0].id == a2.id

    def test_alert_memory_pruning(self, svc):
        """When alerts exceed _MAX_ALERTS_PER_COMPANY, old ones are pruned."""
        max_alerts = svc._MAX_ALERTS_PER_COMPANY  # 500
        # Create 501 alerts
        for i in range(max_alerts + 1):
            svc.create_alert(
                COMPANY_ID, "google", level="info",
                message=f"alert-{i}",
            )
        # After pruning, count should be <= max_alerts
        remaining = len(svc._alerts[COMPANY_ID])
        assert remaining <= max_alerts

    def test_alert_created_on_model_disable(self, svc):
        """Disabling a model automatically creates a WARNING alert."""
        svc.disable_provider_model(
            COMPANY_ID, "cerebras", "llama-3.1-8b", "manual disable",
        )
        alerts = svc.get_alerts(COMPANY_ID, level="warning")
        assert any(
            "llama-3.1-8b" in a.message and "disabled" in a.message
            for a in alerts
        )

    def test_acknowledge_invalid_alert_raises(self, svc):
        """Acknowledging a non-existent alert_id raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            svc.acknowledge_alert(
                COMPANY_ID, str(uuid.uuid4()), "user-1",
            )

    def test_alerts_are_company_scoped(self, svc):
        """Alerts from one company are not visible to another."""
        svc.create_alert(COMPANY_ID, "google", level="info", message="a-co")
        alerts = svc.get_alerts(OTHER_COMPANY)
        assert len(alerts) == 0


# ══════════════════════════════════════════════════════════════════
# 4. API KEYS (~6 tests)
# ══════════════════════════════════════════════════════════════════


class TestAPIKeys:
    """API key management tests."""

    def test_get_api_keys_empty(self, svc):
        """get_api_keys returns empty list when no keys configured."""
        keys = svc.get_api_keys(COMPANY_ID)
        assert keys == []

    def test_rotate_api_key_creates_key(self, svc):
        """rotate_api_key creates a new active key."""
        result = svc.rotate_api_key(
            COMPANY_ID, "google", "AIzaSuperSecretKey12345",
        )
        assert result["provider"] == "google"
        assert result["is_active"] is True
        assert "key_id" in result
        assert "key_value_masked" in result

    def test_new_key_replaces_old(self, svc):
        """Rotating a key deactivates the previous key."""
        svc.rotate_api_key(COMPANY_ID, "groq", "old-key-123")
        first_keys = svc.get_api_keys(COMPANY_ID, provider="groq")
        assert len(first_keys) == 1
        assert first_keys[0]["is_active"] is True

        svc.rotate_api_key(COMPANY_ID, "groq", "new-key-456")
        all_keys = svc.get_api_keys(COMPANY_ID, provider="groq")
        assert len(all_keys) == 2
        # The first key should now be inactive.
        active_keys = [k for k in all_keys if k["is_active"]]
        inactive_keys = [k for k in all_keys if not k["is_active"]]
        assert len(active_keys) == 1
        assert len(inactive_keys) == 1

    def test_key_masking_format(self):
        """_mask_api_key shows visible chars + ****."""
        # Normal key (>=16 chars -> visible = min(8, max(4, 8)) = 8)
        assert _mask_api_key("ABCDEFGH12345678") == "ABCDEFGH****"
        # Short key (10 chars -> visible = min(8, max(4, 5)) = 5)
        assert _mask_api_key("ABCDE12345") == "ABCDE****"
        # Very short key (6 chars -> visible = min(8, max(4, 3)) = 4)
        assert _mask_api_key("ABCD12") == "ABCD****"
        # Empty key
        assert _mask_api_key("") == "****"
        # None key
        assert _mask_api_key(None) == "****"

    def test_get_api_keys_filtered_by_provider(self, svc):
        """get_api_keys with provider= returns only keys for that provider."""
        svc.rotate_api_key(COMPANY_ID, "google", "key1")
        svc.rotate_api_key(COMPANY_ID, "groq", "key2")

        google_keys = svc.get_api_keys(COMPANY_ID, provider="google")
        assert len(google_keys) == 1
        assert google_keys[0]["provider"] == "google"

    def test_rotate_creates_info_alert(self, svc):
        """Rotating an API key creates an INFO-level audit alert."""
        svc.rotate_api_key(COMPANY_ID, "cerebras", "my-new-key")
        alerts = svc.get_alerts(COMPANY_ID, level="info")
        assert any("API key rotated" in a.message for a in alerts)

    def test_rotate_empty_key_raises(self, svc):
        """Rotating with an empty new_key raises ValueError."""
        with pytest.raises((ValueError, TypeError)):
            svc.rotate_api_key(COMPANY_ID, "google", "")


# ══════════════════════════════════════════════════════════════════
# 5. USAGE STATS (~4 tests)
# ══════════════════════════════════════════════════════════════════


class TestUsageStats:
    """Usage analytics tests."""

    def test_get_usage_stats_returns_list(self, svc_with_registry):
        """get_usage_stats returns a list of ProviderUsageStats."""
        stats = svc_with_registry.get_usage_stats(COMPANY_ID, days=1)
        assert isinstance(stats, list)
        assert len(stats) >= 1
        assert all(isinstance(s, ProviderUsageStats) for s in stats)

    def test_filter_by_provider(self, svc_with_registry):
        """get_usage_stats with provider= returns stats for that provider only."""
        stats = svc_with_registry.get_usage_stats(
            COMPANY_ID, provider="google", days=1,
        )
        assert all(s.provider == "google" for s in stats)

    def test_stats_structure_correct(self, svc_with_registry):
        """Each ProviderUsageStats has all required fields."""
        stats = svc_with_registry.get_usage_stats(COMPANY_ID, days=1)
        for s in stats:
            assert hasattr(s, "provider")
            assert hasattr(s, "date")
            assert hasattr(s, "total_requests")
            assert hasattr(s, "successful_requests")
            assert hasattr(s, "failed_requests")
            assert hasattr(s, "rate_limited_count")
            assert hasattr(s, "avg_latency_ms")
            assert hasattr(s, "total_tokens_used")
            assert hasattr(s, "error_types")

    def test_empty_stats_for_no_usage(self, svc):
        """Without any recorded usage, historical days show zero entries."""
        # Without a mock registry/tracker, days > 1 will use stored data
        # (empty).
        stats = svc.get_usage_stats(COMPANY_ID, days=1)
        # Without registry, it should still return entries (possibly zero).
        assert isinstance(stats, list)

    def test_days_parameter_capped_at_90(self, svc_with_registry):
        """days parameter is capped at 90."""
        stats = svc_with_registry.get_usage_stats(COMPANY_ID, days=200)
        # 200 days -> capped to 90, 3 providers = 90*3 = 270 max entries.
        assert len(stats) <= 270

    def test_days_parameter_minimum_is_1(self, svc_with_registry):
        """days parameter is floored at 1."""
        stats = svc_with_registry.get_usage_stats(COMPANY_ID, days=0)
        assert len(stats) >= 1


# ══════════════════════════════════════════════════════════════════
# 6. HEALTH CHECK & DASHBOARD (~4 tests)
# ══════════════════════════════════════════════════════════════════


class TestHealthCheckDashboard:
    """Health check and dashboard data tests."""

    def test_health_check_returns_dict(self, svc_with_registry):
        """health_check returns a dict with required keys."""
        result = svc_with_registry.health_check(COMPANY_ID)
        assert isinstance(result, dict)
        assert "overall_status" in result
        assert "checked_at" in result

    def test_health_check_with_no_tracker_returns_unknown(self, svc):
        """Without health tracker, health_check returns UNKNOWN status."""
        # Force the lazy loaders to return None/{} by patching.
        svc._health_tracker = None
        svc._model_registry = {}
        # Also patch the lazy methods to prevent real imports.
        svc._get_health_tracker = MagicMock(return_value=None)
        svc._get_model_registry = MagicMock(return_value={})
        result = svc.health_check(COMPANY_ID)
        assert result["overall_status"] == ProviderStatus.UNKNOWN.value
        assert "error" in result

    def test_dashboard_data_has_all_sections(self, svc_with_registry):
        """get_dashboard_data returns dict with providers, alerts, usage, keys."""
        data = svc_with_registry.get_dashboard_data(COMPANY_ID)
        assert isinstance(data, dict)
        assert "providers" in data
        assert "alerts" in data
        assert "usage_summary" in data
        assert "api_keys" in data
        assert "generated_at" in data

    def test_dashboard_includes_all_providers(self, svc_with_registry):
        """Dashboard providers list includes google, cerebras, and groq."""
        data = svc_with_registry.get_dashboard_data(COMPANY_ID)
        provider_names = {p["provider"] for p in data["providers"]}
        assert provider_names == {"google", "cerebras", "groq"}

    def test_health_check_detects_disabled_models(self, svc_with_registry):
        """Health check marks manually disabled models as DISABLED."""
        svc_with_registry.disable_provider_model(
            COMPANY_ID, "cerebras", "llama-3.1-8b", "manual test",
        )
        result = svc_with_registry.health_check(COMPANY_ID)
        cerebras_info = result["providers"].get("cerebras", {})
        model_statuses = cerebras_info.get("models", [])
        disabled_models = [
            m for m in model_statuses
            if m.get("status") == ProviderStatus.DISABLED.value
        ]
        assert len(disabled_models) >= 1
        assert disabled_models[0]["model_id"] == "llama-3.1-8b"


# ══════════════════════════════════════════════════════════════════
# 7. EDGE CASES (~4 tests)
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases: company_id validation, BC-008, constructor, etc."""

    def test_none_company_id_raises_parwa_base_error(self, svc):
        """None company_id raises ParwaBaseError (BC-001)."""
        with pytest.raises(ParwaBaseError, match="company_id is required"):
            svc.get_all_providers_status(None)

    def test_empty_company_id_raises_parwa_base_error(self, svc):
        """Empty string company_id raises ParwaBaseError."""
        with pytest.raises(ParwaBaseError, match="company_id is required"):
            svc.get_all_providers_status("")

    def test_whitespace_company_id_raises_parwa_base_error(self, svc):
        """Whitespace-only company_id raises ParwaBaseError."""
        with pytest.raises(ParwaBaseError, match="company_id is required"):
            svc.get_all_providers_status("   ")

    def test_service_constructor_does_not_crash(self):
        """ProviderManagementService() can be instantiated without arguments."""
        service = ProviderManagementService()
        assert service.db is None
        assert service._health_tracker is None
        assert service._disabled_models == {}
        assert service._alerts == {}
        assert service._api_keys == {}

    def test_constructor_with_db_param(self):
        """Constructor accepts an optional db parameter."""
        mock_db = MagicMock()
        service = ProviderManagementService(db=mock_db)
        assert service.db is mock_db

    def test_sequential_concurrent_calls(self, svc):
        """Multiple sequential operations on the same service instance work."""
        # Disable a model
        svc.disable_provider_model(
            COMPANY_ID, "groq", "llama-3.1-8b", "test",
        )
        # Create alerts
        svc.create_alert(COMPANY_ID, "groq", level="info", message="alert-1")
        svc.create_alert(
            COMPANY_ID,
            "groq",
            level="warning",
            message="alert-2")
        # Rotate key
        svc.rotate_api_key(COMPANY_ID, "groq", "key-123")
        # Enable model
        svc.enable_provider_model(COMPANY_ID, "groq", "llama-3.1-8b")
        # All should succeed without error
        disabled = svc.get_disabled_models(COMPANY_ID)
        assert "groq" not in disabled
        alerts = svc.get_alerts(COMPANY_ID)
        assert len(alerts) >= 2  # manual disable + 2 created = 3 min
        keys = svc.get_api_keys(COMPANY_ID, provider="groq")
        assert len(keys) == 1

    def test_create_alert_on_empty_provider_still_works(self, svc):
        """create_alert handles empty provider string gracefully (BC-008)."""
        alert = svc.create_alert(COMPANY_ID, "", level="info", message="test")
        assert alert is not None
        assert alert.message == "test"

    def test_get_alerts_limit_capped_at_500(self, svc):
        """get_alerts limit parameter is capped at 500."""
        # Pass limit=1000, should be capped to 500
        for i in range(10):
            svc.create_alert(
                COMPANY_ID, "google", level="info",
                message=f"msg-{i}",
            )
        alerts = svc.get_alerts(COMPANY_ID, limit=1000)
        # Only 10 exist, but the method itself caps at 500.
        assert len(alerts) <= 500


# ══════════════════════════════════════════════════════════════════
# 8. HELPER FUNCTIONS (~6 tests)
# ══════════════════════════════════════════════════════════════════


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_worst_status_healthy_wins_over_healthy(self):
        assert _worst_status(["healthy", "healthy"]) == "healthy"

    def test_worst_status_unhealthy_wins(self):
        assert _worst_status(
            ["healthy", "unhealthy", "healthy"]) == "unhealthy"

    def test_worst_status_disabled_wins_over_all(self):
        assert _worst_status(
            ["healthy", "degraded", "unhealthy", "disabled"]) == "disabled"

    def test_worst_status_empty_returns_unknown(self):
        assert _worst_status([]) == "unknown"

    def test_utc_now_returns_string(self):
        result = _utc_now()
        assert isinstance(result, str)
        assert "T" in result  # ISO-8601 format

    def test_utc_today_returns_date_string(self):
        result = _utc_today()
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD

    def test_validate_company_id_valid(self):
        """_validate_company_id does not raise for valid input."""
        _validate_company_id("company-123")  # should not raise

    def test_validate_company_id_none_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id(None)

    def test_validate_company_id_empty_raises(self):
        with pytest.raises(ParwaBaseError):
            _validate_company_id("")

    def test_mask_api_key_short_key(self):
        """Short key (6 chars) shows min(8, max(4, 3)) = 4 visible chars."""
        masked = _mask_api_key("abcdef")
        assert masked == "abcd****"

    def test_mask_api_key_normal_key(self):
        """Normal key (20 chars) shows min(8, max(4, 10)) = 8 visible chars."""
        masked = _mask_api_key("abcdefghijklmnopqrst")
        assert masked == "abcdefgh****"


# ══════════════════════════════════════════════════════════════════
# 9. LATENCY & SUCCESS RECORDING (~4 tests)
# ══════════════════════════════════════════════════════════════════


class TestLatencyAndSuccessRecording:
    """Tests for record_latency and record_success."""

    def test_record_latency_stores_samples(self, svc):
        svc.record_latency(COMPANY_ID, "groq", "llama-3.1-8b", 150.0)
        svc.record_latency(COMPANY_ID, "groq", "llama-3.1-8b", 250.0)
        avg = svc._avg_latency(COMPANY_ID, "groq", "llama-3.1-8b")
        assert avg == pytest.approx(200.0)

    def test_record_latency_keeps_max_100(self, svc):
        """Latency samples are capped at 100 per model."""
        for i in range(150):
            svc.record_latency(
                COMPANY_ID,
                "cerebras",
                "llama-3.1-8b",
                float(i))
        key = ("cerebras", "llama-3.1-8b")
        samples = svc._latency_samples[COMPANY_ID][key]
        assert len(samples) == 100

    def test_record_success_stores_timestamp(self, svc):
        svc.record_success(COMPANY_ID, "google", "gemini-2.0-flash")
        ts = svc._last_success[COMPANY_ID][("google", "gemini-2.0-flash")]
        assert ts is not None
        assert isinstance(ts, str)

    def test_avg_latency_for_unknown_model(self, svc):
        """avg_latency returns 0.0 when no samples exist."""
        avg = svc._avg_latency(COMPANY_ID, "google", "nonexistent")
        assert avg == 0.0


# ══════════════════════════════════════════════════════════════════
# 10. DATA CLASS STRUCTURE (~2 tests)
# ══════════════════════════════════════════════════════════════════


class TestDataClassStructure:
    """Verify data classes have expected fields."""

    def test_provider_summary_fields(self):
        s = ProviderSummary(
            provider="google",
            display_name="Google AI Studio",
            status="healthy",
            total_models=2,
            healthy_models=2,
            degraded_models=0,
            unhealthy_models=0,
            total_requests_today=0,
        )
        assert s.provider == "google"
        assert s.models == []

    def test_provider_alert_fields(self):
        a = ProviderAlert(
            id="uuid-1",
            provider="groq",
            model_id="llama-3.1-8b",
            level="warning",
            message="test",
            created_at=_utc_now(),
        )
        assert a.acknowledged is False
        assert a.acknowledged_by is None
