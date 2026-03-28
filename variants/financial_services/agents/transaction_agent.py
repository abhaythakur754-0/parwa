"""
Transaction Agent for Financial Services.

Handles transaction-related inquiries with security focus:
- Transaction status inquiries
- Transaction history (limited)
- Payment status checks
- Transfer status inquiries

CRITICAL: This agent NEVER initiates transactions.
All transaction initiation must go through secure channels
with proper authentication and approval.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)

logger = logging.getLogger(__name__)


class TransactionStatus(str, Enum):
    """Transaction status types."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"
    DISPUTED = "disputed"


class TransactionType(str, Enum):
    """Transaction types."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    REFUND = "refund"
    FEE = "fee"
    INTEREST = "interest"
    ADJUSTMENT = "adjustment"


@dataclass
class TransactionInfo:
    """
    Transaction information safe for display.

    Sensitive details are masked per regulatory requirements.
    """
    transaction_id: str
    transaction_type: TransactionType
    status: TransactionStatus
    amount_range: str  # Range for security
    currency: str = "USD"
    timestamp: str = ""
    description: str = ""
    category: str = ""
    masked_counterparty: Optional[str] = None  # e.g., "Merchant ****1234"
    reference_number: Optional[str] = None
    # Limited history
    status_history: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class TransactionInquiryResult:
    """Result of a transaction inquiry."""
    success: bool
    transaction_info: Optional[TransactionInfo] = None
    message: str = ""
    requires_authentication: bool = False
    audit_id: str = ""


class TransactionAgent:
    """
    Agent for handling transaction inquiries in financial services.

    Security Features:
    - NO transaction initiation capability (security by design)
    - Amount shown as ranges, not exact amounts
    - Counterparty information masked
    - Audit trail for all inquiries
    - Limited transaction history

    Regulatory Compliance:
    - PCI DSS data protection
    - SOX audit trail
    - FINRA record keeping
    - GLBA privacy requirements

    CRITICAL: This agent can ONLY inquire about transactions.
    It cannot create, modify, or cancel any transaction.
    """

    # Amount ranges for security display
    AMOUNT_RANGES = [
        (0, 10, "Under $10"),
        (10, 50, "$10 - $50"),
        (50, 100, "$50 - $100"),
        (100, 500, "$100 - $500"),
        (500, 1000, "$500 - $1,000"),
        (1000, 5000, "$1,000 - $5,000"),
        (5000, 10000, "$5,000 - $10,000"),
        (10000, float('inf'), "Over $10,000"),
    ]

    # Maximum transaction history returned
    MAX_HISTORY_ITEMS = 30

    def __init__(
        self,
        config: Optional[FinancialServicesConfig] = None
    ):
        """
        Initialize transaction agent.

        Args:
            config: Financial services configuration
        """
        self.config = config or get_financial_services_config()
        self._audit_log: List[Dict[str, Any]] = []

    def get_transaction_status(
        self,
        customer_id: str,
        transaction_id: str,
        actor: str
    ) -> TransactionInquiryResult:
        """
        Get status of a specific transaction.

        Args:
            customer_id: Customer identifier
            transaction_id: Transaction to query
            actor: User performing the inquiry

        Returns:
            TransactionInquiryResult with status information
        """
        audit_id = self._create_audit_entry(
            action="transaction_status_inquiry",
            actor=actor,
            customer_id=customer_id,
            transaction_id=transaction_id
        )

        # Look up transaction (simulated)
        transaction_info = self._lookup_transaction(customer_id, transaction_id)

        if not transaction_info:
            return TransactionInquiryResult(
                success=False,
                message="Transaction not found or access denied.",
                audit_id=audit_id
            )

        logger.info({
            "event": "transaction_status_inquiry",
            "customer_id": customer_id,
            "transaction_id": transaction_id,
            "actor": actor,
            "audit_id": audit_id,
        })

        return TransactionInquiryResult(
            success=True,
            transaction_info=transaction_info,
            message="Transaction status retrieved successfully.",
            audit_id=audit_id
        )

    def search_transactions(
        self,
        customer_id: str,
        account_id: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        transaction_type: Optional[str] = None,
        actor: str = "system"
    ) -> Dict[str, Any]:
        """
        Search transaction history.

        Returns limited transaction history for security.
        Exact amounts are never shown.

        Args:
            customer_id: Customer identifier
            account_id: Account to search
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            transaction_type: Filter by type
            actor: User performing the search

        Returns:
            Dict with transaction list
        """
        audit_id = self._create_audit_entry(
            action="transaction_search",
            actor=actor,
            customer_id=customer_id,
            metadata={
                "account_id": account_id,
                "date_from": date_from,
                "date_to": date_to,
                "type": transaction_type
            }
        )

        # Validate date range
        if not self._validate_date_range(date_from, date_to):
            return {
                "success": False,
                "message": "Invalid date range. Maximum range is 90 days.",
                "audit_id": audit_id
            }

        # Get transactions (simulated)
        transactions = self._get_transaction_history(
            customer_id, account_id, date_from, date_to, transaction_type
        )

        logger.info({
            "event": "transaction_search",
            "customer_id": customer_id,
            "account_id": account_id,
            "actor": actor,
            "results_count": len(transactions),
            "audit_id": audit_id,
        })

        return {
            "success": True,
            "transactions": transactions[:self.MAX_HISTORY_ITEMS],
            "total_count": len(transactions),
            "returned_count": min(len(transactions), self.MAX_HISTORY_ITEMS),
            "message": f"Found {len(transactions)} transactions.",
            "audit_id": audit_id
        }

    def verify_payment(
        self,
        customer_id: str,
        payment_id: str,
        actor: str
    ) -> Dict[str, Any]:
        """
        Verify payment status.

        Args:
            customer_id: Customer identifier
            payment_id: Payment to verify
            actor: User performing verification

        Returns:
            Dict with verification result
        """
        audit_id = self._create_audit_entry(
            action="payment_verification",
            actor=actor,
            customer_id=customer_id,
            transaction_id=payment_id
        )

        # Look up payment (simulated)
        transaction = self._lookup_transaction(customer_id, payment_id)

        if not transaction:
            return {
                "success": False,
                "verified": False,
                "message": "Payment not found.",
                "audit_id": audit_id
            }

        verified = transaction.status == TransactionStatus.COMPLETED

        logger.info({
            "event": "payment_verification",
            "customer_id": customer_id,
            "payment_id": payment_id,
            "actor": actor,
            "verified": verified,
            "audit_id": audit_id,
        })

        return {
            "success": True,
            "verified": verified,
            "status": transaction.status.value,
            "message": "Payment verified successfully." if verified else "Payment not yet completed.",
            "audit_id": audit_id
        }

    def get_transfer_status(
        self,
        customer_id: str,
        transfer_id: str,
        actor: str
    ) -> Dict[str, Any]:
        """
        Get transfer status.

        Args:
            customer_id: Customer identifier
            transfer_id: Transfer to check
            actor: User performing the inquiry

        Returns:
            Dict with transfer status
        """
        audit_id = self._create_audit_entry(
            action="transfer_status_inquiry",
            actor=actor,
            customer_id=customer_id,
            transaction_id=transfer_id
        )

        transaction = self._lookup_transaction(customer_id, transfer_id)

        if not transaction or transaction.transaction_type != TransactionType.TRANSFER:
            return {
                "success": False,
                "message": "Transfer not found.",
                "audit_id": audit_id
            }

        logger.info({
            "event": "transfer_status_inquiry",
            "customer_id": customer_id,
            "transfer_id": transfer_id,
            "actor": actor,
            "audit_id": audit_id,
        })

        return {
            "success": True,
            "transfer_id": transfer_id,
            "status": transaction.status.value,
            "amount_range": transaction.amount_range,
            "estimated_completion": self._estimate_completion(transaction),
            "message": "Transfer status retrieved.",
            "audit_id": audit_id
        }

    def _lookup_transaction(
        self,
        customer_id: str,
        transaction_id: str
    ) -> Optional[TransactionInfo]:
        """Look up transaction information (simulated)."""
        import hashlib

        hash_val = int(hashlib.md5(f"{customer_id}{transaction_id}".encode()).hexdigest()[:8], 16)

        types = list(TransactionType)
        statuses = [TransactionStatus.COMPLETED, TransactionStatus.PENDING, TransactionStatus.PROCESSING]

        txn_type = types[hash_val % len(types)]
        status = statuses[hash_val % len(statuses)]

        amount = hash_val % 10000

        return TransactionInfo(
            transaction_id=transaction_id,
            transaction_type=txn_type,
            status=status,
            amount_range=self._get_amount_range(amount),
            timestamp=(datetime.utcnow() - timedelta(hours=hash_val % 48)).isoformat(),
            description="Transaction",
            category="General",
            masked_counterparty="Merchant ****" + str(hash_val % 10000).zfill(4),
        )

    def _get_transaction_history(
        self,
        customer_id: str,
        account_id: str,
        date_from: Optional[str],
        date_to: Optional[str],
        txn_type: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get transaction history (simulated)."""
        import hashlib
        import random

        hash_val = int(hashlib.md5(f"{customer_id}{account_id}".encode()).hexdigest()[:8], 16)
        random.seed(hash_val)

        count = random.randint(5, 20)
        transactions = []

        for i in range(count):
            txn_id = f"TXN-{random.randint(100000, 999999)}"
            amount = random.randint(10, 5000)

            txn = {
                "transaction_id": txn_id,
                "type": random.choice(list(TransactionType)).value,
                "status": random.choice(["completed", "completed", "pending"]),
                "amount_range": self._get_amount_range(amount),
                "date": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "description": "Transaction",
            }
            transactions.append(txn)

        return transactions

    def _get_amount_range(self, amount: float) -> str:
        """Convert amount to range string for security."""
        for min_val, max_val, label in self.AMOUNT_RANGES:
            if min_val <= amount < max_val:
                return label
        return "Over $10,000"

    def _validate_date_range(
        self,
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> bool:
        """Validate date range is within limits."""
        if not date_from or not date_to:
            return True

        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            to_date = datetime.strptime(date_to, "%Y-%m-%d")

            # Maximum 90 day range
            if (to_date - from_date).days > 90:
                return False

            return True
        except ValueError:
            return False

    def _estimate_completion(self, transaction: TransactionInfo) -> Optional[str]:
        """Estimate completion time for pending transactions."""
        if transaction.status == TransactionStatus.PENDING:
            return (datetime.utcnow() + timedelta(hours=24)).strftime("%Y-%m-%d %H:00")
        elif transaction.status == TransactionStatus.PROCESSING:
            return (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%d %H:00")
        return None

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
