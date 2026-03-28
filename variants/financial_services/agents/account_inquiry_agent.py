"""
Account Inquiry Agent for Financial Services.

Handles customer account-related inquiries with strict security:
- Balance inquiries (limited info for security)
- Account status checks
- Statement requests
- Account verification

CRITICAL: Never exposes full account numbers or sensitive PII.
All responses are masked per PCI DSS and GLBA requirements.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)

logger = logging.getLogger(__name__)


class AccountStatus(str, Enum):
    """Account status types."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    PENDING = "pending"
    FROZEN = "frozen"


class AccountType(str, Enum):
    """Account types."""
    CHECKING = "checking"
    SAVINGS = "savings"
    MONEY_MARKET = "money_market"
    CREDIT = "credit"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"


@dataclass
class AccountInfo:
    """
    Masked account information safe for display.

    All sensitive data is masked per regulatory requirements.
    """
    account_id: str
    masked_account_number: str  # Only last 4 digits visible
    account_type: AccountType
    status: AccountStatus
    account_holder_name: str  # First name + last initial
    open_date: str  # YYYY-MM-DD
    last_activity_date: Optional[str] = None
    currency: str = "USD"
    # Balance is shown as range for security
    balance_range: Optional[str] = None  # e.g., "$1,000 - $5,000"
    available_credit_range: Optional[str] = None  # For credit accounts
    # Compliance flags
    has_alerts: bool = False
    requires_verification: bool = False


@dataclass
class InquiryResult:
    """Result of an account inquiry."""
    success: bool
    account_info: Optional[AccountInfo] = None
    message: str = ""
    requires_authentication: bool = False
    compliance_flags: List[str] = field(default_factory=list)
    audit_id: str = ""


