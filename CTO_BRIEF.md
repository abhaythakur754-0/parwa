# PARWA — CTO Technical Brief & Codebase Map

**Author:** Your technical co-founder (AI)
**Built with:** Graphify knowledge graph (73,497 nodes / 146,840 edges / 2,204 communities)
**Last walked:** Full module-by-module pass, every subsystem
**Status:** Living document — update as we learn more

> Purpose: one place where the ENTIRE Parwa system is understood. No more
> "where is X" or "how does Y work". If you forget, read this first, then
> query the graph: `graphify query "..." --graph graphify-out/graph.json`

---

## 0. What Parwa Actually Is (plain-English, for the CEO)

Parwa is an **AI customer-care SaaS**. A business plugs it in, and Parwa
handles customer messages across **chat, email, SMS, and voice** — replying,
resolving tickets, escalating to humans when needed, and giving the business
an admin copilot ("Jarvis") that watches everything and flags problems.

It's sold in **3 tiers** (Mini $1K/mo, Growth $2.5K/mo, High $4K/mo). All
tiers use the *same* AI brain — the tier just controls how much horsepower
gets used per message.

The "brain" is an **8-step AI pipeline** (think: 8 specialists in a row, each
doing one job — read → route → fetch knowledge → reason → act → quality-check
→ deliver → learn). There's a *separate* 3-step admin pipeline ("Jarvis")
that watches the business, not the customer.

---

## 1. Tech Stack (the truth, not the docs)

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 16 (App Router) + React 19 + TS 6 | Tailwind 4, shadcn/ui (Radix), NextAuth v4, TanStack Query, Zustand, socket.io-client, next-intl, framer-motion |
| Backend | FastAPI (Python 3.12) + uvicorn, port 8000 | async, SQLAlchemy ORM, Alembic migrations |
| Performance core | **Rust + PyO3** (`backend/parwa_core/`) | Rate limiter, circuit breaker, crypto, HMAC verifier — exposed to Python via bridges |
| Main DB | **Supabase Postgres** | 156 tables, RLS on all, 18MB used of 500MB free tier |
| Local DB | **Prisma + better-sqlite3** | Only 10 models — frontend-local cache (auth/onboarding/KB), NOT the source of truth |
| Cache/queue | **Redis + Celery** | 33 Celery task modules. STATE.md is accurate (updated). |
| AI orchestration | **LangGraph** | Two graphs: `parwa_pipeline/graph_v2.py` (8-node, main) + `jarvis_pipeline/graph.py` (3-node, admin) |
| LLMs | Multi-provider via `SmartRouter` | "MAKER-aware 3-tier routing via free providers" — provider failover + health tracking |
| Vector store | Custom (`VectorStore` + `EmbeddingService`) | RAG retrieval, HyDE, multi-query, LLM reranker |
| Payments | **Razorpay (India) — sole provider** | Paddle fully removed 2026-06-24 — see §7 |
| Email | Brevo (inbound webhooks + outbound) | Bounce/complaint/OOO/spam detection |
| SMS/Voice | Twilio | |
| Realtime | socket.io (frontend) ← backend | Toasts, presence, typing, ticket updates |
| Auth | **Single JWT issuer (backend)** — frontend verifies only, see §6 | Custom JWT (HS256/RS256) + MFA + Google OAuth |
| Tool protocol | **MCP server** (`mcp_server/`) | Exposes 17 tool servers for AI assistants |
| Deploys | Docker Compose (dev + prod), render.yaml, vercel.json, Caddy + nginx | Multiple deploy targets exist |

---

## 2. The Two Pipelines (THE core of the product)

### 2.1 PARWA Pipeline — 8 nodes (`backend/app/core/parwa_pipeline/graph_v2.py`)

This is the MAIN product. Every customer message flows through it.

