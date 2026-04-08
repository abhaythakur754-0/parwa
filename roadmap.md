# PARWA Execution Roadmap

> **Last Updated:** Week 8 COMPLETE → Moving to Week 9  
> **Current Phase:** Week 9 - AI Core (Classification + RAG + Response Generation)

---

## 📊 PROJECT PROGRESS

| Week | Phase | Status | Description |
|------|-------|--------|-------------|
| **Week 1** | Foundation | ✅ COMPLETE | Project skeleton, database, config |
| **Week 2** | Auth System | ✅ COMPLETE | Registration, login, MFA, sessions |
| **Week 3** | Infrastructure | ✅ COMPLETE | Celery, Socket.io, webhooks, health |
| **Week 4** | Ticket System | ✅ COMPLETE | Tickets, customers, omnichannel |
| **Week 5** | Billing System | ✅ COMPLETE | Paddle, subscriptions, invoices |
| **Week 6** | Onboarding | ✅ COMPLETE | F-028 to F-035 + Frontend |
| **Week 7** | Approval System | ✅ COMPLETE | F-074 to F-086 |
| **Week 8** | AI Engine (Phase 3) | ✅ COMPLETE | F-054 to F-059 + 14 SG gaps (991 tests) |
| **Week 9** | AI Core (Classification + RAG + Response) | 🔵 CURRENT | F-062 to F-066, F-149 to F-160 + 12 SG gaps |

---

## ✅ COMPLETED WEEKS

### Week 1: Foundation (Days 1-7)
- Project skeleton (FastAPI + Next.js)
- PostgreSQL + Alembic migrations
- Redis layer
- Error handling + logging
- Health checks
- Multi-tenant middleware

### Week 2: Auth System (Days 8-14)
- User registration (F-010)
- Email verification (F-012)
- Login system (F-013)
- MFA setup (F-015)
- Backup codes (F-016)
- Session management (F-017)
- Rate limiting (F-018)
- API keys (F-019)

### Week 3: Infrastructure (Days 15-22)
- Celery setup (7 queues)
- Socket.io server
- Webhook framework
- Background tasks
- Real-time events

### Week 4: Ticket System (Days 23-32)
- Ticket CRUD (F-046)
- Ticket search (F-048)
- Classification (F-049)
- Assignment (F-050)
- Omnichannel (F-052)
- Customer identity (F-070)

### Week 5: Billing System (Days 27-33)
- Paddle checkout (F-020)
- Webhook handler (F-022)
- Subscription management (F-021)
- Payment confirmation (F-027)
- Invoice history (F-023)
- Overage charging (F-024)
- Cancellation flow (F-025, F-026)

---

## 🔵 CURRENT WEEK: Week 6 - Onboarding System

### Scope (F-028 to F-035 + Frontend)

| Feature ID | Feature | Backend | Frontend |
|------------|---------|---------|----------|
| **NEW** | Post-Payment Details | Details API | Form UI |
| **F-028** | Onboarding Wizard | State machine | 5-step wizard |
| **F-029** | Legal Consent | Consent storage | Checkboxes |
| **F-030** | Pre-built Integrations | OAuth flows | Integration cards |
| **F-031** | Custom Integration Builder | API config | Builder form |
| **F-032** | KB Document Upload | File upload | Drag-drop UI |
| **F-033** | KB Processing + Indexing | Vector embedding | Progress UI |
| **F-034** | AI Activation Gate | Validation API | Activation UI |
| **F-035** | First Victory Celebration | Event tracking | Celebration UI |

---

## 📊 DATABASE STATUS (Week 6)

### ✅ ALREADY EXISTS (Migration 006):

| Table | Status | Location |
|-------|--------|----------|
| `onboarding_sessions` | ✅ EXISTS | Basic columns, needs extension |
| `consent_records` | ✅ EXISTS | Full schema complete |
| `knowledge_documents` | ✅ EXISTS | Full schema complete |
| `document_chunks` | ✅ EXISTS | Full schema complete |
| `demo_sessions` | ✅ EXISTS | For demo chat/call |
| `newsletter_subscribers` | ✅ EXISTS | For newsletter |

**Models Location:** `database/models/onboarding.py`

### ❌ MISSING TABLES:

| Table | Description | Migration |
|-------|-------------|-----------|
| `user_details` | Post-payment details (name, company, industry, work_email) | 010 |

### ❌ MISSING COLUMNS (in `onboarding_sessions`):

| Column | Type | Purpose |
|--------|------|---------|
| `legal_accepted` | BOOLEAN | Legal consent flag |
| `terms_accepted_at` | TIMESTAMPTZ | Terms timestamp |
| `privacy_accepted_at` | TIMESTAMPTZ | Privacy timestamp |
| `ai_data_accepted_at` | TIMESTAMPTZ | AI data timestamp |
| `integrations` | JSONB | Selected integrations `{"email": true, "chat": false}` |
| `knowledge_base_files` | JSONB | Uploaded files list |
| `ai_name` | VARCHAR(50) | AI assistant name (default: 'Jarvis') |
| `ai_tone` | VARCHAR(20) | AI tone (professional/friendly/casual) |
| `ai_response_style` | VARCHAR(20) | AI response style (concise/detailed) |
| `ai_greeting` | TEXT | Custom greeting message |
| `first_victory_completed` | BOOLEAN | First victory flag |

---

## 📊 API STATUS (Week 6)

### ❌ ALL APIs MISSING (18 endpoints):

