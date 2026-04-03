# PARWA Week 6 - Onboarding System Implementation Plan

> **Document Version:** 1.1  
> **Created:** Day 33 (Week 5)  
> **Scope:** WEEK 6 ONLY - Onboarding System (F-028 to F-035) + Frontend + Backend

---

## Scope Definition

### ✅ What We ARE Building (Week 6):

| Feature ID | Feature Name | Backend | Frontend |
|------------|--------------|---------|----------|
| **F-028** | Onboarding Wizard | State machine API | 5-step wizard UI |
| **F-029** | Legal Consent Collection | Consent storage | Checkboxes UI |
| **F-030** | Pre-built Integration Setup | OAuth flows | Integration cards |
| **F-031** | Custom Integration Builder | API config storage | Builder form |
| **F-032** | KB Document Upload | File upload API | Drag-drop UI |
| **F-033** | KB Processing + Indexing | Vector embedding | Progress UI |
| **F-034** | AI Activation Gate | Validation API | Activation UI |
| **F-035** | First Victory Celebration | Event tracking | Celebration UI |
| **NEW** | Post-Payment Details | Details API | Form UI |

### ❌ What We Are NOT Building (Separate Weeks):

- Landing Page (F-001) → Week 18
- Pricing Page (F-004) → Week 18
- ROI Calculator (F-007) → Week 18
- Demo Chat Widget (F-003) → Week 11-12
- Demo Voice Call (F-008) → Week 11-12

---

## User Flow (Week 6 Scope Only)

```
PAYMENT SUCCESS (from Paddle)
         │
         ▼
┌─────────────────────────┐
│  POST-PAYMENT DETAILS   │  ◄── NEW (discussed)
│  - Full Name            │
│  - Company Name         │
│  - Work Email           │
│  - Industry             │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  ONBOARDING WIZARD      │  ◄── F-028
│  Step 1: Welcome        │
│  Step 2: Legal (F-029)  │
│  Step 3: Integrations   │
│         (F-030, F-031)  │
│  Step 4: KB (F-032,33)  │
│  Step 5: AI (F-034)     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  FIRST VICTORY          │  ◄── F-035
│  - Test ticket resolved │
│  - Celebration UI       │
└───────────┬─────────────┘
            │
            ▼
        DASHBOARD
```

---

## Implementation Plan (8 Days)

### Day 1: Database Schema + Post-Payment Details API

**Database Migrations:**
- [ ] `user_details` table
- [ ] `onboarding_state` table
- [ ] `consent_records` table
- [ ] `knowledge_documents` table
- [ ] `knowledge_chunks` table

**Backend APIs:**
- [ ] `GET /api/onboarding/state` - Get current state
- [ ] `POST /api/user/details` - Submit user details
- [ ] `POST /api/user/verify-work-email` - Verify work email

**Files:**
```
backend/app/models/onboarding.py
backend/app/schemas/onboarding.py
backend/app/api/user_details.py
database/migrations/009_onboarding_tables.sql
```

---

### Day 2: Post-Payment Details Frontend

**Frontend:**
- [ ] `frontend/src/app/welcome/details/page.tsx`
- [ ] `frontend/src/components/onboarding/DetailsForm.tsx`
- [ ] `frontend/src/components/onboarding/IndustrySelect.tsx`
- [ ] `frontend/src/components/onboarding/WorkEmailVerification.tsx`

**Files:**
```
frontend/src/app/welcome/details/page.tsx
frontend/src/components/onboarding/DetailsForm.tsx
frontend/src/components/onboarding/IndustrySelect.tsx
frontend/src/components/onboarding/WorkEmailVerification.tsx
```

---

### Day 3: Onboarding Wizard Backend (F-028, F-029)

**Backend APIs:**
- [ ] `POST /api/onboarding/start` - Initialize wizard
- [ ] `GET /api/onboarding/state` - Get current step
- [ ] `POST /api/onboarding/legal` - Save legal consents
- [ ] `POST /api/onboarding/step/{n}` - Complete step

**Services:**
- [ ] `OnboardingService` - State machine management
- [ ] `ConsentService` - Legal consent handling

**Files:**
```
backend/app/api/onboarding.py
backend/app/services/onboarding_service.py
backend/app/services/consent_service.py
```

---

### Day 4: Onboarding Wizard Frontend (F-028, F-029)

**Frontend:**
- [ ] `frontend/src/app/onboarding/page.tsx`
- [ ] `frontend/src/components/onboarding/OnboardingWizard.tsx`
- [ ] `frontend/src/components/onboarding/ProgressIndicator.tsx`
- [ ] `frontend/src/components/onboarding/WelcomeScreen.tsx`
- [ ] `frontend/src/components/onboarding/LegalCompliance.tsx`