```
node_1_ingest_classify  →  node_2_smart_route  →  node_3_knowledge_fetch
   (ClassificationEngine)    (SmartRouter)         (RAGRetriever)
                                                         │
         ┌───────────────────────────────────────────────┘
         ▼
node_4_reasoning_engine  →  node_4_5_chain_of_verification
   (TechniqueRouter          (verification sub-step)
    + TechniqueExecutor
    + 13 techniques)
         │
         ▼
node_5_act_verify  →  node_6_quality_format  →  node_6_5_deliver
                       (GuardrailsEngine         (delivery sub-step)
                        + CLARAQualityGate)
         │
         ▼
node_7_simple_resolver  →  node_8_super_node
```

**Conditional routers** after nodes 1, 2, 6, 7 — the graph branches based on
classification confidence, tier, and quality score.

**The 13 AI techniques** (in `backend/app/core/techniques/`):
ChainOfThought, TreeOfThoughts, Reflexion, ReAct, GST, StepBack,
ThreadOfThought, SelfConsistency, LeastToMost, UniverseOfThoughts,
ReverseThinking, CRP, MAKER. Some have **stub placeholders**
(`stub_nodes.py`) — meaning not all are fully implemented. ⚠️ Verify which
are real vs stubbed.

**Supporting engines** (the "specialists" the nodes call):
- `SmartRouter` (god-node, 203 edges) — MAKER-aware 3-tier LLM routing. Used by Classification, ResponseGen, DraftComposer, AIPipeline, LangGraphWorkflow.
- `SignalExtractor` (221 edges) — pulls `QuerySignals` that drive routing.
- `ClassificationEngine` (196 edges) — intent + keyword classification.
- `CLARAQualityGate` (359 edges) — quality scoring.
- `GSDEngine` (456 edges) — "Get Stuff Done" conversation state machine (`ConversationState` + `GSDState`).
- `StateSerializer` (243 edges) — serializes pipeline state.
- `ContextCompressor` + `ContextHealthMeter` — context-window management.
- `ResponseGenerator` — composes final reply (CLARA + RAG + SmartRouter + BrandVoice + Sentiment + Template + TokenBudget).
- `DraftComposer` — drafts replies for human review.
- `LoopholeDetectionEngine` — rule-based scan of AI responses for exploitable loopholes.
- `ConfidenceScoringEngine` — 4-factor weighted scoring.
- `SelfHealingEngine` — auto-recovery from pipeline failures.
- `SentimentAnalyzer`, `LanguagePipeline` (Industry/Language enums), `RuleAIMigrationEngine`, `AIAssignmentEngine`, `EdgeCaseRegistry`.

### 2.2 Jarvis Pipeline — 3 nodes (`backend/app/core/jarvis_pipeline/graph.py`)

```
SENSE  →  EVALUATE  →  NOTIFY
```

Separate graph. Watches the BUSINESS, not customers. The `JarvisAwarenessEngine`
runs 8 rule checks on a schedule: `system_health`, `error_rate`, `agent_pool`,
`drift`, `quality`, `plan_usage`, `subscription`, `renewal`. When something's
wrong, `JarvisProactiveInjector` pushes an alert into the admin UI, and
`JarvisCommandService` can take actions (e.g. `_handler_call_customer`) and
generate copilot suggestions.

There's ALSO a separate `OnboardingJarvisOrchestrator` — a Jarvis-like flow
specifically for the onboarding wizard (`process_onboarding_message`).

⚠️ **P-002 from CLAUDE.md**: All 3 tiers use the SAME 8-node pipeline. Node 2
(SmartRouter) handles tier routing internally. Never make per-tier pipelines.

---

## 3. Channel Architecture (how messages get in/out)

Four "bridges" (`backend/app/core/*_bridge/`) all use the same `ingest_*` pattern:

| Bridge | Ingest method | Handler |
|---|---|---|
| `EmailBridge` | `ingest_email()` | `webhooks/brevo_handler.py` (Brevo inbound) |
| `SMSBridge` | `ingest_sms()` | `webhooks/twilio_handler.py` |
| `CRMBridge` | `ingest_ticket()` | `api/crm_webhooks.py` (HubSpot/Salesforce/Zoho/generic) |
| `PaymentBridge` | `ingest_webhook()` | `webhooks/paddle_handler.py` + Razorpay |
| (chat widget) | direct | `api/chat_widget.py` + `services/chat_widget_service.py` |
| (voice) | `VoiceChannelService` | `webhooks/twilio_handler.py` |

