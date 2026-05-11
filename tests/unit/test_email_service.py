"""
Day 8: Email Service Tests

Tests for Brevo email client with circuit breaker.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services import email_service


@pytest.fixture(autouse=True)
def _setup_env():
    """Set required env vars for email tests."""
    os.environ["BREVO_API_KEY"] = "test-brevo-api-key"


@pytest.fixture(autouse=True)
def _reset_circuit():
    """Reset circuit breaker state before each test."""
    email_service.reset_circuit_breaker()


class TestCircuitBreaker:
    """Tests for circuit breaker pattern (BC-012)."""

    def test_starts_closed(self):
        """Circuit breaker should start closed."""
        assert email_service._is_circuit_open() is False

    def test_opens_after_threshold(self):
        """Circuit opens after 3 consecutive failures."""
        for _ in range(3):
            email_service._record_failure()
        assert email_service._is_circuit_open() is True

    def test_resets_on_success(self):
        """Success resets failure count."""
        email_service._record_failure()
        email_service._record_failure()
        email_service._record_success()
        assert email_service._cb_state["failures"] == 0
        assert email_service._is_circuit_open() is False


class TestSendEmail:
    """Tests for email sending via Brevo API."""

    @patch("backend.app.services.email_service.httpx")
    def test_send_success(self, mock_httpx):
        """Successful send returns True."""
        mock_httpx.post.return_value = MagicMock(
            status_code=200
        )
        result = email_service.send_email(
            to="test@example.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )
        assert result is True

    @patch("backend.app.services.email_service.httpx")
    def test_send_201_success(self, mock_httpx):
        """Brevo 201 is also success."""
        mock_httpx.post.return_value = MagicMock(
            status_code=201
        )
        result = email_service.send_email(
            to="test@example.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )
        assert result is True

    @patch("backend.app.services.email_service.httpx")
    def test_send_api_error(self, mock_httpx):
        """Brevo API error returns False."""
        mock_httpx.post.return_value = MagicMock(
            status_code=500,
            text="Internal Server Error",
        )
        result = email_service.send_email(
            to="test@example.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )
        assert result is False

    @patch("backend.app.services.email_service.httpx")
    def test_send_timeout(self, mock_httpx):
        """Timeout returns False and records failure."""
        from httpx import TimeoutException
        mock_httpx.post.side_effect = TimeoutException(
            "timed out"
        )
        result = email_service.send_email(
            to="test@example.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )
        assert result is False

    @patch("backend.app.services.email_service.httpx")
    def test_send_skipped_when_circuit_open(self, mock_httpx):
        """Send skipped when circuit breaker is open."""
        email_service._cb_state["is_open"] = True
        email_service._cb_state["last_failure"] = (
            __import__("time").time()
        )
        result = email_service.send_email(
            to="test@example.com",
            subject="Test",
            html_content="<p>Hello</p>",
        )
        assert result is False
        mock_httpx.post.assert_not_called()


class TestTemplateEmails:
    """Tests for verification and reset email sending."""

    @patch("backend.app.services.email_service.httpx")
    def test_send_verification_email(self, mock_httpx):
        """Verification email sends via Brevo template."""
        mock_httpx.post.return_value = MagicMock(
            status_code=200
        )
        result = email_service.send_verification_email(
            user_email="test@example.com",
            user_name="Test",
            verification_url=(
                "https://parwa.ai/verify?token=abc"
            ),
        )
        assert result is True
        call_args = mock_httpx.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert "Verify your PARWA" in payload["subject"]

    @patch("backend.app.services.email_service.httpx")
    def test_send_password_reset_email(self, mock_httpx):
        """Password reset email sends via Brevo template."""
        mock_httpx.post.return_value = MagicMock(
            status_code=200
        )
        result = email_service.send_password_reset_email(
            user_email="test@example.com",
            user_name="Test",
            reset_url=(
                "https://parwa.ai/reset?token=xyz"
            ),
        )
        assert result is True
        call_args = mock_httpx.post.call_args
        payload = call_args.kwargs.get("json", {})
        assert "Reset your PARWA" in payload["subject"]
