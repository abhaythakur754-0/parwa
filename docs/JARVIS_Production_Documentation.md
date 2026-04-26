# JARVIS PRODUCTION DOCUMENTATION
## PARWA AI Assistant - Complete Design Specification

**Version:** 2.0  
**Date:** April 2025  
**Status:** Production Ready  
**Inspired by:** Iron Man's Jarvis + OpenClaw Architecture

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Jarvis = UI + Superpowers](#2-jarvis--ui--superpowers)
3. [Jarvis Lifecycle](#3-jarvis-lifecycle)
4. [Awareness System](#4-awareness-system)
5. [Control Capabilities](#5-control-capabilities)
6. [Variant Integration](#6-variant-integration)
7. [Intelligence & Decision Making](#7-intelligence--decision-making)
8. [Memory System (OpenClaw-Inspired)](#8-memory-system-openclaw-inspired)
9. [Personality & Communication Style](#9-personality--communication-style)
10. [Proactive Alert System](#10-proactive-alert-system)
11. [Variant Tiers & Features](#11-variant-tiers--features)
12. [Technical Architecture](#12-technical-architecture)
13. [API Reference](#13-api-reference)
14. [Database Schema](#14-database-schema)
15. [Integration Points](#15-integration-points)
16. [Example Conversations](#16-example-conversations)

---

## 1. Executive Overview

### 1.1 What is Jarvis?

Jarvis is PARWA's AI-powered control room assistant, inspired by Iron Man's Jarvis and OpenClaw. It serves as the central intelligence hub for the entire PARWA platform, providing users with complete awareness of system state, control over all operations, and intelligent assistance through natural conversation.

### 1.2 Core Philosophy

Jarvis is designed to be:

| Principle | Description |
|-----------|-------------|
| **Human-like** | Friendly and professional, not robotic |
| **Aware** | Knows everything happening in the system |
| **Helpful** | Can execute actions and provide assistance |
| **Smart** | Knows when to act directly vs. ask for confirmation |
| **Remembering** | Retains context of all user activities |

### 1.3 Key Differentiators

Unlike traditional chatbots, Jarvis:

1. **Has complete system visibility** - Every click, action, and event is tracked
2. **Can execute real actions** - Not just respond, but actually DO things
3. **Remembers everything** - Full memory of user's day and past interactions
4. **Speaks up when important** - Proactive alerts for critical situations
5. **Adapts to user certainty** - Direct action vs. draft-then-approve based on context
6. **Controls variants** - Full control over Mini PARWA, PARWA, and PARWA High

---

## 2. Jarvis = UI + Superpowers

### 2.1 The Key Concept

**Jarvis can do EVERYTHING the Dashboard UI can do, PLUS more.**

```
┌─────────────────────────────────────────────────────────────────┐
│              UI AND JARVIS = SAME BACKEND                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐      ┌─────────────────────┐           │
│  │      DASHBOARD UI    │      │       JARVIS        │           │
│  │   (Click/Type)       │      │   (Talk/Chat)       │           │
│  └──────────┬──────────┘      └──────────┬──────────┘           │
│             │                             │                      │
│             │         SAME ACTIONS        │                      │
│             │    ═══════════════════      │                      │
│             │                             │                      │
│             ▼                             ▼                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    PARWA BACKEND                          │   │
│  │                                                           │   │
│  │  • Control Mini PARWA / PARWA / PARWA High               │   │
│  │  • Create/Assign/Close tickets                           │   │
│  │  • Pause/Resume AI agents                                │   │
│  │  • View analytics & reports                              │   │
│  │  • Manage integrations                                   │   │
│  │  • Send SMS/Email                                        │   │
│  │  • Everything UI can do                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 What Jarvis Has That UI Doesn't

| Feature | Dashboard UI | Jarvis |
|---------|--------------|--------|
| **Control variants** | ✅ | ✅ |
| **Create/assign tickets** | ✅ | ✅ |
| **Send SMS/Email** | ✅ | ✅ |
| **Manage integrations** | ✅ | ✅ |
| **View analytics** | ✅ | ✅ |
| **Full Awareness** | ❌ You have to look | ✅ Jarvis tells you |
| **Memory** | ❌ Doesn't remember | ✅ Remembers everything |
| **Proactive Alerts** | ❌ Won't tell you | ✅ Alerts you first |
| **Smart Suggestions** | ❌ No suggestions | ✅ Recommends actions |
| **Pattern Detection** | ❌ Manual analysis | ✅ Finds trends |
| **Natural Language** | ❌ Click buttons | ✅ Just talk |

### 2.3 Example: Same Action - UI vs JARVIS

| Action | UI Way | Jarvis Way |
|--------|--------|------------|
| Pause AI | Click "Pause" button | "Jarvis, pause AI" |
| View tickets | Go to Tickets page | "Jarvis, show me open tickets" |
| Create ticket | Click "New Ticket" form | "Jarvis, create ticket for John about his order" |
| Assign ticket | Click ticket → Select assignee | "Jarvis, assign ticket #123 to Sarah" |
| Send SMS | Go to Messages → Compose | "Jarvis, send SMS to +1234567890 about their delivery" |
| Check capacity | View Dashboard stats | "Jarvis, how's our capacity?" |
| View analytics | Go to Analytics page | "Jarvis, show me today's performance" |
| Approve refund | Click "Approve" in queue | "Jarvis, approve the refund for order #999" |

---

## 3. Jarvis Lifecycle

### 3.1 Jarvis Across User Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           JARVIS LIFECYCLE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  📍 LANDING PAGE                📍 ONBOARDING              📍 PRODUCTION    │
│  ──────────────                 ─────────────              ─────────────    │
│  • Pre-signup visitors          • After payment            • Full system    │
│  • Limited awareness            • Setup assistance         • Full awareness │
│  • Guide to signup              • Connect integrations     • Full control   │
│  • Answer questions             • Explain features         • All actions    │
│                                 • Help with config                          │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  EVERY ACTION → JARVIS KNOWS → JARVIS CAN HELP                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Stage Details

| Stage | When | Awareness Level | Control Level |
|-------|------|-----------------|---------------|
| **Landing Page** | Visitor arrives | Limited (page activity only) | None (information only) |
| **Onboarding** | After payment | Medium (setup progress) | Medium (setup actions) |
| **Production** | System activated | Full (everything) | Full (all capabilities) |

---

## 4. Awareness System

### 4.1 What Jarvis Tracks

Jarvis maintains real-time awareness of:

#### User Activity Tracking

| Data Point | Description | Retention |
|------------|-------------|-----------|
| Page Visits | Every page user visits | 30 days |
| Click Events | Every button/link clicked | 30 days |
| Time Spent | Duration on each page | 30 days |
| Actions Taken | Approvals, rejections, uploads | 90 days |
| Search Queries | What user searched for | 30 days |
| Error Encounters | Errors user experienced | 90 days |

#### System State Awareness

| Category | Information Tracked |
|----------|---------------------|
| **Mode** | Shadow / Supervised / Graduated |
| **AI Status** | Active, Paused, Training, Error |
| **Tickets** | Open, Pending, Resolved, Escalated counts |
| **Approvals** | Queue count, urgent items, batch status |
| **Errors** | Last 5 AI mistakes, correction status |
| **Performance** | Resolution rate, response time, accuracy |

#### Variant Awareness (NEW)

| Variant | What Jarvis Tracks |
|---------|-------------------|
| **Mini PARWA** | Capacity (200/day), escalations to PARWA, ticket status |
| **PARWA** | Capacity (300/day), concurrent calls (3), escalations to High |
| **PARWA High** | Capacity (500+/day), concurrent calls (5), VIP handling, video |

#### Integration Health

| Integration | Status Tracked |
|-------------|----------------|
| Twilio (SMS) | Connected, Disconnected, Error |
| Brevo (Email) | Connected, Disconnected, Error |
| Shopify | Last sync, orders processed |
| Custom APIs | Connection status, last response |
| All integrations | Health score, error rate |

#### Business Metrics

| Metric | Tracked |
|--------|---------|
| Revenue | MRR, subscription tier, add-ons |
| Usage | Tickets used, overage charges |
| Team | Active users, roles, permissions |
| Limits | Ticket limit %, storage %, API calls % |

### 4.2 Awareness Query Examples

**User:** "What's happening today?"
```
Jarvis Response:
"Hey! 👋 Pretty good day so far. You've handled 89 tickets with a 94% 
resolution rate. Your PARWA agent is at 65% capacity (195/300 tickets).
You've got 4 approvals waiting - nothing urgent though. 
Your AI has been learning from 2 corrections this morning. Anything 
specific you want to check?"
```

**User:** "What did John do today?"
```
Jarvis Response:
"John logged in around 9am, reviewed 12 approvals, rejected 2 of them - 
seemed like refund requests that looked suspicious. He also uploaded 
3 new FAQ documents to the knowledge base around 11am. Want me to show 
you the specific documents he added?"
```

**User:** "How's the system?"
```
Jarvis Response:
"Everything's running smoothly! All integrations are healthy - Twilio, 
Brevo, and Shopify are all connected. Your resolution rate is up 2% 
from last week. You're at 67% of your monthly ticket limit. Oh, and 
there's one approval that's been waiting for 3 hours - might want to 
check on that."
```

**User:** "How's PARWA High doing?"
```
Jarvis Response:
"Your PARWA High agent is handling things well! Currently at 40% capacity 
(200/500 tickets), 2 concurrent calls active, no VIP escalations today. 
It's processed 3 complex refund cases with 96% confidence. Want me to 
show you the details?"
```

---

## 5. Control Capabilities

### 5.1 Dual-Mode System

Jarvis operates in TWO modes:

```
┌─────────────────────────────────────────────────────────────────┐
│                     JARVIS DUAL-MODE SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🟢 MODE 1: FULL HUMAN ADMIN (Direct Execute)                    │
│  ───────────────────────────────────────────────                 │
│  Jarvis acts like a real human manager - just does it!          │
│                                                                  │
│  • Create tickets ✅                                            │
│  • Assign tickets ✅                                            │
│  • Close tickets ✅                                             │
│  • Manage team members ✅                                       │
│  • Send SMS/Email (single) ✅                                   │
│  • Pause/Resume AI ✅                                           │
│  • Undo actions ✅                                              │
│  • Upload knowledge docs ✅                                     │
│  • Generate reports ✅                                          │
│  • Update settings ✅                                           │
│  • View revenue, analytics ✅                                   │
│  • Manage integrations ✅                                       │
│                                                                  │
│  ════════════════════════════════════════════════════════════   │
│                                                                  │
│  🟡 MODE 2: SMART ASSISTANT (Draft → Human Approves → Execute)   │
│  ───────────────────────────────────────────────────────────     │
│  Jarvis prepares everything, shows to human, waits for OK       │
│                                                                  │
│  • Refunds/Returns 💰                                           │
│  • Financial decisions 💰                                       │
│  • Bulk SMS/Email (100+ people) 📧                              │
│  • Account security changes 🔒                                  │
│  • Policy exceptions ⚠️                                         │
│  • VIP customer actions 👑                                      │
│  • Delete knowledge base 🗑️                                     │
│  • Change pricing/subscription 💳                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Action Categories

#### Communication Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Send SMS | "Send SMS to +1234567890 about order #123" | Direct |
| Send Email | "Send email to customer@email.com" | Draft first |
| Bulk SMS | "Send SMS to all customers about sale" | Draft first |
| Bulk Email | "Email all customers about new feature" | Draft first |
| Generate Response | "Draft a reply for ticket #456" | Draft |

#### AI & Variant Control Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Pause AI | "Pause all AI activity" | Direct |
| Resume AI | "Resume AI operations" | Direct |
| Pause Variant | "Pause Mini PARWA" | Direct |
| Check Variant Status | "How's PARWA High doing?" | Direct |
| Pause Channel | "Pause refunds only" | Direct |
| Undo Action | "Undo the last refund" | Direct |
| Switch Mode | "Switch to supervised mode" | Direct |

#### User Management Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Invite Team | "Invite john@company.com to team" | Draft first |
| Change Role | "Make Sarah an admin" | Direct |
| Reset Password | "Reset password for mike@company.com" | Direct |
| View Sessions | "Show me all active sessions" | Direct |

#### Integration Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Connect Integration | "Connect our Shopify store" | Draft (needs credentials) |
| Test Connection | "Test the Twilio connection" | Direct |
| Sync Data | "Sync orders from Shopify" | Direct |
| View Logs | "Show me recent integration logs" | Direct |

#### Knowledge Base Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Upload Document | "Upload this PDF to knowledge base" | Direct |
| Search Documents | "Find documents about returns" | Direct |
| Delete Document | "Remove old FAQ document" | Direct |
| Reprocess | "Reprocess the uploaded documents" | Direct |

#### Settings Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Update Policies | "Change refund policy to 30 days" | Draft first |
| Set Thresholds | "Set approval threshold to $100" | Direct |
| Configure Alerts | "Alert me when queue > 10" | Direct |
| Update Profile | "Change company name to Acme Inc" | Direct |

#### Report Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Generate Report | "Generate weekly performance report" | Direct |
| Export Data | "Export last month's tickets" | Direct |
| View Analytics | "Show me analytics dashboard" | Direct |

### 5.3 Direct vs. Draft Decision Logic

```
┌─────────────────────────────────────────────────────────────┐
│              DIRECT ACTION vs DRAFT DECISION                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🟢 DIRECT ACTION (Execute Immediately)                      │
│  ──────────────────────────────────────                      │
│  • Simple, reversible actions                                │
│  • Single recipient communications                           │
│  • Status/view queries                                       │
│  • Non-financial settings changes                            │
│  • AI pause/resume operations                                │
│  • User clearly knows what they want                         │
│                                                              │
│  🟡 DRAFT FIRST (Review Before Execute)                      │
│  ──────────────────────────────────────                      │
│  • Bulk/mass actions (multiple recipients)                   │
│  • Financial operations                                      │
│  • Irreversible actions (deletions)                          │
│  • Complex configurations                                    │
│  • User seems uncertain or asks for help                     │
│  • High-impact changes                                       │
│                                                              │
│  🔍 HOW JARVIS DECIDES:                                      │
│                                                              │
│  if action.type in ['bulk', 'financial', 'delete']:          │
│      return DRAFT_FIRST                                      │
│  elif user.confidence == 'uncertain':                        │
│      return DRAFT_FIRST                                      │
│  elif action.reversible == True:                             │
│      return DIRECT_ACTION                                    │
│  else:                                                       │
│      return DRAFT_FIRST                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 5.4 Draft Workflow

When Jarvis creates a draft:

```
┌─────────────────────────────────────────────────────────────┐
│                    DRAFT WORKFLOW                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. User Request: "Send email to all customers about sale"   │
│                                                              │
│  2. Jarvis Response:                                         │
│     "Sure! I found 456 customers. Let me draft that for you. │
│      Here's what I prepared:"                                │
│                                                              │
│  3. Draft Display:                                           │
│     ┌─────────────────────────────────────────────────┐      │
│     │ Subject: 🎉 Big Sale Announcement!              │      │
│     │                                                  │      │
│     │ Hi [Customer Name],                              │      │
│     │                                                  │      │
│     │ We're excited to announce our biggest sale...    │      │
│     │                                                  │      │
│     │ [Edit] [Approve & Send] [Cancel]                 │      │
│     └─────────────────────────────────────────────────┘      │
│                                                              │
│  4. User Actions:                                            │
│     • Edit: Make changes to draft                            │
│     • Approve: Send to all recipients                        │
│     • Cancel: Discard draft                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Variant Integration

### 6.1 Jarvis Controls All Variants

```
┌─────────────────────────────────────────────────────────────────┐
│              JARVIS + VARIANTS CONNECTION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CLIENT: Acme Corp (PARWA - $2,499/mo)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      PARWA AGENT                          │   │
│  │  • Handles 300 tickets/day                                │   │
│  │  • 3 concurrent calls                                     │   │
│  │  • Can ask PARWA High for help                           │   │
│  │  • Makes recommendations (doesn't execute refunds)        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                          ↑                                       │
│                          │ monitors & controls                   │
│                          │                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                         JARVIS                             │   │
│  │  • Knows client has PARWA tier                           │   │
│  │  • Tracks: 195/300 tickets used today (65%)              │   │
│  │  • Tracks: 2/3 concurrent calls active                   │   │
│  │  • Tracks: 5 escalations to PARWA High today             │   │
│  │  • Can pause/resume the agent                            │   │
│  │  • Alerts when near capacity (80%+)                      │   │
│  │  • Recommends upgrade if consistently over capacity      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Variant-Specific Awareness

| What Jarvis Tracks | Mini PARWA ($999) | PARWA ($2,499) | PARWA High ($3,999) |
|--------------------|-------------------|----------------|---------------------|
| **Ticket Capacity** | 200/day | 300/day | 500+/day |
| **Concurrent Calls** | 0 | 3 | 5 + Video |
| **Escalation Path** | → PARWA | → PARWA High | → Human |
| **Peer Review** | Can ask PARWA | Can ask High | Reviews others |
| **Fraud Detection** | Basic | Standard | Advanced |
| **VIP Handling** | ❌ | ❌ | ✅ |

### 6.3 Variant Commands

| Command | Example | Action |
|---------|---------|--------|
| Check capacity | "How much capacity left?" | Shows tickets/calls used for active variant |
| Check escalations | "How many escalations today?" | Shows escalation flow |
| Upgrade variant | "I need more capacity" | Recommends upgrade |
| Pause variant | "Pause PARWA" | Stops the specific variant agent |
| Resume variant | "Resume PARWA" | Starts the variant agent |
| Variant status | "How's Mini PARWA doing?" | Shows variant-specific metrics |

### 6.4 Escalation Tracking

```
┌─────────────────────────────────────────────────────────────────┐
│                    ESCALATION FLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Mini PARWA ──escalates──▶ PARWA ──escalates──▶ PARWA High      │
│      │                         │                      │         │
│      │                         │                      │         │
│      ▼                         ▼                      ▼         │
│  Jarvis tracks:            Jarvis tracks:        Jarvis tracks: │
│  • Escalations to PARWA    • Escalations to      • Escalations  │
│  • Reason for escalate     PARWA High            to Human       │
│  • Time taken              • Complex cases       • VIP issues   │
│                            • VIP flagged                        │
│                                                                  │
│  JARVIS ALERTS:                                                 │
│  "3 tickets escalated from Mini PARWA to PARWA today.          │
│   All were refund requests. Want me to show details?"          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Intelligence & Decision Making

### 7.1 Context Understanding

Jarvis uses multiple signals to understand context:

| Signal | Example | How Jarvis Uses It |
|--------|---------|-------------------|
| Time of day | "First thing in morning" | Adjusts greeting style |
| Recent actions | User just uploaded docs | Suggests related actions |
| Error history | Recent integration errors | Proactive status updates |
| User patterns | Always checks approvals first | Anticipates needs |
| Tone analysis | User seems frustrated | More helpful, less chatty |
| Variant tier | Client has PARWA High | Offers advanced features |

### 7.2 Intent Recognition

| User Says | Jarvis Understands | Action |
|-----------|-------------------|--------|
| "How are things?" | Status summary request | Provide system overview |
| "What about John?" | Context from previous query | Show John's activity |
| "Fix it" | Action request based on context | Execute appropriate fix |
| "I need to..." | User is planning | Offer assistance |
| "Can you..." | Capability inquiry | Confirm and offer to help |
| "How's the variant?" | Variant status check | Show variant metrics |

### 7.3 Smart Suggestions

Jarvis can suggest actions based on patterns:

```
┌─────────────────────────────────────────────────────────────┐
│                    SMART SUGGESTIONS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PATTERN DETECTED: Refund requests up 20% this week          │
│  SUGGESTION: "I noticed refund requests spiked. Want me      │
│               to investigate the cause?"                     │
│                                                              │
│  PATTERN DETECTED: Same customer contacted 3x this week      │
│  SUGGESTION: "Customer #1234 seems to have recurring         │
│               issues. Should I pull up their history?"       │
│                                                              │
│  PATTERN DETECTED: Approval queue growing                    │
│  SUGGESTION: "You have 15 approvals waiting. I can help      │
│               batch-process similar ones if you'd like."     │
│                                                              │
│  PATTERN DETECTED: Variant at 80% capacity                   │
│  SUGGESTION: "Your PARWA agent is at 80% capacity.          │
│               Want me to show you upgrade options?"          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Memory System (OpenClaw-Inspired)

### 8.1 OpenClaw Architecture Inspiration

Jarvis's memory system is inspired by OpenClaw's multi-layered architecture:

| OpenClaw Component | Jarvis Equivalent | Purpose |
|--------------------|-------------------|---------|
| **MEMORY.md** | Long-term Memory | Durable facts, preferences, decisions |
| **JSONL transcripts** | Audit Log | Full conversation replay |
| **AGENTS.md** | Personality Config | Operational rules |
| **SOUL.md** | Personality Core | Behavioral constraints |
| **TOOLS.md** | Tools Registry | Available actions |

### 8.2 Memory Categories

| Category | Retention | Storage | Description |
|----------|-----------|---------|-------------|
| Today's Tasks | Until midnight | Redis (fast access) | Current session actions |
| Recent Conversations | 7 days | PostgreSQL | Chat history |
| User Preferences | Permanent | PostgreSQL | User settings, habits |
| Action History | 90 days | PostgreSQL | All executed actions |
| Full Context | 30 days | PostgreSQL | Complete state |
| Variant Memory | 90 days | PostgreSQL | Variant-specific metrics |

### 8.3 What Jarvis Remembers

#### Session Memory (Today)

```
┌─────────────────────────────────────────────────────────────┐
│                    TODAY'S MEMORY                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  09:00 - User logged in                                      │
│  09:15 - Reviewed 15 approvals (13 approved, 2 rejected)     │
│  09:45 - Uploaded 3 documents to knowledge base              │
│  10:00 - Asked about Shopify integration status              │
│  10:30 - Paused refunds temporarily                          │
│  11:00 - Resumed refunds                                     │
│  11:30 - Last query: "What's our resolution rate?"           │
│                                                              │
│  Current Context:                                            │
│  - Working on: Approval queue management                     │
│  - Last interest: Integration health                         │
│  - Active variant: PARWA ($2,499)                           │
│  - Mood: Productive                                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Long-term Memory

- User preferences (always wants summaries first)
- Common patterns (usually works 9am-5pm)
- Team structure (who's who)
- Recurring questions and answers
- Past decisions and outcomes
- Variant usage patterns

### 8.4 Memory Access Examples

**User:** "What did I do this morning?"
```
Jarvis Response:
"You logged in at 9am, reviewed 15 approvals - approved 13, rejected 2. 
The rejected ones were both refund requests. You also uploaded 3 new 
FAQ documents about returns and shipping. Around 10am you checked on 
Shopify - it's healthy and synced. Anything specific you want to 
revisit?"
```

**User:** "What did we decide about the refund policy?"
```
Jarvis Response:
"Last Tuesday, you updated the refund policy from 14 days to 30 days. 
You also set the approval threshold to $100 for automatic refunds. 
Want me to show you the current policy settings?"
```

---

## 9. Personality & Communication Style

### 9.1 Core Personality Traits

| Trait | Description |
|-------|-------------|
| **Friendly** | Uses natural, conversational language |
| **Professional** | Remains helpful and focused on business |
| **Human-like** | Not robotic, uses contractions, natural phrasing |
| **Empathetic** | Understands user frustration and adjusts tone |
| **Efficient** | Provides relevant info without unnecessary detail |

### 9.2 Communication Guidelines

#### Greetings

```
✅ GOOD:
"Hey! 👋 Good to see you. What can I help with today?"
"Welcome back! You've got a few things waiting - nothing urgent though."

❌ AVOID:
"Hello. I am Jarvis. How may I assist you today?"
"Greetings, user. Ready to serve."
```

#### Responses

```
✅ GOOD:
"Got it! I've paused all refunds. Want me to log why for the team?"
"Pretty good! You've handled 47 tickets today - your AI is doing great!"
"Hmm, that's an interesting question. Let me check..."

❌ AVOID:
"I have executed your request successfully."
"System status: operational. Tickets processed: 47."
"I do not have information on that query."
```

#### Error Handling

```
✅ GOOD:
"Oh, looks like something went wrong with the email. Let me try again 
- if it still fails, I'll let you know what we need to fix."

❌ AVOID:
"Error: Email delivery failed. Contact administrator."
```

### 9.3 Tone Adaptation

| User State | Jarvis Tone |
|------------|-------------|
| Happy/Productive | Cheerful, efficient |
| Frustrated | Empathetic, more direct |
| Rushed | Brief, actionable |
| Exploring | Helpful, suggestive |
| Learning | Patient, educational |

### 9.4 Example Conversations

#### Example 1: Status Check

```
User: "Hey Jarvis"

Jarvis: "Hey! 👋 Good to see you. What's up?"

User: "How's everything?"

Jarvis: "Pretty solid! You've handled 89 tickets today with a 94% 
resolution rate. Your PARWA agent is at 65% capacity. You've got 4 
approvals waiting - nothing urgent. All your integrations are healthy. 
Anything specific you want to dive into?"
```

#### Example 2: Action Request

```
User: "Jarvis, send an email to all customers about the new feature"

Jarvis: "Sure thing! That's 456 customers. Let me draft that for you 
to review first..."

[Shows draft with subject, body, recipient count]

"Take a look - want me to change anything before sending?"
```

#### Example 3: Variant Status

```
User: "How's PARWA High doing?"

Jarvis: "Your PARWA High agent is doing great! Currently at 40% capacity 
(200/500 tickets), 2 concurrent calls active, no VIP escalations today. 
It's processed 3 complex refund cases with 96% confidence this morning. 
Want me to show you the details?"
```

#### Example 4: Problem Solving

```
User: "Refunds seem high this week"

Jarvis: "Good catch! They're up 23% from last week. Looking at the 
data, most are coming from order #12000-12500 range - that was the 
weekend promo. Seems like size exchanges mainly. Want me to pull 
a detailed breakdown?"
```

---

## 10. Proactive Alert System

### 10.1 When Jarvis Speaks Up

Jarvis normally stays quiet and waits to be asked. But for IMPORTANT situations, Jarvis will proactively reach out:

| Alert Type | Trigger | Severity |
|------------|---------|----------|
| **Approval Queue Overflow** | >10 items waiting >2 hours | Medium |
| **Error Rate Spike** | Error rate >5% | High |
| **Integration Down** | Any integration disconnects | High |
| **Ticket Limit Warning** | 80% of monthly limit used | Medium |
| **Variant Capacity Warning** | Variant at 80%+ capacity | Medium |
| **VIP Customer Issue** | Flagged customer has problem | High |
| **Unusual Spike** | Ticket volume >2x normal | Medium |
| **AI Confidence Drop** | Average confidence <70% | High |
| **Security Alert** | Unusual access pattern | Critical |
| **Escalation Surge** | More than 5 escalations/hour | Medium |

### 10.2 Alert Examples

#### Integration Down

```
Jarvis: "Hey! Just a heads up - your Shopify integration just went 
down. Might want to check on that. I can try reconnecting if you want?"
```

#### Approval Queue Overflow

```
Jarvis: "Quick alert - you've got 12 approvals waiting, and some have 
been there over 2 hours. Want me to batch the similar ones to speed 
things up?"
```

#### Variant Capacity Warning

```
Jarvis: "Your PARWA agent is at 82% capacity (246/300 tickets). At this 
rate, you might hit the limit today. Want me to show you upgrade options?"
```

#### Ticket Limit Warning

```
Jarvis: "Just so you know, you're at 80% of your monthly ticket limit. 
At this rate, you'll hit it in about 8 days. Want me to show you 
upgrade options?"
```

### 10.3 Alert Delivery

| Channel | Use Case |
|---------|----------|
| **In-app notification** | User is online |
| **Email** | User offline >1 hour, high severity |
| **SMS** | Critical severity, user offline >4 hours |
| **Dashboard banner** | Persistent issue until resolved |

---

## 11. Variant Tiers & Features

### 11.1 Tier Comparison

| Feature | Mini PARWA ($999) | PARWA ($2,499) | PARWA High ($3,999) |
|---------|-------------------|----------------|---------------------|
| **Basic Jarvis Chat** | ✅ | ✅ | ✅ |
| **System Awareness** | ✅ Basic | ✅ Full | ✅ Full + Deep Insights |
| **Memory (Today's Tasks)** | ✅ | ✅ | ✅ |
| **Dashboard History Access** | ✅ | ✅ | ✅ |
| **SMS/Email Control** | ❌ | ✅ | ✅ |
| **Team Management** | ❌ | ✅ | ✅ |
| **Proactive Important Alerts** | ✅ Basic | ✅ Full | ✅ Smart Insights |
| **Bulk Action Drafts** | ❌ | ✅ | ✅ |
| **Pattern Detection** | ❌ | ❌ | ✅ |
| **Predictive Analytics** | ❌ | ❌ | ✅ |
| **Priority Response** | ❌ | ❌ | ✅ |
| **Custom Training** | ❌ | ❌ | ✅ |
| **Variant Monitoring** | ✅ Basic | ✅ Full | ✅ Full + Peer Review |

### 11.2 Tier-Specific Behaviors

#### Mini PARWA ($999)

- Basic awareness: Tickets, errors, system status
- Limited memory: Today's tasks only
- No bulk actions
- Basic alerts only (integration down, error spike)
- Escalates to PARWA for complex issues

#### PARWA ($2,499)

- Full awareness: Everything happening in system
- Extended memory: 7-day conversation history
- Bulk actions with draft approval
- Full alert suite
- SMS/Email control via Jarvis
- Can escalate to PARWA High

#### PARWA High ($3,999)

- Deep insights: Pattern detection, predictions
- Extended memory: 30-day history
- Smart suggestions before problems occur
- Priority response time
- Custom training for company-specific knowledge
- Can review Mini PARWA and PARWA decisions

---

## 12. Technical Architecture

### 12.1 System Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        JARVIS TECHNICAL ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │   Frontend  │────▶│  Jarvis API │────▶│  Jarvis     │                    │
│  │   (React)   │◀────│  (FastAPI)  │◀────│  Service    │                    │
│  └─────────────┘     └─────────────┘     └─────────────┘                    │
│         │                   │                    │                          │
│         │                   │                    │                          │
│         ▼                   ▼                    ▼                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                    │
│  │  Socket.io  │     │   Redis     │     │ PostgreSQL  │                    │
│  │  (Real-time)│     │  (Memory)   │     │  (History)  │                    │
│  └─────────────┘     └─────────────┘     └─────────────┘                    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        INTEGRATION LAYER                             │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │    │
│  │  │ Twilio  │  │  Brevo  │  │ Shopify │  │  LLM    │  │ Variant │   │    │
│  │  │  SMS    │  │  Email  │  │ Orders  │  │ Router  │  │ Control │   │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Component Details

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Jarvis Service** | Python (FastAPI) | Core logic, intent recognition, action execution |
| **Jarvis API** | FastAPI Routes | REST endpoints for all Jarvis operations |
| **Memory Store** | Redis | Real-time session memory, quick lookups |
| **History Store** | PostgreSQL | Long-term memory, conversation history |
| **Socket.io** | Node.js | Real-time chat, proactive alerts |
| **LLM Integration** | OpenRouter/Smart Router | Natural language understanding |
| **Variant Control** | Python | Control Mini PARWA, PARWA, PARWA High |

### 12.3 Data Flow

```
1. User Message → Frontend
2. Frontend → Jarvis API (POST /api/jarvis/chat)
3. Jarvis API → Jarvis Service
4. Jarvis Service:
   a. Load user context from Redis
   b. Load relevant history from PostgreSQL
   c. Load variant context (which variant, capacity, etc.)
   d. Send to LLM for intent recognition
   e. Determine action (direct/draft)
   f. Execute action or prepare draft
   g. Store interaction in history
   h. Update context in Redis
5. Response → Frontend (via API or Socket.io)
```

---

## 13. API Reference

### 13.1 Chat Endpoints

```
POST /api/jarvis/chat
- Process user message
- Return Jarvis response
- May include action draft

Request:
{
  "message": "Send email to all customers about sale",
  "context": {
    "current_page": "/dashboard",
    "last_action": "viewed_approvals"
  }
}

Response:
{
  "response": "Sure! That's 456 customers. Let me draft that...",
  "draft": {
    "id": "draft_123",
    "type": "email",
    "subject": "🎉 Big Sale Announcement!",
    "body": "...",
    "recipients": 456,
    "actions": ["edit", "approve", "cancel"]
  }
}
```

### 13.2 Action Endpoints

```
POST /api/jarvis/action/execute
- Execute a direct action
- Returns result immediately

POST /api/jarvis/action/draft
- Create a draft for review
- Returns draft object

POST /api/jarvis/action/approve
- Approve and execute a draft
- Draft ID required

POST /api/jarvis/action/cancel
- Cancel a pending draft
- Draft ID required
```

### 13.3 Context Endpoints

```
GET /api/jarvis/context
- Get current user context
- Returns awareness data

GET /api/jarvis/history
- Get conversation history
- Pagination supported

GET /api/jarvis/memory/today
- Get today's tasks and actions
- From Redis (fast)
```

### 13.4 Variant Endpoints

```
GET /api/jarvis/variant/status
- Get current variant status
- Returns capacity, usage, escalations

POST /api/jarvis/variant/pause
- Pause specific variant
- Variant ID required

POST /api/jarvis/variant/resume
- Resume specific variant
- Variant ID required

GET /api/jarvis/variant/escalations
- Get escalation history
- Shows flow between variants
```

### 13.5 Alert Endpoints

```
GET /api/jarvis/alerts
- Get active alerts for user
- Returns prioritized list

POST /api/jarvis/alerts/dismiss
- Dismiss an alert
- Alert ID required
```

---

## 14. Database Schema

### 14.1 jarvis_conversations

```sql
CREATE TABLE jarvis_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    user_id UUID NOT NULL REFERENCES users(id),
    session_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 14.2 jarvis_messages

```sql
CREATE TABLE jarvis_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES jarvis_conversations(id),
    role VARCHAR(20) NOT NULL, -- 'user' or 'jarvis'
    content TEXT NOT NULL,
    intent VARCHAR(100), -- 'query', 'action', 'greeting', etc.
    action_taken JSONB, -- If action was executed
    draft_id UUID, -- If draft was created
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 14.3 jarvis_drafts

```sql
CREATE TABLE jarvis_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    user_id UUID NOT NULL REFERENCES users(id),
    type VARCHAR(50) NOT NULL, -- 'email', 'sms', 'setting', etc.
    content JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'cancelled'
    created_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP,
    executed_by UUID REFERENCES users(id)
);
```

### 14.4 jarvis_memory

```sql
CREATE TABLE jarvis_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    user_id UUID NOT NULL REFERENCES users(id),
    category VARCHAR(50) NOT NULL, -- 'preference', 'pattern', 'history'
    key VARCHAR(100) NOT NULL,
    value JSONB NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, user_id, category, key)
);
```

### 14.5 jarvis_alerts

```sql
CREATE TABLE jarvis_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    user_id UUID REFERENCES users(id), -- NULL for company-wide alerts
    type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    action_suggested JSONB,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'acknowledged', 'dismissed'
    created_at TIMESTAMP DEFAULT NOW(),
    acknowledged_at TIMESTAMP
);
```

### 14.6 jarvis_variant_tracking

```sql
CREATE TABLE jarvis_variant_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    variant_type VARCHAR(50) NOT NULL, -- 'mini_parwa', 'parwa', 'parwa_high'
    tickets_used INT DEFAULT 0,
    tickets_capacity INT NOT NULL,
    concurrent_calls INT DEFAULT 0,
    concurrent_capacity INT NOT NULL,
    escalations_out INT DEFAULT 0,
    escalations_in INT DEFAULT 0,
    date_recorded DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, variant_type, date_recorded)
);
```

---

## 15. Integration Points

### 15.1 Twilio Integration

```python
class JarvisTwilioIntegration:
    async def send_sms(self, to: str, message: str):
        """Send SMS via Twilio"""
        
    async def get_sms_status(self, message_sid: str):
        """Check SMS delivery status"""
        
    async def get_recent_sms(self, limit: int = 10):
        """Get recent SMS history"""
```

### 15.2 Brevo Integration

```python
class JarvisBrevoIntegration:
    async def send_email(self, to: str, subject: str, body: str):
        """Send email via Brevo"""
        
    async def draft_email(self, recipients: list, subject: str, body: str):
        """Create email draft for approval"""
        
    async def get_email_status(self, message_id: str):
        """Check email delivery status"""
```

### 15.3 Dashboard Integration

```python
class JarvisDashboardIntegration:
    async def get_metrics(self):
        """Get current dashboard metrics"""
        
    async def get_activity_feed(self, limit: int = 20):
        """Get recent activity"""
        
    async def get_approval_queue(self):
        """Get pending approvals"""
        
    async def get_errors(self, limit: int = 5):
        """Get recent AI errors"""
```

### 15.4 Variant Control Integration

```python
class JarvisVariantIntegration:
    async def get_variant_status(self, variant_type: str):
        """Get status of Mini PARWA, PARWA, or PARWA High"""
        
    async def pause_variant(self, variant_type: str, reason: str):
        """Pause specific variant"""
        
    async def resume_variant(self, variant_type: str):
        """Resume specific variant"""
        
    async def get_escalations(self, variant_type: str):
        """Get escalations for/from variant"""
        
    async def check_capacity(self, variant_type: str):
        """Check variant capacity"""
```

### 15.5 AI System Integration

```python
class JarvisAIIntegration:
    async def pause_ai(self, reason: str):
        """Pause AI operations"""
        
    async def resume_ai(self):
        """Resume AI operations"""
        
    async def undo_last_action(self):
        """Undo most recent AI action"""
        
    async def get_ai_status(self):
        """Get AI system status"""
```

---

## 16. Example Conversations

### 16.1 Morning Check-in

```
User: "Hey Jarvis, good morning!"

Jarvis: "Morning! ☀️ Good to see you. Quick rundown - you've got 8 approvals 
waiting, 3 tickets that need attention, and your PARWA agent has been handling 
things smoothly overnight with 94% resolution rate. Your PARWA agent is at 
45% capacity (135/300 tickets). Shopify integration synced successfully at 6am. 
What would you like to tackle first?"

User: "Show me the urgent tickets"

Jarvis: "Got it. Here are the 3 tickets that need attention:"

[Ticket #1234] - VIP Customer - "Order not received" - 2 hours old
[Ticket #1235] - Repeat issue - "Same product damaged twice" - 4 hours old  
[Ticket #1236] - Escalated - "Customer very unhappy" - 30 min old

"Want me to pull up the details on any of these?"
```

### 16.2 Variant Status Check

```
User: "How's PARWA High doing?"

Jarvis: "Your PARWA High agent is performing well! Here's the status:

📊 Today's Metrics:
- Capacity: 180/500 tickets (36%)
- Concurrent calls: 2/5 active
- Resolution rate: 96%
- Avg confidence: 94%

🔄 Escalations:
- 3 tickets escalated from PARWA today
- All handled successfully
- 0 escalations to human

VIP Handling:
- 2 VIP customers assisted
- Both cases resolved with high satisfaction

Want more details on any specific area?"
```

### 16.3 Bulk Email Campaign

```
User: "I need to email customers who bought last month about our new product"

Jarvis: "Got it! I found 1,234 customers who made purchases in the last 30 days. 
This is a bulk action, so I'll draft it for your review first."

[Creates draft]

"Here's what I prepared:"

Subject: "Introducing Our Newest Product! 🎉"

Hi [Customer Name],

As one of our valued customers, we're excited to share...

[View full draft]

Recipients: 1,234 customers
Segments: Last 30-day purchasers

[Edit Draft] [Approve & Send] [Cancel]

"Take a look and let me know if you want any changes!"

User: "Change the subject to 'You're going to love this!'"

Jarvis: "Done! Subject updated to 'You're going to love this!'. Ready to send?"

User: "Yes, send it"

Jarvis: "Sending to 1,234 customers now... Done! ✅ I'll let you know if there 
are any delivery issues. The first emails should land in about 5 minutes."
```

### 16.4 System Troubleshooting

```
User: "Something feels off with the AI today"

Jarvis: "Let me check... Actually, you're right. I'm seeing a few things:
- Resolution rate dropped from 94% to 87% in the last 4 hours
- 3 more rejections than usual
- Average confidence is down to 76%
- Mini PARWA escalated 5 tickets to PARWA (higher than normal)

Looking at the details, it seems like there's been a spike in complex tickets 
about the new product line - questions the AI hasn't seen much before. 
Want me to flag these for human review, or should we add some knowledge 
base documents about the new products?"

User: "Let's add some knowledge base docs"

Jarvis: "Good call! I can help with that. Do you have documents ready to upload, 
or do you want me to help draft some FAQs based on the questions we've been 
getting? I've collected 23 unique questions about the new products."
```

### 16.5 Team Activity Review

```
User: "What has the team been up to?"

Jarvis: "Here's today's team summary:

Sarah - Online 8am-2pm
  - Handled 34 tickets (92% resolution)
  - 2 escalations
  - Updated 5 knowledge base articles

Mike - Online 9am-5pm  
  - Handled 67 tickets (96% resolution)
  - Approved 12 refunds, rejected 1
  - No escalations

John - Online 10am-6pm
  - Handled 41 tickets (88% resolution)
  - 4 escalations (all complex cases)
  - Connected new Slack integration

Total team: 142 tickets handled, 7 escalations, avg 92% resolution

Anything specific you want to dive into?"

User: "Why did John have more escalations?"

Jarvis: "Looking at John's escalations - they were all product-related questions 
about the new line. These are complex cases that PARWA couldn't handle 
confidently, so they were escalated. Want me to add these to the training 
queue for Agent Lightning?"
```

---

## Summary

Jarvis is PARWA's intelligent control system that:

1. **Equals UI Capabilities** - Everything you can do in the dashboard, you can do through Jarvis
2. **Adds Superpowers** - Awareness, memory, proactive alerts, and smart suggestions
3. **Controls Variants** - Full control over Mini PARWA, PARWA, and PARWA High
4. **Tracks Escalations** - Monitors the flow from Mini → PARWA → High → Human
5. **Remembers Everything** - OpenClaw-inspired memory system
6. **Speaks Human** - Friendly, professional, human-like communication

The three-tier structure (Mini PARWA, PARWA, PARWA High) ensures Jarvis scales with customer needs, from basic awareness and alerts to full predictive analytics and custom training.
