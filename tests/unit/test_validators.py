"""
Tests for shared/utils/validators.py

Tests email, phone, UUID, URL validation and string sanitization.
"""

from shared.utils.validators import (
    is_valid_email,
    is_valid_phone,
    is_valid_uuid,
    is_valid_url,
    sanitize_string,
)


class TestIsValidEmail:
    """Tests for email validation."""

    def test_valid_simple_email(self):
        assert is_valid_email("user@example.com") is True

    def test_valid_with_dots(self):
        assert is_valid_email("first.last@company.co") is True

    def test_valid_with_plus(self):
        assert is_valid_email("user+tag@gmail.com") is True

    def test_valid_with_hyphen(self):
        assert is_valid_email("user-name@domain.com") is True

    def test_valid_with_numbers(self):
        assert is_valid_email("user123@domain456.com") is True

    def test_valid_subdomain(self):
        assert is_valid_email("user@sub.domain.com") is True

    def test_valid_long_tld(self):
        assert is_valid_email("user@example.technology") is True

    def test_invalid_no_at(self):
        assert is_valid_email("userexample.com") is False

    def test_invalid_no_domain(self):
        assert is_valid_email("user@") is False

    def test_invalid_no_user(self):
        assert is_valid_email("@example.com") is False

    def test_invalid_double_at(self):
        assert is_valid_email("user@@example.com") is False

    def test_invalid_spaces(self):
        assert is_valid_email("user @example.com") is False

    def test_invalid_double_dots(self):
        assert is_valid_email("user@example..com") is False

    def test_none_returns_false(self):
        assert is_valid_email(None) is False

    def test_empty_returns_false(self):
        assert is_valid_email("") is False

    def test_non_string_returns_false(self):
        assert is_valid_email(123) is False

    def test_whitespace_only_returns_false(self):
        assert is_valid_email("   ") is False

    def test_too_long(self):
        long_email = "a" * 255 + "@test.com"
        assert is_valid_email(long_email) is False

    def test_strips_and_validates(self):
        assert is_valid_email("  user@example.com  ") is True


class TestIsValidPhone:
    """Tests for E.164 phone validation."""

    def test_valid_us(self):
        assert is_valid_phone("+14155552671") is True

    def test_valid_india(self):
        assert is_valid_phone("+919876543210") is True

    def test_valid_uk(self):
        assert is_valid_phone("+447911123456") is True

    def test_minimum_length(self):
        """E.164: 7 digits minimum."""
        assert is_valid_phone("+1234567") is True

    def test_maximum_length(self):
        """E.164: 15 digits maximum."""
        assert is_valid_phone("+123456789012345") is True

    def test_invalid_no_plus(self):
        assert is_valid_phone("14155552671") is False

    def test_invalid_letters(self):
        assert is_valid_phone("+1ABC5552671") is False

    def test_invalid_spaces(self):
        assert is_valid_phone("+1 415 555 2671") is False

    def test_invalid_too_short(self):
        assert is_valid_phone("+123456") is False

    def test_invalid_too_long(self):
        assert is_valid_phone("+1234567890123456") is False

    def test_invalid_starts_zero(self):
        """Country code cannot start with 0."""
        assert is_valid_phone("+04155552671") is False

    def test_none_returns_false(self):
        assert is_valid_phone(None) is False

    def test_empty_returns_false(self):
        assert is_valid_phone("") is False

    def test_non_string_returns_false(self):
        assert is_valid_phone(14155552671) is False


class TestIsValidUuid:
    """Tests for UUID validation."""

    def test_valid_uuid_v4(self):
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_lowercase(self):
        assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True

    def test_valid_uppercase(self):
        assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000") is True

    def test_valid_mixed_case(self):
        assert is_valid_uuid("550E8400-e29b-41d4-A716-446655440000") is True

    def test_invalid_no_hyphens(self):
        assert is_valid_uuid("550e8400e29b41d4a716446655440000") is False

    def test_invalid_wrong_length(self):
        assert is_valid_uuid("550e8400-e29b-41d4") is False

    def test_invalid_letters_outside_hex(self):
        assert is_valid_uuid("550g8400-e29b-41d4-a716-446655440000") is False

    def test_none_returns_false(self):
        assert is_valid_uuid(None) is False

    def test_empty_returns_false(self):
        assert is_valid_uuid("") is False

    def test_non_string_returns_false(self):
        assert is_valid_uuid(12345) is False

    def test_strips_and_validates(self):
        assert is_valid_uuid(
            "  550e8400-e29b-41d4-a716-446655440000  "
        ) is True


