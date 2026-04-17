# PARWA Ticket Management — Complete 8-Day Build Roadmap v2.0

> **Part:** 13 - Ticket Management
> **Current State:** ~65% Complete
> **Target:** 100% Production Ready
> **Created:** April 18, 2026
> **Updated:** After reviewing Part 12, 11, 15 roadmaps for connections

---

## 🔗 CONNECTION MAP — Where Ticket Management Connects

### Part Dependency Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     TICKET MANAGEMENT CONNECTION MAP                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────┐                          ┌────────────────┐            │
│  │ PART 12        │                          │ PART 11        │            │
│  │ DASHBOARD      │                          │ SHADOW MODE    │            │
│  │                │                          │                │            │
│  │ Day 3: Tickets │◄───── Frontend ────────► │ Day 3: Ticket  │            │
│  │ Page Build     │      Components          │ Integration    │            │
│  │ (20 items)     │                          │                │            │
│  └───────┬────────┘                          └───────┬────────┘            │
│          │                                           │                      │
│          │ Uses Backend APIs                         │ Needs ticket         │
│          ▼                                           ▼                      │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │                    PART 13: TICKET MANAGEMENT                  │        │
│  │                                                                │        │
│  │  CORE SERVICES:                                                │        │
│  │  ├── Ticket CRUD (✅ exists)                                  │        │
│  │  ├── SLA Management (❌ needs build)                          │        │
│  │  ├── AI Assignment Scoring (⚠️ stub)                         │        │
│  │  ├── Omnichannel Identity (⚠️ partial)                       │        │
│  │  ├── Merge/Dedupe (⚠️ partial)                               │        │
│  │  ├── Export (❌ needs build)                                 │        │
│  │  └── Rich Text Templates (❌ needs build)                    │        │
│  │                                                                │        │
│  └───────────────────────────┬────────────────────────────────────┘        │
│                              │                                              │
│                              │ Provides ticket counts                       │
│                              ▼                                              │
│                       ┌────────────────┐                                   │
│                       │ PART 15         │                                   │
│                       │ BILLING         │                                   │
│                       │                 │                                   │
│                       │ Day 1: Usage    │                                   │
│                       │ Metering Hook   │                                   │
│                       └────────────────┘                                   │
│                                                                             │
│  OTHER CONNECTIONS:                                                         │
│  ├── Part 14 (Channels) → Tickets created from all channels                │
│  ├── Part 10 (Jarvis) → Jarvis shows ticket errors, trains from tickets    │
│  ├── Part 9 (AI Techniques) → Techniques applied to tickets                │
│  └── Part 6 (Training) → Training data from ticket resolutions             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Current State Analysis — What Exists

### Database Models: ✅ 95% Complete
**File:** `database/models/tickets.py` — 740 lines

| Model | Status | Notes |
|-------|--------|-------|
| Ticket | ✅ Complete | All fields including shadow_status, risk_score |
| TicketMessage | ✅ Complete | Includes ai_confidence, variant_version |
| TicketAttachment | ✅ Complete | File handling ready |
| TicketInternalNote | ✅ Complete | Pinned notes supported |
| TicketStatusChange | ✅ Complete | Audit trail |
| SLAPolicy | ✅ Complete | Per plan/priority |
| SLATimer | ✅ Complete | Breach tracking |
| TicketAssignment | ✅ Complete | Assignment history |
| BulkActionLog | ✅ Complete | Undo support |
| TicketMerge | ✅ Complete | Merge audit |
| NotificationTemplate | ✅ Complete | Email templates |
| TicketFeedback | ✅ Complete | CSAT |
| CustomerChannel | ✅ Complete | Omnichannel linking |
| IdentityMatchLog | ✅ Complete | Identity resolution |
| TicketIntent | ✅ Complete | AI classification |
| ClassificationCorrection | ✅ Complete | Human corrections |
| AssignmentRule | ✅ Complete | Custom rules |
| TicketTrigger | ✅ Complete | Automation |
| CustomField | ✅ Complete | Custom fields |
| TicketCollision | ✅ Complete | Concurrent editing |

