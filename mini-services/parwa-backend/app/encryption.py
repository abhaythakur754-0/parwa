"""AES-256-GCM encryption service for PARWA backend."""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_master_key() -> bytes:
    """Generate a 256-bit key from the ENCRYPTION_MASTER_KEY env var using SHA-256."""
    env_key = os.environ.get("ENCRYPTION_MASTER_KEY", "parwa-default-encryption-key-change-in-production")
    return hashlib.sha256(env_key.encode("utf-8")).digest()


def encrypt_data(plaintext: str, master_key: str = None) -> str:
    """
    Encrypt plaintext using AES-256-GCM.
    Returns base64 encoded nonce + ciphertext + tag.
    """
    if master_key:
        key = hashlib.sha256(master_key.encode("utf-8")).digest()
    else:
        key = _get_master_key()

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # ciphertext includes the tag (last 16 bytes) by default
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_data(encrypted: str, master_key: str = None) -> str:
    """
    Decrypt AES-256-GCM encrypted data.
    Input is base64 encoded nonce + ciphertext + tag.
    """
    if master_key:
        key = hashlib.sha256(master_key.encode("utf-8")).digest()
    else:
        key = _get_master_key()

    raw = base64.b64decode(encrypted)
    nonce = raw[:12]
    ciphertext = raw[12:]

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def mask_key(key: str) -> str:
    """Mask a key, showing only the last 4 characters."""
    if not key or len(key) < 4:
        return "••••••••"
    return "••••••••" + key[-4:]
