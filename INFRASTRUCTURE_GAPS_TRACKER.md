# PARWA Infrastructure Gaps Tracker

> Discovered during comprehensive gap analysis (Days 6, 15-18, and pre-Week 3 audit).
> Items marked with target week should be addressed when that week begins.
> Items without a week are notes for future reference.
> Last updated: Post Day 23 — AI Technique Framework (TRIVYA v1.0) gaps added.
> New doc analyzed: `documents/PARWA_AI_Technique_Framework.md` (9 new features + BC-013).

---

## CRITICAL — Must Fix Before Week 2 ✅ ALL DONE

These infrastructure items were built in Week 1 (Day 6 fixes) to unblock future development.

- [x] C1: Generate Alembic migration stubs (0 exist)
- [x] C2: Add CORS middleware to main.py
- [x] Fix alembic.ini -> PostgreSQL
- [x] Fix .env.example missing vars
- [x] Fix Docker compose: remove OPENAI_API_KEY, STRIPE_SECRET_KEY, STRIPE references
- [x] Remove Qdrant config (use pgvector only)
- [x] Add missing packages to requirements.txt
- [x] Fix Socket.io cors_allowed_origins
- [x] Wire API Key Auth middleware in main.py
- [x] Add security headers middleware
- [x] Fix rate limiter MD5 -> SHA-256
- [x] Fix document_chunks embedding column type
- [x] Add API versioning prefix /api/v1/
- [x] Fix Docker compose PADDLE_VENDOR_ID/PADDLE_AUTH_CODE -> correct env names

---

## Week 2 GAPS — Auth System ✅ ALL DONE

- [x] C3-alt: JWT auth functions (create/verify/refresh tokens) -> `backend/app/core/auth.py` ✅ Day 7
- [x] C4: Brevo email client + email service -> `backend/app/services/email_service.py` ✅ Day 8
- [x] C5: Phone OTP login (Twilio Verify) -> new endpoints under /api/auth/phone ✅ Day 11
- [x] F04: Google OAuth implementation -> httpx server-side token verification ✅ Day 7
- [x] F05: Pydantic schemas directory -> `backend/app/schemas/` ✅ Day 7
- [x] F07: Email template rendering (Jinja2) -> `backend/app/templates/emails/` ✅ Day 8
- [x] S02: Socket.io JWT auth middleware (real auth, not placeholder) ✅ Day 11
- [x] FP11: Audit trail auto-logging middleware (log all write ops) ✅ Day 17
- [x] Add `phone` column to users model ✅ Already exists in core.py
- [x] Add pyotp, qrcode, jinja2, brevo-python, authlib to requirements.txt ✅ Day 8-9

---

## Week 3 GAPS — Background Jobs + Real-Time + Middleware (Days 19-23)

> These are the TRUE Week 3 gaps from the Build Roadmap.
> Days 15-18 were infrastructure hardening overflow from Weeks 1-2.

### GAP 1.1: Socket.io Business Event System ✅ Day 19
- [x] Event type registry (enum/class) with all event types defined
- [x] Event payload schemas (Pydantic) for each event type
- [x] High-level emit helpers (emit_ticket_event, emit_ai_event, emit_approval_event, etc.)
- [x] Business event handlers registered on Socket.io server
- [x] Async event emission Celery task for fan-out
- [x] Event rate limiting per tenant (max 100 events/sec)
- [x] Event payload size validation (max 10KB)
- [x] Integration tests for emit → handler → room broadcast flow
- [x] Tests: 95 new

### GAP 1.2: Multi-Tenant Middleware Hardening (BC-001) ✅ Day 20
- [x] Auto-inject company_id into ALL SQLAlchemy queries via session events
- [x] Explicit opt-out mechanism with @bypass_tenant for admin/system queries
- [x] Tenant context propagation to Celery tasks (company_id in task headers)
- [x] Redis key enforcement — all operations MUST use make_key(), reject raw keys
- [x] API key auth also enforces tenant isolation (not just JWT)
- [x] Integration test: API → middleware → DB → Celery → Redis, all tenant-scoped
- [x] Tests: 81 new

### GAP 1.3: Health Check System + Monitoring Config (BC-012) ✅ Day 21
- [x] Health check orchestrator with dependency graph (degraded vs down)
- [x] Per-subsystem health: PostgreSQL, Redis, Celery, Socket.io, Disk Space
- [x] Per-queue Celery health: depth check for all 7 queues
- [x] External API health probes: Paddle, Brevo, Twilio (connectivity only)
- [x] Prometheus metrics endpoint (/metrics) with counters, histograms, gauges
- [x] Detailed health endpoint (/health/detail) with latency info
- [x] `monitoring/prometheus.yml` — Prometheus scrape config
- [x] `monitoring/grafana_dashboards/` — 3 dashboard JSON files
- [x] `monitoring/alerting/rules.yml` — Alertmanager rules
- [x] Tests: 112 new

### GAP 1.4: Celery Task Modules for All 7 Queues ✅ Day 22
- [x] `email_tasks.py` — send_email, render_template, send_bulk_notification
- [x] `analytics_tasks.py` — aggregate_metrics, calculate_roi, drift_detection
- [x] `ai_tasks.py` — classify_ticket (light), generate_response (heavy), score_confidence (light)
- [x] `training_tasks.py` — prepare_dataset, check_mistake_threshold, schedule_training
- [x] `approval_tasks.py` — approval_timeout_check, approval_reminder, batch_process
- [x] `billing_tasks.py` — daily_overage_charge, invoice_sync, subscription_check
- [x] New Beat schedule entries: approval timeout (15min), reminders (30min), overage (daily 02:00), drift (daily 03:00), metrics (5min), training check (hourly)
- [x] All tasks follow BC-004 pattern (company_id, retry, DLQ, idempotency)
- [x] Tests: 270 new

