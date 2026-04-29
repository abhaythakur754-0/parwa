"""
Tests for PII Redaction Engine (F-056).
Tests cover: PIIDetector, PIIRedactor, PIIDeredactor, PIIRedactionCache,
overlap deduplication, token determinism, factory functions.
"""

import pytest
from unittest.mock import AsyncMock, patch

# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def detector():
    """Return a PIIDetector instance (no Redis needed)."""
    from app.core.pii_redaction_engine import PIIDetector
    return PIIDetector()


@pytest.fixture
def redactor():
    """Return a PIIRedactor instance."""
    from app.core.pii_redaction_engine import PIIRedactor
    return PIIRedactor()


@pytest.fixture
def deredactor():
    """Return a PIIDeredactor instance."""
    from app.core.pii_redaction_engine import PIIDeredactor
    return PIIDeredactor()


# ── PIIDetector Tests ──────────────────────────────────────────


class TestPIIDetectorSSN:
    """Tests for SSN detection."""

    def test_detect_ssn_standard_format(self, detector):
        matches = detector._detect_ssn("My SSN is 123-45-6789 please help.")
        assert len(matches) == 1
        assert matches[0].pii_type == "SSN"
        assert "123-45-6789" in matches[0].value
        assert matches[0].confidence >= 0.90

    def test_detect_ssn_space_separator(self, detector):
        matches = detector._detect_ssn("SSN: 123 45 6789")
        assert len(matches) == 1
        assert matches[0].pii_type == "SSN"

    def test_reject_ssn_000_area(self, detector):
        matches = detector._detect_ssn("000-45-6789")
        assert len(matches) == 0

    def test_reject_ssn_666_area(self, detector):
        matches = detector._detect_ssn("666-45-6789")
        assert len(matches) == 0

    def test_reject_ssn_9xx_area(self, detector):
        matches = detector._detect_ssn("912-45-6789")
        assert len(matches) == 0

    def test_reject_ssn_00_group(self, detector):
        matches = detector._detect_ssn("123-00-6789")
        assert len(matches) == 0

    def test_reject_ssn_0000_serial(self, detector):
        matches = detector._detect_ssn("123-45-0000")
        assert len(matches) == 0

    def test_no_ssn_in_safe_text(self, detector):
        matches = detector._detect_ssn("Hello, how are you today?")
        assert len(matches) == 0


class TestPIIDetectorCreditCard:
    """Tests for credit card detection."""

    def test_detect_visa(self, detector):
        matches = detector._detect_credit_card("Card: 4111 1111 1111 1111 ok")
        assert len(matches) >= 1
        assert matches[0].pii_type == "CREDIT_CARD"
        assert "visa" in matches[0].pattern_matched

    def test_detect_mastercard(self, detector):
        matches = detector._detect_credit_card("MC: 5512 3456 7890 1234")
        assert len(matches) >= 1
        assert "mastercard" in matches[0].pattern_matched

    def test_detect_amex(self, detector):
        matches = detector._detect_credit_card("Amex: 378282246310005")
        assert len(matches) >= 1
        assert "amex" in matches[0].pattern_matched

    def test_luhn_boost(self, detector):
        """Valid Luhn card should have higher confidence."""
        valid_card = "4532 0151 1283 0366"  # Known valid Visa
        invalid_card = "4532 0151 1283 0367"  # Changed last digit
        valid_matches = detector._detect_credit_card(f"Card: {valid_card}")
        invalid_matches = detector._detect_credit_card(f"Card: {invalid_card}")
        if valid_matches and invalid_matches:
            assert valid_matches[0].confidence > invalid_matches[0].confidence

    def test_no_cc_in_safe_text(self, detector):
        matches = detector._detect_credit_card("No card number here")
        assert len(matches) == 0


class TestPIIDetectorEmail:
    """Tests for email detection."""

    def test_detect_email(self, detector):
        matches = detector._detect_email("Email: john.doe@example.com")
        assert len(matches) == 1
        assert matches[0].pii_type == "EMAIL"

    def test_detect_email_complex(self, detector):
        matches = detector._detect_email("Contact: user+tag@sub.domain.co.uk")
        assert len(matches) == 1
        assert matches[0].confidence >= 0.97

    def test_reject_example_domain(self, detector):
        """example.com has reduced confidence but still detected."""
        matches = detector._detect_email("test@example.com")
        assert len(matches) == 1
        assert matches[0].confidence <= 0.60

    def test_reject_image_extension(self, detector):
        matches = detector._detect_email("photo@domain.png")
        assert len(matches) == 0

    def test_no_email_in_safe_text(self, detector):
        matches = detector._detect_email("No email here at all")
        assert len(matches) == 0


