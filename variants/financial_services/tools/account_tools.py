"""
Account Tools for Financial Services.

Provides account-related tools with:
- PII masking
- Audit logging
- Security validation

All tools generate audit trail entries per SOX requirements.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import uuid

from variants.financial_services.config import (
    FinancialServicesConfig,
    get_financial_services_config,
)

logger = logging.getLogger(__name__)


def get_account_summary(
    customer_id: str,
    account_id: str,
    actor: str,
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Get masked account summary.

    Returns limited account info with PII masked for security.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        account_id: Account to query
        actor: User performing the action
        config: Optional config override

    Returns:
        Dict with masked account summary
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Mask account number
    masked_number = f"XXXX-XXXX-XXXX-{account_id[-4:]}" if len(account_id) >= 4 else account_id

    # Log audit entry
    logger.info({
        "event": "account_summary_tool",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "account_id": masked_number,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "account_id": account_id,
        "masked_account_number": masked_number,
        "account_type": "checking",  # Simulated
        "status": "active",
        "balance_range": "$1,000 - $5,000",  # Never show exact balance
        "currency": "USD",
        "audit_id": audit_id,
    }


def verify_account_status(
    customer_id: str,
    account_id: str,
    actor: str,
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Verify account status.

    Checks if account is active and in good standing.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        account_id: Account to verify
        actor: User performing verification
        config: Optional config override

    Returns:
        Dict with verification result
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    logger.info({
        "event": "account_status_verification",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "account_id": account_id,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "verified": True,
        "status": "active",
        "has_alerts": False,
        "requires_verification": False,
        "audit_id": audit_id,
    }


def request_statement(
    customer_id: str,
    account_id: str,
    statement_period: str,
    actor: str,
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Request account statement.

    Creates statement request to be sent to verified email.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        account_id: Account for statement
        statement_period: Period (e.g., "2024-01", "last_3_months")
        actor: User making request
        config: Optional config override

    Returns:
        Dict with request status
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Validate period
    import re
    valid_period = (
        statement_period in ["last_3_months", "last_6_months", "last_year"] or
        re.match(r"^\d{4}-\d{2}$", statement_period) is not None
    )

    if not valid_period:
        return {
            "success": False,
            "message": "Invalid statement period format",
            "audit_id": audit_id,
        }

    logger.info({
        "event": "statement_request_tool",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "account_id": account_id,
        "period": statement_period,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "request_id": f"STMT-{audit_id[-8:]}",
        "message": "Statement will be sent to verified email",
        "period": statement_period,
        "audit_id": audit_id,
    }


def check_account_eligibility(
    customer_id: str,
    account_id: str,
    feature: str,
    actor: str,
    config: Optional[FinancialServicesConfig] = None
) -> Dict[str, Any]:
    """
    Check account eligibility for features.

    Verifies if account is eligible for specific features.
    Generates audit trail entry.

    Args:
        customer_id: Customer identifier
        account_id: Account to check
        feature: Feature to check eligibility for
        actor: User performing check
        config: Optional config override

    Returns:
        Dict with eligibility result
    """
    config = config or get_financial_services_config()
    audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"

    # Basic eligibility check
    eligible_features = ["balance_inquiry", "statement", "transfer_inquiry"]
    eligible = feature in eligible_features

    logger.info({
        "event": "eligibility_check_tool",
        "audit_id": audit_id,
        "customer_id": customer_id,
        "account_id": account_id,
        "feature": feature,
        "eligible": eligible,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return {
        "success": True,
        "eligible": eligible,
        "feature": feature,
        "reason": "Account in good standing" if eligible else "Feature not available",
        "audit_id": audit_id,
    }
