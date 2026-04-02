# PARWA — Complete Project Context Bible

> **Read this file in full. It contains everything needed to continue building PARWA.**
>
> Last updated: April 2026

---

## 1. WHAT IS PARWA?

PARWA is an **AI-powered customer support platform** with 500+ features (170+ AI features). It allows companies to deploy AI agents that handle customer support tickets across email, chat, SMS, voice, and social media — with human-in-the-loop approval for critical actions.

**Core Purpose:** "Make the hardest automation look effortless."

**Three Sellable Variants:**
- **Mini PARWA (The Freshy):** FAQs, ticket intake, up to 2 concurrent calls, escalates complex issues
- **PARWA (The Junior):** Resolves 70-80% autonomously, verifies refunds (never executes), recommends APPROVE/REVIEW/DENY
- **PARWA High (The Senior):** Complex cases, strategic insights, up to 5 concurrent calls, churn prediction, video support

**Tech Stack:** FastAPI (backend) + Next.js/Tailwind (frontend) + PostgreSQL/pgvector + Redis + Celery + Socket.io + Paddle (billing) + Brevo (email) + Twilio (SMS/voice) + LiteLLM/OpenRouter (AI) + DSPy + LangGraph + Docker + K8s + GCP

---

## 2. WHAT HAS BEEN COMPLETED

### Phase 1: Building Codes ✅ COMPLETE
12 reusable rule sets that apply to ALL 500+ features. Think of these as city building codes — every feature must comply.

| Code | Name | What It Enforces |
|------|------|-----------------|
| BC-001 | Multi-Tenant Isolation | Every query scoped by company_id. Zero cross-tenant data leakage. |
| BC-002 | Financial Actions | DECIMAL(10,2) for money. Atomic transactions. Idempotency. Audit trail. |
| BC-003 | Webhook Handling | HMAC verification. Idempotency via event_id. Async Celery. Response < 3s. |
| BC-004 | Background Jobs | Celery with company_id first param. max_retries=3. Exponential backoff. DLQ. |
| BC-005 | Real-Time (Socket.io) | Rooms: tenant_{company_id}. Event buffer. Reconnection recovery. |
| BC-006 | Email (Brevo) | Templates. 5 replies/thread/24h. OOO detection. Email loop prevention. |
| BC-007 | AI Model (Smart Router) | 3-tier routing (Light/Medium/Heavy). PII redaction before LLM. Per-company confidence thresholds. 50-mistake threshold LOCKED. |
| BC-008 | State Management (GSD) | Redis primary + PostgreSQL fallback. State machine for every ticket. |
| BC-009 | Approval Workflow | Supervisor+ for financial. Audit logged. Jarvis shows consequences before auto-approve. |
| BC-010 | Data Lifecycle (GDPR) | Retention policies. Right-to-erasure. PII redaction. |
| BC-011 | Auth & Security | Google OAuth (v1 only). MFA enforced. JWT 15min. Refresh 7d rotation. Max 5 sessions. |
| BC-012 | Error Handling | Structured errors. No stack traces to users. Graceful degradation. Circuit breakers. |

**Files:**
- `PARWA_Building_Codes_v1.md` (main)
- `PARWA_Building_Codes_v1.docx` (formatted)
- `PARWA_Building_Codes_v1.pdf` (formatted)
- `PARWA_Building_Codes_PART1.docx` (BC-001 to BC-006)
- `PARWA_Building_Codes_PART2.docx` (BC-007 to BC-012)

---

### Phase 2: Feature Catalog + Feature Specs ✅ COMPLETE

**Feature Catalog:** 139 major features across 13 categories with full dependency mapping.
- File: `PARWA_Feature_Catalog_v1.md`

**Feature Specs:** Detailed blueprints for ALL 139 features. Each spec includes:
- Overview, API endpoints, DB tables with columns/types/indexes, Building Code rules applied, Edge cases table, Acceptance criteria (Given/When/Then)

