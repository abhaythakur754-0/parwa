"""
Tests for Tenant Configuration Management
"""

import pytest
from datetime import datetime
from enterprise.multi_tenancy.config_manager import (
    ConfigManager, ConfigScope, ConfigType, ConfigEntry
)
from enterprise.multi_tenancy.feature_flags import (
    FeatureFlags, FeatureStatus, FeatureFlag, TenantOverride
)
from enterprise.multi_tenancy.config_validator import (
    ConfigValidator, ValidationRule, ValidationRuleType, ValidationSeverity
)


class TestConfigManager:
    """Tests for ConfigManager"""

    @pytest.fixture
    def manager(self):
        return ConfigManager()

    def test_set_global(self, manager):
        entry = manager.set_global("test_key", "test_value")
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.scope == ConfigScope.GLOBAL

    def test_set_tenant(self, manager):
        entry = manager.set_tenant("tenant_001", "test_key", "tenant_value")
        assert entry.tenant_id == "tenant_001"
        assert entry.scope == ConfigScope.TENANT

    def test_get_global(self, manager):
        manager.set_global("test_key", "global_value")
        value = manager.get("test_key")
        assert value == "global_value"

    def test_get_tenant_override(self, manager):
        manager.set_global("test_key", "global_value")
        manager.set_tenant("tenant_001", "test_key", "tenant_value")

        # Tenant override takes precedence
        value = manager.get("test_key", tenant_id="tenant_001")
        assert value == "tenant_value"

        # Global still available for other tenants
        value = manager.get("test_key", tenant_id="tenant_002")
        assert value == "global_value"

    def test_get_default(self, manager):
        # Get a default that exists
        value = manager.get("ai.model")
        assert value == "gpt-4"

    def test_get_nonexistent(self, manager):
        value = manager.get("nonexistent_key", default="default_value")
        assert value == "default_value"

    def test_get_tenant_configs(self, manager):
        manager.set_tenant("tenant_001", "custom_key", "custom_value")
        configs = manager.get_tenant_configs("tenant_001")

        assert "custom_key" in configs
        assert configs["custom_key"] == "custom_value"

    def test_delete_global(self, manager):
        manager.set_global("test_key", "test_value")
        result = manager.delete("test_key")
        assert result is True
        assert manager.get("test_key") is None

    def test_delete_tenant(self, manager):
        manager.set_tenant("tenant_001", "test_key", "test_value")
        result = manager.delete("test_key", tenant_id="tenant_001")
        assert result is True

    def test_get_history(self, manager):
        manager.set_tenant("tenant_001", "test_key", "value1", changed_by="user1")
        manager.set_tenant("tenant_001", "test_key", "value2", changed_by="user2")

        history = manager.get_history(tenant_id="tenant_001")
        assert len(history) >= 2

    def test_export_configs(self, manager):
        manager.set_global("test_key", "test_value")
        configs = manager.export_configs()
        assert "test_key" in configs

    def test_import_configs(self, manager):
        configs = {"imported_key": "imported_value"}
        count = manager.import_configs(configs)
        assert count == 1
        assert manager.get("imported_key") == "imported_value"

    def test_version_increment(self, manager):
        manager.set_global("test_key", "value1")
        entry1 = manager.get_entry("test_key")

        manager.set_global("test_key", "value2")
        entry2 = manager.get_entry("test_key")

        assert entry2.version == entry1.version + 1

    def test_get_metrics(self, manager):
        manager.set_global("test_key", "test_value")
        manager.set_tenant("tenant_001", "tenant_key", "tenant_value")

        metrics = manager.get_metrics()
        assert metrics["global_configs"] > 0
        assert metrics["tenants_with_configs"] > 0


