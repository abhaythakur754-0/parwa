# PARWA Week 4 Roadmap — Ticket System Complete Build

> **Phase 2 Start — Days 24-34 (11 days)**
> Last updated: April 3, 2026
> Previous commit: `7ab06da` (Day 24 model rewrite)

---

## What This Week Covers

Week 4 builds the COMPLETE ticket system — every feature, every loophole fix, every production handler. This is not just CRUD. This is a production-grade ticket system that handles every real-world situation.

### Three Sources Combined

| Source | Count | What |
|--------|-------|------|
| **Original Roadmap Features** | 8 | F-046, F-047, F-048, F-049, F-050, F-051, F-052, F-070 |
| **Code Loopholes (BL)** | 9 | BL01-BL09 (BL01-BL02, BL04 DONE on Day 24) |
| **Production Situations (PS)** | 29 | PS01-PS29 (10 MUST, 7 SHOULD, 12 DEFER) |
| **Missing Features (MF)** | 24 | MF01-MF24 (6 MUST, 6 SHOULD, 12 DEFER) |
| **TOTAL** | **70 items** | |

### What's Already Done (Day 24)

- [x] BL01: Table rename — `sessions` → `tickets`, `interactions` → `ticket_messages` (models only, migration pending)
- [x] BL02: All 15 missing model classes added to `database/models/tickets.py`
- [x] BL04: DECIMAL verified on all money columns (Numeric(10,2))
- [x] MF01: `TicketPriority` enum (critical/high/medium/low)
- [x] MF02: `TicketCategory` enum (tech_support/billing/feature_request/bug_report/general/complaint)
- [x] MF03: `tags` column on tickets (Text, JSON array)
- [x] `TicketStatus` enum expanded with 12 states (open/assigned/in_progress/awaiting_client/awaiting_human/resolved/reopened/closed/frozen/queued/stale/escalated_by_client)
- [x] 18 production-situation columns added to Ticket model (reopen_count, frozen, parent_ticket_id, duplicate_of_id, is_spam, awaiting_human, awaiting_client, escalation_level, sla_breached, plan_snapshot, variant_version, first_response_at, resolution_target_at, client_timezone)

### What's Still Missing (10 days of work)

- **Migration**: Alembic migration 002 still uses old `sessions`/`interactions` table names — needs rewrite
- **Schemas**: Zero Pydantic request/response schemas for tickets
- **Service**: Zero business logic for tickets
- **API**: Zero ticket endpoints
- **Tasks**: Zero ticket Celery tasks
- **Tests**: Zero ticket tests
- **Socket.io**: No ticket events integrated
- **All PS handlers**: No production situation logic
- **All MF features**: Priority/category/tags are just columns, no logic
- **SLA system**: Tables exist but zero enforcement logic
- **Notification system**: Tables exist but zero sending logic

---

## Day-by-Day Breakdown

### Day 24 ✅ DONE — Foundation: Models + Enums + Loophole Fixes
**Commit:** `7ab06da`

| Item | Status |
|------|--------|
| BL01: Session→Ticket, Interaction→TicketMessage model rename | ✅ |
| BL02: 15 new model classes | ✅ |
| BL04: DECIMAL verification | ✅ |
| MF01: TicketPriority enum | ✅ |
| MF02: TicketCategory enum | ✅ |
| MF03: tags column | ✅ |
| TicketStatus expanded to 12 states | ✅ |
| 18 PS columns on Ticket model | ✅ |
| Backward compat aliases (Session=Ticket, Interaction=TicketMessage) | ✅ |

**NOT done yet (carries to Day 25):**
- Migration 002 rewrite (still uses `sessions`/`interactions`)
- TicketAttachment FK fix (still references `sessions.id`)

---

### Day 25 — Migration + Schemas Foundation
**Gap IDs covered:** BL02 (migration part), F-046 (schemas), F-047 (message schemas)

**Files to build:**
1. `database/alembic/versions/002_ticketing_tables.py` — REWRITE: rename tables, add all Week 4 columns, create 15 new tables
2. `backend/app/schemas/__init__.py` — Add ticket schema exports
3. `backend/app/schemas/ticket.py` — All Pydantic schemas for tickets
4. `backend/app/schemas/ticket_message.py` — Message + attachment schemas
5. `backend/app/schemas/sla.py` — SLA policy + timer schemas
6. `backend/app/schemas/assignment.py` — Assignment rule schemas
7. `backend/app/schemas/bulk_action.py` — Bulk action + merge schemas
8. `backend/app/schemas/notification.py` — Notification template + preference schemas
9. `backend/app/schemas/customer.py` — Customer + channel + identity schemas

**Schema details:**