| Batch | Features | Lines | Content |
|-------|----------|-------|---------|
| Batch 1 | F-004, F-010, F-011, F-012, F-013, F-015, F-020, F-022, F-025, F-027, F-028, F-029 (12) | 1,566 | Auth, Billing, Onboarding |
| Batch 2 | F-032, F-033, F-034, F-036, F-046, F-047, F-074, F-075, F-076, F-078, F-080, F-083, F-084 (13) | 1,394 | Tickets, KB, Approval |
| Batch 3 | F-053, F-054, F-055, F-056, F-057, F-058, F-059, F-060, F-061, F-064, F-065, F-074, F-076, F-082, F-088, F-089, F-100 (16) | 1,705 | AI Core Engine |
| Batch 4 | F-030, F-038, F-046, F-048, F-053, F-054, F-055, F-056, F-062, F-065, F-070, F-074, F-076, F-077, F-078, F-083, F-084, F-087, F-088, F-089, F-091, F-093, F-094, F-095, F-098, F-102, F-104, F-105, F-116, F-120, F-121, F-131, F-137, F-138, F-139 (20) | 1,107 | Jarvis, Channels, Integration |
| Batch 5 | F-003, F-007, F-011, F-014, F-015, F-016, F-017, F-018, F-019, F-021, F-023, F-024, F-025, F-028, F-029, F-030, F-031, F-032, F-033, F-034 (17) | 1,114 | Public, Auth, Billing, Onboarding |
| Batch 6 | F-028, F-030, F-036, F-037, F-038, F-040, F-041, F-042, F-044, F-047, F-048, F-049, F-050, F-052, F-057, F-058, F-061, F-062, F-064, F-065, F-066, F-067, F-068, F-069, F-070, F-080 (15) | 691 | Dashboard, Tickets, AI |
| Batch 7 | F-050, F-071, F-075, F-077, F-079, F-080, F-081, F-082, F-084, F-088, F-089, F-091, F-092, F-094, F-095, F-097, F-098, F-099, F-100, F-101, F-102, F-103, F-107 (15) | 734 | Approval, Jarvis, Training |
| Batch 8 | F-021, F-030, F-059, F-061, F-067, F-072, F-084, F-085, F-088, F-094, F-098, F-100, F-101, F-102, F-103, F-105, F-106, F-109, F-110, F-111, F-112, F-113, F-115, F-116, F-118, F-119, F-123, F-125, F-132, F-134, F-135, F-136, F-137, F-138, F-139 (21) | 747 | Training, Analytics, Channels |
| Batch 9 | F-006, F-001, F-005, F-008, F-026, F-035, F-039, F-051, F-063, F-073, F-114, F-117, F-122, F-124 (14) | 661 | High+Medium remaining |
| Batch 10 | F-090, F-096, F-126, F-127, F-128, F-130, F-133, F-086, F-002, F-009, F-043, F-045, F-108, F-129 (14) | 691 | Medium+Low remaining |
| **TOTAL** | **139 features** | **10,410 lines** | **100% coverage** |

---

### Phase 3: Connection Map ✅ COMPLETE

Maps how every feature connects, communicates, and depends on every other feature. A developer reading this knows exactly what breaks if any feature changes.

| Part | Lines | Content |
|------|-------|---------|
| PART 1: Core Systems | 2,251 | Auth deps, Billing deps, Ticket lifecycle (17-step flow), AI pipeline connections (30-row table), Approval web, Shared DB tables (15 tables), Conflict analysis (19 items CC-001 to CC-019), Redis keys, Socket.io rooms, Celery queues |
| PART 2: Support Systems | 1,843 | Channel connections (5 ingestion paths), Integration connections (9 features), Jarvis command mappings (18+ NL commands), Analytics data sources, Training pipeline (4 trigger paths), Onboarding → Production (8-step journey) |
| **TOTAL** | **4,094 lines** | |

---

## 3. BUILD STRATEGY (6 TEAMS)