| # | Endpoint | Method | Purpose | Day |
|---|----------|--------|---------|-----|
| 1 | `/api/onboarding/state` | GET | Get current onboarding state | Day 1 |
| 2 | `/api/user/details` | POST | Submit user details (name, company, industry) | Day 1 |
| 3 | `/api/user/verify-work-email` | POST | Send verification for work email | Day 1 |
| 4 | `/api/onboarding/start` | POST | Initialize onboarding wizard | Day 3 |
| 5 | `/api/onboarding/legal` | POST | Save legal consents (terms, privacy, AI data) | Day 3 |
| 6 | `/api/onboarding/step/{n}` | POST | Mark step n as complete | Day 3 |
| 7 | `/api/onboarding/activate` | POST | Activate AI after prerequisites | Day 7 |
| 8 | `/api/integrations/available` | GET | List available integrations | Day 5 |
| 9 | `/api/integrations` | POST | Create/save integration config | Day 5 |
| 10 | `/api/integrations/:id/test` | POST | Test integration connection | Day 5 |
| 11 | `/api/knowledge/upload` | POST | Upload KB document | Day 6 |
| 12 | `/api/knowledge` | GET | List uploaded documents | Day 6 |
| 13 | `/api/knowledge/:id` | DELETE | Delete uploaded document | Day 6 |
| 14 | `/api/knowledge/:id/status` | GET | Get document processing status | Day 6 |
| 15 | `/api/onboarding/first-victory` | GET | Get first victory status | Day 8 |
| 16 | `/api/onboarding/first-victory` | POST | Mark first victory complete | Day 8 |
| 17 | `/api/user/details` | GET | Get current user details | Day 1 |
| 18 | `/api/user/details` | PATCH | Update user details | Day 1 |

---

## 📊 SERVICE STATUS (Week 6)

### ❌ ALL SERVICES MISSING:

| Service | Purpose | Day |
|---------|---------|-----|
| `UserDetailsService` | Handle post-payment details CRUD | Day 1 |
| `OnboardingService` | State machine management (step transitions) | Day 3 |
| `ConsentService` | Legal consent handling + GDPR compliance | Day 3 |
| `IntegrationService` | Integration config + OAuth flows | Day 5 |
| `KnowledgeService` | File upload + document management | Day 6 |
| `EmbeddingService` | Vector embedding generation (pgvector) | Day 7 |
| `VictoryService` | First victory tracking + celebration | Day 8 |

---

## 📊 CELERY TASK STATUS (Week 6)

### ❌ ALL TASKS MISSING:

| Task | Queue | Purpose | Day |
|------|-------|---------|-----|
| `process_knowledge_document` | knowledge | Extract text, chunk, queue embedding | Day 7 |
| `generate_embeddings` | ai_heavy | Generate vector embeddings for chunks | Day 7 |

---

## 📊 FRONTEND STATUS (Week 6)

### ❌ ALL FRONTEND MISSING (19 components):

#### Day 2: Post-Payment Details (4 components)
| Component | Purpose |
|-----------|---------|
| `frontend/src/app/welcome/details/page.tsx` | Post-payment details page |
| `frontend/src/components/onboarding/DetailsForm.tsx` | Form for name, company, industry |
| `frontend/src/components/onboarding/IndustrySelect.tsx` | Industry dropdown |
| `frontend/src/components/onboarding/WorkEmailVerification.tsx` | Work email verification flow |

#### Day 4: Onboarding Wizard (5 components)
| Component | Purpose |
|-----------|---------|
| `frontend/src/app/onboarding/page.tsx` | Main wizard page |
| `frontend/src/components/onboarding/OnboardingWizard.tsx` | Wizard container + navigation |
| `frontend/src/components/onboarding/ProgressIndicator.tsx` | Step progress indicator |
| `frontend/src/components/onboarding/WelcomeScreen.tsx` | Step 1: Welcome |
| `frontend/src/components/onboarding/LegalCompliance.tsx` | Step 2: Legal checkboxes |

#### Day 5: Integrations (3 components)
| Component | Purpose |
|-----------|---------|
| `frontend/src/components/onboarding/IntegrationSetup.tsx` | Step 3: Integration selection |
| `frontend/src/components/onboarding/IntegrationCard.tsx` | Individual integration card |
| `frontend/src/components/onboarding/CustomIntegrationBuilder.tsx` | Custom API integration form |

#### Day 6: Knowledge Base (3 components)
| Component | Purpose |
|-----------|---------|
| `frontend/src/components/onboarding/KnowledgeUpload.tsx` | Step 4: KB upload container |
| `frontend/src/components/onboarding/FileDropZone.tsx` | Drag-drop file upload |
| `frontend/src/components/onboarding/FileList.tsx` | List of uploaded files |

#### Day 7: AI Activation (3 components)
| Component | Purpose |
|-----------|---------|
| `frontend/src/components/onboarding/ProcessingStatus.tsx` | Document processing progress |
| `frontend/src/components/onboarding/AIConfig.tsx` | Step 5: AI personality config |
| `frontend/src/components/onboarding/ActivationButton.tsx` | AI activation button |

#### Day 8: First Victory (1 component)
| Component | Purpose |
|-----------|---------|
| `frontend/src/components/onboarding/FirstVictory.tsx` | Victory celebration + confetti |

---

## Week 6 Implementation Plan (8 Days)

---

### Day 1: Database Schema + Post-Payment Details API

**Database Migration (010_onboarding_extended.py):**
- [ ] Create `user_details` table
- [ ] Add missing columns to `onboarding_sessions` table

**Backend APIs:**
- [ ] `GET /api/onboarding/state` - Get onboarding state
- [ ] `GET /api/user/details` - Get current user details
- [ ] `POST /api/user/details` - Submit user details
- [ ] `PATCH /api/user/details` - Update user details
- [ ] `POST /api/user/verify-work-email` - Send verification email

**Services:**
- [ ] `UserDetailsService` - CRUD for user details

**Files to Build:**
```
database/alembic/versions/010_onboarding_extended.py
backend/app/api/user_details.py
backend/app/api/onboarding.py (partial)
backend/app/schemas/onboarding.py
backend/app/services/user_details_service.py
database/models/user_details.py
```

**Files to Update:**
```
database/models/onboarding.py (add missing columns)
```

**Tests:**
- [ ] Test: `user_details` table created with correct columns
- [ ] Test: `onboarding_sessions` extended with new columns
- [ ] Test: company_id on every table (BC-001)
- [ ] Test: API endpoints work correctly
- [ ] Test: Work email verification flow