```
ticket.py:
  - TicketCreate (subject, customer_id, channel, priority, category, tags, metadata)
  - TicketUpdate (priority, category, tags, status, assigned_to, subject)
  - TicketResponse (full ticket with all fields, timestamps, computed fields)
  - TicketListResponse (paginated list with filters)
  - TicketFilter (status, priority, category, assigned_to, channel, date_range, tags)
  - TicketStatusUpdate (status + reason)
  - TicketAssign (assignee_id, assignee_type, reason)

ticket_message.py:
  - MessageCreate (content, role, channel, is_internal, attachments)
  - MessageResponse (full message with metadata)
  - AttachmentResponse (id, filename, file_url, file_size, mime_type)
  - AttachmentUpload (file validation schema)

sla.py:
  - SLAPolicyCreate (plan_tier, priority, first_response_minutes, resolution_minutes, update_frequency_minutes)
  - SLAPolicyResponse
  - SLATimerResponse (time_remaining, is_breached, breached_at)
  - SLABreachAlert (ticket_id, policy, breach_type, time_elapsed)

assignment.py:
  - AssignmentRuleCreate (name, conditions JSON, action JSON, priority_order)
  - AssignmentRuleResponse
  - AssignmentScore (ticket_id, candidate_scores, final_assignee, reason)

bulk_action.py:
  - BulkActionRequest (action_type, ticket_ids, params)
  - BulkActionResponse (bulk_action_id, undo_token, success_count, failure_count)
  - BulkActionUndo (undo_token)
  - TicketMergeRequest (primary_ticket_id, merged_ticket_ids, reason)
  - TicketUnmergeRequest (merge_id)

notification.py:
  - NotificationTemplateCreate (event_type, channel, subject_template, body_template)
  - NotificationTemplateResponse
  - NotificationPreferenceUpdate (event_type, channel, enabled)
  - NotificationSendRequest (ticket_id, event_type, recipient_ids)

customer.py:
  - CustomerCreate (email, phone, name, external_id, metadata)
  - CustomerUpdate (email, phone, name, metadata)
  - CustomerResponse
  - CustomerMergeRequest (primary_customer_id, merged_customer_ids, reason)
  - IdentityMatchRequest (email, phone, social_id)
  - IdentityMatchResponse (matched_customer_id, match_method, confidence)
  - CustomerChannelCreate (customer_id, channel_type, external_id)
  - CustomerChannelResponse
```

**Tests:** ~120 (schema validation, field constraints, edge cases)
**Push after completion.**

---

### Day 26 — Ticket CRUD Service + API (F-046, MF01-03)
**Gap IDs covered:** F-046, MF01, MF02, MF03, BL05 (rate limiting), BL06 (attachment whitelist), BL07 (PII scanning)

**Files to build:**
1. `backend/app/services/ticket_service.py` — Core ticket business logic
2. `backend/app/services/priority_service.py` — Priority auto-assignment rules
3. `backend/app/services/category_service.py` — Category routing rules
4. `backend/app/services/tag_service.py` — Tag CRUD, auto-tagging, filter
5. `backend/app/services/attachment_service.py` — File validation, whitelist, size limits (PS09)
6. `backend/app/services/pii_scan_service.py` — PII detection + auto-redaction (BL07, PS29)
7. `backend/app/api/tickets.py` — Ticket CRUD endpoints
8. `backend/app/api/__init__.py` — Register ticket router

**Ticket CRUD endpoints (F-046):**
```
POST   /api/v1/tickets                    — Create ticket (with PS01 scope check, PS05 duplicate check)
GET    /api/v1/tickets                    — List tickets (paginated, filtered, sorted)
GET    /api/v1/tickets/:id                — Get ticket detail
PUT    /api/v1/tickets/:id                — Update ticket (priority, category, tags, assignee)
DELETE /api/v1/tickets/:id                — Soft delete (PS12)
PATCH  /api/v1/tickets/:id/status         — Change status (with full state machine validation)
POST   /api/v1/tickets/:id/assign         — Assign ticket (agent, AI, system)
POST   /api/v1/tickets/:id/tags           — Add tags
DELETE /api/v1/tickets/:id/tags/:tag      — Remove tag
POST   /api/v1/tickets/:id/attachments    — Upload attachment (BL06, PS09 validation)
GET    /api/v1/tickets/:id/attachments    — List attachments
```

**Production situation handlers in service layer:**
- PS01: Out-of-plan scope check on create — check client plan entitlements, tag `out_of_scope` if beyond variant capability, show upgrade option
- PS05: Duplicate detection on create — fuzzy match subject + first message against recent open tickets for same customer, similarity >85% → link as duplicate
- PS07: Account suspended check — reject new tickets if company is suspended, freeze existing open tickets

**BL fixes:**
- BL05: Rate limiting on ticket creation — per-client rate limit via existing rate_limit_service (max 10 tickets/hour default, configurable per plan)
- BL06: Attachment whitelist — allowed extensions: pdf, doc, docx, txt, png, jpg, jpeg, gif, csv, xls, xlsx; max size per plan (5MB/25MB/100MB); MIME type verification
- BL07: PII scan on message content — regex patterns for credit cards, SSN, API keys, passwords; auto-redact + store redaction map in Redis

**Tests:** ~200 (CRUD operations, state machine transitions, rate limiting, attachment validation, PII scanning, duplicate detection, scope checks)
**Push after completion.**

---

### Day 27 — Ticket Conversation + Internal Notes (F-047, MF04 Activity Log)
**Gap IDs covered:** F-047, MF04, BL08 (audit trail for tickets)

**Files to build:**
1. `backend/app/services/message_service.py` — Message CRUD, thread management
2. `backend/app/services/activity_log_service.py` — Timeline/activity log for every ticket change
3. `backend/app/services/internal_note_service.py` — Internal notes CRUD
4. `backend/app/api/ticket_messages.py` — Message endpoints
5. `backend/app/api/ticket_notes.py` — Internal note endpoints
6. `backend/app/api/ticket_timeline.py` — Activity timeline endpoint

