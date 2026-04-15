# PARWA Execution Roadmap v2.0 — Part-by-Part Production Readiness

> **Last Updated:** April 16, 2026
> **Approach:** Build ONE part completely before moving to the next. No more "mark complete and skip."
> **Source:** Based on PARWA Complete Production Readiness Report (18-part assessment)

---

## PHILOSOPHY

1. **One part at a time.** Complete it fully. Test it. Verify it. Only then move on.
2. **No stubs allowed.** If a function returns fake data, it is NOT done.
3. **Real code or nothing.** MockVectorStore is not a vector store. A stub reconciliation task is not reconciliation.
4. **Parallel when independent.** Parts with no dependencies can run simultaneously.

---

## OVERALL STATUS — 18 Parts

| # | Part | Completeness | Priority | Status |
|---|------|-------------|----------|--------|
| 1 | Infrastructure & Foundation | ~55% | P0 | Pending |
| 2 | Onboarding System | ~60% | P0 | Pending |
| 3 | Three Variants & Billing | ~50% | P0 | Pending |
| 4 | Industry-Specific Variants | ~15% | P1 | Pending |
| 5 | Variant Orchestration | ~40% | P1 | Pending |
| 6 | Agent Lightning (Training) | ~20% | P1 | Pending |
| 7 | MAKER Framework | ~15% | P1 | Pending |
| 8 | Context Awareness / Memory | ~35% | P1 | Pending |
| 9 | AI Technique Engine (14 Techniques) | ~70% | P1 | Pending |
| 10 | Jarvis Control System | ~40% | P1 | Pending |
| 11 | Shadow Mode | ~0% | P2 | Pending |
| 12 | Dashboard System | ~30% | P1 | Pending |
| 13 | Ticket Management | ~65% | P1 | Pending |
| 14 | Communication Channels | ~30% | P2 | Pending |
| 15 | Billing & Revenue | ~50% | P0 | Pending |
| 16 | Training & Analytics | ~25% | P2 | Pending |
| 17 | Integrations | ~35% | P2 | Pending |
| 18 | Safety & Compliance | ~40% | P0 | Pending |

---

## EXECUTION ORDER — Systematic Priority

### Why This Order?

Each part is ordered by: (1) launch-blocking severity, (2) dependency chain, (3) parallel possibility.

---

### PART 18 — Safety & Compliance [FIRST]

**Priority:** P0 — Cannot launch without this.
**Current:** ~40% complete
**Why First:** PII at 40% accuracy means customer data leaks. Prompt injection at 15% means AI can be manipulated. Legal/compliance risk.

**What exists:**
- PII redaction engine (15 types) — but only 40% accurate
- Prompt injection defense (25+ rules, 7 categories) — but only 15% detection
- Guardrails AI (8-layer) — basic patterns only
- HMAC webhook verification — working
- Rate limiting — working
- Multi-tenant isolation — working
- JWT security — working

**What needs to be done:**
- Fix PII regex: add NER fallback, handle short emails (a@b.c), IP addresses, partial phones, names in context
- Expand prompt injection: add SQL injection, XSS, command injection, role-play attack patterns
- Validate guardrails on REAL LLM outputs (not mock data in tests)
- Build GDPR right-to-erasure endpoint
- Add training data isolation between tenants (tenant-scoped vector search, KB access)
- Add information leakage prevention (block revealing LLM strategy, model names, internal workflows)
- Add Docker security hardening (Redis auth, non-root containers, network isolation)
- Validate all 8 guardrail layers run on actual outputs

**Target:** PII 90%+, Prompt Injection 95%+, GDPR endpoint live, 100% tenant data isolation

**Dependencies:** None (can start immediately)

---

### PART 12 — Dashboard System [SECOND — parallel with Part 18]

**Priority:** P1 — Core product UI
**Current:** ~30% complete
**Why Second:** 4 of 7 dashboard pages are 404. 7 backend modules have ZERO frontend. Clients pay $999-$3,999/month and can't see their data.
**8-Day Plan:** See `PART12_DASHBOARD_8DAY_PLAN.md` — 155 items across 8 days

**What exists:**
- Dashboard home (/dashboard) — KPI cards, analytics, activity feed
- Channels page (/dashboard/channels) — channel cards
- Training page (/dashboard/training) — not in sidebar
- 8 orphaned chart components (ConfidenceTrend, AdaptationTracker, ROIDashboard, CSATTrends, QAScores, DriftDetection, GrowthNudge, TicketForecast)
- Backend APIs for: CRM, documents, billing, notifications, integrations, analytics, audit — ALL with no frontend