`ChannelDispatcher` (`core/channel_dispatcher.py`) coordinates outbound delivery.

Channel services: `EmailChannelService` (uses ClassificationEngine + OOO detection),
`SMSChannelService`, `VoiceChannelService`, `OutboundEmailService` (uses
BounceComplaint + OOO). Plus `BounceComplaintService`, `OOODetectionService`,
`SpamDetectionService` for email hygiene.

---

## 4. API Surface (85 FastAPI routers, grouped)

| Domain | Routers |
|---|---|
| **tickets-customers (16)** | tickets, ticket_lifecycle, ticket_messages, ticket_notes, ticket_timeline, ticket_search, ticket_bulk, ticket_merge, ticket_templates, ticket_classification, ticket_analytics, ticket_assignment, customers, approval, collisions, escalation |
| **jarvis-admin-onboarding (10)** | jarvis, jarvis_cc, jarvis_chat, jarvis_integrations, jarvis_onboarding, jarvis_routes, admin, admin_bootstrap, onboarding, onboarding_jarvis |
| **ai-pipeline (9)** | ai_engine, ai_agent, ai_classification, ai_signals, classification, signals, technique_config, workflow, builder_agent |
| **integrations (7)** | integrations, integration_cache, crm_actions, crm_webhooks, carrier_actions, custom_connectors, custom_fields |
| **channels-webhooks (6)** | channels, chat_widget, email_channel, sms_channel, voice_channel, webhooks |
| **billing-payments (4)** | billing, billing_razorpay, billing_webhooks, razorpay_checkout |
| **ops-monitoring (4)** | audit, debug, health, system_health |
| **auth-security (3)** | auth, mfa, api_keys |
| **tenant-config (3)** | models, shadow_mode, user_details |
| **knowledge-base (2)** | knowledge_base, rag |
| **other (19)** | admin_bootstrap, api_utils, bounce_complaint, client, cross_channel, deps, dlq, ecommerce_actions, flexpay, identity, notifications, ooo_detection, pricing, public, response, sla, sse, triggers, verification |

