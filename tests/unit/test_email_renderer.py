"""
Day 8: Email Renderer Tests

Tests for Jinja2 email template rendering.
BC-006: All emails use templates (no hardcoded bodies).
"""

import pytest

from backend.app.core.email_renderer import render_email_template


class TestRenderEmailTemplate:
    """Tests for email template renderer."""

    def test_render_verification_email(self):
        """Verification email template renders correctly."""
        html = render_email_template(
            "verification_email.html",
            {
                "user_name": "Test User",
                "verification_url": "https://example.com/verify?token=abc",
            },
        )
        assert "Test User" in html
        assert "https://example.com/verify" in html
        assert "abc" in html
        assert "24 hours" in html

    def test_render_password_reset_email(self):
        """Password reset template renders correctly."""
        html = render_email_template(
            "password_reset_email.html",
            {
                "user_name": "John",
                "reset_url": "https://example.com/reset?token=xyz",
            },
        )
        assert "John" in html
        assert "https://example.com/reset" in html
        assert "15 minutes" in html

    def test_render_base_includes_parwa_branding(self):
        """Base template includes PARWA branding."""
        html = render_email_template(
            "verification_email.html",
            {
                "user_name": "User",
                "verification_url": "https://test.com",
            },
        )
        assert "PARWA" in html

    def test_render_invalid_template_raises(self):
        """Invalid template name raises ValueError."""
        with pytest.raises(ValueError):
            render_email_template(
                "nonexistent.html",
                {},
            )
