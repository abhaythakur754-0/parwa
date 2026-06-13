"""
Provider Configuration Model — Multi-provider credential store

Stores encrypted API credentials for third-party providers
(email, SMS, payment, voice, CRM, e-commerce, shipping)
on a per-company basis.

Building Codes:
- BC-001: Every table has company_id
- BC-011: Credentials encrypted at rest (Fernet)
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)

from database.base import Base

logger = logging.getLogger(__name__)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Enum-like value sets (CHECK constraints) ────────────────

_PROVIDER_CATEGORIES = (
    "'email','sms','payment','voice','crm','ecommerce','shipping'"
)


class ProviderConfiguration(Base):
    """Per-company provider credential configuration.

    Stores a Fernet-encrypted JSON blob of provider-specific
    credentials (API keys, tokens, secrets) indexed by
    (company_id, category, provider_type).

    BC-001: Scoped to company_id.
    BC-011: Credentials encrypted at rest.
    """

    __tablename__ = "provider_configurations"

    id = Column(String(36), primary_key=True, default=_uuid)
    company_id = Column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Provider classification
    category = Column(String(50), nullable=False)  # e.g. "email", "sms", "payment"
    provider_type = Column(String(50), nullable=False)  # e.g. "brevo", "twilio", "paddle"

    # Encrypted credentials (Fernet-encrypted JSON blob)
    credentials_encrypted = Column(Text, nullable=False)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Credential rotation tracking
    rotated_at = Column(DateTime, nullable=True)  # when credentials were last rotated
    rotated_by = Column(String(36), nullable=True)  # user_id who rotated

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "category",
            "provider_type",
            name="uq_provider_config_company_cat_type",
        ),
        CheckConstraint(
            f"category IN ({_PROVIDER_CATEGORIES})",
            name="ck_provider_config_category",
        ),
        {"schema": None},
    )

    def to_dict(self) -> dict:
        """Serialize provider configuration for API responses.

        Never exposes ``credentials_encrypted`` — instead includes
        ``has_credentials`` to indicate whether credentials are stored.
        """
        return {
            "id": self.id,
            "company_id": self.company_id,
            "category": self.category,
            "provider_type": self.provider_type,
            "has_credentials": bool(self.credentials_encrypted),
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
            "rotated_at": (
                self.rotated_at.isoformat() if self.rotated_at else None
            ),
            "rotated_by": self.rotated_by,
        }

    def decrypt_credentials(self) -> dict:
        """Decrypt and return the stored credentials as a dict.

        Returns:
            Decrypted credential dict, or empty dict on failure.
        """
        try:
            from shared.utils.token_encryption import decrypt_token

            decrypted = decrypt_token(self.credentials_encrypted)
            if decrypted is None:
                return {}
            return json.loads(decrypted)
        except Exception:
            logger.warning(
                "Failed to decrypt credentials for provider %s/%s "
                "(company=%s)",
                self.category,
                self.provider_type,
                self.company_id,
            )
            return {}

    def encrypt_and_set_credentials(self, credentials_dict: dict) -> None:
        """Encrypt and store a credential dict.

        Args:
            credentials_dict: Plain credential dict to encrypt and persist.
        """
        from shared.utils.token_encryption import encrypt_token

        plain = json.dumps(credentials_dict)
        self.credentials_encrypted = encrypt_token(plain)