---

### Day 2: Post-Payment Details Frontend

**Frontend Components:**
- [ ] `frontend/src/app/welcome/details/page.tsx`
- [ ] `frontend/src/components/onboarding/DetailsForm.tsx`
- [ ] `frontend/src/components/onboarding/IndustrySelect.tsx`
- [ ] `frontend/src/components/onboarding/WorkEmailVerification.tsx`

**Tests:**
- [ ] Test: Form renders correctly
- [ ] Test: Validation works (required fields)
- [ ] Test: Submit calls API
- [ ] Test: Industry dropdown populated
- [ ] Test: Work email verification UI

---

### Day 3: Onboarding Wizard Backend (F-028, F-029)

**Backend APIs:**
- [ ] `POST /api/onboarding/start` - Initialize wizard
- [ ] `POST /api/onboarding/legal` - Save legal consents
- [ ] `POST /api/onboarding/step/{n}` - Complete step

**Services:**
- [ ] `OnboardingService` - State machine management
- [ ] `ConsentService` - Legal consent handling

**Files to Build:**
```
backend/app/api/onboarding.py (complete)
backend/app/services/onboarding_service.py
backend/app/services/consent_service.py
```

**Tests:**
- [ ] Test: State machine transitions correctly
- [ ] Test: Consents stored with timestamps
- [ ] Test: BC-010 compliance (GDPR)
- [ ] Test: Cannot skip steps
- [ ] Test: Step completion idempotent

---

### Day 4: Onboarding Wizard Frontend (F-028, F-029)

**Frontend Components:**
- [ ] `frontend/src/app/onboarding/page.tsx`
- [ ] `frontend/src/components/onboarding/OnboardingWizard.tsx`
- [ ] `frontend/src/components/onboarding/ProgressIndicator.tsx`
- [ ] `frontend/src/components/onboarding/WelcomeScreen.tsx`
- [ ] `frontend/src/components/onboarding/LegalCompliance.tsx`

**Tests:**
- [ ] Test: Wizard renders all steps
- [ ] Test: Progress indicator updates
- [ ] Test: Legal checkboxes required
- [ ] Test: Navigation (back/next) works
- [ ] Test: State persists on refresh

---

### Day 5: Integration Setup (F-030, F-031)

**Backend APIs:**
- [ ] `GET /api/integrations/available` - List available integrations
- [ ] `POST /api/integrations` - Create integration
- [ ] `POST /api/integrations/:id/test` - Test connection

**Services:**
- [ ] `IntegrationService` - Integration logic

**Frontend Components:**
- [ ] `frontend/src/components/onboarding/IntegrationSetup.tsx`
- [ ] `frontend/src/components/onboarding/IntegrationCard.tsx`
- [ ] `frontend/src/components/onboarding/CustomIntegrationBuilder.tsx`

**Files to Build:**
```
backend/app/api/integrations.py
backend/app/services/integration_service.py
frontend/src/components/onboarding/IntegrationSetup.tsx
frontend/src/components/onboarding/IntegrationCard.tsx
frontend/src/components/onboarding/CustomIntegrationBuilder.tsx
```

**Tests:**
- [ ] Test: Integration list loads
- [ ] Test: Test connection works
- [ ] Test: Custom builder saves config
- [ ] Test: Integration config stored correctly

---

### Day 6: Knowledge Base Upload (F-032)

**Backend APIs:**
- [ ] `POST /api/knowledge/upload` - Upload document
- [ ] `GET /api/knowledge` - List documents
- [ ] `DELETE /api/knowledge/:id` - Delete document
- [ ] `GET /api/knowledge/:id/status` - Get processing status

**Services:**
- [ ] `KnowledgeService` - File handling

**Frontend Components:**
- [ ] `frontend/src/components/onboarding/KnowledgeUpload.tsx`
- [ ] `frontend/src/components/onboarding/FileDropZone.tsx`
- [ ] `frontend/src/components/onboarding/FileList.tsx`

**Files to Build:**
```
backend/app/api/knowledge.py
backend/app/services/knowledge_service.py
frontend/src/components/onboarding/KnowledgeUpload.tsx
frontend/src/components/onboarding/FileDropZone.tsx
frontend/src/components/onboarding/FileList.tsx
```

**Tests:**
- [ ] Test: File upload works
- [ ] Test: File validation (PDF, DOCX, TXT, CSV)
- [ ] Test: File size limit (10MB)
- [ ] Test: File list displays correctly
- [ ] Test: Delete removes file

---

### Day 7: KB Processing + AI Activation (F-033, F-034)

**Backend:**
- [ ] Text extraction from documents (PDF, DOCX, TXT, CSV)
- [ ] Chunking logic (500-1000 chars with overlap)
- [ ] Vector embedding generation (pgvector)
- [ ] `POST /api/onboarding/activate` - Activate AI
- [ ] Prerequisites validation (legal + KB)

**Celery Tasks:**
- [ ] `process_knowledge_document` task
- [ ] `generate_embeddings` task

**Frontend Components:**
- [ ] `frontend/src/components/onboarding/ProcessingStatus.tsx`
- [ ] `frontend/src/components/onboarding/AIConfig.tsx`
- [ ] `frontend/src/components/onboarding/ActivationButton.tsx`

**Files to Build:**
```
backend/app/services/embedding_service.py
backend/app/tasks/knowledge_tasks.py
frontend/src/components/onboarding/ProcessingStatus.tsx
frontend/src/components/onboarding/AIConfig.tsx
frontend/src/components/onboarding/ActivationButton.tsx
```

**Tests:**
- [ ] Test: Document processing works
- [ ] Test: Embeddings generated correctly
- [ ] Test: Activation validates prerequisites
- [ ] Test: Celery task queue routing
- [ ] Test: Processing status updates

---

### Day 8: First Victory + Testing (F-035)

