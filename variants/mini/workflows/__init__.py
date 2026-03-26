"""
PARWA Mini Workflows Package.

This package contains workflows used by Mini PARWA agents:
- InquiryWorkflow: Handle customer inquiries
- TicketCreationWorkflow: Create support tickets
- EscalationWorkflow: Handle escalations to human support
- OrderStatusWorkflow: Check and report order status
- RefundVerificationWorkflow: Process refund requests

All workflows are designed for Mini variant with appropriate limits.
CRITICAL: RefundVerificationWorkflow never calls Paddle directly.
"""
from variants.mini.workflows.inquiry import InquiryWorkflow
from variants.mini.workflows.ticket_creation import TicketCreationWorkflow
from variants.mini.workflows.escalation import EscalationWorkflow
from variants.mini.workflows.order_status import OrderStatusWorkflow
from variants.mini.workflows.refund_verification import RefundVerificationWorkflow

__all__ = [
    "InquiryWorkflow",
    "TicketCreationWorkflow",
    "EscalationWorkflow",
    "OrderStatusWorkflow",
    "RefundVerificationWorkflow",
]
