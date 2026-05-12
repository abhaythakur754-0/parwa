"""
PARWA Sentry Integration Tests (Phase 6)

Comprehensive tests for the Sentry error monitoring integration:
- Initialization with/without DSN
- PII scrubbing (emails, phone numbers)
- Tenant context enrichment
- Exception capture wrapper
- Environment-aware sample rates
- Health check status reporting
"""

import os
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_sentry_state():
    """Reset Sentry module state between tests."""
    import app.core.sentry as sentry_module
    original_initialized = sentry_module._sentry_initialized
    sentry_module._sentry_initialized = False
    yield
    sentry_module._sentry_initialized = original_initialized


@pytest.fixture
def mock_settings():
    """Mock settings with Sentry DSN configured."""
    mock = MagicMock()
    mock.SENTRY_DSN = "https://examplePublicKey@o0.ingest.sentry.io/0"
    mock.SENTRY_TRACES_SAMPLE_RATE = 0.1
    mock.SENTRY_PROFILES_SAMPLE_RATE = 0.1
    mock.SENTRY_ENVIRONMENT = ""
    mock.ENVIRONMENT = "production"
    return mock


@pytest.fixture
def mock_settings_no_dsn():
    """Mock settings without Sentry DSN."""
    mock = MagicMock()
    mock.SENTRY_DSN = ""
    mock.SENTRY_TRACES_SAMPLE_RATE = 0.1
    mock.SENTRY_PROFILES_SAMPLE_RATE = 0.1
    mock.SENTRY_ENVIRONMENT = ""
    mock.ENVIRONMENT = "development"
    return mock


@pytest.fixture
def mock_settings_dev():
    """Mock settings for development environment."""
    mock = MagicMock()
    mock.SENTRY_DSN = "https://examplePublicKey@o0.ingest.sentry.io/0"
    mock.SENTRY_TRACES_SAMPLE_RATE = 0.1
    mock.SENTRY_PROFILES_SAMPLE_RATE = 0.1
    mock.SENTRY_ENVIRONMENT = ""
    mock.ENVIRONMENT = "development"
    return mock


# ── Initialization Tests ────────────────────────────────────────


