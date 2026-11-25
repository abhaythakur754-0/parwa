"""
Safety classifier for Superglue tool actions.

Keyword-based classification — zero LLM cost. Used by the approval gate
to decide whether a tool action requires human approval.

BC-008: classify_action never crashes; returns READ on any error.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ActionSafetyLevel(str, Enum):
    """Risk level for a tool action."""
    READ = "read"
    WRITE = "write"
    SENSITIVE_PII = "sensitive_pii"
    DESTRUCTIVE = "destructive"
    FINANCIAL = "financial"


# Highest-severity first. First match wins when iterating levels.
_KEYWORDS: dict[ActionSafetyLevel, list[str]] = {
    ActionSafetyLevel.FINANCIAL: [
        "refund", "credit", "payment", "charge", "invoice",
        "billing", "money", "debit", "payout",
    ],
    ActionSafetyLevel.DESTRUCTIVE: [
        "delete", "remove", "cancel", "terminate", "destroy", "drop", "purge",
    ],
    ActionSafetyLevel.SENSITIVE_PII: [
        "export_customer", "download_data", "list_users", "get_customer",
        "lookup", "pii", "ssn", "personal",
    ],
    ActionSafetyLevel.WRITE: [
        "update", "modify", "change", "edit", "set", "create",
        "add", "assign", "send", "email", "sms", "notify",
        "reply", "respond", "comment", "escalate", "escalation", "note", "resolve",
    ],
    ActionSafetyLevel.READ: [
        "get", "fetch", "list", "search", "query", "check",
        "verify", "status", "health", "info",
    ],
}

# Precedence order: highest severity first.
_PRIORITY = [
    ActionSafetyLevel.FINANCIAL,
    ActionSafetyLevel.DESTRUCTIVE,
    ActionSafetyLevel.SENSITIVE_PII,
    ActionSafetyLevel.WRITE,
    ActionSafetyLevel.READ,
]


@dataclass
class ActionSafetyResult:
    level: ActionSafetyLevel
    confidence: float
    matched_keyword: Optional[str]
    reasoning: str


def classify_action(tool_name: str, tool_description: str = "") -> ActionSafetyResult:
    """Classify an action using explicit operation intent, not domain nouns alone.

    A read-only search for payment/refund records is not a financial write.
    Financial approval is required when a financial domain is combined with a
    write operation; destructive operations always take precedence.
    """
    try:
        text = f"{tool_name} {tool_description}".lower()

        destructive_terms = tuple(_KEYWORDS[ActionSafetyLevel.DESTRUCTIVE])
        financial_domains = (
            "refund", "credit", "payment", "charge", "invoice",
            "billing", "money", "debit", "payout", "transfer",
        )
        read_verbs = (
            "get", "fetch", "list", "search", "query", "check", "verify",
            "status", "health", "info", "lookup", "read", "retrieve",
            "find", "inspect", "investigate", "analyze", "analyse", "review",
        )
        write_verbs = tuple(_KEYWORDS[ActionSafetyLevel.WRITE]) + (
            "process", "issue", "capture", "pay", "refund", "charge",
            "credit", "debit", "payout", "transfer", "void",
        )

        destructive_match = next((term for term in destructive_terms if term in text), None)
        if destructive_match:
            return ActionSafetyResult(
                level=ActionSafetyLevel.DESTRUCTIVE,
                confidence=0.95,
                matched_keyword=destructive_match,
                reasoning=f"Matched destructive operation '{destructive_match}'",
            )

        read_match = next((term for term in read_verbs if term in text), None)
        write_match = next((term for term in write_verbs if term in text), None)
        financial_domain = next((term for term in financial_domains if term in text), None)

        # Explicit read-only intent wins over financial nouns such as "billing"
        # or "payment", unless the description also contains a write operation.
        if financial_domain and write_match:
            return ActionSafetyResult(
                level=ActionSafetyLevel.FINANCIAL,
                confidence=0.95,
                matched_keyword=financial_domain,
                reasoning=f"Financial write operation detected ({financial_domain}/{write_match})",
            )

        if read_match and not write_match:
            sensitive = next(
                (term for term in _KEYWORDS[ActionSafetyLevel.SENSITIVE_PII] if term in text),
                None,
            )
            level = ActionSafetyLevel.SENSITIVE_PII if sensitive else ActionSafetyLevel.READ
            return ActionSafetyResult(
                level=level,
                confidence=0.9,
                matched_keyword=sensitive or read_match,
                reasoning=f"Read-only operation matched '{sensitive or read_match}'",
            )

        if financial_domain:
            return ActionSafetyResult(
                level=ActionSafetyLevel.FINANCIAL,
                confidence=0.8,
                matched_keyword=financial_domain,
                reasoning=f"Financial tool requires approval ({financial_domain})",
            )

        if write_match:
            return ActionSafetyResult(
                level=ActionSafetyLevel.WRITE,
                confidence=0.9,
                matched_keyword=write_match,
                reasoning=f"Write operation matched '{write_match}'",
            )

        return ActionSafetyResult(
            level=ActionSafetyLevel.READ,
            confidence=0.5,
            matched_keyword=None,
            reasoning="No operation intent matched; caller must fail closed",
        )
    except Exception:
        return ActionSafetyResult(
            level=ActionSafetyLevel.DESTRUCTIVE,
            confidence=0.0,
            matched_keyword=None,
            reasoning="Error during classification; blocking for manual review",
        )


def needs_approval(level: ActionSafetyLevel) -> bool:
    """Return True if the action requires human approval."""
    return level in (ActionSafetyLevel.FINANCIAL, ActionSafetyLevel.DESTRUCTIVE)
