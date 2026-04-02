"""
PARWA Security Utilities (BC-011)

Password hashing (bcrypt cost factor 12) and AES-256-GCM encryption.
Encryption key comes from env var DATA_ENCRYPTION_KEY — never hardcoded.

BC-011 Requirements:
- bcrypt cost factor >= 12 (we use exactly 12)
- AES-256 for data encryption (not AES-128)
- Encryption key from environment variable
- Constant-time comparison for sensitive data
"""

import base64
import hashlib
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# BC-011: bcrypt cost factor MUST be 12 (not default 10)
BCRYPT_COST_FACTOR = 12

# AES-256-GCM parameters
AES_KEY_LENGTH = 32  # 256 bits
AES_NONCE_LENGTH = 12  # 96 bits (recommended for GCM)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with cost factor 12.

    BC-011: bcrypt cost factor must be >= 12.
    Uses passlib which wraps bcrypt internally.

    Args:
        password: Plain-text password to hash.

    Returns:
        bcrypt hash string (includes salt and cost factor).
    """
    from passlib.hash import bcrypt  # noqa: C901 (lazy import)
    return bcrypt.hash(password, rounds=BCRYPT_COST_FACTOR)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash.

    Uses constant-time comparison internally via bcrypt.
    Never raises exceptions — returns False on any failure.

    Args:
        password: Plain-text password to verify.
        hashed: bcrypt hash to compare against.

    Returns:
        True if password matches, False otherwise.
    """
    if not password or not hashed:
        return False
    try:
        from passlib.hash import bcrypt
        return bcrypt.verify(password, hashed)
    except Exception:
        return False


def derive_key(encryption_key: str) -> bytes:
    """Derive a 256-bit AES key from the encryption key string.

    Uses SHA-256 to ensure exactly 32 bytes regardless of input length.
    The raw encryption key is never used directly.

    Args:
        encryption_key: Raw key string (from DATA_ENCRYPTION_KEY env).

    Returns:
        Exactly 32 bytes for AES-256.
    """
    return hashlib.sha256(encryption_key.encode("utf-8")).digest()


def encrypt_data(plaintext: str, encryption_key: str) -> str:
    """Encrypt data using AES-256-GCM.

    BC-011: AES-256 only (not AES-128).
    Uses authenticated encryption (GCM mode) which provides
    both confidentiality and integrity protection.

    Args:
        plaintext: Data to encrypt.
        encryption_key: Encryption key (from DATA_ENCRYPTION_KEY env).

    Returns:
        Base64-encoded string containing: nonce + ciphertext + tag.
        The nonce is generated randomly for each encryption.

    Raises:
        ValueError: If plaintext is empty or key is invalid.
    """
    if not plaintext:
        raise ValueError("Cannot encrypt empty plaintext")
    if not encryption_key or len(encryption_key) < 16:
        raise ValueError("Encryption key must be at least 16 characters")

    key = derive_key(encryption_key)
    nonce = os.urandom(AES_NONCE_LENGTH)
    aesgcm = AESGCM(key)

    # Encrypt: AES-GCM returns ciphertext + 16-byte tag appended
    plaintext_bytes = plaintext.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)

    # Combine nonce + ciphertext for storage
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("utf-8")


def decrypt_data(encrypted: str, encryption_key: str) -> str:
    """Decrypt data encrypted with AES-256-GCM.

    Expects the same format produced by encrypt_data():
    base64-encoded nonce + ciphertext + tag.

    Args:
        encrypted: Base64-encoded encrypted data.
        encryption_key: Encryption key (from DATA_ENCRYPTION_KEY env).

    Returns:
        Decrypted plaintext string.

    Raises:
        ValueError: If encrypted data is invalid or decryption fails.
    """
    if not encrypted:
        raise ValueError("Cannot decrypt empty data")
    if not encryption_key or len(encryption_key) < 16:
        raise ValueError("Encryption key must be at least 16 characters")

    try:
        key = derive_key(encryption_key)
        combined = base64.b64decode(encrypted)

        # Split nonce and ciphertext
        nonce = combined[:AES_NONCE_LENGTH]
        ciphertext = combined[AES_NONCE_LENGTH:]

        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
    except Exception:
        # BC-011: Never leak crypto implementation details
        raise ValueError("Decryption failed")


def constant_time_compare(val1: str, val2: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Use this for comparing API keys, tokens, secrets.
    Never use == for security-sensitive comparisons.

    Args:
        val1: First string to compare.
        val2: Second string to compare.

    Returns:
        True if strings are equal, False otherwise (always takes same time).
    """
    if not isinstance(val1, str) or not isinstance(val2, str):
        return False
    return secrets.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def generate_api_key() -> str:
    """Generate a secure random API key.

    Produces a 32-byte (256-bit) cryptographically secure random key,
    encoded as base64url (URL-safe, no padding).

    Returns:
        URL-safe API key string (43 characters).
    """
    raw = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def generate_token() -> str:
    """Generate a secure random token for verification/reset URLs.

    Produces a 24-byte (192-bit) token encoded as hex (48 characters).

    Returns:
        Hex-encoded token string.
    """
    return secrets.token_hex(24)