**What needs to be done (155 items):**
- **Day 1 — Foundation:** Header bar (8 items: plan badge, notification bell, system status, emergency pause, mode selector, user menu, logout), Sidebar restructure (13 nav items), Socket.io client (6 event types), System status API endpoint
- **Day 2 — Overview:** ROI comparison card (PROMINENT), First Victory banner, savings counter enhancement, active agents summary, growth nudge, system health strip, real-time activity feed
- **Day 3 — Tickets:** Full ticket list (search, filters, sort, pagination, bulk actions), ticket detail (conversation transcript, AI confidence, sentiment, GSD state, technique display, internal notes, reply box, export)
- **Day 4 — Agents:** Agent cards grid, per-agent LIVE activity view (what each agent is doing NOW), per-agent call records, call recording playback, agent metrics, train-from-errors flow, agent comparison
- **Day 5 — CRM + Conversations:** Customers page (CRM list, detail, ticket history, interaction timeline, lead pipeline, merge/dedup), Conversations page (all channels unified, call recording playback, chat transcripts, AI summaries, export)
- **Day 6 — Knowledge Base + Analytics:** Document management (upload, search, reindex, RAG test), Analytics page (wire all 8 orphaned components: ROI, confidence, adaptation, CSAT, forecast, drift, QA, growth nudge), report export (CSV/PDF, 7 types)
- **Day 7 — Billing + Integrations + Notifications:** Billing page (plan, usage meters, upgrade/downgrade/cancel, invoices, overage, buy agent/variant), Integrations page (6+ services, webhooks, channels), Notifications center (real-time, preferences, quick actions)
- **Day 8 — Settings + Approvals + Jarvis + Polish:** Settings tabs (Account, Team, Security, Notifications, API), Approvals page (queue, rules, analytics), Jarvis sidebar panel, Audit log viewer, responsive design, loading/empty/error states

**New pages to build:** Customers (CRM), Conversations, Analytics, Knowledge Base, Billing, Integrations, Notifications
**Existing pages to fix:** Tickets (404), Agents (404), Approvals (404), Settings (404)
**Backend APIs already built:** 33+ endpoints need frontend consumers

**Dependencies:** None for frontend pages. Mode selector needs Part 11 (Shadow Mode).

---

### PART 15 — Billing & Revenue [THIRD — parallel with Part 18 + Part 12]

**Priority:** P0 — Revenue engine. Clients pay $999-$3,999/month. Must be bulletproof.
**Current:** ~50% complete (core flows exist, but 5 critical architectural bugs + 33 gaps found)
**6-Day Plan:** See `PART15_BILLING_ROADMAP.md` — 105 items across 6 days

**What exists:**
- Monthly subscription creation via Paddle
- Mid-month upgrades with proration
- Cancel with Netflix-style grace period (access until period end)
- Overage calculation ($0.10/ticket, daily cron) — but usage never auto-incremented
- Invoice sync and PDF download
- Webhook processing (18 endpoints, 25+ handlers — most log-only)
- Usage tracking model (but NOT hooked to ticket lifecycle)

**Critical bugs found (5):**
1. Downgrades scheduled but NEVER executed — no cron job applies pending downgrades
2. Usage metering NOT hooked to ticket lifecycle — tickets_used never auto-incremented
3. Industry variants DISCONNECTED from billing — purchases are cosmetic, never affect limits
4. Entitlement enforcement only works for tickets — agents, team, KB, voice have NO limits
5. Calendar month vs billing period misalignment — usage resets on 1st, billing on anniversary

**Additional bugs (8):** email says 48hr but code stops immediately, create_transaction() missing on PaddleClient, double-counting in overage, agents not stopped on payment failure, ticket status lost on resume, fake variant price IDs, wrong plan names in ReAct tool, HMAC inconsistency