The platform is organized into 6 teams. Each team owns their domain. Teams communicate through API contracts.

### Team 1: Platform & Infrastructure (BUILD FIRST)
- Database schema, Redis, Auth (F-010 to F-019), multi-tenant middleware, Celery, Socket.io, Docker, K8s, error handling, logging, audit trail, rate limiting
- **Everyone depends on this. Nothing works without Team 1.**

### Team 2: Core Engine (Tickets & Approval)
- Ticket CRUD (F-046 to F-052), Approval system (F-074 to F-084), email channel, bulk actions, undo system
- **Depends on: Team 1**

### Team 3: AI/ML (The Brain)
- Smart Router (F-054), PII Redaction (F-056), Guardrails (F-057), Confidence (F-059), GSD Engine (F-053), RAG (F-064), Auto-response (F-065), Classification (F-049), Sentiment (F-063), DSPy (F-061), all AI sub-features
- **Depends on: Team 1 + uses Team 2's tickets**

### Team 4: Channels & Integrations
- Email (Brevo), Chat (Socket.io), SMS (Twilio), Voice (Twilio), Social, REST/GraphQL/Webhook connectors (F-131 to F-139), Circuit Breaker (F-139)
- **Depends on: Team 1 + Team 2 + Team 3**

### Team 5: Billing & Growth
- Paddle checkout/webhooks (F-020 to F-027), Onboarding wizard (F-028 to F-035), Landing page, Pricing (F-004, F-005), ROI Calculator (F-007)
- **Depends on: Team 1 (can start in parallel with Team 2)**

### Team 6: Analytics, Jarvis & Training
- Dashboard (F-036 to F-045), Analytics (F-109 to F-121), Jarvis Command Center (F-087 to F-096), Training pipeline (F-100 to F-108)
- **Depends on: ALL other teams**

### Build Order:
```
Week 1-4:  Team 1 (Foundation)
Week 3-4:  Team 5 starts (needs only Team 1)
Week 5-8:  Team 2 (Tickets) + Team 5 continues
Week 9-12: Team 3 (AI) + Team 4 (Channels) + Team 6 starts
Week 13-16: Team 3 continues + Team 4 continues + Team 6 continues
Week 17-20: Polish, testing, mobile
```

---

## 4. LOCKED DECISIONS (Cannot Be Changed)

| # | Decision | Detail |
|---|----------|--------|
| #19 | No training until revenue | Cannot spend on GPU training until PARWA earns money. When revenue starts, use RunPod for GPU. |
| #20 | 50 mistakes threshold | AI agent auto-triggers retraining at exactly 50 mistake reports. HARD-CODED. Cannot be configured. |
| #22 | Jarvis shows consequences before auto-approve | When enabling auto-approve rules, Jarvis must display ALL potential actions, financial impacts, and risks. User must explicitly confirm. |

---

## 5. UNRESOLVED CONFLICTS (Need User Decision)

| Conflict | Between | Impact |
|----------|---------|--------|
| **Billing provider** | Feature Specs say **Paddle**. Technical Assistant v9 says **Stripe/Razorpay**. | Affects F-020 to F-027 (8 feature specs) + webhook handling. |
| **Background jobs** | Feature Specs say **Celery**. Technical Assistant v9 says **ARQ**. | Affects BC-004 + all background task specs. |
| **OAuth method** | BC-011 says "Google OAuth only in v1". Feature Catalog has F-010 (email/password registration). | F-010 and F-013 exist in specs but may conflict with BC-011. |
| **Smart Router tiers** | Feature Specs say 3 tiers (Light/Medium/Heavy). Tech Assistant says Light/Heavy/Ultra. | Naming difference — may just need alignment. |
| **Payment in AI** | Tech Assistant examples use `stripe.Charge.create`. Our specs use Paddle API. | All code examples in v9 need updating if using Paddle. |

---

## 6. ALL FILES CREATED (Download These)

All files are in `/home/z/my-project/download/`:

