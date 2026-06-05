# PARWA Connection Map — Part 1: Core Systems

> **AI-Powered Customer Support Platform — Feature Interconnection Reference**
>
> This document maps how features in the CORE systems of PARWA connect, communicate,
> and depend on each other. A developer reading this should know exactly which
> features break if they change any given feature.
>
> **Scope:** F-010 through F-086 + shared infrastructure tables
> **Version:** 1.0 | **Last Updated:** March 2026
> **Companion Docs:** Building Codes v1.0, Feature Catalog v1.0

---

## Table of Contents

1. [Feature Dependency Matrix (Core)](#section-1-feature-dependency-matrix-core)
2. [Ticket Lifecycle Flow (Critical Path)](#section-2-ticket-lifecycle-flow-critical-path)
3. [AI Pipeline Internal Connections](#section-3-ai-pipeline-internal-connections)
4. [Approval System Connection Web](#section-4-approval-system-connection-web)
5. [Shared Database Tables Map](#section-5-shared-database-tables-map)
6. [Circular Dependency & Conflict Analysis](#section-6-circular-dependency--conflict-analysis)

---

# Section 1: Feature Dependency Matrix (Core)

## 1.1 Authentication & Security (F-010 to F-019)

### 1.1.1 Visual Dependency Tree

```
F-010 User Registration  ◄═══ ROOT (no upstream deps)
  ├── F-011 Google OAuth
  ├── F-012 Email Verification
  │     └── [uses] F-006 Brevo (email_logs table)
  ├── F-013 Login System
  │     ├── F-014 Forgot Password / Reset Password
  │     │     └── [uses] F-006 Brevo (email_logs table)
  │     ├── F-015 MFA Setup (Authenticator App)
  │     │     └── F-016 Backup Codes Generation
  │     ├── F-017 Session Management (Active Sessions, Revoke)
  │     │     └── F-019 API Key Management
  │     └── F-018 Rate Limiting (Advanced, Per-User)
  └── F-014 Forgot Password  (also depends on F-013)
```

### 1.1.2 Dependency Table — Authentication & Security

| Feature | Depends On | Depended By | Shared Tables | Breaking Change Impact |
|---------|-----------|-------------|---------------|----------------------|
| **F-010** User Registration | — | F-011, F-012, F-013, F-014, F-015 | `users`, `companies` | **CRITICAL** — Every auth feature breaks. Root node. |
| **F-011** Google OAuth | F-010 | — | `users`, `oauth_accounts` | Low — Isolated OAuth flow |
| **F-012** Email Verification | F-010 | F-013 | `users`, `email_logs`, `verification_tokens` | **HIGH** — Login gated until verified |
| **F-013** Login System | F-010, F-012 | F-014, F-015, F-017, F-018, F-019, F-028, F-036 | `users`, `sessions` | **CRITICAL** — 10+ downstream features |
| **F-014** Forgot Password | F-013 | — | `users`, `password_reset_tokens`, `email_logs` | Medium — Self-contained recovery |
| **F-015** MFA Setup | F-013 | F-016 | `users`, `mfa_secrets` | Medium — Only F-016 breaks |
| **F-016** Backup Codes | F-015 | — | `users`, `backup_codes` | Low — Leaf node |
| **F-017** Session Management | F-013 | F-019 | `users`, `sessions`, `api_keys` | **HIGH** — API keys depend on sessions |
| **F-018** Rate Limiting | F-013 | — | `rate_limit_counters` (Redis) | Medium — Non-blocking if removed |
| **F-019** API Key Management | F-017 | F-031, F-099 (integrations) | `api_keys`, `audit_trail` | **HIGH** — Integration builders break |

### 1.1.3 Authentication Data Flow

```
Registration (F-010)
  → INSERT users {email, password_hash, company_id, is_verified=false}
  → INSERT companies {name, plan='trial', ...}
  → Celery: send_verification_email.delay(company_id, user_id)  ← F-012
  → Brevo API: transactional email via template ID

Email Verification (F-012)
  → GET /api/auth/verify?token={token}
  → READ verification_tokens WHERE token = :token AND expires_at > NOW()
  → UPDATE users SET is_verified = true WHERE id = :user_id
  → DELETE verification_tokens WHERE id = :token_id

Login (F-013)
  → POST /api/auth/login {email, password, mfa_code?}
  → READ users WHERE email = :email AND company_id = :tenant_id
  → bcrypt.compare(password, stored_hash)
  → IF mfa_enabled: VERIFY totp_code via F-015 secret
  → IF rate_limited (F-018): REJECT with 429
  → GENERATE JWT {user_id, company_id, role, exp}
  → INSERT sessions {user_id, jwt_id, ip, user_agent, created_at}
  → SET Redis parwa:{company_id}:session:{jwt_id} → {user_id, role}
  → RETURN {access_token, refresh_token}

Session Management (F-017)
  → GET /api/sessions
  → READ sessions WHERE user_id = :user_id AND company_id = :tenant_id
  → DELETE /api/sessions/:id  (revoke single)
  → DELETE sessions WHERE user_id = :user_id AND id != :current_session_id  (revoke all)
  → DEL Redis parwa:{company_id}:session:{jwt_id}

API Key Management (F-019)
  → POST /api/keys  → INSERT api_keys {name, key_hash, company_id, permissions, expires_at}
  → Middleware: extract Bearer token → READ api_keys WHERE key_hash = :hash AND company_id = :tenant_id
  → INSERT audit_trail {action='api_key_usage', company_id, ...}
```

---

## 1.2 Billing & Payments (F-020 to F-027)

### 1.2.1 Visual Dependency Tree

```
F-004 Pricing Page
  └── F-020 Paddle Checkout Integration
        ├── F-021 Subscription Management (Upgrade/Downgrade)
        │     └── F-025 Cancellation Flow
        │           └── F-026 Cancellation Tracking
        ├── F-022 Paddle Webhook Handler  ◄═══ CENTRAL HUB
        │     ├── F-023 Invoice History
        │     ├── F-024 Daily Overage Charging
        │     │     └── [reads] F-046 Ticket List (ticket counts)
        │     └── [triggers] F-027 Payment Confirmation
        └── F-027 Payment Confirmation & Verification
              └── [writes] subscriptions, companies.plan
```

### 1.2.2 Dependency Table — Billing & Payments

| Feature | Depends On | Depended By | Shared Tables | Breaking Change Impact |
|---------|-----------|-------------|---------------|----------------------|
| **F-020** Paddle Checkout | F-004 | F-021, F-022, F-027 | `webhook_events` | **CRITICAL** — Entire billing chain |
| **F-021** Subscription Management | F-020 | F-025, F-072 (proration) | `subscriptions`, `audit_trail` | **HIGH** — Plan changes break |
| **F-022** Paddle Webhook Handler | F-020 | F-023, F-024, F-027 | `webhook_events`, `subscriptions` | **CRITICAL** — All financial state flows here |
| **F-023** Invoice History | F-022 | — | `invoices` | Low — Read-only consumer |
| **F-024** Daily Overage | F-022, F-046 | — | `tickets`, `overage_charges`, `subscriptions` | Medium — Writes to billing |
| **F-025** Cancellation Flow | F-021 | F-026 | `subscriptions`, `cancellation_requests` | Medium — Retention path |
| **F-026** Cancellation Tracking | F-025 | — | `cancellation_requests` | Low — Leaf node, analytics |
| **F-027** Payment Confirmation | F-020 | F-028 (onboarding) | `subscriptions`, `companies`, `email_logs` | **HIGH** — Onboarding gated |

### 1.2.3 Billing Data Flow

```
Checkout (F-020)
  → POST /api/billing/checkout {plan_id, billing_cycle}
  → Paddle.js overlay opens with plan_id + passthrough={company_id}
  → On success: Paddle redirect to /billing/confirm?checkout_id={id}

Webhook Handler (F-022)  ◄═══ ALL Paddle events enter here
  → POST /webhooks/paddle
  → Verify HMAC-SHA256 signature (BC-003)
  → Check webhook_events.paddle_event_id for idempotency
  → INSERT webhook_events {provider='paddle', event_id, event_type, payload, status='pending'}
  → Celery: process_paddle_webhook.delay(company_id, event.id)
    → dispatch by event_type:
      subscription.created → UPDATE subscriptions + trigger F-027
      subscription.updated → UPDATE subscriptions + trigger F-021 logic
      subscription.cancelled → UPDATE subscriptions + trigger F-025
      payment.succeeded → INSERT invoices + trigger F-023
      payment.failed → UPDATE subscriptions.status + alert

Daily Overage (F-024)  ◄═══ Celery beat: daily at 02:00 UTC
  → Celery: calculate_daily_overage.delay()
  → FOR each active subscription:
    → COUNT tickets WHERE company_id = :cid AND created_at = YESTERDAY
    → IF count > plan.ticket_inclusion:
      → excess = count - plan.ticket_inclusion
      → amount = excess × 0.10
      → Check idempotency: overage_charges WHERE company_id AND charge_date = YESTERDAY
      → IF not exists:
        → INSERT overage_charges {company_id, amount, ticket_count, charge_date}
        → Paddle API: create charge (idempotency_key: {company_id}_{date})
        → INSERT audit_trail {action='overage_charge', amount, ...}
        → Brevo: send overage notification email
        → Socket.io emit: tenant_{company_id} → 'billing:overage_charged'

Cancellation Flow (F-025)
  → POST /api/billing/cancel {reason, feedback}
  → INSERT cancellation_requests {company_id, reason, feedback, status='pending'}
  → Display retention offers (pause, downgrade, discount)
  → IF user confirms cancellation:
    → Paddle API: cancel subscription
    → UPDATE subscriptions SET status = 'cancelled', cancelled_at = NOW()
    → UPDATE cancellation_requests SET status = 'confirmed'
    → Celery: schedule_agent_deprovisioning.apply_async(countdown=86400)
    → Socket.io emit: tenant_{company_id} → 'billing:subscription_cancelled'
```

### 1.2.4 Combined Auth + Billing Cross-Feature Dependency

The authentication and billing systems share a critical cross-dependency through the
`companies` table and JWT tokens:

```
F-013 Login → JWT contains company_id
  → Every API call uses company_id for tenant isolation (BC-001)
  → F-020 Checkout passes company_id to Paddle as passthrough
  → F-022 Webhook extracts company_id from passthrough to scope events
  → F-024 Overage uses company_id to count tenant-specific tickets

⚡ BREAKING: If F-013 JWT payload structure changes (e.g., company_id field rename),
  F-020, F-022, F-024, and all middleware break simultaneously.
```

---

# Section 2: Ticket Lifecycle Flow (Critical Path)

## 2.1 End-to-End Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TICKET LIFECYCLE — CRITICAL PATH                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [1] Customer Message In                                                │
│       ↓                                                                 │
│  [2] Channel Ingestion                                                  │
│       ├── F-052 Omnichannel Router                                     │
│       ├── F-126 SMS (Twilio webhook)                                   │
│       ├── F-127 Voice (Twilio call)                                    │
│       └── F-130 Social Media (Shopify/Facebook)                        │
│       ↓                                                                 │
│  [3] OOO Detection (F-122)                                             │
│       └── IF out-of-office → STOP, log, return auto-reply             │
│       ↓                                                                 │
│  [4] PII Redaction (F-056)                                             │
│       └── Scan & redact PII before any processing                      │
│       ↓                                                                 │
│  [5] Ticket Creation                                                   │
│       ├── F-046 Ticket List (INSERT)                                   │
│       └── F-047 Ticket Detail (initial message)                        │
│       ↓                                                                 │
│  [6] Customer Identity Resolution (F-070)                              │
│       └── Match cross-channel identity                                 │
│       ↓                                                                 │
│  [7] Intent Classification (F-049)                                     │
│       └── Uses Smart Router Light tier                                 │
│       ↓                                                                 │
│  [8] Sentiment Analysis (F-063)                                        │
│       └── Empathy Engine scoring                                       │
│       ↓                                                                 │
│  [9] Auto-Assignment (F-050)                                           │
│       └── Score-based agent matching                                   │
│       ↓                                                                 │
│  [10] RAG Retrieval (F-064)                                            │
│       └── Vector search for knowledge context                          │
│       ↓                                                                 │
│  [11] Auto-Response Generation (F-065)                                 │
│       └── Combines RAG + intent + sentiment                            │
│       ↓                                                                 │
│  [12] Guardrails Check (F-057)                                         │
│       ├── BLOCKED → F-058 Blocked Response Manager → Review Queue     │
│       └── PASSED → [13]                                                │
│       ↓                                                                 │
│  [13] Confidence Scoring (F-059)                                       │
│       ├── Score ≥ Threshold → [14] Auto-Approve                       │
│       └── Score < Threshold → [16] Approval Queue                     │
│       ↓                                                                 │
│  [14] Auto-Approve (F-077, F-078)                                      │
│       └── Execute action (refund/status/email)                         │
│       ↓                                                                 │
│  [15] Socket.io Notification (F-037)                                   │
│       └── Emit to tenant room                                          │
│       ↓                                                                 │
│  [16] Approval Queue (F-074, F-076)                                    │
│       └── Supervisor review → Approve/Reject/Edit                     │
│       ↓                                                                 │
│  [17] Undo System (F-084)  ← available post-execution                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2.2 Step-by-Step Technical Details

### Step 1: Customer Message In — Channel Ingestion

**Features involved:** F-052, F-126, F-127, F-130

| Channel | Webhook Endpoint | Auth Method | Rate Limit |
|---------|-----------------|-------------|------------|
| Email | `POST /webhooks/brevo/inbound` | IP allowlist (BC-006) | 100 req/min |
| Chat | `Socket.io: chat:message` | JWT auth | 30 msg/min per user |
| SMS | `POST /webhooks/twilio/sms` | Twilio signature (BC-003) | 50 req/min |
| Voice | `POST /webhooks/twilio/voice` | Twilio signature (BC-003) | 20 req/min |
| Social | `POST /webhooks/shopify/order` | HMAC-SHA256 (BC-003) | 50 req/min |

**DB writes per ingestion:**
```sql
-- Immediate write on ingestion
INSERT INTO ticket_messages (company_id, ticket_id, channel, sender_type,
    sender_id, content, raw_payload, created_at)
VALUES (:company_id, :ticket_id, :channel, 'customer', :sender_id,
    :content, :payload, NOW());

-- Redis: rate limit counter
INCR parwa:{company_id}:rate:{channel}:{sender_id}
EXPIRE parwa:{company_id}:rate:{channel}:{sender_id} 60
```

**Socket.io events emitted:**
- `tenant_{company_id}` → `ticket:message_received` `{ticket_id, channel, preview}`

**Celery tasks triggered:**
- `process_incoming_message.delay(company_id, message_id)` (queue: `default`)

**Error recovery:**
- Webhook returns `200 OK` immediately (BC-003), processing is async
- If Celery task fails: retry 3× with exponential backoff (BC-004)
- If all retries fail: route to DLQ, alert ops team via Slack webhook
- Client reconnect: `GET /api/events/since?last_seen={timestamp}` recovers missed events

---

### Step 2: OOO Detection (F-122)

**DB reads:**
```sql
SELECT ooo_status, ooo_message, ooo_until
FROM company_settings
WHERE company_id = :company_id;
```

**Logic:**
```
IF company_settings.ooo_status = 'active'
  AND NOW() < company_settings.ooo_until:
    → Return auto-reply with ooo_message
    → INSERT ticket_messages (type='system', content=ooo_message)
    → Do NOT proceed to ticket creation
    → Socket.io emit: tenant_{company_id} → 'ticket:ooo_response'
    → STOP PROCESSING
```

**Error recovery:**
- If `company_settings` read fails: default to `ooo_status = 'inactive'` (fail-open)
- OOO messages are never processed through the AI pipeline — no downstream impact

---

### Step 3: PII Redaction (F-056)

**Called by:** F-053, F-054, F-064, F-065, F-066 (every feature that touches LLM)

**DB reads:**
```sql
SELECT pii_patterns, custom_regex
FROM company_settings
WHERE company_id = :company_id;
```

**Processing:**
```
1. Regex scan for: email, phone, SSN, credit card, address
2. Named Entity Recognition (NER) model for names/organizations
3. Replace matches with tokens: [EMAIL_REDACTED_1], [PHONE_REDACTED_2], etc.
4. Store redaction map in Redis: parwa:{company_id}:redaction:{message_id}
   → TTL: 24 hours (matches event_buffer retention)
5. Return redacted text
```

**Redis keys:**
- `parwa:{company_id}:redaction:{message_id}` → `{original: "john@example.com", token: "[EMAIL_REDACTED_1]"}`
- Used by F-065 and F-066 to restore PII when displaying to authenticated agents

**Error recovery:**
- If PII engine fails: DO NOT proceed to LLM call (fail-closed per BC-007)
- Log error, queue for manual review
- Fallback: strip all content and create ticket with "[Content pending review]" note

---

### Step 4: Ticket Creation

**Features involved:** F-046 (list), F-047 (detail)

**API endpoints:**
- `POST /api/tickets` — internal creation from channel ingestion
- `GET /api/tickets` — F-046 list view (paginated, filtered)
- `GET /api/tickets/:id` — F-047 detail view

**DB writes:**
```sql
INSERT INTO tickets (company_id, customer_id, channel, status, priority,
    intent, sentiment_score, assigned_agent_id, created_at, updated_at)
VALUES (:company_id, :customer_id, :channel, 'open', 'medium',
    NULL, NULL, NULL, NOW(), NOW());

INSERT INTO ticket_messages (company_id, ticket_id, sender_type, sender_id,
    content, content_redacted, channel, created_at)
VALUES (:company_id, :ticket_id, 'customer', :customer_id,
    :original_content, :redacted_content, :channel, NOW());
```

**Redis keys set:**
- `parwa:{company_id}:ticket:{ticket_id}:status` → `"open"`
- `parwa:{company_id}:ticket:{ticket_id}:lock` → `{agent_id}` (if assigned)

**Socket.io events:**
- `tenant_{company_id}` → `ticket:created` `{ticket_id, customer_name, channel, preview}`
- `tenant_{company_id}` → `ticket:count_updated` `{open_count, unassigned_count}`

**Celery tasks:**
- `classify_ticket.delay(company_id, ticket_id)` → triggers F-049
- `resolve_customer_identity.delay(company_id, ticket_id, customer_email)` → triggers F-070

**Error recovery:**
- If ticket INSERT fails: message is buffered in Redis `parwa:{company_id}:ingest_buffer`
  with TTL 1 hour, retried every 60 seconds
- If classification task fails: ticket remains with `intent=NULL`, flagged for manual review
- Socket.io failure: non-critical, event stored in `event_buffer` for recovery

---

### Step 5: Customer Identity Resolution (F-070)

**DB reads:**
```sql
-- Match by email
SELECT id, email, phone, name FROM customers
WHERE company_id = :company_id AND email = :email;

-- Match by phone (secondary)
SELECT id, email, phone, name FROM customers
WHERE company_id = :company_id AND phone = :phone;

-- Match by social account ID
SELECT c.id FROM customers c
JOIN customer_social_accounts sa ON sa.customer_id = c.id
WHERE c.company_id = :company_id AND sa.platform = :platform AND sa.platform_id = :platform_id;
```

**Logic:**
```
1. Try email match → if found, use existing customer
2. Try phone match → if found, merge identity if different from email match
3. Try social ID match → if found, link to existing customer
4. If no match → INSERT new customer record
5. UPDATE ticket.customer_id with resolved customer ID
```

**Socket.io events:**
- `tenant_{company_id}` → `ticket:identity_resolved` `{ticket_id, customer_id, customer_name, match_method}`

**Error recovery:**
- If identity resolution fails entirely: create anonymous customer record
  with `email = 'unknown_{timestamp}@pending.parwa.internal'`
- A background Celery task retries resolution after 5 minutes

---

### Step 6: Intent Classification (F-049)

**Feature:** F-049 (wrapper around F-062 Ticket Intent Classification + F-054 Smart Router)

**DB reads:**
```sql
-- Load company-specific classification config
SELECT confidence_thresholds, intent_labels, custom_rules
FROM company_settings
WHERE company_id = :company_id;

-- Load active model config from Smart Router
SELECT model_id, provider, priority, tier
FROM api_providers
WHERE tier = 'light' AND is_active = true
ORDER BY priority ASC;
```

**Processing:**
```
1. F-056 PII redaction (already done in step 3, but re-verify)
2. F-054 Smart Router: route to Light tier model
3. Prompt: "Classify this support message: {redacted_content}"
4. Response: {intent: "refund_request", confidence: 0.92, type: "urgent"}
5. F-059 Confidence Scoring: score the classification result
6. UPDATE tickets SET intent = :intent, priority = :type WHERE id = :ticket_id
```

**DB writes:**
```sql
UPDATE tickets SET intent = :intent, priority = :priority,
    classification_confidence = :score, updated_at = NOW()
WHERE id = :ticket_id AND company_id = :company_id;

INSERT INTO classification_log (company_id, ticket_id, intent, confidence,
    model_used, latency_ms, created_at)
VALUES (:company_id, :ticket_id, :intent, :confidence, :model, :latency, NOW());
```

**Redis keys:**
- `parwa:{company_id}:classification:{ticket_id}` → `{intent, confidence, model}`

**Celery tasks:**
- If classification confidence < 0.5: `escalate_to_human.delay(company_id, ticket_id)`
  → Sets ticket.assigned_agent_id to round-robin human agent

**Error recovery:**
- If Smart Router returns 429 on all models: queue classification, set `intent = 'pending_classification'`
- If model returns invalid JSON: F-055 Model Failover triggers retry with simplified prompt
- If all retries fail: default intent to `"general_inquiry"`, flag for supervisor review

---

### Step 7: Sentiment Analysis (F-063)

**Feature:** F-063 (Empathy Engine)

**Processing:**
```
1. F-054 Smart Router: route to Light tier (sentiment is low-cost)
2. Analyze: frustration level, urgency signals, emotional tone
3. Score: 0-100 where 0=calm, 50=neutral, 100=extremely frustrated
4. UPDATE tickets SET sentiment_score = :score
```

**DB writes:**
```sql
UPDATE tickets SET sentiment_score = :score, updated_at = NOW()
WHERE id = :ticket_id AND company_id = :company_id;
```

**Side effects based on sentiment score:**
| Score Range | Action | Target Feature |
|-------------|--------|----------------|
| 0–30 | Normal processing | — |
| 31–60 | Increase response urgency | F-050 (assignment priority boost) |
| 61–80 | Alert supervisor via Socket.io | F-037, F-080 |
| 81–100 | Route to VIP/Legal panel | F-080 (Urgent Attention) |

**Socket.io events:**
- `tenant_{company_id}` → `ticket:sentiment_alert` `{ticket_id, score, customer_name}` (if score > 60)

**Error recovery:**
- If sentiment analysis fails: default score to `50` (neutral)
- This is non-blocking — ticket processing continues without sentiment data

---

### Step 8: Auto-Assignment (F-050)

**DB reads:**
```sql
-- Load assignment rules
SELECT assignment_rules FROM company_settings WHERE company_id = :company_id;

-- Load available agents with current workload
SELECT a.id, a.name, a.specialties, a.is_available,
    COUNT(t.id) as active_tickets
FROM agents a
LEFT JOIN tickets t ON t.assigned_agent_id = a.id
    AND t.status IN ('open', 'in_progress')
    AND t.company_id = :company_id
WHERE a.company_id = :company_id AND a.is_available = true
GROUP BY a.id
ORDER BY active_tickets ASC;
```

**Assignment algorithm:**
```
1. Match ticket intent → agent specialties
2. Filter by availability (is_available = true)
3. Score each agent:
   - Specialty match: +40 points
   - Lowest workload: +30 points (inversely proportional to active_tickets)
   - Historical resolution rate on this intent: +20 points
   - Random jitter: +10 points (prevent herd behavior)
4. Select top-scoring agent
5. UPDATE tickets SET assigned_agent_id = :agent_id, status = 'assigned'
```

**DB writes:**
```sql
UPDATE tickets SET assigned_agent_id = :agent_id, status = 'assigned',
    assigned_at = NOW(), updated_at = NOW()
WHERE id = :ticket_id AND company_id = :company_id;
```

**Socket.io events:**
- `tenant_{company_id}` → `ticket:assigned` `{ticket_id, agent_id, agent_name}`
- `agent_{agent_id}` → `ticket:new_assignment` `{ticket_id, customer_name, intent}`

**Error recovery:**
- If no agents available: set `status = 'unassigned'`, emit `ticket:unassigned` alert
- If assignment rules DB read fails: fall back to round-robin (F-050 default behavior)

---

### Step 9: RAG Retrieval (F-064)

**DB reads:**
```sql
-- Knowledge base document metadata
SELECT id, title, chunk_count, last_indexed_at
FROM knowledge_base_documents
WHERE company_id = :company_id AND is_indexed = true;

-- Company-specific RAG config
SELECT top_k, similarity_threshold, rerank_model
FROM company_settings WHERE company_id = :company_id;
```

**Processing (via F-054 Smart Router — Light tier for embedding query):**
```
1. Generate embedding from redacted customer message
2. Vector search: SELECT top_k=5 similar chunks from tenant-isolated vector DB
3. Filter by similarity_threshold (default: 0.7)
4. Rerank results (if rerank_model configured)
5. Return context: [{chunk_text, source_doc, relevance_score}]
```

**Redis keys:**
- `parwa:{company_id}:rag_cache:{ticket_id}` → `[{chunk, source, score}]`
  TTL: 1 hour (cached for potential re-generation)

**Error recovery:**
- If vector DB is unreachable: return empty context, proceed with LLM without KB context
- F-065 Auto-Response Generation handles missing context gracefully (generic response)
- If embedding generation fails: log error, skip RAG, proceed with classification-only response

---

### Step 10: Auto-Response Generation (F-065)

**Feature:** F-065 (combines F-062 intent, F-064 RAG, F-063 sentiment)

**DB reads:**
```sql
-- Load response templates for intent
SELECT template_id, template_body, variables, tone_adjustments
FROM response_templates
WHERE company_id = :company_id AND intent = :intent AND is_active = true;

-- Load company brand voice settings
SELECT brand_voice, tone_guidelines, prohibited_phrases
FROM company_settings WHERE company_id = :company_id;
```

**Processing:**
```
1. F-054 Smart Router: route to Medium tier (standard response generation)
2. Construct prompt:
   - System: brand voice + tone guidelines + prohibited phrases
   - Context: RAG results from F-064
   - Customer message: PII-redacted content
   - Intent classification: {intent, confidence}
   - Sentiment: {score} → adjust tone (empathetic if frustrated)
3. Generate response via LLM
4. F-057 Guardrails: check response for safety
5. F-056 PII: re-check output for any leaked PII
6. F-059 Confidence: score the overall response quality
```

**DB writes:**
```sql
-- Store AI draft
INSERT INTO ticket_messages (company_id, ticket_id, sender_type, sender_id,
    content, content_redacted, channel, is_ai_generated, confidence_score,
    guardrails_status, created_at)
VALUES (:company_id, :ticket_id, 'ai', 'system', :response, :redacted,
    :channel, true, :confidence, :guardrails_status, NOW());

-- Store confidence record
INSERT INTO confidence_scores (company_id, ticket_id, message_id,
    overall_score, retrieval_score, intent_score, sentiment_score,
    model_used, created_at)
VALUES (:company_id, :ticket_id, :message_id, :overall, :retrieval,
    :intent, :sentiment, :model, NOW());
```

**Socket.io events:**
- `tenant_{company_id}` → `ticket:ai_draft_ready` `{ticket_id, message_id, preview}`
- `agent_{agent_id}` → `ticket:response_ready` `{ticket_id, preview, confidence}`

**Celery tasks:**
- `evaluate_response_approval.delay(company_id, ticket_id, message_id)`
  → triggers approval logic (Steps 12-16)

---

### Step 11: Guardrails Check (F-057)

**Detailed in Section 3.** Key connections:

| Scenario | Next Step | Feature |
|----------|-----------|---------|
| PASSED (safe) | Confidence scoring | F-059 |
| BLOCKED (unsafe) | Review queue | F-058 → F-074 |
| PII detected in output | Re-redact, re-check | F-056 |

**DB writes:**
```sql
INSERT INTO guardrails_audit_log (company_id, ticket_id, message_id,
    check_result, category, reason, model_output, created_at)
VALUES (:company_id, :ticket_id, :message_id, :result, :category,
    :reason, :output, NOW());

-- If blocked:
INSERT INTO guardrails_blocked_queue (company_id, ticket_id, message_id,
    original_prompt, model_output, blocking_reason, blocking_category,
    status, created_at)
VALUES (...);
```

---

### Step 12: Confidence Scoring (F-059)

**Scoring formula:**
```
overall_confidence = (
    retrieval_relevance × 0.30 +
    intent_match × 0.25 +
    sentiment_alignment × 0.15 +
    historical_accuracy × 0.20 +
    context_completeness × 0.10
)
```

**DB reads:**
```sql
-- Per-company thresholds
SELECT auto_approve_threshold, require_approval_threshold
FROM confidence_thresholds
WHERE company_id = :company_id;

-- Historical accuracy for model/ticket-type combination
SELECT AVG(was_correct) as model_accuracy
FROM ai_response_feedback
WHERE company_id = :company_id
    AND model_used = :model
    AND intent = :intent
    AND created_at > NOW() - INTERVAL '30 days';
```

**Decision tree:**
```
IF overall_confidence >= auto_approve_threshold:
    → F-077 Auto-Handle rules check
    → IF action is auto-handleable AND confidence >= action threshold:
        → F-078 Auto-Approve Confirmation (if first-time for this action type)
        → Execute action
    → ELSE:
        → Approval Queue (F-074)

ELIF overall_confidence >= require_approval_threshold:
    → Approval Queue (F-074) — standard review

ELSE:
    → Approval Queue (F-074) — flagged as LOW CONFIDENCE
    → Socket.io emit: urgent alert to supervisors
```

**DB writes:**
```sql
UPDATE confidence_scores SET overall_score = :score,
    retrieval_score = :retrieval, intent_score = :intent,
    sentiment_score = :sentiment, historical_score = :history,
    context_score = :context, decision = :decision
WHERE id = :score_id;

-- If auto-approved:
INSERT INTO approval_records (company_id, ticket_id, message_id,
    action_type, proposed_value, status, approved_by, approved_at,
    confidence_score, created_at)
VALUES (:company_id, :ticket_id, :message_id, :action, :value,
    'auto_approved', 'system', NOW(), :confidence, NOW());
```

---

### Step 13-14: Auto-Approve & Execute Action

**Action types and their execution paths:**

#### Refund Action
```
1. Validate refund amount ≤ order total (BC-002)
2. INSERT approval_records (status='auto_approved')
3. Paddle API: create refund {transaction_id, amount, reason}
4. IF Paddle succeeds:
     UPDATE tickets SET status = 'resolved', resolution = 'refunded'
     INSERT audit_trail {action='auto_refund', amount, paddle_refund_id}
     Socket.io emit: tenant_{company_id} → 'ticket:resolved' {ticket_id, action: 'refund'}
   ELSE:
     UPDATE approval_records SET status = 'failed'
     INSERT audit_trail {action='refund_failed', error}
     Re-queue to human approval (F-074)
```

#### Status Change Action
```
1. INSERT approval_records (status='auto_approved')
2. UPDATE tickets SET status = :new_status, updated_at = NOW()
3. INSERT audit_trail {action='auto_status_change', old_status, new_status}
4. Socket.io emit: tenant_{company_id} → 'ticket:status_changed' {ticket_id, old, new}
```

#### Email Send Action
```
1. INSERT approval_records (status='auto_approved')
2. F-056 PII check on email content (re-verify)
3. Brevo API: send transactional email {template_id, to, params}
4. INSERT email_logs {template_used, recipient, status='sent', ticket_id}
5. Socket.io emit: tenant_{company_id} → 'ticket:email_sent' {ticket_id}
```

---

### Step 15-16: Approval Queue & Supervisor Review

**Detailed in Section 4.** Key flow:

```
→ F-074 Approval Queue Dashboard (real-time via Socket.io)
→ F-076 Individual Approval/Reject
   → Approve: execute action (same as auto-approve) + F-084 Undo record
   → Reject: AI re-generates OR human handles manually
   → Edit: supervisor modifies AI response, then approve
→ F-075 Batch Approval (via F-071 Semantic Clustering)
→ F-081 Approval Reminders (2h/4h/8h/24h escalation)
→ F-082 Approval Timeout (72h auto-reject)
```

---

### Step 17: Undo System (F-084)

**Triggered after any executed action:**
```sql
INSERT INTO undo_records (company_id, ticket_id, approval_record_id,
    action_type, original_state, new_state, recall_available_until,
    is_undone, created_at)
VALUES (:company_id, :ticket_id, :approval_id, :action,
    :original_state_json, :new_state_json,
    NOW() + INTERVAL '15 minutes', false, NOW());
```

**Undo operations:**
| Action Type | Undo Method | Window |
|-------------|-------------|--------|
| Refund | Paddle API: reverse refund | 15 minutes |
| Status change | UPDATE tickets SET status = original | 15 minutes |
| Email sent | Brevo API: recall if supported, else mark as `recall_attempted` | 5 minutes |

---

## 2.3 Ticket Lifecycle Event Summary

### Socket.io Events by Step

| Step | Event Name | Room | Payload |
|------|-----------|------|---------|
| 1 (Ingestion) | `ticket:message_received` | `tenant_{company_id}` | `{ticket_id, channel, preview}` |
| 2 (OOO) | `ticket:ooo_response` | `tenant_{company_id}` | `{ticket_id, ooo_message}` |
| 4 (Create) | `ticket:created` | `tenant_{company_id}` | `{ticket_id, customer_name, channel}` |
| 5 (Identity) | `ticket:identity_resolved` | `tenant_{company_id}` | `{ticket_id, customer_id}` |
| 7 (Sentiment) | `ticket:sentiment_alert` | `tenant_{company_id}` | `{ticket_id, score}` |
| 8 (Assign) | `ticket:assigned` | `tenant_{company_id}` + `agent_{agent_id}` | `{ticket_id, agent_name}` |
| 10 (Draft) | `ticket:ai_draft_ready` | `tenant_{company_id}` | `{ticket_id, preview}` |
| 11 (Blocked) | `ticket:guardrails_blocked` | `tenant_{company_id}` | `{ticket_id, reason}` |
| 14 (Auto-approve) | `ticket:auto_resolved` | `tenant_{company_id}` | `{ticket_id, action}` |
| 16 (Queue) | `approval:queued` | `tenant_{company_id}` | `{ticket_id, action, confidence}` |

### Celery Tasks by Step

| Task Name | Queue | Triggered By | Timeout |
|-----------|-------|-------------|---------|
| `process_incoming_message` | `default` | Webhook/Socket | 120s |
| `classify_ticket` | `ai_light` | Ticket creation | 60s |
| `resolve_customer_identity` | `default` | Ticket creation | 30s |
| `analyze_sentiment` | `ai_light` | Classification complete | 30s |
| `assign_ticket` | `default` | Sentiment complete | 15s |
| `generate_response` | `ai_medium` | Assignment complete | 120s |
| `check_guardrails` | `ai_light` | Response generated | 30s |
| `evaluate_approval` | `default` | Guardrails pass | 15s |
| `execute_approved_action` | `default` | Approval given | 120s |
| `send_approval_reminder` | `default` | Celery beat (periodic) | 30s |
| `timeout_approval` | `default` | Celery beat (periodic) | 30s |

---

# Section 3: AI Pipeline Internal Connections

## 3.1 GSD State Engine (F-053) Connections

The GSD (Guided Support Dialogue) State Engine is the orchestrator for multi-step
conversational AI flows. It maintains persistent state across LLM calls.

### Connection Map

```
                    ┌──────────────────────┐
                    │   F-060 LangGraph     │
                    │  Workflow Engine      │
                    └──────────┬───────────┘
                               │ orchestrates
                               ▼
┌──────────────┐    calls    ┌──────────────────────┐    calls    ┌──────────────┐
│   F-054      │◄────────────│   F-053 GSD State    │────────────►│   F-059      │
│ Smart Router │────────────►│     Engine           │◄────────────│ Confidence   │
│              │  LLM calls  │                      │  scoring    │  Scoring     │
└──────┬───────┘             └──────────┬───────────┘             └──────────────┘
       │                                │
       │  failover                      │ retrieval
       ▼                                ▼
┌──────────────┐              ┌──────────────────────┐
│   F-055      │              │   F-064              │
│ Model Fail   │              │  Knowledge Base RAG  │
│              │              │  (Vector Search)     │
└──────────────┘              └──────────────────────┘
                                       ▲
                                       │ redaction before/after
                                ┌──────┴───────┐
                                │   F-056      │
                                │ PII Redaction│
                                └──────────────┘
```

### State Storage Pattern

**Redis (primary — low latency):**
```
Key:    parwa:{company_id}:gsd:{ticket_id}
Type:   Hash
Fields:
  - session_id:           UUID
  - current_step:         "collecting_order_info"
  - next_step:            "verify_order_status"
  - intent:               "refund_request"
  - collected_info:       JSON {"order_id": "ORD-123", "reason": "damaged"}
  - pending_actions:      JSON [{"type": "refund", "amount": null}]
  - conversation_history: JSON [{"role":"user","content":"..."}, ...]
  - context_tokens:       1847
  - max_tokens:           8000
  - health_status:        "healthy"  | "warning" | "critical" | "suggest_new"
  - created_at:           ISO timestamp
  - updated_at:           ISO timestamp
TTL:    7200 (2 hours, per BC-008)
```

**PostgreSQL (fallback — persistence per BC-008):**
```sql
-- Table: gsd_sessions
CREATE TABLE gsd_sessions (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    state JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    context_tokens INTEGER NOT NULL DEFAULT 0,
    max_tokens INTEGER NOT NULL DEFAULT 8000,
    health_status VARCHAR(20) NOT NULL DEFAULT 'healthy',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(ticket_id)
);
-- Critical index for recovery queries
CREATE INDEX idx_gsd_sessions_company_ticket
    ON gsd_sessions(company_id, ticket_id);
```

### Socket.io Events Emitted

| Event | Room | Trigger | Payload |
|-------|------|---------|---------|
| `gsd:transition:{ticket_id}` | `tenant_{company_id}` | Every step transition | `{from_step, to_step, ticket_id}` |
| `gsd:state_updated:{ticket_id}` | `tenant_{company_id}` | Any state change | `{state_delta, health_status}` |
| `gsd:context_warning:{ticket_id}` | `tenant_{company_id}` | 70% capacity | `{context_tokens, max_tokens, level: "warning"}` |
| `gsd:context_critical:{ticket_id}` | `tenant_{company_id}` | 90% capacity | `{level: "critical", compressed: true}` |
| `gsd:suggest_new_chat:{ticket_id}` | `tenant_{company_id}` | 95% capacity | `{level: "suggest_new"}` |

---

## 3.2 Smart Router (F-054) Connections

The Smart Router is the most-connected feature in the AI pipeline. Every feature
that makes an LLM call goes through it.

### Callers (who calls F-054)

| Caller Feature | Tier Used | Use Case |
|---------------|-----------|----------|
| F-053 GSD State Engine | Medium/Heavy | Multi-step conversational reasoning |
| F-049 Ticket Classification | Light | Intent/type classification |
| F-062 Intent Classification | Light | Detailed multi-label classification |
| F-065 Auto-Response Generation | Medium | Customer response composition |
| F-066 AI Draft Composer | Medium | Agent co-pilot draft suggestions |
| F-057 Guardrails AI | Light | Content safety evaluation |
| F-058 Blocked Response Manager | Light | Re-evaluation of edited blocked responses |
| F-061 DSPy Optimization | Heavy | Prompt optimization experiments |
| F-063 Sentiment Analysis | Light | Frustration/tone detection |
| F-087 Jarvis Chat Panel | Medium | Natural language command processing |
| F-094 Trust Preservation | Medium | Safe fallback response generation |

### Tier Fallback Chain

```
Request arrives at F-054 with requested tier (e.g., "light")
  │
  ▼
Try Model #1 in "light" tier (highest priority)
  │
  ├── SUCCESS → return response
  │
  ├── 429 Rate Limit → Try Model #2 in "light" tier
  │                      ├── SUCCESS → return response
  │                      └── 429 → Try next model in "light"
  │                              └── All "light" exhausted → Fall to "medium" tier
  │
  ├── 500 Server Error → F-055 Model Failover → Try Model #2
  │
  ├── Timeout (>30s) → F-055 Model Failover → Try Model #2
  │
  └── Invalid JSON → Retry with simplified prompt → If still invalid → template fallback

ALL tiers exhausted:
  → Queue request in Redis: parwa:{company_id}:llm_queue
  → Return {status: "processing", estimated_wait: "2-3 minutes"}
  → Celery: process_queued_llm_request.delay(company_id, request_id)
```

### DB Reads per Request

```sql
-- Load model configuration
SELECT id, model_id, provider, api_key_ref, priority, tier, max_tokens,
    temperature, is_active
FROM api_providers
WHERE tier = :requested_tier AND is_active = true
ORDER BY priority ASC;

-- Load company-specific thresholds
SELECT auto_approve_threshold, max_retries, fallback_tier
FROM confidence_thresholds
WHERE company_id = :company_id;
```

### Rate Limit Tracking (Redis)

```
Key:    parwa:ratelimit:{provider}:{model_id}
Type:   String (counter)
TTL:    60 (sliding window)
Pattern: INCR → if > limit, skip to next model

Key:    parwa:ratelimit:{company_id}:llm_calls
Type:   String (counter)
TTL:    3600 (per-hour company limit)
```

---

## 3.3 Guardrails AI (F-057) Connections

### Connection Map

```
                    F-065 Auto-Response
                    F-066 AI Draft Composer
                           │
                           │  every AI output
                           ▼
                   ┌───────────────┐
                   │   F-057      │
                   │  Guardrails  │
                   │     AI       │
                   └───┬───────┬───┘
                       │       │
              PASSED   │       │  BLOCKED
                       │       │
                       ▼       ▼
                  F-059      F-058 Blocked Response
                  Confidence   Manager & Review Queue
                  Scoring           │
                               BC-007 Rule 7:
                               Second check on
                               approved blocked
                               responses ─────►│
                                              ▼
                                         F-074 Approval Queue
```

### Guardrails Checks Performed

| Check # | Category | What It Detects | Blocking Action |
|---------|----------|----------------|-----------------|
| 1 | PII Leakage | SSN, credit cards, emails in output | F-056 re-redact + re-check |
| 2 | Toxicity | Hate speech, harassment, profanity | Hard block → F-058 |
| 3 | Hallucination | Claims not supported by RAG context | Soft block → F-058 |
| 4 | Off-topic | Response unrelated to customer query | Soft block → F-058 |
| 5 | Policy violation | Promises not in company policy | Soft block → F-058 |
| 6 | Financial inaccuracy | Wrong refund amounts, incorrect prices | Hard block → F-058 |
| 7 | Legal liability | Legal advice, contractual commitments | Hard block → F-058 |

### DB Tables

```sql
-- Every check is logged
INSERT INTO guardrails_audit_log (company_id, ticket_id, message_id,
    check_number, category, check_result, reason, model_output,
    confidence, created_at)
VALUES (...);

-- Blocked responses get queued
INSERT INTO guardrails_blocked_queue (company_id, ticket_id, message_id,
    original_prompt, model_output, blocking_reason, blocking_category,
    check_number, status, created_at)
VALUES (...);
-- status: 'pending_review' | 'approved' | 'rejected' | 'permanently_banned'
```

---

## 3.4 Complete AI Pipeline Connection Table

| Source Feature | Target Feature | Call Type | Data Passed | Sync/Async | Error Handling |
|---------------|---------------|-----------|-------------|------------|----------------|
| F-053 GSD Engine | F-054 Smart Router | Direct function | Prompt, context, tier | Async | F-055 failover |
| F-053 GSD Engine | F-059 Confidence | Direct function | AI response, context | Sync | Default score=50 |
| F-053 GSD Engine | F-064 RAG | Direct function | Query text, top_k | Async | Empty context fallback |
| F-053 GSD Engine | F-056 PII Redaction | Direct function | Text (pre-LLM) | Sync | Fail-closed (stop) |
| F-054 Smart Router | F-055 Model Failover | Direct function | Error, model_id, tier | Sync | Escalate tier |
| F-049 Classification | F-054 Smart Router | Direct function | Redacted text, tier='light' | Async | Default intent |
| F-049 Classification | F-062 Intent Class | Internal call | Text, company config | Async | Fallback to 'general' |
| F-062 Intent Class | F-054 Smart Router | Direct function | Classification prompt, tier='light' | Async | Fail to next model |
| F-063 Sentiment | F-054 Smart Router | Direct function | Message text, tier='light' | Async | Default neutral |
| F-064 RAG | F-056 PII Redaction | Direct function | Query text | Sync | Fail-closed |
| F-064 RAG | F-032 KB Upload | DB read | Company doc IDs | Sync | Empty results |
| F-065 Auto-Response | F-054 Smart Router | Direct function | Full prompt, tier='medium' | Async | Template fallback |
| F-065 Auto-Response | F-064 RAG | Direct function | Customer query | Async | No-context response |
| F-065 Auto-Response | F-062 Intent | DB read | Cached intent for ticket | Sync | Re-classify |
| F-065 Auto-Response | F-063 Sentiment | DB read | Cached sentiment score | Sync | Neutral tone |
| F-065 Auto-Response | F-057 Guardrails | Direct function | Generated response | Sync | Block → F-058 |
| F-065 Auto-Response | F-056 PII Redaction | Direct function | Output text | Sync | Fail-closed |
| F-065 Auto-Response | F-059 Confidence | Direct function | Response + metadata | Sync | Queue for review |
| F-066 Draft Composer | F-054 Smart Router | Direct function | Draft prompt, tier='medium' | Async | Template fallback |
| F-066 Draft Composer | F-064 RAG | Direct function | Customer query | Async | No-context draft |
| F-066 Draft Composer | F-057 Guardrails | Direct function | Draft response | Sync | Block → F-058 |
| F-057 Guardrails | F-058 Blocked Mgr | DB write | Blocked response data | Async | Alert supervisor |
| F-057 Guardrails | F-056 PII Redaction | Direct function | Output text | Sync | Re-redact |
| F-058 Blocked Mgr | F-074 Approval Queue | DB write | Blocked item record | Async | Queue item |
| F-058 Blocked Mgr | F-057 Guardrails | Direct function | Edited response (BC-007 R7) | Sync | Re-check |
| F-059 Confidence | F-074 Approval Queue | DB write | Score + decision | Async | Queue if low |
| F-059 Confidence | F-077 Auto-Handle | DB read | Threshold config | Sync | Default to queue |
| F-059 Confidence | F-079 Score Breakdown | DB write | Component scores | Sync | Display raw scores |
| F-060 LangGraph | F-053 GSD Engine | Orchestration | Workflow definition, state | Async | Workflow halt |
| F-060 LangGraph | F-054 Smart Router | Orchestration | Step-specific prompts | Async | Failover |
| F-067 Context Compress | F-053 GSD Engine | State mutation | Compressed history | Sync | Skip compression |
| F-067 Context Compress | F-054 Smart Router | Direct function | Summarization prompt, tier='medium' | Async | Skip compression |
| F-068 Health Meter | F-053 GSD Engine | DB read | Token count, thresholds | Sync (poll) | Display last known |
| F-069 Capacity Popup | F-068 Health Meter | Event subscription | Health status updates | Sync | Manual check |
| F-070 Identity Resolution | F-056 PII Redaction | Direct function | Customer text | Sync | Skip redaction |
| F-071 Semantic Cluster | F-062 Intent | DB read | Intent vectors | Async | Empty clusters |
| F-071 Semantic Cluster | F-075 Batch Approve | DB write | Cluster assignments | Async | Individual review |

---

# Section 4: Approval System Connection Web

## 4.1 What Feeds INTO the Approval Queue

### Input Sources

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPROVAL QUEUE INPUTS                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  F-059 Confidence Scoring                                        │
│    ├── Score < require_approval_threshold → F-074 (standard)    │
│    └── Score < 0.3 → F-074 (flagged LOW CONFIDENCE)            │
│                                                                  │
│  F-057 Guardrails AI                                             │
│    └── BLOCKED response → F-058 → F-074 (guardrails_review)    │
│                                                                  │
│  F-077 Auto-Handle Rules                                         │
│    └── Actions ABOVE threshold → BYPASS queue (auto-execute)   │
│    └── New rule activation → F-078 confirmation first           │
│                                                                  │
│  F-080 Urgent Attention Panel                                    │
│    ├── VIP customer tickets → ALWAYS to queue (never auto)      │
│    ├── Legal escalations → ALWAYS to queue (never auto)         │
│    └── High sentiment (score > 80) → ALWAYS to queue            │
│                                                                  │
│  F-082 Approval Timeout (72h)                                    │
│    └── Re-queued items → back to F-074 with 'timeout' flag     │
│                                                                  │
│  F-092 Train from Error                                          │
│    └── Training data flagged for review → F-074 (training)      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Input Data Model

All inputs converge on the `approval_records` table:

```sql
CREATE TABLE approval_records (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    ticket_id UUID REFERENCES tickets(id),
    message_id UUID REFERENCES ticket_messages(id),
    action_type VARCHAR(50) NOT NULL,  -- 'refund', 'status_change', 'email_send', 'guardrails_review'
    proposed_value JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- status: pending | auto_approved | approved | rejected | timed_out | cancelled
    source VARCHAR(30) NOT NULL,
    -- source: confidence_score | guardrails | urgent_panel | timeout_retry
    confidence_score DECIMAL(5,2),
    approved_by UUID REFERENCES users(id),  -- NULL for auto/timeouts
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,
    reminder_count INTEGER NOT NULL DEFAULT 0,
    last_reminded_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,  -- NOW() + 72h
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approval_pending
    ON approval_records(company_id, status, created_at DESC)
    WHERE status = 'pending';
```

---

## 4.2 What the Approval Queue Triggers

### Output Flow Diagram

```
                    F-074 Approval Queue Dashboard
                    (real-time via Socket.io)
                           │
              ┌────────────┼────────────────┐
              │            │                │
              ▼            ▼                ▼
        F-076          F-075          F-081
      Individual     Batch           Approval
       Approve      Approval       Reminders
      /Reject       (Clusters)      (2h/4h/8h/24h)
              │            │                │
              │            │                ▼
              │            │           F-082
              │            │        Timeout (72h)
              │            │                │
              ▼            ▼                │
         ┌─────────────────────┐            │
         │  Execute Action     │◄───────────┘
         │  (if approved)      │  (auto-reject)
         └────────┬────────────┘
                  │
                  ▼
           ┌────────────┐
           │  F-084     │
           │  Undo Sys  │
           │ (create    │
           │ undo rec)  │
           └────────────┘
```

### F-076 Individual Approval — Execution Paths

**Approve path:**
```
1. PATCH /api/approvals/:id/approve {reviewer_notes?}
2. UPDATE approval_records SET status='approved', approved_by=:user, approved_at=NOW()
3. Route by action_type:
   - 'refund'      → Paddle API refund + audit_trail
   - 'status_change' → UPDATE tickets.status + Socket.io emit
   - 'email_send'  → Brevo API + email_logs
   - 'guardrails_review' → release response + F-057 second check (BC-007 R7)
4. INSERT undo_records (F-084)
5. INSERT audit_trail {action='manual_approval', reviewer, ticket_id}
6. Socket.io emit: tenant_{company_id} → 'approval:approved' {approval_id, ticket_id}
7. Socket.io emit: tenant_{company_id} → 'ticket:updated' {ticket_id}
```

**Reject path:**
```
1. PATCH /api/approvals/:id/reject {reason}
2. UPDATE approval_records SET status='rejected', rejection_reason=:reason
3. Socket.io emit: tenant_{company_id} → 'approval:rejected' {approval_id, reason}
4. IF source = 'confidence_score':
     → Celery: regenerate_response.delay(company_id, ticket_id)
     → AI generates new response, re-enters approval cycle
   ELIF source = 'guardrails':
     → Mark response as permanently handled by human
5. INSERT audit_trail {action='approval_rejected', reason}
```

### F-075 Batch Approval — Cluster-Based Processing

```
1. User selects cluster (from F-071 Semantic Clustering)
2. POST /api/approvals/batch
   {cluster_id, action: 'approve_all' | 'reject_all', notes?}
3. READ approval_records WHERE cluster_id = :cluster_id AND status = 'pending'
4. FOR EACH record in cluster:
     → Execute same approve/reject logic as F-076
5. INSERT audit_trail {action='batch_approval', count, cluster_id}
6. Socket.io emit: tenant_{company_id} → 'approval:batch_processed'
   {cluster_id, approved_count, rejected_count}
```

### F-081 Approval Reminders — Escalation Schedule

| Time After Queue | Action | Channel | Feature Connection |
|-------------------|--------|---------|-------------------|
| 2 hours | First reminder | In-app notification | Socket.io `approval:reminder` |
| 4 hours | Second reminder | In-app + email | F-006 Brevo template |
| 8 hours | Urgent reminder | In-app + email + push | F-006 Brevo + Push API |
| 24 hours | Critical escalation | Email to supervisor + manager | F-006 Brevo |
| 48 hours | Escalate to admin | Email to company admin | F-006 Brevo |
| 72 hours | Auto-reject | System action | F-082 |

**Implementation (Celery beat):**
```
Celery beat schedule:
  check_approval_reminders:
    task: send_approval_reminders
    schedule: every 15 minutes
    queue: default

Task logic:
  SELECT * FROM approval_records
  WHERE status = 'pending'
    AND last_reminded_at IS NULL  (never reminded → 2h+ check)
    OR (last_reminded_at + interval < NOW())  (escalation check)
  ORDER BY created_at ASC;

  FOR each record:
    hours_pending = (NOW() - created_at).total_hours()
    IF hours_pending >= 72: → auto-reject (F-082)
    ELIF hours_pending >= 48: → admin escalation
    ELIF hours_pending >= 24: → critical escalation
    ELIF hours_pending >= 8:  → urgent reminder
    ELIF hours_pending >= 4:  → second reminder
    ELIF hours_pending >= 2:  → first reminder

    UPDATE reminder_count += 1, last_reminded_at = NOW()
```

### F-082 Approval Timeout — 72h Auto-Reject

```
1. Celery beat: check_approval_timeouts (every 15 minutes)
2. SELECT * FROM approval_records
   WHERE status = 'pending' AND expires_at < NOW()
3. FOR EACH timed-out record:
   UPDATE approval_records SET status = 'timed_out'
4. INSERT audit_trail {action='approval_timeout', ticket_id, approval_id}
5. Socket.io emit: tenant_{company_id} → 'approval:timed_out' {ticket_id}
6. IF action was time-sensitive (refund, urgent status change):
   → Notify ticket assignee that approval expired
   → Re-queue with elevated priority IF still relevant
```

---

## 4.3 Financial Flow Specifically

### Refund Approval — Detailed Path

```
Step 1: F-065 generates refund suggestion
  → proposed_value: {"amount": 49.99, "currency": "USD", "order_id": "ORD-123",
                      "reason": "damaged_on_arrival", "paddle_tx_id": "tx_abc"}

Step 2: F-059 scores confidence
  → overall_score: 0.82 (above auto-approve threshold for refunds: 0.85? No → queue)

Step 3: F-074 queues for approval
  → INSERT approval_records {
       action_type: 'refund',
       proposed_value: {amount, order_id, reason, paddle_tx_id},
       confidence_score: 0.82,
       source: 'confidence_score'
     }

Step 4: Supervisor reviews via F-076
  → Approve

Step 5: Execute refund (BC-002 compliant)
  → BEGIN TRANSACTION
  → INSERT approval_records SET status='approved'
  → Paddle API: POST /refunds {transaction_id, amount, reason}
  → IF Paddle success:
       INSERT audit_trail {
         action: 'refund_executed',
         amount: 49.99,
         paddle_refund_id: 'ref_xyz',
         order_id: 'ORD-123',
         approved_by: user_id
       }
       UPDATE tickets SET status='resolved', resolution='refunded'
       INSERT undo_records {action_type:'refund', ...}
  → COMMIT
  → Socket.io emit: 'ticket:resolved' {ticket_id, action:'refund', amount: 49.99}
```

### Status Change Approval — Detailed Path

```
Step 1: F-065 suggests status change
  → proposed_value: {"from": "open", "to": "resolved",
                      "resolution_note": "Issue resolved per KB article #42"}

Step 2: F-059 scores: 0.91 (above threshold) → Auto-approve (F-077)

Step 3: Execute (BC-009 compliant)
  → INSERT approval_records {status: 'auto_approved', approved_by: 'system'}
  → UPDATE tickets SET status = 'resolved'
  → INSERT audit_trail {action: 'auto_status_change'}
  → Socket.io emit: 'ticket:status_changed' {ticket_id, old: 'open', new: 'resolved'}
```

### Email Send Approval — Detailed Path

```
Step 1: F-065 drafts email response
  → proposed_value: {
       template_id: 'tpl_welcome_back',
       to: 'customer@example.com',
       params: {name: 'John', order_id: 'ORD-123'},
       content_preview: 'Dear John, we apologize for...'
     }

Step 2: F-057 Guardrails check: PASSED
Step 3: F-059 scores: 0.88 → Auto-approve (F-077)

Step 4: Execute
  → F-056 PII re-check on content
  → Brevo API: send email via template tpl_welcome_back
  → INSERT email_logs {
       template_used: 'tpl_welcome_back',
       recipient: 'customer@example.com',
       status: 'sent',
       related_ticket_id: ticket_id,
       brevo_message_id: 'msg_abc'
     }
  → INSERT audit_trail {action: 'auto_email_sent'}
  → Socket.io emit: 'ticket:email_sent' {ticket_id}
```

---

## 4.4 Approval System Dependency Summary Table

| Source → Target | Data Format | Sync/Async | Failure Impact |
|-----------------|-------------|------------|---------------|
| F-059 → F-074 | `approval_records` INSERT | Async (Celery) | Item stuck in limbo |
| F-057 → F-058 → F-074 | `guardrails_blocked_queue` INSERT | Async | Unsafe response could leak |
| F-080 → F-074 | `approval_records` INSERT with `source='urgent'` | Sync | VIP ticket goes to auto-handle |
| F-077 → F-078 | Config check + confirmation UI | Sync | Auto-approve activated without confirmation |
| F-074 → F-076 | `approval_records` UPDATE | Sync (API) | Approval action not executed |
| F-074 → F-075 | Cluster-based batch read | Sync (API) | Cluster items processed individually |
| F-076 → F-084 | `undo_records` INSERT | Sync | No undo available for executed action |
| F-081 → F-074 | Reminder counter UPDATE | Async (Celery) | Supervisor unaware of pending item |
| F-082 → F-074 | `approval_records` status UPDATE | Async (Celery) | Stale approvals remain forever |
| F-076 → audit_trail | `audit_trail` INSERT | Sync | No audit record of approval decision |

---

# Section 5: Shared Database Tables Map

## 5.1 Table: `tickets`

**The most heavily shared table in PARWA.** Schema changes here affect 10+ features.

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-046, F-047, F-048, F-049, F-050, F-051, F-052, F-024, F-119 |
| **Primary Writer** | F-052 (Omnichannel ingestion creates tickets) |
| **Read-Only Consumers** | F-046 (list), F-048 (search), F-024 (overage count) |
| **Read-Write Consumers** | F-047 (messages), F-049 (classification), F-050 (assignment), F-051 (bulk) |
| **Critical Indexes** | `(company_id, status, created_at DESC)`, `(company_id, assigned_agent_id)`, `(company_id, intent)`, `(customer_id, company_id)` |

**Impact analysis for schema changes:**

| Change Type | Features Affected | Risk Level |
|-------------|------------------|------------|
| Add column | F-046 (list display), F-047 (detail), F-051 (bulk filter) | Low (additive) |
| Rename column | All 9 features | **CRITICAL** — application-wide breakage |
| Change `status` enum | F-046 (filters), F-050 (assignment), F-051 (bulk), F-047 (display) | **HIGH** |
| Add `company_id` constraint | Already exists (BC-001) | N/A |
| Change `intent` type | F-049, F-050, F-062, F-065, F-071 | **HIGH** |

---

## 5.2 Table: `users`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-010, F-011, F-012, F-013, F-014, F-015, F-016, F-017, F-018, F-019 |
| **Primary Writer** | F-010 (Registration) |
| **Read-Only Consumers** | F-017 (session listing), F-018 (rate limit checks) |
| **Read-Write Consumers** | F-011 (OAuth profile update), F-012 (verification), F-013 (login), F-014 (password reset), F-015 (MFA), F-016 (backup codes), F-019 (API key ownership) |
| **Critical Indexes** | `(email) UNIQUE`, `(company_id)`, `(id, company_id)`, `(is_verified, company_id)` |

**Impact analysis:**

| Change Type | Features Affected | Risk Level |
|-------------|------------------|------------|
| Add column | Most features (non-breaking if nullable) | Low |
| Rename `email` | All auth features | **CRITICAL** |
| Change `is_verified` semantics | F-012, F-013 | **HIGH** |
| Modify `company_id` FK | All features + middleware (BC-001) | **CRITICAL** |

---

## 5.3 Table: `companies`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | Nearly ALL features (BC-001 tenant scoping) |
| **Primary Writer** | F-010 (Registration), F-027 (Payment Confirmation updates plan) |
| **Read-Only Consumers** | Every authenticated feature (via middleware) |
| **Critical Indexes** | `(id) PRIMARY`, `(plan)`, `(is_active)` |

> ⚠️ **HIGHEST RISK TABLE.** The `companies` table is read by the BC-001 middleware
> on EVERY API request. A schema change here affects the entire application.

| Change Type | Features Affected | Risk Level |
|-------------|------------------|------------|
| Any column change | All 139 features | **CRITICAL** |
| Add column (nullable) | Low direct impact, but ORM models must update | Medium |
| Rename `plan` column | F-020, F-021, F-022, F-024, F-027, F-042, F-099 | **CRITICAL** |

---

## 5.4 Table: `api_providers`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-054, F-055, F-059, F-100, F-102 |
| **Primary Writer** | Admin API / F-100 (training may update model status) |
| **Read-Only Consumers** | F-054 (Smart Router reads model config), F-055 (failover reads alternatives), F-059 (reads tier config) |
| **Read-Write Consumers** | F-100 (flag for retraining), F-102 (update performance stats) |
| **Critical Indexes** | `(tier, is_active, priority)`, `(company_id, tier)` |

| Change Type | Features Affected | Risk Level |
|-------------|------------------|------------|
| Add provider field | F-054, F-055 | Low |
| Rename `tier` | F-054, F-055, F-059, F-049, F-062, F-065, F-066 | **CRITICAL** |
| Change `priority` semantics | F-054 (model selection order) | **HIGH** |

---

## 5.5 Table: `approval_records`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-074, F-075, F-076, F-077, F-078, F-081, F-082, F-084 |
| **Primary Writer** | F-059 (creates from scoring), F-057 (creates from guardrails), F-076 (status updates) |
| **Read-Only Consumers** | F-074 (dashboard list), F-079 (confidence display) |
| **Read-Write Consumers** | F-075 (batch updates), F-076 (individual approve/reject), F-081 (reminder tracking), F-082 (timeout), F-084 (undo link) |
| **Critical Indexes** | `(company_id, status, created_at DESC) WHERE status='pending'`, `(ticket_id)`, `(cluster_id)`, `(expires_at) WHERE status='pending'` |

| Change Type | Features Affected | Risk Level |
|-------------|------------------|------------|
| Add `action_type` value | F-076 (execution routing), F-077 (auto-handle rules) | Medium |
| Rename `status` values | All 8 features | **CRITICAL** |
| Change `proposed_value` JSON schema | F-076 (action execution), F-077 (consequence display) | **HIGH** |

---

## 5.6 Table: `ticket_messages`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-047, F-048, F-052, F-065, F-066, F-119 |
| **Primary Writer** | F-052 (channel ingestion), F-065 (AI response), F-066 (draft) |
| **Read-Only Consumers** | F-047 (detail display), F-048 (search index), F-119 |
| **Read-Write Consumers** | F-065 (marks as ai_generated), F-066 (marks as draft) |
| **Critical Indexes** | `(company_id, ticket_id, created_at)`, `(company_id, content_redacted) tsvector`, `(ticket_id, sender_type)` |

| Change Type | Features Affected | Risk Level |
|-------------|------------------|------------|
| Add column | F-047 (display), F-048 (search) | Low |
| Rename `content_redacted` | F-047 (display logic), F-048 (search), F-056 (redaction) | **HIGH** |
| Change `is_ai_generated` semantics | F-065, F-066, F-074 | **HIGH** |

---

## 5.7 Table: `email_logs`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-006 (Brevo integration), F-012 (verification), F-014 (password reset), F-024 (overage notification), F-084 (email recall) |
| **Primary Writer** | F-006 (Brevo webhook handler updates status), F-012 (verification email sent), F-014 (reset email sent), F-024 (overage notification), F-081 (reminder emails) |
| **Read-Only Consumers** | F-024 (rate limit check per BC-006), F-084 (recall lookup) |
| **Critical Indexes** | `(company_id, recipient, created_at)`, `(related_ticket_id)`, `(template_used)`, `(status)` |

---

## 5.8 Table: `event_buffer`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-037, F-038, F-088, F-089, F-091 |
| **Primary Writer** | Every Socket.io emit also writes here (BC-005) |
| **Read-Only Consumers** | F-037 (reconnection recovery: `GET /api/events/since`) |
| **Read-Write Consumers** | F-038 (metrics aggregation reads + marks as consumed) |
| **Critical Indexes** | `(company_id, created_at)`, `(created_at)` for cleanup |
| **Retention** | 24 hours (Celery beat cleanup per BC-005 Rule 4) |

> ⚠️ **WRITE-HOT TABLE.** Every Socket.io event triggers a write. During high traffic,
> this table can see 1000+ writes/minute. Consider partitioning by `company_id` or using
> TimescaleDB hypertable for production.

---

## 5.9 Table: `knowledge_base_documents`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-032, F-033, F-064 |
| **Primary Writer** | F-032 (document upload), F-033 (status updates during processing) |
| **Read-Only Consumers** | F-064 (RAG pipeline reads metadata for filtering) |
| **Critical Indexes** | `(company_id, is_indexed)`, `(company_id, title)` |

---

## 5.10 Table: `training_runs`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-100, F-101, F-102, F-103 |
| **Primary Writer** | F-100 (creates run record), F-101 (status updates), F-102 (performance metrics) |
| **Read-Only Consumers** | F-103 (rollback reads previous run) |
| **Critical Indexes** | `(company_id, agent_id, created_at DESC)`, `(status)` |

---

## 5.11 Table: `guardrails_blocked_queue`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-057, F-058 |
| **Primary Writer** | F-057 (creates blocked entries) |
| **Read-Write Consumers** | F-058 (reads queue, updates status on review) |
| **Critical Indexes** | `(company_id, status, created_at)`, `(ticket_id)` |

---

## 5.12 Table: `subscriptions`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-020, F-021, F-022, F-024, F-025 |
| **Primary Writer** | F-020 (checkout creates), F-022 (webhook updates) |
| **Read-Only Consumers** | F-024 (overage reads plan limits), F-042 (growth nudge reads usage) |
| **Read-Write Consumers** | F-021 (plan changes), F-025 (cancellation) |
| **Critical Indexes** | `(company_id) UNIQUE`, `(paddle_subscription_id) UNIQUE`, `(status)` |

---

## 5.13 Table: `gsd_sessions`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-053, F-089 |
| **Primary Writer** | F-053 (creates and updates on every state transition) |
| **Read-Only Consumers** | F-089 (GSD State Terminal reads for display) |
| **Critical Indexes** | `(company_id, ticket_id) UNIQUE`, `(status, updated_at)` |
| **Recovery** | On Redis restart, F-053 reads active sessions from this table to hydrate Redis |

---

## 5.14 Table: `confidence_scores`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-059, F-079 |
| **Primary Writer** | F-059 (creates score record for every AI response) |
| **Read-Only Consumers** | F-079 (displays breakdown to supervisors) |
| **Critical Indexes** | `(company_id, ticket_id)`, `(company_id, created_at)` for trend analysis |

---

## 5.15 Table: `audit_trail`

| Attribute | Detail |
|-----------|--------|
| **Used By Features** | F-021, F-024, F-025, F-076, F-077, F-084 |
| **Primary Writer** | Every financial action (F-021, F-024, F-025), every approval (F-076, F-077), every undo (F-084) |
| **Read-Only Consumers** | Admin audit dashboard, compliance reporting (BC-010) |
| **Critical Indexes** | `(company_id, created_at DESC)`, `(action_type)`, `(company_id, ticket_id)` |

> ⚠️ **COMPLIANCE-CRITICAL.** This table supports GDPR audits, financial reconciliation,
> and dispute resolution. Writes here must NEVER fail silently. Use WAL mode and
> consider streaming replicas for compliance.

---

## 5.16 Complete Cross-Reference Summary

| DB Table | # Features Using | Primary Writer | Highest Risk Change |
|----------|-----------------|---------------|--------------------|
| `companies` | **139** (all) | F-010 | Any column modification |
| `tickets` | 10 | F-052 | `status` enum change |
| `users` | 10 | F-010 | `email` rename |
| `event_buffer` | 5 | All Socket.io | Schema change |
| `approval_records` | 8 | F-059 | `status` enum change |
| `ticket_messages` | 6 | F-052 | `content_redacted` rename |
| `api_providers` | 5 | Admin API | `tier` column change |
| `subscriptions` | 5 | F-020 | `status` enum change |
| `email_logs` | 5 | F-006 | `template_used` change |
| `audit_trail` | 6 | Multiple | `action_type` rename |
| `gsd_sessions` | 2 | F-053 | `state` JSONB schema |
| `confidence_scores` | 2 | F-059 | Score component rename |
| `guardrails_blocked_queue` | 2 | F-057 | `status` enum change |
| `knowledge_base_documents` | 3 | F-032 | `is_indexed` semantics |
| `training_runs` | 4 | F-100 | `status` enum change |

---

# Section 6: Circular Dependency & Conflict Analysis

## 6.1 Circular Dependencies

### Analysis Result: No Hard Circular Dependencies Detected

After mapping all feature connections in the core system, **no hard circular
dependencies exist** in the PARWA architecture. The dependency graph is a DAG
(Directed Acyclic Graph). However, several **soft cycles** exist where features
communicate bidirectionally through events or database state.

### Soft Cycle 1: F-054 ↔ F-059 (Score-Router Feedback)

```
F-054 Smart Router → returns LLM response → F-059 scores it
F-059 reads api_providers (F-054 config) to select models
```

**Why this is NOT a true circular dependency:**
- F-054 does not call F-059. F-059 is called by consumers of F-054's output.
- F-059 reads `api_providers` to adjust scoring weights, but does not call F-054.
- Data flows one direction: F-054 → output → F-059 → score.

**Risk:** If F-059 modifies `api_providers` (e.g., downgrading a model's priority
based on low scores), it could affect future F-054 routing decisions. This is
**intentional feedback** — not a bug — but should be rate-limited.

**Mitigation:** F-059 should NEVER write to `api_providers`. Only F-100 (training loop)
should modify model priorities based on accumulated 50-mistake threshold (BC-007 Rule 10).

---

### Soft Cycle 2: F-053 ↔ F-059 (GSD-Confidence Loop)

```
F-053 calls F-054 for LLM → receives response → calls F-059 to score
F-059 score determines F-053 next step (continue vs. escalate)
```

**Why this is NOT a true circular dependency:**
- F-053 orchestrates; F-059 evaluates. One-way data flow with a branch.
- F-059 does not call F-053. F-053 reads the score and decides next action.

**Risk:** If F-059 returns extremely low confidence, F-053 may re-call F-054 with
a different prompt, creating a retry loop. Without a max-retry limit, this could
infinite-loop.

**Mitigation:**
```python
MAX_GSD_LLM_RETRIES = 3  # Hard cap in F-053

async def gsd_step(self, state):
    for attempt in range(MAX_GSD_LLM_RETRIES):
        response = await smart_router.route(prompt, tier='medium')
        score = await confidence_scoring.evaluate(response)
        if score >= CONTINUE_THRESHOLD:
            return response
        # Low score → adjust prompt and retry
        prompt = self._simplify_prompt(prompt, score.breakdown)
    # All retries exhausted → escalate to human
    return self.escalate_to_human(state)
```

---

### Soft Cycle 3: F-058 → F-057 (Blocked Response Re-check)

```
F-057 blocks response → F-058 queues it → Supervisor edits → F-057 re-checks
```

**Why this is NOT a true circular dependency:**
- This is BC-007 Rule 7: intentionally designed second-pass check.
- Data flows: F-057 → block → F-058 → edit → F-057 (re-check with NEW input).
- The re-check receives a different input (edited response), not the original.

**Risk:** Supervisor could edit response 10 times, each triggering F-057 re-check,
consuming LLM credits.

**Mitigation:** Limit re-check attempts per blocked response:
```
Redis: parwa:{company_id}:blocked_rechecks:{blocked_id}
INCR → IF > 3: reject with "Maximum re-check attempts exceeded"
```

---

## 6.2 Race Conditions

### Race Condition 1: Ticket Assignment (F-050)

**Scenario:**
```
Time 0ms:   F-049 classifies ticket #123 as "refund"
Time 50ms:  F-050 reads agent list → Agent A has 3 tickets
Time 60ms:  Another ticket arrives → F-050 assigns to Agent A (now 4 tickets)
Time 100ms: F-050 assigns ticket #123 to Agent A (based on stale count of 3)
```

**Result:** Agent A gets 5 tickets when max intended was 4. Workload skew.

**Mitigation:**
```sql
-- Use optimistic locking with version column
UPDATE tickets SET assigned_agent_id = :agent_id, status = 'assigned',
    version = version + 1
WHERE id = :ticket_id
    AND version = :expected_version
    AND company_id = :company_id;

-- If rows_affected = 0: another process assigned it first → re-evaluate
```

Also use Redis distributed lock:
```
SET parwa:{company_id}:ticket:{ticket_id}:lock {agent_id} NX EX 10
IF lock acquired: proceed with assignment
ELSE: another agent is assigning → wait and retry
```

---

### Race Condition 2: Approval Record Concurrent Updates

**Scenario:**
```
Supervisor A clicks "Approve" at time T
Supervisor B clicks "Reject" at time T+50ms (same record)
```

**Result:** Last write wins. One supervisor's action is silently lost.

**Mitigation:**
```sql
UPDATE approval_records SET status = 'approved', approved_by = :supervisor_a
WHERE id = :approval_id AND status = 'pending';

-- If rows_affected = 0: already processed by another supervisor
-- Return 409 Conflict to Supervisor B's request
```

Also emit Socket.io `approval:status_changed` immediately on first update,
causing UI to disable buttons for other viewers.

---

### Race Condition 3: Daily Overage Calculation (F-024)

**Scenario:**
```
Celery beat triggers F-024 at 02:00 UTC
Webhook for late-night ticket arrives at 02:00:01 UTC
F-024 counts tickets for yesterday: misses the late ticket
Next day: F-024 counts tickets again: includes yesterday's late ticket
```

**Result:** Ticket counted twice or not at all depending on timezone handling.

**Mitigation:**
```python
# Use strict date boundaries in UTC
yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
today = now.replace(hour=0, minute=0, second=0, microsecond=0)

count = db.query(Ticket).filter(
    Ticket.company_id == company_id,
    Ticket.created_at >= yesterday,
    Ticket.created_at < today
).count()

# Plus idempotency check
exists = db.query(OverageCharge).filter(
    OverageCharge.company_id == company_id,
    OverageCharge.charge_date == yesterday.date()
).first()
```

---

### Race Condition 4: GSD State Concurrent Updates (F-053)

**Scenario:**
```
Customer sends message → F-053 updates state (adds to history)
AI generates response → F-053 updates state (adds response to history)
Both write to Redis parwa:{company_id}:gsd:{ticket_id} simultaneously
```

**Result:** One write overwrites the other. Conversation history corrupted.

**Mitigation:**
```python
# Use Redis WATCH/MULTI for optimistic locking
async def update_gsd_state(self, ticket_id, delta):
    key = f"parwa:{company_id}:gsd:{ticket_id}"
    async with redis.pipeline() as pipe:
        while True:
            try:
                pipe.watch(key)
                current = await pipe.get(key)
                merged = self._merge(json.loads(current), delta)
                pipe.multi()
                pipe.setex(key, 7200, json.dumps(merged))
                await pipe.execute()
                break
            except WatchError:
                continue  # Retry on conflict
```

---

## 6.3 Shared Lock Contention (Redis)

### High-Contention Redis Key Patterns

| Redis Key Pattern | Writers | Contention Level | Impact |
|-------------------|---------|-----------------|--------|
| `parwa:{company_id}:ticket:{id}:lock` | F-050 (assignment) | Medium | Assignment conflicts |
| `parwa:{company_id}:gsd:{ticket_id}` | F-053 (state engine) | **HIGH** | State corruption |
| `parwa:{company_id}:rate:{channel}:{sender}` | F-052 (ingestion) | **HIGH** | Rate limit miscalculation |
| `parwa:ratelimit:{provider}:{model}` | F-054 (smart router) | **CRITICAL** | All AI calls affected |
| `parwa:{company_id}:llm_queue` | F-054 (queuing) | Medium | Delayed AI responses |
| `parwa:{company_id}:redaction:{msg_id}` | F-056 (PII engine) | Low | Short-lived, per-message |
| `parwa:{company_id}:session:{jwt_id}` | F-013, F-017 | Medium | Session state conflicts |

### CRITICAL: `parwa:ratelimit:{provider}:{model}`

This key tracks per-model rate limits globally (not per-tenant). In a multi-tenant
environment with 100+ active tenants, this key receives **hundreds of INCR operations
per second**.

**Symptoms of contention:**
- Redis CPU spikes on INCR operations
- Latency p99 for Smart Router calls increases
- Some tenants experience false 429 errors (key lock wait time interpreted as rate limit)

**Mitigation:**
1. **Use Redis cluster** with sharding by provider (not single key per model)
2. **Implement local rate limiting** in each Celery worker (in-memory sliding window)
   with periodic sync to Redis
3. **Use Lua scripts** for atomic INCR + TTL operations:
```lua
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
```
4. **Consider Redis Streams** instead of key-based rate limiting for high-throughput scenarios

---

## 6.4 Cascade Failure Paths

### Failure Path 1: F-054 Smart Router Down

```
F-054 Smart Router fails (all providers 429 or infrastructure down)
  ├── F-049 Classification fails → tickets created with intent=NULL
  ├── F-063 Sentiment fails → all sentiment=50 (neutral)
  ├── F-064 RAG unaffected (uses vector DB directly, not LLM)
  ├── F-065 Auto-Response fails → no AI responses generated
  ├── F-066 Draft Composer fails → no co-pilot drafts
  ├── F-057 Guardrails fails → all responses pass (DANGEROUS)
  │     └── MITIGATION: If guardrails can't check, BLOCK all AI output
  ├── F-059 Confidence fails → all scores default to 0 → everything queues for approval
  ├── F-087 Jarvis fails → no NL commands
  └── F-094 Trust Preservation activates → safe template responses only
```

**Features still operational:** F-046 (list), F-047 (detail), F-050 (manual assignment),
F-074 (approval queue), F-076 (manual approve/reject), F-083 (emergency pause).

**Total cascading failures:** ~15 features directly affected, ~5 indirectly.

**Mitigation:**
- F-083 Emergency Pause: kill-switch immediately stops all AI processing
- F-094 Trust Preservation: ensures customer never sees "we can't help"
- F-093 Self-Healing: auto-retries with fallback providers
- Manual queue: human agents can handle all tickets via F-047

---

### Failure Path 2: F-022 Paddle Webhook Handler Down

```
F-022 fails (webhook endpoint unresponsive)
  ├── Paddle events not processed → subscription status stale
  ├── F-023 Invoice History outdated → missing invoices
  ├── F-024 Daily Overage still runs (reads tickets table, not webhooks) ✓
  ├── F-025 Cancellation not processed → customer still charged
  ├── F-027 Payment Confirmation delayed → onboarding blocked
  └── audit_trail missing financial entries → compliance risk
```

**Mitigation:**
- Paddle retries webhooks for up to 72 hours (built-in provider retry)
- Implement webhook processing backlog: query Paddle API for missed events on recovery
- BC-003 Rule 10: endpoint MUST respond within 3 seconds (queue for async processing)
- Health check: if F-022 returns non-200, alert ops team immediately

---

### Failure Path 3: Redis Down

```
Redis becomes unavailable
  ├── F-053 GSD State: falls back to PostgreSQL (BC-008 Rule 1,2) ✓
  ├── F-017 Sessions: falls back to PostgreSQL sessions table ✓
  ├── F-037 Activity Feed: falls back to REST API polling ✓
  ├── F-054 Rate Limiting: NO FALLBACK → rate limits disabled (SECURITY RISK)
  ├── F-050 Ticket Locks: NO FALLBACK → concurrent assignment possible
  └── F-018 Rate Limiting: NO FALLBACK → brute-force attacks possible
```

**Mitigation:**
- Redis Sentinel or Redis Cluster for HA
- Application-level rate limiting as fallback (in-process token bucket per worker)
- Redis AOF persistence for state recovery (BC-004 Rule 6)
- Immediate alert on Redis connection failure

---

### Failure Path 4: Socket.io Server Down

```
Socket.io becomes unavailable
  ├── F-037 Activity Feed: still works via REST polling ✓
  ├── F-047 Ticket Detail: still works via REST ✓
  ├── F-074 Approval Queue: still works via REST polling ✓
  ├── F-050 Assignment notifications: missed (agent doesn't see new ticket)
  ├── F-081 Reminders: still works via Celery → Brevo email ✓
  └── Event buffer: events still stored in DB for recovery ✓
```

**Mitigation:**
- BC-005 Rule 6: dashboard must function without Socket.io
- Client-side: exponential backoff reconnection (1s, 2s, 4s...30s max)
- `GET /api/events/since?last_seen={ts}` recovers missed events on reconnect
- Nginx sticky sessions (BC-005 Rule 7) prevent drops during rolling deploys

---

### Failure Path 5: PostgreSQL Down

```
PostgreSQL becomes unavailable
  ├── ALL features fail (total system outage)
  ├── No ticket creation, no auth, no billing, no AI
  ├── Redis state becomes source of truth temporarily (stale)
  └── Celery tasks fail and queue up
```

**Mitigation:**
- PostgreSQL streaming replication with automatic failover (Patroni)
- Connection pooling (PgBouncer) with connection retry logic
- Circuit breaker pattern: after N failed connections, stop attempting and return
  degraded responses
- Redis serves as temporary buffer for incoming messages (max 1 hour)
- On recovery: flush Redis buffer to PostgreSQL in order

---

## 6.5 Upgrade Risk Zones

### Risk Zone 1: `tickets.status` Enum — Affects 9 Features

**Current values:** `open`, `assigned`, `in_progress`, `pending_approval`, `resolved`,
`closed`, `cancelled`

**Affected features if changed:** F-046, F-047, F-049, F-050, F-051, F-052, F-024,
F-074, F-076

**Migration strategy:**
1. Add new status values as additive ALTER (no removal)
2. Update application code to handle new values
3. Deploy application code
4. After 30 days, optionally remove deprecated values with a separate migration
5. Test with 3+ tenants (BC-001 Rule 6)

---

### Risk Zone 2: `companies.plan` Column — Affects 7+ Features

**Current values:** `trial`, `starter`, `growth`, `high`

**Affected features:** F-020, F-021, F-022, F-024, F-025, F-027, F-042, F-099

**Risk:** Changing plan names breaks Paddle integration (plan IDs reference plan names),
overage calculations (ticket inclusion varies by plan), and feature entitlements.

**Migration strategy:**
1. Add new column `plan_tier` alongside existing `plan`
2. Dual-write both columns during transition
3. Update all feature code to read from `plan_tier`
4. After verification, deprecate `plan` column

---

### Risk Zone 3: `approval_records.status` Enum — Affects 8 Features

**Current values:** `pending`, `auto_approved`, `approved`, `rejected`,
`timed_out`, `cancelled`

**Affected features:** F-074, F-075, F-076, F-077, F-078, F-081, F-082, F-084

**Risk:** The approval system is a state machine. Adding/removing states without
updating all 8 features can cause items to get stuck in invalid states.

**Migration strategy:**
1. Map all state transitions in a state machine diagram
2. Add new states only at the END of the flow (terminal states)
3. Update all 8 features' status checks in a single atomic deployment
4. Run integration tests for all transition paths

---

### Risk Zone 4: `api_providers.tier` Enum — Affects 7+ Features

**Current values:** `light`, `medium`, `heavy`

**Affected features:** F-054, F-055, F-049, F-062, F-065, F-066, F-057, F-058

**Risk:** Tier names are hardcoded in Smart Router fallback logic, confidence
thresholds, and guardrails check routing. Changing tier names breaks the entire
AI pipeline.

**Migration strategy:**
1. This should NEVER be changed without a full system-wide migration plan
2. If adding a new tier: add as new value, update F-054 routing logic first
3. Extensive testing with all AI features before deployment

---

### Risk Zone 5: `event_buffer` Schema — Affects All Real-Time Features

**Affected features:** F-037, F-038, F-088, F-089, F-091

**Risk:** This table receives writes from EVERY Socket.io event. Schema changes
require locking the table, which blocks all real-time event writes.

**Migration strategy:**
1. Use `ALTER TABLE ... ADD COLUMN` (does not require table lock in PostgreSQL)
2. Never rename or drop columns on a live system
3. Consider creating `event_buffer_v2` and dual-writing during transition
4. Apply changes during low-traffic window (02:00-04:00 UTC)

---

## 6.6 Conflict Summary Matrix

| Conflict ID | Type | Features Involved | Severity | Mitigation |
|-------------|------|------------------|----------|------------|
| CC-001 | Race condition | F-050 (assignment) | Medium | Optimistic locking + Redis distributed lock |
| CC-002 | Race condition | F-076 (approval update) | **HIGH** | Optimistic locking + 409 Conflict response |
| CC-003 | Race condition | F-024 (overage calc) | Medium | UTC date boundaries + idempotency |
| CC-004 | Race condition | F-053 (GSD state) | **HIGH** | Redis WATCH/MULTI pipeline |
| CC-005 | Redis contention | F-054 (rate limit key) | **CRITICAL** | Redis cluster + Lua scripts + local caching |
| CC-006 | Redis contention | F-053 (GSD state key) | **HIGH** | Redis WATCH/MULTI |
| CC-007 | Cascade failure | F-054 down → 15 features | **CRITICAL** | F-083 pause + F-094 trust + F-093 self-heal |
| CC-008 | Cascade failure | F-022 down → 5 billing features | **HIGH** | Paddle retry + API backlog query |
| CC-009 | Cascade failure | Redis down → rate limits off | **HIGH** | Sentinel HA + in-process fallback |
| CC-010 | Cascade failure | Socket.io down → notifications lost | Medium | Event buffer + REST fallback |
| CC-011 | Cascade failure | PostgreSQL down → total outage | **CRITICAL** | Patroni HA + circuit breaker |
| CC-012 | Soft cycle | F-054 ↔ F-059 | Low | F-059 read-only on api_providers |
| CC-013 | Soft cycle | F-053 ↔ F-059 | Low | MAX_GSD_LLM_RETRIES = 3 |
| CC-014 | Soft cycle | F-057 → F-058 → F-057 | Low | Max 3 re-checks per blocked response |
| CC-015 | Upgrade risk | `tickets.status` enum | **HIGH** | Additive migration only |
| CC-016 | Upgrade risk | `companies.plan` column | **HIGH** | Dual-write migration |
| CC-017 | Upgrade risk | `approval_records.status` | **HIGH** | State machine validation |
| CC-018 | Upgrade risk | `api_providers.tier` | **CRITICAL** | System-wide migration plan |
| CC-019 | Upgrade risk | `event_buffer` schema | Medium | Online DDL + low-traffic window |

---

## Appendix A: Redis Key Namespace Reference

| Key Pattern | Owner Feature(s) | TTL | Purpose |
|-------------|-----------------|-----|---------|
| `parwa:{company_id}:session:{jwt_id}` | F-013, F-017 | Session duration | Active session lookup |
| `parwa:{company_id}:gsd:{ticket_id}` | F-053 | 7200s | GSD state (primary store) |
| `parwa:{company_id}:ticket:{ticket_id}:status` | F-046, F-050 | 3600s | Cached ticket status |
| `parwa:{company_id}:ticket:{ticket_id}:lock` | F-050 | 10s | Assignment lock |
| `parwa:{company_id}:rate:{channel}:{sender}` | F-052, F-018 | 60s | Ingestion rate limit |
| `parwa:{company_id}:redaction:{message_id}` | F-056 | 86400s | PII redaction map |
| `parwa:{company_id}:rag_cache:{ticket_id}` | F-064 | 3600s | RAG results cache |
| `parwa:{company_id}:classification:{ticket_id}` | F-049 | 3600s | Classification cache |
| `parwa:{company_id}:llm_queue` | F-054 | None (list) | Queued LLM requests |
| `parwa:ratelimit:{provider}:{model}` | F-054, F-055 | 60s | Global model rate limit |
| `parwa:{company_id}:ratelimit:llm_calls` | F-054 | 3600s | Per-company LLM rate limit |
| `parwa:{company_id}:blocked_rechecks:{id}` | F-057, F-058 | 86400s | Re-check counter |
| `parwa:{company_id}:ingest_buffer` | F-052 | 3600s | Failed ingestion buffer |

---

## Appendix B: Socket.io Room Naming Convention

| Room Pattern | Created By | Purpose | BC Reference |
|-------------|-----------|---------|-------------|
| `tenant_{company_id}` | F-037 | All tenant users see tenant events | BC-005 Rule 5 |
| `agent_{agent_id}` | F-050 | Agent-specific assignment notifications | BC-001 |
| `approval_{company_id}` | F-074 | Approval queue updates for supervisors | BC-009 |
| `admin_{company_id}` | F-083, F-088 | Admin-only emergency and system events | BC-011 |

> ⚠️ Per BC-005 Rule 5: A client MUST NEVER join a global or cross-tenant room.
> All room operations must validate company_id from JWT before joining.

---

## Appendix C: Celery Queue Architecture

| Queue Name | Workers | Features Served | Priority |
|-----------|---------|----------------|----------|
| `default` | 4 | General tasks (F-050, F-070, F-074) | Normal |
| `ai_light` | 2 | F-049, F-062, F-063, F-057 (low-cost models) | High |
| `ai_medium` | 2 | F-065, F-066, F-053 (standard responses) | High |
| `ai_heavy` | 1 | F-061, F-087 (complex reasoning) | Medium |
| `billing` | 1 | F-022, F-024, F-027 | **Critical** |
| `email` | 2 | F-006, F-012, F-014, F-081 | High |
| `dlq` | 1 | Failed tasks from all queues (BC-004) | Manual |

**Beat Schedule (recurring tasks):**
| Task | Schedule | Feature |
|------|----------|---------|
| `calculate_daily_overage` | Daily 02:00 UTC | F-024 |
| `check_approval_reminders` | Every 15 minutes | F-081 |
| `check_approval_timeouts` | Every 15 minutes | F-082 |
| `cleanup_event_buffer` | Daily 03:00 UTC | F-037 (BC-005) |
| `check_temp_agent_expiry` | Daily 04:00 UTC | F-073 |
| `sync_paddle_invoices` | Hourly | F-023 |
| `recover_gsd_states` | On worker startup | F-053 (BC-008) |

---

*End of PARWA Connection Map — Part 1: Core Systems*
*Next: Part 2 covers Channel Integrations, Agent Management, Analytics, and MCP/Extensibility*























# PARWA Connection Map — Part 2: Support Systems

> **AI-Powered Customer Support Platform — 139 Features, 13 Categories**
>
> This document maps how features in **support-facing systems** connect, communicate, and depend on each other and on **core systems** (Part 1). It covers: Communication Channels, Integrations & Extensibility, Jarvis Command Center, Analytics & Dashboard, Agent Training Pipeline, and Onboarding.
>
> **Cross-reference:** Core system connections (Auth, Billing, Ticket Management, AI Core Engine, Approval System) are documented in *PARWA Connection Map Part 1*. Where Part 1 features are referenced, the notation `[Part 1]` is used.

---

## Table of Contents

1. [Section 1: Communication Channels Connection Map](#section-1-communication-channels-connection-map)
2. [Section 2: Integration System Connections](#section-2-integration-system-connections)
3. [Section 3: Jarvis Command Center Connections](#section-3-jarvis-command-center-connections)
4. [Section 4: Analytics & Dashboard Connections](#section-4-analytics--dashboard-connections)
5. [Section 5: Agent Training Pipeline Connections](#section-5-agent-training-pipeline-connections)
6. [Section 6: Onboarding → Production Connection Path](#section-6-onboarding--production-connection-path)

---

# Section 1: Communication Channels Connection Map

> **Scope:** Features F-120 through F-130 — all channels through which customers and agents interact with PARWA.
>
> **Core Principle:** Every channel follows the **ingest → classify → route → respond → track** pipeline, but each has unique webhook providers, rate limits, consent requirements, and response delivery mechanisms.

---

## 1.1 Channel Ingestion Flow

All inbound customer messages, regardless of channel, ultimately land in the ticket system. The entry paths differ per channel:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CHANNEL INGESTION ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  EMAIL (Brevo)                                                          │
│    Brevo Parse Webhook                                                  │
│    → POST /webhooks/brevo/inbound [F-121]                              │
│    → Celery task: process_inbound_email(company_id, raw_payload)        │
│    → F-122 OOO Detection (check headers)                               │
│    → F-070 Customer Identity Resolution                                │
│    → F-052 Omnichannel Session (append to thread)                      │
│    → F-046 Ticket (create or append message)                           │
│    → F-062 Intent Classification [Part 1]                              │
│    → F-054 Smart Router [Part 1]                                       │
│                                                                         │
│  SMS (Twilio)                                                           │
│    Twilio SMS Webhook                                                   │
│    → POST /webhooks/twilio/sms [F-126]                                 │
│    → Celery task: process_inbound_sms(company_id, from, body)          │
│    → TCPA opt-in check (must have consent record)                      │
│    → F-070 Customer Identity Resolution                                │
│    → F-052 Omnichannel Session                                         │
│    → F-046 Ticket (create or append)                                   │
│                                                                         │
│  VOICE (Twilio)                                                         │
│    Twilio Voice Webhook                                                 │
│    → POST /webhooks/twilio/voice [F-127]                               │
│    → Celery task: process_inbound_call(company_id, call_sid)           │
│    → TCPA consent check + call recording consent                       │
│    → F-128 Incoming Call System (STT → AI → TTS)                       │
│    → F-052 Omnichannel Session                                         │
│    → F-046 Ticket (create with voice transcript)                       │
│                                                                         │
│  CHAT (Internal Widget)                                                 │
│    Socket.io connection via F-125 Chat Widget                          │
│    → socket.on('chat:message')                                         │
│    → F-070 Customer Identity Resolution                                │
│    → F-052 Omnichannel Session (real-time)                             │
│    → F-046 Ticket (create or append)                                   │
│    → Socket.io emit for AI streaming response                          │
│                                                                         │
│  SOCIAL (Twitter/X, Instagram, Facebook)                               │
│    Platform-specific Webhook                                            │
│    → POST /webhooks/social/{platform} [F-130]                         │
│    → Celery task: process_social_message(company_id, platform, msg)    │
│    → OAuth token validation                                            │
│    → F-070 Customer Identity Resolution                                │
│    → F-063 Sentiment Analysis [Part 1] (social posts carry sentiment)  │
│    → F-052 Omnichannel Session                                         │
│    → F-046 Ticket (create or append)                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Webhook Endpoint Specifications

| Channel | Endpoint | HTTP Method | Signature Verification | BC Compliance |
|---------|----------|-------------|----------------------|---------------|
| Email (Inbound) | `/webhooks/brevo/inbound` | POST | IP allowlist (Brevo IPs) | BC-003, BC-006 |
| SMS (Inbound) | `/webhooks/twilio/sms` | POST | X-Twilio-Signature HMAC | BC-003, BC-005 |
| Voice (Inbound) | `/webhooks/twilio/voice` | POST | X-Twilio-Signature HMAC | BC-003, BC-005 |
| Voice (Status) | `/webhooks/twilio/voice/status` | POST | X-Twilio-Signature HMAC | BC-003 |
| Chat | Socket.io `chat:message` event | WebSocket | JWT auth on connect | BC-005, BC-011 |
| Social (Twitter) | `/webhooks/social/twitter` | POST | OAuth 1.0a signature | BC-003 |
| Social (Instagram) | `/webhooks/social/instagram` | POST | App Secret HMAC | BC-003 |
| Social (Facebook) | `/webhooks/social/facebook` | POST | App Secret HMAC | BC-003 |
| Bounce/Complaint | `/webhooks/brevo/events` | POST | IP allowlist | BC-003, BC-006 |

### Celery Task Specifications for Channel Ingestion

Every channel ingestion task follows BC-004 (Background Jobs) patterns:

| Task Name | Queue | Timeout | Max Retries | DLQ on Failure |
|-----------|-------|---------|-------------|----------------|
| `process_inbound_email` | `email` | 30s | 3 | `dlq` |
| `process_inbound_sms` | `sms` | 15s | 3 | `dlq` |
| `process_inbound_call` | `voice` | 60s | 2 | `dlq` |
| `process_social_message` | `social` | 30s | 3 | `dlq` |
| `process_bounce_event` | `email` | 10s | 3 | `dlq` |

All tasks receive `company_id` as the first parameter per BC-001 and BC-004 rules.

---

## 1.2 Outbound Response Flow

When the AI generates a response (F-065 Auto-Response Generation, `[Part 1]`), the outbound path depends on the originating channel of the ticket:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    OUTBOUND RESPONSE ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  F-065 Auto-Response Generated                                          │
│    ↓                                                                    │
│  Channel Detection (read from ticket.channel field)                     │
│    ↓                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ EMAIL Response Path                                          │       │
│  │   → F-123 Rate Limit Check (5/thread/24h)                   │       │
│  │   → Check F-124 bounce status (is recipient valid?)          │       │
│  │   → Brevo API: POST /v3/smtp/email                          │       │
│  │   → Log to email_logs table (BC-006 rule 5)                 │       │
│  │   → Update ticket status via F-046                           │       │
│  │   → Emit Socket.io: ticket:message_sent                      │       │
│  └──────────────────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ SMS Response Path                                            │       │
│  │   → TCPA opt-in verification (F-029 consent records)        │       │
│  │   → Twilio API: POST /2010-04-01/Accounts/{sid}/Messages.json│       │
│  │   → Delivery tracking via Twilio status webhook              │       │
│  │   → Emit Socket.io: ticket:message_sent                      │       │
│  └──────────────────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ VOICE Response Path                                          │       │
│  │   → F-128 TTS synthesis (AI text → spoken audio)            │       │
│  │   → Twilio API: TwiML response with <Say> or <Play>         │       │
│  │   → Call recording storage (S3/GCS)                         │       │
│  │   → Emit Socket.io: ticket:voice_responded                  │       │
│  └──────────────────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ CHAT Response Path                                           │       │
│  │   → Socket.io emit: chat:ai_response (streamed)             │       │
│  │   → Token-by-token streaming for real-time typing feel       │       │
│  │   → F-066 AI Draft Composer available in co-pilot mode      │       │
│  │   → F-069 90% Capacity check (new thread needed?)           │       │
│  └──────────────────────────────────────────────────────────────┘       │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │ SOCIAL Response Path                                         │       │
│  │   → Platform API: POST comment/DM                           │       │
│  │   → Public vs. private routing (DMs for sensitive data)     │       │
│  │   → Platform rate limit respect                             │       │
│  │   → Emit Socket.io: ticket:social_responded                 │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Outbound Response Failure Handling

| Channel | Failure Scenario | Recovery Action | Connected Feature |
|---------|-----------------|-----------------|-------------------|
| Email | Brevo API timeout | Retry 3x (BC-006 rule 9), then alert ops | F-093 Self-Healing |
| Email | Bounce/complaint | Update contact status, stop sending | F-124 Bounce Handling |
| Email | Rate limit hit (5/thread/24h) | Queue for next 24h window | F-123 Rate Limiting |
| SMS | Twilio 429 rate limit | Retry with backoff via F-093 | F-093 Self-Healing |
| SMS | TCPA non-compliance | Block send, log violation, alert admin | F-083 Emergency Pause |
| Voice | Call drops mid-response | Log partial, mark ticket as needs-follow-up | F-053 GSD State Engine |
| Voice | TTS synthesis failure | Fallback to text SMS notification | F-094 Trust Preservation |
| Chat | Socket.io disconnection | Queue message in event_buffer, deliver on reconnect | BC-005 rule 2-3 |
| Social | Platform API error | Retry via F-139 Circuit Breaker | F-139 Circuit Breaker |

---

## 1.3 Cross-Channel Connections

Channels are not independent — several features stitch them together into a unified experience:

### F-070 Customer Identity Resolution

This is the **critical bridge** across all channels. Without it, a customer emailing and then calling would appear as two different people.

```
Identity Resolution Pipeline (F-070):
    Input: incoming message from any channel
    ↓
    Extract identifiers:
    ├── Email address (from, reply-to, body patterns)
    ├── Phone number (SMS from, voice caller ID, body patterns)
    ├── Social handle (@username, profile URL)
    ├── Account/order IDs (body text extraction via F-056 PII Redaction)
    └── Cookie/session ID (chat widget)
    ↓
    Match against customer_profiles table:
    ├── Exact match → merge into existing profile
    ├── Fuzzy match → confidence score → if > 85% → suggest merge
    └── No match → create new profile
    ↓
    Output: unified customer_id → attached to ticket
```

**Connected features:**
- F-062 Ticket Intent Classification `[Part 1]` — uses unified customer history
- F-056 PII Redaction Engine `[Part 1]` — extracts and redacts identifiers before matching
- F-121 Inbound Email Parsing — provides email address for matching
- F-126 SMS Handling — provides phone number for matching
- F-130 Social Media Integration — provides social handles for matching

### F-052 Omnichannel Sessions

Stitches messages from different channels into a single conversation thread:

```
Omnichannel Stitching Rules (F-052):

  Rule 1: Same customer_id + overlapping time window (72h) → merge
  Rule 2: Customer references previous ticket (parsed by F-062) → link
  Rule 3: Explicit channel handoff (agent transfers chat → voice) → merge
  Rule 4: Same email thread (In-Reply-To / References headers) → merge

  Channel context metadata preserved per message:
  {
    "channel": "email" | "sms" | "voice" | "chat" | "social",
    "channel_metadata": {
      "email_thread_id": "msg_xxx",       // email only
      "twilio_call_sid": "CA_xxx",        // voice only
      "twilio_message_sid": "SM_xxx",     // SMS only
      "social_post_id": "tweet_xxx",      // social only
      "socket_session_id": "sess_xxx",    // chat only
      "recording_url": "https://...",     // voice only
      "attachment_urls": [...]            // all channels
    },
    "timestamp": "2026-03-15T10:30:00Z"
  }
```

### F-122 Out-of-Office / Auto-Reply Detection

Email-specific feature that prevents the AI from responding to automated messages:

```
OOO Detection Pipeline (F-122):
    Inbound email received
    ↓
    Check headers:
    ├── X-Auto-Response-Suppress: present? → STOP
    ├── Auto-Submitted: present? → STOP
    ├── Subject contains "Out of Office" / "Auto Reply"? → flag for review
    └── Body matches OOO template patterns? → flag for review
    ↓
    If OOO detected:
    → Do NOT create ticket
    → Do NOT trigger AI response
    → Log to email_logs with status = "ooo_ignored"
    → Return 200 to webhook (prevent retry)
```

**Connection point:** F-122 runs INSIDE the `process_inbound_email` Celery task BEFORE ticket creation. It does not connect to any other channel — it is email-only.

---

## 1.4 Channel Feature Connection Matrix

| Channel Feature | Ingests From | Sends To | Triggers AI | Rate Limit | Webhook Provider | BC Codes |
|----------------|-------------|----------|-------------|-----------|-----------------|----------|
| F-121 Email Inbound | Brevo Parse | F-046 Ticket | Yes (F-062, F-054) | 5/thread/24h (F-123) | Brevo (IP allowlist) | BC-003, BC-006 |
| F-120 Email Outbound | F-065 Response | Brevo API | No | 5/customer/hour | N/A (outbound) | BC-006 |
| F-126 SMS | Twilio | F-046 Ticket | Yes (F-062, F-054) | TCPA opt-in required | Twilio (HMAC) | BC-005, BC-010, BC-011 |
| F-127 Voice | Twilio | F-046 Ticket | Yes (F-128 STT→AI→TTS) | TCPA consent required | Twilio (HMAC) | BC-005, BC-010, BC-007 |
| F-128 Voice-First | F-127 | F-065 Response | Yes (core AI pipeline) | Call duration limit | Twilio (TwiML) | BC-005, BC-007 |
| F-125 Chat Widget | Internal Socket.io | F-046 Ticket | Yes (F-062, F-054) | 10 messages/visitor | None (WebSocket) | BC-005, BC-001, BC-011 |
| F-130 Social | Twitter/IG/FB | F-046 Ticket | Yes (F-062, F-063, F-054) | Platform rate limits | Platform OAuth | BC-005, BC-001, BC-003 |
| F-122 OOO Detection | F-121 | STOP (no ticket) | No | N/A | N/A | BC-006, BC-007 |
| F-123 Email Rate Limit | F-120 | Block queue | No | 5/thread/24h | N/A | BC-006, BC-012 |
| F-124 Bounce Handler | Brevo events | F-010 customer status | No | N/A | Brevo (IP allowlist) | BC-006, BC-010 |

---

## 1.5 Channel → Core System Dependency Map

```
                              ┌──────────────────┐
                              │   F-046 Ticket    │
                              │   Management      │
                              │   [Part 1]        │
                              └────────┬─────────┘
                                       │
                  ┌────────────────────┼────────────────────┐
                  │                    │                    │
           ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
           │  F-062      │     │  F-050      │     │  F-052      │
           │  Intent     │     │  Assignment │     │  Omnichannel│
           │  Classify   │     │  [Part 1]   │     │  Sessions   │
           └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
                  │                    │                    │
           ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
           │  F-054      │     │  F-097      │     │  F-070      │
           │  Smart      │     │  Agent      │     │  Identity   │
           │  Router     │     │  Dashboard  │     │  Resolution │
           └──────┬──────┘     └─────────────┘     └─────────────┘
                  │
           ┌──────▼──────┐
           │  F-065      │
           │  Auto-      │
           │  Response   │
           └──────┬──────┘
                  │
    ┌─────────────┼─────────────┬─────────────┐
    │             │             │             │
┌───▼───┐   ┌────▼───┐   ┌────▼───┐   ┌────▼───┐
│F-120  │   │F-126   │   │F-128   │   │F-125   │
│Email  │   │SMS     │   │Voice   │   │Chat    │
│Out    │   │Out     │   │Out     │   │Out     │
└───────┘   └────────┘   └────────┘   └────────┘
```

---

# Section 2: Integration System Connections

> **Scope:** Features F-131 through F-139 — how PARWA connects to external systems and platforms.
>
> **Core Principle:** Every outbound integration call passes through the Circuit Breaker (F-139). Combined with the Health Monitor (F-137) and Trust Preservation Protocol (F-094 `[Part 1]`), external failures never cascade into customer-facing breakdowns.

---

## 2.1 Pre-built Integration Connections (F-131)

F-131 contains ready-to-use connectors. Each connector has a specific data flow into PARWA's core systems:

### Connector → Core System Mapping

| Pre-built Connector | Authentication | Data Sync Direction | Core Feature Connected | Sync Method | BC Compliance |
|---------------------|---------------|--------------------|-----------------------|-------------|---------------|
| Zendesk | OAuth 2.0 | Bidirectional | F-046 Ticket List | Polling (5 min) + webhook | BC-003 |
| Freshdesk | API Key | Bidirectional | F-046 Ticket List | Polling (5 min) + webhook | BC-003 |
| Intercom | OAuth 2.0 | Bidirectional | F-052 Omnichannel | Real-time webhook | BC-003, BC-005 |
| Slack | OAuth 2.0 | Outbound only | F-037 Activity Feed | Outgoing webhook (F-138) | BC-003, BC-005 |
| Shopify | OAuth 2.0 | Inbound | F-070 Identity + F-046 | Real-time webhook | BC-003 |
| GitHub | OAuth 2.0 | Inbound | F-046 Ticket List | Real-time webhook | BC-003 |
| Stripe | API Key | Inbound | F-072 Subscription Proration | Webhook | BC-003, BC-002 |
| TMS/WMS | API Key | Bidirectional | F-064 RAG Context | Polling (15 min) | BC-003, BC-004 |

### Data Flow: Shopify → PARWA Example

```
Shopify Integration Data Flow:

  Customer places order on Shopify store
    ↓
  Shopify webhook: orders/create → POST /webhooks/shopify/orders
    ↓ (BC-003: HMAC verification, idempotency check)
  Celery task: process_shopify_order(company_id, order_data)
    ↓
  Enrich customer profile:
    → F-070: match customer by email → attach order history
    → F-046: if support ticket exists, add order context
    → F-064: index order FAQ for RAG retrieval
    ↓
  Emit Socket.io: integration:shopify:order_synced
    ↓
  F-137: log successful sync, update health status
```

### Data Flow: Slack → PARWA Example

```
Slack Integration Data Flow (Outbound):

  PARWA event occurs (ticket created, AI resolved, escalation)
    ↓
  F-037 Activity Feed generates event
    ↓
  F-138 Outgoing Webhook checks Slack integration config
    ↓
  Slack channel mapping (configurable per event type):
    → ticket:created → #support-tickets
    → ticket:ai_resolved → #support-ai
    → approval:pending → #approvals
    → system:alert → #ops-alerts
    ↓
  POST https://hooks.slack.com/services/xxx
    ↓ (wrapped in F-139 Circuit Breaker)
  F-137: log delivery status
```

---

## 2.2 Custom Integration Connections

### F-132 REST API Connector

```
F-132 Architecture:

  User configures REST integration in UI:
    ├── Endpoint URL
    ├── HTTP Method (GET, POST, PUT, DELETE, PATCH)
    ├── Headers (auth tokens, content-type)
    ├── Body template (with {{ticket.field}} variables)
    ├── Response mapping (JSON path → PARWA field)
    └── Retry policy (default: 3 retries)
    ↓
  Stored in: custom_integrations table
    {
      "id": "int_xxx",
      "company_id": "comp_xxx",
      "type": "rest",
      "config": { "url": "...", "method": "POST", ... },
      "triggers": ["ticket:created", "ticket:resolved"],
      "status": "active"
    }
    ↓
  When trigger fires:
    → F-134 Webhook Integration checks triggers → matches
    → F-132 builds request from template
    → F-139 Circuit Breaker wraps the outbound call
    → Response parsed per mapping config
    → Result logged in connector_usage_logs
    ↓
  Connection to BC-003 rules:
    → F-138 outgoing webhooks also use F-132 for HTTP delivery
```

### F-133 GraphQL Connector

```
F-133 Architecture:

  Same pattern as F-132 but with:
    ├── Query/Mutation builder UI
    ├── Variables mapping ({{ticket.field}} → $variable)
    ├── Subscription support (real-time via WebSocket)
    └── Schema introspection for field discovery

  Connected features:
    → F-132 REST: shares connector_usage_logs table
    → F-137 Health: monitors GraphQL endpoint health
    → F-139 Circuit Breaker: wraps all GraphQL calls
```

### F-134 Webhook Integration (Incoming)

```
F-134 Incoming Webhook Architecture:

  External system → POST /webhooks/custom/{integration_id}
    ↓
  BC-003 Verification:
    ├── HMAC signature check (if secret configured)
    ├── IP allowlist check (if configured)
    ├── Rate limit check (100/minute per integration)
    └── Idempotency check (webhook_events table)
    ↓
  Payload transformation (user-configured mapping):
    ├── Extract fields from JSON body
    ├── Map to PARWA data model
    └── Validate required fields
    ↓
  Route to workflow:
    ├── Create ticket → F-046
    ├── Update ticket → F-046
    ├── Trigger automation → F-060 LangGraph `[Part 1]`
    └── Store as data point → F-064 RAG
    ↓
  Celery task: process_custom_webhook(company_id, integration_id, payload)
  → logged in connector_usage_logs
  → health tracked by F-137
```

### F-135 MCP Integration (Model Context Protocol)

```
F-135 MCP Architecture:

  MCP allows AI agents to use external tools as part of their reasoning:

  Agent receives ticket → F-054 Smart Router processes
    ↓
  F-135 checks available MCP tools for this tenant:
    ├── Shopify: lookup_order(order_id)
    ├── Stripe: get_payment_status(customer_id)
    ├── GitHub: get_issue_status(issue_number)
    └── Custom: any MCP-exposed tool
    ↓
  Tool results injected into AI context (F-064 RAG augmentation):
    → Agent can now reference real-time external data
    → "Your order #12345 is currently in transit"
    ↓
  Response generation with external data context
    ↓
  Connected features:
    → F-054 Smart Router: MCP tools augment routing context
    → F-060 LangGraph: MCP calls are nodes in the workflow graph
    → F-064 RAG: MCP results join KB search results
    → F-096 Dynamic Instructions: MCP tools configurable per agent
```

### F-136 Database Connection Integration

```
F-136 Architecture:

  Direct database connections for real-time data lookups:

  Configured in: db_connections table
    {
      "id": "dbc_xxx",
      "company_id": "comp_xxx",
      "type": "postgresql" | "mysql" | "mongodb" | "redis",
      "host": "db.customer.com",
      "port": 5432,
      "database": "production",
      "connection_pool_size": 5,
      "read_only": true,         // ALWAYS read-only
      "allowed_tables": ["orders", "products", "customers"],
      "query_timeout_ms": 5000
    }
    ↓
  Connection pool per integration (ConnectionPool per BC-004)
    ↓
  Used by:
    → F-064 RAG: real-time KB augmentation from customer DB
    → F-135 MCP: SQL query as MCP tool
    → F-054 Smart Router: context enrichment
    ↓
  Security: 
    → Read-only connections ONLY (enforced at connection level)
    → Table-level allowlisting (never expose full schema)
    → Query timeout enforcement (5s max)
    → Connection via encrypted tunnel
    → BC-011: credentials encrypted at rest (AES-256)
```

---

## 2.3 Operational Integration Features

### F-137 Integration Health Monitor

```
F-137 Health Check Pipeline:

  Celery beat schedule (every 60 seconds):
    → check_integration_health(company_id)
    ↓
  For each active integration:
    ├── REST/GraphQL: HEAD request to health endpoint
    ├── Webhook (incoming): verify last received timestamp < 5 min
    ├── MCP: ping MCP server
    ├── DB: SELECT 1
    └── Slack: test webhook delivery
    ↓
  Health status stored in: integration_health table
    {
      "integration_id": "int_xxx",
      "status": "healthy" | "degraded" | "down",
      "latency_ms": 120,
      "last_check": "2026-03-15T10:30:00Z",
      "consecutive_failures": 0,
      "error_message": null
    }
    ↓
  Consumers of F-137 data:
    → F-088 System Status Panel `[Part 1]` — displays integration health
    → F-037 Activity Feed — emits integration:status_changed events
    → F-139 Circuit Breaker — reads failure count for open/close decisions
    → F-093 Self-Healing — triggers recovery when status = "degraded"
```

### F-138 Outgoing Webhooks

```
F-138 Outgoing Webhook Architecture:

  PARWA internal event bus → F-138 checks subscriber list
    ↓
  Events available for subscription:
    ├── ticket:created
    ├── ticket:resolved
    ├── ticket:escalated
    ├── approval:pending
    ├── approval:approved
    ├── approval:rejected
    ├── agent:training_complete
    ├── integration:sync_complete
    └── system:alert
    ↓
  For each subscriber:
    → Build payload from event template
    → F-139 Circuit Breaker wraps HTTP POST
    → Log delivery in webhook_delivery_logs
    → On failure: retry 3x with exponential backoff (BC-003)
    ↓
  Connection to BC-003 rules:
    → Signature header: X-Parwa-Signature (HMAC-SHA256)
    → Idempotency: webhook_events table (outbound direction)
    → Timeout: 5s per delivery attempt
```

### F-139 Circuit Breaker

```
F-139 Circuit Breaker State Machine:

  ┌──────────┐     failures >= 5      ┌──────────┐
  │  CLOSED  │ ──────────────────────→ │   OPEN   │
  │ (normal) │                         │(blocked) │
  └──────────┘                         └──────────┘
       ↑                                    │ cooldown
       │                              60s timer expires
       │                                    │
       │                              ┌─────▼──────┐
       │                              │ HALF-OPEN   │
       │◄────────── 1 success ────────│ (testing)   │
       │                              └─────────────┘
                                    │ failure
                                    ↓
                               Returns to OPEN

  Per-integration circuit breaker state:
  {
    "integration_id": "int_xxx",
    "state": "closed",               // closed | open | half_open
    "failure_count": 0,              // consecutive failures
    "last_failure": null,
    "opened_at": null,
    "cooldown_seconds": 60,
    "half_open_successes_needed": 3  // must succeed 3x to close
  }

  Every outbound call flow:
    → F-132/F-133/F-134/F-135/F-138 wants to make call
    → Checks F-139 state for that integration
    → CLOSED: allow call, track result
    → OPEN: return fallback response immediately (no call)
    → HALF_OPEN: allow call, if success → increment counter
      → if 3 successes → CLOSED
      → if 1 failure → OPEN (reset cooldown)
    ↓
  Connected features:
    → ALL integration features (F-131 through F-138)
    → F-093 Self-Healing: monitors circuit breaker state
    → F-094 Trust Preservation: provides fallback responses when OPEN
    → F-088 System Status: displays circuit breaker state
```

---

## 2.4 Integration → Core System Connection Table

| Integration Feature | Core Feature Connected | Data Flow Direction | DB Tables Written | Impact if Integration Fails | Recovery Feature |
|---------------------|----------------------|--------------------|-------------------|---------------------------|------------------|
| F-132 REST Connector | F-046 Ticket List | Bidirectional | connector_usage_logs | Circuit breaker activates | F-139 → F-093 |
| F-133 GraphQL | F-046, F-064 RAG | Bidirectional | connector_usage_logs | Circuit breaker activates | F-139 → F-093 |
| F-134 Webhook In | F-046 Tickets, F-060 LangGraph | Inbound (external→PARWA) | webhook_events, tickets | New tickets/events missed | F-137 alerts → F-093 |
| F-135 MCP | F-054 Smart Router, F-064 RAG | Inbound (tools→AI) | mcp_tool_logs | AI loses external tool capabilities | F-094 Trust Preservation |
| F-136 DB Connection | F-064 RAG, F-070 Identity | Inbound (data lookup) | db_connection_logs | RAG context incomplete | F-064 falls back to KB only |
| F-137 Health Monitor | F-088 System Status | Inbound (monitoring) | integration_health | Blind spot in monitoring | N/A (it IS the monitor) |
| F-138 Webhook Out | BC-003 rules, external systems | Outbound (PARWA→external) | webhook_delivery_logs | External systems not notified | F-139 retry → DLQ |
| F-139 Circuit Breaker | All integrations | Protective wrapper | circuit_breaker_state | No protection from cascade failures | N/A (it IS the protection) |

---

## 2.5 Integration Dependency Graph

```
                    ┌───────────────────────────────────┐
                    │        EXTERNAL SYSTEMS           │
                    │  Shopify, Zendesk, Stripe, etc.   │
                    └───────────┬───────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
        ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
        │  F-131    │   │  F-134    │   │  F-138      │
        │  Pre-built│   │  Webhook  │   │  Outgoing   │
        │  Connectors│  │  Incoming │   │  Webhooks   │
        └─────┬─────┘   └─────┬─────┘   └──────┬──────┘
              │               │                 │
        ┌─────▼─────┐   ┌─────▼─────┐   ┌──────▼──────┐
        │  F-132    │   │  F-135    │   │             │
        │  REST     │   │  MCP      │   │             │
        └─────┬─────┘   └─────┬─────┘   │             │
              │               │          │             │
        ┌─────▼─────┐   ┌─────▼─────┐   │             │
        │  F-133    │   │  F-136    │   │             │
        │  GraphQL  │   │  DB Conn  │   │             │
        └─────┬─────┘   └─────┬─────┘   │             │
              │               │          │             │
              └───────────────┼──────────┘             │
                              │                        │
                    ┌─────────▼──────────┐             │
                    │     F-139          │◄────────────┘
                    │  Circuit Breaker   │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
        │  F-137    │   │  F-093    │   │  F-094    │
        │  Health   │   │  Self-    │   │  Trust    │
        │  Monitor  │   │  Healing  │   │  Preserv. │
        └─────┬─────┘   └───────────┘   └───────────┘
              │
        ┌─────▼─────┐
        │  F-088    │
        │  System   │
        │  Status   │
        └───────────┘
```

---

# Section 3: Jarvis Command Center Connections

> **Scope:** Features F-087 through F-096 — the natural language command layer that wraps the entire PARWA platform.
>
> **Core Principle:** Jarvis (F-087) is a **read/write API layer expressed in natural language**. Every NL command maps to one or more specific feature actions. The Quick Commands (F-090) are pre-parsed shortcuts that bypass NL parsing.

---

## 3.1 Jarvis NL Command → Feature Mapping

F-087 processes natural language through F-054 Smart Router (Medium tier) to parse intent and dispatch to target features:

### Command Dispatch Table

| Natural Language Command | Parsed Intent | Target Feature(s) | API Calls Generated | Actions Performed | Requires Approval |
|-------------------------|--------------|-------------------|---------------------|-------------------|-------------------|
| "show refund tickets" | `ticket_filter` | F-046, F-048 | `GET /api/tickets?intent=refund&status=open` | Filter + display in chat | No (read-only) |
| "show tickets from last week" | `ticket_filter` | F-046, F-110 | `GET /api/tickets?from=7d` | Filter with time range | No (read-only) |
| "pause email channel" | `channel_control` | F-083 Emergency Pause | `POST /api/channels/email/pause` | Pause outbound emails | No (admin action) |
| "pause all channels" | `emergency_stop` | F-083 Emergency Pause | `POST /api/emergency/pause-all` | Pause all AI outbound | No (admin action) |
| "resume email channel" | `channel_control` | F-083 Emergency Pause | `POST /api/channels/email/resume` | Resume outbound emails | No (admin action) |
| "create returns agent" | `agent_creation` | F-095, F-097, F-099 | `POST /api/agents` → Paddle checkout | Provision + configure new agent | Yes (via F-078) |
| "show system health" | `system_status` | F-088 System Status | `GET /api/system/status` | Display subsystem health | No (read-only) |
| "show last 5 errors" | `error_log` | F-091 Last 5 Errors | `GET /api/errors?limit=5` | Display error details | No (read-only) |
| "approve all pending" | `batch_approval` | F-075, F-074 | `POST /api/approval/batch-approve` | Batch approve queue | **Yes** (F-078 confirm) |
| "reject all pending" | `batch_reject` | F-074 | `POST /api/approval/batch-reject` | Batch reject queue | **Yes** (F-078 confirm) |
| "train agent from errors" | `training_trigger` | F-092, F-103, F-100 | `POST /api/training/trigger` | Start training pipeline | No (admin action) |
| "what happened to ticket 123" | `ticket_lookup` | F-047, F-048 | `GET /api/tickets/123` | Display ticket detail + thread | No (read-only) |
| "disable auto-approve" | `config_change` | F-077 Auto-Handle | `PUT /api/config/auto-handle` | Update auto-handle rules | **Yes** (F-078 confirm) |
| "show agent performance" | `agent_metrics` | F-097, F-098 | `GET /api/agents/metrics` | Display per-agent analytics | No (read-only) |
| "export analytics report" | `export_data` | F-117 | `POST /api/analytics/export` | Generate CSV/PDF export | No (admin action) |
| "check drift status" | `drift_check` | F-116 | `GET /api/analytics/drift` | Display drift report | No (read-only) |
| "create instruction set" | `instruction_create` | F-096 | `POST /api/instructions` | Create new instruction version | No (admin action) |
| "show GSD state for ticket 456" | `gsd_debug` | F-089 GSD State Terminal | `GET /api/gsd/state?ticket_id=456` | Display state machine debug | No (read-only) |

### NL Parsing Pipeline

```
Jarvis NL Command Processing (F-087):

  User types: "show refund tickets from VIP customers"
    ↓
  F-054 Smart Router (Medium tier) parses intent:
    {
      "intent": "ticket_filter",
      "entities": {
        "intent_filter": "refund",
        "customer_tier": "VIP",
        "action": "display"
      },
      "confidence": 0.94,
      "target_features": ["F-046", "F-048"],
      "api_calls": [
        "GET /api/tickets?intent=refund&tier=vip&status=open"
      ]
    }
    ↓
  Permission check (BC-011):
    → Is user authorized for this action?
    → Is this a read-only query? (no approval needed)
    → Is this a destructive action? (requires F-078 confirmation)
    ↓
  Execute API calls → collect results
    ↓
  F-054 formats response in natural language:
    "Found 12 open refund tickets from VIP customers. 
     3 are pending approval. The oldest is 4 hours old. 
     Want me to approve them all?"
    ↓
  Display in Jarvis chat panel
```

---

## 3.2 Jarvis → System Connection Map

Every Jarvis feature connects to specific subsystems:

### Read Connections (Jarvis reads data)

| Jarvis Feature | Reads From | Data Retrieved | Update Frequency |
|---------------|-----------|---------------|-----------------|
| F-087 NL Commands | F-088 System Status | Subsystem health | On-demand |
| F-087 NL Commands | F-089 GSD State Terminal | State machine state | On-demand |
| F-087 NL Commands | F-091 Last 5 Errors | Error stack traces | On-demand |
| F-087 NL Commands | F-046 Ticket List | Ticket data | On-demand |
| F-087 NL Commands | F-097 Agent Dashboard | Agent status | On-demand |
| F-087 NL Commands | F-098 Performance Metrics | Agent metrics | On-demand |
| F-087 NL Commands | F-074 Approval Queue | Pending approvals | On-demand |
| F-087 NL Commands | F-116 Drift Detection | Drift reports | On-demand |
| F-088 System Status | F-137 Integration Health | Integration status | Polling (30s) |
| F-088 System Status | F-055 Model Failover `[Part 1]` | LLM provider status | Polling (15s) |
| F-088 System Status | F-139 Circuit Breaker | Circuit states | Polling (30s) |
| F-089 GSD State Terminal | F-053 GSD State Engine `[Part 1]` | Active GSD sessions | Socket.io (real-time) |
| F-091 Last 5 Errors | error_logs table | Recent errors | Socket.io (real-time) |

### Write Connections (Jarvis modifies state)

| Jarvis Feature | Writes To | Action Performed | Approval Required |
|---------------|----------|-----------------|-------------------|
| F-087 NL Commands | F-083 Emergency Pause | Pause/resume channels | No (admin-only) |
| F-087 NL Commands | F-075 Batch Approval | Batch approve tickets | **Yes** (F-078) |
| F-087 NL Commands | F-074 Approval Queue | Approve/reject individual | **Yes** (F-076) |
| F-087 NL Commands | F-077 Auto-Handle Rules | Modify auto-approve config | **Yes** (F-078) |
| F-087 NL Commands | F-092 Train from Error | Trigger training | No (admin-only) |
| F-087 NL Commands | F-117 Export | Generate analytics export | No (admin-only) |
| F-095 Create Agent | F-099 Add/Scale Agent | Provision new agent | Yes (via F-078) |
| F-095 Create Agent | F-100 Training Loop | Start agent training | Automatic after provision |
| F-095 Create Agent | F-097 Agent Dashboard | Add agent card | Automatic |
| F-096 Instructions | F-060 LangGraph `[Part 1]` | Update agent instructions | No (admin-only) |

---

## 3.3 Jarvis Agent Creation Flow (F-095)

```
F-095 "Create Agent" NL Command Flow:

  User: "create a returns specialist agent"
    ↓
  F-087 parses intent → agent_creation
    ↓
  F-095 extracts parameters:
    ├── agent_name: "Returns Specialist"
    ├── specialty: "returns, refunds, exchanges"
    ├── permissions: ["ticket:read", "ticket:write", "refund:process"]
    └── integration_access: ["shopify", "stripe"]
    ↓
  Display confirmation (F-078 Auto-Approve Confirmation):
    ├── Agent name + specialty
    ├── Estimated monthly cost (via F-099 → F-020 Paddle)
    ├── Permissions list
    └── Integration access list
    ↓
  User confirms
    ↓
  F-099 Add/Scale Agent:
    ├── POST /api/agents (create agent record)
    ├── F-020 Paddle Checkout: charge for additional agent
    ├── Paddle webhook → F-022 confirms payment
    ├── Assign default instructions (F-096)
    └── Assign integration access (F-131, F-135)
    ↓
  F-100 Lightning Training Loop:
    ├── F-103 Dataset Preparation (filter tickets matching specialty)
    ├── F-102 Training Run Execution (train on specialized data)
    ├── F-104 Model Validation (test against holdout)
    └── F-105 Model Deployment (deploy to production)
    ↓
  F-097 Agent Dashboard: new agent card appears (status: "active")
  F-037 Activity Feed: emit agent:created event
  F-088 System Status: update active agent count
```

---

## 3.4 Quick Commands (F-090)

F-090 provides one-click preset buttons that bypass NL parsing. Each maps to a direct API call:

| Button Label | API Call | HTTP Method | Feature Target | Effect |
|-------------|----------|-------------|----------------|--------|
| Pause All | `/api/emergency/pause-all` | POST | F-083 | Pauses AI on all channels |
| Resume All | `/api/emergency/resume-all` | POST | F-083 | Resumes AI on all channels |
| Export Report | `/api/analytics/export` | POST | F-117 | Generates CSV/PDF of current view |
| Check Health | `/api/system/status` | GET | F-088 | Refreshes system status display |
| Clear Queue | `/api/approval/clear-queue` | POST | F-074 | Clears all pending approvals |
| Show Errors | `/api/errors?limit=5` | GET | F-091 | Refreshes last 5 errors panel |
| Train Agent | `/api/training/trigger` | POST | F-092 | Starts training from recent errors |
| New Agent | `/api/agents/create` | POST | F-095 | Opens guided agent creation flow |

### F-090 Button → F-087 NL Equivalent Mapping

```
Quick Command                    NL Equivalent
─────────────                    ──────────────
[Pause All]             →       "pause all channels"
[Resume All]            →       "resume all channels"
[Export Report]         →       "export analytics report"
[Check Health]          →       "show system health"
[Clear Queue]           →       "approve all pending" (with confirmation)
[Show Errors]           →       "show last 5 errors"
[Train Agent]           →       "train agent from errors"
[New Agent]             →       "create a new agent"
```

---

## 3.5 Self-Healing & Trust Preservation Connections

### F-093 Proactive Self-Healing → Monitor Targets

```
F-093 monitors these subsystems continuously:

  ┌──────────────────────────────────────────────────┐
  │              F-093 SELF-HEALING MONITORS         │
  ├──────────────────────────────────────────────────┤
  │                                                  │
  │  1. F-055 Model Failover [Part 1]               │
  │     → Track: consecutive_failures per model      │
  │     → Action: if > 10 fails → alert F-088       │
  │     → Action: if ALL models down → F-083 pause  │
  │                                                  │
  │  2. F-137 Integration Health                    │
  │     → Track: status of all integrations         │
  │     → Action: if integration DOWN → F-139 open  │
  │     → Action: auto-retry after cooldown          │
  │                                                  │
  │  3. F-139 Circuit Breaker                       │
  │     → Track: circuit states per integration     │
  │     → Action: HALF_OPEN testing                 │
  │     → Action: auto-close on 3 consecutive OK    │
  │                                                  │
  │  4. Celery Queue Depth                           │
  │     → Track: queue lengths (default, email, sms) │
  │     → Action: if > 1000 → scale workers alert   │
  │     → Action: if DLQ growing → ops alert        │
  │                                                  │
  │  5. Redis Health                                │
  │     → Track: response time, memory usage         │
  │     → Action: if degraded → alert ops            │
  │                                                  │
  └──────────────────────────────────────────────────┘
```

### F-094 Trust Preservation Protocol → Failure Interception

```
F-094 activates when external systems fail mid-conversation:

  Customer asks: "What's the status of my order?"
    ↓
  F-054 routes to AI with MCP tools (F-135) → calls Shopify API
    ↓
  Shopify returns 500 (or F-139 Circuit Breaker is OPEN)
    ↓
  F-094 Trust Preservation intercepts:
    ├── NEVER say: "Sorry, our system is down"
    ├── NEVER say: "I can't access that information"
    ├── INSTEAD: "Let me look into that for you. I'll have an 
    │   update shortly." (reassuring, human-like)
    ├── Queue the action: store pending_lookup in Redis
    │   → key: parwa:{company_id}:pending_lookup:{ticket_id}
    └── Trigger F-093 Self-Healing to recover
    ↓
  When Shopify recovers (F-137 status → "healthy"):
    → F-093 processes pending_lookups
    → F-065 generates response with order data
    → Response delivered to customer via original channel
    ↓
  Connected features:
    → F-054 Smart Router: F-094 wraps the entire response pipeline
    → F-065 Auto-Response: F-094 provides fallback templates
    → F-139 Circuit Breaker: F-094 reads circuit state
    → F-052 Omnichannel: F-094 ensures response goes to correct channel
```

---

# Section 4: Analytics & Dashboard Connections

> **Scope:** Dashboard widgets (F-036 through F-045) and analytics features (F-109 through F-119).
>
> **Core Principle:** Analytics features are **pure consumers** — they read data produced by operational features but never write operational state. Dashboard widgets are the **presentation layer** that renders analytics data via REST or Socket.io.

---

## 4.1 Data Sources → Analytics Consumers

### Primary Data Flow Map

| Data Source (Producer) | Analytics Consumer | Data Type | Refresh Method | DB Tables Read | Celery Beat Schedule |
|-----------------------|-------------------|-----------|---------------|----------------|---------------------|
| F-046 Ticket List `[Part 1]` | F-109 Analytics Overview | Ticket counts, status distribution | Celery beat (5 min) | tickets, ticket_messages | `refresh_analytics_overview` |
| F-046 Ticket List `[Part 1]` | F-111 Key Metrics Cards | KPI aggregation | Materialized view (5 min) | tickets (materialized) | `refresh_key_metrics` |
| F-046 Ticket List `[Part 1]` | F-112 Trend Charts | Time series data | Materialized view (1 hr) | tickets (materialized) | `refresh_trend_data` |
| F-046 + F-020 Billing `[Part 1]` | F-113 ROI Dashboard | Cost savings, financial impact | Celery beat (15 min) | tickets, subscriptions, overages | `refresh_roi_dashboard` |
| F-059 Confidence Scoring `[Part 1]` | F-115 Confidence Trend | AI confidence distribution | Celery beat (5 min) | confidence_scores | `refresh_confidence_trend` |
| F-059 + F-098 Agent Performance | F-116 Drift Detection | Model drift indicators | Celery beat (daily at 02:00) | confidence_scores, agent_metrics | `generate_drift_report` |
| F-098 Agent Performance Metrics | F-114 Before/After Comparison | Performance delta | On-demand + post-training | agent_metrics, agent_metrics_history | On-demand (POST trigger) |
| F-119 Post-Interaction QA | F-118 Quality Coach Reports | Quality metrics per agent | Celery beat (hourly) | qa_scores, agent_metrics | `generate_quality_reports` |
| F-117 Analytics Export | External (CSV/PDF) | Formatted data | On-demand | All analytics tables | On-demand (POST trigger) |

### Data Pipeline Detail: F-113 ROI Dashboard

```
F-113 ROI Calculation Pipeline:

  Inputs needed:
    ├── Total tickets resolved by AI (from tickets table)
    ├── Total tickets resolved by humans (from tickets table)
    ├── Cost per AI-resolved ticket (configured, default $0.15)
    ├── Cost per human-resolved ticket (configured, default $12.00)
    ├── Agent subscription cost (from F-020 Paddle data)
    └── Overage charges (from F-024 overages table)

  Calculation (per company, per time range):
    ai_resolved = COUNT(tickets WHERE resolved_by = 'ai')
    human_resolved = COUNT(tickets WHERE resolved_by = 'human')
    ai_cost = ai_resolved * 0.15
    human_equivalent_cost = (ai_resolved + human_resolved) * 12.00
    platform_cost = agent_subscription + overages
    total_saved = human_equivalent_cost - (ai_cost + platform_cost)
    roi_percentage = (total_saved / human_equivalent_cost) * 100

  Output:
    {
      "total_saved": 45230.50,
      "roi_percentage": 78.4,
      "ai_resolved_count": 3842,
      "human_resolved_count": 891,
      "platform_cost": 1250.00,
      "period": "2026-03"
    }
    ↓
  Stored in: analytics_roi table (monthly snapshots)
  Consumed by: F-040 Running Savings Widget (cumulative from snapshots)
```

### Data Pipeline Detail: F-116 Drift Detection

```
F-116 Drift Detection Pipeline:

  Daily at 02:00 UTC → Celery beat triggers:
    ↓
  Step 1: Collect metrics for last 30 days
    ├── F-098: agent resolution rate trend
    ├── F-059: confidence score distribution trend
    ├── F-119: QA score trend
    └── F-074: approval rejection rate trend
    ↓
  Step 2: Calculate drift indicators
    ├── confidence_drift = |mean_confidence(d7) - mean_confidence(d28)|
    ├── resolution_drift = |resolution_rate(d7) - resolution_rate(d28)|
    ├── qa_drift = |mean_qa_score(d7) - mean_qa_score(d28)|
    └── rejection_drift = |rejection_rate(d7) - rejection_rate(d28)|
    ↓
  Step 3: Composite drift score (0-100)
    drift_score = weighted_average(confidence_drift, resolution_drift,
                                    qa_drift, rejection_drift)
    weights = [0.3, 0.3, 0.2, 0.2]
    ↓
  Step 4: Threshold check
    ├── drift_score < 30 → "healthy" (no action)
    ├── 30 ≤ drift_score < 70 → "watching" (log, alert via F-037)
    └── drift_score ≥ 70 → "critical" (alert admin, suggest training)
    ↓
  Step 5: Store drift report
    → analytics_drift table
    → If critical: emit Socket.io event drift:alert
    → If critical: send email notification via F-006 Brevo
    ↓
  Connected downstream features:
    → F-101 50-Mistake Threshold: drift data feeds threshold check
    → F-106 Time-Based Fallback: drift report validates retraining need
    → F-087 Jarvis: "check drift status" reads this report
    → F-118 Quality Coach: uses drift data for coaching recommendations
```

---

## 4.2 Dashboard Widget Connection Map

### Widget → Data Source → Transport Table

| Widget | Feature ID | Data Source Feature(s) | Socket.io Events | Polling Fallback | DB Tables |
|--------|-----------|----------------------|-----------------|-----------------|-----------|
| Dashboard Home | F-036 | All widgets (container) | — | REST GET `/api/dashboard` | dashboard_config |
| Activity Feed | F-037 | All features (event_buffer) | `event:new` | REST GET `/api/events?page=N` | event_buffer |
| Key Metrics | F-038 | F-109, F-111 | `metrics:updated` | REST GET `/api/metrics` | analytics_overview |
| Adaptation Tracker | F-039 | F-098, F-101 | — | REST GET `/api/adaptation` | agent_metrics, drift_reports |
| Running Savings | F-040 | F-113 ROI | `savings:updated` | REST GET `/api/savings` | analytics_roi |
| Workforce Map | F-041 | F-050 Assignment `[Part 1]` | — | REST GET `/api/workforce` | tickets, assignments |
| Growth Nudge | F-042 | F-024 Overage, F-021 Sub `[Part 1]` | — | REST GET `/api/growth-nudge` (daily) | tickets, subscriptions |
| Feature Discovery | F-043 | F-036 Dashboard config | — | REST GET `/api/features/teaser` | dashboard_config |
| Spike Forecast | F-044 | F-049 Classification `[Part 1]` | — | REST GET `/api/forecast` (weekly) | tickets (historical) |
| Contextual Help | F-045 | Static content (no data source) | — | None (client-side) | None |

### Socket.io Event Specifications for Dashboard

```
Dashboard Socket.io Events (Room: tenant_{company_id}):

  Events EMITTED by server → consumed by widgets:

  event:new
    payload: { type, title, description, timestamp, entity_id, entity_type }
    consumer: F-037 Activity Feed
    source: all operational features via event_buffer

  metrics:updated
    payload: { total_tickets, ai_resolution_rate, avg_response_time, csat, queue_depth }
    consumer: F-038 Key Metrics
    source: F-109 Analytics Overview (Celery beat every 5 min)

  savings:updated
    payload: { monthly_saved, cumulative_saved, roi_percentage }
    consumer: F-040 Running Savings
    source: F-113 ROI Dashboard (Celery beat every 15 min)

  ticket:new
    payload: { ticket_id, customer, channel, intent, priority }
    consumer: F-037 Activity Feed
    source: F-046 Ticket List

  ticket:resolved
    payload: { ticket_id, resolved_by, resolution_time, confidence }
    consumer: F-037 Activity Feed, F-038 Key Metrics
    source: F-053 GSD State Engine

  approval:pending
    payload: { ticket_id, action_type, confidence, urgency }
    consumer: F-037 Activity Feed, F-074 Approval Queue
    source: F-074 Approval Queue

  drift:alert
    payload: { drift_score, indicators, recommendation }
    consumer: F-039 Adaptation Tracker
    source: F-116 Drift Detection

  agent:status_change
    payload: { agent_id, old_status, new_status, reason }
    consumer: F-097 Agent Dashboard
    source: F-099, F-105, F-101
```

---

## 4.3 Analytics → Training Pipeline Connection

Analytics features feed directly into the training loop (see Section 5):

```
Analytics → Training Data Flow:

  F-098 Agent Performance Metrics
    ↓ (daily aggregation)
  F-116 Drift Detection reads performance data
    ↓ (if drift_score ≥ 70)
  Alert sent to admin via F-037 Activity Feed
    ↓
  Admin triggers: "train agent from errors" via F-087 Jarvis
    ↓
  F-092 packages error data
    ↓
  F-103 Dataset Preparation uses F-098 + F-119 data for training
    ↓
  F-100 Training Loop executes
    ↓
  F-104 Model Validation compares new model vs. baseline (F-114 before/after)
    ↓
  F-105 Deployment
    ↓
  F-098 resumes tracking new performance
    ↓
  Cycle repeats
```

---

## 4.4 Dashboard Widget Dependency Graph

```
┌─────────────────────────────────────────────────────────┐
│                    F-036 DASHBOARD HOME                  │
│                   (container/layout)                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ F-037       │  │ F-038       │  │ F-039       │     │
│  │ Activity    │  │ Key Metrics │  │ Adaptation  │     │
│  │ Feed        │  │             │  │ Tracker     │     │
│  │ [Socket.io] │  │ [5min beat] │  │ [daily]     │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         │                │                │             │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐     │
│  │ F-040       │  │ F-041       │  │ F-042       │     │
│  │ Running     │  │ Workforce   │  │ Growth      │     │
│  │ Savings     │  │ Map         │  │ Nudge       │     │
│  │ [15min beat]│  │ [5min beat] │  │ [daily beat]│     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ F-043       │  │ F-044       │  │ F-045       │     │
│  │ Feature     │  │ Spike       │  │ Contextual  │     │
│  │ Discovery   │  │ Forecast    │  │ Help        │     │
│  │ [static]    │  │ [weekly]    │  │ [static]    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

# Section 5: Agent Training Pipeline Connections

> **Scope:** Features F-097 through F-108 — the complete lifecycle from agent creation through training, deployment, and continuous improvement.
>
> **Core Principle:** Training is a **closed loop**: mistakes → dataset preparation → training → validation → deployment → performance monitoring → next cycle. Two triggers ensure both reactive (50-mistake threshold) and proactive (bi-weekly) training.

---

## 5.1 Training Trigger Paths

### Path 1: Manual Trigger via Jarvis

```
Path 1: Manual Training (Jarvis-initiated)

  Admin clicks F-092 "Train from Error" button (in F-091 Last 5 Errors panel)
    OR
  Admin types "train agent from errors" in F-087 Jarvis
    ↓
  F-092 packages error context:
    ├── Error ticket IDs (from F-091 selection)
    ├── Error descriptions and stack traces
    ├── Original AI responses (failed)
    ├── Correct responses (if admin provided correction)
    └── Confidence scores at time of failure
    ↓
  F-103 Dataset Preparation:
    ├── Deduplicate against existing training data
    ├── Format as (input, expected_output) pairs
    ├── Validate quality (minimum 10 new samples required)
    ├── Augment with similar historical tickets
    └── Store in training_datasets table
    ↓
  F-100 Lightning Training Loop:
    ├── Load base model
    ├── Load training dataset from F-103
    ├── Configure hyperparameters
    └── Execute training (local GPU or cloud)
    ↓
  F-102 Training Run Execution:
    ├── Track training progress (loss, accuracy per epoch)
    ├── Store checkpoints
    ├── Log to training_runs table
    └── Emit Socket.io: training:progress events
    ↓
  F-104 Model Validation:
    ├── Evaluate against holdout test set (20% of dataset)
    ├── Run edge-case scenario tests
    ├── Compare against current production model (F-114)
    └── Check: new_model_accuracy > current_accuracy - 2%?
    ↓
  F-105 Model Deployment:
    ├── Canary deployment (10% of traffic)
    ├── Monitor for 1 hour
    ├── If quality OK → promote to 100%
    ├── If quality degrades → auto-rollback (F-105)
    └── Update F-054 Smart Router model list
    ↓
  F-098 Performance Metrics resumes tracking
  F-037 Activity Feed: emit agent:training_complete
```

### Path 2: Automatic Trigger (50-Mistake Threshold — LOCKED)

```
Path 2: Automatic Training (50-Mistake Threshold)

  Ticket resolved by AI → F-119 QA Scoring evaluates
    ↓
  If QA score < threshold (e.g., < 60):
    → Increment mistake_counter in Redis:
      key: parwa:{company_id}:agent:{agent_id}:mistake_count
    ↓
  F-098 Agent Performance Metrics tracks mistake_count
    ↓
  F-101 checks mistake_count on every ticket resolution:
    ├── IF mistake_count < 50 → continue normal operation
    └── IF mistake_count >= 50 → TRIGGER TRAINING
    ↓
  *** IMPORTANT: 50 threshold is LOCKED (BC-007 rule 10) ***
  *** No admin can change this value ***
  *** This value cannot be changed by any configuration ***
    ↓
  When threshold reached:
    ├── F-101 flags agent for retraining
    ├── Agent status changed to "training_required"
    ├── F-088 System Status shows warning
    ├── F-037 Activity Feed: emit agent:training_required
    ├── Email notification to admin (F-006 Brevo)
    ├── F-097 Agent Dashboard shows warning badge
    └── Auto-pause agent from receiving new tickets? → Configurable
    ↓
  F-103 Dataset Preparation:
    ├── Collect all 50 mistake tickets
    ├── Add 200 similar successful tickets (contrast set)
    ├── Add 100 random tickets (generalization set)
    └── Total: ~350 training samples
    ↓
  F-100 → F-102 → F-104 → F-105 (same pipeline as Path 1)
    ↓
  After successful deployment:
    → Reset mistake_counter to 0
    → Update agent status to "active"
    → Emit agent:retrained event
```

### Path 3: Scheduled Trigger (Drift Detection)

```
Path 3: Scheduled Training (Drift-based)

  F-116 Drift Detection runs daily at 02:00 UTC (see Section 4.1)
    ↓
  Drift score calculated:
    ├── drift_score < 30 → no action
    ├── 30 ≤ drift_score < 70 → "watching" status, logged
    └── drift_score ≥ 70 → "critical" alert
    ↓
  When drift_score ≥ 70:
    ├── F-116 generates detailed drift report
    ├── F-037 Activity Feed: emit drift:alert
    ├── Email notification to admin (via F-006 Brevo)
    └── F-088 System Status shows drift warning
    ↓
  Admin reviews drift report in F-116 or via F-087 Jarvis:
    → "check drift status" shows the report
    → "train agent from errors" triggers F-092
    ↓
  Manual confirmation required — automatic training NOT triggered
  by drift alone (to prevent unnecessary retraining costs)
    ↓
  F-092 → F-103 → F-100 → F-102 → F-104 → F-105
```

### Path 4: Optimization (DSPy Prompt Optimization)

```
Path 4: Prompt Optimization (F-061 DSPy)

  F-061 DSPy Prompt Optimization pipeline:
    ↓
  Triggered: weekly on Sunday at 03:00 UTC (Celery beat)
    ↓
  Process:
    ├── Collect last 500 resolved tickets (successful)
    ├── Define optimization metric: resolution_rate + csat_weighted
    ├── Create prompt variants (A, B, C) using DSPy algorithms
    ├── Run A/B test on historical data (offline evaluation)
    └── Select winner: variant with highest optimization metric
    ↓
  Validation:
    ├── Winner must outperform current prompt by > 2%
    ├── Run against edge-case test suite
    └── F-104 Model Validation checks quality
    ↓
  If winner passes validation:
    ├── Promote to production prompt (F-105 deployment)
    ├── Store previous prompt version (F-096 version control)
    ├── F-054 Smart Router uses new prompt
    └── F-037 Activity Feed: emit prompt:optimized
    ↓
  If no winner (all variants < 2% improvement):
    → Log "no improvement found" → skip deployment
    → Retry next week with different variants
```

---

## 5.2 Training Feature Connection Table

| Feature | Connects To | Data Flow | Trigger | DB Tables Written | Celery Task |
|---------|------------|-----------|---------|-------------------|-------------|
| F-097 Agent Dashboard | F-098 Performance Metrics | Agent status → metrics display | On page load | None (reader) | None |
| F-098 Performance Metrics | F-101, F-109, F-116 | Per-ticket results → aggregated metrics | Every ticket resolution | agent_metrics | `update_agent_metrics` |
| F-099 Add/Scale Agent | F-020 Paddle Checkout | Billing trigger → agent provisioning | Manual + Paddle webhook | agents, permissions | `provision_agent` |
| F-100 Training Loop | F-102 Run Execution | Agent + dataset → trained model | Called by F-092, F-101 | training_runs | `execute_training` |
| F-101 50-Mistake Threshold | F-103, F-100 | Mistake data → dataset → training | Automatic (count = 50) | agent_metrics | `check_mistake_threshold` |
| F-102 Run Execution | F-105 Deployment | Trained model → deployment candidate | After F-100 completes | training_runs, checkpoints | `execute_training_run` |
| F-103 Dataset Preparation | F-100 Training Loop | Clean dataset → training input | Called by F-092 or F-101 | training_datasets | `prepare_training_dataset` |
| F-104 Model Validation | F-105 Deployment | Test results → deploy/reject | After F-102 succeeds | validation_results | `validate_model` |
| F-105 Model Deployment | F-054 Smart Router `[Part 1]` | New model → production routing | After F-104 passes | api_providers, model_versions | `deploy_model` |
| F-106 Time-Based Fallback | F-054 Smart Router `[Part 1]` | Scheduled retraining → fresh model | Scheduled (bi-weekly) | training_datasets, training_runs | `scheduled_retraining` |
| F-107 Cold Start Handler | F-099, F-100 | New agent → high-approval-threshold mode | Automatic on agent creation | agents (mode flag) | None (immediate) |
| F-108 Peer Review | F-059, F-074 `[Part 1]` | Low-confidence → escalate to senior agent | Per-ticket (confidence < 40) | tickets (escalation) | None (inline) |

---

## 5.3 Agent Lifecycle State Machine

```
Agent Lifecycle States (F-097 tracks):

  ┌──────────┐
  │ CREATING │ ← F-095 Jarvis or F-099 manual
  └────┬─────┘
       │ Paddle payment confirmed
  ┌────▼─────┐
  │ TRAINING │ ← F-100 Lightning Training Loop
  └────┬─────┘
       │ F-104 validation passes + F-105 deployment succeeds
  ┌────▼─────┐
  │  ACTIVE  │ ← Normal operation, receiving tickets
  └──┬──┬──┬─┘
     │  │  │
     │  │  └── F-101 mistake_count ≥ 50 ──→ ┌──────────────┐
     │  │                                   │RETRAIN_NEEDED│
     │  └── F-083 Emergency Pause ──────────→ │              │
     │                                       └──────┬───────┘
     └── F-073 temporary expiry ───────────────→└──────┬──────┘
                                                   │
                                              Admin triggers
                                              F-092 or F-106
                                                   │
  ┌──────────────┐                          ┌──────▼───────┐
  │  RELEASING   │ ← F-073 expiry         │  RELEASING   │
  └──────┬───────┘                          └──────┬───────┘
         │                                         │
         │ F-105 deployment succeeds               │
         ▼                                         ▼
  ┌──────────────┐                          ┌──────────────┐
  │  DEPRECATED  │                          │  ACTIVE      │
  └──────────────┘                          └──────────────┘
```

---

## 5.4 Training Pipeline → External Services

| Training Step | External Service | Purpose | Failure Handling |
|--------------|-----------------|---------|-----------------|
| F-102 Training Run | Local GPU / RunPod / Colab | Execute model training | Retry on GPU OOM, fallback to smaller batch |
| F-105 Deployment | OpenRouter API `[Part 1]` | Register new model endpoint | F-055 Failover if registration fails |
| F-103 Dataset Prep | PostgreSQL (tickets table) | Extract historical data | BC-004 retry on DB timeout |
| F-106 Scheduled | Celery beat | Bi-weekly scheduling | BC-004 DLQ on persistent failure |
| F-061 DSPy | Local compute | Prompt optimization | Skip if compute unavailable, log warning |

---

# Section 6: Onboarding → Production Connection Path

> **Scope:** Features F-010 through F-035 — the complete journey from sign-up to first AI-resolved ticket.
>
> **Core Principle:** Onboarding is a **strictly sequential pipeline**. Each step has prerequisites, and the system cannot skip steps. AI Activation (F-034) is the final gate that validates all prerequisites before enabling live ticket processing.

---

## 6.1 Complete Onboarding Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ONBOARDING → PRODUCTION PIPELINE                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 1: Registration (F-010 / F-011)                               │
│    └→ Creates user + company in database                            │
│                                                                     │
│  Step 2: Email Verification (F-012)                                  │
│    └→ Verifies email ownership via Brevo                            │
│                                                                     │
│  Step 3: Authentication (F-013 → F-015 → F-016)                    │
│    └→ Login + MFA setup + backup codes                              │
│                                                                     │
│  Step 4: Payment Confirmation (F-027)                                │
│    └→ Paddle webhook confirms subscription active                    │
│                                                                     │
│  Step 5: Onboarding Wizard (F-028) — 5 sub-steps                   │
│    ├── 5a: Company Profile                                          │
│    ├── 5b: Legal Consent (F-029)                                    │
│    ├── 5c: Pre-built Integration Setup (F-030)                     │
│    ├── 5d: KB Upload (F-032) + Processing (F-033)                  │
│    └── 5e: AI Activation (F-034)                                    │
│                                                                     │
│  Step 6: First Victory (F-035)                                      │
│    └→ First AI-resolved ticket → celebration                        │
│                                                                     │
│  Step 7: Adaptation Tracking (F-039)                                │
│    └→ 30-day monitoring period begins                               │
│                                                                     │
│  Step 8: Growth Monitoring (F-042)                                  │
│    └→ Ongoing usage and limit alerts                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6.2 Step-by-Step Detail

### Step 1: Registration (F-010 / F-011)

| Aspect | Detail |
|--------|--------|
| **Features** | F-010 User Registration, F-011 Google OAuth |
| **API Endpoints** | `POST /api/auth/register`, `POST /api/auth/google-oauth` |
| **DB Tables Written** | `users` (email, password_hash, role, company_id), `companies` (name, industry, plan_id, status='trial'), `user_roles` |
| **External Services** | None for F-010; Google Identity Services for F-011 |
| **Validation** | Email uniqueness, password strength (min 12 chars, uppercase, lowercase, number, special), company name required |
| **Time Estimate** | 30–60 seconds |
| **On Failure** | Validation errors return 422 with field-level messages; F-011 OAuth failure returns redirect to registration form with error flash |
| **Next Step Trigger** | Auto-redirect to Step 2 (email verification) |
| **BC Compliance** | BC-011 (password hashing via bcrypt), BC-001 (tenant isolation on user creation), BC-010 (minimal data collection) |
| **Connection to Part 1** | Creates the `company_id` that ALL subsequent features use for tenant isolation |

### Step 2: Email Verification (F-012)

| Aspect | Detail |
|--------|--------|
| **Feature** | F-012 Email Verification |
| **API Endpoints** | `POST /api/auth/send-verification` (resend), `GET /api/auth/verify?token={token}` |
| **DB Tables Written** | `users` (email_verified_at), `verification_tokens` (token, expires_at, used_at) |
| **External Services** | **Brevo** — sends verification email via Brevo Template #1 (verification_email) |
| **Validation** | Token must exist, not expired (24h TTL), not already used, match user email |
| **Time Estimate** | 1–2 minutes (user clicks email link) |
| **On Failure** | Token expired → offer "Resend Verification" button (max 3 resends/hour per F-018 rate limiting); Brevo send failure → Celery retry (BC-006 rule 9), after 3 failures → show "Contact support" |
| **Next Step Trigger** | On successful verification → redirect to login (Step 3) |
| **BC Compliance** | BC-006 (Brevo template required, email logged), BC-004 (async via Celery), BC-012 (retry on failure) |

### Step 3: Authentication (F-013 → F-015 → F-016)

| Aspect | Detail |
|--------|--------|
| **Features** | F-013 Login, F-015 MFA Setup, F-016 Backup Codes |
| **API Endpoints** | `POST /api/auth/login`, `POST /api/auth/mfa/setup`, `POST /api/auth/mfa/verify`, `POST /api/auth/mfa/backup-codes` |
| **DB Tables Written** | `sessions` (user_id, token_hash, ip_address, user_agent, expires_at), `mfa_secrets` (encrypted TOTP secret), `backup_codes` (code_hash, used_at) |
| **External Services** | None (all local computation) |
| **Validation** | Email must be verified (from Step 2); password check; MFA code validation (TOTP window: ±1 period) |
| **Time Estimate** | 1–2 minutes |
| **On Failure** | Login failure → F-018 rate limiting (5 attempts then 15-min lockout); MFA code wrong → 3 retries then fallback to backup code; All backup codes lost → contact support flow |
| **Next Step Trigger** | On successful MFA verification → redirect to billing (Step 4) if no active subscription; or to dashboard if subscription exists |
| **BC Compliance** | BC-011 (JWT issuance, HTTP-only cookies, SameSite), BC-012 (rate limiting, error handling), BC-001 (tenant context in JWT) |
| **Connection to Part 1** | JWT token with `company_id` is the foundation for ALL subsequent authenticated API calls |

### Step 4: Payment Confirmation (F-027)

| Aspect | Detail |
|--------|--------|
| **Features** | F-020 Paddle Checkout, F-022 Paddle Webhook Handler, F-027 Payment Confirmation |
| **API Endpoints** | `POST /api/billing/checkout` (initiates Paddle overlay), `POST /webhooks/paddle` (webhook receiver) |
| **DB Tables Written** | `subscriptions` (paddle_subscription_id, plan_id, status, current_period_end), `companies` (status='active'), `audit_trail` (payment record), `webhook_events` (Paddle event log) |
| **External Services** | **Paddle** — checkout overlay UI, subscription creation, payment processing |
| **Validation** | Paddle webhook signature verification (HMAC-SHA256, BC-002 rule 2); idempotency check on `paddle_event_id` |
| **Time Estimate** | 1–3 minutes (user completes checkout) |
| **On Failure** | Paddle payment fails → Paddle handles retry UI; webhook not received within 5 min → Celery retry (BC-004); webhook signature invalid → reject with 403; payment succeeded but webhook lost → Paddle sends again (idempotent) |
| **Next Step Trigger** | On `subscription.created` webhook → F-027 sends welcome email (Brevo Template #2) → redirect to onboarding wizard (Step 5) |
| **BC Compliance** | BC-002 (financial atomicity, audit trail, idempotency), BC-003 (webhook verification), BC-006 (welcome email), BC-001 (tenant-scoped subscription) |

### Step 5: Onboarding Wizard (F-028) — 5 Sub-Steps

#### Step 5a: Company Profile

| Aspect | Detail |
|--------|--------|
| **Feature** | F-028 Onboarding Wizard (Step 1 of 5) |
| **API Endpoints** | `PUT /api/onboarding/company-profile` |
| **DB Tables Written** | `companies` (industry, size, support_email, brand_name, timezone, language) |
| **External Services** | None |
| **Validation** | Industry required, support_email format, timezone valid |
| **Time Estimate** | 30 seconds |
| **On Failure** | Validation errors shown inline; no rollback needed |
| **Next Step Trigger** | Save → advance to Step 5b |

#### Step 5b: Legal Consent (F-029)

| Aspect | Detail |
|--------|--------|
| **Feature** | F-029 Legal Consent Collection |
| **API Endpoints** | `POST /api/onboarding/consent` |
| **DB Tables Written** | `consent_records` (company_id, consent_type, consented_at, ip_address, consent_text_hash) |
| **Consent Types Required** | TCPA (SMS/Voice), GDPR Data Processing, Call Recording Permission |
| **External Services** | None |
| **Validation** | All 3 consent types must be accepted; consent_text_hash stored for audit trail |
| **Time Estimate** | 30–60 seconds |
| **On Failure** | Cannot proceed without all consents; UI blocks advancement; no rollback (nothing written yet) |
| **Next Step Trigger** | All consents recorded → advance to Step 5c |
| **BC Compliance** | BC-010 (GDPR consent logging, data processing records), BC-009 (consent as approval workflow) |
| **Gate for Later** | Voice (F-127) and SMS (F-126) channels CANNOT be activated without TCPA consent record |

#### Step 5c: Pre-built Integration Setup (F-030)

| Aspect | Detail |
|--------|--------|
| **Feature** | F-030 Pre-built Integration Setup |
| **API Endpoints** | `GET /api/integrations/available`, `POST /api/integrations/connect`, `POST /api/integrations/oauth/{provider}` |
| **DB Tables Written** | `integrations` (company_id, provider, status, auth_config_encrypted, last_sync), `consent_records` (OAuth scopes consented) |
| **External Services** | Zendesk (OAuth 2.0), Freshdesk (API Key), Intercom (OAuth 2.0), Slack (OAuth 2.0), Shopify (OAuth 2.0) |
| **Validation** | At least 1 integration must be connected; OAuth callback validated; API key format checked |
| **Time Estimate** | 2–5 minutes per integration |
| **On Failure** | OAuth flow fails → show error + retry button; API key test fails → show specific error (401, 403, timeout); can skip and come back later (wizard supports save-and-resume) |
| **Next Step Trigger** | ≥ 1 integration connected → advance to Step 5d |
| **BC Compliance** | BC-003 (OAuth token storage, webhook registration), BC-011 (credentials encrypted), BC-001 (tenant-scoped integration config) |
| **Gate for Later** | F-034 AI Activation requires ≥ 1 active integration |

#### Step 5d: Knowledge Base Upload (F-032) + Processing (F-033)

| Aspect | Detail |
|--------|--------|
| **Features** | F-032 Document Upload, F-033 KB Processing & Indexing |
| **API Endpoints** | `POST /api/kb/upload` (multipart), `GET /api/kb/status`, `GET /api/kb/documents` |
| **DB Tables Written** | `kb_documents` (company_id, filename, format, size, chunk_count, status), `kb_chunks` (document_id, content_hash, embedding_id), `vector_store` (tenant-isolated embeddings) |
| **External Services** | **OpenAI Embeddings API** (or self-hosted) — generates vector embeddings; **S3/GCS** — stores uploaded files |
| **Validation** | Supported formats: PDF, DOCX, TXT, Markdown, HTML, CSV; Max file size: 50MB; Min total documents: 1 |
| **Time Estimate** | Upload: 30 seconds–2 minutes; Processing (F-033): 2–10 minutes depending on document count/size |
| **On Failure** | Upload failure → retry button; Processing failure (extraction error) → log error per document, show partial success; Embedding API timeout → Celery retry (BC-004, max 3 retries); Can proceed to Step 5e while processing continues (async) |
| **Next Step Trigger** | ≥ 1 document uploaded → can advance to Step 5e (F-033 processing can complete in background) |
| **BC Compliance** | BC-004 (Celery async processing), BC-007 (embedding via Smart Router), BC-001 (tenant-isolated vector store), BC-010 (document retention policy) |
| **Connection to Part 1** | F-033 indexed data feeds directly into F-064 RAG `[Part 1]` which feeds F-065 Auto-Response `[Part 1]` |

#### Step 5e: AI Activation (F-034)

| Aspect | Detail |
|--------|--------|
| **Feature** | F-034 AI Activation System |
| **API Endpoints** | `POST /api/onboarding/activate-ai`, `GET /api/onboarding/readiness` |
| **DB Tables Written** | `companies` (ai_active=true, ai_activated_at), `agents` (default agent created), `smart_router_config` (company-specific configuration), `gsd_config` (company-specific state machine config) |
| **External Services** | None (all local configuration) |
| **Prerequisites Validated** | |
| ├── Consent collected? | Query `consent_records` WHERE company_id — must have TCPA, GDPR, Call Recording |
| ├── ≥ 1 integration active? | Query `integrations` WHERE company_id AND status='connected' |
| └── KB indexed? | Query `kb_documents` WHERE company_id AND status='indexed' — must have ≥ 1 |
| **Activation Actions** | |
| ├── Configure F-054 Smart Router | Set model tiers, confidence thresholds, fallback rules |
| ├── Create default agent | F-097 Agent Dashboard, F-099 Add Agent (no billing — included in plan) |
| ├── Initialize F-053 GSD Engine | Set up state machine configuration for tenant |
| ├── Configure F-062 Intent Classification | Load intent categories based on industry (from Step 5a) |
| └── Enable channel listeners | Start webhook consumers for connected integrations |
| **Time Estimate** | 5–10 seconds (all configuration, no heavy computation) |
| **On Failure** | Prerequisite not met → show which step is incomplete + "Go Back" button; Configuration save fails → retry (BC-012); cannot be skipped |
| **Next Step Trigger** | AI activated → redirect to dashboard (F-036) |
| **BC Compliance** | BC-007 (Smart Router config), BC-008 (GSD state config), BC-001 (tenant-isolated config), BC-012 (atomic config save with rollback) |
| **Gate** | This is the FINAL gate. No tickets can be processed until F-034 completes successfully |

---

### Step 6: First Victory (F-035)

| Aspect | Detail |
|--------|--------|
| **Feature** | F-035 First Victory Celebration |
| **Trigger** | First ticket resolved by AI (F-053 GSD Engine → state='resolved', resolved_by='ai') |
| **API Endpoints** | None (event-driven) — triggered by F-053 state transition |
| **DB Tables Written** | `companies` (first_victory_at), `milestones` (type='first_victory', timestamp) |
| **External Services** | **Brevo** — sends congratulatory email (Template #3: first_victory_email) |
| **UI Actions** | Confetti animation modal, milestone badge in F-037 Activity Feed, F-039 Adaptation Tracker starts |
| **Time Estimate** | Instant (once first ticket resolved — could be minutes or hours after activation) |
| **On Failure** | Email send fails → Celery retry (BC-006); modal doesn't show → Socket.io fallback (BC-005); no rollback needed (non-critical feature) |
| **BC Compliance** | BC-005 (Socket.io event), BC-006 (Brevo template), BC-012 (graceful degradation if email fails) |

---

### Step 7: Adaptation Tracker (F-039)

| Aspect | Detail |
|--------|--------|
| **Feature** | F-039 Adaptation Tracker (Day X/30) |
| **Trigger** | Auto-starts when F-034 AI Activation completes |
| **API Endpoints** | `GET /api/adaptation/status`, `GET /api/adaptation/progress` |
| **DB Tables Read** | `agent_metrics` (resolution rate over time), `qa_scores` (quality over time), `companies` (ai_activated_at as Day 1) |
| **External Services** | None |
| **Metrics Tracked** | AI resolution rate trend, confidence score trend, CSAT trend (30-day window) |
| **Time Estimate** | Passive — runs automatically for 30 days |
| **On Failure** | No failure mode — it's a read-only analytics feature. If data is sparse (low ticket volume), shows "Not enough data yet" message |
| **Connection to Part 1** | Consumes data from F-098 Agent Performance Metrics `[Part 1]` |

---

### Step 8: Growth Nudge Monitoring (F-042)

| Aspect | Detail |
|--------|--------|
| **Feature** | F-042 Growth Nudge Alert |
| **Trigger** | Celery beat daily check |
| **API Endpoints** | `GET /api/growth-nudge/status` |
| **DB Tables Read** | `tickets` (count by company_id, current month), `subscriptions` (plan_id, ticket_inclusion), `overages` (current month charges) |
| **External Services** | **Brevo** — sends growth nudge email (Template #4: growth_nudge_email) when threshold reached |
| **Threshold Checks** | |
| ├── Ticket count ≥ 80% of plan inclusion | Show "Approaching limit" warning |
| ├── Ticket count ≥ 100% of plan inclusion | Show "Overage charges will apply" alert |
| ├── Ticket count growth rate > 20% month-over-month | Show "Consider upgrading" nudge |
| └── Feature utilization < 30% | Show "Underutilized features" tip |
| **Time Estimate** | Passive — runs automatically |
| **On Failure** | No failure mode — notification failure degrades gracefully |
| **Connection to Part 1** | Reads from F-024 Overage Charging `[Part 1]` and F-021 Subscription Management `[Part 1]` |

---

## 6.3 Onboarding → Production Prerequisite Chain

```
┌──────────────────────────────────────────────────────────────────┐
│                 ONBOARDING PREREQUISITE CHAIN                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  F-010 Registration                                               │
│    ↓ (creates company_id)                                        │
│  F-012 Email Verification  ◄── BLOCKS all features until done    │
│    ↓                                                              │
│  F-013 Login + F-015 MFA  ◄── BLOCKS authenticated access       │
│    ↓                                                              │
│  F-027 Payment Confirmation ◄── BLOCKS onboarding wizard         │
│    ↓                                                              │
│  F-028 Step 1: Company Profile                                   │
│    ↓                                                              │
│  F-029 Step 2: Legal Consent ◄── GATES voice/SMS channels        │
│    ↓                                                              │
│  F-030 Step 3: Integration Setup ◄── GATES F-034 activation       │
│    ↓                                                              │
│  F-032 Step 4: KB Upload                                         │
│    ↓                                                              │
│  F-033 Step 4: KB Processing ◄── GATES F-034 activation           │
│    ↓                                                              │
│  F-034 Step 5: AI Activation ◄── FINAL GATE                      │
│    ├── Validates: consent ✓                                       │
│    ├── Validates: integration ✓                                   │
│    ├── Validates: KB indexed ✓                                    │
│    ├── Configures: F-054 Smart Router                             │
│    ├── Configures: F-053 GSD Engine                               │
│    ├── Creates: Default agent (F-097, F-099)                     │
│    └── Enables: All channel listeners                            │
│    ↓                                                              │
│  ★ PRODUCTION — tickets can flow ★                               │
│    ↓                                                              │
│  F-035 First Victory (event-triggered)                           │
│    ↓                                                              │
│  F-039 Adaptation Tracker (30-day monitoring)                    │
│    ↓                                                              │
│  F-042 Growth Nudge (ongoing monitoring)                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6.4 Onboarding → External Service Dependency Map

| Onboarding Step | External Service | Purpose | Failure Recovery |
|----------------|-----------------|---------|-----------------|
| Step 1 (F-010) | None | N/A | N/A |
| Step 1 (F-011) | Google Identity Services | OAuth SSO | Fallback to F-010 email registration |
| Step 2 (F-012) | Brevo | Send verification email | Celery retry (3x), then show "Resend" |
| Step 4 (F-027) | Paddle | Payment processing | Webhook retry (BC-003), Paddle handles payment retry |
| Step 4 (F-027) | Brevo | Send welcome email | Celery retry (3x), non-blocking |
| Step 5b (F-029) | None | N/A (local consent storage) | N/A |
| Step 5c (F-030) | Zendesk/Freshdesk/Intercom/Slack/Shopify | OAuth for integration | Retry OAuth flow; can skip and return later |
| Step 5d (F-032) | S3/GCS | Store uploaded KB files | Retry upload; show partial success |
| Step 5d (F-033) | OpenAI Embeddings API | Generate vector embeddings | Celery retry (3x, BC-004); F-055 failover to backup provider |
| Step 5e (F-034) | None | N/A (local configuration) | Atomic rollback on save failure |
| Step 6 (F-035) | Brevo | Send celebration email | Celery retry; non-blocking |
| Step 8 (F-042) | Brevo | Send growth nudge email | Celery retry; non-blocking |

---

## 6.5 Onboarding → Feature Cross-Reference Summary

This table maps each onboarding step to ALL features it enables downstream:

| Onboarding Step | Features Enabled Downstream |
|----------------|---------------------------|
| F-010 Registration | All features (creates `company_id` for BC-001 tenant isolation) |
| F-012 Email Verification | F-013 Login, F-014 Forgot Password, all authenticated features |
| F-015 MFA | F-013 Login (with MFA enforced), F-017 Session Management |
| F-027 Payment | F-021 Subscriptions, F-023 Invoices, F-024 Overage, F-099 Add Agent |
| F-029 Legal Consent | F-126 SMS, F-127 Voice (gated by TCPA consent), GDPR compliance for all data |
| F-030 Integrations | F-131 Pre-built connectors, F-137 Health Monitor, F-135 MCP, F-138 Outgoing webhooks |
| F-032/F-033 KB | F-064 RAG `[Part 1]`, F-065 Auto-Response `[Part 1]`, F-061 DSPy `[Part 1]` |
| F-034 AI Activation | F-054 Smart Router, F-053 GSD Engine, F-062 Intent Classification, all AI features |
| F-035 First Victory | F-039 Adaptation Tracker (starts 30-day clock) |
| F-039 Adaptation | F-116 Drift Detection, F-118 Quality Coach Reports |

---

## 6.6 Onboarding Failure Scenarios & Recovery

| Failure Scenario | Step Affected | User Action Needed | System Recovery | Data Rollback |
|-----------------|---------------|-------------------|----------------|---------------|
| Email not received | Step 2 (F-012) | Click "Resend Verification" | New token generated, old invalidated | Token record updated |
| MFA device lost | Step 3 (F-015/F-016) | Use backup code → re-enroll MFA | F-016 provides single-use codes | Backup code marked used |
| Paddle payment fails | Step 4 (F-027) | Retry payment in Paddle overlay | Paddle handles retry flow | No data written until webhook confirms |
| Brevo email API down | Steps 2, 4, 6 | No action — emails are non-blocking | Celery retry queue; email sent when Brevo recovers | No rollback needed |
| OAuth flow fails | Step 5c (F-030) | Retry OAuth or enter API key manually | Show error message with specific failure reason | Partial integration config deleted |
| KB processing stuck | Step 5d (F-033) | Re-upload failed document | Celery DLQ alert → manual retry from dashboard | Partial chunks cleaned up |
| Prerequisites not met | Step 5e (F-034) | Complete missing steps | "Go Back" buttons to specific incomplete step | No rollback (nothing written yet) |
| Smart Router config fails | Step 5e (F-034) | Retry activation | F-034 retries config save (3x) with rollback | Config reverted to pre-activation |

---

# Appendix: Cross-Reference Quick Reference

## Building Code Usage in This Document

| Building Code | Where Applied in This Document |
|--------------|-------------------------------|
| BC-001 Multi-Tenant Isolation | Every DB write scoped by `company_id`; every Celery task receives `company_id` first |
| BC-002 Financial Actions | F-099 agent provisioning via Paddle; F-113 ROI calculations |
| BC-003 Webhook Handling | All channel ingestion (email, SMS, voice, social); F-134 incoming webhooks; F-138 outgoing webhooks |
| BC-004 Background Jobs | All channel ingestion Celery tasks; F-033 KB processing; F-116 drift detection; F-092 training |
| BC-005 Real-Time Communication | F-037 Activity Feed; F-125 Chat Widget; F-089 GSD Terminal; all dashboard Socket.io events |
| BC-006 Email Communication | F-120 outbound email; F-121 inbound email; F-122 OOO detection; F-123 rate limiting |
| BC-007 AI Model Interaction | F-087 NL parsing via Smart Router; F-061 DSPy optimization; F-128 voice-first AI |
| BC-008 State Management | F-089 GSD State Terminal; F-034 AI Activation configures GSD |
| BC-009 Approval Workflow | F-078 auto-approve confirmation for Jarvis destructive commands |
| BC-010 Data Lifecycle | F-029 consent records; F-033 KB document retention |
| BC-011 Authentication | All webhook verification; F-030 OAuth flows; F-136 DB connection credentials |
| BC-012 Error Handling | F-139 Circuit Breaker; F-093 Self-Healing; F-094 Trust Preservation; all retry logic |

## Feature Count by Section

| Section | Features Covered | Feature IDs |
|---------|-----------------|-------------|
| Section 1: Channels | 11 | F-120–F-130 |
| Section 2: Integrations | 9 | F-131–F-139 |
| Section 3: Jarvis | 10 | F-087–F-096 |
| Section 4: Analytics/Dashboard | 20 | F-036–F-045, F-109–F-119 |
| Section 5: Training | 12 | F-097–F-108 |
| Section 6: Onboarding | 26 | F-010–F-035 + cross-references |
| **Total Unique Features** | **88** | |

---

*PARWA Connection Map Part 2: Support Systems — Generated for developer reference. See PARWA Connection Map Part 1 for core system connections (Auth, Billing, Ticket Management, AI Core Engine, Approval System).*