**What needs to be done (105 items across 6 days):**
- **Day 1 — Critical Fixes:** Fix all 8 bugs, hook usage metering to ticket lifecycle, fix billing period alignment, fix entitlement enforcement for ALL resources (agents/team/KB/voice/tickets), connect variant ticket stacking, change middleware from fail-open to fail-closed
- **Day 2 — Core Engine:** Downgrade execution cron (period-end), resource cleanup on downgrade (pause agents, downgrade team, archive docs, disable voice), yearly billing cycle (365-day periods, monthly↔yearly switching), exact 30-day billing periods everywhere
- **Day 3 — Variant Add-Ons:** Add/remove industry variants API, mid-year variant purchase with proration, variant entitlement stacking (tickets + KB), variant knowledge archive/restore on removal, Paddle subscription items for variants
- **Day 4 — Cancel/Data Lifecycle:** Netflix cancel improvements (feedback, save offer, consequences), 30-day data retention after cancel, data export ZIP endpoint, GDPR cleanup cron, re-subscription flow (within 30 days = restore data), payment failure: immediate stop + 7-day fix window, auto-retry failed payments
- **Day 5 — Financial Safety:** Chargeback handling (webhook + service stop + admin alert), admin refund system with Paddle integration, credit balance system, 24-hour cooling-off refund, customer spending cap (hard/soft), webhook backfill mechanism, dead letter queue, global overage max ($500/mo), anomaly detection, invoice audit
- **Day 6 — Features + Testing + Prep:** Trial period, subscription pause/resume, promo codes, multi-currency prep, company timezone, corporate/B2B invoicing, invoice amendments, spending analytics, budget alerts, voice/SMS tracking, 8 test suites, 5 dashboard-ready API endpoints

**All 43 issues mapped to specific day/item IDs in PART15_BILLING_ROADMAP.md**

**Dependencies:** None for billing logic. Dashboard UI for billing pages needs Part 12.

---

### PART 1 — Infrastructure & Foundation [FOURTH]

**Priority:** P0 — Platform foundation
**Current:** ~55% complete

**What exists:**
- PostgreSQL schema (50+ tables, migrations 001-023)
- Redis layer (partial, not all keys namespaced)
- Celery workers (7 queues, some tasks are stubs)
- Socket.io server (runs, not all events wired)
- Multi-tenant middleware (working)
- Docker compose (dev + prod)
- Nginx config (built)
- Health checks (built)
- Prometheus + Grafana (partial)

**What needs to be done:**
- Kubernetes manifests (none exist)
- Production .env setup documentation
- Redis key namespacing consistency
- End-to-end Docker prod build test
- SSL/HTTPS configuration in nginx
- Database backup strategy
- Sentry/error monitoring setup
- PostgreSQL pgvector extension enablement script
- Verify all Celery tasks are real (not stubs)

**Dependencies:** None

---

### PART 11 — Shadow Mode [FIFTH]

**Priority:** P2 — Critical for safe launch
**Current:** ~0% — ZERO code exists

**What needs to be built from scratch:**
- system_mode enum: SHADOW | SUPERVISED | GRADUATED (add to Company model)
- Shadow mode middleware: intercept all action executions, log to shadow_log
- shadow_log DB table: ticket_id, ai_recommendation, action, manager_decision, outcome
- Dashboard shadow mode view: manager sees AI recommendations, approves/rejects
- Mode selection UI in dashboard
- Jarvis reports current mode
- Auto-graduation logic: after N successful approvals, suggest Supervised mode
- Onboarding step for initial mode selection

**Dependencies:** Part 12 (Dashboard UI needed for shadow mode view)

---

### PART 14 — Communication Channels [SIXTH]

**Priority:** P2 — No customer messages without this
**Current:** ~30% complete

**What exists:**
- Email inbound (Brevo parse webhook, partial threading)
- Email outbound (partial, rate limiter built)
- Chat widget component (exists, not connected to AI)
- Twilio webhook handlers (SMS/Voice logic not built)

**What needs to be done:**
- Complete email inbound to AI to outbound full loop
- Connect chat widget to AI pipeline
- Build SMS channel (Twilio inbound/outbound + AI loop)
- Build voice channel (Twilio + STT + AI + TTS)
- Build social media channels (Twitter/X, Instagram, Facebook)
- Connect all channels to variant orchestration layer
- Shadow mode intercept before outbound send

**Dependencies:** Part 18 (Safety), Part 11 (Shadow Mode), Part 5 (Variant Orchestration)

---

### PART 3 — Three Variants & Billing [SEVENTH]

**Priority:** P0 — Core product differentiation
**Current:** ~50% complete

