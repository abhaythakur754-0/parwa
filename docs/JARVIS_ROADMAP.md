# PARWA Jarvis Build Roadmap

> **Document Version:** 1.0
> **Created:** Week 6 Day 8 (April 2026)
> **Based On:** JARVIS_SPECIFICATION.md v1.0
> **Scope:** Complete Jarvis onboarding system — from code zero to production-ready

---

## Overview

**One page. One Jarvis. Everything happens here.**

The `/onboarding` page is THE single page where the entire pre-purchase experience happens:
- Demo chat (conversing with Jarvis)
- Demo call booking ($1 AI voice call)
- Business email OTP verification
- Variant payment (Paddle checkout)
- Bill summary display
- Handoff to Customer Care Jarvis

After onboarding completes, the UI changes completely — dashboard takes over.

---

## Architecture Recap

```
┌──────────────────────────────────────────────────────────────┐
│                   /onboarding (ONE PAGE)                      │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   JARVIS CHAT                            │ │
│  │                                                         │ │
│  │  Welcome → Demo → Pricing → Bill → OTP → Payment → Handoff│
│  │                                                         │ │
│  │  [All conversation flows happen inside this chat]       │ │
│  │  [Rich cards appear inline: bill, OTP, payment, etc.]   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Message Counter: 16/20 remaining today                       │
│  [Upgrade to Demo Pack]                                       │
└──────────────────────────────────────────────────────────────┘
                              |
                              | Payment Success + Handoff
                              v
┌──────────────────────────────────────────────────────────────┐
│                     /dashboard (NEW UI)                       │
│                                                               │
│  Customer Care Jarvis + Knowledge Base + Integrations        │
│  Completely different interface from onboarding               │
└──────────────────────────────────────────────────────────────┘
```

---

## Build Phases

### Phase 1: Database + Models (Day 1 — Morning)

**Goal:** Create the data layer that everything else depends on.

#### Migration: `012_jarvis_system.py`

```sql
-- jarvis_sessions
CREATE TABLE jarvis_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    company_id      UUID REFERENCES companies(id),
    type            VARCHAR(20) NOT NULL DEFAULT 'onboarding'
                    CHECK (type IN ('onboarding', 'customer_care')),
    context_json    JSONB NOT NULL DEFAULT '{}',
    message_count_today INTEGER NOT NULL DEFAULT 0,
    total_message_count INTEGER NOT NULL DEFAULT 0,
    pack_type       VARCHAR(10) NOT NULL DEFAULT 'free'
                    CHECK (pack_type IN ('free', 'demo')),
    pack_expiry     TIMESTAMP,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    payment_status  VARCHAR(15) NOT NULL DEFAULT 'none'
                    CHECK (payment_status IN ('none','pending','completed','failed')),
    handoff_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- jarvis_messages
CREATE TABLE jarvis_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES jarvis_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL
                    CHECK (role IN ('user', 'jarvis', 'system')),
    content         TEXT NOT NULL,
    message_type    VARCHAR(20) NOT NULL DEFAULT 'text'
                    CHECK (message_type IN (
                        'text', 'bill_summary', 'payment_card',
                        'otp_card', 'handoff_card', 'demo_call_card'
                    )),
    metadata_json   JSONB DEFAULT '{}',
    timestamp       TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_jarvis_sessions_user_active ON jarvis_sessions(user_id, is_active);
CREATE INDEX idx_jarvis_messages_session_ts ON jarvis_messages(session_id, timestamp);
CREATE INDEX idx_jarvis_sessions_company ON jarvis_sessions(company_id);
```

#### Files to Create

| # | File | Lines (est.) | What |
|---|------|-------------|------|
| 1 | `database/alembic/versions/012_jarvis_system.py` | ~120 | Migration with both tables + indexes |
| 2 | `database/models/jarvis.py` | ~100 | `JarvisSession` + `JarvisMessage` SQLAlchemy models |

#### Acceptance Criteria
- [ ] Migration runs without errors (`alembic upgrade head`)
- [ ] Models importable: `from database.models.jarvis import JarvisSession, JarvisMessage`
- [ ] Models exported from `database/models/__init__.py`

---

### Phase 2: Schemas + Service Layer (Day 1 — Afternoon)

**Goal:** Pydantic schemas for API validation + core Jarvis service functions.

#### Schemas: `backend/app/schemas/jarvis.py`

