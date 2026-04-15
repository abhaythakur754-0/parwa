# Part 12: Dashboard System — Complete Architecture

> **Status:** 8-Day Build Plan Ready — See PART12_DASHBOARD_8DAY_PLAN.md
> **Priority:** P1 — Core product UI
> **Current:** ~30% complete (3 of 7 pages work, 8 components orphaned, 7 backend modules have ZERO frontend)
> **Total Items:** 155 items across 8 days
> **Dependencies:** None (can run parallel with Part 18 + Part 15)

---

## The Dashboard Problem

The dashboard is NOT just 4 missing pages. It's the **entire client experience** — everything a paying customer ($999-$3999/month) sees after logging in. Currently:

- 4 sidebar links are **404** (Tickets, Agents, Approvals, Settings)
- 8 dashboard components are **built but orphaned** (no page renders them)
- Backend has 867 lines of system status code with **no endpoint and no UI**
- No **Socket.io client** on frontend — everything polls instead of live updates
- No **user menu, logout, plan badge, emergency pause, mode selector** in the header
- No way to **upgrade, downgrade, cancel, buy additional variants**
- No **per-agent view** (what is each agent doing right now?)
- No **call records / conversation logs** view
- Jarvis is **not accessible from the dashboard sidebar**
- **Customers (CRM) page missing** — 5 backend services built, 0 frontend
- **Conversations / Call Records page missing** — 5 backend services built, 0 frontend
- **Knowledge Base page missing** — 6+ backend services built, 0 frontend
- **Billing page missing** — 10+ backend services built, 0 frontend
- **Integrations page missing** — 12+ backend services built, 0 frontend
- **Notifications center missing** — 5 backend services built, 0 frontend
- **Audit log viewer missing** — 3 backend services built, 0 frontend
- **Per-agent individual views missing** (client specifically asked: what is each agent doing)
- **Call recording playback missing** (client specifically asked: listen to conversations)
- **Document management missing** (client specifically asked: see their documents)

---

## Complete Dashboard Architecture

### Layout Structure

```
┌──────────────────────────────────────────────────────────────────┐
│  [HEADER BAR]                                                    │
│  Logo | Company | Plan Badge | Notif | Status | Pause | Mode | User │
├────────────┬─────────────────────────────────────────────────────┤
│            │                                                     │
│  SIDEBAR   │              MAIN CONTENT AREA                      │
│            │                                                     │
│  Overview  │   (changes based on sidebar selection)              │
│  Tickets   │                                                     │
│  Agents    │                                                     │
│  Customers │   ← NEW: CRM, leads, profiles                        │
│  Conversations│ ← NEW: Call records, transcripts, playback          │
│  Approvals │                                                     │
│  Analytics │   ← NEW: 8 orphaned components                       │
│  Knowledge │   ← NEW: Documents, upload, RAG                     │
│  Channels  │                                                     │
│  Billing   │   ← NEW: Plan, invoices, upgrade/downgrade          │
│  Integrations│ ← NEW: Connected apps, webhooks                     │
│  Settings  │                                                     │
│  ──────    │                                                     │
│  Jarvis 💬 │                                                     │
│            │                                                     │
└────────────┴─────────────────────────────────────────────────────┘
```

---

## 1. HEADER BAR — What Should Be There

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [PARWA] Acme Corp  │  [PARWA $2,499/mo ▾]  │  🔔 3  │  🟢 All Systems  │  │
│                     │                        │       │  ⚡ Emergency Pause │  │
│                     │                        │       │  🔄 Shadow Mode ▾   │  │
│                     │                        │       │  👤 John ▾          │  │
│                     │                        │       │    Profile          │  │
│                     │                        │       │    Settings         │  │
│                     │                        │       │    ─────────       │  │
│                     │                        │       │    Logout           │  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Header Items Breakdown:

