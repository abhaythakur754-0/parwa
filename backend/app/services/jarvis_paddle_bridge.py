"""
PARWA Jarvis-Paddle Bridge

Connects Jarvis billing executors to the real Paddle API.
When a client tells Jarvis "upgrade my plan" or "show me my transaction history",
this bridge actually calls Paddle's API and returns real data.

Architecture:
  Jarvis Executor → jarvis_paddle_bridge → PaddleClient → Paddle API

  The bridge adds:
    - DB lookups for Paddle customer/subscription IDs
    - Graceful fallbacks when Paddle is unavailable
    - Business logic (plan validation, upgrade path checking)
    - Formatted responses for Jarvis to present conversationally

BC-001: company_id enforced at every layer.
BC-008: Every method returns graceful defaults on failure — never crash.
BC-012: All timestamps UTC.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.clients.paddle_client import PaddleClient, PaddleError, PaddleNotFoundError, PaddleAuthError
from app.logger import get_logger

logger = get_logger("jarvis_paddle_bridge")

# Plan name mappings
PLAN_NAMES = {
    "mini_parwa": "Mini Parwa (Starter)",
    "parwa": "Parwa (Professional)", 
    "parwa_high": "Parwa High (Enterprise)",
}

PLAN_ORDER = ["mini_parwa", "parwa", "parwa_high"]

# Price ID mapping from paddle_service
# Will be loaded at runtime
_plan_price_ids: Dict[str, str] = {}

def _get_plan_price_ids() -> Dict[str, str]:
    """Load plan price IDs from paddle_service."""
    global _plan_price_ids
    if not _plan_price_ids:
        try:
            from app.services.paddle_service import PLAN_PRICE_IDS
            _plan_price_ids = PLAN_PRICE_IDS
        except Exception:
            logger.debug("plan_price_ids_fallback_to_defaults")
            _plan_price_ids = {
                "mini_parwa": "pri_mini_parwa_01",
                "parwa": "pri_parwa_01",
                "parwa_high": "pri_parwa_high_01",
            }
    return _plan_price_ids


class JarvisPaddleBridge:
    """
    Bridge between Jarvis executors and the Paddle API.
    
    Usage:
        bridge = JarvisPaddleBridge(api_key="...", client_token="...", sandbox=False)
        result = await bridge.get_subscription_info(company_id="...")
    """
    
    def __init__(
        self,
        api_key: str,
        client_token: Optional[str] = None,
        sandbox: bool = True,
    ):
        self.api_key = api_key
        self.client_token = client_token
        self.sandbox = sandbox
        self._client: Optional[PaddleClient] = None
    
    @property
    def client(self) -> PaddleClient:
        """Get or create Paddle client."""
        if self._client is None:
            self._client = PaddleClient(
                api_key=self.api_key,
                client_token=self.client_token,
                sandbox=self.sandbox,
            )
        return self._client
    
    async def close(self):
        """Close the Paddle client."""
        if self._client:
            await self._client.close()
            self._client = None
    
    # ── Helper Methods ──
    
    def get_paddle_customer_id(self, db: Any, company_id: str) -> Optional[str]:
        """Look up Paddle customer ID for a company from DB."""
        try:
            from database.models.billing import Subscription
            sub = db.query(Subscription).filter(
                Subscription.company_id == company_id,
                Subscription.status.in_(["active", "trialing"]),
            ).first()
            if sub and hasattr(sub, "paddle_customer_id"):
                return sub.paddle_customer_id
        except Exception:
            logger.debug("paddle_customer_id_lookup_failed: company=%s", company_id)
        return None
    
    def get_paddle_subscription_id(self, db: Any, company_id: str) -> Optional[str]:
        """Look up Paddle subscription ID for a company from DB."""
        try:
            from database.models.billing import Subscription
            sub = db.query(Subscription).filter(
                Subscription.company_id == company_id,
                Subscription.status.in_(["active", "trialing"]),
            ).first()
            if sub and hasattr(sub, "paddle_subscription_id"):
                return sub.paddle_subscription_id
        except Exception:
            logger.debug("paddle_subscription_id_lookup_failed: company=%s", company_id)
        return None
    
    # ── Subscription Info ──
    
    async def get_subscription_info(
        self,
        company_id: str,
        paddle_customer_id: Optional[str] = None,
        paddle_subscription_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get subscription info from Paddle.
        
        Returns real plan details, status, renewal date, and billing amount.
        Falls back to DB data if Paddle is unavailable.
        """
        try:
            # Try to get subscription from Paddle
            if paddle_subscription_id:
                result = await self.client.get_subscription(paddle_subscription_id)
                data = result.get("data", result)
                
                status = data.get("status", "unknown")
                billing_cycle = data.get("billing_cycle", {})
                next_billed_at = data.get("next_billed_at")
                items = data.get("items", [])
                
                # Determine plan from price_id
                current_plan = "unknown"
                price_ids = _get_plan_price_ids()
                for item in items:
                    price_id = item.get("price", {}).get("id", "")
                    for plan, pid in price_ids.items():
                        if pid == price_id:
                            current_plan = plan
                            break
                
                # Calculate days until renewal
                days_until_renewal = None
                if next_billed_at:
                    try:
                        renewal_dt = datetime.fromisoformat(next_billed_at.replace("Z", "+00:00"))
                        days_until_renewal = (renewal_dt - datetime.now(timezone.utc)).days
                    except Exception:
                        pass
                
                return {
                    "success": True,
                    "source": "paddle_api",
                    "plan": current_plan,
                    "plan_name": PLAN_NAMES.get(current_plan, current_plan),
                    "status": status,
                    "next_billed_at": next_billed_at,
                    "days_until_renewal": days_until_renewal,
                    "items": items,
                    "subscription_id": paddle_subscription_id,
                }
            
            # Try listing subscriptions by customer
            if paddle_customer_id:
                result = await self.client.list_subscriptions(
                    customer_id=paddle_customer_id,
                    status="active",
                )
                subs = result.get("data", [])
                if subs:
                    sub = subs[0]
                    sub_id = sub.get("id", "")
                    # Recursively get details
                    return await self.get_subscription_info(
                        company_id=company_id,
                        paddle_subscription_id=sub_id,
                    )
            
            # No Paddle IDs available
            return {
                "success": False,
                "source": "fallback",
                "plan": "unknown",
                "status": "unknown",
                "message": "No Paddle subscription found for this company.",
            }
            
        except PaddleNotFoundError:
            return {
                "success": False,
                "source": "paddle_api",
                "plan": "unknown",
                "status": "not_found",
                "message": "Subscription not found on Paddle.",
            }
        except PaddleAuthError:
            return {
                "success": False,
                "source": "paddle_api",
                "plan": "unknown",
                "status": "auth_error",
                "message": "Paddle authentication failed. Check API key.",
            }
        except Exception as e:
            logger.exception("get_subscription_info_error: company=%s", company_id)
            return {
                "success": False,
                "source": "error",
                "plan": "unknown",
                "status": "error",
                "message": f"Failed to get subscription info: {str(e)[:200]}",
            }
    
    # ── Upgrade Plan ──
    
    async def upgrade_plan(
        self,
        company_id: str,
        target_plan: str,
        current_plan: str,
        paddle_subscription_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upgrade subscription plan via Paddle API.
        
        Updates the subscription's price_id to the new plan's price_id.
        Paddle handles proration automatically.
        """
        try:
            # Validate upgrade path
            if current_plan in PLAN_ORDER and target_plan in PLAN_ORDER:
                current_idx = PLAN_ORDER.index(current_plan)
                target_idx = PLAN_ORDER.index(target_plan)
                if target_idx <= current_idx:
                    return {
                        "success": False,
                        "message": f"Cannot upgrade from {PLAN_NAMES.get(current_plan)} to {PLAN_NAMES.get(target_plan)}. You can only upgrade to a higher plan.",
                    }
            
            price_ids = _get_plan_price_ids()
            new_price_id = price_ids.get(target_plan)
            if not new_price_id:
                return {
                    "success": False,
                    "message": f"Unknown plan: {target_plan}. Available plans: {', '.join(PLAN_NAMES.values())}",
                }
            
            if not paddle_subscription_id:
                return {
                    "success": False,
                    "message": "No Paddle subscription ID found. Cannot upgrade via Paddle without an active subscription.",
                }
            
            # Update subscription via Paddle API
            result = await self.client.update_subscription(
                subscription_id=paddle_subscription_id,
                items=[{"price_id": new_price_id, "quantity": 1}],
                prorate=True,
            )
            
            logger.info(
                "plan_upgraded_via_paddle: company=%s, from=%s, to=%s, sub=%s",
                company_id, current_plan, target_plan, paddle_subscription_id,
            )
            
            return {
                "success": True,
                "source": "paddle_api",
                "previous_plan": current_plan,
                "previous_plan_name": PLAN_NAMES.get(current_plan, current_plan),
                "new_plan": target_plan,
                "new_plan_name": PLAN_NAMES.get(target_plan, target_plan),
                "subscription_id": paddle_subscription_id,
                "proration": True,
                "message": f"Plan upgraded from {PLAN_NAMES.get(current_plan, current_plan)} to {PLAN_NAMES.get(target_plan, target_plan)} via Paddle. Proration will be applied.",
            }
            
        except PaddleNotFoundError:
            return {
                "success": False,
                "message": f"Subscription {paddle_subscription_id} not found on Paddle.",
            }
        except PaddleError as e:
            logger.error("upgrade_paddle_error: company=%s, error=%s", company_id, str(e))
            return {
                "success": False,
                "message": f"Paddle API error during upgrade: {str(e)[:200]}",
            }
        except Exception as e:
            logger.exception("upgrade_plan_error: company=%s", company_id)
            return {
                "success": False,
                "message": f"Failed to upgrade plan: {str(e)[:200]}",
            }
    
    # ── Cancel Subscription ──
    
    async def cancel_subscription(
        self,
        company_id: str,
        reason: str,
        immediate: bool = False,
        paddle_subscription_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel subscription via Paddle API.
        
        Netflix-style: By default cancels at end of billing period.
        If immediate=True, cancels right away.
        """
        try:
            if not paddle_subscription_id:
                return {
                    "success": False,
                    "message": "No Paddle subscription ID found. Cannot cancel via Paddle without an active subscription.",
                }
            
            effective_from = "immediately" if immediate else "next_billing_period"
            
            result = await self.client.cancel_subscription(
                subscription_id=paddle_subscription_id,
                effective_from=effective_from,
                reason=reason,
            )
            
            logger.info(
                "subscription_cancelled_via_paddle: company=%s, sub=%s, immediate=%s",
                company_id, paddle_subscription_id, immediate,
            )
            
            if immediate:
                msg = "Your subscription has been cancelled immediately via Paddle. All services will be shut down."
            else:
                msg = "Your subscription has been scheduled for cancellation at the end of the current billing period via Paddle. You'll continue to have access until then."
            
            return {
                "success": True,
                "source": "paddle_api",
                "cancellation_type": "immediate" if immediate else "end_of_period",
                "reason": reason,
                "subscription_id": paddle_subscription_id,
                "message": msg,
            }
            
        except PaddleNotFoundError:
            return {
                "success": False,
                "message": f"Subscription {paddle_subscription_id} not found on Paddle.",
            }
        except PaddleError as e:
            logger.error("cancel_paddle_error: company=%s, error=%s", company_id, str(e))
            return {
                "success": False,
                "message": f"Paddle API error during cancellation: {str(e)[:200]}",
            }
        except Exception as e:
            logger.exception("cancel_subscription_error: company=%s", company_id)
            return {
                "success": False,
                "message": f"Failed to cancel subscription: {str(e)[:200]}",
            }
    
    # ── Transaction History ──
    
    async def get_transaction_history(
        self,
        company_id: str,
        paddle_customer_id: Optional[str] = None,
        period: str = "last_30_days",
        transaction_type: str = "all",
    ) -> Dict[str, Any]:
        """Get transaction/billing history from Paddle API.
        
        Returns real transaction data with amounts, dates, and statuses.
        """
        try:
            if not paddle_customer_id:
                return {
                    "success": False,
                    "transactions": [],
                    "message": "No Paddle customer ID found. Cannot fetch transaction history from Paddle.",
                }
            
            # Get transactions from Paddle
            params: Dict[str, Any] = {"per_page": 50}
            if paddle_customer_id:
                params["customer_id"] = paddle_customer_id
            if transaction_type != "all":
                params["status"] = transaction_type
            
            result = await self.client.list_transactions(
                customer_id=paddle_customer_id,
                per_page=50,
            )
            
            raw_transactions = result.get("data", [])
            
            # Process transactions
            transactions = []
            for txn in raw_transactions:
                try:
                    amount = str(txn.get("details", {}).get("totals", {}).get("total", "0"))
                    currency = txn.get("currency_code", "USD")
                    status = txn.get("status", "unknown")
                    created_at = txn.get("created_at", "")
                    txn_id = txn.get("id", "")
                    
                    # Determine type
                    origin = txn.get("origin", "")
                    if origin == "subscription":
                        txn_type = "payment"
                    elif origin == "adjustment":
                        txn_type = "refund"
                    else:
                        txn_type = origin or "charge"
                    
                    # Build description
                    items = txn.get("items", [])
                    description = ""
                    if items:
                        first_item = items[0]
                        description = first_item.get("price", {}).get("name", "")
                    if not description:
                        description = f"{origin.title()} transaction" if origin else "Transaction"
                    
                    transactions.append({
                        "id": txn_id,
                        "type": txn_type,
                        "amount": float(amount) if amount else 0,
                        "currency": currency,
                        "status": status,
                        "description": description,
                        "date": created_at[:10] if created_at else "",
                    })
                except Exception:
                    logger.debug("transaction_parse_failed: txn_id=%s", txn.get("id", "?"))
            
            # Filter by period
            now = datetime.now(timezone.utc)
            period_days = {"last_30_days": 30, "last_90_days": 90, "this_year": 365, "all": 9999}
            days = period_days.get(period, 30)
            
            if days < 9999:
                cutoff = now - timedelta(days=days)
                filtered = []
                for t in transactions:
                    try:
                        if t["date"]:
                            txn_date = datetime.fromisoformat(t["date"].replace("Z", "+00:00"))
                            if txn_date >= cutoff:
                                filtered.append(t)
                        else:
                            filtered.append(t)
                    except Exception:
                        filtered.append(t)
                transactions = filtered
            
            # Filter by type
            if transaction_type != "all":
                transactions = [t for t in transactions if t["type"] == transaction_type]
            
            # Calculate totals
            total_payments = sum(t["amount"] for t in transactions if t["type"] == "payment" and t["amount"] > 0)
            total_refunds = sum(abs(t["amount"]) for t in transactions if t["type"] == "refund")
            total_credits = sum(abs(t["amount"]) for t in transactions if t["type"] == "credit" and t["amount"] < 0)
            
            logger.info(
                "transaction_history_fetched: company=%s, count=%d, period=%s",
                company_id, len(transactions), period,
            )
            
            return {
                "success": True,
                "source": "paddle_api",
                "transactions": transactions,
                "total_count": len(transactions),
                "total_payments": round(total_payments, 2),
                "total_refunds": round(total_refunds, 2),
                "total_credits": round(total_credits, 2),
                "period": period,
                "message": f"Found {len(transactions)} transactions from Paddle.",
            }
            
        except PaddleAuthError:
            return {
                "success": False,
                "transactions": [],
                "message": "Paddle authentication failed. Check API key.",
            }
        except Exception as e:
            logger.exception("transaction_history_error: company=%s", company_id)
            return {
                "success": False,
                "transactions": [],
                "message": f"Failed to fetch transactions: {str(e)[:200]}",
            }
    
    # ── Process Refund (Real Paddle Adjustments API) ──
    
    async def process_refund(
        self,
        company_id: str,
        customer_id: str,
        amount: float,
        reason: str,
        ticket_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        partial: bool = False,
    ) -> Dict[str, Any]:
        """Process a refund via Paddle Adjustments API.
        
        Paddle uses "adjustments" to issue refunds/credits on transactions.
        This is a REAL monetary action — requires approval_required safety level.
        
        Flow:
          1. If transaction_id provided → create adjustment directly
          2. If only customer_id → find latest transaction for customer first
          3. Create adjustment (full or partial) via Paddle API
          4. Return adjustment details
        
        Args:
            company_id: Company ID (BC-001).
            customer_id: Paddle customer ID.
            amount: Refund amount (used for partial refunds).
            reason: Reason for the refund.
            ticket_id: Related ticket ID (for audit trail).
            transaction_id: Paddle transaction ID to refund (optional — auto-find if not given).
            partial: If True, do a partial refund for the given amount.
        """
        try:
            # Map reason to Paddle's accepted reason values
            paddle_reason = self._map_refund_reason(reason)
            
            # Step 1: Find transaction if not provided
            if not transaction_id:
                logger.info(
                    "refund_finding_transaction: company=%s, customer=%s",
                    company_id, customer_id,
                )
                txn_result = await self.client.list_transactions(
                    customer_id=customer_id,
                    status="completed",
                    per_page=5,
                )
                transactions = txn_result.get("data", [])
                if not transactions:
                    return {
                        "success": False,
                        "message": f"No completed transactions found for customer {customer_id}. Cannot process refund.",
                    }
                transaction_id = transactions[0].get("id", "")
                logger.info(
                    "refund_found_transaction: txn=%s, customer=%s",
                    transaction_id, customer_id,
                )
            
            # Step 2: Build adjustment items
            adjustment_items = None
            if partial and amount:
                # Partial refund — need to specify amount per item
                # First get the transaction to find its items
                try:
                    txn_detail = await self.client.get_transaction(transaction_id)
                    txn_items = txn_detail.get("data", {}).get("details", {}).get("line_items", [])
                    if txn_items:
                        # Apply partial amount to the first item
                        first_item = txn_items[0]
                        adjustment_items = [{
                            "item_id": first_item.get("id", ""),
                            "type": "partial",
                            "amount": str(amount),
                        }]
                except Exception as e:
                    logger.warning(
                        "refund_partial_item_lookup_failed: txn=%s, error=%s",
                        transaction_id, str(e)[:100],
                    )
            
            # Step 3: Create adjustment via Paddle API
            description_parts = [f"Refund for company {company_id}"]
            if ticket_id:
                description_parts.append(f"Related ticket: {ticket_id}")
            description_parts.append(f"Reason: {reason}")
            description = ". ".join(description_parts)
            
            adjustment_result = await self.client.create_adjustment(
                transaction_id=transaction_id,
                items=adjustment_items,
                reason=paddle_reason,
                description=description,
            )
            
            adjustment_data = adjustment_result.get("data", adjustment_result)
            adjustment_id = adjustment_data.get("id", "")
            adjustment_status = adjustment_data.get("status", "pending")
            
            # Calculate refund total from adjustment
            refund_total = adjustment_data.get("details", {}).get("totals", {}).get("total", "0")
            
            logger.info(
                "refund_adjustment_created: company=%s, customer=%s, txn=%s, "
                "adjustment=%s, status=%s, amount=%.2f, reason=%s",
                company_id, customer_id, transaction_id,
                adjustment_id, adjustment_status, amount, reason,
            )
            
            return {
                "success": True,
                "source": "paddle_api",
                "customer_id": customer_id,
                "transaction_id": transaction_id,
                "adjustment_id": adjustment_id,
                "refund_amount": amount,
                "refund_total": refund_total,
                "reason": reason,
                "paddle_reason": paddle_reason,
                "ticket_id": ticket_id,
                "status": adjustment_status,
                "partial": partial,
                "message": (
                    f"Refund of ${amount:.2f} has been submitted via Paddle Adjustments API. "
                    f"Adjustment ID: {adjustment_id}. Status: {adjustment_status}. "
                    f"The refund will be processed within 3-5 business days."
                ),
            }
            
        except PaddleAuthError:
            return {
                "success": False,
                "message": "Paddle authentication failed. Check API key has adjustments:create permission.",
            }
        except PaddleNotFoundError:
            return {
                "success": False,
                "message": f"Transaction {transaction_id} not found on Paddle.",
            }
        except PaddleError as e:
            logger.error("refund_paddle_error: company=%s, error=%s", company_id, str(e))
            return {
                "success": False,
                "message": f"Paddle API error during refund: {str(e)[:200]}",
            }
        except Exception as e:
            logger.exception("process_refund_error: company=%s", company_id)
            return {
                "success": False,
                "message": f"Failed to process refund: {str(e)[:200]}",
            }
    
    @staticmethod
    def _map_refund_reason(reason: str) -> str:
        """Map free-text reason to Paddle's accepted adjustment reason values.
        
        Paddle accepts: duplicate, fraudulent, subscription_canceled,
        product_unsatisfactory, other
        """
        reason_lower = reason.lower().strip()
        reason_map = {
            "duplicate": "duplicate",
            "dup": "duplicate",
            "fraud": "fraudulent",
            "fraudulent": "fraudulent",
            "cancel": "subscription_canceled",
            "canceled": "subscription_canceled",
            "cancelled": "subscription_canceled",
            "subscription_canceled": "subscription_canceled",
            "unsatisfied": "product_unsatisfactory",
            "product_unsatisfactory": "product_unsatisfactory",
            "bad_product": "product_unsatisfactory",
            "not_working": "product_unsatisfactory",
            "defective": "product_unsatisfactory",
        }
        for key, paddle_value in reason_map.items():
            if key in reason_lower:
                return paddle_value
        return "other"
    
    # ── List Invoices ──
    
    async def list_invoices(
        self,
        company_id: str,
        paddle_customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List invoices from Paddle API."""
        try:
            if not paddle_customer_id:
                return {
                    "success": False,
                    "invoices": [],
                    "message": "No Paddle customer ID found.",
                }
            
            result = await self.client.list_invoices(
                customer_id=paddle_customer_id,
                per_page=20,
            )
            
            invoices = result.get("data", [])
            invoice_list = []
            for inv in invoices:
                invoice_list.append({
                    "id": inv.get("id", ""),
                    "number": inv.get("invoice_number", ""),
                    "amount": inv.get("details", {}).get("totals", {}).get("total", "0"),
                    "currency": inv.get("currency_code", "USD"),
                    "status": inv.get("status", "unknown"),
                    "date": inv.get("created_at", "")[:10],
                })
            
            return {
                "success": True,
                "source": "paddle_api",
                "invoices": invoice_list,
                "total_count": len(invoice_list),
            }
            
        except Exception as e:
            logger.exception("list_invoices_error: company=%s", company_id)
            return {
                "success": False,
                "invoices": [],
                "message": f"Failed to list invoices: {str(e)[:200]}",
            }
    
    # ── List Customers (for testing/lookup) ──
    
    async def list_customers(
        self,
        email: Optional[str] = None,
        per_page: int = 10,
    ) -> Dict[str, Any]:
        """List customers from Paddle. Useful for testing."""
        try:
            result = await self.client.list_customers(email=email, per_page=per_page)
            customers = result.get("data", [])
            return {
                "success": True,
                "customers": customers,
                "total_count": len(customers),
            }
        except Exception as e:
            return {
                "success": False,
                "customers": [],
                "message": f"Failed to list customers: {str(e)[:200]}",
            }
    
    # ── List Subscriptions (for testing/lookup) ──
    
    async def list_subscriptions(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        per_page: int = 10,
    ) -> Dict[str, Any]:
        """List subscriptions from Paddle. Useful for testing."""
        try:
            result = await self.client.list_subscriptions(
                customer_id=customer_id,
                status=status,
                per_page=per_page,
            )
            subscriptions = result.get("data", [])
            return {
                "success": True,
                "subscriptions": subscriptions,
                "total_count": len(subscriptions),
            }
        except Exception as e:
            return {
                "success": False,
                "subscriptions": [],
                "message": f"Failed to list subscriptions: {str(e)[:200]}",
            }


# ── Factory Function ────────────────────────────────────────────────────

_bridge: Optional[JarvisPaddleBridge] = None

def get_jarvis_paddle_bridge(
    api_key: Optional[str] = None,
    client_token: Optional[str] = None,
    sandbox: bool = True,
) -> JarvisPaddleBridge:
    """Get or create the Jarvis-Paddle bridge singleton."""
    global _bridge
    if _bridge is None:
        if not api_key:
            try:
                # Prefer app config (which reads .env via pydantic-settings)
                from app.config import get_settings
                settings = get_settings()
                api_key = settings.PADDLE_API_KEY
                client_token = client_token or settings.PADDLE_CLIENT_TOKEN
                sandbox = settings.ENVIRONMENT != "production"
            except Exception:
                # Fallback to raw env vars if config is unavailable
                try:
                    import os
                    api_key = os.environ.get("PADDLE_API_KEY", "")
                    client_token = client_token or os.environ.get("PADDLE_CLIENT_TOKEN", "")
                    env = os.environ.get("ENVIRONMENT", "sandbox")
                    sandbox = env != "production"
                except Exception:
                    api_key = api_key or ""
        
        _bridge = JarvisPaddleBridge(
            api_key=api_key or "",
            client_token=client_token,
            sandbox=sandbox,
        )
        logger.info("jarvis_paddle_bridge_initialized sandbox=%s", sandbox)
    
    return _bridge


async def close_jarvis_paddle_bridge() -> None:
    """Close the bridge and its Paddle client."""
    global _bridge
    if _bridge:
        await _bridge.close()
        _bridge = None
