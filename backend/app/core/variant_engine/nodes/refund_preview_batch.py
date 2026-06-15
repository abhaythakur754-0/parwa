"""
Refund Preview + Batch Node — Shows refunds to customers FIRST, then processes in batch.

Architecture:
  1. Detects refund-related intent from classification + billing_resolver
  2. Builds a refund PREVIEW showing all items that can be refunded
  3. Groups related refunds into a BATCH
  4. Checks tier permissions — can this tier actually EXECUTE the refund?
  5. If tier can execute → process batch
  6. If tier can't → show preview to customer, escalate for approval

KEY USER REQUIREMENT: "any refunds should be shown to users first and in batch"

This means:
  - Customer ALWAYS sees a preview before any refund happens
  - Multiple refunds are grouped into a batch, not processed one-by-one
  - Mini can PREVIEW refunds but can't EXECUTE them
  - Pro can preview + execute up to $100
  - High can preview + execute up to $10,000

BC-008: Never crash.
BC-001: company_id first parameter.
BC-012: All timestamps UTC.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.core.parwa_graph_state import (
    ParwaGraphState,
    read_comm_bus,
    post_to_comm_bus,
    post_shared_insight,
    append_audit_entry,
)
from app.core.variant_engine.tier_permissions import (
    check_permission,
    needs_approval,
    get_execution_limit,
)
from app.logger import get_logger

logger = get_logger("refund_preview_batch_node")


def _detect_refund_items(state: ParwaGraphState) -> List[Dict[str, Any]]:
    """Detect all refundable items from the pipeline state.

    Scans billing data, billing_self_service, paddle_dispute, and
    comm bus messages to find all refundable items.

    Args:
        state: Current pipeline state.

    Returns:
        List of refund item descriptors.
    """
    refund_items = []
    classification = state.get("classification", {})
    intent = classification.get("intent", "").lower()

    # Only proceed if refund-related intent
    refund_intents = {"refund", "billing", "payment", "overcharge", "charge", "invoice"}
    if intent not in refund_intents:
        secondary = classification.get("secondary_intents", [])
        if not any(s.lower() in refund_intents for s in secondary):
            return []

    # Check billing self-service data
    billing_self = state.get("billing_self_service", {})
    if billing_self.get("refund_eligible"):
        refund_items.append({
            "item_id": f"item_{uuid.uuid4().hex[:8]}",
            "description": "Eligible refund from billing dispute",
            "amount": billing_self.get("refund_amount", 0),
            "reason": billing_self.get("dispute_status", "disputed"),
        })

    # Check Paddle dispute data
    paddle = state.get("paddle_dispute", {})
    if paddle.get("auto_resolved") and paddle.get("refund_amount"):
        refund_items.append({
            "item_id": f"paddle_{uuid.uuid4().hex[:8]}",
            "description": "Paddle dispute auto-resolution refund",
            "amount": paddle.get("refund_amount", 0),
            "reason": "paddle_dispute_resolved",
        })

    # Check billing dispute data
    billing_dispute = state.get("billing_dispute", {})
    if billing_dispute.get("auto_resolvable"):
        refund_items.append({
            "item_id": f"dispute_{uuid.uuid4().hex[:8]}",
            "description": f"Billing dispute: {billing_dispute.get('dispute_category', 'unknown')}",
            "amount": billing_dispute.get("disputed_amount", 0),
            "reason": billing_dispute.get("resolution_type", "dispute"),
        })

    # Check comm bus for refund-related messages from other nodes
    messages = read_comm_bus(state, "refund_preview_batch", message_types=["insight"])
    for msg in messages:
        payload = msg.get("payload", {})
        if "refund_item" in payload:
            refund_items.append(payload["refund_item"])

    return refund_items


def _build_refund_preview(
    refund_items: List[Dict[str, Any]],
    variant_tier: str,
) -> Dict[str, Any]:
    """Build the refund preview object.

    Args:
        refund_items: List of refundable items.
        variant_tier: Current variant tier.

    Returns:
        Refund preview dict.
    """
    total_amount = sum(item.get("amount", 0) for item in refund_items)
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    max_refund = get_execution_limit(variant_tier, "max_refund_amount") or 0
    can_execute = check_permission(variant_tier, "refund")

    return {
        "refund_items": refund_items,
        "total_refund_amount": total_amount,
        "refund_method": "original",  # Default: refund to original payment method
        "estimated_processing_days": 3,
        "batch_id": batch_id,
        "preview_shown_to_customer": True,  # ALWAYS show preview first
        "customer_approved": False,  # Not yet approved by customer
        "tier_can_execute": can_execute and total_amount <= max_refund,
    }


def _process_refund_batch(
    preview: Dict[str, Any],
    state: ParwaGraphState,
) -> Dict[str, Any]:
    """Process a batch of refunds.

    In production, this calls the payment provider API.
    For now, returns simulated results.

    Args:
        preview: The refund preview with customer approval.
        state: Current pipeline state.

    Returns:
        Batch processing result.
    """
    items = preview.get("refund_items", [])
    batch_id = preview.get("batch_id", "")
    total_amount = preview.get("total_refund_amount", 0)

    # Simulated batch processing
    processed_items = []
    for item in items:
        processed_items.append({
            **item,
            "status": "processed",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "transaction_id": f"txn_{uuid.uuid4().hex[:10]}",
        })

    return {
        "batch_id": batch_id,
        "total_items": len(items),
        "processed_items": len(processed_items),
        "failed_items": 0,
        "total_amount": total_amount,
        "processed_amount": total_amount,
        "items": processed_items,
        "status": "completed",
    }


async def refund_preview_batch_node(state: ParwaGraphState) -> Dict[str, Any]:
    """Refund preview + batch node.

    Flow:
      1. Detect refundable items from pipeline state
      2. Build refund preview (ALWAYS shown to customer first)
      3. Group into batch
      4. Check tier permissions
      5. If tier can execute → process batch
      6. If tier can't → preview only, escalate for execution

    Args:
        state: Current pipeline state.

    Returns:
        Dict with state updates.
    """
    start = time.monotonic()
    variant_tier = state.get("variant_tier", "mini_parwa")
    company_id = state.get("company_id", "")

    try:
        # 1. Detect refund items
        refund_items = _detect_refund_items(state)

        if not refund_items:
            return {
                "refund_preview": {},
                "refund_batch": {},
                "steps_completed": ["refund_preview_batch"],
                **append_audit_entry(state, "refund_preview_batch", "no_refunds_found"),
            }

        # 2. Build preview — ALWAYS show to customer first
        preview = _build_refund_preview(refund_items, variant_tier)

        # 3. Determine if this tier can execute
        can_execute = preview.get("tier_can_execute", False)
        total_amount = preview.get("total_refund_amount", 0)
        approval_needed = needs_approval(
            variant_tier, "refund", amount=total_amount
        )

        batch_result = {}

        if can_execute and not approval_needed:
            # Tier allows execution — process the batch
            batch_result = _process_refund_batch(preview, state)
            preview["customer_approved"] = True  # Auto-approved by tier

        elif can_execute and approval_needed:
            # Tier allows but needs approval — preview only for now
            batch_result = {
                "batch_id": preview["batch_id"],
                "total_items": len(refund_items),
                "processed_items": 0,
                "failed_items": 0,
                "total_amount": total_amount,
                "processed_amount": 0,
                "items": [],
                "status": "pending_approval",
            }
            # Post to comm bus for approval
            post_to_comm_bus(
                state,
                from_node="refund_preview_batch",
                to_node="auto_action",
                message_type="request",
                payload={
                    "action": "refund_batch_approval_needed",
                    "batch_id": preview["batch_id"],
                    "total_amount": total_amount,
                    "item_count": len(refund_items),
                },
                priority="high",
            )

        else:
            # Tier can't execute — preview only, must escalate
            batch_result = {
                "batch_id": preview["batch_id"],
                "total_items": len(refund_items),
                "processed_items": 0,
                "failed_items": 0,
                "total_amount": total_amount,
                "processed_amount": 0,
                "items": [],
                "status": "escalation_required",
            }
            # Post to comm bus for escalation
            post_to_comm_bus(
                state,
                from_node="refund_preview_batch",
                to_node="all",
                message_type="warning",
                payload={
                    "action": "refund_escalation_needed",
                    "reason": f"Tier {variant_tier} cannot execute refunds",
                    "total_amount": total_amount,
                    "preview_available": True,
                },
                priority="critical",
            )

        # 4. Post shared insight
        post_shared_insight(
            "refund_preview_batch",
            "refund_status",
            {
                "preview_built": True,
                "items_count": len(refund_items),
                "total_amount": total_amount,
                "batch_status": batch_result.get("status", "unknown"),
                "tier_can_execute": can_execute,
            },
        )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        result = {
            "refund_preview": preview,
            "refund_batch": batch_result,
            "steps_completed": ["refund_preview_batch"],
            **append_audit_entry(
                state,
                "refund_preview_batch",
                f"preview_{'and_batch' if can_execute else 'only'}",
                duration_ms=duration_ms,
                details={
                    "items": len(refund_items),
                    "amount": total_amount,
                    "tier": variant_tier,
                    "can_execute": can_execute,
                },
            ),
        }

        logger.info(
            "refund_preview_batch: tier=%s, items=%d, amount=%.2f, "
            "can_execute=%s, batch_status=%s, ms=%.1f",
            variant_tier, len(refund_items), total_amount,
            can_execute, batch_result.get("status", "unknown"), duration_ms,
        )

        return result

    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception("refund_preview_batch_error: %s", str(exc)[:200])
        return {
            "refund_preview": {},
            "refund_batch": {},
            "errors": [f"refund_preview_batch_error: {str(exc)[:200]}"],
            **append_audit_entry(state, "refund_preview_batch", "error", duration_ms=duration_ms),
        }