**Message endpoints (F-047):**
```
POST   /api/v1/tickets/:id/messages       — Add message (customer or agent)
GET    /api/v1/tickets/:id/messages       — List messages (paginated, with filters)
GET    /api/v1/tickets/:id/messages/:mid  — Get single message
PUT    /api/v1/tickets/:id/messages/:mid  — Edit message (only own messages, within 5 min)
DELETE /api/v1/tickets/:id/messages/:mid  — Soft delete message
```

**Internal note endpoints:**
```
POST   /api/v1/tickets/:id/notes          — Create internal note
GET    /api/v1/tickets/:id/notes          — List notes
PUT    /api/v1/tickets/:id/notes/:nid     — Edit note
DELETE /api/v1/tickets/:id/notes/:nid     — Delete note
PATCH  /api/v1/tickets/:id/notes/:nid/pin — Pin/unpin note
```

**Activity timeline endpoint:**
```
GET    /api/v1/tickets/:id/timeline       — Full activity log (status changes, assignments, messages, notes, SLA events, merges)
```

**Activity log events tracked (MF04):**
- Status changed (who, when, old → new, reason)
- Priority changed (who, when, old → new)
- Category changed (who, when, old → new)
- Assigned (who assigned, to whom, type: ai/human/system, score)
- Tags added/removed
- SLA warning triggered
- SLA breached
- Reopened (count, who)
- Frozen/thawed
- Merged/unmerged
- Message added (by whom, channel)
- Internal note added (by whom)
- Attachment uploaded (filename, size)

**BL08 audit trail:** Every ticket write operation logged via existing audit_service from FP11. The activity_log_service provides the human-readable timeline; audit_service provides the machine-readable audit trail.

**Tests:** ~180 (message CRUD, thread ordering, internal notes, activity log entries, timeline pagination, audit trail verification)
**Push after completion.**

---

### Day 28 — Ticket Search + Classification + Assignment (F-048, F-049, F-050)
**Gap IDs covered:** F-048, F-049, F-050

**Files to build:**
1. `backend/app/services/ticket_search_service.py` — Full-text search with fuzzy matching
2. `backend/app/services/classification_service.py` — AI intent classification (stub for Week 8, rule-based for now)
3. `backend/app/services/assignment_service.py` — Score-based assignment (stub scoring, rule-based routing)
4. `backend/app/api/ticket_search.py` — Search endpoints
5. `backend/app/api/ticket_classification.py` — Classification endpoints
6. `backend/app/api/ticket_assignment.py` — Assignment endpoints
7. `backend/app/tasks/ticket_tasks.py` — Ticket Celery tasks (classification, assignment, search indexing)

**Search endpoints (F-048):**
```
GET    /api/v1/tickets/search             — Full-text search (query, filters, sort, pagination)
GET    /api/v1/tickets/search/suggestions — Auto-complete suggestions
```

Search capabilities:
- Full-text search across subject, message content, customer name, customer email
- Fuzzy matching (Levenshtein distance for typos)
- Filter by status, priority, category, assignee, channel, date range, tags
- Sort by created_at, updated_at, priority, SLA time remaining
- Highlighted matching snippets in results
- Recent searches stored in Redis per user

**Classification endpoints (F-049):**
```
POST   /api/v1/tickets/:id/classify       — Trigger classification (AI or manual override)
GET    /api/v1/tickets/:id/classification — Get classification result
PUT    /api/v1/tickets/:id/classification — Human correction to AI classification
GET    /api/v1/classification/corrections — List all corrections (for training data)
```

Classification approach (Week 4 — rule-based, Week 9 — AI):
- Rule-based classifier using keyword matching + category patterns
- Intent categories: refund, technical, billing, complaint, feature_request, general
- Urgency levels: urgent, routine, informational
- Confidence scoring (rule-based: 0.0-1.0 based on match strength)
- Human correction workflow → feeds into training data

**Assignment endpoints (F-050):**
```
POST   /api/v1/tickets/:id/assign/score   — Get assignment scores for all candidates
POST   /api/v1/tickets/:id/assign/auto    — Auto-assign based on rules/scores
GET    /api/v1/assignments/rules           — List assignment rules
POST   /api/v1/assignments/rules           — Create assignment rule
PUT    /api/v1/assignments/rules/:id       — Update rule
DELETE /api/v1/assignments/rules/:id       — Delete rule
```

Assignment approach (Week 4 — rule-based, Week 9 — AI scoring):
- Rule-based routing: category → department → agent pool → round-robin or least-loaded
- Assignment rules engine: conditions (category, priority, channel) → action (assign to user/queue)
- Auto-assignment on ticket create: run rules, if no match → assign to default queue
- Manual reassignment: any agent can reassign to another agent or back to queue

**Tests:** ~160 (search queries, fuzzy matching, classification rules, assignment rules, correction workflow)
**Push after completion.**

---

### Day 29 — Bulk Actions + Merge/Split (F-051) + SLA System (MF06, PS11, PS17)
**Gap IDs covered:** F-051, MF06, PS11, PS17

**Files to build:**
1. `backend/app/services/bulk_action_service.py` — Bulk operations with undo
2. `backend/app/services/ticket_merge_service.py` — Merge/unmerge logic
3. `backend/app/services/sla_service.py` — SLA policy management, timer enforcement, breach detection
4. `backend/app/api/ticket_bulk.py` — Bulk action endpoints
5. `backend/app/api/ticket_merge.py` — Merge/unmerge endpoints
6. `backend/app/api/sla.py` — SLA policy + timer endpoints
7. `backend/app/tasks/sla_tasks.py` — SLA monitoring Celery tasks

