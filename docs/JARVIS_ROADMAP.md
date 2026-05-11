# PARWA Jarvis Build Roadmap — Complete

> **Document Version:** 4.0
> **Created:** Week 6 Day 8 (April 2026)
> **Updated:** Week 6 Day 10 — Added: action_tickets table to migration, Knowledge Service functions, aligned with Spec v3.0
> **Updated:** Week X — Added: Phase 15-19 Provider-Agnostic Integration Architecture, API Key Auto-Detection, Jarvis Integration Setup Flow
> **Based On:** JARVIS_SPECIFICATION.md v3.0
> **Scope:** Complete Jarvis onboarding system — EVERYTHING from code zero to production-ready

---

## Overview

**One page. One Jarvis. Everything happens here.**

The `/onboarding` page is THE single page where the entire pre-purchase experience happens:
- Demo chat (conversing with Jarvis)
- Demo call booking ($1 AI voice call) — full flow inside chat
- Post-call summary (Jarvis tells what happened in the call)
- Action ticket system (every action = ticket with result)
- ROI context-aware entry (adapts to where user came from)
- Business email OTP verification
- Variant payment (Paddle checkout)
- Bill summary display
- Handoff to Customer Care Jarvis
- **Jarvis IS the product demo** — users see the actual product

After onboarding completes, the UI changes completely — dashboard takes over.

---

## Complete Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      /onboarding (ONE PAGE)                       │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                       JARVIS CHAT                             │ │
│  │                                                               │ │
│  │  [NON-LINEAR]: Users enter from demo/ROI/pricing/chat       │ │
│  │  Jarvis adapts based on entry_source in context_json         │ │
│  │                                                               │ │
│  │  Demo → ROI Chat → Pricing → Bill → OTP → Payment → Handoff  │ │
│  │  [All flows inside chat — every action = ticket]           │ │
│  │                                                               │ │
│  │  [All flows inside chat — rich cards for interactive actions] │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Backend Layers:                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  API Layer (jarvis.py)                                      │  │
│  │    → Service Layer (jarvis_service.py)                      │  │
│  │      → Knowledge Service (jarvis_knowledge_service.py)      │  │
│  │        → AI Provider (z-ai-web-dev-sdk)                     │  │
│  │          → Knowledge Base (JSON files)                      │  │
│  │            → System Prompt + Context + RAG                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Complete Build Phases (19 Phases, 12 Days)

### NEW in v4.0 (from Spec v3.0)

| Addition | Where | What |
|----------|-------|------|
| `jarvis_action_tickets` table | Phase 1 | New DB table for ticket CRUD + independent querying |
| Knowledge Base section | Phase 7 | 10 JSON files + knowledge service (now fully specified in Spec Sec 12) |
| Action Ticket System | Phase 2, 4, 6 | Every action treated as ticket with status + result |
| Post-Call Summary | Phase 6 | Card showing what happened in demo call |
| Non-Linear Entry Routing | Phase 9 | URL params + context-aware welcome |
| ActionTicketCard.tsx | Phase 6 | New card component for tickets |
| PostCallSummaryCard.tsx | Phase 6 | New card for call summary |
| ticket management endpoints | Phase 3 | New API endpoints for ticket CRUD |
| entry context endpoint | Phase 3 | New API endpoint for URL param routing |

---

### Phase 1: Database + Models (Day 1 — Morning)

**Goal:** Create the data layer that everything else depends on.

#### Migration: `012_jarvis_system.py`

```sql
-- jarvis_sessions
CREATE TABLE jarvis_sessions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL REFERENCES users(id),
    company_id           UUID REFERENCES companies(id),
    type                 VARCHAR(20) NOT NULL DEFAULT 'onboarding'
                         CHECK (type IN ('onboarding', 'customer_care')),
    context_json         JSONB NOT NULL DEFAULT '{}',
    message_count_today  INTEGER NOT NULL DEFAULT 0,
    last_message_date    DATE,
    total_message_count  INTEGER NOT NULL DEFAULT 0,
    pack_type            VARCHAR(10) NOT NULL DEFAULT 'free'
                         CHECK (pack_type IN ('free', 'demo')),
    pack_expiry          TIMESTAMP,
    demo_call_used       BOOLEAN NOT NULL DEFAULT FALSE,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    payment_status       VARCHAR(15) NOT NULL DEFAULT 'none'
                         CHECK (payment_status IN ('none','pending','completed','failed')),
    handoff_completed    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMP NOT NULL DEFAULT NOW()
);

-- jarvis_messages
CREATE TABLE jarvis_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES jarvis_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(10) NOT NULL
                    CHECK (role IN ('user', 'jarvis', 'system')),
    content         TEXT NOT NULL,
    message_type    VARCHAR(25) NOT NULL DEFAULT 'text'
                    CHECK (message_type IN (
                        'text', 'bill_summary', 'payment_card',
                        'otp_card', 'handoff_card', 'demo_call_card',
                        'error', 'limit_reached', 'pack_expired'
                    )),
    metadata_json   JSONB DEFAULT '{}',
    timestamp       TIMESTAMP NOT NULL DEFAULT NOW()
);

-- jarvis_knowledge_used (tracks which knowledge was used per response)
CREATE TABLE jarvis_knowledge_used (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID NOT NULL REFERENCES jarvis_messages(id) ON DELETE CASCADE,
    knowledge_file  VARCHAR(100) NOT NULL,
    relevance_score FLOAT DEFAULT 1.0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_jarvis_sessions_user_active ON jarvis_sessions(user_id, is_active);
CREATE INDEX idx_jarvis_messages_session_ts ON jarvis_messages(session_id, timestamp);
CREATE INDEX idx_jarvis_sessions_company ON jarvis_sessions(company_id);
CREATE INDEX idx_jarvis_knowledge_used_msg ON jarvis_knowledge_used(message_id);

-- jarvis_action_tickets (tracks every user action as a ticket)
CREATE TABLE jarvis_action_tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES jarvis_sessions(id) ON DELETE CASCADE,
    message_id      UUID REFERENCES jarvis_messages(id) ON DELETE SET NULL,
    ticket_type     VARCHAR(30) NOT NULL
                    CHECK (ticket_type IN (
                        'otp_verification', 'otp_verified',
                        'payment_demo_pack', 'payment_variant', 'payment_variant_completed',
                        'demo_call', 'demo_call_completed',
                        'roi_import', 'handoff'
                    )),
    status          VARCHAR(15) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    result_json     JSONB DEFAULT '{}',
    metadata_json   JSONB DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMP
);

CREATE INDEX idx_jarvis_action_tickets_session ON jarvis_action_tickets(session_id);
CREATE INDEX idx_jarvis_action_tickets_status ON jarvis_action_tickets(session_id, status);
```

#### Files to Create

| # | File | Lines (est.) | What |
|---|------|-------------|------|
| 1 | `database/alembic/versions/012_jarvis_system.py` | ~140 | Migration with all 3 tables + indexes |
| 2 | `database/models/jarvis.py` | ~150 | `JarvisSession` + `JarvisMessage` + `JarvisKnowledgeUsed` + `JarvisActionTicket` models |

#### Acceptance Criteria
- [ ] Migration runs without errors
- [ ] All 4 models importable and exported from `database/models/__init__.py` (JarvisSession, JarvisMessage, JarvisKnowledgeUsed, JarvisActionTicket)
- [ ] Cascade delete works (deleting session deletes messages + knowledge_used + action_tickets)

---

### Phase 2: Schemas + Service Layer (Day 1 — Afternoon)

**Goal:** Pydantic schemas for API validation + core Jarvis service functions.

#### Schemas: `backend/app/schemas/jarvis.py`

| Schema | Purpose |
|--------|---------|
| `JarvisSessionCreate` | Request to create session |
| `JarvisSessionResponse` | Session details with context + limits |
| `JarvisMessageSend` | User sends message |
| `JarvisMessageResponse` | AI response with metadata |
| `JarvisContextUpdate` | Partial context update |
| `JarvisBillItem` | Single variant line item |
| `JarvisBillSummary` | Full bill data for card |
| `JarvisOtpRequest` | Business email OTP send |
| `JarvisOtpVerify` | OTP code verification |
| `JarvisDemoPackPurchase` | Demo pack purchase request |
| `JarvisDemoCallRequest` | Phone number for demo call |
| `JarvisHandoffRequest` | Handoff execution |
| `JarvisHistoryResponse` | Paginated chat history |
| `JarvisError` | Error response format |
| `JarvisActionTicket` | Action ticket creation + status |
| `JarvisActionTicketResponse` | Ticket with result + metadata |
| `JarvisPostCallSummary` | Call summary data + ROI mapping |

#### Service: `backend/app/services/jarvis_service.py`

| Function | Purpose |
|----------|---------|
| `create_or_resume_session(db, user_id)` | Create new or return active onboarding session |
| `get_session(db, session_id, user_id)` | Get session with full context |
| `get_session_context(db, session_id)` | Get context_json for AI injection |
| `update_context(db, session_id, partial_updates)` | Update specific context fields |
| `send_message(db, session_id, user_message)` | Save user msg → check limits → call AI → save response → return |
| `get_history(db, session_id, limit, offset)` | Paginated message history |
| `check_message_limit(db, session)` | Returns remaining count, whether limit reached |
| `reset_daily_counter(db, session_id)` | Reset message_count_today (called on new day) |
| `purchase_demo_pack(db, session_id)` | Set pack_type=demo, pack_expiry=now+24h, reset counter |
| `send_business_otp(db, session_id, email)` | Generate 6-digit OTP, store in context, send email |
| `verify_business_otp(db, session_id, code)` | Verify OTP, update context |
| `create_payment_session(db, session_id, variants)` | Create Paddle checkout URL |
| `handle_payment_webhook(db, event)` | Process Paddle webhook (success/fail) |
| `execute_handoff(db, session_id)` | Create customer_care session, transfer selective context |
| `initiate_demo_call(db, session_id, phone)` | Initiate Twilio voice call flow |
| `build_system_prompt(db, session_id)` | Dynamic prompt with context + knowledge |
| `detect_stage(db, session_id)` | Determine conversation stage from context |
| `handle_error(db, session_id, error)` | Graceful error handling + user-friendly message |
| `create_action_ticket(db, session_id, type, metadata)` | Create ticket for any user action |
| `update_ticket_status(db, ticket_id, status)` | Update ticket status (pending/in_progress/completed/failed) |
| `complete_ticket(db, ticket_id, result_data)` | Mark ticket completed with result data |
| `get_call_summary(db, session_id, call_id)` | Get post-call summary with topics discussed |
| `get_entry_context(entry_source, params)` | Parse URL params into context_json |
| `build_context_aware_welcome(db, session_id)` | Generate welcome based on entry source |

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 3 | `backend/app/schemas/jarvis.py` | ~250 |
| 4 | `backend/app/services/jarvis_service.py` | ~600 |