class TestSentryInitialization:
    """Tests for Sentry initialization logic."""

    def test_sentry_not_initialized_without_dsn(self, mock_settings_no_dsn):
        """Sentry should not initialize when SENTRY_DSN is empty."""
        with patch("app.core.sentry._get_settings", return_value=mock_settings_no_dsn):
            from app.core.sentry import init_sentry
            result = init_sentry()

        assert result is False

    def test_sentry_initialized_with_dsn(self, mock_settings):
        """Sentry should initialize when SENTRY_DSN is provided."""
        with patch("app.core.sentry._get_settings", return_value=mock_settings):
            with patch("sentry_sdk.init") as mock_init:
                from app.core.sentry import init_sentry
                result = init_sentry()

        assert result is True
        mock_init.assert_called_once()

        # Verify key parameters
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["dsn"] == "https://examplePublicKey@o0.ingest.sentry.io/0"
        assert call_kwargs["send_default_pii"] is False

    def test_sentry_init_does_not_crash_on_error(self):
        """Sentry initialization failure should not crash the app (BC-008)."""
        with patch("app.core.sentry._get_settings", side_effect=Exception("config error")):
            from app.core.sentry import init_sentry
            result = init_sentry()

        assert result is False

    def test_sentry_already_initialized_returns_true(self, mock_settings):
        """Calling init_sentry() twice should return True without re-init."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = True

        from app.core.sentry import init_sentry
        result = init_sentry()

        assert result is True

    def test_sentry_init_with_fastapi_celery_redis_integrations(self, mock_settings):
        """Sentry should include FastAPI, Celery, and Redis integrations."""
        with patch("app.core.sentry._get_settings", return_value=mock_settings):
            with patch("sentry_sdk.init") as mock_init:
                from app.core.sentry import init_sentry
                init_sentry()

        call_kwargs = mock_init.call_args[1]
        integrations = call_kwargs["integrations"]
        integration_types = [type(i).__name__ for i in integrations]

        assert "FastApiIntegration" in integration_types
        assert "CeleryIntegration" in integration_types
        assert "RedisIntegration" in integration_types

    def test_sentry_before_send_hook_set(self, mock_settings):
        """Sentry should set before_send hook for PII scrubbing + context."""
        with patch("app.core.sentry._get_settings", return_value=mock_settings):
            with patch("sentry_sdk.init") as mock_init:
                from app.core.sentry import init_sentry
                init_sentry()

        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["before_send"] is not None
        assert callable(call_kwargs["before_send"])


# ── PII Scrubbing Tests ────────────────────────────────────────


class TestPIIScrubbing:
    """Tests for PII scrubbing in Sentry events."""

    def test_pii_scrubbing_removes_emails(self):
        """Email addresses should be redacted from event data."""
        from app.core.sentry import scrub_pii

        event = {
            "message": "User john.doe@example.com failed to login",
            "extra": {
                "user_input": "Contact us at support@parwa.ai",
            },
        }

        result = scrub_pii(event, {})

        assert "john.doe@example.com" not in result["message"]
        assert "support@parwa.ai" not in result["extra"]["user_input"]
        assert "[REDACTED]" in result["message"]
        assert "[REDACTED]" in result["extra"]["user_input"]

    def test_pii_scrubbing_removes_phone_numbers(self):
        """Phone numbers should be redacted from event data."""
        from app.core.sentry import scrub_pii

        event = {
            "message": "Customer called from +1-555-123-4567",
            "extra": {
                "phone": "+44 20 7946 0958",
            },
        }

        result = scrub_pii(event, {})

        # Phone numbers with 7+ digits should be redacted
        assert "+1-555-123-4567" not in result["message"]
        assert "[REDACTED]" in result["message"]

    def test_pii_scrubbing_preserves_non_pii(self):
        """Non-PII data should be preserved unchanged."""
        from app.core.sentry import scrub_pii

        event = {
            "message": "Database connection timeout",
            "extra": {
                "error_code": 500,
                "retry_count": 3,
            },
        }

        result = scrub_pii(event, {})

        assert result["message"] == "Database connection timeout"
        assert result["extra"]["error_code"] == 500
        assert result["extra"]["retry_count"] == 3

    def test_pii_scrubbing_nested_dicts(self):
        """PII should be scrubbed from nested structures."""
        from app.core.sentry import scrub_pii

        event = {
            "extra": {
                "request": {
                    "body": "Email: admin@company.com",
                },
            },
        }

        result = scrub_pii(event, {})

        assert "admin@company.com" not in str(result)
        assert "[REDACTED]" in result["extra"]["request"]["body"]

    def test_pii_scrubbing_list_values(self):
        """PII should be scrubbed from list values."""
        from app.core.sentry import scrub_pii

        event = {
            "breadcrumbs": [
                {"message": "Sent email to user@test.com"},
                {"message": "Processed order #12345"},
            ],
        }

        result = scrub_pii(event, {})

        assert "user@test.com" not in str(result)
        assert "[REDACTED]" in result["breadcrumbs"][0]["message"]
        assert result["breadcrumbs"][1]["message"] == "Processed order #12345"

    def test_pii_scrubbing_does_not_crash_on_error(self):
        """PII scrubbing should never crash (BC-008)."""
        from app.core.sentry import scrub_pii

        # Create an event with a problematic structure
        class BadRepr:
            def __str__(self):
                raise RuntimeError("cannot stringify")

        event = {"extra": {"bad": BadRepr()}}
        # Should not raise
        result = scrub_pii(event, {})
        assert result is not None

    def test_pii_scrubbing_short_numbers_not_redacted(self):
        """Short numbers (< 7 digits) should not be redacted (avoid false positives)."""
        from app.core.sentry import scrub_pii

        event = {
            "message": "Error code 404 at port 8080",
        }

        result = scrub_pii(event, {})

        # "404" and "8080" should NOT be redacted (too short for phone numbers)
        assert "404" in result["message"]
        assert "8080" in result["message"]


# ── Tenant Context Tests ───────────────────────────────────────


class TestTenantContext:
    """Tests for tenant context enrichment in Sentry events."""

    def test_tenant_context_added(self):
        """company_id should be added to Sentry event tags and extra."""
        from app.core.sentry import add_tenant_context

        with patch("app.core.sentry.get_tenant_context") as mock_get_tenant:
            # Mock get_tenant_context from the sentry module's import
            with patch(
                "app.core.tenant_context.get_tenant_context",
                return_value="acme-corp",
            ):
                # Patch the import inside the function
                with patch.dict(
                    "sys.modules",
                    {"app.core.tenant_context": MagicMock(
                        get_tenant_context=MagicMock(return_value="acme-corp")
                    )},
                ):
                    event = {"tags": {}, "extra": {}}
                    result = add_tenant_context(event, {})

        # company_id should be present in tags
        assert result["tags"]["company_id"] == "acme-corp"
        # company_id should be present in extra
        assert result["extra"]["company_id"] == "acme-corp"

    def test_tenant_context_missing_company_id(self):
        """When no tenant context is set, event should still be valid."""
        from app.core.sentry import add_tenant_context

        with patch(
            "app.core.tenant_context.get_tenant_context",
            return_value=None,
        ):
            event = {"tags": {}, "extra": {}}
            result = add_tenant_context(event, {})

        # Should not have company_id but should not crash
        assert "company_id" not in result.get("tags", {})
        # Should still have captured_at_utc
        assert "captured_at_utc" in result["extra"]

    def test_tenant_context_does_not_crash_on_error(self):
        """Tenant context enrichment should never crash (BC-008)."""
        from app.core.sentry import add_tenant_context

        with patch(
            "app.core.tenant_context.get_tenant_context",
            side_effect=Exception("context error"),
        ):
            event = {"tags": {}, "extra": {}}
            result = add_tenant_context(event, {})

        # Should return original event (or modified without crash)
        assert result is not None

    def test_captured_at_utc_timestamp_included(self):
        """All events should include a UTC timestamp (BC-012)."""
        from app.core.sentry import add_tenant_context

        with patch(
            "app.core.tenant_context.get_tenant_context",
            return_value=None,
        ):
            event = {"extra": {}}
            result = add_tenant_context(event, {})

        assert "captured_at_utc" in result["extra"]
        # Should end with Z (UTC indicator)
        assert result["extra"]["captured_at_utc"].endswith("Z")


# ── Capture Exception Wrapper Tests ────────────────────────────


class TestCaptureException:
    """Tests for the capture_exception wrapper."""

    def test_capture_exception_wrapper(self):
        """capture_exception should call sentry_sdk.capture_exception."""
        from app.core.sentry import capture_exception, _sentry_initialized

        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = True

        mock_exc = ValueError("test error")

        with patch("sentry_sdk.capture_exception", return_value="event-123") as mock_capture:
            with patch("sentry_sdk.push_scope") as mock_push_scope:
                mock_scope = MagicMock()
                mock_push_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
                mock_push_scope.return_value.__exit__ = MagicMock(return_value=False)

                result = capture_exception(mock_exc)

        assert result == "event-123"
        mock_capture.assert_called_once_with(mock_exc)

    def test_capture_exception_without_init(self):
        """capture_exception should return None if Sentry not initialized."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = False

        from app.core.sentry import capture_exception
        result = capture_exception(ValueError("test"))

        assert result is None

    def test_capture_exception_with_kwargs(self):
        """capture_exception should add kwargs as extra context."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = True

        from app.core.sentry import capture_exception

        with patch("sentry_sdk.capture_exception", return_value="event-456"):
            with patch("sentry_sdk.push_scope") as mock_push_scope:
                mock_scope = MagicMock()
                mock_push_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
                mock_push_scope.return_value.__exit__ = MagicMock(return_value=False)

                capture_exception(
                    ValueError("test"),
                    request_id="abc-123",
                    user_action="submit_form",
                )

        # Verify extra context was set
        mock_scope.set_extra.assert_any_call("request_id", "abc-123")
        mock_scope.set_extra.assert_any_call("user_action", "submit_form")

    def test_capture_exception_does_not_crash(self):
        """capture_exception should never crash (BC-008)."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = True

        from app.core.sentry import capture_exception

        with patch("sentry_sdk.capture_exception", side_effect=Exception("sentry down")):
            with patch("sentry_sdk.push_scope", side_effect=Exception("scope error")):
                result = capture_exception(ValueError("test"))

        assert result is None


