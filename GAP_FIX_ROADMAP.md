# PARWA Gap Fix Roadmap — Pre-Phase 4 Critical Fixes

> **Purpose:** Fix ALL gaps discovered from Technology Verification Report + Infrastructure Gaps Tracker + Day27 Security Audit BEFORE starting Phase 4 (Channels + Jarvis + Dashboard) and Phase 5 (Public + Training + Polish).
>
> **Trigger:** Technology Verification Report identified 6 critical findings + 8 uncovered gaps that are NOT in any Week 9-21 plan.
>
> **Rule:** Fix these NOW. Do NOT proceed to Phase 4-5 until these are resolved.

---

## Master Gap Consolidation — 16 Items

### From Technology Verification Report (Critical Findings)

| # | Gap | Severity | Root Cause |
|---|-----|----------|------------|
| C1 | RAG Pipeline uses MockVectorStore (random scores, not pgvector) | CRITICAL | `shared/knowledge_base/vector_search.py` uses `MockVectorStore` |
| C2 | LangGraph NOT actually used (custom dataclass state machine) | CRITICAL | `langgraph_workflow.py` imports in try/except, never calls |
| C3 | LiteLLM NOT used at all (raw httpx to providers) | CRITICAL | `smart_router.py` uses httpx directly, LiteLLM only in test file |
| C4 | DSPy running in stub mode (import fails gracefully) | CRITICAL | `dspy_integration.py` has `_DSPY_AVAILABLE = False` |
| C5 | brevo-python v1.1.2 severely deprecated (v4 available) | HIGH | Package outdated since Jul 2024 |
| C6 | Paddle SDK not in requirements.txt (custom HTTP) | HIGH | Revenue depends on fragile custom implementation |

### From Infrastructure Gaps Analysis (Uncovered)

| # | Gap | Severity | Root Cause |
|---|-----|----------|------------|
| G1 | Paddle webhook ordering + missed detection | HIGH | BG-01, BG-15 unchecked in INFRA GAPS TRACKER |
| G2 | KB document quality validation missing | MEDIUM | No chunking quality, relevance feedback, or dedup logic |
| G3 | Response quality benchmarking suite missing | MEDIUM | No metrics to prove AI quality to clients |
| G4 | Framework documentation mismatch | HIGH | Docs claim LangGraph/DSPy/LiteLLM — code doesn't use them |

### From Partially Covered + Additional Items

| # | Gap | Severity | Root Cause |
|---|-----|----------|------------|
| P1 | Twilio SDK not in requirements.txt | MEDIUM | Voice/SMS features use manual HTTP calls |
| P2 | Technique nodes quality audit | MEDIUM | 12 nodes vary in depth, some may be stubs |
| P3 | Dependency versions outdated | LOW | LangGraph >=0.2.0 (latest 1.1.7), DSPy >=2.5.0 (latest 3.1.3), Celery, Socket.io |
| P4 | Emergency runbooks not documented | MEDIUM | No documented procedures for DB failover, Redis down, LLM outage |
| P5 | Paddle webhook sequence ordering | HIGH | Out-of-order events could leave paying clients without access |
| P6 | GDPR compliance procedures | MEDIUM | Auto-delete, right-to-erasure, consent withdrawal flows |

---

## Execution Plan — 3 Phases (12 Days)

### Phase P0: CRITICAL Fixes (Days 1-5)

These MUST be fixed before ANY client demo or Phase 4 work.

---

#### Day 1 — MockVectorStore → Real pgvector (C1)

**Goal:** Replace MockVectorStore with actual pgvector cosine similarity queries so RAG actually works.

**Files to Modify:**
- `shared/knowledge_base/vector_search.py` — Replace `MockVectorStore` with `PgVectorStore`
- `shared/knowledge_base/__init__.py` — Update exports

**Files to Create:**
- `shared/knowledge_base/pgvector_queries.py` — Raw SQL queries for vector operations

