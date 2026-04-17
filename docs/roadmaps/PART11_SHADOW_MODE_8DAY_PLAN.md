# Shadow Mode — 8-Day Production Roadmap

> **Created:** April 17, 2026
> **Part:** Part 11 (Shadow Mode)
> **Priority:** P2 — Critical for Safe Launch
> **Current Status:** ~30% complete (backend service + models built, wiring needed)
> **Dependencies:** Part 12 (Dashboard), Part 14 (Channels), Part 13 (Tickets), Part 10 (Jarvis)

---

## EXECUTIVE SUMMARY

Shadow Mode is PARWA's safety system that controls how Jarvis executes actions. This 8-day plan covers **ALL integration points** identified in the architecture:

| # | Integration Point | Day(s) | Priority |
|---|-------------------|--------|----------|
| 1 | Backend Service Completion | Day 1 | P0 |
| 2 | Channel Interceptors (Email/SMS/Voice/Chat) | Day 2 | P0 |
| 3 | Ticket Management Integration | Day 3 | P0 |
| 4 | Dashboard Frontend (Approvals, Undo, Log) | Day 4-5 | P0 |
| 5 | Jarvis Commands & Dual Control | Day 6 | P1 |
| 6 | Onboarding Stage 0 Enforcer | Day 7 | P1 |
| 7 | Testing, Polish & Documentation | Day 8 | P1 |

---

## PREREQUISITES (Already Built)

| Component | Status | File |
|-----------|--------|------|
| `shadow_log` table | ✅ Done | `database/models/shadow_mode.py` |
| `shadow_preferences` table | ✅ Done | `database/models/shadow_mode.py` |
| `undo_log` table | ✅ Done | `database/models/approval.py` |
| `system_mode` column on Company | ✅ Done | Migration 026 |
| ShadowModeService (4-layer decision) | ✅ Done | `backend/app/services/shadow_mode_service.py` |
| Shadow API Routes (11 endpoints) | ✅ Done | `backend/app/api/shadow.py` |
| Approvals Bridge API (6 endpoints) | ✅ Done | `backend/app/api/approvals.py` |
| Jarvis Knowledge File | ✅ Done | `backend/app/data/jarvis_knowledge/11_shadow_mode.json` |

---

## DAY 1 — Backend Service Completion & Testing

### Goal
Ensure all backend services are production-ready, wire missing dependencies, add comprehensive tests.

### Morning: Service Hardening (4 hours)

#### B1.1 — Add Undo Window Configuration
- [ ] Add `undo_window_minutes` column to `companies` table (default: 30)
- [ ] Add `undo_window_minutes` to ShadowModeService.undo_auto_approved_action()
- [ ] Validate undo is within window before allowing

#### B1.2 — Add Risk Threshold Configuration
- [ ] Add `risk_threshold_shadow` column to `companies` (default: 0.7)
- [ ] Add `risk_threshold_auto` column to `companies` (default: 0.3)
- [ ] Use these thresholds in evaluate_action_risk() instead of hardcoded values

#### B1.3 — Wire Socket.io Events
- [ ] Import emitter in shadow_mode_service.py
- [ ] Emit `shadow:action_logged` when action is logged
- [ ] Emit `shadow:action_approved` when approved
- [ ] Emit `shadow:action_rejected` when rejected
- [ ] Emit `shadow:action_undone` when undone
- [ ] Emit `shadow:mode_changed` when company mode changes
- [ ] Emit `shadow:preference_changed` when preference updated

### Afternoon: Comprehensive Tests (4 hours)

#### B1.4 — Unit Tests
- [ ] Test evaluate_action_risk() for all 14 action types
- [ ] Test Layer 1: Heuristic scoring with payload adjustments
- [ ] Test Layer 2: Preference override
- [ ] Test Layer 3: Historical pattern escalation
- [ ] Test Layer 4: Hard safety floor enforcement
- [ ] Test approve/reject/undo flows
- [ ] Test batch resolution
- [ ] Test preference CRUD operations

