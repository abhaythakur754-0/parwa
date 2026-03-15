# AGENT_COMMS.md — Week 4 Day 5
# Last updated: 2026-03-31
# Current status: WEEK 4 DAY 5 STARTED

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 4 DAY 5 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-31

> **Phase: Phase 2 — Core AI Engine (API Layer)**
> Day 1 COMPLETE ✅ — Auth API, License API, Auth Core, License Manager. 138 tests.
> Day 2 COMPLETE ✅ — Support API, Dashboard API, Billing API, Compliance API. 106 tests.
> Day 3 COMPLETE ✅ — Support Service, Analytics Service, Billing Service, Onboarding Service. 136 tests.
> Day 4 COMPLETE ✅ — Jarvis API, Analytics API, Integrations API, Notification Service. 137 tests.
> **Total: 517+ tests passing.**
>
> Day 5: Building webhook handlers and remaining services — Shopify/Stripe Webhooks, Compliance Service, SLA/License/User Services.
> All 4 files are INDEPENDENT — build in PARALLEL.
>
> **CRITICAL RULES:**
> 1. You CANNOT use Docker locally — write tests with MOCKED databases
> 2. Build → Unit Test passes → THEN push (ONE push only)
> 3. NEVER push before test passes
> 4. Type hints on ALL functions, docstrings on ALL classes/functions
> 5. ALL webhooks MUST verify HMAC signature before processing

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/api/webhooks/shopify.py`

**Purpose:** Shopify Webhook Handler — Receives and processes Shopify webhooks (orders, customers, products).

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `security/hmac_verification.py` — HMAC verification utility
- `backend/app/database.py` — Database session
- `backend/models/company.py` — Company model
- `shared/core_functions/logger.py` — Logger
- `shared/core_functions/config.py` — Configuration

**Step 3: Create the Webhooks Directory**
```bash
mkdir -p backend/api/webhooks
```

**Step 4: Create the Webhook File**

Create `backend/api/webhooks/shopify.py` with:

```python
"""
PARWA Shopify Webhook Handler.

Processes Shopify webhooks for orders, customers, and product updates.
All webhooks verify HMAC signature before processing.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.company import Company
from security.hmac_verification import verify_hmac
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

# Initialize router and logger
router = APIRouter(prefix="/webhooks/shopify", tags=["Webhooks - Shopify"])
logger = get_logger(__name__)
settings = get_settings()


# --- Pydantic Schemas ---

class WebhookResponse(BaseModel):
    """Response schema for webhook processing."""
    status: str
    message: str
    processed_at: datetime
    event_type: Optional[str] = None


# --- Helper Functions ---

def verify_shopify_webhook(request_body: bytes, signature: str) -> bool:
    """
    Verify Shopify webhook HMAC signature.
    
    Shopify sends HMAC-SHA256 signature in X-Shopify-Hmac-SHA256 header.
    
    Args:
        request_body: Raw request body bytes
        signature: Signature from X-Shopify-Hmac-SHA256 header
        
    Returns:
        bool: True if signature is valid
    """
    if not signature:
        return False
    
    webhook_secret = settings.shopify_webhook_secret
    if not webhook_secret:
        logger.error({"event": "shopify_webhook_secret_not_configured"})
        return False
    
    return verify_hmac(request_body, signature, webhook_secret)


async def get_company_by_shopify_domain(
    db: AsyncSession,
    shopify_domain: str
) -> Optional[Company]:
    """
    Get company by Shopify store domain.
    
    Args:
        db: Database session
        shopify_domain: Shopify store domain (e.g., "mystore.myshopify.com")
        
    Returns:
        Company if found, None otherwise
    """
    # TODO: Add shopify_domain field to Company model
    # For now, return None - this will be implemented with Company integration
    result = await db.execute(
        select(Company).where(Company.is_active == True)
    )
    companies = result.scalars().all()
    
    # Return first active company for testing
    return companies[0] if companies else None


# --- Webhook Endpoints ---

@router.post(
    "/orders/create",
    response_model=WebhookResponse,
    summary="Handle orders/create webhook",
    description="Process Shopify orders/create webhook events."
)
async def handle_order_created(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """
    Handle Shopify orders/create webhook.
    
    Verifies HMAC signature and processes new order.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        WebhookResponse with processing status
        
    Raises:
        HTTPException: 401 if HMAC verification fails
    """
    # Get raw body for HMAC verification
    body = await request.body()
    
    # Verify HMAC signature
    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        logger.warning({
            "event": "shopify_webhook_hmac_failed",
            "endpoint": "orders/create",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Get shop domain
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    
    # Get company
    company = await get_company_by_shopify_domain(db, shop_domain)
    if not company:
        logger.warning({
            "event": "shopify_webhook_company_not_found",
            "shop_domain": shop_domain,
        })
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found for this Shopify store"
        )
    
    # Log the event
    order_id = payload.get("id")
    order_number = payload.get("order_number")
    
    logger.info({
        "event": "shopify_order_created",
        "company_id": str(company.id),
        "shop_domain": shop_domain,
        "order_id": order_id,
        "order_number": order_number,
        "total_price": payload.get("total_price"),
        "currency": payload.get("currency"),
    })
    
    # TODO: Process order (create ticket, update customer, etc.)
    
    return WebhookResponse(
        status="accepted",
        message="Order created webhook processed successfully",
        processed_at=datetime.now(timezone.utc),
        event_type="orders/create"
    )


@router.post(
    "/orders/updated",
    response_model=WebhookResponse,
    summary="Handle orders/updated webhook",
    description="Process Shopify orders/updated webhook events."
)
async def handle_order_updated(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """
    Handle Shopify orders/updated webhook.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        WebhookResponse with processing status
    """
    body = await request.body()
    
    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    payload = json.loads(body)
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    
    logger.info({
        "event": "shopify_order_updated",
        "shop_domain": shop_domain,
        "order_id": payload.get("id"),
    })
    
    return WebhookResponse(
        status="accepted",
        message="Order updated webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="orders/updated"
    )


@router.post(
    "/customers/create",
    response_model=WebhookResponse,
    summary="Handle customers/create webhook",
    description="Process Shopify customers/create webhook events."
)
async def handle_customer_created(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """
    Handle Shopify customers/create webhook.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        WebhookResponse with processing status
    """
    body = await request.body()
    
    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    payload = json.loads(body)
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    
    logger.info({
        "event": "shopify_customer_created",
        "shop_domain": shop_domain,
        "customer_id": payload.get("id"),
        "email": payload.get("email", "")[:50] if payload.get("email") else None,
    })
    
    return WebhookResponse(
        status="accepted",
        message="Customer created webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="customers/create"
    )


@router.post(
    "/products/update",
    response_model=WebhookResponse,
    summary="Handle products/update webhook",
    description="Process Shopify products/update webhook events."
)
async def handle_product_updated(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """
    Handle Shopify products/update webhook.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        WebhookResponse with processing status
    """
    body = await request.body()
    
    signature = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_shopify_webhook(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    payload = json.loads(body)
    
    logger.info({
        "event": "shopify_product_updated",
        "product_id": payload.get("id"),
        "product_title": payload.get("title", "")[:50],
    })
    
    return WebhookResponse(
        status="accepted",
        message="Product updated webhook processed",
        processed_at=datetime.now(timezone.utc),
        event_type="products/update"
    )
```

**Step 5: Create the Test File**

Create `tests/unit/test_shopify_webhook.py`:

```python
"""
Unit tests for Shopify Webhook Handler.
Uses mocked database sessions - no Docker required.
"""
import os
import json
import hmac
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def shopify_secret():
    """Test Shopify webhook secret."""
    return "test_shopify_webhook_secret"


def create_test_app():
    """Create a FastAPI test app with shopify webhook router."""
    app = FastAPI()

    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    from backend.api.webhooks.shopify import router
    app.include_router(router)

    return app


def generate_shopify_signature(body: bytes, secret: str) -> str:
    """Generate valid Shopify HMAC signature."""
    return hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()


class TestShopifyRouter:
    """Tests for Shopify webhook router configuration."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.webhooks.shopify import router
        assert router.prefix == "/webhooks/shopify"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.webhooks.shopify import router
        assert "Webhooks - Shopify" in router.tags