| Schema | Purpose |
|--------|---------|
| `JarvisSessionCreate` | Request to create session |
| `JarvisSessionResponse` | Session details with context |
| `JarvisMessageSend` | User sends message |
| `JarvisMessageResponse` | AI response with metadata |
| `JarvisContextUpdate` | Partial context update |
| `JarvisBillSummary` | Variant bill data for card |
| `JarvisOtpRequest` | Business email OTP |
| `JarvisOtpVerify` | OTP verification |
| `JarvisDemoPackPurchase` | Demo pack purchase |
| `JarvisHandoffRequest` | Handoff execution |
| `JarvisHistoryResponse` | Paginated chat history |

#### Service: `backend/app/services/jarvis_service.py`

| Function | Purpose |
|----------|---------|
| `create_or_resume_session(db, user_id)` | Create new or return active session |
| `get_session(db, session_id, user_id)` | Get session with context |
| `get_session_context(db, session_id)` | Get context_json for AI injection |
| `update_context(db, session_id, partial)` | Update specific context fields |
| `send_message(db, session_id, user_message)` | Save user msg + call AI + save response + check limits |
| `get_history(db, session_id, limit, offset)` | Paginated message history |
| `check_message_limit(db, session)` | Check if user can send more messages |
| `purchase_demo_pack(db, session_id)` | Activate demo pack |
| `send_business_otp(db, session_id, email)` | Generate and send OTP |
| `verify_business_otp(db, session_id, code)` | Verify OTP code |
| `create_payment_session(db, session_id, variants)` | Create Paddle checkout |
| `execute_handoff(db, session_id)` | Transition to customer care |
| `increment_message_count(db, session_id)` | Daily counter management |
| `build_system_prompt(db, session_id)` | Dynamic system prompt with context injection |

#### Files to Create

| # | File | Lines (est.) | What |
|---|------|-------------|------|
| 3 | `backend/app/schemas/jarvis.py` | ~200 | All Pydantic schemas |
| 4 | `backend/app/services/jarvis_service.py` | ~500 | Core service functions |

#### Acceptance Criteria
- [ ] All schemas pass Pydantic validation
- [ ] `create_or_resume_session` creates session in DB
- [ ] `send_message` saves user message + generates AI response
- [ ] `check_message_limit` enforces 20/day limit
- [ ] `build_system_prompt` injects context into prompt

---

### Phase 3: API Endpoints (Day 2 — Morning)

**Goal:** FastAPI router with all Jarvis endpoints wired to service layer.

#### Router: `backend/app/api/jarvis.py`

| Method | Endpoint | Auth | Handler |
|--------|----------|------|---------|
| `POST` | `/api/jarvis/session` | `get_current_user` | Create/resume session |
| `GET` | `/api/jarvis/session` | `get_current_user` | Get current session |
| `GET` | `/api/jarvis/history` | `get_current_user` | Chat history |
| `POST` | `/api/jarvis/message` | `get_current_user` | Send message |
| `PATCH` | `/api/jarvis/context` | `get_current_user` | Update context |
| `POST` | `/api/jarvis/demo-pack/purchase` | `get_current_user` | Buy demo pack |
| `GET` | `/api/jarvis/demo-pack/status` | `get_current_user` | Demo pack info |
| `POST` | `/api/jarvis/verify/send-otp` | `get_current_user` | Send OTP |
| `POST` | `/api/jarvis/verify/verify-otp` | `get_current_user` | Verify OTP |
| `POST` | `/api/jarvis/payment/create` | `get_current_user` | Create Paddle session |
| `POST` | `/api/jarvis/payment/webhook` | None (Paddle) | Webhook handler |
| `GET` | `/api/jarvis/payment/status` | `get_current_user` | Payment status |
| `POST` | `/api/jarvis/handoff` | `get_current_user` | Execute handoff |

#### Files to Create / Update

| # | File | Action |
|---|------|--------|
| 5 | `backend/app/api/jarvis.py` | **Create** — full router with all endpoints |
| 6 | `backend/app/main.py` | **Update** — register `jarvis_router` |
| 7 | `backend/app/api/__init__.py` | **Update** — import jarvis router |

#### Acceptance Criteria
- [ ] `POST /api/jarvis/session` returns new session
- [ ] `POST /api/jarvis/message` returns AI response
- [ ] `PATCH /api/jarvis/context` updates session context
- [ ] All endpoints return structured JSON (matching PARWA error format)
- [ ] Auth-protected endpoints return 401 without token
- [ ] Paddle webhook endpoint works without auth

---

### Phase 4: Frontend Types + Hook (Day 2 — Afternoon)

**Goal:** TypeScript types and the `useJarvisChat` hook that manages all chat state.

#### Types: `src/types/jarvis.ts`

