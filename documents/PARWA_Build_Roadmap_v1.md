# PARWA Build Roadmap v1.0 — Infrastructure Blueprint

> **This is a blueprint, not a file list.** Actual file structure will be created during implementation.
>
> **Philosophy:** Build what you need now. Discover what's next from the code you just wrote. Don't plan week 15 before you've coded week 1.

---

## HOW THIS ROADMAP WORKS

**Three Rules:**

1. **Build infrastructure first.** Backend, database, auth, services — the skeleton. Nothing else works without it.
2. **Discover, don't presume.** Each phase reveals what the next phase actually needs. The AI phase will tell you what backend endpoints it needs. The frontend phase will tell you what APIs it needs. Build those when you know, not before.
3. **Parallel when independent, sequential when dependent.** If two things don't need each other, build them at the same time.

**Legend:**
- `→` means "must be built first"
- `||` means "can be built in parallel"
- `🔄` means "you'll come back to this" — discovered need from later phase

---

## PHASE 1: FOUNDATION (Weeks 1-3)

**Goal:** The platform exists. A developer can spin it up, run migrations, create a database, and authenticate a user. Nothing more.

### Week 1: Project Skeleton + Database

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Project scaffolding | FastAPI backend + Next.js frontend repos, Docker setup, env config, linters, CI pipeline | — |
| PostgreSQL + Alembic | Database connection, migration framework, all 8 migration groups (50+ tables) | BC-001 (every table has company_id) |
| Redis layer | Connection pooling, key namespace design (parwa:{company_id}:*), health checks | BC-005, BC-008 |
| Base error handling | Structured error responses, no stack traces to users, base exception classes | BC-012 |
| Logging + audit trail | Structured logging, audit_trail table, every write action logged | BC-012, BC-002 |

**Outcome:** You can run `docker-compose up`, database is created with all tables, Redis is connected, and any error returns a clean JSON response with a correlation ID.

**Depends on:** Nothing. This is ground zero.

---

### Week 2: Authentication System (F-010 to F-019)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| User registration (F-010) | Email/password signup, company creation, tenant isolation from day 1 | BC-011, BC-001 |
| Email verification (F-012) | Token generation, Brevo integration for sending verification emails, expiry handling | BC-006, BC-011 |
| Login system (F-013) | JWT access (15min) + refresh (7d rotation), bcrypt, credential validation | BC-011 |
| MFA setup (F-015) + Backup codes (F-016) | TOTP authenticator QR code, verification, one-time backup codes | BC-011 |
| Forgot/reset password (F-014) | Secure reset token via Brevo, password change with session invalidation | BC-006, BC-011 |
| Session management (F-017) | View active sessions, revoke individual or all, max 5 sessions enforced | BC-011 |
| Rate limiting (F-018) | Sliding window per-user on auth endpoints, progressive backoff, temp lockouts | BC-011, BC-012 |
| API key management (F-019) | Create/rotate/revoke keys, key auth middleware, usage audit logging | BC-011, BC-001 |

**Outcome:** A user can sign up, verify email, log in with MFA, manage sessions, and make API calls with a key. Every request is tenant-scoped.

**Depends on:** Week 1 (database, Redis, error handling, Brevo connection for emails)

---

### Week 3: Background Jobs + Real-Time + Middleware

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Celery infrastructure | Worker setup, 7 queues (default, ai_heavy, ai_light, email, webhook, analytics, training), task base class with company_id first param, retry/backoff/DLQ | BC-004 |
| Socket.io server | Server setup, room pattern (tenant_{company_id}), event buffer for reconnection, heartbeat | BC-005 |
| Multi-tenant middleware | Every request extracts company_id from JWT, injects into DB queries, rejects cross-tenant access | BC-001 |
| Webhook base framework | HMAC verification, idempotency via event_id, async processing, response < 3s | BC-003 |
| Health check system | Per-subsystem health (DB, Redis, Celery, external APIs), global health endpoint | BC-012 |

**Outcome:** Background tasks can be queued and processed. Real-time events can be pushed to browsers. Every API call is tenant-isolated. Incoming webhooks have a reusable verification layer.

**Depends on:** Week 2 (auth middleware for tenant extraction)

---

## PHASE 2: CORE BUSINESS LOGIC (Weeks 4-7)

**Goal:** Tickets can be created, classified, and assigned. The billing system works. Users can onboard. This is the product's heart.

