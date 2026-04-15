# Part 12: Dashboard System — 8-Day Build Plan

> **Status:** Planning Complete — Ready to Build
> **Priority:** P1 — Core product UI (clients see this EVERY day)
> **Current:** ~30% complete (3 of 7 pages work, 8 components orphaned, 7 backend modules have ZERO frontend)
> **Dependencies:** None (can run parallel with Part 18 Safety + Part 15 Billing)
> **Created:** April 16, 2026

---

## THE PROBLEM

The dashboard is the **entire client experience** — everything a paying customer ($999-$3,999/month) sees after logging in. Currently:

### What Works (3 pages):
- Home Overview (`/dashboard`) — KPI cards, activity feed, workforce chart
- Channels (`/dashboard/channels`) — channel cards
- Training (`/dashboard/training`) — training status (not even in sidebar)

### What's Broken (4 pages are 404):
- Tickets — 404
- Agents — 404
- Approvals — 404
- Settings — 404

### What's Missing Entirely (7 pages have NO frontend despite backend being built):
- Customers (CRM) — 5 backend services, 0 frontend
- Conversations / Call Records — 5 backend services, 0 frontend
- Knowledge Base / Documents — 6+ backend services, 0 frontend
- Billing — 10+ backend services, 0 frontend
- Integrations — 12+ backend services, 0 frontend
- Notifications Center — 5 backend services, 0 frontend
- Audit Log — 3 backend services, 0 frontend

### What's Built But Not Connected:
- 8 orphaned chart components (ConfidenceTrend, AdaptationTracker, ROIDashboard, CSATTrends, QAScores, DriftDetection, GrowthNudge, TicketForecast)
- Backend APIs with no consumers (agent dashboard, adaptation analytics, savings, forecast, CSAT trends, growth nudges)
- system_status_service.py — 867 lines, no API endpoint, no frontend
- Socket.io server — 22 events, frontend has ZERO socket client
- UserMenu.tsx — exists but not in dashboard header
- FirstVictory.tsx — only in onboarding
- SavingsCounter.tsx — on home but not prominent

### Critical Missing UI Elements:
- Header bar: no plan badge, no notification bell, no system status, no emergency pause, no shadow mode selector, no logout
- Per-agent individual views (what each agent is doing)
- Call record playback (listen to conversations)
- Jarvis in sidebar (currently separate page only)
- ROI comparison (PARWA vs human agents cost)
- Confidence display
- Buy additional variant/agent flow

---

## COMPLETE DASHBOARD ARCHITECTURE

### Layout Structure

```
+----------------------------------------------------------------------+
|  [HEADER BAR]                                                        |
|  Logo | Company | Plan Badge | Notif | Status | Pause | Mode | User |
+--------+-------------------------------------------------------------+
|        |                                                             |
| SIDEBAR|              MAIN CONTENT AREA                              |
|        |                                                             |
| Overview|   (changes based on sidebar selection)                     |
| Tickets |                                                             |
| Agents  |                                                             |
| Customers (NEW)                                                       |
| Conversations (NEW)                                                   |
| Approvals                                                             |
| Analytics (NEW)                                                       |
| Knowledge Base (NEW)                                                  |
| Channels                                                              |
| Billing (NEW)                                                         |
| Integrations (NEW)                                                    |
| Settings                                                              |
| --------                                                             |
| Jarvis                                                                |
|        |                                                             |
+--------+-------------------------------------------------------------+
```

### Header Bar Items (8 items):

| # | Item | Status | What it Does |
|---|------|--------|-------------|
| H1 | Logo + Company Name | Partial | Shows PARWA logo + tenant company name |
| H2 | Plan Badge | Missing | Shows "Mini PARWA $999" / "PARWA $2,499" / "PARWA High $3,999". Click opens billing |
| H3 | Notification Bell | Missing | Unread count badge, dropdown with recent notifications |
| H4 | System Status Indicator | Missing | Green/Yellow/Red dot. Backend 867 lines exists, no frontend |
| H5 | Emergency Pause Button | Missing | ONE CLICK stops ALL AI agents. Critical safety feature |
| H6 | Mode Selector (Shadow/Supervised/Graduated) | Missing | Dropdown for system operating mode |
| H7 | User Menu Dropdown | Partial | UserMenu.tsx exists but not wired to dashboard header |
| H8 | Logout | Missing in header | Exists in AuthContext but not connected |

### Sidebar Navigation (13 items):

| # | Route | Label | Status |
|---|-------|-------|--------|
| S1 | `/dashboard` | Overview | Working |
| S2 | `/dashboard/tickets` | Tickets | 404 |
| S3 | `/dashboard/agents` | Agents | 404 |
| S4 | `/dashboard/customers` | Customers | DOES NOT EXIST |
| S5 | `/dashboard/conversations` | Conversations | DOES NOT EXIST |
| S6 | `/dashboard/approvals` | Approvals | 404 |
| S7 | `/dashboard/analytics` | Analytics | DOES NOT EXIST |
| S8 | `/dashboard/knowledge-base` | Knowledge Base | DOES NOT EXIST |
| S9 | `/dashboard/channels` | Channels | Working |
| S10 | `/dashboard/billing` | Billing | DOES NOT EXIST |
| S11 | `/dashboard/integrations` | Integrations | DOES NOT EXIST |
| S12 | `/dashboard/settings` | Settings | 404 |
| S13 | Side panel | Jarvis | Separate page only |

---

## 8-DAY BUILD PLAN

### DAY 1 — Foundation: Header Bar, Sidebar, Socket.io Client
**Goal:** Get the chrome (frame) of the dashboard working perfectly. Every button visible, every link navigable.

#### Header Bar (8 items):