#### B1.5 — Integration Tests
- [ ] Test full flow: log → approve → execute → undo
- [ ] Test Socket.io event emission
- [ ] Test company isolation (BC-001 enforcement)

### Deliverables Day 1
- [ ] 2 new columns on companies table (undo_window, risk_thresholds)
- [ ] 6 Socket.io events wired
- [ ] 15+ unit tests passing
- [ ] 3+ integration tests passing

---

## DAY 2 — Channel Interceptors (Email/SMS/Voice/Chat)

### Goal
Wire Shadow Mode evaluation into ALL outbound communication channels.

### Morning: Email Channel (3 hours)

#### B2.1 — Email Outbound Interceptor
**File:** `backend/app/services/email_channel_service.py`

- [ ] Create `evaluate_email_shadow()` function
- [ ] Call `shadow_service.evaluate_action_risk("email_reply", payload)`
- [ ] If requires_approval: save to shadow_log, return pending status
- [ ] If auto_execute: send email + log to undo queue
- [ ] Add shadow_status field to OutboundEmail model

#### B2.2 — Email Shadow Hold Queue
- [ ] Create `email_shadow_queue` table (id, email_data, shadow_log_id, created_at)
- [ ] When email is in shadow: save to queue, don't send
- [ ] When approved: fetch from queue, send via Brevo
- [ ] When rejected: delete from queue, log rejection

### Midday: SMS Channel (2 hours)

#### B2.3 — SMS Outbound Interceptor
**File:** `backend/app/services/sms_channel_service.py`

- [ ] Create `evaluate_sms_shadow()` function
- [ ] Call `shadow_service.evaluate_action_risk("sms_reply", payload)`
- [ ] If requires_approval: save to shadow_log, return pending
- [ ] If auto_execute: send SMS + log to undo queue
- [ ] Add shadow_status to SMSMessage model

#### B2.4 — SMS Shadow Hold Queue
- [ ] Create `sms_shadow_queue` table
- [ ] Same flow as email shadow queue

### Afternoon: Voice & Chat Channels (3 hours)

#### B2.5 — Voice Channel Interceptor
**File:** `backend/app/services/voice_service.py`

- [ ] Create `evaluate_voice_shadow()` function
- [ ] Intercept before TTS plays to customer
- [ ] If shadow: play "please hold" message, alert manager
- [ ] Add shadow_status to VoiceCall model

#### B2.6 — Chat Widget Interceptor
**File:** `backend/app/services/chat_widget_service.py`

- [ ] Create `evaluate_chat_shadow()` function
- [ ] Intercept before Socket.io emit to customer
- [ ] If shadow: show typing indicator, don't send message
- [ ] Add shadow_status to ChatMessage model

### Deliverables Day 2
- [ ] 4 channel interceptors (email, sms, voice, chat)
- [ ] 2 shadow hold queue tables (email, sms)
- [ ] 4 model updates with shadow_status field
- [ ] All interceptors call evaluate_action_risk()

---

## DAY 3 — Ticket Management Integration

### Goal
Add Shadow Mode fields to tickets, wire approval flow to ticket resolution.

### Morning: Database Schema (2 hours)

#### B3.1 — Ticket Shadow Fields Migration
**File:** `database/alembic/versions/027_ticket_shadow_fields.py`

```sql
ALTER TABLE tickets ADD COLUMN shadow_status VARCHAR(20) DEFAULT 'none';
ALTER TABLE tickets ADD COLUMN risk_score FLOAT DEFAULT NULL;
ALTER TABLE tickets ADD COLUMN approved_by VARCHAR(36) DEFAULT NULL;
ALTER TABLE tickets ADD COLUMN approved_at TIMESTAMP DEFAULT NULL;
ALTER TABLE tickets ADD COLUMN shadow_log_id VARCHAR(36) REFERENCES shadow_log(id);
```

- [ ] Create migration with 5 new columns
- [ ] Add to Ticket model in `database/models/tickets.py`

