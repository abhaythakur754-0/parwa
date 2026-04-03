# PARWA — Week 5: Payment & Billing System Roadmap

> **Phase**: 2 - Core Business Logic
> **Duration**: 6 Days (Day 24-29)
> **Focus**: Paddle Integration, Subscription Lifecycle, Usage Tracking, Payment Failure Handling
> **Last Updated**: Pre-Week 5 Planning

---

## Business Rules (LOCKED)

| Rule | Decision | Impact |
|------|----------|--------|
| **Payment Failure** | STOP immediately (Netflix style) | No dunning system needed |
| **Free Trials** | NOT offered | No trial management needed |
| **Dunning** | NOT needed | Skip BG-02 gap |
| **Grace Period** | NOT needed | Skip BG-03 gap |
| **Refunds** | NO REFUNDS (Netflix style) | Only track client refunds (PARWA clients to THEIR customers) |
| **Cancellation** | Cancel anytime, access until month end | No partial refunds |
| **Overage Rate** | $0.10/ticket (daily billing) | Celery task exists from Day 22 |

---

## Variant Structure (LOCKED)

| Variant | Price | Tickets/mo | AI Agents | Team | Voice Slots | KB Docs |
|---------|-------|------------|-----------|------|-------------|---------|
| **PARWA Starter** | $999 | 2,000 | 1 | 3 | 0 | 100 |
| **PARWA Growth** | $2,499 | 5,000 | 3 | 10 | 2 | 500 |
| **PARWA High** | $3,999 | 15,000 | 5 | 25 | 5 | 2,000 |

---

## Week 5 Goals

| Day | Focus | Critical Deliverables |
|-----|-------|----------------------|
| Day 24 | Paddle Client + Database Tables | paddle_client.py, 8 new DB tables, migrations |
| Day 25 | Subscription Service + Proration | subscription_service.py, proration_service.py |
| Day 26 | Usage Tracking + Variant Limits | usage_tracking_service.py, variant_limit_service.py |
| Day 27 | Payment Failure + Immediate Stop | payment_failure_service.py, BG-16 implementation |
| Day 28 | Webhook Expansion (25+ Events) | Extend paddle_handler.py, idempotency, ordering |
| Day 29 | Invoice + Reconciliation + Integration | invoice_service.py, reconciliation_tasks.py, full integration |

---

## Detailed Day Breakdown

---

### Day 24 — Paddle Client + Database Tables

**Goal**: Build Paddle API client and create all billing-related database tables.

#### BUILD Phase

| Step | File | Description | Depends On |
|------|------|-------------|------------|
| 1 | `database/migrations/versions/008_billing_tables.py` | New migration for 8 billing tables | Day 18 migrations |
| 2 | `database/models/billing_extended.py` | Extended billing models | database/base.py |
| 3 | `backend/app/clients/paddle_client.py` | Paddle API client (subscription, customer, transaction endpoints) | config.py |
| 4 | `backend/app/schemas/billing.py` | Pydantic schemas for billing requests/responses | None |
| 5 | `backend/app/schemas/paddle.py` | Paddle webhook event schemas (25+ event types) | None |
| 6 | `tests/unit/test_paddle_client.py` | Unit tests for Paddle client | paddle_client.py |

#### New Database Tables

