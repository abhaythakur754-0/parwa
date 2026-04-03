# PARWA Execution Roadmap

> **Last Updated:** Day 33 (Week 5 Complete)  
> **Current Phase:** Week 6 - Onboarding System

---

## 📊 PROJECT PROGRESS

| Week | Phase | Status | Description |
|------|-------|--------|-------------|
| **Week 1** | Foundation | ✅ COMPLETE | Project skeleton, database, config |
| **Week 2** | Auth System | ✅ COMPLETE | Registration, login, MFA, sessions |
| **Week 3** | Infrastructure | ✅ COMPLETE | Celery, Socket.io, webhooks, health |
| **Week 4** | Ticket System | ✅ COMPLETE | Tickets, customers, omnichannel |
| **Week 5** | Billing System | ✅ COMPLETE | Paddle, subscriptions, invoices |
| **Week 6** | Onboarding | 🔵 CURRENT | F-028 to F-035 + Frontend |
| **Week 7** | Approval System | ⬜ PLANNED | F-074 to F-086 |

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

### Week 6 Implementation Plan (8 Days)

---

#### Day 1: Database Schema + Post-Payment Details API

**Database Migrations:**
- [ ] `user_details` table
- [ ] `onboarding_state` table
- [ ] `consent_records` table
- [ ] `knowledge_documents` table
- [ ] `knowledge_chunks` table (with pgvector)

**Backend APIs:**
- [ ] `GET /api/onboarding/state` - Get onboarding state
- [ ] `POST /api/user/details` - Submit user details
- [ ] `POST /api/user/verify-work-email` - Verify work email

**Files to Build:**
```
database/migrations/009_onboarding_tables.sql
backend/app/models/onboarding.py
backend/app/schemas/onboarding.py
backend/app/api/user_details.py
```

**Tests:**
- [ ] Test: Tables created with correct columns
- [ ] Test: company_id on every table (BC-001)
- [ ] Test: API endpoints work correctly

---

#### Day 2: Post-Payment Details Frontend

**Frontend Components:**
- [ ] `frontend/src/app/welcome/details/page.tsx`
- [ ] `frontend/src/components/onboarding/DetailsForm.tsx`
- [ ] `frontend/src/components/onboarding/IndustrySelect.tsx`
- [ ] `frontend/src/components/onboarding/WorkEmailVerification.tsx`

**Files to Build:**
```
frontend/src/app/welcome/details/page.tsx
frontend/src/components/onboarding/DetailsForm.tsx
frontend/src/components/onboarding/IndustrySelect.tsx
frontend/src/components/onboarding/WorkEmailVerification.tsx
```

**Tests:**
- [ ] Test: Form renders correctly
- [ ] Test: Validation works
- [ ] Test: Submit calls API

---

#### Day 3: Onboarding Wizard Backend (F-028, F-029)

**Backend APIs:**
- [ ] `POST /api/onboarding/start` - Initialize wizard
- [ ] `POST /api/onboarding/legal` - Save legal consents
- [ ] `POST /api/onboarding/step/{n}` - Complete step

**Services:**
- [ ] `OnboardingService` - State machine management
- [ ] `ConsentService` - Legal consent handling

**Files to Build:**
```
backend/app/api/onboarding.py
backend/app/services/onboarding_service.py
backend/app/services/consent_service.py
```

**Tests:**
- [ ] Test: State machine transitions correctly
- [ ] Test: Consents stored with timestamps
- [ ] Test: BC-010 compliance (GDPR)

---

#### Day 4: Onboarding Wizard Frontend (F-028, F-029)

**Frontend Components:**
- [ ] `frontend/src/app/onboarding/page.tsx`
- [ ] `frontend/src/components/onboarding/OnboardingWizard.tsx`
- [ ] `frontend/src/components/onboarding/ProgressIndicator.tsx`
- [ ] `frontend/src/components/onboarding/WelcomeScreen.tsx`
- [ ] `frontend/src/components/onboarding/LegalCompliance.tsx`

**Files to Build:**
```
frontend/src/app/onboarding/page.tsx
frontend/src/components/onboarding/OnboardingWizard.tsx
frontend/src/components/onboarding/ProgressIndicator.tsx
frontend/src/components/onboarding/WelcomeScreen.tsx
frontend/src/components/onboarding/LegalCompliance.tsx
```

**Tests:**
- [ ] Test: Wizard renders all steps
- [ ] Test: Progress indicator updates
- [ ] Test: Legal checkboxes required

---

#### Day 5: Integration Setup (F-030, F-031)

**Backend APIs:**
- [ ] `GET /api/integrations/available` - List available integrations
- [ ] `POST /api/integrations` - Create integration
- [ ] `POST /api/integrations/:id/test` - Test connection

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

---

#### Day 6: Knowledge Base Upload (F-032)

**Backend APIs:**
- [ ] `POST /api/knowledge/upload` - Upload document
- [ ] `GET /api/knowledge` - List documents
- [ ] `DELETE /api/knowledge/:id` - Delete document

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
- [ ] Test: File list displays correctly

---

#### Day 7: KB Processing + AI Activation (F-033, F-034)

**Backend:**
- [ ] Text extraction from documents
- [ ] Chunking logic
- [ ] Vector embedding generation (pgvector)
- [ ] `POST /api/onboarding/activate` - Activate AI
- [ ] Prerequisites validation

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

---

#### Day 8: First Victory + Testing (F-035)

**Backend:**
- [ ] `GET /api/onboarding/first-victory` - Get first victory status
- [ ] First victory event tracking
- [ ] Celebration event emission (Socket.io)

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
backend/app/api/first_victory.py
backend/app/services/victory_service.py
frontend/src/components/onboarding/FirstVictory.tsx
tests/unit/test_onboarding.py
tests/integration/test_onboarding_flow.py
```

---

### Week 6 Summary

| Metric | Count |
|--------|-------|
| Days | 8 |
| Backend APIs | 18 |
| Frontend Components | 19 |
| DB Tables | 5 |
| Celery Tasks | 2 |

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