| ID | Item | Details |
|----|------|---------|
| H1.1 | Logo + Company Name | Wire company name from JWT/auth context into header. PARWA logo left-aligned |
| H1.2 | Plan Badge | Fetch current subscription plan. Show "Mini PARWA $999/mo" with colored badge (blue/silver/gold). Click navigates to `/dashboard/billing`. Badge reflects tier |
| H1.3 | Notification Bell | Create `<NotificationBell />` component. Fetch unread count from `/api/notifications`. Show red badge with count. Dropdown shows 5 most recent: ticket new, AI resolved, approval needed, system alert. Each with timestamp and read/unread state. Click "View All" goes to notifications page |
| H1.4 | System Status Indicator | Create `<SystemStatusIndicator />`. Poll `/api/system/status` every 30s (or Socket.io). Show green/yellow/red dot + "All Systems" text. Hover/click dropdown shows: LLM status, Redis status, DB status, each channel status. Backend `system_status_service.py` (867 lines) needs a new API endpoint first |
| H1.5 | Emergency Pause Button | Create `<EmergencyPauseButton />`. Red button with lightning icon. Click opens confirmation dialog: "This will IMMEDIATELY stop ALL AI agents. Continue?". On confirm: POST `/api/agents/emergency-pause`. Show pulsing red state while active. "Resume All" button to re-enable |
| H1.6 | Mode Selector | Create `<ModeSelector />`. Dropdown showing current mode: Shadow (orange) / Supervised (blue) / Graduated (green). Only visible when Part 11 is active. Calls PUT `/api/system/mode` on change. Default: Supervised |
| H1.7 | User Menu Dropdown | Wire existing `UserMenu.tsx` into dashboard header. Show user name + avatar initials. Dropdown: Profile, Account Settings, Help & Docs, Logout |
| H1.8 | Logout | Wire logout to auth context. Clear session/token. Redirect to `/login`. Confirm dialog if there are unsaved changes |

#### Sidebar Restructure:

| ID | Item | Details |
|----|------|---------|
| SB1 | Rebuild sidebar with all 13 items | Icons + labels. Active state highlighting. Collapsible. Mobile hamburger menu |
| SB2 | Badge counts on sidebar items | Tickets: unread count. Approvals: pending count. Notifications: total unread |
| SB3 | Active section highlighting | Current page highlighted in sidebar with accent color |
| SB4 | Jarvis button at bottom | Distinct styling (chat bubble icon). Opens side panel (not page navigation) |

#### Socket.io Client:

| ID | Item | Details |
|----|------|---------|
| SO1 | Socket.io client library | Install `socket.io-client`. Create `lib/socket.ts` with connection manager. Auto-connect on dashboard mount. Auto-reconnect with exponential backoff. Join tenant room |
| SO2 | Wire ticket events | `ticket:new` (increment count, show notification), `ticket:resolved` (update KPI, savings counter), `ticket:escalated` (update approvals badge) |
| SO3 | Wire agent events | `agent:status_changed` (update agent card instantly), `ai:confidence_low` (yellow agent card, alert) |
| SO4 | Wire notification events | `notification:new` (update bell badge count) |
| SO5 | Wire system events | `system:error` (status indicator turns red), `system:recovered` (status turns green) |
| SO6 | Wire approval events | `approval:pending` (update approvals badge, notification) |

#### System Status API Endpoint:

| ID | Item | Details |
|----|------|---------|
| SS1 | Create `/api/system/status` endpoint | Expose `system_status_service.py` via FastAPI. Return health of: LLM, Redis, PostgreSQL, Celery, Socket.io, each channel (email, SMS, chat, voice). Include uptime, response times, error counts |

**Day 1 Deliverables:**
- Fully functional header bar with all 8 items
- Restructured sidebar with all 13 navigation items
- Socket.io client connected and receiving live events
- System status API endpoint created
- All navigation links go to actual pages (even if pages are placeholder for now)

**Day 1 Total: 20 items**

---

### DAY 2 — Overview Page Enhancement + ROI + First Victory
**Goal:** Make the home dashboard the WOW page — the first thing clients see that proves PARWA's value.

#### Overview Page Widgets:

| ID | Widget | Details |
|----|--------|---------|
| O1.1 | System Health Strip | Horizontal bar at page top. Shows: LLM status, Redis, DB, each channel. Green checkmarks or red X. Auto-updates via Socket.io. Click any item for details |
| O1.2 | ROI Comparison Card (PROMINENT) | BIG card: "You saved $X vs hiring human agents this month". Comparison table: PARWA cost vs human agent cost (5 agents x $3,000/mo) vs competitor cost. Monthly/yearly toggle. "Export Report" button. Wire existing `ROIDashboard.tsx` component (currently orphaned). Backend `/api/analytics/savings` exists |
| O1.3 | KPI Cards Enhancement | Existing 4 cards (tickets resolved, auto-resolve %, avg response time, CSAT) — make them animated with real-time Socket.io updates. Add sparkline mini-charts. Show trend arrows (up/down vs last week) |
| O1.4 | Active Agents Summary | Quick view strip: "3 agents active, 2 paused, 1,247 tickets today". Each agent with name, mini confidence bar, tickets handled, status dot. Click agent name goes to agent detail. Backend `/api/agents/dashboard` exists |
| O1.5 | First Victory Banner | Celebration banner: "Your AI just resolved its first ticket! In 47 seconds." Appears when first AI resolution happens. Shows for 24 hours with dismiss. Animated confetti effect. Wire existing `FirstVictory.tsx` concept from onboarding |
| O1.6 | Growth Nudge Card | Smart CTA: "Upgrade to PARWA High and save an additional $50K/year" based on usage patterns. Shows when approaching usage limits. Wire existing `GrowthNudge.tsx` (currently orphaned). Backend `/api/analytics/growth-nudges` exists |
| O1.7 | Activity Feed Enhancement | Existing feed — add real-time Socket.io updates. Show agent avatar (AI icon) vs customer avatar. Add filter: "All / AI Actions / Human Actions / Escalations". Show relative time ("2 min ago") |
| O1.8 | Recent Approvals Widget | Last 3 pending/approved items with quick action buttons. "Approve" / "Reject" inline buttons. Click goes to full approvals page |
| O1.9 | Workforce Allocation Chart Enhancement | Existing chart — add Socket.io live updates. Add legend. Add click-to-filter (click a segment to see those tickets) |
| O1.10 | Savings Counter Enhancement | Existing `SavingsCounter.tsx` — make it PROMINENT. Animate counting up. Show daily/weekly/monthly savings. Compare to human cost. Use real data from `/api/analytics/savings` |