```sql
-- client_refunds: Track PARWA clients refunding THEIR customers
CREATE TABLE client_refunds (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    ticket_id UUID REFERENCES tickets(id),
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    reason TEXT,
    status VARCHAR(20) DEFAULT 'pending', -- pending/processed/failed
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- payment_methods: Cache payment method info from Paddle
CREATE TABLE payment_methods (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    paddle_payment_method_id VARCHAR(255) NOT NULL,
    method_type VARCHAR(20), -- card/paypal/wire
    last_four VARCHAR(4),
    expiry_month INT,
    expiry_year INT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- usage_records: Daily/monthly usage tracking
CREATE TABLE usage_records (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    record_date DATE NOT NULL,
    record_month VARCHAR(7) NOT NULL, -- YYYY-MM
    tickets_used INT DEFAULT 0,
    ai_agents_used INT DEFAULT 0,
    voice_minutes_used DECIMAL(10,2) DEFAULT 0,
    overage_tickets INT DEFAULT 0,
    overage_charges DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, record_date)
);

-- variant_limits: Variant feature limits cache
CREATE TABLE variant_limits (
    id UUID PRIMARY KEY,
    variant_name VARCHAR(50) NOT NULL, -- starter/growth/high
    monthly_tickets INT NOT NULL,
    ai_agents INT NOT NULL,
    team_members INT NOT NULL,
    voice_slots INT NOT NULL,
    kb_docs INT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- idempotency_keys: Webhook idempotency tracking
CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY,
    company_id UUID,
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    request_body_hash VARCHAR(64),
    response_status INT,
    response_body TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

-- webhook_sequences: Webhook ordering tracking
CREATE TABLE webhook_sequences (
    id UUID PRIMARY KEY,
    company_id UUID,
    paddle_event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    occurred_at TIMESTAMP NOT NULL,
    processed_at TIMESTAMP,
    processing_order INT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- proration_audits: Proration calculation audit trail
CREATE TABLE proration_audits (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    old_variant VARCHAR(50) NOT NULL,
    new_variant VARCHAR(50) NOT NULL,
    old_price DECIMAL(10,2) NOT NULL,
    new_price DECIMAL(10,2) NOT NULL,
    days_remaining INT NOT NULL,
    days_in_period INT NOT NULL,
    unused_amount DECIMAL(10,2) NOT NULL,
    proration_amount DECIMAL(10,2) NOT NULL,
    credit_applied DECIMAL(10,2) DEFAULT 0,
    charge_applied DECIMAL(10,2) DEFAULT 0,
    calculated_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- payment_failures: Payment failure audit log
CREATE TABLE payment_failures (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    paddle_subscription_id VARCHAR(255),
    paddle_transaction_id VARCHAR(255),
    failure_code VARCHAR(50),
    failure_reason TEXT,
    amount_attempted DECIMAL(10,2),
    currency VARCHAR(3) DEFAULT 'USD',
    service_stopped_at TIMESTAMP,
    service_resumed_at TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Paddle Client Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/subscriptions/{id}` | GET | Get subscription details |
| `/subscriptions` | POST | Create subscription |
| `/subscriptions/{id}` | PATCH | Update subscription (variant change) |
| `/subscriptions/{id}/cancel` | POST | Cancel subscription |
| `/customers/{id}` | GET | Get customer details |
| `/transactions` | GET | List transactions |
| `/transactions/{id}` | GET | Get transaction details |
| `/prices` | GET | Get price/variant info |

#### Tests Required
- Paddle client initialization with API keys
- Subscription CRUD operations (mocked)
- Error handling (rate limits, auth failures)
- Retry logic with exponential backoff
- All 8 table migrations apply cleanly

#### Commit Message
```
Week 5 Day 24: Paddle API client + 8 billing tables + migrations
```

---

### Day 25 — Subscription Service + Proration

**Goal**: Build subscription lifecycle management and variant change proration logic.

#### BUILD Phase

| Step | File | Description | Depends On |
|------|------|-------------|------------|
| 1 | `backend/app/services/subscription_service.py` | Subscription lifecycle management | paddle_client.py |
| 2 | `backend/app/services/proration_service.py` | Variant change proration calculations | subscription_service.py |
| 3 | `backend/app/api/billing.py` | Billing API routes (upgrade/downgrade/cancel) | services |
| 4 | `tests/unit/test_subscription_service.py` | Unit tests for subscription service | subscription_service.py |
| 5 | `tests/unit/test_proration_service.py` | Unit tests for proration service | proration_service.py |

#### Subscription Service Methods

```python
class SubscriptionService:
    async def create_subscription(
        company_id: UUID,
        variant: str,  # starter/growth/high
        payment_method_id: str
    ) -> SubscriptionResult
    
    async def get_subscription(company_id: UUID) -> SubscriptionInfo
    
    async def upgrade_subscription(
        company_id: UUID,
        new_variant: str
    ) -> UpgradeResult  # Includes proration
    
    async def downgrade_subscription(
        company_id: UUID,
        new_variant: str
    ) -> DowngradeResult  # Effective at period end
    
    async def cancel_subscription(
        company_id: UUID,
        reason: str | None
    ) -> CancelResult  # Access until month end
    
    async def get_subscription_status(company_id: UUID) -> SubscriptionStatus
```