# ── Environment Tests ──────────────────────────────────────────


class TestSentryEnvironment:
    """Tests for environment-aware configuration."""

    def test_sentry_respects_environment(self, mock_settings):
        """Sentry should use SENTRY_ENVIRONMENT if set, else ENVIRONMENT."""
        # When SENTRY_ENVIRONMENT is set
        mock_settings.SENTRY_ENVIRONMENT = "staging"
        with patch("app.core.sentry._get_settings", return_value=mock_settings):
            with patch("sentry_sdk.init") as mock_init:
                from app.core.sentry import init_sentry
                # Reset for fresh init
                import app.core.sentry as sentry_module
                sentry_module._sentry_initialized = False
                init_sentry()

        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["environment"] == "staging"

    def test_sentry_falls_back_to_environment(self, mock_settings):
        """Sentry should fall back to ENVIRONMENT when SENTRY_ENVIRONMENT is empty."""
        mock_settings.SENTRY_ENVIRONMENT = ""
        mock_settings.ENVIRONMENT = "production"
        with patch("app.core.sentry._get_settings", return_value=mock_settings):
            with patch("sentry_sdk.init") as mock_init:
                import app.core.sentry as sentry_module
                sentry_module._sentry_initialized = False
                from app.core.sentry import init_sentry
                init_sentry()

        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["environment"] == "production"


# ── Sample Rate Tests ──────────────────────────────────────────