### Week 4: Ticket System (F-046 to F-052)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Ticket CRUD (F-046) | Create, list (paginated/filter/sort), ticket lifecycle states (open → assigned → in_progress → resolved → closed) | BC-001 |
| Ticket detail + conversation (F-047) | Full message thread per ticket, internal notes vs customer messages, file attachments | BC-001, BC-005 |
| Ticket search (F-048) | Full-text search by customer, ID, content with fuzzy matching | BC-001 |
| Ticket bulk actions (F-051) | Multi-select: status change, reassign, tag, merge, close — with undo | BC-001, BC-009 |
| Omnichannel session model (F-052) | Single ticket linking messages from email/chat/SMS/voice/social with channel metadata | BC-005 |
| Customer identity resolution (F-070) | Match customer across channels by email/phone/social ID, merge profiles | BC-001, BC-010 |

**Outcome:** A ticket can be created via API, listed, searched, and assigned. Messages from different channels can be stitched into one conversation thread.

**Depends on:** Phase 1 (auth, DB, Celery, Socket.io)

**🔄 You'll return to this:** When building channels (Phase 4), you'll discover ticket ingestion needs you didn't anticipate — add them then.

---

### Week 5: Billing System (F-020 to F-027)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Paddle checkout integration (F-020) | Subscription creation via Paddle, plan IDs mapped to Starter/Growth/High, tax handling | BC-002, BC-003 |
| Paddle webhook handler (F-022) | ALL Paddle events (subscription.created/updated/cancelled, payment.succeeded/failed), HMAC verify, idempotent processing, async Celery dispatch | BC-003, BC-002 |
| Subscription management (F-021) | Upgrade/downgrade with proration, plan entitlement enforcement | BC-002, BC-009 |
| Payment confirmation (F-027) | Post-checkout verification, entitlement activation, welcome email | BC-002, BC-006 |
| Invoice history (F-023) | Paginated invoice list from Paddle, PDF download | BC-002, BC-001 |
| Graceful cancellation (F-025) + Tracking (F-026) | Multi-step cancellation with retention offers, reason capture | BC-002, BC-009 |
| Daily overage charging (F-024) | Cron: count yesterday's tickets, charge $0.10/ticket over plan limit, notify via email + Socket.io | BC-002, BC-004, BC-006 |

**Outcome:** A user can subscribe, pay, get invoices, upgrade, downgrade, and cancel. Overage charges run daily.

**Depends on:** Phase 1 (webhook framework, Celery, Brevo). Week 4 (ticket count for overage).

---

### Week 6: Onboarding System (F-028 to F-035)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Onboarding wizard backend (F-028) | 5-step state machine: company profile → legal consent → integrations → KB upload → AI activation. Save/resume support | BC-008 |
| Legal consent collection (F-029) | TCPA, GDPR, call recording consent with timestamps and IP storage | BC-010, BC-009 |
| Pre-built integration setup (F-030) | OAuth flows for Zendesk, Freshdesk, Intercom, Slack, Shopify, etc. | BC-003 |
| Custom integration builder (F-031) | REST/GraphQL/webhook/DB connection configuration with test connectivity | BC-003, BC-004 |
| KB document upload (F-032) | Accept PDF/DOCX/TXT/MD/HTML/CSV, store raw, trigger processing | BC-004, BC-001 |
| KB processing + indexing (F-033) | Text extraction, chunking, embedding generation, vector storage (pgvector), tenant-isolated | BC-004, BC-007 |
| AI activation gate (F-034) | Validate all prerequisites (consent ✓, integration ✓, KB indexed ✓), configure Smart Router, enable live processing | BC-007, BC-008 |
| First Victory celebration (F-035) | Track first AI-resolved ticket, trigger celebration event + email | BC-005, BC-006 |

**Outcome:** A new tenant can sign up, give consent, connect integrations, upload knowledge base, and activate their AI agent.

**Depends on:** Week 4 (ticket system — AI needs tickets to resolve). Week 5 (billing — KB processing has cost implications).

**🔄 You'll return to this:** When building AI (Phase 3), the AI activation logic will need real AI pipeline testing — not just a flag flip.

---

