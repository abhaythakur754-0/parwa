"""
Compliance Agent for Financial Services.

Provides real-time compliance monitoring for financial services:
- Regulatory requirement checks
- Suspicious activity flagging
- Audit trail generation
- Compliance violation alerts

CRITICAL: All compliance checks must pass before financial actions.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)
from variants.financial_services.compliance.sox_compliance import (
    SOXCompliance,
    SOXViolation,
    SOXSeverity,
    SOXViolationType,
    SOXSection,
)
from variants.financial_services.compliance.finra_rules import (
    FINRARules,
    FINRAViolation,
    FINRASeverity,
)

logger = logging.getLogger(__name__)


class ComplianceCheckType(str, Enum):
    """Types of compliance checks."""
    PRE_TRANSACTION = "pre_transaction"
    POST_TRANSACTION = "post_transaction"
    PERIODIC_REVIEW = "periodic_review"
    CUSTOMER_VERIFICATION = "customer_verification"
    AML_CHECK = "aml_check"
    SUITABILITY_CHECK = "suitability_check"
    PII_HANDLING = "pii_handling"
    AUDIT_TRAIL = "audit_trail"


class ComplianceStatus(str, Enum):
    """Compliance check status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    PENDING = "pending"
    REQUIRES_REVIEW = "requires_review"


