"""
Unit tests for app/core/regulatory_guardrails.py

Tests tier-based financial guardrails (P-002), regulatory framework
mapping, and PHI extension that delegates to PIILeakGuard.

Run: pytest backend/app/tests/test_regulatory_guardrails.py -v
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.regulatory_guardrails import (
    GuardrailResult,
    PHIResult,
    PARWA_TIER_LIMITS,
    check_financial_guardrails,
    check_phi_guardrails,
    get_applicable_frameworks,
    _resolve_limit_type,
)


class TestResolveLimitType:
    def test_refund_maps_to_max_refund(self):
        assert _resolve_limit_type("financial", "process_refund") == "max_refund"

    def test_cashback_maps_to_max_refund(self):
        assert _resolve_limit_type("financial", "issue_cashback") == "max_refund"

    def test_payout_maps_to_max_refund(self):
        assert _resolve_limit_type("financial", "process_payout") == "max_refund"

    def test_credit_maps_to_max_credit(self):
        assert _resolve_limit_type("financial", "issue_credit") == "max_credit"

    def test_discount_maps_to_max_credit(self):
        assert _resolve_limit_type("financial", "apply_discount") == "max_credit"

    def test_unknown_financial_defaults_to_max_refund(self):
        assert _resolve_limit_type("financial", "unknown_action") == "max_refund"

    def test_write_maps_to_max_write(self):
        assert _resolve_limit_type("write", "update_thing") == "max_write"

    def test_read_returns_none(self):
        assert _resolve_limit_type("read", "get_thing") is None


class TestFinancialGuardrails:
    def test_non_positive_amount_allowed(self):
        result = check_financial_guardrails("financial", 0, "parwa")
        assert result.allowed is True
        assert "Non-positive" in result.reason

    def test_negative_amount_allowed(self):
        result = check_financial_guardrails("financial", -50, "parwa")
        assert result.allowed is True

    def test_non_financial_action_allowed(self):
        result = check_financial_guardrails("read", 1000, "parwa")
        assert result.allowed is True
        assert "not financial" in result.reason

    def test_parwa_high_unlimited(self):
        result = check_financial_guardrails("financial", 999999, "parwa_high")
        assert result.allowed is True
        assert "unlimited" in result.reason

    def test_unknown_tier_allowed(self):
        result = check_financial_guardrails("financial", 1000, "unknown_tier")
        assert result.allowed is True
        assert "Unknown tier" in result.reason

    def test_parwa_refund_within_limit(self):
        result = check_financial_guardrails("financial", 400, "parwa", "process_refund")
        assert result.allowed is True
        assert result.limit == 500.0
        assert result.remaining == 100.0

    def test_parwa_refund_at_limit(self):
        result = check_financial_guardrails("financial", 500, "parwa", "process_refund")
        assert result.allowed is True
        assert result.remaining == 0.0

    def test_parwa_refund_exceeds_limit(self):
        result = check_financial_guardrails("financial", 501, "parwa", "process_refund")
        assert result.allowed is False
        assert "exceeds" in result.reason
        assert result.limit == 500.0

    def test_parwa_credit_within_limit(self):
        result = check_financial_guardrails("financial", 150, "parwa", "issue_credit")
        assert result.allowed is True
        assert result.limit == 200.0

    def test_parwa_credit_exceeds_limit(self):
        result = check_financial_guardrails("financial", 250, "parwa", "issue_credit")
        assert result.allowed is False
        assert "exceeds" in result.reason

    def test_guardrail_result_structure(self):
        result = check_financial_guardrails("financial", 100, "parwa")
        assert isinstance(result, GuardrailResult)
        assert isinstance(result.allowed, bool)
        assert isinstance(result.reason, str)


class TestBC008Guardrails:
    def test_none_amount(self):
        result = check_financial_guardrails("financial", None, "parwa")
        assert result.allowed is True

    def test_string_amount(self):
        result = check_financial_guardrails("financial", "abc", "parwa")
        assert result.allowed is True

    def test_none_tier(self):
        result = check_financial_guardrails("financial", 100, None)
        assert result.allowed is True

    def test_empty_string_inputs(self):
        result = check_financial_guardrails("", "", "")
        assert result.allowed is True


class TestFrameworks:
    def test_financial_pci_dss(self):
        fw = get_applicable_frameworks("financial")
        assert "PCI-DSS" in fw

    def test_sensitive_pii_gdpr_ccpa(self):
        fw = get_applicable_frameworks("sensitive_pii")
        assert "GDPR" in fw
        assert "CCPA" in fw

    def test_destructive_sox(self):
        fw = get_applicable_frameworks("destructive")
        assert "SOX" in fw

    def test_write_soc2(self):
        fw = get_applicable_frameworks("write")
        assert "SOC-2" in fw

    def test_read_empty(self):
        fw = get_applicable_frameworks("read")
        assert fw == []

    def test_unknown_level_empty(self):
        fw = get_applicable_frameworks("nonexistent")
        assert fw == []

    def test_returns_copy(self):
        fw1 = get_applicable_frameworks("financial")
        fw1.append("EXTRA")
        fw2 = get_applicable_frameworks("financial")
        assert "EXTRA" not in fw2


class TestPHIGuardrails:
    def test_safe_text(self):
        result = check_phi_guardrails("This is safe text", "get_order")
        assert isinstance(result, PHIResult)
        assert result.safe is True

    def test_pii_text_delegates_to_guard(self):
        result = check_phi_guardrails("Email: test@example.com", "export")
        assert isinstance(result, PHIResult)
        assert isinstance(result.pii_fields_found, list)
        assert isinstance(result.scrubbed_text, str)

    def test_empty_text(self):
        result = check_phi_guardrails("", "")
        assert result.safe is True

    def test_phi_result_structure(self):
        result = check_phi_guardrails("test")
        assert hasattr(result, 'safe')
        assert hasattr(result, 'pii_fields_found')
        assert hasattr(result, 'scrubbed_text')
        assert hasattr(result, 'reason')


class TestTierLimits:
    def test_parwa_tier_exists(self):
        assert "parwa" in PARWA_TIER_LIMITS
        assert PARWA_TIER_LIMITS["parwa"]["max_refund"] == 500.0
        assert PARWA_TIER_LIMITS["parwa"]["max_credit"] == 200.0

    def test_parwa_high_tier_exists(self):
        assert "parwa_high" in PARWA_TIER_LIMITS
        assert PARWA_TIER_LIMITS["parwa_high"]["max_refund"] is None
