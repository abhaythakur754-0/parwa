"""
Token Encryption Utility (C-14)

Fernet-based symmetric encryption for OAuth access/refresh tokens.
Uses DATA_ENCRYPTION_KEY from application config (32-char key).

All OAuth tokens stored in the database MUST be encrypted with these
helpers before persistence. Never store plaintext tokens.

Usage::

    from shared.utils.token_encryption import encrypt_token, decrypt_token

    # Storing a token
    account.access_token = encrypt_token(raw_token)

    # Reading a token
    raw_token = decrypt_token(account.access_token)
"""

import base64
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Module-level Fernet singleton (lazy-initialized)
_fernet_instance: Optional[Fernet] = None


def _build_fernet_key(key: str) -> bytes:
    """Build a Fernet-compatible key from a 32-character string.

    Fernet requires a 32-byte key, base64-url-safe encoded (44 chars).
    We take the raw 32-char config key, encode it as bytes, pad/truncate
    to exactly 32 bytes, then base64-urlsafe-encode it.

    Args:
        key: The DATA_ENCRYPTION_KEY string (expected 32 chars).

    Returns:
        A 44-character base64-urlsafe-encoded key suitable for Fernet.
    """
    key_bytes = key.encode("utf-8").ljust(32)[:32]
    return base64.urlsafe_b64encode(key_bytes)


def get_fernet() -> Fernet:
    """Return a cached Fernet instance using DATA_ENCRYPTION_KEY.

    Lazily initializes on first call and caches the result for
    subsequent calls.

    Returns:
        A ready-to-use Fernet instance.
    """
    global _fernet_instance
    if _fernet_instance is None:
        from app.config import get_settings

        settings = get_settings()
        fernet_key = _build_fernet_key(settings.DATA_ENCRYPTION_KEY)
        _fernet_instance = Fernet(fernet_key)
    return _fernet_instance


def encrypt_token(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a plaintext token using Fernet.

    Args:
        plaintext: The raw token string, or None.

    Returns:
        The encrypted token as a base64-encoded string, or None if
        the input was None/empty.
    """
    if not plaintext:
        return None
    fernet = get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt a Fernet-encrypted token.

    Args:
        ciphertext: The encrypted token string, or None.

    Returns:
        The original plaintext token, or None if the input was None,
        empty, or decryption failed (e.g., wrong key, corrupted data).
    """
    if not ciphertext:
        return None
    try:
        fernet = get_fernet()
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, Exception) as exc:
        logger.warning(
            "token_decryption_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None