**Backend:**
- [ ] `GET /api/onboarding/first-victory` - Get first victory status
- [ ] `POST /api/onboarding/first-victory` - Mark complete
- [ ] First victory event tracking
- [ ] Celebration event emission (Socket.io)

**Services:**
- [ ] `VictoryService` - First victory tracking

**Frontend Components:**
- [ ] `frontend/src/components/onboarding/FirstVictory.tsx`
- [ ] Celebration animation/confetti
- [ ] Redirect to dashboard

**Testing:**
- [ ] End-to-end test: Payment → Details → Onboarding → Victory
- [ ] Unit tests for all services
- [ ] Integration tests for all APIs

**Files to Build:**
```
backend/app/services/victory_service.py
frontend/src/components/onboarding/FirstVictory.tsx
tests/unit/test_onboarding.py
tests/integration/test_onboarding_flow.py
```

**Files to Update:**
```
backend/app/api/onboarding.py (add victory endpoints)
```

---

## Week 6 Summary

| Metric | Count |
|--------|-------|
| Days | 8 |
| New DB Tables | 1 (`user_details`) |
| Extended DB Tables | 1 (`onboarding_sessions` +11 columns) |
| Backend APIs | 18 |
| Backend Services | 7 |
| Celery Tasks | 2 |
| Frontend Components | 19 |
| Total Files | ~35 |

---

## ⬜ UPCOMING: Week 7 - Approval System

**Brief Overview:**

Week 7 is the **Human Review System** where managers approve/reject AI actions before execution.

| Feature | Description |
|---------|-------------|
| F-074 | Approval Queue - Pending actions dashboard |
| F-075 | Batch Approval - Approve similar tickets at once |
| F-076 | Individual Approve/Reject |
| F-077 | Auto-handle Rules |
| F-079 | Confidence Score Breakdown |
| F-080 | Urgent Attention Panel - VIP/Legal tickets |
| F-081 | Approval Reminders - Escalating notifications |
| F-082 | Approval Timeout - Auto-reject after 72h |
| F-083 | Emergency Pause - Kill-switch for AI |
| F-084 | Undo System - Reverse executed actions |

**Purpose:** Safety layer ensuring every AI action with real-world impact goes through human review.

---

## ✅ Week 8: AI Engine — Phase 3 Core (Days 1-2 COMPLETE, Days 3-5 Pending)

### Scope

Week 8 establishes the AI pipeline foundation — Smart Router, PII Redaction, Guardrails, Confidence Scoring, and Variant-aware routing. Every subsequent Week 9-12 AI feature depends on this.

### Day 1 (COMPLETE) — Database + Variant AI Matrix

| Task | ID | Status | File |
|------|----|--------|------|
| Phase 3 DB Migration (9 tables) | — | ✅ Done | `database/alembic/versions/011_phase3_variant_engine.py` |
| Variant AI Capability Matrix | SG-01 | ✅ Done | `backend/app/services/variant_capability_service.py` |
| Unlimited Variant Instance Architecture | SG-37 | ✅ Done | `backend/app/services/variant_instance_service.py` |
| Variant Orchestration Layer | SG-38 | ✅ Done | `backend/app/services/variant_orchestration_service.py` |
| AI Feature Entitlement Enforcement | SG-05 | ✅ Done | `backend/app/services/entitlement_middleware.py` |
| Agent Assignment Strategy | SG-22 | ✅ Done | `backend/app/services/agent_assignment_service.py` |
| Task Decomposition Plan | SG-21 | ✅ Done | `backend/app/services/agent_assignment_service.py` |

### Day 2 (COMPLETE) — Smart Router + Variant Model Access

| Task | ID | Status | File |
|------|----|--------|------|
| Smart Router (3-tier LLM routing) | F-054 | ✅ Done | `backend/app/core/smart_router.py` |
| Variant-Specific Router Model Access | SG-03 | ✅ Done | `backend/app/core/smart_router.py` |
| Model Failover | F-055 | ✅ Done | `backend/app/core/model_failover.py` |
| AI Engine Cold Start | SG-30 | ✅ Done | `backend/app/core/cold_start_service.py` |
| AI Engine Cost Overrun Protection | SG-35 | ✅ Done | `backend/app/services/cost_protection_service.py` |

### Day 2 Gap Fixes (COMPLETE)

| Gap | Severity | What Was Fixed |
|-----|----------|---------------|
| GAP 1 | CRITICAL | Non-atomic counter race conditions → atomic SQL UPDATE |
| GAP 2 | CRITICAL | updated_at never auto-updates → onupdate=lambda |
| GAP 3 | HIGH | route_ticket() missing capacity check → 503 check |
| GAP 4-8 | HIGH/MED/LOW | Various updated_at, rollback, rebalance, datetime fixes |
| GAP 9-14 | CRITICAL/HIGH | Smart Router: shared state, 429 handling, async, system prompt |
| GAP 15-21 | CRITICAL/HIGH | Failover: wrong model IDs, tier chains, guardrail chain, async |
| GAP 22-26 | HIGH/MEDIUM | Cold Start: API keys, guardrail tier, heavy timeout, cleanup |
| GAP 27-30 | MEDIUM | Cost Protection: deprecated datetime, tier budgets, router integration |

### Day 2 Infrastructure Gaps (COMPLETE)

| Gap | What Was Built |
|-----|----------------|
| No API endpoints | `backend/app/api/ai_engine.py` — 28 REST endpoints for all services |
| No AI entitlement middleware | `backend/app/middleware/ai_entitlement.py` — ASGI middleware wired in main.py |
| No Celery tasks for AI Engine | `backend/app/tasks/ai_engine_tasks.py` — rebalancer, budget reset, warmup, cleanup |
| No agent assignment service | `backend/app/services/agent_assignment_service.py` + `backend/app/api/ai_agent.py` |
| Celery beat not configured | 3 new beat entries: rebalance 60s, budget reset midnight, injection log cleanup |

### Day 3 (COMPLETE) — PII Redaction + Guardrails + Prompt Injection Defense