**Bulk action endpoints (F-051):**
```
POST   /api/v1/tickets/bulk/status        — Bulk status change
POST   /api/v1/tickets/bulk/assign        — Bulk reassign
POST   /api/v1/tickets/bulk/tags          — Bulk add/remove tags
POST   /api/v1/tickets/bulk/priority      — Bulk priority change
POST   /api/v1/tickets/bulk/close         — Bulk close
POST   /api/v1/tickets/bulk/undo/:token   — Undo last bulk action
GET    /api/v1/bulk-actions               — List bulk action history
GET    /api/v1/bulk-actions/:id           — Get bulk action detail + failures
```

Bulk action mechanics:
- Each bulk action gets a unique `undo_token`
- Max 500 tickets per bulk action
- Individual failures tracked in `bulk_action_failures` table
- Undo reverses the action within 24 hours
- All bulk actions audit-logged

**Merge/unmerge endpoints (F-051):**
```
POST   /api/v1/tickets/merge              — Merge tickets (primary + merged list)
POST   /api/v1/tickets/unmerge/:merge_id  — Unmerge (PS26)
GET    /api/v1/tickets/:id/merges         — Get merge history for ticket
```

Merge mechanics:
- Primary ticket retains all messages from merged tickets
- Merged tickets get status `closed` with merge reference
- Each merge gets an `undo_token` for unmerge
- PS26: Unmerge preserves message history, re-opens merged tickets

**SLA endpoints (MF06):**
```
POST   /api/v1/sla/policies               — Create SLA policy
GET    /api/v1/sla/policies               — List SLA policies
PUT    /api/v1/sla/policies/:id           — Update SLA policy
DELETE /api/v1/sla/policies/:id           — Delete SLA policy
GET    /api/v1/tickets/:id/sla            — Get SLA timer for ticket
GET    /api/v1/sla/breached               — List breached tickets
GET    /api/v1/sla/approaching            — List tickets approaching SLA (PS17: 75%)
```

SLA mechanics:
- SLA policies: plan_tier × priority → first_response_minutes, resolution_minutes, update_frequency_minutes
- Default policies seeded: Starter (low: 24h/72h, medium: 12h/48h, high: 4h/24h, critical: 1h/8h), Growth (half of Starter), High (half of Growth)
- On ticket create → look up SLA policy → create SLA timer → set `resolution_target_at`
- SLA timer tracking: first_response_at, breached_at, is_breached
- PS11: At 75% of SLA time → auto-warn assigned agent + subtle client notification
- PS17: At 100% → auto-escalate to higher tier, change priority to critical, mark breached
- SLA monitoring Celery task: runs every 5 minutes, checks all active SLA timers

**Tests:** ~200 (bulk operations, undo, merge/unmerge, SLA policy CRUD, timer enforcement, breach detection, escalation)
**Push after completion.**

---

### Day 30 — Omnichannel + Customer Identity Resolution (F-052, F-070)
**Gap IDs covered:** F-052, F-070, PS08, PS13, PS14

**Files to build:**
1. `backend/app/services/channel_service.py` — Channel configuration + routing
2. `backend/app/services/customer_service.py` — Customer CRUD + channel linking
3. `backend/app/services/identity_resolution_service.py` — Match customers across channels
4. `backend/app/api/channels.py` — Channel configuration endpoints
5. `backend/app/api/customers.py` — Customer management endpoints
6. `backend/app/api/identity.py` — Identity resolution endpoints

**Channel configuration endpoints (F-052):**
```
GET    /api/v1/channels                   — List available channels
GET    /api/v1/channels/config            — Get company's channel config
PUT    /api/v1/channels/config/:type      — Update channel config (enable/disable, settings)
POST   /api/v1/channels/config/:type/test — Test channel connectivity
```

Channel mechanics:
- System channels: email, chat, sms, voice, social (twitter, instagram, facebook)
- Per-company channel config: enabled/disabled, API keys, webhook URLs, file type limits, char limits
- Auto-create ticket on inbound: configurable per channel
- Channel-specific formatting: character limits, media handling, consent checks
- PS13: Variant down → ticket queued, auto-retry when variant returns, human fallback after 1hr

**Customer endpoints (F-070):**
```
POST   /api/v1/customers                  — Create customer
GET    /api/v1/customers                  — List customers (paginated, searchable)
GET    /api/v1/customers/:id              — Get customer detail
PUT    /api/v1/customers/:id              — Update customer
GET    /api/v1/customers/:id/tickets      — Get customer's tickets
GET    /api/v1/customers/:id/channels     — Get customer's linked channels
POST   /api/v1/customers/:id/channels     — Link channel to customer
DELETE /api/v1/customers/:id/channels/:ch — Unlink channel
POST   /api/v1/customers/merge            — Merge customers (identity resolution)
```

**Identity resolution endpoints (F-070):**
```
POST   /api/v1/identity/resolve           — Resolve identity (email, phone, social_id)
GET    /api/v1/identity/matches           — Get potential duplicate customers
GET    /api/v1/identity/logs              — Get identity match logs
```

Identity resolution mechanics:
- Match by email (exact + fuzzy), phone (exact), social_id (exact)
- Confidence scoring: email=0.9, phone=0.8, social=0.7
- Multiple matches → suggest merge, don't auto-merge
- All match attempts logged in `identity_match_logs`
- PS14: Grandfathered tickets — open tickets retain plan tier at creation, plan_snapshot stored