**Tasks:**
- [ ] Create `PgVectorStore` class implementing `VectorStore` ABC
- [ ] Implement `add_documents(doc_id, chunks, embeddings, metadata)` using pgvector `INSERT`
- [ ] Implement `search(query_embedding, top_k, similarity_threshold, filters)` using pgvector `<=>` cosine distance
- [ ] Implement `delete_by_document(doc_id)` for document removal
- [ ] Implement `update_document(doc_id, chunks, embeddings)` for re-indexing
- [ ] Add HNSW index creation for `document_chunks.embedding` column
- [ ] Add metadata filtering (tenant isolation via company_id)
- [ ] Verify `pgvector` extension is enabled in PostgreSQL (SQL: `CREATE EXTENSION IF NOT EXISTS vector`)
- [ ] Update `embedding_service.py` to store embeddings in pgvector (not mock)
- [ ] Wire `rag_retrieval.py` to use `PgVectorStore` instead of `MockVectorStore`
- [ ] Remove `MockVectorStore` class entirely
- [ ] Add integration test: upload document → generate embeddings → search → verify relevant results

**Verification:**
- [ ] Upload a test PDF → chunk → embed → search returns relevant chunks (not random)
- [ ] Cosine similarity scores are deterministic (same query = same results)
- [ ] Tenant isolation: Company A docs don't appear in Company B search

**SQL for pgvector:**
```sql
-- Ensure extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
ON document_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Verify existing data
SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL;
```

---

#### Day 2 — LangGraph Real Integration (C2)

**Goal:** Replace custom dataclass state machine with real LangGraph `StateGraph` workflows.

**Files to Modify:**
- `backend/app/core/langgraph_workflow.py` — Full rewrite to use LangGraph
- `backend/app/core/gsd_engine.py` — Migrate state machine to LangGraph nodes
- `backend/app/core/technique_executor.py` — Wire techniques as LangGraph nodes

**Tasks:**
- [ ] Install/update LangGraph: `pip install langgraph>=1.0.0`
- [ ] Define `ConversationState` TypedDict with all state fields (GSD state, signals, messages, technique_stack)
- [ ] Build LangGraph `StateGraph` with nodes:
  - `intake_node` — Signal extraction + intent classification
  - `classify_node` — Multi-label classification
  - `rag_node` — RAG retrieval + reranking
  - `technique_node` — Technique Router + execution
  - `response_node` — Response generation + CLARA quality gate
  - `escalation_node` — Human handoff trigger
- [ ] Add conditional edges:
  - `intake → classify → rag → technique → response`
  - `response → CLARA pass → output`
  - `response → CLARA fail → technique → response` (regenerate)
  - `any → confidence < threshold → escalation`
- [ ] Per-variant workflow graphs:
  - Mini PARWA: Linear chain only (intake → classify → respond)
  - PARWA: Conditional branching (intake → classify → [simple|complex] → respond/approve)
  - PARWA High: Full graph with human checkpoints + loops + technique nodes
- [ ] Add checkpoint persistence (Redis + PostgreSQL fallback)
- [ ] Add cycle detection (max 10 edges to prevent infinite loops)
- [ ] Remove old custom `WorkflowState` dataclass
- [ ] Wire into `ai_pipeline.py` as the primary workflow engine
- [ ] Tests: Linear flow, conditional branching, cycle detection, checkpoint recovery

**Verification:**
- [ ] LangGraph `StateGraph` compiles without errors
- [ ] Simple query flows through linear chain
- [ ] Complex query triggers conditional branching
- [ ] Checkpoint saves state to Redis, recovers on restart

---

#### Day 3 — LiteLLM Integration (C3) + DSPy Enable (C4)

**Goal A:** Replace raw httpx LLM calls with LiteLLM unified API.
**Goal B:** Install DSPy v3 and enable prompt optimization.

**LiteLLM Tasks (C3):**
- [ ] Install LiteLLM: `pip install litellm>=1.82.0`
- [ ] Rewrite `backend/app/core/smart_router.py` to use `litellm.completion()` instead of `httpx`
- [ ] Configure model mapping in Smart Router:
  ```python
  MODEL_MAP = {
      "google": "gemini/gemini-2.0-flash",
      "cerebras": "cerebras/llama3.1-8b",
      "groq": "groq/llama3-70b-8192",
  }
  ```
