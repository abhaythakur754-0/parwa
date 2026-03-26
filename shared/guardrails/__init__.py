"""
PARWA Guardrails Package.

Provides AI safety guardrails including:
- Hallucination detection
- Competitor mention blocking
- PII exposure detection
- Approval gate enforcement

CRITICAL: These guardrails protect AI outputs from harmful content
and enforce approval workflows for sensitive actions like refunds.
"""
from shared.guardrails.guardrails import (
    GuardrailsManager,
    GuardrailResult,
    GuardrailRule
)
from shared.guardrails.approval_enforcer import (
    ApprovalEnforcer,
    ApprovalStatus,
    ApprovalRequest
)

__all__ = [
    "GuardrailsManager",
    "GuardrailResult",
    "GuardrailRule",
    "ApprovalEnforcer",
    "ApprovalStatus",
    "ApprovalRequest",
]
