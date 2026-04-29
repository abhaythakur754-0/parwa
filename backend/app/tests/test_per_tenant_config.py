"""
Comprehensive unit tests for per_tenant_config module.

Tests: 65+
Categories:
  - Default config per variant (5)
  - Per-company overrides (6)
  - Config merging (6)
  - Config validation (12)
  - Config versioning (6)
  - Config reset (5)
  - Config export/import (8)
  - Change notifications (6)
  - Thread safety (4)
  - Edge cases (7)
"""

import json
import threading
from dataclasses import asdict

import pytest
from app.core.per_tenant_config import (
    VALID_LEVELS,
    VALID_STRATEGIES,
    VALID_VARIANT_TYPES,
    VARIANT_DEFAULTS,
    TenantConfigManager,
    TenantFullConfig,
)

# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def manager() -> TenantConfigManager:
    """Fresh config manager for each test."""
    return TenantConfigManager(default_variant="parwa")


@pytest.fixture
def manager_mini() -> TenantConfigManager:
    """Config manager with mini_parwa default."""
    return TenantConfigManager(default_variant="mini_parwa")


@pytest.fixture
def manager_high() -> TenantConfigManager:
    """Config manager with high_parwa default."""
    return TenantConfigManager(default_variant="high_parwa")


# ── Default Config per Variant ──────────────────────────────────


class TestDefaultConfigPerVariant:
    """Tests for default configurations per variant type."""

    def test_default_variant_is_parwa(self, manager):
        config = manager.get_config("new_company")
        assert config.workflow.variant_type == "parwa"

    def test_mini_parwa_defaults(self, manager_mini):
        config = manager_mini.get_config("company_a")
        assert config.workflow.variant_type == "mini_parwa"
        assert config.technique.token_budget_override == 500
        assert config.compression.strategy == "extractive"
        assert config.compression.level == "aggressive"
        assert "chain_of_thought" in config.technique.disabled_techniques
        assert config.model.preferred_model_tier == "light"
        assert config.model.temperature == 0.1
        assert not config.workflow.enable_human_checkpoint

    def test_parwa_defaults(self, manager):
        config = manager.get_config("company_b")
        assert config.workflow.variant_type == "parwa"
        assert config.technique.token_budget_override == 1500
        assert config.compression.strategy == "hybrid"
        assert config.compression.level == "moderate"
        assert "reflexion" in config.technique.disabled_techniques
        assert config.model.preferred_model_tier == "medium"
        assert config.workflow.enable_human_checkpoint is True
        assert config.workflow.max_concurrent_workflows == 5

    def test_high_parwa_defaults(self, manager_high):
        config = manager_high.get_config("company_c")
        assert config.workflow.variant_type == "high_parwa"
        assert config.technique.token_budget_override == 3000
        assert config.compression.strategy == "priority_based"
        assert config.compression.level == "light"
        assert config.technique.disabled_techniques == []
        assert "reflexion" in config.technique.enabled_techniques
        assert config.model.preferred_model_tier == "heavy"
        assert config.model.temperature == 0.5

    def test_get_defaults_returns_fresh_copy(self, manager):
        d1 = manager.get_defaults("parwa")
        d2 = manager.get_defaults("parwa")
        assert d1 is not d2
        assert asdict(d1) == asdict(d2)

    def test_get_defaults_invalid_variant(self, manager):
        with pytest.raises(ValueError, match="Invalid variant_type"):
            manager.get_defaults("nonexistent")

    def test_all_variant_types_have_defaults(self):
        for vt in VALID_VARIANT_TYPES:
            assert vt in VARIANT_DEFAULTS


# ── Per-Company Overrides ───────────────────────────────────────


