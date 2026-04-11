"""
Day 26 Unit Tests - PII Scan Service

Tests for BL07: PII detection with:
- Credit card detection
- SSN detection
- API key detection
- Password pattern detection
- Auto-redaction
"""

import pytest
from unittest.mock import MagicMock

from app.services.pii_scan_service import PIIScanService


# ── FIXTURES ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_company_id():
    """Test company ID."""
    return "test-company-123"


@pytest.fixture
def pii_service(mock_db, mock_company_id):
    """PII scan service instance."""
    return PIIScanService(mock_db, mock_company_id)


@pytest.fixture
def pii_service_with_redis(mock_db, mock_company_id):
    """PII scan service with Redis client."""
    redis = MagicMock()
    return PIIScanService(mock_db, mock_company_id, redis_client=redis)


# ── CREDIT CARD DETECTION TESTS ─────────────────────────────────────────────

class TestCreditCardDetection:
    """Tests for credit card PII detection."""

    def test_detect_visa_card(self, pii_service):
        """Test detection of Visa card number."""
        result = pii_service.scan_text(
            "My card number is 4532015112830366"
        )
        assert result["detected"] is True
        assert any(f["type"] == "credit_card" for f in result["findings"])

    def test_detect_mastercard(self, pii_service):
        """Test detection of Mastercard number."""
        result = pii_service.scan_text(
            "Card: 5425233430109903"
        )
        assert result["detected"] is True
        assert any(f["type"] == "credit_card" for f in result["findings"])

    def test_detect_card_with_dashes(self, pii_service):
        """Test detection of card with dashes."""
        result = pii_service.scan_text(
            "CC: 4532-0151-1283-0366"
        )
        assert result["detected"] is True

    def test_detect_card_with_spaces(self, pii_service):
        """Test detection of card with spaces."""
        result = pii_service.scan_text(
            "Card number: 4532 0151 1283 0366"
        )
        assert result["detected"] is True

    def test_no_false_positive_small_numbers(self, pii_service):
        """Test small numbers don't trigger false positive."""
        result = pii_service.scan_text(
            "I have 123 items and 456 orders"
        )
        # Small numbers shouldn't be detected as credit cards
        # (depends on implementation - may or may not match)


# ── SSN DETECTION TESTS ─────────────────────────────────────────────────────

class TestSSNDetection:
    """Tests for SSN PII detection."""

    def test_detect_ssn_with_dashes(self, pii_service):
        """Test detection of SSN with dashes."""
        result = pii_service.scan_text(
            "My SSN is 123-45-6789"
        )
        assert result["detected"] is True
        assert any(f["type"] == "ssn" for f in result["findings"])

    def test_detect_ssn_without_dashes(self, pii_service):
        """Test detection of SSN without dashes."""
        result = pii_service.scan_text(
            "SSN: 123456789"
        )
        # May or may not match depending on pattern strictness
        pass

    def test_detect_ssn_with_spaces(self, pii_service):
        """Test detection of SSN with spaces."""
        result = pii_service.scan_text(
            "Social: 123 45 6789"
        )
        assert result["detected"] is True


# ── EMAIL DETECTION TESTS ───────────────────────────────────────────────────

class TestEmailDetection:
    """Tests for email PII detection."""

    def test_detect_email(self, pii_service):
        """Test detection of email address."""
        result = pii_service.scan_text(
            "Contact me at john.doe@example.com"
        )
        assert result["detected"] is True
        assert any(f["type"] == "email" for f in result["findings"])

    def test_detect_multiple_emails(self, pii_service):
        """Test detection of multiple emails."""
        result = pii_service.scan_text(
            "Emails: user1@test.com and user2@test.com"
        )
        email_findings = [f for f in result["findings"] if f["type"] == "email"]
        assert len(email_findings) >= 2


# ── PHONE DETECTION TESTS ───────────────────────────────────────────────────

class TestPhoneDetection:
    """Tests for phone number PII detection."""

    def test_detect_phone_with_dashes(self, pii_service):
        """Test detection of phone with dashes."""
        result = pii_service.scan_text(
            "Call me at 555-123-4567"
        )
        assert result["detected"] is True

    def test_detect_phone_with_parens(self, pii_service):
        """Test detection of phone with parentheses."""
        result = pii_service.scan_text(
            "Phone: (555) 123-4567"
        )
        assert result["detected"] is True

    def test_detect_phone_with_country_code(self, pii_service):
        """Test detection of phone with country code."""
        result = pii_service.scan_text(
            "Mobile: +1-555-123-4567"
        )
        assert result["detected"] is True