**PS08: Awaiting client action**
- Status `awaiting_client` when ticket needs client input
- Auto-remind at 24h, gentle nudge at 7d, "Still need help?" at 14d
- No response 14d → status stays open but flagged stale

**Tests:** ~150 (channel config, customer CRUD, identity matching, merging, grandfathering, awaiting client flow)
**Push after completion.**

---

### Day 31 — Notification System + Email Templates (MF05)
**Gap IDs covered:** MF05, PS03, PS10

**Files to build:**
1. `backend/app/services/notification_service.py` — Notification dispatch engine
2. `backend/app/services/notification_template_service.py` — Template management
3. `backend/app/services/notification_preference_service.py` — User preferences
4. `backend/app/api/notifications.py` — Notification endpoints
5. `backend/app/tasks/notification_tasks.py` — Notification Celery tasks
6. `backend/app/templates/emails/ticket_created.html` — Email template
7. `backend/app/templates/emails/ticket_updated.html` — Email template
8. `backend/app/templates/emails/ticket_assigned.html` — Email template
9. `backend/app/templates/emails/ticket_resolved.html` — Email template
10. `backend/app/templates/emails/ticket_closed.html` — Email template
11. `backend/app/templates/emails/ticket_reopened.html` — Email template
12. `backend/app/templates/emails/sla_warning.html` — Email template
13. `backend/app/templates/emails/sla_breached.html` — Email template
14. `backend/app/templates/emails/ticket_escalated.html` — Email template

**Notification endpoints:**
```
GET    /api/v1/notifications/templates      — List notification templates
POST   /api/v1/notifications/templates      — Create custom template
PUT    /api/v1/notifications/templates/:id  — Update template
DELETE /api/v1/notifications/templates/:id  — Delete template
GET    /api/v1/notifications/preferences    — Get user notification preferences
PUT    /api/v1/notifications/preferences    — Update preferences
POST   /api/v1/notifications/send           — Manually trigger notification
GET    /api/v1/notifications/history        — Notification history
```

Notification mechanics:
- Event types: ticket_created, ticket_updated, ticket_assigned, ticket_resolved, ticket_closed, ticket_reopened, sla_warning, sla_breached, ticket_escalated, mention, bulk_action_completed
- Channels: email (via Brevo), in_app (via Socket.io), push (future)
- Per-user preferences: which events to receive, which channel
- CC/BCC support on email notifications
- Digest mode: aggregate notifications into daily/weekly digest
- PS03: "Talk to human" → auto-notify human queue with AI conversation summary
- PS10: Incident mode → mass-notify all affected clients with status updates

**Tests:** ~140 (template CRUD, preference management, notification dispatch, email rendering, Socket.io in-app notifications)
**Push after completion.**

---

### Day 32 — Production Situation Handlers + Ticket State Machine
**Gap IDs covered:** PS01-PS10 (all MUST), PS04 (reopen), PS06 (stale), PS15 (spam), BL09 (test isolation)

**Files to build:**
1. `backend/app/services/ticket_state_machine.py` — Complete state machine with all transitions
2. `backend/app/services/ticket_lifecycle_service.py` — Orchestrates all PS handlers
3. `backend/app/services/stale_ticket_service.py` — PS06: Stale detection + auto-close
4. `backend/app/services/incident_service.py` — PS10: Incident mode management
5. `backend/app/services/spam_detection_service.py` — PS15 + MF21: Spam detection
6. `backend/app/tasks/ticket_lifecycle_tasks.py` — Lifecycle Celery tasks
7. `backend/app/api/ticket_lifecycle.py` — Lifecycle endpoints

**Ticket State Machine — All Valid Transitions:**
```
open → assigned (manual or auto-assign)
open → queued (variant down, PS13)
open → frozen (account suspended, PS07)
open → closed (spam, invalid)

assigned → in_progress (agent starts working)
assigned → awaiting_client (needs client input, PS08)
assigned → awaiting_human (AI can't solve, PS02)
assigned → open (unassigned)

in_progress → awaiting_client (needs client input, PS08)
in_progress → awaiting_human (escalated, PS02/PS03)
in_progress → resolved (issue fixed)

awaiting_client → in_progress (client responded)
awaiting_client → stale (no response 24h+, PS06)
awaiting_client → resolved (auto-resolve if client confirms)

awaiting_human → in_progress (human picks up)
awaiting_human → resolved (human resolves)

resolved → closed (client satisfied, 7-day window)
resolved → reopened (client replies, PS04)

reopened → in_progress (work resumes)
reopened → awaiting_human (reopened >2 times, PS04 auto-escalate)

closed → reopened (within 7-day reopen window, PS04)

frozen → open (account reactivated, PS07)
frozen → closed (frozen >30 days, PS07)

queued → open (variant back online, PS13)
stale → in_progress (agent picks up)
stale → closed (double timeout, PS06)
```

**PS handlers implemented:**
- PS01: Out-of-plan scope — check variant capabilities on create, tag + show upgrade
- PS02: AI can't solve — N attempts → auto-escalate to human, status `awaiting_human`
- PS03: Client asks for human — keyword/button trigger → jump to human queue with AI summary
- PS04: Disputes resolution — reopen flow with count tracking, >2 reopens → auto-escalate
- PS05: Duplicate detection — similarity check on create (Day 26, integrated here)
- PS06: Stale timeout — configurable idle timeout per priority, flag → notify → auto-close
- PS07: Account suspended — reject new, freeze open, thaw on renewal, 30d → auto-close
- PS08: Awaiting client — auto-remind at 24h/7d/14d
- PS09: Attachment limits — enforced in attachment_service (Day 26)
- PS10: Incident mode — system banner, auto-tag, link to master ticket, mass-notify
- PS15: Rate limiting / spam — per-client limits, auto-flag spam, admin alert

