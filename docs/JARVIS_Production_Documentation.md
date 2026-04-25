# JARVIS PRODUCTION DOCUMENTATION
## PARWA AI Assistant - Complete Design Specification

**Version:** 1.0  
**Date:** April 2025  
**Status:** Production Ready

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Jarvis Lifecycle](#2-jarvis-lifecycle)
3. [Awareness System](#3-awareness-system)
4. [Control Capabilities](#4-control-capabilities)
5. [Intelligence & Decision Making](#5-intelligence--decision-making)
6. [Memory System](#6-memory-system)
7. [Personality & Communication Style](#7-personality--communication-style)
8. [Proactive Alert System](#8-proactive-alert-system)
9. [Variant Tiers & Features](#9-variant-tiers--features)
10. [Technical Architecture](#10-technical-architecture)
11. [API Reference](#11-api-reference)
12. [Database Schema](#12-database-schema)
13. [Integration Points](#13-integration-points)
14. [Example Conversations](#14-example-conversations)

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

---

## 2. Jarvis Lifecycle

### 2.1 Jarvis Across User Journey

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

### 2.2 Stage Details

| Stage | When | Awareness Level | Control Level |
|-------|------|-----------------|---------------|
| **Landing Page** | Visitor arrives | Limited (page activity only) | None (information only) |
| **Onboarding** | After payment | Medium (setup progress) | Medium (setup actions) |
| **Production** | System activated | Full (everything) | Full (all capabilities) |

---

## 3. Awareness System

### 3.1 What Jarvis Tracks

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

### 3.2 Awareness Query Examples

**User:** "What's happening today?"
```
Jarvis Response:
"Hey! 👋 Pretty good day so far. You've handled 89 tickets with a 94% 
resolution rate. You've got 4 approvals waiting - nothing urgent though. 
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

---

## 4. Control Capabilities

### 4.1 Action Categories

#### Communication Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Send SMS | "Send SMS to +1234567890 about order #123" | Direct |
| Send Email | "Send email to customer@email.com" | Draft first |
| Bulk SMS | "Send SMS to all customers about sale" | Draft first |
| Bulk Email | "Email all customers about new feature" | Draft first |
| Generate Response | "Draft a reply for ticket #456" | Draft |

#### AI Control Actions

| Action | Command Example | Direct/Draft |
|--------|-----------------|--------------|
| Pause AI | "Pause all AI activity" | Direct |
| Resume AI | "Resume AI operations" | Direct |
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

### 4.2 Direct vs. Draft Decision Logic

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

### 4.3 Draft Workflow

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

## 5. Intelligence & Decision Making

### 5.1 Context Understanding

Jarvis uses multiple signals to understand context:

| Signal | Example | How Jarvis Uses It |
|--------|---------|-------------------|
| Time of day | "First thing in morning" | Adjusts greeting style |
| Recent actions | User just uploaded docs | Suggests related actions |
| Error history | Recent integration errors | Proactive status updates |
| User patterns | Always checks approvals first | Anticipates needs |
| Tone analysis | User seems frustrated | More helpful, less chatty |

### 5.2 Intent Recognition

| User Says | Jarvis Understands | Action |
|-----------|-------------------|--------|
| "How are things?" | Status summary request | Provide system overview |
| "What about John?" | Context from previous query | Show John's activity |
| "Fix it" | Action request based on context | Execute appropriate fix |
| "I need to..." | User is planning | Offer assistance |
| "Can you..." | Capability inquiry | Confirm and offer to help |

### 5.3 Smart Suggestions

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
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Memory System

### 6.1 Memory Categories

| Category | Retention | Storage |
|----------|-----------|---------|
| Today's Tasks | Until midnight | Redis (fast access) |
| Recent Conversations | 7 days | PostgreSQL |
| User Preferences | Permanent | PostgreSQL |
| Action History | 90 days | PostgreSQL |
| Full Context | 30 days | PostgreSQL |

### 6.2 What Jarvis Remembers

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

### 6.3 Memory Access Examples

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

## 7. Personality & Communication Style

### 7.1 Core Personality Traits

| Trait | Description |
|-------|-------------|
| **Friendly** | Uses natural, conversational language |
| **Professional** | Remains helpful and focused on business |
| **Human-like** | Not robotic, uses contractions, natural phrasing |
| **Empathetic** | Understands user frustration and adjusts tone |
| **Efficient** | Provides relevant info without unnecessary detail |

### 7.2 Communication Guidelines

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

### 7.3 Tone Adaptation

| User State | Jarvis Tone |
|------------|-------------|
| Happy/Productive | Cheerful, efficient |
| Frustrated | Empathetic, more direct |
| Rushed | Brief, actionable |
| Exploring | Helpful, suggestive |
| Learning | Patient, educational |

### 7.4 Example Conversations

#### Example 1: Status Check

```
User: "Hey Jarvis"

Jarvis: "Hey! 👋 Good to see you. What's up?"

User: "How's everything?"

Jarvis: "Pretty solid! You've handled 89 tickets today with a 94% 
resolution rate. You've got 4 approvals waiting - nothing urgent. 
All your integrations are healthy. Anything specific you want to 
dive into?"
```

#### Example 2: Action Request

```
User: "Jarvis, send an email to all customers about the new feature"

Jarvis: "Sure thing! That's 456 customers. Let me draft that for you 
to review first..."

[Shows draft with subject, body, recipient count]

"Take a look - want me to change anything before sending?"
```

#### Example 3: Information Query

```
User: "What did Sarah do today?"

Jarvis: "Sarah's been busy! She logged in at 8:30am, processed 23 
tickets - all resolved without escalation. She also approved 5 
refund requests and rejected 1 that looked suspicious. Around 
11am she updated the knowledge base with 2 new shipping FAQs. 
Want more details on any of that?"
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

## 8. Proactive Alert System

### 8.1 When Jarvis Speaks Up

Jarvis normally stays quiet and waits to be asked. But for IMPORTANT situations, Jarvis will proactively reach out:

| Alert Type | Trigger | Severity |
|------------|---------|----------|
| **Approval Queue Overflow** | >10 items waiting >2 hours | Medium |
| **Error Rate Spike** | Error rate >5% | High |
| **Integration Down** | Any integration disconnects | High |
| **Ticket Limit Warning** | 80% of monthly limit used | Medium |
| **VIP Customer Issue** | Flagged customer has problem | High |
| **Unusual Spike** | Ticket volume >2x normal | Medium |
| **AI Confidence Drop** | Average confidence <70% | High |
| **Security Alert** | Unusual access pattern | Critical |

### 8.2 Alert Examples

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

#### Ticket Limit Warning

```
Jarvis: "Just so you know, you're at 80% of your monthly ticket limit. 
At this rate, you'll hit it in about 8 days. Want me to show you 
upgrade options?"
```

### 8.3 Alert Delivery

| Channel | Use Case |
|---------|----------|
| **In-app notification** | User is online |
| **Email** | User offline >1 hour, high severity |
| **SMS** | Critical severity, user offline >4 hours |
| **Dashboard banner** | Persistent issue until resolved |

---

## 9. Variant Tiers & Features

### 9.1 Tier Comparison

| Feature | PARWA Starter ($999) | PARWA Growth ($2,499) | PARWA High ($3,999) |
|---------|---------------------|----------------------|---------------------|
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

### 9.2 Tier-Specific Behaviors

#### PARWA Starter ($999)

- Basic awareness: Tickets, errors, system status
- Limited memory: Today's tasks only
- No bulk actions
- Basic alerts only (integration down, error spike)

#### PARWA Growth ($2,499)

- Full awareness: Everything happening in system
- Extended memory: 7-day conversation history
- Bulk actions with draft approval
- Full alert suite
- SMS/Email control via Jarvis

#### PARWA High ($3,999)

- Deep insights: Pattern detection, predictions
- Extended memory: 30-day history
- Smart suggestions before problems occur
- Priority response time
- Custom training for company-specific knowledge

---

## 10. Technical Architecture

### 10.1 System Components

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
│  │  │ Twilio  │  │  Brevo  │  │ Shopify │  │  LLM    │  │ Custom  │   │    │
│  │  │  SMS    │  │  Email  │  │ Orders  │  │ Router  │  │   API   │   │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 Component Details

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Jarvis Service** | Python (FastAPI) | Core logic, intent recognition, action execution |
| **Jarvis API** | FastAPI Routes | REST endpoints for all Jarvis operations |
| **Memory Store** | Redis | Real-time session memory, quick lookups |
| **History Store** | PostgreSQL | Long-term memory, conversation history |
| **Socket.io** | Node.js | Real-time chat, proactive alerts |
| **LLM Integration** | OpenRouter/Smart Router | Natural language understanding |

### 10.3 Data Flow

```
1. User Message → Frontend
2. Frontend → Jarvis API (POST /api/jarvis/chat)
3. Jarvis API → Jarvis Service
4. Jarvis Service:
   a. Load user context from Redis
   b. Load relevant history from PostgreSQL
   c. Send to LLM for intent recognition
   d. Determine action (direct/draft)
   e. Execute action or prepare draft
   f. Store interaction in history
   g. Update context in Redis
5. Response → Frontend (via API or Socket.io)
```

---

## 11. API Reference

### 11.1 Chat Endpoints

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

### 11.2 Action Endpoints

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

### 11.3 Context Endpoints

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

### 11.4 Alert Endpoints

```
GET /api/jarvis/alerts
- Get active alerts for user
- Returns prioritized list

POST /api/jarvis/alerts/dismiss
- Dismiss an alert
- Alert ID required
```

---

## 12. Database Schema

### 12.1 jarvis_conversations

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

### 12.2 jarvis_messages

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

### 12.3 jarvis_drafts

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

### 12.4 jarvis_memory

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

### 12.5 jarvis_alerts

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

---

## 13. Integration Points

### 13.1 Twilio Integration

```python
class JarvisTwilioIntegration:
    async def send_sms(self, to: str, message: str):
        """Send SMS via Twilio"""
        
    async def get_sms_status(self, message_sid: str):
        """Check SMS delivery status"""
        
    async def get_recent_sms(self, limit: int = 10):
        """Get recent SMS history"""
```

### 13.2 Brevo Integration

```python
class JarvisBrevoIntegration:
    async def send_email(self, to: str, subject: str, body: str):
        """Send email via Brevo"""
        
    async def draft_email(self, recipients: list, subject: str, body: str):
        """Create email draft for approval"""
        
    async def get_email_status(self, message_id: str):
        """Check email delivery status"""
```

### 13.3 Dashboard Integration

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

### 13.4 AI System Integration

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

## 14. Example Conversations

### 14.1 Morning Check-in

```
User: "Hey Jarvis, good morning!"

Jarvis: "Morning! ☀️ Good to see you. Quick rundown - you've got 8 approvals 
waiting, 3 tickets that need attention, and your AI has been handling 
things smoothly overnight with 94% resolution rate. The Shopify integration 
synced successfully at 6am. What would you like to tackle first?"

User: "Show me the urgent tickets"

Jarvis: "Got it. Here are the 3 tickets that need attention:"

[Ticket #1234] - VIP Customer - "Order not received" - 2 hours old
[Ticket #1235] - Repeat issue - "Same product damaged twice" - 4 hours old  
[Ticket #1236] - Escalated - "Customer very unhappy" - 30 min old

"Want me to pull up the details on any of these?"
```

### 14.2 Bulk Email Campaign

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

### 14.3 System Troubleshooting

```
User: "Something feels off with the AI today"

Jarvis: "Let me check... Actually, you're right. I'm seeing a few things:
- Resolution rate dropped from 94% to 87% in the last 4 hours
- 3 more rejections than usual
- Average confidence is down to 76%

Looking at the details, it seems like there's been a spike in complex tickets 
about the new product line - questions the AI hasn't seen much before. 
Want me to flag these for human review, or should we add some knowledge 
base documents about the new products?"

User: "Let's add some knowledge base docs"

Jarvis: "Good call! I can help with that. Do you have documents ready to upload, 
or do you want me to help draft some FAQs based on the questions we've been 
getting? I've collected 23 unique questions about the new products."
```

### 14.4 Team Activity Review

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
about features we don't have documentation for yet. Actually, that matches 
what we saw with the AI struggles. Should I create a task to write docs 
for those features?"
```

### 14.5 End of Day Summary

```
User: "Jarvis, wrap up my day"

Jarvis: "Here's your day in review! 📊

TICKETS:
- Handled: 127 total
- Resolution rate: 93%
- Average response: 2.3 minutes

APPROVALS:
- Reviewed: 23
- Approved: 20
- Rejected: 3 (all suspicious refunds)

TEAM:
- 3 team members active
- 0 issues reported

SYSTEM:
- All integrations healthy
- No errors or outages
- AI learning from 2 corrections

MEMORY SAVED:
- You paused refunds at 10:30am, resumed at 11am
- You updated the return policy FAQ
- You approved the new team member invite for Jen

Tomorrow's priorities:
- 4 approvals waiting (one is 3 hours old)
- 2 VIP customer follow-ups
- Consider: The refund spike might need attention

Anything else before you head out?"
```

---

## Appendix A: Jarvis Command Reference

### Quick Commands (Buttons)

| Command | Action | Tier Required |
|---------|--------|---------------|
| Pause AI | Immediately pause all AI operations | All |
| Resume AI | Resume AI operations | All |
| Show Errors | Display last 5 AI errors | All |
| Undo Last | Undo most recent AI action | All |
| View Queue | Show approval queue | All |
| Check Status | Full system status | All |

### Natural Language Commands

| Say This | Jarvis Understands |
|----------|-------------------|
| "What's happening?" | General status summary |
| "Show me tickets" | Display ticket list |
| "What about [person]?" | Contextual person query |
| "Send [message] to [recipient]" | Communication action |
| "Pause [operation]" | Pause specific operation |
| "How's [integration]?" | Check integration status |
| "What did I do [timeframe]?" | Memory/history query |
| "Help me with [task]" | Offer assistance |

---

## Appendix B: Configuration Options

### Company-Level Settings

```json
{
  "jarvis_settings": {
    "proactive_alerts": true,
    "alert_channels": ["in_app", "email"],
    "memory_retention_days": 30,
    "draft_approval_required": ["bulk_email", "bulk_sms", "financial", "delete"],
    "personality_tone": "friendly_professional",
    "response_style": "concise",
    "smart_suggestions": true
  }
}
```

### User-Level Settings

```json
{
  "jarvis_user_settings": {
    "greeting_style": "casual",
    "summary_first": true,
    "alert_level": "important_only",
    "memory_access": "full",
    "preferred_channels": ["in_app"]
  }
}
```

---

**Document End**

*This documentation is a living document and will be updated as Jarvis evolves.*