#### Acceptance Criteria
- [ ] All schemas pass Pydantic validation
- [ ] `create_or_resume_session` creates session in DB with default context
- [ ] `send_message` saves user message, calls AI, saves AI response
- [ ] `check_message_limit` enforces 20/day (free) or 500/day (demo pack)
- [ ] `reset_daily_counter` called automatically when date changes
- [ ] `build_system_prompt` injects context into prompt
- [ ] `handle_error` returns user-friendly error message (not stack trace)

---

### Phase 3: API Endpoints (Day 2 — Morning)

**Goal:** FastAPI router with all Jarvis endpoints wired to service layer.

#### Router: `backend/app/api/jarvis.py`

| Method | Endpoint | Auth | Handler | Description |
|--------|----------|------|---------|-------------|
| `POST` | `/api/jarvis/session` | `get_current_user` | `create_session` | Create or resume session |
| `GET` | `/api/jarvis/session` | `get_current_user` | `get_session` | Get current session + context |
| `GET` | `/api/jarvis/history` | `get_current_user` | `get_history` | Paginated chat history |
| `POST` | `/api/jarvis/message` | `get_current_user` | `send_message` | Send message + get AI response |
| `PATCH` | `/api/jarvis/context` | `get_current_user` | `update_context` | Update session context |
| `POST` | `/api/jarvis/demo-pack/purchase` | `get_current_user` | `purchase_demo_pack` | Buy $1 demo pack |
| `GET` | `/api/jarvis/demo-pack/status` | `get_current_user` | `demo_pack_status` | Demo pack info |
| `POST` | `/api/jarvis/verify/send-otp` | `get_current_user` | `send_otp` | Send OTP to business email |
| `POST` | `/api/jarvis/verify/verify-otp` | `get_current_user` | `verify_otp` | Verify OTP code |
| `POST` | `/api/jarvis/payment/create` | `get_current_user` | `create_payment` | Create Paddle checkout |
| `POST` | `/api/jarvis/payment/webhook` | None (Paddle sig) | `payment_webhook` | Handle Paddle webhook |
| `GET` | `/api/jarvis/payment/status` | `get_current_user` | `payment_status` | Check payment status |
| `POST` | `/api/jarvis/demo-call/initiate` | `get_current_user` | `initiate_call` | Start demo voice call |
| `POST` | `/api/jarvis/demo-call/otp` | `get_current_user` | `verify_call_otp` | Verify phone OTP |
| `POST` | `/api/jarvis/handoff` | `get_current_user` | `execute_handoff` | Transition to customer care |
| `GET` | `/api/jarvis/handoff/status` | `get_current_user` | `handoff_status` | Check if handoff done |
| `POST` | `/api/jarvis/tickets` | `get_current_user` | `create_ticket` | Create action ticket |
| `GET` | `/api/jarvis/tickets` | `get_current_user` | `get_tickets` | List all tickets for session |
| `GET` | `/api/jarvis/tickets/:id` | `get_current_user` | `get_ticket` | Get single ticket with result |
| `PATCH` | `/api/jarvis/tickets/:id/status` | `get_current_user` | `update_ticket_status` | Update ticket status |
| `GET` | `/api/jarvis/demo-call/summary` | `get_current_user` | `call_summary` | Get post-call summary |
| `POST` | `/api/jarvis/context/entry` | `get_current_user` | `set_entry_context` | Set entry source from URL params |

#### Files to Create / Update

| # | File | Action |
|---|------|--------|
| 5 | `backend/app/api/jarvis.py` | **Create** — full router with all 21 endpoints |
| 6 | `backend/app/main.py` | **Update** — register jarvis_router |
| 7 | `backend/app/api/__init__.py` | **Update** — import jarvis router |

#### Acceptance Criteria
- [ ] All 16 endpoints return correct status codes
- [ ] Auth-protected endpoints return 401 without token
- [ ] Paddle webhook endpoint works without auth (signature verification only)
- [ ] All errors return structured JSON matching PARWA error format
- [ ] Rate limiting on `POST /message` endpoint (prevent spam)

---

### Phase 4: Frontend Types + Hook (Day 2 — Afternoon)

**Goal:** TypeScript types and the `useJarvisChat` hook managing all chat state.

#### Types: `src/types/jarvis.ts`

```typescript
// Core types
type MessageType = 'text' | 'bill_summary' | 'payment_card' | 'otp_card'
  | 'handoff_card' | 'demo_call_card' | 'error' | 'limit_reached'
  | 'pack_expired';

type SessionType = 'onboarding' | 'customer_care';
type PackType = 'free' | 'demo';
type PaymentStatus = 'none' | 'pending' | 'completed' | 'failed';

// Stage types
type ConversationStage = 'welcome' | 'discovery' | 'demo' | 'pricing'
  | 'bill_review' | 'verification' | 'payment' | 'handoff';

// Context — everything Jarvis remembers
interface JarvisContext {
  pages_visited: string[];
  industry: string | null;
  selected_variants: VariantSelection[];
  roi_result: RoiResult | null;
  demo_topics: string[];
  concerns_raised: string[];
  business_email: string | null;
  email_verified: boolean;
  referral_source: string;
}

// Session
interface JarvisSession {
  id: string;
  type: SessionType;
  context: JarvisContext;
  message_count_today: number;
  total_message_count: number;
  remaining_today: number;
  pack_type: PackType;
  pack_expiry: string | null;
  demo_call_used: boolean;
  is_active: boolean;
  payment_status: PaymentStatus;
  handoff_completed: boolean;
  detected_stage: ConversationStage;
}

// Messages
interface JarvisMessage {
  id: string;
  session_id: string;
  role: 'user' | 'jarvis' | 'system';
  content: string;
  message_type: MessageType;
  metadata: Record<string, any>;
  timestamp: string;
}

// Flow states
interface OtpState { status: 'idle' | 'sending' | 'sent' | 'verifying' | 'verified' | 'error'; email: string; attempts: number; expires_at: string | null; }
interface PaymentState { status: 'idle' | 'processing' | 'success' | 'failed'; paddle_url: string | null; error: string | null; }
interface HandoffState { status: 'idle' | 'in_progress' | 'completed'; }
interface DemoCallState { status: 'idle' | 'initiating' | 'calling' | 'completed' | 'failed'; phone: string | null; duration: number; }
```

#### Hook: `src/hooks/useJarvisChat.ts`

| State | Type | Purpose |
|-------|------|---------|
| `messages` | `JarvisMessage[]` | Full chat history |
| `session` | `JarvisSession \| null` | Current session |
| `isLoading` | `boolean` | API call in progress |
| `isTyping` | `boolean` | Jarvis is generating response |
| `remainingToday` | `number` | Messages left today |
| `isLimitReached` | `boolean` | Hit daily limit |
| `isDemoPackActive` | `boolean` | $1 pack purchased |
| `otpState` | `OtpState` | OTP verification flow |
| `paymentState` | `PaymentState` | Payment flow |
| `handoffState` | `HandoffState` | Handoff flow |
| `demoCallState` | `DemoCallState` | Demo call flow |
| `error` | `string \| null` | Current error message |

| Action | Returns | Purpose |
|--------|---------|---------|
| `initSession()` | `Promise<void>` | Create/resume on page load, load history |
| `sendMessage(content)` | `Promise<void>` | Send message, get AI response |
| `retryLastMessage()` | `Promise<void>` | Retry failed message |
| `updateContext(partial)` | `void` | Update context (variant selection, etc.) |
| `sendOtp(email)` | `Promise<void>` | Send OTP to business email |
| `verifyOtp(code)` | `Promise<boolean>` | Verify OTP |
| `purchaseDemoPack()` | `Promise<void>` | Buy $1 demo pack |
| `createPayment(variants)` | `Promise<string>` | Get Paddle checkout URL |
| `initiateDemoCall(phone)` | `Promise<void>` | Start 3-min AI voice call |
| `executeHandoff()` | `Promise<void>` | Transition to customer care |
| `clearError()` | `void` | Dismiss error |

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 8 | `src/types/jarvis.ts` | ~180 |
| 9 | `src/hooks/useJarvisChat.ts` | ~500 |

#### Acceptance Criteria
- [ ] All types compile without errors
- [ ] `initSession()` creates session + loads history on page load
- [ ] `sendMessage()` appends user msg → shows typing → appends Jarvis response
- [ ] `sendMessage()` blocked when limit reached
- [ ] `retryLastMessage()` resends last failed user message
- [ ] All state transitions handled (otp, payment, handoff, demo call)
- [ ] Error state populated on failure, clearable via `clearError()`

---

### Phase 5: Core Chat UI (Day 3 — Full Day)

**Goal:** The visual chat interface.

#### Components

| # | Component | Lines (est.) | What |
|---|-----------|-------------|------|
| 10 | `src/app/onboarding/page.tsx` | ~100 | Full-page route with auth guard |
| 11 | `src/components/jarvis/JarvisChat.tsx` | ~250 | Main container — wraps all, calls hook |
| 12 | `src/components/jarvis/ChatWindow.tsx` | ~150 | Scrollable message list, auto-scroll |
| 13 | `src/components/jarvis/ChatMessage.tsx` | ~200 | Single message (text or card type) |
| 14 | `src/components/jarvis/ChatInput.tsx` | ~180 | Input field + send button |
| 15 | `src/components/jarvis/TypingIndicator.tsx` | ~50 | Three bouncing dots |
| 16 | `src/components/jarvis/ChatHeader.tsx` | ~60 | "Jarvis — Your AI Assistant" header |
| 17 | `src/components/jarvis/ErrorBanner.tsx` | ~50 | Dismissible error message banner |
| 18 | `src/components/jarvis/index.ts` | ~25 | Barrel exports |

#### Auth Guard Logic

