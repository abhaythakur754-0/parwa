"""
PARWA Shopify Integration API Router

Endpoints for Shopify data management and sync operations.
These endpoints allow PARWA to interact with a company's connected
Shopify store — sync data, manage webhooks, and query orders/products.

- POST /api/shopify/sync/full     — Full sync of all Shopify data
- POST /api/shopify/sync/incremental — Incremental sync since last sync
- GET  /api/shopify/sync/status   — Get current sync status
- GET  /api/shopify/orders/{id}   — Get a Shopify order
- GET  /api/shopify/orders        — List Shopify orders
- GET  /api/shopify/products/{id} — Get a Shopify product
- GET  /api/shopify/products      — List Shopify products
- GET  /api/shopify/customers/{id} — Get a Shopify customer
- GET  /api/shopify/customers     — List Shopify customers
- POST /api/shopify/fulfillments  — Create a fulfillment
- POST /api/shopify/refunds       — Create a refund
- GET  /api/shopify/webhooks      — List registered webhooks
- POST /api/shopify/webhooks      — Register a webhook
- DELETE /api/shopify/webhooks/{id} — Delete a webhook

BC-001: All operations scoped to authenticated user's company_id.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.clients.shopify_client import ShopifyClient, ShopifyResult, create_shopify_client_from_config
from app.logger import get_logger
from app.services.shopify_data_sync import ShopifyDataSync, SyncResult
from database.base import get_db
from database.models.core import User
from database.models.integration import Integration

logger = get_logger("api.shopify")

router = APIRouter(prefix="/api/shopify", tags=["Shopify Integration"])


# ── Request/Response Schemas ─────────────────────────────────────


class SyncResponse(BaseModel):
    """Response for sync operations."""
    status: str
    orders_synced: int = 0
    products_synced: int = 0
    customers_synced: int = 0
    total_synced: int = 0
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """Response for sync status."""
    company_id: str
    integration_id: str
    shop_domain: str
    status: str
    last_full_sync: Optional[str] = None
    last_incremental_sync: Optional[str] = None
    total_orders_synced: int = 0
    total_products_synced: int = 0
    total_customers_synced: int = 0


class OrderResponse(BaseModel):
    """Response with Shopify order data."""
    order_id: str
    order_number: str = ""
    email: str = ""
    total_price: str = "0"
    currency: str = "USD"
    financial_status: str = ""
    fulfillment_status: str = ""
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    customer_id: str = ""
    customer_name: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductResponse(BaseModel):
    """Response with Shopify product data."""
    product_id: str
    title: str = ""
    vendor: str = ""
    product_type: str = ""
    status: str = ""
    variants: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None


class CustomerResponse(BaseModel):
    """Response with Shopify customer data."""
    customer_id: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    orders_count: int = 0
    total_spent: str = "0.00"
    created_at: Optional[str] = None


class CreateFulfillmentRequest(BaseModel):
    """Request to create a fulfillment."""
    order_id: str = Field(..., description="Shopify order ID")
    tracking_number: str = Field("", description="Tracking number")
    tracking_url: str = Field("", description="Tracking URL")
    tracking_company: str = Field("", description="Carrier name")
    notify_customer: bool = Field(True, description="Notify customer")


class RefundLineItem(BaseModel):
    """A single line item to refund."""
    line_item_id: str = Field(..., description="Shopify line item ID")
    quantity: int = Field(1, ge=1, description="Quantity to refund")
    amount: Optional[str] = Field(None, description="Per-item refund amount for partial refunds")


class CreateRefundRequest(BaseModel):
    """Request to create a refund.

    Day 5 Update: Now supports partial refunds with specific line items
    and amounts. Also supports Paddle payment processing via RefundBridge.
    """
    order_id: str = Field(..., description="Shopify order ID")
    items: Optional[List[RefundLineItem]] = Field(
        None,
        description="Line items to refund. If empty, all items are refunded.",
    )
    amount: Optional[str] = Field(
        None,
        description="Total refund amount. If provided, overrides sum of items.",
    )
    reason: str = Field("", description="Refund reason")
    notify_customer: bool = Field(True, description="Notify customer")
    process_payment: bool = Field(
        True,
        description="Also process refund via Paddle (payment processing). "
                    "Set to False for Shopify-only refunds.",
    )


class WebhookRegistrationRequest(BaseModel):
    """Request to register a webhook with Shopify."""
    topic: str = Field(..., description="Event topic (e.g., orders/create)")
    address: str = Field(..., description="Webhook callback URL")
    format: str = Field("json", description="Payload format")


class WebhookResponse(BaseModel):
    """Response with webhook data."""
    webhook_id: str
    topic: str
    address: str
    format: str = "json"
    created_at: Optional[str] = None


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


# ── Helper: Get Shopify Client ──────────────────────────────────


def _get_shopify_integration(user: User, db: Session) -> Dict[str, Any]:
    """Get the company's active Shopify integration.

    Raises HTTPException if no active Shopify integration found.

    Returns:
        Dict with integration data and config.
    """
    integration = db.query(Integration).filter(
        Integration.company_id == user.company_id,
        Integration.integration_type == "shopify",
        Integration.status == "active",
    ).first()

    if not integration:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NO_SHOPIFY_INTEGRATION",
                "message": "No active Shopify integration found for your company. "
                           "Please connect your Shopify store first.",
            },
        )

    config = {}
    try:
        config = json.loads(integration.credentials_encrypted) if integration.credentials_encrypted else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "integration_id": integration.id,
        "config": config,
        "shop_domain": config.get("shop_domain", ""),
        "access_token": config.get("access_token", ""),
    }


def _create_client(integration: Dict[str, Any]) -> ShopifyClient:
    """Create a ShopifyClient from integration data."""
    if not integration["shop_domain"] or not integration["access_token"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_SHOPIFY_CONFIG",
                "message": "Shopify integration is missing shop_domain or access_token.",
            },
        )

    return ShopifyClient(
        shop_domain=integration["shop_domain"],
        access_token=integration["access_token"],
    )


def _get_paddle_bridge() -> Optional[Any]:
    """Get a JarvisPaddleBridge instance if Paddle is configured.

    Returns None if Paddle is not configured (graceful degradation).
    Day 5 Addition: Used for refund payment processing.
    """
    try:
        import os
        from app.services.jarvis_paddle_bridge import JarvisPaddleBridge

        api_key = os.environ.get("PADDLE_API_KEY", "")
        if not api_key:
            return None

        sandbox = os.environ.get("ENVIRONMENT", "development") != "production"
        return JarvisPaddleBridge(
            api_key=api_key,
            client_token=os.environ.get("PADDLE_CLIENT_TOKEN", ""),
            sandbox=sandbox,
        )
    except ImportError:
        logger.debug("paddle_bridge_not_available_for_refund")
        return None
    except Exception as exc:
        logger.warning("paddle_bridge_init_failed error=%s", str(exc)[:200])
        return None


# ── Sync Endpoints ──────────────────────────────────────────────


@router.post("/sync/full", response_model=SyncResponse)
async def full_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Perform a full sync of all Shopify data.

    Fetches all orders, products, and customers from the connected
    Shopify store. This is a comprehensive sync that should be used
    when first connecting a store or after a long period of inactivity.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    sync_service = ShopifyDataSync(
        db=db,
        shopify_client=client,
        company_id=str(user.company_id),
        integration_id=integration["integration_id"],
    )

    result = await sync_service.full_sync()
    return SyncResponse(**result.to_dict())


@router.post("/sync/incremental", response_model=SyncResponse)
async def incremental_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Perform an incremental sync of Shopify data.

    Only fetches records updated since the last successful sync.
    Much faster than a full sync and suitable for regular scheduling.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    sync_service = ShopifyDataSync(
        db=db,
        shopify_client=client,
        company_id=str(user.company_id),
        integration_id=integration["integration_id"],
    )

    result = await sync_service.incremental_sync()
    return SyncResponse(**result.to_dict())


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current sync status for the Shopify integration.

    Returns information about the last sync, including timestamps
    and counts of synced records.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    sync_service = ShopifyDataSync(
        db=db,
        shopify_client=client,
        company_id=str(user.company_id),
        integration_id=integration["integration_id"],
    )

    status = sync_service.get_sync_status()
    return SyncStatusResponse(**status)


# ── Order Endpoints ─────────────────────────────────────────────


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a Shopify order by ID.

    Fetches order data directly from Shopify API.

    BC-001: Scoped to user's company_id via Shopify integration.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.get_order(order_id)
    if not result.success:
        raise HTTPException(status_code=404, detail={"error": result.error})

    order = result.data
    return OrderResponse(
        order_id=str(order.get("id", "")),
        order_number=str(order.get("order_number", "")),
        email=order.get("email", ""),
        total_price=str(order.get("total_price", "0")),
        currency=order.get("currency", "USD"),
        financial_status=order.get("financial_status", ""),
        fulfillment_status=order.get("fulfillment_status", ""),
        line_items=[
            {
                "title": item.get("title", ""),
                "quantity": item.get("quantity", 1),
                "price": item.get("price", "0"),
                "sku": item.get("sku", ""),
            }
            for item in order.get("line_items", [])
        ],
        customer_id=str(order.get("customer", {}).get("id", "")),
        customer_name=" ".join(filter(None, [
            order.get("customer", {}).get("first_name", ""),
            order.get("customer", {}).get("last_name", ""),
        ])),
        created_at=order.get("created_at"),
        updated_at=order.get("updated_at"),
    )


@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    status: str = Query("any", description="Order status filter"),
    limit: int = Query(50, ge=1, le=250, description="Results per page"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List orders from the connected Shopify store.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.list_orders(status=status, limit=limit)
    if not result.success:
        raise HTTPException(status_code=500, detail={"error": result.error})

    orders = result.data if isinstance(result.data, list) else []
    return [
        OrderResponse(
            order_id=str(order.get("id", "")),
            order_number=str(order.get("order_number", "")),
            email=order.get("email", ""),
            total_price=str(order.get("total_price", "0")),
            currency=order.get("currency", "USD"),
            financial_status=order.get("financial_status", ""),
            fulfillment_status=order.get("fulfillment_status", ""),
            created_at=order.get("created_at"),
            updated_at=order.get("updated_at"),
        )
        for order in orders
    ]


# ── Product Endpoints ───────────────────────────────────────────


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a Shopify product by ID.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.get_product(product_id)
    if not result.success:
        raise HTTPException(status_code=404, detail={"error": result.error})

    product = result.data
    return ProductResponse(
        product_id=str(product.get("id", "")),
        title=product.get("title", ""),
        vendor=product.get("vendor", ""),
        product_type=product.get("product_type", ""),
        status=product.get("status", ""),
        variants=[
            {
                "variant_id": str(v.get("id", "")),
                "title": v.get("title", ""),
                "price": v.get("price", "0"),
                "sku": v.get("sku", ""),
            }
            for v in product.get("variants", [])
        ],
        created_at=product.get("created_at"),
    )


@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    limit: int = Query(50, ge=1, le=250, description="Results per page"),
    status: str = Query("active", description="Product status filter"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List products from the connected Shopify store.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.list_products(limit=limit, status=status)
    if not result.success:
        raise HTTPException(status_code=500, detail={"error": result.error})

    products = result.data if isinstance(result.data, list) else []
    return [
        ProductResponse(
            product_id=str(product.get("id", "")),
            title=product.get("title", ""),
            vendor=product.get("vendor", ""),
            product_type=product.get("product_type", ""),
            status=product.get("status", ""),
            created_at=product.get("created_at"),
        )
        for product in products
    ]


# ── Customer Endpoints ──────────────────────────────────────────


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a Shopify customer by ID.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.get_customer(customer_id)
    if not result.success:
        raise HTTPException(status_code=404, detail={"error": result.error})

    customer = result.data
    return CustomerResponse(
        customer_id=str(customer.get("id", "")),
        email=customer.get("email", ""),
        first_name=customer.get("first_name", ""),
        last_name=customer.get("last_name", ""),
        phone=customer.get("phone", ""),
        orders_count=int(customer.get("orders_count", 0)),
        total_spent=str(customer.get("total_spent", "0.00")),
        created_at=customer.get("created_at"),
    )


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    limit: int = Query(50, ge=1, le=250, description="Results per page"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List customers from the connected Shopify store.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.list_customers(limit=limit)
    if not result.success:
        raise HTTPException(status_code=500, detail={"error": result.error})

    customers = result.data if isinstance(result.data, list) else []
    return [
        CustomerResponse(
            customer_id=str(customer.get("id", "")),
            email=customer.get("email", ""),
            first_name=customer.get("first_name", ""),
            last_name=customer.get("last_name", ""),
            phone=customer.get("phone", ""),
            orders_count=int(customer.get("orders_count", 0)),
            total_spent=str(customer.get("total_spent", "0.00")),
            created_at=customer.get("created_at"),
        )
        for customer in customers
    ]


# ── Fulfillment Endpoints ───────────────────────────────────────


@router.post("/fulfillments", response_model=Dict[str, Any])
async def create_fulfillment(
    body: CreateFulfillmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a fulfillment for a Shopify order with tracking info.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.create_fulfillment(
        order_id=body.order_id,
        tracking_number=body.tracking_number or None,
        tracking_url=body.tracking_url or None,
        tracking_company=body.tracking_company or None,
        notify_customer=body.notify_customer,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail={"error": result.error})

    return result.data


# ── Refund Endpoints ────────────────────────────────────────────


@router.post("/refunds", response_model=Dict[str, Any])
async def create_refund(
    body: CreateRefundRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a refund for a Shopify order.

    Day 5 Update: Supports partial refunds with specific line items and amounts.
    When process_payment=True (default), also processes refund via Paddle.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    # If items or amount specified, use RefundBridge for atomic processing
    if body.items or body.amount or body.process_payment:
        try:
            from app.services.refund_bridge import get_refund_bridge
            bridge = get_refund_bridge()

            # Get optional Paddle bridge
            paddle_bridge = _get_paddle_bridge()

            items_data = []
            if body.items:
                for item in body.items:
                    items_data.append({
                        "line_item_id": item.line_item_id,
                        "quantity": item.quantity,
                        "amount": item.amount,
                    })

            result = await bridge.initiate_refund(
                company_id=str(user.company_id),
                order_id=body.order_id,
                items=items_data,
                amount=body.amount,
                reason=body.reason,
                notify_customer=body.notify_customer,
                shopify_client=client,
                paddle_bridge=paddle_bridge if body.process_payment else None,
            )

            if not result.success:
                raise HTTPException(status_code=400, detail={"error": result.error})

            return result.to_dict()

        except ImportError:
            # RefundBridge not available — fall through to simple refund
            pass

    # Simple Shopify-only refund (no items, no amount)
    result = await client.create_refund(
        order_id=body.order_id,
        note=body.reason,
        notify_customer=body.notify_customer,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail={"error": result.error})

    return result.data


@router.get("/orders/{order_id}/refunds", response_model=Dict[str, Any])
async def list_order_refunds(
    order_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List refunds for a specific Shopify order.

    Day 5 Addition: Returns refund history from Shopify API.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.list_refunds(order_id)

    if not result.success:
        raise HTTPException(status_code=400, detail={"error": result.error})

    refunds = result.data if isinstance(result.data, list) else []
    return {
        "order_id": order_id,
        "refunds": refunds,
        "total": len(refunds),
    }


# ── Webhook Management Endpoints ────────────────────────────────


@router.get("/webhooks", response_model=List[Dict[str, Any]])
async def list_webhooks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List webhooks registered with Shopify.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.list_webhooks()
    if not result.success:
        raise HTTPException(status_code=500, detail={"error": result.error})

    webhooks = result.data if isinstance(result.data, list) else []
    return webhooks


@router.post("/webhooks", response_model=WebhookResponse)
async def register_webhook(
    body: WebhookRegistrationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a webhook with Shopify.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.create_webhook(
        topic=body.topic,
        address=body.address,
        format=body.format,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail={"error": result.error})

    webhook = result.data
    return WebhookResponse(
        webhook_id=str(webhook.get("id", "")),
        topic=webhook.get("topic", body.topic),
        address=webhook.get("address", body.address),
        format=webhook.get("format", body.format),
        created_at=webhook.get("created_at"),
    )


@router.delete("/webhooks/{webhook_id}", response_model=MessageResponse)
async def delete_webhook(
    webhook_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a webhook registration from Shopify.

    BC-001: Scoped to user's company_id.
    """
    integration = _get_shopify_integration(user, db)
    client = _create_client(integration)

    result = await client.delete_webhook(webhook_id)
    if not result.success:
        raise HTTPException(status_code=400, detail={"error": result.error})

    return MessageResponse(message=f"Webhook {webhook_id} deleted successfully.")
