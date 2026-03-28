"""
Week 60 - Builder 4 Tests: Configuration Manager Module
Unit tests for Config Manager, Secret Manager, and Feature Flags
"""

import pytest
from parwa_final_release.config_manager import (
    ConfigManager, ConfigEntry, ConfigSource,
    SecretManager, Secret,
    FeatureFlags, FeatureFlag, FeatureStatus
)


class TestConfigManager:
    """Tests for ConfigManager class"""

    @pytest.fixture
    def manager(self):
        """Create config manager"""
        return ConfigManager()

    def test_set_config(self, manager):
        """Test setting config"""
        entry = manager.set_config("database_url", "postgres://localhost")

        assert entry.key == "database_url"
        assert entry.value == "postgres://localhost"

    def test_get_config(self, manager):
        """Test getting config"""
        manager.set_config("key", "value")

        value = manager.get_config("key")
        assert value == "value"

    def test_get_config_default(self, manager):
        """Test getting config with default"""
        value = manager.get_config("nonexistent", default="default_value")
        assert value == "default_value"

    def test_set_override(self, manager):
        """Test setting override"""
        manager.set_config("key", "value")
        manager.set_override("production", "key", "prod_value")

        value = manager.get_config("key", environment="production")
        assert value == "prod_value"

    def test_remove_override(self, manager):
        """Test removing override"""
        manager.set_override("prod", "key", "value")
        result = manager.remove_override("prod", "key")

        assert result is True

    def test_get_history(self, manager):
        """Test getting history"""
        manager.set_config("key", "value1")
        manager.set_config("key", "value2")

        history = manager.get_history("key")
        assert len(history) == 1

    def test_list_configs(self, manager):
        """Test listing configs"""
        manager.set_config("key1", "value1")
        manager.set_config("key2", "value2")

        keys = manager.list_configs()
        assert len(keys) == 2

    def test_delete_config(self, manager):
        """Test deleting config"""
        manager.set_config("key", "value")
        result = manager.delete_config("key")

        assert result is True
        assert manager.get_config("key") is None

    def test_export_configs(self, manager):
        """Test exporting configs"""
        manager.set_config("key1", "value1")
        manager.set_config("key2", "value2")

        exported = manager.export_configs()
        assert exported["key1"] == "value1"
        assert exported["key2"] == "value2"


class TestSecretManager:
    """Tests for SecretManager class"""

    @pytest.fixture
    def manager(self):
        """Create secret manager"""
        return SecretManager()

    def test_store_secret(self, manager):
        """Test storing secret"""
        secret = manager.store_secret("api_key", "secret_value")

        assert secret.name == "api_key"
        assert secret.version == 1

    def test_get_secret(self, manager):
        """Test getting secret"""
        manager.store_secret("api_key", "secret_value")

        value = manager.get_secret("api_key")
        assert value is not None

    def test_get_nonexistent_secret(self, manager):
        """Test getting nonexistent secret"""
        value = manager.get_secret("nonexistent")
        assert value is None

    def test_rotate_secret(self, manager):
        """Test rotating secret"""
        manager.store_secret("api_key", "old_value")
        secret = manager.rotate_secret("api_key", "new_value")

        assert secret.version == 2

    def test_delete_secret(self, manager):
        """Test deleting secret"""
        manager.store_secret("api_key", "value")
        result = manager.delete_secret("api_key")

        assert result is True
        assert manager.get_secret("api_key") is None

    def test_list_secrets(self, manager):
        """Test listing secrets"""
        manager.store_secret("key1", "value1")
        manager.store_secret("key2", "value2")

        secrets = manager.list_secrets()
        assert len(secrets) == 2

    def test_get_audit_log(self, manager):
        """Test getting audit log"""
        manager.store_secret("key", "value")
        manager.get_secret("key")

        log = manager.get_audit_log("key")
        assert len(log) >= 2


class TestFeatureFlags:
    """Tests for FeatureFlags class"""

    @pytest.fixture
    def flags(self):
        """Create feature flags"""
        return FeatureFlags()

    def test_create_flag(self, flags):
        """Test creating flag"""
        flag = flags.create_flag("new_feature", "New feature description")

        assert flag.name == "new_feature"
        assert flag.status == FeatureStatus.DISABLED

    def test_enable_flag(self, flags):
        """Test enabling flag"""
        flags.create_flag("feature")
        result = flags.enable("feature")

        assert result is True
        assert flags.get_flag("feature").status == FeatureStatus.ENABLED

    def test_disable_flag(self, flags):
        """Test disabling flag"""
        flags.create_flag("feature")
        flags.enable("feature")
        result = flags.disable("feature")

        assert result is True
        assert flags.get_flag("feature").status == FeatureStatus.DISABLED

    def test_set_percentage(self, flags):
        """Test setting percentage"""
        flags.create_flag("feature")
        result = flags.set_percentage("feature", 50)

        assert result is True
        assert flags.get_flag("feature").percentage == 50

    def test_add_target(self, flags):
        """Test adding target"""
        flags.create_flag("feature")
        result = flags.add_target("feature", "user123")

        assert result is True
        assert "user123" in flags.get_flag("feature").targets

    def test_remove_target(self, flags):
        """Test removing target"""
        flags.create_flag("feature")
        flags.add_target("feature", "user123")
        result = flags.remove_target("feature", "user123")

        assert result is True
        assert "user123" not in flags.get_flag("feature").targets

    def test_is_enabled_for_enabled(self, flags):
        """Test is_enabled for enabled flag"""
        flags.create_flag("feature")
        flags.enable("feature")

        assert flags.is_enabled("feature") is True

    def test_is_enabled_for_disabled(self, flags):
        """Test is_enabled for disabled flag"""
        flags.create_flag("feature")

        assert flags.is_enabled("feature") is False

    def test_is_enabled_for_targeted(self, flags):
        """Test is_enabled for targeted flag"""
        flags.create_flag("feature")
        flags.add_target("feature", "user123")

        assert flags.is_enabled("feature", "user123") is True
        assert flags.is_enabled("feature", "other_user") is False

    def test_is_enabled_for_percentage(self, flags):
        """Test is_enabled for percentage rollout"""
        flags.create_flag("feature")
        flags.set_percentage("feature", 100)

        # With 100% rollout, should be enabled
        assert flags.is_enabled("feature", "any_user") is True

    def test_get_flag(self, flags):
        """Test getting flag"""
        flags.create_flag("feature")
        flag = flags.get_flag("feature")

        assert flag.name == "feature"

    def test_list_flags(self, flags):
        """Test listing flags"""
        flags.create_flag("feature1")
        flags.create_flag("feature2")

        flag_names = flags.list_flags()
        assert len(flag_names) == 2

    def test_delete_flag(self, flags):
        """Test deleting flag"""
        flags.create_flag("feature")
        result = flags.delete_flag("feature")

        assert result is True
        assert flags.get_flag("feature") is None