#### Home Page Layout (Final):

```
+----------------------------------------------------------------------+
|  Health: LLM check | Redis check | DB check | Email check | SMS check |
+----------------------------------------------------------------------+
|                                                                        |
|  [KPI 1] [KPI 2] [KPI 3] [KPI 4]     |  SAVINGS COUNTER (animated)  |
|                                          |  $156,240 saved this month  |
+------------------------------------------+------------------------------+
|                                                                        |
|  ACTIVE AGENTS: [Agent 1: 94%] [Agent 2: 87%] [Agent 3: 91%] [+]   |
|                                                                        |
+------------------------------------------+------------------------------+
|                                          |                              |
|  ROI COMPARISON (BIG CARD)               |  GROWTH NUDGE                |
|  PARWA: $2,499/mo                        |  "Upgrade & save $50K more"  |
|  Human Agents: $15,000/mo                |                              |
|  You save: $150,501/year                 |                              |
|  [Monthly] [Yearly] [Export]             |                              |
+------------------------------------------+------------------------------+
|                                          |                              |
|  ACTIVITY FEED (real-time)               |  RECENT APPROVALS            |
|  - AI resolved #1247 in 47s              |  - Pending: Refund $150      |
|  - AI resolved #1246 in 38s              |  - Approved: Free shipping   |
|  - Escalated #1245 to human              |  - Rejected: Custom discount |
+------------------------------------------+------------------------------+
|                                                                        |
|  WORKFORCE ALLOCATION CHART              |  FIRST VICTORY BANNER       |
|  (pie/bar chart)                         |  (when applicable)          |
+------------------------------------------+------------------------------+
```

**Day 2 Deliverables:**
- Enhanced overview page with all 10 widgets
- ROI comparison card prominently displayed
- First Victory banner working
- Savings counter animated and prominent
- All widgets connected to real backend APIs
- Socket.io live updates on all widgets

**Day 2 Total: 10 items**

---

### DAY 3 — Tickets Page (Full Build)
**Goal:** The most-used page. Clients see ALL their customer conversations here.

#### Ticket List View:

| ID | Feature | Details |
|----|---------|---------|
| T1 | Ticket list with pagination | 25 per page. Virtual scrolling for performance. Total count. Page navigation. Backend `/api/tickets` exists |
| T2 | Search | Full-text search across ticket subjects, customer names, message content. Debounced 300ms |
| T3 | Multi-filter bar | Status (New/In Progress/Escalated/Resolved/Closed), Channel (Email/SMS/Chat/Voice), Agent (dropdown of all agents), Priority (High/Medium/Low), AI Confidence (0-25/25-50/50-75/75-100), Date range picker |
| T4 | Sortable columns | Click column header to sort. ID, Status, Priority, Channel, Agent, Confidence, Created At |
| T5 | Ticket row design | Each row: ID, priority badge (color), status badge, subject (truncated), customer name, channel icon, agent name, confidence bar, time ago. Hover shows preview |
| T6 | Bulk actions | Checkbox per row. Select all. Bulk: Mark Resolved, Assign Agent, Change Priority, Export Selected |
| T7 | Real-time new tickets | Socket.io `ticket:new` event adds row to top of list with highlight animation. Sound notification option |
| T8 | Quick view hover panel | Hover ticket row shows: first 3 messages, customer info, AI confidence, sentiment. No click needed for quick glance |

#### Ticket Detail View:

| ID | Feature | Details |
|----|---------|---------|
| T9 | Conversation view | Full customer-to-AI chat transcript. Customer messages left-aligned (gray), AI messages right-aligned (blue). Timestamps on each message. Message type indicators (text, image, file attachment) |
| T10 | Metadata side panel | Channel, Agent, Variant/Plan, AI Confidence (color bar), Resolution Time, GSD State (visual step indicator: NEW -> GREETING -> DIAGNOSIS -> RESOLUTION -> CLOSED), Technique(s) used (CLARA, ReAct, etc.), Sentiment (per-message emoji + overall), Language, Priority |
| T11 | AI confidence per message | Show confidence score on each AI response. Color: green (75%+), yellow (50-75%), red (below 50%). Hover shows breakdown |
| T12 | Sentiment analysis | Per-message sentiment indicator. Overall conversation sentiment. Sentiment trend line. Backend `conversation_service.py` tracks sentiment |
| T13 | GSD state visualization | Visual step indicator showing current GSD state. Each step lights up as conversation progresses. Time spent per state |
| T14 | AI technique display | Show which technique(s) fired for each AI response. Tooltip explaining what each technique does. Technique stacking indicator |
| T15 | Customer info card | Customer name, email, phone, all linked channels. Click goes to customer detail page. "View all tickets from this customer" link |
| T16 | Action buttons | Escalate to Human (opens form with reason), Reassign to Agent (dropdown), Add Internal Note (expandable text area, only team-visible), View Full Transcript, Export Conversation (PDF/CSV) |
| T17 | Internal notes section | Team-only notes with author name, timestamp. Can edit/delete own notes. Pin important notes |
| T18 | Timeline view | Chronological timeline: ticket created, AI assigned, AI responded, customer replied, technique fired, escalated, resolved, closed. Each event with timestamp and actor |
| T19 | Attachment handling | Show file attachments in conversation. Image preview. PDF thumbnail. Download button. Backend `attachment_service.py` exists |
| T20 | Reply box | Human agent can type reply directly from ticket detail. Select channel (responds via same channel customer used). Supports formatting. Backend `message_service.py` exists |