- [ ] Enable LiteLLM's built-in: retry logic, fallback chains, cost tracking, rate limit handling
- [ ] Add LiteLLM callbacks for token usage logging
- [ ] Update `model_failover.py` to use LiteLLM's native failover
- [ ] Remove raw httpx LLM calls from all files
- [ ] Tests: Verify all 3 providers work via LiteLLM, failover triggers correctly

**DSPy Tasks (C4):**
- [ ] Install DSPy v3: `pip install dspy-ai>=3.0.0`
- [ ] Update `backend/app/core/dspy_integration.py`:
  - Remove `try/except ImportError` wrapper
  - Set `_DSPY_AVAILABLE = True`
  - Implement real DSPy `teleprompt` optimization
  - Configure DSPy with LiteLLM as the LM backend: `dspy.LM(model="litellm/gemini-2.0-flash")`
- [ ] Build DSPy modules for:
  - `PARWAClassify` — Signature-based classification module
  - `PARWAResponse` — Signature-based response generation module
  - `PARWARAGRetrieve` — RAG retrieval + generation module
- [ ] Implement prompt optimization loop:
  - Bootstrap few-shot examples from ticket history
  - Run `BootstrapFewShot` or `MIPROv2` optimizer
  - Store optimized prompts in `prompt_template_service.py`
  - A/B test optimized vs default prompts
- [ ] Wire into Week 10 F-061 (DSPy prompt optimization)
- [ ] Tests: DSPy compiles modules, optimization runs on sample data, results improve

**Verification:**
- [ ] LiteLLM: All 3 LLM providers respond via `litellm.completion()`
- [ ] LiteLLM: Failover works (kill Google → falls to Cerebras → Groq)
- [ ] DSPy: `_DSPY_AVAILABLE` is `True`
- [ ] DSPy: Prompt optimization runs and produces improved prompts

---

#### Day 4 — Brevo SDK v4 Migration (C5) + Paddle SDK (C6)

**Goal A:** Migrate brevo-python from v1.1.2 to v4.0.5.
**Goal B:** Replace custom Paddle HTTP with official paddle-python-sdk.

**Brevo Tasks (C5):**
- [ ] Install: `pip install brevo-python>=4.0.0`
- [ ] Update `backend/app/services/email_service.py`:
  - Replace `brevo-python` v1 API calls with v4 API
  - v4 uses `TransactionnalEmailsApi` with `SendSmtpEmail` model
  - Migrate all email sends: OTP, verification, welcome, MFA, approval, overage, etc.
- [ ] Update `backend/app/webhooks/brevo_handler.py`:
  - v4 webhook parsing may differ
  - Test inbound email parsing
- [ ] Update all email templates (6 templates in `backend/app/templates/emails/`)
- [ ] Verify v4 async support (if using async FastAPI)
- [ ] Tests: Send test email via v4 API, verify delivery, check webhook parsing

**Paddle Tasks (C6):**
- [ ] Install: `pip install paddle-python-sdk>=2.0.0`
- [ ] Update `backend/app/services/paddle_service.py`:
  - Replace custom `httpx` calls with Paddle SDK client
  - Use `paddle.Client(api_key=...)` for all API calls
  - Migrate: subscription create/update/cancel, payment methods, invoices, credits
- [ ] Update `backend/app/webhooks/paddle_handler.py`:
  - Use SDK's webhook signature verification
  - SDK handles HMAC verification natively
- [ ] Update `backend/app/services/subscription_service.py`:
  - Use SDK for subscription management
  - Proration via SDK if available
- [ ] Handle all 25+ Paddle webhook events via SDK event parser
- [ ] Add Paddle SDK to `requirements.txt`
- [ ] Tests: Create subscription via SDK, process webhook, verify invoice retrieval

