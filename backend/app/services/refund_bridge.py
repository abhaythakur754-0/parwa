"""
PARWA Refund Bridge — Shopify + Paddle Atomic Refund Service

When a PARWA client (e-commerce business) needs to refund a customer:
  1. Create refund in Shopify (marks order items as refunded)
  2. Create Paddle adjustment (processes the actual money back)
  3. Track refund in ClientRefundService (audit trail)

This bridge ensures BOTH systems are updated. If Paddle fails after
Shopify succeeds, the refund is marked "partial" and flagged for
manual reconciliation.

Input:  order_id + items + amount
Output: refund object (ties into Paddle for payment processing)

BC-001: All operations scoped to company_id
BC-002: All money calculations use Decimal
BC-008: Never crash — graceful degradation on failure
BC-012: All timestamps UTC
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.logger import get_logger

logger = get_logger("refund_bridge")


class RefundItem:
    """Represents a single line item to refund."""

    def __init__(
        self,
        line_item_id: str,
        quantity: int = 1,
        amount: Optional[str] = None,
        reason: str = "",
    ):
        self.line_item_id = line_item_id
        self.quantity = quantity
        self.amount = Decimal(amount) if amount else None
        self.reason = reason

    def to_shopify_dict(self) -> Dict[str, Any]:
        """Convert to Shopify refund_line_items format."""
        item: Dict[str, Any] = {
            "line_item_id": self.line_item_id,
            "quantity": self.quantity,
        }
        if self.amount is not None:
            item["restock_type"] = "return"
        return item

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_item_id": self.line_item_id,
            "quantity": self.quantity,
            "amount": str(self.amount) if self.amount else None,
            "reason": self.reason,
        }


class RefundResult:
    """Result of a refund initiate operation."""

    def __init__(
        self,
        success: bool,
        refund_id: str = "",
        shopify_refund_id: str = "",
        paddle_adjustment_id: str = "",
        client_refund_id: str = "",
        order_id: str = "",
        amount: str = "0.00",
        currency: str = "USD",
        status: str = "pending",
        shopify_status: str = "",
        paddle_status: str = "",
        items_refunded: Optional[List[Dict[str, Any]]] = None,
        error: str = "",
        requires_reconciliation: bool = False,
    ):
        self.success = success
        self.refund_id = refund_id
        self.shopify_refund_id = shopify_refund_id
        self.paddle_adjustment_id = paddle_adjustment_id
        self.client_refund_id = client_refund_id
        self.order_id = order_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.shopify_status = shopify_status
        self.paddle_status = paddle_status
        self.items_refunded = items_refunded or []
        self.error = error
        self.requires_reconciliation = requires_reconciliation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "refund_id": self.refund_id,
            "shopify_refund_id": self.shopify_refund_id,
            "paddle_adjustment_id": self.paddle_adjustment_id,
            "client_refund_id": self.client_refund_id,
            "order_id": self.order_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "shopify_status": self.shopify_status,
            "paddle_status": self.paddle_status,
            "items_refunded": self.items_refunded,
            "error": self.error,
            "requires_reconciliation": self.requires_reconciliation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class RefundBridge:
    """
    Bridge between Shopify and Paddle for atomic refund processing.

    Usage:
        bridge = RefundBridge()
        result = await bridge.initiate_refund(
            company_id="BC-001",
            order_id="12345",
            items=[{"line_item_id": "li_1", "quantity": 1}],
            amount="29.99",
            reason="Product defective",
            shopify_client=client,
            paddle_bridge=paddle_bridge,
        )
    """

    def __init__(self):
        self._refund_counter = 0

    def _generate_refund_id(self) -> str:
        """Generate a unique refund tracking ID."""
        self._refund_counter += 1
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"rf_{ts}_{self._refund_counter:04d}"

    async def initiate_refund(
        self,
        company_id: str,
        order_id: str,
        items: List[Dict[str, Any]],
        amount: Optional[str] = None,
        reason: str = "",
        currency: str = "USD",
        notify_customer: bool = True,
        shopify_client: Optional[Any] = None,
        paddle_bridge: Optional[Any] = None,
        paddle_customer_id: Optional[str] = None,
        paddle_transaction_id: Optional[str] = None,
    ) -> RefundResult:
        """Initiate a refund across Shopify and Paddle.

        This is the PRIMARY entry point for the Refund Initiate Tool.
        Input:  order_id + items + amount
        Output: refund object (ties into Paddle for payment processing)

        Flow:
          1. Validate inputs
          2. Create Shopify refund (marks order items as refunded)
          3. Create Paddle adjustment (processes actual money)
          4. Track in ClientRefundService (audit trail)
          5. Return consolidated refund result

        If Paddle fails after Shopify succeeds, the refund is marked
        "partial" and flagged for manual reconciliation.

        Args:
            company_id: PARWA company ID (BC-001).
            order_id: Shopify order ID to refund.
            items: List of items to refund, each with:
                - line_item_id: Shopify line item ID (required)
                - quantity: Number of units to refund (default 1)
                - amount: Per-item refund amount for partial (optional)
            amount: Total refund amount. If provided, overrides sum of items.
                    If None, refunds full order amount.
            reason: Refund reason text.
            currency: Currency code (default USD).
            notify_customer: Whether to email the customer.
            shopify_client: ShopifyClient instance for API calls.
            paddle_bridge: JarvisPaddleBridge instance for Paddle calls.
            paddle_customer_id: Paddle customer ID for refund lookup.
            paddle_transaction_id: Paddle transaction ID for direct refund.

        Returns:
            RefundResult with consolidated status across all systems.
        """
        refund_id = self._generate_refund_id()
        is_partial = amount is not None and amount != ""

        logger.info(
            "refund_initiate: refund_id=%s, company=%s, order=%s, items=%d, "
            "amount=%s, partial=%s, reason=%s",
            refund_id, company_id, order_id, len(items),
            amount, is_partial, reason[:50],
        )

        # ── Step 1: Validate inputs ──────────────────────────────
        if not order_id:
            return RefundResult(
                success=False,
                refund_id=refund_id,
                error="order_id is required",
                status="failed",
            )

        if not items:
            # If no items specified, try to auto-detect from order
            if shopify_client:
                auto_items = await self._auto_detect_items(
                    shopify_client, order_id
                )
                if auto_items:
                    items = auto_items
                    logger.info(
                        "refund_auto_detected_items: refund_id=%s, items=%d",
                        refund_id, len(items),
                    )
                else:
                    return RefundResult(
                        success=False,
                        refund_id=refund_id,
                        order_id=order_id,
                        error="No items provided and could not auto-detect from order",
                        status="failed",
                    )
            else:
                return RefundResult(
                    success=False,
                    refund_id=refund_id,
                    order_id=order_id,
                    error="No items provided and no Shopify client available",
                    status="failed",
                )

        # Parse items into RefundItem objects
        refund_items = []
        for item_data in items:
            refund_items.append(RefundItem(
                line_item_id=str(item_data.get("line_item_id", "")),
                quantity=int(item_data.get("quantity", 1)),
                amount=item_data.get("amount"),
                reason=item_data.get("reason", reason),
            ))

        # Calculate total refund amount
        if amount:
            total_amount = Decimal(amount)
        else:
            # Sum item amounts or use 0 (will be filled by Shopify)
            item_total = sum(
                item.amount or Decimal("0") for item in refund_items
            )
            total_amount = item_total if item_total > 0 else Decimal("0")

        # ── Step 2: Create Shopify refund ─────────────────────────
        shopify_result_data: Dict[str, Any] = {}
        shopify_success = False
        shopify_error = ""

        if shopify_client:
            try:
                shopify_line_items = [
                    item.to_shopify_dict() for item in refund_items
                ]

                # Build Shopify transactions if amount is specified
                shopify_transactions = None
                if is_partial and total_amount > 0:
                    shopify_transactions = [{
                        "parent_id": None,  # Will use order's transaction
                        "amount": str(total_amount),
                        "kind": "refund",
                    }]

                shopify_result = await shopify_client.create_refund(
                    order_id=order_id,
                    refund_line_items=shopify_line_items,
                    transactions=shopify_transactions,
                    note=f"[PARWA] {reason}" if reason else "[PARWA] Refund initiated via PARWA",
                    notify_customer=notify_customer,
                )

                if shopify_result.success:
                    shopify_success = True
                    shopify_result_data = shopify_result.data
                    # Get actual refunded amount from Shopify response
                    if not is_partial and shopify_result_data.get("transactions"):
                        for txn in shopify_result_data["transactions"]:
                            if txn.get("kind") == "refund":
                                total_amount = Decimal(
                                    str(txn.get("amount", total_amount))
                                )
                                currency = txn.get("currency", currency)
                                break
                else:
                    shopify_error = shopify_result.error
                    logger.warning(
                        "refund_shopify_failed: refund_id=%s, error=%s",
                        refund_id, shopify_error[:200],
                    )
            except Exception as exc:
                shopify_error = f"Shopify refund exception: {str(exc)[:200]}"
                logger.error(
                    "refund_shopify_exception: refund_id=%s, error=%s",
                    refund_id, shopify_error,
                )
        else:
            # No Shopify client — mark as skipped (for non-Shopify platforms)
            shopify_success = True
            shopify_result_data = {"note": "No Shopify client — skipped Shopify refund"}

        # ── Step 3: Create Paddle adjustment ──────────────────────
        paddle_result_data: Dict[str, Any] = {}
        paddle_success = False
        paddle_error = ""

        if paddle_bridge:
            try:
                paddle_result = await paddle_bridge.process_refund(
                    company_id=company_id,
                    customer_id=paddle_customer_id or "",
                    amount=float(total_amount) if total_amount > 0 else 0.0,
                    reason=reason or "Refund initiated via PARWA",
                    transaction_id=paddle_transaction_id,
                    partial=is_partial,
                )

                if paddle_result.get("success", False):
                    paddle_success = True
                    paddle_result_data = paddle_result
                else:
                    paddle_error = paddle_result.get("message", "Paddle refund failed")
                    logger.warning(
                        "refund_paddle_failed: refund_id=%s, error=%s",
                        refund_id, paddle_error[:200],
                    )
            except Exception as exc:
                paddle_error = f"Paddle refund exception: {str(exc)[:200]}"
                logger.error(
                    "refund_paddle_exception: refund_id=%s, error=%s",
                    refund_id, paddle_error,
                )
        else:
            # No Paddle bridge — mark as skipped
            paddle_success = True
            paddle_result_data = {"note": "No Paddle bridge — skipped payment refund"}

        # ── Step 4: Determine final status ────────────────────────
        requires_reconciliation = False

        if shopify_success and paddle_success:
            final_status = "processed"
        elif shopify_success and not paddle_success:
            # Shopify refunded but Paddle failed — needs reconciliation
            final_status = "partial"
            requires_reconciliation = True
            logger.critical(
                "refund_requires_reconciliation: refund_id=%s, shopify=OK, "
                "paddle=FAILED (%s). Manual payment refund needed!",
                refund_id, paddle_error[:100],
            )
        elif not shopify_success and paddle_success:
            # Rare: Paddle refunded but Shopify failed
            final_status = "partial"
            requires_reconciliation = True
            logger.critical(
                "refund_requires_reconciliation: refund_id=%s, shopify=FAILED "
                "(%s), paddle=OK. Manual Shopify refund needed!",
                refund_id, shopify_error[:100],
            )
        else:
            final_status = "failed"

        # ── Step 5: Track in ClientRefundService ──────────────────
        client_refund_id = ""
        try:
            from app.services.client_refund_service import get_client_refund_service
            refund_service = get_client_refund_service()
            client_refund = refund_service.create_refund_request(
                company_id=UUID(company_id) if len(company_id) > 20 else company_id,
                amount=total_amount if total_amount > 0 else Decimal("0"),
                currency=currency,
                reason=f"Shopify order {order_id}: {reason}" if reason else f"Shopify order {order_id}",
                external_ref=refund_id,
            )
            client_refund_id = str(client_refund.get("id", ""))

            # Auto-process if both systems succeeded
            if final_status == "processed" and client_refund_id:
                try:
                    refund_service.process_refund(
                        company_id=UUID(company_id) if len(company_id) > 20 else company_id,
                        refund_id=client_refund_id,
                        external_ref=refund_id,
                    )
                except Exception:
                    pass  # Non-critical — refund is tracked

        except ImportError:
            logger.debug("client_refund_service_not_available")
        except Exception as exc:
            logger.warning(
                "refund_tracking_failed: refund_id=%s, error=%s",
                refund_id, str(exc)[:200],
            )

        # ── Build result ──────────────────────────────────────────
        shopify_refund_id = str(shopify_result_data.get("id", ""))
        paddle_adjustment_id = paddle_result_data.get("adjustment_id", "")

        result = RefundResult(
            success=final_status in ("processed", "partial"),
            refund_id=refund_id,
            shopify_refund_id=shopify_refund_id,
            paddle_adjustment_id=paddle_adjustment_id,
            client_refund_id=client_refund_id,
            order_id=order_id,
            amount=str(total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            currency=currency,
            status=final_status,
            shopify_status="processed" if shopify_success else f"failed: {shopify_error[:100]}",
            paddle_status="processed" if paddle_success else f"failed: {paddle_error[:100]}",
            items_refunded=[item.to_dict() for item in refund_items],
            error="" if final_status == "processed" else (
                f"Partial refund — reconciliation required. "
                f"Shopify: {'OK' if shopify_success else shopify_error[:50]}, "
                f"Paddle: {'OK' if paddle_success else paddle_error[:50]}"
                if requires_reconciliation else
                f"Shopify: {shopify_error[:100]}, Paddle: {paddle_error[:100]}"
            ),
            requires_reconciliation=requires_reconciliation,
        )

        logger.info(
            "refund_completed: refund_id=%s, status=%s, amount=%s %s, "
            "shopify=%s, paddle=%s, reconciliation=%s",
            refund_id, final_status, result.amount, currency,
            "OK" if shopify_success else "FAIL",
            "OK" if paddle_success else "FAIL",
            requires_reconciliation,
        )

        return result

    async def _auto_detect_items(
        self,
        shopify_client: Any,
        order_id: str,
    ) -> List[Dict[str, Any]]:
        """Auto-detect refundable items from a Shopify order.

        When no items are specified, this fetches the order and creates
        refund entries for all line items.

        Args:
            shopify_client: ShopifyClient instance.
            order_id: Shopify order ID.

        Returns:
            List of item dicts with line_item_id and quantity.
        """
        try:
            result = await shopify_client.get_order(order_id)
            if not result.success:
                return []

            line_items = result.data.get("line_items", [])
            items = []
            for item in line_items:
                items.append({
                    "line_item_id": str(item.get("id", "")),
                    "quantity": item.get("quantity", 1),
                    "title": item.get("title", ""),
                    "price": item.get("price", "0"),
                })
            return items

        except Exception as exc:
            logger.warning(
                "auto_detect_items_failed: order=%s, error=%s",
                order_id, str(exc)[:200],
            )
            return []

    async def get_refund_history(
        self,
        company_id: str,
        order_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get refund history for a company.

        Delegates to ClientRefundService for database-backed history.

        Args:
            company_id: PARWA company ID.
            order_id: Optional Shopify order ID filter.
            status: Optional status filter.
            page: Page number.
            page_size: Items per page.

        Returns:
            Dict with refunds list and pagination info.
        """
        try:
            from app.services.client_refund_service import get_client_refund_service
            refund_service = get_client_refund_service()
            return refund_service.list_refunds(
                company_id=UUID(company_id) if len(company_id) > 20 else company_id,
                status=status,
                page=page,
                page_size=page_size,
            )
        except ImportError:
            return {"refunds": [], "pagination": {"page": page, "page_size": page_size, "total": 0, "total_pages": 0}}
        except Exception as exc:
            logger.warning(
                "refund_history_failed: company=%s, error=%s",
                company_id, str(exc)[:200],
            )
            return {"refunds": [], "pagination": {"page": page, "page_size": page_size, "total": 0, "total_pages": 0}}

    async def get_order_refunds(
        self,
        shopify_client: Any,
        order_id: str,
    ) -> Dict[str, Any]:
        """Get refunds from Shopify for a specific order.

        Args:
            shopify_client: ShopifyClient instance.
            order_id: Shopify order ID.

        Returns:
            Dict with refund list from Shopify.
        """
        try:
            result = await shopify_client.list_refunds(order_id)
            if result.success:
                refunds = result.data if isinstance(result.data, list) else []
                return {
                    "success": True,
                    "order_id": order_id,
                    "refunds": refunds,
                    "total": len(refunds),
                }
            return {
                "success": False,
                "order_id": order_id,
                "refunds": [],
                "error": result.error,
            }
        except Exception as exc:
            return {
                "success": False,
                "order_id": order_id,
                "refunds": [],
                "error": str(exc)[:200],
            }


# ── Singleton ──────────────────────────────────────────────────────

_refund_bridge: Optional[RefundBridge] = None


def get_refund_bridge() -> RefundBridge:
    """Get the RefundBridge singleton."""
    global _refund_bridge
    if _refund_bridge is None:
        _refund_bridge = RefundBridge()
    return _refund_bridge
