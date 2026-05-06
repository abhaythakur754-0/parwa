"""
Handle Inquiry Task for Financial Services.

Processes financial inquiries with:
- Compliance checks
- Audit trail generation
- PII masking
"""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import logging
import uuid

from variants.financial_services.config import get_financial_services_config
from variants.financial_services.workflows.compliance_workflow import ComplianceWorkflow

logger = logging.getLogger(__name__)


@dataclass
class InquiryResult:
    """Result of inquiry handling."""
    success: bool
    inquiry_id: str
    response: str
    masked_response: str
    audit_id: str
    compliance_passed: bool


def handle_inquiry(
    customer_id: str,
    inquiry_type: str,
    inquiry_data: Dict[str, Any],
    actor: str,
    actor_role: str = "agent"
) -> InquiryResult:
    """
    Handle financial inquiry with compliance checks.

    Args:
        customer_id: Customer identifier
        inquiry_type: Type of inquiry (balance, transaction, account)
        inquiry_data: Inquiry details
        actor: User handling inquiry
        actor_role: Role of the user

    Returns:
        InquiryResult with response and audit info
    """
    config = get_financial_services_config()
    workflow = ComplianceWorkflow(config)
    inquiry_id = f"INQ-{uuid.uuid4().hex[:8].upper()}"
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Execute compliance workflow
    result = workflow.execute_sync(
        action_type=f"inquiry_{inquiry_type}",
        customer_id=customer_id,
        amount=0.0,
        actor=actor,
        actor_role=actor_role,
        context=inquiry_data
    )

    # Generate response based on inquiry type
    response = _generate_response(inquiry_type, inquiry_data)
    masked_response = _mask_sensitive_data(response)

    logger.info({
        "event": "inquiry_handled",
        "inquiry_id": inquiry_id,
        "customer_id": customer_id,
        "inquiry_type": inquiry_type,
        "actor": actor,
        "audit_id": audit_id,
    })

    return InquiryResult(
        success=result.passed,
        inquiry_id=inquiry_id,
        response=response,
        masked_response=masked_response,
        audit_id=audit_id,
        compliance_passed=result.passed
    )


def _generate_response(inquiry_type: str, data: Dict[str, Any]) -> str:
    """Generate inquiry response."""
    responses = {
        "balance": "Your account balance is in the range of $1,000 - $5,000.",
        "transaction": "Transaction status: Completed.",
        "account": "Account status: Active.",
    }
    return responses.get(inquiry_type, "Inquiry processed.")


def _mask_sensitive_data(text: str) -> str:
    """Mask sensitive data in text."""
    import re
    # Mask account numbers
    text = re.sub(r'\b\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\b', 'XXXX-XXXX-XXXX-XXXX', text)
    # Mask SSN
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', 'XXX-XX-XXXX', text)
    return text
