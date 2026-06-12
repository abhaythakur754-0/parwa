"""
PARWA Phase 4 — Base ReAct Tool

Foundation class for all ReAct tools that use ProviderBridge.
Every tool follows the pattern:
1. Check variant permission (Mini=recommend, PARWA=execute, High=execute+voice)
2. Try real provider via ProviderBridge
3. Fall back to mock data if no provider configured

CRITICAL RULES:
- BC-001: All operations scoped to company_id
- BC-008: Never crash — always return a ToolResult
- Mini: recommendations only (needs human approval)
- PARWA: auto-execute (can undo)
- High: auto-execute + voice + recordings
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission levels (maps to variant tiers)
# ---------------------------------------------------------------------------

class PermissionLevel(str, Enum):
    RECOMMEND = "recommend"   # Mini PARWA — suggest, wait for approval
    EXECUTE = "execute"       # PARWA — auto-execute, can undo
    FULL = "full"             # PARWA High — execute + voice + recordings


# Variant → default permission mapping
VARIANT_PERMISSIONS = {
    "mini": PermissionLevel.RECOMMEND,
    "parwa": PermissionLevel.EXECUTE,
    "high": PermissionLevel.FULL,
}


# ---------------------------------------------------------------------------
# Tool Result
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result from a ReAct tool execution."""
    success: bool
    data: Any = None
    message: str = ""
    tool_name: str = ""
    action_type: str = ""
    can_undo: bool = False
    needs_approval: bool = False
    variant_tier: str = "parwa"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "tool_name": self.tool_name,
            "action_type": self.action_type,
            "can_undo": self.can_undo,
            "needs_approval": self.needs_approval,
            "variant_tier": self.variant_tier,
        }


# ---------------------------------------------------------------------------
# Provider Result (compatible with ProviderBridge)
# ---------------------------------------------------------------------------

@dataclass
class ProviderResult:
    """Result from a provider execution."""
    success: bool
    data: Any = None
    message: str = ""
    provider_name: str = ""


# ---------------------------------------------------------------------------
# Mock Data Generators
# ---------------------------------------------------------------------------

def _mock_customer(customer_id: str = "cust-001", **kwargs) -> Dict[str, Any]:
    """Generate mock customer data."""
    return {
        "customer_id": customer_id,
        "name": kwargs.get("name", "John Doe"),
        "email": kwargs.get("email", "john@example.com"),
        "phone": kwargs.get("phone", "+1234567890"),
        "company": kwargs.get("company", "Acme Corp"),
        "lifetime_value": kwargs.get("lifetime_value", 1250.00),
        "total_orders": kwargs.get("total_orders", 15),
        "last_order_date": kwargs.get("last_order_date", "2026-06-01"),
    }


def _mock_subscription(customer_id: str = "cust-001") -> Dict[str, Any]:
    """Generate mock subscription data."""
    return {
        "subscription_id": "sub-001",
        "customer_id": customer_id,
        "plan": "Pro",
        "status": "active",
        "amount": 79.00,
        "currency": "USD",
        "next_billing_date": "2026-07-01",
        "created_at": "2026-01-15",
    }


def _mock_order(order_id: str = "ORD-001") -> Dict[str, Any]:
    """Generate mock order data."""
    return {
        "order_id": order_id,
        "customer_id": "cust-001",
        "status": "shipped",
        "items": [{"name": "Widget Pro", "quantity": 2, "price": 29.99}],
        "total": 59.98,
        "currency": "USD",
        "tracking_number": "TRK-123456789",
        "created_at": "2026-06-05",
        "shipped_at": "2026-06-07",
    }


def _mock_ticket(ticket_id: str = "TKT-001") -> Dict[str, Any]:
    """Generate mock helpdesk ticket data."""
    return {
        "ticket_id": ticket_id,
        "subject": "Order tracking request",
        "status": "open",
        "priority": "medium",
        "customer_id": "cust-001",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_email_result(to: str = "customer@example.com") -> Dict[str, Any]:
    """Generate mock email send result."""
    return {
        "message_id": f"msg-{datetime.now().strftime('%H%M%S')}",
        "to": to,
        "status": "sent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _mock_sms_result(to: str = "+1234567890") -> Dict[str, Any]:
    """Generate mock SMS send result."""
    return {
        "message_id": f"sms-{datetime.now().strftime('%H%M%S')}",
        "to": to,
        "status": "delivered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _mock_slack_result(channel: str = "#support") -> Dict[str, Any]:
    """Generate mock Slack message result."""
    return {
        "message_id": f"slack-{datetime.now().strftime('%H%M%S')}",
        "channel": channel,
        "status": "sent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Base ReAct Tool
# ---------------------------------------------------------------------------

class BaseReactTool:
    """Base class for all ReAct tools that use ProviderBridge.

    Subclasses must implement:
    - name: str — tool name
    - description: str — tool description for AI
    - category: str — provider category (crm, payment, ecommerce, etc.)
    """

    name: str = "base_tool"
    description: str = "Base tool — override in subclass"
    category: str = ""

    def __init__(
        self,
        bridge: Optional[Any] = None,
        executor: Optional[Any] = None,
    ):
        self._bridge = bridge
        self._executor = executor

    def _check_permission(
        self,
        variant_tier: str,
        action: str,
    ) -> PermissionLevel:
        """Check what permission level this action has for the variant."""
        return VARIANT_PERMISSIONS.get(variant_tier, PermissionLevel.EXECUTE)

    async def _execute_via_bridge(
        self,
        company_id: str,
        action: str,
        fallback_fn: Callable,
        **kwargs,
    ) -> Any:
        """Try executing via ProviderBridge, fall back to mock data."""
        try:
            if self._bridge:
                # Try real provider
                result = await self._bridge.execute_with_fallback(
                    company_id=company_id,
                    category=self.category,
                    action=action,
                    fallback_fn=lambda **kw: ProviderResult(
                        success=True,
                        data=fallback_fn(**kw),
                    ),
                    **kwargs,
                )
                if isinstance(result, ProviderResult):
                    return result.data
                return result
        except Exception as exc:
            logger.warning("Bridge execution failed for %s.%s: %s", self.name, action, exc)

        # Fall back to mock
        return fallback_fn(**kwargs)

    def _build_result(
        self,
        success: bool,
        data: Any = None,
        message: str = "",
        action_type: str = "",
        variant_tier: str = "parwa",
    ) -> ToolResult:
        """Build a standardized ToolResult."""
        perm = self._check_permission(variant_tier, action_type)
        return ToolResult(
            success=success,
            data=data,
            message=message,
            tool_name=self.name,
            action_type=action_type,
            can_undo=(perm in (PermissionLevel.EXECUTE, PermissionLevel.FULL)),
            needs_approval=(perm == PermissionLevel.RECOMMEND),
            variant_tier=variant_tier,
        )