### Backend Services: ⚠️ 75% Complete

| Service | File | Status | Gap |
|---------|------|--------|-----|
| TicketService | ticket_service.py | ✅ 90% | Shadow methods need testing |
| TicketLifecycleService | ticket_lifecycle_service.py | ✅ 85% | State machine complete |
| TicketMergeService | ticket_merge_service.py | ✅ 80% | Undo needs testing |
| TicketSearchService | ticket_search_service.py | ✅ 85% | Full-text works |
| TicketAnalyticsService | ticket_analytics_service.py | ✅ 70% | Missing real-time metrics |
| StaleTicketService | stale_ticket_service.py | ✅ 90% | Cron job exists |
| SLAService | ❌ MISSING | Create needed | Timers, alerts, breach handling |
| AssignmentScoringService | ❌ MISSING | Create needed | Real AI scoring (not stub) |
| IdentityMatchingService | ❌ MISSING | Create needed | Cross-channel identity |
| TicketExportService | ❌ MISSING | Create needed | CSV/PDF/JSON export |
| TemplateService | ❌ MISSING | Create needed | Response templates |

### API Endpoints: ✅ 85% Complete

**File:** `backend/app/api/tickets.py` — 907 lines

| Endpoint | Status | Notes |
|----------|--------|-------|
| POST /api/tickets | ✅ | Create ticket |
| GET /api/tickets | ✅ | List with filters |
| GET /api/tickets/{id} | ✅ | Get details |
| PUT /api/tickets/{id} | ✅ | Update |
| DELETE /api/tickets/{id} | ✅ | Soft/hard delete |
| PATCH /api/tickets/{id}/status | ✅ | Status update |
| POST /api/tickets/{id}/assign | ✅ | Assign |
| POST /api/tickets/{id}/tags | ✅ | Add tags |
| DELETE /api/tickets/{id}/tags/{tag} | ✅ | Remove tag |
| POST /api/tickets/{id}/attachments | ✅ | Upload |
| GET /api/tickets/{id}/attachments | ✅ | List attachments |
| POST /api/tickets/bulk/status | ✅ | Bulk status |
| POST /api/tickets/bulk/assign | ✅ | Bulk assign |
| POST /api/tickets/detect-priority | ✅ | AI priority |
| POST /api/tickets/detect-category | ✅ | AI category |
| POST /api/tickets/scan-pii | ✅ | PII scan |
| POST /api/tickets/{id}/resolve-with-shadow | ✅ | Shadow resolve |
| POST /api/tickets/{id}/approve-resolution | ✅ | Approve |
| POST /api/tickets/{id}/undo-resolution | ✅ | Undo |
| GET /api/tickets/{id}/shadow-details | ✅ | Shadow info |
| GET /api/tickets/export/csv | ❌ MISSING | Export CSV |
| GET /api/tickets/export/pdf | ❌ MISSING | Export PDF |
| GET /api/tickets/{id}/suggest-assignee | ❌ MISSING | AI assignment |
| GET /api/tickets/duplicates | ❌ MISSING | Find duplicates |

### Frontend Components: ⚠️ 40% Complete

**Directory:** `src/components/dashboard/tickets/`

