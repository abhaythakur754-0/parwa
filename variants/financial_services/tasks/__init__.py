"""
Financial Services Tasks Module.

Provides task implementations for financial operations:
- handle_inquiry: Process financial inquiries
- process_complaint: FINRA-compliant complaint handling
- fraud_alert: Fraud alert generation
"""

from variants.financial_services.tasks.handle_inquiry import (
    handle_inquiry,
    InquiryResult,
)
from variants.financial_services.tasks.process_complaint import (
    process_complaint,
    ComplaintResult,
)
from variants.financial_services.tasks.fraud_alert import (
    create_fraud_alert,
    FraudAlertResult,
)

__all__ = [
    "handle_inquiry",
    "InquiryResult",
    "process_complaint",
    "ComplaintResult",
    "create_fraud_alert",
    "FraudAlertResult",
]
