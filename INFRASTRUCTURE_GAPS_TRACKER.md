# PARWA Infrastructure Gaps Tracker

> Discovered during comprehensive gap analysis (Days 6, 15-18, and pre-Week 3 audit).
> Items marked with target week should be addressed when that week begins.
> Items without a week are notes for future reference.
> Last updated: Pre-Week 3 (Day 19) — Full audit completed.

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

### GAP 1.1: Socket.io Business Event System
- [ ] Event type registry (enum/class) with all event types defined
- [ ] Event payload schemas (Pydantic) for each event type
- [ ] High-level emit helpers (emit_ticket_event, emit_ai_event, emit_approval_event, etc.)
- [ ] Business event handlers registered on Socket.io server
- [ ] Async event emission Celery task for fan-out
- [ ] Event rate limiting per tenant (max 100 events/sec)
- [ ] Event payload size validation (max 10KB)
- [ ] Integration tests for emit → handler → room broadcast flow
- [ ] Tests: ~70 new

### GAP 1.2: Multi-Tenant Middleware Hardening (BC-001)
- [ ] Auto-inject company_id into ALL SQLAlchemy queries via session events
- [ ] Explicit opt-out mechanism with @bypass_tenant for admin/system queries
- [ ] Tenant context propagation to Celery tasks (company_id in task headers)
- [ ] Redis key enforcement — all operations MUST use make_key(), reject raw keys
- [ ] API key auth also enforces tenant isolation (not just JWT)
- [ ] Integration test: API → middleware → DB → Celery → Redis, all tenant-scoped
- [ ] Tests: ~55 new

### GAP 1.3: Health Check System + Monitoring Config (BC-012)
- [ ] Health check orchestrator with dependency graph (degraded vs down)
- [ ] Per-subsystem health: PostgreSQL, Redis, Celery, Socket.io, Disk Space
- [ ] Per-queue Celery health: depth check for all 7 queues
- [ ] External API health probes: Paddle, Brevo, Twilio (connectivity only)
- [ ] Prometheus metrics endpoint (/metrics) with counters, histograms, gauges
- [ ] Detailed health endpoint (/health/detail) with latency info
- [ ] `monitoring/prometheus.yml` — Prometheus scrape config (MISSING — docker-compose will crash)
- [ ] `monitoring/grafana_dashboards/` — At least 3 dashboard JSON files (MISSING — docker-compose will crash)
- [ ] `monitoring/alerting/rules.yml` — Alertmanager rules
- [ ] Tests: ~65 new

### GAP 1.4: Celery Task Modules for All 7 Queues
- [ ] `email_tasks.py` — send_email_task, render_template_task, send_bulk_notification_task
- [ ] `analytics_tasks.py` — aggregate_metrics, calculate_roi, drift_detection
- [ ] `ai_tasks.py` — classify_ticket (light), generate_response (heavy), score_confidence (light)
- [ ] `training_tasks.py` — prepare_dataset, check_mistake_threshold, schedule_training
- [ ] `approval_tasks.py` — timeout_check, reminder_dispatch, batch_approval
- [ ] `billing_tasks.py` — daily_overage_charge, invoice_sync, subscription_check
- [ ] New Beat schedule entries: approval timeout (15min), reminders (30min), overage (daily 02:00), drift (daily 03:00), metrics (5min), training check (hourly)
- [ ] All tasks follow BC-004 pattern (company_id, retry, DLQ, idempotency)
- [ ] Tests: ~120 new

### GAP 1.5: Webhook Provider Handlers + Email Templates + Cleanup
- [ ] `webhooks/paddle_handler.py` — subscription.created/updated/cancelled, payment.succeeded/failed
- [ ] `webhooks/brevo_handler.py` — inbound_email parse → ticket creation
- [ ] `webhooks/twilio_handler.py` — sms.incoming, voice.call.started/ended
- [ ] `webhooks/shopify_handler.py` — orders.create, customers.create
- [ ] 6 additional email templates: welcome, mfa_enabled, session_revoked, api_key_created, approval_notification, overage_notification
- [ ] `AGENT_COMMS.md` — Inter-agent communication log
- [ ] `ERROR_LOG.md` — Error tracking log
- [ ] `PROJECT_STATE.md` — Live project state memory
- [ ] Delete stale `infra/docker/docker-compose.prod.yml`
- [ ] Delete stale `infra/docker/.env.example`
- [ ] Tests: ~70 new

---

## Week 4 GAPS — Ticket System (Phase 2 Start)

> Phase 2 starts after Week 3. These gaps will be discovered in detail when building.

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

---

## Week 5 GAPS — Billing System (Paddle)

