"""
PARWA Audit Trail Module
Provides immutable auditing functionality for critical financial 
and agentic actions. Enforces strict JSON schemas for logging.
Depends on: logger.py (Week 1 Day 3)
"""

from typing import Any, Dict, Optional
import time
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


def log_financial_action(
    action_type: str, 
    amount: float, 
    target_id: str, 
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Logs a high-stakes financial action (refund, charge, discount).
    This log is considered immutable and critical.
    
    Args:
        action_type: Type of action (e.g., 'refund', 'charge').
        amount: Financial amount involved.
        target_id: ID of the transaction/invoice.
        user_id: ID of the user triggering the action.
        metadata: Optional extra context.
        
    Returns:
        The exact audit payload that was logged.
    """
    if amount < 0:
        raise ValueError("Amount must be positive")
        
    if not all([action_type, target_id, user_id]):
        raise ValueError("Missing required fields for financial audit")

    audit_payload = {
        "event": "financial_audit",
        "audit_type": "transaction",
        "context": {
            "action": action_type,
            "amount": amount,
            "target_id": target_id,
            "user_id": user_id,
            "timestamp_utc": time.time(),
            "metadata": metadata or {}
        }
    }
    
    # In production, this would also write to an append-only ledger DB
    logger.info(audit_payload)
    
    return audit_payload


def log_agent_decision(
    prompt_hash: str, 
    selected_action: str, 
    confidence_score: float,
    agent_id: str = "primary_router"
) -> Dict[str, Any]:
    """
    Logs an autonomous decision made by the AI LLM logic.
    Used for the Quality Coach and SLA verification.
    
    Args:
        prompt_hash: SHA256 hash or unique ID of the input prompt.
        selected_action: The routing or logic decision made.
        confidence_score: Float between 0 and 1 indicating LLM certainty.
        agent_id: Which internal agent made the call.
        
    Returns:
        The exact audit payload that was logged.
    """
    if not (0.0 <= confidence_score <= 1.0):
        raise ValueError("Confidence score must be between 0.0 and 1.0")

    if not all([prompt_hash, selected_action, agent_id]):
        raise ValueError("Missing required fields for agent audit")

    audit_payload = {
        "event": "agent_decision_audit",
        "audit_type": "ai_logic",
        "context": {
            "prompt_hash": prompt_hash,
            "selected_action": selected_action,
            "confidence_score": confidence_score,
            "agent_id": agent_id,
            "timestamp_utc": time.time()
        }
    }
    
    logger.info(audit_payload)
    return audit_payload