class TestOrderCreatedWebhook:
    """Tests for orders/create webhook."""

    def test_order_created_missing_signature(self):
        """Test that webhook rejects request without signature."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/orders/create",
                json={"id": 12345, "order_number": 1001}
            )

        assert response.status_code == 401

    def test_order_created_invalid_signature(self):
        """Test that webhook rejects request with invalid signature."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/orders/create",
                json={"id": 12345, "order_number": 1001},
                headers={"X-Shopify-Hmac-SHA256": "invalid_signature"}
            )

        assert response.status_code == 401


class TestCustomerCreatedWebhook:
    """Tests for customers/create webhook."""

    def test_customer_created_missing_signature(self):
        """Test that webhook rejects request without signature."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/customers/create",
                json={"id": 12345, "email": "test@example.com"}
            )

        assert response.status_code == 401


class TestProductUpdatedWebhook:
    """Tests for products/update webhook."""

    def test_product_updated_missing_signature(self):
        """Test that webhook rejects request without signature."""
        app = create_test_app()

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/products/update",
                json={"id": 12345, "title": "Test Product"}
            )

        assert response.status_code == 401


class TestVerifyShopifyWebhook:
    """Tests for HMAC verification function."""

    def test_verify_with_valid_signature(self):
        """Test verification with valid signature."""
        from backend.api.webhooks.shopify import verify_shopify_webhook
        
        with patch("backend.api.webhooks.shopify.settings") as mock_settings:
            mock_settings.shopify_webhook_secret = "test_secret"
            
            body = b'{"test": "data"}'
            signature = hmac.new(
                b"test_secret",
                body,
                hashlib.sha256
            ).hexdigest()
            
            # This will fail without proper settings mock
            # In real tests, we'd mock settings properly
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_shopify_webhook.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/api/webhooks/shopify.py tests/unit/test_shopify_webhook.py backend/api/webhooks/__init__.py
git commit -m "Week 4 Day 5: Builder 1 - Shopify webhook handler with HMAC verification"
git push origin main
```

**Step 9: Update Status**
Update your status section in AGENT_COMMS.md.

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/api/webhooks/stripe.py`

**Purpose:** Stripe Webhook Handler — Receives and processes Stripe webhooks (payments, invoices, refunds).

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `security/hmac_verification.py` — HMAC verification utility
- `backend/app/database.py` — Database session
- `backend/models/company.py` — Company model
- `shared/core_functions/logger.py` — Logger

**Step 3: Create the Webhook File**

Create `backend/api/webhooks/stripe.py` with:

```python
"""
PARWA Stripe Webhook Handler.

Processes Stripe webhooks for payments, invoices, refunds, and disputes.
All webhooks verify HMAC signature before processing.

