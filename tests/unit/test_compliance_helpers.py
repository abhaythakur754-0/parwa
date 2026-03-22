"""
Unit tests for shared/utils/compliance_helpers.py
All 12 tests must pass with no live external dependencies.
"""

import pytest
from datetime import datetime, timedelta

from shared.utils.compliance_helpers import (
    redact_pii,
    mask_email,
    is_within_retention,
    generate_gdpr_export,
    check_tcpa_consent,
    DEFAULT_PII_FIELDS,
)


# ── redact_pii ──────────────────────────────────────────────────────────────

def test_redact_pii_removes_default_fields():
    data = {
        "name": "Alice",
        "email": "alice@example.com",
        "phone": "+1-800-555-0001",
        "password": "s3cr3t",
    }
    result = redact_pii(data)
    assert result["name"] == "Alice"
    assert result["email"] == "[REDACTED]"
    assert result["phone"] == "[REDACTED]"
    assert result["password"] == "[REDACTED]"


def test_redact_pii_does_not_mutate_original():
    data = {"email": "alice@example.com", "age": 30}
    original_email = data["email"]
    redact_pii(data)
    assert data["email"] == original_email  # must remain unchanged


def test_redact_pii_works_on_nested_dict():
    data = {
        "user": {
            "email": "bob@example.com",
            "profile": {
                "ssn": "123-45-6789",
                "nickname": "Bobby",
            }
        }
    }
    result = redact_pii(data)
    assert result["user"]["email"] == "[REDACTED]"
    assert result["user"]["profile"]["ssn"] == "[REDACTED]"
    assert result["user"]["profile"]["nickname"] == "Bobby"


# ── mask_email ───────────────────────────────────────────────────────────────

def test_mask_email_standard_case():
    assert mask_email("john@example.com") == "j***@example.com"


def test_mask_email_single_char_local():
    assert mask_email("a@b.com") == "*@b.com"


def test_mask_email_invalid_input():
    assert mask_email("notanemail") == "[INVALID_EMAIL]"


# ── is_within_retention ──────────────────────────────────────────────────────

def test_is_within_retention_not_expired():
    recent = datetime.utcnow() - timedelta(days=10)
    assert is_within_retention(recent, retention_days=30) is True


def test_is_within_retention_expired():
    old = datetime.utcnow() - timedelta(days=400)
    assert is_within_retention(old, retention_days=365) is False


def test_is_within_retention_zero_days_always_true():
    very_old = datetime.utcnow() - timedelta(days=9999)
    assert is_within_retention(very_old, retention_days=0) is True


# ── generate_gdpr_export ─────────────────────────────────────────────────────

def test_generate_gdpr_export_structure():
    customer_data = {"name": "Alice", "email": "alice@example.com", "age": 30}
    result = generate_gdpr_export(customer_data)

    assert result["export_version"] == "1.0"
    assert "generated_at" in result
    assert "data_subject" in result
    assert result["rights"] == ["access", "rectification", "erasure", "portability"]
    assert result["contact"] == "privacy@parwa.ai"
    # PII must be redacted in the exported data_subject
    assert result["data_subject"]["email"] == "[REDACTED]"
    assert result["data_subject"]["name"] == "Alice"  # non-PII kept


# ── check_tcpa_consent ────────────────────────────────────────────────────────

def test_check_tcpa_consent_found():
    log = [
        {"phone": "+1-800-555-0001", "consented": True},
        {"phone": "+1-800-555-0002", "consented": False},
    ]
    assert check_tcpa_consent("+1-800-555-0001", log) is True


def test_check_tcpa_consent_not_found():
    log = [
        {"phone": "+1-800-555-0002", "consented": True},
    ]
    assert check_tcpa_consent("+1-800-555-0001", log) is False
    assert check_tcpa_consent("+1-800-555-0001", []) is False