#### Proration Calculation (Netflix Style)

```python
class ProrationService:
    """
    Proration Rules:
    - Upgrade: Immediate, prorated credit from old variant applied to new variant
    - Downgrade: Effective at NEXT billing cycle (no proration needed)
    - Cancel: Access until end of current billing period
    
    Formula (Upgrade only):
    - unused_amount = (old_price / days_in_period) * days_remaining
    - proration_credit = unused_amount
    - new_charge = (new_price / days_in_period) * days_remaining
    - net_charge = new_charge - proration_credit
    """
    
    async def calculate_upgrade_proration(
        company_id: UUID,
        old_variant: str,
        new_variant: str,
        billing_cycle_start: date,
        billing_cycle_end: date
    ) -> ProrationResult
    
    async def apply_proration_credit(
        company_id: UUID,
        proration_result: ProrationResult
    ) -> None
    
    async def get_proration_audit_log(
        company_id: UUID
    ) -> List[ProrationAudit]
```

#### Proration Example

```
Scenario: Growth ($2,499) → High ($3,999) upgrade on day 15 of 30-day month

Calculation:
- Days remaining: 15
- Days in period: 30
- Unused Growth: ($2,499 / 30) * 15 = $1,249.50
- New High charge: ($3,999 / 30) * 15 = $1,999.50
- Net charge: $1,999.50 - $1,249.50 = $750.00

Result: Customer charged $750 immediately, full High access granted
```

#### Tests Required
- Create subscription (all 3 variants)
- Upgrade subscription with proration calculation
- Downgrade subscription (schedules for next cycle)
- Cancel subscription (access until month end)
- Proration edge cases (mid-month, last day, first day)
- Proration audit trail verification

#### Commit Message
```
Week 5 Day 25: Subscription service + proration calculations + billing routes
```

---

### Day 26 — Usage Tracking + Variant Limits

**Goal**: Real-time usage counting and variant limit enforcement.

#### BUILD Phase

| Step | File | Description | Depends On |
|------|------|-------------|------------|
| 1 | `backend/app/services/usage_tracking_service.py` | Daily usage tracking | usage_records model |
| 2 | `backend/app/services/variant_limit_service.py` | Variant limit enforcement | variant_limits model |
| 3 | `backend/app/middleware/variant_check.py` | Middleware for limit enforcement | variant_limit_service.py |
| 4 | `backend/app/tasks/usage_tasks.py` | Daily usage aggregation tasks | usage_tracking_service.py |
| 5 | `tests/unit/test_usage_tracking.py` | Unit tests for usage tracking | services |
| 6 | `tests/unit/test_variant_limits.py` | Unit tests for variant limits | services |

#### Usage Tracking Service

```python
class UsageTrackingService:
    async def increment_ticket_usage(
        company_id: UUID,
        count: int = 1
    ) -> UsageResult
    
    async def get_current_usage(
        company_id: UUID,
        month: str | None = None  # YYYY-MM
    ) -> UsageInfo
    
    async def get_usage_percentage(
        company_id: UUID
    ) -> float  # 0.0 to 1.0+
    
    async def check_approaching_limit(
        company_id: UUID,
        threshold: float = 0.8  # 80%
    ) -> bool
    
    async def calculate_overage(
        company_id: UUID,
        tickets_used: int,
        ticket_limit: int
    ) -> OverageResult  # $0.10/ticket over limit
    
    async def get_usage_history(
        company_id: UUID,
        months: int = 12
    ) -> List[MonthlyUsage]
```

#### Variant Limit Service