| Type | Purpose |
|------|---------|
| `JarvisMessage` | Single message (role, content, type, metadata, timestamp) |
| `JarvisSession` | Session with context, limits, pack info |
| `JarvisContext` | Full context shape (pages, variants, ROI, concerns, etc.) |
| `JarvisBillSummary` | Variant name, qty, price per unit, total |
| `OtpState` | OTP flow state (idle, sending, sent, verified, error) |
| `PaymentState` | Payment flow state (idle, processing, success, failed) |
| `HandoffState` | Handoff flow state |
| `MessageType` | Union type: text \| bill_summary \| payment_card \| otp_card \| handoff_card \| demo_call_card |

#### Hook: `src/hooks/useJarvisChat.ts`

This is the **brain of the frontend**. It manages:

| State | Type | Purpose |
|-------|------|---------|
| `messages` | `JarvisMessage[]` | Chat history |
| `session` | `JarvisSession \| null` | Current session info |
| `isLoading` | `boolean` | API call in progress |
| `isTyping` | `boolean` | Jarvis is "thinking" |
| `remainingToday` | `number` | Messages left today |
| `isLimitReached` | `boolean` | Hit 20/day limit |
| `isDemoPackActive` | `boolean` | $1 pack active |
| `otpState` | `OtpState` | OTP verification flow |
| `paymentState` | `PaymentState` | Payment flow |
| `handoffState` | `HandoffState` | Handoff flow |

| Action | Returns | Purpose |
|--------|---------|---------|
| `initSession()` | `Promise<void>` | Create/resume session on page load |
| `sendMessage(content)` | `Promise<void>` | Send user message, get AI response |
| `updateContext(partial)` | `void` | Update context (e.g., variant selection from pricing) |
| `sendOtp(email)` | `Promise<void>` | Trigger OTP to business email |
| `verifyOtp(code)` | `Promise<boolean>` | Verify OTP |
| `purchaseDemoPack()` | `Promise<void>` | Buy $1 demo pack |
| `createPayment(variants)` | `Promise<string>` | Initiate Paddle checkout |
| `executeHandoff()` | `Promise<void>` | Transition to customer care |
| `retryLastMessage()` | `Promise<void>` | Retry failed message |

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 8 | `src/types/jarvis.ts` | ~150 |
| 9 | `src/hooks/useJarvisChat.ts` | ~400 |

#### Acceptance Criteria
- [ ] All types compile without errors
- [ ] `initSession()` creates session via API and stores in state
- [ ] `sendMessage()` appends user message, shows typing, appends Jarvis response
- [ ] `sendMessage()` blocks when `isLimitReached` is true
- [ ] Context updates reflect in subsequent AI responses

---

### Phase 5: Core Chat UI (Day 3 — Full Day)

**Goal:** The visual chat interface — messages, input, typing indicator.

#### Components

| # | Component | Lines (est.) | What It Renders |
|---|-----------|-------------|----------------|
| 10 | `JarvisChat.tsx` | ~200 | **Main container** — wraps everything, calls `useJarvisChat` hook |
| 11 | `ChatWindow.tsx` | ~120 | Scrollable message list, auto-scroll to bottom |
| 12 | `ChatMessage.tsx` | ~180 | Single message bubble (different style for user vs Jarvis vs system) |
| 13 | `ChatInput.tsx` | ~150 | Input field + send button + disabled state when limit reached |
| 14 | `TypingIndicator.tsx` | ~40 | Three bouncing dots animation |

#### The `/onboarding` Page: `src/app/onboarding/page.tsx`

```
+------------------------------------------------------------------+
|  [PARWA Logo]    Home    Models    ROI    Jarvis*    [User Icon]  |
|                                                    (active)       |
+------------------------------------------------------------------+
|                                                                   |
|  <JarvisChat>                                                     |
|    <ChatWindow>                                                   |
|      <ChatMessage role="jarvis" />                                |
|      <ChatMessage role="user" />                                  |
|      <ChatMessage role="jarvis" />                                |
|      <TypingIndicator /> (when Jarvis is thinking)                |
|    </ChatWindow>                                                  |
|                                                                   |
|    <ChatInput />                                                  |
|    <MessageCounter />                                             |
|    <DemoPackCTA /> (when < 5 remaining)                           |
|  </JarvisChat>                                                    |
|                                                                   |
+------------------------------------------------------------------+
```

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 15 | `src/app/onboarding/page.tsx` | ~80 |
| 16 | `src/components/jarvis/JarvisChat.tsx` | ~200 |
| 17 | `src/components/jarvis/ChatWindow.tsx` | ~120 |
| 18 | `src/components/jarvis/ChatMessage.tsx` | ~180 |
| 19 | `src/components/jarvis/ChatInput.tsx` | ~150 |
| 20 | `src/components/jarvis/TypingIndicator.tsx` | ~40 |
| 21 | `src/components/jarvis/index.ts` | ~20 |