**Files:**
```
frontend/src/app/onboarding/page.tsx
frontend/src/components/onboarding/OnboardingWizard.tsx
frontend/src/components/onboarding/ProgressIndicator.tsx
frontend/src/components/onboarding/WelcomeScreen.tsx
frontend/src/components/onboarding/LegalCompliance.tsx
```

---

### Day 5: Integration Setup (F-030, F-031)

**Backend APIs:**
- [ ] `GET /api/integrations/available` - List available integrations
- [ ] `POST /api/integrations` - Create integration
- [ ] `POST /api/integrations/:id/test` - Test connection
- [ ] OAuth callback handlers

**Frontend:**
- [ ] `frontend/src/components/onboarding/IntegrationSetup.tsx`
- [ ] `frontend/src/components/onboarding/IntegrationCard.tsx`
- [ ] `frontend/src/components/onboarding/CustomIntegrationBuilder.tsx`

**Files:**
```
backend/app/api/integrations.py
backend/app/services/integration_service.py
frontend/src/components/onboarding/IntegrationSetup.tsx
frontend/src/components/onboarding/IntegrationCard.tsx
frontend/src/components/onboarding/CustomIntegrationBuilder.tsx
```

---

### Day 6: Knowledge Base Upload (F-032)

**Backend APIs:**
- [ ] `POST /api/knowledge/upload` - Upload document
- [ ] `GET /api/knowledge` - List documents
- [ ] `DELETE /api/knowledge/:id` - Delete document

**Frontend:**
- [ ] `frontend/src/components/onboarding/KnowledgeUpload.tsx`
- [ ] `frontend/src/components/onboarding/FileDropZone.tsx`
- [ ] `frontend/src/components/onboarding/FileList.tsx`

**Files:**
```
backend/app/api/knowledge.py
backend/app/services/knowledge_service.py
frontend/src/components/onboarding/KnowledgeUpload.tsx
frontend/src/components/onboarding/FileDropZone.tsx
frontend/src/components/onboarding/FileList.tsx
```

---

### Day 7: KB Processing + AI Activation (F-033, F-034)

**Backend:**
- [ ] Text extraction from documents
- [ ] Chunking logic
- [ ] Vector embedding generation (pgvector)
- [ ] `POST /api/onboarding/activate` - Activate AI
- [ ] Prerequisites validation

**Celery Tasks:**
- [ ] `process_knowledge_document` task
- [ ] `generate_embeddings` task

**Frontend:**
- [ ] `frontend/src/components/onboarding/ProcessingStatus.tsx`
- [ ] `frontend/src/components/onboarding/AIConfig.tsx`
- [ ] `frontend/src/components/onboarding/ActivationButton.tsx`

**Files:**
```
backend/app/services/embedding_service.py
backend/app/tasks/knowledge_tasks.py
frontend/src/components/onboarding/ProcessingStatus.tsx
frontend/src/components/onboarding/AIConfig.tsx
frontend/src/components/onboarding/ActivationButton.tsx
```

---

### Day 8: First Victory + Testing (F-035)

**Backend:**
- [ ] `GET /api/onboarding/first-victory` - Get first victory status
- [ ] First victory event tracking
- [ ] Celebration event emission

**Frontend:**
- [ ] `frontend/src/components/onboarding/FirstVictory.tsx`
- [ ] Celebration animation/confetti
- [ ] Redirect to dashboard

**Testing:**
- [ ] End-to-end test: Payment → Details → Onboarding → Victory
- [ ] Unit tests for all services
- [ ] Integration tests for all APIs

**Files:**
```
backend/app/api/first_victory.py
backend/app/services/victory_service.py
frontend/src/components/onboarding/FirstVictory.tsx
tests/unit/test_onboarding.py
tests/integration/test_onboarding_flow.py
```

---

## Summary

| Day | Focus | Backend | Frontend |
|-----|-------|---------|----------|
| 1 | DB + Post-Payment API | 3 APIs | 0 |
| 2 | Post-Payment UI | 0 | 4 components |
| 3 | Wizard Backend | 4 APIs | 0 |
| 4 | Wizard Frontend | 0 | 5 components |
| 5 | Integrations | 4 APIs | 3 components |
| 6 | KB Upload | 3 APIs | 3 components |
| 7 | KB Processing + AI | 2 APIs + Tasks | 3 components |
| 8 | First Victory + Tests | 2 APIs | 1 component |
| **Total** | **8 Days** | **18 APIs** | **19 Components** |

---

## Database Tables