class AccountInquiryAgent:
    """
    Agent for handling account inquiries in financial services.

    Security Features:
    - All account numbers masked (showing only last 4 digits)
    - Balance shown as ranges, not exact amounts
    - PII masked in all responses
    - Audit trail for all inquiries
    - Rate limiting per customer

    Regulatory Compliance:
    - GLBA privacy requirements
    - PCI DSS data protection
    - SOX audit trail
    - FINRA record keeping
    """

    # Balance ranges for security (never show exact amounts)
    BALANCE_RANGES = [
        (0, 100, "Under $100"),
        (100, 500, "$100 - $500"),
        (500, 1000, "$500 - $1,000"),
        (1000, 5000, "$1,000 - $5,000"),
        (5000, 10000, "$5,000 - $10,000"),
        (10000, 50000, "$10,000 - $50,000"),
        (50000, 100000, "$50,000 - $100,000"),
        (100000, float('inf'), "Over $100,000"),
    ]

    def __init__(
        self,
        config: Optional[FinancialServicesConfig] = None
    ):
        """
        Initialize account inquiry agent.

        Args:
            config: Financial services configuration
        """
        self.config = config or get_financial_services_config()
        self._inquiry_count: Dict[str, int] = {}
        self._audit_log: List[Dict[str, Any]] = []

    def handle_balance_inquiry(
        self,
        customer_id: str,
        account_id: str,
        actor: str,
        authentication_level: str = "standard"
    ) -> InquiryResult:
        """
        Handle balance inquiry request.

        Returns balance as range for security, never exact amount.

        Args:
            customer_id: Customer identifier
            account_id: Account to inquire about
            actor: User performing the inquiry
            authentication_level: Level of authentication provided

        Returns:
            InquiryResult with masked balance information
        """
        # Create audit entry
        audit_id = self._create_audit_entry(
            action="balance_inquiry",
            actor=actor,
            customer_id=customer_id,
            account_id=account_id
        )

        # Check rate limiting
        if not self._check_rate_limit(customer_id):
            return InquiryResult(
                success=False,
                message="Rate limit exceeded. Please try again later.",
                requires_authentication=False,
                audit_id=audit_id
            )

        # Simulate account lookup (in production, this would query backend)
        account_info = self._lookup_account(customer_id, account_id)

        if not account_info:
            return InquiryResult(
                success=False,
                message="Account not found or access denied.",
                audit_id=audit_id
            )

        # Check for compliance flags
        compliance_flags = self._check_compliance_flags(account_info)

        logger.info({
            "event": "account_balance_inquiry",
            "customer_id": customer_id,
            "account_id": account_id,
            "actor": actor,
            "audit_id": audit_id,
        })

        return InquiryResult(
            success=True,
            account_info=account_info,
            message="Balance inquiry processed successfully.",
            compliance_flags=compliance_flags,
            audit_id=audit_id
        )

    def handle_status_inquiry(
        self,
        customer_id: str,
        account_id: str,
        actor: str
    ) -> InquiryResult:
        """
        Handle account status inquiry.

        Args:
            customer_id: Customer identifier
            account_id: Account to check
            actor: User performing the inquiry

        Returns:
            InquiryResult with account status
        """
        audit_id = self._create_audit_entry(
            action="status_inquiry",
            actor=actor,
            customer_id=customer_id,
            account_id=account_id
        )

        account_info = self._lookup_account(customer_id, account_id)

        if not account_info:
            return InquiryResult(
                success=False,
                message="Account not found or access denied.",
                audit_id=audit_id
            )

        logger.info({
            "event": "account_status_inquiry",
            "customer_id": customer_id,
            "account_id": account_id,
            "actor": actor,
            "audit_id": audit_id,
        })

        return InquiryResult(
            success=True,
            account_info=account_info,
            message="Account status retrieved successfully.",
            audit_id=audit_id
        )

    def handle_statement_request(
        self,
        customer_id: str,
        account_id: str,
        statement_period: str,
        actor: str
    ) -> Dict[str, Any]:
        """
        Handle statement request.

        Creates a statement request for the specified period.
        Statement is not returned directly - sent to verified email.

        Args:
            customer_id: Customer identifier
            account_id: Account for statement
            statement_period: Period (e.g., "2024-01", "last_3_months")
            actor: User making the request

        Returns:
            Dict with request status
        """
        audit_id = self._create_audit_entry(
            action="statement_request",
            actor=actor,
            customer_id=customer_id,
            account_id=account_id,
            metadata={"period": statement_period}
        )

        # Validate period format
        if not self._validate_statement_period(statement_period):
            return {
                "success": False,
                "message": "Invalid statement period format.",
                "audit_id": audit_id
            }

        logger.info({
            "event": "account_statement_request",
            "customer_id": customer_id,
            "account_id": account_id,
            "period": statement_period,
            "actor": actor,
            "audit_id": audit_id,
        })

        return {
            "success": True,
            "message": "Statement request submitted. Statement will be sent to verified email.",
            "request_id": f"STMT-{audit_id[-8:]}",
            "audit_id": audit_id
        }

    def verify_account(
        self,
        customer_id: str,
        account_id: str,
        verification_data: Dict[str, Any],
        actor: str
    ) -> Dict[str, Any]:
        """
        Verify account ownership.

        Args:
            customer_id: Customer identifier
            account_id: Account to verify
            verification_data: Verification information
            actor: User performing verification

        Returns:
            Dict with verification result
        """
        audit_id = self._create_audit_entry(
            action="account_verification",
            actor=actor,
            customer_id=customer_id,
            account_id=account_id
        )

        # Check verification data
        verified = self._perform_verification(verification_data)

        logger.info({
            "event": "account_verification",
            "customer_id": customer_id,
            "account_id": account_id,
            "actor": actor,
            "verified": verified,
            "audit_id": audit_id,
        })

        return {
            "success": True,
            "verified": verified,
            "message": "Account verified successfully." if verified else "Verification failed.",
            "audit_id": audit_id
        }

    def _lookup_account(
        self,
        customer_id: str,
        account_id: str
    ) -> Optional[AccountInfo]:
        """
        Look up account information (simulated).

        In production, this would query the banking backend.
        Returns masked account info.
        """
        # Simulate account lookup
        # In production, this would call banking API

        import hashlib
        hash_val = int(hashlib.md5(f"{customer_id}{account_id}".encode()).hexdigest()[:8], 16)

        # Generate simulated account data
        account_types = list(AccountType)
        account_type = account_types[hash_val % len(account_types)]

        statuses = [AccountStatus.ACTIVE, AccountStatus.ACTIVE, AccountStatus.ACTIVE, AccountStatus.INACTIVE]
        status = statuses[hash_val % len(statuses)]

        # Generate masked account number
        masked_number = f"XXXX-XXXX-XXXX-{hash_val % 10000:04d}"

        return AccountInfo(
            account_id=account_id,
            masked_account_number=masked_number,
            account_type=account_type,
            status=status,
            account_holder_name="Customer",  # Would be first name + last initial
            open_date="2020-01-15",
            last_activity_date="2024-12-01",
            balance_range=self._get_balance_range(hash_val % 100000),
            has_alerts=(hash_val % 10 == 0),
            requires_verification=False
        )

    def _get_balance_range(self, balance: float) -> str:
        """Convert balance to range string for security."""
        for min_val, max_val, label in self.BALANCE_RANGES:
            if min_val <= balance < max_val:
                return label
        return "Over $100,000"

    def _check_rate_limit(self, customer_id: str) -> bool:
        """Check if customer has exceeded inquiry rate limit."""
        max_inquiries_per_hour = 10
        current_count = self._inquiry_count.get(customer_id, 0)

        if current_count >= max_inquiries_per_hour:
            logger.warning({
                "event": "rate_limit_exceeded",
                "customer_id": customer_id,
                "count": current_count
            })
            return False

        self._inquiry_count[customer_id] = current_count + 1
        return True

    def _check_compliance_flags(self, account_info: AccountInfo) -> List[str]:
        """Check for compliance flags on account."""
        flags = []

        if account_info.has_alerts:
            flags.append("ACCOUNT_HAS_ALERTS")

        if account_info.requires_verification:
            flags.append("VERIFICATION_REQUIRED")

        if account_info.status == AccountStatus.SUSPENDED:
            flags.append("ACCOUNT_SUSPENDED")

        if account_info.status == AccountStatus.FROZEN:
            flags.append("ACCOUNT_FROZEN")

        return flags

    def _create_audit_entry(
        self,
        action: str,
        actor: str,
        customer_id: str,
        account_id: str,
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
            "account_id": account_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        self._audit_log.append(entry)

        return audit_id

    def _validate_statement_period(self, period: str) -> bool:
        """Validate statement period format."""
        # Accept formats: YYYY-MM, last_3_months, last_6_months, last_year
        if period in ["last_3_months", "last_6_months", "last_year"]:
            return True

        # Check YYYY-MM format
        if re.match(r"^\d{4}-\d{2}$", period):
            return True

        return False

    def _perform_verification(self, data: Dict[str, Any]) -> bool:
        """Perform account verification (simulated)."""
        # In production, this would verify against multiple data points
        required_fields = ["last_4_ssn", "date_of_birth", "zip_code"]
        return all(field in data for field in required_fields)
