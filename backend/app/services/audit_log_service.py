"""
Audit Log Service (SG-13)

Higher-level audit log management layer built ON TOP of the basic
audit_service.py CRUD operations.  Provides:

  - Structured audit log entries with SHA-256 checksums for tamper detection
  - Category-based retention policies (e.g. security=7 years, system=90 days)
  - Audit log analytics and statistics (category/severity distributions)
  - Compliance export capabilities (JSON / CSV)
  - Audit log integrity verification (checksum-based tamper detection)
  - Real-time audit event streaming (mock)
  - Sensitive data redaction

NOTE: This service does NOT duplicate the basic CRUD in audit_service.py.
      Instead it layers advanced compliance, analytics, and integrity
      features on top of the existing audit infrastructure.

BC-001: All public methods take company_id as first parameter.
BC-008: Every method wrapped in try/except — never crash.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.exceptions import ParwaBaseError
from app.logger import get_logger

logger = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════


class AuditSeverity(str, Enum):
    """Severity levels for audit log entries."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SECURITY = "security"


class AuditCategory(str, Enum):
    """Categories for classifying audit events."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    BILLING = "billing"
    SYSTEM = "system"
    AI_OPERATION = "ai_operation"
    INTEGRATION = "integration"


class ExportFormat(str, Enum):
    """Supported export formats for compliance reports."""

    JSON = "json"
    CSV = "csv"


class IntegrityStatus(str, Enum):
    """Result of an integrity check on audit log entries."""

    VALID = "valid"
    TAMPERED = "tampered"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


# ══════════════════════════════════════════════════════════════════
# DATACLASSES
# ══════════════════════════════════════════════════════════════════


@dataclass
class AuditLogEntry:
    """A single structured audit log entry with integrity checksum.

    This is the in-memory representation used by the higher-level
    audit log service.  It extends the basic AuditEntry from
    audit_service.py with category, severity, metadata, and a
    tamper-detection checksum.
    """

    entry_id: str
    company_id: str
    category: AuditCategory
    severity: AuditSeverity
    action: str
    actor_id: Optional[str] = None
    actor_type: str = "user"
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


@dataclass
class AuditRetentionPolicy:
    """Retention configuration for audit log entries.

    Supports per-category retention periods so that security-sensitive
    categories (e.g. AUTHENTICATION, AUTHORIZATION) can be kept for
    longer periods than routine system events.

    Attributes:
        company_id: Tenant the policy applies to (BC-001).
        category_retention_days: Map of category name to retention in days.
            Categories not listed fall back to the class-level default.
        max_entries_per_category: Max entries to keep per category (0 = unlimited).
        enable_auto_cleanup: Whether periodic cleanup is active.
        cleanup_frequency_hours: How often auto-cleanup runs (hours).
    """

    company_id: str
    category_retention_days: Dict[str, int] = field(default_factory=dict)
    max_entries_per_category: int = 0  # 0 = unlimited
    enable_auto_cleanup: bool = True
    cleanup_frequency_hours: int = 24


@dataclass
class AuditStats:
    """Aggregated statistics for a company's audit log.

    Computed over a configurable look-back window.
    """

    company_id: str
    total_entries: int = 0
    entries_by_category: Dict[str, int] = field(default_factory=dict)
    entries_by_severity: Dict[str, int] = field(default_factory=dict)
    entries_last_24h: int = 0
    entries_last_7d: int = 0
    most_active_actors: List[Dict[str, Any]] = field(default_factory=list)
    unique_resources: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class AuditIntegrityReport:
    """Result of an integrity verification pass.

    Checks every entry in the requested range against its stored
    SHA-256 checksum to detect tampering.
    """

    company_id: str
    status: IntegrityStatus = IntegrityStatus.UNKNOWN
    total_checked: int = 0
    valid_count: int = 0
    tampered_count: int = 0
    missing_count: int = 0
    checked_range_start: Optional[datetime] = None
    checked_range_end: Optional[datetime] = None
    details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AuditExportResult:
    """Result of a compliance export operation.

    Contains the exported data (or a file path) along with metadata
    about the export run.
    """

    company_id: str
    format: ExportFormat = ExportFormat.JSON
    total_entries: int = 0
    file_path_or_data: Any = None
    export_started_at: Optional[datetime] = None
    export_completed_at: Optional[datetime] = None
    entry_count: int = 0


@dataclass
class AuditLogConfig:
    """Global configuration for the audit log service.

    Attributes:
        default_retention_days: Fallback retention when no per-category
            policy is defined.
        max_batch_size: Maximum entries processed in a single batch
            (for exports, cleanups, etc.).
        enable_checksum: Whether to compute and store SHA-256 checksums.
        enable_streaming: Whether to push events to the real-time stream.
        sensitive_fields: Field names that should be redacted when
            exporting or displaying audit entries.
        checksum_algorithm: Hash algorithm used for tamper detection.
    """

    default_retention_days: int = 365
    max_batch_size: int = 1000
    enable_checksum: bool = True
    enable_streaming: bool = True
    sensitive_fields: Tuple[str, ...] = (
        "password",
        "token",
        "api_key",
        "secret",
    )
    checksum_algorithm: str = "sha256"


# ══════════════════════════════════════════════════════════════════
# CUSTOM ERROR
# ══════════════════════════════════════════════════════════════════


class AuditLogError(ParwaBaseError):
    """Raised when an audit log operation fails.

    Error codes:
        INVALID_COMPANY_ID  — company_id missing or empty
        INVALID_CATEGORY    — category is not a valid AuditCategory
        INVALID_SEVERITY    — severity is not a valid AuditSeverity
        ENTRY_NOT_FOUND     — requested entry does not exist
        EXPORT_FAILED       — compliance export encountered an error
        INTEGRITY_VIOLATION — checksum mismatch detected
    """


# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════
# Default per-category retention when no explicit policy is set.
# Security categories get longer retention for compliance (e.g. SOC2).
_DEFAULT_CATEGORY_RETENTION_DAYS: Dict[str, int] = {
    AuditCategory.AUTHENTICATION.value: 2555,  # 7 years
    AuditCategory.AUTHORIZATION.value: 2555,  # 7 years
    AuditCategory.DATA_ACCESS.value: 1095,  # 3 years
    AuditCategory.DATA_MODIFICATION.value: 1095,  # 3 years
    AuditCategory.BILLING.value: 2555,  # 7 years
    AuditCategory.SYSTEM.value: 90,  # 90 days
    AuditCategory.AI_OPERATION.value: 365,  # 1 year
    AuditCategory.INTEGRATION.value: 365,  # 1 year
}

# Actions that are considered security-sensitive for alert generation.
_SECURITY_RELEVANT_ACTIONS: frozenset = frozenset(
    {
        "login_failed",
        "permission_change",
        "api_key_revoke",
        "api_key_rotate",
        "settings_change",
        "delete",
        "export",
    }
)

# Maximum number of alerts kept in memory per company.
_MAX_ALERTS_PER_COMPANY: int = 100


# ══════════════════════════════════════════════════════════════════
# VALIDATION HELPERS
# ══════════════════════════════════════════════════════════════════


def _validate_company_id(company_id: str) -> None:
    """BC-001: company_id is required and must be a non-empty string."""
    if not company_id or not str(company_id).strip():
        raise AuditLogError(
            error_code="INVALID_COMPANY_ID",
            message="company_id is required and cannot be empty",
            status_code=400,
        )


def _validate_category(category: Any) -> AuditCategory:
    """Validate that category is a recognised AuditCategory value.

    Accepts both AuditCategory enum members and their string values.

    Returns:
        The validated AuditCategory enum.

    Raises:
        AuditLogError: If the category is not recognised.
    """
    if isinstance(category, AuditCategory):
        return category
    if isinstance(category, str) and category.strip():
        try:
            return AuditCategory(category.strip().lower())
        except ValueError:
            valid = ", ".join(c.value for c in AuditCategory)
            raise AuditLogError(
                error_code="INVALID_CATEGORY",
                message=(f"Invalid category '{category}'. " f"Must be one of: {valid}"),
                status_code=400,
            )
    valid = ", ".join(c.value for c in AuditCategory)
    raise AuditLogError(
        error_code="INVALID_CATEGORY",
        message=(
            "Category must be a non-empty string or AuditCategory enum. "
            f"Valid values: {valid}"
        ),
        status_code=400,
    )


def _validate_severity(severity: Any) -> AuditSeverity:
    """Validate that severity is a recognised AuditSeverity value.

    Accepts both AuditSeverity enum members and their string values.

    Returns:
        The validated AuditSeverity enum.

    Raises:
        AuditLogError: If the severity is not recognised.
    """
    if isinstance(severity, AuditSeverity):
        return severity
    if isinstance(severity, str) and severity.strip():
        try:
            return AuditSeverity(severity.strip().lower())
        except ValueError:
            valid = ", ".join(s.value for s in AuditSeverity)
            raise AuditLogError(
                error_code="INVALID_SEVERITY",
                message=(f"Invalid severity '{severity}'. " f"Must be one of: {valid}"),
                status_code=400,
            )
    valid = ", ".join(s.value for s in AuditSeverity)
    raise AuditLogError(
        error_code="INVALID_SEVERITY",
        message=(
            "Severity must be a non-empty string or AuditSeverity enum. "
            f"Valid values: {valid}"
        ),
        status_code=400,
    )


# ══════════════════════════════════════════════════════════════════
# SERVICE
# ══════════════════════════════════════════════════════════════════


class AuditLogService:
    """
    Audit Log Service (SG-13).

    Provides advanced audit log management capabilities on top of the
    basic CRUD in audit_service.py:

    - Structured logging with category / severity taxonomy
    - SHA-256 checksum-based integrity verification
    - Per-category retention policies for compliance
    - Analytics and statistics over audit trails
    - JSON / CSV compliance exports
    - Sensitive data redaction
    - Security alert generation

    All public methods accept ``company_id`` as their first argument
    (BC-001) and are wrapped in try/except for graceful degradation
    (BC-008).
    """

    def __init__(
        self,
        config: Optional[AuditLogConfig] = None,
    ) -> None:
        self.config = config or AuditLogConfig()

        # In-memory audit log store (keyed by company_id)
        # In production this would delegate to the database via
        # audit_service.py; here we maintain a local store for
        # the advanced features to operate on.
        self._entries: Dict[str, List[AuditLogEntry]] = {}

        # Per-company retention policies
        self._retention_policies: Dict[str, AuditRetentionPolicy] = {}

        # Per-company security alerts
        self._alerts: Dict[str, List[Dict[str, Any]]] = {}

        # Real-time event stream subscribers (mock — no actual WebSocket)
        self._stream_callbacks: List = []

        # Thread-safety lock for all mutable state
        self._lock = threading.Lock()

    # ═══════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ═══════════════════════════════════════════════════════════

    def _get_entries(self, company_id: str) -> List[AuditLogEntry]:
        """Return the entry list for a company (empty list if none)."""
        return self._entries.get(company_id, [])

    def _set_entries(
        self,
        company_id: str,
        entries: List[AuditLogEntry],
    ) -> None:
        """Replace the entry list for a company."""
        self._entries[company_id] = entries

    def _find_entry_by_id(
        self,
        company_id: str,
        entry_id: str,
    ) -> Optional[AuditLogEntry]:
        """Look up a single entry by ID within a company's log."""
        for entry in self._get_entries(company_id):
            if entry.entry_id == entry_id:
                return entry
        return None

    def _compute_checksum(self, entry_data: dict) -> str:
        """Compute an SHA-256 checksum over the entry's fields.

        The checksum covers all mutable content fields so that any
        post-hoc modification is detectable.  The checksum itself
        is excluded from the hash input.

        Args:
            entry_data: Dictionary of entry fields (excluding checksum).

        Returns:
            Hex-encoded SHA-256 digest string.
        """
        if not self.config.enable_checksum:
            return ""

        # Build a deterministic string from the entry fields.
        # Sort keys for consistent serialisation across runs.
        hash_fields = {
            "entry_id": entry_data.get("entry_id", ""),
            "company_id": entry_data.get("company_id", ""),
            "category": str(entry_data.get("category", "")),
            "severity": str(entry_data.get("severity", "")),
            "action": entry_data.get("action", ""),
            "actor_id": entry_data.get("actor_id") or "",
            "actor_type": entry_data.get("actor_type", ""),
            "resource_type": entry_data.get("resource_type") or "",
            "resource_id": entry_data.get("resource_id") or "",
            "old_value": entry_data.get("old_value") or "",
            "new_value": entry_data.get("new_value") or "",
            "ip_address": entry_data.get("ip_address") or "",
            "metadata": json.dumps(
                entry_data.get("metadata", {}),
                sort_keys=True,
                default=str,
            ),
            "created_at": str(entry_data.get("created_at", "")),
        }
        canonical = json.dumps(hash_fields, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _validate_checksum(self, entry: AuditLogEntry) -> bool:
        """Verify that an entry's stored checksum matches the recomputed one.

        Returns:
            True if checksums match (or checksums are disabled).
        """
        if not self.config.enable_checksum or not entry.checksum:
            # If checksums aren't enabled or entry has none, we
            # cannot verify — treat as unknown rather than failed.
            return True

        entry_data = {
            "entry_id": entry.entry_id,
            "company_id": entry.company_id,
            "category": entry.category.value,
            "severity": entry.severity.value,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "actor_type": entry.actor_type,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "old_value": entry.old_value,
            "new_value": entry.new_value,
            "ip_address": entry.ip_address,
            "metadata": entry.metadata,
            "created_at": entry.created_at.isoformat() if entry.created_at else "",
        }
        computed = self._compute_checksum(entry_data)
        return computed == entry.checksum

    def _redact_field(self, value: str) -> str:
        """Mask a sensitive field value.

        Replaces the value with asterisks of equal length, preserving
        first and last character for debugging context.  Short values
        (≤ 2 chars) are fully redacted.

        Args:
            value: The original value to redact.

        Returns:
            Masked string.
        """
        if not value or not isinstance(value, str):
            return ""
        if len(value) <= 2:
            return "*" * len(value)
        return value[0] + "*" * (len(value) - 2) + value[-1]

    def _should_retain(
        self,
        entry: AuditLogEntry,
        policy: AuditRetentionPolicy,
    ) -> bool:
        """Determine whether an entry should be retained per policy.

        Checks both the time-based retention (category-specific days)
        and the per-category max entries cap.

        Args:
            entry: The audit log entry to evaluate.
            policy: The retention policy to apply.

        Returns:
            True if the entry should be kept, False if it should be purged.
        """
        now = datetime.now(timezone.utc)
        entry_time = entry.created_at

        # ── Time-based check ──
        category_key = entry.category.value
        retention_days = policy.category_retention_days.get(
            category_key,
            _DEFAULT_CATEGORY_RETENTION_DAYS.get(
                category_key,
                self.config.default_retention_days,
            ),
        )
        cutoff = now - timedelta(days=retention_days)
        if entry_time < cutoff:
            return False

        # ── Max entries cap check ──
        if policy.max_entries_per_category > 0:
            company_entries = self._get_entries(entry.company_id)
            category_entries = [
                e for e in company_entries if e.category == entry.category
            ]
            if len(category_entries) > policy.max_entries_per_category:
                # The entry is among the oldest beyond the cap —
                # sort by created_at ascending to identify overflow.
                sorted_entries = sorted(
                    category_entries,
                    key=lambda e: e.created_at,
                )
                cutoff_idx = len(sorted_entries) - policy.max_entries_per_category
                if entry.entry_id in [e.entry_id for e in sorted_entries[:cutoff_idx]]:
                    return False

        return True

    def _stream_event(self, entry: AuditLogEntry) -> None:
        """Push the event to registered real-time stream subscribers.

        This is a mock implementation — in production this would
        publish to a WebSocket channel, Redis pub/sub, or similar
        real-time messaging system.

        The call is fire-and-forget; errors are logged but never
        propagated to the caller (BC-008).
        """
        if not self.config.enable_streaming:
            return

        event_payload = {
            "event_type": "audit_log_entry",
            "entry_id": entry.entry_id,
            "company_id": entry.company_id,
            "category": entry.category.value,
            "severity": entry.severity.value,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "actor_type": entry.actor_type,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "timestamp": (entry.created_at.isoformat() if entry.created_at else None),
        }

        for callback in self._stream_callbacks:
            try:
                callback(event_payload)
            except Exception as exc:
                logger.warning(
                    "audit_stream_callback_error",
                    entry_id=entry.entry_id,
                    error=str(exc),
                )

    def _create_security_alert(
        self,
        company_id: str,
        alert_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create and store a security alert for a company.

        Alerts are kept in-memory up to ``_MAX_ALERTS_PER_COMPANY``.
        Older alerts are evicted FIFO when the cap is reached.

        Args:
            company_id: Tenant that owns the alert.
            alert_type: Short identifier for the alert type.
            details: Structured details about the alert.

        Returns:
            The created alert dictionary.
        """
        alert = {
            "alert_id": str(uuid.uuid4()),
            "company_id": company_id,
            "alert_type": alert_type,
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "acknowledged": False,
        }

        with self._lock:
            if company_id not in self._alerts:
                self._alerts[company_id] = []
            company_alerts = self._alerts[company_id]
            company_alerts.append(alert)

            # Evict oldest alerts if over the cap
            while len(company_alerts) > _MAX_ALERTS_PER_COMPANY:
                company_alerts.pop(0)

        logger.info(
            "security_alert_created",
            company_id=company_id,
            alert_type=alert_type,
            alert_id=alert["alert_id"],
        )
        return alert

    def _entry_to_dict(
        self,
        entry: AuditLogEntry,
        redact: bool = False,
    ) -> Dict[str, Any]:
        """Serialise an AuditLogEntry to a dictionary.

        Args:
            entry: The entry to serialise.
            redact: If True, sensitive fields are masked.

        Returns:
            Dictionary representation of the entry.
        """
        old_value = entry.old_value
        new_value = entry.new_value
        metadata = dict(entry.metadata)

        if redact:
            # Redact top-level sensitive fields
            for sensitive_key in self.config.sensitive_fields:
                if sensitive_key in metadata:
                    val = metadata[sensitive_key]
                    if isinstance(val, str):
                        metadata[sensitive_key] = self._redact_field(val)
                    elif isinstance(val, dict):
                        for k, v in val.items():
                            if isinstance(v, str):
                                val[k] = self._redact_field(v)

            # Redact values that look like they contain sensitive data
            old_value = self._redact_if_sensitive(old_value)
            new_value = self._redact_if_sensitive(new_value)

        return {
            "entry_id": entry.entry_id,
            "company_id": entry.company_id,
            "category": entry.category.value,
            "severity": entry.severity.value,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "actor_type": entry.actor_type,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "old_value": old_value,
            "new_value": new_value,
            "ip_address": entry.ip_address,
            "user_agent": entry.user_agent,
            "metadata": metadata,
            "checksum": entry.checksum,
            "created_at": (entry.created_at.isoformat() if entry.created_at else None),
        }

    def _redact_if_sensitive(self, value: Optional[str]) -> Optional[str]:
        """Check if a value appears to contain sensitive keywords and redact.

        This is a best-effort heuristic — it scans for field names that
        appear in the config's sensitive_fields list within JSON or
        key=value patterns.
        """
        if not value or not isinstance(value, str):
            return value

        # Try to detect if the value is a JSON blob containing
        # sensitive keys
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                modified = False
                for key in self.config.sensitive_fields:
                    if key in parsed and isinstance(parsed[key], str):
                        parsed[key] = self._redact_field(parsed[key])
                        modified = True
                if modified:
                    return json.dumps(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

        return value

    # ═══════════════════════════════════════════════════════════
    # PUBLIC METHODS
    # ═══════════════════════════════════════════════════════════

    def log_event(
        self,
        company_id: str,
        category: Any,
        severity: Any,
        action: str,
        actor_id: Optional[str] = None,
        actor_type: str = "user",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLogEntry:
        """Log a structured audit event with checksum.

        Creates a full AuditLogEntry, computes its integrity checksum,
        persists it to the in-memory store, streams it to real-time
        subscribers, and generates security alerts if the action is
        security-relevant.

        Args:
            company_id: Tenant ID (BC-001).
            category: Event category (AuditCategory or string).
            severity: Event severity (AuditSeverity or string).
            action: Human-readable action description.
            actor_id: Who performed the action.
            actor_type: Type of actor (user, system, api_key).
            resource_type: Type of resource affected.
            resource_id: ID of the resource.
            old_value: Previous value (for updates).
            new_value: New value (for creates/updates).
            metadata: Arbitrary structured metadata.
            ip_address: Client IP address.
            user_agent: Client user-agent string.

        Returns:
            The created AuditLogEntry.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)
            validated_category = _validate_category(category)
            validated_severity = _validate_severity(severity)

            if not action or not str(action).strip():
                raise AuditLogError(
                    error_code="INVALID_CATEGORY",
                    message="action is required and cannot be empty",
                    status_code=400,
                )

            entry_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            # Build the entry data dict for checksum computation
            # (checksum not yet included)
            entry_data = {
                "entry_id": entry_id,
                "company_id": company_id,
                "category": validated_category.value,
                "severity": validated_severity.value,
                "action": str(action).strip(),
                "actor_id": actor_id,
                "actor_type": actor_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "old_value": old_value,
                "new_value": new_value,
                "ip_address": ip_address,
                "metadata": metadata or {},
                "created_at": now.isoformat(),
            }

            checksum = self._compute_checksum(entry_data)

            entry = AuditLogEntry(
                entry_id=entry_id,
                company_id=company_id,
                category=validated_category,
                severity=validated_severity,
                action=str(action).strip(),
                actor_id=actor_id,
                actor_type=actor_type,
                resource_type=resource_type,
                resource_id=resource_id,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata or {},
                checksum=checksum,
                created_at=now,
            )

            # Store the entry
            with self._lock:
                entries = self._get_entries(company_id)
                entries.append(entry)
                self._set_entries(company_id, entries)

            # Stream to real-time consumers (fire-and-forget)
            self._stream_event(entry)

            # Generate security alert for security-relevant actions
            action_lower = str(action).strip().lower()
            if action_lower in _SECURITY_RELEVANT_ACTIONS:
                self._create_security_alert(
                    company_id=company_id,
                    alert_type=f"audit_{action_lower}",
                    details={
                        "entry_id": entry_id,
                        "action": action,
                        "actor_id": actor_id,
                        "actor_type": actor_type,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "ip_address": ip_address,
                        "severity": validated_severity.value,
                    },
                )

            logger.info(
                "audit_event_logged",
                company_id=company_id,
                entry_id=entry_id,
                category=validated_category.value,
                severity=validated_severity.value,
                action=str(action).strip(),
                actor_id=actor_id,
            )

            return entry

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "log_event_error",
                company_id=company_id,
                error=str(exc),
            )
            # Return a minimal entry so callers never crash (BC-008)
            return AuditLogEntry(
                entry_id=str(uuid.uuid4()),
                company_id=company_id,
                category=_validate_category("system"),
                severity=AuditSeverity.WARNING,
                action=f"error_fallback: {str(exc)[:100]}",
                created_at=datetime.now(timezone.utc),
            )

    def query_events(
        self,
        company_id: str,
        category: Any = None,
        severity: Any = None,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Tuple[List[AuditLogEntry], int]:
        """Query audit log events with filtering and pagination.

        All results are scoped to ``company_id`` (BC-001).

        Args:
            company_id: Tenant ID (BC-001).
            category: Filter by AuditCategory (enum or string).
            severity: Filter by AuditSeverity (enum or string).
            actor_id: Filter by the actor who performed the action.
            resource_type: Filter by resource type.
            date_from: Include entries at or after this datetime.
            date_to: Include entries at or before this datetime.
            offset: Pagination offset (records to skip).
            limit: Max records to return.

        Returns:
            Tuple of (matching_entries, total_matching_count).

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)

            # Validate filter values if provided
            validated_category: Optional[AuditCategory] = None
            if category is not None:
                validated_category = _validate_category(category)

            validated_severity: Optional[AuditSeverity] = None
            if severity is not None:
                validated_severity = _validate_severity(severity)

            # Clamp pagination values to sensible ranges
            offset = max(0, int(offset))
            limit = max(1, min(int(limit), self.config.max_batch_size))

            with self._lock:
                all_entries = self._get_entries(company_id)

            # Apply filters
            filtered: List[AuditLogEntry] = []
            for entry in all_entries:
                # Category filter
                if validated_category is not None:
                    if entry.category != validated_category:
                        continue
                # Severity filter
                if validated_severity is not None:
                    if entry.severity != validated_severity:
                        continue
                # Actor ID filter
                if actor_id is not None:
                    if entry.actor_id != actor_id:
                        continue
                # Resource type filter
                if resource_type is not None:
                    if entry.resource_type != resource_type:
                        continue
                # Date range filters
                if date_from is not None and entry.created_at:
                    if entry.created_at < date_from:
                        continue
                if date_to is not None and entry.created_at:
                    if entry.created_at > date_to:
                        continue

                filtered.append(entry)

            # Sort by created_at descending (newest first)
            filtered.sort(key=lambda e: e.created_at or datetime.min, reverse=True)

            total = len(filtered)
            page = filtered[offset : offset + limit]

            logger.debug(
                "audit_events_queried",
                company_id=company_id,
                filters_applied={
                    "category": (
                        validated_category.value if validated_category else None
                    ),
                    "severity": (
                        validated_severity.value if validated_severity else None
                    ),
                    "actor_id": actor_id,
                    "resource_type": resource_type,
                },
                total=total,
                returned=len(page),
                offset=offset,
                limit=limit,
            )

            return page, total

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "query_events_error",
                company_id=company_id,
                error=str(exc),
            )
            return [], 0

    def get_statistics(
        self,
        company_id: str,
        days: int = 30,
    ) -> AuditStats:
        """Get aggregated audit log statistics for a company.

        Computes category/severity distributions, temporal counts,
        most active actors, and unique resource counts over the
        specified look-back window.

        Args:
            company_id: Tenant ID (BC-001).
            days: Look-back window in days (default 30).

        Returns:
            AuditStats with aggregated metrics.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)
            days = max(1, min(int(days), 3650))  # Cap at 10 years

            now = datetime.now(timezone.utc)
            period_start = now - timedelta(days=days)
            period_end = now

            # Time thresholds for recent counts
            last_24h_cutoff = now - timedelta(hours=24)
            last_7d_cutoff = now - timedelta(days=7)

            with self._lock:
                all_entries = self._get_entries(company_id)

            entries_by_category: Dict[str, int] = {}
            entries_by_severity: Dict[str, int] = {}
            actor_counts: Dict[str, int] = {}
            resource_set: set = set()
            total_entries = 0
            entries_last_24h = 0
            entries_last_7d = 0

            for entry in all_entries:
                if not entry.created_at or entry.created_at < period_start:
                    continue

                total_entries += 1

                # Category distribution
                cat_key = entry.category.value
                entries_by_category[cat_key] = entries_by_category.get(cat_key, 0) + 1

                # Severity distribution
                sev_key = entry.severity.value
                entries_by_severity[sev_key] = entries_by_severity.get(sev_key, 0) + 1

                # Actor activity
                if entry.actor_id:
                    actor_counts[entry.actor_id] = (
                        actor_counts.get(entry.actor_id, 0) + 1
                    )

                # Unique resources
                if entry.resource_type and entry.resource_id:
                    resource_set.add(f"{entry.resource_type}:{entry.resource_id}")

                # Temporal counts
                if entry.created_at >= last_24h_cutoff:
                    entries_last_24h += 1
                if entry.created_at >= last_7d_cutoff:
                    entries_last_7d += 1

            # Top 10 most active actors
            most_active_actors = [
                {"actor_id": aid, "count": count}
                for aid, count in sorted(
                    actor_counts.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ]

            stats = AuditStats(
                company_id=company_id,
                total_entries=total_entries,
                entries_by_category=entries_by_category,
                entries_by_severity=entries_by_severity,
                entries_last_24h=entries_last_24h,
                entries_last_7d=entries_last_7d,
                most_active_actors=most_active_actors,
                unique_resources=len(resource_set),
                period_start=period_start,
                period_end=period_end,
            )

            logger.info(
                "audit_statistics_computed",
                company_id=company_id,
                total_entries=total_entries,
                period_days=days,
            )

            return stats

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_statistics_error",
                company_id=company_id,
                error=str(exc),
            )
            return AuditStats(
                company_id=company_id,
                period_start=datetime.now(timezone.utc) - timedelta(days=max(1, days)),
                period_end=datetime.now(timezone.utc),
            )

    def verify_integrity(
        self,
        company_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> AuditIntegrityReport:
        """Verify audit log integrity via SHA-256 checksum validation.

        Iterates over all entries in the requested range and recomputes
        each checksum.  Mismatches indicate potential tampering.

        Args:
            company_id: Tenant ID (BC-001).
            date_from: Start of range (inclusive). Defaults to all time.
            date_to: End of range (inclusive). Defaults to now.

        Returns:
            AuditIntegrityReport with validation results.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)

            now = datetime.now(timezone.utc)

            with self._lock:
                all_entries = self._get_entries(company_id)

            # Filter to date range
            checked: List[AuditLogEntry] = []
            for entry in all_entries:
                if not entry.created_at:
                    continue
                if date_from and entry.created_at < date_from:
                    continue
                if date_to and entry.created_at > date_to:
                    continue
                checked.append(entry)

            # Determine the actual checked range
            checked_range_start = None
            checked_range_end = None
            if checked:
                checked.sort(key=lambda e: e.created_at or datetime.min)
                checked_range_start = checked[0].created_at
                checked_range_end = checked[-1].created_at

            valid_count = 0
            tampered_count = 0
            missing_count = 0
            details: List[Dict[str, Any]] = []

            for entry in checked:
                if not entry.checksum:
                    # Entry has no checksum — can't verify.
                    # This is a partial result rather than tampered.
                    missing_count += 1
                    details.append(
                        {
                            "entry_id": entry.entry_id,
                            "status": "missing_checksum",
                            "message": "Entry has no checksum stored",
                        }
                    )
                    continue

                is_valid = self._validate_checksum(entry)
                if is_valid:
                    valid_count += 1
                else:
                    tampered_count += 1
                    details.append(
                        {
                            "entry_id": entry.entry_id,
                            "status": "tampered",
                            "message": "Checksum mismatch — entry may have been modified",
                            "category": entry.category.value,
                            "action": entry.action,
                            "created_at": (
                                entry.created_at.isoformat()
                                if entry.created_at
                                else None
                            ),
                        }
                    )

            # Determine overall status
            total_checked = len(checked)
            if total_checked == 0:
                status = IntegrityStatus.UNKNOWN
            elif tampered_count > 0:
                status = IntegrityStatus.TAMPERED
            elif missing_count > 0:
                status = IntegrityStatus.PARTIAL
            else:
                status = IntegrityStatus.VALID

            report = AuditIntegrityReport(
                company_id=company_id,
                status=status,
                total_checked=total_checked,
                valid_count=valid_count,
                tampered_count=tampered_count,
                missing_count=missing_count,
                checked_range_start=checked_range_start,
                checked_range_end=checked_range_end,
                details=details,
            )

            logger.info(
                "integrity_verification_completed",
                company_id=company_id,
                status=status.value,
                total_checked=total_checked,
                valid_count=valid_count,
                tampered_count=tampered_count,
                missing_count=missing_count,
            )

            # If tampering is detected, create a security alert
            if status == IntegrityStatus.TAMPERED:
                self._create_security_alert(
                    company_id=company_id,
                    alert_type="integrity_violation",
                    details={
                        "tampered_count": tampered_count,
                        "checked_range_start": (
                            checked_range_start.isoformat()
                            if checked_range_start
                            else None
                        ),
                        "checked_range_end": (
                            checked_range_end.isoformat() if checked_range_end else None
                        ),
                        "tampered_entries": [
                            d["entry_id"] for d in details if d["status"] == "tampered"
                        ],
                    },
                )

            return report

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "verify_integrity_error",
                company_id=company_id,
                error=str(exc),
            )
            return AuditIntegrityReport(
                company_id=company_id,
                status=IntegrityStatus.UNKNOWN,
                details=[{"error": str(exc)[:200]}],
            )

    def export_events(
        self,
        company_id: str,
        format: ExportFormat = ExportFormat.JSON,
        category: Any = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> AuditExportResult:
        """Export audit log events for compliance reporting.

        Supports JSON and CSV output formats.  Sensitive fields are
        automatically redacted in the exported data.

        Args:
            company_id: Tenant ID (BC-001).
            format: Export format (JSON or CSV).
            category: Optional category filter (AuditCategory or string).
            date_from: Start of range (inclusive).
            date_to: End of range (inclusive).

        Returns:
            AuditExportResult containing the exported data.

        Raises:
            AuditLogError: On validation failure.
        """
        export_started_at = datetime.now(timezone.utc)

        try:
            _validate_company_id(company_id)

            # Validate category if provided
            validated_category: Optional[AuditCategory] = None
            if category is not None:
                validated_category = _validate_category(category)

            with self._lock:
                all_entries = self._get_entries(company_id)

            # Filter entries
            filtered: List[AuditLogEntry] = []
            for entry in all_entries:
                if not entry.created_at:
                    continue
                if validated_category is not None:
                    if entry.category != validated_category:
                        continue
                if date_from and entry.created_at < date_from:
                    continue
                if date_to and entry.created_at > date_to:
                    continue
                filtered.append(entry)

            # Sort by created_at ascending for export
            filtered.sort(key=lambda e: e.created_at or datetime.min)

            # Serialise with sensitive data redacted
            export_rows = [
                self._entry_to_dict(entry, redact=True) for entry in filtered
            ]

            export_data: Any
            if format == ExportFormat.JSON:
                # Pretty-printed JSON with metadata wrapper
                export_data = {
                    "export_meta": {
                        "company_id": company_id,
                        "format": "json",
                        "exported_at": datetime.now(timezone.utc).isoformat(),
                        "total_entries": len(export_rows),
                        "filters": {
                            "category": (
                                validated_category.value if validated_category else None
                            ),
                            "date_from": (date_from.isoformat() if date_from else None),
                            "date_to": (date_to.isoformat() if date_to else None),
                        },
                    },
                    "entries": export_rows,
                }
            elif format == ExportFormat.CSV:
                # Build CSV in-memory using StringIO
                if not export_rows:
                    export_data = ""
                else:
                    output = io.StringIO()
                    # Use fieldnames from the first entry
                    flat_fieldnames = [
                        "entry_id",
                        "company_id",
                        "category",
                        "severity",
                        "action",
                        "actor_id",
                        "actor_type",
                        "resource_type",
                        "resource_id",
                        "old_value",
                        "new_value",
                        "ip_address",
                        "user_agent",
                        "checksum",
                        "created_at",
                    ]
                    writer = csv.DictWriter(output, fieldnames=flat_fieldnames)
                    writer.writeheader()
                    for row in export_rows:
                        flat_row = {
                            k: (
                                json.dumps(row[k])
                                if isinstance(row.get(k), dict)
                                else row.get(k, "")
                            )
                            for k in flat_fieldnames
                        }
                        writer.writerow(flat_row)
                    export_data = output.getvalue()
            else:
                raise AuditLogError(
                    error_code="EXPORT_FAILED",
                    message=(
                        f"Unsupported export format: {format}. " "Supported: json, csv"
                    ),
                    status_code=400,
                )

            export_completed_at = datetime.now(timezone.utc)

            result = AuditExportResult(
                company_id=company_id,
                format=format,
                total_entries=len(filtered),
                file_path_or_data=export_data,
                export_started_at=export_started_at,
                export_completed_at=export_completed_at,
                entry_count=len(export_rows),
            )

            logger.info(
                "audit_events_exported",
                company_id=company_id,
                format=format.value,
                total_entries=result.total_entries,
                duration_ms=(
                    (export_completed_at - export_started_at).total_seconds() * 1000
                ),
            )

            return result

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "export_events_error",
                company_id=company_id,
                error=str(exc),
            )
            return AuditExportResult(
                company_id=company_id,
                format=format,
                export_started_at=export_started_at,
                export_completed_at=datetime.now(timezone.utc),
                total_entries=0,
                entry_count=0,
                file_path_or_data={"error": str(exc)[:200]},
            )

    def retention_cleanup(
        self,
        company_id: str,
        policy: Optional[AuditRetentionPolicy] = None,
    ) -> int:
        """Clean up old audit entries per the retention policy.

        Removes entries that exceed their category-specific retention
        period.  If no policy is provided, uses the company's current
        policy (or the default).

        Args:
            company_id: Tenant ID (BC-001).
            policy: Optional policy override. If None, uses the stored
                policy for this company.

        Returns:
            Number of entries removed.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)

            # Resolve the effective policy
            effective_policy = policy or self.get_retention_policy(company_id)

            with self._lock:
                entries = self._get_entries(company_id)

                # Determine which entries to keep
                retained: List[AuditLogEntry] = []
                removed_count = 0

                for entry in entries:
                    if self._should_retain(entry, effective_policy):
                        retained.append(entry)
                    else:
                        removed_count += 1

                self._set_entries(company_id, retained)

            logger.info(
                "retention_cleanup_completed",
                company_id=company_id,
                removed_count=removed_count,
                retained_count=len(retained),
                policy_auto_cleanup=effective_policy.enable_auto_cleanup,
            )

            return removed_count

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "retention_cleanup_error",
                company_id=company_id,
                error=str(exc),
            )
            return 0

    def get_retention_policy(self, company_id: str) -> AuditRetentionPolicy:
        """Get the current retention policy for a company.

        If no custom policy has been set, returns the default policy
        populated with the standard category retention periods from
        ``_DEFAULT_CATEGORY_RETENTION_DAYS``.

        Args:
            company_id: Tenant ID (BC-001).

        Returns:
            The AuditRetentionPolicy for this company.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)

            with self._lock:
                if company_id in self._retention_policies:
                    return self._retention_policies[company_id]

                # Return the default policy
                default_policy = AuditRetentionPolicy(
                    company_id=company_id,
                    category_retention_days=dict(_DEFAULT_CATEGORY_RETENTION_DAYS),
                    max_entries_per_category=0,
                    enable_auto_cleanup=True,
                    cleanup_frequency_hours=24,
                )
                self._retention_policies[company_id] = default_policy
                return default_policy

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_retention_policy_error",
                company_id=company_id,
                error=str(exc),
            )
            return AuditRetentionPolicy(
                company_id=company_id,
                category_retention_days=dict(_DEFAULT_CATEGORY_RETENTION_DAYS),
            )

    def set_retention_policy(
        self,
        company_id: str,
        policy: AuditRetentionPolicy,
    ) -> AuditRetentionPolicy:
        """Update the retention policy for a company.

        Validates that the policy targets the correct company and
        stores it for future retention cleanups.

        Args:
            company_id: Tenant ID (BC-001).
            policy: The new retention policy to apply.

        Returns:
            The stored policy.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)

            if policy is None:
                raise AuditLogError(
                    error_code="INVALID_CATEGORY",
                    message="Policy cannot be None",
                    status_code=400,
                )

            # Ensure the policy's company_id matches
            if policy.company_id != company_id:
                raise AuditLogError(
                    error_code="INVALID_COMPANY_ID",
                    message=(
                        f"Policy company_id '{policy.company_id}' does not "
                        f"match requested company_id '{company_id}'"
                    ),
                    status_code=400,
                )

            # Validate retention days are positive integers
            for cat_key, days in policy.category_retention_days.items():
                if not isinstance(days, int) or days < 1:
                    raise AuditLogError(
                        error_code="INVALID_CATEGORY",
                        message=(
                            f"Retention days for category '{cat_key}' "
                            f"must be a positive integer, got {days}"
                        ),
                        status_code=400,
                    )

            with self._lock:
                self._retention_policies[company_id] = policy

            logger.info(
                "retention_policy_updated",
                company_id=company_id,
                category_count=len(policy.category_retention_days),
                auto_cleanup=policy.enable_auto_cleanup,
                cleanup_frequency_hours=policy.cleanup_frequency_hours,
            )

            return policy

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "set_retention_policy_error",
                company_id=company_id,
                error=str(exc),
            )
            # Return the existing policy as a safe fallback
            return self.get_retention_policy(company_id)

    def redact_sensitive_data(
        self,
        company_id: str,
        entry_id: str,
    ) -> bool:
        """Redact sensitive fields in an audit log entry.

        Masks values in old_value, new_value, and metadata where the
        field name matches the configured sensitive_fields list.
        The modification is applied in-place to the stored entry.

        Args:
            company_id: Tenant ID (BC-001).
            entry_id: ID of the entry to redact.

        Returns:
            True if the entry was found and redacted, False otherwise.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)

            if not entry_id or not str(entry_id).strip():
                raise AuditLogError(
                    error_code="ENTRY_NOT_FOUND",
                    message="entry_id is required and cannot be empty",
                    status_code=400,
                )

            with self._lock:
                entry = self._find_entry_by_id(company_id, entry_id)

                if entry is None:
                    logger.warning(
                        "redact_sensitive_data_entry_not_found",
                        company_id=company_id,
                        entry_id=entry_id,
                    )
                    return False

                # Redact old_value
                if entry.old_value:
                    entry.old_value = self._redact_if_sensitive(entry.old_value)

                # Redact new_value
                if entry.new_value:
                    entry.new_value = self._redact_if_sensitive(entry.new_value)

                # Redact metadata fields
                for sensitive_key in self.config.sensitive_fields:
                    if sensitive_key in entry.metadata:
                        val = entry.metadata[sensitive_key]
                        if isinstance(val, str):
                            entry.metadata[sensitive_key] = self._redact_field(val)
                        elif isinstance(val, dict):
                            for k, v in val.items():
                                if isinstance(v, str):
                                    val[k] = self._redact_field(v)

                # Recompute checksum after redaction to reflect the
                # new state as the canonical one
                entry_data = {
                    "entry_id": entry.entry_id,
                    "company_id": entry.company_id,
                    "category": entry.category.value,
                    "severity": entry.severity.value,
                    "action": entry.action,
                    "actor_id": entry.actor_id,
                    "actor_type": entry.actor_type,
                    "resource_type": entry.resource_type,
                    "resource_id": entry.resource_id,
                    "old_value": entry.old_value,
                    "new_value": entry.new_value,
                    "ip_address": entry.ip_address,
                    "metadata": entry.metadata,
                    "created_at": (
                        entry.created_at.isoformat() if entry.created_at else ""
                    ),
                }
                entry.checksum = self._compute_checksum(entry_data)

            logger.info(
                "sensitive_data_redacted",
                company_id=company_id,
                entry_id=entry_id,
                sensitive_fields=list(self.config.sensitive_fields),
            )

            return True

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "redact_sensitive_data_error",
                company_id=company_id,
                entry_id=entry_id,
                error=str(exc),
            )
            return False

    def get_alerts(self, company_id: str) -> List[Dict[str, Any]]:
        """Get security-related alerts for a company.

        Returns all stored alerts including failed login attempts,
        permission changes, integrity violations, and other
        security-relevant events.

        Args:
            company_id: Tenant ID (BC-001).

        Returns:
            List of alert dictionaries, newest first.

        Raises:
            AuditLogError: On validation failure.
        """
        try:
            _validate_company_id(company_id)

            with self._lock:
                alerts = list(self._alerts.get(company_id, []))

            # Return newest first
            alerts.sort(
                key=lambda a: a.get("created_at", ""),
                reverse=True,
            )

            logger.debug(
                "audit_alerts_retrieved",
                company_id=company_id,
                alert_count=len(alerts),
            )

            return alerts

        except ParwaBaseError:
            raise
        except Exception as exc:
            logger.error(
                "get_alerts_error",
                company_id=company_id,
                error=str(exc),
            )
            return []

    def reset(self, company_id: str = "") -> None:
        """Reset all in-memory state for testing.

        If ``company_id`` is provided, clears only that company's
        data.  If empty string, clears all companies' data.

        Args:
            company_id: Company to reset, or empty for global reset.
        """
        try:
            with self._lock:
                if company_id:
                    self._entries.pop(company_id, None)
                    self._retention_policies.pop(company_id, None)
                    self._alerts.pop(company_id, None)
                else:
                    self._entries.clear()
                    self._retention_policies.clear()
                    self._alerts.clear()

            logger.info(
                "audit_log_service_reset",
                company_id=company_id or "all",
            )

        except Exception as exc:
            logger.error(
                "reset_error",
                company_id=company_id,
                error=str(exc),
            )

    def is_healthy(self) -> bool:
        """Quick health check for the audit log service.

        Verifies that internal state structures are accessible and
        the threading lock is not deadlocked.

        Returns:
            True if the service appears healthy.
        """
        try:
            # Attempt to acquire and release the lock to detect deadlocks
            with self._lock:
                # Verify internal data structures are dict/list types
                assert isinstance(self._entries, dict)
                assert isinstance(self._retention_policies, dict)
                assert isinstance(self._alerts, dict)
                assert isinstance(self._stream_callbacks, list)
                assert isinstance(self.config, AuditLogConfig)
            return True
        except Exception as exc:
            logger.error(
                "audit_log_health_check_failed",
                error=str(exc),
            )
            return False
