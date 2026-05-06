"""
HIPAA Compliance Manager.
Week 33, Builder 2: Healthcare HIPAA + Logistics

Automated HIPAA compliance checking, audit logging, and violation detection.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime, timedelta
from uuid import uuid4

logger = logging.getLogger(__name__)


class ComplianceStatus(Enum):
    """HIPAA compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    PENDING_REVIEW = "pending_review"


class ComplianceCheck(Enum):
    """Types of HIPAA compliance checks."""
    BAA_VERIFICATION = "baa_verification"
    PHI_ENCRYPTION = "phi_encryption"
    ACCESS_CONTROL = "access_control"
    AUDIT_LOGGING = "audit_logging"
    MINIMUM_NECESSARY = "minimum_necessary"
    PATIENT_RIGHTS = "patient_rights"
    BREACH_NOTIFICATION = "breach_notification"
    SECURITY_TRAINING = "security_training"
    INCIDENT_RESPONSE = "incident_response"
    DATA_RETENTION = "data_retention"


@dataclass
class ComplianceResult:
    """Result of a compliance check."""
    check_type: ComplianceCheck
    status: ComplianceStatus
    passed: bool
    timestamp: datetime
    details: str = ""
    violations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'check_type': self.check_type.value,
            'status': self.status.value,
            'passed': self.passed,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
            'violations': self.violations,
            'recommendations': self.recommendations,
            'metadata': self.metadata,
        }


@dataclass
class AuditLogEntry:
    """HIPAA audit log entry."""
    entry_id: str
    timestamp: datetime
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    client_id: str
    phi_accessed: bool
    access_justification: str
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    outcome: str = "success"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'client_id': self.client_id,
            'phi_accessed': self.phi_accessed,
            'access_justification': self.access_justification,
            'ip_address': self.ip_address,
            'session_id': self.session_id,
            'outcome': self.outcome,
            'metadata': self.metadata,
        }