#### B3.2 — Shadow Status Enum
- [ ] Add ShadowStatus enum: none, pending_approval, approved, rejected, auto_approved, undone
- [ ] Add color coding helper: red (< 0.5), yellow (0.5-0.8), green (> 0.8)

### Midday: Ticket Service Integration (3 hours)

#### B3.3 — AI Resolution Shadow Flow
**File:** `backend/app/services/ticket_service.py`

- [ ] In `resolve_ticket_with_ai()`: call shadow evaluation BEFORE executing resolution
- [ ] If shadow: save ticket in pending state, create shadow_log entry
- [ ] If supervised/graduated with low risk: auto-resolve + add to undo queue
- [ ] If high risk: require approval

#### B3.4 — Ticket Approval Flow
- [ ] Add `approve_ticket_resolution()` method
- [ ] Called when shadow action is approved
- [ ] Updates ticket.status to resolved
- [ ] Sets approved_by, approved_at, shadow_status

#### B3.5 — Ticket Undo Flow
- [ ] Add `undo_ticket_resolution()` method
- [ ] Reopens ticket
- [ ] Sets shadow_status to 'undone'
- [ ] Logs to undo_log

### Afternoon: API & Frontend Types (3 hours)

#### B3.6 — Ticket API Updates
**File:** `backend/app/api/tickets.py`

- [ ] Add `GET /api/tickets?shadow_status=pending_approval` filter
- [ ] Add `POST /api/tickets/{id}/approve` endpoint
- [ ] Add `POST /api/tickets/{id}/undo-resolution` endpoint
- [ ] Add `GET /api/tickets/{id}/shadow-details` endpoint

#### B3.7 — Frontend Types
**File:** `frontend/types/ticket.ts`

- [ ] Add shadow_status field to Ticket type
- [ ] Add risk_score field
- [ ] Add shadow_details interface

### Deliverables Day 3
- [ ] Migration with 5 new columns
- [ ] Ticket model updated
- [ ] 3 new service methods (resolve_shadow, approve, undo)
- [ ] 4 new API endpoints
- [ ] Frontend types updated

---

## DAY 4 — Dashboard Frontend: Approvals Queue

### Goal
Build the complete Approvals Queue page with real-time updates.

### Morning: API Client & Types (2 hours)

#### B4.1 — Shadow Mode API Client
**File:** `frontend/lib/shadow-api.ts`

```typescript
// Types
interface ShadowLogEntry {
  id: string;
  company_id: string;
  action_type: string;
  action_payload: Record<string, any>;
  jarvis_risk_score: number;
  mode: 'shadow' | 'supervised' | 'graduated';
  manager_decision: 'approved' | 'rejected' | 'modified' | null;
  manager_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

interface ShadowPreferences {
  action_category: string;
  preferred_mode: string;
  set_via: 'ui' | 'jarvis';
}

interface ShadowStats {
  total_actions: number;
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  approval_rate: number;
  avg_risk_score: number;
}

// API Functions
- getShadowMode(): Promise<string>
- setShadowMode(mode: string, setVia: string): Promise<void>
- getShadowPreferences(): Promise<ShadowPreferences[]>
- setShadowPreference(category: string, mode: string, setVia: string): Promise<void>
- getShadowLog(filters, page): Promise<PaginatedResponse<ShadowLogEntry>>
- getShadowStats(): Promise<ShadowStats>
- evaluateActionRisk(actionType: string, payload: any): Promise<RiskEvaluation>
- approveShadowAction(id: string, note?: string): Promise<void>
- rejectShadowAction(id: string, note?: string): Promise<void>
- undoShadowAction(id: string, reason: string): Promise<void>
- batchResolve(ids: string[], decision: string, note?: string): Promise<void>
```

- [ ] Create shadow-api.ts with 12+ API functions
- [ ] Create all TypeScript interfaces
- [ ] Add error handling

### Midday: Approvals Queue Page (3 hours)

#### B4.2 — Approvals Queue Page
**File:** `frontend/app/dashboard/approvals/page.tsx`