| # | Item | What it does | Status |
|---|------|-------------|--------|
| H1 | **Logo + Company Name** | Shows PARWA logo + tenant company name | ✅ Logo exists, company name not in header |
| H2 | **Plan Badge** | Shows "Mini PARWA $999" or "PARWA $2,499" or "PARWA High $3,999". Clicking opens billing settings with upgrade/downgrade options | ❌ Missing |
| H3 | **Notification Bell** | Shows unread count badge. Dropdown: recent notifications (new ticket, AI resolved, approval needed, etc.) | ⚠️ DashboardAlerts exists, not wired as bell dropdown |
| H4 | **System Status Indicator** | Green dot = all healthy, Yellow = degraded, Red = down. Clicking shows which services are affected | ❌ Missing (867-line backend exists, no frontend) |
| H5 | **Emergency Pause Button** | ONE CLICK stops ALL AI agents immediately. Red button, prominent. Requires confirm dialog. | ❌ Missing (critical safety feature) |
| H6 | **Mode Selector Dropdown** | Shadow / Supervised / Graduated. Only visible when Shadow Mode is enabled (Part 11). Shows current mode with icon. | ❌ Missing (Part 11 depends on this) |
| H7 | **User Menu Dropdown** | User name + avatar/initials. Dropdown: Profile, Account Settings, Help/Docs, Logout. | ⚠️ UserMenu.tsx exists but not in dashboard header |
| H8 | **Logout** | Inside user menu. Clears session, redirects to login. | ⚠️ Exists in AuthContext, not connected to dashboard header |

---

## 2. SIDEBAR — Navigation Structure

```
┌──────────────────────┐
│   📊 Overview        │  ← Home dashboard
│   🎫 Tickets         │  ← All support tickets
│   🤖 Agents          │  ← AI workforce + per-agent views
│   👥 Customers       │  ← CRM, profiles, leads (NEW)
│   💬 Conversations   │  ← Call records, transcripts (NEW)
│   ✅ Approvals       │  ← AI action approvals
│   📈 Analytics       │  ← Charts, ROI, trends (NEW)
│   📄 Knowledge Base  │  ← Documents, upload, RAG (NEW)
│   📡 Channels        │  ← Email, SMS, Chat, Voice
│   💰 Billing         │  ← Plan, invoices, upgrade (NEW)
│   🔗 Integrations    │  ← Connected apps, webhooks (NEW)
│   ⚙️ Settings        │  ← Account, team, security
│   ─────────────────  │
│   🤖 Jarvis          │  ← Opens chat side panel
└──────────────────────┘
```

### Sidebar Items:

| # | Route | Label | Status |
|---|-------|-------|--------|
| S1 | `/dashboard` | Overview | ✅ Exists |
| S2 | `/dashboard/tickets` | Tickets | ❌ 404 |
| S3 | `/dashboard/agents` | Agents | ❌ 404 |
| S4 | `/dashboard/customers` | Customers (CRM) | ❌ DOES NOT EXIST |
| S5 | `/dashboard/conversations` | Conversations | ❌ DOES NOT EXIST |
| S6 | `/dashboard/approvals` | Approvals | ❌ 404 |
| S7 | `/dashboard/analytics` | Analytics | ❌ DOES NOT EXIST |
| S8 | `/dashboard/knowledge-base` | Knowledge Base | ❌ DOES NOT EXIST |
| S9 | `/dashboard/channels` | Channels | ✅ Exists |
| S10 | `/dashboard/billing` | Billing | ❌ DOES NOT EXIST |
| S11 | `/dashboard/integrations` | Integrations | ❌ DOES NOT EXIST |
| S12 | `/dashboard/settings` | Settings | ❌ 404 |
| S13 | Side panel | Jarvis | ⚠️ Page exists, not in sidebar |

---

## 3. OVERVIEW PAGE (`/dashboard`) — Enhance What Exists

The home page exists but needs more widgets. Current + what's missing:

### Current (Working):
- ✅ KPI Cards (tickets resolved, auto-resolve %, avg response time, CSAT)
- ✅ Activity Feed (recent events)
- ✅ Workforce Allocation Chart
- ✅ Savings Counter (small widget)