Frontend `src/app/api/` has **~50 Next.js routes**, many are `[...path]`
catch-all **proxies** to FastAPI (`backend-proxy.ts`). Direct routes: auth
(login/register/refresh/me/logout/google/verify-email/verify-otp/reset-password),
chat, health, book-demo, billing/status, billing/invoices, flexpay/*, etc.

---

## 5. Data Architecture (the truth about the "two databases")

### 5.1 Supabase Postgres = SOURCE OF TRUTH
- **38 SQLAlchemy model files** in `backend/database/models/`
- **32 Alembic migrations** in `backend/database/alembic/versions/`
- 156 tables, RLS enabled on all
- Models span: activity_log, ai_pipeline, analytics, api_key_audit, approval,
  billing, billing_extended, business_email_otp, chat_widget, core (User/Company/etc),
  core_rate_limit, crm_analysis, email_bounces, email_channel, email_delivery_event,
  flexpay, integration, jarvis, jarvis_activity, jarvis_cc, langgraph_dlq, onboarding,
  ooo_detection, outbound_email, outbound_webhook, phone_otp, provider_config,
  shadow_mode, sms_channel, technique, tickets, training, user_details, variant_engine,
  voice_channel, webhook_event

### 5.2 Prisma + SQLite = frontend-local cache (NOT source of truth)
Only 10 models: User, OnboardingSession, UserDetails, LegalConsent, Integration,
KnowledgeBase, KnowledgeDocument, Payment, Subscription, Post.
Used for: NextAuth sessions, onboarding wizard state, KB document cache.

⚠️ **Note**: frontend Prisma User (session/local cache) vs backend Supabase User
(source of truth) still coexist, but token issuance is unified — see §6.
Prisma `User` is written only by the gated local-auth fallback and the
onboarding cache; the backend remains authoritative for identity.

---

## 6. Authentication (✅ RESOLVED — was the biggest architectural risk)

**STATUS: FIXED.** The dual-JWT system described below was unified — the
backend is now the sole token issuer. Verified 2026 (this brief's original
claims were stale; re-verified by code audit with graphify).

**Current architecture:**

1. **Backend** (`backend/app/core/jwt_auth.py` + `auth_service.py`) — the ONLY
   token issuer. Supports HS256 and RS256 (see `scripts/RS256_MIGRATION_NOTES.md`).
2. **Frontend** (`src/lib/jwt.ts`) — verifies tokens only (`jwtVerify` via
   `jose`). The old `signAccessToken()`/`signRefreshToken()` functions were
   removed. Supports RS256 public-key verification (`JWT_PUBLIC_KEY`).
3. **Auth routes** (`src/app/api/auth/{login,register,google}/route.ts`) —
   pure proxies to the backend; store backend-issued tokens in httpOnly
   cookies (`parwa_at` / `parwa_rt`). No local fallback in production.
4. **Local fallback** (`src/lib/local-auth.ts` + `mintLocalTokens()`) — dev/
   sandbox resilience only, hard-gated behind `ENABLE_LOCAL_GOOGLE_AUTH=1`.
   Production (Render/Vercel) does NOT set it, so the backend stays sole issuer.

Also present: MFA (`mfa_service.py` — TOTP, backup codes), Google OAuth,
password reset, email OTP + phone OTP.

**Residual notes:** the historic `signup redirect race condition` patches
addressed symptoms of the old dual-issuer era; keep them, they are harmless.
Stale test `src/components/auth/__tests__/Day1Security.test.ts` (referenced
removed sign functions) was deleted in the 2026 docs-truthification pass.

---

## 7. Payments (✅ RESOLVED — was the second biggest risk)

**STATUS: FIXED.** Paddle was fully removed on **2026-06-24**. Razorpay is
the sole billing provider. (This brief's original "half-migrated, 29 files"
claim was stale; re-verified by code audit with graphify.)

**Current architecture:**

- `subscription_service.py` — DB-only. Docstring: "Paddle was removed on
  2026-06-24. Razorpay handles all subscription creation / cancellation /
  updates via `app.services.razorpay_service` (exposed at `/api/billing/razorpay/*`)."
- `invoice_service.py` — invoices created locally; `paddle_invoice_id` remains
  ONLY as a legacy DB column name (kept deliberately to avoid a production
  DB migration — contains no Paddle dependency).
- `overage_service.py` — no provider client; overages recorded in DB.
- Razorpay paths: `razorpay_service.py`, `api/billing_razorpay.py`,
  `api/razorpay_checkout.py`, `src/lib/flexpay/razorpay-integration.ts`,
  `src/components/razorpay/`.
- `webhooks/paddle_handler.py` is DELETED; Razorpay webhooks live in
  `api/billing_razorpay.py`. `process_paddle_webhook` Celery task is an
  intentional no-op kept so old scheduler entries don't crash.
- Legacy compatibility symbols (`PaddleOperationError`, deprecated
  `create/upgrade_subscription` methods that raise with Razorpay guidance)
  are intentional shims so old call sites fail loudly instead of silently.
- `services/payment_service.py` contains simulated demo providers
  (Paddle/Stripe/Razorpay) for the $1 Demo Pack — fake URLs, no real Paddle
  API calls anywhere (verified: zero `api.paddle.com` references).

**No action needed.** Do NOT run a DB migration to rename `paddle_*` columns
unless a dedicated decision is made — the names are cosmetic.

---

## 8. Background Jobs (Celery + Redis — 33 task modules)

`backend/app/tasks/` — `celery_app.py` + `celery_health.py` + 31 task modules:
ai_engine, ai, analytics, approval, billing, dlq_retry, email_channel, email,
error_callbacks, event, jarvis_awareness, jarvis_command, knowledge,
notification, payment_failure, periodic, pipeline, reconciliation,
redis_cleanup, self_healing, sla, sms, technique, ticket_lifecycle, ticket,
training, usage, webhook_recovery, webhook, workflow, + base_task + example_tasks.

⚠️ STATE.md says "no additional middleware (MySQL, Redis)". **Out of date** —
Redis + Celery are clearly in use. Update STATE.md.

---

## 9. MCP Server (Model Context Protocol)

`mcp_server/` — exposes Parwa's capabilities as MCP tools for AI assistants:
- **integrations/** (9): carrier, chat, crm, ecommerce, email, external_tool_bus, sms, ticketing, voice
- **knowledge/** (3): faq, kb, rag
- **tools/** (5): analytics, compliance, monitoring, notification, sla

Entry: `mcp_server/main.py`, base: `base_server.py`. This is a strategic asset
— it means Parwa can be driven by any MCP-compatible AI agent (Claude, etc.).

---

## 10. Builder Agent (Tier 2 — "agent builder")

`backend/app/core/builder_agent/` — `builder_pipeline.py`, `builder_state.py`,
`builder_non_llm.py` (has `maker_find_gaps()`), `builder_llm.py`.
Per `TIER_2_AGENT_BUILDER_ROADMAP.md`, this builds custom agents per tenant.
This is a future product line — verify it's not blocking the main pipeline.

---

## 11. Frontend Map

### Pages (`src/app/`)
- **(auth) group**: login, signup, forgot-password, reset-password
- **/auth**: mfa-setup, mfa-verify, verify-email
- **/dashboard** (18 pages): agents (new/setup), billing, calls, channels, cost-breakdown, crm-dlq, escalations, integrations, jarvis, knowledge, monitoring, settings, shadow-mode, tickets, variants
- **Standalone**: / (landing), /jarvis, /models, /onboarding, /pricing, /profile, /roi-calculator, /test-razorpay, /welcome/details