### GAP 1.5: Webhook Provider Handlers + Email Templates + Cleanup ✅ Day 23
- [x] `webhooks/paddle_handler.py` — subscription.created/updated/cancelled, payment.succeeded/failed
- [x] `webhooks/brevo_handler.py` — inbound_email parse → ticket creation
- [x] `webhooks/twilio_handler.py` — sms.incoming, voice.call.started/ended
- [x] `webhooks/shopify_handler.py` — orders.create, customers.create
- [x] 6 additional email templates: welcome, mfa_enabled, session_revoked, api_key_created, approval_notification, overage_notification
- [x] `AGENT_COMMS.md` — Inter-agent communication log
- [x] `ERROR_LOG.md` — Error tracking log
- [x] `PROJECT_STATE.md` — Live project state memory
- [x] Delete stale `infra/docker/docker-compose.prod.yml`
- [x] Delete stale `infra/docker/.env.example`
- [x] Tests: ~80 new

---

## Week 4 GAPS — Ticket System (Phase 2 Start)

> Phase 2 starts after Week 3. These gaps will be discovered in detail when building.

### Roadmap Feature Items

- [ ] F-046: Ticket CRUD API routes + service + schemas (create, list paginated, filter, sort, lifecycle states)
- [ ] F-047: Ticket detail + conversation thread (messages, internal notes, file attachments)
- [ ] F-048: Ticket search (full-text search with fuzzy matching)
- [ ] F-049: Ticket classification by AI (intent: refund/technical/billing/complaint/feature_request)
- [ ] F-050: Ticket assignment — AI-powered score-based matching
- [ ] F-051: Ticket bulk actions (multi-select: status, reassign, tag, merge, close, undo)
- [ ] F-052: Omnichannel session model (link messages from email/chat/SMS/voice/social)
- [ ] F-070: Customer identity resolution (match across channels by email/phone/social ID)
- [ ] Ticket API schema files (request/response Pydantic models)
- [ ] Ticket service (business logic layer)
- [ ] Ticket Celery tasks (assignment scoring, classification dispatch)
- [ ] Ticket Socket.io events (integrate with Day 19 event system)

### Code Loopholes Found (Pre-Week 4 Audit)

- [ ] BL01: Table naming mismatch — DB models use `sessions`/`interactions` but feature specs (F-046→F-052) reference `tickets`/`ticket_messages`. Need to decide and align naming before building API routes.
- [ ] BL02: Missing DB tables for planned features — `ticket_intents`, `classification_corrections`, `ticket_assignments`, `assignment_rules`, `bulk_action_logs`, `bulk_action_failures`, `ticket_merges`, `customer_channels`, `channel_configs`, `identity_match_log`, `customer_merge_audit`, `ticket_feedback`. Roadmap references these in F-049→F-052, F-070 but no migration exists.
- [ ] BL03: `get_db()` dependency — fixed (commit on success, rollback on exception) but needs regression test for all write operations.
- [ ] BL04: Float loophole in money columns — database allows float types for monetary fields. Need strict DECIMAL enforcement on all `price`, `amount`, `fee` columns across billing models.
- [ ] BL05: No rate limiting on ticket creation endpoints — could allow spam/bot ticket flooding. Need per-client rate limits before going live.
- [ ] BL06: No file type whitelist on ticket attachments — current model stores any file type. Need validation (size + extension + mime check + async malware scan).
- [ ] BL07: No sensitive data scanning on ticket messages — clients could paste credit card numbers, API keys, passwords. Need regex-based PII detection + auto-redaction.
- [ ] BL08: Audit trail (FP11) still deferred from Week 2 — ticket system writes (status changes, assignments, merges) MUST be audit-logged. Cannot defer further.
- [ ] BL09: Test isolation issues — 22 tests fail in large batch runs but pass individually (shared DB state pollution). Must fix before Week 4 adds more tests.

### Production Situations (Must Handle in Ticket System)

Real scenarios that WILL happen in production. Each needs a defined handling flow.

#### MUST Handle (Build in Week 4)

| ID | Situation | Description |
|----|-----------|-------------|
| PS01 | Out-of-plan scope | Client asks for something outside their plan's variant capability. AI detects, tags `out_of_scope`, shows upgrade option, ticket stays open. If client upgrades mid-ticket, ticket auto-unblocks. |
| PS02 | AI can't solve | AI tries N attempts (configurable per variant, e.g., 3), then auto-escalates to human queue. Status → `awaiting_human`. Client notified with context. |
| PS03 | Client asks for human | "Talk to human" trigger (button + keyword detection). Ticket jumps to human queue with AI conversation summary. Status → `escalated_by_client`. |
| PS04 | Client disputes resolution | Client replies to resolved ticket → auto-reopen (status → `reopened`). If reopened >2 times on same ticket → auto-escalate to human. Track reopen count per ticket. |
| PS05 | Duplicate ticket detection | On ticket creation, run similarity check against client's recent open tickets (fuzzy match on subject + first message). If similarity >85%: show "You already have #TK-1234" with link. Still allow but auto-link as duplicate. |
| PS06 | Stale ticket timeout | Configurable idle timeout per priority (Critical: 1h, High: 4h, Medium: 24h, Low: 72h). After timeout → flag `stale`, notify client. After double timeout → auto-close with reason, 7-day reopen window. |
| PS07 | Account suspended with open tickets | No new tickets allowed. Existing open tickets → `frozen` state. On renewal → auto-thaw. After 30 days frozen → auto-close + archive. |
| PS08 | Awaiting client action | Ticket needs client to do something (restart server, update settings). Status → `awaiting_client_action`. Auto-remind at 24h. No response 7d → gentle nudge. 14d → "Still need help?" |
| PS09 | Attachment handling (size/format) | File size limit per plan (Basic: 5MB, Premium: 25MB, Enterprise: 100MB). Format whitelist per ticket type. Async malware scan. Failed upload → clear error, message still goes through. |
| PS10 | Incident/maintenance mode | Platform-wide issue: auto-create system status banner, auto-tag incoming tickets with `known_incident`, link to master incident ticket, auto-reply with status updates, mass-notify all affected clients. |

#### SHOULD Handle (Build in Week 4 if time, else Week 5)