**Features:**
- [ ] Page header with pending count badge
- [ ] Stats strip: pending, today's approved, today's rejected, avg risk
- [ ] Filter bar: action type dropdown, risk level (high/medium/low), date range
- [ ] Approvals list: each item shows:
  - Action type icon (refund/sms/email/ticket/etc)
  - Action description (smart summary from payload)
  - Risk score with color-coded indicator
  - AI recommendation text
  - Timestamp (relative)
  - Mode badge (shadow/supervised/graduated)
- [ ] Action buttons per item: Approve, Reject, View Details
- [ ] Batch selection checkbox
- [ ] Batch action bar: "Approve Selected", "Reject Selected"
- [ ] "Approve All Low Risk" button (risk < 0.3)
- [ ] Real-time updates via Socket.io (new items appear automatically)
- [ ] Loading skeleton, empty state, error state

### Afternoon: Approval Detail Modal (3 hours)

#### B4.3 — Approval Detail Modal
**File:** `frontend/components/dashboard/ApprovalDetailModal.tsx`

**Features:**
- [ ] Full action payload viewer (JSON pretty-print)
- [ ] 4-Layer decision breakdown:
  - Layer 1: Heuristic score + reason
  - Layer 2: Preference override (if any)
  - Layer 3: Historical pattern
  - Layer 4: Safety floor status
- [ ] Risk score visualization (gauge/progress bar)
- [ ] Customer context (if ticket-related)
- [ ] Related ticket/conversation link
- [ ] Approve/Reject buttons with note input
- [ ] "Escalate to Shadow" button (change mode to shadow)

#### B4.4 — Socket.io Integration
- [ ] Listen to `shadow:action_logged` event → add to queue
- [ ] Listen to `shadow:action_approved` event → remove from queue, show toast
- [ ] Listen to `shadow:action_rejected` event → remove from queue, show toast
- [ ] Listen to `shadow:mode_changed` event → update mode badge

### Deliverables Day 4
- [ ] shadow-api.ts with 12+ functions
- [ ] Approvals queue page (full page)
- [ ] Approval detail modal
- [ ] Real-time Socket.io updates

---

## DAY 5 — Dashboard Frontend: Undo, Log & Settings

### Goal
Build Undo Interface, Shadow Log audit trail, and Settings panel.

### Morning: Undo Interface (2 hours)

#### B5.1 — Undo Queue Component
**File:** `frontend/components/dashboard/UndoQueue.tsx`

**Features:**
- [ ] List of auto-approved actions within undo window
- [ ] Each item shows:
  - Action type + description
  - Executed timestamp
  - Undo countdown timer (e.g., "24 min left")
  - Risk score badge
- [ ] "Undo" button per item
- [ ] Undo confirmation modal with reason input
- [ ] After undo: show what was rolled back
- [ ] Empty state: "No actions available for undo"

#### B5.2 — Undo History
**File:** `frontend/components/dashboard/UndoHistory.tsx`

- [ ] List of past undos
- [ ] Each shows: original action, undo reason, undone by, timestamp
- [ ] Filter by date range
- [ ] Export to CSV

### Midday: Shadow Log Audit Trail (3 hours)

#### B5.3 — Shadow Log Page
**File:** `frontend/app/dashboard/shadow-log/page.tsx`

**Features:**
- [ ] Full-page audit trail
- [ ] Table columns: Timestamp, Action Type, Mode, Risk Score, AI Recommendation, Decision, Outcome, Manager Note
- [ ] Filters:
  - Action type dropdown (14 options)
  - Mode dropdown (shadow/supervised/graduated)
  - Decision dropdown (pending/approved/rejected/undone)
  - Date range picker
- [ ] Search: full-text search in action_payload
- [ ] Pagination (20 per page)
- [ ] Export to CSV button
- [ ] Charts:
  - Approval rate over time (line chart)
  - Risk distribution (histogram)
  - Action type breakdown (pie chart)
