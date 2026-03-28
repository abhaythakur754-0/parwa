"""
SOX Compliance Module.

Implements Sarbanes-Oxley Act compliance requirements for financial services.
Focuses on Section 404 (Internal Controls) and related provisions.

Key Requirements:
- Internal control documentation
- Audit trail for all financial transactions
- Segregation of duties
- Access controls and authorization
- Financial reporting accuracy
- Whistleblower protections

Reference: Sarbanes-Oxley Act of 2002 (Pub.L. 107-204)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class SOXSection(str, Enum):
    """SOX Act sections relevant to financial services support."""
    SECTION_302 = "302"  # Corporate Responsibility for Financial Reports
    SECTION_404 = "404"  # Management Assessment of Internal Controls
    SECTION_409 = "409"  # Real Time Issuer Disclosures
    SECTION_802 = "802"  # Criminal Penalties for Altering Documents
    SECTION_806 = "806"  # Whistleblower Protection
    SECTION_906 = "906"  # Corporate Responsibility for Financial Reports


class SOXViolationType(str, Enum):
    """Types of SOX violations."""
    MISSING_AUDIT_TRAIL = "missing_audit_trail"
    INSUFFICIENT_CONTROLS = "insufficient_controls"
    ACCESS_VIOLATION = "access_violation"
    DUTY_SEGREGATION = "duty_segregation"
    DOCUMENT_ALTERATION = "document_alteration"
    MISSING_APPROVAL = "missing_approval"
    DATA_INTEGRITY = "data_integrity"
    RETENTION_VIOLATION = "retention_violation"


class SOXSeverity(str, Enum):
    """Severity levels for SOX violations."""
    LOW = "low"  # Minor procedural issue
    MEDIUM = "medium"  # Control deficiency
    HIGH = "high"  # Material weakness
    CRITICAL = "critical"  # Potential fraud or major violation


@dataclass
class SOXViolation:
    """
    Represents a SOX compliance violation.

    Attributes:
        violation_type: Type of SOX violation
        severity: Severity level of the violation
        section: Related SOX section
        description: Human-readable description
        timestamp: When the violation occurred
        context: Additional context data
        remediation: Suggested remediation steps
    """
    violation_type: SOXViolationType
    severity: SOXSeverity
    section: SOXSection
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)
    remediation: Optional[str] = None
    violation_id: str = field(default="")

    def __post_init__(self):
        """Generate unique violation ID."""
        if not self.violation_id:
            hash_input = f"{self.violation_type.value}{self.timestamp.isoformat()}"
            self.violation_id = f"SOX-{hashlib.md5(hash_input.encode()).hexdigest()[:8].upper()}"


@dataclass
class AuditEntry:
    """
    SOX-compliant audit trail entry.

    Every significant action must create an audit entry with:
    - Who performed the action
    - What action was performed
    - When it occurred
    - Why it was performed (justification)
    - Integrity hash for tamper detection
    """
    action_type: str
    actor: str
    actor_role: str
    resource_type: str
    resource_id: str
    action_details: Dict[str, Any]
    justification: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    entry_hash: str = field(default="")

    def __post_init__(self):
        """Generate integrity hash for tamper detection."""
        if not self.entry_hash:
            hash_data = {
                "action_type": self.action_type,
                "actor": self.actor,
                "resource_id": self.resource_id,
                "timestamp": self.timestamp.isoformat(),
            }
            self.entry_hash = hashlib.sha256(
                json.dumps(hash_data, sort_keys=True).encode()
            ).hexdigest()


class SOXCompliance:
    """
    SOX Compliance checker and enforcer.

    Implements Sarbanes-Oxley Act compliance requirements:
    - Section 404: Internal control assessments
    - Section 802: Document retention and integrity
    - Audit trail generation and verification
    - Segregation of duties enforcement
    - Access control validation

    Usage:
        sox = SOXCompliance()

        # Check action compliance
        result = sox.check_action(
            action_type="refund_request",
            actor="user@example.com",
            amount=150.00
        )

        # Create audit entry
        entry = sox.create_audit_entry(
            action_type="refund_approved",
            actor="manager@example.com",
            resource_id="REF-123",
            justification="Customer complaint resolved"
        )
    """

    # Actions requiring audit trail per SOX
    AUDITABLE_ACTIONS = {
        "refund_request",
        "refund_approve",
        "refund_deny",
        "account_access",
        "data_export",
        "config_change",
        "user_permission_change",
        "financial_report_access",
        "transaction_view",
        "complaint_handle",
    }

    # Actions requiring segregation of duties
    DUTY_SEGREGATION_RULES = {
        "refund_approve": {
            "cannot_perform_if_did": ["refund_request"],
            "description": "Requester cannot approve own refund request",
        },
        "financial_report_access": {
            "cannot_perform_if_has_role": ["data_entry"],
            "description": "Data entry cannot access financial reports",
        },
    }

    def __init__(self):
        """Initialize SOX compliance checker."""
        self._audit_log: List[AuditEntry] = []
        self._violations: List[SOXViolation] = []
        self._action_history: Dict[str, List[str]] = {}  # user -> actions

    def check_action(
        self,
        action_type: str,
        actor: str,
        actor_role: str,
        resource_id: Optional[str] = None,
        amount: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check if an action is SOX compliant.

        Args:
            action_type: Type of action being performed
            actor: User performing the action
            actor_role: Role of the user
            resource_id: Resource being acted upon
            amount: Financial amount (if applicable)
            context: Additional context

        Returns:
            Dict with 'compliant' boolean and any 'violations'
        """
        violations = []
        compliant = True

        # Check segregation of duties
        sod_violation = self._check_duty_segregation(
            action_type, actor, actor_role
        )
        if sod_violation:
            violations.append(sod_violation)
            compliant = False

        # Check if action requires audit trail
        requires_audit = action_type in self.AUDITABLE_ACTIONS

        # Check approval requirements for financial actions
        if action_type in ["refund_approve", "refund_request"] and amount:
            if amount >= 100.0:  # Financial threshold
                approval_check = self._check_approval_requirements(
                    action_type, actor, amount
                )
                if not approval_check["valid"]:
                    violations.append(SOXViolation(
                        violation_type=SOXViolationType.MISSING_APPROVAL,
                        severity=SOXSeverity.HIGH,
                        section=SOXSection.SECTION_404,
                        description=approval_check["reason"],
                        context={"amount": amount, "actor": actor},
                        remediation="Obtain proper approval before processing",
                    ))
                    compliant = False

        result = {
            "compliant": compliant,
            "requires_audit": requires_audit,
            "violations": violations,
            "action_type": action_type,
            "actor": actor,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if violations:
            self._violations.extend(violations)
            logger.warning({
                "event": "sox_compliance_violation",
                "action_type": action_type,
                "actor": actor,
                "violations": [v.violation_type.value for v in violations],
            })

        # Track action history for segregation of duties checks
        # This is done AFTER the check so current action doesn't affect itself
        if actor not in self._action_history:
            self._action_history[actor] = []
        self._action_history[actor].append(action_type)

        return result

    def _check_duty_segregation(
        self,
        action_type: str,
        actor: str,
        actor_role: str
    ) -> Optional[SOXViolation]:
        """
        Check segregation of duties requirements.

        Per SOX Section 404, certain actions must be segregated
        to prevent fraud and errors.
        """
        if action_type not in self.DUTY_SEGREGATION_RULES:
            return None

        rules = self.DUTY_SEGREGATION_RULES[action_type]

        # Check if actor previously performed conflicting action
        if "cannot_perform_if_did" in rules:
            user_history = self._action_history.get(actor, [])
            for conflicting_action in rules["cannot_perform_if_did"]:
                if conflicting_action in user_history:
                    return SOXViolation(
                        violation_type=SOXViolationType.DUTY_SEGREGATION,
                        severity=SOXSeverity.HIGH,
                        section=SOXSection.SECTION_404,
                        description=f"Duty segregation violation: {rules['description']}",
                        context={
                            "actor": actor,
                            "conflicting_action": conflicting_action,
                        },
                        remediation="Assign to different user for approval",
                    )

        # Check role-based restrictions
        if "cannot_perform_if_has_role" in rules:
            if actor_role in rules["cannot_perform_if_has_role"]:
                return SOXViolation(
                    violation_type=SOXViolationType.ACCESS_VIOLATION,
                    severity=SOXSeverity.MEDIUM,
                    section=SOXSection.SECTION_404,
                    description=f"Role restriction: {rules['description']}",
                    context={"actor": actor, "role": actor_role},
                    remediation="Reassign to user with appropriate role",
                )

        return None

    def _check_approval_requirements(
        self,
        action_type: str,
        actor: str,
        amount: float
    ) -> Dict[str, Any]:
        """
        Check approval requirements for financial actions.

        Per SOX, significant financial transactions require
        documented approval.
        """
        # High-value transactions require dual approval
        if amount >= 500.0:
            return {
                "valid": False,
                "reason": f"Amount ${amount:.2f} requires dual approval",
                "requirement": "dual_approval",
            }

        # Standard approval required for amounts >= $100
        if amount >= 100.0:
            return {
                "valid": False,
                "reason": f"Amount ${amount:.2f} requires supervisor approval",
                "requirement": "single_approval",
            }

        return {"valid": True}

    def create_audit_entry(
        self,
        action_type: str,
        actor: str,
        actor_role: str,
        resource_type: str,
        resource_id: str,
        justification: str,
        action_details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """
        Create a SOX-compliant audit trail entry.

        Per SOX Section 802, all significant actions must be
        logged with tamper-proof audit trails.

        Args:
            action_type: Type of action performed
            actor: User who performed the action
            actor_role: Role of the user
            resource_type: Type of resource affected
            resource_id: ID of the resource
            justification: Business justification for the action
            action_details: Additional details about the action
            ip_address: IP address of the actor
            session_id: Session ID of the actor
            previous_state: State before the action
            new_state: State after the action

        Returns:
            AuditEntry with integrity hash
        """
        entry = AuditEntry(
            action_type=action_type,
            actor=actor,
            actor_role=actor_role,
            resource_type=resource_type,
            resource_id=resource_id,
            action_details=action_details or {},
            justification=justification,
            ip_address=ip_address,
            session_id=session_id,
            previous_state=previous_state,
            new_state=new_state,
        )

        self._audit_log.append(entry)

        # Track action history for segregation of duties
        if actor not in self._action_history:
            self._action_history[actor] = []
        self._action_history[actor].append(action_type)

        logger.info({
            "event": "sox_audit_entry_created",
            "action_type": action_type,
            "actor": actor,
            "resource_id": resource_id,
            "entry_hash": entry.entry_hash,
        })

        return entry

    def verify_audit_integrity(self) -> Dict[str, Any]:
        """
        Verify integrity of all audit entries.

        Recalculates hashes and checks for tampering.

        Returns:
            Dict with 'valid' boolean and any 'issues'
        """
        issues = []

        for entry in self._audit_log:
            hash_data = {
                "action_type": entry.action_type,
                "actor": entry.actor,
                "resource_id": entry.resource_id,
                "timestamp": entry.timestamp.isoformat(),
            }
            expected_hash = hashlib.sha256(
                json.dumps(hash_data, sort_keys=True).encode()
            ).hexdigest()

            if entry.entry_hash != expected_hash:
                issues.append({
                    "entry": entry.resource_id,
                    "issue": "hash_mismatch",
                    "severity": "critical",
                })

        return {
            "valid": len(issues) == 0,
            "entries_checked": len(self._audit_log),
            "issues": issues,
        }

    def get_violations(
        self,
        severity: Optional[SOXSeverity] = None
    ) -> List[SOXViolation]:
        """
        Get all SOX violations.

        Args:
            severity: Optional filter by severity level

        Returns:
            List of violations
        """
        if severity:
            return [v for v in self._violations if v.severity == severity]
        return self._violations.copy()

    def get_audit_log(
        self,
        actor: Optional[str] = None,
        action_type: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """
        Get audit log entries.

        Args:
            actor: Optional filter by actor
            action_type: Optional filter by action type
            limit: Maximum number of entries to return

        Returns:
            List of audit entries
        """
        entries = self._audit_log

        if actor:
            entries = [e for e in entries if e.actor == actor]
        if action_type:
            entries = [e for e in entries if e.action_type == action_type]

        return entries[-limit:]

    def get_compliance_summary(self) -> Dict[str, Any]:
        """
        Get SOX compliance summary.

        Returns:
            Summary of compliance status
        """
        violations_by_severity = {}
        for severity in SOXSeverity:
            violations_by_severity[severity.value] = len([
                v for v in self._violations if v.severity == severity
            ])

        return {
            "total_audit_entries": len(self._audit_log),
            "total_violations": len(self._violations),
            "violations_by_severity": violations_by_severity,
            "compliance_status": "compliant" if len(self._violations) == 0 else "non_compliant",
            "audit_integrity": self.verify_audit_integrity()["valid"],
        }