| Task | ID | Status | File |
|------|----|--------|------|
| PII Redaction Engine (15 PII types, Redis map, deterministic tokens) | F-056 | ✅ Done | `backend/app/core/pii_redaction_engine.py` |
| Guardrails AI (8-layer safety engine, per-tenant config) | F-057 | ✅ Done | `backend/app/core/guardrails_engine.py` |
| Tenant-Specific Prompt Injection Defense (25+ rules, 7 categories) | SG-36 | ✅ Done | `backend/app/core/prompt_injection_defense.py` |
| Hallucination Detection Patterns (12 patterns) | SG-27 | ✅ Done | `backend/app/core/hallucination_detector.py` |

#### Day 3 Gap Analysis (COMPLETE)

| File | Gaps Found | Severity Breakdown |
|------|------------|-------------------|
| F-056 PII Redaction | 5 | 2 HIGH, 2 MEDIUM, 1 LOW |
| F-057 Guardrails | 4 | 1 HIGH, 2 MEDIUM, 1 LOW |
| SG-36 Prompt Injection | 5 | 2 HIGH, 2 MEDIUM, 1 LOW |
| SG-27 Hallucination | 6 | 2 HIGH, 3 MEDIUM, 1 LOW |

All gaps identified and fixed during Day 3 build cycle.

### Day 4 (COMPLETE) — Confidence Scoring + Blocked Response + Variant Thresholds

| Task | ID | Status | File |
|------|----|--------|------|
| Confidence Scoring (7 weighted signals, variant thresholds) | F-059 | ✅ Done | `backend/app/core/confidence_scoring_engine.py` |
| Variant-Specific Confidence Thresholds (mini=95, parwa=85, high=75) | SG-04 | ✅ Done | `backend/app/core/confidence_scoring_engine.py` |
| Blocked Response Manager + Review Queue (priority, auto-reject, batch) | F-058 | ✅ Done | `backend/app/core/blocked_response_manager.py` |
| LLM Provider Management (health, alerts, API keys, usage stats) | — | ✅ Done | `backend/app/services/provider_management_service.py` |
| Prompt Template Management (10 defaults, versioning, A/B testing) | — | ✅ Done | `backend/app/services/prompt_template_service.py` |

### Day 5 (COMPLETE) — Integration + Testing + Monitoring

| Task | ID | Status |
|------|----|--------|
| Week 8 Integration Testing | — | ✅ Done |
| Real-Time AI Performance Monitoring | SG-19 | ✅ Done |
| AI Self-Healing Per Variant | SG-20 | ✅ Done |
| Week 8 Error Fix Sprint | — | ✅ Done |

### Week 8 Files Created/Modified

| File | Type | Description |
|------|------|-------------|
| `database/alembic/versions/011_phase3_variant_engine.py` | Migration | 9 new tables for Phase 3 |
| `database/models/variant_engine.py` | Model | SQLAlchemy models for 9 tables |
| `backend/app/core/smart_router.py` | Core | 3-tier LLM routing (Light/Medium/Heavy) |
| `backend/app/core/model_failover.py` | Core | Provider failover chains |
| `backend/app/core/cold_start_service.py` | Core | Tenant model warmup |
| `backend/app/services/cost_protection_service.py` | Service | Token budget management |
| `backend/app/services/variant_capability_service.py` | Service | Feature→variant mapping |
| `backend/app/services/variant_instance_service.py` | Service | Unlimited instance management |
| `backend/app/services/variant_orchestration_service.py` | Service | Celery workload distribution |
| `backend/app/services/entitlement_middleware.py` | Service | Feature entitlement enforcement |
| `backend/app/services/agent_assignment_service.py` | Service | Agent→feature/task mapping |
| `backend/app/api/ai_engine.py` | API | 28 REST endpoints for AI services |
| `backend/app/api/ai_agent.py` | API | 8 endpoints for agent management |
| `backend/app/middleware/ai_entitlement.py` | Middleware | AI entitlement ASGI middleware |
| `backend/app/tasks/ai_engine_tasks.py` | Celery | Rebalancer, budget reset, warmup, cleanup |
| `backend/app/core/pii_redaction_engine.py` | Core | 15 PII types, Redis map, deterministic tokens (F-056) |
| `backend/app/core/guardrails_engine.py` | Core | 8-layer safety engine, per-tenant config (F-057) |
| `backend/app/core/prompt_injection_defense.py` | Core | 25+ rules, 7 categories, rate limiting (SG-36) |
| `backend/app/core/hallucination_detector.py` | Core | 12 detection patterns, recommendation engine (SG-27) |
| `backend/app/tests/test_pii_redaction.py` | Tests | 60+ tests for PII redaction |
| `backend/app/tests/test_guardrails.py` | Tests | 55+ tests for guardrails |
| `backend/app/tests/test_prompt_injection.py` | Tests | 68+ tests for prompt injection |
| `backend/app/tests/test_hallucination_detector.py` | Tests | 70+ tests for hallucination detection |
| `backend/app/core/confidence_scoring_engine.py` | Core | 7 weighted signals, variant thresholds (F-059, SG-04) |
| `backend/app/core/blocked_response_manager.py` | Core | Review queue, auto-reject, batch review (F-058) |
| `backend/app/services/provider_management_service.py` | Service | Provider health, alerts, API key rotation |
| `backend/app/services/prompt_template_service.py` | Service | 10 default templates, versioning, A/B testing |
| `backend/app/tests/test_confidence_scoring.py` | Tests | 148 tests for confidence scoring |
| `backend/app/tests/test_blocked_response.py` | Tests | 98 tests for blocked response manager |
| `backend/app/tests/test_provider_management.py` | Tests | 69 tests for provider management |
| `backend/app/tests/test_prompt_template.py` | Tests | 83 tests for prompt templates |

### Week 8 Test Summary

| Metric | Count |
|--------|-------|
| Test files | 8 |
| Total tests | 523 |
| Passing | 523 |
| Failing | 0 |

---