**Verification:**
- [ ] Brevo: Test email sent and received successfully
- [ ] Brevo: OTP flow works end-to-end
- [ ] Paddle: Subscription creation works via SDK
- [ ] Paddle: Webhook signature verification uses SDK
- [ ] Paddle: Invoice retrieval works

---

#### Day 5 — Integration Testing + Framework Docs Update (C2/C3/C4 + G4)

**Goal:** Verify all P0 fixes work together + update documentation to reflect reality.

**Integration Tests:**
- [ ] E2E: Upload doc → embed → pgvector search → LiteLLM classify → DSPy optimize → LangGraph workflow → response
- [ ] E2E: Paddle webhook → SDK verification → subscription activation → Brevo welcome email
- [ ] E2E: Ticket intake → Signal extraction → Intent classification → RAG retrieval → Response generation → CLARA quality gate
- [ ] Multi-tenant: Company A and Company B operate independently
- [ ] Failover: Kill one LLM provider → Smart Router (via LiteLLM) falls to next

**Documentation Update (G4):**
- [ ] Update `PARWA_Build_Roadmap_v1.md` — Remove "LangGraph" claims if not used, or confirm it IS now used after Day 2
- [ ] Update `PARWA_Phase3_AI_Engine_Roadmap.md` — Accurate framework references
- [ ] Update `CORRECTED_PARWA_Complete_Master_Document.md` — Framework section
- [ ] Update `requirements.txt` — Add all new/updated packages:
  - `langgraph>=1.0.0`
  - `litellm>=1.82.0`
  - `dspy-ai>=3.0.0`
  - `brevo-python>=4.0.0`
  - `paddle-python-sdk>=2.0.0`
  - `twilio>=9.0.0`
- [ ] Create `FRAMEWORK_INTEGRATION_STATUS.md` — Honest status of each framework

---

### Phase P1: HIGH Priority Fixes (Days 6-9)

These fix important operational gaps before production.

---

#### Day 6 — Paddle Webhook Reliability (G1 + P5)

**Goal:** Handle webhook ordering, missed detection, and out-of-order events.

**Tasks:**
- [ ] Implement webhook sequence tracking:
  - Store `webhook_sequences` table: event_id, sequence_number, processed_at
  - Reject out-of-order events (sequence gap detected)
  - Queue out-of-order events for retry after gap filled
- [ ] Implement missed webhook detection:
  - Celery beat task every 15 minutes
  - Query Paddle API for recent events
  - Compare with `webhook_events` table
  - Process any missing events
- [ ] Implement webhook deduplication:
  - Idempotency key per event_id
  - Retry safe (same event processed twice = no side effect)
- [ ] Add monitoring:
  - Alert if > 5 events missed in 1 hour
  - Alert if webhook processing latency > 30 seconds
  - Dashboard showing webhook health
- [ ] Tests: Out-of-order events, duplicate events, missed events, sequence gap recovery

---

#### Day 7 — KB Document Quality + Response Benchmarking (G2 + G3)

**Goal A:** Add document quality validation for KB uploads.
**Goal B:** Build response quality benchmarking suite.

**KB Quality Tasks (G2):**
- [ ] Build document quality validator:
  - File type validation (PDF, DOCX, TXT, CSV, MD, HTML)
  - File size limits (10MB per file, 500MB total per tenant)
  - Content extraction quality check (extracted text > 50% of file size)
  - Language detection (must be supported language)
  - Duplicate detection (fingerprint similar documents)
  - Chunk quality validation (chunks 200-1000 chars, no empty chunks)
  - Embedding quality check (norm > 0.1, not all-zeros)
- [ ] Build retrieval relevance feedback loop:
  - After RAG retrieval, log: query, retrieved chunks, were they relevant?
  - Store feedback in `rag_feedback` table
  - Weekly analysis: which documents have lowest relevance scores?
  - Notify admin: "These 10 KB documents need improvement"
- [ ] Build document health dashboard endpoint:
  - `/api/knowledge/health` — show per-document quality metrics

