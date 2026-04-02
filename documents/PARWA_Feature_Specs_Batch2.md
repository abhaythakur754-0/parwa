# PARWA Feature Specs — Batch 2: Tickets/Approvals

> **AI-Powered Customer Support Platform**
>
> This document contains detailed engineering specifications for 9 critical features spanning knowledge base processing, AI activation, ticket management, approval workflows, and emergency controls. Each spec includes frontend components, backend APIs, database schemas, building code compliance, edge cases, and acceptance criteria ready for AI coding agent implementation.
>
> **Tech Stack:** Next.js (Frontend) · FastAPI (Backend) · PostgreSQL (Database) · Redis (Cache) · Celery (Background Jobs) · Socket.io (Real-Time) · Paddle (Payments) · Brevo (Email)
>
> **Dependencies:** PARWA Building Codes v1.0 (BC-001 through BC-012) · PARWA Feature Catalog v1.0

---

## Table of Contents

1. [F-033: Knowledge Base Processing & Indexing](#f-033-knowledge-base-processing--indexing)
2. [F-034: AI Activation System](#f-034-ai-activation-system)
3. [F-046: Ticket List (Filterable, Sortable)](#f-046-ticket-list-filterable-sortable)
4. [F-047: Ticket Detail Modal (Full Conversation)](#f-047-ticket-detail-modal-full-conversation)
5. [F-074: Approval Queue Dashboard](#f-074-approval-queue-dashboard)
6. [F-076: Individual Ticket Approval/Reject](#f-076-individual-ticket-approvalreject)
7. [F-078: Auto-Approve Confirmation Flow](#f-078-auto-approve-confirmation-flow)
8. [F-080: Urgent Attention Panel (VIP/Legal)](#f-080-urgent-attention-panel-viplegal)
9. [F-083: Emergency Pause Controls](#f-083-emergency-pause-controls)

---

# F-033: Knowledge Base Processing & Indexing

## Overview
This feature implements the background Celery pipeline responsible for ingesting uploaded knowledge base documents, extracting raw text, splitting it into semantic chunks, generating vector embeddings via the Smart Router, and storing results in a tenant-isolated vector index. It is the heaviest background operation in the onboarding flow and directly gates AI Activation (F-034). Without reliable processing, the AI agent has no knowledge base to ground its responses.

## User Journey
1. User uploads documents via the Knowledge Base Document Upload UI (F-032).
2. The upload endpoint creates `knowledge_base_documents` rows with status `uploaded` and dispatches a Celery task per document.
3. The Celery pipeline runs 4 stages sequentially: **extract** → **chunk** → **embed** → **index**.
4. Frontend polls `GET /api/kb/status` (or receives Socket.io events) showing per-document progress: "Extracting text...", "Chunking into 23 segments...", "Generating embeddings...", "Indexing complete."
5. On failure, the document status becomes `failed` with an error message, and the user can click "Retry" to re-queue.
6. When all documents reach `indexed`, the onboarding wizard enables the "Activate AI" step.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| KBProgressBar | `src/components/onboarding/KBProgressBar.tsx` | Per-document progress bar with stage labels and percentage |
| KBStatusList | `src/components/onboarding/KBStatusList.tsx` | List of all uploaded documents with status badges (uploaded/processing/indexed/failed) |
| KBErrorToast | `src/components/onboarding/KBErrorToast.tsx` | Toast notification on processing failure with retry button |
| OnboardingStep4 | `src/pages/onboarding/Step4KnowledgeBase.tsx` | Wrapper step that combines upload and status views |

## Backend APIs

### `POST /api/kb/upload`
- **Auth:** JWT (tenant-scoped)
- **Request:** `multipart/form-data` with field `files[]` (PDF, DOCX, TXT, MD, HTML, CSV), max 50MB per file, max 20 files per batch.
- **Response 200:**
```json
{
  "documents": [
    {"id": "doc_abc123", "filename": "product-guide.pdf", "size_bytes": 2400000, "status": "uploaded"},
    {"id": "doc_def456", "filename": "faq.md", "size_bytes": 45000, "status": "uploaded"}
  ],
  "total_queued": 2
}
```
- **Error 413:** File exceeds 50MB limit.
- **Error 400:** Unsupported file type.
- **Error 401:** Missing/invalid JWT.

### `GET /api/kb/status`
- **Auth:** JWT
- **Query Params:** none
- **Response 200:**
```json
{
  "documents": [
    {"id": "doc_abc123", "filename": "product-guide.pdf", "status": "indexed", "chunks_count": 47, "progress_pct": 100},
    {"id": "doc_def456", "filename": "faq.md", "status": "chunking", "chunks_count": 0, "progress_pct": 40, "error": null}
  ],
  "overall_status": "processing",
  "total_documents": 2,
  "indexed_documents": 1
}
```

### `POST /api/kb/retry/{document_id}`
- **Auth:** JWT
- **Response 200:** `{"id": "doc_def456", "status": "queued", "message": "Re-queued for processing"}`
- **Error 404:** Document not found or cross-tenant.
- **Error 400:** Document not in `failed` state.

### Celery Task: `process_kb_document(self, company_id, document_id)`
- **Queue:** `kb_processing`
- **Timeout:** `soft_time_limit=600`, `time_limit=660` (10 minutes for large docs)
- **Pipeline Stages:**
  1. **Extract:** Uses `unstructured` library to extract text. Updates status to `extracting`.
  2. **Chunk:** Splits text into 512-token chunks with 64-token overlap. Updates status to `chunking`.
  3. **Embed:** Sends chunks to Smart Router (Light tier) for embedding generation. Updates status to `embedding`.
  4. **Index:** Stores chunks + embeddings in `knowledge_base_chunks` table. Updates status to `indexed`.

## Database Tables

### `knowledge_base_documents`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id |
| filename | VARCHAR(512) | NOT NULL |
| file_type | VARCHAR(20) | NOT NULL (pdf/docx/txt/md/html/csv) |
| file_size_bytes | INTEGER | NOT NULL |
| storage_path | VARCHAR(1024) | NOT NULL |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'uploaded', CHECK (status IN ('uploaded','extracting','chunking','embedding','indexed','failed')) |
| progress_pct | INTEGER | NOT NULL, DEFAULT 0 |
| chunks_count | INTEGER | NOT NULL, DEFAULT 0 |
| error_message | TEXT | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(company_id)`, `(company_id, status)`, `(id, company_id)` |

### `knowledge_base_chunks`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| document_id | UUID | NOT NULL, FK → knowledge_base_documents.id ON DELETE CASCADE |
| company_id | UUID | NOT NULL, FK → companies.id |
| chunk_index | INTEGER | NOT NULL |
| content_text | TEXT | NOT NULL |
| embedding | VECTOR(1536) | NOT NULL (pgvector extension) |
| token_count | INTEGER | NOT NULL |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(company_id)`, `(document_id)`, `(company_id, document_id)`, vector index: `ivfflat` on `embedding` with `lists = 100` |

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 2, 7, 8 — All queries scoped by `company_id`, Celery task receives `company_id` as first param, Redis keys namespaced with `company_id`, indexes on `company_id`.
- **BC-004 (Background Jobs):** Rules 1, 2, 3, 4, 5, 10 — `company_id` first param, `max_retries=3` with exponential backoff, 600s timeout, DLQ routing, task_logs recording.
- **BC-007 (AI Model Interaction):** Rules 3, 5 — Smart Router Light tier used for embeddings with 429 fallback; PII redaction on extracted text before embedding.
- **BC-012 (Error Handling & Resilience):** All rules — Each pipeline stage has try/catch, status rolled back on failure, user-visible error messages.

## Edge Cases
1. **Corrupted PDF:** `unstructured` library raises exception during extraction. Pipeline catches it, marks document as `failed` with error "Unable to extract text from PDF. The file may be corrupted or password-protected."
2. **Oversized document (>50MB):** Rejected at upload with 413. User sees "File 'manual.pdf' exceeds the 50MB limit. Please split into smaller files."
3. **Zero-text extraction:** Document is an image-only PDF. Pipeline marks as `failed` with "No text content found. OCR is not yet supported."
4. **Embedding API rate-limited:** Smart Router falls through to next model (BC-007 Rule 3). If all models rate-limited, task retries with exponential backoff.
5. **Duplicate document upload:** System checks SHA-256 hash of file content against existing documents for the same tenant. If duplicate found, warns user but allows re-upload (user may want updated version).
6. **Celery worker crash mid-pipeline:** Document status remains at current stage. On retry, pipeline resumes from the failed stage (chunks already created are not re-created; embedding skips already-embedded chunks).

## Acceptance Criteria
1. **AC-1:** Uploading a valid PDF creates a `knowledge_base_documents` row with status `uploaded` and dispatches a Celery task within 2 seconds.
2. **AC-2:** The pipeline progresses through all 4 stages (extract → chunk → embed → index) and the document reaches status `indexed` with accurate `chunks_count`.
3. **AC-3:** A corrupted PDF is marked as `failed` with a descriptive error message within the `GET /api/kb/status` response.
4. **AC-4:** Clicking "Retry" on a failed document re-queues it and the pipeline runs again from the failed stage, not from scratch.
5. **AC-5:** All `knowledge_base_chunks` rows have the correct `company_id` matching the uploading tenant. Cross-tenant vector search returns zero results.
6. **AC-6:** If the embedding API returns 429 for all models, the task retries up to 3 times with exponential backoff (2s, 4s, 8s) before routing to DLQ.
7. **AC-7:** The `GET /api/kb/status` endpoint returns results scoped to the authenticated tenant only — a different tenant's documents are never visible.

---

# F-034: AI Activation System

## Overview
This feature is the final gate in the onboarding wizard. It validates that all prerequisites are met (legal consent collected, at least one integration active, knowledge base indexed with minimum chunk count), then activates the tenant's AI agent by configuring the Smart Router, initializing GSD state engine settings, and enabling live ticket processing. Once activated, the tenant begins their 30-day AI adaptation period.

## User Journey
1. User reaches Step 5 of the onboarding wizard. The system runs a readiness check against 3 prerequisites.
2. If all prerequisites pass, the user sees a green "Ready to Activate" panel with a summary card: "Consent: Collected | Integration: Zendesk (Active) | Knowledge Base: 47 articles indexed".
3. If prerequisites are missing, the user sees red warnings with "Go Back" links to the incomplete steps.
4. User clicks "Activate AI Agent". A confirmation modal shows: "Your AI agent will start handling support tickets. You can pause it anytime from the dashboard."
5. On confirmation, the backend activates the tenant, sets `ai_active = true`, initializes confidence thresholds to defaults, starts the adaptation day counter, and triggers a welcome email via Brevo.
6. User is redirected to the Dashboard Home (F-036) with a "First Victory" tracker visible.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| ActivationGate | `src/components/onboarding/ActivationGate.tsx` | Readiness check panel showing pass/fail for each prerequisite |
| ActivationSummary | `src/components/onboarding/ActivationSummary.tsx` | Summary card with consent status, active integrations, KB article count |
| ActivationConfirmModal | `src/components/onboarding/ActivationConfirmModal.tsx` | Confirmation dialog before activation |
| OnboardingStep5 | `src/pages/onboarding/Step5Activation.tsx` | Final onboarding step wrapper |

## Backend APIs

### `GET /api/onboarding/readiness`
- **Auth:** JWT
- **Response 200:**
```json
{
  "ready": true,
  "prerequisites": {
    "legal_consent": {"met": true, "detail": "TCPA, GDPR, and Call Recording consent collected on 2026-03-15"},
    "integration_active": {"met": true, "detail": "Zendesk integration active (synced 2 min ago)"},
    "knowledge_base_indexed": {"met": true, "detail": "47 articles indexed across 3 documents"}
  },
  "warnings": []
}
```
- **Response 200 (not ready):**
```json
{
  "ready": false,
  "prerequisites": {
    "legal_consent": {"met": true, "detail": "TCPA, GDPR, and Call Recording consent collected on 2026-03-15"},
    "integration_active": {"met": false, "detail": "No integration configured"},
    "knowledge_base_indexed": {"met": false, "detail": "0 articles indexed. Upload and process documents first."}
  },
  "warnings": [
    {"step": 3, "message": "At least one integration must be active before AI activation."},
    {"step": 4, "message": "Knowledge base must have at least 1 indexed article."}
  ]
}
```

### `POST /api/onboarding/activate`
- **Auth:** JWT (requires admin or owner role)
- **Request Body:** `{ "confirmed": true }`
- **Response 200:**
```json
{
  "status": "activated",
  "company": {
    "id": "comp_abc",
    "ai_active": true,
    "adaptation_day": 1,
    "confidence_thresholds": {
      "refund": 85,
      "subscription_change": 80,
      "response_send": 75,
      "escalation": 60
    },
    "activated_at": "2026-03-15T14:30:00Z"
  }
}
```
- **Error 400:** `"confirmed" must be true.` or `Prerequisites not met. Complete steps 3 and 4 first.`
- **Error 403:** User does not have admin/owner role.

### Celery Task: `send_activation_email(self, company_id, user_id)`
- Dispatched after successful activation.
- Uses Brevo template `TPL-007` (AI Activation Welcome).
- Logs to `email_logs` table.

## Database Tables

### `companies` (columns affected by this feature)
| Column | Type | Notes |
|--------|------|-------|
| ai_active | BOOLEAN | NOT NULL, DEFAULT false. Set to `true` on activation. |
| adaptation_start_date | DATE | NULL. Set to `CURRENT_DATE` on activation. |
| activated_at | TIMESTAMPTZ | NULL. Set to `now()` on activation. |
| default_confidence_thresholds | JSONB | DEFAULT `'{"refund": 85, "subscription_change": 80, "response_send": 75, "escalation": 60}'` |

### `onboarding_progress`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id, UNIQUE |
| step_legal_consent | BOOLEAN | NOT NULL, DEFAULT false |
| step_integration | BOOLEAN | NOT NULL, DEFAULT false |
| step_knowledge_base | BOOLEAN | NOT NULL, DEFAULT false |
| step_ai_activation | BOOLEAN | NOT NULL, DEFAULT false |
| completed_at | TIMESTAMPTZ | NULL |
| **Indexes:** | | `(company_id)` |

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 8 — All queries scoped by `company_id`, indexes on `company_id`.
- **BC-006 (Email Communication):** Rules 4, 5 — Activation email uses Brevo template `TPL-007`, logged in `email_logs`.
- **BC-007 (AI Model Interaction):** Rule 9 — Confidence thresholds stored in `default_confidence_thresholds` JSONB per company, not hardcoded.
- **BC-008 (State Management):** Rule 1 — GSD engine settings initialized with dual Redis/Postgres storage on activation.
- **BC-011 (Authentication & Security):** Rules applied — Only admin/owner role can activate; activation requires JWT auth.
- **BC-012 (Error Handling & Resilience):** Activation wrapped in atomic DB transaction; if email send fails, activation still succeeds (non-blocking).

## Edge Cases
1. **Double activation:** If `POST /api/onboarding/activate` is called twice, the second call returns 200 with current state (idempotent). No duplicate emails sent.
2. **Activation with 0 KB articles:** The readiness check requires at least 1 indexed chunk. If KB was cleared between readiness check and activation, the activation fails atomically.
3. **User role change mid-onboarding:** If admin is demoted to agent after starting onboarding but before activation, `POST /activate` returns 403.
4. **Integration goes inactive between readiness and activation:** Readiness check passes, but by the time user clicks activate, integration is disabled. Activation still succeeds (integration is not re-checked at activation time — readiness snapshot is used).
5. **Brevo email send failure:** Activation completes successfully. Email failure is logged but does not block activation. A Celery retry handles the email.

## Acceptance Criteria
1. **AC-1:** `GET /api/onboarding/readiness` returns `ready: false` when knowledge base has 0 indexed articles, with a warning pointing to Step 4.
2. **AC-2:** `GET /api/onboarding/readiness` returns `ready: true` when all 3 prerequisites are met.
3. **AC-3:** `POST /api/onboarding/activate` with `confirmed: true` sets `companies.ai_active = true` and `adaptation_start_date = CURRENT_DATE`.
4. **AC-4:** After activation, default confidence thresholds are stored in `companies.default_confidence_thresholds` as JSONB.
5. **AC-5:** A non-admin user calling `POST /api/onboarding/activate` receives HTTP 403.
6. **AC-6:** Brevo welcome email is sent within 30 seconds of successful activation and logged in `email_logs` with template `TPL-007`.
7. **AC-7:** Calling `POST /api/onboarding/activate` on an already-active tenant returns 200 without side effects (idempotent).

---

# F-046: Ticket List (Filterable, Sortable)

## Overview
This is the primary ticket management view — the most-used screen in the PARWA platform. It presents a paginated, multi-column data table of all support tickets belonging to the authenticated tenant, with real-time filtering by status, channel, assignee, priority, and date range, plus column sorting, row hover preview, and quick-action buttons. Performance is critical as this view loads frequently and must handle thousands of tickets with sub-second response times.

## User Journey
1. User navigates to `/tickets` from the main navigation. The Ticket List loads with default filters (all open tickets, sorted by newest first, 25 per page).
2. User clicks the "Status" filter dropdown and selects "Awaiting Approval". The list re-renders showing only tickets in that status.
3. User clicks the "Channel" filter and toggles "Email" and "Chat". The list narrows to email and chat tickets.
4. User clicks the "Created At" column header to sort ascending (oldest first). Clicking again sorts descending.
5. User hovers over a ticket row and sees a quick-preview tooltip showing the first 150 characters of the latest message.
6. User clicks a ticket row to open the Ticket Detail Modal (F-047).
7. New tickets arrive via Socket.io and appear at the top of the list with a brief highlight animation.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| TicketListPage | `src/pages/tickets/index.tsx` | Main ticket list page with filter bar, table, and pagination |
| TicketFilterBar | `src/components/tickets/TicketFilterBar.tsx` | Horizontal filter strip with dropdowns: Status, Channel, Assignee, Priority, Date Range |
| TicketTable | `src/components/tickets/TicketTable.tsx` | React Table (TanStack Table) with sortable columns, row selection checkboxes, and hover preview |
| TicketRowPreview | `src/components/tickets/TicketRowPreview.tsx` | Tooltip/ popover showing ticket summary on row hover |
| TicketPagination | `src/components/tickets/TicketPagination.tsx` | Page navigation with page size selector (25/50/100) |
| TicketStatusBadge | `src/components/tickets/TicketStatusBadge.tsx` | Color-coded badge: open (blue), in_progress (yellow), awaiting_approval (orange), resolved (green), closed (gray) |

## Backend APIs

### `GET /api/tickets`
- **Auth:** JWT
- **Query Params:**
  - `status` (optional, comma-separated): `open,in_progress,awaiting_approval,resolved,closed`
  - `channel` (optional, comma-separated): `email,chat,sms,voice,social`
  - `assignee_id` (optional, UUID): Filter by assigned agent/user
  - `priority` (optional): `low,medium,high,urgent`
  - `date_from` (optional, ISO 8601): Start of date range
  - `date_to` (optional, ISO 8601): End of date range
  - `search` (optional, string): Full-text search across subject and latest message
  - `sort_by` (optional, default `created_at`): Column to sort by
  - `sort_order` (optional, default `desc`): `asc` or `desc`
  - `page` (optional, default `1`): Page number
  - `page_size` (optional, default `25`): Items per page (max 100)
- **Response 200:**
```json
{
  "tickets": [
    {
      "id": "tkt_001",
      "subject": "Refund request for order #12345",
      "status": "awaiting_approval",
      "channel": "email",
      "priority": "high",
      "customer_name": "Jane Doe",
      "customer_email": "j***@example.com",
      "assignee": {"id": "usr_abc", "name": "AI Agent - Billing", "type": "ai"},
      "latest_message_preview": "I would like a full refund for my recent order...",
      "created_at": "2026-03-15T10:30:00Z",
      "updated_at": "2026-03-15T11:45:00Z",
      "confidence_score": 87,
      "is_vip": false,
      "message_count": 3
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total_items": 142,
    "total_pages": 6
  },
  "filters_applied": {
    "status": ["awaiting_approval"],
    "channel": null,
    "assignee_id": null,
    "priority": null,
    "date_from": null,
    "date_to": null
  }
}
```
- **Error 401:** Missing/invalid JWT.
- **Error 422:** Invalid query parameter (e.g., `sort_order=invalid`).

### Socket.io Events (Room: `tenant_{company_id}`)
- **Event: `ticket:new`** — Emitted when a new ticket is created. Payload: `{ ticket_id, subject, status, channel, customer_name, created_at }`
- **Event: `ticket:updated`** — Emitted when ticket status/assignee changes. Payload: `{ ticket_id, field, old_value, new_value }`

## Database Tables

### `tickets` (read-only for this feature)
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id |
| subject | VARCHAR(512) | NOT NULL |
| status | VARCHAR(30) | NOT NULL, DEFAULT 'open', CHECK (status IN ('open','in_progress','awaiting_approval','resolved','closed')) |
| channel | VARCHAR(20) | NOT NULL, CHECK (channel IN ('email','chat','sms','voice','social')) |
| priority | VARCHAR(10) | NOT NULL, DEFAULT 'medium', CHECK (priority IN ('low','medium','high','urgent')) |
| customer_id | UUID | NOT NULL, FK → customers.id |
| assignee_id | UUID | NULL, FK → users.id |
| assignee_type | VARCHAR(10) | NULL, CHECK (assignee_type IN ('ai','human','system')) |
| confidence_score | INTEGER | NULL |
| is_vip | BOOLEAN | NOT NULL, DEFAULT false |
| is_legal | BOOLEAN | NOT NULL, DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(company_id)`, `(company_id, status)`, `(company_id, created_at DESC)`, `(company_id, priority)`, `(company_id, channel)`, `(company_id, assignee_id)`, composite: `(company_id, status, created_at DESC)` for common filter+sort |

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 3, 4, 5, 8 — Every query includes `WHERE company_id = :tenant_id` via middleware; Socket.io room scoped to `tenant_{company_id}`; all response data filtered by tenant; `company_id` indexed.
- **BC-005 (Real-Time Communication):** Rules 1, 2, 3, 5, 6 — Socket.io reconnection with exponential backoff; event buffer for missed events; tenant-scoped rooms; graceful degradation (list works without Socket.io on refresh).
- **BC-011 (Authentication & Security):** JWT required; PII masking on `customer_email` in list view (show `j***@example.com`).
- **BC-012 (Error Handling & Resilience):** Invalid query params return 422 with descriptive message; database query timeout at 5 seconds.

## Edge Cases
1. **Empty result set:** User applies a filter combination matching zero tickets. UI shows "No tickets match your filters" with a "Clear Filters" button.
2. **Sorting by nullable column (e.g., assignee_id):** Tickets without an assignee sort to the end regardless of ASC/DESC.
3. **Page beyond total:** User navigates to page 10 but only 6 pages exist. API returns page 6 (last page) with HTTP 200.
4. **Socket.io disconnection during filter change:** Real-time updates pause. On reconnect, the full filtered list is re-fetched via REST to ensure consistency.
5. **Extremely large tenant (100K+ tickets):** Pagination prevents loading all tickets. `page_size` capped at 100. Query uses covering index `(company_id, status, created_at DESC)` for sub-second performance.
6. **VIP/Legal tickets:** Always highlighted with a special badge/icon in the list row (links to F-080).

## Acceptance Criteria
1. **AC-1:** Loading `/tickets` with default filters returns the first 25 open tickets sorted by `created_at DESC` within 500ms.
2. **AC-2:** Applying a "Status = Awaiting Approval" filter returns only tickets with that status. Changing to "Status = Open" refreshes the list correctly.
3. **AC-3:** Clicking the "Created At" column header toggles sort order between ASC and DESC, and the URL query params update accordingly (deep-linkable).
4. **AC-4:** A ticket created by another user (via Socket.io event `ticket:new`) appears at the top of the list with a brief highlight animation without a full page reload.
5. **AC-5:** Hovering over a ticket row shows a preview tooltip with the first 150 characters of the latest message.
6. **AC-6:** The API returns HTTP 401 if JWT is missing and HTTP 422 if `sort_order` is not `asc` or `desc`.
7. **AC-7:** Tickets from Tenant A are never visible when querying with Tenant B's JWT — confirmed with cross-tenant test.

---

# F-047: Ticket Detail Modal (Full Conversation)

## Overview
A slide-in panel/modal that displays the complete conversation history for a selected ticket — all messages from customer, AI agent, and human agents, with timestamps, sender identification, channel context, file attachments, internal notes, metadata sidebar (classification, confidence, sentiment), and real-time status updates. This is the primary workspace for reviewing and acting on individual tickets.

## User Journey
1. User clicks a ticket row in the Ticket List (F-046). The Ticket Detail Modal slides in from the right, taking 60% of the screen width.
2. The modal header shows: ticket ID, subject, status badge, priority badge, and a close button.
3. The left panel displays the full conversation thread: each message has a sender avatar, name, timestamp, and content. Customer messages are left-aligned (blue), AI/agent messages are right-aligned (gray). Internal notes are yellow.
4. The right sidebar shows ticket metadata: channel, classification (intent/type), confidence score breakdown, sentiment indicator, customer profile summary, and linked approval records.
5. If the ticket has an AI-proposed action awaiting approval, an action bar appears at the bottom: "Approve", "Reject", "Edit & Approve" buttons.
6. User types an internal note in the note input and clicks "Add Note". The note appears in the thread immediately (optimistic update) and is confirmed via Socket.io.
7. User clicks "Approve" on a pending action. The action executes, the status changes to "resolved", and a real-time Socket.io event updates the Ticket List behind the modal.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| TicketDetailModal | `src/components/tickets/TicketDetailModal.tsx` | Slide-in modal container with close/resize controls |
| ConversationThread | `src/components/tickets/ConversationThread.tsx` | Scrollable message list with sender alignment and timestamps |
| MessageBubble | `src/components/tickets/MessageBubble.tsx` | Individual message with avatar, sender, content, attachments |
| TicketMetadataSidebar | `src/components/tickets/TicketMetadataSidebar.tsx` | Right sidebar with classification, confidence, sentiment, customer info |
| TicketActionbar | `src/components/tickets/TicketActionBar.tsx` | Bottom action bar with Approve/Reject/Edit buttons for pending actions |
| InternalNoteInput | `src/components/tickets/InternalNoteInput.tsx` | Text input for adding internal notes to the ticket |
| AttachmentViewer | `src/components/tickets/AttachmentViewer.tsx` | File attachment thumbnails with download links |

## Backend APIs

### `GET /api/tickets/{ticket_id}`
- **Auth:** JWT
- **Response 200:**
```json
{
  "ticket": {
    "id": "tkt_001",
    "subject": "Refund request for order #12345",
    "status": "awaiting_approval",
    "channel": "email",
    "priority": "high",
    "classification": {"intent": "refund", "type": "financial", "confidence": 87},
    "sentiment": {"score": -0.3, "label": "frustrated"},
    "customer": {"id": "cust_abc", "name": "Jane Doe", "email": "jane@example.com", "vip": false, "total_tickets": 5},
    "assignee": {"id": "usr_abc", "name": "AI Agent - Billing", "type": "ai"},
    "is_vip": false,
    "is_legal": false,
    "created_at": "2026-03-15T10:30:00Z",
    "updated_at": "2026-03-15T11:45:00Z"
  },
  "messages": [
    {
      "id": "msg_001",
      "sender_type": "customer",
      "sender_name": "Jane Doe",
      "content": "I would like a full refund for my recent order #12345. The product arrived damaged.",
      "attachments": [{"id": "att_001", "filename": "damaged-product.jpg", "url": "/api/attachments/att_001", "size_bytes": 340000}],
      "created_at": "2026-03-15T10:30:00Z",
      "is_internal": false
    },
    {
      "id": "msg_002",
      "sender_type": "ai",
      "sender_name": "PARWA AI",
      "content": "I'm sorry to hear about the damaged product, Jane. I've reviewed your order #12345 and can confirm it qualifies for a full refund of $49.99. Shall I process this for you?",
      "attachments": [],
      "created_at": "2026-03-15T10:30:15Z",
      "is_internal": false
    }
  ],
  "pending_actions": [
    {
      "id": "appr_001",
      "action_type": "refund",
      "description": "Process full refund of $49.99 for order #12345",
      "amount": 49.99,
      "confidence": 87,
      "confidence_breakdown": {"retrieval": 92, "intent_match": 95, "history": 80, "sentiment": 78},
      "created_at": "2026-03-15T10:30:15Z",
      "timeout_at": "2026-03-18T10:30:15Z"
    }
  ],
  "internal_notes": [
    {"id": "note_001", "author": "John Smith", "content": "Customer has contacted us 3 times about this. Prioritize.", "created_at": "2026-03-15T11:00:00Z"}
  ]
}
```
- **Error 404:** Ticket not found or cross-tenant access.
- **Error 401:** Missing/invalid JWT.

### `POST /api/tickets/{ticket_id}/notes`
- **Auth:** JWT
- **Request Body:**
```json
{
  "content": "Customer confirmed they want the refund. Proceeding.",
  "is_internal": true
}
```
- **Response 201:**
```json
{
  "id": "note_002",
  "author": "Current User",
  "content": "Customer confirmed they want the refund. Proceeding.",
  "created_at": "2026-03-15T12:00:00Z"
}
```
- **Error 404:** Ticket not found.
- **Error 400:** `content` must be 1-5000 characters.

## Database Tables

### `ticket_messages`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| ticket_id | UUID | NOT NULL, FK → tickets.id ON DELETE CASCADE |
| company_id | UUID | NOT NULL, FK → companies.id |
| sender_type | VARCHAR(10) | NOT NULL, CHECK (sender_type IN ('customer','ai','human','system')) |
| sender_id | UUID | NULL, FK → users.id (null for customer) |
| sender_name | VARCHAR(255) | NOT NULL |
| content | TEXT | NOT NULL |
| is_internal | BOOLEAN | NOT NULL, DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(ticket_id, created_at ASC)`, `(company_id, ticket_id)` |

### `ticket_attachments`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| message_id | UUID | NOT NULL, FK → ticket_messages.id ON DELETE CASCADE |
| company_id | UUID | NOT NULL, FK → companies.id |
| filename | VARCHAR(512) | NOT NULL |
| storage_path | VARCHAR(1024) | NOT NULL |
| mime_type | VARCHAR(100) | NOT NULL |
| size_bytes | INTEGER | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

### `ticket_internal_notes`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| ticket_id | UUID | NOT NULL, FK → tickets.id ON DELETE CASCADE |
| company_id | UUID | NOT NULL, FK → companies.id |
| author_id | UUID | NOT NULL, FK → users.id |
| content | TEXT | NOT NULL, CHECK (length(content) BETWEEN 1 AND 5000) |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(ticket_id, created_at ASC)`, `(company_id, ticket_id)` |

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 4, 8 — All ticket/message queries scoped by `company_id`; responses filtered; indexes on `company_id`.
- **BC-005 (Real-Time Communication):** Rules 1, 3, 5, 6 — Socket.io events for new messages, status changes; events stored in `event_buffer`; tenant-scoped rooms; graceful degradation on Socket.io failure.
- **BC-009 (Approval Workflow):** Rule 8 — VIP tickets flagged; Rule 9 — Approval actions logged in audit trail.
- **BC-011 (Authentication & Security):** JWT required for all endpoints; internal notes only visible to tenant users, not to customer-facing channels.
- **BC-012 (Error Handling & Resilience):** 404 for cross-tenant access; 400 for validation errors; optimistic UI updates with rollback on failure.

## Edge Cases
1. **Ticket deleted while modal is open:** Socket.io event `ticket:deleted` triggers modal close with toast: "This ticket has been deleted."
2. **Very long conversation (500+ messages):** Messages are paginated in the thread — initial load shows last 50 messages with a "Load earlier messages" button.
3. **Attachment download failure:** If attachment file is missing from storage, the attachment viewer shows "File unavailable" instead of a broken link.
4. **Concurrent edits:** Two users viewing the same ticket both see real-time updates. If one approves and the other tries to approve, the second sees "Action already processed" toast.
5. **Customer PII in messages:** Full email/phone visible only to authenticated tenant users (not masked in detail view unlike the list view).

## Acceptance Criteria
1. **AC-1:** Clicking a ticket row opens the modal within 300ms with the full conversation thread and metadata sidebar visible.
2. **AC-2:** Customer messages are left-aligned with blue styling; AI/agent messages are right-aligned with gray styling; internal notes have yellow background.
3. **AC-3:** Adding an internal note posts it optimistically in the UI and confirms via Socket.io event within 2 seconds.
4. **AC-4:** The pending action bar shows "Approve" and "Reject" buttons only when the ticket has an action in `awaiting_approval` status.
5. **AC-5:** Requesting a ticket belonging to another tenant returns HTTP 404, not 403 (no information leakage).
6. **AC-6:** Attachments are displayed with filename, file size, and a working download link.
7. **AC-7:** Closing and reopening the modal preserves the scroll position of the conversation thread.

---

# F-074: Approval Queue Dashboard

## Overview
The Approval Queue Dashboard is the centralized command center for all AI-initiated actions requiring human review. It displays pending approval items in a filterable, sortable list with confidence indicators, batch processing capabilities, and real-time count updates. This is where supervisors spend a significant portion of their day, so usability and performance are paramount. It integrates with F-076 (Individual Approval), F-075 (Batch Approval), and F-080 (Urgent Attention Panel).

## User Journey
1. User navigates to `/approvals` from the sidebar. The dashboard loads with a summary bar showing counts: Pending (23), Approved Today (47), Rejected Today (5), Overdue (2).
2. The main list shows all pending approvals sorted by urgency (VIP first, then by confidence ascending, then by age ascending).
3. User applies a filter: "Action Type = Refund". The list narrows to refund-related approvals only.
4. User selects 5 refund approvals using checkboxes and clicks "Batch Approve". A confirmation dialog shows: "You are about to approve 5 refund actions totaling $342.50. Continue?" User confirms, all 5 execute atomically.
5. A new approval enters the queue via Socket.io event. The pending count increments in real-time and the new item appears at the top with a pulse animation.
6. User clicks on an individual approval to open the Individual Ticket Approval panel (F-076) as a slide-in.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| ApprovalDashboard | `src/pages/approvals/index.tsx` | Main dashboard page with summary bar, filters, and approval list |
| ApprovalSummaryBar | `src/components/approvals/ApprovalSummaryBar.tsx` | Top bar with pending/approved/rejected/overdue counts with live updates |
| ApprovalFilterBar | `src/components/approvals/ApprovalFilterBar.tsx` | Filters: action type, confidence range, date range, VIP only toggle |
| ApprovalList | `src/components/approvals/ApprovalList.tsx` | List of pending approvals with checkboxes for batch selection |
| ApprovalItemCard | `src/components/approvals/ApprovalItemCard.tsx` | Individual approval card showing action type, amount, confidence, ticket link, age |
| BatchApproveDialog | `src/components/approvals/BatchApproveDialog.tsx` | Confirmation dialog for batch approve/reject with summary totals |
| ApprovalCountBadge | `src/components/approvals/ApprovalCountBadge.tsx` | Animated badge showing pending count (used in sidebar nav) |

## Backend APIs

### `GET /api/approvals`
- **Auth:** JWT (requires supervisor or admin role)
- **Query Params:**
  - `status` (optional, default `pending`): `pending,approved,rejected,expired`
  - `action_type` (optional): `refund,subscription_change,response_send,escalation`
  - `confidence_min` (optional, integer 0-100): Minimum confidence score
  - `confidence_max` (optional, integer 0-100): Maximum confidence score
  - `is_vip` (optional, boolean): Filter VIP-only
  - `sort_by` (optional, default `urgency`): `urgency,confidence,created_at,amount`
  - `sort_order` (optional, default `asc`): `asc` or `desc`
  - `page` (optional, default `1`)
  - `page_size` (optional, default `25`)
- **Response 200:**
```json
{
  "summary": {
    "pending_count": 23,
    "approved_today": 47,
    "rejected_today": 5,
    "overdue_count": 2
  },
  "approvals": [
    {
      "id": "appr_001",
      "action_type": "refund",
      "description": "Process full refund of $49.99 for order #12345",
      "amount": 49.99,
      "confidence": 87,
      "confidence_breakdown": {"retrieval": 92, "intent_match": 95, "history": 80, "sentiment": 78},
      "ticket_id": "tkt_001",
      "ticket_subject": "Refund request for order #12345",
      "customer_name": "Jane Doe",
      "is_vip": false,
      "is_legal": false,
      "status": "pending",
      "created_at": "2026-03-15T10:30:00Z",
      "timeout_at": "2026-03-18T10:30:15Z",
      "age_hours": 1.5,
      "is_overdue": false
    }
  ],
  "pagination": {"page": 1, "page_size": 25, "total_items": 23, "total_pages": 1}
}
```
- **Error 403:** User lacks supervisor/admin role.

### `POST /api/approvals/batch`
- **Auth:** JWT (supervisor/admin)
- **Request Body:**
```json
{
  "approval_ids": ["appr_001", "appr_002", "appr_003"],
  "decision": "approve",
  "comment": "Verified order details match refund requests."
}
```
- **Response 200:**
```json
{
  "processed": 3,
  "results": [
    {"id": "appr_001", "status": "approved", "executed": true},
    {"id": "appr_002", "status": "approved", "executed": true},
    {"id": "appr_003", "status": "approved", "executed": true}
  ],
  "total_amount": 142.50
}
```
- **Error 400:** `decision` must be `approve` or `reject`. `approval_ids` must contain 1-50 items.
- **Error 409:** One or more approvals already processed. Returns list of conflicts.

### Socket.io Events (Room: `tenant_{company_id}`)
- **Event: `approval:new`** — New approval added to queue. Payload: `{ approval_id, action_type, confidence, ticket_id }`
- **Event: `approval:processed`** — Approval decided. Payload: `{ approval_id, decision, processed_by }`
- **Event: `approval:count_update`** — Pending count changed. Payload: `{ pending_count }`

## Database Tables

### `approval_records`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id |
| ticket_id | UUID | NOT NULL, FK → tickets.id |
| action_type | VARCHAR(30) | NOT NULL, CHECK (action_type IN ('refund','subscription_change','response_send','escalation','account_modification')) |
| description | TEXT | NOT NULL |
| amount | DECIMAL(10,2) | NULL |
| confidence | INTEGER | NOT NULL |
| confidence_breakdown | JSONB | DEFAULT '{}' — `{"retrieval": 92, "intent_match": 95, "history": 80, "sentiment": 78}` |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK (status IN ('pending','approved','rejected','expired','auto_approved')) |
| route | VARCHAR(20) | NOT NULL — `human_agent, manager_escalation, auto_execute, human_required` |
| requester_id | UUID | NULL, FK → users.id (system for AI) |
| approver_id | UUID | NULL, FK → users.id |
| comment | TEXT | NULL |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| timeout_at | TIMESTAMPTZ | NOT NULL — 72h from creation |
| executed_at | TIMESTAMPTZ | NULL |
| **Indexes:** | | `(company_id, status, created_at)`, `(company_id, ticket_id)`, `(company_id, action_type)`, `(company_id, confidence)`, `(timeout_at)` for expiry job |

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 3, 4, 5, 8 — All queries scoped by `company_id`; Socket.io rooms tenant-scoped; `company_id` indexed on all related tables.
- **BC-002 (Financial Actions):** Rules 1, 5, 8 — Financial approval records created before execution; atomic DB transactions for batch operations; audit trail logging.
- **BC-005 (Real-Time Communication):** Rules 1, 3, 5, 6 — Socket.io for live count updates and new approval notifications; event buffer for missed events; tenant-scoped rooms; graceful degradation.
- **BC-009 (Approval Workflow):** Rules 1, 2, 3, 6, 7, 8, 9 — Confidence-based routing; atomic batch processing; timeout ladder; self-approval prohibition; 30s undo window; VIP override; full audit trail.
- **BC-011 (Authentication & Security):** Supervisor/admin role required for approval endpoints.
- **BC-012 (Error Handling & Resilience):** Batch operations atomic (all-or-nothing); conflict detection for already-processed approvals.

## Edge Cases
1. **Batch with mixed statuses:** User selects 5 approvals but 2 were already approved by another supervisor. API returns 409 with conflict details; the 3 remaining are not processed.
2. **Empty queue:** No pending approvals. Dashboard shows "All caught up! No pending approvals." with a celebration illustration.
3. **Very large batch (50+ items):** `approval_ids` limited to 50 per batch. UI shows "Select up to 50 items" warning.
4. **Socket.io disconnection:** Summary bar counts may be stale. On reconnect, counts are re-fetched from REST API.
5. **Financial approval with Paddle failure:** If refund execution fails after approval, the approval record shows `status: approved` but `executed_at: null`. A retry button appears.

## Acceptance Criteria
1. **AC-1:** Loading `/approvals` shows the summary bar with accurate pending/approved/rejected/overdue counts within 500ms.
2. **AC-2:** Filtering by `action_type = refund` shows only refund approvals. Clearing the filter restores the full list.
3. **AC-3:** Selecting 3 approvals and clicking "Batch Approve" with confirmation executes all 3 atomically — either all succeed or all fail.
4. **AC-4:** A new approval entering the queue via Socket.io increments the pending count in real-time and the new item appears in the list.
5. **AC-5:** A user with an "agent" role (non-supervisor) receives HTTP 403 when accessing `GET /api/approvals`.
6. **AC-6:** Batch approving items that include an already-processed approval returns HTTP 409 with details of which items conflicted.
7. **AC-7:** VIP approvals are surfaced at the top of the default sort regardless of other sort criteria.

---

# F-076: Individual Ticket Approval/Reject

## Overview
The per-ticket review interface where supervisors examine an AI-proposed action in full detail, view the confidence score breakdown (retrieval relevance, intent match, historical accuracy, sentiment alignment), read the complete ticket conversation for context, and then approve, reject, or edit-and-approve the proposed action. This is the core human-in-the-loop decision point for the PARWA approval system.

## User Journey
1. Supervisor clicks on an approval item in the Approval Queue Dashboard (F-074). The Individual Approval panel slides in.
2. The panel shows 3 sections: (a) **Proposed Action** — action type, amount (if financial), description, and edit capability; (b) **Confidence Breakdown** — visual bars for retrieval, intent, history, sentiment scores with color coding; (c) **Ticket Context** — scrollable conversation thread.
3. Supervisor reviews the confidence breakdown. Retrieval is 92 (green), intent match is 95 (green), but sentiment is 45 (orange — customer is frustrated). Supervisor decides to approve with a modified response.
4. Supervisor clicks "Edit & Approve", modifies the AI's proposed response text, and confirms. The edited response is sent to the customer.
5. Alternatively, supervisor clicks "Reject" and selects a reason from a dropdown: "Incorrect amount", "Wrong customer", "Policy violation", "Other". The rejection is logged and the ticket is routed back to human handling.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| IndividualApprovalPanel | `src/components/approvals/IndividualApprovalPanel.tsx` | Slide-in panel with action details, confidence, and ticket context |
| ConfidenceBreakdown | `src/components/approvals/ConfidenceBreakdown.tsx` | Visual score bars for retrieval, intent, history, sentiment with color coding (0-49 red, 50-79 orange, 80-100 green) |
| ProposedActionCard | `src/components/approvals/ProposedActionCard.tsx` | Editable card showing the AI's proposed action with amount, description, response preview |
| ApprovalDecisionBar | `src/components/approvals/ApprovalDecisionBar.tsx` | Bottom bar with Approve, Reject, Edit & Approve buttons |
| RejectReasonDropdown | `src/components/approvals/RejectReasonDropdown.tsx` | Dropdown for reject reason selection with optional comment field |
| ResponseEditor | `src/components/approvals/ResponseEditor.tsx` | Rich text editor for modifying AI-proposed responses before approval |

## Backend APIs

### `GET /api/approvals/{approval_id}`
- **Auth:** JWT (supervisor/admin)
- **Response 200:**
```json
{
  "approval": {
    "id": "appr_001",
    "action_type": "refund",
    "description": "Process full refund of $49.99 for order #12345",
    "proposed_response": "I've processed a full refund of $49.99 for your order #12345. You should see it reflected in your account within 3-5 business days.",
    "amount": 49.99,
    "currency": "USD",
    "confidence": 87,
    "confidence_breakdown": {
      "retrieval": {"score": 92, "label": "Knowledge base match quality"},
      "intent_match": {"score": 95, "label": "Ticket intent classification accuracy"},
      "history": {"score": 80, "label": "Historical resolution pattern match"},
      "sentiment": {"score": 78, "label": "Customer sentiment alignment"}
    },
    "route": "human_agent",
    "status": "pending",
    "ticket": {
      "id": "tkt_001",
      "subject": "Refund request for order #12345",
      "customer_name": "Jane Doe",
      "is_vip": false,
      "message_count": 3,
      "messages": [
        {"sender_type": "customer", "content": "I would like a full refund for order #12345. Product arrived damaged.", "created_at": "2026-03-15T10:30:00Z"},
        {"sender_type": "ai", "content": "I'm sorry about the damaged product. I can process a full refund of $49.99.", "created_at": "2026-03-15T10:30:15Z"},
        {"sender_type": "customer", "content": "Yes please, refund it.", "created_at": "2026-03-15T10:35:00Z"}
      ]
    },
    "created_at": "2026-03-15T10:30:15Z",
    "timeout_at": "2026-03-18T10:30:15Z",
    "age_hours": 1.5
  }
}
```
- **Error 404:** Approval not found or cross-tenant.
- **Error 403:** User lacks supervisor/admin role.

### `POST /api/approvals/{approval_id}/decision`
- **Auth:** JWT (supervisor/admin)
- **Request Body (Approve):**
```json
{
  "decision": "approve",
  "edited_response": null,
  "comment": "Order confirmed damaged via photo attachment."
}
```
- **Request Body (Edit & Approve):**
```json
{
  "decision": "approve",
  "edited_response": "I've processed a full refund of $49.99 for order #12345. Given the damaged product, I've also added a 10% discount code for your next purchase: SORRY10.",
  "comment": "Added goodwill discount per our policy."
}
```
- **Request Body (Reject):**
```json
{
  "decision": "reject",
  "reject_reason": "incorrect_amount",
  "comment": "Customer ordered 2 items ($89.98 total), refund should be for full amount."
}
```
- **Response 200 (Approve):**
```json
{
  "status": "approved",
  "executed": true,
  "undo_available_until": "2026-03-15T10:31:00Z",
  "ticket_status": "resolved",
  "message_sent": true,
  "message_id": "msg_003"
}
```
- **Response 200 (Reject):**
```json
{
  "status": "rejected",
  "ticket_status": "in_progress",
  "routed_to": "human_agent"
}
```
- **Error 409:** Approval already processed.
- **Error 403:** Self-approval attempt (approver is the same as the AI requester — edge case for future human-requested approvals).

## Database Tables

Uses `approval_records` table (defined in F-074) plus:

### `approval_audit_log`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id |
| approval_id | UUID | NOT NULL, FK → approval_records.id |
| approver_id | UUID | NOT NULL, FK → users.id |
| decision | VARCHAR(10) | NOT NULL, CHECK (decision IN ('approved','rejected')) |
| confidence_score | INTEGER | NOT NULL |
| reject_reason | VARCHAR(50) | NULL |
| comment | TEXT | NULL |
| edited_response | TEXT | NULL |
| executed | BOOLEAN | NOT NULL, DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(company_id, approval_id)`, `(approver_id, created_at DESC)` |

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 4, 8 — All queries scoped by `company_id`; approval details verified against tenant.
- **BC-002 (Financial Actions):** Rules 1, 5, 8 — Approval record exists before execution; refund processed in atomic transaction; full audit trail.
- **BC-005 (Real-Time Communication):** Rules 3, 5 — Decision events emitted to Socket.io room; tenant-scoped.
- **BC-009 (Approval Workflow):** Rules 1, 6, 7, 8, 9 — Confidence-based display; self-approval check; 30-second undo window; VIP override (always routes to human); comprehensive audit logging.
- **BC-012 (Error Handling & Resilience):** 409 for already-processed approvals; financial execution failure triggers compensation transaction rollback.

## Edge Cases
1. **Undo within 30 seconds:** Approver clicks "Undo" within the window. The approval status reverts to `pending`, the executed action is reversed (refund reversal via Paddle, email recall via Brevo), and the ticket re-enters `awaiting_approval`.
2. **Undo after 30 seconds:** The "Undo" button disappears. The approver sees a toast: "Action finalized. Contact support to reverse."
3. **Financial execution failure after approval:** Paddle API returns 500. Approval stays `approved` but `executed = false`. A Celery retry task is queued. Approver sees a warning: "Approval recorded but execution failed. System will retry."
4. **Edited response too long:** If `edited_response` exceeds 5000 characters, return 400 with validation error.
5. **VIP ticket approval attempt:** The approval record has `route = human_required`. The approver can still approve but sees a VIP banner: "This is a VIP customer. Extra review recommended."

## Acceptance Criteria
1. **AC-1:** Loading an individual approval shows the proposed action, confidence breakdown with 4 sub-scores, and the full ticket conversation.
2. **AC-2:** Clicking "Approve" with no edits executes the action and returns `executed: true` with an `undo_available_until` timestamp 30 seconds in the future.
3. **AC-3:** Clicking "Reject" with reason "incorrect_amount" and a comment updates the approval status to `rejected`, creates an audit log entry, and routes the ticket back to `in_progress`.
4. **AC-4:** Edit & Approve with a modified response sends the edited text (not the AI's original) to the customer.
5. **AC-5:** The "Undo" button is visible for 30 seconds after approval and disappears after 30 seconds.
6. **AC-6:** A second supervisor attempting to decide on an already-processed approval receives HTTP 409.
7. **AC-7:** The confidence breakdown colors are correct: 0-49 red, 50-79 orange, 80-100 green.

---

# F-078: Auto-Approve Confirmation Flow

## Overview
When a client enables auto-approve rules for specific action types, Jarvis (the AI assistant) must display a comprehensive, multi-step confirmation flow showing ALL possible consequences of enabling auto-approval before the client can confirm. This is a critical safety mechanism (Locked Decision LD-022) that prevents accidental auto-approval of actions with significant financial or reputational impact. The user must explicitly click a confirm link to proceed; no auto-approval activates without this explicit confirmation.

## User Journey
1. Client navigates to Settings > Auto-Approve Rules and toggles "Auto-approve refunds under $100".
2. Jarvis appears as an inline chat panel and displays a multi-step consequence analysis:
   - **Step 1 — Scope:** "This rule will auto-approve ALL refund requests under $100. Based on your last 30 days of data, this affects approximately 23 refunds/week averaging $47.50 each."
   - **Step 2 — Financial Impact:** "Estimated monthly auto-approved refund volume: $4,370. Maximum single auto-approved refund: $99.99. Annual projection: $52,440."
   - **Step 3 — Risk Assessment:** "Historical error rate for refunds under $100: 3.2%. This means approximately 1 erroneous refund every 2 weeks, costing ~$47.50 per error. Estimated monthly loss from errors: ~$95."
   - **Step 4 — What Happens:** "When a refund request meets these criteria: (a) Amount ≤ $100, (b) AI confidence ≥ 80%, (c) Non-VIP customer, the system will immediately process the refund and send the customer a confirmation email. You will NOT be notified for individual approvals. You can review approved refunds in the Approval History."
   - **Step 5 — Safety Nets:** "You retain full control: Emergency Pause (F-083) stops all auto-approvals instantly. The Undo System (F-084) allows reversal within the undo window. You can disable this rule at any time from Settings."
3. At the bottom, Jarvis shows: "Do you want to proceed? [I Understand, Enable Auto-Approve]" and "[Cancel]".
4. Client clicks "I Understand, Enable Auto-Approve". The rule is saved and activated.
5. If client clicks "Cancel", the toggle reverts and no rule is created.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| AutoApproveSettings | `src/pages/settings/AutoApproveSettings.tsx` | Settings page with toggle switches per action type |
| JarvisConsequencePanel | `src/components/approvals/JarvisConsequencePanel.tsx` | Multi-step consequence display panel (appears when toggling auto-approve) |
| ConsequenceStep | `src/components/approvals/ConsequenceStep.tsx` | Individual consequence step with icon, title, and detail content |
| JarvisConfirmBar | `src/components/approvals/JarvisConfirmBar.tsx` | Bottom bar with "I Understand, Enable" and "Cancel" buttons |

## Backend APIs

### `POST /api/auto-approve/consequence-analysis`
- **Auth:** JWT (admin only)
- **Request Body:**
```json
{
  "action_type": "refund",
  "conditions": {
    "max_amount": 100.00,
    "min_confidence": 80,
    "exclude_vip": true
  }
}
```
- **Response 200:**
```json
{
  "analysis": {
    "scope": {
      "description": "Auto-approve all refund requests under $100 with AI confidence ≥ 80%",
      "estimated_weekly_count": 23,
      "estimated_avg_amount": 47.50,
      "based_on_period_days": 30
    },
    "financial_impact": {
      "estimated_monthly_volume": 4370.00,
      "max_single_amount": 99.99,
      "annual_projection": 52440.00,
      "currency": "USD"
    },
    "risk_assessment": {
      "historical_error_rate_pct": 3.2,
      "estimated_errors_per_month": 3,
      "estimated_error_cost_per_month": 142.50,
      "sample_period": "last_90_days"
    },
    "affected_actions": [
      "Immediate refund processing via Paddle",
      "Automatic customer confirmation email sent via Brevo",
      "Ticket status changed to 'resolved'",
      "Approval record created with status 'auto_approved'"
    ],
    "safety_nets": [
      {"name": "Emergency Pause", "description": "Immediately halts all auto-approvals"},
      {"name": "Undo System", "description": "Reverse auto-approved actions within undo window"},
      {"name": "Audit Trail", "description": "All auto-approved actions logged for review"},
      {"name": "Disable Rule", "description": "Turn off this rule anytime from Settings"}
    ]
  }
}
```

### `POST /api/auto-approve/rules`
- **Auth:** JWT (admin only)
- **Request Body:**
```json
{
  "action_type": "refund",
  "conditions": {
    "max_amount": 100.00,
    "min_confidence": 80,
    "exclude_vip": true
  },
  "confirmed": true,
  "confirmation_token": "jwt_encoded_token_from_consequence_analysis"
}
```
- **Response 201:**
```json
{
  "rule": {
    "id": "rule_001",
    "action_type": "refund",
    "conditions": {"max_amount": 100.00, "min_confidence": 80, "exclude_vip": true},
    "status": "active",
    "created_by": "usr_admin",
    "created_at": "2026-03-15T14:00:00Z"
  },
  "message": "Auto-approve rule activated. Refunds under $100 with confidence ≥ 80% will be processed automatically."
}
```
- **Error 400:** `confirmed` must be `true` and `confirmation_token` must be valid and not expired (tokens expire after 30 minutes).
- **Error 403:** User is not admin.
- **Error 409:** A conflicting rule already exists for this action type.

### `GET /api/auto-approve/rules`
- **Auth:** JWT (admin)
- **Response 200:**
```json
{
  "rules": [
    {"id": "rule_001", "action_type": "refund", "conditions": {"max_amount": 100.00, "min_confidence": 80, "exclude_vip": true}, "status": "active", "created_at": "2026-03-15T14:00:00Z"}
  ]
}
```

### `DELETE /api/auto-approve/rules/{rule_id}`
- **Auth:** JWT (admin)
- **Response 200:** `{"status": "disabled", "message": "Auto-approve rule disabled. All matching actions will now require manual approval."}`

## Database Tables

### `auto_approve_rules`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id |
| action_type | VARCHAR(30) | NOT NULL, CHECK (action_type IN ('refund','subscription_change','response_send','escalation')) |
| conditions | JSONB | NOT NULL — `{"max_amount": 100.00, "min_confidence": 80, "exclude_vip": true}` |
| status | VARCHAR(10) | NOT NULL, DEFAULT 'active', CHECK (status IN ('active','disabled')) |
| created_by | UUID | NOT NULL, FK → users.id |
| confirmed_by | UUID | NOT NULL, FK → users.id |
| confirmed_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(company_id)`, `(company_id, action_type)`, UNIQUE `(company_id, action_type)` where `status = 'active'` |
| **Constraints:** | | Only one active rule per action_type per company |

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 8 — All queries scoped by `company_id`; indexes on `company_id`.
- **BC-002 (Financial Actions):** Rules 1, 4, 8 — Auto-approved financial actions still create approval records; rate limiting on rule creation (admin-only, max 1 rule change per hour); full audit trail.
- **BC-009 (Approval Workflow):** Rules 1, 4, 5 — Auto-approve rules only activate above confidence threshold; conflicting rules resolved by most restrictive; emergency pause immediately disables all auto-approve rules.
- **BC-011 (Authentication & Security):** Admin-only access; confirmation token with 30-minute expiry to prevent CSRF/session hijacking.
- **BC-012 (Error Handling & Resilience):** Invalid or expired confirmation tokens rejected; conflicting rule detection returns 409.

## Edge Cases
1. **Confirmation token expired (>30 min):** User takes too long reading consequences. The "I Understand, Enable" button shows "Token expired. Refresh the analysis." Clicking it re-runs the consequence analysis with fresh data.
2. **Conflicting rules:** Admin tries to create a refund auto-approve with max_amount $50 when an existing rule has max_amount $100. The more restrictive rule ($50) should win per BC-009 Rule 4.
3. **Emergency pause active:** If emergency pause (F-083) is active, the confirmation panel shows an additional warning: "Emergency Pause is currently active. Auto-approve rules will be dormant until pause is lifted."
4. **VIP override:** Even with auto-approve active, VIP customer tickets are ALWAYS excluded (condition `exclude_vip: true` is non-negotiable per BC-009 Rule 8).
5. **Admin change mid-confirmation:** If admin is demoted to supervisor between analysis and confirmation, `POST /auto-approve/rules` returns 403.

## Acceptance Criteria
1. **AC-1:** Toggling an auto-approve rule triggers the Jarvis Consequence Panel with all 5 steps: Scope, Financial Impact, Risk Assessment, What Happens, and Safety Nets.
2. **AC-2:** The consequence analysis includes accurate estimated weekly/monthly counts and amounts calculated from the tenant's last 30 days of data.
3. **AC-3:** Clicking "I Understand, Enable Auto-Approve" with a valid confirmation token creates the rule and returns HTTP 201.
4. **AC-4:** Clicking "Cancel" reverts the toggle and does NOT create any rule.
5. **AC-5:** Submitting confirmation with an expired token (>30 minutes) returns HTTP 400 with message "Confirmation token expired. Please refresh the analysis."
6. **AC-6:** VIP tickets are never auto-approved even when a matching rule is active — verified by creating a VIP ticket that meets all other conditions and confirming it enters manual review.
7. **AC-7:** Emergency Pause immediately disables all active auto-approve rules, and the settings page shows all rules as "Dormant (Emergency Pause Active)".

---

# F-080: Urgent Attention Panel (VIP/Legal)

## Overview
A persistent, prominently displayed UI panel that flags tickets from VIP customers and legal escalations. These tickets are never auto-handled regardless of confidence score, always bubble to the top of all ticket and approval lists, and trigger immediate notifications to account managers. This feature ensures high-value customers and legally sensitive issues receive the highest level of human attention at all times.

## User Journey
1. Supervisor logs into the dashboard. A red-bordered "Urgent Attention" panel is pinned at the top of the sidebar or as a floating widget.
2. The panel shows: "3 tickets require urgent attention" with a breakdown: "2 VIP | 1 Legal".
3. Clicking the panel opens a filtered view showing only VIP and legal tickets, sorted by creation time (newest first).
4. Each urgent ticket has a red/gold border indicator, a VIP badge or legal badge, and the customer's account value (for VIP) or case reference (for legal).
5. When a new VIP or legal ticket arrives, the panel count pulses and a push notification is sent to all supervisors.
6. VIP tickets bypass auto-approve rules entirely (BC-009 Rule 8). They always enter `route = human_required` in the approval queue.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| UrgentAttentionWidget | `src/components/dashboard/UrgentAttentionWidget.tsx` | Floating/badge widget showing urgent count, always visible in sidebar |
| UrgentAttentionPanel | `src/components/tickets/UrgentAttentionPanel.tsx` | Expanded panel listing all VIP and legal tickets |
| UrgentTicketRow | `src/components/tickets/UrgentTicketRow.tsx` | Ticket row with red/gold border, VIP/legal badge, and account value |
| VIPBadge | `src/components/ui/VIPBadge.tsx` | Gold badge with star icon for VIP tickets |
| LegalBadge | `src/components/ui/LegalBadge.tsx` | Red badge with scale icon for legal escalations |

## Backend APIs

### `GET /api/tickets/urgent`
- **Auth:** JWT (supervisor/admin)
- **Query Params:**
  - `type` (optional): `vip`, `legal`, or omit for both
  - `status` (optional, default `open,in_progress,awaiting_approval`): Only active statuses by default
  - `page` (optional, default `1`)
  - `page_size` (optional, default `25`)
- **Response 200:**
```json
{
  "summary": {
    "total_urgent": 3,
    "vip_count": 2,
    "legal_count": 1,
    "oldest_urgent_minutes": 45
  },
  "tickets": [
    {
      "id": "tkt_vip001",
      "subject": "Account billing discrepancy - URGENT",
      "status": "in_progress",
      "urgency_type": "vip",
      "priority": "urgent",
      "customer": {
        "name": "Acme Corporation",
        "vip": true,
        "account_value_monthly": 12500.00,
        "account_manager": "Sarah Johnson",
        "total_lifetime_value": 450000.00
      },
      "confidence_score": 72,
      "created_at": "2026-03-15T09:45:00Z",
      "age_minutes": 45,
      "latest_message_preview": "We need this resolved before our board meeting tomorrow..."
    },
    {
      "id": "tkt_legal001",
      "subject": "Formal complaint - service level breach",
      "status": "awaiting_approval",
      "urgency_type": "legal",
      "priority": "urgent",
      "customer": {
        "name": "John Smith",
        "vip": false,
        "legal_case_reference": "LC-2026-0442"
      },
      "confidence_score": null,
      "created_at": "2026-03-15T10:00:00Z",
      "age_minutes": 30,
      "latest_message_preview": "This constitutes a formal complaint under our service agreement..."
    }
  ]
}
```

### `POST /api/tickets/{ticket_id}/flag-urgent`
- **Auth:** JWT (supervisor/admin)
- **Request Body:**
```json
{
  "urgency_type": "vip",
  "reason": "Customer spends $12,500/month. Flagged as VIP."
}
```
or
```json
{
  "urgency_type": "legal",
  "reason": "Customer mentions formal complaint and legal action.",
  "legal_case_reference": "LC-2026-0442"
}
```
- **Response 200:**
```json
{
  "ticket_id": "tkt_001",
  "is_vip": true,
  "is_legal": false,
  "flagged_by": "usr_admin",
  "flagged_at": "2026-03-15T11:00:00Z",
  "message": "Ticket flagged as VIP. It will always require human review."
}
```
- **Error 404:** Ticket not found.
- **Error 400:** `urgency_type` must be `vip` or `legal`.

### Socket.io Events (Room: `tenant_{company_id}`)
- **Event: `urgent:new`** — New VIP or legal ticket. Payload: `{ ticket_id, urgency_type, customer_name, subject }`
- **Event: `urgent:count_update`** — Count changed. Payload: `{ total_urgent, vip_count, legal_count }`

## Database Tables

Uses `tickets` table (columns `is_vip`, `is_legal` defined in F-046) plus:

### `urgent_flags`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id |
| ticket_id | UUID | NOT NULL, FK → tickets.id |
| urgency_type | VARCHAR(10) | NOT NULL, CHECK (urgency_type IN ('vip','legal')) |
| reason | TEXT | NOT NULL |
| legal_case_reference | VARCHAR(100) | NULL |
| flagged_by | UUID | NOT NULL, FK → users.id |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(company_id, urgency_type)`, `(company_id, ticket_id)`, UNIQUE `(ticket_id, urgency_type)` |

### `customers` (columns used by this feature)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PRIMARY KEY |
| company_id | UUID | FK → companies.id |
| name | VARCHAR(255) | |
| email | VARCHAR(512) | |
| is_vip | BOOLEAN | DEFAULT false |
| account_value_monthly | DECIMAL(10,2) | NULL |
| account_manager_id | UUID | NULL, FK → users.id |
| total_lifetime_value | DECIMAL(12,2) | NULL |

## Technique Activation for VIP/Legal (BC-013)

When a ticket is flagged as VIP or legal escalation, the Technique Router (BC-013) automatically upgrades the response pipeline to Tier 3 premium techniques. This ensures the highest-quality AI reasoning for the most sensitive tickets.

### VIP Customer Behavior
- VIP tickets auto-trigger **Universe of Thought (F-144)** — a Tier 3 premium technique that generates multiple independent reasoning chains before converging on the best response.
- VIP tickets auto-trigger **Reflexion (F-147)** — a Tier 3 premium technique that performs iterative self-evaluation and refinement, producing progressively higher-quality outputs.
- Both techniques activate in tandem: Reflexion evaluates and refines the outputs generated by Universe of Thought, providing a multi-pass reasoning pipeline.
- The additional inference cost is absorbed as part of the VIP service tier (no per-ticket cost increase to the tenant).

### Legal Escalation Behavior
- Legal escalation tickets always use **Self-Consistency (F-146)** — a Tier 3 premium technique that runs the same reasoning prompt multiple times and selects the most consistent response.
- Self-Consistency provides compliance verification by ensuring that legal interpretations, policy citations, and liability assessments are stable across multiple inference passes.
- A legal ticket with inconsistent outputs across passes is automatically flagged with `consistency_risk: true` and routed to `human_required` regardless of individual pass confidence.

### Technique Router Integration
- The Technique Router (BC-013) uses VIP and Legal flags as **primary trigger signals** for Tier 3 activation — these flags take precedence over all other technique selection logic.
- VIP flag → activates F-144 + F-147 (Universe of Thought + Reflexion)
- Legal flag → activates F-146 (Self-Consistency)
- Both flags present → activates F-144 + F-146 + F-147 (full Tier 3 pipeline)
- Tier 3 activation is logged in the ticket's `technique_log` metadata: `{ "tier": 3, "techniques": ["F-144", "F-147"], "trigger": "vip_flag", "activated_at": "..." }`

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 3, 4, 8 — All queries scoped by `company_id`; Socket.io rooms tenant-scoped; indexes on `company_id`.
- **BC-002 (Financial Actions):** Rule 8 — VIP-related financial actions (refunds for high-value customers) are audit-logged with extra detail.
- **BC-005 (Real-Time Communication):** Rules 1, 3, 5 — Socket.io for real-time urgent count and new urgent ticket notifications; tenant-scoped rooms; graceful degradation.
- **BC-006 (Email Communication):** Rule 5 — Urgent ticket notifications to account managers logged in `email_logs`.
- **BC-009 (Approval Workflow):** Rule 8 — VIP accounts ALWAYS require human approval regardless of confidence score. VIP flag overrides any auto-approve rule. Rule 9 — All VIP/legal flagging logged in audit trail.
- **BC-011 (Authentication & Security):** Only supervisors/admins can flag tickets as urgent.
- **BC-012 (Error Handling & Resilience):** Flagging operations are atomic; urgent panel degrades gracefully (shows stale count) when Socket.io is down.
- **BC-013 (Technique Router):** VIP and Legal flags serve as primary trigger signals for Tier 3 premium technique activation. VIP tickets auto-trigger F-144 (Universe of Thought) and F-147 (Reflexion); legal escalation tickets auto-trigger F-146 (Self-Consistency). Dual-flagged tickets activate the full Tier 3 pipeline (F-144 + F-146 + F-147). All Tier 3 activations are recorded in ticket `technique_log` metadata for audit traceability.

## Edge Cases
1. **Ticket flagged as both VIP and legal:** Both flags are independent. The ticket appears in both categories with dual badges (gold + red border).
2. **VIP customer with auto-approve rule:** Even if auto-approve is enabled for refunds, a VIP customer's refund ALWAYS routes to `human_required` (BC-009 Rule 8).
3. **Unflagging a ticket:** Supervisor can remove VIP/legal flag via `DELETE /api/tickets/{ticket_id}/flag-urgent`. The ticket returns to normal routing.
4. **Urgent panel with 0 items:** Widget shows "No urgent tickets" with a green checkmark instead of the red count.
5. **Notification fatigue:** If multiple VIP tickets arrive in rapid succession, notifications are batched — max 1 notification per 60 seconds.

## Acceptance Criteria
1. **AC-1:** The UrgentAttentionWidget is visible on every page and displays an accurate count of VIP + legal tickets.
2. **AC-2:** Flagging a ticket as VIP via `POST /api/tickets/{ticket_id}/flag-urgent` sets `is_vip = true` and triggers a Socket.io `urgent:new` event.
3. **AC-3:** A VIP customer's refund request with confidence score 95 still routes to `human_required` and appears in the Approval Queue — never auto-approved.
4. **AC-4:** The urgent ticket list sorts by newest first and shows VIP tickets with gold borders and legal tickets with red borders.
5. **AC-5:** When a new VIP ticket arrives, the urgent widget count increments in real-time via Socket.io within 2 seconds.
6. **AC-6:** Removing a VIP flag via `DELETE` returns the ticket to normal routing and decrements the VIP count.
7. **AC-7:** VIP customer account value and account manager name are displayed on each urgent ticket row.

---

# F-083: Emergency Pause Controls

## Overview
The Emergency Pause is a kill-switch that allows admins to immediately halt ALL AI auto-handling across the platform — or scoped to specific channels. When activated, every in-flight auto-execution is queued, no new auto-approvals execute, and the AI agent switches to "human-handoff only" mode where it informs customers that a human agent will assist them shortly. This is the most critical safety control in PARWA and must work instantly and reliably.

## User Journey
1. Admin clicks the "Emergency Pause" button in the Jarvis Command Center or the global header. A large red confirmation modal appears: "EMERGENCY PAUSE — This will immediately stop all AI auto-handling. All pending auto-approvals will be queued for manual review. AI responses will switch to human-handoff messages. Are you sure?"
2. Admin clicks "Confirm Emergency Pause". The system immediately: (a) Sets Redis key `parwa:{company_id}:emergency_pause = true`, (b) Queues all in-flight auto-executions, (c) Emits Socket.io event `emergency:paused` to all connected clients.
3. All dashboard components instantly reflect the paused state: a persistent red banner appears at the top: "EMERGENCY PAUSE ACTIVE — AI auto-handling is suspended. All actions require manual review."
4. The Ticket List shows paused tickets with a "Paused" badge. The Approval Queue shows all queued items with "Queued (Paused)" status.
5. When the admin is ready to resume, they click "Resume AI" in the Jarvis Command Center. A confirmation modal shows: "Resume AI auto-handling? Queued items will resume processing in order."
6. Admin confirms. The system removes the Redis key, emits `emergency:resumed`, and queued items resume FIFO processing.

## Frontend Components
| Component | Path | Renders |
|-----------|------|---------|
| EmergencyPauseButton | `src/components/common/EmergencyPauseButton.tsx` | Large red button in header/Jarvis panel — pulsing when active |
| EmergencyPauseConfirmModal | `src/components/common/EmergencyPauseConfirmModal.tsx` | Full-screen confirmation modal with warning messaging |
| EmergencyPauseBanner | `src/components/common/EmergencyPauseBanner.tsx` | Persistent red banner shown on all pages when pause is active |
| ResumeConfirmModal | `src/components/common/ResumeConfirmModal.tsx` | Confirmation modal for resuming with queued item count |
| PauseStatusIndicator | `src/components/common/PauseStatusIndicator.tsx` | Small indicator dot (red=paused, green=active) in header |

## Backend APIs

### `POST /api/emergency/pause`
- **Auth:** JWT (admin only)
- **Request Body:**
```json
{
  "scope": "all",
  "reason": "AI generated incorrect refund amounts. Investigating.",
  "channels": null
}
```
or scoped:
```json
{
  "scope": "channels",
  "reason": "Email channel sending malformed responses.",
  "channels": ["email"]
}
```
- **Response 200:**
```json
{
  "status": "paused",
  "scope": "all",
  "paused_at": "2026-03-15T14:30:00Z",
  "paused_by": "usr_admin",
  "reason": "AI generated incorrect refund amounts. Investigating.",
  "queued_items_count": 12,
  "message": "Emergency pause activated. All AI auto-handling is suspended."
}
```
- **Error 403:** User is not admin.
- **Error 409:** Emergency pause is already active.

### `POST /api/emergency/resume`
- **Auth:** JWT (admin only)
- **Request Body:**
```json
{
  "reason": "Issue resolved. AI model retrained."
}
```
- **Response 200:**
```json
{
  "status": "active",
  "resumed_at": "2026-03-15T15:00:00Z",
  "resumed_by": "usr_admin",
  "queued_items_resuming": 12,
  "message": "AI auto-handling resumed. 12 queued items processing in FIFO order."
}
```
- **Error 409:** No active emergency pause.

### `GET /api/emergency/status`
- **Auth:** JWT
- **Response 200:**
```json
{
  "is_paused": true,
  "scope": "all",
  "paused_at": "2026-03-15T14:30:00Z",
  "paused_by": {"id": "usr_admin", "name": "Admin User"},
  "reason": "AI generated incorrect refund amounts. Investigating.",
  "duration_minutes": 30,
  "queued_items_count": 12
}
```

### Socket.io Events (Room: `tenant_{company_id}`)
- **Event: `emergency:paused`** — Pause activated. Payload: `{ scope, reason, paused_at, paused_by, queued_items_count }`
- **Event: `emergency:resumed`** — Pause lifted. Payload: `{ resumed_at, resumed_by, queued_items_resuming }`

## Database Tables

### `emergency_pause_log`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() |
| company_id | UUID | NOT NULL, FK → companies.id |
| scope | VARCHAR(10) | NOT NULL, CHECK (scope IN ('all','channels')) |
| channels | VARCHAR(20)[] | NULL — e.g., `'{email,chat}'` |
| reason | TEXT | NOT NULL |
| action | VARCHAR(10) | NOT NULL, CHECK (action IN ('pause','resume')) |
| initiated_by | UUID | NOT NULL, FK → users.id |
| queued_items_count | INTEGER | NOT NULL, DEFAULT 0 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| **Indexes:** | | `(company_id, created_at DESC)` |

### Redis Key (Primary pause state — for sub-millisecond checks)
- **Key:** `parwa:{company_id}:emergency_pause`
- **Value:** JSON `{"paused": true, "scope": "all", "channels": null, "paused_at": "..."}`
- **TTL:** None (persistent until explicitly removed)
- **Check pattern:** Every auto-approval and AI response generation checks this Redis key BEFORE execution. If `paused = true` and the action/channel matches the scope, the action is queued.

## Building Codes Applied
- **BC-001 (Multi-Tenant Isolation):** Rules 1, 2, 7 — Emergency pause is per-tenant (each company has its own pause state); Redis key namespaced with `company_id`.
- **BC-002 (Financial Actions):** Rule 1 — Financial actions queued during pause still create approval records with status `queued_paused`.
- **BC-004 (Background Jobs):** Rules 1, 3 — Celery tasks that process queued items receive `company_id` and check pause state before execution.
- **BC-005 (Real-Time Communication):** Rules 3, 5, 8 — Emergency pause/resume events emitted to tenant Socket.io room; events stored in `event_buffer`; pause context flag included in all subsequent events.
- **BC-009 (Approval Workflow):** Rule 5 — Emergency pause immediately queues all pending auto-execution items; customers see "under review" status; FIFO resumption on resume.
- **BC-011 (Authentication & Security):** Admin-only access to pause/resume endpoints; all pause actions audit-logged.
- **BC-012 (Error Handling & Resilience):** Redis key as primary store with PostgreSQL `emergency_pause_log` as persistent backup; if Redis is down, system falls back to checking the DB log for the most recent pause event.

## Edge Cases
1. **Redis down during pause activation:** The system writes to both Redis and the `emergency_pause_log` table atomically. AI processing checks Redis first (fast path), falls back to DB query (slow path — acceptable during Redis outage). The emergency_pause_log is the source of truth.
2. **Admin pauses during batch approval:** If an admin activates emergency pause while a batch approval is executing, the batch continues (already started). Only NEW auto-approvals are queued.
3. **Multiple pause/resume cycles:** Each cycle is logged separately. The current state is determined by the most recent log entry. UI shows "Paused 3 times today" if relevant.
4. **Scoped pause (channels):** If pause scope is `channels: ["email"]`, only email-related auto-approvals are paused. Chat and SMS continue normally.
5. **Pause during onboarding:** If AI has not been activated yet, the pause button is disabled with tooltip "AI is not active yet."
6. **Resume with 0 queued items:** Resume works normally with `queued_items_resuming: 0` and message "AI auto-handling resumed. No queued items."

## Acceptance Criteria
1. **AC-1:** Clicking "Emergency Pause" with confirmation sets the Redis key and creates a log entry within 500ms. The Socket.io `emergency:paused` event is emitted within 1 second.
2. **AC-2:** After pause activation, all new auto-approval actions are queued (not executed) and their approval records show status `queued_paused`.
3. **AC-3:** The EmergencyPauseBanner appears on all pages within 2 seconds of pause activation via Socket.io.
4. **AC-4:** Resuming the pause removes the Redis key, emits `emergency:resumed`, and queued items begin processing in FIFO order within 5 seconds.
5. **AC-5:** A scoped pause on `channels: ["email"]` pauses only email auto-approvals. Chat and SMS auto-approvals continue unaffected.
6. **AC-6:** A non-admin user calling `POST /api/emergency/pause` receives HTTP 403.
7. **AC-7:** If Redis is down, the system falls back to checking `emergency_pause_log` and pause/resume still functions (within 1-2 seconds latency).

---

## Document Information

| Field | Value |
|-------|-------|
| **Document Title** | PARWA Feature Specs — Batch 2: Tickets/Approvals |
| **Version** | 1.0 |
| **Date** | March 2026 |
| **Features Specified** | 9 (F-033, F-034, F-046, F-047, F-074, F-076, F-078, F-080, F-083) |
| **Priority Breakdown** | 8 Critical, 1 High |
| **Building Codes Referenced** | BC-001, BC-002, BC-003, BC-004, BC-005, BC-006, BC-007, BC-008, BC-009, BC-010, BC-011, BC-012 |
| **Locked Decisions Applied** | LD-022 (Jarvis consequence display for auto-approve confirmation) |
| **Dependencies** | PARWA Building Codes v1.0, PARWA Feature Catalog v1.0 |