### Week 7: Approval System (F-074 to F-086)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Approval queue (F-074) | Pending actions dashboard data: filter, sort, search by ticket/action type | BC-009, BC-005 |
| Individual approve/reject (F-076) | Review AI proposed action with confidence breakdown, approve/reject/edit | BC-009, BC-002 |
| Batch approval (F-075) | Semantic cluster approval — approve groups of similar tickets at once | BC-009, BC-007 |
| Auto-handle rules (F-077) + Confirmation (F-078) | Rules engine for auto-approving specific actions. Jarvis MUST show consequences before enabling (LOCKED decision #22) | BC-009, BC-002 |
| Confidence score breakdown (F-079) | Per-component scores (retrieval, intent, sentiment, history, context) for transparency | BC-007 |
| Urgent attention panel (F-080) | VIP/Legal tickets — never auto-handled, always bubble to top | BC-009, BC-011 |
| Approval reminders (F-081) | Escalating notifications at 2h, 4h, 8h, 24h via in-app + email + push | BC-009, BC-004 |
| Approval timeout (F-082) | Auto-reject after 72h, log timeout, re-queue if appropriate | BC-009, BC-004 |
| Emergency pause (F-083) | Kill-switch to pause AI auto-handling per channel or all channels | BC-009, BC-011 |
| Undo system (F-084) | Reverse executed actions (refund reversal, status change, email recall within window) | BC-009, BC-002, BC-006 |

**Outcome:** Every AI action that has real-world impact (refunds, emails, status changes) goes through human review. Safety net with undo.

**Depends on:** Week 4 (ticket system — approvals act on tickets). Phase 1 (Celery for reminders/timeouts, Socket.io for real-time queue updates).

**🔄 You'll return to this:** When building Jarvis (Phase 4), the NL command layer will need to trigger approval actions — you'll add those API endpoints then.

---

## PHASE 3: AI ENGINE (Weeks 8-12)

**Goal:** PARWA becomes intelligent. Tickets get classified, responses get generated, and the approval system gets fed with AI proposals.

> **Important:** This phase will likely reveal missing backend pieces from Phase 2. Build them when discovered. That's the point.

### Week 8: AI Core — Routing + Redaction + Guardrails

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Smart Router (F-054) | 3-tier LLM routing (Light/Medium/Heavy) via LiteLLM/OpenRouter, per-company tier config, auto-fallback chain | BC-007 |
| Model failover (F-055) | Detect rate limits/timeouts/degraded responses, fall through to backup providers without dropping conversations | BC-007, BC-004 |
| PII Redaction Engine (F-056) | Regex + NER scan for SSN/credit card/email/phone, token replacement, redaction map in Redis (24h TTL) | BC-007, BC-010, BC-011 |
| Guardrails AI (F-057) | Multi-layer safety: block harmful/off-topic/hallucinated/policy-violating responses | BC-007, BC-010, BC-009 |
| Blocked response manager (F-058) | Review queue for blocked responses, admin can approve/edit/ban patterns | BC-007, BC-009 |
| Confidence scoring (F-059) | Calibrated 0-100 score: retrieval (30%) + intent (25%) + sentiment (15%) + history (20%) + context (10%) | BC-007, BC-008 |

**🔄 Backend discoveries expected:** The Smart Router will need API provider management (store provider configs, API keys, rate limits). Build a provider management module when you hit this.

**Depends on:** Phase 1 (Redis, Celery ai_heavy/ai_light queues). Phase 2 tickets (AI needs tickets to process).

---

### Week 9: AI Core — Classification + RAG + Response Generation

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Ticket intent classification (F-062) | Multi-label classifier: refund/technical/billing/complaint/feature_request. Uses Smart Router Light tier | BC-007, BC-008 |
| Sentiment analysis (F-063) | Empathy engine: 0-100 frustration score, triggers escalation at 60+, VIP routing at 80+ | BC-007, BC-005 |
| Knowledge Base RAG (F-064) | Vector search (pgvector), top-k retrieval, similarity threshold filtering, reranking | BC-007, BC-010 |
| Auto-response generation (F-065) | Combine intent + RAG context + sentiment → brand-aligned response. Uses Smart Router Medium tier | BC-007, BC-006 |
| AI draft composer (F-066) | Co-pilot mode: suggest drafts to human agents, accept/edit/regenerate | BC-007, BC-005 |
| Ticket assignment — AI powered (F-050) | Score-based matching: specialty (40) + workload (30) + historical accuracy (20) + jitter (10) | BC-001, BC-008 |

**🔄 Backend discoveries expected:** Prompt template management, response template storage, brand voice config per company. Build when needed.

**Depends on:** Week 8 (Smart Router, PII Redaction, Guardrails, Confidence). Week 6 (KB must be indexed for RAG).

---

### Week 10: AI Core — State Engine + Workflow

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| GSD State Engine (F-053) | Guided Support Dialogue — structured state machine for multi-step conversations. Redis primary + PostgreSQL fallback (BC-008) | BC-008, BC-007 |
| LangGraph workflow engine (F-060) | Graph-based orchestration: complex multi-step AI workflows as directed state machines with conditional branching and human checkpoints | BC-007, BC-008, BC-004 |
| Context compression trigger (F-067) | Monitor token usage, compress prior context when approaching window limits | BC-007, BC-008 |
| Context health meter (F-068) | Real-time context quality indicator (healthy/warning/critical) | BC-007, BC-008 |
| 90% capacity popup trigger (F-069) | Alert when conversation nears AI context limit, prompt fresh thread | BC-005, BC-008 |
| DSPy prompt optimization (F-061) | Automated prompt engineering against historical resolution metrics | BC-007, BC-004 |

**🔄 Backend discoveries expected:** The GSD engine will need a state serialization/deserialization layer, state migration between Redis and PostgreSQL, and session recovery logic. Build when you hit these.

**Depends on:** Week 9 (classification, RAG, response generation all feed into GSD state).

### Week 10.5: AI Technique Framework (F-140 to F-148)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Technique Router Engine (BC-013) | Analyzes query signals (complexity, confidence, sentiment, tier, monetary value) and selects optimal reasoning techniques per query. Separately from model routing (BC-007) | BC-013, BC-007 |
| CRP — Concise Response Protocol (F-140) | Tier 1 always-active technique that minimizes token waste, eliminates filler, reduces response length 30-40% while maintaining accuracy | BC-013, BC-007 |
| Reverse Thinking Engine (F-141) | Tier 2 technique: generates wrong answer, inverts to find correct one. Auto-triggers when confidence < 0.7 | BC-013, BC-007, BC-008 |
| Step-Back Prompting (F-142) | Tier 2 technique: AI steps back for broader context when query is narrow or AI is stuck. Auto-triggers on low sentiment or reasoning loops | BC-013, BC-007 |
| GST — Guided Sequential Thinking (F-143) | Tier 3 technique: strategic decision reasoning with sequential checkpoints. Auto-triggers on multi-party/policy impact queries | BC-013, BC-007, BC-009 |
| UoT — Universe of Thoughts (F-144) | Tier 3 technique: generates multiple diverse solutions, evaluates each. Auto-triggers for VIP or angry customers (sentiment < 0.3) | BC-013, BC-007, BC-009 |
| ToT — Tree of Thoughts (F-145) | Tier 3 technique: branching decision tree exploration. Auto-triggers when 3+ resolution paths exist | BC-013, BC-007 |
| Self-Consistency (F-146) | Tier 3 technique: generates multiple answers, returns most consistent. Auto-triggers for monetary amounts > $100 or financial queries | BC-013, BC-007, BC-002 |
| Reflexion (F-147) | Tier 3 technique: self-correction from rejected/failed responses. Auto-triggers when previous response was rejected | BC-013, BC-007, BC-008 |
| Least-to-Most Decomposition (F-148) | Tier 3 technique: breaks complex queries into sub-queries. Auto-triggers when complexity > 0.7 or task has 5+ sub-steps | BC-013, BC-007, BC-004 |
| Technique Performance Tracking | Log every technique execution: technique used, trigger signal, token cost, latency, outcome quality. Feeds into F-098 | BC-013, BC-004 |
| Per-Tenant Technique Config | Admin UI to enable/disable techniques per tenant. Tier 1 techniques locked (cannot disable) | BC-013, BC-001, BC-009 |

**Depends on:** Week 8 (Smart Router, Confidence Scoring), Week 9 (Sentiment Analysis), Week 10 (GSD Engine, LangGraph)

**Note:** The Technique Router works alongside (not replaces) the Smart Router. BC-007 selects which MODEL to use; BC-013 selects which TECHNIQUE to apply. Both execute for every query.

---

### Week 11-12: AI Core — Advanced Features + Semantic Intelligence

**What to build (these can run in parallel):**

| Module | Purpose | Building Codes | Parallel? |
|--------|---------|----------------|-----------|
| Semantic clustering (F-071) | Group similar tickets by embedding similarity for batch operations | BC-007, BC-004 | ✅ with others |
| Subscription change proration (F-072) | Calculate prorated charges on plan changes mid-cycle | BC-002, BC-001 | ✅ with others |
| Temp agent expiry (F-073) | Auto-deprovision temp agents, reassign tickets | BC-002, BC-004, BC-011 | ✅ with others |
| Voice demo system (F-008) | $1 paywall for voice AI demo (backend payment + Twilio voice handling) | BC-002 | ✅ with others |

**Depends on:** Week 8-10 (needs AI pipeline functional for semantic clustering and voice demo).

---

## PHASE 4: CHANNELS + JARVIS + DASHBOARD (Weeks 13-17)

**Goal:** PARWA talks to the outside world (email, chat, SMS, voice, social). Jarvis lets admins control everything via natural language. Dashboard shows what's happening.

> **This is where frontend work begins in earnest.** The backend APIs from Phases 1-3 define what the frontend needs.

### Week 13: Communication Channels (F-120 to F-130)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Email inbound (F-121) | Brevo parse webhook → ticket creation. OOO detection (F-122), email loop prevention | BC-003, BC-006 |
| Email outbound (F-120) | Send AI responses via Brevo. Rate limit: 5 replies/thread/24h (BC-006) | BC-006 |
| Email bounce handling (F-124) | Process bounce/complaint events, update contact status | BC-006, BC-010 |
| Chat widget backend (F-125) | Socket.io chat events, customer identity via cookie/session, message persistence | BC-005, BC-001 |
| SMS inbound/outbound (F-126) | Twilio SMS webhook, TCPA consent check before sending | BC-003, BC-005, BC-010 |
| Voice call system (F-127) | Twilio voice webhook, STT → AI → TTS pipeline | BC-003, BC-005, BC-007 |
| Voice-First AI (F-128) | Full conversational voice AI: speech-to-text, AI processing, text-to-speech | BC-005, BC-007 |
| Social media integration (F-130) | Twitter/X, Instagram, Facebook webhooks, OAuth token management | BC-003, BC-001 |

**🔄 Backend discoveries expected:** Each channel will need channel-specific message formatting, character limits, media handling, consent flows. Build when you implement each channel.

**Depends on:** Week 4 (ticket system), Week 8-9 (AI pipeline for auto-responses).

---

### Week 14-15: Jarvis Command Center (F-087 to F-096)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Jarvis chat panel backend (F-087) | NL command parsing via Smart Router Medium tier, intent → feature action dispatch | BC-007, BC-005, BC-011 |
| System status panel backend (F-088) | Aggregate health: LLM status, queue depths, approval backlog, agent count, integration connectivity | BC-005, BC-012 |
| GSD state terminal backend (F-089) | Expose GSD state machine debug data: active step, next step, pending decisions, variables | BC-008, BC-005 |
| Quick command buttons (F-090) | Pre-parsed command shortcuts that bypass NL parsing | BC-005 |
| Last 5 errors panel (F-091) | Recent errors with stack traces, affected tickets, timestamps | BC-012, BC-005 |
| Train from error button (F-092) | Package error context + ticket data into training data point | BC-007, BC-004 |
| Proactive self-healing (F-093) | Monitor external API failures, auto-retry with fallback before alerting humans | BC-012, BC-004, BC-003 |
| Trust preservation protocol (F-094) | When external systems fail, never tell customer "we can't help" — queue actions, provide reassuring messaging | BC-012, BC-007, BC-005 |
| Jarvis "create agent" (F-095) | NL agent creation: parse request → provision agent → configure permissions → trigger training | BC-007, BC-001, BC-011 |
| Dynamic instruction workflow (F-096) | Create/modify/version-control instruction sets for AI agents, A/B test variants | BC-007, BC-008, BC-001 |

**🔄 Backend discoveries expected:** Jarvis NL commands will need a command registry, permission checks per command, and response formatting. Build when implementing each command.

**Depends on:** Phase 3 (AI pipeline), Phase 2 (approval, ticket, billing systems).

---

### Week 16: Dashboard + Analytics (F-036 to F-045, F-109 to F-121)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Dashboard home data (F-036) | Unified widget data: activity feed, metrics summary, adaptation tracker, savings counter, alerts | BC-001, BC-011 |
| Activity feed backend (F-037) | Real-time event stream via Socket.io: new tickets, AI resolutions, escalations, team actions | BC-005, BC-001 |
| Key metrics aggregation (F-038) | KPIs: total tickets, AI resolution rate, avg response time, CSAT, integration health. Configurable time ranges | BC-001 |
| Adaptation tracker (F-039) | 30-day AI learning progress: accuracy trend, resolution rate, satisfaction improvement | BC-001, BC-008 |
| Running total — cumulative savings (F-040) | Compare AI-resolved ticket costs vs estimated human costs, running dollar total | BC-001, BC-002 |
| Workforce allocation (F-041) | AI vs human ticket distribution by category, channel, time period | BC-001 |
| Growth nudge alert (F-042) | Usage pattern analysis: approaching limits, underutilizing features, upgrade recommendations | BC-006, BC-001 |
| Seasonal spike forecast (F-044) | AI-powered support volume prediction based on historical patterns | BC-007, BC-001 |
| ROI Dashboard (F-113) | REAL savings from actual usage data (not prospect projections). Different from F-007. Tracks cost per ticket, labor savings, revenue impact | BC-001, BC-002 |
| Analytics event pipeline (F-109 to F-112) | Metric aggregation jobs, data warehouse feeds, export capabilities | BC-004, BC-001 |
| Agent performance analytics (F-114 to F-118) | Per-agent: resolution rate, confidence, CSAT, escalation frequency, handle time | BC-007, BC-001 |
| Drift detection + reporting (F-116) | Daily AI model drift analysis, comparison against baseline performance | BC-007, BC-004 |

**Depends on:** Phase 2 (tickets, billing for cost data), Phase 3 (AI pipeline for resolution metrics).

---

### Week 17: Integrations + Mobile (F-131 to F-139, F-085, F-086)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Pre-built connectors (F-131) | Zendesk, Freshdesk, Intercom, Slack, Shopify, GitHub, Stripe, TMS/WMS | BC-003 |
| Custom REST connector (F-132) | User-configured REST API calls with request/response mapping | BC-003 |
| Custom GraphQL connector (F-133) | GraphQL query/mutation support with subscription | BC-003 |
| Incoming webhook integration (F-134) | Custom webhook endpoints with payload transformation | BC-003 |
| MCP integration (F-135) | Model Context Protocol — AI agents use external tools as reasoning context | BC-003 |
| Database connection integration (F-136) | Read-only customer DB connections for RAG context | BC-003, BC-011 |
| Integration health monitor (F-137) | Per-integration health checks every 60s, status tracking | BC-012 |
| Outgoing webhooks (F-138) | Push PARWA events to external systems (Slack, custom) | BC-003 |
| Circuit breaker (F-139) | State machine (CLOSED → OPEN → HALF_OPEN), wraps all outbound calls | BC-012, BC-003 |
| Mobile: Voice confirmation (F-085) | Approve/reject tickets via voice on mobile | BC-009, BC-007 |
| Mobile: Swipe gestures (F-086) | Swipe left (reject) / right (approve) for mobile approval | BC-009, BC-005 |

**Depends on:** Phase 2 (approval system), Phase 3 (AI for voice), Week 13 (channel infrastructure).

---

## PHASE 5: PUBLIC FACING + TRAINING + POLISH (Weeks 18-21)

**Goal:** The platform is complete. Now add the public-facing pages, training pipeline, and polish.

### Week 18: Public Facing + Billing Pages (F-001 to F-009, F-004, F-005, F-007)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Landing page (F-001) | Dynamic landing with industry selector tailoring content | BC-012 |
| Pricing page (F-004) | Three tier cards (Starter $999 / Growth $2,499 / High $3,999), annual toggle 20% discount, feature matrix | BC-001, BC-002 |
| Smart Bundle Visualizer (F-005) | Interactive add-on toggles that recalculate price in real time | BC-001, BC-002 |
| Anti-arbitrage matrix (F-006) | Detect tier gaming by comparing volume patterns, surface upgrade nudges | BC-002, BC-001 |
| ROI Calculator (F-007) | PROSPECT-facing. Input: headcount, avg ticket cost, volume → Output: projected monthly/annual savings. DIFFERENT from F-113 (which is tenant-facing with real data) | BC-001 |
| Live AI demo widget (F-003) | Embedded chat letting visitors talk to PARWA AI without signup | BC-007, BC-005 |
| Dogfooding banner (F-002) | "PARWA's own support is powered by PARWA" credibility banner | BC-012 |
| Newsletter subscription (F-009) | Footer email capture with Brevo integration, double opt-in | BC-006, BC-010 |

**Depends on:** Phase 2 (billing APIs), Phase 3 (AI for live demo widget).

---

### Week 19: Training Pipeline (F-097 to F-108)

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Agent dashboard (F-097) | Card-based view of all agents: status, specialty, performance, quick actions | BC-005, BC-001 |
| Agent performance metrics (F-098) | Per-agent analytics: resolution rate, confidence, CSAT, escalation frequency | BC-007, BC-001 |
| Add/scale agent (F-099) | Agent provisioning → Paddle checkout → auto-provision with base training | BC-002, BC-001 |
| Lightning training loop (F-100) | Rapid training: new agent from baseline to production-ready | BC-007, BC-004 |
| Training data preparation (F-101) | Clean, label, and prepare datasets from ticket history | BC-004, BC-010 |
| Training execution (F-102) | Run training on RunPod GPU (only after revenue per LOCKED decision #19) | BC-004, BC-007 |
| Training evaluation (F-103) | Evaluate trained model against test set, compare with production | BC-007, BC-004 |
| Agent versioning (F-104) | Model version management: deploy, rollback, A/B test | BC-007, BC-004 |
| Model comparison (F-105) | Side-by-side model performance comparison | BC-007 |
| Training dataset management (F-106) | Version, tag, search training datasets | BC-004 |
| Model rollback (F-107) | One-click rollback to previous model version | BC-007, BC-004 |
| Drift alert trigger (F-108) | Auto-trigger training when 50-mistake threshold hit (LOCKED decision #20) | BC-004, BC-007 |

**Depends on:** Phase 3 (AI pipeline), Phase 2 (ticket history for training data). Revenue must exist before GPU training (LOCKED #19).

---

### Week 20-21: Polish, Testing, Hardening

**What to build:**

| Module | Purpose | Building Codes |
|--------|---------|----------------|
| Contextual help system (F-045) | In-app help overlay based on current page context | BC-012 |
| Feature discovery teasers (F-043) | Rotating banner surfacing underused features | BC-001 |
| Full test suite | Unit tests, integration tests, BDD scenarios for all 139 features | BC-012 |
| Load testing | Simulate 10,000 concurrent tickets, measure response times, identify bottlenecks | BC-012 |
| Security audit | Review all BC-011 compliance, MFA enforcement, session management, API key security | BC-011 |
| GDPR compliance verification | Right-to-erasure flows, PII redaction verification, consent records audit | BC-010 |
| Error log review + fix | Review ERROR_LOG.md, fix all accumulated issues | BC-012 |
| Documentation | API docs, deployment guide, runbook for ops | — |

---

## PARALLEL TRACKS VISUAL

```
WEEK →  1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18  19  20  21

PHASE 1: FOUNDATION
        [███████████████████████]

PHASE 2: CORE BUSINESS
                               [████████████████████████████████████████████████████]

PHASE 3: AI ENGINE
                                                           [████████████████████████████████████████]

PHASE 4: CHANNELS+JARVIS+DASHBOARD
                                                                                               [████████████████████████████████████████████]

PHASE 5: PUBLIC+TRAINING+POLISH
                                                                                                                                    [████████████████████████████████████]
```

**Note:** Dashed lines above are approximate. Phases overlap — you'll discover backend needs in Phase 3 that send you back to Phase 2 code. That's expected. That's the point.

---

## DEPENDENCY MAP (Who blocks whom)

```
PHASE 1 (Foundation)
    ↓
PHASE 2 (Core Business Logic)
    ├── Ticket System (F-046 to F-052, F-070) ← blocks AI, channels, dashboard
    ├── Billing (F-020 to F-027) ← blocks onboarding, public pages
    ├── Onboarding (F-028 to F-035) ← blocks AI activation
    └── Approval (F-074 to F-086) ← blocks Jarvis, channels
    ↓
PHASE 3 (AI Engine)
    ├── Smart Router + Guardrails (Week 8) ← blocks everything AI
    ├── Classification + RAG + Response (Week 9) ← blocks GSD, channels
    └── GSD + LangGraph + DSPy (Week 10-12) ← blocks Jarvis, training
    ↓
PHASE 4 (Channels + Jarvis + Dashboard)
    ├── Channels (Week 13) ← needs tickets + AI
    ├── Jarvis (Week 14-15) ← needs AI + approval + tickets
    ├── Dashboard + Analytics (Week 16) ← needs ticket data + billing data + AI metrics
    └── Integrations + Mobile (Week 17) ← needs approval + channels
    ↓
PHASE 5 (Public + Training + Polish)
    ├── Public pages (Week 18) ← needs billing + AI
    ├── Training (Week 19) ← needs AI + revenue (LOCKED #19)
    └── Polish (Week 20-21) ← needs everything
```

---

## FEEDBACK LOOPS (Where you'll go backwards)

These are the places where building later phases WILL send you back to improve earlier code:

| Trigger | Where You Go Back | What You'll Add |
|---------|------------------|-----------------|
| Building Smart Router (Week 8) | Phase 1 — Redis | Provider state caching, rate limit tracking per provider |
| Building Channels (Week 13) | Phase 2 — Tickets | Channel-specific ticket fields, media attachment handling, thread linking logic |
| Building Jarvis (Week 14) | Phase 2 — Approval | New API endpoints for NL-triggered approval actions |
| Building Dashboard (Week 16) | Phase 2 — Tickets | Aggregation queries, materialized views for metric performance |
| Building RAG (Week 9) | Phase 2 — Onboarding | Vector search performance tuning, re-indexing triggers |
| Building Training (Week 19) | Phase 3 — AI | Training data export pipeline, model comparison endpoints |
| Building Integrations (Week 17) | Phase 1 — Webhooks | Custom webhook payload schemas, dynamic endpoint registration |

**These are not failures.** They are the natural consequence of building iteratively. Each loop makes the system stronger.

---

## UNRESOLVED DECISIONS (Must resolve before starting)

| Decision | Options | Affects | When Needed |
|----------|---------|---------|-------------|
| **Billing provider** | Paddle (specs) vs Stripe (Tech Assistant) | F-020 to F-027 (8 features) + webhook handling | Before Week 5 |
| **Background jobs** | Celery (specs) vs ARQ (Tech Assistant) | BC-004 + all background task specs | Before Week 3 |
| **Auth method** | Google OAuth only (BC-011) vs email/password (F-010 exists) | F-010, F-011, F-013 | Before Week 2 |
| **Smart Router tiers** | Light/Medium/Heavy (specs) vs Light/Heavy/Ultra (Tech Assistant) | F-054, all AI features | Before Week 8 |

---

## LOCKED DECISIONS (Cannot be changed)

| # | Decision | Rule |
|---|----------|------|
| #19 | No GPU training until revenue | Training pipeline (F-102) can only use RunPod after PARWA earns money |
| #20 | 50 mistakes threshold | AI auto-triggers retraining at exactly 50 mistake reports. HARD-CODED. |
| #22 | Jarvis shows consequences before auto-approve | When enabling auto-approve rules, display ALL potential actions, financial impacts, risks. User must confirm. |
| #23 | Technique routing separate from model routing | BC-013 (techniques) and BC-007 (models) are independent systems. Both must execute per query. |

---

## WHAT'S NOT IN THIS ROADMAP

| Item | Why |
|------|-----|
| File paths and structure | You'll create these during implementation based on what the code actually needs |
| Frontend component tree | Discovered from backend APIs — build after backend is done |
| Specific test files | Write tests for what you actually built, not what you planned |
| Deployment pipeline details | Docker/K8s setup depends on final architecture |
| Database query optimization | Tune queries after real data exists |

---

## TOTAL FEATURE COVERAGE

| Phase | Features Built | Feature IDs |
|-------|---------------|-------------|
| Phase 1: Foundation | 0 (infrastructure only) | — |
| Phase 2: Core Business | 47 features | F-010 to F-052, F-062, F-063, F-066, F-070 to F-084 |
| Phase 3: AI Engine | 24 features | F-053 to F-061, F-064 to F-069, F-071 to F-073, F-140 to F-148 |
| Phase 4: Channels + Jarvis + Dashboard | 31 features | F-036 to F-045, F-085 to F-096, F-109 to F-121, F-120 to F-139 |
| Phase 5: Public + Training + Polish | 24 features | F-001 to F-009, F-097 to F-108 |
| **Total** | **148 features** | **All covered (including 9 AI technique features)** |

Plus 150+ AI sub-features within the AI Core Engine features.

---

**END OF ROADMAP v1.0**

> This roadmap is a living document. Update it as you build and discover. The code is the truth — this document follows the code, not the other way around.