- [ ] Click row → expand to see full payload
- [ ] Link to related ticket/customer if applicable

### Afternoon: Settings Panel (3 hours)

#### B5.4 — Shadow Mode Settings
**File:** `frontend/app/dashboard/settings/shadow-mode/page.tsx`

**Features:**
- [ ] Global mode selector: Shadow / Supervised / Graduated
- [ ] Mode descriptions with visual indicators
- [ ] Per-action-category preferences table:
  | Category | Current Mode | Set Via | Last Updated | Actions |
  |----------|-------------|---------|--------------|---------|
  | Refunds | Shadow | UI | 2h ago | Edit/Delete |
  | SMS | Graduated | Jarvis | 1d ago | Edit/Delete |
  | Email | Supervised | UI | 3d ago | Edit/Delete |
- [ ] Add preference modal (category dropdown, mode selector)
- [ ] "Reset to Default" button
- [ ] Undo window duration setting (5/15/30/60 minutes)
- [ ] Risk threshold sliders:
  - "Force shadow above risk:" (default 0.7)
  - "Auto-execute below risk:" (default 0.3)
- [ ] All changes sync to Jarvis in real-time
- [ ] "What-If Simulator" section:
  - Input: action type + payload
  - Output: predicted risk score + mode + reasoning

### Deliverables Day 5
- [ ] Undo queue component with countdown
- [ ] Undo history component
- [ ] Shadow log page with charts
- [ ] Shadow mode settings page
- [ ] What-if simulator

---

## DAY 6 — Jarvis Commands & Dual Control

### Goal
Wire Shadow Mode commands into Jarvis, implement dual control sync.

### Morning: Jarvis Command Handlers (4 hours)

#### B6.1 — Shadow Mode Commands
**File:** `backend/app/services/jarvis_service.py`

**Commands to implement:**

| Command | Action | Response |
|---------|--------|----------|
| "put [action] in shadow mode" | set_shadow_preference(action, 'shadow', 'jarvis') | "Done. [Action] will now require approval." |
| "put [action] in supervised mode" | set_shadow_preference(action, 'supervised', 'jarvis') | "Done. [Action] will use supervised mode." |
| "put [action] in graduated mode" | set_shadow_preference(action, 'graduated', 'jarvis') | "Done. [Action] will auto-execute low risk." |
| "show me pending approvals" | get_pending_count() + list pending | "You have 5 pending approvals. The first is..." |
| "approve the last [action]" | approve latest pending by type | "Approved. The [action] has been executed." |
| "reject the last [action]" | reject latest pending by type | "Rejected. The [action] was cancelled." |
| "always ask me before [action]" | set_shadow_preference(action, 'shadow', 'jarvis') | "Understood. I'll always ask before [action]." |
| "switch to [mode] mode" | set_company_mode(mode, 'jarvis') | "Done. System is now in [mode] mode." |
| "undo the last [action]" | undo latest auto-approved by type | "Undone. The [action] has been reversed." |
| "what is my current shadow mode?" | get_company_mode() + get_preferences() | "You're in [mode] mode. Preferences: ..." |
| "why was this action put in shadow?" | get latest shadow_log + explain layers | "That action was shadowed because..." |
| "show me the undo queue" | list undo-available actions | "You have 3 actions that can be undone..." |

- [ ] Add 12+ command handlers to Jarvis command parser
- [ ] Map natural language variations (regex patterns)
- [ ] Add to jarvis_knowledge service

### Midday: Dual Control Sync (2 hours)

#### B6.2 — UI → Jarvis Sync
- [ ] When preference changed via UI: emit Socket event to Jarvis
- [ ] Jarvis receives event, updates context_json
- [ ] Jarvis acknowledges in chat: "I noticed you changed [action] to [mode]"

#### B6.3 — Jarvis → UI Sync
- [ ] When preference changed via Jarvis: emit Socket event to UI
- [ ] Frontend settings page receives event, updates UI in real-time
- [ ] Show toast: "Shadow mode updated via Jarvis"

