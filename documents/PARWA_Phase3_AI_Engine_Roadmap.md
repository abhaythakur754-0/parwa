# PARWA Phase 3: AI Engine Roadmap — Complete Build Blueprint

> **Document Classification:** Build Blueprint — AI Build Agents Follow This
> **Version:** 2.1 (Build Roadmap v1 + 38 Situation Gaps Integrated)
> **Last Updated:** 2025-06-30
> **Phase Duration:** Weeks 8–12 (5 weeks + Week 10.5)
> **Total Features/Sub-Tasks:** 30+ features → 200+ sub-tasks
> **Source Documents:** PARWA_Build_Roadmap_v1.md (Phase 3), PARWA_AI_Technique_Framework.md
> **Gap Source:** 36 Situation Gaps (SG-01 through SG-36) identified via comprehensive analysis

---

## HOW TO READ THIS DOCUMENT

- **[EXISTING]** = Item carried forward from Build Roadmap v1 — unchanged
- **[NEW — SG-XX]** = Newly identified gap item being ADDED to the roadmap
- **→** = "must be built first" (sequential dependency)
- **||** = "can be built in parallel" (parallel dependency)
- **🔄** = "you'll come back to this" — discovered need from later in phase

### Building Codes Applied in Phase 3

| Code | Name | Relevance |
|------|------|-----------|
| BC-001 | Multi-Tenant Isolation | Every AI feature scoped to company_id |
| BC-007 | AI Model Interaction (Smart Router) | Core routing, LLM calls, prompt templates |
| BC-008 | State Management (GSD Engine) | State serialization, session persistence |
| BC-013 | AI Technique Routing (3-Tier) | Technique selection, tier enforcement |
| BC-004 | Background Jobs (Celery) | ai_heavy / ai_light queues |
| BC-009 | Approval Workflow | AI actions requiring human review |
| BC-010 | Data Lifecycle & Compliance (GDPR) | PII redaction, data retention |
| BC-011 | Authentication & Security | API keys, prompt injection defense |
| BC-012 | Error Handling & Resilience | Failover, self-healing, timeouts |
| BC-005 | Real-Time Communication (Socket.io) | Live updates, confidence meters |
| BC-006 | Email Communication (Brevo) | AI response delivery |
| BC-002 | Financial Actions | Proration, billing AI |
| BC-014 | Task Decomposition (Build Process) | How to decompose and assign tasks |

---

## PARWA VARIANT MAPPING TABLE

The 3 sellable variants determine which AI capabilities each tenant receives. Every AI feature built in Phase 3 must be variant-aware.

| Dimension | Mini PARWA (The Freshy) | PARWA (The Junior) | PARWA High (The Senior) |
|-----------|------------------------|--------------------|------------------------|
| **Plan Price** | $999/mo | $2,499/mo | $3,999/mo |
| **AI Agents** | 1 | 3 | 5 |
| **AI Resolution Rate** | FAQ handling, ticket intake | 70–80% autonomous | Complex cases + strategic insights |
| **Technique Tiers** | Tier 1 only (CLARA, CRP, GSD) | Tier 1 + Tier 2 | Tier 1 + Tier 2 + Tier 3 (all 14) |
| **Smart Router Access** | Light tier only | Light + Medium | Light + Medium + Heavy |
| **Confidence Auto-Action Threshold** | 95+ (very conservative) | 85+ (moderate) | 75+ (aggressive autonomy) |
| **AI Feature Count** | ~57 (core subset) | ~120 (standard set) | 170+ (full platform) |
| **Techniques Available** | 3 (CLARA, CRP, GSD) | 8 (T1 + T2: CoT, ReAct, ThoT, Reverse Thinking, Step-Back) | 14 (all: T1 + T2 + T3: GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most) |
| **RAG Complexity** | Basic vector search | Reranking + metadata filtering | Full retrieval-rewrite-rerank pipeline |
| **LangGraph Workflows** | Linear chains only | Conditional branching | Full graph with human checkpoints + loops |
| **DSPy Optimization** | Disabled | Enabled for Tier 2 techniques | Enabled for all techniques |
| **AI Self-Healing** | Alert only | Auto-retry + alert | Full self-healing with strategy adjustment |

### Technique → Variant Access Matrix

| Technique | ID | Tier | Mini PARWA | PARWA | PARWA High |
|-----------|-----|------|------------|-------|------------|
| CLARA | — | T1 | ✅ Always | ✅ Always | ✅ Always |
| CRP | F-140 | T1 | ✅ Always | ✅ Always | ✅ Always |
| GSD State Engine | F-053 | T1 | ✅ Always | ✅ Always | ✅ Always |
| Chain of Thought (CoT) | — | T2 | ❌ | ✅ Conditional | ✅ Conditional |
| ReAct | — | T2 | ❌ | ✅ Conditional | ✅ Conditional |
| Thread of Thought (ThoT) | — | T2 | ❌ | ✅ Conditional | ✅ Conditional |
| Reverse Thinking | F-141 | T2 | ❌ | ✅ Conditional | ✅ Conditional |
| Step-Back Prompting | F-142 | T2 | ❌ | ✅ Conditional | ✅ Conditional |
| GST | F-143 | T3 | ❌ | ❌ | ✅ Selective |
| UoT | F-144 | T3 | ❌ | ❌ | ✅ Selective |
| ToT | F-145 | T3 | ❌ | ❌ | ✅ Selective |
| Self-Consistency | F-146 | T3 | ❌ | ❌ | ✅ Selective |
| Reflexion | F-147 | T3 | ❌ | ❌ | ✅ Selective |
| Least-to-Most | F-148 | T3 | ❌ | ❌ | ✅ Selective |

---

## NEW DATABASE TABLES REQUIRED

These tables are needed by the 38 gap items. Create migrations in the first days of Week 8.

| Table | Purpose | Created By | Used By |
|-------|---------|------------|---------|
| `variant_ai_capabilities` | Maps features/techniques to variant tiers WITH instance-level support (tenant_id + variant_type + instance_id) | SG-01 | SG-02, SG-03, SG-05, SG-37, SG-38 |
| `variant_instances` | Tracks every variant instance per tenant — instance_id, variant_type, status, channel_assignment, capacity_config, created_at | SG-37 | SG-06, SG-07, SG-38 |
| `variant_workload_distribution` | Tracks ticket assignments across variant instances — which instance handled which ticket, load metrics, rebalance history | SG-38 | SG-07, SG-10, SG-11 |
| `ai_agent_assignments` | Tracks which agents are assigned to which build tasks and tenant agents | SG-22 | SG-10, SG-07 |
| `technique_caches` | Query-similarity-based caching for technique results | SG-14 | F-141–F-148 |
| `ai_token_budgets` | Per-tenant, per-variant-instance, per-day token limits and tracking | SG-35 | F-054, F-060, SG-38 |
| `prompt_injection_attempts` | Logs all detected injection attempts per tenant | SG-36 | F-057 |
| `ai_performance_variant_metrics` | Per-variant-instance AI performance metrics (latency, accuracy, cost) | SG-19 | F-098, SG-20, SG-38 |
| `pipeline_state_snapshots` | Serialized LangGraph state for recovery and debugging | SG-15 | F-060, F-053 |

---

## WEEK 8: AI Core — Routing + Redaction + Guardrails

**Goal:** Establish the AI pipeline foundation. The Smart Router, PII Redaction, and Guardrails form the safety and routing backbone that every subsequent AI feature depends on. This week also introduces variant-aware AI behavior (the most critical gap area).

**Dependencies:** Phase 1 (Redis, Celery ai_heavy/ai_light queues), Phase 2 (tickets, billing)

---