class TestFeatureFlags:
    """Tests for FeatureFlags"""

    @pytest.fixture
    def flags(self):
        return FeatureFlags()

    def test_create_flag(self, flags):
        flag = flags.create_flag("test_feature", "Test Feature")
        assert flag.flag_id == "test_feature"
        assert flag.status == FeatureStatus.DISABLED

    def test_is_enabled_disabled(self, flags):
        flags.create_flag("test_feature", "Test", status=FeatureStatus.DISABLED)
        assert flags.is_enabled("test_feature", "tenant_001") is False

    def test_is_enabled_enabled(self, flags):
        flags.create_flag("test_feature", "Test", status=FeatureStatus.ENABLED)
        assert flags.is_enabled("test_feature", "tenant_001") is True

    def test_enable(self, flags):
        flags.create_flag("test_feature", "Test")
        flags.enable("test_feature")
        assert flags.is_enabled("test_feature", "tenant_001") is True

    def test_disable(self, flags):
        flags.create_flag("test_feature", "Test", status=FeatureStatus.ENABLED)
        flags.disable("test_feature")
        assert flags.is_enabled("test_feature", "tenant_001") is False

    def test_rollout_percentage(self, flags):
        flags.create_flag("test_feature", "Test")
        flags.set_rollout_percentage("test_feature", 50)

        flag = flags.get_flag("test_feature")
        assert flag.status == FeatureStatus.PERCENTAGE
        assert flag.rollout_percentage == 50

    def test_whitelist(self, flags):
        flags.create_flag("test_feature", "Test")
        flags.add_to_whitelist("test_feature", "tenant_001")

        assert flags.is_enabled("test_feature", "tenant_001") is True
        assert flags.is_enabled("test_feature", "tenant_002") is False

    def test_tenant_override(self, flags):
        flags.create_flag("test_feature", "Test", status=FeatureStatus.DISABLED)
        flags.set_tenant_override("tenant_001", "test_feature", True)

        assert flags.is_enabled("test_feature", "tenant_001") is True
        assert flags.is_enabled("test_feature", "tenant_002") is False

    def test_clear_tenant_override(self, flags):
        flags.create_flag("test_feature", "Test", status=FeatureStatus.DISABLED)
        flags.set_tenant_override("tenant_001", "test_feature", True)
        flags.clear_tenant_override("tenant_001", "test_feature")

        assert flags.is_enabled("test_feature", "tenant_001") is False

    def test_get_tenant_flags(self, flags):
        result = flags.get_tenant_flags("tenant_001")
        assert isinstance(result, dict)

    def test_get_metrics(self, flags):
        flags.create_flag("test_feature", "Test")
        flags.is_enabled("test_feature", "tenant_001")

        metrics = flags.get_metrics()
        assert metrics["total_flags"] > 0
        assert metrics["total_checks"] > 0


class TestConfigValidator:
    """Tests for ConfigValidator"""

    @pytest.fixture
    def validator(self):
        return ConfigValidator()

    def test_validate_valid_config(self, validator):
        config = {
            "ai.temperature": 0.7,
            "ai.max_tokens": 2048,
            "limits.max_users": 100
        }
        result = validator.validate(config)
        assert result.is_valid is True

    def test_validate_invalid_range(self, validator):
        config = {
            "ai.temperature": 5.0  # Out of range
        }
        result = validator.validate(config)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_invalid_type(self, validator):
        config = {
            "limits.max_users": "not_an_integer"
        }
        result = validator.validate(config)
        assert result.is_valid is False

    def test_validate_key(self, validator):
        result = validator.validate_key("ai.temperature", 0.5)
        assert result.is_valid is True

    def test_validate_value_type(self, validator):
        result = validator.validate_value("test", expected_type="string")
        assert result.is_valid is True

    def test_validate_value_type_invalid(self, validator):
        result = validator.validate_value("test", expected_type="integer")
        assert result.is_valid is False

    def test_validate_value_range(self, validator):
        result = validator.validate_value(50, min_val=0, max_val=100)
        assert result.is_valid is True

    def test_validate_value_range_invalid(self, validator):
        result = validator.validate_value(150, min_val=0, max_val=100)
        assert result.is_valid is False

    def test_validate_value_pattern(self, validator):
        result = validator.validate_value("gpt-4", pattern=r"^gpt-")
        assert result.is_valid is True

    def test_validate_value_enum(self, validator):
        result = validator.validate_value("option1", allowed_values=["option1", "option2"])
        assert result.is_valid is True

    def test_add_rule(self, validator):
        rule = ValidationRule(
            rule_id="custom_rule",
            key_pattern=r"^custom\.",
            rule_type=ValidationRuleType.REQUIRED,
            message="Custom field required"
        )
        validator.add_rule(rule)

        rules = validator.get_all_rules()
        assert any(r.rule_id == "custom_rule" for r in rules)

    def test_remove_rule(self, validator):
        validator.add_rule(ValidationRule(
            rule_id="to_remove",
            key_pattern=r"^test\.",
            rule_type=ValidationRuleType.REQUIRED
        ))
        result = validator.remove_rule("to_remove")
        assert result is True

    def test_get_rules_for_key(self, validator):
        rules = validator.get_rules_for_key("ai.temperature")
        assert len(rules) > 0


class TestConfigIntegration:
    """Integration tests"""

    def test_full_config_workflow(self):
        # Setup
        config_manager = ConfigManager()
        feature_flags = FeatureFlags()
        validator = ConfigValidator()

        # Set and validate config
        config = {
            "ai.temperature": 0.8,
            "ai.max_tokens": 2048
        }

        result = validator.validate(config)
        assert result.is_valid is True

        # Apply config
        for key, value in config.items():
            config_manager.set_tenant("tenant_001", key, value)

        # Check feature flag
        feature_flags.create_flag("advanced_ai", "Advanced AI Features")
        feature_flags.set_tenant_override("tenant_001", "advanced_ai", True)

        assert feature_flags.is_enabled("advanced_ai", "tenant_001") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