**Response Benchmarking Tasks (G3):**
- [ ] Build `response_quality_benchmark.py`:
  - Define quality dimensions: accuracy, relevance, tone, completeness, brevity
  - Create test dataset: 50 question-answer pairs per industry
  - Run AI responses through quality evaluation
  - Store results in `quality_benchmarks` table
- [ ] Build quality comparison:
  - Compare response quality across variants (Mini vs PARWA vs High)
  - Compare response quality across time (improving or degrading?)
  - A/B test: optimized prompts vs default prompts (DSPy integration)
- [ ] Build quality reporting endpoint:
  - `/api/analytics/response-quality` — quality trends over time

**Tests:**
- [ ] Upload bad PDF → rejected with clear error message
- [ ] Upload duplicate document → deduplication warning
- [ ] Benchmark runs on test dataset → produces quality scores

---

#### Day 8 — Twilio SDK + Technique Nodes Audit (P1 + P2)

**Goal A:** Add official Twilio SDK.
**Goal B:** Audit and fix all 12 technique nodes.

**Twilio Tasks (P1):**
- [ ] Add `twilio>=9.0.0` to requirements.txt
- [ ] Update `backend/app/services/phone_service.py`:
  - Replace manual HTTP calls with `twilio.rest.Client`
  - Use SDK for: OTP verification, SMS send/receive
- [ ] Update `backend/app/webhooks/twilio_handler.py`:
  - Use SDK's request validator for webhook signature verification
- [ ] Update `backend/app/services/voice_demo.py`:
  - Use SDK's TwiML generation for voice calls
- [ ] Tests: OTP send/verify, SMS webhook validation, voice call setup

**Technique Nodes Audit (P2):**
For each of the 12 technique nodes in `backend/app/core/techniques/`:

| Node | File | Check | Fix If Stub |
|------|------|-------|-------------|
| CRP | `crp.py` | F-140 — Concise Response Protocol | Implement real filler elimination |
| Reverse Thinking | `reverse_thinking.py` | F-141 — Inversion reasoning | Implement real inversion logic |
| Step-Back | `step_back.py` | F-142 — Broader context | Implement real step-back prompts |
| Chain of Thought | `chain_of_thought.py` | CoT reasoning | Implement real chain-of-thought |
| ReAct | `react.py` | F-157 — Tool integration | Verify tool calls work |
| Thread of Thought | `thread_of_thought.py` | ThoT multi-perspective | Implement multi-perspective |
| GST | `gst.py` | F-143 — Sequential checkpoints | Implement 5-checkpoint process |
| UoT | `universe_of_thoughts.py` | F-144 — Multi-solution eval | Implement evaluation matrix |
| ToT | `tree_of_thoughts.py` | F-145 — Branching exploration | Implement real branching |
| Self-Consistency | `self_consistency.py` | F-146 — Multi-answer voting | Implement majority voting |
| Reflexion | `reflexion.py` | F-147 — Self-correction | Implement meta-reasoning |
| Least-to-Most | `least_to_most.py` | F-148 — Query decomposition | Implement ordered sub-queries |

- [ ] For each node: Check if it has real LLM calls or returns placeholder
- [ ] For stubs: Implement using LiteLLM (now available from Day 3)
- [ ] Per-node test: Input → process → verify output quality
- [ ] Integration test: Technique Router → select node → execute → return result

---

#### Day 9 — GDPR Procedures + Emergency Runbooks (P6 + P4)

**Goal A:** Implement GDPR compliance flows.
**Goal B:** Document emergency scenarios.

**GDPR Tasks (P6):**
- [ ] Build data retention service:
  - `backend/app/services/data_retention_service.py`
  - Auto-delete conversations older than N days (configurable per tenant)
  - Auto-delete audit logs older than 365 days
  - Configurable retention periods per data type
- [ ] Build right-to-erasure flow:
  - `DELETE /api/gdpr/erasure-request` — Request data deletion
  - Admin approval required before execution
  - Cascade delete: user → tickets → conversations → embeddings → audit logs
  - Generate erasure certificate (what was deleted, when, by whom)