### Building Codes
| File | Description |
|------|-------------|
| `PARWA_Building_Codes_v1.md` | Complete 12 Building Codes |
| `PARWA_Building_Codes_v1.docx` | Formatted Word document |
| `PARWA_Building_Codes_v1.pdf` | Formatted PDF |
| `PARWA_Building_Codes_PART1.docx` | BC-001 to BC-006 |
| `PARWA_Building_Codes_PART2.docx` | BC-007 to BC-012 |

### Feature Catalog
| File | Description |
|------|-------------|
| `PARWA_Feature_Catalog_v1.md` | All 139 features with categories, priorities, dependencies |

### Feature Specs (10 batches)
| File | Features | Lines |
|------|----------|-------|
| `PARWA_Feature_Specs_Batch1.md` | 12 Critical features | 1,566 |
| `PARWA_Feature_Specs_Batch2.md` | 13 Critical features | 1,394 |
| `PARWA_Feature_Specs_Batch3.md` | 16 Critical features | 1,705 |
| `PARWA_Feature_Specs_Batch4.md` | 20 Critical features | 1,107 |
| `PARWA_Feature_Specs_Batch5.md` | 17 High priority | 1,114 |
| `PARWA_Feature_Specs_Batch6.md` | 15 High priority | 691 |
| `PARWA_Feature_Specs_Batch7.md` | 15 High priority | 734 |
| `PARWA_Feature_Specs_Batch8.md` | 21 High priority | 747 |
| `PARWA_Feature_Specs_Batch9.md` | 14 remaining | 661 |
| `PARWA_Feature_Specs_Batch10.md` | 14 remaining | 691 |

### Connection Map
| File | Description |
|------|-------------|
| `PARWA_Connection_Map_PART1.md` | Core systems connections (2,251 lines) |
| `PARWA_Connection_Map_PART2.md` | Support systems connections (1,843 lines) |

### Source Documents (Read-Only Reference)
Located in `/home/z/my-project/upload/`:
- `CORRECTED_PARWA_Complete_Master_Document.md`
- `CORRECTED_PARWA_Complete_Backend_Documentation.md`
- `CORRECTED_PARWA_Complete_Frontend_Documentation.md`
- `CORRECTED_PARWA_Complete_Infrastructure_Documentation.md`
- `CORRECTED_PARWA_UI_Additional_Features.md`
- `PARWA_Technical_Assistant_Prompt_v9.docx` (build workflow reference)
- `technical_assistant_prompt.md` (build workflow reference)

---

## 7. KEY TECHNICAL DETAILS

### Database Schema (All Tables)
Over 50 PostgreSQL tables defined across 8 migration groups:
- Migration 001: Core (users, companies, refresh_tokens, mfa_secrets, backup_codes, api_keys, etc.)
- Migration 002: Billing (subscriptions, invoices, overage_charges, cancellation_requests, paddle_events)
- Migration 003: Tickets (tickets, ticket_messages, ticket_assignments, customers, channels, etc.)
- Migration 004: AI Pipeline (gsd_sessions, confidence_scores, guardrails_blocked_queue, prompt_templates, etc.)
- Migration 005: Approval (approval_records, auto_handle_rules, executed_actions, undo_log)
- Migration 006: Analytics (metric_aggregates, roi_snapshots, drift_reports, qa_scores)
- Migration 007: Training (training_runs, training_datasets, training_checkpoints, agent_mistakes)
- Migration 008: Integration & System (rest_connectors, webhook_events, mcp_connections, event_buffer, error_log, audit_trail)

**Every table has company_id column with index** (BC-001 multi-tenant isolation).

### Redis Key Patterns
- Auth: `parwa:mfa_setup:{user_id}`, `parwa:rate_limit:{key}`
- AI: `parwa:{company_id}:gsd:{ticket_id}`, `parwa:confidence:{ticket_id}`
- Real-time: `event_buffer:{company_id}`
- Socket.io rooms: `tenant_{company_id}`
- System: `parwa:health:{subsystem}`, `parwa:health:global`