```python
class VariantLimitService:
    """
    Variant Limits (from locked structure):
    
    | Variant | Tickets | AI Agents | Team | Voice | KB Docs |
    |---------|---------|-----------|------|-------|---------|
    | Starter | 2,000   | 1         | 3    | 0     | 100     |
    | Growth  | 5,000   | 3         | 10   | 2     | 500     |
    | High    | 15,000  | 5         | 25   | 5     | 2,000   |
    """
    
    async def get_variant_limits(variant: str) -> VariantLimits
    
    async def check_ticket_limit(
        company_id: UUID
    ) -> LimitCheckResult  # allowed/at_limit/exceeded
    
    async def check_team_member_limit(
        company_id: UUID,
        current_count: int
    ) -> LimitCheckResult
    
    async def check_ai_agent_limit(
        company_id: UUID,
        current_count: int
    ) -> LimitCheckResult
    
    async def check_voice_slot_limit(
        company_id: UUID,
        current_count: int
    ) -> LimitCheckResult
    
    async def check_kb_doc_limit(
        company_id: UUID,
        current_count: int
    ) -> LimitCheckResult
    
    async def enforce_limit(
        company_id: UUID,
        limit_type: str  # tickets/team/agents/voice/kb
    ) -> EnforcementResult  # raise exception if exceeded
```

#### Variant Check Middleware

```python
class VariantCheckMiddleware:
    """
    Injected into API routes that consume variant resources:
    - POST /api/tickets - check ticket limit
    - POST /api/team/invite - check team limit
    - POST /api/agents - check agent limit
    - POST /api/kb/documents - check KB limit
    
    Returns 402 Payment Required if limit exceeded:
    {
        "error": "variant_limit_exceeded",
        "message": "You have reached your monthly ticket limit of 2,000",
        "current_usage": 2000,
        "limit": 2000,
        "overage_rate": "$0.10/ticket",
        "upgrade_url": "/billing/upgrade"
    }
    """
```

#### Daily Overage Task (Extends Day 22)

```python
@celery_app.task(name="billing.daily_overage_charge")
def daily_overage_charge():
    """
    Runs daily at 02:00 (from Day 22 Beat schedule).
    
    For each company with overage:
    1. Calculate tickets over limit
    2. Charge $0.10 per overage ticket
    3. Log to usage_records
    4. Send notification
    """
```

#### Tests Required
- Usage increment and retrieval
- Usage percentage calculation
- Overage calculation ($0.10/ticket)
- All 5 limit types (tickets/team/agents/voice/kb)
- Middleware returns 402 when exceeded
- Daily overage task processes correctly

#### Commit Message
```
Week 5 Day 26: Usage tracking + variant limit enforcement + overage charging
```

---

### Day 27 — Payment Failure + Immediate Stop

**Goal**: Implement payment failure handling with immediate service stop (Netflix style).

#### BUILD Phase

| Step | File | Description | Depends On |
|------|------|-------------|------------|
| 1 | `backend/app/services/payment_failure_service.py` | Payment failure handling | paddle_client.py |
| 2 | `backend/app/tasks/payment_failure_tasks.py` | Immediate stop tasks | payment_failure_service.py |
| 3 | `backend/app/api/billing_webhooks.py` | Payment webhook routes | paddle_handler.py |
| 4 | `backend/app/templates/emails/payment_failed.html` | Payment failure email template | None |
| 5 | `tests/unit/test_payment_failure.py` | Unit tests for payment failure | services |
| 6 | `tests/integration/test_payment_failure_flow.py` | Integration tests | all |

#### Payment Failure Service (BG-16 Implementation)

```python
class PaymentFailureService:
    """
    Netflix-Style Payment Failure Handling:
    
    1. Payment fails → IMMEDIATE service stop
    2. No grace period
    3. No dunning emails
    4. Single notification: "Payment failed, update payment method"
    5. Service resumes immediately on successful payment
    
    This is deliberately strict to reduce churn from forgotten cards.
    """
    
    async def handle_payment_failure(
        company_id: UUID,
        paddle_transaction_id: str,
        failure_code: str,
        failure_reason: str,
        amount_attempted: Decimal
    ) -> PaymentFailureResult:
        """
        1. Log to payment_failures table
        2. Set company.subscription_status = 'payment_failed'
        3. Stop all AI agents immediately
        4. Block new ticket creation
        5. Freeze existing open tickets (status → 'frozen')
        6. Send payment_failed email notification
        7. Create Socket.io event for real-time UI update
        """
    
    async def is_service_stopped(company_id: UUID) -> bool
    
    async def resume_service(
        company_id: UUID,
        paddle_transaction_id: str
    ) -> ResumeResult:
        """
        Called when payment succeeds after failure:
        1. Update subscription_status → 'active'
        2. Resume AI agents
        3. Unfreeze tickets
        4. Send service_resumed notification
        """
    
    async def get_payment_failure_history(
        company_id: UUID
    ) -> List[PaymentFailure]
```