@dataclass
class ComplianceCheckResult:
    """Result of a compliance check."""
    check_type: ComplianceCheckType
    status: ComplianceStatus
    passed: bool
    violations: List[Any] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    audit_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class ComplianceAgent:
    """
    Agent for real-time compliance monitoring in financial services.

    Features:
    - Real-time compliance monitoring
    - SOX compliance checks
    - FINRA rule enforcement
    - Suspicious activity detection
    - Audit trail generation
    - Compliance violation alerts

    Regulatory Coverage:
    - SOX (Sarbanes-Oxley Act)
    - FINRA Rules
    - AML (Anti-Money Laundering)
    - KYC (Know Your Customer)
    - GLBA (Gramm-Leach-Bliley Act)
    """

    def __init__(
        self,
        config: Optional[FinancialServicesConfig] = None
    ):
        """
        Initialize compliance agent.

        Args:
            config: Financial services configuration
        """
        self.config = config or get_financial_services_config()
        self.sox = SOXCompliance() if self.config.sox_compliance_enabled else None
        self.finra = FINRARules() if self.config.finra_compliance_enabled else None
        self._audit_log: List[Dict[str, Any]] = []
        self._violations: List[Any] = []

    def check_pre_transaction(
        self,
        transaction_type: str,
        customer_id: str,
        amount: float,
        actor: str,
        actor_role: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ComplianceCheckResult:
        """
        Perform pre-transaction compliance check.

        All transactions must pass this check before execution.

        Args:
            transaction_type: Type of transaction
            customer_id: Customer identifier
            amount: Transaction amount
            actor: User initiating transaction
            actor_role: Role of the user
            context: Additional context

        Returns:
            ComplianceCheckResult with pass/fail status
        """
        audit_id = self._create_audit_entry(
            action="pre_transaction_compliance_check",
            actor=actor,
            customer_id=customer_id,
            metadata={"transaction_type": transaction_type, "amount": amount}
        )

        violations = []
        warnings = []
        recommendations = []

        # SOX compliance check
        if self.sox:
            sox_result = self.sox.check_action(
                action_type=transaction_type,
                actor=actor,
                actor_role=actor_role,
                amount=amount
            )
            if not sox_result.get("compliant", True):
                violations.extend(sox_result.get("violations", []))

        # Amount threshold check
        if amount >= self.config.approval_threshold:
            recommendations.append(
                f"Transaction amount ${amount:.2f} requires supervisor approval"
            )

        if amount >= self.config.dual_approval_threshold:
            recommendations.append(
                f"Transaction amount ${amount:.2f} requires dual approval"
            )

        # AML check for large amounts
        if amount >= 10000:
            warnings.append("Large transaction - AML review may be required")

        # Customer verification check
        if context and not context.get("customer_verified"):
            warnings.append("Customer identity verification pending")

        passed = len(violations) == 0
        status = ComplianceStatus.PASSED if passed else ComplianceStatus.FAILED

        if warnings:
            status = ComplianceStatus.WARNING if passed else status

        result = ComplianceCheckResult(
            check_type=ComplianceCheckType.PRE_TRANSACTION,
            status=status,
            passed=passed,
            violations=violations,
            warnings=warnings,
            recommendations=recommendations,
            audit_id=audit_id
        )

        if violations:
            self._violations.extend(violations)
            logger.warning({
                "event": "compliance_violation_pre_transaction",
                "transaction_type": transaction_type,
                "customer_id": customer_id,
                "amount": amount,
                "actor": actor,
                "violations_count": len(violations),
                "audit_id": audit_id,
            })
        else:
            logger.info({
                "event": "compliance_check_passed",
                "transaction_type": transaction_type,
                "customer_id": customer_id,
                "amount": amount,
                "actor": actor,
                "audit_id": audit_id,
            })

        return result

    def check_post_transaction(
        self,
        transaction_id: str,
        transaction_type: str,
        customer_id: str,
        amount: float,
        actor: str
    ) -> ComplianceCheckResult:
        """
        Perform post-transaction compliance verification.

        Args:
            transaction_id: Completed transaction ID
            transaction_type: Type of transaction
            customer_id: Customer identifier
            amount: Transaction amount
            actor: User who performed transaction

        Returns:
            ComplianceCheckResult
        """
        audit_id = self._create_audit_entry(
            action="post_transaction_compliance_check",
            actor=actor,
            customer_id=customer_id,
            transaction_id=transaction_id,
            metadata={"transaction_type": transaction_type, "amount": amount}
        )

        violations = []
        warnings = []

        # Verify audit trail exists
        if self.sox:
            audit_entries = self.sox.get_audit_log(actor=actor, limit=1)
            if not audit_entries:
                violations.append("Missing audit trail for transaction")
                if self.sox:
                    self.sox._violations.append(SOXViolation(
                        violation_type=SOXViolationType.MISSING_AUDIT_TRAIL,
                        severity=SOXSeverity.HIGH,
                        section=SOXSection.SECTION_404,
                        description="No audit trail found for transaction",
                        context={"transaction_id": transaction_id}
                    ))

        passed = len(violations) == 0
        status = ComplianceStatus.PASSED if passed else ComplianceStatus.FAILED

        result = ComplianceCheckResult(
            check_type=ComplianceCheckType.POST_TRANSACTION,
            status=status,
            passed=passed,
            violations=violations,
            warnings=warnings,
            audit_id=audit_id
        )

        logger.info({
            "event": "post_transaction_compliance_check",
            "transaction_id": transaction_id,
            "customer_id": customer_id,
            "passed": passed,
            "audit_id": audit_id,
        })

        return result

    def check_suitability(
        self,
        customer_id: str,
        recommendation: str,
        product_type: str,
        customer_profile: Dict[str, Any],
        actor: str
    ) -> ComplianceCheckResult:
        """
        Check recommendation suitability per FINRA Rule 2111.

        Args:
            customer_id: Customer identifier
            recommendation: Recommendation made
            product_type: Product recommended
            customer_profile: Customer investment profile
            actor: User making recommendation

        Returns:
            ComplianceCheckResult
        """
        audit_id = self._create_audit_entry(
            action="suitability_check",
            actor=actor,
            customer_id=customer_id,
            metadata={"recommendation": recommendation, "product": product_type}
        )

        violations = []
        warnings = []

        if self.finra:
            result = self.finra.check_suitability(
                recommendation=recommendation,
                customer_profile=customer_profile,
                product_type=product_type
            )

            if not result.get("suitable", True):
                violations.extend(result.get("issues", []))

        passed = len(violations) == 0
        status = ComplianceStatus.PASSED if passed else ComplianceStatus.FAILED

        return ComplianceCheckResult(
            check_type=ComplianceCheckType.SUITABILITY_CHECK,
            status=status,
            passed=passed,
            violations=violations,
            warnings=warnings,
            audit_id=audit_id
        )

    def check_aml(
        self,
        customer_id: str,
        transaction_amount: float,
        transaction_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ComplianceCheckResult:
        """
        Perform AML (Anti-Money Laundering) check.

        Args:
            customer_id: Customer identifier
            transaction_amount: Transaction amount
            transaction_type: Type of transaction
            context: Additional context

        Returns:
            ComplianceCheckResult
        """
        audit_id = self._create_audit_entry(
            action="aml_check",
            actor="system",
            customer_id=customer_id,
            metadata={"amount": transaction_amount, "type": transaction_type}
        )

        violations = []
        warnings = []

        # Check for suspicious patterns
        if transaction_amount >= 10000:
            warnings.append("Large transaction - enhanced due diligence required")

        if transaction_amount >= 50000:
            warnings.append("Very large transaction - senior review required")

        # Pattern checks (simplified)
        if context:
            # Check for structuring (multiple small transactions)
            if context.get("recent_transactions_count", 0) > 5:
                recent_total = context.get("recent_transactions_total", 0)
                if recent_total >= 9000 and transaction_amount < 10000:
                    warnings.append("Possible structuring pattern detected")

            # Check for unusual timing
            if context.get("off_hours", False):
                warnings.append("Transaction outside normal hours")

        passed = len(violations) == 0
        status = ComplianceStatus.PASSED if passed else ComplianceStatus.FAILED

        if warnings:
            status = ComplianceStatus.WARNING if passed else status

        return ComplianceCheckResult(
            check_type=ComplianceCheckType.AML_CHECK,
            status=status,
            passed=passed,
            violations=violations,
            warnings=warnings,
            audit_id=audit_id
        )

    def flag_suspicious_activity(
        self,
        customer_id: str,
        activity_type: str,
        details: Dict[str, Any],
        severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Flag suspicious activity for review.

        Args:
            customer_id: Customer identifier
            activity_type: Type of suspicious activity
            details: Activity details
            severity: Severity level (low, medium, high, critical)

        Returns:
            Dict with flag result
        """
        audit_id = self._create_audit_entry(
            action="suspicious_activity_flagged",
            actor="compliance_agent",
            customer_id=customer_id,
            metadata={"activity_type": activity_type, "severity": severity}
        )

        flag_id = f"FLAG-{audit_id[-8:]}"

        logger.warning({
            "event": "suspicious_activity_flagged",
            "flag_id": flag_id,
            "customer_id": customer_id,
            "activity_type": activity_type,
            "severity": severity,
            "audit_id": audit_id,
        })

        return {
            "success": True,
            "flag_id": flag_id,
            "message": "Activity flagged for review",
            "escalated": severity in ["high", "critical"],
            "audit_id": audit_id
        }

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get compliance status summary."""
        summary = {
            "sox_compliance": None,
            "finra_compliance": None,
            "total_violations": len(self._violations),
        }

        if self.sox:
            summary["sox_compliance"] = self.sox.get_compliance_summary()

        if self.finra:
            summary["finra_compliance"] = self.finra.get_compliance_summary()

        return summary

    def _create_audit_entry(
        self,
        action: str,
        actor: str,
        customer_id: str,
        transaction_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create audit trail entry."""
        import uuid

        audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

        entry = {
            "audit_id": audit_id,
            "action": action,
            "actor": actor,
            "customer_id": customer_id,
            "transaction_id": transaction_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        self._audit_log.append(entry)

        return audit_id