class TestIsValidUrl:
    """Tests for URL validation."""

    def test_valid_http(self):
        assert is_valid_url("http://example.com") is True

    def test_valid_https(self):
        assert is_valid_url("https://example.com") is True

    def test_valid_with_path(self):
        assert is_valid_url("https://example.com/api/v1/test") is True

    def test_valid_with_query(self):
        assert is_valid_url("https://example.com?page=1") is True

    def test_invalid_no_scheme(self):
        assert is_valid_url("example.com") is False

    def test_invalid_ftp(self):
        assert is_valid_url("ftp://example.com") is False

    def test_invalid_no_host(self):
        assert is_valid_url("https://") is False

    def test_none_returns_false(self):
        assert is_valid_url(None) is False

    def test_empty_returns_false(self):
        assert is_valid_url("") is False

    def test_non_string_returns_false(self):
        assert is_valid_url(123) is False

    def test_invalid_no_tld(self):
        assert is_valid_url("https://localhost") is False

    def test_strips_and_validates(self):
        assert is_valid_url("  https://example.com  ") is True


class TestSanitizeString:
    """Tests for string sanitization."""

    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_collapses_multiple_spaces(self):
        assert sanitize_string("hello    world") == "hello world"

    def test_truncates_to_max_length(self):
        result = sanitize_string("a" * 600, max_length=100)
        assert len(result) == 100

    def test_under_max_length_unchanged(self):
        result = sanitize_string("hello", max_length=100)
        assert result == "hello"

    def test_none_returns_empty(self):
        assert sanitize_string(None) == ""

    def test_non_string_returns_empty(self):
        assert sanitize_string(123) == ""

    def test_empty_returns_empty(self):
        assert sanitize_string("") == ""

    def test_strips_newlines(self):
        assert sanitize_string("  hello\nworld  ") == "hello world"

    def test_strips_tabs(self):
        assert sanitize_string("hello\tworld") == "hello world"

    def test_default_max_length(self):
        """Default max is 500."""
        result = sanitize_string("a" * 1000)
        assert len(result) == 500

    def test_null_bytes_stripped(self):
        """Null bytes (\x00) must be removed — prevents log injection."""
        result = sanitize_string("hello\x00world")
        assert "\x00" not in result
        assert result == "helloworld"

    def test_null_byte_only_string(self):
        """String of only null bytes should become empty."""
        result = sanitize_string("\x00\x00\x00")
        assert result == ""

    def test_null_byte_at_start(self):
        """Null byte at start should be stripped."""
        result = sanitize_string("\x00hello")
        assert result == "hello"
        assert "\x00" not in result

    def test_null_byte_at_end(self):
        """Null byte at end should be stripped."""
        result = sanitize_string("hello\x00")
        assert result == "hello"
        assert "\x00" not in result

    def test_multiple_null_bytes_in_middle(self):
        """Multiple null bytes in middle should be removed."""
        result = sanitize_string("hel\x00\x00\x00lo")
        assert result == "hello"
        assert "\x00" not in result

    def test_null_bytes_with_whitespace(self):
        """Null bytes combined with whitespace should all be cleaned."""
        result = sanitize_string("  \x00 hello \x00 world \x00  ")
        assert result == "hello world"
        assert "\x00" not in result

    def test_null_bytes_in_truncated_string(self):
        """Null bytes should be removed before truncation."""
        result = sanitize_string("\x00" + "a" * 600, max_length=50)
        assert "\x00" not in result
        assert len(result) == 50
