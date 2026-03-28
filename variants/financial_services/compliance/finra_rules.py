"""
FINRA Rules Compliance Module.

Implements Financial Industry Regulatory Authority (FINRA) rules
for broker-dealers and financial services companies.

Key Rules Implemented:
- Rule 3110: Supervision
- Rule 4511: Books and Records
- Rule 4512: Customer Account Information
- Rule 4513: Customer Account Statements
- Rule 2010: Standards of Commercial Honor
- Rule 2111: Suitability

Reference: FINRA Manual (https://www.finra.org/rules-guidance/rulebooks)
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class FINRARule(str, Enum):
    """FINRA rule identifiers."""
    RULE_2010 = "2010"  # Standards of Commercial Honor
    RULE_2111 = "2111"  # Suitability
    RULE_3110 = "3110"  # Supervision
    RULE_3110_A = "3110(a)"  # Supervisory System
    RULE_3110_B = "3110(b)"  # Written Supervisory Procedures
    RULE_3110_C = "3110(c)"  # Internal Inspections
    RULE_3110_D = "3110(d)"  # Review of Transactions
    RULE_4511 = "4511"  # Books and Records
    RULE_4512 = "4512"  # Customer Account Information
    RULE_4513 = "4513"  # Customer Account Statements
    RULE_4514 = "4514"  # Customer Account Documents
    RULE_4516 = "4516"  # Customer Account Maintenance
    RULE_4517 = "4517"  # Customer Complaints


class FINRAViolationType(str, Enum):
    """Types of FINRA violations."""
    SUPERVISION_FAILURE = "supervision_failure"
    RECORD_RETENTION = "record_retention"
    CUSTOMER_INFO_MISSING = "customer_info_missing"
    UNSUITABLE_RECOMMENDATION = "unsuitable_recommendation"
    COMPLAINT_HANDLING = "complaint_handling"
    DOCUMENTATION_MISSING = "documentation_missing"
    TIMELINE_VIOLATION = "timeline_violation"
    DISCLOSURE_FAILURE = "disclosure_failure"


class FINRASeverity(str, Enum):
    """Severity levels for FINRA violations."""
    MINOR = "minor"  # Procedural issue
    MODERATE = "moderate"  # Rule violation, no customer harm
    SIGNIFICANT = "significant"  # Potential customer impact
    MAJOR = "major"  # Customer harm or regulatory action risk


@dataclass
class FINRAViolation:
    """
    Represents a FINRA rule violation.

    Attributes:
        violation_type: Type of FINRA violation
        severity: Severity level
        rule: Related FINRA rule
        description: Human-readable description
        timestamp: When the violation occurred
        context: Additional context data
        remediation: Suggested remediation steps
        deadline: Deadline for remediation
    """
    violation_type: FINRAViolationType
    severity: FINRASeverity
    rule: FINRARule
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)
    remediation: Optional[str] = None
    deadline: Optional[datetime] = None
    violation_id: str = field(default="")

    def __post_init__(self):
        """Generate unique violation ID."""
        if not self.violation_id:
            import hashlib
            hash_data = f"{self.violation_type.value}{self.timestamp.isoformat()}"
            self.violation_id = f"FINRA-{hashlib.md5(hash_data.encode()).hexdigest()[:8].upper()}"


@dataclass
class CustomerComplaint:
    """
    Customer complaint record per FINRA Rule 4513.

    FINRA requires member firms to maintain records of
    customer complaints with specific data elements.
    """
    complaint_id: str
    customer_name: str
    customer_account: str
    complaint_date: datetime
    receipt_date: datetime
    complaint_type: str  # written, oral, electronic
    description: str
    products_services: List[str]
    associated_persons: List[str]
    status: str = "open"  # open, under_review, resolved, closed
    resolution_date: Optional[datetime] = None
    resolution_description: Optional[str] = None
    supervisory_review_date: Optional[datetime] = None
    supervisory_reviewer: Optional[str] = None

    def to_record(self) -> Dict[str, Any]:
        """Convert to record format for retention."""
        return {
            "complaint_id": self.complaint_id,
            "customer_name": self.customer_name,
            "customer_account": self.customer_account,
            "complaint_date": self.complaint_date.isoformat(),
            "receipt_date": self.receipt_date.isoformat(),
            "complaint_type": self.complaint_type,
            "description": self.description,
            "products_services": self.products_services,
            "associated_persons": self.associated_persons,
            "status": self.status,
            "resolution_date": self.resolution_date.isoformat() if self.resolution_date else None,
            "resolution_description": self.resolution_description,
            "supervisory_review_date": self.supervisory_review_date.isoformat() if self.supervisory_review_date else None,
            "supervisory_reviewer": self.supervisory_reviewer,
        }


@dataclass
class SupervisoryReview:
    """
    Supervisory review record per FINRA Rule 3110.

    Documents supervisory review of customer accounts
    and transactions.
    """
    review_id: str
    review_type: str  # transaction, account, complaint, communication
    reviewer: str
    review_date: datetime
    items_reviewed: List[str]
    findings: List[str]
    actions_taken: List[str]
    next_review_date: Optional[datetime] = None

    def to_record(self) -> Dict[str, Any]:
        """Convert to record format for retention."""
        return {
            "review_id": self.review_id,
            "review_type": self.review_type,
            "reviewer": self.reviewer,
            "review_date": self.review_date.isoformat(),
            "items_reviewed": self.items_reviewed,
            "findings": self.findings,
            "actions_taken": self.actions_taken,
            "next_review_date": self.next_review_date.isoformat() if self.next_review_date else None,
        }


class FINRARules:
    """
    FINRA Rules compliance checker and enforcer.

    Implements key FINRA regulatory requirements:
    - Rule 3110: Supervision system and procedures
    - Rule 4511: Books and records retention
    - Rule 4512: Customer account information
    - Complaint handling requirements
    - Communication retention

    Usage:
        finra = FINRARules()

        # Process customer complaint
        complaint = finra.create_complaint(
            customer_name="John Doe",
            description="Unauthorized transaction",
            complaint_type="written"
        )

        # Check compliance
        result = finra.check_compliance("complaint_handling", complaint)
    """

    # Complaint handling timelines per FINRA
    COMPLAINT_ACKNOWLEDGMENT_DAYS = 7  # Days to acknowledge complaint
    COMPLAINT_RESOLUTION_DAYS = 30  # Target resolution timeline
    COMPLAINT_ESCALATION_DAYS = 60  # Escalation if unresolved

    # Record retention periods per Rule 4511
    RECORD_RETENTION_YEARS = {
        "customer_account": 6,
        "customer_complaint": 7,
        "communication": 7,
        "transaction": 6,
        "supervisory_review": 6,
    }

    # Required customer account information per Rule 4512
    REQUIRED_CUSTOMER_INFO = [
        "customer_name",
        "customer_address",
        "customer_tax_id",  # SSN or EIN
        "customer_dob",  # Date of birth
        "customer_occupation",
        "customer_employer",
        "investment_objectives",
        "risk_tolerance",
        "account_type",
    ]

    def __init__(self):
        """Initialize FINRA rules checker."""
        self._complaints: List[CustomerComplaint] = []
        self._supervisory_reviews: List[SupervisoryReview] = []
        self._violations: List[FINRAViolation] = []

    def create_complaint(
        self,
        customer_name: str,
        customer_account: str,
        description: str,
        complaint_type: str,
        products_services: Optional[List[str]] = None,
        associated_persons: Optional[List[str]] = None,
    ) -> CustomerComplaint:
        """
        Create a customer complaint record.

        Per FINRA Rule 4513, firms must maintain records of
        all customer complaints with specific data elements.

        Args:
            customer_name: Name of complaining customer
            customer_account: Customer account number
            description: Description of complaint
            complaint_type: Type (written, oral, electronic)
            products_services: Products/services involved
            associated_persons: Associated persons involved

        Returns:
            CustomerComplaint record
        """
        import uuid

        complaint = CustomerComplaint(
            complaint_id=f"CMP-{uuid.uuid4().hex[:8].upper()}",
            customer_name=customer_name,
            customer_account=customer_account,
            complaint_date=datetime.utcnow(),
            receipt_date=datetime.utcnow(),
            complaint_type=complaint_type,
            description=description,
            products_services=products_services or [],
            associated_persons=associated_persons or [],
        )

        self._complaints.append(complaint)

        logger.info({
            "event": "finra_complaint_created",
            "complaint_id": complaint.complaint_id,
            "customer_account": customer_account,
            "complaint_type": complaint_type,
        })

        return complaint

    def process_complaint(
        self,
        complaint_id: str,
        resolution_description: str,
        supervisor: str
    ) -> Dict[str, Any]:
        """
        Process and resolve a customer complaint.

        Per FINRA Rule 3110, complaints must be supervised
        and documented.

        Args:
            complaint_id: Complaint to process
            resolution_description: Resolution details
            supervisor: Supervising person

        Returns:
            Processing result
        """
        complaint = next(
            (c for c in self._complaints if c.complaint_id == complaint_id),
            None
        )

        if not complaint:
            return {"success": False, "error": "Complaint not found"}

        # Update complaint record
        complaint.status = "resolved"
        complaint.resolution_date = datetime.utcnow()
        complaint.resolution_description = resolution_description
        complaint.supervisory_review_date = datetime.utcnow()
        complaint.supervisory_reviewer = supervisor

        # Check timeline compliance
        days_open = (datetime.utcnow() - complaint.receipt_date).days

        result = {
            "success": True,
            "complaint_id": complaint_id,
            "days_to_resolve": days_open,
            "timeline_compliant": days_open <= self.COMPLAINT_RESOLUTION_DAYS,
        }

        if days_open > self.COMPLAINT_RESOLUTION_DAYS:
            self._violations.append(FINRAViolation(
                violation_type=FINRAViolationType.TIMELINE_VIOLATION,
                severity=FINRASeverity.MODERATE,
                rule=FINRARule.RULE_3110,
                description=f"Complaint {complaint_id} exceeded resolution timeline",
                context={"days_open": days_open, "target": self.COMPLAINT_RESOLUTION_DAYS},
                remediation="Review complaint handling procedures",
            ))

        logger.info({
            "event": "finra_complaint_resolved",
            "complaint_id": complaint_id,
            "days_to_resolve": days_open,
            "supervisor": supervisor,
        })

        return result

    def create_supervisory_review(
        self,
        review_type: str,
        reviewer: str,
        items_reviewed: List[str],
        findings: Optional[List[str]] = None,
        actions_taken: Optional[List[str]] = None,
    ) -> SupervisoryReview:
        """
        Create a supervisory review record.

        Per FINRA Rule 3110, firms must conduct and document
        supervisory reviews.

        Args:
            review_type: Type of review
            reviewer: Person conducting review
            items_reviewed: Items reviewed
            findings: Review findings
            actions_taken: Actions taken based on findings

        Returns:
            SupervisoryReview record
        """
        import uuid

        review = SupervisoryReview(
            review_id=f"REV-{uuid.uuid4().hex[:8].upper()}",
            review_type=review_type,
            reviewer=reviewer,
            review_date=datetime.utcnow(),
            items_reviewed=items_reviewed,
            findings=findings or [],
            actions_taken=actions_taken or [],
        )

        self._supervisory_reviews.append(review)

        logger.info({
            "event": "finra_supervisory_review_created",
            "review_id": review.review_id,
            "review_type": review_type,
            "reviewer": reviewer,
        })

        return review

    def check_customer_info(
        self,
        customer_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check customer account information completeness.

        Per FINRA Rule 4512, customer accounts must have
        specific required information.

        Args:
            customer_data: Customer account data

        Returns:
            Compliance check result
        """
        missing_fields = []

        for field in self.REQUIRED_CUSTOMER_INFO:
            if field not in customer_data or not customer_data[field]:
                missing_fields.append(field)

        compliant = len(missing_fields) == 0

        if not compliant:
            self._violations.append(FINRAViolation(
                violation_type=FINRAViolationType.CUSTOMER_INFO_MISSING,
                severity=FINRASeverity.MODERATE,
                rule=FINRARule.RULE_4512,
                description="Customer account missing required information",
                context={"missing_fields": missing_fields},
                remediation="Obtain missing customer information",
            ))

        return {
            "compliant": compliant,
            "missing_fields": missing_fields,
            "required_fields": self.REQUIRED_CUSTOMER_INFO,
        }

    def check_suitability(
        self,
        recommendation: str,
        customer_profile: Dict[str, Any],
        product_type: str
    ) -> Dict[str, Any]:
        """
        Check recommendation suitability per FINRA Rule 2111.

        Recommendations must be suitable based on customer's
        investment profile.

        Args:
            recommendation: The recommendation made
            customer_profile: Customer investment profile
            product_type: Type of product recommended

        Returns:
            Suitability check result
        """
        issues = []

        # Check risk tolerance alignment
        customer_risk = customer_profile.get("risk_tolerance", "moderate")
        product_risk = self._get_product_risk(product_type)

        if product_risk == "high" and customer_risk == "low":
            issues.append({
                "type": "risk_mismatch",
                "description": "High-risk product not suitable for low-risk customer",
            })

        # Check investment objectives alignment
        objectives = customer_profile.get("investment_objectives", [])
        if product_type == "speculative" and "growth" not in objectives:
            issues.append({
                "type": "objective_mismatch",
                "description": "Speculative product may not align with objectives",
            })

        suitable = len(issues) == 0

        if not suitable:
            self._violations.append(FINRAViolation(
                violation_type=FINRAViolationType.UNSUITABLE_RECOMMENDATION,
                severity=FINRASeverity.SIGNIFICANT,
                rule=FINRARule.RULE_2111,
                description="Potential unsuitable recommendation",
                context={
                    "recommendation": recommendation,
                    "product_type": product_type,
                    "issues": issues,
                },
                remediation="Review recommendation with supervisor",
            ))

        return {
            "suitable": suitable,
            "issues": issues,
            "customer_risk_tolerance": customer_risk,
            "product_risk": product_risk,
        }

    def _get_product_risk(self, product_type: str) -> str:
        """Get risk level for product type."""
        risk_map = {
            "savings_bond": "low",
            "treasury": "low",
            "municipal_bond": "low",
            "corporate_bond": "moderate",
            "mutual_fund": "moderate",
            "etf": "moderate",
            "stock": "moderate",
            "options": "high",
            "futures": "high",
            "speculative": "high",
        }
        return risk_map.get(product_type, "moderate")

    def get_pending_complaints(self) -> List[CustomerComplaint]:
        """Get all pending complaints requiring action."""
        return [c for c in self._complaints if c.status == "open"]

    def get_overdue_complaints(self) -> List[CustomerComplaint]:
        """Get complaints past resolution deadline."""
        threshold = datetime.utcnow() - timedelta(days=self.COMPLAINT_RESOLUTION_DAYS)
        return [
            c for c in self._complaints
            if c.status == "open" and c.receipt_date < threshold
        ]

    def get_violations(
        self,
        severity: Optional[FINRASeverity] = None
    ) -> List[FINRAViolation]:
        """Get all FINRA violations."""
        if severity:
            return [v for v in self._violations if v.severity == severity]
        return self._violations.copy()

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get FINRA compliance summary."""
        violations_by_severity = {}
        for severity in FINRASeverity:
            violations_by_severity[severity.value] = len([
                v for v in self._violations if v.severity == severity
            ])

        overdue_complaints = self.get_overdue_complaints()

        return {
            "total_complaints": len(self._complaints),
            "open_complaints": len(self.get_pending_complaints()),
            "overdue_complaints": len(overdue_complaints),
            "total_supervisory_reviews": len(self._supervisory_reviews),
            "total_violations": len(self._violations),
            "violations_by_severity": violations_by_severity,
            "compliance_status": "compliant" if len(self._violations) == 0 and len(overdue_complaints) == 0 else "non_compliant",
        }