### Celery Queues
- `default` — general tasks
- `ai_heavy` — heavy AI model calls
- `ai_light` — lightweight classification/scoring
- `email` — Brevo email sending
- `webhook` — incoming webhook processing
- `analytics` — metric calculations
- `training` — GPU training tasks

### Critical Path (Longest Dependency Chain)
```
Auth (F-013) → Tickets (F-046) → Classification (F-049) → RAG (F-064) → Auto-Response (F-065) → Guardrails (F-057) → Confidence (F-059) → Approval (F-074) → Auto-Approve (F-077) → Undo (F-084) → Dashboard (F-036) → Analytics (F-109) → ROI Dashboard (F-113)
```

---

## 8. FEATURE VARIANTS (Important Subtleties)

### Pricing (F-004, F-005)
- 3 plans: Starter ($999/mo), Growth ($2,499/mo), High ($3,999/mo)
- Annual toggle: 20% discount
- Starter: 3 agents, 1,000 tickets/mo, email+chat
- Growth: 8 agents, 5,000 tickets/mo, +SMS+voice, +AI training
- High: 15 agents, 15,000 tickets/mo, +social+voice, +priority support
- Smart Bundle (F-005): toggle add-ons that recalculate total price

### ROI — TWO Different Features
- **F-007 ROI Calculator** = PROSPECT-facing (landing page). Projected/estimated savings from demo inputs.
- **F-113 ROI Dashboard** = TENANT-facing (authenticated). REAL savings from actual usage data.
- These are NOT the same feature. They have different formulas, different data sources, different UIs.

### Smart Router (F-054) — 3 Tiers
- Light: GPT-4o-mini / Claude Haiku — fast, cheap, FAQ/simple queries
- Medium: GPT-4o / Claude Sonnet — balanced, reasoning tasks
- Heavy: GPT-4 / Claude Opus — thorough, expensive, complex/edge cases
- Auto-fallback: Light fails → Medium → Heavy
- Per-company tier configuration

### Approval — 4 Modes
1. Individual (F-076): One ticket at a time
2. Batch (F-075): Semantic cluster approval
3. Auto-Handle (F-077): Rules-based, Jarvis confirms consequences first
4. Emergency (F-080): VIP/Legal — ALWAYS human, never auto

### Training — 4 Trigger Paths
1. Manual: Jarvis "train from errors" command
2. Automatic: 50-mistake threshold (LOCKED, cannot change)
3. Scheduled: Drift detection daily report
4. DSPy: Prompt optimization A/B test

---

## 9. WHAT TO DO NEXT (Next Chat Instructions)

### Immediate: Resolve Conflicts
Tell the new chat agent to ask you about:
1. **Paddle vs Stripe** — affects 8 feature specs
2. **Celery vs ARQ** — affects BC-004

### Then: Start Building
Follow the Technical Assistant v9 workflow:
- **5 Builder agents per week** (Days 1-5 parallel, Day 6 tester)
- **Week 1-4**: Team 1 (Foundation) — database, auth, infra
- **Week 3-4**: Team 5 (Billing) — can run parallel with Team 1 completion
- **Week 5-8**: Team 2 (Tickets) + Team 5 continues
- Continue through all teams per the build order

### How to Use This File
Paste this entire file at the start of a new chat, then say:
> "Read the PARWA Context Bible. We are at the build phase. Start with Team 1 (Foundation) — Week 1. Generate the PROJECT_STATE.md and AGENT_COMMS.md for Week 1 following the Technical Assistant v9 format. Build the database schema, auth system, multi-tenant middleware, Celery infrastructure, Socket.io setup, and error handling framework. Follow Building Codes BC-001 through BC-012 strictly."

---

## 10. CATEGORIES & FEATURE LIST (Quick Reference)

