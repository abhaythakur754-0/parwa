"""
Transaction Tools for Financial Services.

Provides transaction-related tools with:
- Read-only access (no initiation)
- PII masking
- Audit logging

CRITICAL: These tools CANNOT initiate transactions.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
import uuid
import hashlib
import random

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)

logger = logging.getLogger(__name__)

# Amount ranges for security
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


def get_transaction_status(
    customer_id: str,
    transaction_id: str,
    actor: str,
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Get transaction status (inquiry only).

    Returns masked transaction information.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        transaction_id: Transaction to query
        actor: User performing inquiry
        config: Optional config override

    Returns:
        Dict with transaction status
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Simulate transaction lookup
    hash_val = int(hashlib.md5(f"{customer_id}{transaction_id}".encode()).hexdigest()[:8], 16)
    statuses = ["completed", "completed", "pending", "processing"]
    status = statuses[hash_val % len(statuses)]
    amount = hash_val % 5000

    logger.info({
        "event": "transaction_status_tool",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "transaction_id": transaction_id,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "transaction_id": transaction_id,
        "status": status,
        "amount_range": _get_amount_range(amount),
        "type": "payment",
        "timestamp": datetime.utcnow().isoformat(),
        "audit_id": audit_id,
    }


def search_transactions(
    customer_id: str,
    account_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    transaction_type: Optional[str] = None,
    actor: str = "system",
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Search transaction history.

    Returns limited transaction history with masked amounts.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        account_id: Account to search
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        transaction_type: Optional type filter
        actor: User performing search
        config: Optional config override

    Returns:
        Dict with transaction list
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Validate date range
    if date_from and date_to:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            to_date = datetime.strptime(date_to, "%Y-%m-%d")
            if (to_date - from_date).days > 90:
                return {
                    "success": False,
                    "message": "Date range exceeds 90 days",
                    "audit_id": audit_id,
                }
        except ValueError:
            return {
                "success": False,
                "message": "Invalid date format",
                "audit_id": audit_id,
            }

    # Generate simulated transactions
    transactions = _generate_transaction_history(customer_id, 10)

    logger.info({
        "event": "transaction_search_tool",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "account_id": account_id,
        "actor": actor,
        "results_count": len(transactions),
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "transactions": transactions,
        "total_count": len(transactions),
        "audit_id": audit_id,
    }


def verify_payment(
    customer_id: str,
    payment_id: str,
    actor: str,
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Verify payment status.

    Checks if payment has been completed.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        payment_id: Payment to verify
        actor: User performing verification
        config: Optional config override

    Returns:
        Dict with verification result
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Simulate payment lookup
    hash_val = int(hashlib.md5(f"{customer_id}{payment_id}".encode()).hexdigest()[:8], 16)
    verified = hash_val % 3 != 0  # 2/3 chance of being verified

    logger.info({
        "event": "payment_verification_tool",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "payment_id": payment_id,
        "actor": actor,
        "verified": verified,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "verified": verified,
        "status": "completed" if verified else "pending",
        "payment_id": payment_id,
        "audit_id": audit_id,
    }


def get_transfer_status(
    customer_id: str,
    transfer_id: str,
    actor: str,
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Get transfer status (inquiry only).

    Returns transfer status and estimated completion.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        transfer_id: Transfer to check
        actor: User performing inquiry
        config: Optional config override

    Returns:
        Dict with transfer status
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Simulate transfer lookup
    hash_val = int(hashlib.md5(f"{customer_id}{transfer_id}".encode()).hexdigest()[:8], 16)
    statuses = ["completed", "pending", "processing"]
    status = statuses[hash_val % len(statuses)]

    logger.info({
        "event": "transfer_status_tool",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "transfer_id": transfer_id,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "transfer_id": transfer_id,
        "status": status,
        "estimated_completion": (
            datetime.utcnow() + timedelta(hours=24)
        ).strftime("%Y-%m-%d %H:00") if status != "completed" else None,
        "audit_id": audit_id,
    }


def _get_amount_range(amount: float) -> str:
    """Convert amount to range string."""
    for min_val, max_val, label in AMOUNT_RANGES:
        if min_val <= amount < max_val:
            return label
    return "Over $10,000"


def _generate_transaction_history(
    customer_id: str,
    count: int
) -> List[Dict[str, Any]]:
    """Generate simulated transaction history."""
    hash_val = int(hashlib.md5(customer_id.encode()).hexdigest()[:8], 16)
    random.seed(hash_val)

    transactions = []
    types = ["deposit", "withdrawal", "transfer", "payment"]

    for i in range(count):
        amount = random.randint(10, 1000)
        transactions.append({
            "transaction_id": f"TXN-{random.randint(100000, 999999)}",
            "type": random.choice(types),
            "status": random.choice(["completed", "completed", "pending"]),
            "amount_range": _get_amount_range(amount),
            "date": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
            "description": "Transaction",
        })

    return transactions