#### Payment Failure Flow

```
┌─────────────────┐
│ Payment Fails   │
│ (Paddle webhook)│
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ IMMEDIATE STOP (no grace, no dunning)       │
├─────────────────────────────────────────────┤
│ 1. Log to payment_failures                  │
│ 2. subscription_status = 'payment_failed'   │
│ 3. Stop all AI agents                       │
│ 4. Block new ticket creation                │
│ 5. Freeze existing open tickets             │
│ 6. Send payment_failed email                │
│ 7. Emit Socket.io event                     │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ User updates payment method                 │
│ (Paddle handles retry)                      │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ PAYMENT SUCCEEDS                            │
├─────────────────────────────────────────────┤
│ 1. subscription_status = 'active'           │
│ 2. Resume AI agents                         │
│ 3. Unfreeze tickets                         │
│ 4. Send service_resumed notification        │
└─────────────────────────────────────────────┘
```

#### Email Template: Payment Failed

```html
Subject: Action Required: Payment Failed for PARWA

Hi {{company_name}},

Your payment of ${{amount}} for PARWA {{variant}} has failed.

**Reason**: {{failure_reason}}

Your service has been paused. To resume:

[Update Payment Method]

You won't be charged until your payment method is updated.

PARWA Support
```

#### Tests Required
- Payment failure triggers immediate stop
- All services stop correctly (agents, tickets)
- Notification sent
- Service resumes on successful payment
- Frozen tickets unfrozen correctly
- Payment failure history retrieval

#### Commit Message
```
Week 5 Day 27: Payment failure handling + immediate service stop (Netflix style)
```

---

### Day 28 — Webhook Expansion (25+ Events)

**Goal**: Extend Paddle webhook handler from 5 events to 25+ events with idempotency and ordering.

#### BUILD Phase

| Step | File | Description | Depends On |
|------|------|-------------|------------|
| 1 | `backend/app/webhooks/paddle_handler.py` (UPDATE) | Extend to 25+ events | existing handler |
| 2 | `backend/app/services/webhook_processor.py` | Webhook processing with idempotency | idempotency_keys table |
| 3 | `backend/app/tasks/webhook_recovery.py` | Missed webhook recovery | paddle_client.py |
| 4 | `tests/unit/test_paddle_webhooks_extended.py` | Extended webhook tests | handlers |
| 5 | `tests/unit/test_webhook_idempotency.py` | Idempotency tests | services |

#### Paddle Events (25+)

| Event Category | Events |
|----------------|--------|
| **Subscription** | subscription.created, subscription.updated, subscription.activated, subscription.canceled, subscription.past_due, subscription.paused, subscription.resumed |
| **Transaction** | transaction.completed, transaction.paid, transaction.payment_failed, transaction.canceled, transaction.updated |
| **Customer** | customer.created, customer.updated, customer.deleted |
| **Price/Variant** | price.created, price.updated, price.deleted |
| **Discount** | discount.created, discount.updated, discount.deleted |
| **Credit** | credit.created, credit.updated, credit.deleted |
| **Adjustment** | adjustment.created, adjustment.updated |
| **Report** | report.created, report.updated |

#### Webhook Handler Structure

