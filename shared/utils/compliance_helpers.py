"""
PARWA Compliance Helpers — Week 2 Day 2
Thin helper layer on top of shared/core_functions/compliance.py.
Provides reusable PII sanitization, retention policy enforcement,
GDPR export generation, and TCPA consent verification.
Depends on: compliance.py, logger.py (Week 1)
"""

import re
from datetime import datetime
from typing import Any, Optional

from shared.core_functions.compliance import mask_pii
from shared.core_functions.logger import get_logger

logger = get_logger("compliance_helpers")

# Default fields always redacted by redact_pii()
DEFAULT_PII_FIELDS: list[str] = [
    "email", "phone", "password", "address",
    "card_number", "ssn", "date_of_birth",
]

_EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


def redact_pii(data: dict, fields: Optional[list[str]] = None) -> dict:
    """
    Return a deep copy of `data` with PII fields replaced by '[REDACTED]'.
    Works recursively on nested dicts.
    Never mutates the original dict.

    Args:
        data:   The source dictionary.
        fields: Additional field names to redact on top of the defaults.

    Returns:
        A new dict with PII values redacted.
    """
    target_fields = set(DEFAULT_PII_FIELDS)
    if fields:
        target_fields.update(fields)

    def _redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if k in target_fields else _redact(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [_redact(item) for item in obj]
        return obj

    return _redact(data)


def mask_email(email: str) -> str:
    """
    Returns a privacy-safe masked version of an email address.

    Examples:
        "john@example.com"  → "j***@example.com"
        "a@b.com"           → "*@b.com"
        "notanemail"        → "[INVALID_EMAIL]"
    """
    if not _EMAIL_REGEX.match(email):
        return "[INVALID_EMAIL]"

    local, domain = email.split("@", 1)

    if len(local) <= 1:
        return f"*@{domain}"

    return f"{local[0]}***@{domain}"


def is_within_retention(created_at: datetime, retention_days: int) -> bool:
    """
    Return True if `created_at` is still within the allowed retention window.

    Args:
        created_at:      Timezone-naive UTC datetime of record creation.
        retention_days:  Number of days to keep. 0 means keep forever.
    """
    if retention_days == 0:
        return True

    age_days = (datetime.utcnow() - created_at).days
    return age_days <= retention_days


def generate_gdpr_export(customer_data: dict) -> dict:
    """
    Wrap customer data in a GDPR-compliant export envelope.
    PII is redacted from the data_subject field before export.

    Returns:
        A standardised export dict.
    """
    safe_data = redact_pii(customer_data)
    logger.info(
        "GDPR export generated",
        extra={"context": {"fields": list(customer_data.keys())}},
    )
    return {
        "export_version": "1.0",
        "generated_at": datetime.utcnow().isoformat(),
        "data_subject": safe_data,
        "rights": ["access", "rectification", "erasure", "portability"],
        "contact": "privacy@parwa.ai",
    }


def check_tcpa_consent(phone: str, consent_log: list[dict]) -> bool:
    """
    Return True if there is at least one entry in consent_log where
    entry['phone'] == phone AND entry['consented'] is True.

    Args:
        phone:       The phone number to check.
        consent_log: List of consent record dicts.
    """
    return any(
        entry.get("phone") == phone and entry.get("consented") is True
        for entry in consent_log
    )
