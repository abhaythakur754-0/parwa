"""
Refund Agent Node — Group 4 Domain Agent (Refund / Returns / Cancellations)

Specialized domain agent for handling refund processing, returns,
and cancellation requests. Extends BaseDomainAgent with order lookup
and refund eligibility check capabilities.

State Contract:
  Reads:  pii_redacted_message, intent, tenant_id, variant_tier,
          sentiment_score, technique_stack, signals_extracted,
          conversation_id, gsd_state, context_health
  Writes: agent_response, agent_confidence, proposed_action,
          action_type, agent_reasoning, agent_type,
          order_lookup_result, refund_eligibility

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import importlib

from app.core.langgraph.config import get_variant_config
from app.logger import get_logger

logger = get_logger("node_refund_agent")

# Lazy import of BaseDomainAgent — module name starts with digit so
# we use importlib instead of a standard import statement.
_base_agent_module = importlib.import_module(
    "app.core.langgraph.nodes.04_base_domain_agent"
)
BaseDomainAgent = _base_agent_module.BaseDomainAgent


# ──────────────────────────────────────────────────────────────
# Refund Agent Implementation
# ──────────────────────────────────────────────────────────────


class RefundAgent(BaseDomainAgent):
    """
    Refund Domain Agent — handles refund processing, returns,
    and cancellation requests.

    Specializes the base domain agent with:
      - Refund-oriented system prompt
      - Order lookup via react_tools.order_tool
      - Refund eligibility checking
      - Partial/full refund calculation

    This agent is available on Pro + High tiers ONLY (not mini).
    Tier check is performed in the node function; mini-tier requests
    fall back to a safe informational response.
    """

    agent_name: str = "refund"

    system_prompt: str = (
        "You are a knowledgeable and empathetic refund support agent. "
        "Your goal is to help customers with refund requests, returns, "
        "and cancellations efficiently and fairly. Always verify order "
        "details and check refund eligibility before proposing any "
        "monetary action. Calculate partial or full refunds accurately "
        "based on the return policy and order status. If a refund is "
        "not possible, explain the reasons clearly and offer alternative "
        "solutions. Maintain a calm, understanding tone — customers "
        "requesting refunds are often frustrated. Escalate to a human "
        "when policy limits are reached or when legal threats are detected."
    )

    domain_knowledge: Dict[str, Any] = {
        "domains": [
            "refund_processing",
            "return_requests",
            "cancellation_handling",
            "order_lookup",
            "refund_eligibility",
        ],
        "proposed_actions": {
            "respond": "informational",
            "refund": "monetary",
            "escalate": "escalation",
        },
        "refund_policy": {
            "full_refund_window_days": 30,
            "partial_refund_window_days": 60,
            "no_refund_after_days": 90,
            "restocking_fee_percent": 15,
            "digital_items_refundable": False,
        },
        "max_order_lookup_retries": 3,
        "require_order_verification": True,
    }

    # ── Tier availability ─────────────────────────────────────

    _AVAILABLE_TIERS = {"pro", "high"}

    @classmethod
    def is_available_for_tier(cls, variant_tier: str) -> bool:
        """
        Check if this agent is available for the given variant tier.

        Refund agent is only available on Pro and High tiers.

        Args:
            variant_tier: Variant tier string.

        Returns:
            True if available for this tier.
        """
        return variant_tier in cls._AVAILABLE_TIERS

    # ── Order lookup ──────────────────────────────────────────

    def _lookup_order(
        self,
        message: str,
        tenant_id: str,
        signals: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Look up order details using the order_tool.

        Uses app.core.react_tools.order_tool for order lookups.
        Falls back to empty results if the tool is unavailable.

        Args:
            message: The PII-redacted message to extract order info from.
            tenant_id: Tenant identifier (BC-001).
            signals: Extracted query signals (may contain order_id).

        Returns:
            Dict with 'order_found', 'order_details', 'order_id'.
        """
        try:
            from app.core.react_tools.order_tool import lookup_order  # type: ignore[import-untyped]

            order_id = signals.get("order_id", "") if signals else ""

            result = lookup_order(
                query=message,
                tenant_id=tenant_id,
                order_id=order_id,
            )

            order_found = result.get("found", False)
            order_details = result.get("details", {})

            logger.info(
                "order_lookup_success",
                tenant_id=tenant_id,
                order_found=order_found,
                order_id=order_id or result.get("order_id", ""),
            )

            return {
                "order_found": order_found,
                "order_details": order_details,
                "order_id": order_id or result.get("order_id", ""),
            }

        except ImportError:
            logger.warning(
                "order_tool_unavailable",
                tenant_id=tenant_id,
            )
        except Exception as order_exc:
            logger.warning(
                "order_lookup_error",
                tenant_id=tenant_id,
                error=str(order_exc),
            )

        # Fallback: no order info available
        return {
            "order_found": False,
            "order_details": {},
            "order_id": "",
        }

    # ── Refund eligibility ────────────────────────────────────

    def _check_refund_eligibility(
        self,
        order_details: Dict[str, Any],
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Check refund eligibility based on order details and policy.

        Applies the refund policy from domain_knowledge to determine
        whether a full, partial, or no refund is available.

        Args:
            order_details: Order details from lookup.
            tenant_id: Tenant identifier (BC-001).

        Returns:
            Dict with 'eligible', 'refund_type', 'refund_amount', 'reason'.
        """
        try:
            policy = self.domain_knowledge.get("refund_policy", {})

            # If no order details, cannot determine eligibility
            if not order_details:
                return {
                    "eligible": False,
                    "refund_type": "none",
                    "refund_amount": 0.0,
                    "reason": "Order details not available for eligibility check.",
                }

            days_since_purchase = order_details.get("days_since_purchase", 999)
            order_total = order_details.get("total", 0.0)
            is_digital = order_details.get("is_digital", False)

            # Digital items not refundable
            if is_digital and not policy.get("digital_items_refundable", False):
                return {
                    "eligible": False,
                    "refund_type": "none",
                    "refund_amount": 0.0,
                    "reason": "Digital items are not eligible for refunds.",
                }

            full_window = policy.get("full_refund_window_days", 30)
            partial_window = policy.get("partial_refund_window_days", 60)
            no_refund_after = policy.get("no_refund_after_days", 90)
            restocking_fee = policy.get("restocking_fee_percent", 15)

            if days_since_purchase <= full_window:
                return {
                    "eligible": True,
                    "refund_type": "full",
                    "refund_amount": order_total,
                    "reason": f"Within {full_window}-day full refund window.",
                }
            elif days_since_purchase <= partial_window:
                refund_amount = order_total * (1 - restocking_fee / 100)
                return {
                    "eligible": True,
                    "refund_type": "partial",
                    "refund_amount": round(refund_amount, 2),
                    "reason": (
                        f"Within {partial_window}-day partial refund window. "
                        f"{restocking_fee}% restocking fee applies."
                    ),
                }
            elif days_since_purchase <= no_refund_after:
                return {
                    "eligible": False,
                    "refund_type": "none",
                    "refund_amount": 0.0,
                    "reason": (
                        f"Outside refund window ({days_since_purchase} days "
                        f"since purchase). Maximum {no_refund_after} days."
                    ),
                }
            else:
                return {
                    "eligible": False,
                    "refund_type": "none",
                    "refund_amount": 0.0,
                    "reason": "Refund period has expired.",
                }

        except Exception as elig_exc:
            logger.warning(
                "refund_eligibility_check_error",
                tenant_id=tenant_id,
                error=str(elig_exc),
            )
            return {
                "eligible": False,
                "refund_type": "none",
                "refund_amount": 0.0,
                "reason": f"Could not determine eligibility: {elig_exc}",
            }

    # ── Extra state update ────────────────────────────────────

    def _extra_state_update(
        self,
        state: Dict[str, Any],
        generation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add refund-specific fields to the state update.

        Extends the base state update with:
          - order_lookup_result: Result of order lookup
          - refund_eligibility: Refund eligibility assessment

        Args:
            state: Current ParwaGraphState dict.
            generation_result: Output from _generate_response().

        Returns:
            Dict with additional refund state fields.
        """
        tenant_id = state.get("tenant_id", "unknown")
        message = state.get("pii_redacted_message", "") or state.get("message", "")
        signals = state.get("signals_extracted", {})

        # Perform order lookup
        order_result = self._lookup_order(
            message=message,
            tenant_id=tenant_id,
            signals=signals,
        )

        # Check refund eligibility if order was found
        if order_result.get("order_found"):
            eligibility = self._check_refund_eligibility(
                order_details=order_result.get("order_details", {}),
                tenant_id=tenant_id,
            )
        else:
            eligibility = {
                "eligible": False,
                "refund_type": "none",
                "refund_amount": 0.0,
                "reason": "Order not found — cannot assess eligibility.",
            }

        return {
            "order_lookup_result": order_result,
            "refund_eligibility": eligibility,
        }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def refund_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Refund Agent Node — LangGraph agent node.

    Handles refund processing, returns, and cancellation requests.
    Uses order lookup to verify order details and checks refund
    eligibility before proposing monetary actions.

    This agent is available on Pro + High tiers ONLY. For mini-tier
    requests, returns a safe informational response directing the
    customer to alternative support channels.

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with domain agent output fields
        plus order lookup and refund eligibility fields.
    """
    tenant_id = state.get("tenant_id", "unknown")
    variant_tier = state.get("variant_tier", "mini")

    logger.info(
        "refund_agent_node_start",
        tenant_id=tenant_id,
        intent=state.get("intent", "unknown"),
        variant_tier=variant_tier,
    )

    try:
        # ── Tier gate: Refund agent not available on mini ────────
        if not RefundAgent.is_available_for_tier(variant_tier):
            logger.info(
                "refund_agent_tier_unavailable",
                tenant_id=tenant_id,
                variant_tier=variant_tier,
                message="Refund agent requires Pro or High tier",
            )
            return {
                "agent_response": (
                    "I understand you're looking for help with a refund. "
                    "Our refund specialist team is available on our Pro and "
                    "High service plans. Let me connect you with a support "
                    "agent who can assist you further."
                ),
                "agent_confidence": 0.5,
                "proposed_action": "escalate",
                "action_type": "escalation",
                "agent_reasoning": (
                    f"Refund agent not available for tier '{variant_tier}'. "
                    "Escalating to human support."
                ),
                "agent_type": "refund",
                "order_lookup_result": {
                    "order_found": False,
                    "order_details": {},
                    "order_id": "",
                },
                "refund_eligibility": {
                    "eligible": False,
                    "refund_type": "none",
                    "refund_amount": 0.0,
                    "reason": "Agent not available for this tier.",
                },
            }

        agent = RefundAgent()
        return agent.run(state)
    except Exception as exc:
        logger.error(
            "refund_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            "agent_response": "",
            "agent_confidence": 0.0,
            "proposed_action": "respond",
            "action_type": "informational",
            "agent_reasoning": f"Refund agent fatal error: {exc}",
            "agent_type": "refund",
            "order_lookup_result": {
                "order_found": False,
                "order_details": {},
                "order_id": "",
            },
            "refund_eligibility": {
                "eligible": False,
                "refund_type": "none",
                "refund_amount": 0.0,
                "reason": f"Agent error: {exc}",
            },
            "errors": [f"Refund agent fatal error: {exc}"],
        }