- [ ] Build consent withdrawal flow:
  - `POST /api/gdpr/withdraw-consent` — Withdraw consent
  - Disable AI processing for this tenant
  - Stop all data collection
  - Notify admin
- [ ] Build GDPR compliance dashboard:
  - `/api/gdpr/status` — Show compliance status
  - Active consent records, data retention status, pending erasure requests
- [ ] GDPR Celery task: Daily retention check + auto-delete
- [ ] Tests: Erasure request → approval → cascade delete → certificate

**Emergency Runbooks (P4):**
- [ ] Create `docs/runbooks/` directory
- [ ] Write `01-database-failover.md`:
  - PostgreSQL goes down mid-conversation
  - Detection: health check failure
  - Immediate: Queue new conversations in Redis
  - Recovery: Replay queued conversations after DB restored
  - RTO: 5 minutes, RPO: 0 (streaming replication)
- [ ] Write `02-redis-failure.md`:
  - Redis cluster failure
  - Impact: Rate limiting, sessions, caching stop working
  - Immediate: Switch to in-memory fallback for sessions
  - Recovery: Rebuild cache from PostgreSQL
  - RTO: 2 minutes
- [ ] Write `03-llm-provider-outage.md`:
  - All 3 providers (Google, Cerebras, Groq) down simultaneously
  - Detection: LiteLLM timeout + health checks
  - Immediate: Queue responses, send "We'll get back to you" message
  - Recovery: Process queue when providers恢复
  - Escalation: Page on-call engineer
- [ ] Write `04-celery-queue-starvation.md`:
  - Queue depth exceeds threshold
  - Detection: Beat task monitoring
  - Action: Auto-scale workers, shed non-critical tasks
- [ ] Write `05-deployment-rollback.md`:
  - Deployment causes regression
  - Detection: Error rate spike
  - Action: Blue-green rollback procedure

---

### Phase P2: MEDIUM Priority + Polish (Days 10-12)

---

#### Day 10 — Dependency Updates + pgvector Performance (P3 + performance)

**Tasks:**
- [ ] Update all dependency versions:
  - `langgraph>=1.1.0` (from >=0.2.0)
  - `dspy-ai>=3.1.0` (from >=2.5.0)
  - `litellm>=1.82.0` (from >=1.40.0)
  - `celery>=5.6.0` (from 5.4.0)
  - `python-socketio>=5.16.0` (from 5.11.4)
  - `brevo-python>=4.0.5`
  - `paddle-python-sdk>=2.0.0`
  - `twilio>=9.0.0`
- [ ] Run full test suite with updated versions
- [ ] Fix any breaking changes from version updates
- [ ] pgvector HNSW index tuning:
  - Benchmark: `m=16, ef_construction=64` vs `m=32, ef_construction=128`
  - Set `hnsw.ef_search` at query time for optimal recall/speed tradeoff
  - Document optimal settings per dataset size

---

#### Day 11 — CI/CD Pipeline (Missing from all phases)

**Goal:** Replace placeholder CI/CD with real deployment pipelines.

**Tasks:**
- [ ] Update `.github/workflows/deploy-backend.yml`:
  - Real AWS ECR image build + push
  - ECS Fargate deployment
  - Environment: staging → production promotion
  - Health check post-deployment
  - Auto-rollback on failure
- [ ] Update `.github/workflows/deploy-frontend.yml`:
  - Real S3 static site deployment
  - CloudFront CDN invalidation
  - Environment variables per stage
- [ ] Add `.github/workflows/test.yml`:
  - Run full test suite on every PR
  - Linting (ruff/flake8)
  - Type checking (mypy)
  - Coverage report
- [ ] Add `.github/workflows/security.yml`:
  - Dependency vulnerability scan (safety)
  - SAST (bandit)
  - Secret detection (trufflehog)

---

#### Day 12 — Final Verification + Phase 3→4 Handoff Prep