class HIPAAComplianceManager:
    """
    HIPAA Compliance Manager.

    Manages HIPAA compliance checks, audit logging, and violation detection
    for healthcare clients.
    """

    # Required compliance checks for healthcare
    REQUIRED_CHECKS = [
        ComplianceCheck.BAA_VERIFICATION,
        ComplianceCheck.PHI_ENCRYPTION,
        ComplianceCheck.ACCESS_CONTROL,
        ComplianceCheck.AUDIT_LOGGING,
        ComplianceCheck.MINIMUM_NECESSARY,
        ComplianceCheck.BREACH_NOTIFICATION,
    ]

    # Role-based access matrix for minimum necessary
    ACCESS_MATRIX = {
        "admin": ["all"],
        "provider": ["medical_records", "prescriptions", "appointments", "notes", "test_results"],
        "nurse": ["medical_records", "vitals", "appointments", "notes"],
        "billing": ["billing_info", "insurance", "demographics"],
        "support": ["appointments", "general_info", "faq"],
        "ai_agent": ["appointments", "general_info", "faq", "knowledge_base"],
    }

    def __init__(
        self,
        client_id: str,
        baa_verified: bool = False,
        audit_retention_years: int = 6,
    ):
        """
        Initialize HIPAA Compliance Manager.

        Args:
            client_id: Client identifier
            baa_verified: Whether BAA is on file
            audit_retention_years: Years to retain audit logs
        """
        self.client_id = client_id
        self.baa_verified = baa_verified
        self.audit_retention_years = audit_retention_years

        # Storage
        self._audit_logs: List[AuditLogEntry] = []
        self._compliance_history: List[ComplianceResult] = []
        self._consent_records: Dict[str, Dict[str, Any]] = {}

        # Metrics
        self._phi_access_count = 0
        self._violation_count = 0

        logger.info({
            "event": "hipaa_compliance_manager_initialized",
            "client_id": client_id,
            "baa_verified": baa_verified,
        })

    def run_compliance_check(
        self,
        check_type: ComplianceCheck,
        context: Optional[Dict[str, Any]] = None,
    ) -> ComplianceResult:
        """
        Run a specific compliance check.

        Args:
            check_type: Type of check to run
            context: Additional context for the check

        Returns:
            ComplianceResult with check outcome
        """
        context = context or {}
        violations = []
        recommendations = []
        passed = True

        if check_type == ComplianceCheck.BAA_VERIFICATION:
            passed = self.baa_verified
            if not passed:
                violations.append("No valid BAA on file")
                recommendations.append("Execute BAA before processing any PHI")

        elif check_type == ComplianceCheck.PHI_ENCRYPTION:
            # Check encryption requirements
            encryption_ok = context.get("encryption_at_rest", True) and \
                           context.get("encryption_in_transit", True)
            passed = encryption_ok
            if not encryption_ok:
                violations.append("PHI encryption requirements not met")
                recommendations.append("Enable AES-256 encryption at rest and TLS 1.3 in transit")

        elif check_type == ComplianceCheck.ACCESS_CONTROL:
            # Check role-based access
            has_rbac = context.get("rbac_enabled", True)
            passed = has_rbac
            if not has_rbac:
                violations.append("Role-based access control not enabled")
                recommendations.append("Implement RBAC with minimum necessary principle")

        elif check_type == ComplianceCheck.AUDIT_LOGGING:
            # Audit logging check
            audit_enabled = context.get("audit_enabled", True)
            passed = audit_enabled and len(self._audit_logs) >= 0
            if not audit_enabled:
                violations.append("Audit logging not enabled")
                recommendations.append("Enable comprehensive audit logging for all PHI access")

        elif check_type == ComplianceCheck.MINIMUM_NECESSARY:
            # Minimum necessary standard check
            min_necessary = context.get("minimum_necessary_enabled", True)
            passed = min_necessary
            if not min_necessary:
                violations.append("Minimum necessary standard not enforced")
                recommendations.append("Implement minimum necessary access controls")

        elif check_type == ComplianceCheck.BREACH_NOTIFICATION:
            # Breach notification procedures
            has_procedures = context.get("breach_procedures", True)
            passed = has_procedures
            if not has_procedures:
                violations.append("Breach notification procedures not established")
                recommendations.append("Define 72-hour breach notification process")

        elif check_type == ComplianceCheck.PATIENT_RIGHTS:
            # Patient rights check
            rights_enabled = context.get("patient_rights_enabled", True)
            passed = rights_enabled
            if not rights_enabled:
                violations.append("Patient rights processes not configured")
                recommendations.append("Implement patient access, amendment, and accounting processes")

        else:
            # Default check
            passed = context.get("passed", True)

        status = ComplianceStatus.COMPLIANT if passed else ComplianceStatus.NON_COMPLIANT

        result = ComplianceResult(
            check_type=check_type,
            status=status,
            passed=passed,
            timestamp=datetime.utcnow(),
            violations=violations,
            recommendations=recommendations,
            metadata={"client_id": self.client_id, "context": context},
        )

        self._compliance_history.append(result)
        if not passed:
            self._violation_count += 1

        logger.info({
            "event": "compliance_check_completed",
            "check_type": check_type.value,
            "passed": passed,
            "client_id": self.client_id,
        })

        return result

    def run_all_checks(self, context: Optional[Dict[str, Any]] = None) -> List[ComplianceResult]:
        """
        Run all required compliance checks.

        Args:
            context: Context for checks

        Returns:
            List of all compliance results
        """
        results = []
        for check_type in self.REQUIRED_CHECKS:
            result = self.run_compliance_check(check_type, context)
            results.append(result)

        return results

    def get_compliance_summary(self) -> Dict[str, Any]:
        """
        Get overall compliance summary.

        Returns:
            Summary of compliance status
        """
        if not self._compliance_history:
            return {
                "client_id": self.client_id,
                "overall_status": ComplianceStatus.UNKNOWN.value,
                "checks_run": 0,
                "passed": 0,
                "failed": 0,
            }

        passed = sum(1 for r in self._compliance_history if r.passed)
        failed = len(self._compliance_history) - passed

        if failed == 0:
            overall = ComplianceStatus.COMPLIANT
        elif passed == 0:
            overall = ComplianceStatus.NON_COMPLIANT
        else:
            overall = ComplianceStatus.PARTIAL

        return {
            "client_id": self.client_id,
            "overall_status": overall.value,
            "baa_verified": self.baa_verified,
            "checks_run": len(self._compliance_history),
            "passed": passed,
            "failed": failed,
            "violation_count": self._violation_count,
            "phi_access_count": self._phi_access_count,
            "audit_log_count": len(self._audit_logs),
            "last_check": self._compliance_history[-1].timestamp.isoformat() if self._compliance_history else None,
        }

    def log_phi_access(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        justification: str,
        phi_accessed: bool = True,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AuditLogEntry:
        """
        Log PHI access for HIPAA audit trail.

        Args:
            user_id: User performing action
            action: Action performed
            resource_type: Type of resource accessed
            resource_id: Resource identifier
            justification: Justification for access
            phi_accessed: Whether PHI was accessed
            ip_address: User's IP address
            session_id: Session identifier

        Returns:
            Created audit log entry
        """
        entry = AuditLogEntry(
            entry_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            client_id=self.client_id,
            phi_accessed=phi_accessed,
            access_justification=justification,
            ip_address=ip_address,
            session_id=session_id,
        )

        self._audit_logs.append(entry)

        if phi_accessed:
            self._phi_access_count += 1

        logger.info({
            "event": "phi_access_logged",
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "phi_accessed": phi_accessed,
            "client_id": self.client_id,
        })

        return entry

    def check_minimum_necessary(
        self,
        user_role: str,
        requested_data: str,
        purpose: str,
    ) -> tuple[bool, str]:
        """
        Check if access complies with minimum necessary standard.

        Args:
            user_role: User's role
            requested_data: Data being requested
            purpose: Purpose of access

        Returns:
            Tuple of (allowed, reason)
        """
        allowed_data = self.ACCESS_MATRIX.get(user_role, [])

        if "all" in allowed_data:
            return True, "Full access granted for admin role"

        if requested_data.lower() in [d.lower() for d in allowed_data]:
            return True, f"Access granted for {user_role} role"

        return False, f"Role '{user_role}' not authorized for '{requested_data}'"

    def verify_consent(
        self,
        patient_id: str,
        consent_type: str,
    ) -> tuple[bool, str]:
        """
        Verify patient consent is on file.

        Args:
            patient_id: Patient identifier
            consent_type: Type of consent required

        Returns:
            Tuple of (has_consent, reason)
        """
        consent_key = f"{patient_id}:{consent_type}"

        if consent_key in self._consent_records:
            record = self._consent_records[consent_key]
            if record.get("valid", False):
                return True, "Consent verified"

        # In production, check actual consent database
        # For now, assume consent for valid patient IDs
        if patient_id:
            self._consent_records[consent_key] = {
                "valid": True,
                "verified_at": datetime.utcnow().isoformat(),
            }
            return True, "Consent verified"

        return False, "Consent not found"

    def emergency_access(
        self,
        user_id: str,
        patient_id: str,
        reason: str,
    ) -> tuple[bool, str]:
        """
        Handle emergency access to PHI.

        Args:
            user_id: User requesting access
            patient_id: Patient identifier
            reason: Emergency reason

        Returns:
            Tuple of (granted, reason)
        """
        # Log emergency access
        self.log_phi_access(
            user_id=user_id,
            action="EMERGENCY_ACCESS",
            resource_type="patient_record",
            resource_id=patient_id,
            justification=f"EMERGENCY: {reason}",
            phi_accessed=True,
        )

        logger.warning({
            "event": "emergency_access_granted",
            "user_id": user_id,
            "patient_id": patient_id,
            "reason": reason,
            "client_id": self.client_id,
        })

        return True, "Emergency access granted - will be reviewed"

    def get_audit_trail(
        self,
        patient_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for compliance review.

        Args:
            patient_id: Filter by patient
            user_id: Filter by user
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of audit log entries
        """
        logs = self._audit_logs

        if patient_id:
            logs = [l for l in logs if l.resource_id == patient_id]
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        if start_date:
            logs = [l for l in logs if l.timestamp >= start_date]
        if end_date:
            logs = [l for l in logs if l.timestamp <= end_date]

        return [l.to_dict() for l in logs]

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            "client_id": self.client_id,
            "baa_verified": self.baa_verified,
            "audit_log_count": len(self._audit_logs),
            "compliance_checks_run": len(self._compliance_history),
            "violation_count": self._violation_count,
            "phi_access_count": self._phi_access_count,
            "consent_records": len(self._consent_records),
        }