### `src/lib/` (40 files)
- **Stores** (Zustand): agents, approval, billing, call, collision, escalation, mfa, notification, presence, system-health, ticket, typing, variant
- **API clients**: analytics, channels, dlq, jarvis-cc, jarvis-pipeline, onboarding-jarvis, shadow-mode, voice
- **Core**: api, auth, auth-cookies, backend-proxy, backend-url, db, jwt, socket-client, supabase-db, utils
- **Feature libs**: ai-pipeline, email-brevo, email, sms, paddle, pricing-config, jarvis-ai-engine, integration-catalog, notifications

### `src/hooks/` (16)
useAuth, useJarvisCC, useJarvisChat, useJarvisPipeline, useOnboardingJarvis,
useShadowMode, useVariant, useRealtimeEvents, useSocket, usePollingFallback,
useRetryWithBackoff, useNetworkStatus, useKeyboardShortcut, useFocusTrap,
use-mobile, use-toast.

### `src/components/` (21 groups, 210 files)
approvals, auth, chat, common, dashboard, demo, flexpay, integrations, jarvis,
jarvis-cc, landing, models, notifications, onboarding, onboarding-jarvis,
pages, pricing, razorpay, shadow-mode, ui (shadcn — 48 files), __tests__.

⚠️ Largest frontend files (complexity hotspots):
- `src/app/dashboard/settings/page.tsx` — **2,321 lines** (should be split)
- `src/app/api/jarvis/[...path]/route.ts` — 1,888 (proxy)
- `src/app/dashboard/tickets/page.tsx` — 1,835
- `src/components/pages/TicketsPage.tsx` — 1,718
- `src/app/api/onboarding-jarvis/[...path]/route.ts` — 1,556
- `src/app/dashboard/escalations/page.tsx` — 1,280
- `src/hooks/useRealtimeEvents.ts` — 1,126

---

## 12. Infrastructure & Deploys