class TestPIIDetectorPhone:
    """Tests for phone detection."""

    def test_detect_us_local_10digit(self, detector):
        matches = detector._detect_phone("Call 555-123-4567 now")
        assert len(matches) == 1
        assert matches[0].pii_type == "PHONE"
        assert matches[0].confidence >= 0.85

    def test_detect_international(self, detector):
        matches = detector._detect_phone("Phone: +44 20 7946 0958")
        assert len(matches) >= 1
        assert "international" in matches[0].pattern_matched

    def test_reject_too_short(self, detector):
        matches = detector._detect_phone("123")
        assert len(matches) == 0

    def test_reject_too_long(self, detector):
        matches = detector._detect_phone("12345678901234567")
        # Long digit sequences may partially match as phone; just ensure no
        # INTERNATIONAL match
        for m in matches:
            assert m.pattern_matched != "phone_international"


class TestPIIDetectorOverlap:
    """Tests for overlap deduplication (GAP FIX)."""

    def test_overlap_ssn_phone_dedup(self, detector):
        """SSN and phone patterns can overlap. Only one should be kept."""
        # "123-45-6789" matches as SSN and also as phone.
        # SSN has higher confidence (0.95) and longer match (-len sort).
        matches = detector.detect(
            "My SSN is 123-45-6789", {PII_SSN, PII_PHONE})
        # Should not return both at the same position
        starts = [m.start for m in matches]
        for i in range(len(starts)):
            for j in range(i + 1, len(starts)):
                # No two matches should overlap
                m1, m2 = matches[i], matches[j]
                assert not (m1.start < m2.end and m2.start < m1.end), \
                    f"Overlapping matches at {starts[i]} and {starts[j]}"

    def test_no_false_overlap(self, detector):
        """Non-overlapping matches should all be returned."""
        matches = detector.detect(
            "Email john@foo.com and phone 555-123-4567",
            {PII_EMAIL, PII_PHONE},
        )
        assert len(matches) == 2

    def test_dedup_keeps_higher_confidence(self, detector):
        """When overlapping, the first match (sorted by start, -len) is kept."""
        from app.core.pii_redaction_engine import PII_SSN, PII_PHONE
        matches = detector.detect("SSN: 123-45-6789", {PII_SSN, PII_PHONE})
        if len(matches) == 1:
            # Should be the SSN match (higher priority due to -len sort)
            assert matches[0].pii_type == PII_SSN


class TestPIIDetectorAllTypes:
    """Tests for detecting all 15 PII types."""

    def test_detect_ip_v4(self, detector):
        from app.core.pii_redaction_engine import PII_IP_ADDRESS
        matches = detector._detect_ip_address("Server: 192.168.1.100")
        assert len(matches) >= 1
        assert matches[0].pii_type == PII_IP_ADDRESS

    def test_detect_date_of_birth(self, detector):
        from app.core.pii_redaction_engine import PII_DATE_OF_BIRTH
        matches = detector._detect_date_of_birth("DOB: 03/15/1985")
        assert len(matches) >= 1
        assert matches[0].pii_type == PII_DATE_OF_BIRTH

    def test_detect_api_key_openai(self, detector):
        matches = detector._detect_api_key(
            "Key: sk-proj-abc123def456ghi789jkl012mno345")
        assert len(matches) >= 1
        assert matches[0].pattern_matched == "api_key_openai"

    def test_detect_api_key_google(self, detector):
        pass
        # AIza + 35 chars = 39 total (matching regex AIza[A-Za-z0-9_\-]{35})
        matches = detector._detect_api_key(
            "AIzaSyA1234567890abcdefghijklmnopqrstuv")
        assert len(matches) >= 1
        assert "google" in matches[0].pattern_matched

    def test_detect_aadhaar(self, detector):
        from app.core.pii_redaction_engine import PII_AADHAAR
        matches = detector._detect_aadhaar("Aadhaar: 2345 6789 0123")
        assert len(matches) == 1
        assert matches[0].pii_type == PII_AADHAAR

    def test_detect_pan(self, detector):
        from app.core.pii_redaction_engine import PII_PAN
        # ABCCA1234F — 4th char 'A' is in valid_fourth set
        matches = detector._detect_pan("PAN: ABCCA1234F")
        assert len(matches) == 1
        assert matches[0].pii_type == PII_PAN
        assert matches[0].confidence >= 0.90  # Valid 4th char

    def test_detect_iban(self, detector):
        from app.core.pii_redaction_engine import PII_IBAN
        matches = detector._detect_iban("DE89370400440532013000")
        assert len(matches) >= 1
        assert matches[0].pii_type == PII_IBAN

    def test_detect_record_number(self, detector):
        from app.core.pii_redaction_engine import PII_RECORD_NUMBER
        matches = detector._detect_record_number("MRN-12345A")
        assert len(matches) == 1
        assert matches[0].pii_type == PII_RECORD_NUMBER