**Lifecycle endpoints:**
```
POST   /api/v1/tickets/:id/escalate       — Manual escalate (PS03, PS27)
POST   /api/v1/tickets/:id/reopen         — Reopen ticket (PS04)
POST   /api/v1/tickets/:id/freeze         — Freeze ticket (PS07)
POST   /api/v1/tickets/:id/thaw           — Thaw ticket (PS07)
POST   /api/v1/tickets/:id/spam           — Mark as spam (PS15, MF21)
POST   /api/v1/incidents                  — Create incident (PS10)
GET    /api/v1/incidents                  — List active incidents
POST   /api/v1/incidents/:id/resolve      — Resolve incident
```

**BL09 test isolation fix:** Fix the 22 tests that fail in batch runs but pass individually. Root cause: shared DB state pollution. Fix by ensuring each test uses isolated DB transactions with rollback.

**Tests:** ~250 (state machine transitions — all valid + all invalid, PS handler scenarios, lifecycle tasks, incident management)
**Push after completion.**

---

### Day 33 — SHOULD-HAVE Features: Templates, Triggers, Custom Fields, Collision, Rich Text (MF07-12, PS12, PS16)
**Gap IDs covered:** MF07, MF08, MF09, MF10, MF11, MF12, PS12, PS16

**Files to build:**
1. `backend/app/services/template_service.py` — MF07: Response templates/macros
2. `backend/app/services/trigger_service.py` — MF08: Automated trigger rules engine
3. `backend/app/services/custom_field_service.py` — MF09: Custom ticket fields per category
4. `backend/app/services/collision_service.py` — MF11: Collision detection (concurrent editing)
5. `backend/app/api/ticket_templates.py` — Template endpoints
6. `backend/app/api/triggers.py` — Trigger endpoints
7. `backend/app/api/custom_fields.py` — Custom field endpoints
8. `backend/app/api/collisions.py` — Collision endpoints

**Template/Macro endpoints (MF07):**
```
POST   /api/v1/templates                   — Create response template
GET    /api/v1/templates                   — List templates (filter by category)
GET    /api/v1/templates/:id               — Get template
PUT    /api/v1/templates/:id               — Update template
DELETE /api/v1/templates/:id               — Delete template
POST   /api/v1/tickets/:id/apply-template  — Apply template to ticket
```

**Trigger/Rules endpoints (MF08):**
```
POST   /api/v1/triggers                    — Create trigger rule
GET    /api/v1/triggers                    — List triggers
PUT    /api/v1/triggers/:id                — Update trigger
DELETE /api/v1/triggers/:id                — Delete trigger
PATCH  /api/v1/triggers/:id/toggle         — Enable/disable trigger
GET    /api/v1/triggers/:id/evaluations    — Trigger execution history
```

Trigger engine:
- Condition: field + operator + value (e.g., category=billing AND priority=high)
- Action: change_status, assign_to, send_notification, add_tag, set_priority, escalate
- Trigger events: ticket_created, ticket_updated, message_added, sla_warning, sla_breached
- Max 50 triggers per company (prevent abuse)

**Custom field endpoints (MF09):**
```
POST   /api/v1/custom-fields               — Create custom field
GET    /api/v1/custom-fields               — List custom fields
PUT    /api/v1/custom-fields/:id           — Update custom field
DELETE /api/v1/custom-fields/:id           — Delete custom field
```

Custom field types: text, number, dropdown, multi_select, date, checkbox
Custom fields stored in ticket.metadata_json
Custom field definitions per category (e.g., bug_report has "steps_to_reproduce", billing has "invoice_number")

**Collision detection (MF11):**
```
POST   /api/v1/tickets/:id/viewing         — Mark agent as viewing
DELETE /api/v1/tickets/:id/viewing         — Stop viewing
GET    /api/v1/tickets/:id/viewers         — Get current viewers
```

Collision mechanics:
- Redis: `parwa:{company_id}:ticket_viewing:{ticket_id}` → set of user_ids
- TTL: 5 minutes (auto-expire if user stops interacting)
- On view → check Redis, if others viewing → emit Socket.io event "ticket:collision"
- No hard lock (soft warning only)

**PS12: Ticket deletion/redaction**
- Soft delete: content hidden, metadata kept for audit
- Hard delete: GDPR only, requires admin approval for tickets >30 days
- Message-level redaction: replace content with "[REDACTED]" + audit log

**PS16: Bad feedback auto-review**
- 1-star CSAT → auto-trigger human review, status `feedback_review`
- Track low ratings per variant for quality monitoring

**Tests:** ~170 (templates, triggers, custom fields, collision detection, soft delete, redaction, feedback review)
**Push after completion.**

---

### Day 34 — Ticket Socket.io Events + Celery Tasks + Integration Tests + MF10 Analytics
**Gap IDs covered:** MF10 (analytics dashboard data), BL08 (full audit trail), all Socket.io event wiring