| Component | File | Status | Wired to API? |
|-----------|------|--------|---------------|
| TicketList | TicketList.tsx | ⚠️ Exists | Partial |
| TicketRow | TicketRow.tsx | ⚠️ Exists | Partial |
| TicketDetail | TicketDetail.tsx | ⚠️ Exists | Partial |
| TicketFilters | TicketFilters.tsx | ✅ Exists | Yes |
| TicketSearch | TicketSearch.tsx | ✅ Exists | Yes |
| TicketQuickView | TicketQuickView.tsx | ⚠️ Exists | No |
| ConversationView | ConversationView.tsx | ⚠️ Exists | Partial |
| ReplyBox | ReplyBox.tsx | ⚠️ Exists | No (plain text only) |
| InternalNotes | InternalNotes.tsx | ✅ Exists | Yes |
| BulkActions | BulkActions.tsx | ⚠️ Exists | Partial |
| CustomerInfoCard | CustomerInfoCard.tsx | ⚠️ Exists | No |
| GSDStateIndicator | GSDStateIndicator.tsx | ⚠️ Exists | No |
| ConfidenceBar | ConfidenceBar.tsx | ✅ Exists | Yes |
| TimelineView | TimelineView.tsx | ⚠️ Exists | No |
| TicketMetadata | TicketMetadata.tsx | ⚠️ Exists | No |
| SLATimer | ❌ MISSING | Create needed | - |
| SLABadge | ❌ MISSING | Create needed | - |
| AssignmentSuggestions | ❌ MISSING | Create needed | - |
| TemplateSelector | ❌ MISSING | Create needed | - |
| RichTextEditor | ❌ MISSING | Create needed | - |
| ExportModal | ❌ MISSING | Create needed | - |
| MergeModal | ❌ MISSING | Create needed | - |

---

## 🔥 GAP ANALYSIS — What Needs to Be Built

### Gap 1: SLA Management System
**Priority:** P0 — Critical for enterprise customers

| Item | Description | Complexity |
|------|-------------|------------|
| SLA Service | Timer creation, breach detection, alerting | Medium |
| SLA Background Task | Check timers every minute via Celery | Medium |
| SLA API Endpoints | Policies, timers, breach listing | Low |
| SLA Frontend Components | Timer display, badge, countdown | Medium |
| Timezone Handling | Customer timezone for SLA deadlines | Medium |

### Gap 2: AI Assignment Scoring
**Priority:** P1 — Key differentiator

| Item | Description | Complexity |
|------|-------------|------------|
| Scoring Algorithm | 5-factor scoring (expertise, workload, performance, response, availability) | High |
| Assignment Service | Score calculation and best match selection | Medium |
| Assignment API | Suggest assignees, explain scores | Low |
| Assignment UI | Show suggestions with score breakdown | Medium |

### Gap 3: Omnichannel Identity Matching
**Priority:** P1 — Required for unified customer view

| Item | Description | Complexity |
|------|-------------|------------|
| Identity Matching Service | Match customers across email/phone/social | High |
| Identity API | Find/create/link/merge customers | Medium |
| Identity UI | Show linked channels, merge suggestions | Medium |
| Identity Match Logging | Track all resolution attempts | Low |

### Gap 4: Export Functionality
**Priority:** P2 — Needed for reporting

| Item | Description | Complexity |
|------|-------------|------------|
| Export Service | CSV, JSON, PDF generation | Medium |
| Export API | Single/bulk export endpoints | Low |
| Export UI | Modal with format selection | Low |

### Gap 5: Rich Text & Templates
**Priority:** P2 — Professional responses

| Item | Description | Complexity |
|------|-------------|------------|
| Template Model | Database table for templates | Low |
| Template Service | CRUD, rendering with variables | Medium |
| Rich Text Editor | TipTap integration | Medium |
| Template UI | Selector dropdown, variable inserter | Medium |

### Gap 6: Frontend API Wiring
**Priority:** P0 — Components exist but not connected

| Item | Description | Complexity |
|------|-------------|------------|
| Wire TicketList | Connect to real API, add pagination | Low |
| Wire TicketDetail | Load real data, show conversation | Medium |
| Wire ReplyBox | Send messages, integrate with channels | Medium |
| Wire Real-time | Socket.io updates for new tickets | Medium |

---

## 📅 8-DAY BUILD PLAN

### Day 1 — Audit & Gap Documentation
**Goal:** Complete understanding of what exists and what's needed

#### Morning: Backend Audit (4 hours)

| ID | Task | Status |
|----|------|--------|
| 1.1 | Run all ticket tests: `pytest tests/unit/test_ticket*.py -v` | Pending |
| 1.2 | Test each API endpoint with curl/Postman | Pending |
| 1.3 | Identify all stub functions and TODO comments | Pending |
| 1.4 | Check service layer for fake returns | Pending |
| 1.5 | Document assignment scoring stub location | Pending |

