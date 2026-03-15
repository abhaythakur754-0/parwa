import pytest
from unittest.mock import patch, MagicMock
from shared.utils.monitoring import init_monitoring, capture_exception, track_performance
from shared.core_functions.config import Settings

@pytest.fixture
def mock_settings():
    return Settings(
        ENVIRONMENT="development",
        SECRET_KEY="test_secret",
        POSTGRES_USER="test_user",
        POSTGRES_PASSWORD="test_password",
        POSTGRES_DB="test_db",
        DATABASE_URL="postgresql://test_user:test_password@localhost/test_db",
        REDIS_URL="redis://localhost:6379",
        JWT_SECRET_KEY="test_jwt_secret",
        OPENROUTER_API_KEY="test_key",
        OPENROUTER_BASE_URL="https://test.com",
        AI_LIGHT_MODEL="light",
        AI_MEDIUM_MODEL="medium",
        AI_HEAVY_MODEL="heavy",
        AI_FAILOVER_MODEL="failover",
        STRIPE_SECRET_KEY="sk_test_123",
        STRIPE_PUBLISHABLE_KEY="pk_test_123",
        STRIPE_WEBHOOK_SECRET="whsec_test",
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="auth_token",
        TWILIO_PHONE_NUMBER="+1234567890",
        TWILIO_VOICE_WEBHOOK_URL="https://test.com/voice",
        SHOPIFY_API_KEY="shopify_key",
        SHOPIFY_API_SECRET="shopify_secret",
        SHOPIFY_WEBHOOK_SECRET="shopify_webhook_secret",
        MCP_SERVER_URL="https://test.com",
        MCP_AUTH_TOKEN="mcp_token",
        QDRANT_URL="https://test.com",
        QDRANT_API_KEY="qdrant_key",
        SENDGRID_API_KEY="sendgrid_key",
        FROM_EMAIL="test@test.com",
        NEXT_PUBLIC_API_URL="https://test.com",
        NEXT_PUBLIC_STRIPE_KEY="pk_test_123",
        FEATURE_FLAGS_PATH="feature_flags",
        MODEL_REGISTRY_PATH="models",
        COLAB_WEBHOOK_URL="https://test.com",
        DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
        SENTRY_DSN="http://public@localhost/1",
        GRAFANA_API_KEY="grafana_key"
    )

@patch("shared.utils.monitoring.get_settings")
@patch("shared.utils.monitoring.sentry_sdk.init")
def test_init_monitoring_with_dsn(mock_sentry_init, mock_get_settings, mock_settings):
    mock_get_settings.return_value = mock_settings
    init_monitoring()
    mock_sentry_init.assert_called_once_with(
        dsn="http://public@localhost/1",
        environment="development",
        traces_sample_rate=1.0
    )

@patch("shared.utils.monitoring.get_settings")
@patch("shared.utils.monitoring.sentry_sdk.init")
def test_init_monitoring_no_dsn(mock_sentry_init, mock_get_settings, mock_settings):
    mock_settings.sentry_dsn = None
    mock_get_settings.return_value = mock_settings
    init_monitoring()
    mock_sentry_init.assert_not_called()

@patch("shared.utils.monitoring.get_settings")
@patch("shared.utils.monitoring.sentry_sdk.capture_exception")
@patch("shared.utils.monitoring.sentry_sdk.push_scope")
def test_capture_exception(mock_push_scope, mock_capture_exception, mock_get_settings, mock_settings):
    mock_get_settings.return_value = mock_settings
    
    test_exception = ValueError("Test error")
    context = {"user_id": 123}
    
    mock_scope_instance = MagicMock()
    mock_push_scope.return_value.__enter__.return_value = mock_scope_instance
    
    capture_exception(test_exception, context)
    
    # We shouldn't use assert_called_once_with because depending on the environment,
    # Sentry's internal logic might call it again. Instead, we can verify that
    # the dictionary items inside our context were passed to it.
    mock_scope_instance.set_extra.assert_any_call("user_id", 123)
    mock_capture_exception.assert_called_once_with(test_exception)

@patch("shared.utils.monitoring.logger.info")
def test_track_performance(mock_logger_info):
    @track_performance("test_op", "test_name")
    def dummy_function(x, y):
        return x + y

    result = dummy_function(2, 3)
    assert result == 5
    
    mock_logger_info.assert_called_once()
    args, kwargs = mock_logger_info.call_args
    assert "Performance tracked: test_name" in args[0]
    assert "context" in kwargs["extra"]
    assert kwargs["extra"]["context"]["operation_type"] == "test_op"
    assert kwargs["extra"]["context"]["operation_name"] == "test_name"
    assert "duration_s" in kwargs["extra"]["context"]