### Add to Home:

| # | Widget | Description | Component Status |
|---|--------|-------------|-----------------|
| O1 | **ROI Comparison Card (PROMINENT)** | Big card showing: "You saved $X vs hiring humans" with breakdown. Comparison table: PARWA cost vs human agent cost vs competitor cost. This is the SELL card. | `ROIDashboard.tsx` built but orphaned |
| O2 | **First Victory Banner** | Celebration banner when AI resolves first ticket. "🎉 Your AI just resolved its first ticket! In 47 seconds." Shows for 24 hours then dismisses. | `FirstVictory.tsx` exists in onboarding only |
| O3 | **System Health Strip** | Horizontal strip at top: LLM ✅ | Redis ✅ | Database ✅ | Channels ✅. If anything is down, turns red with link to details. | Backend `system_status_service.py` exists, no frontend |
| O4 | **Growth Nudge Card** | Smart CTA: "Upgrade to PARWA High and save an additional $50K/year" based on their usage patterns. | `GrowthNudge.tsx` built but orphaned |
| O5 | **Active Agents Summary** | Quick view: "3 agents active, 2 paused, 127 tickets handled today." Each agent with mini confidence bar. | Backend `agent_dashboard_service.py` exists, no frontend widget |
| O6 | **Recent Approvals** | Last 3 approval items (approved/rejected/pending) with quick action buttons. | Backend exists, no frontend widget |

### Home Page Layout (Revised):

```
┌─────────────────────────────────────────────────────────┐
│  🟢 System Health: LLM ✅ Redis ✅ DB ✅ Email ✅ SMS ✅ │
├────────────────┬────────────────────────────────────────┤
│                │                                        │
│  KPI Card 1    │     💰 ROI COMPARISON (BIG)            │
│  KPI Card 2    │     "You saved $156,240 this month"     │
│  KPI Card 3    │     vs $312,000 with human agents      │
│  KPI Card 4    │     vs $420,000 with Intercom           │
│                │                                        │
├────────────────┴────────────────────────────────────────┤
│                                                         │
│  🤖 Active Agents:  [Agent 1: 89%] [Agent 2: 92%] [+]  │
│                                                         │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│  Activity Feed       │  💡 Growth Nudge                  │
│  (real-time)         │  "Upgrade to PARWA High"          │
│                      │                                  │
├──────────────────────┴──────────────────────────────────┤
│                                                         │
│  📊 Workforce Allocation     |  🎉 First Victory Banner  │
│                              |  (when applicable)        │
└─────────────────────────────────────────────────────────┘
```

---

## 4. TICKETS PAGE (`/dashboard/tickets`) — BUILD FROM SCRATCH

The most important missing page. This is where clients see ALL their customer conversations.

### Ticket List View:

```
┌──────────────────────────────────────────────────────────────────┐
│  🎫 Tickets                                    [+ New Ticket]   │
│                                                                   │
│  [Search: "order refund"]  [Status ▾] [Channel ▾] [Agent ▾]     │
│  [Date Range]  [Priority ▾]  [AI Confidence ▾]                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  #1247  │ 🔴 High  │ AI resolved │ E-commerce │ Chat │ 94% │ 2m │
│  #1246  │ 🟡 Medium│ Pending     │ SaaS       │ Email│ 87% │ 5m │
│  #1245  │ 🟢 Low   │ Escalated   │ Logistics  │ SMS  │ 62% │ 1h │
│  #1244  │ 🔴 High  │ In progress │ E-commerce │ Chat │ —   │ 3m │
│  #1243  │ 🟡 Medium│ AI resolved │ SaaS       │ Email│ 91% │ 12m│
│                                                                   │
│  Showing 1-25 of 1,247 tickets        [< 1 2 3 ... 50 >]        │
└──────────────────────────────────────────────────────────────────┘
```

