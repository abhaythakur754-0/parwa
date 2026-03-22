"""
Unit tests for the monitoring module.
Tests that Sentry monitoring is initialized correctly and that exceptions are captured properly.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from shared.utils.monitoring import init_monitoring, capture_exception, track_performance
from shared.core_functions.config import Settings


@pytest.fixture
def settings_with_dsn():
    """Settings with Sentry DSN configured."""
    # Use alias name SENTRY_DSN to set the field
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
def settings_no_dsn(monkeypatch):
    """Settings without Sentry DSN - explicitly set to None via environment."""
    # Remove SENTRY_DSN from environment before creating Settings
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    
    # Force create Settings with sentry_dsn explicitly set to None
    # by using model_construct to bypass env var loading
    settings = Settings.model_construct(
        environment="development",
        secret_key="test_secret_key_for_monitoring",
        database_url="postgresql://test_user:test_password@localhost/test_db",
        redis_url="redis://localhost:6379",
        google_ai_api_key="test_google_key",
        stripe_secret_key="sk_test_123",
        stripe_publishable_key="pk_test_123",
        from_email="test@test.com",
        data_encryption_key="12345678901234567890123456789012",
        sentry_dsn=None,
    )
    # Verify sentry_dsn is None
    assert settings.sentry_dsn is None
    return settings


class TestInitMonitoring:
    """Tests for init_monitoring function."""

    @patch("shared.utils.monitoring.sentry_sdk.init")
    def test_with_dsn(self, mock_sentry_init, settings_with_dsn):
        """Test that Sentry is initialized when DSN is configured."""
        with patch("shared.utils.monitoring.get_settings", return_value=settings_with_dsn):
            init_monitoring()
            
            assert mock_sentry_init.called
            call_kwargs = mock_sentry_init.call_args.kwargs
            assert call_kwargs["dsn"] == "http://public@localhost/1"

    @patch("shared.utils.monitoring.sentry_sdk.init")
    def test_without_dsn(self, mock_sentry_init, settings_no_dsn):
        """Test that Sentry is not initialized when DSN is not configured."""
        with patch("shared.utils.monitoring.get_settings", return_value=settings_no_dsn):
            init_monitoring()
            
            mock_sentry_init.assert_not_called()


class TestCaptureException:
    """Tests for capture_exception function."""

    @patch("shared.utils.monitoring.sentry_sdk.push_scope")
    @patch("shared.utils.monitoring.sentry_sdk.capture_exception")
    def test_with_dsn(self, mock_capture, mock_push_scope, settings_with_dsn):
        """Test that exceptions are captured and sent to Sentry with context."""
        with patch("shared.utils.monitoring.get_settings", return_value=settings_with_dsn):
            test_exception = ValueError("Test error")
            context = {"user_id": 123}
            
            mock_scope = MagicMock()
            mock_push_scope.return_value.__enter__.return_value = mock_scope
            
            capture_exception(test_exception, context)
            
            mock_scope.set_extra.assert_any_call("user_id", 123)
            mock_capture.assert_called_once_with(test_exception)

    @patch("shared.utils.monitoring.sentry_sdk.capture_exception")
    def test_without_dsn(self, mock_capture, settings_no_dsn):
        """Test that exceptions are logged but not sent to Sentry when DSN is not configured."""
        with patch("shared.utils.monitoring.get_settings", return_value=settings_no_dsn):
            test_exception = ValueError("Test error")
            context = {"user_id": 123}
            
            capture_exception(test_exception, context)
            
            mock_capture.assert_not_called()


class TestTrackPerformance:
    """Tests for track_performance decorator."""

    @patch("shared.utils.monitoring.logger.info")
    def test_tracks_execution_time(self, mock_logger_info):
        """Test that the performance decorator tracks execution time."""
        @track_performance("test_op", "test_name")
        def dummy_function(x, y):
            return x + y

        result = dummy_function(2, 3)
        
        assert result == 5
        assert mock_logger_info.called
        args, kwargs = mock_logger_info.call_args
        assert "Performance tracked: test_name" in args[0]
        assert kwargs["extra"]["context"]["operation_type"] == "test_op"
        assert "duration_s" in kwargs["extra"]["context"]
