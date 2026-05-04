"""
Billing Agent Node — Group 4 Domain Agent (Billing / Payments / Invoices / Subscriptions)

Specialized domain agent for handling billing inquiries, payment issues,
invoice requests, and subscription management. Extends BaseDomainAgent
with billing lookup capabilities via the billing_tool.

State Contract:
  Reads:  pii_redacted_message, intent, tenant_id, variant_tier,
          sentiment_score, technique_stack, signals_extracted,
          conversation_id, gsd_state, context_health
  Writes: agent_response, agent_confidence, proposed_action,
          action_type, agent_reasoning, agent_type,
          billing_lookup_result, payment_methods

BC-008: Never crash — returns safe defaults on any failure.
BC-001: All log entries include tenant_id for multi-tenant isolation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import importlib

from app.core.langgraph.config import get_variant_config
from app.logger import get_logger

logger = get_logger("node_billing_agent")

# Lazy import of BaseDomainAgent — module name starts with digit so
# we use importlib instead of a standard import statement.
_base_agent_module = importlib.import_module(
    "app.core.langgraph.nodes.04_base_domain_agent"
)
BaseDomainAgent = _base_agent_module.BaseDomainAgent


# ──────────────────────────────────────────────────────────────
# Billing Agent Implementation
# ──────────────────────────────────────────────────────────────


class BillingAgent(BaseDomainAgent):
    """
    Billing Domain Agent — handles billing inquiries, payment issues,
    invoice requests, and subscription management.

    Specializes the base domain agent with:
      - Billing-oriented system prompt
      - Billing lookup via react_tools.billing_tool
      - Invoice retrieval and payment method verification
      - Subscription status checking

    This agent is available on ALL tiers (mini, pro, high).
    """

    agent_name: str = "billing"

    system_prompt: str = (
        "You are a detail-oriented and transparent billing support agent. "
        "Your goal is to help customers with billing inquiries, payment "
        "issues, invoice requests, and subscription management. Always "
        "verify account and billing details before making any changes or "
        "proposing monetary actions. Explain charges clearly and break "
        "down invoices line-by-line when requested. When applying "
        "discounts or waiving fees, clearly state the reason and amount. "
        "For subscription changes, explain the proration and effective "
        "dates. Escalate to a specialist when disputes cannot be resolved "
        "or when the customer requests a manager review."
    )

    domain_knowledge: Dict[str, Any] = {
        "domains": [
            "billing_inquiries",
            "payment_issues",
            "invoice_requests",
            "subscription_management",
            "payment_method_verification",
        ],
        "proposed_actions": {
            "respond": "informational",
            "discount": "monetary",
            "waive_fee": "monetary",
            "escalate": "escalation",
        },
        "billing_policy": {
            "max_discount_percent": 25,
            "fee_waive_requires_justification": True,
            "invoice_retention_months": 24,
            "auto_refund_duplicate_charges": True,
            "proration_on_plan_change": True,
        },
        "subscription": {
            "allowed_plan_changes": ["upgrade", "downgrade"],
            "cooldown_after_downgrade_days": 30,
            "trial_extension_max_days": 14,
        },
    }

    # ── Billing lookup ────────────────────────────────────────

    def _lookup_billing(
        self,
        message: str,
        tenant_id: str,
        signals: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Look up billing information using the billing_tool.

        Uses app.core.react_tools.billing_tool for billing lookups.
        Falls back to empty results if the tool is unavailable.

        Args:
            message: The PII-redacted message to extract billing info from.
            tenant_id: Tenant identifier (BC-001).
            signals: Extracted query signals (may contain invoice_id, etc.).

        Returns:
            Dict with 'billing_found', 'billing_details', 'payment_methods'.
        """
        try:
            from app.core.react_tools.billing_tool import lookup_billing  # type: ignore[import-untyped]

            invoice_id = signals.get("invoice_id", "") if signals else ""

            result = lookup_billing(
                query=message,
                tenant_id=tenant_id,
                invoice_id=invoice_id,
            )

            billing_found = result.get("found", False)
            billing_details = result.get("details", {})
            payment_methods = result.get("payment_methods", [])

            logger.info(
                "billing_lookup_success",
                tenant_id=tenant_id,
                billing_found=billing_found,
                invoice_id=invoice_id or result.get("invoice_id", ""),
            )

            return {
                "billing_found": billing_found,
                "billing_details": billing_details,
                "payment_methods": payment_methods,
            }

        except ImportError:
            logger.warning(
                "billing_tool_unavailable",
                tenant_id=tenant_id,
            )
        except Exception as billing_exc:
            logger.warning(
                "billing_lookup_error",
                tenant_id=tenant_id,
                error=str(billing_exc),
            )

        # Fallback: no billing info available
        return {
            "billing_found": False,
            "billing_details": {},
            "payment_methods": [],
        }

    # ── Payment method verification ───────────────────────────

    def _verify_payment_method(
        self,
        billing_details: Dict[str, Any],
        tenant_id: str,
    ) -> Dict[str, Any]:
        """
        Verify payment methods on file for the customer.

        Checks payment method validity, expiration, and
        available payment options.

        Args:
            billing_details: Billing details from lookup.
            tenant_id: Tenant identifier (BC-001).

        Returns:
            Dict with 'valid_methods', 'expired_methods', 'primary_method'.
        """
        try:
            payment_methods = billing_details.get("payment_methods", [])

            if not payment_methods:
                # Try getting from billing_details directly
                payment_methods = billing_details.get("payment_methods", [])

            valid_methods = []
            expired_methods = []
            primary_method = None

            for method in payment_methods:
                is_expired = method.get("is_expired", False)
                is_primary = method.get("is_primary", False)

                if is_expired:
                    expired_methods.append(method)
                else:
                    valid_methods.append(method)

                if is_primary and not is_expired:
                    primary_method = method

            # Default to first valid method if no primary
            if primary_method is None and valid_methods:
                primary_method = valid_methods[0]

            return {
                "valid_methods": valid_methods,
                "expired_methods": expired_methods,
                "primary_method": primary_method or {},
            }

        except Exception as verify_exc:
            logger.warning(
                "payment_method_verification_error",
                tenant_id=tenant_id,
                error=str(verify_exc),
            )
            return {
                "valid_methods": [],
                "expired_methods": [],
                "primary_method": {},
            }

    # ── Extra state update ────────────────────────────────────

    def _extra_state_update(
        self,
        state: Dict[str, Any],
        generation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add billing-specific fields to the state update.

        Extends the base state update with:
          - billing_lookup_result: Result of billing information lookup
          - payment_methods: Verified payment method information

        Args:
            state: Current ParwaGraphState dict.
            generation_result: Output from _generate_response().

        Returns:
            Dict with additional billing state fields.
        """
        tenant_id = state.get("tenant_id", "unknown")
        message = state.get("pii_redacted_message", "") or state.get("message", "")
        signals = state.get("signals_extracted", {})

        # Perform billing lookup
        billing_result = self._lookup_billing(
            message=message,
            tenant_id=tenant_id,
            signals=signals,
        )

        # Verify payment methods
        payment_info = self._verify_payment_method(
            billing_details=billing_result.get("billing_details", {}),
            tenant_id=tenant_id,
        )

        return {
            "billing_lookup_result": billing_result,
            "payment_methods": payment_info,
        }


# ═══════════════════════════════════════════════════════════════
# LangGraph Node Function
# ═══════════════════════════════════════════════════════════════


def billing_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Billing Agent Node — LangGraph agent node.

    Handles billing inquiries, payment issues, invoice requests,
    and subscription management. Uses billing_tool for lookups
    and verifies payment methods on file.

    This agent is available on ALL tiers (mini, pro, high).

    Args:
        state: Current ParwaGraphState dict.

    Returns:
        Partial state update with domain agent output fields
        plus billing lookup and payment method fields.
    """
    tenant_id = state.get("tenant_id", "unknown")

    logger.info(
        "billing_agent_node_start",
        tenant_id=tenant_id,
        intent=state.get("intent", "unknown"),
    )

    try:
        agent = BillingAgent()
        return agent.run(state)
    except Exception as exc:
        logger.error(
            "billing_agent_node_fatal_error",
            tenant_id=tenant_id,
            error=str(exc),
        )
        return {
            "agent_response": "",
            "agent_confidence": 0.0,
            "proposed_action": "respond",
            "action_type": "informational",
            "agent_reasoning": f"Billing agent fatal error: {exc}",
            "agent_type": "billing",
            "billing_lookup_result": {
                "billing_found": False,
                "billing_details": {},
                "payment_methods": [],
            },
            "payment_methods": {
                "valid_methods": [],
                "expired_methods": [],
                "primary_method": {},
            },
            "errors": [f"Billing agent fatal error: {exc}"],
        }