```typescript
// In /onboarding/page.tsx
const { user, isLoading } = useAuth();

if (isLoading) return <LoadingSpinner />;
if (!user) router.push('/login?redirect=/onboarding');
if (user.onboarding_completed) router.push('/dashboard');

return <JarvisChat />;
```

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 10 | `src/app/onboarding/page.tsx` | ~100 |
| 11 | `src/components/jarvis/JarvisChat.tsx` | ~250 |
| 12 | `src/components/jarvis/ChatWindow.tsx` | ~150 |
| 13 | `src/components/jarvis/ChatMessage.tsx` | ~200 |
| 14 | `src/components/jarvis/ChatInput.tsx` | ~180 |
| 15 | `src/components/jarvis/TypingIndicator.tsx` | ~50 |
| 16 | `src/components/jarvis/ChatHeader.tsx` | ~60 |
| 17 | `src/components/jarvis/ErrorBanner.tsx` | ~50 |
| 18 | `src/components/jarvis/index.ts` | ~25 |

#### Acceptance Criteria
- [ ] `/onboarding` renders full chat page
- [ ] Not logged in → redirect to `/login?redirect=/onboarding`
- [ ] Already onboarded → redirect to `/dashboard`
- [ ] Send "hello" → typing indicator → Jarvis response
- [ ] Messages auto-scroll to bottom
- [ ] Error banner shows on API failure, dismissible
- [ ] Input disabled when limit reached

---

### Phase 6: In-Chat Rich Cards (Day 4 — Full Day)

**Goal:** Interactive card components rendered inline in chat stream. Includes the NEW action ticket card and post-call summary card.

#### Cards

| # | Component | Message Type | What It Shows |
|---|-----------|-------------|---------------|
| 19 | `BillSummaryCard.tsx` | `bill_summary` | Variant rows + qty + price + total + "Proceed" button |
| 20 | `PaymentCard.tsx` | `payment_card` | $1 demo pack OR variant payment + Paddle button |
| 21 | `OtpVerificationCard.tsx` | `otp_card` | Email input → Send OTP → 6-digit input → Verify |
| 22 | `HandoffCard.tsx` | `handoff_card` | Celebration + "Meet Customer Care Jarvis" button |
| 23 | `DemoCallCard.tsx` | `demo_call_card` | Phone input + OTP + Call button + 3-min timer |
| 24 | `MessageCounter.tsx` | (always visible) | "16/20 messages remaining today" |
| 25 | `DemoPackCTA.tsx` | (conditional) | "Upgrade — 500 msgs + AI call for $1" |
| 26 | `LimitReachedCard.tsx` | `limit_reached` | "Daily limit reached. Come back tomorrow or upgrade." |
| 27 | `PackExpiredCard.tsx` | `pack_expired` | "Demo pack expired. Options: free tier / repurchase." |
| 28 | `ActionTicketCard.tsx` | `action_ticket` | Ticket with status indicator (pending/in_progress/completed/failed) + metadata |
| 29 | `PostCallSummaryCard.tsx` | `call_summary` | Call summary: topics, key moments, impressions + ROI mapping |
| 30 | `RechargeCTACard.tsx` | `recharge_cta` | Post-call option to recharge Demo Pack or subscribe |

#### How Cards Render Inside Chat

`ChatMessage.tsx` checks `message_type` and renders the appropriate card instead of a text bubble:

```typescript
function ChatMessage({ message }) {
  switch (message.message_type) {
    case 'text':         return <TextBubble message={message} />;
    case 'bill_summary': return <BillSummaryCard data={message.metadata} />;
    case 'payment_card': return <PaymentCard data={message.metadata} />;
    case 'otp_card':     return <OtpVerificationCard ... />;
    case 'handoff_card': return <HandoffCard ... />;
    case 'demo_call_card': return <DemoCallCard ... />;
    case 'action_ticket': return <ActionTicketCard ... />;
    case 'call_summary': return <PostCallSummaryCard ... />;
    case 'recharge_cta': return <RechargeCTACard ... />;
    case 'limit_reached': return <LimitReachedCard />;
    case 'pack_expired': return <PackExpiredCard />;
    case 'error':        return <ErrorBanner message={message.content} />;
  }
}
```

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 19 | `src/components/jarvis/BillSummaryCard.tsx` | ~130 |
| 20 | `src/components/jarvis/PaymentCard.tsx` | ~180 |
| 21 | `src/components/jarvis/OtpVerificationCard.tsx` | ~200 |
| 22 | `src/components/jarvis/HandoffCard.tsx` | ~110 |
| 23 | `src/components/jarvis/DemoCallCard.tsx` | ~170 |
| 24 | `src/components/jarvis/MessageCounter.tsx` | ~70 |
| 25 | `src/components/jarvis/DemoPackCTA.tsx` | ~90 |
| 26 | `src/components/jarvis/LimitReachedCard.tsx` | ~60 |
| 27 | `src/components/jarvis/PackExpiredCard.tsx` | ~60 |

#### Acceptance Criteria
- [ ] Each card renders correctly inside chat stream
- [ ] BillSummaryCard shows variant rows + total accurately
- [ ] OtpVerificationCard has full flow: email → send → enter code → verify
- [ ] PaymentCard shows correct amount (demo pack vs variant total)
- [ ] LimitReachedCard appears when counter hits 0
- [ ] PackExpiredCard appears when demo pack expires
- [ ] All cards dispatch actions through `useJarvisChat` hook

---

### Phase 7: Jarvis Knowledge Base (Day 5 — Full Day)

**Goal:** Give Jarvis deep product knowledge so it sounds like a real salesperson who knows every detail.

#### Knowledge Structure

```
backend/app/data/jarvis_knowledge/
├── 01_pricing_tiers.json
├── 02_industry_variants.json
├── 03_variant_details.json
├── 04_integrations.json
├── 05_capabilities.json
├── 06_demo_scenarios.json
├── 07_objection_handling.json
├── 08_faq.json
├── 09_competitor_comparisons.json
└── 10_edge_cases.json
```

#### Knowledge Files Detail

**1. `01_pricing_tiers.json`** — Complete pricing breakdown

```json
{
  "tiers": [
    {
      "name": "Starter",
      "price": 999,
      "billing": "monthly",
      "target": "Small businesses starting with AI support",
      "features": ["Up to 3 AI agents", "1,000 tickets/month", "Email channel", "Basic KB upload", "Standard response time"],
      "limitations": ["No voice support", "No custom integrations", "No priority support"],
      "ideal_for": "Businesses with 1-5 support agents handling < 1,000 tickets/month"
    },
    {
      "name": "Growth",
      "price": 2499,
      "billing": "monthly",
      "target": "Growing businesses scaling support",
      "features": ["Up to 7 AI agents", "5,000 tickets/month", "Email + Chat channels", "Advanced KB with auto-learning", "Priority support", "Custom integrations", "Analytics dashboard"],
      "limitations": ["No voice support"],
      "ideal_for": "Businesses with 5-20 support agents handling 1,000-5,000 tickets/month"
    },
    {
      "name": "High",
      "price": 3999,
      "billing": "monthly",
      "target": "Large operations needing full AI support",
      "features": ["Unlimited AI agents", "20,000 tickets/month", "All channels (email, chat, phone, social)", "Advanced KB + auto-learning", "24/7 priority support", "Custom integrations", "Advanced analytics", "Voice support", "Dedicated account manager", "Custom AI training"],
      "limitations": [],
      "ideal_for": "Businesses with 20+ support agents handling 5,000+ tickets/month"
    }
  ],
  "billing_info": {
    "billing_cycle": "Monthly, cancel anytime",
    "overage": "Additional tickets billed at per-ticket rate",
    "discounts": "Annual billing available with 15% discount",
    "trial": "No free trial — demo chat available for evaluation"
  }
}
```

**2. `02_industry_variants.json`** — All 4 industries with 5 variants each

```json
{
  "industries": {
    "ecommerce": {
      "name": "E-commerce",
      "description": "Online retail stores, marketplaces, D2C brands",
      "variants": [
        {
          "id": "order_management",
          "name": "Order Management",
          "description": "Handles order status inquiries, modifications, cancellations, and tracking requests",
          "tickets_per_month": 500,
          "price_per_unit": 99,
          "what_it_handles": ["Order status checks", "Order modifications", "Order cancellations", "Delivery tracking", "Estimated delivery times", "Order history requests"],
          "sample_query": "Where is my order? Order #12345",
          "sample_response": "I've found your order #12345. It's currently being prepared for shipping and should arrive within 2-3 business days. I can see the tracking number will be available by tomorrow evening. Would you like me to send you an update when it ships?"
        },
        {
          "id": "returns_refunds",
          "name": "Returns & Refunds",
          "description": "Processes return requests, checks eligibility, handles full/partial refunds, and sends status updates",
          "tickets_per_month": 200,
          "price_per_unit": 49,
          "what_it_handles": ["Return request initiation", "Eligibility checking", "Full refunds", "Partial refunds", "Exchange processing", "Refund status tracking", "Return policy questions"],
          "sample_query": "I want to return the blue shirt I bought last week",
          "sample_response": "I found your order for the Blue Classic Shirt purchased 5 days ago. It's within our 30-day return window and eligible for a full refund. I've initiated the return process — you'll receive a prepaid shipping label at your email. Once we receive the item, your refund of $49.99 will be processed within 3-5 business days."
        }
        // ... 3 more variants (Product FAQ, Shipping Inquiries, Payment Issues)
      ]
    },
    "saas": { /* 5 variants: Technical Support, Billing Support, Feature Requests, API Support, Account Issues */ },
    "logistics": { /* 5 variants: Tracking, Delivery Issues, Warehouse Queries, Fleet Management, Customs */ },
    "others": { /* Generic variants or custom setup flow */ }
  }
}
```

**3. `03_variant_details.json`** — Deep details per variant

```json
{
  "variant_details": {
    "returns_refunds": {
      "workflow": "1. Customer submits return request → 2. Agent checks order eligibility (date, item condition, return policy) → 3. If eligible, generates return label → 4. Tracks return shipment → 5. Processes refund → 6. Sends confirmation",
      "handles_edge_cases": ["Partial refunds for used items", "Exchange vs refund choice", "Return policy exceptions", "Multiple items in one order", "International returns"],
      "integration_requirements": ["Order management system", "Payment processor", "Shipping carrier"],
      "auto_learning": "Learns return policy from uploaded documents. Adapts to policy changes automatically."
    }
    // ... more variants
  }
}
```

**4. `04_integrations.json`** — All supported integrations