```python
# paddle_handler.py (Extended)

class PaddleEventHandler:
    """
    Event handlers organized by category.
    Each handler:
    1. Validates event signature (HMAC-SHA256)
    2. Checks idempotency (skip if already processed)
    3. Processes event in correct order (if ordering matters)
    4. Logs to webhook_sequences
    5. Updates relevant DB tables
    """
    
    # Subscription Events (7 handlers)
    async def handle_subscription_created(event: PaddleEvent) -> None
    async def handle_subscription_updated(event: PaddleEvent) -> None
    async def handle_subscription_activated(event: PaddleEvent) -> None
    async def handle_subscription_canceled(event: PaddleEvent) -> None
    async def handle_subscription_past_due(event: PaddleEvent) -> None
    async def handle_subscription_paused(event: PaddleEvent) -> None
    async def handle_subscription_resumed(event: PaddleEvent) -> None
    
    # Transaction Events (5 handlers)
    async def handle_transaction_completed(event: PaddleEvent) -> None
    async def handle_transaction_paid(event: PaddleEvent) -> None
    async def handle_transaction_payment_failed(event: PaddleEvent) -> None
    async def handle_transaction_canceled(event: PaddleEvent) -> None
    async def handle_transaction_updated(event: PaddleEvent) -> None
    
    # Customer Events (3 handlers)
    async def handle_customer_created(event: PaddleEvent) -> None
    async def handle_customer_updated(event: PaddleEvent) -> None
    async def handle_customer_deleted(event: PaddleEvent) -> None
    
    # Price Events (3 handlers)
    async def handle_price_created(event: PaddleEvent) -> None
    async def handle_price_updated(event: PaddleEvent) -> None
    async def handle_price_deleted(event: PaddleEvent) -> None
    
    # ... etc (total 25+ handlers)
```

#### Idempotency Handling (BG-08)

```python
class WebhookProcessor:
    async def process_with_idempotency(
        event: PaddleEvent,
        handler: Callable
    ) -> WebhookResult:
        """
        1. Generate idempotency key from event_id
        2. Check if key exists in idempotency_keys
        3. If exists: return cached response (skip processing)
        4. If not: process, store key + response, return
        """
        key = f"paddle:{event.event_id}"
        
        existing = await get_idempotency_key(key)
        if existing:
            logger.info(f"Skipping duplicate webhook: {key}")
            return WebhookResult(
                status=existing.response_status,
                body=existing.response_body,
                duplicate=True
            )
        
        result = await handler(event)
        
        await store_idempotency_key(
            key=key,
            response_status=result.status,
            response_body=result.body,
            expires_at=now() + timedelta(days=7)
        )
        
        return result
```

#### Webhook Ordering (BG-07)

```python
class WebhookOrderingService:
    """
    Some events must be processed in order:
    - subscription.created before subscription.updated
    - transaction.paid before transaction.completed
    
    Strategy:
    1. Store all incoming events in webhook_sequences with occurred_at
    2. Process in order by occurred_at timestamp
    3. If earlier event arrives after later event, reprocess chain
    """
    
    async def process_ordered(
        event: PaddleEvent,
        company_id: UUID
    ) -> None:
        # Store event
        await store_webhook_event(event, company_id)
        
        # Get all pending events ordered by time
        pending = await get_pending_events(company_id)
        
        # Process in order
        for evt in pending:
            await process_event(evt)
            await mark_processed(evt.id)
```

#### Missed Webhook Recovery (BG-15)

```python
@celery_app.task(name="webhook.recover_missed")
def recover_missed_webhooks():
    """
    Runs every hour.
    
    1. For each active subscription in DB:
    2. Call Paddle API to get recent events
    3. Compare with webhook_sequences table
    4. Process any missing events
    """
```

#### Tests Required
- All 25+ event types handled
- Idempotency prevents duplicate processing
- Event ordering maintained
- Missed webhook recovery works
- HMAC signature validation
- Parallel event processing doesn't corrupt data

#### Commit Message
```
Week 5 Day 28: Paddle webhook expansion (25+ events) + idempotency + ordering
```

---

### Day 29 — Invoice + Reconciliation + Integration

**Goal**: Invoice generation, DB↔Paddle reconciliation, and full billing integration testing.

#### BUILD Phase

| Step | File | Description | Depends On |
|------|------|-------------|------------|
| 1 | `backend/app/services/invoice_service.py` | Invoice PDF generation | paddle_client.py |
| 2 | `backend/app/services/client_refund_service.py` | Client refund tracking | billing models |
| 3 | `backend/app/tasks/reconciliation_tasks.py` | DB ↔ Paddle sync | all services |
| 4 | `backend/app/api/billing.py` (UPDATE) | Full billing API integration | all services |
| 5 | `tests/integration/test_billing_e2e.py` | End-to-end billing tests | all |
| 6 | `tests/integration/test_reconciliation.py` | Reconciliation tests | tasks |

#### Invoice Service