### `user_details`
```sql
CREATE TABLE user_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    work_email VARCHAR(255),
    work_email_verified BOOLEAN DEFAULT FALSE,
    industry VARCHAR(50) NOT NULL,
    company_size VARCHAR(20),
    website VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `onboarding_state`
```sql
CREATE TABLE onboarding_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) UNIQUE NOT NULL,
    company_id UUID REFERENCES companies(id) NOT NULL,
    current_step INTEGER DEFAULT 1,
    legal_accepted BOOLEAN DEFAULT FALSE,
    terms_accepted_at TIMESTAMPTZ,
    privacy_accepted_at TIMESTAMPTZ,
    ai_data_accepted_at TIMESTAMPTZ,
    integrations JSONB DEFAULT '{}',
    knowledge_base_files JSONB DEFAULT '[]',
    ai_name VARCHAR(50) DEFAULT 'Jarvis',
    ai_tone VARCHAR(20) DEFAULT 'professional',
    ai_response_style VARCHAR(20) DEFAULT 'concise',
    ai_greeting TEXT,
    first_victory_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `consent_records`
```sql
CREATE TABLE consent_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) NOT NULL,
    user_id UUID REFERENCES users(id) NOT NULL,
    consent_type VARCHAR(50) NOT NULL,  -- 'tcpa', 'gdpr', 'call_recording'
    consented BOOLEAN DEFAULT FALSE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    consented_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `knowledge_documents`
```sql
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    file_size INTEGER NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, indexed, failed
    chunk_count INTEGER DEFAULT 0,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `knowledge_chunks`
```sql
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES knowledge_documents(id) NOT NULL,
    company_id UUID REFERENCES companies(id) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),  -- OpenAI embedding dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_knowledge_chunks_embedding ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops);
```

---

## API Endpoints Summary

### Post-Payment Details
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/onboarding/state` | Get onboarding state |
| POST | `/api/user/details` | Submit user details |
| POST | `/api/user/verify-work-email` | Verify work email |

### Onboarding Wizard
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/onboarding/start` | Initialize wizard |
| POST | `/api/onboarding/legal` | Save legal consents |
| POST | `/api/onboarding/step/{n}` | Complete step n |
| POST | `/api/onboarding/activate` | Activate AI |

### Integrations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/integrations/available` | List available integrations |
| POST | `/api/integrations` | Create integration |
| POST | `/api/integrations/:id/test` | Test connection |

### Knowledge Base
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/knowledge/upload` | Upload document |
| GET | `/api/knowledge` | List documents |
| DELETE | `/api/knowledge/:id` | Delete document |

### First Victory
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/onboarding/first-victory` | Get first victory status |

---

## File Structure

```
backend/app/
├── api/
│   ├── onboarding.py          # Wizard + Victory APIs
│   ├── user_details.py        # Post-payment APIs
│   ├── integrations.py        # Integration APIs
│   └── knowledge.py           # KB APIs
├── models/
│   └── onboarding.py          # SQLAlchemy models
├── schemas/
│   └── onboarding.py          # Pydantic schemas
├── services/
│   ├── onboarding_service.py  # State machine
│   ├── consent_service.py     # Consent handling
│   ├── integration_service.py # Integration logic
│   ├── knowledge_service.py   # File handling
│   └── embedding_service.py   # Vector embeddings
└── tasks/
    └── knowledge_tasks.py     # Celery tasks

frontend/src/
├── app/
│   ├── welcome/
│   │   └── details/page.tsx   # Post-payment form
│   └── onboarding/page.tsx    # Wizard page
└── components/
    └── onboarding/
        ├── DetailsForm.tsx
        ├── IndustrySelect.tsx
        ├── WorkEmailVerification.tsx
        ├── OnboardingWizard.tsx
        ├── ProgressIndicator.tsx
        ├── WelcomeScreen.tsx
        ├── LegalCompliance.tsx
        ├── IntegrationSetup.tsx
        ├── IntegrationCard.tsx
        ├── CustomIntegrationBuilder.tsx
        ├── KnowledgeUpload.tsx
        ├── FileDropZone.tsx
        ├── FileList.tsx
        ├── ProcessingStatus.tsx
        ├── AIConfig.tsx
        ├── ActivationButton.tsx
        └── FirstVictory.tsx
```

---

## API Keys (Provided)

| Service | Key | Usage |
|---------|-----|-------|
| Google AI | `YOUR_GOOGLE_AI_KEY` | AI responses |
| Cerebras | `YOUR_CEREBRAS_KEY` | AI responses |
| Groq | `YOUR_GROQ_KEY` | AI responses |
| Brevo | `YOUR_BREVO_KEY` | Emails |
| Twilio SID | `YOUR_TWILIO_SID` | SMS/Voice |
| Twilio Token | `YOUR_TWILIO_TOKEN` | SMS/Voice |
| Twilio API Key | `YOUR_TWILIO_API_KEY` | SMS/Voice |
| Paddle Client | `YOUR_PADDLE_CLIENT` | Payments |
| Paddle API | `YOUR_PADDLE_API_KEY` | Payments |

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Day 33 | Initial plan (too broad) |
| 1.1 | Day 33 | Focused to Week 6 only (F-028 to F-035) |

---

*This is the CORRECTED plan focusing ONLY on Week 6 Onboarding System.*
