"""
Financial Services Agents Module.

Provides specialized agents for financial services support:

- AccountInquiryAgent: Handle account balance and status inquiries
- TransactionAgent: Handle transaction status and history
- ComplianceAgent: Real-time compliance monitoring
- FraudDetectionAgent: Transaction pattern analysis and fraud detection

All agents enforce:
- PII masking in responses
- Audit trail generation
- Compliance checks before actions
- No transaction initiation (security requirement)
"""

from variants.financial_services.agents.account_inquiry_agent import (
    AccountInquiryAgent,
    AccountInfo,
    AccountStatus,
)
from variants.financial_services.agents.transaction_agent import (
    TransactionAgent,
    TransactionInfo,
    TransactionStatus,
)
from variants.financial_services.agents.compliance_agent import (
    ComplianceAgent,
    ComplianceCheckResult,
)
from variants.financial_services.agents.fraud_detection_agent import (
    FraudDetectionAgent,
    FraudRiskLevel,
    FraudAlert,
)

__all__ = [
    "AccountInquiryAgent",
    "AccountInfo",
    "AccountStatus",
    "TransactionAgent",
    "TransactionInfo",
    "TransactionStatus",
    "ComplianceAgent",
    "ComplianceCheckResult",
    "FraudDetectionAgent",
    "FraudRiskLevel",
    "FraudAlert",
]
