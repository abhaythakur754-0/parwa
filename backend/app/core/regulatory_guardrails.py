"""
Tier-based financial guardrails + PHI extension for Superglue actions.

This module EXTENDS (not duplicates) the existing PIILeakGuard in
guardrails_engine.py and check_phi_guardrails logic. It adds:

1. Tier-based financial limits (P-002): parwa=$500 refund/$200 credit, parwa_high=unlimited
2. Regulatory framework mapping (GDPR, PCI-DSS, SOC-2, SOX)
3. check_phi_guardrails(): delegates to PIILeakGuard.scan() from guardrails_engine.py

BC-008: never crashes — allows on error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# P-002: Hardcoded tier limits. None = unlimited.
PARWA_TIER_LIMITS: dict[str, dict[str, Optional[float]]] = {
    "parwa": {"max_refund": 500.0, "max_credit": 200.0, "max_write": None},
    "parwa_high": {"max_refund": None, "max_credit": None, "max_write": None},
}

# Action name -> limit type mapping.
_ACTION_TO_LIMIT: dict[str, str] = {
    "refund": "max_refund", "cashback": "max_refund", "payout": "max_refund",
    "credit": "max_credit", "discount": "max_credit", "adjustment": "max_credit",
}

# Safety level -> regulatory frameworks.
_FRAMEWORKS: dict[str, list[str]] = {
    "financial": ["PCI-DSS"],
    "sensitive_pii": ["GDPR", "CCPA"],
    "destructive": ["SOX"],
    "write": ["SOC-2"],
    "read": [],
}


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str
    limit: Optional[float]
    remaining: Optional[float]


@dataclass
class PHIResult:
    """Result from PHI guardrails check. Delegates to PIILeakGuard."""
    safe: bool
    pii_fields_found: list[str]
    scrubbed_text: str
    reason: str


def _resolve_limit_type(action_level: str, action_name: str = "") -> Optional[str]:
    """Map an action to its limit type key (max_refund/max_credit/max_write)."""
    if action_level == "financial":
        for keyword, limit_key in _ACTION_TO_LIMIT.items():
            if keyword in action_name.lower():
                return limit_key
        return "max_refund"  # default financial limit
    if action_level == "write":
        return "max_write"
    return None


def check_financial_guardrails(
    action_level: str,
    amount: float,
    variant_tier: str,
    action_name: str = "",
) -> GuardrailResult:
    """Check if a financial action is within tier limits.

    Returns GuardrailResult. BC-008: allows on any error.
    """
    try:
        if amount <= 0:
            return GuardrailResult(
                allowed=True, reason="Non-positive amount, no limit check needed",
                limit=None, remaining=None,
            )

        if action_level != "financial":
            return GuardrailResult(
                allowed=True, reason=f"Action level '{action_level}' is not financial",
                limit=None, remaining=None,
            )

        if variant_tier == "parwa_high":
            return GuardrailResult(
                allowed=True, reason="parwa_high tier has unlimited limits",
                limit=None, remaining=None,
            )

        tier_limits = PARWA_TIER_LIMITS.get(variant_tier)
        if tier_limits is None:
            return GuardrailResult(
                allowed=True, reason=f"Unknown tier '{variant_tier}', no limit enforced",
                limit=None, remaining=None,
            )

        limit_key = _resolve_limit_type(action_level, action_name)
        limit = tier_limits.get(limit_key) if limit_key else None

        if limit is None:
            return GuardrailResult(
                allowed=True, reason=f"No limit configured for {limit_key} on tier '{variant_tier}'",
                limit=None, remaining=None,
            )

        if amount > limit:
            return GuardrailResult(
                allowed=False,
                reason=f"Amount ${amount:.2f} exceeds {limit_key} limit ${limit:.2f} for tier '{variant_tier}'",
                limit=limit,
                remaining=limit,
            )

        return GuardrailResult(
            allowed=True,
            reason=f"Within {limit_key} limit ${limit:.2f} for tier '{variant_tier}'",
            limit=limit,
            remaining=round(limit - amount, 2),
        )
    except Exception:
        return GuardrailResult(
            allowed=True, reason="Error during guardrail check, defaulting to allowed",
            limit=None, remaining=None,
        )


def check_phi_guardrails(text: str, tool_name: str = "") -> PHIResult:
    """Check PHI/PII in text. Delegates to PIILeakGuard.scan() from guardrails_engine.

    This EXTENDS the existing PIILeakGuard (guardrails_engine.py:1180)
    rather than duplicating its regex patterns.

    BC-008: If PIILeakGuard is unavailable, returns safe=True (fail-open).
    """
    try:
        from app.core.guardrails_engine import PIILeakGuard
        guard = PIILeakGuard()
        scan_result = guard.scan(text)
        return PHIResult(
            safe=scan_result.get("safe", True),
            pii_fields_found=scan_result.get("pii_fields", []),
            scrubbed_text=scan_result.get("scrubbed", text),
            reason="PII check passed" if scan_result.get("safe", True) else "PII detected",
        )
    except ImportError:
        # guardrails_engine not available — fail-open per BC-008
        return PHIResult(safe=True, pii_fields_found=[], scrubbed_text=text,
                        reason="PIILeakGuard unavailable, skipping PII check")
    except Exception:
        return PHIResult(safe=True, pii_fields_found=[], scrubbed_text=text,
                        reason="Error during PHI check, defaulting to safe")


def get_applicable_frameworks(action_level: str) -> list[str]:
    """Return regulatory frameworks that apply to an action level."""
    try:
        return list(_FRAMEWORKS.get(action_level, []))
    except Exception:
        return []