- [ ] F-020: Paddle checkout integration (subscription creation, plan IDs, tax)
- [ ] F-021: Subscription management (upgrade/downgrade with proration)
- [ ] F-022: Paddle webhook handler (all events — depends on Day 23 paddle_handler.py)
- [ ] F-023: Invoice history (paginated list from Paddle, PDF download)
- [ ] F-024: Daily overage charging ($0.10/ticket over plan limit — Celery task exists from Day 22)
- [ ] F-025: Graceful cancellation flow (multi-step with retention offers)
- [ ] F-026: Cancellation request tracking (reason capture, analytics)
- [ ] F-027: Payment confirmation + verification (entitlement activation, welcome email)
- [ ] Billing API routes + service + schemas
- [ ] Plan entitlement enforcement middleware (check plan limits on API calls)

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

- [ ] F-054: Smart Router (3-tier LLM routing via LiteLLM/OpenRouter)
- [ ] F-055: Model failover (detect rate limits/timeouts, fallback chain)
- [ ] F-056: PII Redaction Engine (regex + NER for SSN/credit card/email/phone)
- [ ] F-057: Guardrails AI (block harmful/off-topic/hallucinated responses)
- [ ] F-058: Blocked response manager + review queue
- [ ] F-059: Confidence scoring (calibrated 0-100: retrieval 30% + intent 25% + sentiment 15% + history 20% + context 10%)
- [ ] `shared/smart_router/` — Smart router module
- [ ] `shared/confidence/` — Confidence scoring module
- [ ] `shared/compliance/` — Compliance module
- [ ] LLM provider management (store configs, API keys, rate limits)
- [ ] Prompt template management system

---

## Week 9 GAPS — AI Core: Classification + RAG + Response

- [ ] F-062: Ticket intent classification (multi-label: refund/technical/billing/complaint/feature_request)
- [ ] F-063: Sentiment analysis / Empathy engine (0-100 frustration, escalation at 60+, VIP at 80+)
- [ ] F-064: Knowledge Base RAG (pgvector search, top-k retrieval, similarity threshold, reranking)
- [ ] F-065: Auto-response generation (intent + RAG + sentiment → brand-aligned response)
- [ ] F-066: AI draft composer (co-pilot mode: suggest/accept/edit/regenerate)
- [ ] F-050: AI-powered ticket assignment (specialty 40% + workload 30% + historical 20% + jitter 10%)
- [ ] `shared/knowledge_base/` — RAG + vector search module

---

## Week 10 GAPS — AI Core: State Engine + Workflow

- [ ] F-053: GSD State Engine (Guided Support Dialogue — structured state machine)
- [ ] F-060: LangGraph workflow engine (directed state machines with conditional branching)
- [ ] F-061: DSPy prompt optimization (automated prompt engineering)
- [ ] F-067: Context compression trigger (monitor tokens, compress when approaching limits)
- [ ] F-068: Context health meter (healthy/warning/critical indicator)
- [ ] F-069: 90% capacity popup trigger (alert when conversation nears AI context limit)
- [ ] `shared/gsd_engine/` — GSD state machine module
- [ ] State serialization/deserialization layer
- [ ] State migration between Redis and PostgreSQL

---

## Week 11-12 GAPS — AI Advanced + Semantic Intelligence

- [ ] F-071: Semantic clustering (group similar tickets by embedding similarity)
- [ ] F-072: Subscription change proration calculation
- [ ] F-073: Temp agent expiry + auto-deprovisioning
- [ ] F-008: Voice demo system ($1 paywall, Twilio voice handling)

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

## Week 19 GAPS — Training Pipeline

- [ ] F-097: Agent dashboard (card-based view of all agents)
- [ ] F-098: Agent performance metrics (per-agent analytics)
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

### Stale Config Files (Found in Pre-Week 3 Audit)
- [ ] Delete `infra/docker/docker-compose.prod.yml` (stale, conflicts with root version)
- [ ] Delete `infra/docker/.env.example` (stale, references OPENAI/SENDGRID/ANTHROPIC)
- [ ] DC2: Some docs say `tenant_id` vs `company_id` -> standardize to company_id (deferred — requires doc edits in /documents/)

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

## Unresolved Decisions (Still Blocked)

1. **Smart Router tiers**: Light/Medium/Heavy (specs) vs Light/Heavy/Ultra (tech assistant) -> Before Week 8
2. **Rename `sessions` table** to `support_sessions`? -> User confirmation needed

---

## Audit Summary

| Metric | Value |
|--------|-------|
| Total gaps tracked | 170+ items across 21 weeks |
| Week 1-2 gaps | All 24 resolved ✅ |
| Week 3 gaps | 47 items (5 categories) — IN PROGRESS |
| Week 4-21 gaps | 120+ items — FUTURE |
| Cross-phase infra gaps | 15 items — ONGOING |