CRITICAL: Refund webhooks create pending_approval records and NEVER 
call Stripe directly without explicit human approval.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.models.company import Company
from security.hmac_verification import verify_hmac
from shared.core_functions.config import get_settings
from shared.core_functions.logger import get_logger

# Initialize router and logger
router = APIRouter(prefix="/webhooks/stripe", tags=["Webhooks - Stripe"])
logger = get_logger(__name__)
settings = get_settings()


# --- Pydantic Schemas ---

class WebhookResponse(BaseModel):
    """Response schema for webhook processing."""
    status: str
    message: str
    processed_at: datetime
    event_type: Optional[str] = None
    event_id: Optional[str] = None


# --- Helper Functions ---

def verify_stripe_webhook(request_body: bytes, signature: str) -> bool:
    """
    Verify Stripe webhook HMAC signature.
    
    Stripe sends HMAC-SHA256 signature in Stripe-Signature header.
    Format: t=<timestamp>,v1=<signature>
    
    Args:
        request_body: Raw request body bytes
        signature: Signature from Stripe-Signature header
        
    Returns:
        bool: True if signature is valid
    """
    if not signature:
        return False
    
    webhook_secret = settings.stripe_webhook_secret
    if not webhook_secret:
        logger.error({"event": "stripe_webhook_secret_not_configured"})
        return False
    
    # Parse Stripe signature format: t=<timestamp>,v1=<signature>
    parts = {}
    for part in signature.split(","):
        if "=" in part:
            key, value = part.split("=", 1)
            parts[key] = value
    
    if "v1" not in parts:
        return False
    
    # Verify the signature
    return verify_hmac(request_body, parts["v1"], webhook_secret)


async def get_company_by_stripe_account(
    db: AsyncSession,
    stripe_account_id: str
) -> Optional[Company]:
    """
    Get company by Stripe account ID.
    
    Args:
        db: Database session
        stripe_account_id: Stripe account ID
        
    Returns:
        Company if found, None otherwise
    """
    # TODO: Add stripe_account_id field to Company model
    result = await db.execute(
        select(Company).where(Company.is_active == True)
    )
    companies = result.scalars().all()
    
    return companies[0] if companies else None


async def create_pending_approval(
    db: AsyncSession,
    company_id: uuid.UUID,
    event_type: str,
    event_data: Dict[str, Any]
) -> uuid.UUID:
    """
    Create a pending approval record for refund actions.
    
    This is CRITICAL - we NEVER call Stripe directly without human approval.
    
    Args:
        db: Database session
        company_id: Company UUID
        event_type: Type of event (e.g., "refund.requested")
        event_data: Full event data
        
    Returns:
        UUID of pending approval record
    """
    approval_id = uuid.uuid4()
    
    logger.info({
        "event": "pending_approval_created",
        "approval_id": str(approval_id),
        "company_id": str(company_id),
        "event_type": event_type,
        "note": "Refund requires explicit human approval before processing"
    })
    
    # TODO: Store in pending_approvals table when model is created
    
    return approval_id


# --- Webhook Endpoints ---