### Afternoon: Jarvis Context Integration (2 hours)

#### B6.4 — Jarvis Context Updates
**File:** `backend/app/services/jarvis_service.py`

- [ ] Add ShadowModeContext to JarvisContext type:
  ```typescript
  interface ShadowModeContext {
    current_mode: string;
    client_preferences: Record<string, string>;
    pending_approvals_count: number;
    recent_shadow_actions: Array<{...}>;
    undo_available_count: number;
    learned_patterns: string[];
  }
  ```
- [ ] Load shadow context on every Jarvis request
- [ ] Include in system prompt: current mode, pending count, recent patterns

#### B6.5 — Jarvis Shadow Card
**File:** `frontend/components/jarvis/ShadowModeCard.tsx`

- [ ] Visual card showing current mode with color badge
- [ ] Quick action buttons: "View Approvals", "Change Mode"
- [ ] Pending count indicator
- [ ] Last action summary

### Deliverables Day 6
- [ ] 12+ Jarvis command handlers
- [ ] Dual control sync (UI ↔ Jarvis)
- [ ] ShadowModeContext in Jarvis context
- [ ] Shadow mode card component

---

## DAY 7 — Onboarding Stage 0 Enforcer

### Goal
Force all new clients into Shadow Mode for first N actions.

### Morning: Onboarding Integration (3 hours)

#### B7.1 — Stage 0 Shadow Enforcement
**File:** `backend/app/services/onboarding_service.py`

- [ ] New field: `onboarding_progress.shadow_actions_remaining` (default: 10)
- [ ] In `evaluate_action_risk()`: check if shadow_actions_remaining > 0
- [ ] If yes: ALWAYS return mode='shadow', decrement counter
- [ ] Decrement happens AFTER manager approval (not just logging)

#### B7.2 — Onboarding Flow Updates
- [ ] Add Shadow Mode explanation step to onboarding
- [ ] Step content: video/gif explaining shadow mode
- [ ] "Why am I in Shadow Mode?" explanation
- [ ] Progress indicator: "7 of 10 shadow actions remaining"
- [ ] Auto-graduation message: "Congratulations! You've graduated to Supervised mode."

### Midday: Onboarding UI (3 hours)

#### B7.3 — Shadow Mode Onboarding Component
**File:** `frontend/components/onboarding/ShadowModeStep.tsx`