**What needs to be done:**
- Wire variant entitlements to all AI features
- Build yearly billing per variant
- Build variant-specific confidence thresholds enforcement
- Build per-instance billing tracking
- Connect variant selection to AI pipeline routing
- Wire Jarvis billing context (plan, limits, usage)

**Dependencies:** Part 15 (Billing), Part 18 (Safety)

---

### PART 2 — Onboarding System [EIGHTH]

**Priority:** P0 — First customer impression
**Current:** ~60% complete

**What needs to be done:**
- Complete KB vector indexing (currently uses MockVectorStore)
- Wire AI activation gate to real AI pipeline testing
- Build First Victory celebration screen
- Wire Shadow mode activation on day 1
- Build onboarding progress persistence across browser close
- Connect Jarvis to onboarding step tracking
- Build industry-specific onboarding customization

**Dependencies:** Part 18 (Safety), Part 11 (Shadow Mode), Part 9 (AI Techniques)

---

### PART 10 — Jarvis Control System [NINTH]

**Priority:** P1 — Operational backbone
**Current:** ~40% complete

**What exists:**
- Onboarding Jarvis (chat, command engine, ROI card, demo scenarios)
- Command parser (26+ commands)
- Various backend services

**What needs to be done:**
- Wire billing context to Jarvis (plan, usage, renewal date)
- Add upgrade/cancel/my-plan commands to Jarvis
- Wire ticket volume data to Jarvis context
- Build system status card in Jarvis chat
- Build GSD state terminal window
- Build quick command buttons in dashboard Jarvis
- Build last 5 errors panel
- Wire train from error button to training pipeline
- Build Jarvis create agent command (F-095)
- Build dynamic instruction workflow (F-096)

**Dependencies:** Part 15 (Billing), Part 13 (Tickets), Part 6 (Training)

---

### PART 8 — Context Awareness / Memory [TENTH]

**Priority:** P1 — AI needs memory
**Current:** ~35% complete

**What needs to be done:**
- Build omnichannel memory (chat to phone to email thread)
- Wire all system events into Jarvis context (pause, upgrade, cancel, training, channel down, ticket spike)
- Build customer cross-channel identity bridge
- Wire billing data into Jarvis context_json
- Wire dashboard button click tracking into context

**Dependencies:** Part 10 (Jarvis), Part 14 (Channels)

---

### PART 13 — Ticket Management [ELEVENTH]

**Priority:** P1 — Strongest backend, needs polish
**Current:** ~65% complete

**What needs to be done:**
- Build Tickets dashboard UI page (/dashboard/tickets)
- Complete SLA management (timezone, breach alerts)
- Enforce priority system across all ticket flows
- Complete AI-powered assignment scoring (currently stub)
- Complete omnichannel session linking

**Dependencies:** Part 12 (Dashboard UI)

---

### PART 9 — AI Technique Engine [TWELFTH]

**Priority:** P1 — Best built part (70%), needs wiring
**Current:** ~70% complete

**What needs to be done:**
- Wire all 14 techniques to live traffic (not just tests)
- Verify Tier 3 techniques gated to PARWA High variant in production
- Schedule DSPy optimization as Celery beat task
- Validate techniques fire on real email/SMS/voice tickets
- Build technique stacking validation

**Dependencies:** Part 14 (Channels), Part 18 (Safety)

---

### PART 4 — Industry-Specific Variants [THIRTEENTH]

**Priority:** P1 — Differentiation
**Current:** ~15% complete — almost nothing built

**What needs to be done:**
- Create industry_configs/ directory (ecommerce.py, saas.py, logistics.py, others.py)
- Each config: system prompts, blocked topics, allowed integrations, default KB structure
- Wire industry selection to AI pipeline
- Build industry-specific onboarding step
- Build industry-specific integrations per variant
- Build industry-specific KB templates

**Dependencies:** Part 18 (Safety), Part 9 (AI Techniques)

---

### PART 5 — Variant Orchestration [FOURTEENTH]

**Priority:** P1 — Connect variants to live traffic
**Current:** ~40% complete

**What needs to be done:**
- Build 60-second rebalancer (Celery periodic task)
- Wire cross-variant escalation to ticket flow
- Build per-instance billing tracking
- Connect variant orchestration to all channels
- Stress-test round-robin / least-loaded distribution

**Dependencies:** Part 14 (Channels), Part 3 (Variants)