## 🔵 CURRENT WEEK: Week 9 - AI Core (Classification + RAG + Response Generation)

### Scope

Week 9 builds the **AI brain** — classification, RAG retrieval, and response generation. This turns PARWA from a routing framework into an **intelligent system**. The Signal Extraction Layer is the critical glue.

**Dependencies:** Week 8 (✅ Smart Router, PII Redaction, Guardrails, Confidence Scoring), Week 6 (KB must be indexed for RAG)

### Week 9 Prerequisite Fixes (Day 0 — Must Complete Before Day 6)

> These are CRITICAL blockers discovered from gap analysis files and INFRA GAPS TRACKER.

| # | Fix | Severity | Source | Action |
|---|-----|----------|--------|--------|
| P1 | Verify KB embeddings exist in pgvector | 🔴 CRITICAL | INFRA GAPS TRACKER | Check `knowledge_documents` table has processed docs; verify `document_chunks` has embeddings; confirm pgvector extension enabled |
| P2 | Build/verify EmbeddingService | 🔴 CRITICAL | Week 6 gap list | If `embedding_service.py` is a stub, build real embedding generation using Google AI/Cerebras |
| P3 | Fix 3 CRITICAL tenant isolation leaks | 🔴 CRITICAL | `gap_analysis_agent1_models.json`, `gap_analysis_agent2_services.json` | Fix `ai_agent_assignments` company_id filter, `variant_capability_service` isolation, ticket counter race condition |
| P4 | Fix 8 HIGH gaps from agent1/agent2 JSON | 🟡 HIGH | `gap_analysis_agent1_models.json`, `gap_analysis_agent2_services.json` | Fix counter underflow, JSON corruption, FK cascade, status validation, namespace collision, silent batch failures, instance state, capacity overflow |
| P5 | Verify DEP-04 package compatibility | 🟡 HIGH | INFRA GAPS TRACKER | Test `langgraph + dspy-ai + litellm` work with FastAPI/Celery/Redis stack |
| P6 | Resolve tenant_id vs company_id standardization | 🟡 HIGH | INFRA GAPS TRACKER DC2 | Audit all new Week 9 code uses `company_id` consistently |

---

### Day 6 (Monday) — Signal Extraction + Intent Classification + CLARA

| Task | ID | Status | Description |
|------|----|--------|-------------|
| Signal Extraction Layer (10 signals) | — | ⬜ | Extract: intent, sentiment, complexity, monetary value, customer tier, turn count, previous response status, reasoning loop detection, resolution path count, query breadth. Feeds Smart Router + Technique Router. |
| SG-13: Signal Extraction Implementation | SG-13 | ⬜ | Full implementation: dedicated extraction functions, configurable weights per variant, signal cache (60s TTL), quality validation, versioning for A/B testing. |
| F-062: Ticket Intent Classification | F-062 | ⬜ | Multi-label classifier: refund/technical/billing/complaint/feature_request/general. Uses Smart Router Light tier. Outputs: primary intent (1), secondary intents (0-3), confidence per intent. |
| F-149: Intent × Technique Mapping Table | F-149 | ⬜ | Map 6 intent types → recommended techniques + trigger conditions (from Feature Spec Batch 6). Wire F-062 output to Technique Router input. |
| SG-25: Per-Intent Prompt Templates (~40) | SG-25 | ⬜ | 40 specialized prompt templates — one per intent × response type. Each: system prompt, few-shot examples, output schema, tone instructions. |
| F-150: CLARA Quality Gate Pipeline | F-150 | ⬜ | Build 5-stage CLARA pipeline: Structure Check → Logic Check → Brand Check → Tone Check → Delivery. Tier 1 always-active. Required by F-065 auto-response. Source: AI Technique Framework. |

**Files to Build:**
```
backend/app/core/signal_extraction.py
backend/app/core/classification_engine.py
backend/app/core/clara_quality_gate.py
backend/app/services/intent_technique_mapper.py
backend/app/api/classification.py
backend/app/api/signals.py
backend/app/tests/test_signal_extraction.py
backend/app/tests/test_classification.py
backend/app/tests/test_clara.py
backend/app/tests/test_intent_technique_mapping.py
```

---

### Day 7 (Tuesday) — Sentiment Analysis + RAG Part 1 + Language Pipeline

| Task | ID | Status | Description |
|------|----|--------|-------------|
| F-063: Sentiment Analysis / Empathy Engine | F-063 | ⬜ | 0-100 frustration score. Triggers escalation at 60+, VIP routing at 80+. Tone adjustment: empathetic at 40+, urgent at 70+, de-escalation at 90+. |
| F-151: Sentiment × Technique Trigger Mapping | F-151 | ⬜ | Map sentiment ranges → techniques: <0.3 → UoT + Step-Back; 0.3-0.5 → Step-Back only. Priority override rules (from Feature Spec Batch 9). Wire to Technique Router. |
| SG-26: Model-Specific Response Formatters (~15) | SG-26 | ⬜ | 15 response formatters per model variant. Normalize: token limits, markdown, citation formatting, tone, length. |
| F-064: Knowledge Base RAG (part 1 — retrieval) | F-064 | ⬜ | pgvector search, top-k retrieval, similarity threshold. Tenant-isolated. RAG complexity by variant: Mini=basic vector, Parwa=+metadata filtering, High=full pipeline. |
| F-152: `shared/knowledge_base/` Module | F-152 | ⬜ | New shared module for RAG + vector search operations. Reusable across services. Source: INFRA GAPS TRACKER. |
| F-153: RAG Re-Indexing Triggers | F-153 | ⬜ | Cache invalidation on KB document updates. Automatic re-embedding when docs change. Source: Build Roadmap feedback loops. |
| SG-29: Language Detection/Translation Pipeline (~8) | SG-29 | ⬜ | 8-step pipeline: detection → confidence → tenant language → translate → AI process → translate back → quality check → fallback. |

