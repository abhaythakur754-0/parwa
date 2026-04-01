"""
Tests for shared/utils/security.py

Tests bcrypt hashing (BC-011 cost 12), AES-256-GCM encryption,
constant-time comparison, and secure key generation.
"""

import pytest

from shared.utils.security import (
    hash_password,
    verify_password,
    encrypt_data,
    decrypt_data,
    constant_time_compare,
    generate_api_key,
    generate_token,
    BCRYPT_COST_FACTOR,
    derive_key,
)


# Test encryption key (32 chars)
TEST_ENCRYPTION_KEY = "12345678901234567890123456789012"


class TestBcryptCostFactor:
    """BC-011: bcrypt cost factor must be exactly 12."""

    def test_cost_factor_is_12(self):
        assert BCRYPT_COST_FACTOR == 12

    def test_cost_factor_not_lower_than_12(self):
        assert BCRYPT_COST_FACTOR >= 12


class TestHashPassword:
    """Tests for password hashing with bcrypt."""

    def test_returns_string(self):
        result = hash_password("test_password")
        assert isinstance(result, str)

    def test_different_passwords_different_hashes(self):
        h1 = hash_password("password1")
        h2 = hash_password("password2")
        assert h1 != h2

    def test_same_password_different_hashes(self):
        """bcrypt uses random salt — different hashes."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2

    def test_hash_starts_with_dollar_signs(self):
        """bcrypt hashes start with $2b$12$ (algorithm$cost$salt+hash)."""
        result = hash_password("test")
        assert result.startswith("$2")

    def test_hash_contains_cost_12(self):
        """Verify cost factor 12 is embedded in the hash."""
        result = hash_password("test")
        assert "$12$" in result

    def test_long_password(self):
        """bcrypt has 72-byte limit but should not crash."""
        long_pw = "a" * 200
        result = hash_password(long_pw)
        assert isinstance(result, str)
        assert verify_password(long_pw, result)

    def test_empty_password_hashes(self):
        """Empty passwords should hash without error.

        Note: Some bcrypt implementations reject empty passwords.
        We test that hash_password doesn't crash, but verification
        may vary by backend.
        """
        result = hash_password("")
        assert isinstance(result, str)


class TestVerifyPassword:
    """Tests for password verification."""

    def test_correct_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("correct_password", hashed) is True

    def test_incorrect_password(self):
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_empty_password_against_hash(self):
        hashed = hash_password("non_empty")
        assert verify_password("", hashed) is False

    def test_empty_hash_returns_false(self):
        assert verify_password("password", "") is False

    def test_none_password_returns_false(self):
        assert verify_password(None, hash_password("test")) is False

    def test_none_hash_returns_false(self):
        assert verify_password("password", None) is False

    def test_garbage_hash_returns_false(self):
        assert verify_password("password", "not_a_bcrypt_hash") is False

    def test_case_sensitive(self):
        hashed = hash_password("Password")
        assert verify_password("password", hashed) is False

    def test_special_characters(self):
        special_pw = "p@$$w0rd!#$%^&*()"
        hashed = hash_password(special_pw)
        assert verify_password(special_pw, hashed) is True
        assert verify_password("p@$$w0rd", hashed) is False


class TestEncryptDecryptData:
    """Tests for AES-256-GCM encryption/decryption."""

    def test_encrypt_returns_string(self):
        result = encrypt_data("hello", TEST_ENCRYPTION_KEY)
        assert isinstance(result, str)

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "secret data that needs encryption"
        encrypted = encrypt_data(plaintext, TEST_ENCRYPTION_KEY)
        decrypted = decrypt_data(encrypted, TEST_ENCRYPTION_KEY)
        assert decrypted == plaintext

    def test_different_encryptions_different_ciphertexts(self):
        """AES-GCM uses random nonce — different ciphertexts."""
        c1 = encrypt_data("same text", TEST_ENCRYPTION_KEY)
        c2 = encrypt_data("same text", TEST_ENCRYPTION_KEY)
        assert c1 != c2

    def test_long_text(self):
        plaintext = "a" * 10000
        encrypted = encrypt_data(plaintext, TEST_ENCRYPTION_KEY)
        decrypted = decrypt_data(encrypted, TEST_ENCRYPTION_KEY)
        assert decrypted == plaintext

    def test_special_characters(self):
        plaintext = "Hello 世界 🌍 \n\t\r\n<>&\"'"
        encrypted = encrypt_data(plaintext, TEST_ENCRYPTION_KEY)
        decrypted = decrypt_data(encrypted, TEST_ENCRYPTION_KEY)
        assert decrypted == plaintext

    def test_empty_plaintext_raises(self):
        with pytest.raises(ValueError, match="empty plaintext"):
            encrypt_data("", TEST_ENCRYPTION_KEY)

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="Encryption key"):
            encrypt_data("data", "")

    def test_short_key_raises(self):
        with pytest.raises(ValueError, match="Encryption key"):
            encrypt_data("data", "short")

    def test_decrypt_wrong_key_raises(self):
        encrypted = encrypt_data("secret", TEST_ENCRYPTION_KEY)
        wrong_key = "abcdefghij01234567890123456789012"
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_data(encrypted, wrong_key)

    def test_decrypt_tampered_data_raises(self):
        encrypted = encrypt_data("secret", TEST_ENCRYPTION_KEY)
        # Tamper with the base64 data
        tampered = encrypted[:-4] + "XXXX"
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_data(tampered, TEST_ENCRYPTION_KEY)

    def test_decrypt_empty_raises(self):
        with pytest.raises(ValueError, match="Cannot decrypt"):
            decrypt_data("", TEST_ENCRYPTION_KEY)

    def test_decrypt_garbage_raises(self):
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_data("not_encrypted_data", TEST_ENCRYPTION_KEY)


class TestDeriveKey:
    """Tests for AES key derivation."""

    def test_returns_32_bytes(self):
        key = derive_key(TEST_ENCRYPTION_KEY)
        assert isinstance(key, bytes)
        assert len(key) == 32  # 256 bits = AES-256

    def test_same_input_same_output(self):
        k1 = derive_key(TEST_ENCRYPTION_KEY)
        k2 = derive_key(TEST_ENCRYPTION_KEY)
        assert k1 == k2

    def test_different_inputs_different_output(self):
        k1 = derive_key("key_one_12345678901234567890123")
        k2 = derive_key("key_two_12345678901234567890123")
        assert k1 != k2


class TestConstantTimeCompare:
    """Tests for constant-time string comparison (anti-timing-attack)."""

    def test_equal_strings(self):
        assert constant_time_compare("secret", "secret") is True

    def test_different_strings(self):
        assert constant_time_compare("secret", "wrong") is False

    def test_different_lengths(self):
        assert constant_time_compare("short", "much_longer_string") is False

    def test_empty_strings(self):
        assert constant_time_compare("", "") is True

    def test_one_empty(self):
        assert constant_time_compare("a", "") is False

    def test_non_string_first(self):
        assert constant_time_compare(123, "123") is False

    def test_non_string_second(self):
        assert constant_time_compare("123", 123) is False

    def test_unicode_strings(self):
        assert constant_time_compare("café", "café") is True
        assert constant_time_compare("café", "cafe") is False


class TestGenerateApiKey:
    """Tests for secure API key generation."""

    def test_returns_string(self):
        result = generate_api_key()
        assert isinstance(result, str)

    def test_reasonable_length(self):
        result = generate_api_key()
        assert 30 <= len(result) <= 50

    def test_unique_keys(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100  # All unique

    def test_no_special_chars(self):
        """URL-safe base64: alphanumeric, hyphens, underscores."""
        result = generate_api_key()
        for c in result:
            assert c.isalnum() or c in "-_"

    def test_not_equal_to_previous(self):
        k1 = generate_api_key()
        k2 = generate_api_key()
        assert k1 != k2


class TestGenerateToken:
    """Tests for secure token generation."""

    def test_returns_string(self):
        result = generate_token()
        assert isinstance(result, str)

    def test_hex_length(self):
        result = generate_token()
        assert len(result) == 48  # 24 bytes = 48 hex chars

    def test_only_hex_chars(self):
        result = generate_token()
        assert all(c in "0123456789abcdef" for c in result)

    def test_unique_tokens(self):
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100
