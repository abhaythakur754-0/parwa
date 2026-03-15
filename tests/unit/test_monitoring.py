"""
Unit tests for the monitoring module.
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from shared.utils.monitoring import init_monitoring, capture_exception, track_performance
from shared.core_functions.config import Settings


@pytest.fixture
def mock_settings_with_dsn():
    """Settings with Sentry DSN configured."""
    # Use SENTRY_DSN alias to set the field
    return Settings(
        environment="development",
        secret_key="test_secret_key_for_monitoring",
        database_url="postgresql://test_user:test_password@localhost/test_db",
        redis_url="redis://localhost:6379",
        google_ai_api_key="test_google_key",
        stripe_secret_key="sk_test_123",
        stripe_publishable_key="pk_test_123",
        from_email="test@test.com",
        data_encryption_key="12345678901234567890123456789012",
        **{"SENTRY_DSN": "http://public@localhost/1"},
    )


@pytest.fixture
def mock_settings_no_dsn(monkeypatch):
    """Settings without Sentry DSN - explicitly set to None."""
    # Remove SENTRY_DSN from environment to ensure it's not picked up
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    
    # Create settings and explicitly verify sentry_dsn is None
    settings = Settings(
        environment="development",
        secret_key="test_secret_key_for_monitoring",
        database_url="postgresql://test_user:test_password@localhost/test_db",
        redis_url="redis://localhost:6379",
        google_ai_api_key="test_google_key",
        stripe_secret_key="sk_test_123",
        stripe_publishable_key="pk_test_123",
        from_email="test@test.com",
        data_encryption_key="12345678901234567890123456789012",
    )
    # Ensure sentry_dsn is None
    assert settings.sentry_dsn is None, f"Expected sentry_dsn to be None, got {settings.sentry_dsn}"
    return settings


@patch("shared.utils.monitoring.sentry_sdk.init")
def test_init_monitoring_with_dsn(mock_sentry_init, mock_settings_with_dsn):
    """Test that Sentry is initialized when DSN is configured."""
    with patch("shared.utils.monitoring.get_settings", return_value=mock_settings_with_dsn):
        init_monitoring()
        # Verify that sentry_sdk.init was called with the DSN
        assert mock_sentry_init.called
        call_args = mock_sentry_init.call_args
        assert call_args.kwargs["dsn"] == "http://public@localhost/1"


@patch("shared.utils.monitoring.sentry_sdk.init")
def test_init_monitoring_no_dsn(mock_sentry_init, mock_settings_no_dsn):
    """Test that Sentry is not initialized when DSN is not configured."""
    with patch("shared.utils.monitoring.get_settings", return_value=mock_settings_no_dsn):
        init_monitoring()
        mock_sentry_init.assert_not_called()


@patch("shared.utils.monitoring.sentry_sdk.capture_exception")
@patch("shared.utils.monitoring.sentry_sdk.push_scope")
def test_capture_exception(mock_push_scope, mock_capture_exception, mock_settings_with_dsn):
    """Test that exceptions are captured and sent to Sentry with context."""
    with patch("shared.utils.monitoring.get_settings", return_value=mock_settings_with_dsn):
        test_exception = ValueError("Test error")
        context = {"user_id": 123}
        
        mock_scope_instance = MagicMock()
        mock_push_scope.return_value.__enter__.return_value = mock_scope_instance
        
        capture_exception(test_exception, context)
        
        # Verify the context was passed to Sentry scope
        mock_scope_instance.set_extra.assert_any_call("user_id", 123)
        mock_capture_exception.assert_called_once_with(test_exception)


@patch("shared.utils.monitoring.sentry_sdk.capture_exception")
def test_capture_exception_no_sentry_dsn(mock_capture_exception, mock_settings_no_dsn):
    """Test that exceptions are logged but not sent to Sentry when DSN is not configured."""
    with patch("shared.utils.monitoring.get_settings", return_value=mock_settings_no_dsn):
        test_exception = ValueError("Test error")
        context = {"user_id": 123}
        
        capture_exception(test_exception, context)
        
        # Sentry capture should not be called when no DSN
        mock_capture_exception.assert_not_called()


@patch("shared.utils.monitoring.logger.info")
def test_track_performance(mock_logger_info):
    """Test that the performance decorator tracks execution time."""
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