#### Afternoon: Frontend Audit (4 hours)

| ID | Task | Status |
|----|------|--------|
| 1.6 | Check which components are wired to API | Pending |
| 1.7 | Test Socket.io events for tickets | Pending |
| 1.8 | Identify missing real-time updates | Pending |
| 1.9 | Check Part 12 Day 3 plan for overlap | Pending |
| 1.10 | Create GAP_ANALYSIS.md with exact file locations | Pending |

#### Deliverables:
- [ ] Complete test results documented
- [ ] All stubs listed with file:line
- [ ] API endpoint verification matrix
- [ ] Frontend wiring status matrix
- [ ] Gap analysis document

---

### Day 2 — SLA Management Complete
**Goal:** Full SLA timers, breach detection, timezone support

#### Morning: SLA Service (3 hours)

| ID | Task | File |
|----|------|------|
| 2.1 | Create SLAService class | `backend/app/services/sla_service.py` |
| 2.2 | Implement get_policy() for plan/priority lookup | sla_service.py |
| 2.3 | Implement create_timer() for ticket creation | sla_service.py |
| 2.4 | Implement check_breach() for timer status | sla_service.py |
| 2.5 | Implement send_breach_warning() at 80% threshold | sla_service.py |
| 2.6 | Implement record_breach() for overdue tickets | sla_service.py |
| 2.7 | Add timezone-aware deadline calculation | sla_service.py |

#### Afternoon: SLA Background Task & API (3 hours)

| ID | Task | File |
|----|------|------|
| 2.8 | Create Celery task: check_sla_timers() | `backend/app/tasks/sla_tasks.py` |
| 2.9 | Add to Celery Beat schedule (every 1 minute) | `backend/app/core/celery_app.py` |
| 2.10 | Create SLA API endpoints | `backend/app/api/sla.py` |
| 2.11 | GET /api/sla/policies — List policies | sla.py |
| 2.12 | POST /api/sla/policies — Create custom policy | sla.py |
| 2.13 | GET /api/sla/timers/{ticket_id} — Get timer | sla.py |
| 2.14 | GET /api/sla/breached — List breached tickets | sla.py |
| 2.15 | Create default SLA policies migration | `alembic/versions/xxx_sla_defaults.py` |

#### Evening: SLA Frontend Components (2 hours)

| ID | Task | File |
|----|------|------|
| 2.16 | Create SLATimer component | `src/components/dashboard/tickets/SLATimer.tsx` |
| 2.17 | Create SLABadge component | `src/components/dashboard/tickets/SLABadge.tsx` |
| 2.18 | Wire SLA to TicketRow | TicketRow.tsx |
| 2.19 | Wire SLA to TicketDetail | TicketDetail.tsx |

#### Deliverables:
- [ ] SLA Service with all methods
- [ ] Background task checking timers
- [ ] 5 API endpoints
- [ ] Default policies migrated
- [ ] SLA components integrated

---

### Day 3 — AI Assignment Scoring
**Goal:** Real AI-powered agent matching

#### Morning: Scoring Algorithm (3 hours)

| ID | Task | File |
|----|------|------|
| 3.1 | Create AssignmentScoringService | `backend/app/services/assignment_scoring_service.py` |
| 3.2 | Implement score_expertise() — category match | assignment_scoring_service.py |
| 3.3 | Implement score_workload() — open ticket count | assignment_scoring_service.py |
| 3.4 | Implement score_performance() — CSAT, resolution rate | assignment_scoring_service.py |
| 3.5 | Implement score_response_time() — historical SLA | assignment_scoring_service.py |
| 3.6 | Implement score_availability() — online status | assignment_scoring_service.py |
| 3.7 | Implement calculate_scores() — weighted combination | assignment_scoring_service.py |
| 3.8 | Implement get_best_assignee() — top scorer | assignment_scoring_service.py |
| 3.9 | Implement explain_score() — factor breakdown | assignment_scoring_service.py |

#### Afternoon: Assignment API & Integration (3 hours)