**Day 3 Deliverables:**
- Full ticket list page with search, filters, sort, pagination, bulk actions
- Full ticket detail view with conversation transcript
- All metadata, confidence, sentiment, GSD state, technique display
- Action buttons (escalate, reassign, note, export)
- Real-time new ticket updates via Socket.io
- Customer info card linking to CRM

**Day 3 Total: 20 items**

---

### DAY 4 — Agents Page + Per-Agent Views + Call Records
**Goal:** Clients see what EACH agent is doing individually. Call records visible and playable.

#### Agent List/Grid View:

| ID | Feature | Details |
|----|---------|---------|
| A1 | Agent cards grid | Visual cards for each agent. Card shows: agent name, avatar/icon, status (Active green / Paused gray / Error red), variant badge, confidence gauge, tickets today, resolution rate, CSAT score. Backend `/api/agents` exists |
| A2 | Agent status control | Pause/Resume toggle per agent. Confirmation dialog. POST `/api/agents/{id}/pause` or `/resume`. Instant UI update via Socket.io |
| A3 | Add new agent button | "+ Add Agent" button. Opens modal: select variant (Mini/PARWA/PARWA High), name, industry focus. Shows monthly cost. "Confirm and Pay" links to Paddle checkout. Backend `/api/agent_provisioning` exists |
| A4 | Agent comparison view | Toggle to comparison mode. Select 2+ agents. Side-by-side metrics: confidence, tickets, resolution rate, CSAT, avg response time. Bar charts comparing |
| A5 | Agent filter/search | Filter by: status (active/paused/error), variant, industry. Search by agent name |
| A6 | Aggregate stats strip | "5 agents total | 3 active | 1 paused | 1 error | 2,341 tickets handled today | 89% avg confidence" |

#### Agent Detail View (click "View" on agent card):

| ID | Feature | Details |
|----|---------|---------|
| A7 | Agent metrics dashboard | 7-day confidence trend (line chart), tickets today/this week/this month, auto-resolved %, avg response time, escalated count, CSAT score, resolution rate. Backend `/api/agent_dashboard` and `/api/agent_metrics` exist |
| A8 | **Current activity (LIVE)** | What is this agent doing RIGHT NOW. Shows: ticket ID, customer question (first 100 chars), channel, time elapsed, current confidence, active technique. Updates in real-time via Socket.io. Shows up to 3 concurrent activities. **This is the feature the client specifically asked for** |
| A9 | **Call records / conversation logs** | Table of all recent conversations this agent handled. Columns: Ticket ID, Channel icon, Customer name, Duration, Confidence, Result (Resolved/Escalated/Error), Timestamp. Click row opens ticket detail. **Client specifically asked for this** |
| A10 | **Call recording playback** | For voice channel conversations: play button, audio waveform, download. For chat/SMS: "View Transcript" button opens conversation. **Client specifically asked for this** |
| A11 | Performance trend charts | Confidence over time (line), Ticket volume over time (bar), Resolution rate over time (line), CSAT over time (line). Wire existing `ConfidenceTrend.tsx` and `AdaptationTracker.tsx` (orphaned components) |
| A12 | Mistake log | List of recent mistakes/errors this agent made. Each with: ticket ID, what went wrong, customer feedback, timestamp. "Train from these errors" button at bottom triggers retraining flow |
| A13 | Agent configuration | Edit agent name, variant assignment, system prompt override, KB selection, channel assignment. Save with confirmation |
| A14 | Agent-specific ticket list | "View all tickets handled by this agent" — filtered ticket list. Same filters as main Tickets page but pre-filtered to this agent |
| A15 | Train from errors button | Quick action button. Collects last N mistakes. Shows summary: "12 mistakes found. Training will take ~30 minutes." Confirm triggers Celery training task |

**Day 4 Deliverables:**
- Agent cards grid with status, metrics, controls
- Agent detail page with comprehensive metrics
- LIVE current activity view per agent
- Call records table per agent
- Call recording playback for voice conversations
- Agent comparison mode
- Train from errors flow

**Day 4 Total: 15 items**

---

### DAY 5 — Customers (CRM) + Conversations Pages
**Goal:** Clients see their customer base and ALL conversation history across channels.

#### Customers (CRM) Page:

| ID | Feature | Details |
|----|---------|---------|
| C1 | Customer list with pagination | 25 per page. Columns: Name, Email, Phone, Company, Ticket count, Last activity, Status. Sortable, searchable. Backend `/api/customers` exists |
| C2 | Customer search | Full-text search by name, email, phone, company. Debounced. Backend `customer_service.py` has search with pagination |
| C3 | Customer filters | Filter by: status (Active/Inactive), channel (has email/phone/social linked), ticket count range, last activity date |
| C4 | Customer detail/profile view | Click customer row opens detail: full profile (name, email, phone, company, address), all linked channels (email, phone, social media), all linked accounts. Backend `customer_service.py` has full CRUD |
| C5 | Customer ticket history | In customer detail: all tickets from this customer. Mini ticket list with status, channel, date. Click goes to ticket detail |
| C6 | Customer interaction timeline | Chronological timeline of ALL interactions: emails sent/received, chat sessions, phone calls, support tickets. Unified view across channels. Backend `identity_resolution_service.py` handles cross-channel |
| C7 | Customer merge/dedup | "Merge Customers" button. Select 2 customers. Preview what will be merged. Confirm merges with audit trail. Backend `customer_service.py` has merge with audit |
| C8 | Customer notes/tags | Add internal notes on customers. Tag customers (VIP, Enterprise, Trial, Churned). Filter by tags |
| C9 | Lead pipeline | Separate tab/section for leads. Pipeline: Identified -> Contacted -> Qualified -> Converted. Drag between stages. Lead source tracking. Backend `lead_service.py` exists |
| C10 | Customer bulk actions | Select multiple customers. Export CSV, Assign tag, Merge selected |

#### Conversations / Call Records Page:

| ID | Feature | Details |
|----|---------|---------|
| CV1 | Conversation list | All conversations across all channels. Columns: Ticket ID, Customer, Channel icon, Agent, Duration, Confidence, Result, Timestamp. Unified view. Backend `conversation_service.py` exists |
| CV2 | Channel filter tabs | All / Email / Chat / SMS / Voice / Social. Each tab shows only that channel's conversations |
| CV3 | Search conversations | Search within conversation content (message text, customer names, ticket subjects). Backend supports full-text search |
| CV4 | Date range filter | Filter by date range. Quick presets: Today, Last 7 days, Last 30 days, Custom |
| CV5 | Agent filter | Filter by which agent handled the conversation |
| CV6 | **Call recording playback** | For voice calls: audio player with waveform visualization, play/pause/skip, download MP3, speed control (1x/1.5x/2x). Shows call duration, participants, timestamp. **Client specifically asked for this** |
| CV7 | **Chat transcript view** | For chat/SMS/email: full message-by-message transcript with timestamps, sender (customer vs AI), channel indicator. Collapsible sections for long conversations |
| CV8 | **AI-generated conversation summary** | Each conversation has an AI-generated summary (2-3 sentences). Shown in list view. Click to expand full summary. Backend `conversation_summarization.py` exists |
| CV9 | **Sentiment per conversation** | Overall sentiment indicator (Positive/Neutral/Negative/Mixed) with color coding. Sentiment trend across conversations |
| CV10 | Export conversations | Export selected or all conversations as CSV/PDF. Includes: transcript, summary, sentiment, confidence, duration. Backend `export_service.py` exists |
| CV11 | Conversation detail view | Click conversation row opens full detail: complete transcript, metadata side panel (customer, agent, channel, duration, confidence, technique, GSD state), action buttons (escalate, reassign, note) |
| CV12 | Real-time conversation view | When a conversation is actively happening, show live-updating messages. Socket.io pushes new messages as they happen. "Watching live" indicator |

**Day 5 Deliverables:**
- Full CRM page with customer list, detail, tickets, timeline
- Lead pipeline view
- Customer merge and tags
- Full Conversations page with all channels unified
- Call recording playback with audio controls
- Chat transcript view
- AI-generated conversation summaries
- Conversation export (CSV/PDF)

**Day 5 Total: 22 items**

---

### DAY 6 — Knowledge Base + Analytics Page
**Goal:** Clients manage their documents. All 8 orphaned chart components finally get a home.

#### Knowledge Base Page:

| ID | Feature | Details |
|----|---------|---------|
| K1 | Document list | Table of all uploaded documents. Columns: Name, Type (PDF/DOCX/TXT/CSV), Size, Uploaded date, Status (Indexed/Pending/Failed), Chunks count. Search and filter. Backend `/api/knowledge-base` exists |
| K2 | Upload documents | Drag-and-drop upload area. Support PDF, DOCX, TXT, CSV, MD. Multiple file upload. Progress bar per file. Auto-chunking after upload. Backend `file_storage_service.py` + `knowledge_base/manager.py` exist |
| K3 | Document status management | For each document: Reindex button (forces re-chunking and re-embedding), Delete (with confirmation), Download original file. Show indexing status: Pending -> Chunking -> Embedding -> Indexed (Ready) -> Failed |
| K4 | Search knowledge base | Search across all documents. Shows matching chunks with document source, relevance score, page/section reference. Backend `knowledge_base/retriever.py` + `vector_search.py` exist |
| K5 | KB statistics | Total documents, total chunks, total embeddings, storage used, last indexed date, indexing health (any failed?) |
| K6 | Category/folder organization | Group documents by category (Product Info, Policies, FAQs, Procedures, etc.). Create folders. Drag documents between folders |
| K7 | Chunk preview | Click document to see all chunks. Each chunk: content preview, embedding status, relevance score, source page. Flag bad chunks for exclusion |
| K8 | RAG test panel | "Test your knowledge base" — type a question, see what the AI would retrieve. Shows top-5 chunks with relevance scores. Helps client understand what their AI knows |

#### Analytics Page:

| ID | Section | Component | Details |
|----|---------|-----------|---------|
| AN1 | **ROI Comparison (TOP — PROMINENT)** | Wire `ROIDashboard.tsx` | BIG card at top. PARWA cost vs human agents vs competitors. Monthly/yearly toggle. Per-channel breakdown. Exportable. Backend `/api/analytics/savings` exists |
| AN2 | **Confidence Trend** | Wire `ConfidenceTrend.tsx` | Line chart: AI confidence over time (7/30/90 day views). Per-agent breakdown toggle. Threshold line at 75% (yellow zone) and 50% (red zone). Backend `/api/agent_dashboard` + `/api/agent_metrics` exist |
| AN3 | **Adaptation Tracker** | Wire `AdaptationTracker.tsx` | How fast AI is learning. Accuracy improvements after each training cycle. Before/after training comparison. Backend `/api/analytics/adaptation` exists |
| AN4 | **CSAT Trends** | Wire `CSATTrends.tsx` | Customer satisfaction over time. Per-channel breakdown. Per-agent breakdown. Industry benchmark comparison. Backend `/api/analytics/csat-trends` exists |
| AN5 | **Ticket Forecast** | Wire `TicketForecast.tsx` | Predict next week/month volume based on historical trends. Seasonal patterns. Growth rate. Capacity planning recommendation. Backend `/api/analytics/forecast` exists |
| AN6 | **Drift Detection** | Wire `DriftDetection.tsx` | Is AI quality dropping? Accuracy trend line. Alert when drift detected. Last retraining date. Recommended retraining threshold. |
| AN7 | **QA Scores** | Wire `QAScores.tsx` | Quality assurance scores for AI responses. Per-category scores (accuracy, tone, completeness, safety). Overall quality score. |
| AN8 | **Growth Nudge** | Wire `GrowthNudge.tsx` | Smart upgrade CTA based on usage patterns. "You're at 80% capacity — upgrade to handle more." Shows projected savings with upgrade. Backend `/api/analytics/growth-nudges` exists |
| AN9 | Date range selector | New component | Global date filter for all analytics charts. Presets: Today, 7d, 30d, 90d, Custom. All charts update together |
| AN10 | Export reports | New component | "Export Report" button. Select type: Summary, Tickets, Agents, SLA, CSAT, Forecast, Full. Format: CSV or PDF. Backend `export_service.py` handles 7 report types. Backend `/api/reports` exists |