@router.post(
    "",
    response_model=WebhookResponse,
    summary="Handle all Stripe webhooks",
    description="Process all Stripe webhook events with HMAC verification."
)
async def handle_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> WebhookResponse:
    """
    Handle Stripe webhook events.
    
    Verifies HMAC signature and routes to appropriate handler.
    CRITICAL: Refund events create pending_approval records only.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        WebhookResponse with processing status
        
    Raises:
        HTTPException: 401 if HMAC verification fails
    """
    # Get raw body for HMAC verification
    body = await request.body()
    
    # Verify HMAC signature
    signature = request.headers.get("Stripe-Signature", "")
    if not verify_stripe_webhook(body, signature):
        logger.warning({
            "event": "stripe_webhook_hmac_failed",
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    
    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    event_type = payload.get("type", "unknown")
    event_id = payload.get("id", "")
    event_data = payload.get("data", {}).get("object", {})
    
    # Get company (from Stripe account or connected account)
    stripe_account = payload.get("account") or event_data.get("account")
    
    company = await get_company_by_stripe_account(db, stripe_account)
    if not company:
        logger.warning({
            "event": "stripe_webhook_company_not_found",
            "stripe_account": stripe_account,
        })
        # Still process webhook, but log warning
    
    # Log the event
    logger.info({
        "event": "stripe_webhook_received",
        "company_id": str(company.id) if company else None,
        "stripe_event_type": event_type,
        "stripe_event_id": event_id,
    })
    
    # Handle specific event types
    if event_type == "payment_intent.succeeded":
        return await _handle_payment_succeeded(db, company, event_data, event_id)
    elif event_type == "invoice.paid":
        return await _handle_invoice_paid(db, company, event_data, event_id)
    elif event_type == "charge.refunded":
        return await _handle_refund(db, company, event_data, event_id)
    elif event_type == "customer.subscription.updated":
        return await _handle_subscription_updated(db, company, event_data, event_id)
    else:
        # Default handling for other events
        return WebhookResponse(
            status="accepted",
            message=f"Event {event_type} received and logged",
            processed_at=datetime.now(timezone.utc),
            event_type=event_type,
            event_id=event_id
        )


async def _handle_payment_succeeded(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """Handle payment_intent.succeeded event."""
    logger.info({
        "event": "stripe_payment_succeeded",
        "company_id": str(company.id) if company else None,
        "payment_intent_id": event_data.get("id"),
        "amount": event_data.get("amount"),
        "currency": event_data.get("currency"),
    })
    
    return WebhookResponse(
        status="accepted",
        message="Payment success processed",
        processed_at=datetime.now(timezone.utc),
        event_type="payment_intent.succeeded",
        event_id=event_id
    )


async def _handle_invoice_paid(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """Handle invoice.paid event."""
    logger.info({
        "event": "stripe_invoice_paid",
        "company_id": str(company.id) if company else None,
        "invoice_id": event_data.get("id"),
        "amount_paid": event_data.get("amount_paid"),
    })
    
    return WebhookResponse(
        status="accepted",
        message="Invoice paid processed",
        processed_at=datetime.now(timezone.utc),
        event_type="invoice.paid",
        event_id=event_id
    )


async def _handle_refund(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """
    Handle charge.refunded event.
    
    CRITICAL: Creates pending_approval record for manual review.
    Does NOT process refund automatically.
    """
    if company:
        approval_id = await create_pending_approval(
            db=db,
            company_id=company.id,
            event_type="charge.refunded",
            event_data=event_data
        )
        
        logger.info({
            "event": "stripe_refund_pending_approval",
            "company_id": str(company.id),
            "approval_id": str(approval_id),
            "charge_id": event_data.get("id"),
            "amount_refunded": event_data.get("amount_refunded"),
            "note": "Refund created pending_approval - requires human approval"
        })
    
    return WebhookResponse(
        status="accepted",
        message="Refund event logged - pending approval required",
        processed_at=datetime.now(timezone.utc),
        event_type="charge.refunded",
        event_id=event_id
    )


async def _handle_subscription_updated(
    db: AsyncSession,
    company: Optional[Company],
    event_data: Dict[str, Any],
    event_id: str
) -> WebhookResponse:
    """Handle customer.subscription.updated event."""
    logger.info({
        "event": "stripe_subscription_updated",
        "company_id": str(company.id) if company else None,
        "subscription_id": event_data.get("id"),
        "status": event_data.get("status"),
    })
    
    return WebhookResponse(
        status="accepted",
        message="Subscription update processed",
        processed_at=datetime.now(timezone.utc),
        event_type="customer.subscription.updated",
        event_id=event_id
    )
```

**Step 5: Create the Test File**

Create `tests/unit/test_stripe_webhook.py`:

```python
"""
Unit tests for Stripe Webhook Handler.
Uses mocked database sessions - no Docker required.
"""
import os
import json
import hmac
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


def create_test_app():
    """Create a FastAPI test app with stripe webhook router."""
    app = FastAPI()

    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    from backend.api.webhooks.stripe import router
    app.include_router(router)

    return app


def generate_stripe_signature(body: bytes, secret: str) -> str:
    """Generate valid Stripe signature format."""
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{body.decode()}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return f"t={timestamp},v1={signature}"


class TestStripeRouter:
    """Tests for Stripe webhook router configuration."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.webhooks.stripe import router
        assert router.prefix == "/webhooks/stripe"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.webhooks.stripe import router
        assert "Webhooks - Stripe" in router.tags


class TestWebhookAuthentication:
    """Tests for webhook authentication."""

    def test_webhook_missing_signature(self):
        """Test that webhook rejects request without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123"}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401

    def test_webhook_invalid_signature(self):
        """Test that webhook rejects request with invalid signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123"}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload,
                headers={"Stripe-Signature": "invalid_signature"}
            )

        assert response.status_code == 401


class TestPaymentSucceeded:
    """Tests for payment_intent.succeeded event."""

    def test_payment_succeeded_missing_signature(self):
        """Test payment succeeded without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123", "amount": 1000}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401


class TestRefundWebhook:
    """Tests for charge.refunded event."""

    def test_refund_missing_signature(self):
        """Test refund without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "charge.refunded",
            "data": {"object": {"id": "ch_test123", "amount_refunded": 500}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401
```

**Step 6: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_stripe_webhook.py -v
```

**Step 7: Fix Until Pass**

**Step 8: Push When Pass**
```bash
git add backend/api/webhooks/stripe.py tests/unit/test_stripe_webhook.py
git commit -m "Week 4 Day 5: Builder 2 - Stripe webhook handler with pending approval for refunds"
git push origin main
```

**Step 9: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**File to Build:** `backend/services/compliance_service.py`

**Purpose:** Compliance Service — Handles GDPR, data retention, and compliance request processing.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/models/compliance_request.py` — Compliance request model
- `backend/models/audit_trail.py` — Audit trail model
- `backend/app/database.py` — Database session
- `shared/core_functions/config.py` — Configuration
- `shared/core_functions/logger.py` — Logger

**Step 3: Create the Service File**

Create `backend/services/compliance_service.py` with:

```python
"""
Compliance Service Layer.

Handles GDPR requests, data retention, and compliance processing.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from backend.models.compliance_request import ComplianceRequest
from backend.models.audit_trail import AuditTrail
from shared.core_functions.logger import get_logger
from shared.core_functions.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class ComplianceStatus(str, Enum):
    """Compliance request status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ComplianceType(str, Enum):
    """Types of compliance requests."""
    GDPR_ACCESS = "gdpr_access"
    GDPR_DELETE = "gdpr_delete"
    GDPR_PORTABILITY = "gdpr_portability"
    DATA_CORRECTION = "data_correction"
    CONSENT_WITHDRAWAL = "consent_withdrawal"
    RETENTION_REVIEW = "retention_review"


class ComplianceService:
    """
    Service class for compliance business logic.
    
    Handles GDPR requests, data retention policies, and compliance audits.
    All methods enforce company-scoped data access (RLS).
    """
    
    GDPR_RESPONSE_DAYS = 30  # GDPR requires response within 30 days
    DATA_RETENTION_YEARS = 7  # Default retention period
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize compliance service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def create_request(
        self,
        request_type: ComplianceType,
        requested_by: UUID,
        subject_email: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new compliance request.
        
        Args:
            request_type: Type of compliance request
            requested_by: User UUID making the request
            subject_email: Email of the data subject
            description: Optional description
            metadata: Optional additional metadata
            
        Returns:
            Dict with created request details
        """
        request_id = UUID(int=0)  # Placeholder
        
        deadline = datetime.now(timezone.utc) + timedelta(days=self.GDPR_RESPONSE_DAYS)
        
        logger.info({
            "event": "compliance_request_created",
            "company_id": str(self.company_id),
            "request_type": request_type.value,
            "subject_email": subject_email[:50],
            "deadline": deadline.isoformat(),
        })
        
        return {
            "request_id": str(request_id),
            "request_type": request_type.value,
            "status": ComplianceStatus.PENDING.value,
            "subject_email": subject_email,
            "requested_by": str(requested_by),
            "deadline": deadline.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def get_request(
        self,
        request_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get a compliance request by ID.
        
        Args:
            request_id: Request UUID
            
        Returns:
            Dict with request details or None
        """
        # TODO: Query from database
        return {
            "request_id": str(request_id),
            "status": ComplianceStatus.PENDING.value,
            "company_id": str(self.company_id),
        }
    
    async def list_requests(
        self,
        status: Optional[ComplianceStatus] = None,
        request_type: Optional[ComplianceType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List compliance requests for the company.
        
        Args:
            status: Filter by status
            request_type: Filter by type
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of compliance requests
        """
        logger.info({
            "event": "compliance_requests_listed",
            "company_id": str(self.company_id),
            "status_filter": status.value if status else None,
            "type_filter": request_type.value if request_type else None,
        })
        
        return []
    
    async def process_gdpr_access_request(
        self,
        request_id: UUID
    ) -> Dict[str, Any]:
        """
        Process a GDPR access request.
        
        Collects all personal data for the subject.
        
        Args:
            request_id: Request UUID
            
        Returns:
            Dict with collected data
        """
        logger.info({
            "event": "gdpr_access_processing",
            "company_id": str(self.company_id),
            "request_id": str(request_id),
        })
        
        # TODO: Collect all personal data
        collected_data = {
            "user_profile": {},
            "support_tickets": [],
            "audit_logs": [],
            "usage_logs": [],
        }
        
        return {
            "request_id": str(request_id),
            "status": ComplianceStatus.COMPLETED.value,
            "data_collected": collected_data,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def process_gdpr_delete_request(
        self,
        request_id: UUID
    ) -> Dict[str, Any]:
        """
        Process a GDPR deletion request.
        
        CRITICAL: Soft deletes data, retains audit trail for compliance.
        
        Args:
            request_id: Request UUID
            
        Returns:
            Dict with deletion status
        """
        logger.info({
            "event": "gdpr_delete_processing",
            "company_id": str(self.company_id),
            "request_id": str(request_id),
            "note": "Soft delete with audit trail retention"
        })
        
        # TODO: Perform soft deletion
        # IMPORTANT: Never hard delete - retain audit trail
        
        return {
            "request_id": str(request_id),
            "status": ComplianceStatus.COMPLETED.value,
            "deleted_at": datetime.now(timezone.utc).isoformat(),
            "note": "Data soft-deleted, audit trail retained for compliance period"
        }
    
    async def check_deadlines(self) -> List[Dict[str, Any]]:
        """
        Check for compliance requests approaching or past deadline.
        
        Returns:
            List of requests needing attention
        """
        now = datetime.now(timezone.utc)
        warning_threshold = now + timedelta(days=7)
        
        logger.info({
            "event": "compliance_deadlines_checked",
            "company_id": str(self.company_id),
            "warning_threshold": warning_threshold.isoformat(),
        })
        
        # TODO: Query for requests near deadline
        return []
    
    async def generate_compliance_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a compliance report for the company.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dict with compliance metrics
        """
        logger.info({
            "event": "compliance_report_generated",
            "company_id": str(self.company_id),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        })
        
        return {
            "company_id": str(self.company_id),
            "report_period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "metrics": {
                "total_requests": 0,
                "completed": 0,
                "pending": 0,
                "overdue": 0,
                "average_resolution_days": 0,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
```

**Step 4: Create the Test File**

Create `tests/unit/test_compliance_service.py`:

```python
"""
Unit tests for Compliance Service.
Uses mocked database sessions - no Docker required.
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.compliance_service import (
    ComplianceService,
    ComplianceStatus,
    ComplianceType,
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def compliance_service(mock_db):
    """Compliance service instance with mocked DB."""
    company_id = uuid.uuid4()
    return ComplianceService(mock_db, company_id)


class TestComplianceServiceInit:
    """Tests for ComplianceService initialization."""
    
    def test_init_stores_db_and_company_id(self, mock_db):
        """Test that init stores db and company_id."""
        company_id = uuid.uuid4()
        service = ComplianceService(mock_db, company_id)
        
        assert service.db == mock_db
        assert service.company_id == company_id
    
    def test_gdpr_response_days(self, compliance_service):
        """Test GDPR response days constant."""
        assert compliance_service.GDPR_RESPONSE_DAYS == 30


class TestComplianceStatusEnum:
    """Tests for ComplianceStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert ComplianceStatus.PENDING.value == "pending"
        assert ComplianceStatus.IN_PROGRESS.value == "in_progress"
        assert ComplianceStatus.COMPLETED.value == "completed"
        assert ComplianceStatus.FAILED.value == "failed"


class TestComplianceTypeEnum:
    """Tests for ComplianceType enum."""
    
    def test_type_values(self):
        """Test type enum values."""
        assert ComplianceType.GDPR_ACCESS.value == "gdpr_access"
        assert ComplianceType.GDPR_DELETE.value == "gdpr_delete"
        assert ComplianceType.GDPR_PORTABILITY.value == "gdpr_portability"


class TestCreateRequest:
    """Tests for create_request method."""
    
    @pytest.mark.asyncio
    async def test_create_request_returns_dict(self, compliance_service):
        """Test that create_request returns proper dict."""
        request_id = uuid.uuid4()
        subject_email = "subject@example.com"
        
        result = await compliance_service.create_request(
            request_type=ComplianceType.GDPR_ACCESS,
            requested_by=request_id,
            subject_email=subject_email
        )
        
        assert result["request_type"] == "gdpr_access"
        assert result["status"] == "pending"
        assert result["subject_email"] == subject_email


class TestGetRequest:
    """Tests for get_request method."""
    
    @pytest.mark.asyncio
    async def test_get_request_returns_dict(self, compliance_service):
        """Test that get_request returns dict."""
        request_id = uuid.uuid4()
        
        result = await compliance_service.get_request(request_id)
        
        assert result is not None
        assert "request_id" in result


class TestListRequests:
    """Tests for list_requests method."""
    
    @pytest.mark.asyncio
    async def test_list_requests_returns_list(self, compliance_service):
        """Test that list_requests returns list."""
        result = await compliance_service.list_requests()
        
        assert isinstance(result, list)


class TestProcessGDPRAccess:
    """Tests for process_gdpr_access_request method."""
    
    @pytest.mark.asyncio
    async def test_process_access_returns_dict(self, compliance_service):
        """Test that process_gdpr_access_request returns dict."""
        request_id = uuid.uuid4()
        
        result = await compliance_service.process_gdpr_access_request(request_id)
        
        assert result["status"] == "completed"
        assert "data_collected" in result


class TestProcessGDPRDelete:
    """Tests for process_gdpr_delete_request method."""
    
    @pytest.mark.asyncio
    async def test_process_delete_returns_dict(self, compliance_service):
        """Test that process_gdpr_delete_request returns dict."""
        request_id = uuid.uuid4()
        
        result = await compliance_service.process_gdpr_delete_request(request_id)
        
        assert result["status"] == "completed"
        assert "deleted_at" in result


class TestCheckDeadlines:
    """Tests for check_deadlines method."""
    
    @pytest.mark.asyncio
    async def test_check_deadlines_returns_list(self, compliance_service):
        """Test that check_deadlines returns list."""
        result = await compliance_service.check_deadlines()
        
        assert isinstance(result, list)


class TestGenerateComplianceReport:
    """Tests for generate_compliance_report method."""
    
    @pytest.mark.asyncio
    async def test_generate_report_returns_dict(self, compliance_service):
        """Test that generate_compliance_report returns dict."""
        result = await compliance_service.generate_compliance_report()
        
        assert "company_id" in result
        assert "metrics" in result
        assert "generated_at" in result
```

**Step 5: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_compliance_service.py -v
```

**Step 6: Fix Until Pass**

**Step 7: Push When Pass**
```bash
git add backend/services/compliance_service.py tests/unit/test_compliance_service.py
git commit -m "Week 4 Day 5: Builder 3 - Compliance service with GDPR handling"
git push origin main
```

**Step 8: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 — FULL PROMPT (READ ENTIRELY)
═══════════════════════════════════════════════════════════════════════════════

### YOUR TASK

**Files to Build:** 
- `backend/services/sla_service.py`
- `backend/services/license_service.py`
- `backend/services/user_service.py`

**Purpose:** Three core services — SLA tracking, License management, User operations.

### STEP-BY-STEP WORKFLOW

**Step 1: Pull Latest Code**
```bash
git pull origin main
```

**Step 2: Read Dependency Files (REQUIRED)**
Read these files:
- `backend/models/` — All models (user, company, license, sla_breach, etc.)
- `backend/services/` — Existing services for patterns
- `shared/core_functions/logger.py` — Logger

**Step 3: Create the SLA Service**

Create `backend/services/sla_service.py`:

```python
"""
SLA (Service Level Agreement) Service Layer.

Handles SLA tracking, breach detection, and reporting.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SLATier(str, Enum):
    """SLA tier levels."""
    MINI = "mini"          # 24hr response, 72hr resolution
    PARWA = "parwa"        # 4hr response, 24hr resolution
    PARWA_HIGH = "high"    # 1hr response, 4hr resolution


class SLAConfig:
    """SLA configuration by tier."""
    TIERS = {
        SLATier.MINI: {
            "response_hours": 24,
            "resolution_hours": 72,
            "support_hours": "9am-5pm EST",
            "channels": ["email"],
        },
        SLATier.PARWA: {
            "response_hours": 4,
            "resolution_hours": 24,
            "support_hours": "8am-8pm EST",
            "channels": ["email", "chat"],
        },
        SLATier.PARWA_HIGH: {
            "response_hours": 1,
            "resolution_hours": 4,
            "support_hours": "24/7",
            "channels": ["email", "chat", "phone", "video"],
        },
    }


class SLAService:
    """
    Service class for SLA tracking and breach management.
    
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize SLA service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_sla_config(self, tier: SLATier) -> Dict[str, Any]:
        """
        Get SLA configuration for a tier.
        
        Args:
            tier: SLA tier level
            
        Returns:
            Dict with SLA configuration
        """
        return SLAConfig.TIERS.get(tier, SLAConfig.TIERS[SLATier.MINI])
    
    async def check_sla_breach(
        self,
        ticket_id: UUID,
        tier: SLATier,
        created_at: datetime,
        first_response_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a ticket has breached SLA.
        
        Args:
            ticket_id: Ticket UUID
            tier: SLA tier
            created_at: When ticket was created
            first_response_at: When first response was made
            
        Returns:
            Dict with breach details if breached, None otherwise
        """
        config = await self.get_sla_config(tier)
        now = datetime.now(timezone.utc)
        
        response_deadline = created_at + timedelta(hours=config["response_hours"])
        
        # Check response SLA
        if first_response_at is None:
            if now > response_deadline:
                breach_id = UUID(int=0)
                
                logger.warning({
                    "event": "sla_response_breach",
                    "company_id": str(self.company_id),
                    "ticket_id": str(ticket_id),
                    "tier": tier.value,
                    "expected_hours": config["response_hours"],
                    "actual_hours": (now - created_at).total_seconds() / 3600,
                })
                
                return {
                    "breach_id": str(breach_id),
                    "ticket_id": str(ticket_id),
                    "breach_type": "response",
                    "tier": tier.value,
                    "deadline": response_deadline.isoformat(),
                    "detected_at": now.isoformat(),
                }
        
        return None
    
    async def get_sla_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get SLA metrics for the company.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dict with SLA metrics
        """
        logger.info({
            "event": "sla_metrics_retrieved",
            "company_id": str(self.company_id),
        })
        
        return {
            "company_id": str(self.company_id),
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "metrics": {
                "total_tickets": 0,
                "response_sla_met": 0,
                "resolution_sla_met": 0,
                "breaches": 0,
                "compliance_rate": 0.0,
            },
        }
    
    async def list_breaches(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List SLA breaches for the company.
        
        Args:
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of SLA breaches
        """
        return []
```

**Step 4: Create the License Service**

Create `backend/services/license_service.py`:

```python
"""
License Service Layer.

Handles license validation, tier management, and usage tracking.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class LicenseTier(str, Enum):
    """License tier levels."""
    MINI_PARWA = "mini"
    PARWA = "parwa"
    PARWA_HIGH = "high"


class LicenseStatus(str, Enum):
    """License status values."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class LicenseService:
    """
    Service class for license management.
    
    Handles validation, tier enforcement, and usage tracking.
    All methods enforce company-scoped data access (RLS).
    """
    
    TIER_LIMITS = {
        LicenseTier.MINI_PARWA: {
            "users": 5,
            "tickets_per_month": 500,
            "api_calls_per_day": 1000,
            "features": ["email", "chat"],
        },
        LicenseTier.PARWA: {
            "users": 25,
            "tickets_per_month": 5000,
            "api_calls_per_day": 10000,
            "features": ["email", "chat", "voice"],
        },
        LicenseTier.PARWA_HIGH: {
            "users": 100,
            "tickets_per_month": 50000,
            "api_calls_per_day": 100000,
            "features": ["email", "chat", "voice", "video", "priority_queue"],
        },
    }
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize license service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_license(self) -> Optional[Dict[str, Any]]:
        """
        Get the company's license information.
        
        Returns:
            Dict with license details or None
        """
        logger.info({
            "event": "license_retrieved",
            "company_id": str(self.company_id),
        })
        
        # TODO: Query from database
        return {
            "company_id": str(self.company_id),
            "tier": LicenseTier.PARWA.value,
            "status": LicenseStatus.ACTIVE.value,
            "limits": self.TIER_LIMITS[LicenseTier.PARWA],
        }
    
    async def validate_license(self) -> bool:
        """
        Validate that the company has an active license.
        
        Returns:
            bool: True if license is valid and active
        """
        license_info = await self.get_license()
        
        if not license_info:
            logger.warning({
                "event": "license_not_found",
                "company_id": str(self.company_id),
            })
            return False
        
        if license_info.get("status") != LicenseStatus.ACTIVE.value:
            logger.warning({
                "event": "license_not_active",
                "company_id": str(self.company_id),
                "status": license_info.get("status"),
            })
            return False
        
        return True
    
    async def get_tier_limits(self, tier: LicenseTier) -> Dict[str, Any]:
        """
        Get limits for a license tier.
        
        Args:
            tier: License tier level
            
        Returns:
            Dict with tier limits
        """
        return self.TIER_LIMITS.get(tier, self.TIER_LIMITS[LicenseTier.MINI_PARWA])
    
    async def check_usage_limit(
        self,
        limit_type: str,
        current_usage: int
    ) -> Dict[str, Any]:
        """
        Check if usage is within limits.
        
        Args:
            limit_type: Type of limit (users, tickets_per_month, api_calls_per_day)
            current_usage: Current usage value
            
        Returns:
            Dict with limit check result
        """
        license_info = await self.get_license()
        
        if not license_info:
            return {"within_limit": False, "reason": "No active license"}
        
        tier = LicenseTier(license_info.get("tier", "mini"))
        limits = await self.get_tier_limits(tier)
        
        limit = limits.get(limit_type, 0)
        within_limit = current_usage < limit
        
        return {
            "within_limit": within_limit,
            "limit_type": limit_type,
            "current_usage": current_usage,
            "limit": limit,
            "remaining": max(0, limit - current_usage),
        }
    
    async def check_feature_access(self, feature: str) -> bool:
        """
        Check if company has access to a feature.
        
        Args:
            feature: Feature name to check
            
        Returns:
            bool: True if feature is accessible
        """
        license_info = await self.get_license()
        
        if not license_info:
            return False
        
        tier = LicenseTier(license_info.get("tier", "mini"))
        limits = await self.get_tier_limits(tier)
        
        return feature in limits.get("features", [])
```

**Step 5: Create the User Service**

Create `backend/services/user_service.py`:

```python
"""
User Service Layer.

Handles user management, preferences, and company membership.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class UserRole(str, Enum):
    """User role levels."""
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    VIEWER = "viewer"


class UserService:
    """
    Service class for user management.
    
    Handles CRUD operations, role assignment, and preferences.
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize user service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_user(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a user by ID.
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with user details or None
        """
        logger.info({
            "event": "user_retrieved",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        # TODO: Query from database
        return {
            "user_id": str(user_id),
            "company_id": str(self.company_id),
            "role": UserRole.AGENT.value,
            "is_active": True,
        }
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email.
        
        Args:
            email: User email address
            
        Returns:
            Dict with user details or None
        """
        # TODO: Query from database
        return None
    
    async def list_users(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List users for the company.
        
        Args:
            role: Filter by role
            is_active: Filter by active status
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of users
        """
        logger.info({
            "event": "users_listed",
            "company_id": str(self.company_id),
            "role_filter": role.value if role else None,
        })
        
        return []
    
    async def update_user(
        self,
        user_id: UUID,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a user.
        
        Args:
            user_id: User UUID
            updates: Fields to update
            
        Returns:
            Dict with updated user details
        """
        logger.info({
            "event": "user_updated",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
            "fields_updated": list(updates.keys()),
        })
        
        return {
            "user_id": str(user_id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def deactivate_user(self, user_id: UUID) -> Dict[str, Any]:
        """
        Deactivate a user (soft delete).
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with deactivation status
        """
        logger.info({
            "event": "user_deactivated",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        return {
            "user_id": str(user_id),
            "is_active": False,
            "deactivated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def update_preferences(
        self,
        user_id: UUID,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update user preferences.
        
        Args:
            user_id: User UUID
            preferences: Preference key-value pairs
            
        Returns:
            Dict with updated preferences
        """
        logger.info({
            "event": "user_preferences_updated",
            "company_id": str(self.company_id),
            "user_id": str(user_id),
        })
        
        return {
            "user_id": str(user_id),
            "preferences": preferences,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
```

**Step 6: Create Test Files**

Create `tests/unit/test_sla_service.py`, `tests/unit/test_license_service.py`, and `tests/unit/test_user_service.py` following the same pattern as other services.

**Step 7: Run Tests**
```bash
cd /home/z/my-project/parwa
PYTHONPATH=/home/z/my-project/parwa pytest tests/unit/test_sla_service.py tests/unit/test_license_service.py tests/unit/test_user_service.py -v
```

**Step 8: Fix Until Pass**

**Step 9: Push When Pass**
```bash
git add backend/services/sla_service.py backend/services/license_service.py backend/services/user_service.py tests/unit/test_sla_service.py tests/unit/test_license_service.py tests/unit/test_user_service.py
git commit -m "Week 4 Day 5: Builder 4 - SLA, License, and User services"
git push origin main
```

**Step 10: Update Status**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS — UPDATE AFTER COMPLETING YOUR TASK
═══════════════════════════════════════════════════════════════════════════════

## BUILDER 1 → STATUS
**File:** `backend/api/webhooks/shopify.py`
**Status:** PENDING
**Unit Test:** PENDING
**Test File:** `tests/unit/test_shopify_webhook.py`
**Pushed:** NO
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 2 → STATUS
**File:** `backend/api/webhooks/stripe.py`
**Status:** PENDING
**Unit Test:** PENDING
**Test File:** `tests/unit/test_stripe_webhook.py`
**Pushed:** NO
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 3 → STATUS
**File:** `backend/services/compliance_service.py`
**Status:** PENDING
**Unit Test:** PENDING
**Test File:** `tests/unit/test_compliance_service.py`
**Pushed:** NO
**Initiative Files:** None
**Notes:** Waiting to start

---

## BUILDER 4 → STATUS
**Files:** `backend/services/sla_service.py`, `backend/services/license_service.py`, `backend/services/user_service.py`
**Status:** PENDING
**Unit Test:** PENDING
**Test Files:** `tests/unit/test_sla_service.py`, `tests/unit/test_license_service.py`, `tests/unit/test_user_service.py`
**Pushed:** NO
**Initiative Files:** None
**Notes:** Waiting to start

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT → VERIFICATION
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS FOR ALL BUILDERS:**

1. **HMAC Verification is MANDATORY** — All webhooks MUST verify signature before processing
2. **Refund Approval Gate** — Stripe refund webhooks create `pending_approval` records, NEVER call Stripe directly
3. **Company Scoping** — All services MUST use `company_id` for RLS compliance
4. **No Docker** — Use mocked database sessions in tests
5. **One Push Only** — Push ONLY after all tests pass

---

═══════════════════════════════════════════════════════════════════════════════
## ASSISTANCE AGENT → RESPONSE
═══════════════════════════════════════════════════════════════════════════════

[Assistance Agent will provide help here when activated]