| ID | Task | File |
|----|------|------|
| 3.10 | Create assignment API endpoints | `backend/app/api/ticket_assignment.py` |
| 3.11 | GET /api/tickets/{id}/suggest-assignee | ticket_assignment.py |
| 3.12 | POST /api/tickets/{id}/auto-assign | ticket_assignment.py |
| 3.13 | GET /api/agents/{id}/assignment-score | ticket_assignment.py |
| 3.14 | Update TicketService.auto_assign() to use scoring | ticket_service.py |
| 3.15 | Store assignment score in TicketAssignment record | ticket_service.py |

#### Evening: Assignment Frontend (2 hours)

| ID | Task | File |
|----|------|------|
| 3.16 | Create AssignmentSuggestions component | `src/components/dashboard/tickets/AssignmentSuggestions.tsx` |
| 3.17 | Create AgentScoreCard component | `src/components/dashboard/tickets/AgentScoreCard.tsx` |
| 3.18 | Wire to TicketDetail page | TicketDetail.tsx |

#### Deliverables:
- [ ] 5-factor scoring algorithm
- [ ] Assignment Service with explainability
- [ ] 3 API endpoints
- [ ] TicketService integration
- [ ] Assignment suggestions UI

---

### Day 4 — Omnichannel Identity Matching
**Goal:** One customer across all channels

#### Morning: Identity Matching Service (3 hours)

| ID | Task | File |
|----|------|------|
| 4.1 | Create IdentityMatchingService | `backend/app/services/identity_matching_service.py` |
| 4.2 | Implement match_by_email() | identity_matching_service.py |
| 4.3 | Implement match_by_phone() with normalization | identity_matching_service.py |
| 4.4 | Implement match_fuzzy() — multi-factor | identity_matching_service.py |
| 4.5 | Implement find_customer() — combined matching | identity_matching_service.py |
| 4.6 | Implement link_channel() — add to CustomerChannel | identity_matching_service.py |
| 4.7 | Implement merge_customers() | identity_matching_service.py |
| 4.8 | Implement get_all_channels() | identity_matching_service.py |

#### Afternoon: Identity API & Integration (3 hours)

| ID | Task | File |
|----|------|------|
| 4.9 | Create identity API endpoints | `backend/app/api/customer_identity.py` |
| 4.10 | POST /api/customers/find-or-create | customer_identity.py |
| 4.11 | GET /api/customers/{id}/channels | customer_identity.py |
| 4.12 | POST /api/customers/{id}/channels | customer_identity.py |
| 4.13 | POST /api/customers/{id}/merge | customer_identity.py |
| 4.14 | Update TicketService.create_ticket() for identity | ticket_service.py |

#### Evening: Identity Frontend (2 hours)

| ID | Task | File |
|----|------|------|
| 4.15 | Create CustomerIdentityCard | `src/components/dashboard/customers/CustomerIdentityCard.tsx` |
| 4.16 | Create ChannelList component | `src/components/dashboard/customers/ChannelList.tsx` |
| 4.17 | Create MergeCustomersModal | `src/components/dashboard/customers/MergeCustomersModal.tsx` |

#### Deliverables:
- [ ] Identity Matching Service
- [ ] 5 API endpoints
- [ ] Ticket creation integration
- [ ] Identity UI components

---

### Day 5 — Merge/Dedupe + Export
**Goal:** Complete merge UI and export functionality

#### Morning: Merge Enhancement (2 hours)

| ID | Task | File |
|----|------|------|
| 5.1 | Verify TicketMergeService works correctly | ticket_merge_service.py |
| 5.2 | Add find_potential_duplicates() method | ticket_merge_service.py |
| 5.3 | Create GET /api/tickets/duplicates endpoint | tickets.py |
| 5.4 | Create POST /api/tickets/merge-preview endpoint | ticket_merge.py |

#### Afternoon: Export Service (3 hours)