#### Acceptance Criteria
- [ ] `/onboarding` renders full chat page with header
- [ ] Typing "hello" sends message, shows typing indicator, gets Jarvis response
- [ ] Messages auto-scroll to bottom on new message
- [ ] User messages right-aligned, Jarvis messages left-aligned
- [ ] Input disabled when limit reached, shows upgrade message
- [ ] Typing indicator shows during AI response generation
- [ ] Not logged in → redirected to `/login?redirect=/onboarding`

---

### Phase 6: In-Chat Rich Cards (Day 4 — Full Day)

**Goal:** Special card components that appear inline in the chat flow for interactive actions.

#### Cards

| # | Component | When It Appears | What It Does |
|---|-----------|----------------|-------------|
| 22 | `BillSummaryCard.tsx` | User selects variants, asks about pricing | Shows selected variants + qty + price + total. "Proceed to Payment" button |
| 23 | `PaymentCard.tsx` | User clicks "Proceed" or wants demo pack | Shows $1 demo pack OR variant subscription payment. Paddle button |
| 24 | `OtpVerificationCard.tsx` | Before payment (anti-scam) | Business email input → "Send OTP" → 6-digit input → "Verify" |
| 25 | `HandoffCard.tsx` | After successful payment | Celebration message + "Meet Your Customer Care Jarvis" button |
| 26 | `DemoCallCard.tsx` | User has demo pack, wants voice call | Phone input + OTP + "Start Call" + 3-min timer |
| 27 | `MessageCounter.tsx` | Always visible at bottom | "16/20 messages remaining today" |
| 28 | `DemoPackCTA.tsx` | < 5 messages remaining | Highlighted: "Upgrade for 500 messages + AI call — $1" |

#### How Cards Work

Cards are **not separate from the chat** — they are a special `message_type` in the chat stream. When Jarvis responds with `message_type: "bill_summary"`, the `ChatMessage.tsx` component renders the `BillSummaryCard` instead of a text bubble.

```
<ChatMessage
  message={{
    role: "jarvis",
    message_type: "bill_summary",
    metadata: {
      variants: [
        { name: "Returns & Refunds", qty: 3, unit_price: 49, total: 147 },
        { name: "Product FAQ", qty: 2, unit_price: 79, total: 158 }
      ],
      grand_total: 305
    }
  }}
/>
```

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 22 | `src/components/jarvis/BillSummaryCard.tsx` | ~120 |
| 23 | `src/components/jarvis/PaymentCard.tsx` | ~150 |
| 24 | `src/components/jarvis/OtpVerificationCard.tsx` | ~180 |
| 25 | `src/components/jarvis/HandoffCard.tsx` | ~100 |
| 26 | `src/components/jarvis/DemoCallCard.tsx` | ~150 |
| 27 | `src/components/jarvis/MessageCounter.tsx` | ~60 |
| 28 | `src/components/jarvis/DemoPackCTA.tsx` | ~80 |

#### Acceptance Criteria
- [ ] `BillSummaryCard` displays variant rows with qty, price, totals
- [ ] `PaymentCard` shows Paddle checkout button
- [ ] `OtpVerificationCard` has email input → send → code input → verify flow
- [ ] `HandoffCard` shows celebration + handoff button
- [ ] `DemoCallCard` shows phone input + call button + timer
- [ ] All cards render inline in chat stream (not popups/modals)

---

### Phase 7: Cross-Page Context Integration (Day 5 — Morning)

**Goal:** When user selects variants on pricing page and then comes to `/onboarding`, Jarvis already knows what they picked.

#### What Gets Wired

| Source | Destination | Data |
|--------|------------|------|
| Pricing page variant selection | `/onboarding` context | `selected_variants`, `industry`, `quantities` |
| ROI calculator results | `/onboarding` context | `roi_result` (current cost, PARWA cost, savings) |
| Landing page sections visited | `/onboarding` context | `pages_visited` array |
| Navigation bar "Jarvis" click | `/onboarding` route | `referral_source: "nav_bar"` |

#### Implementation

1. **Pricing page** — When user clicks "Proceed with Jarvis" or nav "Jarvis":
   ```typescript
   // Save to localStorage or pass via URL params
   router.push('/onboarding');
   ```
   