| ID | Situation | Description |
|----|-----------|-------------|
| PS11 | SLA breach tracking | At 75% SLA time → auto-warn assigned agent + subtle client notification. At 100% → auto-escalate to higher tier, change priority to critical. Track breach count per client. |
| PS12 | Ticket deletion/redaction | Soft delete by default (content hidden, metadata kept for audit). GDPR hard delete with audit trail. Admin approval for hard delete of tickets >30 days. Allow message-level redaction. |
| PS13 | Variant down/under maintenance | Ticket created but variant is down → status `queued`. Auto-retry when variant returns. If down >1hr → offer human fallback. Don't block creation, only processing. |
| PS14 | Plan downgrade mid-ticket | Open tickets are GRANDFATHERED — complete at plan level they were created under. New tickets follow new plan limits. Reopened grandfathered tickets still get original plan treatment. |
| PS15 | Rate limiting / spam tickets | Per-client rate limit: max X tickets/hour (e.g., 10). Varies by plan. Limit hit → clear message. Auto-flag as potential spam after threshold. Admin real-time alert. |
| PS16 | Bad feedback auto-review | 1-star CSAT → auto-trigger human review. Status → `feedback_review`. Track low ratings per variant for quality monitoring. If avg drops below threshold → alert engineering. |
| PS17 | SLA approaching warning | Configurable warning before breach (75% of SLA time). Different SLA tiers per plan × priority matrix. Visible SLA countdown on ticket for agents and client. |

#### CAN DEFER (Later phases)

| ID | Situation | Description |
|----|-----------|-------------|
| PS18 | Credit/usage limit reached | Block new ticket creation with clear message. Existing open tickets unaffected. Payment failure → 7-day grace period. |
| PS19 | Cross-variant tickets | Request needs multiple variants. Parent ticket with child tickets per variant. Parent `in_progress` until all children resolved. |
| PS20 | Conflicting AI info | Same client, different tickets, AI gives contradictory answers. Track confidence scores, knowledge base correction workflow. |
| PS21 | Recurring issue detection | Same client, similar subject/content recurring. Auto-flag, suggest master ticket, notify engineering if multi-client (bug signal). |
| PS22 | Trial user ticket limits | Trial users: max 3 tickets during trial. Grace period on trial end. Mark for conversion analytics. |
| PS23 | Timezone/business hours SLA | Configurable SLA: "business hours only" vs "24/7". Per-plan. Client timezone. Holiday calendar support. |
| PS24 | Unauthorized source detection | Verify identity on all inbound channels. Suspicious → create as `unverified`, human review before processing. |
| PS25 | Variant updated mid-ticket | Active processing completes with current variant version. Next interaction uses new version. Track internally. |
| PS26 | Ticket merge mistakes | Merged tickets can be UNMERGED. Preserve message history. Track merge/unmerge rate. |
| PS27 | Manager escalation | Escalation tiers: L1 (AI) → L2 (Human) → L3 (Manager). "Escalate to manager" → jump to L3. |
| PS28 | Multi-language handling | Auto-detect language. Auto-translate if not supported by variant. Store client preferred language. |
| PS29 | Sensitive data in messages | Auto-scan for PII (credit card, API key, SSN, passwords). Redact/mask in display. Encrypted original. Notify client. |

### Missing Ticket Features (Not in Current Roadmap)

Features that real production ticket systems (Zendesk, Freshdesk, Intercom) have that are completely absent from F-046→F-052 and F-070.

#### MUST ADD to Week 4 (Foundational — can't build without these)

| ID | Feature | Description |
|----|---------|-------------|
| MF01 | **Priority System** | Priority levels: Critical / High / Medium / Low. Auto-priority based on client plan. Priority-based SLA rules. Priority escalation (stale ticket auto-upgrades). **Completely missing from all specs.** |
| MF02 | **Categories / Departments** | Categories: Technical Support, Billing, Feature Request, Bug Report, General Inquiry, Complaint. Each has own assignment rules, SLA, response templates. Category-based routing. **No routing logic exists anywhere.** |
| MF03 | **Tags / Labels** | Custom tags on tickets. Filterable by tags. Auto-tagging based on message content (AI suggests). Tags power reporting and search. **Not mentioned in any feature spec.** |
| MF04 | **Ticket Activity Log / Timeline** | Every change logged: who changed status/when/old→new. All transitions with timestamps. Visible "Timeline" view on ticket detail. Partially covered by FP11 but needs dedicated ticket feature. |
| MF05 | **Email Notification System** | Notification templates: Created, Updated, Assigned, Resolved, Closed, Reopened. Per-user preferences (email, in-app, push, mute). CC/BCC. Email reply parsing. Digest mode. **Zero notification infrastructure exists.** |
| MF06 | **SLA Management System** | SLA policies: First Response Time, Resolution Time, Update Frequency. SLA per plan × priority matrix. Visible SLA clock/timer. Breach alerts. SLA reporting. **Full feature, not just a production situation.** |

#### SHOULD ADD to Week 4 (Important, build if time allows)

| ID | Feature | Description |
|----|---------|-------------|
| MF07 | **Ticket Templates / Macros** | Pre-written response templates for common issues. Per category. Agents (human or AI) select and customize. |
| MF08 | **Automated Triggers & Rules** | "If category = billing AND priority = high → notify billing team." "If no response 24h → send reminder." Custom automation rules for admins. |
| MF09 | **Custom Fields / Ticket Forms** | Different ticket types need different fields. Bug report: steps to reproduce, expected/actual behavior. Billing: invoice number, amount. Admin creates per category. |
| MF10 | **Ticket Analytics Dashboard** | Total tickets, avg metrics (first response time, resolution time). Distribution by category/priority/status/agent/variant. AI performance metrics. Export CSV/PDF. |
| MF11 | **Collision Detection** | Two agents viewing same ticket → show "Agent X is also viewing." Lock mechanism to prevent conflicting responses. |
| MF12 | **Rich Text / Markdown Support** | Messages with formatting: bold, italic, code blocks, lists, links, images. Code syntax highlighting. Message preview. |

#### CAN DEFER (Week 5-7 or later phases)