### Ticket Detail View (click a ticket):

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Back to Tickets    Ticket #1247    🔴 High    AI Resolved     │
├─────────────────────────────┬────────────────────────────────────┤
│                             │                                    │
│  CONVERSATION               │  TICKET INFO                       │
│                             │                                    │
│  🧑 Customer: "Where's my  │  Channel: Chat                     │
│     order #ORD-4521?"       │  Agent: E-commerce Agent 1         │
│                             │  Variant: PARWA $2,499             │
│  🤖 PARWA: "Let me look    │  AI Confidence: 94%                │
│     that up for you..."     │  Resolution Time: 47 seconds       │
│     [Tracked order] ✅      │  GSD State: RESOLUTION → CLOSED    │
│                             │  Technique: CLARA + CRP            │
│  🧑 Customer: "Great,       │  Sentiment: Positive 😊            │
│     thanks!"                │  Language: English                  │
│                             │  Priority: High                    │
│  🤖 PARWA: "Happy to help!  │                                    │
│     Anything else?"          │  ─────────────────────            │
│                             │  ACTIONS                            │
│  🧑 Customer: "No that's    │  [Escalate to Human]              │
│     it, thanks."            │  [Reassign to Agent ▾]            │
│                             │  [Add Internal Note]               │
│  ✅ RESOLVED                │  [View Full Transcript]           │
│                             │  [Export Conversation]             │
│                             │                                    │
├─────────────────────────────┴────────────────────────────────────┤
│  📝 Internal Notes (only visible to team):                      │
│  "Customer was frustrated initially, AI handled well." - Sarah   │
└──────────────────────────────────────────────────────────────────┘
```

### Ticket Page Features:

| # | Feature | Description | Priority |
|---|---------|-------------|----------|
| T1 | Ticket list with pagination | 25 per page, search, sort | P0 |
| T2 | Multi-filter | Status, channel, agent, priority, confidence, date | P0 |
| T3 | Ticket detail view | Full conversation + metadata side panel | P0 |
| T4 | Conversation transcript | See entire customer ↔ AI chat history | P0 |
| T5 | AI confidence per ticket | Show confidence score with color coding | P0 |
| T6 | GSD state visualization | NEW → GREETING → DIAGNOSIS → RESOLUTION → CLOSED | P1 |
| T7 | AI technique used | Which technique(s) fired (CLARA, ReAct, etc.) | P1 |
| T8 | Sentiment analysis | Show customer sentiment per message | P1 |
| T9 | Escalate to human | Button to escalate ticket | P0 |
| T10 | Internal notes | Team-only notes on tickets | P1 |
| T11 | Export conversation | Download as PDF/CSV | P2 |
| T12 | Real-time updates | New tickets appear via Socket.io without refresh | P1 |

---

## 5. AGENTS PAGE (`/dashboard/agents`) — BUILD FROM SCRATCH

This is where clients manage their AI workforce. Multiple agents, multiple variants.

### Agent Grid View:

```
┌──────────────────────────────────────────────────────────────────┐
│  🤖 AI Agents                          [+ Add Agent] [+$999/mo]  │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │  E-com Agent 1  │  │  SaaS Agent     │  │  Logistics Agent│   │
│  │  🟢 Active      │  │  🟢 Active      │  │  ⏸️ Paused      │   │
│  │                 │  │                 │  │                 │   │
│  │  Variant: PARWA │  │  Variant: Mini  │  │  Variant: PARWA │   │
│  │  Confidence: 94%│  │  Confidence: 87%│  │  Confidence: 91%│   │
│  │  Tickets: 847   │  │  Tickets: 312   │  │  Tickets: 198   │   │
│  │  Resolved: 89%  │  │  Resolved: 82%  │  │  Resolved: 85%  │   │
│  │                 │  │                 │  │                 │   │
│  │  [Pause] [View] │  │  [Pause] [View] │  │  [Resume] [View]│   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Detail View (click "View" on an agent):