2. **`useJarvisChat` hook** — On `initSession()`:
   ```typescript
   // Read from localStorage/pricing state
   const pricingState = localStorage.getItem('parwa_pricing_selection');
   if (pricingState) {
     await updateContext(JSON.parse(pricingState));
   }
   ```

3. **`build_system_prompt()` backend** — Injects context:
   ```
   The user has selected:
   - Industry: E-commerce
   - Variants: Returns & Refunds (x3), Product FAQ (x2)
   - Monthly total: $305
   - ROI: saves $47,000/year
   ```

#### Files to Update

| # | File | Action |
|---|------|--------|
| 29 | `src/hooks/useJarvisChat.ts` | Add context reading from pricing state |
| 30 | `src/components/pricing/TotalSummary.tsx` | Add "Proceed with Jarvis" button |
| 31 | `src/components/layout/NavigationBar.tsx` | Link "Jarvis Chatbot" → `/onboarding` |

#### Acceptance Criteria
- [ ] User selects variants on pricing → clicks "Proceed with Jarvis" → lands on `/onboarding`
- [ ] Jarvis's first message references the selected variants: "I see you've selected Returns x3 and FAQ x2..."
- [ ] ROI results appear in context if user calculated them
- [ ] Navigation "Jarvis Chatbot" link navigates to `/onboarding`

---

### Phase 8: AI System Prompt + Intelligence (Day 5 — Afternoon)

**Goal:** Make Jarvis smart — it plays all three roles (Guide, Salesman, Demo) naturally.

#### System Prompt Strategy

The `build_system_prompt()` function in `jarvis_service.py` constructs a dynamic prompt based on the session context:

```python
def build_system_prompt(db, session_id):
    context = get_session_context(db, session_id)
    
    base_prompt = BASE_JARVIS_PERSONA  # Static persona
    
    # Inject context awareness
    if context.get("selected_variants"):
        base_prompt += f"\n\nUSER'S SELECTED VARIANTS: {context['selected_variants']}"
    
    if context.get("industry"):
        base_prompt += f"\n\nUSER'S INDUSTRY: {context['industry']}"
    
    if context.get("roi_result"):
        base_prompt += f"\n\nUSER'S ROI CALCULATION: {context['roi_result']}"
    
    # Inject conversation history (last 10 messages for context)
    recent_messages = get_recent_messages(db, session_id, limit=10)
    if recent_messages:
        base_prompt += "\n\nRECENT CONVERSATION:\n"
        for msg in recent_messages:
            base_prompt += f"{msg.role}: {msg.content}\n"
    
    # Inject information boundaries
    base_prompt += INFO_BOUNDARY_RULES
    
    # Stage detection for response tuning
    stage = detect_stage(context)
    base_prompt += f"\n\nCURRENT STAGE: {stage}"
    base_prompt += STAGE_BEHAVIORS[stage]
    
    return base_prompt
```

#### Stage Detection Logic

| Context Signals | Detected Stage | Jarvis Behavior |
|----------------|---------------|-----------------|
| No variants selected, early in conversation | `WELCOME` | Introduce, offer guidance |
| User asking questions about features | `DISCOVERY` | Answer knowledgeably |
| User says "show me" / "demo" | `DEMO` | Roleplay as customer care agent |
| User asks about cost / has variants | `PRICING` | Show pricing, guide to selection |
| Variants in context, no payment yet | `BILL_REVIEW` | Show bill summary, confirm |
| Payment initiated but not verified | `VERIFICATION` | Guide through OTP |
| Email verified, ready to pay | `PAYMENT` | Initiate Paddle checkout |
| Payment completed | `HANDOFF` | Execute transition |

#### Demo Capability

When Jarvis is in DEMO stage, the AI responds AS IF it's the customer care agent:

```
System prompt addition for DEMO stage:
"You are now demonstrating your capabilities. When the user asks
 you to show something, ROLEPLAY as the Customer Care Jarvis that
 the user would get after hiring. Handle their sample query the way
 a real customer support interaction would go. Use realistic details."
```

#### Files to Update

| # | File | Action |
|---|------|--------|
| 32 | `backend/app/services/jarvis_service.py` | Add `build_system_prompt()`, `detect_stage()`, demo mode logic |

#### Acceptance Criteria
- [ ] Jarvis introduces itself on first message
- [ ] When user asks about refund handling, Jarvis demonstrates (DEMO mode)
- [ ] When user has variants in context, Jarvis mentions them naturally
- [ ] Jarvis never reveals internal strategy/tech details
- [ ] Stage transitions are smooth, not abrupt

---

### Phase 9: Payment Integration (Day 6 — Morning)

**Goal:** Paddle checkout for both $1 demo pack AND variant subscription.