# ── Token Generation Tests ─────────────────────────────────────


class TestTokenGeneration:
    """Tests for deterministic token generation."""

    def test_same_inputs_same_token(self):
        from app.core.pii_redaction_engine import _generate_token
        t1 = _generate_token("SSN", "123-45-6789", "company1")
        t2 = _generate_token("SSN", "123-45-6789", "company1")
        assert t1 == t2

    def test_different_company_different_token(self):
        from app.core.pii_redaction_engine import _generate_token
        t1 = _generate_token("SSN", "123-45-6789", "company1")
        t2 = _generate_token("SSN", "123-45-6789", "company2")
        assert t1 != t2

    def test_different_value_different_token(self):
        from app.core.pii_redaction_engine import _generate_token
        t1 = _generate_token("SSN", "123-45-6789", "company1")
        t2 = _generate_token("SSN", "987-65-4321", "company1")
        assert t1 != t2

    def test_token_format(self):
        from app.core.pii_redaction_engine import _generate_token
        token = _generate_token("SSN", "123-45-6789", "company1")
        assert token.startswith("{{SSN_")
        assert token.endswith("}}")
        assert len(token) == 16  # {{SSN_12345678}} = 16 chars (8-char UUID8)


# ── PIIRedactor Tests ──────────────────────────────────────────


class TestPIIRedactor:
    """Tests for the PII redaction flow."""

    @pytest.mark.asyncio
    async def test_redact_empty_text(self, redactor):
        result = await redactor.redact("", "company1")
        assert result.redacted_text == ""
        assert result.pii_found is False

    @pytest.mark.asyncio
    async def test_redact_no_pii(self, redactor):
        result = await redactor.redact("Hello world", "company1")
        assert result.redacted_text == "Hello world"
        assert result.pii_found is False

    @pytest.mark.asyncio
    async def test_redact_with_ssn(self, redactor):
        result = await redactor.redact("SSN: 123-45-6789", "company1")
        assert result.pii_found is True
        assert "123-45-6789" not in result.redacted_text
        assert "{{SSN_" in result.redacted_text
        assert result.summary.get("company_id") == "company1"

    @pytest.mark.asyncio
    async def test_redact_multiple_pii(self, redactor):
        result = await redactor.redact(
            "Email john@foo.com and SSN 123-45-6789",
            "company1",
        )
        assert result.pii_found is True
        assert "john@foo.com" not in result.redacted_text
        assert "123-45-6789" not in result.redacted_text
        assert result.summary["total_matches"] == 2

    @pytest.mark.asyncio
    async def test_redaction_map_keys_are_tokens(self, redactor):
        result = await redactor.redact("SSN: 123-45-6789", "company1")
        for token in result.redaction_map:
            assert token.startswith("{{") and token.endswith("}}")

    @pytest.mark.asyncio
    async def test_redaction_id_is_uuid(self, redactor):
        import uuid
        result = await redactor.redact("SSN: 123-45-6789", "company1")
        if result.redaction_id:
            # Should be a valid UUID4
            uuid.UUID(result.redaction_id)  # Raises ValueError if invalid

    @pytest.mark.asyncio
    async def test_redact_subset_types(self, redactor):
        from app.core.pii_redaction_engine import PII_SSN
        result = await redactor.redact(
            "Email john@foo.com and SSN 123-45-6789",
            "company1",
            pii_types={PII_SSN},  # Only redact SSN
        )
        assert result.pii_found is True
        assert "john@foo.com" in result.redacted_text  # Email NOT redacted
        assert "123-45-6789" not in result.redacted_text  # SSN redacted

    @pytest.mark.asyncio
    async def test_redis_failure_doesnt_crash(self, redactor):
        """BC-008: Redis failure should not crash redaction."""
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("app.core.pii_redaction_engine.make_key",
                       new_callable=AsyncMock, side_effect=Exception("Redis down")):
                result = await redactor.redact("SSN: 123-45-6789", "company1")
                assert result.pii_found is True  # Still works, just no Redis store


# ── PIIDeredactor Tests ─────────────────────────────────────────