class TestPerCompanyOverrides:
    """Tests for per-company configuration overrides."""

    def test_override_technique_config(self, manager):
        manager.update_config(
            "acme",
            "technique",
            {"token_budget_override": 2500},
        )
        config = manager.get_config("acme")
        assert config.technique.token_budget_override == 2500

    def test_override_compression_config(self, manager):
        manager.update_config(
            "acme",
            "compression",
            {"strategy": "extractive", "level": "aggressive"},
        )
        config = manager.get_config("acme")
        assert config.compression.strategy == "extractive"
        assert config.compression.level == "aggressive"

    def test_override_workflow_config(self, manager):
        manager.update_config(
            "acme",
            "workflow",
            {"max_concurrent_workflows": 20},
        )
        config = manager.get_config("acme")
        assert config.workflow.max_concurrent_workflows == 20

    def test_override_model_config(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.8, "max_tokens": 8192},
        )
        config = manager.get_config("acme")
        assert config.model.temperature == 0.8
        assert config.model.max_tokens == 8192

    def test_override_does_not_affect_other_tenants(self, manager):
        manager.update_config(
            "acme",
            "technique",
            {"token_budget_override": 9999},
        )
        other = manager.get_config("other_co")
        assert other.technique.token_budget_override != 9999

    def test_multiple_overrides_same_tenant(self, manager):
        manager.update_config(
            "acme",
            "technique",
            {"token_budget_override": 2000},
        )
        manager.update_config(
            "acme",
            "compression",
            {"level": "aggressive"},
        )
        config = manager.get_config("acme")
        assert config.technique.token_budget_override == 2000
        assert config.compression.level == "aggressive"


# ── Config Merging ──────────────────────────────────────────────


class TestConfigMerging:
    """Tests for default + override merging behavior."""

    def test_merge_preserves_non_overridden_defaults(self, manager):
        """Overriding one field does not change others."""
        manager.update_config(
            "acme",
            "technique",
            {"token_budget_override": 999},
        )
        config = manager.get_config("acme")
        # Should still have parwa defaults for other fields
        assert config.compression.strategy == "hybrid"
        assert config.model.temperature == 0.3
        assert config.workflow.variant_type == "parwa"

    def test_merge_overrides_all_technique_fields(self, manager):
        manager.update_config(
            "acme",
            "technique",
            {
                "enabled_techniques": ["a", "b"],
                "disabled_techniques": ["c"],
                "custom_thresholds": {"x": 0.5},
                "token_budget_override": 100,
            },
        )
        config = manager.get_config("acme")
        assert config.technique.enabled_techniques == ["a", "b"]
        assert config.technique.disabled_techniques == ["c"]
        assert config.technique.custom_thresholds == {"x": 0.5}
        assert config.technique.token_budget_override == 100

    def test_variant_change_via_workflow_override(self, manager):
        manager.update_config(
            "acme",
            "workflow",
            {"variant_type": "high_parwa"},
        )
        config = manager.get_config("acme")
        assert config.workflow.variant_type == "high_parwa"

    def test_new_tenant_gets_default_variant(self, manager):
        config = manager.get_config("brand_new")
        assert config.workflow.variant_type == "parwa"

    def test_overridden_tenant_keeps_variant(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.7},
        )
        config = manager.get_config("acme")
        # variant_type should still be parwa default
        assert config.workflow.variant_type == "parwa"

    def test_tenant_without_overrides_is_default(self, manager):
        config = manager.get_config("no_overrides_co")
        defaults = manager.get_defaults("parwa")
        assert asdict(config) == asdict(defaults)


# ── Config Validation ───────────────────────────────────────────