```python
class InvoiceService:
    async def get_invoice_list(
        company_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> PaginatedResponse[Invoice]
    
    async def get_invoice_pdf(
        company_id: UUID,
        invoice_id: str
    ) -> bytes:
        """
        Generate or retrieve PDF invoice.
        
        Invoice contains:
        - Company name and address
        - Billing period
        - Variant and price
        - Overage charges (if any)
        - Total amount
        - Payment method (last 4 digits)
        """
    
    async def sync_invoices_from_paddle(
        company_id: UUID
    ) -> int:
        """Pull recent invoices from Paddle API."""
```

#### Client Refund Service (BG-09)

```python
class ClientRefundService:
    """
    PARWA clients refunding THEIR customers.
    This is NOT PARWA refunding clients (NO REFUNDS policy).
    
    Use case: PARWA client has e-commerce store, customer requests refund,
    PARWA AI agent processes refund, we track for analytics.
    """
    
    async def create_refund_request(
        company_id: UUID,
        ticket_id: UUID,
        amount: Decimal,
        reason: str
    ) -> RefundRequest
    
    async def process_refund(
        refund_id: UUID,
        external_ref: str  # Reference from client's payment system
    ) -> RefundResult
    
    async def get_refund_history(
        company_id: UUID,
        months: int = 12
    ) -> List[RefundRecord]
```

#### Reconciliation Tasks (BG-06)

```python
@celery_app.task(name="billing.reconcile_subscriptions")
def reconcile_subscriptions():
    """
    Runs daily at 06:00.
    
    For each company:
    1. Get subscription from Paddle API
    2. Compare with DB subscription record
    3. If diverged:
       - Log discrepancy
       - Reconcile (DB as source of truth for entitlements)
       - Alert finance team if critical mismatch
    """

@celery_app.task(name="billing.reconcile_transactions")
def reconcile_transactions():
    """
    Runs daily at 06:30.
    
    For each company:
    1. Get transactions from Paddle API
    2. Compare with DB transaction records
    3. If diverged:
       - Log discrepancy
       - Sync missing transactions
       - Alert finance team if critical mismatch
    """

@celery_app.task(name="billing.reconcile_usage")
def reconcile_usage():
    """
    Runs daily at 07:00.
    
    For each company:
    1. Get ticket count from DB
    2. Compare with Paddle usage records
    3. If diverged:
       - Update Paddle usage
       - Log for audit
    """
```

#### Full Billing API Routes

```python
# billing.py - Complete routes

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Subscription Management
POST   /subscription          # Create new subscription
GET    /subscription          # Get current subscription
PATCH  /subscription          # Upgrade/downgrade
DELETE /subscription          # Cancel (access until month end)

# Payment Methods
GET    /payment-methods       # List payment methods
POST   /payment-methods       # Add payment method
DELETE /payment-methods/{id}  # Remove payment method

# Invoices
GET    /invoices              # List invoices
GET    /invoices/{id}/pdf     # Download PDF

# Usage
GET    /usage                 # Current month usage
GET    /usage/history         # Historical usage

# Client Refunds (PARWA clients to THEIR customers)
POST   /client-refunds        # Create refund request
GET    /client-refunds        # List refund history

# Webhooks (Paddle)
POST   /webhooks/paddle       # Receive Paddle webhooks
```

#### End-to-End Test Scenarios

| Scenario | Steps |
|----------|-------|
| New Subscription | Checkout → Webhook → DB sync → Service active |
| Upgrade Mid-Month | Request → Proration → Charge → Webhook → DB update |
| Payment Failure | Webhook → Stop service → Notification → Update payment → Resume |
| Cancellation | Request → Schedule cancel → End of month → Stop |
| Overage | Daily task → Calculate → Charge → Notification |
| Reconciliation | Divergence detected → Alert → Auto-fix |

#### Tests Required
- Invoice PDF generation
- Client refund processing
- All 3 reconciliation tasks
- Full subscription lifecycle (create → upgrade → cancel)
- Payment failure → recovery flow
- Overage calculation and charging

#### Commit Message
```
Week 5 Day 29: Invoice service + reconciliation tasks + full billing integration
```

---

## Week 5 Summary

### Files Created/Updated

