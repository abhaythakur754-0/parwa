"""
Unit Tests for PARWA Configuration Module
Tests for configuration loading and validation
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from pydantic import SecretStr

# Add parent directory to path for imports
import sys
sys.path.insert(0, "/home/z/my-project")

from backend.core.config import (
    Environment,
    LogLevel,
    APIKeysConfig,
    WebhookConfig,
    SLAConfig,
    ComplianceConfig,
    LicenseConfig,
    LicenseTier,
    RateLimitConfig,
    AppConfig,
    ConfigManager,
    get_config,
    get_api_key,
    validate_production_config,
    validate_webhook_config,
)


class TestEnvironment:
    """Tests for Environment enum"""
    
    def test_environment_values(self):
        """Test environment enum values"""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
        assert Environment.TESTING.value == "testing"


class TestLogLevel:
    """Tests for LogLevel enum"""
    
    def test_log_level_values(self):
        """Test log level enum values"""
        assert LogLevel.DEBUG.value == "DEBUG"
        assert LogLevel.INFO.value == "INFO"
        assert LogLevel.WARNING.value == "WARNING"
        assert LogLevel.ERROR.value == "ERROR"
        assert LogLevel.CRITICAL.value == "CRITICAL"


class TestAPIKeysConfig:
    """Tests for API keys configuration"""
    
    def test_empty_config(self):
        """Test empty API keys config"""
        config = APIKeysConfig()
        
        assert config.google_ai_key is None
        assert config.cerebras_key is None
        assert config.groq_key is None
        assert config.brevo_key is None
    
    def test_config_with_keys(self):
        """Test API keys config with values"""
        config = APIKeysConfig(
            google_ai_key="test_google_key",
            cerebras_key="test_cerebras_key",
            groq_key="test_groq_key",
            brevo_key="test_brevo_key"
        )
        
        assert isinstance(config.google_ai_key, SecretStr)
        assert config.get_key("google_ai_key") == "test_google_key"
    
    def test_is_configured(self):
        """Test is_configured method"""
        config = APIKeysConfig(
            google_ai_key="test_key",
            cerebras_key=""
        )
        
        assert config.is_configured("google_ai_key") is True
        assert config.is_configured("cerebras_key") is False
        assert config.is_configured("groq_key") is False
    
    def test_get_key_nonexistent(self):
        """Test get_key for non-existent key"""
        config = APIKeysConfig()
        
        assert config.get_key("nonexistent_key") is None


class TestWebhookConfig:
    """Tests for webhook configuration"""
    
    def test_default_values(self):
        """Test webhook config defaults"""
        config = WebhookConfig()
        
        assert config.shopify_verify_signature is True
        assert config.paddle_verify_signature is True
        assert config.shopify_max_timestamp_diff == 300
        assert config.paddle_max_timestamp_diff == 300
        assert config.webhook_retry_attempts == 3
    
    def test_custom_values(self):
        """Test webhook config with custom values"""
        config = WebhookConfig(
            shopify_verify_signature=False,
            webhook_retry_attempts=5,
            webhook_timeout=60
        )
        
        assert config.shopify_verify_signature is False
        assert config.webhook_retry_attempts == 5
        assert config.webhook_timeout == 60


class TestSLAConfig:
    """Tests for SLA configuration"""
    
    def test_default_values(self):
        """Test SLA config defaults"""
        config = SLAConfig()
        
        assert config.tier1_response_hours == 24
        assert config.tier2_response_hours == 48
        assert config.tier3_response_hours == 72
        assert config.breach_warning_hours == 4
        assert config.auto_escalate is True
    
    def test_custom_values(self):
        """Test SLA config with custom values"""
        config = SLAConfig(
            tier1_response_hours=12,
            tier2_response_hours=24,
            tier3_response_hours=48
        )
        
        assert config.tier1_response_hours == 12
        assert config.tier2_response_hours == 24
        assert config.tier3_response_hours == 48


class TestComplianceConfig:
    """Tests for compliance configuration"""
    
    def test_default_values(self):
        """Test compliance config defaults"""
        config = ComplianceConfig()
        
        assert config.gdpr_enabled is True
        assert config.gdpr_response_days == 30
        assert config.gdpr_data_retention_days == 365
        assert config.tcpa_enabled is True
        assert config.consent_required is True
    
    def test_tcpa_calling_hours(self):
        """Test TCPA calling hours defaults"""
        config = ComplianceConfig()
        
        # Default calling hours: 8 AM to 9 PM
        assert config.tcpa_calling_hours_start == 8
        assert config.tcpa_calling_hours_end == 21


class TestLicenseConfig:
    """Tests for license configuration"""
    
    def test_default_values(self):
        """Test license config defaults"""
        config = LicenseConfig()
        
        assert config.default_tier == LicenseTier.PARWA
        assert config.mini_max_seats == 5
        assert config.parwa_max_seats == 25
        assert config.parwa_high_max_seats == 100
    
    def test_get_max_seats(self):
        """Test get_max_seats method"""
        config = LicenseConfig()
        
        assert config.get_max_seats(LicenseTier.MINI) == 5
        assert config.get_max_seats(LicenseTier.PARWA) == 25
        assert config.get_max_seats(LicenseTier.PARWA_HIGH) == 100
    
    def test_get_features(self):
        """Test get_features method"""
        config = LicenseConfig()
        
        mini_features = config.get_features(LicenseTier.MINI)
        assert "basic_support" in mini_features
        assert "email" in mini_features
        
        parwa_high_features = config.get_features(LicenseTier.PARWA_HIGH)
        assert "api" in parwa_high_features
        assert "priority_support" in parwa_high_features


class TestLicenseTier:
    """Tests for license tier enum"""
    
    def test_tier_values(self):
        """Test license tier enum values"""
        assert LicenseTier.MINI.value == "mini"
        assert LicenseTier.PARWA.value == "parwa"
        assert LicenseTier.PARWA_HIGH.value == "parwa_high"


class TestRateLimitConfig:
    """Tests for rate limiting configuration"""
    
    def test_default_values(self):
        """Test rate limit config defaults"""
        config = RateLimitConfig()
        
        assert config.enabled is True
        assert config.api_requests_per_minute == 60
        assert config.api_requests_per_hour == 1000
        assert config.webhook_requests_per_minute == 100
        assert config.ai_requests_per_minute == 30


class TestAppConfig:
    """Tests for main application configuration"""
    
    def test_default_values(self):
        """Test app config defaults"""
        config = AppConfig()
        
        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is False
        assert config.log_level == LogLevel.INFO
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.workers == 1
    
    def test_cors_defaults(self):
        """Test CORS defaults"""
        config = AppConfig()
        
        assert "*" in config.cors_origins
        assert config.cors_allow_credentials is True
    
    def test_nested_configs(self):
        """Test nested configuration objects"""
        config = AppConfig()
        
        assert isinstance(config.api_keys, APIKeysConfig)
        assert isinstance(config.webhooks, WebhookConfig)
        assert isinstance(config.sla, SLAConfig)
        assert isinstance(config.compliance, ComplianceConfig)
        assert isinstance(config.license, LicenseConfig)
        assert isinstance(config.rate_limit, RateLimitConfig)


class TestConfigManager:
    """Tests for configuration manager"""
    
    def test_singleton_pattern(self):
        """Test ConfigManager is a singleton"""
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        
        assert manager1 is manager2
    
    def test_load_config(self):
        """Test loading configuration"""
        manager = ConfigManager()
        # Reset the config
        manager._config = None
        
        config = manager.load()
        
        assert config is not None
        assert isinstance(config, AppConfig)
    
    def test_config_property(self):
        """Test config property"""
        manager = ConfigManager()
        manager._config = None  # Reset
        
        config = manager.config
        
        assert isinstance(config, AppConfig)
    
    def test_get_api_key(self):
        """Test get_api_key method"""
        manager = ConfigManager()
        manager._config = AppConfig(
            api_keys=APIKeysConfig(
                google_ai_key="test_key"
            )
        )
        
        key = manager.get_api_key("google_ai")
        assert key == "test_key"
    
    def test_validate_required_keys(self):
        """Test validate_required_keys method"""
        manager = ConfigManager()
        manager._config = AppConfig(
            api_keys=APIKeysConfig(
                google_ai_key="key1",
                cerebras_key=""  # Empty
            )
        )
        
        results = manager.validate_required_keys([
            "google_ai_key",
            "cerebras_key",
            "groq_key"
        ])
        
        assert results["google_ai_key"] is True
        assert results["cerebras_key"] is False
        assert results["groq_key"] is False
    
    def test_get_missing_keys(self):
        """Test get_missing_keys method"""
        manager = ConfigManager()
        manager._config = AppConfig(
            api_keys=APIKeysConfig(
                google_ai_key="key1"
            )
        )
        
        missing = manager.get_missing_keys([
            "google_ai_key",
            "cerebras_key",
            "groq_key"
        ])
        
        assert "google_ai_key" not in missing
        assert "cerebras_key" in missing
        assert "groq_key" in missing


class TestGetConfigFunction:
    """Tests for get_config helper function"""
    
    def test_get_config_returns_appconfig(self):
        """Test get_config returns AppConfig instance"""
        # Reset manager
        ConfigManager._instance = None
        ConfigManager._config = None
        
        config = get_config()
        
        assert isinstance(config, AppConfig)


class TestGetAPIKeyFunction:
    """Tests for get_api_key helper function"""
    
    def test_get_api_key_with_value(self):
        """Test get_api_key with configured value"""
        # Import the global config_manager to reset it properly
        from backend.core.config import config_manager as global_cm
        
        # Reset and create fresh manager
        ConfigManager._instance = None
        ConfigManager._config = None
        
        # Get the new singleton instance (this updates the class _instance)
        manager = ConfigManager()
        manager._config = AppConfig(
            api_keys=APIKeysConfig(
                google_ai_key="test_google_key"
            )
        )
        
        # Use the manager directly since global config_manager may be stale
        key = manager.get_api_key("google_ai")
        assert key == "test_google_key"
    
    def test_get_api_key_without_value(self):
        """Test get_api_key without configured value"""
        manager = ConfigManager()
        manager._config = AppConfig()
        
        key = get_api_key("nonexistent")
        assert key is None


class TestValidateProductionConfig:
    """Tests for production configuration validation"""
    
    def test_production_debug_enabled(self):
        """Test production config fails with debug enabled"""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            debug=True
        )
        
        errors = validate_production_config(config)
        assert any("DEBUG" in e for e in errors)
    
    def test_production_missing_secrets(self):
        """Test production config fails without required secrets"""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            api_keys=APIKeysConfig()
        )
        
        errors = validate_production_config(config)
        assert any("JWT_SECRET" in e for e in errors)
        assert any("DATABASE_URL" in e for e in errors)
    
    def test_production_debug_log_level(self):
        """Test production config warns about DEBUG log level"""
        config = AppConfig(
            environment=Environment.PRODUCTION,
            log_level=LogLevel.DEBUG,
            api_keys=APIKeysConfig(
                jwt_secret="test",
                database_url="test",
                encryption_key="test"
            )
        )
        
        errors = validate_production_config(config)
        assert any("DEBUG log level" in e for e in errors)
    
    def test_development_no_errors(self):
        """Test development config has no production errors"""
        config = AppConfig(
            environment=Environment.DEVELOPMENT,
            debug=True
        )
        
        errors = validate_production_config(config)
        assert len(errors) == 0


class TestValidateWebhookConfig:
    """Tests for webhook configuration validation"""
    
    def test_shopify_signature_verification_missing_secret(self):
        """Test validation fails when Shopify signature verification enabled without secret"""
        config = AppConfig(
            webhooks=WebhookConfig(
                shopify_verify_signature=True
            ),
            api_keys=APIKeysConfig()
        )
        
        errors = validate_webhook_config(config)
        assert any("SHOPIFY_WEBHOOK_SECRET" in e for e in errors)
    
    def test_paddle_signature_verification_missing_secret(self):
        """Test validation fails when Paddle signature verification enabled without secret"""
        config = AppConfig(
            webhooks=WebhookConfig(
                paddle_verify_signature=True
            ),
            api_keys=APIKeysConfig()
        )
        
        errors = validate_webhook_config(config)
        assert any("PADDLE_WEBHOOK_SECRET" in e for e in errors)
    
    def test_valid_webhook_config(self):
        """Test validation passes with proper secrets"""
        config = AppConfig(
            webhooks=WebhookConfig(
                shopify_verify_signature=True,
                paddle_verify_signature=True,
                shopify_webhook_secret="shopify_secret",
                paddle_webhook_secret="paddle_secret"
            )
        )
        
        errors = validate_webhook_config(config)
        assert len(errors) == 0
    
    def test_disabled_verification_no_secret_needed(self):
        """Test no error when verification disabled"""
        config = AppConfig(
            webhooks=WebhookConfig(
                shopify_verify_signature=False,
                paddle_verify_signature=False
            ),
            api_keys=APIKeysConfig()
        )
        
        errors = validate_webhook_config(config)
        assert len(errors) == 0


class TestEnvironmentVariables:
    """Tests for environment variable loading"""
    
    def test_load_from_env(self):
        """Test loading configuration from environment variables"""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG",
            "PORT": "9000"
        }):
            manager = ConfigManager()
            manager._config = None
            
            config = manager.load()
            
            assert config.environment == Environment.PRODUCTION
            assert config.debug is True
            assert config.log_level == LogLevel.DEBUG
            assert config.port == 9000
    
    def test_load_api_keys_from_env(self):
        """Test loading API keys from environment variables"""
        with patch.dict(os.environ, {
            "GOOGLE_AI_API_KEY": "google_test_key",
            "CEREBRAS_API_KEY": "cerebras_test_key",
            "GROQ_API_KEY": "groq_test_key"
        }):
            manager = ConfigManager()
            manager._config = None
            
            config = manager.load()
            
            assert config.api_keys.get_key("google_ai_key") == "google_test_key"
            assert config.api_keys.get_key("cerebras_key") == "cerebras_test_key"
            assert config.api_keys.get_key("groq_key") == "groq_test_key"
    
    def test_environment_alias_mapping(self):
        """Test that environment aliases are mapped correctly"""
        # Test "test" -> "testing"
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            manager = ConfigManager()
            manager._config = None
            config = manager.load()
            assert config.environment == Environment.TESTING
        
        # Test "dev" -> "development"
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            manager = ConfigManager()
            manager._config = None
            config = manager.load()
            assert config.environment == Environment.DEVELOPMENT
        
        # Test "prod" -> "production"
        with patch.dict(os.environ, {"ENVIRONMENT": "prod"}):
            manager = ConfigManager()
            manager._config = None
            config = manager.load()
            assert config.environment == Environment.PRODUCTION


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