class TestConfigValidation:
    """Tests for configuration validation logic."""

    def test_valid_technique_config(self, manager):
        result = manager.validate_config(
            "technique",
            {"token_budget_override": 500},
        )
        assert result.valid is True
        assert result.errors == []

    def test_invalid_category(self, manager):
        result = manager.validate_config(
            "nonexistent",
            {},
        )
        assert result.valid is False
        assert any("Unknown category" in e for e in result.errors)

    def test_unknown_field_in_category(self, manager):
        result = manager.validate_config(
            "model",
            {"nonexistent_field": "value"},
        )
        assert result.valid is False
        assert any("Unknown field" in e for e in result.errors)

    def test_wrong_type_int_instead_of_str(self, manager):
        result = manager.validate_config(
            "compression",
            {"strategy": 123},
        )
        assert result.valid is False
        assert any("expected" in e for e in result.errors)

    def test_wrong_type_str_instead_of_bool(self, manager):
        result = manager.validate_config(
            "workflow",
            {"enable_human_checkpoint": "yes"},
        )
        assert result.valid is False

    def test_invalid_strategy_value(self, manager):
        result = manager.validate_config(
            "compression",
            {"strategy": "invalid_strategy"},
        )
        assert result.valid is False
        assert any("Invalid strategy" in e for e in result.errors)

    def test_invalid_level_value(self, manager):
        result = manager.validate_config(
            "compression",
            {"level": "extreme"},
        )
        assert result.valid is False
        assert any("Invalid level" in e for e in result.errors)

    def test_invalid_variant_type(self, manager):
        result = manager.validate_config(
            "workflow",
            {"variant_type": "super_parwa"},
        )
        assert result.valid is False
        assert any("Invalid variant_type" in e for e in result.errors)

    def test_invalid_model_tier(self, manager):
        result = manager.validate_config(
            "model",
            {"preferred_model_tier": "ultra"},
        )
        assert result.valid is False
        assert any("Invalid preferred_model_tier" in e for e in result.errors)

    def test_temperature_out_of_range_warning(self, manager):
        result = manager.validate_config(
            "model",
            {"temperature": 5.0},
        )
        # Should be valid (just a warning)
        assert result.valid is True
        assert any("Temperature" in w for w in result.warnings)

    def test_negative_max_tokens_error(self, manager):
        result = manager.validate_config(
            "compression",
            {"max_tokens": -1},
        )
        assert result.valid is False
        assert any("positive" in e for e in result.errors)

    def test_negative_token_budget_override_error(self, manager):
        result = manager.validate_config(
            "technique",
            {"token_budget_override": -10},
        )
        assert result.valid is False

    def test_none_token_budget_override_valid(self, manager):
        result = manager.validate_config(
            "technique",
            {"token_budget_override": None},
        )
        assert result.valid is True

    def test_invalid_threshold_type(self, manager):
        result = manager.validate_config(
            "technique",
            {"custom_thresholds": {"x": "not_a_number"}},
        )
        assert result.valid is False

    def test_valid_custom_thresholds(self, manager):
        result = manager.validate_config(
            "technique",
            {"custom_thresholds": {"confidence": 0.95}},
        )
        assert result.valid is True

    def test_negative_max_concurrent_workflows(self, manager):
        result = manager.validate_config(
            "workflow",
            {"max_concurrent_workflows": -5},
        )
        assert result.valid is False

    def test_all_valid_strategies(self):
        for strategy in VALID_STRATEGIES:
            mgr = TenantConfigManager()
            result = mgr.validate_config(
                "compression",
                {"strategy": strategy},
            )
            assert result.valid is True, f"Strategy {strategy} failed"

    def test_all_valid_levels(self):
        for level in VALID_LEVELS:
            mgr = TenantConfigManager()
            result = mgr.validate_config(
                "compression",
                {"level": level},
            )
            assert result.valid is True, f"Level {level} failed"


# ── Config Versioning ───────────────────────────────────────────