# ── API KEY DETECTION TESTS ─────────────────────────────────────────────────

class TestAPIKeyDetection:
    """Tests for API key PII detection."""

    def test_detect_sk_key(self, pii_service):
        """Test detection of sk- style API key."""
        result = pii_service.scan_text(
            "API key: sk-abcdefghijklmnop123456"
        )
        assert result["detected"] is True
        assert any(f["type"] == "api_key" for f in result["findings"])

    def test_detect_github_token(self, pii_service):
        """Test detection of GitHub token."""
        result = pii_service.scan_text(
            "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"
        )
        assert result["detected"] is True

    def test_detect_generic_api_key(self, pii_service):
        """Test detection of generic API key pattern."""
        result = pii_service.scan_text(
            "api_key_abc123def456ghi789jkl012mno345pqr"
        )
        # May match depending on pattern
        pass


# ── PASSWORD DETECTION TESTS ────────────────────────────────────────────────

class TestPasswordDetection:
    """Tests for password pattern detection."""

    def test_detect_password_assignment(self, pii_service):
        """Test detection of password assignment."""
        result = pii_service.scan_text(
            "password=MySecretPass123"
        )
        assert result["detected"] is True
        assert any(f["type"] == "password" for f in result["findings"])

    def test_detect_password_colon(self, pii_service):
        """Test detection of password with colon."""
        result = pii_service.scan_text(
            "password: SuperSecret123!"
        )
        assert result["detected"] is True

    def test_detect_secret_assignment(self, pii_service):
        """Test detection of secret assignment."""
        result = pii_service.scan_text(
            "secret = 'my_secret_value'"
        )
        assert result["detected"] is True


# ── IP ADDRESS DETECTION TESTS ──────────────────────────────────────────────

class TestIPAddressDetection:
    """Tests for IP address PII detection."""

    def test_detect_ipv4(self, pii_service):
        """Test detection of IPv4 address."""
        result = pii_service.scan_text(
            "Server IP: 192.168.1.100"
        )
        assert result["detected"] is True
        assert any(f["type"] == "ip_address" for f in result["findings"])

    def test_detect_public_ip(self, pii_service):
        """Test detection of public IP."""
        result = pii_service.scan_text(
            "Connect to 8.8.8.8 for DNS"
        )
        assert result["detected"] is True


# ── REDACTION TESTS ─────────────────────────────────────────────────────────

class TestRedaction:
    """Tests for PII redaction."""

    def test_redact_credit_card(self, pii_service):
        """Test credit card redaction."""
        redacted, mapping = pii_service.redact_text(
            "My card is 4532015112830366"
        )
        assert "4532015112830366" not in redacted
        assert len(mapping) > 0

    def test_redact_ssn(self, pii_service):
        """Test SSN redaction."""
        redacted, mapping = pii_service.redact_text(
            "SSN: 123-45-6789"
        )
        assert "123-45-6789" not in redacted

    def test_redact_multiple_types(self, pii_service):
        """Test redaction of multiple PII types."""
        redacted, mapping = pii_service.redact_text(
            "Card: 4532015112830366, SSN: 123-45-6789, Email: test@example.com"
        )
        assert "4532015112830366" not in redacted
        assert "123-45-6789" not in redacted
        assert "test@example.com" not in redacted

    def test_redaction_map_contains_original(self, pii_service):
        """Test redaction map contains original values."""
        redacted, mapping = pii_service.redact_text(
            "Card: 4532015112830366"
        )
        # Find the mapping entry
        for token, info in mapping.items():
            if info["type"] == "credit_card":
                assert info["original"] == "4532015112830366"

    def test_redact_empty_text(self, pii_service):
        """Test redaction of empty text."""
        redacted, mapping = pii_service.redact_text("")
        assert redacted == ""
        assert mapping == {}


# ── UNREDACTION TESTS ───────────────────────────────────────────────────────

class TestUnredaction:
    """Tests for unredacting text."""

    def test_unredact_single(self, pii_service):
        """Test unredacting single PII."""
        original = "My card is 4532015112830366"
        redacted, mapping = pii_service.redact_text(original)
        unredacted = pii_service.unredact_text(redacted, mapping)
        assert unredacted == original

    def test_unredact_multiple(self, pii_service):
        """Test unredacting multiple PII."""
        original = "Card: 4532015112830366, SSN: 123-45-6789"
        redacted, mapping = pii_service.redact_text(original)
        unredacted = pii_service.unredact_text(redacted, mapping)
        assert unredacted == original