**Day 6 Deliverables:**
- Full Knowledge Base management page
- Document upload with progress and auto-indexing
- KB search and RAG test panel
- Full Analytics page with all 8 orphaned components wired
- ROI comparison prominently displayed
- Date range filtering across all charts
- Report export (CSV/PDF) with 7 report types

**Day 6 Total: 18 items**

---

### DAY 7 — Billing Page + Integrations Page + Notifications Center
**Goal:** Clients manage money, connections, and alerts.

#### Billing Page (Dedicated — not just settings tab):

| ID | Feature | Details |
|----|---------|---------|
| B1 | Current plan display | Big card: "PARWA $2,499/month" with tier badge (silver/gold/platinum). Plan features listed. Next billing date. Auto-renewal status. Backend `/api/billing` exists |
| B2 | Usage meters | Visual progress bars for each quota: Tickets (7,432 / 10,000), Agents (2 / 3), Storage (2.1 GB / 5 GB), Channels (3 / 5). Color changes as approaching limit (green -> yellow -> red). Backend `/api/subscription` exists |
| B3 | **Upgrade flow** | "Upgrade to PARWA High $3,999/mo" button. Shows comparison table: what you get vs what you'll get. Prorated cost calculation. "Confirm Upgrade" -> Paddle checkout. Backend `proration_service.py` exists |
| B4 | **Downgrade flow** | "Downgrade to Mini $999/mo" button. Warning: "You'll lose these features: X, Y, Z. Are you sure?" Prorated credit calculation. Confirm -> Paddle update. Backend `proration_service.py` exists |
| B5 | **Cancel subscription flow** | "Cancel Subscription" button (red, at bottom). Step 1: "Why are you leaving?" (feedback form with reasons). Step 2: Save offer — "Stay for 20% off your next 3 months." Step 3: Final confirm with clear "Your service ends on [date]". Backend `subscription_service.py` exists |
| B6 | **Invoice history** | Table of all invoices. Columns: Date, Amount, Status (Paid/Pending/Failed), Download PDF button. Backend `invoice_service.py` exists |
| B7 | **Payment method** | Show current payment method (card last 4 digits). "Update Payment Method" -> Paddle portal. Payment failure alerts if any. Backend `payment_failure_service.py` exists |
| B8 | **Overage charges** | If over quota: show overage charges section. "This month you used 12,000 tickets (2,000 over). Overage charge: $400." Link to upgrade to avoid future overages. Backend `overage_service.py` exists |
| B9 | **Buy additional agent** | "Add another AI agent for $X/month" card. Select variant. Shows added monthly cost. Paddle checkout. |
| B10 | **Buy additional variant** | "Add Logistics variant to your plan" card. Shows added cost. Paddle checkout. |

#### Integrations Page:

| ID | Feature | Details |
|----|---------|---------|
| I1 | Connected integrations grid | Cards for each integration: Shopify, Slack, Zendesk, Gmail, Freshdesk, Intercom. Each shows: connected/disconnected status, last sync time, error count. Backend `/api/integrations` exists |
| I2 | Connect new integration | "Add Integration" button. Modal with available integrations. OAuth flow or API key input depending on service. Backend `integration_service.py` handles 6 real integrations |
| I3 | Integration detail | Click integration card: shows configuration, sync history, error log, connected resources (e.g., Shopify stores, Slack channels). Test connection button. Disconnect button (with confirmation) |
| I4 | Webhook management | List of all configured webhooks. Add new webhook (URL, events to subscribe to, secret). Test webhook (send test event). Show delivery history (success/fail, response code, latency). Backend `/api/webhooks` exists |
| I5 | Custom integrations | "Custom Webhook" card for integrations not in the pre-built list. URL + headers + event mapping. Encrypted credential storage. Backend `custom_integration_service.py` exists |
| I6 | Channel configuration | Sub-section: Email channel (SMTP settings), SMS channel (Twilio settings), Chat widget (embed code), Voice channel (Twilio voice settings). Backend `channel_service.py` + `email_channel_service.py` + `sms_channel_service.py` exist |
| I7 | Integration health dashboard | Overall health: X connected, Y with errors. Error timeline. Auto-retry status. Circuit breaker status. |

#### Notifications Center Page:

| ID | Feature | Details |
|----|---------|---------|
| N1 | Notification list | Chronological list of all notifications. Each: icon, title, description, timestamp, read/unread state. Group by: Today, Yesterday, This Week, Earlier. Infinite scroll |
| N2 | Notification types | Visual icons per type: ticket new (blue), ticket resolved (green), escalated (red), approval needed (orange), system alert (gray), payment (purple), training (cyan) |
| N3 | Mark as read / Mark all read | Click notification marks as read. "Mark All as Read" button at top. Read notifications become muted style |
| N4 | Filter by type | Filter: All, Tickets, Approvals, System, Billing, Training. Each type shows count |
| N5 | Notification preferences | Link to Settings -> Notifications tab. Per-type toggle: email, in-app, push. Digest mode: daily/weekly summary. Backend `notification_preference_service.py` exists |
| N6 | Real-time notifications | Socket.io `notification:new` event adds notification to list with animation. Sound option toggle. Browser notification permission request |
| N7 | Quick actions from notifications | Ticket notifications: "View Ticket" button. Approval notifications: "Approve/Reject" buttons. System notifications: "View Details" button. No need to navigate away first |