class TestConfigVersioning:
    """Tests for configuration version tracking."""

    def test_first_update_increments_version(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        history = manager.get_version_history("acme")
        assert len(history) == 1
        assert history[0]["version"] == 1
        assert history[0]["category"] == "model"

    def test_multiple_updates_increment_version(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        manager.update_config(
            "acme",
            "compression",
            {"level": "aggressive"},
        )
        history = manager.get_version_history("acme")
        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[1]["version"] == 2

    def test_version_history_includes_timestamp(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        history = manager.get_version_history("acme")
        assert "timestamp" in history[0]
        assert len(history[0]["timestamp"]) > 0

    def test_version_history_includes_changes(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        history = manager.get_version_history("acme")
        assert "changes" in history[0]
        assert history[0]["changes"]["temperature"] == 0.5

    def test_version_history_for_unknown_tenant(self, manager):
        history = manager.get_version_history("nonexistent")
        assert history == []

    def test_version_resets_on_full_reset(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        manager.reset_to_defaults("acme")
        history = manager.get_version_history("acme")
        assert history == []


# ── Config Reset ────────────────────────────────────────────────


class TestConfigReset:
    """Tests for configuration reset functionality."""

    def test_full_reset_returns_defaults(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.9},
        )
        config = manager.reset_to_defaults("acme")
        assert config.model.temperature == 0.3  # parwa default

    def test_category_reset_keeps_other_overrides(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.9},
        )
        manager.update_config(
            "acme",
            "compression",
            {"level": "aggressive"},
        )
        manager.reset_to_defaults("acme", category="model")
        config = manager.get_config("acme")
        assert config.model.temperature == 0.3
        assert config.compression.level == "aggressive"

    def test_reset_unknown_category_raises(self, manager):
        with pytest.raises(ValueError, match="Invalid category"):
            manager.reset_to_defaults("acme", category="nonexistent")

    def test_reset_unknown_tenant_returns_defaults(self, manager):
        config = manager.reset_to_defaults("nonexistent")
        assert isinstance(config, TenantFullConfig)

    def test_reset_clears_version_history(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.9},
        )
        manager.reset_to_defaults("acme", category="model")
        # Category was last override, so full cleanup
        history = manager.get_version_history("acme")
        assert history == []


# ── Config Export / Import ──────────────────────────────────────


class TestConfigExportImport:
    """Tests for JSON export and import."""

    def test_export_returns_valid_json(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.7},
        )
        exported = manager.export_config("acme")
        data = json.loads(exported)
        assert data["company_id"] == "acme"
        assert "full_config" in data
        assert "overrides" in data

    def test_export_includes_overrides(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.7},
        )
        exported = manager.export_config("acme")
        data = json.loads(exported)
        assert data["overrides"]["model"]["temperature"] == 0.7

    def test_export_unknown_tenant(self, manager):
        exported = manager.export_config("nonexistent")
        data = json.loads(exported)
        assert data["company_id"] == "nonexistent"
        assert data["overrides"] == {}

    def test_import_valid_config(self, manager):
        json_str = json.dumps(
            {
                "overrides": {
                    "model": {"temperature": 0.9},
                    "compression": {"level": "aggressive"},
                }
            }
        )
        result = manager.import_config("acme", json_str)
        assert result.valid is True

        config = manager.get_config("acme")
        assert config.model.temperature == 0.9
        assert config.compression.level == "aggressive"

    def test_import_invalid_json(self, manager):
        result = manager.import_config("acme", "not json")
        assert result.valid is False
        assert any("JSON" in e for e in result.errors)

    def test_import_non_object_json(self, manager):
        result = manager.import_config("acme", "[1,2,3]")
        assert result.valid is False

    def test_import_invalid_config_values(self, manager):
        json_str = json.dumps(
            {
                "overrides": {
                    "model": {"temperature": "not_a_number"},
                }
            }
        )
        result = manager.import_config("acme", json_str)
        assert result.valid is False

    def test_import_from_full_config(self, manager):
        json_str = json.dumps(
            {
                "full_config": {
                    "model": {"temperature": 0.8},
                }
            }
        )
        result = manager.import_config("acme", json_str)
        assert result.valid is True
        config = manager.get_config("acme")
        assert config.model.temperature == 0.8

    def test_roundtrip_export_import(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.7},
        )
        exported = manager.export_config("acme")

        # Import into a different tenant
        result = manager.import_config("new_co", exported)
        assert result.valid is True

        config_acme = manager.get_config("acme")
        config_new = manager.get_config("new_co")
        assert config_acme.model.temperature == config_new.model.temperature


# ── Change Notifications ────────────────────────────────────────


class TestChangeNotifications:
    """Tests for config change callback system."""

    def test_callback_fired_on_update(self, manager):
        received = []
        manager.on_config_change(lambda cid, cat, chg: received.append((cid, cat, chg)))
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.7},
        )
        assert len(received) == 1
        assert received[0] == (
            "acme",
            "model",
            {"temperature": 0.7},
        )

    def test_callback_not_fired_on_get(self, manager):
        received = []
        manager.on_config_change(lambda cid, cat, chg: received.append(True))
        manager.get_config("acme")
        assert len(received) == 0

    def test_multiple_callbacks(self, manager):
        r1, r2 = [], []
        manager.on_config_change(lambda cid, cat, chg: r1.append(True))
        manager.on_config_change(lambda cid, cat, chg: r2.append(True))
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        assert len(r1) == 1
        assert len(r2) == 1

    def test_remove_callback(self, manager):
        received = []

        def cb(cid, cat, chg):
            return received.append(True)

        manager.on_config_change(cb)
        manager.remove_config_change_callback(cb)
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        assert len(received) == 0

    def test_remove_nonexistent_callback(self, manager):
        result = manager.remove_config_change_callback(lambda: None)
        assert result is False

    def test_callback_error_does_not_break_update(self, manager):

        def bad_cb(cid, cat, chg):
            raise RuntimeError("callback error")

        manager.on_config_change(bad_cb)
        config = manager.update_config(
            "acme",
            "model",
            {"temperature": 0.7},
        )
        assert config.model.temperature == 0.7


# ── Thread Safety ───────────────────────────────────────────────


