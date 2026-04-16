# Shadow Mode Additions — 3 Extra Days

> **Created:** April 16, 2026
> **Source:** Architecture discussion with Abhay — Shadow Mode redesign
> **Status:** PLANNING — Not yet built, tracked for future implementation
> **Applies To:** Part 11 (Shadow Mode) + Part 12 (Dashboard) + Jarvis Context

---

## Background

During the Shadow Mode architecture discussion, the original plan was redesigned. The old plan had a complex per-channel/per-task-type config UI. The new approach is fundamentally different:

**Old approach:** Fixed per-channel or per-task-type shadow assignment (SMS always shadow, email always auto, etc.)

**New approach:** Jarvis decides per-action based on risk/confidence. Both UI panel AND Jarvis (conversational) control shadow mode. They sync to the same backend. Auto-approved actions can be UNDONE.

---

## The 3 Additions (3 Extra Days)

### Addition 1: Dual Control System (Day 1 of 3)

**What:** Both the Dashboard UI panel AND Jarvis conversational chat can control shadow mode settings. They are two interfaces to the same backend — changes in one reflect in the other instantly.

**Architecture — 4-Layer Decision System:**

```
Layer 1: Jarvis AI Risk Assessment (top)
  └─ Jarvis evaluates: "Is this action risky? Am I confident?"
  └─ If Jarvis is unsure → automatically enters shadow mode
  └─ If Jarvis is confident → checks Layer 2

Layer 2: Client Preferences (middle)
  └─ Set via UI Settings page OR via Jarvis conversation
  └─ Example: "Jarvis, always put refunds in shadow mode"
  └─ Both UI and chat commands sync to same DB table
  └─ Jarvis respects client overrides

Layer 3: Learned Behavior (auto)
  └─ Over time, Jarvis learns patterns
  └─ "This client always rejects auto-refunds > $200"
  └─ Jarvis starts shadow mode proactively for those

Layer 4: Hard Safety Floor (bottom — cannot be overridden)
  └─ Irreversible actions ALWAYS require approval
  └─ Examples: delete account, bulk data export, permanent changes
  └─ No way to bypass — not even for High variant clients
```

**DB Tables Needed:**

```sql
-- shadow_log: Every action that went through shadow mode
CREATE TABLE shadow_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id          UUID NOT NULL REFERENCES companies(id),
    action_type         VARCHAR(50) NOT NULL,    -- e.g. 'refund', 'sms_reply', 'ticket_close'
    action_payload      JSONB NOT NULL DEFAULT '{}',  -- what the AI wanted to do
    jarvis_risk_score   FLOAT DEFAULT NULL,      -- 0.0 to 1.0 (1.0 = most risky)
    mode                VARCHAR(15) NOT NULL,    -- 'shadow' | 'supervised' | 'graduated'
    manager_decision    VARCHAR(15),             -- 'approved' | 'rejected' | 'modified' | null (pending)
    manager_note        TEXT,
    resolved_at         TIMESTAMP,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- undo_log: Actions that were auto-approved but then undone
CREATE TABLE undo_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shadow_log_id       UUID REFERENCES shadow_log(id),
    company_id          UUID NOT NULL REFERENCES companies(id),
    original_action     JSONB NOT NULL,          -- what was executed
    undo_reason         TEXT,
    undo_window_used    BOOLEAN DEFAULT FALSE,   -- was it within the undo window?
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- shadow_preferences: Client-set preferences (synced UI + Jarvis)
CREATE TABLE shadow_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id          UUID NOT NULL REFERENCES companies(id),
    action_category     VARCHAR(50) NOT NULL,    -- 'refund', 'sms', 'email_reply', etc.
    preferred_mode      VARCHAR(15) NOT NULL DEFAULT 'shadow',
    set_via             VARCHAR(10) NOT NULL DEFAULT 'ui',  -- 'ui' or 'jarvis'
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(company_id, action_category)
);
```

