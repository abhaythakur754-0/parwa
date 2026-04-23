"""
PARWA ReAct Tool — Billing System  (F-157)

Exposes billing/subscription-related actions to the ReAct agent:
- get_invoice          Fetch a single invoice by ID
- list_invoices        List invoices with date / status filtering
- process_payment      Process a credit-card or bank payment
- get_subscription_status  Get current subscription tier & status
- apply_credit         Apply account credit or discount
- get_payment_history  Retrieve payment history for an account

All actions are scoped to *company_id* (BC-001) and return
structured ToolResult (BC-008).
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import ActionSchema, BaseReactTool, ToolResult, ToolSchema

logger = logging.getLogger(__name__)

# ── Mock data factories ────────────────────────────────────────────

_PLANS = [
    {"plan_id": "PARWA-STARTER-MO", "name": "Mini PARWA", "price": 999.00},
    {"plan_id": "PARWA-STARTER-YR", "name": "Mini PARWA (Annual)", "price": 9590.00},
    {"plan_id": "PARWA-GROWTH-MO", "name": "PARWA", "price": 2499.00},
    {"plan_id": "PARWA-GROWTH-YR", "name": "PARWA (Annual)", "price": 23990.00},
    {"plan_id": "PARWA-HIGH-MO", "name": "PARWA High", "price": 3999.00},
    {"plan_id": "PARWA-HIGH-YR", "name": "PARWA High (Annual)", "price": 38390.00},
]

_PAYMENT_METHODS = ["visa_****4242", "mastercard_****8888", "amex_****1234", "bank_acct_****5678"]


def _mock_invoice(
    invoice_id: str | None = None,
    company_id: str = "",
    status: str = "paid",
) -> dict[str, Any]:
    """Generate a realistic mock invoice."""
    iid = invoice_id or f"INV-{uuid.uuid4().hex[:8].upper()}"
    plan = random.choice(_PLANS)
    tax = round(plan["price"] * 0.08, 2)
    total = round(plan["price"] + tax, 2)
    created = datetime.now(timezone.utc) - timedelta(
        days=random.randint(1, 365),
    )
    due = created + timedelta(days=30)
    paid_at = created + timedelta(days=random.randint(0, 15)) if status == "paid" else None

    return {
        "invoice_id": iid,
        "company_id": company_id,
        "plan": plan["name"],
        "plan_id": plan["plan_id"],
        "subtotal": plan["price"],
        "tax": tax,
        "total": total,
        "currency": "USD",
        "status": status,
        "payment_method": random.choice(_PAYMENT_METHODS) if status == "paid" else None,
        "created_at": created.isoformat(),
        "due_at": due.isoformat(),
        "paid_at": paid_at.isoformat() if paid_at else None,
    }


def _mock_subscription(company_id: str) -> dict[str, Any]:
    """Generate a mock subscription record."""
    plan = random.choice(_PLANS)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=random.randint(30, 365))
    period_end = start + timedelta(days=365)
    return {
        "company_id": company_id,
        "plan_id": plan["plan_id"],
        "plan_name": plan["name"],
        "status": "active",
        "current_period_start": start.isoformat(),
        "current_period_end": period_end.isoformat(),
        "next_billing_date": period_end.isoformat(),
        "seat_count": random.randint(5, 100),
        "payment_method": random.choice(_PAYMENT_METHODS),
        "trial_end": None,
    }


def _mock_payment(company_id: str) -> dict[str, Any]:
    """Generate a mock payment record."""
    plan = random.choice(_PLANS)
    return {
        "payment_id": f"PAY-{uuid.uuid4().hex[:10].upper()}",
        "company_id": company_id,
        "amount": round(plan["price"] * 1.08, 2),
        "currency": "USD",
        "status": random.choice(["succeeded", "succeeded", "succeeded", "failed", "refunded"]),
        "payment_method": random.choice(_PAYMENT_METHODS),
        "description": f"{plan['name']} subscription",
        "created_at": (
            datetime.now(timezone.utc) - timedelta(days=random.randint(1, 180))
        ).isoformat(),
    }


# ── Tool Implementation ────────────────────────────────────────────


class BillingTool(BaseReactTool):
    """ReAct tool for Billing System API integration."""

    def __init__(self) -> None:
        self._invoices: dict[str, dict[str, Any]] = {}
        self._credits: dict[str, float] = {}
        self._payments: list[dict[str, Any]] = []

    # ── Metadata ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "billing_system"

    @property
    def description(self) -> str:
        return (
            "Check invoices, process payments, view billing history, "
            "manage subscriptions, and apply credits"
        )

    @property
    def actions(self) -> list[str]:
        return [
            "get_invoice",
            "list_invoices",
            "process_payment",
            "get_subscription_status",
            "apply_credit",
            "get_payment_history",
        ]

    # ── Schema ──────────────────────────────────────────────────

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            tool_name=self.name,
            description=self.description,
            actions=[
                ActionSchema(
                    name="get_invoice",
                    description="Fetch a single invoice by ID",
                    parameters={
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "Unique invoice identifier"},
                        },
                        "required": ["invoice_id"],
                    },
                    required_params=["invoice_id"],
                    returns="Full invoice object with line items, totals, and payment status",
                ),
                ActionSchema(
                    name="list_invoices",
                    description="List invoices with optional date range and status filtering",
                    parameters={
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "description": "Filter by status: paid, unpaid, overdue, void"},
                            "limit": {"type": "integer", "description": "Max invoices (1-50)", "default": 10},
                            "from_date": {"type": "string", "description": "ISO date start (inclusive)"},
                            "to_date": {"type": "string", "description": "ISO date end (inclusive)"},
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="List of invoice objects with pagination metadata",
                ),
                ActionSchema(
                    name="process_payment",
                    description="Process a payment for an invoice or subscription",
                    parameters={
                        "type": "object",
                        "properties": {
                            "invoice_id": {"type": "string", "description": "Invoice to pay (optional)"},
                            "amount": {"type": "number", "description": "Payment amount"},
                            "payment_method": {"type": "string", "description": "Payment method token"},
                            "description": {"type": "string", "description": "Payment description"},
                        },
                        "required": ["amount", "payment_method"],
                    },
                    required_params=["amount", "payment_method"],
                    returns="Payment confirmation with payment_id and status",
                ),
                ActionSchema(
                    name="get_subscription_status",
                    description="Get current subscription tier, seat count, and billing cycle",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                    required_params=[],
                    returns="Subscription object with plan, status, and next billing date",
                ),
                ActionSchema(
                    name="apply_credit",
                    description="Apply account credit or a discount to a company",
                    parameters={
                        "type": "object",
                        "properties": {
                            "amount": {"type": "number", "description": "Credit amount"},
                            "reason": {"type": "string", "description": "Reason for the credit"},
                            "expires_at": {"type": "string", "description": "ISO expiry date (optional)"},
                        },
                        "required": ["amount", "reason"],
                    },
                    required_params=["amount", "reason"],
                    returns="Credit confirmation with updated balance",
                ),
                ActionSchema(
                    name="get_payment_history",
                    description="Retrieve payment history for the company",
                    parameters={
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Max records (1-100)", "default": 20},
                            "status": {"type": "string", "description": "Filter by status: succeeded, failed, refunded"},
                        },
                        "required": [],
                    },
                    required_params=[],
                    returns="List of payment records with amounts and timestamps",
                ),
            ],
        )

    # ── Execution ───────────────────────────────────────────────

    async def _do_execute(
        self,
        action: str,
        company_id: str,
        **params: Any,
    ) -> ToolResult:
        """Route action to the appropriate handler."""

        # Simulate API latency
        await asyncio.sleep(random.uniform(0.02, 0.12))

        if action == "__health_check__":
            return ToolResult(success=True, error=None, data={"status": "ok"}, execution_time_ms=0)

        handler = {
            "get_invoice": self._get_invoice,
            "list_invoices": self._list_invoices,
            "process_payment": self._process_payment,
            "get_subscription_status": self._get_subscription_status,
            "apply_credit": self._apply_credit,
            "get_payment_history": self._get_payment_history,
        }.get(action)

        if handler is None:
            return ToolResult(
                success=False,
                error=f"Unknown action: {action}. Available: {', '.join(self.actions)}",
                data=None,
                execution_time_ms=0,
            )

        return await handler(company_id, **params)

    # ── Action Handlers ─────────────────────────────────────────

    async def _get_invoice(self, company_id: str, **params: Any) -> ToolResult:
        """Fetch a single invoice by ID."""
        invoice_id: str = params.get("invoice_id", "")

        if invoice_id in self._invoices:
            inv = self._invoices[invoice_id]
            if inv["company_id"] != company_id:
                return ToolResult(
                    success=False,
                    error=f"Invoice {invoice_id} not found in company scope",
                    data=None,
                    execution_time_ms=0,
                )
            return ToolResult(success=True, error=None, data=inv, execution_time_ms=0)

        inv = _mock_invoice(invoice_id=invoice_id, company_id=company_id)
        self._invoices[invoice_id] = inv
        return ToolResult(success=True, error=None, data=inv, execution_time_ms=0)

    async def _list_invoices(self, company_id: str, **params: Any) -> ToolResult:
        """List invoices with optional filtering."""
        status: str | None = params.get("status")
        limit: int = min(max(params.get("limit", 10), 1), 50)
        from_date: str | None = params.get("from_date")
        to_date: str | None = params.get("to_date")

        count = min(limit, 30)
        invoices: list[dict[str, Any]] = []
        for _ in range(count):
            st = status or random.choice(["paid", "paid", "paid", "unpaid", "overdue"])
            inv = _mock_invoice(company_id=company_id, status=st)
            invoices.append(inv)

        # Filter by date range
        if from_date:
            invoices = [i for i in invoices if i.get("created_at", "") >= from_date]
        if to_date:
            invoices = [i for i in invoices if i.get("created_at", "") <= to_date]

        return ToolResult(
            success=True,
            error=None,
            data={
                "invoices": invoices,
                "total": len(invoices),
                "limit": limit,
            },
            execution_time_ms=0,
        )

    async def _process_payment(self, company_id: str, **params: Any) -> ToolResult:
        """Process a payment."""
        amount: float = params.get("amount", 0)
        payment_method: str = params.get("payment_method", "")
        invoice_id: str | None = params.get("invoice_id")
        description: str = params.get("description", "Payment")

        if amount <= 0:
            return ToolResult(
                success=False,
                error="Payment amount must be positive",
                data=None,
                execution_time_ms=0,
            )

        if not payment_method:
            return ToolResult(
                success=False,
                error="Payment method is required",
                data=None,
                execution_time_ms=0,
            )

        # Check credit balance for potential partial credit application
        credit_balance = self._credits.get(company_id, 0.0)
        credit_applied = min(credit_balance, amount)
        net_amount = round(amount - credit_applied, 2)

        payment_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        payment: dict[str, Any] = {
            "payment_id": payment_id,
            "company_id": company_id,
            "invoice_id": invoice_id,
            "amount": amount,
            "credit_applied": credit_applied,
            "net_amount": net_amount,
            "currency": "USD",
            "payment_method": payment_method,
            "description": description,
            "status": "succeeded",
            "created_at": now,
        }

        self._payments.append(payment)

        # Deduct used credit
        if credit_applied > 0:
            self._credits[company_id] = round(credit_balance - credit_applied, 2)

        # Mark invoice as paid if applicable
        if invoice_id and invoice_id in self._invoices:
            self._invoices[invoice_id]["status"] = "paid"
            self._invoices[invoice_id]["paid_at"] = now

        return ToolResult(
            success=True,
            error=None,
            data=payment,
            execution_time_ms=0,
        )

    async def _get_subscription_status(self, company_id: str, **params: Any) -> ToolResult:
        """Get current subscription details."""
        sub = _mock_subscription(company_id)
        credit_balance = self._credits.get(company_id, 0.0)
        sub["credit_balance"] = credit_balance
        return ToolResult(success=True, error=None, data=sub, execution_time_ms=0)

    async def _apply_credit(self, company_id: str, **params: Any) -> ToolResult:
        """Apply account credit."""
        amount: float = params.get("amount", 0)
        reason: str = params.get("reason", "")
        expires_at: str | None = params.get("expires_at")

        if amount <= 0:
            return ToolResult(
                success=False,
                error="Credit amount must be positive",
                data=None,
                execution_time_ms=0,
            )

        if not reason:
            return ToolResult(
                success=False,
                error="Reason is required for applying credit",
                data=None,
                execution_time_ms=0,
            )

        current = self._credits.get(company_id, 0.0)
        self._credits[company_id] = round(current + amount, 2)

        credit_id = f"CRD-{uuid.uuid4().hex[:8].upper()}"
        return ToolResult(
            success=True,
            error=None,
            data={
                "credit_id": credit_id,
                "company_id": company_id,
                "amount_applied": amount,
                "previous_balance": current,
                "new_balance": self._credits[company_id],
                "reason": reason,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            execution_time_ms=0,
        )

    async def _get_payment_history(self, company_id: str, **params: Any) -> ToolResult:
        """Retrieve payment history."""
        limit: int = min(max(params.get("limit", 20), 1), 100)
        status_filter: str | None = params.get("status")

        # Ensure some history exists
        if len(self._payments) < limit:
            for _ in range(limit - len(self._payments)):
                self._payments.append(_mock_payment(company_id))

        history = [p for p in self._payments if p["company_id"] == company_id]

        if status_filter:
            history = [p for p in history if p["status"] == status_filter]

        history = history[:limit]

        total_amount = sum(p["amount"] for p in history if p["status"] == "succeeded")

        return ToolResult(
            success=True,
            error=None,
            data={
                "payments": history,
                "total_count": len(history),
                "total_succeeded_amount": round(total_amount, 2),
                "currency": "USD",
            },
            execution_time_ms=0,
        )