| Type | Files | Count |
|------|-------|-------|
| Services | paddle_client.py, subscription_service.py, proration_service.py, usage_tracking_service.py, variant_limit_service.py, payment_failure_service.py, invoice_service.py, client_refund_service.py, webhook_processor.py | 9 |
| Tasks | usage_tasks.py, payment_failure_tasks.py, reconciliation_tasks.py, webhook_recovery.py | 4 |
| API Routes | billing.py, billing_webhooks.py | 2 |
| Middleware | variant_check.py | 1 |
| Schemas | billing.py, paddle.py | 2 |
| Migrations | 008_billing_tables.py | 1 |
| Models | billing_extended.py | 1 |
| Templates | payment_failed.html, service_resumed.html, overage_notification.html (update) | 3 |
| Tests | 10+ test files | ~15 |

**Total New Files: ~35**

### Tests Expected

| Day | New Tests | Cumulative |
|-----|-----------|------------|
| Day 24 | ~80 | 2,327 |
| Day 25 | ~70 | 2,397 |
| Day 26 | ~90 | 2,487 |
| Day 27 | ~60 | 2,547 |
| Day 28 | ~100 | 2,647 |
| Day 29 | ~80 | 2,727 |

**Target: 2,727 tests by end of Week 5**

### Production Gaps Closed

| Gap ID | Description | Day |
|--------|-------------|-----|
| BG-01 | 25+ Paddle events handled | Day 28 |
| BG-04 | Variant change proration | Day 25 |
| BG-05 | Paddle API client | Day 24 |
| BG-06 | DB ↔ Paddle reconciliation | Day 29 |
| BG-07 | Webhook ordering | Day 28 |
| BG-08 | Idempotency key storage | Day 28 |
| BG-09 | Client refund tracking | Day 29 |
| BG-11 | Payment method update flow | Day 25 |
| BG-12 | PDF invoice generation | Day 29 |
| BG-13 | Real-time usage counting | Day 26 |
| BG-14 | Feature blocking on limits | Day 26 |
| BG-15 | Missed webhook detection | Day 28 |
| BG-16 | Payment failure → immediate stop | Day 27 |

### Features Delivered

| Feature ID | Title | Day |
|------------|-------|-----|
| F-020 | Paddle checkout integration | Day 24 |
| F-021 | Subscription management (upgrade/downgrade) | Day 25 |
| F-022 | Paddle webhook handler (25+ events) | Day 28 |
| F-023 | Invoice history + PDF download | Day 29 |
| F-024 | Daily overage charging | Day 26 |
| F-025 | Cancellation flow | Day 25 |
| F-026 | Cancellation request tracking | Day 25 |
| F-027 | Payment confirmation + verification | Day 27 |

---

## Infrastructure Code Updates Required

### Existing Files to Update

| File | Current State | Update Needed |
|------|---------------|---------------|
| `backend/app/webhooks/paddle_handler.py` | 5 events | Expand to 25+ events |
| `backend/app/tasks/billing_tasks.py` | Stubs | Complete implementation |
| `database/models/billing.py` | Basic tables | Add 8 new tables |
| `backend/app/main.py` | Basic routes | Mount billing routes |
| `.env.example` | Missing vars | Add PADDLE_* vars |

### New Environment Variables

```bash
# Paddle Configuration
PADDLE_CLIENT_TOKEN=xxxxx
PADDLE_CLIENT_SECRET=xxxxx
PADDLE_WEBHOOK_SECRET=xxxxx
PADDLE_SANDBOX=true  # false in production

# Variant Price IDs (Paddle)
PADDLE_PRICE_STARTER=pri_xxxxx
PADDLE_PRICE_GROWTH=pri_xxxxx
PADDLE_PRICE_HIGH=pri_xxxxx
```

---

## Dependencies

```txt
# Add to requirements.txt
paddle-python-sdk>=1.0.0  # Official Paddle SDK
reportlab>=4.0.0          # PDF generation
```

---

## Week 6 Preview

After Week 5 completion, Week 6 will cover:
- Onboarding wizard backend
- Legal consent collection
- Integration setup (OAuth flows)
- Knowledge base upload and processing

---

*Roadmap created: Pre-Week 5 Planning*
*Ready to begin: Day 24*
