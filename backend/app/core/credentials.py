"""
PARWA Phase 3 — AES-256-GCM Credential Encryption Service

Encrypts third-party API keys and credentials at rest. Each encryption
operation binds the company_id as Additional Authenticated Data (AAD),
so a ciphertext decrypted with the wrong company_id fails authentication.

Security notes
--------------
* AES-256-GCM provides both confidentiality *and* integrity.
* A fresh 12-byte nonce is generated for every encrypt call.
* Key rotation re-encrypts every credential for a company under a new key.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

logger = logging.getLogger(__name__)

_NONCE_SIZE = 12  # 96-bit nonce recommended for AES-GCM


class CredentialService:
    """AES-256-GCM encryption service for tenant-scoped credentials.

    Parameters
    ----------
    master_key:
        A high-entropy secret used to derive the 256-bit AES key via
        SHA-256.  Must be at least 16 characters in production.
    """

    def __init__(self, master_key: str) -> None:
        if not master_key or len(master_key) < 16:
            raise ValueError("master_key must be at least 16 characters")
        self._aes_key: bytes = hashlib.sha256(master_key.encode("utf-8")).digest()
        self._aesgcm = AESGCM(self._aes_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str, company_id: str) -> str:
        """Encrypt *plaintext* with company_id as AAD.

        Returns
        -------
        str
            base64-encoded ``nonce + ciphertext + tag``.
        """
        try:
            nonce = os.urandom(_NONCE_SIZE)
            aad = company_id.encode("utf-8")
            ciphertext_with_tag = self._aesgcm.encrypt(
                nonce, plaintext.encode("utf-8"), aad
            )
            payload = nonce + ciphertext_with_tag
            return base64.b64encode(payload).decode("ascii")
        except Exception as exc:
            logger.error("Encryption failed for company_id=%s: %s", company_id, exc)
            raise

    def decrypt(self, encrypted: str, company_id: str) -> str:
        """Decrypt a value previously encrypted with :meth:`encrypt`.

        Raises
        ------
        ValueError
            If the ciphertext is malformed or the AAD (company_id) does
            not match the one used during encryption.
        """
        try:
            raw = base64.b64decode(encrypted)
            nonce = raw[:_NONCE_SIZE]
            ciphertext_with_tag = raw[_NONCE_SIZE:]
            aad = company_id.encode("utf-8")
            plaintext_bytes = self._aesgcm.decrypt(nonce, ciphertext_with_tag, aad)
            return plaintext_bytes.decode("utf-8")
        except InvalidTag:
            logger.warning(
                "AAD verification failed — company_id mismatch for decryption"
            )
            raise ValueError(
                "Decryption failed: company_id does not match the one used during encryption"
            )
        except Exception as exc:
            logger.error("Decryption failed for company_id=%s: %s", company_id, exc)
            raise

    def rotate_key(
        self,
        old_key: str,
        new_key: str,
        company_id: str,
        encrypted_credentials: list[str],
    ) -> list[str]:
        """Re-encrypt all credentials for *company_id* under a new master key.

        Parameters
        ----------
        old_key:
            The current master key used to decrypt existing credentials.
        new_key:
            The new master key to re-encrypt credentials with.
        company_id:
            Tenant identifier (used as AAD on both decrypt & encrypt).
        encrypted_credentials:
            List of base64-encoded ciphertexts to rotate.

        Returns
        -------
        list[str]
            List of re-encrypted credentials under the new key.
        """
        try:
            old_service = CredentialService(old_key)
            new_service = CredentialService(new_key)
            rotated: list[str] = []
            for enc in encrypted_credentials:
                plaintext = old_service.decrypt(enc, company_id)
                re_encrypted = new_service.encrypt(plaintext, company_id)
                rotated.append(re_encrypted)
            return rotated
        except Exception as exc:
            logger.error(
                "Key rotation failed for company_id=%s: %s", company_id, exc
            )
            raise

    @staticmethod
    def mask_credential(value: str, visible_chars: int = 4) -> str:
        """Return a masked representation showing only the last *visible_chars*.

        Examples
        --------
        >>> CredentialService.mask_credential("sk_live_abc123xyz", 4)
        '••••3xyz'
        """
        try:
            if not value:
                return "••••"
            if visible_chars >= len(value):
                return value
            return "••••" + value[-visible_chars:]
        except Exception as exc:
            logger.error("Masking failed: %s", exc)
            return "••••"