### Day 1 (Monday) — Database + Variant AI Matrix

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Create Phase 3 database migrations | EXISTING | All 9 new tables for Phase 3 AI features (7 original + `variant_instances` + `variant_workload_distribution`) | BC-001, BC-004 | Agent 1 |
| SG-01: Variant AI Capability Matrix | **NEW — SG-01** | Map all 170+ AI features to variant tiers WITH instance-level support. Populate `variant_ai_capabilities` table with feature_id, variant_id, **instance_id**, is_enabled, config_json. Schema supports unlimited variant instances per tenant (tenant_id + variant_type + instance_id as composite key). This is the single source of truth for what each variant instance can access. | BC-001, BC-007, BC-013 | Agent 2 |
| SG-37: Unlimited Variant Instance Architecture | **NEW — SG-37** | Design and implement the schema/logic to support ANY number of variant instances per tenant (e.g., 5x Mini + 3x PARWA + 2x PARWA High = 10 instances). Create `variant_instances` table: instance_id (UUID), tenant_id, variant_type, status (active/inactive/warming), channel_assignment (which channels this instance handles), capacity_config (max_concurrent_tickets, token_budget_share), created_at. Build service layer: `VariantInstanceService` with methods: register_instance(), deactivate_instance(), list_instances(), get_highest_active_variant(), get_total_capacity(). Each instance gets its own LangGraph workflow executor, Celery queue namespace, and Redis state partition. | BC-001, BC-004, BC-008 | Agent 2 |
| SG-38: Variant Orchestration Layer (Celery-based Workload Distribution) | **NEW — SG-38** | Build the central orchestrator that distributes tickets across variant instances. NOT a CrewAI-style agent collaboration — this is workload routing via Celery + Redis. Components: (1) **Ticket Router** — receives incoming ticket → checks tenant's variant instances → picks instance based on rules, (2) **Capacity Tracker** — real-time load per instance (Redis counters: active_tickets, queued_tickets, token_usage_today), (3) **Distribution Strategy Engine** — pluggable strategies: round-robin, least-loaded, channel-pinned, variant-priority, (4) **Rebalancer** — background Celery task (every 60s) that checks if any instance is overloaded → migrates queued tickets to underloaded instances of same variant type, (5) **Cross-variant Escalation** — if a ticket exceeds an instance's capability (e.g., Mini can't handle it) → escalate to highest available instance of higher variant, (6) **Billing Per-Instance** — track which instance handled which ticket for billing allocation. Create `variant_workload_distribution` table. This layer sits between the ticket intake and the LangGraph workflow — it decides WHICH instance's workflow runs. | BC-004, BC-001, BC-007, BC-008, BC-002 | Agent 5 |
| SG-05: AI Feature Entitlement Enforcement Middleware | **NEW — SG-05** | Build middleware that intercepts every AI API call and checks `variant_ai_capabilities` against the tenant's variant instance. Checks at instance level (not just variant type). Returns 403 with upgrade nudge if feature not in plan. Supports per-instance feature overrides if needed. | BC-001, BC-007, BC-011 | Agent 3 |
| SG-21: Phase 3 Task Decomposition Plan (BC-014) | **NEW — SG-21** | Create the master decomposition document: 30+ Phase 3 features → 200+ sub-tasks with estimates, dependencies, and agent assignments. Store in `documents/`. | BC-014 | Agent 4 |
| SG-22: Agent Assignment Strategy | **NEW — SG-22** | Define which AI build agents own which features. Create `ai_agent_assignments` table. Map: Agent 1 → Infrastructure, Agent 2 → Routing, Agent 3 → Classification/RAG, Agent 4 → Techniques, Agent 5 → Monitoring/Ops. | BC-014 | Agent 5 |

**Dependencies:** None (Day 1 is the starting line)

**Parallel Groups:**
- Group A: Database migrations → Agent 1
- Group B: SG-01 + SG-37 (variant matrix + unlimited instance architecture) → Agent 2 (sequential: SG-01 first → SG-37 depends on it)
- Group C: SG-05 (entitlement middleware) → Agent 3 (after SG-01 complete)
- Group D: SG-21 + SG-22 (decomposition + agent assignment) → Agents 4 + 5
- Group E: SG-38 (variant orchestration layer) → Agent 5 (after migrations complete, can start parallel with Group D)

---

### Day 2 (Tuesday) — Smart Router + Variant Model Access

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-054: Smart Router (3-tier LLM routing) | EXISTING | 3-tier LLM routing (Light/Medium/Heavy) via LiteLLM/OpenRouter. Per-company tier config. Auto-fallback chain. Selects which MODEL to use per query. | BC-007 | Agent 2 |
| SG-03: Variant-Specific Smart Router Model Access | **NEW — SG-03** | Smart Router must check tenant variant before model selection. Mini PARWA → Light only. PARWA → Light + Medium. PARWA High → Light + Medium + Heavy. Store allowed tiers per variant in `variant_ai_capabilities`. | BC-007, BC-001 | Agent 2 |
| F-055: Model Failover | EXISTING | Detect rate limits/timeouts/degraded responses, fall through to backup providers without dropping conversations. | BC-007, BC-004 | Agent 1 |
| SG-30: AI Engine Cold Start | **NEW — SG-30** | Handle first-request latency when no cache/warm models exist. Implement: (1) Warm-up probe on tenant activation, (2) Pre-warm common model+technique combos, (3) Show loading indicator, (4) Fallback to Light model if Heavy not ready within 5s. | BC-012, BC-007 | Agent 5 |
| SG-35: AI Engine Cost Overrun Protection | **NEW — SG-35** | Create `ai_token_budgets` table. Track per-tenant daily/monthly token usage. Hard-stop at budget limit. Alert at 80%. Per-variant limits: Mini=$50/day, PARWA=$200/day, PARWA High=$500/day. | BC-002, BC-007 | Agent 4 |

**Dependencies:** Day 1 (database tables, variant matrix must exist)

**Parallel Groups:**
- Group A: F-054 + SG-03 (Smart Router + variant gating) → Agent 2 (sequential)
- Group B: F-055 (Model Failover) → Agent 1
- Group C: SG-30 (Cold Start) → Agent 5
- Group D: SG-35 (Cost Overrun) → Agent 4

---

### Day 3 (Wednesday) — PII Redaction + Guardrails + Prompt Injection

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-056: PII Redaction Engine | EXISTING | Regex + NER scan for SSN/credit card/email/phone. Token replacement. Redaction map in Redis (24h TTL). | BC-007, BC-010, BC-011 | Agent 1 |
| F-057: Guardrails AI | EXISTING | Multi-layer safety: block harmful/off-topic/hallucinated/policy-violating responses. | BC-007, BC-010, BC-009 | Agent 3 |
| SG-36: Tenant-Specific Prompt Injection Defense | **NEW — SG-36** | Create `prompt_injection_attempts` table. Log every detected attempt with: tenant_id, pattern_type, severity, query_hash, timestamp. Build per-tenant blocklists. Escalate repeated attempts (3+ in 1 hour → alert). | BC-011, BC-007, BC-010 | Agent 3 |
| SG-27: Hallucination Detection Patterns (~12) | **NEW — SG-27** | Build 12 hallucination detection patterns: (1) Contradiction with KB, (2) Fabricated URLs/IDs, (3) Overconfident wrong answers, (4) Plausible-sounding nonsense, (5) Date/math errors, (6) Entity confusion, (7) Policy fabrication, (8) False feature claims, (9) Circular reasoning, (10) Source attribution without source, (11) Numerical precision hallucination, (12) Temporal inconsistency. Each pattern has a detection function + confidence score. | BC-007, BC-012 | Agent 4 |

**Dependencies:** F-056 has no deps. F-057 depends on F-056 (redact before guard). SG-36 depends on F-057. SG-27 feeds into F-057.

**Parallel Groups:**
- Group A: F-056 (PII Redaction) → Agent 1 (must complete first)
- Group B: F-057 + SG-27 (Guardrails + hallucination patterns) → Agent 3 (after F-056 complete, SG-27 can parallel)
- Group C: SG-36 (Prompt Injection Defense) → Agent 3 (after F-057)

---

### Day 4 (Thursday) — Confidence Scoring + Blocked Response Manager + Variant Thresholds

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-059: Confidence Scoring | EXISTING | Calibrated 0-100 score: retrieval (30%) + intent (25%) + sentiment (15%) + history (20%) + context (10%). | BC-007, BC-008 | Agent 2 |
| SG-04: Variant-Specific Confidence Thresholds | **NEW — SG-04** | Different auto-action thresholds per variant. Mini PARWA: 95+ to auto-respond. PARWA: 85+. PARWA High: 75+. Store thresholds in `variant_ai_capabilities`. Confidence score is the same for all variants — only the ACTION threshold changes. | BC-001, BC-007 | Agent 2 |
| F-058: Blocked Response Manager + Review Queue | EXISTING | Review queue for blocked responses, admin can approve/edit/ban patterns. | BC-007, BC-009 | Agent 3 |
| LLM Provider Management | EXISTING | Store provider configs, API keys, rate limits. Admin UI for provider CRUD. | BC-007, BC-011 | Agent 1 |
| Prompt Template Management | EXISTING | CRUD for prompt templates per tenant. Version control. A/B testing hooks. | BC-007, BC-001 | Agent 4 |

**Dependencies:** F-059 depends on F-054 (Smart Router provides model signals). SG-04 depends on F-059. F-058 depends on F-057.

**Parallel Groups:**
- Group A: F-059 + SG-04 (Confidence + variant thresholds) → Agent 2
- Group B: F-058 (Blocked Response Manager) → Agent 3
- Group C: LLM Provider Management → Agent 1
- Group D: Prompt Template Management → Agent 4

---

### Day 5 (Friday) — Week 8 Integration + Testing + Monitoring

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Week 8 Integration Testing | EXISTING | End-to-end test: query → PII redaction → Smart Router → Guardrails → Confidence → Response. All variant gates tested. | BC-012, BC-007 | Agent 1 |
| SG-19: Real-Time AI Performance Monitoring Per Variant | **NEW — SG-19** | Create `ai_performance_variant_metrics` table. Track per variant: avg latency, p95 latency, error rate, token usage, cost per query. Real-time dashboard via Socket.io. | BC-007, BC-005 | Agent 5 |
| SG-20: AI Self-Healing Per Variant Threshold | **NEW — SG-20** | Per-variant self-healing thresholds. Mini PARWA: alert-only (no auto-heal). PARWA: auto-retry once, then alert. PARWA High: full self-healing with strategy adjustment. Integrate with F-055 (Model Failover) and F-093 (Self-Healing). | BC-012, BC-007, BC-001 | Agent 5 |
| Week 8 Error Fix Sprint | EXISTING | Fix all bugs found in integration testing. Update error log. | BC-012 | All agents |

**Dependencies:** All Week 8 tasks

**Parallel Groups:**
- Group A: Integration Testing → Agent 1
- Group B: SG-19 + SG-20 (Monitoring + Self-Healing) → Agent 5
- Group C: Error fixes → All agents

---

### Week 8 Summary

| Category | Count | IDs |
|----------|-------|-----|
| EXISTING items | 8 | F-054, F-055, F-056, F-057, F-058, F-059, LLM Provider Mgmt, Prompt Template Mgmt |
| NEW gap items | 14 | SG-01, SG-03, SG-04, SG-05, SG-19, SG-20, SG-21, SG-22, SG-27, SG-30, SG-35, SG-36, **SG-37, SG-38** |
| **Total Week 8 tasks** | **~22** | — |

**Key Deliverable:** AI pipeline foundation with variant-aware routing, redaction, guardrails, confidence scoring, and monitoring. Every subsequent week builds on this.

---

## WEEK 9: AI Core — Classification + RAG + Response Generation

**Goal:** Build the AI brain — classification, RAG retrieval, and response generation. This week turns PARWA from a routing framework into an intelligent system. The Signal Extraction Layer is the critical glue.

**Dependencies:** Week 8 (Smart Router, PII Redaction, Guardrails, Confidence Scoring), Week 6 (KB must be indexed for RAG)

---

### Day 6 (Monday) — Signal Extraction Layer + Intent Classification

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Signal Extraction Layer (10 signals) | EXISTING | Extract: intent, sentiment, complexity, monetary value, customer tier, conversation turn count, previous response status, reasoning loop detection, resolution path count, query breadth. Feeds both Smart Router and Technique Router. | BC-007, BC-008 | Agent 2 |
| SG-13: Signal Extraction Layer Implementation (detailed) | **NEW — SG-13** | Full implementation of all 10 signals with: (1) Each signal has a dedicated extraction function, (2) Signal weights are configurable per variant, (3) Signal cache with 60s TTL to avoid redundant extraction, (4) Signal quality validation (reject malformed signals), (5) Signal versioning for A/B testing. | BC-007, BC-008 | Agent 2 |
| F-062: Ticket Intent Classification | EXISTING | Multi-label classifier: refund/technical/billing/complaint/feature_request/general. Uses Smart Router Light tier. Outputs: primary intent (1), secondary intents (0-3), confidence per intent. | BC-007, BC-008 | Agent 3 |
| SG-25: Per-Intent Prompt Templates (~40) | **NEW — SG-25** | Create 40 specialized prompt templates — one for each intent × response type combination. Examples: refund_request_response, billing_question_response, technical_troubleshooting_co_pilot, complaint_acknowledge, feature_request_info, etc. Each template has: system prompt, few-shot examples, output schema, tone instructions. | BC-007, BC-001 | Agent 4 |

**Dependencies:** Signal Extraction depends on Week 8 features. F-062 depends on Signal Extraction.

**Parallel Groups:**
- Group A: Signal Extraction + SG-13 (detailed implementation) → Agent 2
- Group B: F-062 (Intent Classification) → Agent 3 (after signals ready)
- Group C: SG-25 (Prompt Templates) → Agent 4 (parallel, templates don't need signals yet)

---

### Day 7 (Tuesday) — Sentiment Analysis + Empathy Engine

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-063: Sentiment Analysis / Empathy Engine | EXISTING | 0-100 frustration score. Triggers escalation at 60+. VIP routing at 80+. Tone adjustment: empathetic at 40+, urgent at 70+, de-escalation at 90+. | BC-007, BC-005 | Agent 3 |
| SG-26: Model-Specific Response Formatters (~15) | **NEW — SG-26** | Create 15 response formatters, one per model variant combination. Different models produce different output formats — formatters normalize to PARWA's internal schema. Formatters handle: token limits, markdown rendering, citation formatting, tone normalization, length limits. | BC-007, BC-012 | Agent 4 |
| F-064: Knowledge Base RAG (part 1 — retrieval) | EXISTING | pgvector search, top-k retrieval, similarity threshold filtering. Tenant-isolated vector search. | BC-007, BC-010 | Agent 1 |
| SG-29: Language Detection/Translation Pipeline (~8) | **NEW — SG-29** | Build 8-step language pipeline: (1) Language detection (fasttext), (2) Confidence scoring for detection, (3) Tenant preferred language lookup, (4) Source→English translation if needed, (5) AI processing in English, (6) Response→Target translation, (7) Translation quality check, (8) Fallback to source language if translation quality low. | BC-007, BC-006 | Agent 5 |

**Dependencies:** F-063 depends on Signal Extraction (Day 6). F-064 depends on F-056 (PII Redaction from Week 8).

**Parallel Groups:**
- Group A: F-063 (Sentiment) → Agent 3
- Group B: SG-26 (Response Formatters) → Agent 4
- Group C: F-064 RAG part 1 → Agent 1
- Group D: SG-29 (Language Pipeline) → Agent 5

---

### Day 8 (Wednesday) — RAG Reranking + Auto-Response Generation

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-064: Knowledge Base RAG (part 2 — reranking + context assembly) | EXISTING | Reranking algorithm (cross-encoder), metadata filtering, context window assembly, citation tracking. | BC-007, BC-010 | Agent 1 |
| F-065: Auto-Response Generation | EXISTING | Combine intent + RAG context + sentiment → brand-aligned response. Uses Smart Router Medium tier. Runs through CLARA quality gate (Tier 1). | BC-007, BC-006 | Agent 3 |
| SG-23: Parallel Build Groups | **NEW — SG-23** | Document which Week 9+ tasks can be built simultaneously. Update task decomposition plan (SG-21). Create parallel group matrix showing dependencies and overlap. | BC-014 | Agent 5 |
| F-050: AI-Powered Ticket Assignment | EXISTING | Score-based matching: specialty (40) + workload (30) + historical accuracy (20) + jitter (10). | BC-001, BC-008 | Agent 2 |

**Dependencies:** F-064 part 2 depends on F-064 part 1. F-065 depends on F-062, F-064, F-057. F-050 depends on F-062, F-063.

**Parallel Groups:**
- Group A: F-064 part 2 (RAG completion) → Agent 1
- Group B: F-065 (Auto-Response) → Agent 3 (after F-064 ready)
- Group C: F-050 (Ticket Assignment) → Agent 2
- Group D: SG-23 (Parallel Groups documentation) → Agent 5

---

### Day 9 (Thursday) — AI Draft Composer + Training Data Isolation

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-066: AI Draft Composer (Co-Pilot Mode) | EXISTING | Suggest drafts to human agents — accept/edit/regenerate. Real-time suggestions via Socket.io. | BC-007, BC-005 | Agent 3 |
| SG-12: Variant-Specific Training Data Isolation | **NEW — SG-12** | Per-variant training datasets. Mini PARWA training data never leaks into PARWA High models and vice versa. Isolation at: (1) Storage level (separate S3 prefixes), (2) Processing level (variant tag in Celery jobs), (3) Vector index level (tenant + variant metadata filter), (4) Model level (variant-specific fine-tuning configs). | BC-001, BC-010, BC-004 | Agent 4 |
| SG-24: 170+ AI Sub-Features Enumeration | **NEW — SG-24** | Complete enumeration and catalog of all 170+ AI sub-features. Map each sub-feature to: parent feature, variant access, building codes, estimated complexity, dependencies. This becomes the definitive reference for AI build agents. | BC-007, BC-014 | Agent 5 |
| SG-28: Edge-Case Handler Registry (~20) | **NEW — SG-28** | Build 20 edge-case handlers: (1) Empty query, (2) Query too long (>4000 chars), (3) Query in unsupported language, (4) Query with only emojis, (5) Query with code blocks, (6) Duplicate query detection, (7) Query with embedded images, (8) Multi-question query, (9) Query referencing non-existent ticket, (10) Query with malicious HTML, (11) Query matching FAQ exactly, (12) Query below confidence floor, (13) Query during system maintenance, (14) Query with expired context, (15) Query from blocked user, (16) Query with pricing request, (17) Query with legal terminology, (18) Query with competitor mention, (19) Query with system commands, (20) Query timeout during processing. | BC-012, BC-007 | Agent 1 |

**Dependencies:** F-066 depends on F-064 (RAG), F-063 (sentiment).

**Parallel Groups:**
- Group A: F-066 (Draft Composer) → Agent 3
- Group B: SG-12 (Training Data Isolation) → Agent 4
- Group C: SG-24 (Sub-Features Enumeration) → Agent 5
- Group D: SG-28 (Edge-Case Handlers) → Agent 1

---

### Day 10 (Friday) — Week 9 Integration + Multi-Variant Routing Prep

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Week 9 Integration Testing | EXISTING | End-to-end: ticket → classification → sentiment → RAG → response generation. Test all variant tiers. | BC-012, BC-007 | Agent 1 |
| SG-06: Multiple Variants Hired Simultaneously — Cross-Variant Routing Rules | **NEW — SG-06** | When a client has multiple PARWA variants active (e.g., Mini for chat + PARWA High for email), define cross-variant routing: (1) Channel→variant mapping, (2) Escalation path from lower to higher variant, (3) Shared context between variants, (4) Billing allocation per variant. | BC-001, BC-007 | Agent 2 |
| SG-11: Cross-Variant Ticket Routing Logic | **NEW — SG-11** | Routing algorithm for mixed variant environments. Priority: (1) Match ticket to variant based on channel, (2) If no channel match, route to highest variant, (3) If ticket exceeds lower variant capability, auto-escalate to higher variant, (4) Bill to originating variant unless escalated. | BC-001, BC-007, BC-002 | Agent 2 |
| Week 9 Error Fix Sprint | EXISTING | Fix all bugs found. Update error log. | BC-012 | All agents |

**Dependencies:** All Week 9 tasks. SG-06 and SG-11 depend on SG-01 (Variant Matrix from Week 8).

**Parallel Groups:**
- Group A: Integration Testing → Agent 1
- Group B: SG-06 + SG-11 (Cross-Variant Routing) → Agent 2 (sequential)
- Group C: Error fixes → All agents

---

### Week 9 Summary

| Category | Count | IDs |
|----------|-------|-----|
| EXISTING items | 7 | F-062, F-063, F-064, F-065, F-066, F-050, Signal Extraction Layer |
| NEW gap items | 10 | SG-06, SG-11, SG-12, SG-13, SG-23, SG-24, SG-25, SG-26, SG-28, SG-29 |
| **Total Week 9 tasks** | **~25** | — |

**Key Deliverable:** Full AI classification + RAG + response generation pipeline. Cross-variant routing defined. All sub-features enumerated.

---

## WEEK 10: AI Core — State Engine + Workflow Orchestration

**Goal:** Build the GSD State Engine and LangGraph workflow orchestration — the backbone for multi-step AI conversations. This is where PARWA transitions from single-turn responses to intelligent multi-turn dialogue.

**Dependencies:** Week 9 (classification, RAG, response generation all feed into GSD state)

---

### Day 11 (Monday) — State Serialization + GSD Engine

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| SG-15: State Serialization/Deserialization Layer | **NEW — SG-15** | Redis primary + PostgreSQL fallback persistence layer. Serialize LangGraph state for: (1) Recovery after crash, (2) Cross-worker handoff, (3) Debug replay, (4) Audit trail. Create `pipeline_state_snapshots` table. State schema includes: current_node, variables, history, technique_stack, model_used, token_count, timestamps. | BC-008, BC-004, BC-001 | Agent 1 |
| F-053: GSD State Engine | EXISTING | Guided Support Dialogue — structured state machine for multi-step conversations. States: NEW → GREETING → DIAGNOSIS → RESOLUTION → FOLLOW-UP → CLOSED. ESCALATE branch to HUMAN HANDOFF. | BC-008, BC-007 | Agent 2 |
| SG-34: AI Engine Data Freshness | **NEW — SG-34** | Ensure AI always operates on fresh data: (1) Cache invalidation on KB updates, (2) RAG re-indexing on document change, (3) Signal staleness detection (>5min old signal → re-extract), (4) Context window freshness check, (5) Model capability version check. | BC-007, BC-004, BC-008 | Agent 5 |

**Dependencies:** SG-15 must be built first (GSD depends on it). SG-34 runs parallel.

**Parallel Groups:**
- Group A: SG-15 (State Serialization) → Agent 1 (must complete first)
- Group B: F-053 (GSD Engine) → Agent 2 (after SG-15)
- Group C: SG-34 (Data Freshness) → Agent 5

---

### Day 12 (Tuesday) — LangGraph Workflow Engine + Variant-Aware Pipelines

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-060: LangGraph Workflow Engine | EXISTING | Graph-based orchestration: complex multi-step AI workflows as directed state machines with conditional branching and human checkpoints. | BC-007, BC-008, BC-004 | Agent 2 |
| SG-18: LangGraph Variant-Aware Pipeline Routing | **NEW — SG-18** | Per-variant workflow graphs. Mini PARWA: linear chain only (intake → classify → respond). PARWA: conditional branching (intake → classify → [simple|complex] → respond/approve). PARWA High: full graph with human checkpoints + loops + technique nodes. Store graph configs per variant. | BC-007, BC-001, BC-013 | Agent 2 |
| F-067: Context Compression Trigger | EXISTING | Monitor token usage, compress prior context when approaching window limits. Trigger compression at 80% of context window. | BC-007, BC-008 | Agent 3 |
| F-068: Context Health Meter | EXISTING | Real-time context quality indicator (healthy/warning/critical). Pushes via Socket.io. | BC-007, BC-008 | Agent 3 |

**Dependencies:** F-060 depends on F-053 (GSD). SG-18 depends on F-060. F-067 and F-068 can build in parallel.

**Parallel Groups:**
- Group A: F-060 + SG-18 (LangGraph + variant pipelines) → Agent 2 (sequential)
- Group B: F-067 (Context Compression) → Agent 3
- Group C: F-068 (Context Health) → Agent 3 (parallel with F-067)

---

### Day 13 (Wednesday) — Capacity Management + DSPy + Production Situations

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-069: 90% Capacity Popup Trigger | EXISTING | Alert when conversation nears AI context limit. Prompt fresh thread. | BC-005, BC-008 | Agent 3 |
| F-061: DSPy Prompt Optimization | EXISTING | Automated prompt engineering against historical resolution metrics. Optimize top-10 prompt templates first. | BC-007, BC-004 | Agent 4 |
| SG-31: AI Engine Under Heavy Load | **NEW — SG-31** | Handle load spikes: (1) Priority queue (VIP tickets first), (2) Adaptive model downgrade (Heavy → Medium → Light under load), (3) Token budget scaling under load, (4) Request queuing with timeout, (5) Load shedding for non-critical AI tasks (DSPy optimization, semantic clustering), (6) Celery queue depth monitoring, (7) Auto-scaling triggers. | BC-012, BC-007, BC-004 | Agent 5 |
| SG-33: AI Engine Timeout Handling | **NEW — SG-33** | Per-pipeline-stage timeouts: (1) Signal extraction: 2s, (2) Classification: 3s, (3) RAG retrieval: 5s, (4) Technique execution: 10s per technique, (5) Response generation: 15s, (6) Total pipeline: 45s hard limit. On timeout: return cached response, queue for async retry, alert ops. | BC-012, BC-007 | Agent 1 |

**Dependencies:** F-069 depends on F-068. F-061 depends on F-065 (needs response history). SG-31 and SG-33 are independent.

**Parallel Groups:**
- Group A: F-069 (Capacity Popup) → Agent 3
- Group B: F-061 (DSPy) → Agent 4
- Group C: SG-31 (Heavy Load) → Agent 5
- Group D: SG-33 (Timeout Handling) → Agent 1

---

### Day 14 (Thursday) — Partial Failure + Multi-Variant Interaction Handlers

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| SG-32: AI Engine Partial Pipeline Failure | **NEW — SG-32** | When one pipeline stage fails but others succeed: (1) Degraded response generation (use available signals only), (2) Fallback response templates per intent, (3) Automatic retry with reduced pipeline, (4) Error context propagation to next stages, (5) Graceful degradation per variant tier, (6) Human handoff trigger when too many stages fail. | BC-012, BC-007, BC-009 | Agent 1 |
| SG-07: Same-Type Variant Overlap — Load-Aware Distribution | **NEW — SG-07** | When multiple instances of same variant handle overlapping workload: (1) Load measurement per instance, (2) Round-robin with weight adjustment, (3) Sticky sessions where possible, (4) Failover between instances, (5) Capacity-aware routing. | BC-001, BC-007 | Agent 2 |
| SG-08: Variant Upgrade Mid-Ticket — Seamless Capability Transition | **NEW — SG-08** | When tenant upgrades while ticket is in-flight: (1) Complete current turn with old variant capabilities, (2) On next turn, activate new variant's features, (3) Do NOT retroactively re-process, (4) Log transition point, (5) Update technique tier access immediately. | BC-002, BC-001, BC-008 | Agent 2 |
| SG-09: Variant Downgrade AI Behavior — Graceful Degradation | **NEW — SG-09** | When tenant downgrades: (1) Immediately restrict to lower variant's technique tier, (2) In-flight tickets complete with old capabilities (current turn only), (3) Disable higher-tier features on next turn, (4) Show deactivation notice in admin panel, (5) Cache cleared for restricted features. | BC-002, BC-001, BC-009 | Agent 3 |

**Dependencies:** SG-07, SG-08, SG-09 all depend on SG-01 (Variant Matrix) and SG-05 (Entitlement Middleware).

**Parallel Groups:**
- Group A: SG-32 (Partial Failure) → Agent 1
- Group B: SG-07 (Load Distribution) + SG-08 (Upgrade Mid-Ticket) → Agent 2
- Group C: SG-09 (Downgrade Behavior) → Agent 3

---

### Day 15 (Friday) — Week 10 Integration + Multi-Agent Collision

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| SG-10: Multi-Agent Collision Detection | **NEW — SG-10** | AI-agent-aware collision prevention: (1) Detect when multiple AI agents attempt to act on same ticket, (2) Distributed lock per ticket (Redis), (3) Agent coordination protocol (first-to-acquire wins), (4) Conflict resolution queue, (5) Merge proposals when agents produce different responses for same ticket. | BC-001, BC-005, BC-008 | Agent 2 |
| Week 10 Integration Testing | EXISTING | End-to-end: multi-turn conversation → GSD state transitions → LangGraph workflow → context management → response. All variant pipelines tested. | BC-012, BC-007 | Agent 1 |
| Week 10 Error Fix Sprint | EXISTING | Fix all bugs. | BC-012 | All agents |

**Dependencies:** SG-10 depends on F-053 (GSD), F-060 (LangGraph), and Week 8 infrastructure.

**Parallel Groups:**
- Group A: SG-10 (Collision Detection) → Agent 2
- Group B: Integration Testing → Agent 1
- Group C: Error fixes → All agents

---

### Week 10 Summary

| Category | Count | IDs |
|----------|-------|-----|
| EXISTING items | 6 | F-053, F-060, F-061, F-067, F-068, F-069 |
| NEW gap items | 10 | SG-07, SG-08, SG-09, SG-10, SG-15, SG-18, SG-31, SG-32, SG-33, SG-34 |
| **Total Week 10 tasks** | **~24** | — |

**Key Deliverable:** Full GSD State Engine + LangGraph orchestration with per-variant workflow graphs. State persistence, context management, and all production situation handlers complete.

---

## WEEK 10.5: AI Technique Framework (F-140 to F-148)

**Goal:** Build the 14 AI reasoning techniques across 3 tiers. The Technique Router (BC-013) is already built (545 lines). This week implements all techniques and wires them into the LangGraph workflow.

**Dependencies:** Week 8 (Smart Router, Confidence Scoring), Week 9 (Sentiment Analysis), Week 10 (GSD Engine, LangGraph)

---

### Day 16 (Monday) — Technique Router Enhancement + Tier 1 Techniques

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| BC-013: Technique Router Engine Enhancement | EXISTING | Already built (545 lines). Enhance: (1) Add variant tier check (SG-02), (2) Add technique caching integration (SG-14), (3) Add performance metrics emission (SG-16), (4) Add per-tenant config API (SG-17). | BC-013, BC-007 | Agent 2 |
| SG-02: Variant-Specific Technique Tier Access | **NEW — SG-02** | Technique Router must check tenant variant before technique selection. Mini PARWA → Tier 1 only. PARWA → Tier 1 + Tier 2. PARWA High → Tier 1 + Tier 2 + Tier 3 (all 14). Enforced in Technique Router's `select_techniques()` method. | BC-001, BC-013, BC-007 | Agent 2 |
| F-140: CRP — Concise Response Protocol | EXISTING | Tier 1 always-active. Minimize token waste, eliminate filler, reduce response length 30-40% while maintaining accuracy. | BC-013, BC-007 | Agent 3 |
| SG-14: Technique Caching System | **NEW — SG-14** | Query-similarity-based cache. Cache technique results when: (1) Same query hash within 1 hour, (2) Semantic similarity > 0.95, (3) Same signal profile. Cache stored in `technique_caches` table with TTL. Per-variant cache isolation. | BC-007, BC-004, BC-001 | Agent 1 |

**Dependencies:** BC-013 exists. SG-02 enhances it. F-140 depends on Technique Router. SG-14 feeds into all technique execution.

**Parallel Groups:**
- Group A: BC-013 enhancement + SG-02 (variant tier access) → Agent 2 (sequential)
- Group B: F-140 (CRP) → Agent 3 (after Technique Router enhanced)
- Group C: SG-14 (Technique Caching) → Agent 1

---

### Day 17 (Tuesday) — Tier 2 Techniques (Part 1)

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-141: Reverse Thinking | EXISTING | Tier 2. Generate wrong answer → invert → find correct one. Auto-triggers when confidence < 0.7. | BC-013, BC-007, BC-008 | Agent 3 |
| F-142: Step-Back Prompting | EXISTING | Tier 2. AI steps back for broader context when query is narrow or AI is stuck. Auto-triggers on low sentiment or reasoning loops. | BC-013, BC-007 | Agent 4 |
| SG-16: Technique Performance Metrics Pipeline | **NEW — SG-16** | Log every technique execution: technique_id, trigger_signal, input_hash, token_cost, latency_ms, output_quality_score, variant_id, tenant_id. Pipeline: (1) Emit on every execution, (2) Aggregate hourly/daily, (3) Feed into F-098 (Agent Performance Metrics), (4) Feed into DSPy optimization (F-061), (5) Surface in admin dashboard. | BC-013, BC-004, BC-001 | Agent 5 |
| SG-17: Per-Tenant Technique Configuration Admin API | **NEW — SG-17** | REST API for admins to enable/disable techniques per tenant. Endpoints: GET /api/techniques/config, PUT /api/techniques/config/{technique_id}. Tier 1 techniques are locked (cannot disable — API returns 400). Stores config in `variant_ai_capabilities`. | BC-013, BC-001, BC-009, BC-011 | Agent 1 |

**Dependencies:** F-141 and F-142 depend on enhanced Technique Router (Day 16). SG-16 and SG-17 are independent.

**Parallel Groups:**
- Group A: F-141 (Reverse Thinking) + F-142 (Step-Back) → Agent 3 + Agent 4
- Group B: SG-16 (Performance Metrics) → Agent 5
- Group C: SG-17 (Admin API) → Agent 1

---

### Day 18 (Wednesday) — Tier 2 Techniques (Part 2) + Tier 3 Techniques (Part 1)

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| CoT: Chain of Thought | EXISTING | Tier 2. Multi-step reasoning. Auto-triggers when complexity > 0.4. | BC-013, BC-007 | Agent 3 |
| ReAct: Reasoning + Acting | EXISTING | Tier 2. Tool-use cycle (Thought → Action → Observation). Auto-triggers when external data needed. | BC-013, BC-007 | Agent 4 |
| ThoT: Thread of Thought | EXISTING | Tier 2. Multi-turn continuity. Auto-triggers when > 5 messages. | BC-013, BC-007 | Agent 4 |
| F-143: GST — Guided Sequential Thinking | EXISTING | Tier 3. Strategic decision reasoning with 5 sequential checkpoints. Auto-triggers on multi-party/policy impact. | BC-013, BC-007, BC-009 | Agent 2 |

**Dependencies:** All Tier 2 techniques depend on Technique Router. GST (Tier 3) depends on Technique Router variant check.

**Parallel Groups:**
- Group A: CoT (Tier 2) → Agent 3
- Group B: ReAct + ThoT (Tier 2) → Agent 4
- Group C: GST (Tier 3) → Agent 2

---

### Day 19 (Thursday) — Tier 3 Techniques (Part 2)

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-144: UoT — Universe of Thoughts | EXISTING | Tier 3. Generate 3-5 diverse solutions, evaluate via matrix. Auto-triggers for VIP or angry customers (sentiment < 0.3). | BC-013, BC-007, BC-009 | Agent 2 |
| F-145: ToT — Tree of Thoughts | EXISTING | Tier 3. Branching decision tree exploration. Auto-triggers when 3+ resolution paths exist. | BC-013, BC-007 | Agent 3 |
| F-146: Self-Consistency | EXISTING | Tier 3. Generate 3-5 answers, return most consistent. Auto-triggers for monetary > $100 or financial queries. | BC-013, BC-007, BC-002 | Agent 4 |
| Technique Performance Tracking | EXISTING | Log every technique execution: technique used, trigger signal, token cost, latency, outcome quality. Feeds into F-098. | BC-013, BC-004 | Agent 5 |

**Dependencies:** All depend on Technique Router + variant tier access (SG-02).

**Parallel Groups:**
- Group A: UoT + ToT (Tier 3) → Agents 2 + 3
- Group B: Self-Consistency (Tier 3) → Agent 4
- Group C: Performance Tracking → Agent 5

---

### Day 20 (Friday) — Week 10.5 Integration + Remaining Tier 3

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-147: Reflexion | EXISTING | Tier 3. Self-correction from rejected/failed responses. Auto-triggers when previous response was rejected. | BC-013, BC-007, BC-008 | Agent 2 |
| F-148: Least-to-Most Decomposition | EXISTING | Tier 3. Break complex queries into sub-queries. Auto-triggers when complexity > 0.7 or 5+ sub-steps. | BC-013, BC-007, BC-004 | Agent 3 |
| Per-Tenant Technique Config | EXISTING | Admin UI to enable/disable techniques per tenant. Tier 1 techniques locked (cannot disable). | BC-013, BC-001, BC-009 | Agent 4 |
| Week 10.5 Integration Testing | EXISTING | Test all 14 techniques with variant gating. Verify: Mini PARWA gets only Tier 1, PARWA gets T1+T2, PARWA High gets all. | BC-012, BC-013 | Agent 1 |
| Week 10.5 Error Fix Sprint | EXISTING | Fix all bugs. | BC-012 | All agents |

**Dependencies:** All Week 10.5 tasks.

**Parallel Groups:**
- Group A: Reflexion + Least-to-Most → Agents 2 + 3
- Group B: Per-Tenant Config → Agent 4
- Group C: Integration Testing → Agent 1
- Group D: Error fixes → All agents

---

### Week 10.5 Summary

| Category | Count | IDs |
|----------|-------|-----|
| EXISTING items | 14 | BC-013, F-140, F-141, F-142, F-143, F-144, F-145, F-146, F-147, F-148, CoT, ReAct, ThoT, Performance Tracking, Per-Tenant Config |
| NEW gap items | 5 | SG-02, SG-14, SG-16, SG-17 |
| **Total Week 10.5 tasks** | **~19** | — |

**Key Deliverable:** All 14 AI techniques implemented with variant tier gating, caching, performance metrics, and admin configuration API.

---

## WEEK 11-12: AI Advanced + Semantic Intelligence + Production Hardening

**Goal:** Build advanced AI features (semantic clustering, voice demo, proration) and production-harden the entire AI pipeline. These two weeks run many tasks in parallel.

**Dependencies:** Week 8-10 (AI pipeline functional), Week 10.5 (all techniques implemented)

---

### Day 21 (Monday, Week 11) — Semantic Intelligence + Advanced Features

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-071: Semantic Clustering | EXISTING | Group similar tickets by embedding similarity for batch operations. | BC-007, BC-004 | Agent 1 |
| F-072: Subscription Change Proration | EXISTING | Calculate prorated charges on plan changes mid-cycle. | BC-002, BC-001 | Agent 3 |
| F-073: Temp Agent Expiry | EXISTING | Auto-deprovision temp agents, reassign tickets. | BC-002, BC-004, BC-011 | Agent 4 |
| F-008: Voice Demo System | EXISTING | $1 paywall for voice AI demo (backend payment + Twilio voice handling). | BC-002 | Agent 5 |
| Full Pipeline Load Testing | NEW | Simulate 1,000 concurrent AI queries across all variants. Measure: p50/p95/p99 latency, error rates, token costs, queue depths. | BC-012, BC-007 | Agent 2 |

**Dependencies:** F-071 depends on F-062 (classification). Voice demo needs Week 8-10 AI pipeline.

**Parallel Groups:**
- All tasks can run in parallel → Agents 1-5

---

### Day 22 (Tuesday, Week 11) — Multi-Variant Scenarios + Production Hardening

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Cross-Variant Integration Testing | NEW | Test scenarios: (1) Mini PARWA + PARWA High active simultaneously, (2) Upgrade mid-ticket, (3) Downgrade mid-ticket, (4) Same variant overlap, (5) Multi-agent collision, (6) Cross-variant ticket routing. | BC-012, BC-001 | Agent 1 |
| Variant-Specific Performance Benchmarking | NEW | Benchmark each variant independently: (1) Mini PARWA: FAQ throughput, (2) PARWA: 70% resolution rate validation, (3) PARWA High: full technique pipeline latency. Record baselines in `ai_performance_variant_metrics`. | BC-007, BC-001 | Agent 2 |
| Prompt Injection Penetration Testing | NEW | Test SG-36 (Prompt Injection Defense) with 50+ attack patterns: (1) Direct injection, (2) Indirect injection via context, (3) Multi-turn injection, (4) Unicode-based injection, (5) Encoding-based injection. Verify all blocked. | BC-011, BC-007 | Agent 3 |
| Hallucination Detection Validation | NEW | Test SG-27 (12 hallucination patterns) with 100 known-hallucination examples. Verify: detection rate > 90%, false positive rate < 5%. | BC-007, BC-012 | Agent 4 |

**Dependencies:** All Week 8-10.5 features must be complete.

**Parallel Groups:**
- All tasks can run in parallel → Agents 1-4

---

### Day 23 (Wednesday, Week 11) — Edge Cases + Error Recovery

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Edge-Case Handler Integration | NEW | Wire all 20 edge-case handlers (SG-28) into the main pipeline. Test each with representative inputs. | BC-012, BC-007 | Agent 1 |
| Production Situation Handler Validation | NEW | Validate all production situation handlers: cold start (SG-30), heavy load (SG-31), partial failure (SG-32), timeout (SG-33), data freshness (SG-34), cost overrun (SG-35), prompt injection (SG-36). | BC-012, BC-007 | Agent 2 |
| Fallback Chain Validation | NEW | Test complete failover chains: (1) Smart Router fallback (Light → backup provider), (2) Technique fallback (Tier 3 → Tier 2 → Tier 1), (3) RAG fallback (vector search → keyword search → template response), (4) State fallback (Redis → PostgreSQL). | BC-012, BC-007 | Agent 3 |
| Recovery Testing | NEW | Test recovery from: (1) Redis crash mid-pipeline, (2) PostgreSQL failover, (3) Celery worker restart, (4) LLM provider outage. Verify no data loss, no stuck tickets. | BC-012, BC-004 | Agent 4 |

**Dependencies:** All Week 8-10.5 features.

**Parallel Groups:**
- All tasks can run in parallel → Agents 1-4

---

### Day 24 (Thursday, Week 11) — DSPy Optimization Run + Technique Tuning

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| DSPy First Optimization Run | EXISTING | Run F-061 (DSPy Prompt Optimization) against top-10 prompt templates. Compare before/after metrics. | BC-007, BC-004 | Agent 4 |
| Technique Trigger Threshold Tuning | NEW | Analyze SG-16 (Technique Performance Metrics) data. Tune trigger thresholds: (1) Adjust complexity thresholds for CoT/Least-to-Most, (2) Adjust confidence thresholds for Reverse Thinking, (3) Adjust sentiment thresholds for UoT, (4) Validate no regressions. | BC-013, BC-007 | Agent 2 |
| Cost Optimization Pass | NEW | Analyze SG-35 (Token Budgets) data. Optimize: (1) CRP effectiveness (target 30% token reduction), (2) Technique caching hit rates, (3) Model tier distribution (are we over-using Heavy?), (4) RAG retrieval efficiency (reduce unnecessary top-k). | BC-002, BC-007 | Agent 3 |
| Token Budget Calibration | NEW | Set initial per-variant token budgets based on Week 11 testing data. Mini PARWA: $50/day, PARWA: $200/day, PARWA High: $500/day. Validate against real usage patterns. | BC-002, BC-007 | Agent 5 |

**Dependencies:** Week 11 testing data (Days 21-23).

**Parallel Groups:**
- Group A: DSPy Optimization → Agent 4
- Group B: Technique Tuning → Agent 2
- Group C: Cost Optimization → Agent 3
- Group D: Token Budget Calibration → Agent 5

---

### Day 25 (Friday, Week 11) — Week 11 Integration + Documentation

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Week 11 Full Integration Test | NEW | End-to-end test of complete AI pipeline: ticket creation → classification → RAG → technique selection → response generation → approval → delivery. Test with all 3 variants. | BC-012, BC-007 | Agent 1 |
| AI Engine Documentation | NEW | Document: (1) Architecture diagram, (2) API reference, (3) Configuration guide, (4) Troubleshooting runbook, (5) Variant behavior matrix, (6) Technique trigger rules, (7) Fallback chains, (8) Monitoring dashboards. | BC-012 | Agent 5 |
| Week 11 Error Fix Sprint | EXISTING | Fix all bugs found during Week 11. | BC-012 | All agents |

**Dependencies:** All Week 11 tasks.

---

### Day 26 (Monday, Week 12) — Final Advanced Features + Voice Integration

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| F-008: Voice Demo System (completion) | EXISTING | Complete voice demo: Twilio STT → AI pipeline → TTS. Ensure variant-gated features work in voice mode. | BC-002, BC-007 | Agent 5 |
| Semantic Clustering v2 (with variant isolation) | NEW | Enhance F-071: clustering must respect variant boundaries. Mini PARWA clusters don't mix with PARWA High clusters. | BC-007, BC-001 | Agent 1 |
| Technique Stacking Validation | NEW | Test all technique stacking scenarios from the AI Technique Framework: (1) VIP + Angry (UoT + Reflexion), (2) Technical + Order Ref (CoT + ReAct), (3) $200 Refund + Pro (Self-Consistency + CoT). Verify execution order and deduplication. | BC-013, BC-007 | Agent 2 |
| Confidence Threshold Validation | NEW | Validate SG-04 thresholds with real data: (1) Mini PARWA at 95 — verify no false positives, (2) PARWA at 85 — verify 70% resolution target, (3) PARWA High at 75 — verify complex case handling. | BC-007, BC-001 | Agent 3 |

**Dependencies:** All previous weeks.

---

### Day 27 (Tuesday, Week 12) — Security Audit + Compliance

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| AI Security Audit | NEW | Audit: (1) PII redaction effectiveness (test with 100 PII patterns), (2) Prompt injection defense (50+ attack vectors), (3) Variant isolation (attempt cross-tenant/cross-variant access), (4) Token budget enforcement (attempt to exceed budgets), (5) API key security for LLM providers. | BC-011, BC-010, BC-007 | Agent 1 |
| GDPR AI Compliance Check | NEW | Verify: (1) PII redaction before LLM calls, (2) Redaction map cleanup at 24h TTL, (3) Right-to-erasure for AI conversation logs, (4) Training data isolation (SG-12), (5) Consent verification before AI processing. | BC-010, BC-007 | Agent 3 |
| Prompt Injection Defense Final Validation | NEW | Run comprehensive penetration test on SG-36. Verify: detection rate > 95%, false positive rate < 2%, all tenant-specific blocklists functional. | BC-011, BC-007 | Agent 4 |
| Financial AI Accuracy Audit | NEW | Verify all financial AI features: (1) Proration calculations (F-072) ±$0.01 accuracy, (2) Self-Consistency for monetary values (F-146), (3) Refund/credit actions within approval system, (4) Token budget billing accuracy. | BC-002, BC-007 | Agent 2 |

**Dependencies:** All AI features complete.

---

### Day 28 (Wednesday, Week 12) — Performance Optimization + Final Tuning

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| End-to-End Latency Optimization | NEW | Target: p95 < 3s for Mini PARWA, < 5s for PARWA, < 8s for PARWA High. Profile each pipeline stage. Optimize bottlenecks. | BC-012, BC-007 | Agent 1 |
| Token Cost Optimization | NEW | Target: 30% reduction via CRP, 20% via technique caching. Validate against baselines from Day 24. | BC-002, BC-007 | Agent 3 |
| DSPy Second Optimization Run | EXISTING | Second pass of DSPy optimization with more training data from Week 11-12 usage. | BC-007, BC-004 | Agent 4 |
| Monitoring Dashboard Finalization | NEW | Finalize SG-19 (Real-Time Monitoring) dashboard: (1) Per-variant metrics, (2) Per-technique performance, (3) Cost tracking, (4) Error rates, (5) Latency percentiles, (6) Token budget utilization. | BC-007, BC-005 | Agent 5 |

---

### Day 29 (Thursday, Week 12) — Final Integration + Stress Testing

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Phase 3 Full Integration Test | NEW | Complete end-to-end test of entire Phase 3 AI pipeline. All features. All variants. All techniques. All production situations. | BC-012, BC-007 | Agent 1 |
| Stress Test (10,000 concurrent) | NEW | Simulate 10,000 concurrent AI queries. Validate: (1) No data corruption, (2) Graceful degradation under overload, (3) Variant isolation maintained, (4) Token budgets enforced, (5) No stuck pipelines. | BC-012, BC-007, BC-004 | Agent 2 |
| Technique Coverage Test | NEW | Verify every technique triggers correctly per its rules. Test each of the 14 trigger rules from the AI Technique Framework with crafted inputs. | BC-013, BC-007 | Agent 3 |
| Cross-Variant Scenario Final Test | NEW | Run all multi-variant scenarios one final time: upgrade/downgrade mid-ticket, multiple variants active, cross-variant routing, agent collision. | BC-001, BC-007 | Agent 4 |

---

### Day 30 (Friday, Week 12) — Phase 3 Completion + Handoff

| Task | Label | Description | Building Codes | Agent |
|------|-------|-------------|----------------|-------|
| Phase 3 Final Bug Fix Sprint | NEW | Fix all remaining bugs from Week 12 testing. | BC-012 | All agents |
| Phase 3 Completion Report | NEW | Document: (1) All features built, (2) All tests passed, (3) Performance baselines, (4) Known limitations, (5) Handoff notes for Phase 4 (Channels + Jarvis + Dashboard). | BC-012 | Agent 5 |
| Phase 3 → Phase 4 Handoff Prep | NEW | Identify all Phase 4 dependencies on Phase 3: (1) API endpoints needed by Channels, (2) AI pipeline hooks for Jarvis, (3) Metrics feeds for Dashboard. Document in handoff guide. | BC-014 | Agent 5 |
| Phase 3 Retrospective | NEW | Review: (1) What worked well, (2) What was harder than expected, (3) What to improve for Phase 4, (4) Update building codes if needed. | BC-014 | All agents |

---

### Week 11-12 Summary

| Category | Count | IDs |
|----------|-------|-----|
| EXISTING items | 4 | F-071, F-072, F-073, F-008, F-061 (DSPy) |
| NEW gap items | 0 (all gap items integrated in Weeks 8-10.5) | — |
| Production hardening tasks | ~20 | Testing, optimization, security, documentation |
| **Total Week 11-12 tasks** | **~25** | — |

---

## PHASE 3 TASK DECOMPOSITION OVERVIEW

### Master Decomposition: 30+ Features → 200+ Sub-Tasks (BC-014)

This section shows how 5 parallel build agents tackle 200+ sub-tasks across 30 working days.

### Agent Assignment Matrix

| Agent | Domain | Primary Features | Week 8 | Week 9 | Week 10 | Week 10.5 | Week 11-12 |
|-------|--------|-----------------|--------|--------|---------|-----------|------------|
| **Agent 1** | Infrastructure + Resilience | DB migrations, F-055 (Failover), F-056 (PII), SG-15 (State), SG-14 (Cache), SG-32 (Partial Failure) | 6 tasks | 4 tasks | 5 tasks | 3 tasks | 8 tasks |
| **Agent 2** | Routing + State + Techniques | F-054 (Smart Router), SG-03, F-059, Signal Extraction, F-053 (GSD), F-060 (LangGraph), F-143 (GST), F-144 (UoT) | 5 tasks | 5 tasks | 6 tasks | 4 tasks | 6 tasks |
| **Agent 3** | Classification + Guardrails + Gen | F-057 (Guardrails), SG-36, F-062, F-063, F-065, F-066, F-141, F-145, F-147 | 4 tasks | 5 tasks | 3 tasks | 4 tasks | 5 tasks |
| **Agent 4** | RAG + Templates + Techniques | SG-25 (Prompts), SG-26 (Formatters), SG-12 (Data Isolation), SG-27 (Hallucination), F-142, F-146, F-148, SG-24 (Sub-Features) | 3 tasks | 5 tasks | 3 tasks | 3 tasks | 5 tasks |
| **Agent 5** | Monitoring + Ops + Cost | SG-19 (Monitoring), SG-20 (Self-Healing), SG-30 (Cold Start), SG-35 (Cost), SG-34 (Freshness), SG-31 (Load), SG-29 (Language), F-008 (Voice) | 4 tasks | 3 tasks | 3 tasks | 2 tasks | 6 tasks |

### Sub-Task Breakdown by Feature

| Feature | Sub-Tasks | Est. Complexity | Parallelizable |
|---------|-----------|----------------|----------------|
| F-054: Smart Router | 12 sub-tasks (provider config, routing logic, fallback, metrics) | High | Partially |
| F-055: Model Failover | 8 sub-tasks (rate limit detection, fallback chain, retry logic) | Medium | Yes |
| F-056: PII Redaction | 10 sub-tasks (regex patterns, NER model, redaction map, edge cases) | Medium | Yes |
| F-057: Guardrails AI | 15 sub-tasks (safety layers, content filters, SG-27 patterns) | High | Partially |
| F-058: Blocked Response Mgr | 6 sub-tasks (queue, approve, edit, ban, analytics) | Low | Yes |
| F-059: Confidence Scoring | 10 sub-tasks (5 score components, calibration, variant thresholds) | Medium | Partially |
| F-060: LangGraph Engine | 18 sub-tasks (graph builder, node executor, conditional branching, state management) | Very High | Partially |
| F-061: DSPy Optimization | 8 sub-tasks (optimizer setup, metric definitions, prompt tuning, A/B) | High | Partially |
| F-062: Intent Classification | 8 sub-tasks (classifier, multi-label, confidence, 12 intents) | Medium | Yes |
| F-063: Sentiment Analysis | 6 sub-tasks (scorer, escalation triggers, tone adjustment) | Medium | Yes |
| F-064: Knowledge Base RAG | 15 sub-tasks (vector search, reranking, context assembly, caching) | High | Partially |
| F-065: Auto-Response Generation | 12 sub-tasks (pipeline, templates, quality gate, delivery) | High | Partially |
| F-066: AI Draft Composer | 6 sub-tasks (suggestion engine, real-time, accept/edit/regenerate) | Medium | Yes |
| F-053: GSD State Engine | 12 sub-tasks (state machine, transitions, context, persistence) | High | Partially |
| F-067: Context Compression | 5 sub-tasks (trigger, compression algo, quality check) | Medium | Yes |
| F-068: Context Health Meter | 4 sub-tasks (health calculation, Socket.io push, alerting) | Low | Yes |
| F-069: 90% Capacity Popup | 4 sub-tasks (threshold, popup UI, fresh thread creation) | Low | Yes |
| BC-013: Technique Router | 10 sub-tasks (signal eval, tier check, stacking, dedup) | High | Partially |
| F-140: CRP | 5 sub-tasks (filler removal, compression, token budget, validation) | Medium | Yes |
| F-141: Reverse Thinking | 6 sub-tasks (inversion, error analysis, validation) | Medium | Yes |
| F-142: Step-Back | 5 sub-tasks (breadth score, step-back generation, refinement) | Medium | Yes |
| F-143: GST | 8 sub-tasks (5 checkpoints, validation, synthesis) | High | Yes |
| F-144: UoT | 8 sub-tasks (solution generation, evaluation matrix, scoring) | High | Yes |
| F-145: ToT | 8 sub-tasks (tree gen, branch eval, pruning, search) | High | Yes |
| F-146: Self-Consistency | 7 sub-tasks (multi-answer, consistency check, vote) | Medium | Yes |
| F-147: Reflexion | 6 sub-tasks (failure detection, self-reflection, adjustment) | Medium | Yes |
| F-148: Least-to-Most | 7 sub-tasks (decomposition, ordering, solving, combination) | Medium | Yes |
| CoT (Chain of Thought) | 5 sub-tasks (decomposition, step reasoning, validation) | Medium | Yes |
| ReAct (Reason + Act) | 6 sub-tasks (thought-action-observation cycle, tool integration) | Medium | Yes |
| ThoT (Thread of Thought) | 5 sub-tasks (thread extraction, continuity check, update) | Medium | Yes |
| F-071: Semantic Clustering | 6 sub-tasks (embedding, clustering, batch ops) | Medium | Yes |
| F-072: Subscription Proration | 4 sub-tasks (proration calc, mid-cycle handling, edge cases) | Low | Yes |
| F-073: Temp Agent Expiry | 4 sub-tasks (expiry check, deprovision, reassignment) | Low | Yes |
| F-008: Voice Demo | 6 sub-tasks (payment, Twilio STT, AI pipeline, TTS, paywall) | Medium | Partially |
| **SG-01** Variant AI Capability Matrix | 5 sub-tasks (matrix definition, table population, validation) | Medium | Yes |
| **SG-02** Technique Tier Access | 3 sub-tasks (variant check, enforcement, logging) | Low | Yes |
| **SG-03** Smart Router Model Access | 3 sub-tasks (variant tier filter, enforcement) | Low | Yes |
| **SG-04** Confidence Thresholds | 3 sub-tasks (threshold config, per-variant, validation) | Low | Yes |
| **SG-05** Entitlement Middleware | 5 sub-tasks (middleware, 403 handler, upgrade nudge) | Medium | Yes |
| **SG-06** Cross-Variant Routing | 4 sub-tasks (channel mapping, escalation, billing) | Medium | Partially |
| **SG-07** Load Distribution | 4 sub-tasks (load measure, round-robin, failover) | Medium | Yes |
| **SG-08** Upgrade Mid-Ticket | 4 sub-tasks (transition logic, feature activation, logging) | Medium | Yes |
| **SG-09** Downgrade Behavior | 4 sub-tasks (restriction, deactivation, notification) | Medium | Yes |
| **SG-10** Collision Detection | 5 sub-tasks (distributed lock, coordination, merge) | High | Yes |
| **SG-11** Cross-Variant Ticket Routing | 4 sub-tasks (routing algorithm, escalation, billing) | Medium | Yes |
| **SG-12** Training Data Isolation | 5 sub-tasks (storage, processing, vector, model isolation) | Medium | Yes |
| **SG-13** Signal Extraction (detailed) | 8 sub-tasks (10 signals, weights, cache, validation, versioning) | High | Partially |
| **SG-14** Technique Caching | 5 sub-tasks (similarity check, cache store, TTL, invalidation) | Medium | Yes |
| **SG-15** State Serialization | 8 sub-tasks (Redis primary, PG fallback, schema, recovery) | High | Partially |
| **SG-16** Technique Metrics Pipeline | 5 sub-tasks (emit, aggregate, feed F-098, dashboard) | Medium | Yes |
| **SG-17** Technique Config Admin API | 4 sub-tasks (CRUD endpoints, lock Tier 1, validation) | Low | Yes |
| **SG-18** LangGraph Variant Pipelines | 6 sub-tasks (3 graph configs, routing, validation) | High | Partially |
| **SG-19** Per-Variant Monitoring | 6 sub-tasks (metrics table, collection, dashboard, alerts) | Medium | Yes |
| **SG-20** Self-Healing Per Variant | 4 sub-tasks (thresholds, auto-retry, strategy adjustment) | Medium | Yes |
| **SG-21** Task Decomposition Plan | 3 sub-tasks (master list, estimates, agent assignment) | Low | Yes |
| **SG-22** Agent Assignment Strategy | 3 sub-tasks (agent mapping, table, coordination rules) | Low | Yes |
| **SG-23** Parallel Build Groups | 2 sub-tasks (dependency matrix, group assignments) | Low | Yes |
| **SG-24** Sub-Features Enumeration | 5 sub-tasks (catalog all 170+, map to parents, validate) | Medium | Yes |
| **SG-25** Per-Intent Prompt Templates | 12 sub-tasks (~40 templates across 12 intent types) | High | Yes |
| **SG-26** Model-Specific Formatters | 8 sub-tasks (~15 formatters for different model outputs) | Medium | Yes |
| **SG-27** Hallucination Patterns | 12 sub-tasks (12 detection pattern implementations) | High | Yes |
| **SG-28** Edge-Case Handlers | 10 sub-tasks (20 handlers, registration, testing) | Medium | Yes |
| **SG-29** Language Pipeline | 8 sub-tasks (detect, translate, quality check, fallback) | High | Yes |
| **SG-30** Cold Start | 5 sub-tasks (warm-up probe, pre-warm, loading indicator, fallback) | Medium | Yes |
| **SG-31** Heavy Load | 7 sub-tasks (priority queue, adaptive downgrade, shedding) | High | Partially |
| **SG-32** Partial Pipeline Failure | 6 sub-tasks (degraded response, retry, fallback, handoff) | High | Yes |
| **SG-33** Timeout Handling | 6 sub-tasks (stage timeouts, total limit, cache fallback) | Medium | Yes |
| **SG-34** Data Freshness | 5 sub-tasks (cache invalidation, re-index, staleness check) | Medium | Yes |
| **SG-35** Cost Overrun Protection | 6 sub-tasks (budget table, tracking, alerts, hard-stop, per-variant) | Medium | Yes |
| **SG-36** Prompt Injection Defense | 6 sub-tasks (detection, logging, blocklist, escalation, table) | High | Yes |

### Total Sub-Task Count

| Category | Features | Sub-Tasks |
|----------|----------|-----------|
| EXISTING Features (F-0XX) | 30 | ~230 |
| NEW Gap Items (SG-XX) | 36 | ~210 |
| Production Hardening (Week 11-12) | — | ~40 |
| **TOTAL** | **66 items** | **~480 sub-tasks** |

---

## DEPENDENCY GRAPH

### Critical Path (Longest Chain — Must Not Be Delayed)

```
SG-01 (Variant Matrix) ──────────────────────────────────────────────────┐
    │                                                                     │
    ├─→ SG-05 (Entitlement Middleware) ──────────────────────────────────→│
    │       │                                                             │
    │       └─→ F-054 (Smart Router) ─→ SG-03 (Variant Model Access)     │
    │               │                     │                               │
    │               └─→ F-059 (Confidence) → SG-04 (Variant Thresholds)  │
    │                       │                                             │
    │                       └─→ Signal Extraction ─→ F-062 (Classification)│
    │                               │                    │                 │
    │                               └─→ F-063 (Sentiment)│                 │
    │                                       │            │                 │
    │                                       └──→ F-065 (Response Gen)     │
    │                                               │                      │
    │                                               └─→ F-053 (GSD)       │
    │                                                       │              │
    │                                                       └─→ F-060 (LangGraph)│
    │                                                               │      │
    │                               ┌───────────────────────────────┘      │
    │                               │                                      │
    │                           BC-013 (Technique Router) ─→ SG-02        │
    │                               │                                      │
    │                               ├─→ F-140 (CRP, Tier 1)              │
    │                               ├─→ F-141, F-142 (Tier 2)            │
    │                               └─→ F-143-F-148 (Tier 3)             │
    │                                                                      │
    └──────────────────── ALL WEEK 11-12 TESTING/HARDENING ◄──────────────┘
```

### Week-Level Dependency Map

```
WEEK 8 (Foundation)
  ├── SG-01 (Variant Matrix) ──────────────────────→ ALL subsequent weeks
  ├── F-054 (Smart Router) ───────────────────────→ WEEK 9, 10, 10.5
  ├── F-055 (Model Failover) ─────────────────────→ WEEK 11-12 (resilience)
  ├── F-056 (PII Redaction) ──────────────────────→ WEEK 9 (RAG)
  ├── F-057 (Guardrails) ─────────────────────────→ WEEK 9 (response gen)
  ├── F-058 (Blocked Response Mgr) ───────────────→ WEEK 11-12 (testing)
  ├── F-059 (Confidence) ─────────────────────────→ WEEK 9, 10, 10.5
  └── SG-35 (Cost Overrun) ───────────────────────→ WEEK 11-12 (budgets)

WEEK 9 (Classification + RAG + Response)
  ├── Signal Extraction ──────────────────────────→ WEEK 10, 10.5
  ├── F-062 (Intent Classification) ──────────────→ WEEK 10, 11-12
  ├── F-063 (Sentiment) ──────────────────────────→ WEEK 10, 10.5
  ├── F-064 (RAG) ────────────────────────────────→ WEEK 10 (response gen)
  ├── F-065 (Auto-Response) ──────────────────────→ WEEK 10 (GSD)
  └── SG-06, SG-11 (Cross-Variant) ─────────────→ WEEK 11-12 (testing)

WEEK 10 (State + Workflow)
  ├── SG-15 (State Serialization) ────────────────→ F-053, F-060
  ├── F-053 (GSD Engine) ─────────────────────────→ WEEK 10.5, 11-12
  ├── F-060 (LangGraph) ──────────────────────────→ WEEK 10.5, 11-12
  ├── SG-18 (Variant Pipelines) ──────────────────→ WEEK 10.5, 11-12
  └── F-061 (DSPy) ───────────────────────────────→ WEEK 11-12 (optimization)

WEEK 10.5 (Technique Framework)
  ├── BC-013 Enhancement + SG-02 ─────────────────→ ALL techniques
  ├── Tier 1: F-140 (CRP) ───────────────────────→ Immediate use
  ├── Tier 2: F-141, F-142, CoT, ReAct, ThoT ────→ WEEK 11-12
  ├── Tier 3: F-143-F-148 ────────────────────────→ WEEK 11-12
  └── SG-16 (Metrics Pipeline) ───────────────────→ WEEK 11-12 (tuning)

WEEK 11-12 (Advanced + Hardening)
  ├── F-071, F-072, F-073, F-008 ─────────────────→ Phase 4 dependencies
  └── ALL TESTING/HARDENING ──────────────────────→ Phase 4 readiness
```

### Feature-Level Dependency Map (What Blocks What)

```
SG-01 ──→ SG-02, SG-03, SG-04, SG-05, SG-06, SG-08, SG-09, SG-11, SG-18
SG-05 ──→ F-054, F-060, F-065, ALL technique features
F-054 ──→ SG-03, F-055, F-059, F-060, F-062, F-065
F-056 ──→ F-064, F-065
F-057 ──→ F-058, SG-27, SG-36, F-065
F-059 ──→ SG-04, F-060, F-065, ALL techniques
Signal Extraction ──→ F-062, F-063, F-060, ALL techniques
F-062 ──→ F-050, F-065, F-071, ALL techniques
F-063 ──→ F-065, F-066, ALL techniques
F-064 ──→ F-065, F-066, F-061, ReAct technique
F-065 ──→ F-066, F-053
SG-15 ──→ F-053, F-060
F-053 ──→ F-060, F-067, F-068, F-069, ALL techniques
F-060 ──→ SG-18, ALL techniques, F-061
BC-013 ──→ SG-02, F-140-F-148, CoT, ReAct, ThoT
SG-16 ──→ F-098, F-061, F-116
```

---

## PHASE 3 PARALLEL TRACKS VISUAL

```
DAY →  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30

AGENT 1 (Infra+Resilience)
       [DB][Fail][PII][Prov][Int] [RAG1][    ][RAG2][Edge][Int][State][    ][Time][Part][Int][Cache][Tst][    ][    ][    ][Int][Stress][Tech][    ][Bug]
                                                                                                                  [Fix]

AGENT 2 (Routing+State+Tech)
       [    ][SR+VM][    ][Conf][Int] [Sig][Tkt][    ][    ][XVR][GSD][LG+VP][    ][    ][Col][Int][TR+VT][GST][UoT][    ][    ][    ][    ][Ref][Tune][Bench][Tech2][Bug]

AGENT 3 (Class+Guard+Gen)
       [    ][    ][GRD+PI][BRM][    ] [INT][SENT][    ][RESP][    ][CC][    ][CC][    ][    ][    ][RT][SB][    ][    ][Pen][    ][    ][    ][    ][    ][Audit][Bug]

AGENT 4 (RAG+Templates+Tech)
       [    ][    ][    ][PTM][    ] [T40][MSF][    ][    ][TDI][SEF][    ][DSP][    ][    ][    ][    ][SC][LT][    ][DSP2][    ][    ][    ][    ][    ][    ][Bug]

AGENT 5 (Monitor+Ops+Cost)
       [AAS][CS][    ][    ][MON+SH] [    ][LP][    ][PBG][    ][DF][    ][HL][    ][    ][    ][MET][    ][    ][TKC][MON][    ][    ][    ][    ][DOC][FIN][RET]

KEY:
SR    = Smart Router        VM  = Variant Model Access    CS  = Cold Start
GRD   = Guardrails          PI  = Prompt Injection        SH  = Self-Healing
BRM   = Blocked Response     Conf= Confidence Scoring      MON = Monitoring
SIG   = Signal Extraction    INT = Intent Classification   PBG = Parallel Groups
RAG   = RAG Pipeline         Tkt = Ticket Assignment       TDI = Training Data Isolation
SENT  = Sentiment            RES = Auto-Response           SEF = Sub-Features Enum
RESP  = Response Gen          DR = Draft Composer          EDG = Edge-Case Handlers
GSD   = GSD Engine           XVR = Cross-Variant Routing   LP  = Language Pipeline
LG    = LangGraph            CC  = Context Compression     DF  = Data Freshness
VP    = Variant Pipelines    HL  = Heavy Load              Time= Timeouts
TR    = Technique Router     VT  = Variant Tier Access     Part= Partial Failure
CACHE = Technique Cache      MET = Metrics Pipeline        Col = Collision Det
RT    = Reverse Thinking     SB  = Step-Back               GST = GST (Tier 3)
UoT   = UoT (Tier 3)         SC  = Self-Consistency        LT  = Least-to-Most
Ref   = Reflexion            DSP = DSPy Optimization       TKC = Token Budget Cal
Int   = Integration Testing  Bug = Bug Fix Sprint         Tst = Testing
Stress= Stress Test          Pen = Pen Testing             Audit= Security Audit
Bench = Benchmarking         Doc = Documentation           FIN = Final Completion
RET   = Retrospective        Tun = Technique Tuning       MON = Monitoring Dashboard
```

---

## COMPLETE PHASE 3 SUMMARY TABLE

### By Week

| Week | Focus | EXISTING Features | NEW Gap Items | Production Tasks | Total Tasks | Key Deliverable |
|------|-------|-------------------|---------------|------------------|-------------|-----------------|
| **8** | Routing + Redaction + Guardrails | 8 (F-054–F-059, LLM Mgmt, Prompt Mgmt) | 12 (SG-01, SG-03, SG-04, SG-05, SG-19, SG-20, SG-21, SG-22, SG-27, SG-30, SG-35, SG-36) | 1 (Integration) | ~21 | AI pipeline foundation with variant awareness |
| **9** | Classification + RAG + Response | 7 (F-062, F-063, F-064, F-065, F-066, F-050, Signals) | 10 (SG-06, SG-11, SG-12, SG-13, SG-23, SG-24, SG-25, SG-26, SG-28, SG-29) | 1 (Integration) | ~26 | Full AI brain: classification → RAG → response |
| **10** | State Engine + Workflow | 6 (F-053, F-060, F-061, F-067, F-068, F-069) | 10 (SG-07, SG-08, SG-09, SG-10, SG-15, SG-18, SG-31, SG-32, SG-33, SG-34) | 1 (Integration) | ~24 | Multi-turn state management + LangGraph |
| **10.5** | Technique Framework | 14 (BC-013, F-140–F-148, CoT, ReAct, ThoT, Perf, Config) | 5 (SG-02, SG-14, SG-16, SG-17) | 1 (Integration) | ~19 | All 14 techniques with variant gating |
| **11-12** | Advanced + Hardening | 5 (F-071, F-072, F-073, F-008, F-061) | 0 | ~20 (testing, optimization, security, docs) | ~25 | Production-ready AI engine |
| **TOTAL** | **5 weeks** | **40** | **37** | **~24** | **~115** | **Complete AI Engine** |

### By Gap Category

| Category | Gap Items | Status | Weeks |
|----------|-----------|--------|-------|
| **A: Variant-Specific AI Behavior** | SG-01, SG-02, SG-03, SG-04, SG-05 | All integrated | 8, 10.5 |
| **B: Multi-Variant Interaction** | SG-06, SG-07, SG-08, SG-09, SG-10, SG-11, SG-12 | All integrated | 9, 10 |
| **C: AI Engine Infrastructure** | SG-13, SG-14, SG-15, SG-16, SG-17, SG-18, SG-19, SG-20 | All integrated | 8, 9, 10, 10.5 |
| **D: Task Decomposition Strategy** | SG-21, SG-22, SG-23 | All integrated | 8, 9 |
| **E: AI Sub-Feature Mapping** | SG-24, SG-25, SG-26, SG-27, SG-28, SG-29 | All integrated | 8, 9 |
| **F: AI Engine Production Situations** | SG-30, SG-31, SG-32, SG-33, SG-34, SG-35, SG-36 | All integrated | 8, 10 |
| **TOTAL** | **36** | **All integrated** | **8–10.5** |

### By Building Code Usage

| Building Code | Times Applied | Primary Week |
|---------------|--------------|--------------|
| BC-007 (AI Model Interaction) | ~85 features | All weeks |
| BC-001 (Multi-Tenant Isolation) | ~45 features | All weeks |
| BC-012 (Error Handling & Resilience) | ~40 features | All weeks |
| BC-008 (State Management) | ~30 features | 9, 10, 10.5 |
| BC-013 (AI Technique Routing) | ~25 features | 10, 10.5 |
| BC-004 (Background Jobs) | ~25 features | 8, 9, 10 |
| BC-009 (Approval Workflow) | ~15 features | 8, 9, 10.5 |
| BC-010 (Data Lifecycle & Compliance) | ~15 features | 8, 9 |
| BC-011 (Auth & Security) | ~15 features | 8, 9, 10 |
| BC-005 (Real-Time Communication) | ~15 features | 8, 9, 10 |
| BC-002 (Financial Actions) | ~12 features | 8, 10, 11-12 |
| BC-006 (Email Communication) | ~8 features | 9, 11-12 |
| BC-014 (Task Decomposition) | ~5 features | 8, 9 |

---

## LOCKED DECISIONS AFFECTING PHASE 3

| # | Decision | Impact on Phase 3 |
|---|----------|-------------------|
| #19 | No GPU training until revenue | F-061 (DSPy) uses prompt optimization only — no fine-tuning until revenue exists |
| #20 | 50 mistakes threshold | AI auto-triggers retraining at exactly 50 mistake reports. F-061 must support this trigger |
| #22 | Jarvis shows consequences before auto-approve | F-077/F-078 integration with AI engine — consequences must include technique cost impact |
| #23 | Technique routing separate from model routing | BC-013 and BC-007 are independent. Both execute per query. Enforced in architecture |

---

## WHAT PHASE 4 NEEDS FROM PHASE 3

When Phase 4 (Channels + Jarvis + Dashboard) begins, it will need these Phase 3 outputs ready:

| Phase 4 Feature | Phase 3 Dependency | API Endpoint Needed |
|-----------------|-------------------|---------------------|
| Email Channel (F-121) | Auto-Response (F-065) | `POST /api/ai/generate-response` |
| Chat Widget (F-125) | Full AI pipeline | `POST /api/ai/chat` |
| SMS Channel (F-126) | Auto-Response (F-065) | `POST /api/ai/generate-response` |
| Voice Call (F-127) | Full AI pipeline | `POST /api/ai/chat` (with voice flag) |
| Jarvis NL (F-087) | Signal Extraction + Smart Router | `POST /api/ai/parse-command` |
| System Status (F-088) | SG-19 (Monitoring) | `GET /api/ai/status` |
| GSD Terminal (F-089) | F-053 (GSD) | `GET /api/ai/gsd-state/{ticket_id}` |
| Dashboard Metrics (F-038) | SG-16 (Metrics Pipeline) | `GET /api/ai/metrics` |
| Agent Dashboard (F-097) | SG-19 (Per-Agent Metrics) | `GET /api/ai/agents/metrics` |
| Training Pipeline (F-102) | SG-12 (Data Isolation) | `GET /api/ai/training-data` |

---

## FEEDBACK LOOPS (Where You'll Go Back in Phase 3)

| Trigger | Where You Go Back | What You'll Add |
|---------|------------------|-----------------|
| Building LangGraph variant pipelines (SG-18) | Week 8 — Smart Router | Per-variant model selection configs |
| Building technique caching (SG-14) | Week 9 — RAG | RAG result caching layer |
| Testing technique stacking | Week 10 — LangGraph | Additional conditional nodes for technique chaining |
| Load testing (Week 11) | Week 8 — Cost Overrun (SG-35) | Budget tuning based on real load data |
| Security audit (Week 12) | Week 8 — Guardrails (F-057) | Additional safety patterns from penetration findings |
| DSPy optimization (Week 11) | Week 9 — Prompt Templates (SG-25) | Optimized prompt versions |

---

**END OF PHASE 3 AI ENGINE ROADMAP v2.0**

> This roadmap is a living document. Update it as you build and discover. The code is the truth — this document follows the code, not the other way way around.
>
> **Total Phase 3 Scope:** 40 existing features + 37 gap items + ~24 production hardening tasks = ~115 major tasks decomposed into ~480 sub-tasks across 30 working days with 5 parallel build agents.