class TestThreadSafety:
    """Tests for concurrent access safety."""

    def test_concurrent_updates(self, manager):
        """Multiple threads updating different tenants."""
        errors = []

        def update_tenant(tenant_id):
            try:
                for i in range(50):
                    manager.update_config(
                        tenant_id,
                        "model",
                        {"temperature": float(i) / 100},
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=update_tenant, args=(f"t{i}",)) for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(manager.list_tenants()) == 10

    def test_concurrent_same_tenant(self, manager):
        """Multiple threads updating same tenant."""
        errors = []

        def update_model():
            try:
                for i in range(100):
                    manager.update_config(
                        "acme",
                        "model",
                        {"temperature": float(i % 100) / 100},
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=update_model) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_read_write(self, manager):
        """Concurrent reads while writing."""
        errors = []

        def reader():
            try:
                for _ in range(100):
                    manager.get_config("acme")
            except Exception as exc:
                errors.append(exc)

        def writer():
            try:
                for i in range(100):
                    manager.update_config(
                        "acme",
                        "model",
                        {"temperature": float(i) / 100},
                    )
            except Exception as exc:
                errors.append(exc)

        t_read = threading.Thread(target=reader)
        t_write = threading.Thread(target=writer)
        t_read.start()
        t_write.start()
        t_read.join()
        t_write.join()

        assert len(errors) == 0

    def test_concurrent_list_tenants(self, manager):
        """Concurrent list_tenants calls."""
        errors = []

        def lister():
            try:
                for _ in range(100):
                    manager.list_tenants()
            except Exception as exc:
                errors.append(exc)

        def updater():
            try:
                for i in range(50):
                    manager.update_config(
                        f"co_{i}",
                        "model",
                        {"temperature": 0.5},
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=lister),
            threading.Thread(target=lister),
            threading.Thread(target=updater),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ── Tenant Listing ──────────────────────────────────────────────


class TestTenantListing:
    """Tests for list_tenants functionality."""

    def test_empty_manager_has_no_tenants(self, manager):
        assert manager.list_tenants() == []

    def test_list_tenants_after_updates(self, manager):
        manager.update_config(
            "acme",
            "model",
            {"temperature": 0.5},
        )
        manager.update_config(
            "beta",
            "model",
            {"temperature": 0.5},
        )
        tenants = manager.list_tenants()
        assert tenants == ["acme", "beta"]

    def test_list_tenants_sorted(self, manager):
        manager.update_config(
            "charlie",
            "model",
            {"temperature": 0.5},
        )
        manager.update_config(
            "alpha",
            "model",
            {"temperature": 0.5},
        )
        tenants = manager.list_tenants()
        assert tenants == ["alpha", "charlie"]


# ── Edge Cases ──────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_default_variant(self):
        with pytest.raises(ValueError, match="Invalid default_variant"):
            TenantConfigManager(default_variant="invalid")

    def test_update_invalid_category(self, manager):
        with pytest.raises(ValueError, match="Invalid category"):
            manager.update_config(
                "acme",
                "nonexistent",
                {},
            )

    def test_update_invalid_config_raises(self, manager):
        with pytest.raises(ValueError, match="validation failed"):
            manager.update_config(
                "acme",
                "model",
                {"temperature": "not_a_float"},
            )

    def test_update_invalid_strategy_raises(self, manager):
        with pytest.raises(ValueError):
            manager.update_config(
                "acme",
                "compression",
                {"strategy": "bad_strategy"},
            )

    def test_empty_company_id_allowed(self, manager):
        """Empty string company_id is technically allowed
        (validation is at API layer, BC-001)."""
        config = manager.get_config("")
        assert isinstance(config, TenantFullConfig)

    def test_get_config_with_special_chars(self, manager):
        config = manager.get_config("company-123_test")
        assert isinstance(config, TenantFullConfig)

    def test_large_number_of_overrides(self, manager):
        for i in range(100):
            manager.update_config(
                f"co_{i}",
                "model",
                {"temperature": float(i) / 100},
            )
        assert len(manager.list_tenants()) == 100

    def test_export_empty_tenant(self, manager):
        exported = manager.export_config("no_one")
        data = json.loads(exported)
        assert data["company_id"] == "no_one"
        assert data["overrides"] == {}
        assert data["version"] == 0

    def test_import_empty_overrides(self, manager):
        result = manager.import_config("acme", '{"overrides": {}}')
        assert result.valid is True

    def test_update_with_empty_dict(self, manager):
        """Empty dict is valid — no changes made."""
        config = manager.update_config("acme", "model", {})
        assert isinstance(config, TenantFullConfig)
        history = manager.get_version_history("acme")
        assert len(history) == 1

    def test_reset_category_on_tenant_with_no_overrides(self, manager):
        """Reset on unknown tenant should return defaults."""
        config = manager.reset_to_defaults(
            "nobody",
            category="model",
        )
        assert isinstance(config, TenantFullConfig)