| ID | Feature | Target |
|----|---------|--------|
| MF13: CSAT / NPS Surveys | Week 5 |
| MF14: Watchers / Followers | Week 5 |
| MF15: @Mentions in Notes | Week 5 |
| MF16: Ticket Export (PDF/CSV) | Week 6 |
| MF17: Suggested KB Articles | Week 8+ |
| MF18: Ticket Sharing / Public Link | Week 8+ |
| MF19: Approval Workflow (combine with Week 7) | Week 7 |
| MF20: Internal Knowledge Sharing | Week 8+ |
| MF21: Spam & Content Moderation | Week 5 |
| MF22: Client Ticket Portal (frontend) | Week 4 frontend |
| MF23: Ticket Linking / Related Tickets | Week 5 |
| MF24: Ticket Transfer Between Accounts | Week 8+ |

---

## Week 5 GAPS — Billing System (Paddle)

### Business Rules (LOCKED)

| Rule | Decision | Impact |
|------|----------|--------|
| **Payment Failure** | STOP immediately - Netflix style | No dunning system needed |
| **Free Trials** | NOT offered | No trial management needed |
| **Dunning** | NOT needed | Skip BG-02 gap |
| **Grace Period** | NOT needed | Skip BG-03 gap |
| **Refunds** | NO REFUNDS - Netflix style | Only track client refunds (PARWA clients to THEIR customers) |
| **Cancellation** | Cancel anytime, access until month end | No partial refunds |
| **Overage Rate** | $0.10/ticket (daily billing) | Confirmed |

### Variant Structure (LOCKED)

| Variant | Price | Tickets/mo | AI Agents | Team | Voice Slots | KB Docs |
|---------|-------|------------|-----------|------|-------------|---------|
| **PARWA Starter** | $999 | 2,000 | 1 | 3 | 0 | 100 |
| **PARWA Growth** | $2,499 | 5,000 | 3 | 10 | 2 | 500 |
| **PARWA High** | $3,999 | 15,000 | 5 | 25 | 5 | 2,000 |

### Feature Gaps

- [ ] F-020: Paddle checkout integration (subscription creation, variant IDs, tax)
- [ ] F-021: Subscription management (upgrade/downgrade with proration)
- [ ] F-022: Paddle webhook handler (all 25+ events — depends on Day 23 paddle_handler.py)
- [ ] F-023: Invoice history (paginated list from Paddle, PDF download)
- [ ] F-024: Daily overage charging ($0.10/ticket over plan limit — Celery task exists from Day 22)
- [ ] F-025: Cancellation flow (cancel auto-renewal, access until month end - NO retention offers per Netflix model)
- [ ] F-026: Cancellation request tracking (reason capture, analytics)
- [ ] F-027: Payment confirmation + verification (entitlement activation, welcome email)
- [ ] Billing API routes + service + schemas
- [ ] Variant entitlement enforcement middleware (check variant limits on API calls)

### Production Billing Gaps (CRITICAL)

| Gap ID | Severity | Description | Status |
|--------|----------|-------------|--------|
| BG-01 | 🔴 Critical | Only 5 Paddle events handled, 25+ exist | NEEDED |
| BG-02 | ~~Critical~~ | ~~Dunning management~~ | **NOT NEEDED** |
| BG-03 | ~~Critical~~ | ~~Grace period handling~~ | **NOT NEEDED** |
| BG-04 | 🔴 Critical | No variant change proration calculation | NEEDED |
| BG-05 | 🔴 Critical | No outbound calls TO Paddle (API client) | NEEDED |
| BG-06 | 🔴 Critical | No reconciliation if DB/Paddle diverge | NEEDED |
| BG-07 | 🟡 High | Webhook ordering/parallel processing | NEEDED |
| BG-08 | 🟡 High | No idempotency key storage for retries | NEEDED |
| BG-09 | 🟡 High | Client refund tracking (PARWA clients to THEIR customers) | NEEDED |
| BG-10 | ~~High~~ | ~~Trial management~~ | **NOT NEEDED** |
| BG-11 | 🟡 High | No payment method update flow | NEEDED |
| BG-12 | 🟡 High | No PDF invoice generation | NEEDED |
| BG-13 | 🔴 Critical | No real-time usage counting | NEEDED |
| BG-14 | 🔴 Critical | No feature blocking on variant limits | NEEDED |
| BG-15 | 🟡 High | No missed webhook detection | NEEDED |
| BG-16 | 🔴 Critical | Payment failure → immediate service stop | NEEDED |

### New Files Required

| File | Purpose | Priority |
|------|---------|----------|
| `backend/app/clients/paddle_client.py` | Paddle API client | 🔴 Critical |
| `backend/app/services/subscription_service.py` | Subscription lifecycle | 🔴 Critical |
| `backend/app/services/proration_service.py` | Variant change calculations | 🔴 Critical |
| `backend/app/services/payment_failure_service.py` | Immediate stop handling | 🔴 Critical |
| `backend/app/services/variant_limit_service.py` | Feature limit enforcement | 🔴 Critical |
| `backend/app/services/usage_tracking_service.py` | Usage counting | 🔴 Critical |
| `backend/app/services/client_refund_service.py` | Client refund processing | 🟡 High |
| `backend/app/services/invoice_service.py` | PDF generation | 🟡 High |
| `backend/app/tasks/reconciliation_tasks.py` | DB ↔ Paddle sync | 🔴 Critical |
| `backend/app/tasks/webhook_recovery.py` | Missed webhook recovery | 🟡 High |

### New Database Tables

| Table | Purpose |
|-------|---------|
| `client_refunds` | Client refund tracking (PARWA clients to THEIR customers) |
| `payment_methods` | Payment method summary cache |
| `usage_records` | Monthly usage tracking |
| `variant_limits` | Variant feature limits |
| `idempotency_keys` | Idempotency key storage |
| `webhook_sequences` | Webhook ordering tracking |
| `proration_audits` | Proration calculation audit trail |
| `payment_failures` | Payment failure audit log |

---

## Week 6 GAPS — Onboarding System