```
┌──────────────────────────────────────────────────────────────────┐
│  ← Back to Agents        E-commerce Agent 1     🟢 Active        │
├────────────────────────────────┬─────────────────────────────────┤
│                                │                                 │
│  AGENT METRICS                 │  CURRENT ACTIVITY (LIVE)        │
│                                │                                 │
│  Confidence (7-day avg): 94%  │  🔄 Currently handling:          │
│  ████████████████░░░░         │  Ticket #1248 — "Refund status"  │
│                                │  Channel: Chat | 45 seconds in   │
│  Tickets today: 47             │  Confidence: 96%                 │
│  Tickets this week: 312        │  Technique: CLARA                 │
│  Auto-resolved: 89%            │  ───────────────────────         │
│  Avg response time: 38s        │  🔄 Ticket #1247 — "Track order" │
│  Escalated: 11 (3.5%)         │  Channel: Email | Pending        │
│  CSAT: 4.6/5.0                │                                 │
│                                │  ✅ Ticket #1246 — "Cancel sub"  │
│  ──────────────────────       │  Resolved in 52s | 94% conf     │
│                                │                                 │
│  CALL RECORDS (Recent)         │  PERFORMANCE TRENDS              │
│                                │                                 │
│  #1248 Chat  47s   96% ✅     │  [Confidence Trend Chart]        │
│  #1247 Chat  38s   94% ✅     │  [Resolution Rate Chart]         │
│  #1246 Email  2m   91% ✅     │  [Ticket Volume Chart]           │
│  #1245 SMS    1m   88% ⚠️     │                                 │
│  #1244 Chat  45s   82% ✅     │                                 │
│  [View All Records →]         │                                 │
│                                │                                 │
├────────────────────────────────┴─────────────────────────────────┤
│  ACTIONS: [Pause Agent] [Edit Config] [View Full Logs] [Train]   │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Page Features:

| # | Feature | Description | Priority |
|---|---------|-------------|----------|
| A1 | Agent cards grid | Visual cards for each agent with status | P0 |
| A2 | Pause/Resume per agent | Individual agent control | P0 |
| A3 | **Current activity (LIVE)** | What is this agent doing RIGHT NOW | P0 — **User specifically asked for this** |
| A4 | **Call records / conversation logs** | See what each agent said/did per ticket | P0 — **User specifically asked for this** |
| A5 | Per-agent metrics | Confidence, tickets, resolution rate, CSAT | P0 |
| A6 | Add new agent | Create additional AI agent (+$X/month) | P1 |
| A7 | Performance trend charts | Per-agent confidence, volume, resolution trends | P1 |
| A8 | Agent configuration | Edit variant, KB, system prompt | P2 |
| A9 | Train from this agent's errors | Quick button to trigger retraining | P2 |
| A10 | Multi-agent comparison | Compare agent performance side-by-side | P2 |

---

## 6. APPROVALS PAGE (`/dashboard/approvals`) — BUILD FROM SCRATCH

Where humans oversee AI decisions. Critical for Shadow Mode (Part 11).

### Approvals Queue:

```
┌──────────────────────────────────────────────────────────────────┐
│  ✅ Approvals                                   [Pending (5)]     │
│                                                                   │
│  [All] [Pending] [Approved] [Rejected] [Timed Out]               │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  🔴 PENDING — Action Required                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Ticket #1247 | AI wants to: Issue $150 refund             │  │
│  │ Confidence: 94% | Reason: "Customer has valid 30-day..."   │  │
│  │                                                            │  │
│  │ 💰 Financial Impact: -$150                                │  │
│  │                                                            │  │
│  │ [✅ Approve]  [❌ Reject]  [📝 Edit Response]  [⏭ Skip]   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Ticket #1245 | AI wants to: Escalate to billing team     │  │
│  │ Confidence: 62% | Reason: "Customer requesting custom..."  │  │
│  │                                                            │  │
│  │ [✅ Approve]  [❌ Reject]  [📝 Edit Response]  [⏭ Skip]   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ✅ APPROVED (Recent)                                            │
│  #1243 | Refund $45 | Approved by Sarah | 2 hours ago           │
│  #1240 | Free shipping | Auto-approved (95% conf) | 3 hours ago │
│  #1238 | Escalate | Approved by Mike | 5 hours ago              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. ANALYTICS PAGE (`/dashboard/analytics`) — NEW, Wire Orphaned Components