```json
{
  "integrations": [
    {
      "name": "Shopify",
      "type": "ecommerce",
      "category": "E-commerce Platform",
      "what_connects": "Orders, products, customers, returns",
      "setup_difficulty": "Easy (5 minutes, OAuth)",
      "capabilities": ["Auto-sync orders", "Process returns in Shopify", "Update inventory on refund", "Pull product catalog for FAQ"]
    },
    {
      "name": "Zendesk",
      "type": "support",
      "category": "Help Desk",
      "what_connects": "Tickets, customers, knowledge base",
      "setup_difficulty": "Medium (API key + webhook)",
      "capabilities": ["Import existing tickets", "Sync customer data", "Read Zendesk KB articles", "Create tickets in Zendesk"]
    }
    // ... Slack, Freshdesk, Intercom, Help Scout, Custom API, Email, WhatsApp
  ]
}
```

**5. `05_capabilities.json`** — What Jarvis can and can't do

```json
{
  "core_capabilities": {
    "ticket_handling": "Automatically responds to customer support tickets 24/7",
    "knowledge_base": "Learns from uploaded documents (PDF, DOCX, TXT, CSV) — no manual training needed",
    "multi_language": "Currently supports English. More languages coming soon.",
    "response_time": "Average response time under 30 seconds for 90% of queries",
    "escalation": "Detects when human intervention is needed and escalates automatically",
    "learning": "Gets smarter with every interaction. Self-improves from corrections and feedback."
  },
  "what_jarvis_cannot_do": [
    "Cannot make phone calls to end customers (demo call is for business owners only)",
    "Cannot process payments directly (integrates with your payment system)",
    "Cannot access external systems without integration setup",
    "Cannot learn from unstructured data without KB upload",
    "Cannot replace human judgment for complex edge cases"
  ]
}
```

**6. `06_demo_scenarios.json`** — Sample conversations for demo mode

```json
{
  "scenarios": [
    {
      "id": "ecommerce_refund",
      "industry": "ecommerce",
      "title": "Processing a Return Request",
      "difficulty": "basic",
      "customer_message": "Hi, I bought a laptop last week and it's not working properly. I want to return it.",
      "expected_jarvis_behavior": "Check order → Verify eligibility → Explain return process → Generate return label → Confirm refund timeline",
      "talking_points": [
        "Automatic order lookup",
        "30-day return window check",
        "Return label generation",
        "Refund timeline communication"
      ]
    },
    {
      "id": "ecommerce_tracking",
      "industry": "ecommerce",
      "title": "Order Tracking Inquiry",
      "customer_message": "My order hasn't arrived yet. Order #67890.",
      "expected_jarvis_behavior": "Look up order → Check shipping status → Provide ETA → Offer proactive update",
      "talking_points": [
        "Real-time tracking integration",
        "Proactive status updates",
        "ETA calculation"
      ]
    },
    {
      "id": "saas_billing",
      "industry": "saas",
      "title": "Subscription Billing Question",
      "customer_message": "Why was I charged $29 this month? My plan is $19/month.",
      "expected_jarvis_behavior": "Check billing history → Identify overcharge cause → Explain charge → Offer resolution",
      "talking_points": [
        "Billing lookup",
        "Charge explanation",
        "Automatic resolution"
      ]
    }
    // ... 7+ more scenarios across industries
  ]
}
```

**7. `07_objection_handling.json`** — How Jarvis responds to common objections

```json
{
  "objections": [
    {
      "objection": "It's too expensive",
      "response_strategy": "ROI comparison",
      "jarvis_response": "I understand cost is important. Let me put it in perspective — if you're currently handling support with 3 agents at $50,000/year each, that's $150,000/year. PARWA's Growth tier at $2,499/month ($29,988/year) handles the same volume for a fraction. Plus, we work 24/7 with no sick days or training costs. Would you like me to calculate your specific savings?",
      "follow_up": "Offer ROI calculator, ask about current team size and costs"
    },
    {
      "objection": "AI can't handle complex customer issues",
      "response_strategy": "Acknowledge + demonstrate",
      "jarvis_response": "That's a fair concern. Here's how PARWA handles it: our AI resolves 80-90% of routine queries automatically — things like order status, returns, billing questions. For complex issues, it detects when human help is needed and escalates smoothly with full context. The human agent gets the conversation history and can jump right in. Want me to show you a complex scenario?"
    },
    {
      "objection": "We already use Zendesk/Intercom",
      "response_strategy": "Integration advantage",
      "jarvis_response": "Great — PARWA integrates directly with Zendesk and Intercom. We don't replace them, we enhance them. Your existing setup stays, but now routine tickets get resolved automatically by our AI before they ever reach your human team. The complex ones still flow to your agents through Zendesk. It's the best of both worlds."
    },
    {
      "objection": "What about data security?",
      "response_strategy": "Specific security features",
      "jarvis_response": "Data security is our top priority. All customer data is encrypted at rest and in transit. We're GDPR compliant, SOC 2 Type II certified. Your data never trains our models for other clients. Every company's data is completely isolated. We can provide our full security documentation if you'd like."
    },
    {
      "objection": "How long does setup take?",
      "response_strategy": "Quick setup emphasis",
      "jarvis_response": "Setup is incredibly fast. Upload your knowledge base documents, connect your support channels, and you're live — usually within the same day. No technical team needed, no complex configuration. I'm actually helping you set up right now through this chat!"
    },
    {
      "objection": "What if it gives wrong answers?",
      "response_strategy": "Safety features",
      "jarvis_response": "Great question. PARWA has multiple safeguards: first, it only answers based on your knowledge base — it won't make things up. Second, it has confidence scoring — if it's not confident in an answer, it escalates to a human. Third, you can review and approve responses before they go out. And fourth, it learns from corrections — every wrong answer makes it smarter for next time."
    },
    {
      "objection": "I need to think about it",
      "response_strategy": "Low-pressure follow-up",
      "jarvis_response": "Absolutely, no rush. In the meantime, you have 20 free messages per day to chat with me and explore. You can try our demo scenarios, ask me anything about the product, and take your time deciding. I'll be here whenever you're ready."
    }
  ]
}
```

**8. `08_faq.json`** — Top 50+ FAQs

```json
{
  "faqs": [
    { "q": "What is PARWA?", "a": "PARWA is an AI-powered customer support platform..." },
    { "q": "How does PARWA work?", "a": "You upload your knowledge base, connect your support channels..." },
    { "q": "What industries does PARWA support?", "a": "We specialize in E-commerce, SaaS, Logistics..." },
    { "q": "Can I customize Jarvis's behavior?", "a": "Yes — you can set the AI name, tone, greeting, and response style..." },
    { "q": "What happens if a customer asks something not in the KB?", "a": "If Jarvis can't find an answer, it escalates to a human agent..." },
    { "q": "How many tickets can PARWA handle?", "a": "Depends on your plan: Starter (1,000), Growth (5,000), High (20,000)..." },
    { "q": "Can I cancel anytime?", "a": "Yes, monthly billing, cancel anytime with no penalty..." },
    { "q": "Do you offer a free trial?", "a": "No free trial, but you can try our demo chat..." },
    { "q": "How is PARWA different from chatbots?", "a": "Unlike rule-based chatbots, PARWA uses AI to understand context..." },
    { "q": "What languages does PARWA support?", "a": "Currently English. More languages coming soon..." }
    // ... 40+ more
  ]
}
```

**9. `09_competitor_comparisons.json`** — Key differentiators

```json
{
  "comparisons": {
    "vs_intercom": {
      "our_advantage": "PARWA provides AI agents that fully resolve tickets, not just triage them. Intercom's AI assists agents but still requires human action for most tickets.",
      "key_differentiators": ["Full auto-resolution (not just triage)", "Industry-specific agents", "Lower cost per ticket", "No per-seat pricing"]
    },
    "vs_zendesk_ai": {
      "our_advantage": "While Zendesk AI enhances their existing platform, PARWA is built AI-first from the ground up. Every feature is designed around AI automation.",
      "key_differentiators": ["AI-native architecture", "Industry-specific variants", "Self-learning KB", "No per-agent pricing"]
    },
    "vs_freshdesk_ai": {
      "our_advantage": "PARWA offers industry-specific AI agents that understand your business domain deeply, rather than generic AI that treats all support the same.",
      "key_differentiators": ["Industry specialization", "Variant system (5 agents per industry)", "Deep KB learning", "Confidence-based escalation"]
    },
    "vs_custom_chatbots": {
      "our_advantage": "No coding, no training, no maintenance. Upload documents and go live. Custom chatbots require ongoing development and maintenance.",
      "key_differentiators": ["Zero setup time", "No development needed", "Auto-learning", "Continuous improvement"]
    }
  }
}
```

**10. `10_edge_cases.json`** — Edge cases and how Jarvis handles them

```json
{
  "edge_cases": [
    {
      "scenario": "Customer asks something not in the knowledge base",
      "handling": "Jarvis responds honestly: 'I don't have information about that in our knowledge base. Let me connect you with a human agent who can help.' Then escalates with full context."
    },
    {
      "scenario": "Customer is angry/frustrated",
      "handling": "Jarvis detects sentiment, adjusts tone to empathetic, acknowledges frustration, offers resolution, and escalates to human if anger persists."
    },
    {
      "scenario": "Customer asks about competitor products",
      "handling": "Jarvis stays focused on PARWA's value. Does NOT criticize competitors. Says: 'I can tell you more about how PARWA can help your business.'"
    },
    {
      "scenario": "Multiple questions in one message",
      "handling": "Jarvis breaks down the message, addresses each question, and responds comprehensively."
    },
    {
      "scenario": "Customer speaks in a different language",
      "handling": "Jarvis currently responds in English. Politely explains: 'I currently support English. Let me connect you with a human agent for assistance in your preferred language.'"
    },
    {
      "scenario": "Conversation goes off-topic",
      "handling": "Jarvis gently redirects: 'That's an interesting topic! I'm specifically here to help with customer support. For your business, I can help with...' — does not break character."
    }
  ]
}
```

#### Knowledge Service: `backend/app/services/jarvis_knowledge_service.py`

| Function | Purpose |
|----------|---------|
| `load_all_knowledge()` | Load all JSON files into memory (called at startup) |
| `search_knowledge(query, industry?)` | Find relevant knowledge chunks for a query |
| `get_pricing_info()` | Get current pricing data |
| `get_industry_variants(industry)` | Get variants for specific industry |
| `get_variant_details(variant_id)` | Get deep details for one variant |
| `get_demo_scenario(industry?, difficulty?)` | Get appropriate demo scenario |
| `get_objection_response(objection)` | Get response for specific objection |
| `get_faq_answer(question)` | Find closest FAQ match |
| `get_competitor_comparison(competitor)` | Get comparison points |
| `get_edge_case_handler(scenario)` | Get edge case handling protocol |
| `build_context_knowledge(context)` | Build relevant knowledge from session context |

