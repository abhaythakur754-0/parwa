"""
PARWA GDPR/CCPA Compliance Module
Provides utilities for handling data portability, masking PII, 
and processing user erasure (Right to be Forgotten) requests.
Depends on: logger.py (Week 1 Day 3)
"""

from typing import Any, Dict, List, Optional
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)

# Basic PII fields that must be masked or erased
PII_FIELDS = {"email", "phone", "ssn", "credit_card", "address", "last_name", "first_name"}


def mask_pii(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Masks Personally Identifiable Information (PII) in a dictionary.
    Useful for analytics or support views where PII is not strictly needed.
    """
    if not isinstance(data, dict):
        raise TypeError("Input data must be a dictionary")

    masked_data = data.copy()
    
    for key, value in masked_data.items():
        if isinstance(value, dict):
            masked_data[key] = mask_pii(value)
        elif key.lower() in PII_FIELDS:
            if value is not None:
                masked_data[key] = "[REDACTED]"
                
    return masked_data


def generate_portability_report(user_id: str, fetcher_func=None) -> Dict[str, Any]:
    """
    Generates a GDPR-compliant JSON data extraction report for a user.
    
    Args:
        user_id: The ID of the user requesting data.
        fetcher_func: Optional callable to actually fetch from DB (for testing/future).
        
    Returns:
        Structured dictionary containing all known user data.
    """
    if not user_id:
        raise ValueError("user_id must be provided")

    logger.info({"event": "portability_report_generated", "context": {"user_id": user_id}})

    # In a real scenario, fetcher_func would hit Supabase/Postgres
    raw_data = fetcher_func(user_id) if fetcher_func else {"info": "Mock data for testing"}

    return {
        "user_id": user_id,
        "metadata": {
            "report_type": "GDPR_PORTABILITY",
            "version": "1.0",
        },
        "data": raw_data
    }


def process_erasure_request(user_id: str, deleter_func=None) -> bool:
    """
    Processes a GDPR 'Right to be Forgotten' erasure request.
    
    This function creates an audit trail of the deletion mandate
    and triggers the underlying deletion hooks.
    
    Args:
        user_id: The user requesting account deletion.
        deleter_func: Optional callable to actually delete from DB (for testing/future).
        
    Returns:
        True if the request was successfully queued/processed.
    """
    if not user_id:
        raise ValueError("Invalid user_id for erasure request")
        
    if not isinstance(user_id, str):
        raise TypeError("user_id must be a string")

    # The actual deletion would happen via the DB layer
    if deleter_func:
        success = deleter_func(user_id)
        if not success:
            logger.error({"event": "erasure_failed", "context": {"user_id": user_id}})
            return False

    # Auditing the erasure is a strict legal requirement
    logger.info({
        "event": "gdpr_erasure_executed", 
        "context": {
            "user_id": user_id,
            "status": "completed",
            "action_by": "system_compliance_worker"
        }
    })
    
    return True
