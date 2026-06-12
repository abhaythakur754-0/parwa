"""
PARWA Phase 3 — AI Action Audit Trail

Records every action the AI agent performs on behalf of a user, with
automatic PII sanitization so that logs never contain raw emails, phone
numbers, SSNs, or credit-card numbers.

All queries are strictly scoped to company_id (BC-001).
All operations are wrapped in try/except (BC-008).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# PII regex patterns
# ------------------------------------------------------------------
_PII_PATTERNS: Dict[str, re.Pattern[str]] = {
    "email": re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
    ),
    "phone": re.compile(
        r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}"
    ),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(
        r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
    ),
}

_PII_REPLACEMENTS: Dict[str, str] = {
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
    "ssn": "[REDACTED_SSN]",
    "credit_card": "[REDACTED_CC]",
}


@dataclass
class AuditLog:
    """Immutable record of a single audited action."""

    id: str
    company_id: str
    user_id: str
    action: str
    tool: str
    details: dict
    outcome: str
    timestamp: str
    sanitized_details: dict = field(default_factory=dict)


class AuditTrailService:
    """Central service for logging and querying AI action audit trails.

    Storage is in-memory for Phase 3; a production deployment would
    persist to a database.  Every method is company-scoped and
    wrapped in error handling.
    """

    def __init__(self) -> None:
        self._logs: Dict[str, List[AuditLog]] = {}  # company_id -> list

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_action(
        self,
        company_id: str,
        user_id: str,
        action: str,
        tool: str,
        details: dict,
        outcome: str = "success",
    ) -> dict:
        """Record a new audit entry.

        Parameters
        ----------
        company_id:
            Tenant identifier (BC-001 scoping).
        user_id:
            The user who initiated the action.
        action:
            Human-readable action name (e.g. ``"create_contact"``).
        tool:
            The integration or tool used (e.g. ``"hubspot"``).
        details:
            Arbitrary metadata about the action.
        outcome:
            ``"success"`` or ``"failure"``.

        Returns
        -------
        dict
            The full audit log entry as a dict.
        """
        try:
            sanitized = self._sanitize(details)
            log_entry = AuditLog(
                id=str(uuid.uuid4()),
                company_id=company_id,
                user_id=user_id,
                action=action,
                tool=tool,
                details=details,
                outcome=outcome,
                timestamp=datetime.now(timezone.utc).isoformat(),
                sanitized_details=sanitized,
            )

            if company_id not in self._logs:
                self._logs[company_id] = []
            self._logs[company_id].append(log_entry)

            logger.info(
                "Audit log recorded: company=%s action=%s tool=%s outcome=%s",
                company_id,
                action,
                tool,
                outcome,
            )
            return asdict(log_entry)
        except Exception as exc:
            logger.error(
                "Failed to log audit action for company_id=%s: %s", company_id, exc
            )
            return {
                "error": "audit_log_failed",
                "company_id": company_id,
                "action": action,
                "tool": tool,
            }

    def get_trail(
        self,
        company_id: str,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        """Retrieve audit trail entries for *company_id*, optionally filtered.

        Filters can include ``action``, ``tool``, ``outcome``,
        ``user_id``, ``from_timestamp``, ``to_timestamp``.

        Returns only sanitized details to prevent PII leakage in
        read operations.
        """
        try:
            entries = self._logs.get(company_id, [])
            results: List[dict] = []

            for entry in entries:
                if filters and not self._matches_filter(entry, filters):
                    continue
                results.append(
                    {
                        "id": entry.id,
                        "company_id": entry.company_id,
                        "user_id": entry.user_id,
                        "action": entry.action,
                        "tool": entry.tool,
                        "details": entry.sanitized_details,
                        "outcome": entry.outcome,
                        "timestamp": entry.timestamp,
                    }
                )

            return results
        except Exception as exc:
            logger.error(
                "Failed to get audit trail for company_id=%s: %s", company_id, exc
            )
            return []

    def export_trail(self, company_id: str, format: str = "json") -> str:
        """Export the full audit trail for *company_id*.

        Parameters
        ----------
        company_id:
            Tenant identifier.
        format:
            ``"json"`` is the only supported format in Phase 3.

        Returns
        -------
        str
            Serialized trail data.
        """
        try:
            entries = self.get_trail(company_id)
            if format == "json":
                return json.dumps(entries, indent=2, default=str)
            raise ValueError(f"Unsupported export format: {format}")
        except Exception as exc:
            logger.error(
                "Failed to export audit trail for company_id=%s: %s", company_id, exc
            )
            return json.dumps({"error": "export_failed", "company_id": company_id})

    # ------------------------------------------------------------------
    # PII sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize(data: dict) -> dict:
        """Return a deep copy of *data* with PII fields redacted.

        Recurses into nested dicts and lists.
        """
        try:
            return AuditTrailService._sanitize_value(data)
        except Exception as exc:
            logger.error("Sanitization failed: %s", exc)
            return {"error": "sanitization_failed"}

    @staticmethod
    def _sanitize_value(value: Any) -> Any:
        """Recursively sanitize a value."""
        if isinstance(value, dict):
            return {k: AuditTrailService._sanitize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [AuditTrailService._sanitize_value(item) for item in value]
        if isinstance(value, str):
            return AuditTrailService._redact_string(value)
        return value

    @staticmethod
    def _redact_string(text: str) -> str:
        """Apply PII regex replacements to a string.

        Patterns are applied in order from most specific to least
        specific so that, for example, a 16-digit credit-card number
        is fully redacted before the phone regex can match a partial
        substring.
        """
        # Order matters: credit_card and ssn are more specific than phone
        _apply_order = ["credit_card", "ssn", "email", "phone"]
        result = text
        for pii_type in _apply_order:
            pattern = _PII_PATTERNS[pii_type]
            result = pattern.sub(_PII_REPLACEMENTS[pii_type], result)
        return result

    # ------------------------------------------------------------------
    # Filter matching
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_filter(entry: AuditLog, filters: dict) -> bool:
        """Return ``True`` if *entry* matches all *filters*."""
        if "action" in filters and entry.action != filters["action"]:
            return False
        if "tool" in filters and entry.tool != filters["tool"]:
            return False
        if "outcome" in filters and entry.outcome != filters["outcome"]:
            return False
        if "user_id" in filters and entry.user_id != filters["user_id"]:
            return False
        if "from_timestamp" in filters:
            if entry.timestamp < filters["from_timestamp"]:
                return False
        if "to_timestamp" in filters:
            if entry.timestamp > filters["to_timestamp"]:
                return False
        return True