#### Files to Create

| # | File | Lines (est.) |
|---|------|-------------|
| 28 | `backend/app/data/jarvis_knowledge/01_pricing_tiers.json` | ~80 |
| 29 | `backend/app/data/jarvis_knowledge/02_industry_variants.json` | ~300 |
| 30 | `backend/app/data/jarvis_knowledge/03_variant_details.json` | ~250 |
| 31 | `backend/app/data/jarvis_knowledge/04_integrations.json` | ~100 |
| 32 | `backend/app/data/jarvis_knowledge/05_capabilities.json` | ~80 |
| 33 | `backend/app/data/jarvis_knowledge/06_demo_scenarios.json` | ~200 |
| 34 | `backend/app/data/jarvis_knowledge/07_objection_handling.json` | ~150 |
| 35 | `backend/app/data/jarvis_knowledge/08_faq.json` | ~300 |
| 36 | `backend/app/data/jarvis_knowledge/09_competitor_comparisons.json` | ~120 |
| 37 | `backend/app/data/jarvis_knowledge/10_edge_cases.json` | ~120 |
| 38 | `backend/app/services/jarvis_knowledge_service.py` | ~300 |

#### Acceptance Criteria
- [ ] All 10 JSON files load without errors
- [ ] `search_knowledge("refund policy")` returns returns_refunds variant info
- [ ] `get_objection_response("too expensive")` returns ROI comparison response
- [ ] `get_demo_scenario("ecommerce")` returns relevant demo scenario
- [ ] `get_faq_answer("how many tickets")` returns ticket limit info
- [ ] Knowledge loaded at app startup (not per-request for performance)

---

### Phase 8: AI Intelligence — System Prompt + Stage Detection (Day 6 — Morning)

**Goal:** Wire knowledge into the AI calls. Jarvis becomes smart.

#### How Knowledge Flows Into Responses

```
User sends message
    ↓
jarvis_service.send_message()
    ↓
1. Save user message to DB
2. Check message limits
3. Detect conversation stage
4. Build system prompt:
   a. Base Jarvis persona (always)
   b. Session context (user's journey)
   c. Relevant knowledge from KB (based on query + industry)
   d. Recent conversation history (last 10 messages)
   e. Stage-specific behavior instructions
   f. Information boundary rules
5. Call AI provider (z-ai-web-dev-sdk)
6. Parse AI response
7. Determine if response includes card (bill_summary, etc.)
8. Save Jarvis message to DB
9. Track which knowledge was used
10. Return response to frontend
```

#### Dynamic System Prompt Construction

```python
def build_system_prompt(db, session_id):
    session = get_session(db, session_id)
    context = session.context_json
    stage = detect_stage(context)

    # Layer 1: Base persona
    prompt = JARVIS_BASE_PERSONA

    # Layer 2: Product knowledge (always included)
    prompt += knowledge_service.get_pricing_summary()
    prompt += knowledge_service.get_capabilities_summary()

    # Layer 3: Industry-specific knowledge
    if context.get("industry"):
        variants = knowledge_service.get_industry_variants(context["industry"])
        prompt += f"\n\nUSER'S INDUSTRY: {context['industry']}"
        prompt += f"\nAVAILABLE VARIANTS:\n{variants}"

    # Layer 4: Session context
    if context.get("selected_variants"):
        prompt += f"\n\nUSER'S SELECTED VARIANTS: {context['selected_variants']}"
    if context.get("roi_result"):
        prompt += f"\n\nUSER'S ROI: {context['roi_result']}"
    if context.get("concerns_raised"):
        prompt += f"\n\nUSER'S CONCERNS: {context['concerns_raised']}"

    # Layer 5: Relevant knowledge for this specific query
    # (searched after user sends message, injected into the AI call)
    # This happens dynamically per-message

    # Layer 6: Stage behavior
    prompt += STAGE_BEHAVIORS.get(stage, "")

    # Layer 7: Information boundary
    prompt += INFORMATION_BOUNDARY_RULES

    return prompt
```

#### Stage Detection + Behavior

| Stage | Detection Signals | Jarvis Behavior |
|--------|-------------------|-----------------|
| `WELCOME` | `total_message_count < 3`, no variants | Warm introduction, offer guidance |
| `DISCOVERY` | User asking questions, exploring | Answer with knowledge, suggest demos |
| `DEMO` | User says "show me", "demo", "try" | Roleplay as customer care agent |
| `PRICING` | User asks about cost, plans | Show pricing, compare tiers |
| `BILL_REVIEW` | Variants selected, no payment | Show bill summary, confirm |
| `VERIFICATION` | User proceeded, email not verified | Collect + verify business email |
| `PAYMENT` | Email verified, not paid | Guide to Paddle checkout |
| `HANDOFF` | Payment completed | Execute handoff |

#### Demo Mode Behavior

When in DEMO stage, the system prompt adds:

```
DEMO MODE ACTIVE:
You are demonstrating your capabilities as a Customer Care Jarvis.
The user wants to see how you'd handle real customer queries.
Roleplay as the hired agent. Use realistic details. Handle the scenario end-to-end.
If the user's industry is known, use industry-specific examples.
Reference knowledge base details for accuracy.
After the demo, transition back to guide mode and ask if they'd like to see more or proceed to pricing.
```

#### Files to Update

| # | File | Action |
|---|------|--------|
| 39 | `backend/app/services/jarvis_service.py` | **Update** — wire knowledge into `send_message()` + `build_system_prompt()` |
| 40 | `backend/app/services/jarvis_service.py` | **Update** — add `detect_stage()` + stage behaviors |
| 41 | `backend/app/main.py` | **Update** — load knowledge at startup in lifespan |

#### Acceptance Criteria
- [ ] Jarvis introduces itself on first message with product context
- [ ] User asks "how does refund handling work?" → Jarvis gives detailed answer from variant_details.json
- [ ] User says "show me" → Jarvis enters DEMO mode, roleplays as customer care agent
- [ ] User says "too expensive" → Jarvis responds with objection handling from 07_objection_handling.json
- [ ] User asks "how are you different from Zendesk?" → Jarvis gives comparison from 09_competitor_comparisons.json
- [ ] Stage detection works: pricing questions → PRICING stage, show me → DEMO stage
- [ ] Information boundary enforced: never reveals strategy/tech details

---

### Phase 9: Cross-Page Context Integration (Day 6 — Afternoon)

**Goal:** Pricing page → `/onboarding` context flows seamlessly.

#### Data Flow

```
Pricing Page                    /onboarding
─────────────                   ───────────
User selects:            →     Jarvis reads from context:
- Industry: E-commerce         context.industry = "ecommerce"
- Returns x3                   context.selected_variants = [{id: "returns", qty: 3}, ...]
- FAQ x2                       context.pages_visited = ["landing", "pricing"]
- Total: $305                  → Jarvis says: "I see you've selected Returns x3 and FAQ x2..."

ROI Calculator                 /onboarding
─────────────                   ───────────
User calculates:        →     Jarvis reads from context:
- Current cost: $120K/yr      context.roi_result = {current: 120000, parwa: 29988, savings: 90012}
- PARWA cost: $29,988/yr       → Jarvis says: "Based on your ROI calculation, you'd save $90K/year..."
- Savings: $90,012/yr
```

#### Implementation

**Pricing page sends context:**
```typescript
// When user clicks "Proceed with Jarvis" on pricing page
const handleProceedToJarvis = () => {
  localStorage.setItem('parwa_jarvis_context', JSON.stringify({
    industry: selectedIndustry,
    selected_variants: selectedVariants,
    total_price: totalPrice,
    source: 'pricing_page'
  }));
  router.push('/onboarding');
};
```

**Jarvis reads context on init:**
```typescript
// In useJarvisChat.ts → initSession()
const storedContext = localStorage.getItem('parwa_jarvis_context');
if (storedContext) {
  await updateContext(JSON.parse(storedContext));
  localStorage.removeItem('parwa_jarvis_context'); // one-time transfer
}
```

**Also track page visits:**
```typescript
// In layout or page components
useEffect(() => {
  // Track which pages user visited
  const visited = JSON.parse(localStorage.getItem('parwa_pages_visited') || '[]');
  if (!visited.includes(pathname)) {
    visited.push(pathname);
    localStorage.setItem('parwa_pages_visited', JSON.stringify(visited));
  }
}, [pathname]);
```

#### Files to Create / Update

| # | File | Action |
|---|------|--------|
| 42 | `src/hooks/useJarvisChat.ts` | **Update** — read pricing context on init |
| 43 | `src/components/pricing/TotalSummary.tsx` | **Update** — add "Proceed with Jarvis →" button |
| 44 | `src/components/layout/NavigationBar.tsx` | **Update** — "Jarvis Chatbot" → `/onboarding` |
| 45 | `src/components/landing/HeroSection.tsx` | **Update** — "Get Started with Jarvis" → `/onboarding` |

#### Acceptance Criteria
- [ ] User selects variants on pricing → "Proceed with Jarvis" → `/onboarding`
- [ ] Jarvis first message references selected variants
- [ ] ROI results appear in Jarvis's context
- [ ] "Jarvis Chatbot" nav link → `/onboarding`
- [ ] "Get Started with Jarvis" hero CTA → `/onboarding`

---

### Phase 10: Payment Integration (Day 7 — Morning)

**Goal:** Paddle checkout for demo pack AND variant subscription.

#### Two Payment Flows

| Flow | Trigger | Amount | Where |
|------|---------|--------|-------|
| **Demo Pack** | Limit reached OR user requests | $1 | Inside chat (PaymentCard) |
| **Variant Subscription** | After bill review + OTP verified | Variable | Inside chat (PaymentCard → Paddle) |

#### Demo Pack Flow

```
User hits 20 msg limit
    → Jarvis says: "You've used your 20 free messages for today..."
    → LimitReachedCard appears
    → User clicks "Upgrade to Demo Pack"
    → PaymentCard shows: "$1 — 500 messages + 3 min AI call for 24 hours"
    → User clicks "Pay $1"
    → Paddle overlay opens
    → Payment completes → webhook fires
    → Backend: session.pack_type = "demo", pack_expiry = now + 24h, message_count_today = 0
    → Jarvis: "Welcome back! You now have 500 messages..."
```

#### Variant Subscription Flow

