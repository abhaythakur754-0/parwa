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
    """Classify a Superglue tool action by keyword matching.

    Scans both *tool_name* and *tool_description* (case-insensitive).
    Returns the highest-severity match. Defaults to READ.
    BC-008: never raises — returns READ on any error.
    """
    try:
        text = f"{tool_name} {tool_description}".lower()

        best_level = ActionSafetyLevel.READ
        best_keyword: Optional[str] = None

        for level in _PRIORITY:
            for kw in _KEYWORDS[level]:
                if kw in text:
                    best_level = level
                    best_keyword = kw
                    break  # found highest-severity match
            if best_keyword is not None:
                break

        confidence = 0.9 if best_keyword else 0.5
        reasoning = (
            f"Matched keyword '{best_keyword}' -> {best_level.value}"
            if best_keyword
            else "No keyword matched; defaulting to READ"
        )
        return ActionSafetyResult(
            level=best_level,
            confidence=confidence,
            matched_keyword=best_keyword,
            reasoning=reasoning,
        )
    except Exception:
        return ActionSafetyResult(
            level=ActionSafetyLevel.READ,
            confidence=0.0,
            matched_keyword=None,
            reasoning="Error during classification; defaulting to READ",
        )


def needs_approval(level: ActionSafetyLevel) -> bool:
    """Return True if the action requires human approval."""
    return level in (ActionSafetyLevel.FINANCIAL, ActionSafetyLevel.DESTRUCTIVE)
