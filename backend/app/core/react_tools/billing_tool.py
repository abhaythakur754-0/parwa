"""
PARWA Phase 4 — Billing Tool (wired to ProviderBridge)

Methods:
- get_subscription: Check subscription details
- create_refund: Process a refund
- cancel_subscription: Cancel a subscription
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .base import BaseReactTool, ToolResult, _mock_subscription

logger = logging.getLogger(__name__)


class BillingTool(BaseReactTool):
    """Billing/payment integration tool — Stripe, Paddle, etc."""

    name = "billing_tool"
    description = "Check subscriptions, process refunds, cancel subscriptions"
    category = "payment"

    async def get_subscription(
        self,
        company_id: str,
        customer_id: str,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Check subscription details for a customer."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="get_subscription",
                fallback_fn=lambda **kw: _mock_subscription(customer_id=customer_id),
                customer_id=customer_id,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Found subscription for {customer_id}",
                action_type="lookup_subscription",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("billing get_subscription failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="lookup_subscription", variant_tier=variant_tier,
            )

    async def create_refund(
        self,
        company_id: str,
        customer_id: str,
        amount: float,
        reason: str = "customer_request",
        order_id: Optional[str] = None,
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Process a refund.

        Mini: recommend only (needs approval)
        PARWA: auto-execute (can undo)
        High: auto-execute (can undo)
        """
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="create_refund",
                fallback_fn=lambda **kw: {
                    "refund_id": "ref-001",
                    "customer_id": customer_id,
                    "amount": amount,
                    "currency": "USD",
                    "reason": reason,
                    "order_id": order_id,
                    "status": "processed",
                },
                customer_id=customer_id,
                amount=amount,
                reason=reason,
                order_id=order_id,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Refund of ${amount:.2f} processed for {customer_id}",
                action_type="refund",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("billing create_refund failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="refund", variant_tier=variant_tier,
            )

    async def cancel_subscription(
        self,
        company_id: str,
        customer_id: str,
        reason: str = "customer_request",
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Cancel a subscription."""
        try:
            data = await self._execute_via_bridge(
                company_id=company_id,
                action="cancel_subscription",
                fallback_fn=lambda **kw: {
                    "subscription_id": "sub-001",
                    "customer_id": customer_id,
                    "status": "cancelled",
                    "reason": reason,
                    "effective_date": "immediate",
                },
                customer_id=customer_id,
                reason=reason,
            )
            return self._build_result(
                success=True,
                data=data,
                message=f"Subscription cancelled for {customer_id}",
                action_type="cancel_subscription",
                variant_tier=variant_tier,
            )
        except Exception as exc:
            logger.error("billing cancel_subscription failed: %s", exc)
            return self._build_result(
                success=False, message=str(exc),
                action_type="cancel_subscription", variant_tier=variant_tier,
            )