```
User confirms bill summary
    → OtpVerificationCard appears
    → User enters business email, verifies OTP
    → PaymentCard shows variant total
    → User clicks "Pay with Paddle"
    → Paddle checkout opens (full subscription, not $1)
    → Payment completes → webhook fires
    → Backend: session.payment_status = "completed"
    → HandoffCard appears
```

#### Files to Create / Update

| # | File | Action |
|---|------|--------|
| 46 | `backend/app/services/paddle_service.py` | **Update** — add demo pack checkout + variant subscription |
| 47 | `backend/app/api/jarvis.py` | **Update** — wire payment endpoints |
| 48 | `src/components/jarvis/PaymentCard.tsx` | **Update** — integrate Paddle.js |

#### Acceptance Criteria
- [ ] Demo pack: $1 → session updated → 500 messages → 24h expiry
- [ ] Demo pack expiry: after 24h → PackExpiredCard → back to free tier
- [ ] Variant payment: correct total → Paddle → webhook → session updated
- [ ] Payment failure: error in chat, retry option
- [ ] Webhook idempotent (duplicate events handled)

---

### Phase 11: Handoff + Dashboard + Navigation (Day 7 — Afternoon)

**Goal:** Complete the onboarding → post-onboarding transition.

#### Handoff Execution

```python
def execute_handoff(db, onboarding_session_id):
    # 1. Get onboarding session
    onboarding = get_session(db, onboarding_session_id)

    # 2. Mark as completed
    onboarding.handoff_completed = True
    onboarding.is_active = False

    # 3. Create NEW customer care session (fresh)
    care_session = JarvisSession(
        user_id=onboarding.user_id,
        company_id=onboarding.company_id,
        type="customer_care",
        context_json={
            "hired_variants": onboarding.context_json.get("selected_variants", []),
            "industry": onboarding.context_json.get("industry"),
            "business_email": onboarding.context_json.get("business_email"),
            # NO chat history, NO pages visited, NO ROI, NO concerns
        },
        is_active=True
    )
    db.add(care_session)

    # 4. Update user record
    onboarding.user.onboarding_completed = True
```

#### Dashboard UI (Complete New Interface)

```
+------------------------------------------------------------------+
|  [PARWA Logo]    Dashboard    Tickets    KB    Settings    [User] |
+------------------------------------------------------------------+
|                                                                   |
|  ┌-- Welcome Card ------┐  ┌-- Active Agents ------------──┐     |
|  | Welcome back, John!   |  | Returns Agent    x3  Active  |     |
|  | Your Jarvis is live.  |  | FAQ Agent       x2  Active  |     |
|  | 3 variants hired     |  | Shipping Agent   x1  Active  |     |
|  +----------------------+  +-----------------------------+     |
|                                                                   |
|  ┌-- Knowledge Base ----┐  ┌-- Integrations ---------------┐     |
|  | 12 documents          |  | Shopify    Connected          |     |
|  | 94% coverage          |  | Zendesk    Connected          |     |
|  | [Upload Documents]    |  | [Connect More]               |     |
|  +----------------------+  +-----------------------------+     |
|                                                                   |
|  ┌-- Recent Tickets -----------------------------------------+  |
|  | #1042  Refund request   Sarah Johnson  Resolved   12s    |  |
|  | #1041  Order status     Mike Chen      In Progress       |  |
|  | #1040  Product question Amy Wilson     New               |  |
|  +----------------------------------------------------------+  |
+------------------------------------------------------------------+
```

#### Navigation Bar States

**Before Login:**
```
[PARWA Logo]    Home    Models    ROI    Jarvis    [Login]
```

**After Login (Pre-Payment):**
```
[PARWA Logo]    Home    Models    ROI    Jarvis*    [User Menu]
```

**After Payment (Post-Onboarding):**
```
[PARWA Logo]    Dashboard    Tickets    KB    Settings    [User Menu]
```

#### Files to Create / Update

| # | File | Action |
|---|------|--------|
| 49 | `src/app/dashboard/page.tsx` | **Create** — dashboard route with auth guard |
| 50 | `src/components/dashboard/DashboardLayout.tsx` | **Create** — dashboard layout shell |
| 51 | `src/components/dashboard/WelcomeCard.tsx` | **Create** — welcome + variant summary |
| 52 | `src/components/dashboard/ActiveAgentsCard.tsx` | **Create** — hired agents list |
| 53 | `src/components/dashboard/RecentTicketsCard.tsx` | **Create** — latest tickets |
| 54 | `src/components/dashboard/KnowledgeBaseCard.tsx` | **Create** — KB status + upload |
| 55 | `src/components/dashboard/IntegrationsCard.tsx` | **Create** — connected integrations |
| 56 | `src/components/dashboard/index.ts` | **Create** — barrel exports |
| 57 | `src/components/layout/NavigationBar.tsx` | **Update** — auth-aware nav rendering |
| 58 | `src/hooks/useAuth.ts` | **Update** — add `onboardingCompleted` check |

#### Acceptance Criteria
- [ ] Handoff creates new `customer_care` session in DB
- [ ] Onboarding chat history NOT in customer care session
- [ ] HandoffCard shows celebration in chat
- [ ] Clicking "Meet Your Jarvis" → `/dashboard`
- [ ] `/dashboard` shows completely different UI
- [ ] Nav changes after payment (Jarvis → Dashboard)
- [ ] `/dashboard` redirects to `/` if not paid
- [ ] `/onboarding` redirects to `/dashboard` if already onboarded

---

### Phase 12: Session Persistence + Error Handling (Day 8 — Morning)

**Goal:** Sessions survive browser closes. Errors are handled gracefully.

#### Session Persistence

| Scenario | Behavior |
|----------|---------|
| User closes browser, opens `/onboarding` | `initSession()` finds active session → loads history → user sees previous chat |
| User opens on two devices | Both see the same session (messages sync via API) |
| Session inactive for 30+ days | Auto-archived (marked inactive) |
| Payment page refresh during Paddle | Session preserved, payment status checked |

#### Error Handling

| Error | User Sees | What Happens |
|-------|-----------|-------------|
| AI provider down | "I'm having trouble connecting right now. Please try again in a moment." + retry button | Error logged, no data lost |
| Message limit reached | LimitReachedCard with options | User can wait or upgrade |
| Demo pack expired | PackExpiredCard with options | User can repurchase or use free tier |
| Paddle payment fails | "Payment didn't go through. Want to try again?" | Retry option preserved |
| OTP expired | "Your verification code expired. Let me send a new one." | New OTP generated |
| Network error | "Connection lost. Reconnecting..." | Auto-retry on reconnect |
| Invalid input | Jarvis handles gracefully in conversation | No error card needed |

#### Files to Update

| # | File | Action |
|---|------|--------|
| 59 | `src/hooks/useJarvisChat.ts` | **Update** — add session persistence, auto-retry, error recovery |
| 60 | `backend/app/services/jarvis_service.py` | **Update** — add session cleanup, error handling |

#### Acceptance Criteria
- [ ] Close browser → reopen `/onboarding` → previous chat loads
- [ ] AI provider error → friendly message + retry button works
- [ ] Network disconnect → "Reconnecting..." → auto-reconnects
- [ ] Session inactive 30 days → archived, new session created on return

---

### Phase 13: Mobile Responsive + Polish (Day 8 — Afternoon)

**Goal:** Everything works beautifully on all screen sizes.

#### Responsive Design

| Breakpoint | Chat Width | Input | Cards |
|-----------|-----------|-------|-------|
| Desktop (1024px+) | 720px centered | Full-width bar at bottom | Inline in chat |
| Tablet (768-1023px) | Full width, 16px padding | Full-width bar | Inline in chat |
| Mobile (< 768px) | Full screen, no padding | Fixed above keyboard | Full-width stack |

#### Animations

| Element | Animation | Duration |
|---------|-----------|----------|
| New message | Slide up + fade in | 300ms |
| Typing indicator | Three bouncing dots | Continuous |
| Card appear | Expand + fade in | 400ms |
| Send button pulse | Scale on click | 150ms |
| Counter color change | Green → amber → red | 500ms |
| Handoff celebration | Confetti/particles | 2s |
| Error shake | Horizontal shake | 400ms |

#### Files to Update

| # | File | Action |
|---|------|--------|
| 61 | `src/app/onboarding/page.tsx` | **Update** — mobile layout |
| 62 | `src/components/jarvis/JarvisChat.tsx` | **Update** — responsive container |
| 63 | `src/components/jarvis/ChatMessage.tsx` | **Update** — mount animations |
| 64 | `src/components/jarvis/ChatInput.tsx` | **Update** — mobile bottom-fixed |
| 65 | `src/components/jarvis/BillSummaryCard.tsx` | **Update** — mobile responsive |
| 66 | `src/app/dashboard/page.tsx` | **Update** — mobile grid layout |

#### Acceptance Criteria
- [ ] Chat works on 375px (iPhone SE) to 1920px (desktop)
- [ ] Input visible above keyboard on mobile
- [ ] Cards readable on mobile (no horizontal scroll)
- [ ] All animations smooth, no jank
- [ ] Dashboard responsive (single column on mobile)

---

### Phase 14: Tests + Mirror + Push (Day 8 — Evening)

**Goal:** Quality assurance + sync + deploy.

#### Test Files

| # | File | Tests |
|---|------|-------|
| 67 | `tests/unit/test_jarvis_service.py` | Session management, limits, handoff, demo pack, OTP, stage detection |
| 68 | `tests/unit/test_jarvis_api.py` | All 16 API endpoints: success + auth + validation + edge cases |
| 69 | `tests/unit/test_jarvis_knowledge_service.py` | Knowledge loading, search, all 10 knowledge files |
| 70 | `tests/unit/test_jarvis_models.py` | Model creation, relationships, constraints, cascade deletes |

#### Mirror Sync

| # | Source | Destination |
|---|--------|-------------|
| 71 | `src/app/onboarding/` | `frontend/src/app/onboarding/` |
| 72 | `src/components/jarvis/` | `frontend/src/components/jarvis/` |
| 73 | `src/components/dashboard/` | `frontend/src/components/dashboard/` |
| 74 | `src/app/dashboard/` | `frontend/src/app/dashboard/` |
| 75 | `src/hooks/useJarvisChat.ts` | `frontend/src/hooks/useJarvisChat.ts` |
| 76 | `src/types/jarvis.ts` | `frontend/src/types/jarvis.ts` |

