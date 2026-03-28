"""
Financial Services Configuration.

Configuration settings specific to the Financial Services variant.
Implements regulatory requirements for financial industry compliance.

Key Settings:
- Higher refund limits ($500 for financial clients)
- Stricter approval thresholds (>$100 requires approval)
- Enhanced audit logging (100% of actions)
- Encryption at rest required
- Session timeout: 15 minutes (regulatory requirement)
- Max concurrent sessions: 1 per user
- Data retention: 7 years (regulatory requirement)

Regulatory References:
- SOX Section 404: Internal control documentation
- FINRA Rule 4511: Books and records retention
- PCI DSS Requirement 3: Protect stored cardholder data
- GLBA: Financial privacy requirements
"""

from typing import List, Optional, Dict, Any
from datetime import timedelta
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class DataClassification(str, Enum):
    """Data classification levels for financial services."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # PII, PCI, financial data


class EncryptionLevel(str, Enum):
    """Encryption requirements for data at rest and in transit."""
    STANDARD = "aes_256"  # Standard AES-256
    ENHANCED = "aes_256_gcm"  # AES-256-GCM with authentication
    FINANCIAL = "aes_256_gcm_hsm"  # HSM-backed encryption for financial data


class AuditLogLevel(str, Enum):
    """Audit logging verbosity levels."""
    STANDARD = "standard"  # Standard logging
    ENHANCED = "enhanced"  # Enhanced with context
    FINANCIAL = "financial"  # Full regulatory compliance logging


class FinancialServicesConfig(BaseModel):
    """
    Configuration for Financial Services variant.

    This configuration enforces regulatory requirements for financial
    industry clients including banks, credit unions, investment firms,
    and fintech companies.

    Key Regulatory Requirements:
    - SOX: Sarbanes-Oxley Act compliance
    - FINRA: Financial Industry Regulatory Authority rules
    - PCI DSS: Payment Card Industry Data Security Standard
    - GLBA: Gramm-Leach-Bliley Act privacy rules
    """

    model_config = ConfigDict()

    # === Financial Limits ===
    refund_limit: float = Field(
        default=500.0,
        ge=0.0,
        le=10000.0,
        description="Maximum refund amount for financial clients (USD)"
    )

    approval_threshold: float = Field(
        default=100.0,
        ge=0.0,
        description="Amount threshold requiring explicit approval (USD)"
    )

    auto_approve_threshold: float = Field(
        default=25.0,
        ge=0.0,
        description="Amounts under this can be auto-approved for review (USD)"
    )

    # === Session Security ===
    session_timeout_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Session timeout in minutes (regulatory requirement)"
    )

    max_concurrent_sessions: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Maximum concurrent sessions per user (security)"
    )

    idle_timeout_minutes: int = Field(
        default=5,
        ge=1,
        le=15,
        description="Idle timeout before session lock (minutes)"
    )

    # === Data Protection ===
    encryption_at_rest: EncryptionLevel = Field(
        default=EncryptionLevel.FINANCIAL,
        description="Encryption level for data at rest"
    )

    encryption_in_transit: EncryptionLevel = Field(
        default=EncryptionLevel.ENHANCED,
        description="Encryption level for data in transit"
    )

    data_classification: DataClassification = Field(
        default=DataClassification.RESTRICTED,
        description="Default data classification level"
    )

    # === Audit Logging ===
    audit_log_level: AuditLogLevel = Field(
        default=AuditLogLevel.FINANCIAL,
        description="Audit logging verbosity level"
    )

    audit_log_retention_days: int = Field(
        default=2555,  # 7 years = 365 * 7
        ge=365,
        description="Audit log retention period in days (7 years for SOX)"
    )

    audit_all_actions: bool = Field(
        default=True,
        description="Log all actions for regulatory compliance"
    )

    # === Data Retention ===
    data_retention_years: int = Field(
        default=7,
        ge=1,
        le=10,
        description="Data retention period in years (regulatory requirement)"
    )

    complaint_retention_years: int = Field(
        default=7,
        ge=1,
        le=10,
        description="Complaint records retention period (FINRA requirement)"
    )

    communication_retention_years: int = Field(
        default=7,
        ge=1,
        le=10,
        description="Communication records retention (FINRA Rule 4511)"
    )

    # === Communication Channels ===
    supported_channels: List[str] = Field(
        default=["email", "chat", "ticket", "voice"],
        description="Supported communication channels for financial services"
    )

    # === Compliance Settings ===
    sox_compliance_enabled: bool = Field(
        default=True,
        description="Enable SOX (Sarbanes-Oxley) compliance checks"
    )

    finra_compliance_enabled: bool = Field(
        default=True,
        description="Enable FINRA regulatory compliance"
    )

    pci_compliance_enabled: bool = Field(
        default=True,
        description="Enable PCI DSS compliance checks"
    )

    # === Fraud Detection ===
    fraud_detection_enabled: bool = Field(
        default=True,
        description="Enable fraud detection and monitoring"
    )

    fraud_alert_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Risk score threshold for fraud alerts"
    )

    transaction_monitoring_enabled: bool = Field(
        default=True,
        description="Enable real-time transaction monitoring"
    )

    # === PII Protection ===
    pii_masking_enabled: bool = Field(
        default=True,
        description="Enable PII masking in responses and logs"
    )

    pci_masking_enabled: bool = Field(
        default=True,
        description="Enable PCI data masking (card numbers, CVV)"
    )

    account_number_masking: bool = Field(
        default=True,
        description="Mask account numbers in responses"
    )

    # === Approval Workflows ===
    require_dual_approval: bool = Field(
        default=True,
        description="Require dual approval for high-value transactions"
    )

    dual_approval_threshold: float = Field(
        default=500.0,
        ge=100.0,
        description="Amount threshold requiring dual approval (USD)"
    )

    escalation_timeout_hours: int = Field(
        default=24,
        ge=1,
        le=72,
        description="Hours before automatic escalation"
    )

    # === Response Settings ===
    max_response_time_seconds: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Maximum time to generate a response"
    )

    # === Supported Industries ===
    supported_industries: List[str] = Field(
        default=[
            "banking",
            "credit_union",
            "investment",
            "insurance",
            "fintech",
            "wealth_management",
            "mortgage",
            "lending",
        ],
        description="Supported financial services industries"
    )

    def get_variant_name(self) -> str:
        """Get the display name for this variant."""
        return "Financial Services PARWA"

    def get_variant_id(self) -> str:
        """Get the identifier for this variant."""
        return "financial_services"

    def requires_approval(self, amount: float) -> bool:
        """
        Check if a transaction amount requires approval.

        Args:
            amount: Transaction amount in USD

        Returns:
            True if approval is required
        """
        return amount >= self.approval_threshold

    def requires_dual_approval(self, amount: float) -> bool:
        """
        Check if a transaction requires dual approval.

        Args:
            amount: Transaction amount in USD

        Returns:
            True if dual approval is required
        """
        return amount >= self.dual_approval_threshold

    def mask_account_number(self, account_number: str) -> str:
        """
        Mask an account number for display.

        Shows only last 4 digits, replaces rest with X.

        Args:
            account_number: Full account number

        Returns:
            Masked account number (e.g., XXXXX1234)
        """
        if not self.account_number_masking:
            return account_number

        if len(account_number) <= 4:
            return account_number

        return "X" * (len(account_number) - 4) + account_number[-4:]

    def mask_card_number(self, card_number: str) -> str:
        """
        Mask a payment card number for display.

        Shows only last 4 digits per PCI DSS requirements.

        Args:
            card_number: Full card number

        Returns:
            Masked card number (e.g., XXXX-XXXX-XXXX-1234)
        """
        if not self.pci_masking_enabled:
            return card_number

        # Remove any spaces or dashes
        clean_number = card_number.replace(" ", "").replace("-", "")

        if len(clean_number) < 4:
            return clean_number

        # Format as XXXX-XXXX-XXXX-1234
        last_four = clean_number[-4:]
        return f"XXXX-XXXX-XXXX-{last_four}"

    def get_retention_date(self, creation_date: Any) -> Any:
        """
        Calculate the retention end date for a record.

        Args:
            creation_date: Record creation date

        Returns:
            Date when record can be deleted
        """
        from datetime import datetime, timedelta

        if isinstance(creation_date, datetime):
            return creation_date + timedelta(days=self.data_retention_years * 365)

        return None

    def get_compliance_requirements(self) -> Dict[str, Any]:
        """
        Get all compliance requirements for this configuration.

        Returns:
            Dictionary of compliance requirements
        """
        return {
            "sox": {
                "enabled": self.sox_compliance_enabled,
                "audit_logging": self.audit_log_level == AuditLogLevel.FINANCIAL,
                "data_retention_years": self.data_retention_years,
                "internal_controls": True,
            },
            "finra": {
                "enabled": self.finra_compliance_enabled,
                "rule_3110": {
                    "supervision": True,
                    "written_procedures": True,
                },
                "rule_4511": {
                    "books_and_records": True,
                    "retention_years": self.communication_retention_years,
                },
            },
            "pci_dss": {
                "enabled": self.pci_compliance_enabled,
                "data_masking": self.pci_masking_enabled,
                "encryption_at_rest": self.encryption_at_rest.value,
                "encryption_in_transit": self.encryption_in_transit.value,
            },
            "audit": {
                "all_actions_logged": self.audit_all_actions,
                "retention_days": self.audit_log_retention_days,
                "level": self.audit_log_level.value,
            },
        }


# Default configuration instance
DEFAULT_FINANCIAL_SERVICES_CONFIG = FinancialServicesConfig()


def get_financial_services_config() -> FinancialServicesConfig:
    """
    Get the default Financial Services configuration.

    Returns:
        FinancialServicesConfig instance with regulatory settings
    """
    return DEFAULT_FINANCIAL_SERVICES_CONFIG