**Frontend Components:**
- `ShadowModeSettings.tsx` — Settings panel for mode configs (can live in /dashboard/settings or standalone page)
- `useShadowMode.ts` — Hook that syncs state between UI and Jarvis context

**Backend Endpoints:**
- `GET /api/shadow/preferences` — Get client shadow mode preferences
- `PATCH /api/shadow/preferences` — Update preferences (from UI)
- `POST /api/shadow/evaluate` — Jarvis evaluates an action's risk
- `POST /api/shadow/approve/:id` — Manager approves shadow action
- `POST /api/shadow/reject/:id` — Manager rejects shadow action
- `POST /api/shadow/undo/:id` — Undo an auto-approved action (Graduated mode)
- `GET /api/shadow/log` — Get shadow log / audit trail

**Jarvis Commands (conversational):**
- "Put refunds in shadow mode"
- "Show me pending shadow actions"
- "Approve the last refund"
- "Always ask me before sending SMS"
- "What's my current shadow mode?"
- "Undo the last auto-approved refund"
- "Switch to supervised mode"

---

### Addition 2: Shadow Mode Dashboard UI Pages (Day 2 of 3)

**What:** New Dashboard pages/components that show shadow mode state, approvals queue, and audit trail.

**Page 1: Shadow Mode Badge (Dashboard Header)**
- Location: Top-right of dashboard header (next to user menu)
- Shows current global mode: Shadow (orange) / Supervised (yellow) / Graduated (green)
- Clicking opens quick settings dropdown or links to full settings page
- Real-time updates when mode changes (via UI or Jarvis)

**Page 2: Approvals Queue (/dashboard/approvals)**
- Lists all pending shadow mode actions awaiting manager approval
- Each item shows: action type, AI recommendation, risk score, timestamp
- Manager can: Approve / Reject / Modify / View Details
- Filters: by action type, risk level, date range
- Real-time updates (Socket.io) when new items arrive
- Batch approve/reject for multiple items
- "Approve All Low Risk" button

**Page 3: Undo Interface**
- Shows recent auto-approved actions (Graduated mode) that are still within the undo window
- Each item has an "Undo" button
- Shows countdown timer for undo window expiry
- After undo, shows what was rolled back
- History of past undos

**Page 4: Shadow Log / Audit Trail (/dashboard/shadow-log)**
- Full history of all shadow mode actions
- Columns: timestamp, action type, mode, risk score, AI recommendation, manager decision, outcome
- Filterable and searchable
- Export to CSV
- Charts: approval rate over time, risk distribution, mode transition timeline

**Page 5: What-If Simulator (Bonus)**
- Manager can simulate: "What would happen if this action ran in Shadow mode?"
- Shows predicted risk score, predicted mode, what Jarvis would recommend
- Helps managers understand WHY Jarvis chose a certain mode for an action

**Components to Build:**
- `ModeBadge.tsx` — Small badge showing current mode
- `ApprovalsQueue.tsx` — Full approvals list with actions
- `ApprovalItem.tsx` — Single approval card
- `UndoButton.tsx` — Undo button with countdown
- `UndoHistory.tsx` — Past undo actions
- `ShadowLogTable.tsx` — Audit trail table
- `RiskScoreIndicator.tsx` — Visual risk score (color-coded)
- `WhatIfSimulator.tsx` — Simulation interface

---

### Addition 3: Jarvis Context + Memory Integration (Day 3 of 3)

**What:** Ensure Jarvis knows and remembers all Shadow Mode decisions, preferences, and context. When a client talks to Jarvis about shadow mode, Jarvis has full context.

**Jarvis Knowledge Base Addition:**