**Day 7 Deliverables:**
- Full Billing page with plan, usage, upgrade/downgrade/cancel
- Invoice history with PDF download
- Buy additional agent/variant flows
- Full Integrations page with connect/disconnect
- Webhook management
- Notifications center with real-time updates
- Notification quick actions

**Day 7 Total: 24 items**

---

### DAY 8 — Settings Page + Approvals Page + Jarvis Sidebar + Polish
**Goal:** Complete all remaining pages, add Jarvis sidebar, polish everything.

#### Settings Page (Tabbed):

| ID | Tab/Feature | Details |
|----|------------|---------|
| ST1 | **Account tab** | Company name (editable), logo upload, timezone selector, language selector, industry. Save with confirmation. Backend `company_service.py` exists |
| ST2 | **Team tab** | Team members list with name, email, role, last active. "Invite Member" button: sends email invite with role selection (Admin/Manager/Agent/Viewer). Remove member (with confirmation). Role permission matrix shown. Backend `/api/admin` exists |
| ST3 | **Security tab** | Two-factor authentication (MFA) enable/disable. Backend `mfa_service.py` exists. Active sessions list. Revoke session. API key management: generate, view, revoke. Backend `api_key_service.py` exists |
| ST4 | **Notifications tab** | Notification preferences per type: toggle email/in-app/push. Digest settings: daily/weekly/never. Quiet hours (no notifications 10pm-8am). Backend `notification_preference_service.py` + `notification_template_service.py` exist |
| ST5 | **API & Webhooks tab** | API documentation link. Rate limit info. Webhook configuration (or link to full Integrations page). API usage stats |

#### Approvals Page:

| ID | Feature | Details |
|----|---------|---------|
| AP1 | Approvals queue | Tabs: All / Pending / Approved / Rejected / Timed Out. Each approval card shows: ticket ID, AI recommendation, action description, confidence score, reason, financial impact amount. Approve/Reject/Skip buttons. Auto-timeout for pending approvals |
| AP2 | Approval detail | Click approval opens: full conversation context, AI reasoning, financial impact breakdown, risk assessment. Approve/Reject with optional comment |
| AP3 | Approval rules | Settings: auto-approve above X% confidence, auto-reject below Y%, require human approval for actions above $Z amount. Configure per action type |
| AP4 | Approval analytics | Charts: approval rate, average time to approve, most common approval reasons, rejection patterns |
| AP5 | Bulk approvals | Select multiple pending approvals. Bulk approve/reject. Confirmation dialog showing total financial impact |

#### Jarvis Sidebar Panel:

| ID | Feature | Details |
|----|---------|---------|
| J1 | Sidebar chat button | Jarvis button at bottom of sidebar. Chat bubble icon with subtle pulse animation. Unread message indicator |
| J2 | Slide-in panel | Click button -> panel slides in from right. Dashboard stays visible behind. Panel width: 400px. Overlay on mobile |
| J3 | Chat interface | Message list, input box, send button. Jarvis context-aware: knows current page, plan, usage, recent events. Quick command buttons: "Train from errors", "View savings", "Upgrade plan", "System status" |
| J4 | Quick actions | Buttons below chat: common Jarvis commands as one-click actions. Results shown inline in chat |
| J5 | Close panel | X button + click outside panel closes it. Chat history preserved (Jarvis remembers context) |

#### Audit Log Viewer (Settings sub-section or separate):

| ID | Feature | Details |
|----|---------|---------|
| AU1 | Audit log list | Chronological log of all system actions. Columns: Timestamp, User/Agent, Action, Category, Severity, Details. Filter by category (Auth, Billing, System, Ticket, AI, Admin, Data, Config). Backend `audit_log_service.py` exists |
| AU2 | Audit log search | Search by user, action type, date range. Export filtered results as CSV/PDF |
| AU3 | Compliance export | "Export for Compliance" button. Generates full audit report in compliance format. Backend supports JSON/CSV compliance export |
| AU4 | Tamper detection | SHA-256 integrity verification status. Shows if any log entries have been tampered with. Alert indicator if tampering detected |

#### Final Polish:

| ID | Feature | Details |
|----|---------|---------|
| P1 | Responsive design | All pages work on mobile (320px), tablet (768px), desktop (1024px+), ultrawide (1440px+). Sidebar collapses to hamburger on mobile. Tables become card view on mobile |
| P2 | Loading states | Skeleton loaders for all pages. Spinner for actions. Progress bars for uploads/exports. No blank pages while loading |
| P3 | Empty states | Every page has a meaningful empty state: "No tickets yet" with illustration and CTA. "No agents — hire your first AI agent". "No integrations — connect your first app" |
| P4 | Error states | Graceful error handling. Network error retry. API error display with helpful messages. Fallback data where appropriate |
| P5 | Breadcrumbs | Every page shows navigation path: Dashboard > Agents > Agent Detail. Clickable for easy back-navigation |
| P6 | Keyboard shortcuts | Common shortcuts: Ctrl+K (search), Esc (close panels), J/K (navigate list items) |
| P7 | Onboarding hints | First-time tooltips: "Here's where you can see your AI agents". Dismissible. Show once per feature |

**Day 8 Deliverables:**
- Complete Settings page with all tabs
- Approvals page with queue and rules
- Jarvis sidebar panel
- Audit log viewer
- Responsive design across all breakpoints
- Loading/empty/error states
- Polish (breadcrumbs, shortcuts, onboarding hints)

**Day 8 Total: 26 items**

---

## COMPLETE ITEM SUMMARY

| Day | Focus | Items | Cumulative |
|-----|-------|-------|------------|
| Day 1 | Header Bar, Sidebar, Socket.io Client | 20 | 20 |
| Day 2 | Overview Page, ROI, First Victory | 10 | 30 |
| Day 3 | Tickets Page (Full Build) | 20 | 50 |
| Day 4 | Agents Page, Per-Agent Views, Call Records | 15 | 65 |
| Day 5 | Customers (CRM), Conversations | 22 | 87 |
| Day 6 | Knowledge Base, Analytics | 18 | 105 |
| Day 7 | Billing, Integrations, Notifications | 24 | 129 |
| Day 8 | Settings, Approvals, Jarvis Sidebar, Polish | 26 | 155 |

