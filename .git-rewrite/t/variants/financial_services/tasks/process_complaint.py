"""
Process Complaint Task for Financial Services.

Handles customer complaints per FINRA requirements:
- Timeline tracking
- Documentation requirements
- Escalation procedures
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import uuid

from variants.financial_services.config import get_financial_services_config
from variants.financial_services.compliance.finra_rules import FINRARules

logger = logging.getLogger(__name__)


@dataclass
class ComplaintResult:
    """Result of complaint processing."""
    success: bool
    complaint_id: str
    status: str
    timeline_deadline: str
    assigned_to: str
    audit_id: str
    requires_escalation: bool


def process_complaint(
    customer_id: str,
    complaint_type: str,
    complaint_description: str,
    customer_info: Dict[str, Any],
    actor: str
) -> ComplaintResult:
    """
    Process customer complaint per FINRA rules.

    Args:
        customer_id: Customer identifier
        complaint_type: Type of complaint
        complaint_description: Complaint details
        customer_info: Customer information
        actor: User processing complaint

    Returns:
        ComplaintResult with processing status
    """
    config = get_financial_services_config()
    finra = FINRARules()
    complaint_id = f"CMP-{uuid.uuid4().hex[:8].upper()}"
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Create complaint record
    complaint = finra.create_complaint(
        customer_name=customer_info.get("name", "Customer"),
        customer_account=customer_info.get("account_id", "N/A"),
        description=complaint_description,
        complaint_type="written"
    )

    # Calculate deadline (30 days per FINRA)
    deadline = datetime.utcnow() + timedelta(days=30)

    # Check if escalation needed
    requires_escalation = _check_escalation_needed(complaint_type, complaint_description)

    # Assign to appropriate handler
    assigned_to = "compliance_team" if requires_escalation else "support_team"

    logger.info({
        "event": "complaint_processed",
        "complaint_id": complaint_id,
        "customer_id": customer_id,
        "complaint_type": complaint_type,
        "requires_escalation": requires_escalation,
        "audit_id": audit_id,
    })

    return ComplaintResult(
        success=True,
        complaint_id=complaint.complaint_id,
        status="open",
        timeline_deadline=deadline.strftime("%Y-%m-%d"),
        assigned_to=assigned_to,
        audit_id=audit_id,
        requires_escalation=requires_escalation
    )


def _check_escalation_needed(complaint_type: str, description: str) -> bool:
    """Check if complaint requires escalation."""
    escalation_keywords = ["fraud", "unauthorized", "legal", "regulator", "attorney"]
    description_lower = description.lower()
    return any(keyword in description_lower for keyword in escalation_keywords)