| ID | Task | File |
|----|------|------|
| 5.5 | Create TicketExportService | `backend/app/services/ticket_export_service.py` |
| 5.6 | Implement export_csv() | ticket_export_service.py |
| 5.7 | Implement export_json() | ticket_export_service.py |
| 5.8 | Implement export_pdf() | ticket_export_service.py |
| 5.9 | Create export API endpoints | `backend/app/api/ticket_export.py` |
| 5.10 | POST /api/tickets/export/csv | ticket_export.py |
| 5.11 | POST /api/tickets/export/json | ticket_export.py |
| 5.12 | POST /api/tickets/export/pdf | ticket_export.py |

#### Evening: Export & Merge UI (3 hours)

| ID | Task | File |
|----|------|------|
| 5.13 | Create ExportModal | `src/components/dashboard/tickets/ExportModal.tsx` |
| 5.14 | Create MergeModal | `src/components/dashboard/tickets/MergeModal.tsx` |
| 5.15 | Create DuplicateList component | `src/components/dashboard/tickets/DuplicateList.tsx` |
| 5.16 | Wire export to TicketList | TicketList.tsx |
| 5.17 | Wire merge to TicketDetail | TicketDetail.tsx |

#### Deliverables:
- [ ] Enhanced merge service
- [ ] Duplicate detection
- [ ] Export Service (CSV/JSON/PDF)
- [ ] 4 API endpoints
- [ ] Export & Merge UI

---

### Day 6 — Rich Text Editor & Templates
**Goal:** Professional customer responses

#### Morning: Template System (3 hours)

| ID | Task | File |
|----|------|------|
| 6.1 | Create TicketTemplate model | `database/models/ticket_templates.py` |
| 6.2 | Create migration for templates | `alembic/versions/xxx_ticket_templates.py` |
| 6.3 | Create TemplateService | `backend/app/services/template_service.py` |
| 6.4 | Implement get_templates() | template_service.py |
| 6.5 | Implement render_template() | template_service.py |
| 6.6 | Implement create_template() | template_service.py |
| 6.7 | Create template API endpoints | `backend/app/api/templates.py` |
| 6.8 | GET/POST /api/templates | templates.py |
| 6.9 | POST /api/templates/{id}/render | templates.py |

#### Afternoon: Rich Text Editor (3 hours)

| ID | Task | File |
|----|------|------|
| 6.10 | Install TipTap: `npm install @tiptap/react @tiptap/starter-kit` | package.json |
| 6.11 | Create RichTextEditor component | `src/components/dashboard/tickets/RichTextEditor.tsx` |
| 6.12 | Add bold, italic, underline support | RichTextEditor.tsx |
| 6.13 | Add bullet/numbered list support | RichTextEditor.tsx |
| 6.14 | Add link support | RichTextEditor.tsx |
| 6.15 | Add character count display | RichTextEditor.tsx |

#### Evening: Template UI & Reply Box (2 hours)

| ID | Task | File |
|----|------|------|
| 6.16 | Create TemplateSelector component | `src/components/dashboard/tickets/TemplateSelector.tsx` |
| 6.17 | Add variable insertion ({{customer_name}}, etc.) | TemplateSelector.tsx |
| 6.18 | Update ReplyBox to use RichTextEditor | ReplyBox.tsx |
| 6.19 | Add template selector to ReplyBox | ReplyBox.tsx |
| 6.20 | Add signature auto-append option | ReplyBox.tsx |

#### Deliverables:
- [ ] Template database model
- [ ] Template Service
- [ ] 4 Template API endpoints
- [ ] Rich Text Editor component
- [ ] Template Selector component
- [ ] Enhanced ReplyBox

---

### Day 7 — Real-time Updates & Dashboard Integration
**Goal:** Live updates, full dashboard connection

#### Morning: Socket.io Events (3 hours)

| ID | Task | File |
|----|------|------|
| 7.1 | Verify ticket Socket.io events in backend | socketio_server.py |
| 7.2 | Emit ticket:created on new ticket | ticket_service.py |
| 7.3 | Emit ticket:updated on status change | ticket_service.py |
| 7.4 | Emit ticket:assigned on assignment | ticket_service.py |
| 7.5 | Emit ticket:closed on resolution | ticket_service.py |
| 7.6 | Emit ticket:message for new messages | ticket_service.py |
| 7.7 | Emit sla:warning at 80% threshold | sla_service.py |
| 7.8 | Emit sla:breached on breach | sla_service.py |