**Total: 155 items across 8 days**

---

## BACKEND APIs ALREADY BUILT (just need frontend)

| Backend Service | API Endpoint(s) | Frontend Status |
|-----------------|-----------------|-----------------|
| `agent_dashboard_service.py` | `/api/agents/dashboard` | Needs frontend |
| `agent_metrics_service.py` | `/api/agent_metrics` | Needs frontend |
| `agent_provisioning_service.py` | `/api/agent_provisioning` | Needs frontend |
| `conversation_service.py` | `/api/conversations` | Needs frontend |
| `conversation_summarization.py` | Inline in conversations | Needs frontend |
| `customer_service.py` | `/api/customers` | Needs frontend |
| `lead_service.py` | `/api/leads` | Needs frontend |
| `identity_resolution_service.py` | Inline in customer merge | Needs frontend |
| `knowledge_base/manager.py` | `/api/knowledge-base` | Needs frontend |
| `knowledge_base/retriever.py` | `/api/rag` | Needs frontend |
| `knowledge_base/vector_search.py` | Inline in RAG | Needs frontend |
| `file_storage_service.py` | `/api/files` | Needs frontend |
| `attachment_service.py` | `/api/attachments` | Needs frontend |
| `billing.py` (API) | `/api/billing` | Needs frontend |
| `subscription_service.py` | `/api/subscription` | Needs frontend |
| `invoice_service.py` | `/api/invoices` | Needs frontend |
| `proration_service.py` | Inline in upgrade/downgrade | Needs frontend |
| `overage_service.py` | Inline in billing | Needs frontend |
| `payment_failure_service.py` | Inline in billing alerts | Needs frontend |
| `notification_service.py` | `/api/notifications` | Needs frontend |
| `notification_preference_service.py` | Inline in settings | Needs frontend |
| `integration_service.py` | `/api/integrations` | Needs frontend |
| `custom_integration_service.py` | `/api/custom-integrations` | Needs frontend |
| `webhook_service.py` | `/api/webhooks` | Needs frontend |
| `export_service.py` | `/api/reports` | Needs frontend |
| `audit_log_service.py` | `/api/audit` | Needs frontend (new endpoint) |
| `activity_log_service.py` | Inline in timeline | Needs frontend |
| `system_status_service.py` | **NO ENDPOINT** | Needs API endpoint + frontend |
| `analytics/savings` | `/api/analytics/savings` | Needs frontend |
| `analytics/adaptation` | `/api/analytics/adaptation` | Needs frontend |
| `analytics/forecast` | `/api/analytics/forecast` | Needs frontend |
| `analytics/csat-trends` | `/api/analytics/csat-trends` | Needs frontend |
| `analytics/growth-nudges` | `/api/analytics/growth-nudges` | Needs frontend |

---

## ORPHANED COMPONENTS TO WIRE

| Component | Location | Target Page |
|-----------|----------|-------------|
| `ConfidenceTrend.tsx` | `components/dashboard/` | Analytics (Day 6) + Agent Detail (Day 4) |
| `AdaptationTracker.tsx` | `components/dashboard/` | Analytics (Day 6) + Agent Detail (Day 4) |
| `ROIDashboard.tsx` | `components/dashboard/` | Analytics (Day 6) + Overview (Day 2) |
| `CSATTrends.tsx` | `components/dashboard/` | Analytics (Day 6) |
| `QAScores.tsx` | `components/dashboard/` | Analytics (Day 6) |
| `DriftDetection.tsx` | `components/dashboard/` | Analytics (Day 6) |
| `GrowthNudge.tsx` | `components/dashboard/` | Analytics (Day 6) + Overview (Day 2) |
| `TicketForecast.tsx` | `components/dashboard/` | Analytics (Day 6) |

---

## DEPENDENCIES ON OTHER PARTS

| Dependency | Part | Impact on Dashboard |
|------------|------|---------------------|
| Shadow Mode (Shadow/Supervised/Graduated) | Part 11 | Mode Selector in header — shows placeholder if Part 11 not done |
| Real LLM responses (not mock) | Part 9 | Confidence scores may show mock data if Part 9 not wired |
| Real voice channel | Part 14 | Call recording playback needs real voice data |
| Paddle yearly billing | Part 15 | Upgrade/downgrade flows use Paddle |
| Real training pipeline | Part 6 | "Train from errors" needs real training backend |

**Dashboard can be built independently** — all pages show available data. When dependent parts are completed later, the dashboard pages automatically show real data.

---

## VERIFICATION CHECKLIST (after all 8 days)

- [ ] All 13 sidebar links navigate to working pages
- [ ] Header bar has all 8 items functional
- [ ] Socket.io client connected with live events
- [ ] Overview page shows ROI, First Victory, savings counter
- [ ] Tickets page: list, detail, conversation, filters, export
- [ ] Agents page: cards, per-agent view, LIVE activity, call records
- [ ] Customers page: CRM list, detail, timeline, lead pipeline
- [ ] Conversations page: all channels, call playback, summaries
- [ ] Approvals page: queue, approve/reject, rules
- [ ] Analytics page: all 8 orphaned components wired
- [ ] Knowledge Base page: upload, search, RAG test
- [ ] Billing page: plan, usage, upgrade/downgrade/cancel, invoices
- [ ] Integrations page: connect/disconnect, webhooks, channels
- [ ] Notifications center: real-time, preferences, quick actions
- [ ] Settings page: Account, Team, Security, Notifications, API tabs
- [ ] Jarvis sidebar panel: chat, quick actions
- [ ] Audit log viewer: search, export, tamper detection
- [ ] Emergency pause button works
- [ ] Responsive on mobile/tablet/desktop
- [ ] Loading/empty/error states on all pages