---

### PART 6 — Agent Lightning (Training) [FIFTEENTH]

**Priority:** P1 — Key differentiator
**Current:** ~20% — mostly stubs

**What needs to be done:**
- Wire approval rejection to mistake_log table
- Build real 50-mistake threshold DB query (not stub)
- Build Colab/RunPod API integration for training jobs
- Build model versioning and deployment pipeline
- Wire Jarvis 'train from errors' command
- Build drift detection daily report

**Dependencies:** Part 13 (Tickets — for approval rejections), Part 10 (Jarvis)

---

### PART 16 — Training & Analytics [SIXTEENTH]

**Priority:** P2 — Stub pipeline to real
**Current:** ~25% complete

**What needs to be done:**
- Build real training pipeline (not stubs)
- Build ROI dashboard from real usage data
- Build agent performance metrics tracking
- Build drift detection daily report
- Build QA rating system post-interaction
- Build confidence trend dashboard

**Dependencies:** Part 9 (AI Techniques), Part 13 (Tickets), Part 6 (Training)

---

### PART 17 — Integrations [SEVENTEENTH]

**Priority:** P2
**Current:** ~35% complete

**What needs to be done:**
- Build MCP integration (F-135) — currently 4 lines
- Complete all webhook handlers (Shopify, Paddle events)
- Build integration settings UI in dashboard
- Build outgoing webhooks (push events to external systems)
- Build circuit breaker UI wrapper

**Dependencies:** Part 14 (Channels), Part 12 (Dashboard UI)

---

### PART 7 — MAKER Framework [LAST]

**Priority:** P1 — Most complex
**Current:** ~15% complete — bare stubs

**What needs to be done:**
- Build specialist agents (Order, Payment, Policy, Inventory, Communication)
- Build coordinator agent
- Build multi-agent orchestration (MAOS)
- Build variant-gating (PARWA and PARWA High only)
- Build inter-agent validation
- Build red-flagging anomaly escalation
- Build parallel agent execution

**Dependencies:** Everything else must be working first.

---

## PARALLEL EXECUTION MAP

Parts that can run simultaneously (no dependencies on each other):

```
WAVE 1 (Day 1 — Start immediately):
  Stream A: Part 18 — Safety & Compliance
  Stream B: Part 12 — Dashboard Pages
  Stream C: Part 15 — Billing & Revenue

WAVE 2 (After Wave 1):
  Stream D: Part 1  — Infrastructure
  Stream E: Part 11 — Shadow Mode (needs Part 12 dashboard)

WAVE 3 (After Wave 2):
  Stream F: Part 14 — Communication Channels
  Stream G: Part 3  — Three Variants
  Stream H: Part 13 — Ticket Management polish

WAVE 4 (After Wave 3):
  Stream I: Part 10 — Jarvis Control System
  Stream J: Part 4  — Industry-Specific Variants
  Stream K: Part 9  — AI Technique Wiring
  Stream L: Part 8  — Context Awareness

WAVE 5 (After Wave 4):
  Stream M: Part 5  — Variant Orchestration
  Stream N: Part 6  — Agent Lightning
  Stream O: Part 16 — Training & Analytics
  Stream P: Part 17 — Integrations

WAVE 6 (Last):
  Stream Q: Part 2  — Onboarding System
  Stream R: Part 7  — MAKER Framework
```

---

## PREVIOUS ROADMAP — ARCHIVED

The original BUILD_ROADMAP.md (Phases 1-5, Weeks 1-21) has been archived in concept. It served as the initial blueprint. The 18-part assessment revealed that many "complete" items were actually stubs or partial implementations. This roadmap v2.0 is the honest, part-by-part path to production.

**Original BUILD_ROADMAP.md is preserved at:** `docs/roadmaps/BUILD_ROADMAP.md`

---

## LOCKED DECISIONS (Cannot be changed)

| # | Decision | Rule |
|---|----------|------|
| #19 | No GPU training until revenue | Training pipeline can only use RunPod after PARWA earns money |
| #20 | 50 mistakes threshold | AI auto-triggers retraining at exactly 50 mistake reports. HARD-CODED. |
| #22 | Jarvis shows consequences before auto-approve | Display ALL potential actions, financial impacts, risks before enabling |
| #23 | Technique routing separate from model routing | BC-013 (techniques) and BC-007 (models) are independent systems |