- [ ] F-028: Onboarding wizard backend (5-step state machine, save/resume)
- [ ] F-029: Legal consent collection (TCPA, GDPR, call recording with timestamps + IP)
- [ ] F-030: Pre-built integration setup (OAuth flows for Zendesk, Freshdesk, Intercom, Slack, Shopify)
- [ ] F-031: Custom integration builder (REST/GraphQL/webhook/DB with test connectivity)
- [ ] F-032: Knowledge base document upload (PDF/DOCX/TXT/MD/HTML/CSV)
- [ ] F-033: KB processing + indexing (text extraction, chunking, embedding, pgvector)
- [ ] F-034: AI activation gate (validate prerequisites, configure Smart Router)
- [ ] F-035: First Victory celebration (track first AI-resolved ticket)
- [ ] FP05: pgvector extension enablement in PostgreSQL
- [ ] Knowledge base Celery task module (processing pipeline)

---

## Week 7 GAPS — Approval System

- [ ] F-074: Approval queue dashboard data (filter, sort, search by ticket/action type)
- [ ] F-075: Batch approval (semantic cluster approval)
- [ ] F-076: Individual approve/reject (review AI action with confidence breakdown)
- [ ] F-077: Auto-handle rules + consequence display (LOCKED decision #22)
- [ ] F-078: Auto-approve confirmation flow (Jarvis shows consequences)
- [ ] F-079: Confidence score breakdown per-component
- [ ] F-080: Urgent attention panel (VIP/Legal — never auto-handled)
- [ ] F-081: Approval reminders (2h, 4h, 8h, 24h escalation)
- [ ] F-082: Approval timeout (72h auto-reject)
- [ ] F-083: Emergency pause controls (kill-switch per channel or all)
- [ ] F-084: Undo system (refund reversal, status change, email recall within window)
- [ ] Approval Celery tasks (timeout, reminders — stubs from Day 22 need completion)
- [ ] Approval API routes + service + schemas

---

## Week 8 GAPS — AI Core: Routing + Redaction + Guardrails

- [ ] F-054: Smart Router (3-tier LLM routing via LiteLLM/OpenRouter) — **UPDATED**: Now works in parallel with Technique Router (BC-013); Smart Router selects MODEL, Technique Router selects REASONING TECHNIQUE
- [ ] F-055: Model failover (detect rate limits/timeouts, fallback chain) — **UPDATED**: Also handles technique-specific model call fallback (e.g., if ToT node fails, fall back to CoT)
- [ ] F-056: PII Redaction Engine (regex + NER for SSN/credit card/email/phone)
- [ ] F-057: Guardrails AI (block harmful/off-topic/hallucinated responses) — **UPDATED**: CRP (F-140) runs BEFORE Guardrails in pipeline; both always-active but different purposes (efficiency vs safety)
- [ ] F-058: Blocked response manager + review queue
- [ ] F-059: Confidence scoring (calibrated 0-100: retrieval 30% + intent 25% + sentiment 15% + history 20% + context 10%) — **UPDATED**: Now also serves as primary trigger signal for Reverse Thinking (F-141) and Step-Back (F-142) activation
- [x] BC-013: **Technique Router** ✅ Infra Update: `backend/app/core/technique_router.py` — 14 trigger rules, signal extraction, deduplication, budget management, T3→T2 fallback
- [x] `shared/smart_router/` — Smart router module
- [x] `shared/technique_router/` — ✅ Infra Update: `backend/app/core/technique_router.py` (TechniqueRouter class + QuerySignals + TokenBudget + FALLBACK_MAP)
- [x] `shared/confidence/` — Confidence scoring module
- [ ] `shared/compliance/` — Compliance module
- [ ] LLM provider management (store configs, API keys, rate limits)
- [ ] Prompt template management system
- [x] New pip dependencies: `langgraph`, `dspy-ai`, `litellm` ✅ Infra Update

---

## Week 9 GAPS — AI Core: Classification + RAG + Response

- [ ] F-062: Ticket intent classification (multi-label: refund/technical/billing/complaint/feature_request) — **UPDATED**: Now also feeds Query Complexity Score (0.0-1.0) and Intent Type as signals to Technique Router (BC-013); triggers Self-Consistency (F-146) for billing/financial intents, CoT+ReAct for technical troubleshooting
- [ ] F-063: Sentiment analysis / Empathy engine (0-100 frustration, escalation at 60+, VIP at 80+) — **UPDATED**: Now also serves as primary trigger signal for UoT (F-144) when sentiment < 0.3 and Step-Back (F-142) for stuck reasoning
- [ ] F-064: Knowledge Base RAG (pgvector search, top-k retrieval, similarity threshold, reranking) — **UPDATED**: Provides factual data for ReAct technique execution; one of 5 tool integrations (RAG, Order API, Billing API, CRM, Ticket System)
- [ ] F-065: Auto-response generation (intent + RAG + sentiment → brand-aligned response) — **UPDATED**: Now the output channel for technique-processed responses; receives output from full technique pipeline (T1→T2→T3)
- [ ] F-066: AI draft composer (co-pilot mode: suggest/accept/edit/regenerate)
- [ ] F-050: AI-powered ticket assignment (specialty 40% + workload 30% + historical 20% + jitter 10%)
- [ ] `shared/knowledge_base/` — RAG + vector search module
- [ ] Signal Extraction Layer (NEW) — Extracts 10 signals for Technique Router: query complexity score, confidence score, sentiment score, customer tier, monetary value detection, conversation turn count, intent type, previous response status, reasoning loop detection, resolution path count

---

## Week 10 GAPS — AI Core: State Engine + Workflow

- [ ] F-053: GSD State Engine (Guided Support Dialogue — structured state machine) — **UPDATED**: Now Tier 1 always-active technique; provides conversation state context to ALL Tier 2/3 techniques; ESCALATE state auto-triggers Step-Back (F-142)
- [ ] F-060: LangGraph workflow engine (directed state machines with conditional branching) — **UPDATED**: Now orchestrates BOTH model × technique execution; each technique is a LangGraph node; Reasoning Loop Detection added as LangGraph monitor signal
- [ ] F-061: DSPy prompt optimization (automated prompt engineering) — **UPDATED**: Now also used for technique versioning & A/B testing (e.g., `cot-v1` vs `cot-v2`); performance metrics determine default version
- [ ] F-067: Context compression trigger (monitor tokens, compress when approaching limits) — **UPDATED**: Now manages token budget across ALL active techniques; handles overflow (Tier 3 reduced first, then Tier 2)
- [ ] F-068: Context health meter (healthy/warning/critical indicator) — **UPDATED**: Now monitors thread health for ThoT activation and detects reasoning loop for Step-Back trigger
- [ ] F-069: 90% capacity popup trigger (alert when conversation nears AI context limit)
- [ ] `shared/gsd_engine/` — GSD state machine module
- [x] `shared/techniques/` — ✅ Infra Update: `backend/app/core/techniques/` — BaseTechniqueNode ABC, ConversationState, GSDState, 12 stub nodes (CRP, Reverse Thinking, CoT, ReAct, Step-Back, ThoT, GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most)
- [x] Technique fallback mapping system (T3 → T2 equivalent fallbacks) ✅ Infra Update: FALLBACK_MAP in technique_router.py
- [x] Technique token budget allocator (Light=500, Medium=1500, Heavy=3000 tokens) ✅ Infra Update: TokenBudget class + TOKEN_BUDGETS in technique_router.py
- [ ] Technique performance metrics pipeline → feeds F-098
- [ ] Per-tenant technique configuration (Free=T1 only, Pro=T1+T2, Enterprise=all)
- [ ] State serialization/deserialization layer
- [ ] State migration between Redis and PostgreSQL
- [ ] Technique caching system (partial result caching for similar queries)

---

## Week 11-12 GAPS — AI Advanced + Semantic Intelligence + Technique Phase 1

- [ ] F-071: Semantic clustering (group similar tickets by embedding similarity)
- [ ] F-072: Subscription change proration calculation
- [ ] F-073: Temp agent expiry + auto-deprovisioning
- [ ] F-008: Voice demo system ($1 paywall, Twilio voice handling)

### AI Technique Framework — Phase 1: Foundation (F-140, F-142, F-141)
- [ ] F-140: CRP (Concise Response Protocol) — Tier 1 always-active; filler elimination, compression, redundancy removal, token budget enforcement; targets 30-40% response length reduction
- [ ] F-142: Step-Back Prompting — Tier 2 conditional; broader context seeking for narrow queries or stuck reasoning loops; ~300 tokens overhead; depends on F-053 (GSD), F-068 (Context Health)
- [ ] F-141: Reverse Thinking Engine — Tier 2 conditional; inversion-based reasoning for low-confidence queries (confidence < 0.7); ~300 tokens overhead; depends on F-059 (Confidence Scoring)

---

## Week 13 GAPS — Communication Channels

- [ ] F-121: Email inbound (Brevo parse webhook → ticket creation)
- [ ] F-120: Email outbound (send AI responses via Brevo, 5 replies/thread/24h rate limit)
- [ ] F-124: Email bounce handling (bounce/complaint events, update contact status)
- [ ] F-122: Out-of-office (OOO) detection
- [ ] F-125: Chat widget backend (Socket.io chat events, customer identity)
- [ ] F-126: SMS inbound/outbound (Twilio, TCPA consent check)
- [ ] F-127: Voice call system (Twilio voice webhook, STT → AI → TTS)
- [ ] F-128: Voice-First AI (full conversational voice)
- [ ] F-130: Social media integration (Twitter/X, Instagram, Facebook webhooks)
- [ ] FP08: SMS template system (Twilio)
- [ ] Channel-specific message formatting, character limits, media handling

---

### AI Technique Framework — Phase 2: Core Advanced (F-146, F-147, F-144)
- [ ] F-146: Self-Consistency — Tier 3 premium; multi-answer verification (3-5 independent answers) for financial actions; majority voting; ~750-1,150 tokens overhead; depends on F-062 (Intent Classification)
- [ ] F-147: Reflexion — Tier 3 premium; self-correction engine for rejected/failed responses; meta-reasoning trace logging; ~400 tokens overhead; depends on F-068 (Context Health)
- [ ] F-144: Universe of Thoughts (UoT) — Tier 3 premium; multi-solution generation with evaluation matrix (CSAT/Cost/Policy/Speed/Long-Term); ~1,100-1,700 tokens overhead; depends on F-080 (Urgent Attention), F-063 (Sentiment)

---

## Week 14-15 GAPS — Jarvis Command Center

- [ ] F-087: Jarvis chat panel backend (NL command parsing, intent → action dispatch)
- [ ] F-088: System status panel backend (aggregate health from Day 21 health system)
- [ ] F-089: GSD state terminal backend (expose GSD debug data)
- [ ] F-090: Quick command buttons (pre-parsed shortcuts)
- [ ] F-091: Last 5 errors panel (recent errors with stack traces)
- [ ] F-092: Train from error button (package error + ticket data → training point)
- [ ] F-093: Proactive self-healing (monitor external API failures, auto-retry with fallback)
- [ ] F-094: Trust preservation protocol (never say "we can't help" — queue + reassure)
- [ ] F-095: Jarvis "create agent" command (NL → provision → configure → train)
- [ ] F-096: Dynamic instruction workflow (create/modify/version-control instruction sets, A/B test)

---

## Week 16 GAPS — Dashboard + Analytics

- [ ] F-036: Dashboard home data (unified widget data)
- [ ] F-037: Activity feed backend (real-time via Socket.io)
- [ ] F-038: Key metrics aggregation (KPIs with configurable time ranges)
- [ ] F-039: Adaptation tracker (30-day AI learning progress)
- [ ] F-040: Running total — cumulative savings (AI vs human cost comparison)
- [ ] F-041: Workforce allocation (AI vs human distribution)
- [ ] F-042: Growth nudge alert (approaching limits, underutilizing features)
- [ ] F-044: Seasonal spike forecast (AI volume prediction)
- [ ] F-113: ROI Dashboard (REAL savings from actual usage data)
- [ ] F-109 to F-112: Analytics event pipeline, aggregation jobs, exports
- [ ] F-114 to F-118: Agent performance analytics (resolution rate, confidence, CSAT)
- [ ] F-116: Drift detection + reporting (daily AI model drift analysis)

---

## Week 17 GAPS — Integrations + Mobile

- [ ] F-131: Pre-built connectors (Zendesk, Freshdesk, Intercom, Slack, Shopify, GitHub, Stripe, TMS/WMS)
- [ ] F-132: Custom REST connector
- [ ] F-133: Custom GraphQL connector
- [ ] F-134: Incoming webhook integration
- [ ] F-135: MCP integration (Model Context Protocol)
- [ ] F-136: Database connection integration (read-only customer DB)
- [ ] F-137: Integration health monitor (per-integration health, 60s interval)
- [ ] F-138: Outgoing webhooks (push PARWA events to external systems)
- [ ] F-139: Circuit breaker (wrapping all outbound calls)
- [ ] F-085: Voice confirmation (mobile approve/reject via voice)
- [ ] F-086: Swipe gestures (mobile approve/reject)

---

## Week 18 GAPS — Public Facing + Billing Pages (Frontend Phase)

- [ ] F-001: Landing page with industry selector
- [ ] F-002: Dogfooding banner
- [ ] F-003: Live AI demo widget (chat)
- [ ] F-004: Pricing page with variant cards ($999/$2,499/$3,999)
- [ ] F-005: Smart bundle visualizer (add-on toggles, real-time price calc)
- [ ] F-006: Anti-arbitrage matrix (detect tier gaming)
- [ ] F-007: ROI Calculator (prospect-facing, projected savings)
- [ ] F-008: Voice demo paywall ($1)
- [ ] F-009: Newsletter subscription (footer, Brevo, double opt-in)
- [ ] **ENTIRE NEXT.JS FRONTEND** — No frontend code exists yet. Full build required.

---

### AI Technique Framework — Phase 3: Complex Reasoning (F-145, F-143, F-148)
- [ ] F-145: Tree of Thoughts (ToT) — Tier 3 premium; branching decision tree exploration with pruning for complex troubleshooting; ~800-1,500 tokens overhead; depends on F-060 (LangGraph Workflow)
- [ ] F-143: GST (Guided Sequential Thinking) — Tier 3 premium; strategic decision reasoning with 5 explicit checkpoints (Stakeholder Impact, Policy Alignment, Risk Assessment, Financial Impact, Recommendation); ~1,000-1,200 tokens overhead; depends on F-060 (LangGraph Workflow)
- [ ] F-148: Least-to-Most Decomposition — Tier 3 premium; complex query breakdown into ordered sub-queries with dependency resolution and completeness check; ~800-1,300 tokens overhead; depends on F-062 (Intent Classification), F-060 (LangGraph)

---

## Week 19 GAPS — Training Pipeline

- [ ] F-097: Agent dashboard (card-based view of all agents)
- [ ] F-098: Agent performance metrics (per-agent analytics) — **UPDATED**: Now also consumes technique performance metrics (activation rate, accuracy lift, token cost, latency impact, fallback rate, CSAT delta)
- [ ] F-099: Add/scale agent (Paddle trigger → auto-provision)
- [ ] F-100: Lightning training loop (baseline → production-ready)
- [ ] F-101: Training data preparation (clean, label, prepare datasets)
- [ ] F-102: Training execution (RunPod GPU — only after revenue, LOCKED #19)
- [ ] F-103: Training evaluation (compare against test set and production)
- [ ] F-104: Agent versioning (deploy, rollback, A/B test)
- [ ] F-105: Model comparison (side-by-side performance)
- [ ] F-106: Training dataset management (version, tag, search)
- [ ] F-107: Model rollback (one-click to previous version)
- [ ] F-108: Drift alert trigger (auto-train at 50 mistakes, LOCKED #20)
- [ ] Training data export pipeline
- [ ] Model comparison endpoints

---

## Week 20-21 GAPS — Polish + Testing + Hardening

- [ ] F-045: Contextual help system
- [ ] F-043: Feature discovery teasers
- [ ] Full test suite (unit + integration + BDD for all 139 features)
- [ ] Load testing (10,000 concurrent tickets)
- [ ] Security audit (BC-011 compliance, MFA, sessions, API keys)
- [ ] GDPR compliance verification (right-to-erasure, PII redaction, consent audit)
- [ ] FP06: GDPR data export/deletion job
- [ ] Error log review + fix
- [ ] API docs + deployment guide + runbook
- [ ] CI/CD real deployment workflows (currently placeholders)

---

## Cross-Phase Infrastructure Gaps

### Database Gaps
- [ ] DB03: `human_corrections` table -> training.py (needed Week 19) — EXISTS in migration, verify model
- [ ] DB04: `approval_batches` table -> approval.py (needed Week 7) — EXISTS in migration, verify model
- [ ] DB05: `notifications` table -> remaining.py (needed Week 7+) — EXISTS in migration, verify model
- [ ] DB06: `first_victories` table -> remaining.py (needed Week 6) — EXISTS in migration, verify model
- [ ] `user_notification_preferences` unique constraint on (user_id, channel, event_type)
- [ ] DC4: `sessions` table rename to `support_sessions`? (awaiting user confirmation)
- [x] DB07: `technique_configurations` table -> per-tenant technique enable/disable settings ✅ Infra Update
- [x] DB08: `technique_executions` table -> technique activation logs, token usage, latency, fallback tracking ✅ Infra Update
- [x] DB09: `technique_versions` table -> versioned technique implementations with A/B test metadata ✅ Infra Update

### Stale Config Files (Found in Pre-Week 3 Audit)
- [x] Delete `infra/docker/docker-compose.prod.yml` (stale, conflicts with root version) ✅ Day 23
- [x] Delete `infra/docker/.env.example` (stale, references OPENAI/SENDGRID/ANTHROPIC) ✅ Day 23
- [ ] DC2: Some docs say `tenant_id` vs `company_id` -> standardize to company_id (deferred — requires doc edits in /documents/)

### New Dependency Gaps (from AI Technique Framework)
- [x] DEP-01: `langgraph` package — Added to requirements.txt ✅ Infra Update
- [x] DEP-02: `dspy-ai` package — Added to requirements.txt ✅ Infra Update
- [x] DEP-03: `litellm` package — Added to requirements.txt ✅ Infra Update
- [ ] DEP-04: Verify `langgraph` + `dspy-ai` + `litellm` compatibility with existing FastAPI/Celery/Redis stack
- [x] DEP-05: Add technique-related Celery tasks for async technique execution and monitoring ✅ Infra Update

### CI/CD Gaps
- [ ] `deploy-backend.yml` is all echo placeholders — needs real AWS ECR/ECS integration
- [ ] `deploy-frontend.yml` is all echo placeholders — needs real S3/CloudFront integration
- [ ] Root-level `Dockerfile` doesn't exist (all Dockerfiles in infra/docker/ — acceptable but non-standard)

### Frontend (Entire Phase 4+ Dependency)
- [ ] **No frontend code exists** — entire Next.js app needs to be built
- [ ] `frontend/` directory missing (docker-compose frontend service will fail to build)
- [ ] Socket.io client library configuration (`frontend/src/lib/socket.ts`)
- [ ] All dashboard widgets, onboarding wizard, pricing calculator, etc.

---

## Doc Conflicts Resolved

- [x] DC1: F-008 Stripe -> Paddle (all docs updated)
- [x] DC3: OPENAI_API_KEY in Docker -> removed, using correct env names
- [x] DC6: Qdrant config removed, pgvector only
- [ ] DC2: Some docs say `tenant_id` vs `company_id` -> standardize to company_id (deferred - requires doc edits in /documents/)
- [ ] DC4: `sessions` table rename to `support_sessions` (deferred - requires model + migration change)
- [ ] DC5: Table count "50+" vs actual ~77 (deferred - update after Phase 2 complete)

---

## User Decisions Made

1. **Auth method**: Google OAuth OR email/password for account creation. Phone number only for instant demo flow (not for login).
2. **Payment provider**: Paddle for EVERYTHING (subscriptions + $1 voice demo). NO Stripe anywhere.
3. **Voice demo**: 3 minutes for $1, re-pay $1 for additional time.
4. **Vector DB**: pgvector (no Qdrant).
5. **LLM Keys**: User has own set of provider keys (not OpenAI/OpenRouter). Will provide when needed.
6. **$1 demo re-payment**: After initial 3-min demo expires, visitor can pay another $1 for more time.
7. **Payment Failure (Netflix-style)**: If payment fails → STOP service immediately. No grace period, no retry, no dunning. Like Netflix.
8. **Free Trials**: NOT offered. Paid subscription only.
9. **Dunning**: NOT needed. Payment fails = service stops.
10. **Grace Period**: NOT needed. Immediate stop on payment failure.
11. **Refunds (Netflix-style)**: NO REFUNDS. Pay for the month, use the month. No money back for cancelled subscriptions.
12. **Cancellation**: Cancel auto-renewal anytime. Access continues until the paid month ends. No partial refunds for unused days.
13. **Overage Rate**: $0.10/ticket over plan limit, billed daily.

## Unresolved Decisions (Still Blocked)

1. **Smart Router tiers**: Light/Medium/Heavy (specs) vs Light/Heavy/Ultra (tech assistant) -> Before Week 8
2. **Rename `sessions` table** to `support_sessions`? -> User confirmation needed

---

## AI Technique Framework — Feature Dependency Graph

From `documents/PARWA_AI_Technique_Framework.md`:

```
F-140 (CRP)           ← No dependencies (Tier 1, standalone)
F-141 (Reverse Think) ← Depends on F-059 (Confidence Scoring)
F-142 (Step-Back)     ← Depends on F-053 (GSD State), F-068 (Context Health)
F-143 (GST)           ← Depends on F-060 (LangGraph Workflow)
F-144 (UoT)           ← Depends on F-080 (Urgent Attention), F-063 (Sentiment)
F-145 (ToT)           ← Depends on F-060 (LangGraph Workflow)
F-146 (Self-Consist)  ← Depends on F-062 (Intent Classification)
F-147 (Reflexion)     ← Depends on F-068 (Context Health), conversation history
F-148 (Least-to-Most) ← Depends on F-062 (Intent Classification), F-060 (LangGraph)

CLARA (Tier 1)        ← Maps to F-057 (Guardrails) + F-065 (Auto-Response)
BC-013 (Tech Router)  ← Depends on F-059, F-062, F-063, F-060, F-053, F-068
```

### Technique Token Budget Summary

| Model Tier | Total Technique Budget | Tier 1 Reserve | Tier 2 Pool | Tier 3 Pool |
|-----------|----------------------|----------------|-------------|-------------|
| Light | 500 tokens | ~100 tokens | Up to 250 | Up to 150 |
| Medium | 1,500 tokens | ~100 tokens | Up to 700 | Up to 700 |
| Heavy | 3,000 tokens | ~100 tokens | Up to 1,450 | Up to 1,450 |

### Technique Fallback Mapping (T3 → T2)

| Tier 3 Technique | Falls Back To | Condition |
|-------------------|---------------|-----------|
| GST | CoT | Token budget exceeded |
| UoT | CoT + Step-Back | Token budget exceeded |
| ToT | CoT | Token budget exceeded |
| Self-Consistency | CoT | Token budget exceeded |
| Reflexion | Step-Back | Token budget exceeded |
| Least-to-Most | CoT + ThoT | Token budget exceeded |

---

## Audit Summary

| Metric | Value |
|--------|-------|
| Total gaps tracked | 190+ items across 21 weeks |
| Week 1-2 gaps | All 24 resolved ✅ |
| Week 3 gaps | 47 items (5 categories) — ALL DONE ✅ |
| Week 4-21 gaps | 130+ items — FUTURE |
| Cross-phase infra gaps | 24 items — ONGOING |
| NEW from AI Technique Framework | 9 features (F-140 to F-148) + BC-013 Technique Router |
| NEW dependency gaps | 5 items (langgraph, dspy-ai, litellm, compatibility, Celery tasks) |
| NEW database gaps | 3 items (technique_configurations, technique_executions, technique_versions) |