```json
// File: backend/app/data/jarvis_knowledge/11_shadow_mode.json
{
  "shadow_mode": {
    "overview": "PARWA's Shadow Mode is a safety system where Jarvis can preview actions before executing them. It has 3 modes: Shadow (preview only, no execution), Supervised (Jarvis suggests, manager approves), Graduated (Jarvis auto-executes low-risk, shadow for high-risk, undo available).",
    "modes": {
      "shadow": "Jarvis shows what it would do, but nothing is executed. Manager sees the recommendation and decides. Used for new clients or uncertain actions.",
      "supervised": "Jarvis executes low-confidence actions in shadow (preview mode) and asks for approval on medium/high risk. Manager approves/rejects from dashboard or chat.",
      "graduated": "Jarvis auto-executes low-risk actions and shows them in the undo queue. High-risk actions still go to shadow/approval. Auto-approved actions can be undone within a time window."
    },
    "decision_layers": [
      "Layer 1: Jarvis AI Risk Assessment — Jarvis evaluates confidence and risk for each action",
      "Layer 2: Client Preferences — Set via UI or by talking to Jarvis. Both sync to same backend.",
      "Layer 3: Learned Behavior — Over time, Jarvis learns client patterns and preferences",
      "Layer 4: Hard Safety Floor — Irreversible actions always require approval, no override"
    ],
    "dual_control": "Clients can control shadow mode two ways: (1) Dashboard Settings UI page, (2) Talking to Jarvis in chat. Both methods sync to the same database. Changes made in UI appear in Jarvis context and vice versa.",
    "undo_system": "In Graduated mode, auto-approved actions have an undo window. Clients can undo recent actions by clicking the Undo button in dashboard or telling Jarvis 'undo the last refund'. The undo log tracks all undos.",
    "jarvis_commands": [
      "put [action] in shadow mode",
      "show me pending approvals",
      "approve / reject the last [action]",
      "always ask me before [action type]",
      "switch to [shadow/supervised/graduated] mode",
      "undo the last [action]",
      "what is my current shadow mode?",
      "why was this action put in shadow mode?"
    ],
    "safety_floor_actions": [
      "Account deletion",
      "Bulk data export",
      "Permanent data removal",
      "Payment/cancellation above threshold",
      "API key revocation",
      "Integration disconnection"
    ]
  }
}
```

**Jarvis Context Updates (context_json fields to add):**

```typescript
// Add to JarvisContext type
interface ShadowModeContext {
  current_mode: 'shadow' | 'supervised' | 'graduated';
  client_preferences: Record<string, 'shadow' | 'supervised' | 'graduated'>;  // per action category
  pending_approvals_count: number;
  recent_shadow_actions: Array<{
    action_type: string;
    risk_score: number;
    decision: 'approved' | 'rejected' | 'pending';
    timestamp: string;
  }>;
  undo_available_count: number;  // actions in undo window
  learned_patterns: string[];    // patterns Jarvis has learned
}
```

**Jarvis System Prompt Additions:**

```
## Shadow Mode Awareness

You (Jarvis) are responsible for evaluating the risk of every action before execution.
Use the 4-layer decision system:
1. Assess your own confidence and risk
2. Check client preferences
3. Apply learned patterns
4. Enforce hard safety floor

When a client asks you to change shadow mode settings, update both the shadow_preferences table AND inform the UI via WebSocket so the dashboard reflects the change in real-time.

When explaining WHY you put something in shadow mode, be transparent: share your risk score and reasoning.
```

---

## Where These 3 Days Fit in the Roadmap

```
Current Wave 1: Part 18 (Security) ✅ DONE | Part 12 (Dashboard) 🔄 | Part 15 (Billing) 🔄
Current Wave 2: Part 1 (Infra) | Part 11 (Shadow Mode)

UPDATED Wave 2 with +3 days:
  Stream D: Part 1  — Infrastructure
  Stream E: Part 11 — Shadow Mode (original scope)
  Stream NEW: Shadow Mode Additions (these 3 days)
    Day 1: Dual Control System (DB + API + hooks)
    Day 2: Dashboard UI Pages (approvals, undo, audit trail)
    Day 3: Jarvis Context + Memory Integration
```

**Dependencies:**
- Day 1 (Dual Control) needs: Part 11 original (shadow mode middleware, mode enum)
- Day 2 (Dashboard UI) needs: Part 12 dashboard pages (layout, sidebar, routing)
- Day 3 (Jarvis Context) needs: Part 10 (Jarvis Control System) + Day 1 complete

