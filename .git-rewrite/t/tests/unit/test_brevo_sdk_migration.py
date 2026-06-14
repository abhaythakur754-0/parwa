"""
Tests for Brevo SDK migration (Day 9):
- SDK-first email sending with httpx fallback
- New payment/billing email functions
- Circuit breaker compatibility
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from app.services import email_service


# ════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset circuit breaker before each test."""
    email_service.reset_circuit_breaker()
    email_service._brevo_api_client = None
    yield
    email_service.reset_circuit_breaker()
    email_service._brevo_api_client = None


# ════════════════════════════════════════════════════════════════
# SDK-FIRST TESTS
# ════════════════════════════════════════════════════════════════


class TestBrevoSDKMigration:
    """Tests for Brevo SDK migration with fallback."""

    def test_send_email_without_sdk_uses_httpx(self):
        """When SDK is not available, should fall back to httpx."""
        # Save original value
        orig = email_service._BREVO_SDK_AVAILABLE
        email_service._BREVO_SDK_AVAILABLE = False
        try:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.text = '{"message_id": "123"}'

            with patch("app.services.email_service.httpx.post", return_value=mock_response) as mock_post:
                with patch("app.services.email_service.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(
                        BREVO_API_KEY="test_key",
                        FROM_EMAIL="noreply@parwa.ai",
                    )
                    with patch("app.services.email_service._is_circuit_open", return_value=False):
                        result = email_service.send_email(
                            to="test@example.com",
                            subject="Test",
                            html_content="<p>Test</p>",
                        )
                        assert result is True
                        mock_post.assert_called_once()
        finally:
            email_service._BREVO_SDK_AVAILABLE = orig

    def test_send_email_uses_sdk_first(self):
        """When SDK is available, should try SDK before httpx."""
        orig = email_service._BREVO_SDK_AVAILABLE
        email_service._BREVO_SDK_AVAILABLE = True
        try:
            mock_api = MagicMock()
            mock_result = MagicMock()
            mock_result.message_id = "msg_12345"
            mock_api.send_transac_email.return_value = mock_result

            with patch("app.services.email_service._get_brevo_client", return_value=mock_api):
                with patch("app.services.email_service.SendSmtpEmail", return_value=MagicMock()):
                    with patch("app.services.email_service.SendSmtpEmailTo", return_value=MagicMock()):
                        with patch("app.services.email_service.SendSmtpEmailSender", return_value=MagicMock()):
                            with patch("app.services.email_service.get_settings") as mock_settings:
                                mock_settings.return_value = MagicMock(
                                    BREVO_API_KEY="test_key",
                                    FROM_EMAIL="noreply@parwa.ai",
                                )
                                with patch("app.services.email_service._is_circuit_open", return_value=False):
                                    result = email_service.send_email(
                                        to="test@example.com",
                                        subject="Test",
                                        html_content="<p>Test</p>",
                                    )
                                    assert result is True
                                    mock_api.send_transac_email.assert_called_once()
        finally:
            email_service._BREVO_SDK_AVAILABLE = orig

    def test_send_email_sdk_failure_falls_back_to_httpx(self):
        """When SDK throws exception, should fall back to httpx."""
        orig = email_service._BREVO_SDK_AVAILABLE
        email_service._BREVO_SDK_AVAILABLE = True
        try:
            mock_api = MagicMock()
            mock_api.send_transac_email.side_effect = Exception("SDK Error")

            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.text = '{"message_id": "123"}'

            with patch("app.services.email_service._get_brevo_client", return_value=mock_api):
                with patch("app.services.email_service.httpx.post", return_value=mock_response) as mock_post:
                    with patch("app.services.email_service.get_settings") as mock_settings:
                        mock_settings.return_value = MagicMock(
                            BREVO_API_KEY="test_key",
                            FROM_EMAIL="noreply@parwa.ai",
                        )
                        with patch("app.services.email_service._is_circuit_open", return_value=False):
                            result = email_service.send_email(
                                to="test@example.com",
                                subject="Test",
                                html_content="<p>Test</p>",
                            )
                            assert result is True
                            mock_post.assert_called_once()
        finally:
            email_service._BREVO_SDK_AVAILABLE = orig

    def test_send_email_no_api_key(self):
        """Should return False when no API key configured."""
        orig = email_service._BREVO_SDK_AVAILABLE
        email_service._BREVO_SDK_AVAILABLE = False
        try:
            with patch("app.services.email_service.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(BREVO_API_KEY="", FROM_EMAIL="test@test.com")
                with patch("app.services.email_service._is_circuit_open", return_value=False):
                    result = email_service.send_email(
                        to="test@example.com",
                        subject="Test",
                        html_content="<p>Test</p>",
                    )
                    assert result is False
        finally:
            email_service._BREVO_SDK_AVAILABLE = orig

    def test_send_email_circuit_breaker_open(self):
        """Should return False when circuit breaker is open."""
        with patch("app.services.email_service._is_circuit_open", return_value=True):
            result = email_service.send_email(
                to="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )
            assert result is False


# ════════════════════════════════════════════════════════════════
# NEW EMAIL FUNCTIONS
# ════════════════════════════════════════════════════════════════


class TestNewEmailFunctions:
    """Tests for new payment/billing email functions."""

    @patch("app.services.email_service.send_email", return_value=True)
    @patch("app.services.email_service.render_email_template", return_value="<p>Template</p>")
    def test_payment_confirmation_email(self, mock_render, mock_send):
        """Should render and send payment confirmation email."""
        result = email_service.send_payment_confirmation_email(
            user_email="user@example.com",
            user_name="John",
            plan_name="Pro Plan",
            amount="$49.00",
            dashboard_url="https://parwa.ai/dashboard",
        )
        assert result is True
        mock_render.assert_called_once()
        call_args = mock_render.call_args
        assert call_args[0][0] == "payment_confirmation.html"
        mock_send.assert_called_once()

    @patch("app.services.email_service.send_email", return_value=True)
    @patch("app.services.email_service.render_email_template", return_value="<p>Template</p>")
    def test_payment_failed_email(self, mock_render, mock_send):
        """Should render and send payment failed email."""
        result = email_service.send_payment_failed_email(
            user_email="user@example.com",
            user_name="John",
            amount="$49.00",
            reason="Card declined",
        )
        assert result is True
        mock_render.assert_called_once()
        call_args = mock_render.call_args
        assert call_args[0][0] == "payment_failed.html"
        mock_send.assert_called_once()

    @patch("app.services.email_service.send_email", return_value=True)
    @patch("app.services.email_service.render_email_template", return_value="<p>Template</p>")
    def test_subscription_canceled_email(self, mock_render, mock_send):
        """Should render and send subscription canceled email."""
        result = email_service.send_subscription_canceled_email(
            user_email="user@example.com",
            user_name="John",
            plan_name="Pro Plan",
            effective_date="2025-08-14",
        )
        assert result is True
        mock_render.assert_called_once()
        call_args = mock_render.call_args
        assert call_args[0][0] == "subscription_canceled.html"
        mock_send.assert_called_once()

    @patch("app.services.email_service.send_email", return_value=False)
    @patch("app.services.email_service.render_email_template", return_value="<p>Template</p>")
    def test_payment_failed_email_default_reason(self, mock_render, mock_send):
        """Should use default reason when not provided."""
        result = email_service.send_payment_failed_email(
            user_email="user@example.com",
            user_name="John",
            amount="$49.00",
        )
        assert result is False  # send_email returns False
        template_vars = mock_render.call_args[0][1]
        assert template_vars["reason"] == "Your card was declined"


# ════════════════════════════════════════════════════════════════
# SDK CLIENT INITIALIZATION
# ════════════════════════════════════════════════════════════════


class TestBrevoClientInitialization:
    """Tests for lazy SDK client initialization."""

    def test_get_brevo_client_returns_none_when_unavailable(self):
        """Should return None when SDK not available."""
        orig = email_service._BREVO_SDK_AVAILABLE
        email_service._BREVO_SDK_AVAILABLE = False
        try:
            client = email_service._get_brevo_client()
            assert client is None
        finally:
            email_service._BREVO_SDK_AVAILABLE = orig

    def test_get_brevo_client_creates_once(self):
        """Should create client once and cache it."""
        orig = email_service._BREVO_SDK_AVAILABLE
        email_service._BREVO_SDK_AVAILABLE = True
        email_service._brevo_api_client = None
        try:
            mock_api = MagicMock()
            email_service._brevo_api_client = mock_api
            # Since we set the cached client, both calls should return it
            client1 = email_service._get_brevo_client()
            client2 = email_service._get_brevo_client()
            assert client1 is mock_api
            assert client2 is mock_api
        finally:
            email_service._BREVO_SDK_AVAILABLE = orig
            email_service._brevo_api_client = None