**Tasks:**
- [ ] Run full integration test suite (all phases)
- [ ] Verify all 16 gaps are resolved:
  - [ ] C1: pgvector returns real similarity scores
  - [ ] C2: LangGraph StateGraph compiles and runs
  - [ ] C3: LiteLLM handles all LLM calls
  - [ ] C4: DSPy optimization produces results
  - [ ] C5: Brebo v4 sends emails successfully
  - [ ] C6: Paddle SDK handles subscriptions
  - [ ] G1: Paddle webhook ordering works
  - [ ] G2: KB document quality validation works
  - [ ] G3: Response benchmarking produces scores
  - [ ] G4: Docs accurately reflect frameworks
  - [ ] P1: Twilio SDK handles OTP + voice
  - [ ] P2: All 12 technique nodes are real (not stubs)
  - [ ] P3: All dependencies up to date
  - [ ] P4: Emergency runbooks documented
  - [ ] P5: GDPR flows implemented
  - [ ] P6: CI/CD pipelines are real
- [ ] Update `roadmap.md` — Mark Gap Fix phase complete
- [ ] Update `INFRASTRUCTURE_GAPS_TRACKER.md` — Close all resolved gaps
- [ ] Update `PROJECT_STATE.md` — Current state snapshot
- [ ] Phase 3→4 Handoff document:
  - What's been built
  - What's ready for Phase 4
  - Known limitations
  - Recommended starting points for Channels, Jarvis, Dashboard

---

## Summary

| Phase | Days | Items | Severity |
|-------|------|-------|----------|
| **P0: CRITICAL** | Day 1-5 | C1-C6 + G4 | 🔴 CRITICAL/HIGH |
| **P1: HIGH** | Day 6-9 | G1-G3, P1-P2, P4, P6 | 🟡 HIGH/MEDIUM |
| **P2: MEDIUM** | Day 10-12 | P3, P5, CI/CD | 🟢 MEDIUM/LOW |
| **TOTAL** | **12 Days** | **16 items** | — |

---

## Files to Create/Modify Summary

| Day | Create | Modify |
|-----|--------|--------|
| 1 | `pgvector_queries.py` | `vector_search.py`, `embedding_service.py`, `rag_retrieval.py` |
| 2 | — | `langgraph_workflow.py`, `gsd_engine.py`, `technique_executor.py` |
| 3 | — | `smart_router.py`, `dspy_integration.py`, `model_failover.py` |
| 4 | — | `email_service.py`, `brevo_handler.py`, `paddle_service.py`, `paddle_handler.py`, `subscription_service.py` |
| 5 | `FRAMEWORK_INTEGRATION_STATUS.md` | `requirements.txt`, 3 doc files |
| 6 | — | `webhook_tasks.py`, `paddle_handler.py` |
| 7 | `response_quality_benchmark.py` | `knowledge_service.py`, `rag_retrieval.py` |
| 8 | — | `phone_service.py`, `twilio_handler.py`, 12 technique files |
| 9 | `data_retention_service.py`, 5 runbook files | GDPR API routes |
| 10 | — | `requirements.txt` |
| 11 | — | 3 GitHub workflow files |
| 12 | Handoff document | `roadmap.md`, `INFRASTRUCTURE_GAPS_TRACKER.md`, `PROJECT_STATE.md` |

---

## Success Criteria

After these 12 days:
1. ✅ RAG retrieves REAL relevant documents (not random scores)
2. ✅ LangGraph workflows execute real state machines
3. ✅ LiteLLM handles all LLM calls with unified API
4. ✅ DSPy prompt optimization produces improved prompts
5. ✅ Brevo v4 sends all emails reliably
6. ✅ Paddle SDK handles all payment operations
7. ✅ Webhooks are ordered, deduplicated, and recoverable
8. ✅ KB uploads are quality-validated
9. ✅ AI response quality is measurable
10. ✅ Documentation matches code reality
11. ✅ All 12 technique nodes are functional
12. ✅ GDPR compliance flows are operational
13. ✅ CI/CD pipelines deploy real code
14. ✅ Dependencies are up to date
15. ✅ Emergency runbooks exist for all failure scenarios