**Files to build:**
1. `backend/app/core/ticket_events.py` — All ticket Socket.io event definitions + emitters
2. `backend/app/tasks/ticket_tasks.py` — COMPLETE rewrite with all ticket Celery tasks
3. `backend/app/services/ticket_analytics_service.py` — MF10: Ticket analytics queries
4. `backend/app/api/ticket_analytics.py` — Analytics endpoints
5. `tests/integration/test_ticket_flow.py` — Full integration test: create → assign → message → resolve → close
6. `tests/integration/test_ticket_ps_handlers.py` — Integration tests for all PS handlers
7. `tests/integration/test_ticket_sla.py` — SLA breach → escalation flow
8. `tests/integration/test_ticket_bulk.py` — Bulk action → undo flow

**Socket.io ticket events (integrated with Day 19 event system):**
```
ticket:created          — New ticket created
ticket:updated          — Ticket fields changed
ticket:status_changed   — Status transition (with old + new)
ticket:assigned         — Ticket assigned to agent
ticket:message_added    — New message on ticket
ticket:note_added       — New internal note
ticket:resolved         — Ticket resolved
ticket:reopened         — Ticket reopened
ticket:closed           — Ticket closed
ticket:escalated        — Ticket escalated to human
ticket:sla_warning      — SLA 75% approaching
ticket:sla_breached     — SLA breached
ticket:collision        — Another agent viewing same ticket
ticket:merged           — Tickets merged
ticket:incident_created — Incident mode activated
ticket:incident_resolved — Incident resolved
```

All events emitted to room `tenant_{company_id}` with payload including ticket_id, actor_id, and relevant data.

**Celery tasks (complete):**
```
# In ticket_tasks.py
classify_ticket(company_id, ticket_id)           — AI classification (stub, Week 9)
score_assignments(company_id, ticket_id)          — Score-based assignment (stub, Week 9)
check_duplicate_ticket(company_id, ticket_id)     — PS05 duplicate detection
run_sla_check(company_id)                          — SLA timer monitoring (every 5 min)
send_sla_warning(company_id, ticket_id)            — PS17 SLA approaching notification
send_sla_breach(company_id, ticket_id)             — PS11 SLA breach notification
check_stale_tickets(company_id)                    — PS06 stale detection (every 30 min)
send_stale_notification(company_id, ticket_id)     — Stale ticket notification
send_awaiting_client_reminder(company_id, ticket_id) — PS08 reminder (every 24h)
detect_spam_tickets(company_id)                    — PS15 spam detection
notify_incident_subscribers(company_id, incident_id) — PS10 incident updates
cleanup_frozen_tickets(company_id)                 — PS07 frozen >30d cleanup (daily)
process_bulk_action(company_id, bulk_action_id)    — Async bulk action processing
index_ticket_for_search(company_id, ticket_id)     — Search index update
```

**Analytics endpoints (MF10):**
```
GET    /api/v1/analytics/tickets/summary    — Total tickets, by status, by priority
GET    /api/v1/analytics/tickets/trends     — Ticket volume over time (daily/weekly/monthly)
GET    /api/v1/analytics/tickets/category   — Distribution by category
GET    /api/v1/analytics/tickets/sla        — SLA compliance rate, avg response time, avg resolution time
GET    /api/v1/analytics/tickets/agents     — Per-agent metrics: tickets handled, avg time, resolution rate
```

**Tests:** ~300 (Socket.io event emission, Celery task execution, analytics queries, 4 integration test suites)
**Push after completion.**

---

### Day 35 — Full Test Suite + BL09 Fix + Documentation + Push
**Gap IDs covered:** BL09 (test isolation), documentation

**Files to build:**
1. `tests/unit/test_ticket_service.py` — Unit tests for all ticket services
2. `tests/unit/test_ticket_state_machine.py` — State machine unit tests
3. `tests/unit/test_sla_service.py` — SLA unit tests
4. `tests/unit/test_notification_service.py` — Notification unit tests
5. `tests/unit/test_bulk_action_service.py` — Bulk action unit tests
6. `tests/unit/test_identity_resolution.py` — Identity resolution unit tests
7. `tests/unit/test_production_situations.py` — PS01-PS10 handler tests
8. `tests/fixtures/ticket_fixtures.py` — Shared test fixtures
9. Update `PROJECT_STATE.md` — Week 4 completion
10. Update `ERROR_LOG.md` — Any errors encountered
11. Update `AGENT_COMMS.md` — Week 4 summary
12. Update `INFRASTRUCTURE_GAPS_TRACKER.md` — Check off all completed items

**BL09 fix:** Fix 22 test isolation failures. Root cause analysis + fix + verify all pass in batch.

**Full regression test run:** Run ALL tests (existing Phase 1 + new Week 4) to ensure nothing breaks.

**Final Week 4 push with all tests green.**

**Tests:** ~200 (comprehensive unit tests, regression verification)
**Push after completion.**

---

## Complete Item Coverage Map

### Original Roadmap Features → Days

| Feature | Day | Status |
|---------|-----|--------|
| F-046: Ticket CRUD | 26, 27 | 🔲 |
| F-047: Detail + Conversation | 27 | 🔲 |
| F-048: Search + Classify | 28 | 🔲 |
| F-049: Classification | 28 | 🔲 |
| F-050: AI Assignment | 28 | 🔲 |
| F-051: Bulk Actions + Merge | 29 | 🔲 |
| F-052: Omnichannel | 30 | 🔲 |
| F-070: Identity Resolution | 30 | 🔲 |

### Code Loopholes → Days

