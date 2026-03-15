"""
PARWA Configuration Module
Environment-based configuration with API key management
"""

import os
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field, field_validator, SecretStr, ConfigDict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============================================================================
# API Key Configuration
# ============================================================================

class APIKeysConfig(BaseModel):
    """API keys configuration for external services"""
    
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    # AI Providers
    google_ai_key: Optional[SecretStr] = Field(None, alias="GOOGLE_AI_API_KEY")
    cerebras_key: Optional[SecretStr] = Field(None, alias="CEREBRAS_API_KEY")
    groq_key: Optional[SecretStr] = Field(None, alias="GROQ_API_KEY")
    
    # Communication Services
    brevo_key: Optional[SecretStr] = Field(None, alias="BREVO_API_KEY")
    
    # E-commerce & Payments
    shopify_api_key: Optional[SecretStr] = Field(None, alias="SHOPIFY_API_KEY")
    shopify_api_secret: Optional[SecretStr] = Field(None, alias="SHOPIFY_API_SECRET")
    stripe_secret_key: Optional[SecretStr] = Field(None, alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[SecretStr] = Field(None, alias="STRIPE_WEBHOOK_SECRET")
    
    # Database
    database_url: Optional[SecretStr] = Field(None, alias="DATABASE_URL")
    redis_url: Optional[SecretStr] = Field(None, alias="REDIS_URL")
    
    # Security
    jwt_secret: Optional[SecretStr] = Field(None, alias="JWT_SECRET")
    encryption_key: Optional[SecretStr] = Field(None, alias="ENCRYPTION_KEY")
    
    @field_validator("google_ai_key", "cerebras_key", "groq_key", "brevo_key", mode="before")
    @classmethod
    def validate_api_key_format(cls, v):
        """Validate API key format (basic check)"""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return SecretStr(v)
        return v
    
    def get_key(self, key_name: str) -> Optional[str]:
        """Get API key value by name"""
        key = getattr(self, key_name, None)
        if key and isinstance(key, SecretStr):
            return key.get_secret_value()
        return None
    
    def is_configured(self, key_name: str) -> bool:
        """Check if an API key is configured"""
        key = getattr(self, key_name, None)
        if key and isinstance(key, SecretStr):
            return bool(key.get_secret_value())
        return False


# ============================================================================
# Webhook Configuration
# ============================================================================

class WebhookConfig(BaseModel):
    """Webhook configuration"""
    
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    # Shopify
    shopify_webhook_secret: Optional[SecretStr] = Field(None, alias="SHOPIFY_WEBHOOK_SECRET")
    shopify_verify_signature: bool = Field(True, alias="SHOPIFY_VERIFY_SIGNATURE")
    shopify_max_timestamp_diff: int = Field(300, alias="SHOPIFY_MAX_TIMESTAMP_DIFF")  # 5 minutes
    
    # Stripe
    stripe_webhook_secret: Optional[SecretStr] = Field(None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_verify_signature: bool = Field(True, alias="STRIPE_VERIFY_SIGNATURE")
    stripe_max_timestamp_diff: int = Field(300, alias="STRIPE_MAX_TIMESTAMP_DIFF")  # 5 minutes
    
    # General
    webhook_retry_attempts: int = Field(3, alias="WEBHOOK_RETRY_ATTEMPTS")
    webhook_retry_delay: float = Field(1.0, alias="WEBHOOK_RETRY_DELAY")
    webhook_timeout: int = Field(30, alias="WEBHOOK_TIMEOUT")


# ============================================================================
# SLA Configuration
# ============================================================================

class SLAConfig(BaseModel):
    """SLA (Service Level Agreement) configuration"""
    
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    # Response time tiers (in hours)
    tier1_response_hours: int = Field(24, alias="SLA_TIER1_RESPONSE_HOURS")
    tier2_response_hours: int = Field(48, alias="SLA_TIER2_RESPONSE_HOURS")
    tier3_response_hours: int = Field(72, alias="SLA_TIER3_RESPONSE_HOURS")
    
    # Breach thresholds
    breach_warning_hours: int = Field(4, alias="SLA_BREACH_WARNING_HOURS")  # Warn 4 hours before breach
    
    # Escalation
    auto_escalate: bool = Field(True, alias="SLA_AUTO_ESCALATE")
    escalation_email: Optional[str] = Field(None, alias="SLA_ESCALATION_EMAIL")
    
    # Monitoring
    check_interval_minutes: int = Field(5, alias="SLA_CHECK_INTERVAL_MINUTES")


# ============================================================================
# Compliance Configuration
# ============================================================================

class ComplianceConfig(BaseModel):
    """Compliance configuration"""
    
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    # GDPR
    gdpr_enabled: bool = Field(True, alias="GDPR_ENABLED")
    gdpr_response_days: int = Field(30, alias="GDPR_RESPONSE_DAYS")  # 30 days max
    gdpr_data_retention_days: int = Field(365, alias="GDPR_DATA_RETENTION_DAYS")
    
    # TCPA
    tcpa_enabled: bool = Field(True, alias="TCPA_ENABLED")
    tcpa_optout_honor: bool = Field(True, alias="TCPA_OPTOUT_HONOR")
    tcpa_calling_hours_start: int = Field(8, alias="TCPA_CALLING_HOURS_START")  # 8 AM
    tcpa_calling_hours_end: int = Field(21, alias="TCPA_CALLING_HOURS_END")  # 9 PM
    
    # Consent
    consent_required: bool = Field(True, alias="CONSENT_REQUIRED")
    consent_version: str = Field("1.0", alias="CONSENT_VERSION")


# ============================================================================
# License Configuration
# ============================================================================

class LicenseTier(str, Enum):
    """License tier types"""
    MINI = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "parwa_high"


class LicenseConfig(BaseModel):
    """License configuration"""
    
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    default_tier: LicenseTier = Field(LicenseTier.PARWA, alias="DEFAULT_LICENSE_TIER")
    
    # Seat limits per tier
    mini_max_seats: int = Field(5, alias="MINI_MAX_SEATS")
    parwa_max_seats: int = Field(25, alias="PARWA_MAX_SEATS")
    parwa_high_max_seats: int = Field(100, alias="PARWA_HIGH_MAX_SEATS")
    
    # Feature flags per tier
    mini_features: List[str] = Field(
        default=["basic_support", "email"],
        alias="MINI_FEATURES"
    )
    parwa_features: List[str] = Field(
        default=["basic_support", "email", "chat", "phone", "analytics"],
        alias="PARWA_FEATURES"
    )
    parwa_high_features: List[str] = Field(
        default=["basic_support", "email", "chat", "phone", "analytics", "api", "custom_integrations", "priority_support"],
        alias="PARWA_HIGH_FEATURES"
    )
    
    def get_max_seats(self, tier: LicenseTier) -> int:
        """Get max seats for a tier"""
        seat_map = {
            LicenseTier.MINI: self.mini_max_seats,
            LicenseTier.PARWA: self.parwa_max_seats,
            LicenseTier.PARWA_HIGH: self.parwa_high_max_seats
        }
        return seat_map.get(tier, self.parwa_max_seats)
    
    def get_features(self, tier: LicenseTier) -> List[str]:
        """Get features for a tier"""
        feature_map = {
            LicenseTier.MINI: self.mini_features,
            LicenseTier.PARWA: self.parwa_features,
            LicenseTier.PARWA_HIGH: self.parwa_high_features
        }
        return feature_map.get(tier, self.parwa_features)


# ============================================================================
# Rate Limiting Configuration
# ============================================================================

class RateLimitConfig(BaseModel):
    """Rate limiting configuration"""
    
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    # Global limits
    enabled: bool = Field(True, alias="RATE_LIMIT_ENABLED")
    
    # API rate limits
    api_requests_per_minute: int = Field(60, alias="API_REQUESTS_PER_MINUTE")
    api_requests_per_hour: int = Field(1000, alias="API_REQUESTS_PER_HOUR")
    
    # Webhook rate limits
    webhook_requests_per_minute: int = Field(100, alias="WEBHOOK_REQUESTS_PER_MINUTE")
    
    # AI provider limits
    ai_requests_per_minute: int = Field(30, alias="AI_REQUESTS_PER_MINUTE")
    
    # Redis key prefix
    redis_prefix: str = Field("parwa:ratelimit:", alias="RATE_LIMIT_REDIS_PREFIX")


# ============================================================================
# Application Configuration
# ============================================================================

class AppConfig(BaseModel):
    """Main application configuration"""
    
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    
    # Environment
    environment: Environment = Field(Environment.DEVELOPMENT, alias="ENVIRONMENT")
    debug: bool = Field(False, alias="DEBUG")
    log_level: LogLevel = Field(LogLevel.INFO, alias="LOG_LEVEL")
    
    # Server
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")
    workers: int = Field(1, alias="WORKERS")
    
    # CORS
    cors_origins: List[str] = Field(["*"], alias="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(True, alias="CORS_ALLOW_CREDENTIALS")
    
    # Sub-configurations
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
    webhooks: WebhookConfig = Field(default_factory=WebhookConfig)
    sla: SLAConfig = Field(default_factory=SLAConfig)
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    license: LicenseConfig = Field(default_factory=LicenseConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)


# ============================================================================
# Configuration Manager
# ============================================================================

class ConfigManager:
    """Singleton configuration manager"""
    
    _instance: Optional["ConfigManager"] = None
    _config: Optional[AppConfig] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self, env_file: Optional[str] = None) -> AppConfig:
        """Load configuration from environment"""
        if self._config is not None:
            return self._config
        
        # Normalize environment value (map common aliases)
        env_raw = os.getenv("ENVIRONMENT", "development").lower()
        env_mapping = {
            "test": "testing",
            "dev": "development",
            "prod": "production",
            "stage": "staging",
        }
        env_normalized = env_mapping.get(env_raw, env_raw)
        
        # Load from environment variables
        self._config = AppConfig(
            environment=env_normalized,
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            workers=int(os.getenv("WORKERS", "1")),
            cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
            api_keys=APIKeysConfig(
                google_ai_key=os.getenv("GOOGLE_AI_API_KEY"),
                cerebras_key=os.getenv("CEREBRAS_API_KEY"),
                groq_key=os.getenv("GROQ_API_KEY"),
                brevo_key=os.getenv("BREVO_API_KEY"),
                shopify_api_key=os.getenv("SHOPIFY_API_KEY"),
                shopify_api_secret=os.getenv("SHOPIFY_API_SECRET"),
                stripe_secret_key=os.getenv("STRIPE_SECRET_KEY"),
                stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
                database_url=os.getenv("DATABASE_URL"),
                redis_url=os.getenv("REDIS_URL"),
                jwt_secret=os.getenv("JWT_SECRET"),
                encryption_key=os.getenv("ENCRYPTION_KEY"),
            ),
            webhooks=WebhookConfig(
                shopify_webhook_secret=os.getenv("SHOPIFY_WEBHOOK_SECRET"),
                stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
            ),
        )
        
        logger.info(f"Configuration loaded for environment: {self._config.environment}")
        return self._config
    
    @property
    def config(self) -> AppConfig:
        """Get current configuration"""
        if self._config is None:
            return self.load()
        return self._config
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider"""
        key_map = {
            "google_ai": self._config.api_keys.google_ai_key,
            "cerebras": self._config.api_keys.cerebras_key,
            "groq": self._config.api_keys.groq_key,
            "brevo": self._config.api_keys.brevo_key,
            "shopify": self._config.api_keys.shopify_api_key,
            "stripe": self._config.api_keys.stripe_secret_key,
        }
        key = key_map.get(provider)
        if key and isinstance(key, SecretStr):
            return key.get_secret_value()
        return None
    
    def validate_required_keys(self, required_keys: List[str]) -> Dict[str, bool]:
        """Validate that required API keys are configured"""
        results = {}
        for key in required_keys:
            results[key] = self._config.api_keys.is_configured(key)
        return results
    
    def get_missing_keys(self, required_keys: List[str]) -> List[str]:
        """Get list of missing required keys"""
        validation = self.validate_required_keys(required_keys)
        return [key for key, is_valid in validation.items() if not is_valid]


# Global configuration instance
config_manager = ConfigManager()


def get_config() -> AppConfig:
    """Get application configuration"""
    return config_manager.config


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider"""
    return config_manager.get_api_key(provider)


# ============================================================================
# Configuration Validation
# ============================================================================

def validate_production_config(config: AppConfig) -> List[str]:
    """Validate configuration for production environment"""
    errors = []
    
    if config.environment == Environment.PRODUCTION:
        # Check debug mode
        if config.debug:
            errors.append("DEBUG mode should be disabled in production")
        
        # Check required secrets
        required_secrets = [
            ("jwt_secret", "JWT_SECRET"),
            ("database_url", "DATABASE_URL"),
            ("encryption_key", "ENCRYPTION_KEY"),
        ]
        
        for attr, name in required_secrets:
            if not config.api_keys.is_configured(attr):
                errors.append(f"{name} is required in production")
        
        # Check log level
        if config.log_level == LogLevel.DEBUG:
            errors.append("DEBUG log level not recommended for production")
    
    return errors


def validate_webhook_config(config: AppConfig) -> List[str]:
    """Validate webhook configuration"""
    errors = []
    
    if config.webhooks.shopify_verify_signature:
        secret = config.webhooks.shopify_webhook_secret
        if not secret or not secret.get_secret_value():
            errors.append("SHOPIFY_WEBHOOK_SECRET required when signature verification enabled")
    
    if config.webhooks.stripe_verify_signature:
        secret = config.webhooks.stripe_webhook_secret
        if not secret or not secret.get_secret_value():
            errors.append("STRIPE_WEBHOOK_SECRET required when signature verification enabled")
    
    return errors