This is where ALL 8 orphaned chart components finally get a home.

```
┌──────────────────────────────────────────────────────────────────┐
│  📈 Analytics                                   [Date Range ▾]    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  💰 ROI COMPARISON (TOP — PROMINENT)                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  PARWA Cost    │  Human Agents    │  Intercom              │  │
│  │  $2,499/mo     │  $12,000/mo       │  $4,500/mo             │  │
│  │  $156K saved   │  —                │  $78K saved vs this     │  │
│  │                                                            │  │
│  │  [Monthly view] [Yearly view] [Export Report]               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Confidence   │  │ Adaptation   │  │ CSAT Trends  │           │
│  │ Trend 📈     │  │ Tracker 🔄   │  │ 😊 ⭐⭐⭐⭐   │           │
│  │              │  │              │  │              │           │
│  │ [Component]  │  │ [Component]  │  │ [Component]  │           │
│  │ EXISTS ✅    │  │ EXISTS ✅    │  │ EXISTS ✅    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Ticket       │  │ Drift        │  │ QA Scores    │           │
│  │ Forecast 📊  │  │ Detection ⚠️ │  │ Quality 🎯   │           │
│  │              │  │              │  │              │           │
│  │ [Component]  │  │ [Component]  │  │ [Component]  │           │
│  │ EXISTS ✅    │  │ EXISTS ✅    │  │ EXISTS ✅    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 💡 Growth Nudge: "Upgrade to PARWA High to handle 40%     │  │
│  │    more tickets with the same AI quality." [Upgrade →]     │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Analytics Sections:

| # | Section | Component | Status | Description |
|---|---------|-----------|--------|-------------|
| AN1 | **ROI Comparison** | `ROIDashboard.tsx` | Built, orphaned | BIG card at top. PARWA cost vs human agents vs competitors. Monthly/yearly toggle. Exportable. |
| AN2 | **Confidence Trend** | `ConfidenceTrend.tsx` | Built, orphaned | Line chart: AI confidence over time. Per-agent and overall. |
| AN3 | **Adaptation Tracker** | `AdaptationTracker.tsx` | Built, orphaned | How fast the AI is learning. Accuracy improvements after training. |
| AN4 | **CSAT Trends** | `CSATTrends.tsx` | Built, orphaned | Customer satisfaction scores over time. Per-channel breakdown. |
| AN5 | **Ticket Forecast** | `TicketForecast.tsx` | Built, orphaned | Predict next week/month ticket volume based on trends. |
| AN6 | **Drift Detection** | `DriftDetection.tsx` | Built, orphaned | Is the AI getting worse? Accuracy dropping? Needs retraining? |
| AN7 | **QA Scores** | `QAScores.tsx` | Built, orphaned | Quality assurance scores for AI responses. |
| AN8 | **Growth Nudge** | `GrowthNudge.tsx` | Built, orphaned | Smart upgrade CTA based on usage patterns. |

---

## 8. SETTINGS PAGE (`/dashboard/settings`) — BUILD FROM SCRATCH

Settings should be a tabbed page, not separate sub-pages:

```
┌──────────────────────────────────────────────────────────────────┐
│  ⚙️ Settings                                                      │
├──────────────────────────────────────────────────────────────────┤
│  [Account] [Billing] [Team] [Notifications] [Integrations] [API] │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  BILLING TAB (example):                                           │
│                                                                   │
│  Current Plan: PARWA $2,499/month                                 │
│  ├── 10,000 tickets/mo included                                   │
│  ├── 3 AI agents included                                         │
│  ├── All channels (Email, SMS, Chat)                              │
│  └── Billing date: May 1, 2026                                    │
│                                                                   │
│  [Upgrade to PARWA High $3,999] [Downgrade to Mini $999]         │
│                                                                   │
│  ────────────────────────                                         │
│                                                                   │
│  Usage This Period:                                               │
│  Tickets: 7,432 / 10,000 (74%)     ████████████████░░░           │
│  Agents: 2 / 3 (67%)                                             │
│  Storage: 2.1 GB / 5 GB                                          │
│                                                                   │
│  ────────────────────────                                         │
│                                                                   │
│  [Cancel Subscription] (with confirmation + reason + save offer)  │
│                                                                   │
│  Invoice History:                                                 │
│  April 2026 — $2,499 — [Download PDF]                            │
│  March 2026 — $2,499 — [Download PDF]                            │
│  February 2026 — $2,499 — [Download PDF]                         │
└──────────────────────────────────────────────────────────────────┘
```

### Settings Tabs:

| # | Tab | What's Inside | Priority |
|---|-----|--------------|----------|
| ST1 | **Account** | Company name, logo, timezone, language, industry | P0 |
| ST2 | **Billing** | Current plan, usage meters, upgrade/downgrade/cancel, invoice history, payment method | P0 |
| ST3 | **Team** | Invite team members, assign roles (Admin/Manager/Agent/Viewer), remove members | P1 |
| ST4 | **Notifications** | Email notifications toggle, in-app notification preferences, alert rules | P1 |
| ST5 | **Integrations** | Connected services (Shopify, Slack, CRM), webhook URLs, API connections | P1 |
| ST6 | **API Keys** | Generate/revoke API keys, usage stats, rate limit info | P2 |

### Missing Billing Flows:

| # | Flow | Description | Priority |
|---|------|-------------|----------|
| BF1 | **Upgrade** | Mini → PARWA → PARWA High. Paddle checkout. Prorated billing. | P0 |
| BF2 | **Downgrade** | Reverse. Warn about feature loss. Prorated credit. | P0 |
| BF3 | **Cancel** | Confirmation dialog with reason picker. Save offer ("Stay for 20% off"). | P0 |
| BF4 | **Buy additional agent** | "Add another AI agent for $X/month" — links to variant selection | P1 |
| BF5 | **Buy additional variant** | "Add Logistics variant to your PARWA plan" | P1 |
| BF6 | **Invoice history** | List + PDF download per invoice | P1 |

---

## 9. JARVIS IN SIDEBAR

Jarvis is the AI assistant that helps clients manage PARWA. Currently at `/jarvis` as a separate page. It should be accessible from the dashboard sidebar.

### Two Options:

**Option A: Side Panel (Recommended)**
- Click "Jarvis" in sidebar → chat panel slides in from right
- Dashboard stays visible behind the panel
- Can ask Jarvis questions while looking at dashboard data
- Close panel to go back to full dashboard view

**Option B: Separate Page**
- Click "Jarvis" in sidebar → navigates to `/jarvis`
- Full-page Jarvis chat experience
- Simple but loses dashboard context

### Recommended: Option A (Side Panel)
```
┌──────────────────────────────────┬───────────────────────────────┐
│                                  │  🤖 Jarvis AI Assistant        │
│  DASHBOARD                       │  ─────────────────────────    │
│  (visible behind panel)          │                               │
│                                  │  Jarvis: "How can I help you   │
│                                  │  manage PARWA today?"          │
│                                  │                               │
│                                  │  You: "What's my AI            │
│                                  │  confidence this week?"        │
│                                  │                               │
│                                  │  Jarvis: "Your average AI      │
│                                  │  confidence this week is 91%   │
│                                  │  — up from 87% last week.      │
│                                  │  E-commerce Agent 1 leads      │
│                                  │  at 94%. Want me to train      │
│                                  │  from recent errors?"          │
│                                  │                               │
│                                  │  [Quick: Train from errors]    │
│                                  │  [Quick: View savings]         │
│                                  │  [Quick: Upgrade plan]         │
│                                  │                               │
│                                  │  [Type a message...]     [→]   │
└──────────────────────────────────┴───────────────────────────────┘
```

---

## 10. REAL-TIME UPDATES (Socket.io)

Currently the dashboard polls APIs. Need to wire Socket.io for live updates.

### What Should Be Real-Time:

| Event | Trigger | UI Update |
|-------|---------|-----------|
| `ticket:new` | New customer ticket arrives | Ticket count increments, activity feed updates, notification bell |
| `ticket:resolved` | AI resolves a ticket | KPI card updates, activity feed, savings counter increments |
| `ticket:escalated` | Ticket escalated to human | Approvals badge count, notification |
| `ai:confidence_low` | AI confidence drops below threshold | Agent card turns yellow, notification |
| `agent:status_changed` | Agent paused/resumed | Agent card updates instantly |
| `approval:pending` | AI action needs approval | Approvals badge count, notification |
| `system:error` | Service goes down | System status turns red, notification |
| `notification:new` | Any notification | Bell icon badge count |

---

## COMPLETE FEATURE COUNT

| Section | Items | New Build | Wire Existing | Status |
|---------|-------|-----------|---------------|--------|
| Header Bar | 8 items | 5 new | 3 wire | Most missing |
| Sidebar | 13 links | 0 new | 10 add | Partial |
| Overview Page | 10 widgets | 6 new | 2 wire (orphaned) | 50% done |
| Tickets Page | 20 features | 20 new | 0 | 0% — 404 |
| Agents Page | 15 features | 15 new | 0 | 0% — 404 |
| Customers (CRM) | 10 features | 10 new | 0 | 0% — doesn't exist |
| Conversations | 12 features | 12 new | 0 | 0% — doesn't exist |
| Approvals Page | 5 features | 5 new | 0 | 0% — 404 |
| Analytics Page | 10 sections | 2 new | 8 wire (all orphaned!) | 0% — doesn't exist |
| Knowledge Base | 8 features | 8 new | 0 | 0% — doesn't exist |
| Billing Page | 10 features | 10 new | 0 | 0% — doesn't exist |
| Integrations Page | 7 features | 7 new | 0 | 0% — doesn't exist |
| Notifications Center | 7 features | 7 new | 0 | 0% — doesn't exist |
| Settings Page | 5 tabs + 4 audit items | 9 new | 0 | 0% — 404 |
| Jarvis Sidebar | 5 features | 5 new | 0 | Separate page only |
| Socket.io Client | 6 events | 1 new (client lib) | 6 wire | 0% — no client |
| System Status API | 1 endpoint | 1 new | 0 | Backend exists, no endpoint |
| Polish | 7 items | 7 new | 0 | N/A |
| **TOTAL** | **155 items** | **130 new builds** | **19 wire existing** | **~30% overall** |

---

## BUILD PRIORITY (If we have limited time)

### Must Have (Clients can't use product without these):
1. Header bar (user menu, logout, plan badge, notification bell)
2. Tickets page (list + detail + conversation view)
3. Agents page (cards + per-agent view + call records)
4. Customers / CRM page (customer profiles, search, ticket history)
5. Conversations page (transcripts, call recordings, summaries)
6. Billing page (plan, usage, upgrade/downgrade/cancel, invoices)
7. Socket.io client (real-time ticket + notification updates)

### Should Have (Important for value demonstration):
8. Approvals page
9. Analytics page (wire 8 orphaned components + ROI comparison)
10. Knowledge Base page (document management, upload, search)
11. Integrations page (connected apps, webhooks)
12. Notifications center
13. Emergency pause button
14. Jarvis in sidebar (side panel)
15. First Victory banner on dashboard

### Nice to Have:
16. Settings — Team tab (invite, roles)
17. Settings — Security tab (MFA, sessions, API keys)
18. Settings — Notifications tab
19. Audit log viewer
20. Mode selector (Shadow/Supervised/Graduated) — depends on Part 11
21. Polish (responsive, loading states, empty states, shortcuts)

---

## 8-DAY BUILD PLAN

Full day-by-day breakdown with 155 items: **[PART12_DASHBOARD_8DAY_PLAN.md](./PART12_DASHBOARD_8DAY_PLAN.md)**