#### Afternoon: Socket.io Client Hook (3 hours)

| ID | Task | File |
|----|------|------|
| 7.9 | Create useTicketSocket hook | `src/hooks/useTicketSocket.ts` |
| 7.10 | Implement connection with reconnection | useTicketSocket.ts |
| 7.11 | Join company room on connect | useTicketSocket.ts |
| 7.12 | Handle ticket:created event | useTicketSocket.ts |
| 7.13 | Handle ticket:updated event | useTicketSocket.ts |
| 7.14 | Handle ticket:message event | useTicketSocket.ts |
| 7.15 | Handle sla:warning event | useTicketSocket.ts |

#### Evening: Real-time UI Updates (2 hours)

| ID | Task | File |
|----|------|------|
| 7.16 | Wire Socket.io to TicketList | TicketList.tsx |
| 7.17 | Add new ticket highlight animation | TicketList.tsx |
| 7.18 | Wire Socket.io to TicketDetail | TicketDetail.tsx |
| 7.19 | Add live message updates | ConversationView.tsx |
| 7.20 | Add SLA timer countdown | SLATimer.tsx |

#### Deliverables:
- [ ] 8 Socket.io events wired
- [ ] useTicketSocket hook
- [ ] Real-time ticket list updates
- [ ] Real-time message updates
- [ ] Live SLA countdown

---

### Day 8 — Testing, Polish & Documentation
**Goal:** Production-ready, documented, tested

#### Morning: Testing (4 hours)

| ID | Task | File |
|----|------|------|
| 8.1 | Create SLA service tests | `tests/unit/test_sla_service.py` |
| 8.2 | Create assignment scoring tests | `tests/unit/test_assignment_scoring.py` |
| 8.3 | Create identity matching tests | `tests/unit/test_identity_matching.py` |
| 8.4 | Create export service tests | `tests/unit/test_ticket_export.py` |
| 8.5 | Create template service tests | `tests/unit/test_template_service.py` |
| 8.6 | Create integration test for full ticket flow | `tests/integration/test_ticket_flow.py` |

#### Afternoon: Polish (2 hours)

| ID | Task | File |
|----|------|------|
| 8.7 | Add loading skeletons | Multiple components |
| 8.8 | Add empty states | Multiple components |
| 8.9 | Add error states | Multiple components |
| 8.10 | Add responsive design | TicketList, TicketDetail |
| 8.11 | Add keyboard shortcuts | TicketList |
| 8.12 | Add ARIA labels | All components |

#### Evening: Documentation (2 hours)

| ID | Task | File |
|----|------|------|
| 8.13 | Update OpenAPI docs for ticket endpoints | tickets.py |
| 8.14 | Create Ticket Management User Guide | `docs/user-guide/TICKET_MANAGEMENT_GUIDE.md` |
| 8.15 | Create Ticket System Architecture Doc | `docs/architecture/TICKET_SYSTEM_ARCHITECTURE.md` |

#### Deliverables:
- [ ] 5 test suites passing
- [ ] 1 integration test
- [ ] UI polished
- [ ] API documented
- [ ] User guide
- [ ] Architecture doc

---

## 📊 SUMMARY — What Gets Built

### New Backend Services (5)

| Service | Lines Est. | Purpose |
|---------|-----------|---------|
| SLAService | ~300 | Timer management, breach detection |
| AssignmentScoringService | ~250 | AI-powered agent matching |
| IdentityMatchingService | ~200 | Cross-channel identity |
| TicketExportService | ~150 | CSV/JSON/PDF export |
| TemplateService | ~150 | Response templates |

### New API Endpoints (19)

| Category | Count | Endpoints |
|----------|-------|-----------|
| SLA | 5 | policies, timers, breached |
| Assignment | 3 | suggest, auto-assign, score |
| Identity | 5 | find-or-create, channels, merge |
| Export | 4 | csv, json, pdf |
| Templates | 4 | CRUD, render |
| Tickets | 3 | duplicates, merge-preview, suggest |

