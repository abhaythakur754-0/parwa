# JARVIS — Complete Implementation Roadmap

> **Vision**: Jarvis is not a chatbot. It is a **Business Operating System** that manages your entire AI workforce through natural language commands and visual state monitoring. It knows everything happening in the system at all times, can control every variant, and communicates with humans the way an operations manager would — proactively, intelligently, and with full transparency.
>
> **Architecture Principle**: Smart on-demand queries (~500 tokens/interaction). Never bulk-load. LLM decides what SQL is needed, executes exact query, formats only that result.
>
> **Current State**: ~15-20% complete. 3-node skeleton (SENSE → EVALUATE → NOTIFY) exists with in-memory notification center, mock data, and keyword-matched admin chat. All 33 capabilities below need real implementation.
>
> **External Services Available**: Supabase (PostgreSQL + pgvector), Google AI, Groq, Cerebras, LiteLLM (11 models), Google OAuth, Paddle, Vercel, Render
>
> **Missing Services** (needed later, not blockers): Twilio, Email provider (SendGrid/Mailgun), Sentry, Statuspage

---

## Table of Contents

1. [What Jarvis IS and IS NOT](#1-what-jarvis-is-and-is-not)
2. [Current State vs Full Vision](#2-current-state-vs-full-vision)
3. [Architecture: How Jarvis Talks to Everything](#3-architecture-how-jarvis-talks-to-everything)
4. [Jarvis Roadmap — 8 Waves](#4-jarvis-roadmap--8-waves)
   - [Wave 1: Foundation — Database, Auth, Command Parser](#wave-1-foundation)
   - [Wave 2: Awareness Engine — Real Monitoring](#wave-2-awareness-engine)
   - [Wave 3: Control System — Commands That Change Behavior](#wave-3-control-system)
   - [Wave 4: Jarvis-PARWA Bidirectional Channel](#wave-4-jarvis-parwa-bidirectional-channel)
   - [Wave 5: Intelligence Layer — Batching, Confidence, Sentiment](#wave-5-intelligence-layer)
   - [Wave 6: Reporting & Quality Coach](#wave-6-reporting--quality-coach)
   - [Wave 7: Jarvis UI — The Iron Man Interface](#wave-7-jarvis-ui)
   - [Wave 8: Advanced — Agent Creation, Proactive, Voice](#wave-8-advanced)
5. [Database Schema — All Jarvis Tables](#5-database-schema--all-jarvis-tables)
6. [API Endpoints — Complete List](#6-api-endpoints--complete-list)
7. [LLM Cost Model Per Interaction](#7-llm-cost-model-per-interaction)
8. [Dependency Map](#8-dependency-map)
9. [Effort Estimates](#9-effort-estimates)

---

## 1. What Jarvis IS and IS NOT

### Jarvis IS:
- **A System-State-Aware Operating System** — Always knows current operational mode (Shadow, Supervised, Graduated)
- **A proactive healer** — Detects API failures/DDOS attacks and fixes them automatically
- **A behavioral controller** — Executes commands that change AI behavior via natural language
- **A trust-building explainer** — Shows reasoning, GSD state, and safety mechanisms transparently
- **A GSD Terminal Window** — Displays structured state execution steps in real time
- **A quality coach** — QA reports, training suggestions, health scores
- **A success coach** — Guides clients through onboarding milestones

### Jarvis IS NOT:
- A generic FAQ bot that answers scripted questions
- A help desk agent that handles customer queries directly
- A sales assistant that promotes products
- An upgrade/payment handler (variants do that)

### Core Interaction Loop (Every Jarvis Request):
```
1. Intent Classification  (~200 tokens, 1 LLM call) — What does the human want?
2. DB Operation           (0 tokens, pure SQL)          — Execute exact query
3. Response Formatting    (~300 tokens, 1 LLM call)    — Format result for human
─────────────────────────────────────────────────────────────────
Total: ~500 tokens per interaction
```

---

## 2. Current State vs Full Vision

### What EXISTS Today (Skeleton — ~15-20%):

| Component | Status | Reality |
|-----------|--------|---------|
| `jarvis_1_sense.py` | Code exists | Read-only. Collects signals from in-memory PARWA state. Integration health is hardcoded mock (`{"sendgrid": "healthy"}`). No real DB queries. |
| `jarvis_2_evaluate.py` | Code exists | Priority scoring formula works. CLARA + Reflexion LLM calls exist but only fire on "poll" trigger. No real data to evaluate. |
| `jarvis_3_notify.py` | Code exists | Creates notifications in in-memory store. Admin chat is keyword-matched (checks for "PARWA-NFY", "quota", "quality" in question text). No natural language understanding. |
| `notification_center.py` | Code exists | In-memory dict with batching (5-min window). NOT connected to Supabase. Loses all data on restart. |
| `state.py` | Code exists | TypedDict definition, functional. |
| `graph.py` | Code exists | Linear SENSE → EVALUATE → NOTIFY. Works. |

### What DOES NOT Exist (80-85% gap):

| Capability Category | Count | Status |
|---------------------|-------|--------|
| Real Supabase integration | — | ❌ No DB tables, no SQL queries, no connection pooling |
| Natural language command execution | 25+ commands | ❌ Only keyword matching, no intent classification |
| Control commands (pause/resume/route) | 8 types | ❌ No execution layer |
| Jarvis → PARWA communication | — | ❌ No write-back to PARWA state/flags |
| Confidence-based routing | 4 tiers | ❌ No scoring, no routing logic |
| Sentiment-based routing (Empathy Engine) | 2 paths | ❌ No sentiment analysis |
| Intelligent batching (semantic) | — | ❌ Only time-based batching exists |
| Approval gates | 8 action types | ❌ No gate logic |
| Notification table (PostgreSQL) | — | ❌ In-memory only |
| Reporting (Weekly Wins, SLA, Drift) | 6 report types | ❌ No reports |
| Quality Coach (alerts, training suggestions) | — | ❌ No quality tables |
| Jarvis UI (Next.js) | Full dashboard | ❌ No frontend |
| GSD Terminal Window | Real-time display | ❌ No streaming |
| Agent creation from chat | — | ❌ No provisioning |
| Emergency protocols (recall/void/shutdown) | 4 types | ❌ No protocols |
| Proactive outreach | 3 types | ❌ No outbound |
| Self-healing (API/DDOS) | — | ❌ No detection |
| Live takeover | — | ❌ No real-time |
| Co-Pilot mode | Draft composer | ❌ No drafting |
| Dynamic instruction workflow | Teach via chat | ❌ No learning from commands |
| Success Coach / Onboarding | — | ❌ No guidance |
| Webhook health monitoring | — | ❌ No webhook checking |
| SLA calculator | — | ❌ No tracking |
| Context health meter | — | ❌ No token tracking |
| Variant recommendation | — | ❌ No suggestion logic |

---

## 3. Architecture: How Jarvis Talks to Everything

### 3.1 The Bidirectional Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HUMAN MANAGER                            │
│           (Next.js Jarvis Dashboard / Chat)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ Natural Language
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    JARVIS ENGINE                             │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │ COMMAND  │──▶│  INTENT  │──▶│   DB     │──▶│ RESPONSE │ │
│  │ INPUT    │   │ CLASSIFY │   │ EXECUTE  │   │ FORMAT   │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│       │              │               │               │       │
│       │              │               │               │       │
│  ┌────┴──────────────┴───────────────┴───────────────┴────┐  │
│  │               SUPABASE (PostgreSQL + pgvector)         │  │
│  │                                                        │  │
│  │  notifications  │  agent_configs  │  system_flags     │  │
│  │  tickets        │  quality_scores │  audit_trail      │  │
│  │  feature_flags  │  client_skills  │  training_data    │  │
│  │  client_legal   │  provision_logs │  batch_queue      │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                  │
│                    WRITE FLAGS / READ STATE                   │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                 PARWA PIPELINE (Variants)                     │
│                                                              │
│  Node 2 (Smart Route) reads system_flags BEFORE routing      │
│  Node 5 (Act+Verify) checks approval_gates BEFORE executing  │
│  Node 6 (Quality) writes quality_scores AFTER scoring         │
│  Node 8 (Super Node) reads guidance FROM Jarvis               │
│                                                              │
│  PARWA writes to: tickets, conversations, quality_scores      │
│  Jarvis reads from: tickets, quality_scores, conversations    │
│  Jarvis writes to: system_flags, agent_configs, notifications │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Communication Mechanism

Jarvis does NOT call PARWA functions directly. Communication is **bidirectional via shared Supabase tables**:

**Jarvis → PARWA (Commands):**
- Jarvis writes to `system_flags` table (e.g., `flag_type: "pause_refunds", value: true`)
- PARWA Node 2 reads `system_flags` at the START of every ticket before routing
- If a flag matches the current ticket type → PARWA obeys the flag

**PARWA → Jarvis (Awareness):**
- PARWA writes to `tickets`, `quality_scores`, `conversations` tables
- Jarvis queries these tables on-demand when the admin asks or on poll cycle
- Jarvis does NOT bulk-load — it runs exact SQL for what's needed

### 3.3 The 3-Step Loop (Smart Data Access)

```
Human: "Jarvis, show me today's errors"

Step 1 — INTENT CLASSIFY (~200 tokens, 1 LLM call)
  LLM receives: "show me today's errors"
  LLM outputs: {
    "intent": "query_errors",
    "time_range": "today",
    "sql_needed": true,
    "sql_template": "SELECT error_type, COUNT(*), MAX(occurred_at) 
                     FROM error_logs 
                     WHERE tenant_id=$1 AND occurred_at >= CURRENT_DATE
                     GROUP BY error_type ORDER BY count DESC"
  }

Step 2 — DB EXECUTE (0 tokens, pure SQL)
  Supabase executes: the exact SQL above
  Returns: [{error_type: "api_timeout", count: 3, ...}, ...]

Step 3 — RESPONSE FORMAT (~300 tokens, 1 LLM call)
  LLM receives: the SQL result + human context
  LLM outputs: "You've had 3 API timeouts today, all between 2-4 PM.
               The last one was at 3:47 PM. This correlates with your
               peak traffic window. Want me to increase the timeout limit?"
```

**Cost: ~500 tokens total per interaction.** Compare to bulk-loading everything (~50,000 tokens).

---

## 4. Jarvis Roadmap — 8 Waves

Each wave is independently deployable. Dependencies are clearly marked.

---

### Wave 1: Foundation — Database, Auth, Command Parser

**Goal**: Replace all in-memory mocks with real Supabase. Establish the command infrastructure that every subsequent wave builds on.

**What Gets Built**:

#### 1A. Supabase Database Schema
Create ALL Jarvis tables in Supabase (see Section 5 for full schema):
- `notifications` — Replace in-memory notification_center.py
- `system_flags` — Global and per-tenant flags that PARWA reads
- `audit_trail` — Immutable log of every Jarvis action
- `quality_alerts` — Quality degradation alerts
- `quality_scores` — Per-ticket quality metrics
- `training_suggestions` — AI-generated improvement suggestions
- `agent_configs` — Virtual agent configurations
- `client_skills` — Custom skills taught via chat
- `feature_flags` — Per-client feature toggles
- `client_legal_config` — SLA, GDPR, compliance settings
- `agent_provisioning_logs` — Agent creation history

#### 1B. Supabase Connection Layer
- `jarvis_db.py` — Connection pool (pool_size=20, max_overflow=10, pool_pre_ping=True)
- Row-Level Security (RLS) policies on every table
- Tenant isolation: every query filtered by `tenant_id`
- Connection via Supabase pooler URL (port 6543)

#### 1C. Natural Language Command Parser
Replace keyword matching with real intent classification:
```
Input: "Jarvis, pause all refund processing"
Output: {
  "intent": "control_pause",
  "target": "refund_processing",
  "scope": "all",
  "confidence": 0.97
}
```
Supported intent families (expandable):
- `query_*` — Information requests (errors, tickets, quality, quota, status)
- `control_pause` / `control_resume` — Pause/resume capabilities
- `control_route` — Redirect channels/capabilities
- `control_mode` — Change system mode (Shadow/Supervised/Graduated)
- `approve_*` / `reject_*` — Batch or individual approvals
- `create_agent` — Provision new virtual agents
- `teach_skill` — Dynamic instruction workflow
- `emergency_*` — Recall, void, shutdown
- `explain_*` — Why did X happen? (GSD state display)

#### 1D. Auth Integration
- Google OAuth → identify user role (ADMIN, OWNER, SUPERVISOR, TEAM_MEMBER)
- Role-based access control for command authorization
- Admin-only commands: emergency shutdown, agent provisioning, global pause
- All commands logged to `audit_trail`

#### 1E. Migrate notification_center.py
- Replace `_store: Dict` with Supabase INSERT/SELECT
- Replace `_batch_buffer: Dict` with `batch_queue` table
- Keep the same API (create_notification, get_notification, resolve_notification)
- 30-day retention (GDPR), then archive/anonymize

**Deliverables**:
- All 11 DB tables created in Supabase with RLS
- `jarvis_db.py` connection module
- `command_parser.py` — intent classification with 10+ intent families
- Migrated `notification_center.py` → Supabase-backed
- Auth middleware for Jarvis API routes
- Tests: DB connection, RLS enforcement, command parsing

**Effort**: 3-4 days

**Dependencies**: Supabase project already exists. Google OAuth already configured.

---

### Wave 2: Awareness Engine — Real Monitoring

**Goal**: Jarvis actually sees what's happening. Every signal collector in SENSE node becomes real.

**What Gets Built**:

#### 2A. Real Stuck Ticket Detection
- Query `tickets` table: `WHERE status = 'pending_approval' AND created_at < NOW() - INTERVAL '12 hours'`
- Escalation tiers: 12h soft reminder, 24h backup alert, 48h critical
- Per-ticket: show quality_score, loop_count, error history, GSD state steps

#### 2B. Real Integration Health (UCB Monitoring)
- Replace hardcoded `{"sendgrid": "healthy"}` with actual health checks
- For each connected integration (Shopify, Stripe, HubSpot, email, SMS):
  - Store last successful ping timestamp
  - Store last error + response code
  - Calculate uptime percentage
- Webhook health: detect malformed data, track delivery success rate
- Self-healing: auto-restart failed connections (for retries, not permanent fixes)

#### 2C. Real Quota Monitoring
- Query `agent_configs` + usage tables for actual quota burn
- Per-variant: remaining/total/used/burn_pct
- Trend: compare today's burn rate vs yesterday's vs 7-day average
- Alert when >60% used (warning), >80% (critical)

#### 2D. Real Accuracy/Drift Detection
- Query `quality_scores` table for recent tickets
- Calculate 7-day rolling accuracy, confidence trend
- Drift triggers: accuracy drops >5% for 3+ days, CSAT drops >0.3, same error 3+ times
- Store drift status in `quality_alerts`

#### 2E. Real Ticket Flow Metrics
- Query `conversations` + `technique_log` for node-by-node flow
- Show: which nodes each ticket reached, where it got stuck, LLM call count
- Aggregate: "Today 450 tickets: 380 auto-resolved, 50 batched, 20 escalated"

#### 2F. LLM Cost Tracking
- Already partially exists in `llm_client.py` stats
- Store per-tenant LLM costs in DB: tokens used, model used, cost estimate
- Daily/weekly cost aggregation

#### 2G. Load Balancing Awareness
- Detect when a variant is at max concurrent capacity
- VIP overflow alert: if VIP customer arrives and all agents busy → alert manager
- Bottleneck detection: "PARWA High handling 5/5 concurrent calls"

**Deliverables**:
- All 7 SENSE collectors connected to real Supabase data
- Integration health checker with auto-ping
- Drift detection with configurable thresholds
- Stuck ticket cron job (hourly check)
- Cost tracking in DB

**Effort**: 3-4 days

**Dependencies**: Wave 1 (DB tables must exist)

---

### Wave 3: Control System — Commands That Change Behavior

**Goal**: When the admin says "pause refunds", it ACTUALLY happens. Jarvis writes flags that PARWA obeys.

**What Gets Built**:

#### 3A. System Flags Engine
The core of Jarvis control. A `system_flags` table that PARWA reads:
```sql
-- Example flags Jarvis writes:
INSERT INTO system_flags (tenant_id, flag_type, flag_value, scope, set_by, reason)
VALUES ('tenant_123', 'pause_action', 'refund', 'global', 'admin@example.com', 'Jarvis, pause all refund processing');
```

Flag types:
- `pause_action` — Pause specific action types (refund, returns, account_changes)
- `resume_action` — Resume paused actions
- `redirect_channel` — Route channel to AI or human (e.g., "Handle all Instagram DMs today, I'll take calls")
- `force_mode` — Change system mode (Shadow → Supervised → Graduated)
- `approval_override` — "Always auto-approve this type" (creates permanent approval rule)
- `disable_rule` — "Jarvis, undo my last rule" / "disable my last rule"
- `variant_assignment` — Move skills between variants
- `global_shutdown` — Emergency: kill all AI activity

#### 3B. Command Execution Engine
For each control command:
1. Parse intent (Wave 1)
2. Authorize (check role from Wave 1D)
3. Validate (is this action legal? budget? plan limits?)
4. Execute (write to `system_flags` + `audit_trail`)
5. Confirm (format response to admin)

#### 3C. Real-Time Policy Updates
When admin clicks "Always Auto-Approve This Type":
- Jarvis writes to `system_flags`: `{flag_type: "approval_override", flag_value: "address_change", scope: "permanent"}`
- PARWA Node 5 reads this flag BEFORE checking approval gates
- Future address changes skip the approval queue
- Logged in `audit_trail`

#### 3D. Skill Re-Assignment
"Move Product Recommendations from Mini to PARWA":
- Update `agent_configs` for both variants
- Move associated knowledge base entries
- Notify both variants of config change (via system_flags)
- Verify: test query on new variant

#### 3E. Emergency Protocols

**Recall Protocol** (`"Jarvis, recall all emails sent for Free Shipping messages"`):
1. Query `conversations` for matching messages
2. Mark messages as recalled in DB
3. If email provider connected: call Void API (non-financial only)
4. Log to `audit_trail`

**Void Protocol** (`"Delete pending messages for X"`):
1. Query outbox queue for matching messages
2. Remove from queue (before send, not after)
3. Log action

**Rage Quit / Emergency Shutdown** (`"Shut everything down"`):
1. Write `global_shutdown` flag
2. PARWA checks flag at Node 1 entry — rejects all new tickets
3. In-flight tickets: allowed to complete current step, then stop
4. Notify all active team members
5. Log to `audit_trail`

#### 3F. Workflow Redirect
"Handle all Instagram DMs today, I'll take calls":
- Write `redirect_channel` flag: `{channel: "instagram", route_to: "ai"}`
- Write `redirect_channel` flag: `{channel: "calls", route_to: "human"}`
- PARWA Node 2 reads flags → routes accordingly
- Flags can have expiry (e.g., "for today" = set expires_at)

**Deliverables**:
- `system_flags` table with all flag types
- `command_executor.py` — handles all control commands
- PARWA Node 1 & Node 2 modified to read `system_flags` before processing
- Emergency protocol handlers (recall, void, shutdown)
- Audit trail for every command
- Tests: pause/resume, redirect, emergency, undo

**Effort**: 4-5 days

**Dependencies**: Wave 1 (DB + command parser), Wave 2 (awareness of current state before changing it)

---

### Wave 4: Jarvis-PARWA Bidirectional Channel

**Goal**: Jarvis and PARWA share state. PARWA asks Jarvis for help. Jarvis gives guidance. Full 2-way communication.

**What Gets Built**:

#### 4A. PARWA Reads Jarvis Flags
Modify PARWA pipeline nodes to check `system_flags`:
- **Node 1 (Ingest)**: Check `global_shutdown` flag → reject ticket immediately
- **Node 2 (Route)**: Check `redirect_channel`, `force_mode`, `pause_action` flags
- **Node 5 (Act+Verify)**: Check `approval_override` flags → skip approval for matching types
- **Node 8 (Super Node)**: Check for guidance flags from Jarvis

Implementation: Add a `load_system_flags(tenant_id)` function called at Node 1 entry, pass flags through state.

#### 4B. PARWA Asks Jarvis for Help
When PARWA's Super Node (Node 8) can't resolve a ticket:
- Instead of just escalating, write to `jarvis_inbox` table
- Include: ticket_id, stuck_reason, quality_score, what was tried
- Jarvis picks this up on next poll cycle
- Jarvis evaluates: "Can I help with DB data?" or "This needs human attention"

#### 4C. Jarvis Guidance to PARWA
Jarvis can write guidance that PARWA reads:
```
Jarvis writes to system_flags:
{
  flag_type: "guidance",
  target_ticket: "TKT-882",
  guidance: "Check Shopify order #1234 — customer already received replacement per ticket TKT-850",
  set_by: "jarvis_auto"
}
```
- PARWA Node 3 (Knowledge Fetch) reads guidance flags for the current ticket
- Injects guidance as additional context for reasoning

#### 4D. Quality Score Write-Back
After PARWA Node 6 scores a ticket:
- Write `quality_scores` row to Supabase
- Jarvis can now query this data for drift detection, reporting, weekly summaries
- Trigger Jarvis evaluation if quality drops below threshold

#### 4E. Training Data Collection
Every human approval/rejection becomes training data:
- Approved → positive reward signal in `training_data`
- Rejected → negative reward signal
- Human edit of AI draft → both original + corrected stored
- This feeds the AI Wiki Section B (behavior patterns) and future fine-tuning

**Deliverables**:
- `load_system_flags()` in PARWA pipeline
- `jarvis_inbox` table for PARWA → Jarvis communication
- Guidance injection in PARWA Node 3
- Quality score write-back from Node 6
- Training data collection from approval/rejection
- End-to-end test: Jarvis pauses refunds → PARWA obeys → refund ticket gets paused

**Effort**: 3-4 days

**Dependencies**: Wave 1 (DB), Wave 3 (system_flags engine)

---

### Wave 5: Intelligence Layer — Batching, Confidence, Sentiment

**Goal**: Jarvis doesn't just pass information — it clusters, scores, and routes intelligently.

**What Gets Built**:

#### 5A. Confidence-Based Routing
Every PARWA decision gets a confidence score (0-100%). Jarvis uses this to decide what to show the manager:

| Confidence | Action | Jarvis Behavior |
|-----------|--------|-----------------|
| **95%+** | AUTO | Log only. No notification. |
| **85-95%** | BATCH | Group similar decisions. One-click approval. |
| **70-84%** | ASK | Show detailed analysis. Manager reviews individually. |
| **<70%** | ESCALATE | Beyond AI capability. Human judgment required. |

Confidence = weighted average of:
- Pattern match (how closely does this match training data?) — 30%
- Policy alignment (does answer align with uploaded policies?) — 25%
- Risk signals (fraud indicators, VIP customer, high value?) — 25%
- Historical accuracy (has this type been resolved correctly before?) — 20%

#### 5B. Intelligent Batching (Semantic Clustering)
Replace time-based batching with semantic clustering:
- Group tickets by similarity (not just time window)
- Show: "Batch Request: 5 customers requesting address changes — Confidence: 94-98% — Risk: Low"
- Manager actions: `[Approve Batch]` `[Reject Batch]` `[Review Individually]` `[Shadow This New Type]` `[Automate This Rule]`

Implementation:
- After PARWA resolves a ticket, store embedding of the ticket + decision
- When batching, compare new tickets against recent batch using pgvector
- If cosine similarity > 0.85 → same batch

#### 5C. Sentiment Routing (Empathy Engine)
Route customers based on emotional state, not just logic:
- **Angry/Frustrated** (sentiment score < 0.3): Route directly to human manager. Alert: `[!] Angry Customer: Ticket #882`
- **Happy/Neutral** (sentiment score > 0.6): Handle by AI autonomously (often Light Tier for speed/cost)
- **Mixed/Uncertain** (0.3-0.6): Handle by AI but flag for manager review

Sentiment analysis happens in PARWA Node 1 (already has classification). The sentiment score flows through state. Jarvis reads it and applies routing rules.

#### 5D. Approval Gates
Hard-coded safety rules that CANNOT be overridden by AI:
- **Always require approval for**: Refunds (any amount), Returns, Account changes, Policy exceptions, VIP customer actions, Financial transactions (credits, adjustments, discounts >$10)
- Approval gates live in `approval_gates` config (DB, not code)
- Even "Always Auto-Approve" has a blacklist: refunds and account changes ALWAYS need approval regardless
- State is preserved during approval wait — ticket doesn't get lost

#### 5E. Variant Recommendation
When a task seems too complex for current variant:
- Jarvis analyzes: "This requires Shopify API calls + refund logic + cross-reference 3 orders"
- Recommends: "This task needs PARWA High. Your current Mini variant can't handle multi-API calls. Want to upgrade?"
- Checks: is the variant available? Is there budget? What's the queue depth?

**Deliverables**:
- Confidence scoring formula implemented in PARWA Node 6
- Semantic batching with pgvector similarity
- Sentiment routing rules in PARWA Node 2 + Jarvis
- Approval gates configuration in DB
- Variant recommendation logic
- Tests: confidence routing, batch approval, sentiment escalation

**Effort**: 4-5 days

**Dependencies**: Wave 4 (PARWA writes quality scores), Wave 1 (pgvector)

---

### Wave 6: Reporting & Quality Coach

**Goal**: Jarvis becomes the manager's intelligence report — weekly summaries, drift reports, SLA tracking, training suggestions.

**What Gets Built**:

#### 6A. Weekly Wins Report
Auto-generated every Monday at 9 AM (cron):
```
Subject: "Week 2 Progress: Your AI is getting smarter"

- Tickets Handled: 450 (vs your human team handling 12)
- Money Saved: $340 (estimated at $8/ticket human cost)
- New Skill Learned: "AI now knows how to handle 'Wrong Size' returns."
- Prediction: "By next Monday, AI will be 90% ready on refund logic."
- Top Improvement: Address change accuracy went from 78% → 94%
- Needs Attention: 3 refund tickets had incorrect amounts (review needed)
```

Data sources: `tickets`, `quality_scores`, `training_data` — all via SQL aggregation.

#### 6B. Performance Dashboard Data
Real-time metrics Jarvis can report on demand:
- **Volume & Accuracy**: Tickets handled, auto-resolved rate, approval requests, manager approvals/denials
- **Confidence Trends**: Average confidence, trend direction (↑↓→), high/low confidence percentages
- **Efficiency Gains**: Manager time saved, avg response time, Customer CSAT
- **Learning Progress**: New patterns learned, policy updates integrated, error self-corrections

#### 6C. Drift Detection & Alerts
- Monitor: avg confidence (7-day rolling), accuracy rate, CSAT score, error frequency
- Triggers auto-alert if: confidence drops >5% for 3+ days, accuracy <95%, CSAT drops >0.3, same error 3+ times
- Alert types in `quality_alerts` table: `quality_drop`, `recurring_error`, `confidence_drift`, `csat_decline`
- Resolution tracking: manager can mark alert as resolved, system tracks time-to-resolution

#### 6D. Quality Coach Reports
- `generate_weekly_quality_report()`: 7-day performance summary
- `generate_mistake_analysis()`: Error breakdown by type with examples
- `generate_training_priority_list()`: Ranked list of areas needing improvement
- Agent health score: composite of accuracy, empathy, efficiency scores

#### 6E. SLA Calculator
- Track actual uptime vs 99.5% target
- Credit computation: 10% monthly fee per 1% downtime below target
- Per-client SLA config in `client_legal_config` table
- Monthly SLA report generated automatically

#### 6F. Customer Health Score
- For onboarding clients: milestone-based health checkpoints
- Composite score: KB coverage + accuracy + policy count + integration health
- Success Coach AI: "You're 70% ready to go live. Add your return policy and you'll hit 85%."

#### 6G. ROI Response
When admin asks "Is this worth it?":
- Jarvis calculates: current human cost vs AI cost
- Factors in: tickets handled, time saved, accuracy improvement, SLA credits
- Returns: "Based on your industry review time, you're spending ~$1,500/mo. PARWA handles 90% automatically at $300/mo. Net savings: $1,200/mo."

**Deliverables**:
- Weekly report generator (SQL + template)
- Performance metrics API
- Drift detection with auto-alerts
- Quality Coach report functions
- SLA calculator
- Health score computation
- ROI calculator
- Cron jobs: weekly report (Monday 9 AM), drift check (daily), SLA report (monthly)

**Effort**: 3-4 days

**Dependencies**: Wave 2 (real data in DB), Wave 4 (quality_scores table)

---

### Wave 7: Jarvis UI — The Iron Man Interface

**Goal**: The Next.js dashboard that makes Jarvis feel like a real Operating System. Terminal/CLI aesthetic. Real-time everything.

**What Gets Built**:

#### 7A. Jarvis Dashboard (Main Control Center)
The day-to-day control center. Always visible elements:
- **System State Indicator**: Current mode (Shadow/Supervised/Graduated) in header
- **Active AI Agents**: Which variants are running, their status
- **Uptime**: System uptime counter
- **Live Activity Feed**: Color-coded real-time stream
  - 🟢 Green: Auto-handled successfully
  - 🟡 Yellow: Batched for approval (medium confidence)
  - 🔴 Red: Escalated to you
- **System Status Banner**: OPTIMAL / DEGRADED / CRITICAL

#### 7B. Jarvis Chat Panel
The primary interaction method. Natural language. No menus.

Features:
- Proactive greeting: "Good morning. I noticed your Shopify API is lagging. I've restarted the connection." [Yes, Check] [Ignore]
- Command execution with Iron Man terminal display
- Context health meter: `[Normal] Context Usage: 45% ████████░░░░░░░░░░`
- 90% popup: "Jarvis recommends starting a new conversation. Current Chat: 11,500 tokens" [Start New Chat] [Continue Anyway]

#### 7C. GSD Terminal Window
Real-time display of PARWA's decision process:
```
JARVIS - OPERATING SYSTEM
SYSTEM STATUS: OPTIMAL
> [INIT] System Ready.
> [INPUT] "I want a refund for order #8921"
> [THINKING] Analyzing Request...
> [TOOL] Calling Shopify API (get_order)...
> [SUCCESS] Order found: Shipped.
> [STATE UPDATE] Current Issue: Refund Request.
> [DRAFTING] Generating Recommendation...
Recommendation: APPROVE — Confidence: 87%
[Approve Anyway] [Request Photo] [Deny] [Ask AI to Handle]
```
- Streams via WebSocket/Server-Sent Events
- Shows each PARWA node as it executes
- Shows technique being used (CoT, Reflexion, etc.)

#### 7D. Batch Approval Interface
The most-used daily feature. Reduces approval fatigue by 80%.
- Shows: batch description, confidence range, risk indicator, total amount
- Actions: `[Approve Batch]` `[Reject Batch]` `[Review Individually]` `[Automate This Rule]` `[Shadow This New Type]`
- Keyboard shortcuts for power users

#### 7E. Urgent Attention Panel
- VIP customer alerts with strategic analysis (churn risk, LTV, expected value)
- Sticky: stays visible until dismissed
- One-click: "Listen Live" / "Take Over Call Immediately"

#### 7F. Workforce Allocation Map
- Visual diagram: which variants handle which task types
- Real-time load: "PARWA High: 5/5 calls, PARWA Standard: 3/10, Mini: 0/20"
- Drag-and-drop skill re-assignment

#### 7G. Weekly Wins Banner
- Persistent banner: "AI learned 12 new skills this week. Review time down 23%."
- Click → opens full weekly report

#### 7H. Health Card (Drift Report)
- Visual health indicator: 🟢 Healthy / 🟡 Watch / 🔴 Action Needed
- 7-day trend chart (confidence, accuracy, CSAT)
- Click → opens detailed drift report

#### 7I. Adaptation Tracker
- "30-Day Promise" progress bar: `Day 14 / 30`
- Milestone checkpoints: KB coverage, accuracy targets, policy count
- Success Coach AI guidance at each milestone

**Tech Stack**:
- Next.js (already on Vercel)
- Tailwind CSS for styling
- Server-Sent Events for real-time streaming
- Supabase real-time subscriptions for live data
- React Query for data fetching + caching

**Deliverables**:
- Full Jarvis dashboard with 9 UI components
- Real-time WebSocket/SSE streaming
- Batch approval interface with keyboard shortcuts
- GSD Terminal Window
- Mobile-responsive layout
- Auth integration (Google OAuth)

**Effort**: 7-10 days

**Dependencies**: Waves 1-6 (UI needs real data flowing through the system)

---

### Wave 8: Advanced — Agent Creation, Proactive, Voice

**Goal**: The most ambitious capabilities. Agent creation from chat, proactive outreach, voice commands, co-pilot mode.

**What Gets Built**:

#### 8A. Agent Creation from Chat ("Chat-to-Infrastructure")
"Jarvis, I'm getting crushed by sales emails. Add 2 Mini Agents to handle the load for the weekend."

Flow:
1. **Parse Command**: `parse_jarvis_command()` extracts: action=add, count=2, type=mini, duration=weekend
2. **Authorize**: Check role (ADMIN/OWNER/SUPERVISOR only), account active
3. **Budget Check**: Verify client balance can support additional agents
4. **Plan Limit Check**: Max active agents for their plan
5. **Execute**:
   - Create rows in `agent_configs` (virtual agents = DB rows, NOT new containers)
   - Clone context from existing agent of same type (brand voice, FAQ categories, greeting style)
   - Set expiry if temporary (weekend = set expires_at to Monday)
6. **Show Progress**: Iron Man Terminal display
   ```
   JARVIS - ORCHESTRATOR
   > [INPUT] "Add 2 Mini for weekend"
   > [PARSING] Intent Detected
   > [VALIDATING] Role & Budget...
   > [AUTHORIZED] Plan Limit OK
   > [PROVISIONING] Agent Configs...
   > [SUCCESS] Agents #88 & #89 Created
   > [SYNCING] Knowledge Base (Brand Voice)
   [OK] OPERATION COMPLETE — Provisioning ID: prov_99212
   ```

Safety limits:
- Max 20 agents per single provision command
- Budget hard check (can't go negative)
- Plan tier limits enforced
- All provisioning logged to `agent_provisioning_logs`

#### 8B. Dynamic Instruction Workflow
"Jarvis, here is how I want you to handle International Returns."

Flow:
1. Manager describes new process in natural language
2. Jarvis uses LLM to parse into structured steps
3. Store in `client_skills` table: `{skill_name: "international_returns", steps_json: [...], created_at: NOW()}`
4. PARWA Node 3 fetches custom skills when relevant ticket arrives
5. Jarvis confirms: "I've learned 'International Returns' in 4 steps. Want me to test it on a sample ticket?"

When variants get stuck and ask Jarvis for help:
- Jarvis checks `client_skills` for matching guidance
- If found: provides the steps to the variant
- If not found: "I don't have instructions for this. Asking your manager."

#### 8C. Proactive Outbound (Feature-Flagged)
- Abandoned cart recovery: detect abandoned cart via Shopify webhook → generate script → manager approves → send
- Churn prediction: monitor usage patterns → flag disengagement → trigger proactive outreach
- Proactive shipping delay alerts: detect delay from Shopify → notify customer before they complain
- ALL proactive actions require manager approval (never auto-send outbound without permission)
- Feature flag: `proactive_voice` enabled per client

#### 8D. Co-Pilot Mode
Jarvis drafts text for human review:
- Manager types: "Reply to customer about delayed order"
- Jarvis drafts response based on order data + policy + sentiment
- Manager edits → AI learns from edits via training_data
- Saves 90% of typing time

#### 8E. Voice Command Support
- All text commands also work via voice (Web Speech API for browser, Whisper for uploaded audio)
- "Jarvis" wake word → records command → transcribes → processes same as text
- Jarvis repeats back: "You said: pause all refund processing. Is that correct?" [Yes] [No]

#### 8F. Live Takeover
- Manager can "Listen Live" to any active AI conversation
- "Take Over Call Immediately" — AI pauses, manager types/speaks directly
- Jarvis logs the intervention with timestamp + reason
- AI resumes after manager finishes

#### 8G. DSPy-Integrated Corrections
"Jarvis, fix this. Use code 'V2.0'":
- Updates the Prompt Compiler for permanent fix (via DSPy)
- Not just a one-time correction — improves the underlying prompt
- Logged in `training_data` with before/after

**Deliverables**:
- Agent creation from chat (Option B: virtual configs in DB)
- Dynamic instruction workflow (teach via chat)
- Proactive outbound system (feature-flagged)
- Co-Pilot mode
- Voice command support
- Live takeover
- DSPy correction integration

**Effort**: 7-10 days

**Dependencies**: Waves 1-7. This is the capstone wave.

---

## 5. Database Schema — All Jarvis Tables

### 5.1 `notifications` (replaces in-memory store)
```sql
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  notification_key TEXT NOT NULL UNIQUE,  -- PARWA-NFY-XXX
  type TEXT NOT NULL,                     -- stuck_ticket, quota_low, integration_down, accuracy_drop, sla_risk
  priority TEXT NOT NULL DEFAULT 'MEDIUM', -- CRITICAL, HIGH, MEDIUM, LOW
  priority_score DECIMAL(4,4) NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  related_tickets TEXT[] DEFAULT '{}',
  batch_key TEXT,
  source_data JSONB DEFAULT '{}',
  is_read BOOLEAN DEFAULT FALSE,
  is_resolved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days'
);

CREATE INDEX idx_notifications_tenant ON notifications(tenant_id, is_resolved);
CREATE INDEX idx_notifications_priority ON notifications(tenant_id, priority, created_at DESC);
```

### 5.2 `system_flags`
```sql
CREATE TABLE system_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  flag_type TEXT NOT NULL,       -- pause_action, resume_action, redirect_channel, force_mode,
                                  -- approval_override, disable_rule, guidance, global_shutdown
  flag_value TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT 'global',  -- global, per_ticket, per_channel, per_variant
  target_id TEXT,                 -- ticket_id, channel_name, variant_id (for non-global scope)
  set_by TEXT NOT NULL,           -- email or 'jarvis_auto'
  reason TEXT,
  expires_at TIMESTAMPTZ,         -- NULL = permanent, otherwise auto-expires
  created_at TIMESTAMPTZ DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_flags_tenant ON system_flags(tenant_id, flag_type, revoked_at);
CREATE INDEX idx_flags_active ON system_flags(tenant_id) WHERE revoked_at IS NULL 
  AND (expires_at IS NULL OR expires_at > NOW());
```

### 5.3 `audit_trail` (immutable append-only)
```sql
CREATE TABLE audit_trail (
  id SERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  action TEXT NOT NULL,
  actor_email TEXT NOT NULL,
  target_type TEXT,               -- 'ticket', 'flag', 'agent', 'notification', 'skill'
  target_id TEXT,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  payload JSONB DEFAULT '{}',
  previous_hash TEXT,
  current_hash TEXT
);

-- Trigger to prevent UPDATE/DELETE
CREATE OR REPLACE FUNCTION audit_trail_immutable()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_trail is immutable — no UPDATE or DELETE allowed';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_trail_no_modify
  BEFORE UPDATE OR DELETE ON audit_trail
  FOR EACH ROW EXECUTE FUNCTION audit_trail_immutable();
```

### 5.4 `quality_scores`
```sql
CREATE TABLE quality_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  agent_id TEXT,
  ticket_id TEXT,
  conversation_id UUID,
  accuracy_score DECIMAL(3,2),
  empathy_score DECIMAL(3,2),
  efficiency_score DECIMAL(3,2),
  overall_score DECIMAL(3,2),
  confidence_score DECIMAL(3,2),
  sentiment_score DECIMAL(3,2),
  resolution_path TEXT,           -- simple, complex, escalated
  nodes_reached TEXT[],
  llm_calls INT DEFAULT 0,
  tokens_used INT DEFAULT 0,
  model_used TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quality_tenant_date ON quality_scores(tenant_id, created_at DESC);
CREATE INDEX idx_quality_score ON quality_scores(tenant_id, overall_score);
```

### 5.5 `quality_alerts`
```sql
CREATE TABLE quality_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  alert_type TEXT NOT NULL,       -- quality_drop, recurring_error, confidence_drift, csat_decline
  severity TEXT NOT NULL DEFAULT 'medium',  -- low, medium, high, critical
  message TEXT NOT NULL,
  metric_name TEXT,
  metric_value DECIMAL(5,2),
  threshold_value DECIMAL(5,2),
  resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMPTZ,
  resolved_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_tenant ON quality_alerts(tenant_id, resolved, created_at DESC);
```

### 5.6 `training_suggestions`
```sql
CREATE TABLE training_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  suggestion_type TEXT NOT NULL,  -- new_knowledge, policy_update, skill_gap, kb_gap
  description TEXT NOT NULL,
  priority INT DEFAULT 0,          -- 0=highest
  related_tickets TEXT[],
  implemented BOOLEAN DEFAULT FALSE,
  implemented_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.7 `agent_configs` (virtual agent registry)
```sql
CREATE TABLE agent_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  variant_type TEXT NOT NULL,      -- parwa, mini, trivya, high
  status TEXT NOT NULL DEFAULT 'active',  -- active, paused, expired
  capabilities TEXT[] DEFAULT '{}',
  config JSONB DEFAULT '{}',       -- brand_voice, greeting_style, faq_categories, etc.
  created_by TEXT NOT NULL,
  provisioning_id TEXT,
  expires_at TIMESTAMPTZ,          -- NULL = permanent
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_tenant ON agent_configs(tenant_id, status);
```

### 5.8 `client_skills` (taught via chat)
```sql
CREATE TABLE client_skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  skill_name TEXT NOT NULL,
  description TEXT,
  steps_json JSONB NOT NULL,       -- Array of step objects
  source TEXT DEFAULT 'chat',      -- chat, upload, api
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_skills_tenant_name ON client_skills(tenant_id, skill_name);
```

### 5.9 `feature_flags`
```sql
CREATE TABLE feature_flags (
  tenant_id TEXT NOT NULL,
  feature_name TEXT NOT NULL,
  enabled BOOLEAN DEFAULT FALSE,
  rollout_percentage INT DEFAULT 100,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (tenant_id, feature_name)
);
```

### 5.10 `client_legal_config`
```sql
CREATE TABLE client_legal_config (
  tenant_id TEXT PRIMARY KEY,
  allows_data_sharing BOOLEAN DEFAULT FALSE,
  waive_liability_cap BOOLEAN DEFAULT FALSE,
  custom_sla_uptime_percentage DECIMAL(5,2) DEFAULT 99.50,
  custom_sla_credit_percentage INT DEFAULT 10,
  compliance_framework TEXT DEFAULT 'GDPR',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.11 `agent_provisioning_logs`
```sql
CREATE TABLE agent_provisioning_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  variant_type TEXT NOT NULL,
  count INT NOT NULL,
  agent_ids UUID[],               -- IDs of created agents
  expiry_at TIMESTAMPTZ,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 5.12 `training_data` (from approvals/rejections)
```sql
CREATE TABLE training_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  ticket_id TEXT,
  interaction_type TEXT NOT NULL,  -- approved, rejected, edited, corrected
  original_prompt TEXT,
  corrected_prompt TEXT,
  original_response TEXT,
  corrected_response TEXT,
  user_feedback TEXT,
  outcome TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_training_tenant ON training_data(tenant_id, interaction_type, created_at DESC);
```

### 5.13 `batch_queue` (replaces in-memory batch buffer)
```sql
CREATE TABLE batch_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL,
  batch_key TEXT NOT NULL,
  ticket_ids TEXT[] NOT NULL,
  confidence_min DECIMAL(3,2),
  confidence_max DECIMAL(3,2),
  risk_level TEXT,
  total_amount DECIMAL(10,2) DEFAULT 0,
  status TEXT DEFAULT 'pending',   -- pending, approved, rejected, expired
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '5 minutes'
);

CREATE INDEX idx_batch_tenant ON batch_queue(tenant_id, status, created_at DESC);
```

---

## 6. API Endpoints — Complete List

### 6.1 Jarvis Command Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/jarvis/chat` | POST | Main chat endpoint — natural language commands | All roles |
| `/api/jarvis/notifications` | GET | Get notifications for tenant | All roles |
| `/api/jarvis/notifications/:key/resolve` | POST | Mark notification resolved | All roles |
| `/api/jarvis/notifications/batch/approve` | POST | Approve a batch of tickets | Admin+ |
| `/api/jarvis/notifications/batch/reject` | POST | Reject a batch of tickets | Admin+ |
| `/api/jarvis/status` | GET | System status, mode, active agents | All roles |
| `/api/jarvis/metrics` | GET | Performance metrics (volume, accuracy, cost) | All roles |
| `/api/jarvis/flags` | GET | List active system flags | Admin+ |
| `/api/jarvis/flags` | POST | Set a system flag | Admin+ |
| `/api/jarvis/flags/:id/revoke` | POST | Revoke a system flag | Admin+ |

### 6.2 Control Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/jarvis/command/pause` | POST | Pause an action type | Admin+ |
| `/api/jarvis/command/resume` | POST | Resume a paused action | Admin+ |
| `/api/jarvis/command/redirect` | POST | Redirect channel to AI/human | Admin+ |
| `/api/jarvis/command/mode` | POST | Change system mode | Admin+ |
| `/api/jarvis/command/provision` | POST | Create new virtual agent | Admin/Owner only |
| `/api/jarvis/command/teach` | POST | Teach a new skill via chat | Admin+ |

### 6.3 Emergency Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/actions/recall` | POST | Recall sent messages (non-financial) | Admin/Owner only |
| `/api/messages/void` | POST | Void pending messages from queue | Admin/Owner only |
| `/api/emergency/shutdown` | POST | Emergency stop all AI activity | Owner only |
| `/api/pause_all_refunds` | POST | Global refund pause | Owner only |

### 6.4 Quality & Reporting Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/quality/scores` | GET | Quality scores for tenant | All roles |
| `/api/quality/alerts` | GET | Active quality alerts | All roles |
| `/api/quality/alerts/:id/resolve` | POST | Mark quality alert resolved | Admin+ |
| `/api/quality/recommendations` | GET | Training recommendations | All roles |
| `/api/quality/feedback` | POST | Submit quality feedback | All roles |
| `/api/quality/weekly-report` | GET | Generate weekly report | All roles |
| `/api/quality/health-score` | GET | Agent health score | All roles |
| `/api/sla/status` | GET | SLA compliance status | All roles |
| `/api/sla/credits` | GET | SLA credit calculation | Admin+ |

### 6.5 Approval Endpoints

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/approvals/pending` | GET | Get pending approvals | Admin+ |
| `/api/approvals/:id/approve` | POST | Approve a ticket | Admin+ |
| `/api/approvals/:id/reject` | POST | Reject a ticket | Admin+ |
| `/api/approvals/batch` | POST | Batch approve/reject | Admin+ |

### 6.6 Webhook Endpoints (External → PARWA/Jarvis)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhooks/shopify/orders/updated` | POST | Shopify order updates (HMAC verified) |
| `/webhooks/stripe/events` | POST | Stripe events |
| `/webhooks/hubspot/deals` | POST | HubSpot deal updates |

---

## 7. LLM Cost Model Per Interaction

### 7.1 Standard Jarvis Interaction (Query)
```
Intent Classification:  ~200 tokens in, ~50 tokens out  = ~250 tokens (1 call)
DB Operation:           0 tokens (pure SQL)
Response Formatting:    ~300 tokens in, ~150 tokens out = ~450 tokens (1 call)
────────────────────────────────────────────────────────────────────
Total per interaction:  ~700 tokens, 2 LLM calls
Cost (Light tier):      ~$0.0001 per interaction
```

### 7.2 Control Command (Pause/Resume/Route)
```
Intent Classification:  ~200 tokens in, ~50 tokens out  = ~250 tokens (1 call)
DB Write:               0 tokens (pure SQL)
Confirmation:           ~100 tokens in, ~50 tokens out  = ~150 tokens (1 call)
────────────────────────────────────────────────────────────────────
Total per command:      ~400 tokens, 2 LLM calls
```

### 7.3 Complex Evaluation (CLARA + Reflexion)
```
Signal Collection:      0 tokens (pure DB queries)
CLARA Clarification:    ~300 tokens in, ~80 tokens out  = ~380 tokens (1 call)
Reflexion Check:        ~400 tokens in, ~150 tokens out = ~550 tokens (1 call)
Notification Format:    ~200 tokens in, ~100 tokens out = ~300 tokens (1 call)
────────────────────────────────────────────────────────────────────
Total per evaluation:   ~1,230 tokens, 3 LLM calls
This only runs on poll cycle, not per-chat.
```

### 7.4 Weekly Report Generation
```
Data Aggregation:       0 tokens (SQL)
Report Generation:      ~2,000 tokens in, ~800 tokens out = ~2,800 tokens (1 call)
────────────────────────────────────────────────────────────────────
Total per week:         ~2,800 tokens, 1 LLM call (runs once per week)
```

### 7.5 Monthly Cost Estimate (per tenant, moderate usage)
```
50 chat queries/day × 30 days = 1,500 interactions × 700 tokens = 1,050,000 tokens
10 control commands/day × 30 = 300 × 400 = 120,000 tokens
4 poll evaluations/day × 30 = 120 × 1,230 = 147,600 tokens
4 weekly reports × 2,800 = 11,200 tokens
────────────────────────────────────────────────────────────────────
Total: ~1,328,800 tokens/month = ~1.3M tokens
Cost (Light tier, Groq Llama): ~$0.13/month
Cost (Mid tier, Gemini Flash): ~$0.66/month
```

Jarvis is CHEAP to run. The smart query pattern keeps costs near-zero.

---

## 8. Dependency Map

```
Wave 1: Foundation
    │
    ├──▶ Wave 2: Awareness (needs DB tables)
    │
    ├──▶ Wave 3: Control (needs DB + command parser)
    │       │
    │       └──▶ Wave 4: Bidirectional (needs system_flags)
    │               │
    │               ├──▶ Wave 5: Intelligence (needs quality_scores)
    │               │       │
    │               │       └──▶ Wave 6: Reporting (needs real data)
    │               │               │
    │               │               └──▶ Wave 7: UI (needs all data flows)
    │               │                       │
    │               │                       └──▶ Wave 8: Advanced (needs full system)
    │               │
    │               └──(directly)──▶ Wave 5, 6, 7, 8
    │
    └──▶ Wave 7 (UI needs auth from W1, but can start with mock data)
```

### Parallel Work Opportunities:
- **Wave 7 (UI)** can start in parallel with Waves 2-6 using mock data, then connect to real APIs as they become available
- **Wave 8 (Advanced)** features are independent of each other — can be built in any order once Waves 1-6 are done

---

## 9. Effort Estimates

| Wave | Description | Days | Cumulative | Key Risk |
|------|-------------|------|------------|----------|
| **1** | Foundation (DB, Auth, Parser) | 3-4 | 3-4 | Supabase schema migrations |
| **2** | Awareness (Real Monitoring) | 3-4 | 6-8 | Integration health checks need real API access |
| **3** | Control (Commands → Behavior) | 4-5 | 10-13 | Modifying PARWA nodes to read flags |
| **4** | Bidirectional (Jarvis ↔ PARWA) | 3-4 | 13-17 | Race conditions on flag reads/writes |
| **5** | Intelligence (Batching, Confidence) | 4-5 | 17-22 | Semantic clustering accuracy |
| **6** | Reporting (Quality Coach, SLA) | 3-4 | 20-26 | Report template quality |
| **7** | Jarvis UI (Iron Man Interface) | 7-10 | 27-36 | Real-time streaming complexity |
| **8** | Advanced (Agent Creation, Proactive) | 7-10 | 34-46 | Voice, proactive need external services |

### Total Estimated Effort: **34-46 days** (single developer, full-time)

### Suggested Sprint Breakdown:
| Sprint | Waves | Duration |
|--------|-------|----------|
| Sprint 1 | Wave 1 + Wave 2 | 1 week |
| Sprint 2 | Wave 3 + Wave 4 | 1-1.5 weeks |
| Sprint 3 | Wave 5 + Wave 6 | 1-1.5 weeks |
| Sprint 4 | Wave 7 (start) | 1-2 weeks |
| Sprint 5 | Wave 7 (complete) + Wave 8 (start) | 1-2 weeks |
| Sprint 6 | Wave 8 (complete) | 1-2 weeks |

---

## Appendix A: 33 Unique Capabilities — Full Checklist

| # | Capability | Wave | Status |
|---|-----------|------|--------|
| 1 | Business Operating System (manages AI workforce) | All | 🟡 Skeleton |
| 2 | Natural Language Command Execution | W1, W3 | 🟡 Keyword only |
| 3 | Proactive Self-Healing (API/DDOS) | W2, W8 | ❌ None |
| 4 | Behavioral Controller (change AI behavior) | W3 | ❌ None |
| 5 | Trust Preservation Protocol (2-layer messaging) | W4 | ❌ None |
| 6 | Co-Pilot Mode (draft text for human) | W8 | ❌ None |
| 7 | Empathy Engine / Sentiment Routing | W5 | ❌ None |
| 8 | Intelligent Batching (semantic clustering) | W5 | 🟡 Time-based only |
| 9 | Real-Time Policy Training | W3 | ❌ None |
| 10 | Dynamic Instruction Workflow (teach via chat) | W8 | ❌ None |
| 11 | Agent Creation from Chat | W8 | ❌ None |
| 12 | Context Health Meter | W7 | ❌ None |
| 13 | GSD Terminal Window | W7 | ❌ None |
| 14 | Approval Gates | W5 | ❌ None |
| 15 | Confidence-Based Routing | W5 | ❌ None |
| 16 | Weekly Wins Report | W6 | ❌ None |
| 17 | Performance Dashboard | W6, W7 | ❌ None |
| 18 | System-State Awareness (Shadow/Supervised/Graduated) | W2, W7 | ❌ None |
| 19 | Proactive Outbound Voice | W8 | ❌ None |
| 20 | Quality Coach (alerts, training suggestions) | W6 | ❌ None |
| 21 | Success Coach AI (onboarding milestones) | W6, W8 | ❌ None |
| 22 | Full System Overrides (pause/redirect) | W3 | ❌ None |
| 23 | Emergency Brake (recall/void/shutdown) | W3 | ❌ None |
| 24 | Webhook Health Monitoring | W2 | ❌ None |
| 25 | Security/DDOS Shield | W2 | ❌ None |
| 26 | SLA Calculator | W6 | ❌ None |
| 27 | Iron Man Terminal UI | W7 | ❌ None |
| 28 | Variant Recommendation | W5 | ❌ None |
| 29 | Skill Re-Assignment | W3 | ❌ None |
| 30 | Live Takeover | W8 | ❌ None |
| 31 | DSPy-Integrated Corrections | W8 | ❌ None |
| 32 | Onboarding Guide (learning status) | W6, W8 | ❌ None |
| 33 | Integration Health Monitoring | W2 | 🟡 Mock only |

---

## Appendix B: What Jarvis Does NOT Handle

These are explicitly OUT of Jarvis scope (handled by variants or other systems):

| Function | Handled By | Why |
|----------|-----------|-----|
| Subscription upgrades/payments | Paddle + Variants | Financial operations |
| Direct customer support | PARWA Variants | Jarvis manages, variants execute |
| CRM data management | HubSpot/Salesforce + UCB | External system |
| Email/SMS delivery | SendGrid/Twilio + UCB | External service |
| Payment processing | Stripe/Paddle | External service |
| User authentication flows | Google OAuth + Supabase Auth | Infrastructure |
| Deploying new containers | Render/Railway | Infrastructure (Jarvis creates virtual configs, not containers) |