class TestSampleRates:
    """Tests for environment-aware sample rates."""

    def test_sample_rates_production(self):
        """Production should use lower sample rates."""
        from app.core.sentry import _get_sample_rates

        rates = _get_sample_rates("production")

        assert rates["traces_sample_rate"] == 0.1
        assert rates["profiles_sample_rate"] == 0.1

    def test_sample_rates_staging(self):
        """Staging should use lower sample rates."""
        from app.core.sentry import _get_sample_rates

        rates = _get_sample_rates("staging")

        assert rates["traces_sample_rate"] == 0.1
        assert rates["profiles_sample_rate"] == 0.1

    def test_sample_rates_development(self):
        """Development should use full sample rates."""
        from app.core.sentry import _get_sample_rates

        rates = _get_sample_rates("development")

        assert rates["traces_sample_rate"] == 1.0
        assert rates["profiles_sample_rate"] == 1.0

    def test_sample_rates_test(self):
        """Test environment should use full sample rates."""
        from app.core.sentry import _get_sample_rates

        rates = _get_sample_rates("test")

        assert rates["traces_sample_rate"] == 1.0
        assert rates["profiles_sample_rate"] == 1.0

    def test_sentry_send_default_pii_false(self, mock_settings):
        """send_default_pii should always be False for GDPR compliance."""
        with patch("app.core.sentry._get_settings", return_value=mock_settings):
            with patch("sentry_sdk.init") as mock_init:
                import app.core.sentry as sentry_module
                sentry_module._sentry_initialized = False
                from app.core.sentry import init_sentry
                init_sentry()

        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["send_default_pii"] is False


# ── Health Check / Status Tests ────────────────────────────────


class TestSentryStatus:
    """Tests for Sentry health check status reporting."""

    def test_get_sentry_status_initialized(self, mock_settings):
        """Status should reflect initialized state."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = True

        with patch("app.core.sentry._get_settings", return_value=mock_settings):
            from app.core.sentry import get_sentry_status
            status = get_sentry_status()

        assert status["initialized"] is True
        assert status["dsn_configured"] is True
        assert status["send_default_pii"] is False

    def test_get_sentry_status_not_initialized(self, mock_settings_no_dsn):
        """Status should reflect uninitialized state."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = False

        with patch("app.core.sentry._get_settings", return_value=mock_settings_no_dsn):
            from app.core.sentry import get_sentry_status
            status = get_sentry_status()

        assert status["initialized"] is False
        assert status["dsn_configured"] is False

    def test_get_sentry_status_does_not_crash(self):
        """Status check should never crash (BC-008)."""
        with patch("app.core.sentry._get_settings", side_effect=Exception("error")):
            from app.core.sentry import get_sentry_status
            status = get_sentry_status()

        assert status["initialized"] is False
        assert "error" in status

    def test_is_initialized_flag(self):
        """is_initialized() should reflect module state."""
        import app.core.sentry as sentry_module

        sentry_module._sentry_initialized = False
        from app.core.sentry import is_initialized
        assert is_initialized() is False

        sentry_module._sentry_initialized = True
        assert is_initialized() is True


# ── Flush Tests ────────────────────────────────────────────────


class TestSentryFlush:
    """Tests for Sentry event flushing on shutdown."""

    def test_flush_when_initialized(self):
        """Flush should call client.flush when Sentry is initialized."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = True

        mock_client = MagicMock()
        with patch("sentry_sdk.Hub") as mock_hub:
            mock_hub.current.client = mock_client
            from app.core.sentry import flush
            flush(timeout=2.0)

        mock_client.flush.assert_called_once_with(timeout=2.0)

    def test_flush_when_not_initialized(self):
        """Flush should be a no-op when Sentry is not initialized."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = False

        from app.core.sentry import flush
        # Should not raise
        flush(timeout=2.0)

    def test_flush_does_not_crash(self):
        """Flush should never crash (BC-008)."""
        import app.core.sentry as sentry_module
        sentry_module._sentry_initialized = True

        with patch("sentry_sdk.Hub", side_effect=Exception("hub error")):
            from app.core.sentry import flush
            # Should not raise
            flush(timeout=2.0)


# ── Combined Before Send Tests ─────────────────────────────────


class TestCombinedBeforeSend:
    """Tests for the combined before_send hook."""

    def test_combined_before_send_adds_context_and_scrubs_pii(self):
        """Combined hook should add context then scrub PII."""
        from app.core.sentry import _combined_before_send

        with patch(
            "app.core.tenant_context.get_tenant_context",
            return_value="test-company",
        ):
            event = {
                "message": "Error for user john@example.com in company test-company",
                "tags": {},
                "extra": {},
            }
            result = _combined_before_send(event, {})

        # Context should be added
        assert result["tags"]["company_id"] == "test-company"
        # PII should be scrubbed
        assert "john@example.com" not in str(result)
        assert "[REDACTED]" in result["message"]
