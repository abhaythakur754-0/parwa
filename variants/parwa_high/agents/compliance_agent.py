"""
PARWA High Compliance Agent.

HIPAA compliance enforcement agent with BAA verification.
CRITICAL: PHI must NEVER be logged. BAA enforcement for healthcare clients.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field

from variants.base_agents.base_agent import BaseAgent, AgentResponse
from shared.compliance.healthcare_guard import (
    HealthcareGuard,
    BAAStatus,
    PHIType,
    AccessPurpose,
    HealthcareClientType,
    get_healthcare_guard,
)
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class ComplianceLevel(str, Enum):
    """Compliance level enumeration."""
    HIPAA = "hipaa"
    GDPR = "gdpr"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    GENERAL = "general"


class ComplianceStatus(str, Enum):
    """Compliance check status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED = "blocked"


@dataclass
class ComplianceCheckResult:
    """Result of a compliance check."""
    check_id: str
    compliance_level: ComplianceLevel
    status: ComplianceStatus
    is_compliant: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    phi_detected: bool = False
    phi_types: List[str] = field(default_factory=list)
    baa_valid: bool = False
    audit_logged: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ParwaHighComplianceAgent(BaseAgent):
    """
    PARWA High Compliance Agent.

    Provides compliance enforcement capabilities including:
    - HIPAA compliance checking
    - BAA (Business Associate Agreement) verification
    - PHI access auditing
    - Compliance violation tracking

    CRITICAL: PHI must NEVER be logged.
    CRITICAL: BAA enforcement for healthcare clients.
    """

    # PARWA High specific settings
    PARWA_HIGH_ESCALATION_THRESHOLD = 0.50

    def __init__(
        self,
        agent_id: str,
        config: Optional[Dict[str, Any]] = None,
        company_id: Optional[UUID] = None,
        healthcare_guard: Optional[HealthcareGuard] = None,
    ) -> None:
        """
        Initialize PARWA High Compliance Agent.

        Args:
            agent_id: Unique identifier for this agent
            config: Agent configuration dictionary
            company_id: UUID of the company
            healthcare_guard: Optional HealthcareGuard instance
        """
        super().__init__(agent_id, config, company_id)

        self._healthcare_guard = healthcare_guard or get_healthcare_guard()
        self._compliance_checks: Dict[str, ComplianceCheckResult] = {}
        self._violation_log: List[Dict[str, Any]] = []

        logger.info({
            "event": "parwa_high_compliance_agent_initialized",
            "agent_id": agent_id,
            "tier": self.get_tier(),
            "variant": self.get_variant(),
        })

    def get_tier(self) -> str:
        """Get the AI tier for this agent. PARWA High uses 'heavy'."""
        return "heavy"

    def get_variant(self) -> str:
        """Get the PARWA High variant for this agent."""
        return "parwa_high"

    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Process compliance request.

        Args:
            input_data: Must contain 'action' key
                - 'check_hipaa': Check HIPAA compliance
                - 'enforce_baa': Enforce BAA requirement
                - 'audit_phi_access': Audit PHI access
                - 'check_compliance': General compliance check
                - 'get_violations': Get violation log

        Returns:
            AgentResponse with processing result
        """
        action = input_data.get("action")

        if not action:
            return AgentResponse(
                success=False,
                message="Missing required field: action",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        self.log_action("parwa_high_compliance_process", {
            "action": action,
            "tier": self.get_tier(),
        })

        if action == "check_hipaa":
            return await self._handle_check_hipaa(input_data)
        elif action == "enforce_baa":
            return await self._handle_enforce_baa(input_data)
        elif action == "audit_phi_access":
            return await self._handle_audit_phi_access(input_data)
        elif action == "check_compliance":
            return await self._handle_check_compliance(input_data)
        elif action == "get_violations":
            return await self._handle_get_violations()
        else:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

    async def check_hipaa(
        self,
        data: Dict[str, Any],
        client_id: str,
        purpose: str = "healthcare_operations"
    ) -> Dict[str, Any]:
        """
        Check HIPAA compliance for data.

        CRITICAL: PHI must NEVER be logged.

        Args:
            data: Data to check
            client_id: Client identifier
            purpose: Access purpose

        Returns:
            Dict with compliance check result
        """
        check_id = f"HIPAA-{datetime.now().strftime('%Y%m%d%H%M%S')}-{client_id[:8]}"

        # Map purpose string to enum
        purpose_map = {
            "treatment": AccessPurpose.TREATMENT,
            "payment": AccessPurpose.PAYMENT,
            "healthcare_operations": AccessPurpose.HEALTHCARE_OPERATIONS,
            "patient_request": AccessPurpose.PATIENT_REQUEST,
            "legal_requirement": AccessPurpose.LEGAL_REQUIREMENT,
            "emergency": AccessPurpose.EMERGENCY,
        }
        access_purpose = purpose_map.get(purpose, AccessPurpose.HEALTHCARE_OPERATIONS)

        # Perform PHI check using healthcare guard
        phi_result = self._healthcare_guard.check_phi_access(
            client_id=client_id,
            data=data,
            purpose=access_purpose,
        )

        # Determine violations
        violations = []
        if not phi_result.access_granted:
            violations.extend(phi_result.violations)

        # Determine status
        if phi_result.access_granted and not violations:
            status = ComplianceStatus.COMPLIANT
        elif phi_result.access_granted and violations:
            status = ComplianceStatus.REQUIRES_REVIEW
        else:
            status = ComplianceStatus.BLOCKED

        result = ComplianceCheckResult(
            check_id=check_id,
            compliance_level=ComplianceLevel.HIPAA,
            status=status,
            is_compliant=status == ComplianceStatus.COMPLIANT,
            violations=violations,
            warnings=phi_result.warnings,
            phi_detected=phi_result.phi_detected,
            phi_types=[t.value for t in phi_result.phi_types_found],
            baa_valid=phi_result.baa_status == BAAStatus.ACTIVE,
            audit_logged=phi_result.audit_logged,
        )

        self._compliance_checks[check_id] = result

        # Log compliance check (NEVER log actual PHI)
        self.log_action("parwa_high_hipaa_check", {
            "check_id": check_id,
            "client_id": client_id,
            "status": status.value,
            "phi_detected": phi_result.phi_detected,
            # CRITICAL: Never log actual PHI data
        })

        return {
            "check_id": check_id,
            "is_compliant": result.is_compliant,
            "status": status.value,
            "violations": violations,
            "warnings": phi_result.warnings,
            "phi_detected": result.phi_detected,
            "phi_types": result.phi_types,
            "baa_valid": result.baa_valid,
        }

    async def enforce_baa(self, company_id: str) -> Dict[str, Any]:
        """
        Enforce BAA requirement for a company.

        Args:
            company_id: Company identifier

        Returns:
            Dict with BAA enforcement result
        """
        baa_check = self._healthcare_guard.verify_baa(company_id)

        result = {
            "company_id": company_id,
            "baa_valid": baa_check.get("valid", False),
            "baa_status": baa_check.get("status", BAAStatus.NOT_REQUIRED).value
            if isinstance(baa_check.get("status"), BAAStatus)
            else baa_check.get("status", "unknown"),
            "reason": baa_check.get("reason", ""),
        }

        if not result["baa_valid"]:
            result["action_required"] = "BAA must be signed before PHI access"
            self._log_violation(
                company_id=company_id,
                violation_type="baa_not_valid",
                details=result,
            )

        self.log_action("parwa_high_baa_enforcement", {
            "company_id": company_id,
            "baa_valid": result["baa_valid"],
            "status": result["baa_status"],
        })

        return result

    async def audit_phi_access(
        self,
        user_id: str,
        company_id: str,
        access_type: str = "read"
    ) -> Dict[str, Any]:
        """
        Audit PHI access for a user.

        Args:
            user_id: User identifier
            company_id: Company identifier
            access_type: Type of access (read, write, delete)

        Returns:
            Dict with audit result
        """
        audit_id = f"AUDIT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{user_id[:8]}"

        audit_result = {
            "audit_id": audit_id,
            "user_id": user_id,
            "company_id": company_id,
            "access_type": access_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "baa_verified": False,
            "access_logged": True,
        }

        # Verify BAA
        baa_check = self._healthcare_guard.verify_baa(company_id)
        audit_result["baa_verified"] = baa_check.get("valid", False)

        # Log audit (NEVER include actual PHI)
        self.log_action("parwa_high_phi_access_audit", {
            "audit_id": audit_id,
            "user_id": user_id,
            "company_id": company_id,
            "access_type": access_type,
            "baa_verified": audit_result["baa_verified"],
        })

        return audit_result

    async def _handle_check_hipaa(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle check_hipaa action."""
        data = input_data.get("data")
        client_id = input_data.get("client_id")

        if not data or not client_id:
            return AgentResponse(
                success=False,
                message="Missing required fields: data, client_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.check_hipaa(
            data=data,
            client_id=client_id,
            purpose=input_data.get("purpose", "healthcare_operations"),
        )

        return AgentResponse(
            success=result["is_compliant"],
            message=f"HIPAA check: {result['status']}",
            data=result,
            confidence=0.95,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_enforce_baa(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle enforce_baa action."""
        company_id = input_data.get("company_id")

        if not company_id:
            return AgentResponse(
                success=False,
                message="Missing required field: company_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.enforce_baa(company_id)

        return AgentResponse(
            success=result["baa_valid"],
            message=f"BAA enforcement for {company_id}: {'Valid' if result['baa_valid'] else 'Invalid'}",
            data=result,
            confidence=0.95,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_audit_phi_access(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle audit_phi_access action."""
        user_id = input_data.get("user_id")
        company_id = input_data.get("company_id")

        if not user_id or not company_id:
            return AgentResponse(
                success=False,
                message="Missing required fields: user_id, company_id",
                tier_used=self.get_tier(),
                variant=self.get_variant(),
            )

        result = await self.audit_phi_access(
            user_id=user_id,
            company_id=company_id,
            access_type=input_data.get("access_type", "read"),
        )

        return AgentResponse(
            success=True,
            message=f"PHI access audited for user {user_id}",
            data=result,
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_check_compliance(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Handle general compliance check."""
        compliance_level = input_data.get("compliance_level", "general")
        data = input_data.get("data", {})
        client_id = input_data.get("client_id", "unknown")

        check_id = f"COMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Perform basic compliance check
        violations = []
        warnings = []

        # Check for sensitive data patterns
        if compliance_level in ["hipaa", "pci_dss"]:
            phi_types = self._healthcare_guard.detect_phi_in_text(str(data))
            if phi_types:
                warnings.append(f"Potential sensitive data detected: {[t.value for t in phi_types]}")

        result = ComplianceCheckResult(
            check_id=check_id,
            compliance_level=ComplianceLevel(compliance_level),
            status=ComplianceStatus.COMPLIANT if not violations else ComplianceStatus.NON_COMPLIANT,
            is_compliant=len(violations) == 0,
            violations=violations,
            warnings=warnings,
        )

        self._compliance_checks[check_id] = result

        return AgentResponse(
            success=result.is_compliant,
            message=f"Compliance check ({compliance_level}): {result.status.value}",
            data={
                "check_id": check_id,
                "is_compliant": result.is_compliant,
                "status": result.status.value,
                "violations": violations,
                "warnings": warnings,
            },
            confidence=0.90,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    async def _handle_get_violations(self) -> AgentResponse:
        """Handle get_violations action."""
        return AgentResponse(
            success=True,
            message=f"Found {len(self._violation_log)} compliance violations",
            data={
                "violations": self._violation_log,
                "total_checks": len(self._compliance_checks),
                "variant": self.get_variant(),
                "tier": self.get_tier(),
            },
            confidence=1.0,
            tier_used=self.get_tier(),
            variant=self.get_variant(),
        )

    def _log_violation(
        self,
        company_id: str,
        violation_type: str,
        details: Dict[str, Any]
    ) -> None:
        """Log a compliance violation."""
        violation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company_id": company_id,
            "violation_type": violation_type,
            "details": details,
        }
        self._violation_log.append(violation)

        logger.warning({
            "event": "parwa_high_compliance_violation",
            "company_id": company_id,
            "violation_type": violation_type,
        })