| Cat | Name | Features | Count |
|-----|------|----------|-------|
| 1 | Public Facing | F-001 to F-009 | 9 |
| 2 | Auth & Security | F-010 to F-019 | 10 |
| 3 | Billing & Payments | F-020 to F-027 | 8 |
| 4 | Onboarding | F-028 to F-035 | 8 |
| 5 | Dashboard | F-036 to F-045 | 10 |
| 6 | Ticket Management | F-046 to F-052 | 7 |
| 7 | AI Core Engine | F-053 to F-073 | 21 |
| 8 | Approval & Control | F-074 to F-086 | 13 |
| 9 | Jarvis Command Center | F-087 to F-096 | 10 |
| 10 | Agent Mgmt & Training | F-097 to F-108 | 12 |
| 11 | Analytics & Reporting | F-109 to F-121 | 13 |
| 12 | Communication Channels | F-122 to F-130 | 9 |
| 13 | Integrations | F-131 to F-139 | 9 |
| **Total** | | | **139** |

Plus 150+ AI sub-features within Category 7 (per-intent prompt templates, model response formatters, retrieval strategies, hallucination detection patterns, token-budget managers, conversation summarization modes, language detection/translation pipelines, etc.)

---

## 11. TECHNICAL ASSISTANT V9 FORMAT (Build Method)

When building, follow this format from your Technical Assistant v9:
- **1 Zai agent = 1 day**. Agent builds all files sequentially.
- **5 Builder agents = 1 week** (Days 1-5 parallel). No cross-day dependencies within same week.
- **Day 6 = Tester Agent** — runs full week test suite.
- **Across weeks: files CAN depend on previous weeks' files.**
- **Every file:** unit test → black + flake8 → commit → push → verify GitHub CI green → next file.
- **PROJECT_STATE.md and AGENT_COMMS.md** live in GitHub repo root. Every agent reads at session start.
- **ERROR_LOG.md** tracks every error and fix.

The 13 fields every Builder task must include:
1. Files to build (exact paths, sequential order)
2. What each file does (one sentence)
3. Responsibilities (every function with expected behavior)
4. Dependencies
5. Expected output
6. Unit test files
7. BDD scenario satisfied
8. Error handling
9. Security requirements
10. Integration points
11. Code quality (type hints, docstrings, PEP 8, max 40 lines/function)
12. GitHub CI requirements
13. Pass criteria

---

## 12. FILE STRUCTURE (Project Layout)

```
parwa/
├── shared/                    # Shared components
│   ├── core_functions/        # Config, logger, base classes
│   ├── gsd_engine/            # GSD state machine
│   ├── smart_router/          # 3-tier LLM routing
│   ├── knowledge_base/        # RAG + vector search
│   ├── confidence/            # Confidence scoring
│   ├── sentiment/             # Empathy engine
│   ├── compliance/            # GDPR, PII
│   ├── mcp_client/            # MCP protocol
│   └── utils/                 # Common utilities
├── variants/                  # 3 sellable products
│   ├── mini/                  # Mini PARWA
│   ├── parwa/                 # PARWA (The Junior)
│   └── parwa_high/            # PARWA High (The Senior)
├── backend/                   # FastAPI app
│   ├── app/
│   │   ├── core/              # Middleware (tenant, auth, errors)
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── api/               # FastAPI routes
│   │   └── services/          # Business logic
│   └── alembic/               # DB migrations
├── frontend/                  # Next.js app
│   ├── app/                   # App Router pages
│   ├── components/            # React components
│   └── stores/                # Zustand state
├── workers/                   # Celery background tasks
├── database/                  # Schema + migrations + seeds
├── security/                  # RLS, HMAC, rate limiter
├── monitoring/                # Sentry, Prometheus, Grafana
├── infra/                     # Docker, K8s, Terraform
├── docs/                      # BDD scenarios, API docs
├── tests/                     # unit/, integration/, e2e/, bdd/
├── PROJECT_STATE.md           # Live project memory
├── AGENT_COMMS.md             # Team communication
└── ERROR_LOG.md               # Error tracking
```

---

**END OF CONTEXT BIBLE**