**Can Run Parallel With:**
- Part 1 (Infrastructure) — no dependency
- Part 12 (Dashboard) — Day 2 integrates with dashboard, but can build in parallel

---

## Summary Table

| Day | Addition | Key Deliverables | Depends On |
|-----|----------|-----------------|------------|
| 1 | Dual Control System | `shadow_log`, `undo_log`, `shadow_preferences` tables; API endpoints for evaluate/approve/reject/undo/preferences; `useShadowMode.ts` hook; Jarvis commands | Part 11 original |
| 2 | Dashboard UI Pages | ModeBadge, ApprovalsQueue page, Undo interface, ShadowLog audit trail page, What-If Simulator | Part 12 dashboard layout |
| 3 | Jarvis Context + Memory | `11_shadow_mode.json` knowledge file, ShadowModeContext in JarvisContext type, system prompt updates, WebSocket sync UI↔Jarvis | Part 10 + Day 1 |

---

## Other Parts Affected by Shadow Mode

Shadow mode touches more than just Part 11 and Part 12. These 3 parts also have shadow mode integration requirements:

### Part 2 — Onboarding System
- **Stage 0 forced shadow mode:** ALL new clients start in Shadow mode — no exceptions
- Onboarding includes shadow mode explanation step
- First N actions (default 10) are always in shadow regardless of preference
- Auto-graduation suggestion after N successful low-risk approvals
- Shadow mode badge visible in onboarding UI
- `shadow_log` entries tagged with `stage: 'onboarding'`

### Part 13 — Ticket Management
- **New ticket fields:** `shadow_status` enum (none | pending_approval | approved | rejected | auto_approved | undone), `risk_score` float, `approved_by`, `approved_at`
- **Confidence score display** on each AI-resolved ticket (color-coded: red < 0.5, yellow 0.5-0.8, green > 0.8)
- **Undo support:** "Undo Resolution" button for auto-resolved tickets within undo window
- **Shadow indicator** in ticket list (badge/icon)
- **Approval link:** Click shadow badge → see full shadow_log entry with AI reasoning
- **Batch shadow actions:** Grouped in approvals queue for batch approve/reject
- **Filter by shadow status:** auto-approved, pending approval, undone

### Part 14 — Communication Channels
- **Shadow mode middleware for ALL outbound messages** — intercepts before send
- **Flow:** AI response → risk evaluation → shadow hold / auto-send based on mode + risk
- **Channel-specific intercept points:**
  - Email: before Brevo API call
  - SMS: before Twilio `client.messages.create()`
  - Voice: before TTS plays
  - Chat: before Socket.io emit
  - Social: before platform API call
- **Shadow preview:** Manager sees exact message content + recipient before approving
- **Safety floor bypass:** PII/legal/high-impact messages always go to shadow
- **Auto-send with undo:** Graduated mode low-risk messages auto-send + appear in undo queue

---

## Key Architecture Decisions (LOCKED)

| # | Decision | Rule |
|---|----------|------|
| SM-1 | Dual control is mandatory | UI panel AND Jarvis must both work. Neither is secondary. |
| SM-2 | Per-action, not per-channel | Shadow mode is decided per individual action, not fixed per channel or task type |
| SM-3 | Jarvis decides, client overrides | Jarvis assesses risk first, but client preference wins if set |
| SM-4 | Undo is always available in Graduated | Auto-approved actions can be undone within a time window |
| SM-5 | Hard safety floor is non-negotiable | Irreversible actions ALWAYS require approval, no exceptions |
| SM-6 | UI and Jarvis sync in real-time | Changes in one interface instantly reflect in the other |
| SM-7 | Transparent reasoning | Jarvis always explains WHY an action was put in shadow mode |
| SM-8 | New clients start in Shadow (Stage 0) | First N actions (default 10) are always shadow — no override possible |
| SM-9 | All outbound messages intercepted | Every channel (email, SMS, voice, chat, social) passes through shadow middleware before send |