#### Acceptance Criteria
- [ ] All tests pass: `pytest tests/unit/test_jarvis* -v`
- [ ] No regression: `pytest tests/unit/ -v` all green
- [ ] Mirror sync: `diff -r src/ frontend/src/` no relevant differences
- [ ] `git push` succeeds

---

## Complete File Summary

### All Files to Create (60 new files)

| # | File | Phase | Category |
|---|------|-------|----------|
| 1 | `database/alembic/versions/012_jarvis_system.py` | 1 | Database |
| 2 | `database/models/jarvis.py` | 1 | Database |
| 3 | `backend/app/schemas/jarvis.py` | 2 | Backend |
| 4 | `backend/app/services/jarvis_service.py` | 2 | Backend |
| 5 | `backend/app/api/jarvis.py` | 3 | Backend |
| 6 | `backend/app/services/jarvis_knowledge_service.py` | 7 | Backend |
| 7-16 | `backend/app/data/jarvis_knowledge/*.json` (10 files) | 7 | Knowledge |
| 17 | `src/types/jarvis.ts` | 4 | Frontend |
| 18 | `src/hooks/useJarvisChat.ts` | 4 | Frontend |
| 19 | `src/app/onboarding/page.tsx` | 5 | Frontend |
| 20-27 | `src/components/jarvis/*.tsx` (9 core components) | 5-6 | Frontend |
| 28-36 | `src/components/jarvis/*.tsx` (9 card components) | 6 | Frontend |
| 37 | `src/app/dashboard/page.tsx` | 11 | Frontend |
| 38-43 | `src/components/dashboard/*.tsx` (6 components) | 11 | Frontend |
| 44-46 | `tests/unit/test_jarvis*.py` (3 test files) | 14 | Tests |

### All Files to Update (16 existing files)

| # | File | Phase | What Changes |
|---|------|-------|-------------|
| 47 | `database/models/__init__.py` | 1 | Export new models |
| 48 | `backend/app/main.py` | 3,8 | Register router, load knowledge at startup |
| 49 | `backend/app/api/__init__.py` | 3 | Import jarvis router |
| 50 | `backend/app/services/jarvis_service.py` | 8,12 | Wire knowledge, add persistence |
| 51 | `backend/app/services/paddle_service.py` | 10 | Add demo pack + variant checkout |
| 52 | `src/hooks/useJarvisChat.ts` | 9,12 | Read pricing context, add persistence |
| 53 | `src/components/pricing/TotalSummary.tsx` | 9 | "Proceed with Jarvis" button |
| 54 | `src/components/layout/NavigationBar.tsx` | 9,11 | Link to /onboarding, auth-aware nav |
| 55 | `src/components/landing/HeroSection.tsx` | 9 | CTA → /onboarding |
| 56-61 | `src/components/jarvis/*.tsx` (6 files) | 13 | Mobile responsive updates |
| 62 | `src/app/dashboard/page.tsx` | 13 | Mobile layout |

### Mirror Copies (6 directories)

| Source | Destination |
|--------|-------------|
| `src/app/onboarding/` | `frontend/src/app/onboarding/` |
| `src/components/jarvis/` | `frontend/src/components/jarvis/` |
| `src/components/dashboard/` | `frontend/src/components/dashboard/` |
| `src/app/dashboard/` | `frontend/src/app/dashboard/` |
| `src/hooks/useJarvisChat.ts` | `frontend/src/hooks/useJarvisChat.ts` |
| `src/types/jarvis.ts` | `frontend/src/types/jarvis.ts` |

---

## Phase 15: Provider Abstraction Layer (Day 9 — Morning)

**Goal:** Create the provider protocol/interface system that allows ANY provider to be plugged in for email, SMS, and payments.

### Provider Protocols

Create abstract base classes in `backend/app/core/providers/`:

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/app/core/providers/__init__.py` | Package exports |
| 2 | `backend/app/core/providers/base.py` | Base protocol classes: `EmailProvider`, `SMSProvider`, `PaymentProvider` |
| 3 | `backend/app/core/providers/email_brevo.py` | Brevo adapter (migrate from `email_service.py`) |
| 4 | `backend/app/core/providers/email_sendgrid.py` | SendGrid adapter |
| 5 | `backend/app/core/providers/email_ses.py` | AWS SES adapter |
| 6 | `backend/app/core/providers/sms_twilio.py` | Twilio adapter (migrate from `sms_channel_service.py`) |
| 7 | `backend/app/core/providers/sms_vonage.py` | Vonage adapter |
| 8 | `backend/app/core/providers/payment_paddle.py` | Paddle adapter (migrate from `paddle_service.py`) |
| 9 | `backend/app/core/providers/payment_stripe.py` | Stripe adapter |
| 10 | `backend/app/core/providers/registry.py` | Provider registry + factory |
| 11 | `backend/app/core/providers/api_key_detector.py` | API key auto-detection system |

### Provider Registry Pattern

```python
# registry.py
class ProviderRegistry:
    _email_providers = {}  # name -> class
    _sms_providers = {}
    _payment_providers = {}
    
    @classmethod
    def register_email(cls, name, provider_class):
        cls._email_providers[name] = provider_class
    
    @classmethod
    def get_email_provider(cls, company_id) -> EmailProvider:
        config = get_service_config(company_id, 'email')
        provider_class = cls._email_providers[config.provider_name]
        return provider_class(config.api_key, config.settings)
```

### API Key Detector

```python
# api_key_detector.py
class ApiKeyDetector:
    PATTERNS = {
        'sendgrid': {'prefix': 'SG.', 'type': 'email', 'confidence': 0.95},
        'stripe': {'prefix': 'sk_live_', 'type': 'payment', 'confidence': 0.95},
        'aws': {'prefix': 'AKIA', 'type': 'email/sms', 'confidence': 0.90},
        'razorpay': {'prefix': 'rzp_live_', 'type': 'payment', 'confidence': 0.95},
        'paddle': {'prefix': 'pdl_', 'type': 'payment', 'confidence': 0.90},
        'brevo': {'prefix': 'xkeysib-', 'type': 'email', 'confidence': 0.95},
        'mailgun': {'prefix': 'key-', 'type': 'email', 'confidence': 0.80},
        'twilio': {'prefix': 'AC', 'length': 34, 'type': 'sms', 'confidence': 0.85},
        # ... more patterns
    }
    
    @classmethod
    def detect(cls, key: str) -> ProviderDetectionResult:
        # Check prefixes first (high confidence)
        # Then check length + char set (medium confidence)
        # Return: provider_name, provider_type, confidence, detected_by
```

### Acceptance Criteria
- [ ] All provider protocols define the same interface methods
- [ ] Brevo adapter successfully sends email using the new interface
- [ ] Paddle adapter successfully creates checkout using the new interface
- [ ] Twilio adapter successfully sends SMS using the new interface
- [ ] ProviderFactory returns correct provider based on ServiceConfig
- [ ] API key detector correctly identifies 5+ providers with >80% accuracy
- [ ] Unknown key returns "unknown" with 0% confidence

---

## Phase 16: Database Migration — Provider-Agnostic Columns (Day 9 — Afternoon)

**Goal:** Rename all provider-specific database columns to generic names and wire ServiceConfig table.

### Migration: `014_provider_agnostic_columns.py`

| Old Column | New Column | Table |
|-----------|-----------|-------|
| `brevo_message_id` | `provider_message_id` | `outbound_emails` |
| `brevo_message_id` | `provider_message_id` | `email_delivery_events` |
| `brevo_event_id` | `provider_event_id` | `email_delivery_events` |
| `twilio_message_sid` | `provider_message_id` | `sms_messages` |
| `twilio_account_sid` | `provider_account_id` | `sms_messages` |
| `twilio_status` | `provider_status` | `sms_messages` |
| `twilio_error_code` | `provider_error_code` | `sms_messages` |
| `twilio_error_message` | `provider_error_message` | `sms_messages` |
| `twilio_account_sid` | `provider_account_id` | `sms_channel_configs` |
| `twilio_auth_token_encrypted` | `provider_auth_token_encrypted` | `sms_channel_configs` |
| `twilio_phone_number` | `provider_phone_number` | `sms_channel_configs` |
| `twilio_number` | `provider_number` | `sms_conversations` |
| `paddle_customer_id` | `provider_customer_id` | `companies` |
| `paddle_subscription_id` | `provider_subscription_id` | `companies`, `subscriptions` |
| `paddle_invoice_id` | `provider_invoice_id` | `invoices` |
| `paddle_charge_id` | `provider_charge_id` | `overage_charges` |
| `paddle_transaction_id` | `provider_transaction_id` | `transactions` |
| `paddle_payment_method_id` | `provider_payment_method_id` | `payment_methods` |
| `paddle_event_id` | `provider_event_id` | `webhook_sequences` |

### New Columns to Add

| Table | Column | Type | Purpose |
|-------|--------|------|---------|
| `sms_channel_configs` | `provider_type` | VARCHAR(30) | Which SMS provider is configured |
| `companies` | `email_provider` | VARCHAR(30) | Which email provider is configured |
| `companies` | `payment_provider` | VARCHAR(30) | Which payment provider is configured |
| `outbound_emails` | `provider_type` | VARCHAR(30) | Which email provider sent this |
| `sms_messages` | `provider_type` | VARCHAR(30) | Which SMS provider sent this |
| `sms_channel_configs` | `twilio_status` CHECK constraint | - | Remove Twilio-specific CHECK, use generic |

### Files to Create

| # | File | Lines |
|---|------|-------|
| 1 | `database/alembic/versions/014_provider_agnostic_columns.py` | ~200 |
| 2 | Update all model files with new column names | ~50 edits across 8 files |

### Acceptance Criteria
- [ ] Migration runs without errors on existing data
- [ ] All unique constraints updated with new column names
- [ ] All CHECK constraints updated
- [ ] Backward compatibility: old data migrated correctly
- [ ] ServiceConfig table has entries for all existing providers

---

## Phase 17: Jarvis Integration Setup Flow (Day 10)

**Goal:** Add integration setup conversation stages to Jarvis after HANDOFF.

### New Conversation Stages

| Stage | Trigger | Exit Condition |
|-------|---------|---------------|
| `integration_email` | After handoff | Provider connected OR skipped |
| `integration_sms` | After email stage | Provider connected OR skipped |
| `integration_payment` | After SMS stage | Provider connected OR skipped |
| `integration_third_party` | After payment stage | At least 1 connected OR all skipped |
| `first_victory` | After all integration stages | KB uploaded + AI activated OR skipped |

### New Rich Card Components

| # | Component | Message Type |
|---|-----------|-------------|
| 1 | `ProviderSelectorCard.tsx` | `provider_selector` |
| 2 | `ApiKeyInputCard.tsx` | `api_key_input` |
| 3 | `ConnectionStatusCard.tsx` | `connection_status` |
| 4 | `ConnectionErrorCard.tsx` | `connection_error` |
| 5 | `IntegrationSummaryCard.tsx` | `integration_summary` |
| 6 | `IndustrySuggestionCard.tsx` | `industry_suggestion` |

### New API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/jarvis/integrations/providers/:category` | List providers by category |
| `POST` | `/api/jarvis/integrations/detect-key` | Auto-detect API key provider |
| `POST` | `/api/jarvis/integrations/connect` | Connect provider with credentials |
| `POST` | `/api/jarvis/integrations/test` | Test provider connection |
| `GET` | `/api/jarvis/integrations/status` | Get all integration statuses |
| `DELETE` | `/api/jarvis/integrations/:id` | Disconnect a provider |