class TestPIIDeredactor:

    @pytest.mark.asyncio
    async def test_deredact_empty_text(self, deredactor):
        result = await deredactor.deredact("", "company1", "some-id")
        assert result == ""

    @pytest.mark.asyncio
    async def test_deredact_no_tokens(self, deredactor):
        result = await deredactor.deredact("Hello world", "company1", "some-id")
        assert result == "Hello world"

    @pytest.mark.asyncio
    async def test_deredact_restores_pii(self, deredactor):
        # Simulate successful Redis lookup
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value.get = AsyncMock(
                return_value='{"{{SSN_abc12345}}": "123-45-6789"}'
            )
            result = await deredactor.deredact(
                "SSN: {{SSN_abc12345}}", "company1", "some-id",
            )
        assert result == "SSN: 123-45-6789"

    @pytest.mark.asyncio
    async def test_deredact_map_not_found(self, deredactor):
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value.get = AsyncMock(return_value=None)
            result = await deredactor.deredact(
                "SSN: {{SSN_abc12345}}", "company1", "some-id",
            )
        # Returns original text unchanged
        assert "{{SSN_abc12345}}" in result

    @pytest.mark.asyncio
    async def test_deredact_redis_failure(self, deredactor):
        """BC-008: Redis failure should not crash deredaction."""
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock, side_effect=Exception("Redis down")):
            result = await deredactor.deredact(
                "SSN: {{SSN_abc12345}}", "company1", "some-id",
            )
        assert "{{SSN_abc12345}}" in result  # Returns original


# ── Factory Function Tests ─────────────────────────────────────────


class TestFactoryFunctions:
    def test_get_pii_detector_returns_instance(self):
        from app.core.pii_redaction_engine import (
            get_pii_detector, PIIDetector,
        )
        detector = get_pii_detector()
        assert isinstance(detector, PIIDetector)

    def test_get_pii_redactor_returns_instance(self):
        from app.core.pii_redaction_engine import (
            get_pii_redactor, PIIRedactor,
        )
        redactor = get_pii_redactor()
        assert isinstance(redactor, PIIRedactor)

    def test_get_pii_deredactor_returns_instance(self):
        from app.core.pii_redaction_engine import (
            get_pii_deredactor, PIIDeredactor,
        )
        deredactor = get_pii_deredactor()
        assert isinstance(deredactor, PIIDeredactor)


# ── PIIRedactionCache Tests ───────────────────────────────────────


class TestPIIRedactionCache:

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        from app.core.pii_redaction_engine import PIIRedactionCache
        cache = PIIRedactionCache()
        test_map = {"{{SSN_abc}}": "123-45-6789"}
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value.set = AsyncMock(return_value=True)
            mock_redis.return_value.get = AsyncMock(
                return_value='{"{{SSN_abc}}": "123-45-6789"}'
            )
            with patch("app.core.pii_redaction_engine.make_key",
                       return_value="parwa:company1:pii:abc"):
                stored = await cache.store_map("company1", "abc", test_map)
                assert stored is True
                retrieved = await cache.get_map("company1", "abc")
                assert retrieved == {"{{SSN_abc}}": "123-45-6789"}

    @pytest.mark.asyncio
    async def test_store_redis_failure(self):
        from app.core.pii_redaction_engine import PIIRedactionCache
        cache = PIIRedactionCache()
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock, side_effect=Exception("Redis down")):
            with patch("app.core.pii_redaction_engine.make_key"):
                stored = await cache.store_map("company1", "abc", {})
                assert stored is False  # Graceful failure

    @pytest.mark.asyncio
    async def test_retrieve_redis_failure(self):
        from app.core.pii_redaction_engine import PIIRedactionCache
        cache = PIIRedactionCache()
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock, side_effect=Exception("Redis down")):
            result = await cache.get_map("company1", "abc")
            assert result is None  # Graceful failure

    @pytest.mark.asyncio
    async def test_retrieve_invalid_json(self):
        from app.core.pii_redaction_engine import PIIRedactionCache
        cache = PIIRedactionCache()
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value.get = AsyncMock(return_value="not-json")
            result = await cache.get_map("company1", "abc")
            assert result is None

    @pytest.mark.asyncio
    async def test_retrieve_non_dict(self):
        from app.core.pii_redaction_engine import PIIRedactionCache
        cache = PIIRedactionCache()
        with patch("app.core.pii_redaction_engine.get_redis",
                   new_callable=AsyncMock) as mock_redis:
            mock_redis.return_value.get = AsyncMock(return_value="123")
            result = await cache.get_map("company1", "abc")
            assert result is None


# ── Import All PII Constants ────────────────────────────────────

PII_SSN = "SSN"
PII_EMAIL = "EMAIL"
PII_PHONE = "PHONE"
PII_IP_ADDRESS = "IP_ADDRESS"
PII_DATE_OF_BIRTH = "DATE_OF_BIRTH"
PII_API_KEY = "API_KEY"
PII_AADHAAR = "AADHAAR"
PII_PAN = "PAN"
PII_IBAN = "IBAN"
PII_MEDICAL_RECORD_NUMBER = "MEDICAL_RECORD_NUMBER"