**Features:**
- [ ] Animated explanation of Shadow Mode
- [ ] Visual: "You're in the driver's seat" metaphor
- [ ] Progress bar: "X actions until graduation"
- [ ] Sample actions preview (what you'll approve)
- [ ] "Skip explanation" option

#### B7.4 — Graduation Celebration
**File:** `frontend/components/onboarding/ShadowGraduationModal.tsx`

- [ ] Confetti animation
- [ ] "You've graduated to Supervised mode!"
- [ ] Explanation of what changed
- [ ] Option to stay in Shadow mode longer
- [ ] "Continue" button

### Afternoon: Hard Safety Floor Display (2 hours)

#### B7.5 — Safety Floor UI Indicator
- [ ] In approvals queue: show "Safety Floor" badge for mandatory-approval actions
- [ ] In settings: list actions that are ALWAYS supervised
- [ ] Tooltip explaining why certain actions can't be auto-approved

### Deliverables Day 7
- [ ] Stage 0 enforcement logic
- [ ] Shadow actions remaining counter
- [ ] Onboarding step component
- [ ] Graduation celebration modal
- [ ] Safety floor indicators

---

## DAY 8 — Testing, Polish & Documentation

### Goal
Comprehensive testing, bug fixes, performance optimization, documentation.

### Morning: End-to-End Testing (4 hours)

#### B8.1 — E2E Test Scenarios

| Scenario | Steps | Expected Result |
|----------|-------|-----------------|
| New client shadow flow | Sign up → first action → approve → graduation | 10 actions, then supervised |
| Email shadow hold | AI drafts email → shadow → manager approves → email sent | Email in queue, then sent |
| SMS auto-execute | Supervised mode → low risk SMS → auto-send | SMS sent, in undo queue |
| Ticket resolution shadow | AI resolves ticket → shadow → approve → resolved | Ticket status changes |
| Jarvis command | "put refunds in shadow" → check UI | Preference synced |
| Undo action | Auto-approved → undo within window → rolled back | Action reversed |
| Batch approve | Select 5 → batch approve → all executed | 5 approved at once |
| Safety floor | Try to auto-approve account_delete → blocked | Requires approval |

- [ ] Write Cypress/Playwright tests for 8+ scenarios
- [ ] Test all 4 channels (email, SMS, voice, chat)
- [ ] Test Socket.io real-time updates
- [ ] Test dual control sync

### Midday: Performance & Bug Fixes (2 hours)

#### B8.2 — Performance Optimizations
- [ ] Add database indexes for shadow_log queries
- [ ] Add Redis caching for shadow_preferences (TTL: 5 min)
- [ ] Optimize shadow_log table partitioning by month
- [ ] Add rate limiting on shadow evaluation endpoint

#### B8.3 — Bug Sweep
- [ ] Fix any race conditions in dual control sync
- [ ] Fix timezone issues in undo window countdown
- [ ] Fix edge cases: empty action_payload, null risk_score
- [ ] Fix Socket.io reconnection handling

### Afternoon: Documentation (2 hours)

#### B8.4 — Developer Documentation
**File:** `docs/architecture/SHADOW_MODE_ARCHITECTURE.md`

- [ ] System overview diagram
- [ ] 4-layer decision flow chart
- [ ] API endpoint documentation
- [ ] Database schema documentation
- [ ] Channel interceptor implementation guide

#### B8.5 — User Documentation
**File:** `docs/user-guide/SHADOW_MODE_GUIDE.md`

- [ ] What is Shadow Mode?
- [ ] Mode comparison table
- [ ] How to use the Approvals Queue
- [ ] How to configure preferences
- [ ] Jarvis commands reference
- [ ] FAQ

### Deliverables Day 8
- [ ] 8+ E2E test scenarios passing
- [ ] Performance optimizations deployed
- [ ] Bug fixes for edge cases
- [ ] Developer documentation complete
- [ ] User guide complete

---

## SUMMARY TABLE — All 8 Days

| Day | Focus | Frontend | Backend | Priority |
|-----|-------|----------|---------|----------|
| 1 | Backend Completion | - | Service hardening, tests, Socket.io | P0 |
| 2 | Channel Interceptors | - | Email/SMS/Voice/Chat shadow middleware | P0 |
| 3 | Ticket Integration | Types, model updates | Ticket shadow fields, flows | P0 |
| 4 | Approvals Queue UI | Full page + modal + Socket | - | P0 |
| 5 | Undo, Log, Settings | 3 pages + components | - | P0 |
| 6 | Jarvis Commands | Shadow card, sync | 12+ command handlers, context | P1 |
| 7 | Onboarding | Onboarding step, graduation | Stage 0 enforcement | P1 |
| 8 | Testing & Docs | E2E tests | Performance, docs | P1 |

---

## FILES TO CREATE/MODIFY

### New Files (25+)

**Backend:**
- `backend/app/interceptors/shadow_interceptor.py` — Base interceptor class
- `backend/app/interceptors/email_shadow.py` — Email shadow middleware
- `backend/app/interceptors/sms_shadow.py` — SMS shadow middleware
- `backend/app/interceptors/voice_shadow.py` — Voice shadow middleware
- `backend/app/interceptors/chat_shadow.py` — Chat shadow middleware
- `database/alembic/versions/027_ticket_shadow_fields.py` — Migration
- `backend/tests/test_shadow_mode_e2e.py` — E2E tests

**Frontend:**
- `frontend/lib/shadow-api.ts` — API client
- `frontend/app/dashboard/approvals/page.tsx` — Approvals queue
- `frontend/app/dashboard/shadow-log/page.tsx` — Audit trail
- `frontend/app/dashboard/settings/shadow-mode/page.tsx` — Settings
- `frontend/components/dashboard/ApprovalDetailModal.tsx` — Modal
- `frontend/components/dashboard/UndoQueue.tsx` — Undo component
- `frontend/components/dashboard/UndoHistory.tsx` — Undo history
- `frontend/components/dashboard/RiskScoreIndicator.tsx` — Visual indicator
- `frontend/components/dashboard/WhatIfSimulator.tsx` — Simulator
- `frontend/components/onboarding/ShadowModeStep.tsx` — Onboarding step
- `frontend/components/onboarding/ShadowGraduationModal.tsx` — Celebration
- `frontend/components/jarvis/ShadowModeCard.tsx` — Jarvis card

**Docs:**
- `docs/architecture/SHADOW_MODE_ARCHITECTURE.md`
- `docs/user-guide/SHADOW_MODE_GUIDE.md`

### Modified Files (15+)

- `backend/app/services/shadow_mode_service.py` — Add Socket.io, config columns
- `backend/app/services/email_channel_service.py` — Add interceptor
- `backend/app/services/sms_channel_service.py` — Add interceptor
- `backend/app/services/voice_service.py` — Add interceptor
- `backend/app/services/chat_widget_service.py` — Add interceptor
- `backend/app/services/ticket_service.py` — Shadow flows
- `backend/app/services/jarvis_service.py` — Commands + context
- `backend/app/services/onboarding_service.py` — Stage 0 enforcement
- `backend/app/api/tickets.py` — New endpoints
- `database/models/tickets.py` — New columns
- `frontend/app/dashboard/layout.tsx` — Add shadow badge
- `frontend/components/dashboard/DashboardSidebar.tsx` — Nav items
- `frontend/types/ticket.ts` — New types
- `backend/app/core/events.py` — Socket event types
- `backend/app/main.py` — Register any new routers

---

## RISK ASSESSMENT

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Channel interceptor causes message delays | Medium | High | Async processing, timeout limits |
| Socket.io events dropped | Medium | Medium | Fallback polling, retry logic |
| Undo window race conditions | Low | High | DB transactions, locking |
| Jarvis command parsing errors | Medium | Low | Fallback to "I don't understand" |
| Stage 0 counter gets out of sync | Low | Medium | Recalculate from shadow_log |

---

## SUCCESS CRITERIA

After Day 8, Shadow Mode is production-ready when:

- [ ] ALL new clients start in Shadow mode (Stage 0)
- [ ] Managers can approve/reject actions from Dashboard
- [ ] Managers can approve/reject via Jarvis commands
- [ ] All 4 channels intercept outbound messages
- [ ] Tickets have shadow status and risk scores
- [ ] Undo window works for auto-approved actions
- [ ] Hard safety floor blocks auto-approve for critical actions
- [ ] UI and Jarvis preferences stay in sync
- [ ] Real-time updates via Socket.io
- [ ] All E2E tests passing
- [ ] Documentation complete

---

## LOCKED DECISIONS (From Architecture)

| # | Decision | Rule |
|---|----------|------|
| SM-1 | Dual control is mandatory | UI panel AND Jarvis must both work |
| SM-2 | Per-action, not per-channel | Shadow mode is decided per individual action |
| SM-3 | Jarvis decides, client overrides | Jarvis assesses risk first, preference wins if set |
| SM-4 | Undo is always available in Graduated | Auto-approved actions can be undone |
| SM-5 | Hard safety floor is non-negotiable | Irreversible actions ALWAYS require approval |
| SM-6 | UI and Jarvis sync in real-time | Changes in one instantly reflect in the other |
| SM-7 | Transparent reasoning | Jarvis always explains WHY action was shadowed |
| SM-8 | New clients start in Shadow (Stage 0) | First N actions always shadow |
| SM-9 | All outbound messages intercepted | Every channel passes through shadow middleware |

---

*End of Shadow Mode 8-Day Roadmap*