**Files to Build:**
```
backend/app/core/sentiment_engine.py
backend/app/core/rag_retrieval.py
shared/knowledge_base/__init__.py
shared/knowledge_base/vector_search.py
shared/knowledge_base/reindexing.py
backend/app/services/sentiment_technique_mapper.py
backend/app/api/rag.py
backend/app/tests/test_sentiment.py
backend/app/tests/test_rag_retrieval.py
backend/app/tests/test_language_pipeline.py
```

---

### Day 8 (Wednesday) — RAG Part 2 + Auto-Response + Ticket Assignment

| Task | ID | Status | Description |
|------|----|--------|-------------|
| F-064: Knowledge Base RAG (part 2 — reranking) | F-064 | ⬜ | Cross-encoder reranking, metadata filtering, context window assembly, citation tracking. Variant differentiation: Mini=skip reranking, Parwa=cross-encoder, High=retrieve-rewrite-rerank. |
| F-065: Auto-Response Generation | F-065 | ⬜ | Combine intent + RAG context + sentiment → brand-aligned response. Smart Router Medium tier. Runs through CLARA quality gate. |
| F-154: Brand Voice Config Per Company | F-154 | ⬜ | Per-company brand voice settings: tone, formality, prohibited words, response length preference. Source: Build Roadmap v1. |
| F-155: Response Template Storage | F-155 | ⬜ | CRUD for response templates per tenant (distinct from prompt templates in SG-25). Source: Build Roadmap v1. |
| F-156: Per-Conversation Token Budget | F-156 | ⬜ | Track token usage within single conversation thread. Context overflow protection for F-065. Source: Context Bible. |
| F-157: ReAct Tool Integrations (4 tools) | F-157 | ⬜ | Build tool adapters for: Order Management API, Billing System API, CRM Integration, Ticket System. (RAG KB already built Day 7). Source: AI Technique Framework. |
| F-050: AI-Powered Ticket Assignment | F-050 | ⬜ | Score-based: specialty (40) + workload (30) + historical accuracy (20) + jitter (10). |
| F-158: Rule→AI Migration (F-049/F-050) | F-158 | ⬜ | Migrate Week 4 rule-based classification & assignment to AI. Build fallback: if AI classification fails → fall back to rule-based. |
| SG-23: Parallel Build Groups | SG-23 | ⬜ | Document which Week 9+ tasks can be built simultaneously. Update SG-21 task decomposition. |

**Files to Build:**
```
backend/app/core/rag_reranking.py
backend/app/core/response_generator.py
backend/app/services/brand_voice_service.py
backend/app/services/response_template_service.py
backend/app/services/token_budget_service.py
backend/app/core/react_tools/
backend/app/core/react_tools/order_tool.py
backend/app/core/react_tools/billing_tool.py
backend/app/core/react_tools/crm_tool.py
backend/app/core/react_tools/ticket_tool.py
backend/app/api/response.py
backend/app/tests/test_rag_reranking.py
backend/app/tests/test_response_generation.py
backend/app/tests/test_react_tools.py
```

---

### Day 9 (Thursday) — Draft Composer + Training Data + Edge Cases

| Task | ID | Status | Description |
|------|----|--------|-------------|
| F-066: AI Draft Composer (Co-Pilot Mode) | F-066 | ⬜ | Suggest drafts to human agents — accept/edit/regenerate. Real-time via Socket.io. |
| SG-12: Variant-Specific Training Data Isolation | SG-12 | ⬜ | Per-variant datasets. Isolation at: storage (S3 prefixes), processing (variant tag in Celery), vector index (tenant+variant metadata), model (variant fine-tuning configs). |
| SG-24: 170+ AI Sub-Features Enumeration | SG-24 | ⬜ | Complete catalog of ALL 170+ sub-features. Map: parent feature, variant access, building codes, complexity, dependencies. Must cover the ~87 unenumerated sub-features from Context Bible. |
| SG-28: Edge-Case Handler Registry (~20) | SG-28 | ⬜ | 20 edge-case handlers: empty query, too long, unsupported language, emojis only, code blocks, duplicate, embedded images, multi-question, non-existent ticket, malicious HTML, FAQ match, below confidence, maintenance mode, expired context, blocked user, pricing request, legal terminology, competitor mention, system commands, timeout. |
| SG-34: Data Freshness for RAG | SG-34 | ⬜ | Moved from Week 10. RAG needs cache invalidation on KB updates, signal staleness detection (>5min → re-extract), context freshness check. |
| SG-02: Technique Tier Access Check | SG-02 | ⬜ | Moved from Week 10.5. Technique Router must check variant before technique selection. Needed by intent/sentiment × technique mappings built Day 6-7. |

**Files to Build:**
```
backend/app/core/draft_composer.py
backend/app/core/edge_case_handlers.py
backend/app/services/training_data_isolation.py
backend/app/services/data_freshness_service.py
backend/app/tests/test_draft_composer.py
backend/app/tests/test_edge_cases.py
backend/app/tests/test_training_isolation.py
```

---

### Day 10 (Friday) — Cross-Variant Routing + Anti-Arbitrage + Integration

| Task | ID | Status | Description |
|------|----|--------|-------------|
| SG-06: Cross-Variant Routing Rules | SG-06 | ⬜ | Channel→variant mapping, escalation path (lower→higher), shared context, billing allocation per variant. |
| SG-11: Cross-Variant Ticket Routing Logic | SG-11 | ⬜ | Algorithm: channel match → highest variant → auto-escalate if exceeds capability → bill to originating variant unless escalated. |
| F-159: Multi-Instance Anti-Arbitrage | F-159 | ⬜ | Detect tier gaming: e.g., 10 Mini instances to get capacity of 1 PARWA High. Cap total capacity per tenant across all instances. Source: Build Roadmap F-006. |
| F-160: Conversation Summarization Modes | F-160 | ⬜ | Multi-turn conversation summarization for context management. Needed for long conversations before Week 10 context compression. Source: Context Bible. |
| Week 9 Integration Testing | — | ⬜ | E2E: ticket → classification → sentiment → RAG → response generation. Test ALL variant tiers (Mini/Parwa/High). |
| Week 9 Gap Analysis Sprint | — | ⬜ | Run gap_finder.py on ALL Week 9 files. Fix all discovered gaps. |
| Week 9 Error Fix Sprint | — | ⬜ | Fix all bugs from integration testing. Update ERROR_LOG.md. |

