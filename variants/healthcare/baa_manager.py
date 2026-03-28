"""
BAA (Business Associate Agreement) Manager.
Week 33, Builder 3: Healthcare HIPAA + Logistics

Manages BAA lifecycle: creation, tracking, renewal, and compliance.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)


class BAAStatus(Enum):
    """BAA status enumeration."""
    DRAFT = "draft"
    PENDING_SIGNATURE = "pending_signature"
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    BREACHED = "breached"


class BAAType(Enum):
    """Types of Business Associate Agreements."""
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    SUBCONTRACTOR = "subcontractor"
    LIMITED = "limited"


@dataclass
class BAARecord:
    """Business Associate Agreement record."""
    baa_id: str
    client_id: str
    client_name: str
    status: BAAStatus
    baa_type: BAAType
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    signed_date: Optional[datetime] = None
    signed_by: Optional[str] = None
    terminated_date: Optional[datetime] = None
    termination_reason: Optional[str] = None
    permitted_uses: List[str] = field(default_factory=list)
    permitted_disclosures: List[str] = field(default_factory=list)
    security_safeguards: List[str] = field(default_factory=list)
    breach_notification_required: bool = True
    audit_rights: bool = True
    document_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'baa_id': self.baa_id,
            'client_id': self.client_id,
            'client_name': self.client_name,
            'status': self.status.value,
            'baa_type': self.baa_type.value,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'signed_date': self.signed_date.isoformat() if self.signed_date else None,
            'signed_by': self.signed_by,
            'terminated_date': self.terminated_date.isoformat() if self.terminated_date else None,
            'termination_reason': self.termination_reason,
            'permitted_uses': self.permitted_uses,
            'permitted_disclosures': self.permitted_disclosures,
            'security_safeguards': self.security_safeguards,
            'breach_notification_required': self.breach_notification_required,
            'audit_rights': self.audit_rights,
            'document_url': self.document_url,
            'metadata': self.metadata,
        }

    @property
    def is_valid(self) -> bool:
        """Check if BAA is valid."""
        if self.status != BAAStatus.ACTIVE and self.status != BAAStatus.EXPIRING_SOON:
            return False

        if self.expiry_date and datetime.utcnow() > self.expiry_date:
            return False

        return True

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Get days until expiry."""
        if not self.expiry_date:
            return None
        delta = self.expiry_date - datetime.utcnow()
        return max(0, delta.days)