### New Frontend Components (10)

| Component | Purpose |
|-----------|---------|
| SLATimer | Countdown display |
| SLABadge | Status indicator |
| AssignmentSuggestions | AI recommendations |
| AgentScoreCard | Score breakdown |
| CustomerIdentityCard | Identity display |
| ChannelList | Linked channels |
| MergeCustomersModal | Merge UI |
| ExportModal | Export options |
| MergeModal | Ticket merge |
| RichTextEditor | Professional responses |
| TemplateSelector | Quick responses |

### Files to Create (15+ new)

```
backend/app/services/
├── sla_service.py (NEW)
├── assignment_scoring_service.py (NEW)
├── identity_matching_service.py (NEW)
├── ticket_export_service.py (NEW)
└── template_service.py (NEW)

backend/app/api/
├── sla.py (NEW)
├── ticket_assignment.py (NEW)
├── customer_identity.py (NEW)
├── ticket_export.py (NEW)
└── templates.py (NEW)

backend/app/tasks/
└── sla_tasks.py (NEW)

src/components/dashboard/tickets/
├── SLATimer.tsx (NEW)
├── SLABadge.tsx (NEW)
├── AssignmentSuggestions.tsx (NEW)
├── AgentScoreCard.tsx (NEW)
├── ExportModal.tsx (NEW)
├── MergeModal.tsx (NEW)
├── RichTextEditor.tsx (NEW)
└── TemplateSelector.tsx (NEW)

src/components/dashboard/customers/
├── CustomerIdentityCard.tsx (NEW)
├── ChannelList.tsx (NEW)
└── MergeCustomersModal.tsx (NEW)

src/hooks/
└── useTicketSocket.ts (NEW)
```

---

## 🔗 CONNECTION CHECKLIST

### Part 12 (Dashboard) — Handoff Items
- [x] Ticket frontend components ready for Part 12 Day 3
- [x] API endpoints documented for frontend consumption
- [ ] Socket.io events tested for real-time updates
- [ ] Activity feed events from tickets

### Part 11 (Shadow Mode) — Integration Points
- [x] Ticket.shadow_status field exists
- [x] Ticket.risk_score field exists
- [x] resolve_with_shadow() method exists
- [x] approve_resolution() method exists
- [x] undo_resolution() method exists
- [ ] Test shadow flow end-to-end

### Part 15 (Billing) — Usage Hook
- [ ] Hook ticket creation to usage metering
- [ ] Hook ticket resolution to usage metering
- [ ] Test overage calculation with real tickets

### Part 14 (Channels) — Ticket Creation
- [ ] Email channel creates tickets
- [ ] SMS channel creates tickets
- [ ] Chat widget creates tickets
- [ ] Voice channel creates tickets

### Part 10 (Jarvis) — Error Panel Data
- [ ] Ticket errors feed to Jarvis J6 panel
- [ ] Train-from-errors has ticket data

---

## ✅ SUCCESS CRITERIA

After Day 8, Ticket Management is **100% production ready** when:

1. ✅ All tests pass (unit + integration)
2. ✅ SLA timers work with real-time breach alerts
3. ✅ AI assignment produces meaningful scores
4. ✅ Customers linked across channels
5. ✅ Merge/undo works correctly
6. ✅ Export produces valid CSV/JSON/PDF
7. ✅ Rich text editor with templates works
8. ✅ Real-time Socket.io updates
9. ✅ Documentation complete
10. ✅ No stubs, no TODOs, no placeholders

---

## 🚨 RISK MITIGATION

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Part 12 frontend overlap | Medium | Medium | Coordinate with Dashboard build |
| Assignment scoring accuracy | Medium | Medium | Start simple, iterate |
| Identity false positives | Medium | High | Conservative thresholds, review queue |
| Socket.io reliability | Low | High | Fallback polling |
| Export performance | Low | Medium | Background jobs for large exports |

---

*End of Ticket Management 8-Day Roadmap v2.0*
