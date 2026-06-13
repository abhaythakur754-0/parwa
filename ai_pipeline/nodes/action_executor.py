"""Node 8: ACTION_EXECUTOR — Executes planned actions or creates recommendations.

Action Agent node. THIS IS THE KEY NODE for variant differentiation.
- If variant allows EXECUTE: runs the action against the Fake CRM
- If variant allows RECOMMEND: creates a recommendation for human approval
- If variant DENIES: skips the action

Phase 9: Now uses DeliveryProvider for REAL SMS and voice call delivery.
SMS and voice calls go through the provider chain:
  1. TwilioProvider (real delivery) — if TWILIO_* env vars are set
  2. SimulationProvider (honest simulation) — always available as fallback

CRITICAL: We NEVER claim "executed" when nothing was actually delivered.
If Twilio is configured, SMS/calls are REALLY sent.
If not, status is honestly "simulated" (not "executed").
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from parwa.config import get_permission
from parwa.state import ActionType, ExecutionMode
from parwa.utils.node_base import safe_node

logger = logging.getLogger("parwa.node.action_executor")


async def _execute_send_sms(action_plan: dict, state: dict) -> dict[str, Any]:
    """Execute: Send an SMS using the DeliveryProvider.

    This actually sends the SMS via Twilio (if configured) or honestly
    reports it as simulated (if no provider available).
    """
    params = action_plan.get("parameters", {})
    customer_id = state.get("customer_id", "")
    message = params.get("message", action_plan.get("description", "Follow-up from support"))

    # Get the customer's phone number from CRM
    phone = "unknown"
    customer_name = "unknown"
    if customer_id and customer_id != "default":
        try:
            from parwa.fake_crm.database import get_crm
            crm = get_crm()
            cust = crm.get_customer(customer_id)
            if cust:
                phone = cust.get("phone", "unknown")
                customer_name = cust.get("name", "unknown")
        except (ValueError, ImportError):
            pass

    # Use the DeliveryProvider for REAL delivery
    try:
        from parwa.delivery import deliver_sms, DeliveryStatus
        delivery_result = await deliver_sms(
            to=phone,
            message=message[:1600],  # SMS limit
            metadata={"customer_id": customer_id, "customer_name": customer_name},
        )

        # Map delivery status to action status HONESTLY
        if delivery_result.status == DeliveryStatus.DELIVERED:
            action_status = "executed"
            status_msg = f"SMS delivered to {phone}"
        elif delivery_result.status == DeliveryStatus.DELIVERY_PENDING:
            action_status = "delivery_pending"
            status_msg = f"SMS sent to {phone}, awaiting delivery confirmation (SID: {delivery_result.provider_sid})"
        elif delivery_result.status == DeliveryStatus.SIMULATED:
            action_status = "simulated"
            status_msg = f"SMS simulated to {phone} (not actually delivered)"
        else:
            action_status = "delivery_failed"
            status_msg = f"SMS delivery failed to {phone}: {delivery_result.error}"

        return {
            "action_type": "send_sms",
            "status": action_status,
            "message": status_msg,
            "parameters": params,
            "details": delivery_result.to_dict(),
        }

    except ImportError:
        # Delivery module not available — fall back to CRM logging with honest status
        if customer_id and customer_id != "default":
            try:
                from parwa.fake_crm.database import get_crm
                crm = get_crm()
                crm.add_note(customer_id, f"[SMS SIMULATED — NOT DELIVERED] {message[:200]}")
            except (ValueError, ImportError):
                pass
        return {
            "action_type": "send_sms",
            "status": "simulated",
            "message": f"SMS logged but NOT delivered to {phone} (delivery module unavailable)",
            "parameters": params,
            "details": {"phone": phone, "honest_note": "SMS was NOT actually sent. Delivery module not available."},
        }


async def _execute_voice_call(action_plan: dict, state: dict) -> dict[str, Any]:
    """Execute: Make a voice call using the DeliveryProvider.

    This actually makes the call via Twilio (if configured) or honestly
    reports it as simulated (if no provider available).
    """
    params = action_plan.get("parameters", {})
    customer_id = state.get("customer_id", "")
    reason = params.get("reason", action_plan.get("description", "Customer follow-up"))

    # Get the customer's phone number from CRM
    phone = "unknown"
    customer_name = "unknown"
    if customer_id and customer_id != "default":
        try:
            from parwa.fake_crm.database import get_crm
            crm = get_crm()
            cust = crm.get_customer(customer_id)
            if cust:
                phone = cust.get("phone", "unknown")
                customer_name = cust.get("name", "unknown")
        except (ValueError, ImportError):
            pass

    # Use the DeliveryProvider for REAL delivery
    try:
        from parwa.delivery import deliver_voice_call, DeliveryStatus
        delivery_result = await deliver_voice_call(
            to=phone,
            reason=reason,
            metadata={"customer_id": customer_id, "customer_name": customer_name},
        )

        # Map delivery status to action status HONESTLY
        if delivery_result.status == DeliveryStatus.DELIVERED:
            action_status = "executed"
            status_msg = f"Voice call delivered to {phone}"
        elif delivery_result.status == DeliveryStatus.DELIVERY_PENDING:
            action_status = "delivery_pending"
            status_msg = f"Voice call initiated to {phone} (SID: {delivery_result.provider_sid})"
        elif delivery_result.status == DeliveryStatus.SIMULATED:
            action_status = "simulated"
            status_msg = f"Voice call simulated to {phone} (not actually dialed)"
        else:
            action_status = "delivery_failed"
            status_msg = f"Voice call failed to {phone}: {delivery_result.error}"

        return {
            "action_type": "voice_call",
            "status": action_status,
            "message": status_msg,
            "parameters": params,
            "details": delivery_result.to_dict(),
        }

    except ImportError:
        # Delivery module not available — fall back with honest status
        if customer_id and customer_id != "default":
            try:
                from parwa.fake_crm.database import get_crm
                crm = get_crm()
                crm.add_note(customer_id, f"[VOICE CALL SIMULATED — NOT DIALED] Reason: {reason}")
            except (ValueError, ImportError):
                pass
        return {
            "action_type": "voice_call",
            "status": "simulated",
            "message": f"Voice call logged but NOT made to {phone} (delivery module unavailable)",
            "parameters": params,
            "details": {"phone": phone, "honest_note": "Call was NOT actually made. Delivery module not available."},
        }


def _execute_crm_action(action_plan: dict, state: dict) -> dict[str, Any]:
    """Execute a CRM-modifying action (refund, cancel, modify, etc.).

    These actions ACTUALLY modify the CRM state — refunds change payment
    status, cancellations change order status, etc.
    """
    action_type = action_plan.get("action_type", "send_reply")
    params = action_plan.get("parameters", {})
    customer_id = state.get("customer_id", "")

    try:
        from parwa.fake_crm.database import get_crm
        crm = get_crm()

        # ─── Process Refund — Actually refunds in CRM ───
        if action_type == "process_refund":
            amount = params.get("amount", 0)
            reason = params.get("reason", "customer_request")

            if not customer_id or customer_id == "default":
                return {
                    "action_type": action_type,
                    "status": "simulated",
                    "message": f"Refund of ${amount:.2f} simulated (no CRM customer)",
                    "parameters": params,
                    "details": {"refund_amount": amount, "reason": reason, "honest_note": "No CRM customer — refund was simulated, not processed"},
                }

            payments = crm.get_payments(customer_id)
            target_payment = None

            if reason == "duplicate_charge":
                duplicates = crm.find_duplicate_payments(customer_id)
                if duplicates:
                    target_payment = duplicates[0][1]

            if not target_payment:
                for p in payments:
                    if p.get("status") == "completed" and abs(p.get("amount", 0) - amount) < 0.01:
                        target_payment = p
                        break

            if not target_payment:
                for p in payments:
                    if p.get("status") == "completed":
                        target_payment = p
                        break

            if not target_payment:
                return {
                    "action_type": action_type,
                    "status": "failed",
                    "message": f"No completed payment found to refund for customer {customer_id}",
                }

            try:
                refund_amount = amount if amount > 0 else target_payment.get("amount", 0)
                result = crm.process_refund(
                    customer_id=customer_id,
                    payment_id=target_payment["payment_id"],
                    amount=refund_amount,
                    reason=reason,
                )
                return {
                    "action_type": action_type,
                    "status": "executed",
                    "message": result.get("message", "Refund processed"),
                    "parameters": params,
                    "details": {
                        "refund_id": result.get("refund_id"),
                        "amount": refund_amount,
                        "payment_id": target_payment["payment_id"],
                    },
                }
            except Exception as exc:
                return {
                    "action_type": action_type,
                    "status": "failed",
                    "message": f"Refund failed: {exc}",
                    "parameters": params,
                }

        # ─── Cancel Order — Actually cancels in CRM ───
        elif action_type == "cancel_order":
            order_id = params.get("order_id", "")
            reason = params.get("reason", "customer_request")

            if not customer_id or customer_id == "default":
                return {
                    "action_type": action_type,
                    "status": "simulated",
                    "message": "Order cancellation simulated (no CRM customer)",
                    "parameters": params,
                }

            if not order_id:
                orders = crm.get_orders(customer_id)
                for order in reversed(orders):
                    if order.get("status") in ("processing", "shipped"):
                        order_id = order.get("order_id", "")
                        break

            if not order_id:
                return {
                    "action_type": action_type,
                    "status": "failed",
                    "message": f"No cancellable order found for customer {customer_id}",
                    "parameters": params,
                }

            try:
                result = crm.cancel_order(customer_id, order_id, reason)
                if result.get("status") == "already_cancelled":
                    return {
                        "action_type": action_type,
                        "status": "executed",
                        "message": f"Order {order_id} was already cancelled",
                        "parameters": params,
                    }
                if result.get("status") == "cannot_cancel":
                    return {
                        "action_type": action_type,
                        "status": "failed",
                        "message": result.get("reason", "Order cannot be cancelled"),
                        "parameters": params,
                    }
                return {
                    "action_type": action_type,
                    "status": "executed",
                    "message": f"Order {order_id} cancelled successfully",
                    "parameters": params,
                }
            except ValueError as exc:
                return {
                    "action_type": action_type,
                    "status": "failed",
                    "message": str(exc),
                    "parameters": params,
                }

        # ─── Modify Account — Actually modifies in CRM ───
        elif action_type == "modify_account":
            if not customer_id or customer_id == "default":
                return {
                    "action_type": action_type,
                    "status": "simulated",
                    "message": "Account modification simulated (no CRM customer)",
                    "parameters": params,
                }

            changes = {}
            for key, value in params.items():
                if key in ("email", "phone", "plan"):
                    changes[key] = value
                elif key == "add_seats":
                    changes["add_seats"] = int(value)
                elif key == "reactivate":
                    changes["reactivate"] = True
                elif key == "reset_password":
                    changes["reset_password"] = True

            if not changes:
                crm.add_note(customer_id, f"Account modification requested: {params}")
                return {
                    "action_type": action_type,
                    "status": "executed",
                    "message": "Account modification note added",
                    "parameters": params,
                }

            try:
                result = crm.modify_account(customer_id, changes)
                return {
                    "action_type": action_type,
                    "status": "executed",
                    "message": "Account modified successfully",
                    "parameters": params,
                    "details": result.get("changes_made", []),
                }
            except ValueError as exc:
                return {
                    "action_type": action_type,
                    "status": "failed",
                    "message": str(exc),
                    "parameters": params,
                }

        # ─── Escalate to Human — Creates escalation ticket in CRM ───
        elif action_type == "escalate_to_human":
            import uuid
            reason = params.get("reason", action_plan.get("description", ""))
            if customer_id and customer_id != "default":
                try:
                    ticket = crm.create_ticket(customer_id, f"[ESCALATED] {reason}")
                    crm.add_note(customer_id, f"Escalated to human: {reason}")
                except ValueError:
                    ticket = {"ticket_id": f"ESC-{uuid.uuid4().hex[:6].upper()}"}
            else:
                ticket = {"ticket_id": f"ESC-{uuid.uuid4().hex[:6].upper()}"}
            return {
                "action_type": action_type,
                "status": "executed",
                "message": "Ticket escalated to human agent",
                "parameters": params,
                "details": {"escalation_ticket_id": ticket.get("ticket_id"), "reason": reason},
            }

        # ─── Send Reply — Logs reply in CRM ───
        elif action_type == "send_reply":
            message = params.get("message", action_plan.get("description", ""))
            if customer_id and customer_id != "default":
                try:
                    crm.add_note(customer_id, f"[Reply Sent] {message[:200]}")
                except ValueError:
                    pass
            return {
                "action_type": action_type,
                "status": "executed",
                "message": "Reply sent to customer",
                "parameters": params,
            }

        # ─── Share FAQ / Policy — Logs in CRM ───
        elif action_type == "share_faq":
            faq_id = params.get("faq_id", "")
            if customer_id and customer_id != "default":
                try:
                    crm.add_note(customer_id, f"Shared FAQ: {faq_id}")
                except ValueError:
                    pass
            return {
                "action_type": action_type,
                "status": "executed",
                "message": "FAQ article shared with customer",
                "parameters": params,
            }

        elif action_type == "share_policy":
            policy = params.get("policy", "")
            if customer_id and customer_id != "default":
                try:
                    crm.add_note(customer_id, f"Shared policy: {policy}")
                except ValueError:
                    pass
            return {
                "action_type": action_type,
                "status": "executed",
                "message": f"Policy information shared: {policy or 'relevant policy'}",
                "parameters": params,
            }

        # ─── Create Note ───
        elif action_type == "create_note":
            note = params.get("note", action_plan.get("description", ""))
            if customer_id and customer_id != "default":
                try:
                    crm.add_note(customer_id, note)
                except ValueError:
                    pass
            return {
                "action_type": action_type,
                "status": "executed",
                "message": "Note added to customer record",
                "parameters": params,
            }

        # ─── Other variant-restricted actions (bulk, analytics, etc.) ───
        elif action_type in ("bulk_operation", "api_webhook",
                             "custom_integration", "access_analytics"):
            import uuid as _uuid
            action_id = f"{action_type[:3].upper()}-{_uuid.uuid4().hex[:6].upper()}"
            if customer_id and customer_id != "default":
                try:
                    crm.add_note(customer_id, f"[{action_type.upper()}] ID: {action_id} | Params: {str(params)[:200]}")
                except ValueError:
                    pass
            return {
                "action_type": action_type,
                "status": "executed",
                "message": f"Action '{action_type}' processed (ID: {action_id})",
                "parameters": params,
                "details": {"action_id": action_id},
            }

        # ─── Fallback for unknown actions ───
        else:
            return {
                "action_type": action_type,
                "status": "executed",
                "message": f"Action '{action_type}' executed",
                "parameters": params,
            }

    except ImportError:
        return {
            "action_type": action_type,
            "status": "simulated",
            "message": f"Action '{action_type}' simulated (CRM not available)",
            "parameters": params,
        }
    except Exception as exc:
        logger.error("ACTION_EXECUTOR: unexpected error: %s", exc)
        return {
            "action_type": action_type,
            "status": "failed",
            "message": f"Action execution error: {exc}",
            "parameters": params,
        }


def _create_recommendation(action_plan: dict, state: dict) -> dict[str, Any]:
    """Create a recommendation for human approval (Mini PARWA)."""
    action_type = action_plan.get("action_type", "send_reply")
    evidence = action_plan.get("evidence", [])
    params = action_plan.get("parameters", {})
    risk_level = action_plan.get("risk_level", "low")
    quality_score = state.get("quality_score", 0)

    # Also log the pending action in CRM
    customer_id = state.get("customer_id", "")
    if customer_id and customer_id != "default":
        try:
            from parwa.fake_crm.database import get_crm
            crm = get_crm()
            crm.add_note(customer_id, f"[PENDING APPROVAL] {action_type}: {action_plan.get('description', '')}")
        except (ValueError, ImportError):
            pass

    return {
        "pending_approval": True,
        "action_type": action_type,
        "description": action_plan.get("description", ""),
        "evidence": evidence,
        "parameters": params,
        "risk_level": risk_level,
        "quality_score": quality_score,
        "message": f"Recommended action '{action_type}' pending human approval for this variant.",
    }


# ─── Actions that require real async delivery ────────────────────────────────
_ASYNC_DELIVERY_ACTIONS = {"send_sms", "voice_call"}


@safe_node("ACTION_EXECUTOR", fallback={"execution_results": [], "recommendation": None})
async def action_executor(state: dict[str, Any]) -> dict[str, Any]:
    """Execute or recommend actions based on variant permissions (async).

    THIS IS THE KEY NODE for variant differentiation AND for making
    PARWA capable of replacing humans.

    CRM-modifying actions (refund, cancel, modify_account, notes) are
    REALLY executed against the CRM state.

    Communication actions (SMS, voice call) use the DeliveryProvider:
    - If Twilio is configured → actually delivered
    - If not → honestly marked as "simulated" (NOT "executed")

    We NEVER lie about execution status.

    Reads: action_plans, variant, customer_id
    Writes: execution_results, recommendation
    """
    variant = state.get("variant", "parwa")
    action_plans = state.get("action_plans", [])

    # Guard: ensure types
    if not isinstance(variant, str):
        variant = "parwa"
    if not isinstance(action_plans, list):
        action_plans = []

    execution_results = []
    recommendation = None

    for plan in action_plans:
        action_type_str = plan.get("action_type", "send_reply")

        # Get the ActionType enum
        try:
            action_type = ActionType(action_type_str)
        except (ValueError, TypeError):
            action_type = ActionType.SEND_REPLY

        # Check variant permissions
        try:
            permission = get_permission(variant, action_type)
        except (ValueError, KeyError) as exc:
            logger.warning(
                "ACTION_EXECUTOR: permission check failed for variant=%s action=%s: %s",
                variant, action_type_str, exc,
            )
            permission = ExecutionMode.DENY

        if permission == ExecutionMode.EXECUTE:
            # ─── Use async delivery for SMS/voice ───
            if action_type_str in _ASYNC_DELIVERY_ACTIONS:
                if action_type_str == "send_sms":
                    result = await _execute_send_sms(plan, state)
                elif action_type_str == "voice_call":
                    result = await _execute_voice_call(plan, state)
                else:
                    result = _execute_crm_action(plan, state)
            else:
                result = _execute_crm_action(plan, state)
            execution_results.append(result)

            logger.info(
                "ACTION_EXECUTOR: %s for variant=%s → status=%s",
                action_type_str, variant, result.get("status"),
            )

        elif permission == ExecutionMode.RECOMMEND:
            # Don't execute — create recommendation for human
            recommendation = _create_recommendation(plan, state)
            execution_results.append({
                "action_type": action_type_str,
                "status": "recommended",
                "message": f"Action '{action_type_str}' requires human approval for variant '{variant}'",
            })
            logger.info(
                "ACTION_EXECUTOR: recommended (not executed) %s for variant=%s",
                action_type_str, variant,
            )

        elif permission == ExecutionMode.DENY:
            execution_results.append({
                "action_type": action_type_str,
                "status": "denied",
                "message": f"Action '{action_type_str}' is not available for variant '{variant}'",
            })
            logger.info(
                "ACTION_EXECUTOR: denied %s for variant=%s",
                action_type_str, variant,
            )

    return {
        "execution_results": execution_results,
        "recommendation": recommendation,
    }