#### Two Payment Flows

| Flow | Trigger | Amount | What User Gets |
|------|---------|--------|---------------|
| Demo Pack | User runs out of free messages OR requests it | $1 | 500 messages + 3 min AI call for 24 hours |
| Variant Subscription | User proceeds after bill summary | Variable (based on variants selected) | Hired AI agents |

#### Demo Pack Flow (Inside Chat)

```
User hits 20 msg limit OR clicks "Upgrade"
    → Jarvis: "Want 500 messages and a 3-min AI call for $1?"
    → PaymentCard appears in chat
    → User clicks "Pay $1 with Paddle"
    → Paddle overlay opens
    → Payment completes
    → Webhook fires → backend updates session.pack_type = "demo"
    → Jarvis: "Done! You have 500 messages and a 3-min call. What next?"
```

#### Variant Subscription Flow (Inside Chat)

```
User confirms bill summary
    → Jarvis: "Let me verify your business email first..."
    → OtpVerificationCard appears
    → User enters email, receives OTP, verifies
    → Jarvis: "Verified! Let's process your payment..."
    → PaymentCard appears with variant total
    → User clicks "Pay with Paddle"
    → Paddle checkout opens
    → Payment completes
    → Webhook fires → backend updates session.payment_status = "completed"
    → HandoffCard appears
    → Transition to Customer Care Jarvis
```

#### Files to Create / Update

| # | File | Action |
|---|------|--------|
| 33 | `backend/app/services/paddle_service.py` | **Update** — add demo pack checkout + webhook handling |
| 34 | `backend/app/api/jarvis.py` | **Update** — wire payment endpoints to paddle_service |
| 35 | `src/components/jarvis/PaymentCard.tsx` | **Update** — integrate Paddle.js checkout |

#### Acceptance Criteria
- [ ] Demo pack purchase: $1 → session updated → messages counter resets to 500
- [ ] Variant payment: correct total → session updated → handoff triggers
- [ ] Payment failure: Jarvis shows error, offers retry
- [ ] Webhook handles duplicate events gracefully (idempotency)

---

### Phase 10: Handoff + Post-Onboarding (Day 6 — Afternoon)

**Goal:** Smooth transition from Onboarding Jarvis to Customer Care Jarvis. UI changes.

#### Handoff Sequence

```
Payment webhook confirms success
    → backend: execute_handoff(session_id)
      - Mark onboarding session handoff_completed = True
      - Create NEW session: type = "customer_care"
      - Transfer selective context (variants, industry, business info)
      - DO NOT transfer chat history
    → frontend: HandoffCard appears in chat
    → User clicks "Meet Your Customer Care Jarvis"
    → Navigate to /dashboard (NEW UI)
```

#### Post-Handoff: Dashboard UI

The `/dashboard` route has a completely different interface:

```
+------------------------------------------------------------------+
|  [PARWA Logo]    Dashboard    Tickets    KB    Settings    [User] |
+------------------------------------------------------------------+
|                                                                   |
|  +-- Welcome Card ------+  +-- Active Agents ----------+         |
|  | Welcome back!         |  | Returns Agent    x3  Active|         |
|  | 5 variants hired      |  | FAQ Agent       x2  Active|         |
|  | 247 tickets resolved  |  | Shipping Agent   x1  Active|         |
|  +-----------------------+  +--------------------------+         |
|                                                                   |
|  +-- Knowledge Base -----+  +-- Integrations ----------+         |
|  | 12 documents uploaded  |  | Shopify    Connected     |         |
|  | 94% coverage score     |  | Zendesk    Connected     |         |
|  | [Upload More]          |  | Email      Not setup     |         |
|  +-----------------------+  +--------------------------+         |
|                                                                   |
|  +-- Recent Tickets -----------------------------------------+   |
|  | #1042  Refund request   Sarah    Resolved  12s         |   |
|  | #1041  Order status     Mike     In Progress           |   |
|  | #1040  Product question Amy      New                   |   |
|  +-------------------------------------------------------+   |
|                                                                   |
+------------------------------------------------------------------+
```

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 36 | `src/app/dashboard/page.tsx` | ~150 |
| 37 | `src/components/dashboard/DashboardLayout.tsx` | ~120 |
| 38 | `src/components/dashboard/WelcomeCard.tsx` | ~80 |
| 39 | `src/components/dashboard/ActiveAgentsCard.tsx` | ~100 |
| 40 | `src/components/dashboard/RecentTicketsCard.tsx` | ~100 |