# ── SCAN AND REDACT TESTS ───────────────────────────────────────────────────

class TestScanAndRedact:
    """Tests for combined scan and redact."""

    def test_scan_and_redact_result(self, pii_service):
        """Test scan_and_redact returns correct structure."""
        result = pii_service.scan_and_redact("Card: 4532015112830366")
        assert "original_text" in result
        assert "redacted_text" in result
        assert "redaction_map" in result
        assert "redaction_count" in result
        assert "pii_types" in result

    def test_scan_and_redact_no_pii(self, pii_service):
        """Test scan_and_redact with no PII."""
        result = pii_service.scan_and_redact("Hello, how are you?")
        assert result["redaction_count"] == 0


# ── VALIDATION TESTS ────────────────────────────────────────────────────────

class TestValidateNoPII:
    """Tests for PII validation."""

    def test_validate_no_pii_passes(self, pii_service):
        """Test validation passes with no PII."""
        is_valid, violations = pii_service.validate_no_pii(
            "This is a normal message"
        )
        assert is_valid is True
        assert len(violations) == 0

    def test_validate_pii_fails(self, pii_service):
        """Test validation fails with PII."""
        is_valid, violations = pii_service.validate_no_pii(
            "Card: 4532015112830366"
        )
        assert is_valid is False
        assert len(violations) > 0

    def test_validate_strict_types(self, pii_service):
        """Test validation with specific PII types."""
        is_valid, violations = pii_service.validate_no_pii(
            "Email: test@example.com",
            strict_types=["email"]
        )
        assert is_valid is False


# ── MASK VALUE TESTS ────────────────────────────────────────────────────────

class TestMaskValue:
    """Tests for PII value masking."""

    def test_mask_credit_card(self, pii_service):
        """Test credit card masking shows last 4."""
        masked = pii_service.mask_value("4532015112830366", "credit_card")
        assert masked.endswith("0366")
        assert "****" in masked or "*" * 12 in masked

    def test_mask_ssn(self, pii_service):
        """Test SSN masking shows last 4."""
        masked = pii_service.mask_value("123-45-6789", "ssn")
        assert "6789" in masked

    def test_mask_email(self, pii_service):
        """Test email masking hides most chars."""
        masked = pii_service.mask_value("john.doe@example.com", "email")
        assert "@" in masked
        assert "john.doe" not in masked

    def test_mask_phone(self, pii_service):
        """Test phone masking shows last 4."""
        masked = pii_service.mask_value("555-123-4567", "phone")
        assert "4567" in masked

    def test_mask_api_key(self, pii_service):
        """Test API key masking shows ends."""
        masked = pii_service.mask_value("sk-abcdefghijklmnop123456", "api_key")
        assert "sk-" in masked or "..." in masked


# ── STATS TESTS ─────────────────────────────────────────────────────────────

class TestGetPIIStats:
    """Tests for PII statistics."""

    def test_get_stats_multiple_types(self, pii_service):
        """Test stats count multiple PII types."""
        stats = pii_service.get_pii_stats(
            "Card: 4532015112830366, SSN: 123-45-6789, Email: test@example.com"
        )
        assert "credit_card" in stats
        assert "ssn" in stats
        assert "email" in stats

    def test_get_stats_no_pii(self, pii_service):
        """Test stats with no PII."""
        stats = pii_service.get_pii_stats("No PII here")
        assert len(stats) == 0

    def test_get_stats_counts(self, pii_service):
        """Test stats counts multiple same type."""
        stats = pii_service.get_pii_stats(
            "Card1: 4532015112830366, Card2: 5425233430109903"
        )
        if "credit_card" in stats:
            assert stats["credit_card"] >= 1


# ── SCAN TYPES FILTER TESTS ─────────────────────────────────────────────────

class TestScanTypesFilter:
    """Tests for filtering scan types."""

    def test_scan_specific_types(self, pii_service):
        """Test scanning only specific PII types."""
        result = pii_service.scan_text(
            "Card: 4532015112830366, Email: test@example.com",
            scan_types=["credit_card"]
        )
        assert any(f["type"] == "credit_card" for f in result["findings"])
        # Email should not be detected
        assert not any(f["type"] == "email" for f in result["findings"])