class BAAManager:
    """
    Business Associate Agreement Manager.

    Manages the full lifecycle of BAAs including creation, tracking,
    renewal, and compliance monitoring.
    """

    # Standard BAA terms
    DEFAULT_TERM_YEARS = 3
    EXPIRY_WARNING_DAYS = 90
    RENEWAL_REMINDER_DAYS = 60

    # Standard permitted uses
    STANDARD_PERMITTED_USES = [
        "treatment",
        "payment",
        "healthcare_operations",
        "customer_support",
    ]

    # Standard security safeguards
    STANDARD_SAFEGUARDS = [
        "encryption_at_rest",
        "encryption_in_transit",
        "access_controls",
        "audit_logging",
        "incident_response",
        "workforce_training",
    ]

    def __init__(
        self,
        client_id: str,
        expiry_warning_days: int = EXPIRY_WARNING_DAYS,
        renewal_reminder_days: int = RENEWAL_REMINDER_DAYS,
    ):
        """
        Initialize BAA Manager.

        Args:
            client_id: Client identifier
            expiry_warning_days: Days before expiry to warn
            renewal_reminder_days: Days before expiry to remind
        """
        self.client_id = client_id
        self.expiry_warning_days = expiry_warning_days
        self.renewal_reminder_days = renewal_reminder_days

        # BAA storage
        self._baa_records: Dict[str, BAARecord] = {}

        # Metrics
        self._total_baas = 0
        self._active_baas = 0
        self._expired_baas = 0
        self._terminated_baas = 0

        logger.info({
            "event": "baa_manager_initialized",
            "client_id": client_id,
        })

    def create_baa(
        self,
        client_name: str,
        baa_type: BAAType = BAAType.STANDARD,
        term_years: int = DEFAULT_TERM_YEARS,
        permitted_uses: Optional[List[str]] = None,
        permitted_disclosures: Optional[List[str]] = None,
        security_safeguards: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BAARecord:
        """
        Create a new BAA record.

        Args:
            client_name: Name of the client
            baa_type: Type of BAA
            term_years: Term length in years
            permitted_uses: List of permitted uses
            permitted_disclosures: List of permitted disclosures
            security_safeguards: List of security safeguards
            metadata: Additional metadata

        Returns:
            Created BAA record
        """
        baa_id = f"BAA-{uuid4().hex[:8].upper()}"

        record = BAARecord(
            baa_id=baa_id,
            client_id=self.client_id,
            client_name=client_name,
            status=BAAStatus.DRAFT,
            baa_type=baa_type,
            permitted_uses=permitted_uses or self.STANDARD_PERMITTED_USES.copy(),
            permitted_disclosures=permitted_disclosures or [],
            security_safeguards=security_safeguards or self.STANDARD_SAFEGUARDS.copy(),
            metadata=metadata or {},
        )

        self._baa_records[baa_id] = record
        self._total_baas += 1

        logger.info({
            "event": "baa_created",
            "baa_id": baa_id,
            "client_name": client_name,
            "baa_type": baa_type.value,
        })

        return record

    def sign_baa(
        self,
        baa_id: str,
        signed_by: str,
        effective_date: Optional[datetime] = None,
        term_years: Optional[int] = None,
    ) -> BAARecord:
        """
        Sign a BAA, making it active.

        Args:
            baa_id: BAA identifier
            signed_by: Who signed the BAA
            effective_date: When BAA becomes effective
            term_years: Term length override

        Returns:
            Updated BAA record
        """
        if baa_id not in self._baa_records:
            raise ValueError(f"BAA {baa_id} not found")

        record = self._baa_records[baa_id]

        effective = effective_date or datetime.utcnow()
        term = term_years or self.DEFAULT_TERM_YEARS
        expiry = effective + timedelta(days=term * 365)

        record.status = BAAStatus.ACTIVE
        record.signed_date = datetime.utcnow()
        record.signed_by = signed_by
        record.effective_date = effective
        record.expiry_date = expiry

        self._active_baas += 1

        logger.info({
            "event": "baa_signed",
            "baa_id": baa_id,
            "signed_by": signed_by,
            "effective_date": effective.isoformat(),
            "expiry_date": expiry.isoformat(),
        })

        return record

    def verify_baa(self, baa_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify BAA status.

        Args:
            baa_id: Optional specific BAA to verify

        Returns:
            Verification result
        """
        if baa_id:
            if baa_id not in self._baa_records:
                return {
                    "valid": False,
                    "reason": "BAA not found",
                    "baa_id": baa_id,
                }

            record = self._baa_records[baa_id]
            return {
                "valid": record.is_valid,
                "baa_id": baa_id,
                "status": record.status.value,
                "days_until_expiry": record.days_until_expiry,
                "reason": None if record.is_valid else f"BAA status: {record.status.value}",
            }

        # Check for any active BAA
        active_baas = [b for b in self._baa_records.values() if b.is_valid]

        if not active_baas:
            return {
                "valid": False,
                "reason": "No active BAA on file",
                "baa_count": len(self._baa_records),
            }

        return {
            "valid": True,
            "baa_count": len(active_baas),
            "baa_ids": [b.baa_id for b in active_baas],
        }

    def check_expiry_warnings(self) -> List[Dict[str, Any]]:
        """
        Check for BAAs nearing expiry.

        Returns:
            List of warnings
        """
        warnings = []
        now = datetime.utcnow()

        for record in self._baa_records.values():
            if record.status != BAAStatus.ACTIVE:
                continue

            if not record.expiry_date:
                continue

            days_until = record.days_until_expiry

            if days_until is not None and days_until <= self.expiry_warning_days:
                warning_level = "critical" if days_until <= 30 else "warning"

                warnings.append({
                    "baa_id": record.baa_id,
                    "client_name": record.client_name,
                    "days_until_expiry": days_until,
                    "expiry_date": record.expiry_date.isoformat(),
                    "warning_level": warning_level,
                })

                # Update status if expiring soon
                if days_until <= self.expiry_warning_days:
                    record.status = BAAStatus.EXPIRING_SOON

        return warnings

    def renew_baa(
        self,
        baa_id: str,
        term_years: Optional[int] = None,
        new_permitted_uses: Optional[List[str]] = None,
    ) -> BAARecord:
        """
        Renew an existing BAA.

        Args:
            baa_id: BAA to renew
            term_years: New term length
            new_permitted_uses: Updated permitted uses

        Returns:
            Renewed BAA record
        """
        if baa_id not in self._baa_records:
            raise ValueError(f"BAA {baa_id} not found")

        record = self._baa_records[baa_id]

        # Create new BAA based on existing
        new_record = self.create_baa(
            client_name=record.client_name,
            baa_type=record.baa_type,
            term_years=term_years or self.DEFAULT_TERM_YEARS,
            permitted_uses=new_permitted_uses or record.permitted_uses,
            permitted_disclosures=record.permitted_disclosures,
            security_safeguards=record.security_safeguards,
        )

        # Immediately sign it
        self.sign_baa(
            new_record.baa_id,
            signed_by=record.signed_by or "system",
        )

        # Terminate old BAA
        self.terminate_baa(baa_id, f"Renewed as {new_record.baa_id}")

        logger.info({
            "event": "baa_renewed",
            "old_baa_id": baa_id,
            "new_baa_id": new_record.baa_id,
        })

        return new_record

    def terminate_baa(
        self,
        baa_id: str,
        reason: str,
    ) -> BAARecord:
        """
        Terminate a BAA.

        Args:
            baa_id: BAA to terminate
            reason: Reason for termination

        Returns:
            Terminated BAA record
        """
        if baa_id not in self._baa_records:
            raise ValueError(f"BAA {baa_id} not found")

        record = self._baa_records[baa_id]
        record.status = BAAStatus.TERMINATED
        record.terminated_date = datetime.utcnow()
        record.termination_reason = reason

        self._terminated_baas += 1
        if record.status == BAAStatus.ACTIVE:
            self._active_baas -= 1

        logger.warning({
            "event": "baa_terminated",
            "baa_id": baa_id,
            "reason": reason,
        })

        return record

    def report_breach(
        self,
        baa_id: str,
        breach_details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Report a breach related to a BAA.

        Args:
            baa_id: BAA identifier
            breach_details: Details of the breach

        Returns:
            Breach report
        """
        if baa_id not in self._baa_records:
            raise ValueError(f"BAA {baa_id} not found")

        record = self._baa_records[baa_id]
        record.status = BAAStatus.BREACHED

        breach_report = {
            "baa_id": baa_id,
            "client_id": self.client_id,
            "reported_at": datetime.utcnow().isoformat(),
            "breach_details": breach_details,
            "notification_required": record.breach_notification_required,
            "notification_deadline": (
                datetime.utcnow() + timedelta(hours=72)
            ).isoformat(),
        }

        logger.critical({
            "event": "baa_breach_reported",
            "baa_id": baa_id,
            "breach_details": breach_details,
        })

        return breach_report

    def get_baa(self, baa_id: str) -> Optional[BAARecord]:
        """Get BAA by ID."""
        return self._baa_records.get(baa_id)

    def list_baas(
        self,
        status: Optional[BAAStatus] = None,
    ) -> List[BAARecord]:
        """
        List BAAs, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            List of BAA records
        """
        records = list(self._baa_records.values())

        if status:
            records = [r for r in records if r.status == status]

        return records

    def get_stats(self) -> Dict[str, Any]:
        """Get BAA manager statistics."""
        return {
            "client_id": self.client_id,
            "total_baas": self._total_baas,
            "active_baas": sum(1 for b in self._baa_records.values() if b.is_valid),
            "expired_baas": sum(1 for b in self._baa_records.values() if b.status == BAAStatus.EXPIRED),
            "terminated_baas": sum(1 for b in self._baa_records.values() if b.status == BAAStatus.TERMINATED),
            "expiring_soon_count": len(self.check_expiry_warnings()),
        }