#### Acceptance Criteria
- [ ] Handoff creates new `customer_care` session in DB
- [ ] Onboarding session marked as `handoff_completed = True`
- [ ] Chat history NOT transferred to new session
- [ ] HandoffCard shows in chat after payment success
- [ ] Clicking "Meet Your Jarvis" navigates to `/dashboard`
- [ ] `/dashboard` shows completely different UI (no chat)
- [ ] Not logged in or no payment → redirect away from `/dashboard`

---

### Phase 11: Navigation + Auth Guard (Day 6 — Evening)

**Goal:** Wire the navigation and protect routes.

#### Changes

| File | Change |
|------|--------|
| `src/components/layout/NavigationBar.tsx` | "Jarvis Chatbot" → `/onboarding`; Add auth-aware nav (show "Dashboard" after payment) |
| `src/app/onboarding/page.tsx` | Auth guard: redirect to `/login?redirect=/onboarding` if not logged in |
| `src/app/dashboard/page.tsx` | Auth guard + payment check: redirect to `/` if not paid |
| `src/hooks/useAuth.ts` | Add `hasCompletedOnboarding` check |

#### Nav Bar States

**Before Login:**
```
[PARWA Logo]    Home    Models    ROI    Jarvis    [Login]
```

**After Login (Pre-Payment):**
```
[PARWA Logo]    Home    Models    ROI    Jarvis*    [User Menu]
                                                    (active)
```

**After Payment (Post-Onboarding):**
```
[PARWA Logo]    Dashboard    Tickets    KB    Settings    [User Menu]
```

#### Files to Update

| # | File | Action |
|---|------|--------|
| 41 | `src/components/layout/NavigationBar.tsx` | Update nav items, auth-aware rendering |
| 42 | `src/hooks/useAuth.ts` | Add onboarding/payment status checks |

#### Acceptance Criteria
- [ ] "Jarvis Chatbot" in nav navigates to `/onboarding`
- [ ] Not logged in + click Jarvis → redirected to `/login?redirect=/onboarding`
- [ ] After login → nav shows user menu
- [ ] After payment → nav changes to dashboard layout
- [ ] `/dashboard` inaccessible without payment → redirect to `/`

---

### Phase 12: Mobile Responsive + Polish (Day 7)

**Goal:** Make everything work beautifully on mobile + polish animations.

#### Responsive Breakpoints

| Breakpoint | Chat Layout | Input Layout | Card Layout |
|-----------|-------------|-------------|-------------|
| Desktop (1024px+) | 720px centered, full height | Full-width input bar | Cards inline |
| Tablet (768-1023px) | Full width, slight padding | Full-width input bar | Cards inline |
| Mobile (< 768px) | Full screen, no padding | Bottom-fixed input (chat app style) | Cards stack full-width |

#### Animations

| Element | Animation | Duration |
|---------|-----------|----------|
| New message | Slide in from bottom + fade in | 300ms |
| Typing indicator | Bouncing dots | Continuous |
| Card appear | Expand + fade in | 400ms |
| Send button | Scale pulse on click | 150ms |
| Message counter | Color transition (green → amber → red) | 500ms |
| Handoff card | Celebration particles | 2s |

#### Files to Update

| # | File | Action |
|---|------|--------|
| 43 | `src/app/onboarding/page.tsx` | Add mobile layout |
| 44 | `src/components/jarvis/JarvisChat.tsx` | Responsive container |
| 45 | `src/components/jarvis/ChatMessage.tsx` | Animation on mount |
| 46 | `src/components/jarvis/ChatInput.tsx` | Mobile bottom-fixed layout |
| 47 | `src/components/jarvis/BillSummaryCard.tsx` | Mobile responsive |

#### Acceptance Criteria
- [ ] Chat works on 375px width (iPhone SE)
- [ ] Chat works on 1440px width (desktop)
- [ ] Input stays visible above keyboard on mobile
- [ ] Cards are readable on mobile (no horizontal scroll)
- [ ] Smooth animations on all message types
- [ ] No layout shift when typing indicator appears

---

### Phase 13: Tests (Day 7 — Parallel with Polish)

**Goal:** Unit tests for backend + integration tests for API.

#### Test Files

| # | File | Tests |
|---|------|-------|
| 48 | `tests/unit/test_jarvis_service.py` | `create_session`, `send_message`, `check_limit`, `build_prompt`, `execute_handoff`, `demo_pack`, `otp` |
| 49 | `tests/unit/test_jarvis_api.py` | All 13 API endpoints: success + auth + validation + edge cases |
| 50 | `tests/unit/test_jarvis_models.py` | Model creation, relationships, constraints |

#### Test Coverage Goals