**Files to Build:**
```
backend/app/core/cross_variant_router.py
backend/app/core/anti_arbitrage.py
backend/app/core/conversation_summarizer.py
backend/app/api/cross_variant.py
backend/app/tests/test_cross_variant.py
backend/app/tests/test_anti_arbitrage.py
backend/app/tests/test_conversation_summarizer.py
backend/app/tests/test_week9_integration.py
```

---

### Week 9 Summary

| Category | Original Count | Added | New Total |
|----------|---------------|-------|-----------|
| EXISTING features | 7 | 0 | 7 |
| SG gap items | 10 | 0 | 10 |
| NEW items from gap analysis | 0 | 14 | 14 |
| Prerequisite fixes | 0 | 6 | 6 |
| **Total Week 9 tasks** | **~25** | **+20** | **~45** |

### Week 9 New Items Added (from comprehensive doc/gap review)

| # | Item | F-ID | Source | Day |
|---|------|------|--------|-----|
| N1 | CLARA Quality Gate Pipeline (5-stage) | F-150 | AI Technique Framework | Day 6 |
| N2 | Intent × Technique Mapping Table | F-149 | Feature Spec Batch 6 | Day 6 |
| N3 | Sentiment × Technique Trigger Mapping | F-151 | Feature Spec Batch 9 | Day 7 |
| N4 | `shared/knowledge_base/` Module | F-152 | INFRA GAPS TRACKER | Day 7 |
| N5 | RAG Re-Indexing Triggers | F-153 | Build Roadmap feedback loops | Day 7 |
| N6 | RAG Complexity Per Variant (3 tiers) | (F-064) | Phase 3 Variant Mapping Table | Day 7-8 |
| N7 | Brand Voice Config Per Company | F-154 | Build Roadmap v1 | Day 8 |
| N8 | Response Template Storage | F-155 | Build Roadmap v1 | Day 8 |
| N9 | Per-Conversation Token Budget | F-156 | Context Bible | Day 8 |
| N10 | ReAct Tool Integrations (4 tools) | F-157 | AI Technique Framework | Day 8 |
| N11 | Rule→AI Migration (F-049/F-050) | F-158 | WEEK4_ROADMAP | Day 8 |
| N12 | Multi-Instance Anti-Arbitrage | F-159 | Build Roadmap F-006 | Day 10 |
| N13 | Conversation Summarization Modes | F-160 | Context Bible | Day 10 |
| N14 | SG-34 Data Freshness (moved early) | SG-34 | Phase 3 Roadmap | Day 9 |
| N15 | SG-02 Technique Tier Access (moved early) | SG-02 | Phase 3 Roadmap | Day 9 |

### Week 9 Prerequisite Fixes (Day 0)

| # | Fix | Severity | Source |
|---|-----|----------|--------|
| P1 | Verify KB embeddings in pgvector | 🔴 CRITICAL | INFRA GAPS TRACKER |
| P2 | Build EmbeddingService if stub | 🔴 CRITICAL | Week 6 gap list |
| P3 | Fix 3 CRITICAL tenant isolation leaks | 🔴 CRITICAL | gap_analysis_agent1/2 JSON |
| P4 | Fix 8 HIGH model/service gaps | 🟡 HIGH | gap_analysis_agent1/2 JSON |
| P5 | Verify package compatibility | 🟡 HIGH | INFRA GAPS TRACKER DEP-04 |
| P6 | Standardize company_id usage | 🟡 HIGH | INFRA GAPS TRACKER DC2 |

### Week 9 Files to Create (~45 files)

| Category | Files |
|----------|-------|
| Core AI engines | `signal_extraction.py`, `classification_engine.py`, `sentiment_engine.py`, `rag_retrieval.py`, `rag_reranking.py`, `response_generator.py`, `clara_quality_gate.py`, `draft_composer.py`, `edge_case_handlers.py`, `conversation_summarizer.py` |
| Services | `intent_technique_mapper.py`, `sentiment_technique_mapper.py`, `brand_voice_service.py`, `response_template_service.py`, `token_budget_service.py`, `training_data_isolation.py`, `data_freshness_service.py` |
| Shared modules | `shared/knowledge_base/__init__.py`, `shared/knowledge_base/vector_search.py`, `shared/knowledge_base/reindexing.py` |
| ReAct tools | `react_tools/order_tool.py`, `react_tools/billing_tool.py`, `react_tools/crm_tool.py`, `react_tools/ticket_tool.py` |
| Cross-variant | `cross_variant_router.py`, `anti_arbitrage.py` |
| API endpoints | `api/classification.py`, `api/signals.py`, `api/rag.py`, `api/response.py`, `api/cross_variant.py` |
| Tests | 15+ test files |
| Migrations | 1 migration for new tables (brand_voice_configs, response_templates, technique_mappings, conversation_summaries) |

---

## 📁 KEY DOCUMENTS

| Document | Purpose |
|----------|---------|
| `docs/ONBOARDING_SPEC.md` | Full onboarding specification |
| `docs/WEEK6_ONBOARDING_PLAN.md` | Week 6 detailed plan |
| `docs/PARWA_Build_Roadmap_v1.md` | Full build roadmap (all weeks) |
| `PROJECT_STATE.md` | Current project state |

---

## 🔑 API KEYS (Available)

| Service | Status |
|---------|--------|
| Google AI | ✅ Available |
| Cerebras | ✅ Available |
| Groq | ✅ Available |
| Brevo | ✅ Available |
| Twilio | ✅ Available |
| Paddle | ✅ Available |

---

*This roadmap is a living document. Update as implementation progresses.*