### Knowledge Base Addition: `11_integration_providers.json`

```json
{
  "provider_categories": {
    "email": {
      "providers": [
        {"name": "Brevo", "setup_difficulty": "Easy", "key_location": "Settings → API Keys", "popular_industries": ["others", "logistics"]},
        {"name": "SendGrid", "setup_difficulty": "Easy", "key_location": "Settings → API Keys → Create", "popular_industries": ["ecommerce", "saas"]},
        {"name": "AWS SES", "setup_difficulty": "Medium", "key_location": "IAM → Access Keys", "popular_industries": ["saas", "logistics"]},
        {"name": "Mailgun", "setup_difficulty": "Easy", "key_location": "Settings → API Keys", "popular_industries": ["ecommerce"]},
        {"name": "Postmark", "setup_difficulty": "Easy", "key_location": "Settings → API Tokens", "popular_industries": ["saas"]}
      ],
      "jarvis_prompts": {
        "ask": "Which email provider do you use for customer emails?",
        "help": "Your email provider is where you send emails FROM. This could be Brevo, SendGrid, AWS SES, or any SMTP server.",
        "popular": "Most {industry} businesses use {provider}."
      }
    },
    "sms": { /* Similar structure */ },
    "payment": { /* Similar structure */ },
    "third_party": {
      "providers": [
        {"name": "Shopify", "category": "ecommerce", "setup_difficulty": "Easy", "auth_type": "OAuth"},
        {"name": "Zendesk", "category": "helpdesk", "setup_difficulty": "Medium", "auth_type": "API Key"},
        {"name": "HubSpot", "category": "crm", "setup_difficulty": "Easy", "auth_type": "OAuth"},
        {"name": "Slack", "category": "communication", "setup_difficulty": "Easy", "auth_type": "OAuth"}
      ]
    }
  }
}
```

### Service Layer Updates

Update `jarvis_service.py` with new functions:

| Function | Purpose |
|----------|---------|
| `detect_api_key(key)` | Auto-detect provider from key pattern |
| `connect_provider(company_id, provider_type, provider_name, credentials)` | Connect a provider |
| `test_provider_connection(company_id, integration_id)` | Test connection |
| `get_integration_status(company_id)` | Get all integration statuses |
| `get_provider_suggestions(industry)` | Suggest popular providers for industry |

### Acceptance Criteria
- [ ] Jarvis shows provider selector cards after handoff
- [ ] API key auto-detection works for 5+ providers
- [ ] Connection test shows real-time success/failure
- [ ] Error cards show helpful troubleshooting steps
- [ ] All stages are skippable without blocking onboarding
- [ ] Integration summary card shows connected + skipped + remaining
- [ ] Industry-specific suggestions appear based on client's industry

---

## Phase 18: Dashboard Integration Management UI (Day 11)

**Goal:** Full integration management page for post-onboarding provider management.

### New Page: `/dashboard/integrations`

| Section | What It Shows |
|---------|--------------|
| **Overview Cards** | Connected providers count, health status, usage metrics |
| **Email Providers** | Connected email provider with test/disconnect actions |
| **SMS Providers** | Connected SMS provider with test/disconnect actions |
| **Payment Providers** | Connected payment provider with test/disconnect actions |
| **Third-Party** | CRM, e-commerce, helpdesk, communication integrations |
| **Custom API** | REST connectors, webhook subscriptions |
| **Add New** | Provider selector → API key input → test → connect |

### Files to Create

| # | File | Purpose |
|---|------|---------|
| 1 | `src/app/dashboard/integrations/page.tsx` | Integration management page |
| 2 | `src/components/integrations/ProviderCard.tsx` | Individual provider display |
| 3 | `src/components/integrations/ProviderList.tsx` | List of providers by category |
| 4 | `src/components/integrations/ConnectProviderModal.tsx` | Connect new provider flow |
| 5 | `src/components/integrations/TestConnectionButton.tsx` | Live test with status |
| 6 | `src/components/integrations/ConnectionHealthBadge.tsx` | Green/Yellow/Red health indicator |
| 7 | `src/components/integrations/WebhookLogs.tsx` | Recent webhook activity |
| 8 | `src/hooks/useIntegrations.ts` | Integration state management hook |

### Acceptance Criteria
- [ ] `/dashboard/integrations` shows all connected providers
- [ ] Each provider has test/disconnect/change key actions
- [ ] Add new provider flow works end-to-end
- [ ] Health badges reflect real connection status
- [ ] Mobile responsive layout

---

## Phase 19: Webhook Unification + Universal API (Day 12)

**Goal:** Generic webhook receiver for ANY provider + universal REST connector.

### Generic Webhook Handler

Replace provider-specific webhook endpoints with a unified system:

```python
# POST /api/webhooks/{provider_name}
# Automatically routes to correct parser based on provider_name
# Verifies signature using provider-specific method
# Stores in universal WebhookEvent table
```

### Files to Create

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/app/core/providers/webhook_parser.py` | Generic webhook parser registry |
| 2 | `backend/app/core/providers/webhook_verifier.py` | Per-provider webhook verification |
| 3 | `backend/app/services/webhook_unified_service.py` | Unified webhook processing |
| 4 | `src/components/integrations/CustomApiBuilder.tsx` | Custom API config UI |
| 5 | `src/components/integrations/WebhookConfigurator.tsx` | Webhook setup UI |

### Acceptance Criteria
- [ ] Webhooks from any registered provider route correctly
- [ ] Signature verification works per-provider
- [ ] Custom REST API connections can be created via UI
- [ ] Custom webhook subscriptions can receive any format
- [ ] Error handling with retry for failed webhooks

---

## Updated File Count

| Phase | New Files | Updated Files | Total |
|-------|----------|--------------|-------|
| Phase 15 | 11 | 0 | 11 |
| Phase 16 | 1 | 8 | 9 |
| Phase 17 | 8 | 2 | 10 |
| Phase 18 | 8 | 1 | 9 |
| Phase 19 | 5 | 2 | 7 |
| **Phase 1-14 (existing)** | 60 | 5 | 65 |
| **TOTAL (all phases)** | **93** | **18** | **111** |

---

## Timeline

| Day | Phase(s) | Key Deliverable |
|-----|----------|----------------|
| **Day 1** | 1-2 | Database + Models + Schemas + Service Layer |
| **Day 2** | 3-4 | API Endpoints + TypeScript Types + Hook |
| **Day 3** | 5 | Core Chat UI (messages, input, typing) |
| **Day 4** | 6 | Rich In-Chat Cards (9 card components) |
| **Day 5** | 7 | **Knowledge Base** (10 JSON files + knowledge service) |
| **Day 6** | 8-9 | AI Intelligence + Cross-Page Context |
| **Day 7** | 10-11 | Payment + Handoff + Dashboard + Navigation |
| **Day 8** | 12-14 | Persistence + Errors + Mobile + Tests + Mirror + Push |
| **Day 9** | 15-16 | Provider Abstraction Layer + DB Migration |
| **Day 10** | 17 | Jarvis Integration Setup Flow |
| **Day 11** | 18 | Dashboard Integration Management UI |
| **Day 12** | 19 | Webhook Unification + Universal API |

**Total: 111 files (93 new + 18 updated) across 19 phases over 12 days.**

---

## Dependency Graph

```
Phase 1 (DB) ─────┐
                    ├──> Phase 2 (Service) ──> Phase 3 (API)
Phase 4 (Types) ───┘                          │
                                               v
                                        Phase 5 (Core UI)
                                               │
                                               v
                                        Phase 6 (Rich Cards)
                                               │
                                               v
                                 Phase 7 (Knowledge Base)
                                               │
                                               v
                                 Phase 8 (AI Intelligence)
                                               │
                                               v
                                 Phase 9 (Cross-Page Context)
                                               │
                                               v
                                 Phase 10 (Payment)
                                               │
                                               v
                          Phase 11 (Handoff + Dashboard + Nav)
                                               │
                                               v
                          Phase 12 (Persistence + Errors)
                                               │
                                               v
                          Phase 13 (Mobile + Polish)
                                               │
                                               v
                          Phase 14 (Tests + Mirror + Push)
                                               │
                                               v
                    Phase 15 (Provider Abstraction Layer)
                                               │
                                               v
               Phase 16 (Provider-Agnostic DB Migration)
                                               │
                                               v
             Phase 17 (Jarvis Integration Setup Flow)
                                               │
                                               v
        Phase 18 (Dashboard Integration Management)
                                               │
                                               v
        Phase 19 (Webhook Unification + Universal API)
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Week 6 Day 8 | Initial 7-day plan (42 files, 14 phases) |
| 2.0 | Week 6 Day 8 | **Complete** — added Knowledge Base (Phase 7), Session Persistence (Phase 12), Error Handling, expanded to 76 files / 14 phases / 8 days |
| 3.0 | Week 6 Day 9 | Added: Action Ticket System, Post-Call Summary, Non-Linear Entry Routing, Jarvis-as-Product-Demo |
| 4.0 | Week 6 Day 10 | Added: `jarvis_action_tickets` DB table, knowledge service functions, aligned with Spec v3.0, fixed phase count |
| 5.0 | Week X | Added: Phase 15-19 Provider-Agnostic Integration Architecture, API Key Auto-Detection, Jarvis Integration Setup Flow, Dashboard Integration Management, Webhook Unification |

---

*This is the complete execution plan for JARVIS_SPECIFICATION.md v3.0 + Provider-Agnostic Integration Architecture. Nothing is left out. Follow phases in order.*