| Module | Target Coverage |
|--------|----------------|
| `jarvis_service.py` | 85%+ |
| `jarvis.py` (API) | 90%+ |
| `jarvis.py` (models) | 95%+ |

#### Acceptance Criteria
- [ ] All tests pass: `pytest tests/unit/test_jarvis* -v`
- [ ] No regression in existing tests: `pytest tests/unit/ -v`
- [ ] Coverage report shows 85%+ for new code

---

### Phase 14: Mirror + Commit (Day 7 — Final)

**Goal:** Sync `src/` mirror and push to GitHub.

#### Mirror Sync

Every new/updated file in `src/` must be mirrored to `frontend/src/`:

```bash
# Copy all new files
cp -r src/app/onboarding/ frontend/src/app/onboarding/
cp -r src/components/jarvis/ frontend/src/components/jarvis/
cp -r src/app/dashboard/ frontend/src/app/dashboard/
cp -r src/components/dashboard/ frontend/src/components/dashboard/
cp src/hooks/useJarvisChat.ts frontend/src/hooks/
cp src/types/jarvis.ts frontend/src/types/
```

#### Files to Mirror

| # | Source | Destination |
|---|--------|-------------|
| 51 | `src/app/onboarding/page.tsx` | `frontend/src/app/onboarding/page.tsx` |
| 52 | `src/components/jarvis/*` | `frontend/src/components/jarvis/*` |
| 53 | `src/hooks/useJarvisChat.ts` | `frontend/src/hooks/useJarvisChat.ts` |
| 54 | `src/types/jarvis.ts` | `frontend/src/types/jarvis.ts` |
| 55 | `src/app/dashboard/page.tsx` | `frontend/src/app/dashboard/page.tsx` |
| 56 | `src/components/dashboard/*` | `frontend/src/components/dashboard/*` |

#### Acceptance Criteria
- [ ] `diff -r src/app/onboarding/ frontend/src/app/onboarding/` — no differences
- [ ] `diff -r src/components/jarvis/ frontend/src/components/jarvis/` — no differences
- [ ] `git push` succeeds

---

## Summary

### Total Files

| Category | New Files | Updated Files | Total |
|----------|----------|---------------|-------|
| Database (migration + models) | 2 | 1 | 3 |
| Backend (schemas + service + API) | 3 | 2 | 5 |
| Frontend Types + Hook | 2 | 0 | 2 |
| Frontend Components | 18 | 5 | 23 |
| Tests | 3 | 0 | 3 |
| Mirror copies | 6 | 0 | 6 |
| **TOTAL** | **34** | **8** | **42** |

### Timeline

| Day | Phase | Key Deliverable |
|-----|-------|----------------|
| **Day 1** | Phase 1-2 | Database tables + models + schemas + service |
| **Day 2** | Phase 3-4 | API endpoints + TypeScript types + hook |
| **Day 3** | Phase 5 | Core chat UI (JarvisChat, messages, input) |
| **Day 4** | Phase 6 | Rich cards (bill, payment, OTP, handoff) |
| **Day 5** | Phase 7-8 | Cross-page context + AI intelligence |
| **Day 6** | Phase 9-11 | Payment + handoff + dashboard + navigation |
| **Day 7** | Phase 12-14 | Mobile + polish + tests + mirror + push |

### Dependencies

```
Phase 1 (DB) ────┐
                   ├──> Phase 2 (Service) ──> Phase 3 (API)
Phase 4 (Types) ─┘                          │
                                            v
                                     Phase 5 (Core UI)
                                            │
                                            v
                                     Phase 6 (Rich Cards)
                                            │
                                            v
                              Phase 7 (Context) + Phase 8 (AI)
                                            │
                                            v
                                     Phase 9 (Payment)
                                            │
                                            v
                                     Phase 10 (Handoff + Dashboard)
                                            │
                                            v
                              Phase 11 (Navigation)
                                            │
                                            v
                              Phase 12 (Polish) + Phase 13 (Tests)
                                            │
                                            v
                              Phase 14 (Mirror + Push)
```

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Paddle not configured yet | Build payment with mock/sandbox mode first, swap real keys later |
| z-ai-web-dev-sdk rate limits | Add retry logic + graceful fallback in service |
| Daily message reset timezone | Store user timezone, use for reset calculation |
| Large context_json slowing AI calls | Summarize old context, keep only recent + key facts |
| Mobile keyboard covering input | Use `visualViewport` API for proper positioning |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Week 6 Day 8 | Complete 7-day build roadmap |

---

*This roadmap is the execution plan for JARVIS_SPECIFICATION.md v1.0. Follow phases in order.*