- **Dev**: `docker-compose.yml` (frontend 3000 + backend 8000 + DB + Redis)
- **Prod**: `docker-compose.prod.yml`, `render.yaml` (Render hosting), `vercel.json` (frontend?), `Dockerfile`, `deploy.sh`
- **Reverse proxy**: `Caddyfile` (local gateway) + `nginx/` (prod)
- **K8s**: `infra/k8s/` exists (aspirational? staging?)
- **Backup**: `infra/backup.sh` + `backup_cron.sh` + `restore.sh`
- **CI**: `.github/` workflows (need to verify what's wired)
- **Monitoring**: `infra/monitoring/` + `backend/app/api/system_health.py`

---

## 13. Code-Health Risks (ranked Critical → Minor)

### CRITICAL — all three resolved (verified 2026 code audit)
1. ~~**Dual JWT auth**~~ ✅ RESOLVED — backend is sole issuer; frontend verifies
   only. See §6.
2. ~~**Paddle half-migration**~~ ✅ RESOLVED — Paddle fully removed 2026-06-24.
   See §7.
3. ~~**STATE.md is stale**~~ ✅ RESOLVED — STATE.md now documents Redis +
   Celery accurately.

### HIGH
4. ~~**13 AI techniques, some are stubs**~~ ✅ RESOLVED — `stub_nodes.py`
   "Placeholder" classes are lazy-loading delegates: every `execute()` imports
   and calls the REAL implementation (`reverse_thinking.py`, `react.py`, etc.).
   All 13 techniques route to real processing logic. No empty desks.
5. ~~**Root-level script debt**~~ ✅ MOSTLY RESOLVED — probe/scratch files
   (`probe_llm_raw.py`, `probe_body_via_transform.py`, `probe_sourcedata.py`,
   `dup_probe.json`, `tickets-*.json`, `ticket-*.json`, `e2e_gen_test.py`,
   dead `backend/main.py`) deleted in the 2026 docs-truthification pass;
   `verify_deploy.py` moved to `scripts/`.
6. ~~**Two fake-CRM implementations**~~ ✅ RESOLVED — `fake-crm-server/` no
   longer exists; only `mini-services/fake-crm/index.ts` remains.
7. ~~**`backend/venv/` committed to repo**~~ ✅ NOT TRACKED — `git ls-files
   backend/venv` returns 0 files. (Large historical blobs do remain in old
   commits — see §16 repo-size note if shrinking is ever needed.)

### MEDIUM
8. **Settings page is 2,321 lines** — split into tabs/sub-components.
9. **Multiple pipeline files** — `graph_v2.py`, `langgraph_workflow.py`,
   `ai_pipeline.py`, `variant_pipeline_bridge.py`. CLAUDE.md P-002 says V2
   replaced the "3-pipeline system" — verify the old ones aren't still wired.
10. **945 test files** — huge test surface. Good, but verify they actually
    run (CI status unknown) and aren't skipped.
11. **`jwt_auth.py` line 190 `verify_access_token`** + frontend `jwt.ts` —
    confirm algorithm/secret alignment (RS256 implied by `.env.rs256.example`).

### MINOR
12. **38,764 files in repo** (incl. venv, .next, node_modules, tool-results).
    Tighten `.gitignore`.
13. **Multiple pricing JSON files** at root (`parwa_pricing.json`,
    `parwa_pricing_live.json`, `parwa_pricing_page.json`, `parwa_billing_page.json`,
    `razorpay_limits.json`, `razorpay_partial_capture.json`, `bank_limits.json`,
    `india_recurring.json`, `saas_payments.json`, `usd_inr_rate.json`).
    Consolidate into a config module.

---

## 14. How to Query the Graph (so you never read files blindly)

The graph lives at `parwa/graphify-out/graph.json` (73K nodes / 147K edges).

```bash
# Always export PATH first
export PATH="/home/z/.local/bin:$PATH"

# Find architectural hubs
graphify god-nodes --top 30 --graph graphify-out/graph.json

# Understand a specific symbol (class/function/file)
graphify explain "SmartRouter" --graph graphify-out/graph.json
graphify explain "build_parwa_pipeline" --graph graphify-out/graph.json

# Ask a question (BFS the graph)
graphify query "how does auth connect to the database?" --budget 3000 --graph graphify-out/graph.json
graphify query "Paddle Razorpay payment billing" --budget 2500 --graph graphify-out/graph.json

# Find what breaks if you change a file
graphify affected "backend/app/core/smart_router.py" --depth 3 --graph graphify-out/graph.json

# Shortest path between two symbols
graphify path "SmartRouter" "DatabasePool" --graph graphify-out/graph.json

# Update the graph after code changes (no LLM, free)
graphify update . --force
```

> **Rule (from CLAUDE.md §5):** Always query the graph BEFORE editing code.
> The codebase has 73K nodes. Guessing = broken code.

---

## 15. CTO Recommendations — What I'd Do First (partner-style)

Abhay, here's how I'd sequence the next 30 days, in plain business terms:

**Week 1 — Stop the bleeding (trust & money)** ✅ ALL DONE (verified 2026)
1. ~~**Kill the dual-auth bug.**~~ ✅ DONE — backend is the sole token issuer;
   the frontend only verifies and carries the badge. See §6.
2. ~~**Finish or formally accept the Paddle situation.**~~ ✅ DONE — Paddle
   fully removed 2026-06-24; Razorpay is the only billing provider. See §7.
3. ~~**Fix STATE.md.**~~ ✅ DONE — STATE.md documents Redis + Celery accurately.

**Week 2 — Verify the product actually works end-to-end**
4. ~~**Audit the 13 AI techniques.**~~ ✅ DONE — all "Placeholder" nodes are
   lazy delegates to real implementations; no no-op technique can be routed to.
   (See §13 item 4.)
5. **Run the full customer journey in a staging env**: signup → onboard →
   connect a channel → send a message → pipeline runs → ticket created →
   resolved → billed. Document where it breaks. The 945 test files don't
   prove this works — only a real run does.

**Week 3 — Clean the workshop** ✅ mostly done (2026 docs-truthification pass)
6. ~~**Move the root scripts to `scripts/`**, delete the throwaway ones.~~
   ✅ DONE — probe/scratch files deleted; `verify_deploy.py` moved to `scripts/`.
7. ~~**Remove `backend/venv/` from git**~~ ✅ VERIFIED NOT TRACKED (0 files in
   git index). Historical blobs remain in old commits only.
8. ~~**Pick one fake-CRM**, delete the other.~~ ✅ DONE — `fake-crm-server/`
   is gone; `mini-services/fake-crm/` is the only one.
9. **Split `settings/page.tsx`** (2,321 lines) into tabs. ← still open

**Week 4 — Build the next revenue thing**
10. Now that the foundation is trustworthy, pick ONE growth bet:
    - Ship the MCP server publicly (let external AI agents drive Parwa —
      differentiator), OR
    - Ship the Builder Agent (Tier 2 — custom agents per tenant = upsell), OR
    - Add a 4th channel (e.g. WhatsApp) using the existing bridge pattern.

My pick: **MCP server first.** It's 80% built, it's a real moat (none of
your competitors expose MCP), and it unlocks enterprise buyers who want to
wire Parwa into their existing AI stacks.

---

## 16. Open Questions for You (Abhay)

1. **Is Paddle supposed to be gone, or do we use both?** (Your docs contradict.)
2. **Which of the 13 techniques are actually shipping vs stubbed?**
3. **Is the Rust `parwa_core` extension actually loaded in prod?** (PyO3
   build step — easy to skip.)
4. **Where is prod actually hosted?** Render? Vercel? Docker on a VM?
5. **Is the Celery/Redis worker actually running in prod?** (33 task modules
   imply yes, but STATE.md says no Redis.)
6. **Do you have paying customers yet, or pre-revenue?** (Changes the risk
   tolerance for #1 and #2 above.)
7. **`jarvis-cli` — REMOVED.** It was a misread of Jarvis's role. Jarvis is
   the in-product owner layer (chat + notifications + variant bridge); no
   separate terminal ships. Escalations now notify the owner directly via
   the standard notification system (in-app + email).

Answer these and I'll refine the 30-day plan into a sprint board.

— Your technical co-founder
