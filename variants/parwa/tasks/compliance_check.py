"""
PARWA Junior Compliance Check Task.

Task for running compliance checks on actions and data.
Ensures all operations comply with regulations and policies.

PARWA Junior Features:
- GDPR compliance verification
- HIPAA checks for healthcare data
- TCPA compliance for communications
- Data retention policy enforcement
- Jurisdiction-based rule application
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from variants.parwa.config import ParwaConfig, get_parwa_config
from shared.core_functions.logger import get_logger
from shared.core_functions.compliance import mask_pii, generate_portability_report

logger = get_logger(__name__)


class ComplianceCheckType(Enum):
    """Types of compliance checks."""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    TCPA = "tcpa"
    DATA_RETENTION = "data_retention"
    JURISDICTION = "jurisdiction"
    ALL = "all"


class ComplianceStatus(Enum):
    """Status of compliance check."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    REQUIRES_REVIEW = "requires_review"
    ERROR = "error"


@dataclass
class ComplianceViolation:
    """Details of a compliance violation."""
    check_type: str
    severity: str  # low, medium, high, critical
    description: str
    remediation: Optional[str] = None
    reference: Optional[str] = None


@dataclass
class ComplianceCheckResult:
    """Result from compliance check task."""
    success: bool
    check_id: Optional[str] = None
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    check_types_run: List[str] = field(default_factory=list)
    violations: List[ComplianceViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    compliant: bool = True
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComplianceCheckTask:
    """
    Task for running compliance checks.

    This task runs various compliance checks to ensure operations
    comply with regulations and policies.

    Checks include:
    - GDPR: Data protection and privacy
    - HIPAA: Healthcare information protection
    - TCPA: Communication regulations
    - Data Retention: Policy enforcement
    - Jurisdiction: Location-based rules

    Example:
        task = ComplianceCheckTask()
        result = await task.execute({
            "check_type": "gdpr",
            "action": "data_export",
            "customer_id": "cust_123",
            "jurisdiction": "EU"
        })
    """

    def __init__(
        self,
        parwa_config: Optional[ParwaConfig] = None,
    ) -> None:
        """
        Initialize compliance check task.

        Args:
            parwa_config: PARWA Junior configuration
        """
        self._config = parwa_config or get_parwa_config()

    async def execute(self, input_data: Dict[str, Any]) -> ComplianceCheckResult:
        """
        Execute the compliance check task.

        Args:
            input_data: Dict with:
                - check_type: Type of check (gdpr, hipaa, tcpa, data_retention, jurisdiction, all)
                - action: Action being checked
                - customer_id: Customer identifier
                - jurisdiction: Customer jurisdiction
                - data_type: Type of data involved
                - phi_present: Whether PHI is present (for HIPAA)

        Returns:
            ComplianceCheckResult with check status
        """
        check_type_str = input_data.get("check_type", "all")
        action = input_data.get("action", "")
        customer_id = input_data.get("customer_id", "")
        jurisdiction = input_data.get("jurisdiction", "US")

        check_id = f"comp_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{customer_id}"

        logger.info({
            "event": "compliance_check_task_started",
            "check_id": check_id,
            "check_type": check_type_str,
            "action": action,
            "jurisdiction": jurisdiction,
        })

        violations: List[ComplianceViolation] = []
        warnings: List[str] = []
        check_types_run: List[str] = []

        try:
            # Determine which checks to run
            check_types = self._get_check_types(check_type_str)

            # Run each check
            for ct in check_types:
                check_types_run.append(ct.value)

                if ct == ComplianceCheckType.GDPR:
                    gdpr_violations = await self._check_gdpr(input_data)
                    violations.extend(gdpr_violations)

                elif ct == ComplianceCheckType.HIPAA:
                    hipaa_violations = await self._check_hipaa(input_data)
                    violations.extend(hipaa_violations)

                elif ct == ComplianceCheckType.TCPA:
                    tcpa_violations = await self._check_tcpa(input_data)
                    violations.extend(tcpa_violations)

                elif ct == ComplianceCheckType.DATA_RETENTION:
                    retention_violations = await self._check_data_retention(input_data)
                    violations.extend(retention_violations)

                elif ct == ComplianceCheckType.JURISDICTION:
                    jurisdiction_violations = await self._check_jurisdiction(input_data)
                    violations.extend(jurisdiction_violations)

            # Determine status
            if any(v.severity in ["high", "critical"] for v in violations):
                status = ComplianceStatus.NON_COMPLIANT
                compliant = False
            elif violations:
                status = ComplianceStatus.REQUIRES_REVIEW
                compliant = True  # Still compliant but needs review
            else:
                status = ComplianceStatus.COMPLIANT
                compliant = True

            # Build message
            if violations:
                message = f"Found {len(violations)} compliance issue(s)"
            else:
                message = "All compliance checks passed"

            result = ComplianceCheckResult(
                success=True,
                check_id=check_id,
                status=status,
                check_types_run=check_types_run,
                violations=violations,
                warnings=warnings,
                compliant=compliant,
                message=message,
                metadata={
                    "variant": "parwa",
                    "tier": "medium",
                    "jurisdiction": jurisdiction,
                    "action": action,
                },
            )

            logger.info({
                "event": "compliance_check_task_complete",
                "check_id": check_id,
                "status": status.value,
                "violations_count": len(violations),
                "compliant": compliant,
            })

            return result

        except Exception as e:
            logger.error({
                "event": "compliance_check_task_error",
                "check_id": check_id,
                "error": str(e),
            })
            return ComplianceCheckResult(
                success=False,
                check_id=check_id,
                status=ComplianceStatus.ERROR,
                message=f"Error running compliance check: {str(e)}",
                metadata={"error": str(e)},
            )

    def _get_check_types(self, check_type_str: str) -> List[ComplianceCheckType]:
        """Get list of check types to run."""
        if check_type_str == "all":
            return [
                ComplianceCheckType.GDPR,
                ComplianceCheckType.HIPAA,
                ComplianceCheckType.TCPA,
                ComplianceCheckType.DATA_RETENTION,
                ComplianceCheckType.JURISDICTION,
            ]
        try:
            return [ComplianceCheckType(check_type_str)]
        except ValueError:
            return [ComplianceCheckType.ALL]

    async def _check_gdpr(self, data: Dict[str, Any]) -> List[ComplianceViolation]:
        """Run GDPR compliance check."""
        violations = []
        jurisdiction = data.get("jurisdiction", "US")

        # Check if GDPR applies (EU jurisdiction)
        if jurisdiction in ["EU", "UK", "EEA"]:
            # Check for proper consent
            if not data.get("has_consent", True):
                violations.append(ComplianceViolation(
                    check_type="gdpr",
                    severity="high",
                    description="Missing required consent for data processing",
                    remediation="Obtain explicit consent before processing",
                    reference="GDPR Article 6",
                ))

            # Check for data minimization
            if data.get("excessive_data_collection", False):
                violations.append(ComplianceViolation(
                    check_type="gdpr",
                    severity="medium",
                    description="Data collection exceeds necessary scope",
                    remediation="Limit data collection to minimum required",
                    reference="GDPR Article 5(1)(c)",
                ))

            # Check for right to erasure capability
            if not data.get("erasure_capability", True):
                violations.append(ComplianceViolation(
                    check_type="gdpr",
                    severity="medium",
                    description="Right to erasure not properly implemented",
                    remediation="Implement data deletion workflow",
                    reference="GDPR Article 17",
                ))

        return violations

    async def _check_hipaa(self, data: Dict[str, Any]) -> List[ComplianceViolation]:
        """Run HIPAA compliance check."""
        violations = []
        phi_present = data.get("phi_present", False)

        if phi_present:
            # Check for BAA
            if not data.get("has_baa", False):
                violations.append(ComplianceViolation(
                    check_type="hipaa",
                    severity="critical",
                    description="PHI present without Business Associate Agreement",
                    remediation="Execute BAA before handling PHI",
                    reference="HIPAA 164.502",
                ))

            # Check for encryption
            if not data.get("encryption_enabled", True):
                violations.append(ComplianceViolation(
                    check_type="hipaa",
                    severity="high",
                    description="PHI transmitted without encryption",
                    remediation="Enable encryption for all PHI handling",
                    reference="HIPAA 164.312",
                ))

            # Check for audit logging
            if not data.get("audit_logging", True):
                violations.append(ComplianceViolation(
                    check_type="hipaa",
                    severity="medium",
                    description="PHI access not being audit logged",
                    remediation="Enable audit logging for PHI access",
                    reference="HIPAA 164.312(b)",
                ))

            # Check for PHI in logs
            if data.get("phi_in_logs", False):
                violations.append(ComplianceViolation(
                    check_type="hipaa",
                    severity="high",
                    description="PHI detected in log files",
                    remediation="Implement PHI scrubbing for logs",
                    reference="HIPAA 164.502",
                ))

        return violations

    async def _check_tcpa(self, data: Dict[str, Any]) -> List[ComplianceViolation]:
        """Run TCPA compliance check."""
        violations = []
        action = data.get("action", "")

        if action in ["sms", "voice_call", "auto_dial"]:
            # Check for consent
            if not data.get("tcpa_consent", True):
                violations.append(ComplianceViolation(
                    check_type="tcpa",
                    severity="high",
                    description="Communication initiated without TCPA consent",
                    remediation="Obtain prior express written consent",
                    reference="TCPA 47 USC 227",
                ))

            # Check time restrictions
            hour = datetime.now().hour
            if not (8 <= hour <= 21):
                violations.append(ComplianceViolation(
                    check_type="tcpa",
                    severity="medium",
                    description="Communication outside permitted hours (8am-9pm)",
                    remediation="Schedule communication during permitted hours",
                    reference="TCPA 47 CFR 64.1200",
                ))

            # Check for do-not-call list
            if data.get("on_dnc_list", False):
                violations.append(ComplianceViolation(
                    check_type="tcpa",
                    severity="high",
                    description="Contact is on do-not-call list",
                    remediation="Remove from contact list immediately",
                    reference="TCPA DNC Regulations",
                ))

        return violations

    async def _check_data_retention(self, data: Dict[str, Any]) -> List[ComplianceViolation]:
        """Run data retention compliance check."""
        violations = []
        data_age_days = data.get("data_age_days", 0)
        retention_limit_days = data.get("retention_limit_days", 365)

        if data_age_days > retention_limit_days:
            violations.append(ComplianceViolation(
                check_type="data_retention",
                severity="medium",
                description=f"Data retained beyond policy limit ({data_age_days} days vs {retention_limit_days} limit)",
                remediation="Initiate data deletion or archive process",
                reference="Data Retention Policy",
            ))

        # Check for expired data
        if data.get("data_expired", False):
            violations.append(ComplianceViolation(
                check_type="data_retention",
                severity="low",
                description="Data past retention period",
                remediation="Schedule for deletion",
                reference="Data Retention Policy",
            ))

        return violations

    async def _check_jurisdiction(self, data: Dict[str, Any]) -> List[ComplianceViolation]:
        """Run jurisdiction-based compliance check."""
        violations = []
        jurisdiction = data.get("jurisdiction", "US")

        # Check for jurisdiction-specific requirements
        if jurisdiction in ["EU", "UK", "EEA"] and not data.get("gdpr_compliant", True):
            violations.append(ComplianceViolation(
                check_type="jurisdiction",
                severity="high",
                description="EU jurisdiction requires GDPR compliance",
                remediation="Ensure GDPR compliance measures in place",
                reference="GDPR",
            ))

        if jurisdiction == "CA" and not data.get("ccpa_compliant", True):
            violations.append(ComplianceViolation(
                check_type="jurisdiction",
                severity="medium",
                description="California jurisdiction requires CCPA compliance",
                remediation="Ensure CCPA compliance measures in place",
                reference="CCPA",
            ))

        return violations

    def get_task_name(self) -> str:
        """Get task name."""
        return "compliance_check"

    def get_variant(self) -> str:
        """Get variant name."""
        return "parwa"

    def get_tier(self) -> str:
        """Get tier used."""
        return "medium"