| ID | Description | Day | Status |
|----|-------------|-----|--------|
| BL01 | Table rename sessions→tickets | 24 | ✅ |
| BL02 | 15 missing DB tables (models) | 24 | ✅ Models, 🔲 Migration |
| BL03 | get_db() regression test | 26 | 🔲 |
| BL04 | DECIMAL not FLOAT | 24 | ✅ |
| BL05 | Rate limiting on ticket endpoints | 26 | 🔲 |
| BL06 | Attachment whitelist | 26 | 🔲 |
| BL07 | PII scanning on messages | 26 | 🔲 |
| BL08 | Audit trail for tickets | 27, 34 | 🔲 |
| BL09 | Test isolation (22 failures) | 32, 35 | 🔲 |

### Production Situations → Days

| ID | Description | Day | Status |
|----|-------------|-----|--------|
| PS01 | Out-of-plan scope | 26, 32 | 🔲 |
| PS02 | AI can't solve | 32 | 🔲 |
| PS03 | Client asks for human | 31, 32 | 🔲 |
| PS04 | Disputes/reopen | 32 | 🔲 |
| PS05 | Duplicate detection | 26 | 🔲 |
| PS06 | Stale ticket timeout | 32 | 🔲 |
| PS07 | Account suspended/frozen | 26, 32 | 🔲 |
| PS08 | Awaiting client action | 30, 32 | 🔲 |
| PS09 | Attachment limits | 26 | 🔲 |
| PS10 | Incident mode | 31, 32 | 🔲 |
| PS11 | SLA breach | 29 | 🔲 |
| PS12 | Deletion/redaction | 33 | 🔲 |
| PS13 | Variant down | 30 | 🔲 |
| PS14 | Plan downgrade | 30 | 🔲 |
| PS15 | Rate limiting/spam | 26, 32 | 🔲 |
| PS16 | Bad feedback | 33 | 🔲 |
| PS17 | SLA approaching | 29 | 🔲 |
| PS18 | Credit limits | DEFER | — |
| PS19 | Cross-variant | 24 (model) | ✅ Column only |
| PS20 | Conflicting AI info | DEFER | — |
| PS21 | Recurring issues | DEFER | — |
| PS22 | Trial limits | DEFER | — |
| PS23 | Timezone SLA | 24 (model) | ✅ Column only |
| PS24 | Unauthorized source | DEFER | — |
| PS25 | Variant update mid-ticket | 24 (model) | ✅ Column only |
| PS26 | Merge mistakes | 29 | 🔲 |
| PS27 | Manager escalation | 24 (model), 32 | ✅ Column, 🔲 Handler |
| PS28 | Multi-language | DEFER | — |
| PS29 | Sensitive data | 26 | 🔲 |

### Missing Features → Days

| ID | Feature | Day | Status |
|----|---------|-----|--------|
| MF01 | Priority System | 24, 26 | ✅ Enum, 🔲 Logic |
| MF02 | Categories/Departments | 24, 26 | ✅ Enum, 🔲 Logic |
| MF03 | Tags/Labels | 24, 26 | ✅ Column, 🔲 Logic |
| MF04 | Activity Log/Timeline | 27 | 🔲 |
| MF05 | Email Notifications | 31 | 🔲 |
| MF06 | SLA Management | 29 | 🔲 |
| MF07 | Templates/Macros | 33 | 🔲 |
| MF08 | Automated Triggers | 33 | 🔲 |
| MF09 | Custom Fields | 33 | 🔲 |
| MF10 | Analytics Dashboard | 34 | 🔲 |
| MF11 | Collision Detection | 33 | 🔲 |
| MF12 | Rich Text/Markdown | 33 | 🔲 |
| MF13 | CSAT/NPS | 24 (model) | ✅ Table, 🔲 Logic |
| MF14 | Watchers | DEFER | — |
| MF15 | @Mentions | DEFER | — |
| MF16 | Export | DEFER | — |
| MF17 | KB Suggestions | DEFER (Week 8+) | — |
| MF18 | Sharing | DEFER | — |
| MF19 | Approval Workflow | DEFER (Week 7) | — |
| MF20 | Internal Knowledge | DEFER | — |
| MF21 | Spam Moderation | 32, 33 | 🔲 |
| MF22 | Client Portal | DEFER (frontend) | — |
| MF23 | Ticket Linking | 24 (model) | ✅ Column only |
| MF24 | Transfer Between Accounts | DEFER | — |

---

## Daily Build Pattern

Each day follows this pattern:
1. Read `PROJECT_STATE.md` + `AGENT_COMMS.md` + `ERROR_LOG.md`
2. Build all files listed for that day
3. Write tests for everything built
4. Run `pytest tests/unit/` — all pass
5. Run `black` + `flake8` — clean
6. Commit + push
7. Update `PROJECT_STATE.md` with day's progress
8. Append to `AGENT_COMMS.md` with day's work summary
9. Append to `ERROR_LOG.md` with any errors found/fixed

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total days | 12 (Day 24 done, Days 25-35 remaining) |
| Original roadmap features | 8 (F-046→F-052, F-070) |
| Code loophole fixes | 9 (BL01-BL09) |
| Production situation handlers | 17 built, 12 deferred |
| Missing features built | 13 full, 4 partial (table only), 7 deferred |
| New API endpoints | ~80 |
| New service files | ~20 |
| New schema files | ~8 |
| New Celery task files | ~4 |
| Email templates | 8 |
| Socket.io events | 17 |
| Estimated tests | ~2,200 |
| Files to create/modify | ~100 |

---

**END OF WEEK 4 ROADMAP**
