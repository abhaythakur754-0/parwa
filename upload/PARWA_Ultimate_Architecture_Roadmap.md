# PARWA — Ultimate Architecture Roadmap

> **Target**: 90%+ resolution accuracy across all ticket types  
> **Philosophy**: Quality-first technique mapping, non-LLM fast track, smart variant routing, full multi-tenant isolation  
> **Systems**: PARWA 8-Node Pipeline + Jarvis 3-Node Pipeline + Notification Center + AI Wiki + Integration Layer + Key-Based Access + Onboarding  
> **Total Nodes**: 11 (8 PARWA + 3 Jarvis)  
> **Status**: Architecture finalized, implementation phased

---

## Table of Contents

1. [Combined System Architecture](#1-combined-system-architecture)
2. [Key-Based Access System](#2-key-based-access-system)
3. [Onboarding Flow & Dashboard Wiring](#3-onboarding-flow--dashboard-wiring)
4. [PARWA 8-Node Pipeline — Complete Detail](#4-parwa-8-node-pipeline--complete-detail)
5. [Jarvis 3-Node Pipeline — Complete Detail](#5-jarvis-3-node-pipeline--complete-detail)
6. [Notification Center](#6-notification-center)
7. [AI Wiki — 3-Section Per-Client Design](#7-ai-wiki--3-section-per-client-design)
8. [Integration Layer — Unified Connector Bus (UCB)](#8-integration-layer--unified-connector-bus-ucb)
9. [Multi-Tenant Data Isolation](#9-multi-tenant-data-isolation)
10. [Policy Change Detection](#10-policy-change-detection)
11. [25 Techniques — LLM vs Non-LLM Classification](#11-25-techniques--llm-vs-non-llm-classification)
12. [Technique-to-Node Mapping (PARWA + Jarvis)](#12-technique-to-node-mapping-parwa--jarvis)
13. [Dual Pipeline Flow](#13-dual-pipeline-flow)
14. [Variant System & Quota Management](#14-variant-system--quota-management)
15. [Quality Loop & Super Node](#15-quality-loop--super-node)
16. [MAKER Hallucination Prevention](#16-maker-hallucination-prevention)
17. [Implementation Phases](#17-implementation-phases)
18. [Production Readiness Checklist](#18-production-readiness-checklist)
19. [Dashboard Production Readiness](#19-dashboard-production-readiness)

---

## 1. Combined System Architecture

### The Complete System Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PARWA PLATFORM (Multi-Tenant)                          │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                     ACCESS LAYER — KEY-BASED AUTH                         │  │
│  │                                                                           │  │
│  │   Admin (buyer) creates account ──▶ Gets unique ACCESS KEY               │  │
│  │   Team members use same KEY ──▶ All see same dashboard                   │  │
│  │   Multiple users with same KEY ──▶ Work in parallel                      │  │
│  │   Admin can change/retrieve KEY ──▶ Only admin has this power            │  │
│  │   KEY generated during onboarding ──▶ Before first ticket victory        │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                     TENANT ISOLATION LAYER                                │  │
│  │                                                                           │  │
│  │   Client A (key: pk_live_xxx)     Client B (key: pk_live_yyy)            │  │
│  │  ┌──────────────────┐            ┌──────────────────┐                    │  │
│  │  │ AI Wiki A│B│C    │            │ AI Wiki A│B│C    │                    │  │
│  │  │ Knowledge Base   │            │ Knowledge Base   │                    │  │
│  │  │ Ticket History   │            │ Ticket History   │                    │  │
│  │  │ Quota Tracking   │            │ Quota Tracking   │                    │  │
│  │  │ Integration Creds│            │ Integration Creds│                    │  │
│  │  │ Notification Log │            │ Notification Log │                    │  │
│  │  │ Onboarding State │            │ Onboarding State │                    │  │
│  │  └──────────────────┘            └──────────────────┘                    │  │
│  │                                                                           │  │
│  │  🔒 Same Variant Tier ≠ Same Data. Each client = fully isolated tenant   │  │
│  │  🔒 Row-Level Security at DB. Namespace isolation in Vector Store        │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │              INTEGRATION LAYER — UCB (Per Client)                        │  │
│  │                                                                           │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │  │
│  │  │  EMAIL   │ │   SMS    │ │  CALLS   │ │  CHAT    │ │   CRM   │      │  │
│  │  │SendGrid  │ │ Twilio   │ │ Twilio   │ │WhatsApp  │ │HubSpot  │      │  │
│  │  │Mailgun   │ │MSG91    │ │ Vonage   │ │Intercom  │ │Salesforce│      │  │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │  │
│  │       └─────────────┴─────────────┴─────────────┴────────────┘            │  │
│  │                           │                                               │  │
│  │              UNIFIED CONNECTOR BUS (UCB)                                  │  │
│  │              Normalize → Route → Execute → Verify                         │  │
│  │              Each client connects THEIR tools → Only THEIR data flows     │  │
│  └──────────────────────────────────┼────────────────────────────────────────┘  │
│                                     │                                           │
│            ┌────────────────────────┼────────────────────────┐                   │
│            │                        │                        │                   │
│            ▼                        ▼                        ▼                   │
│      INGEST to Node 1        ACTION from Node 5       SYNC to Node 3           │
│      (Tickets arrive)        (Send replies back)      (Fetch CRM data)          │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │              PARWA 8-NODE PIPELINE (Variant Ticket Solver)               │  │
│  │                                                                           │  │
│  │  Node 1 ──▶ Node 2 ──▶ Node 3 ──▶ SPLIT                               │  │
│  │  Ingest+     Smart      Knowledge    │                                  │  │
│  │  Classify    Route      Fetch+AIWiki │                                  │  │
│  │                                   ┌──┴──┐                               │  │
│  │                                   │     │                               │  │
│  │                              Simple   Complex                           │  │
│  │                                  │       │                              │  │
│  │                             Node 7     Node 4→5→6                      │  │
│  │                             (Non-LLM)  (LLM + Quality Loop)            │  │
│  │                                  │       │                              │  │
│  │                                  │    Node 8 (Super Node)              │  │
│  │                                  │       │                              │  │
│  │                                  ▼       ▼                              │  │
│  │                            ✅ Resolved / ❌ Stuck                       │  │
│  └──────────────────────────────┬───────────┬───────────────────────────────┘  │
│                                 │           │                                   │
│                        Resolved │           │ Stuck/Unsolved                    │
│                        Update   │           │ Send to                            │
│                        Wiki A   │           │ Jarvis SENSE                       │
│                                 ▼           ▼                                   │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │              JARVIS 3-NODE PIPELINE (Awareness + Notify + Chat)          │  │
│  │                                                                           │  │
│  │  Node 1 (SENSE) ──▶ Node 2 (EVALUATE) ──▶ Node 3 (NOTIFY)              │  │
│  │                                                                           │  │
│  │  • Monitor PARWA     • CoT + CLARA        • Notification Center          │  │
│  │  • Track Quotas      • Step-Back          • Unique Keys (PARWA-NFY-XXX)  │  │
│  │  • Watch Stuck       • Reflexion          • Batch Similar Alerts         │  │
│  │  • Policy Changes    • Priority Score      • Chat Answer to Admin        │  │
│  │  • Tool Health       • Decide Action       • Feed Quota to PARWA Node 2  │  │
│  │                                               • Update Wiki Section B   │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │              AI WIKI (Per Client — FULLY ISOLATED)                       │  │
│  │                                                                           │  │
│  │  Section A: Ticket Patterns   ← PARWA writes, Jarvis reads               │  │
│  │  Section B: Admin Behavior    ← Jarvis writes, PARWA reads               │  │
│  │  Section C: Company Knowledge ← Admin writes manually, both read          │  │
│  │                                                                           │  │
│  │  🔒 Cross-read within SAME client only. Zero leakage between clients.    │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │              NOTIFICATION CENTER (Per Client)                            │  │
│  │                                                                           │  │
│  │  • Unsolved/Stuck problems ONLY — not all tickets                        │  │
│  │  • Unique key per notification: PARWA-NFY-XXX                           │  │
│  │  • Batched similar issues together                                      │  │
│  │  • Admin copies key → asks Jarvis for details                           │  │
│  │  • Shown in dashboard, wired to Jarvis chat                            │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### System Connection Points

| From | To | Connection Type | What Flows |
|------|----|----------------|------------|
| UCB | PARWA Node 1 | Ingest | Incoming tickets (email, SMS, chat, calls) normalized |
| PARWA Node 5 | UCB | Action | Reply/execute actions through correct channel |
| PARWA Node 3 | UCB | Sync | Fetch CRM/contact data for context |
| PARWA (resolved) | AI Wiki Section A | Write | Ticket patterns from resolved tickets |
| PARWA (stuck) | Jarvis Node 1 (SENSE) | Alert | Stuck/unsolved ticket signals |
| Jarvis Node 3 (NOTIFY) | PARWA Node 2 | Feed | Quota decisions, variant info |
| Jarvis Node 3 (NOTIFY) | Notification Center | Push | Unsolved/stuck alerts with unique keys |
| Jarvis | AI Wiki Section B | Write | Admin behavior patterns |
| Admin | AI Wiki Section C | Write | Company knowledge, policies |
| AI Wiki Section C | Jarvis Node 1 (SENSE) | Read | Policy change detection |
| Onboarding | Dashboard | Wire | Integration status, tools connected, config |
| Onboarding | UCB | Register | Tool credentials, API keys per client |
| Onboarding | Key System | Generate | Access key for the client |

---

## 2. Key-Based Access System

### Why Key-Based, Not Login-Based

Traditional username/password login creates friction for team-based usage. PARWA uses a **key-based access model** where:

- The **buyer (admin)** creates the account and receives a unique access key
- **Team members** use the SAME key to access the dashboard — no separate accounts needed
- **Multiple people** can work in parallel using the same key simultaneously
- The **admin** is the ONLY one who can change or retrieve the key
- This is similar to how API keys work — simple, shareable, revocable

### Key Format

```
pk_live_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

pk_live_     = prefix (production live key)
XXXX...      = 32-character cryptographically random string
```

### Key Lifecycle

```
1. Admin signs up ──▶ Creates account with email + master password
                         │
2. System generates ──▶  pk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
                         │
3. Key shown ONCE ──▶   Displayed during onboarding (before first victory)
   during onboarding     Admin must save it. Can share with team.
                         │
4. Team uses key ──▶    Anyone with the key can:
   for dashboard          • View dashboard
                          • Chat with Jarvis
                          • See notifications
                          • Monitor variants
                          BUT CANNOT:
                          • Change the key
                          • Access billing
                          • Modify integrations
                         │
5. Admin manages ──▶    Only admin (authenticated via master password) can:
   the key                • Regenerate key (invalidates old one)
                          • Retrieve key if lost
                          • Change master password
                          • Modify integrations
                          • Access billing
                         │
6. Key revoked ──▶      If compromised:
                          • Admin regenerates → old key instantly invalid
                          • New key issued → team must update
                          • All active sessions with old key terminated
```

### Parallel Access with Same Key

```
┌─────────────────────────────────────────────────────────────────┐
│              PARALLEL KEY USAGE                                 │
│                                                                 │
│  Team Member 1 (key: pk_live_xxx)  ──▶  Dashboard Session A    │
│  Team Member 2 (key: pk_live_xxx)  ──▶  Dashboard Session B    │
│  Team Member 3 (key: pk_live_xxx)  ──▶  Dashboard Session C    │
│                                                                 │
│  All sessions:                                                   │
│  ✅ See same data (same tenant_id)                              │
│  ✅ Chat with Jarvis independently                               │
│  ✅ View same notifications                                     │
│  ✅ Monitor same variants                                       │
│  ❌ Cannot kick other sessions                                  │
│  ❌ Cannot change key or billing                                │
│                                                                 │
│  Concurrency handled by:                                        │
│  • WebSocket per session (real-time updates)                    │
│  • Optimistic locking on writes (no conflicts)                  │
│  • Each chat session has unique session_id                      │
│  • Jarvis tracks which admin is in which session                │
└─────────────────────────────────────────────────────────────────┘
```

### Key Security Measures

| Measure | How It Works |
|---------|-------------|
| Cryptographic randomness | 32-char key using `secrets.token_urlsafe(24)` — not guessable |
| Hashed storage | Key stored as SHA-256 hash in DB — never in plaintext |
| Rate limiting | 5 failed key attempts → 15-minute lockout per IP |
| Session binding | Each key use creates a signed JWT with tenant_id + session_id |
| Key rotation | Admin can regenerate anytime — old key instantly invalid |
| Audit logging | Every key use logged with IP, timestamp, action |
| No key in URLs | Key sent in Authorization header, never in query params |

### Database Schema — Keys

```sql
CREATE TABLE access_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    key_hash        VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hash
    key_prefix      VARCHAR(12) NOT NULL,          -- "pk_live_xxx" for display
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    
    INDEX idx_access_keys_key_hash (key_hash),
    INDEX idx_access_keys_tenant_id (tenant_id)
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL DEFAULT 'admin',  -- 'admin' or 'team'
    is_account_owner BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, email)
);

CREATE TABLE key_usage_audit (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    key_prefix      VARCHAR(12) NOT NULL,
    action          VARCHAR(50) NOT NULL,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### Key Delivery — Before First Victory

The key is generated and displayed during onboarding as the LAST step before the variant processes its first ticket (the "first victory"). The flow is:

```
Onboarding Step 1: Company Info
Onboarding Step 2: Variant Selection (Mini / PARWA / High)
Onboarding Step 3: Integration Setup (Email, SMS, CRM, etc.)
Onboarding Step 4: Knowledge Base Upload (docs, policies)
Onboarding Step 5: Policy Configuration (refund rules, etc.)
    │
    ▼
┌──────────────────────────────────────────────────┐
│  🎉 YOUR ACCESS KEY IS READY!                    │
│                                                   │
│  pk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6      │
│                                                   │
│  ⚠️ Save this key now. It won't be shown again.  │
│  Share it with your team to access the dashboard. │
│  Only you (admin) can regenerate this key.        │
│                                                   │
│  [Copy Key]  [Download as .txt]  [Continue]       │
└──────────────────────────────────────────────────┘
    │
    ▼
Onboarding Step 6: First Ticket Test (first victory)
    → System processes a test ticket to verify everything works
    → Dashboard becomes fully active
```

---

## 3. Onboarding Flow & Dashboard Wiring

### Complete Onboarding Pipeline

The onboarding flow is a 6-step wizard that sets up everything a client needs. Every choice made during onboarding is **wired directly into the dashboard** — what you configure here shows there in real-time.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ONBOARDING FLOW (6 Steps)                     │
│                                                                 │
│  Step 1: ACCOUNT SETUP                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Company name                                         │    │
│  │  • Admin email + master password                        │    │
│  │  • Industry category (helps initial knowledge)          │    │
│  │  • Company size (helps quota recommendations)           │    │
│  │                                                         │    │
│  │  → Creates tenant_id in database                        │    │
│  │  → Creates admin user record                            │    │
│  │  → Initializes empty AI Wiki (Sections A, B, C)        │    │
│  │  → Dashboard: Shows "Setup in Progress"                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  Step 2: VARIANT SELECTION                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Choose tier: Mini / PARWA / High                     │    │
│  │  • See what each tier can do (interactive comparison)   │    │
│  │  • Monthly/Annual billing toggle                        │    │
│  │  • Quota preview (how many tickets/month)               │    │
│  │                                                         │    │
│  │  → Creates variant_registry entry for tenant            │    │
│  │  → Sets initial quota based on tier                     │    │
│  │  → Dashboard: Shows variant badge + quota meter         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  Step 3: INTEGRATION SETUP (Connect Your Tools)                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │    │
│  │  │ Email   │ │  SMS    │ │  Calls  │ │  Chat   │      │    │
│  │  │ ● Gmail│ │ ● Twilio│ │ ● Twilio│ │ ● WA   │      │    │
│  │  │ ○ Other│ │ ○ MSG91 │ │ ○ Vonage│ │ ○ Inter.│      │    │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘      │    │
│  │       │           │           │           │            │    │
│  │  ┌────┴────┐ ┌────┴────┐ ┌────┴────┐                  │    │
│  │  │  CRM   │ │Helpdesk │ │  Docs   │                  │    │
│  │  │●HubSpot│ │●ZenDesk │ │●Notion  │                  │    │
│  │  │○SF DC  │ │○Fresh.  │ │○GDrive  │                  │    │
│  │  └────────┘ └─────────┘ └─────────┘                  │    │
│  │                                                         │    │
│  │  Each integration:                                      │    │
│  │  • OAuth flow or API key input                         │    │
│  │  • Test connection button (verify it works)            │    │
│  │  • Choose which channels to monitor                    │    │
│  │                                                         │    │
│  │  → Stores encrypted credentials per tenant             │    │
│  │  → Registers integration in UCB                        │    │
│  │  → Dashboard: Shows connected tools with status ✅/❌  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  Step 4: KNOWLEDGE BASE UPLOAD                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Upload company docs (PDF, DOCX, URLs)               │    │
│  │  • Enter refund/return policies                         │    │
│  │  • Add product/service information                      │    │
│  │  • FAQ import                                           │    │
│  │  • Auto-parse and chunk documents                       │    │
│  │  • Show preview of what was parsed                      │    │
│  │                                                         │    │
│  │  → Documents stored in tenant-scoped vector store       │    │
│  │  → Policies stored in AI Wiki Section C                 │    │
│  │  → Dashboard: Shows knowledge base stats (docs, chunks)│    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  Step 5: POLICY CONFIGURATION                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Set refund rules (auto-approve under $X?)            │    │
│  │  • Set credit rules                                     │    │
│  │  • Define escalation triggers                           │    │
│  │  • Set response tone (formal/casual/friendly)           │    │
│  │  • Business hours (when to respond vs queue)            │    │
│  │  • Restricted actions (what needs human approval)       │    │
│  │                                                         │    │
│  │  → Stored in AI Wiki Section C (Company Knowledge)      │    │
│  │  → PARWA Node 3 reads these on every ticket             │    │
│  │  → Dashboard: Shows policy config summary               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                     │
│                           ▼                                     │
│  Step 6: KEY GENERATION + FIRST VICTORY                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │  🎉 YOUR ACCESS KEY IS READY!                    │    │    │
│  │  │  pk_live_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6      │    │    │
│  │  │  ⚠️ Save now. Won't show again.                  │    │    │
│  │  │  [Copy] [Download] [Continue →]                  │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  │                                                         │    │
│  │  After key is saved:                                    │    │
│  │  • System sends a TEST TICKET through the pipeline      │    │
│  │  • "Hi, what's your refund policy?" → goes through      │    │
│  │    Node 1 → Node 2 → Node 3 → Node 7 → ✅ Resolved    │    │
│  │  • First Victory = proof that everything works          │    │
│  │  • Dashboard activates fully                            │    │
│  │                                                         │    │
│  │  → Access key stored (hashed) in database               │    │
│  │  → First ticket processed → AI Wiki Section A created   │    │
│  │  → Dashboard: FULLY ACTIVE                              │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Onboarding ↔ Dashboard Wiring

Every step of onboarding is **directly wired to the dashboard**. What you configure there appears here:

| Onboarding Step | Dashboard Section | What Shows |
|----------------|-------------------|------------|
| Step 1: Account Setup | Top bar | Company name, admin avatar |
| Step 2: Variant Selection | Left panel | Variant badge (Mini/PARWA/High), quota meter |
| Step 3: Integration Setup | Bottom panel | Connected tools list with status ✅/❌, last sync time, tool health |
| Step 4: Knowledge Base | Bottom panel → AI Wiki | Document count, chunk count, last updated |
| Step 5: Policy Config | AI Wiki → Section C | Policy rules summary, response tone setting |
| Step 6: Key Generation | Settings → Access | Active key (masked), session count, last activity |

### Dashboard Live Updates During Onboarding

```
┌─────────────────────────────────────────────────────────────────┐
│  DASHBOARD (builds up as onboarding progresses)                  │
│                                                                 │
│  BEFORE ONBOARDING:     [Setup in Progress — 0/6 complete]      │
│                                                                 │
│  AFTER STEP 1:         [1/6 ●○○○○○] Account created             │
│  AFTER STEP 2:         [2/6 ●●○○○○] Variant: High ●            │
│  AFTER STEP 3:         [3/6 ●●●○○○] Email ✅ HubSpot ✅         │
│  AFTER STEP 4:         [4/6 ●●●●○○] 12 docs loaded             │
│  AFTER STEP 5:         [5/6 ●●●●●○] Policies configured        │
│  AFTER STEP 6:         [6/6 ●●●●●●] 🎉 FULLY ACTIVE            │
│                                                                 │
│  Each step progressively enables dashboard sections:             │
│  • After Step 2: Variant panel + quota meter lights up           │
│  • After Step 3: Integration status panel lights up              │
│  • After Step 4: AI Wiki panel lights up                         │
│  • After Step 5: Policy compliance badge shows in ticket view    │
│  • After Step 6: Everything active, first ticket test runs       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. PARWA 8-Node Pipeline — Complete Detail

### Evolution: 62 Nodes → 8 Nodes

| Before | After |
|--------|-------|
| 23 main nodes + 39 subgraph nodes = 62 total | 8 focused nodes |
| 1 technique per node | Multiple techniques per node, some used across nodes |
| Every ticket goes through all nodes | Smart routing: simple tickets skip LLM entirely |
| No variant awareness | Node 2 handles variant matching + quota |
| No quality loop | Max 2 loops → Super Node → Human escalation |
| Subgraphs for sub-tasks | Layers inside nodes for sub-tasks |

### The 8 Nodes at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                 NODE 1: INGEST + CLASSIFY                │
│                 (WHAT is this ticket?)                   │
│                 SmartRouter + UoT + DynamicContext       │
│                 + MetaLearner                            │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 NODE 2: SMART ROUTE                      │
│                 (WHO handles it + WHERE does it go?)     │
│                 Variant Registry + Quota Tracker         │
│                 + Capability Match + Route Decision      │
│                 (0 LLM calls, pure logic)                │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
      SIMPLE / MEDIUM                COMPLEX / HARD
           │                              │
           ▼                              ▼
┌─────────────────────┐    ┌──────────────────────────────┐
│  NODE 3: KNOWLEDGE  │    │  NODE 3: KNOWLEDGE           │
│  FETCH + AI WIKI    │    │  FETCH + AI WIKI             │
│  (shared by both)   │    │  (shared by both)            │
└──────────┬──────────┘    └──────────────┬───────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐    ┌──────────────────────────────┐
│  NODE 7: SIMPLE/    │    │  NODE 4: REASONING ENGINE    │
│  MEDIUM RESOLVER    │    │  (4-layer: Decompose→Solve   │
│  (3 non-LLM layers) │    │   →Validate→Combine)         │
└──────────┬──────────┘    └──────────┬───────────────────┘
           │                          │
           │                          ▼
           │              ┌──────────────────────────────┐
           │              │  NODE 5: ACT + VERIFY        │
           │              │  (Rule-based + ReAct +        │
           │              │   Reverse Validation)        │
           │              └──────────┬───────────────────┘
           │                         │
           │                         ▼
           │              ┌──────────────────────────────┐
           │              │  NODE 6: QUALITY + FORMAT    │
           │              │  (Reflexion + CRP +          │
           │              │   Quality Loop Gate)         │
           │              └──────┬───────────┬───────────┘
           │                     │           │
           │                PASS ✓      FAIL (loop)
           │                     │           │
           │                     │     Back to Node 4
           │                     │     (max 2 loops)
           │                     │           │
           │                     │     FAIL after 2
           │                     │           │
           │                     │           ▼
           │                     │  ┌────────────────────┐
           │                     │  │ NODE 8: SUPER NODE │
           │                     │  │ (Maximum power,    │
           │                     │  │  all heavy LLM     │
           │                     │  │  techniques)       │
           │                     │  └──────┬─────────────┘
           │                     │         │
           ▼                     ▼         ▼
           ┌──────────────────────────────────────────┐
           │          RESPONSE OUTPUT                   │
           │     (or Human Escalation)                  │
           └──────────────────────────────────────────┘
```

**IMPORTANT**: Node 3 (Knowledge Fetch) is SHARED by both paths. Every ticket — simple or complex — must go through the knowledge base. You cannot answer ANY ticket without evidence.

---

### NODE 1: INGEST + CLASSIFY

**Purpose**: Receive the ticket, understand what it is, and extract all classification signals.

**Question it answers**: WHAT is this ticket?

| Technique | LLM? | What It Does Here | Why Here |
|-----------|------|-------------------|----------|
| SmartRouter | ❌ Non-LLM | Classifies ticket type (refund, billing, technical, etc.) and complexity (simple/medium/complex) | Primary classifier — fast, free, pattern-based |
| UoT | ✅ LLM | Measures uncertainty in classification — if SmartRouter is confident but wrong, UoT catches it | Quality gate for classification. Prevents misrouting |
| DynamicContext | ❌ Non-LLM | Pulls customer history, recent tickets, account type, conversation context | Classification needs context — same question from a Pro user vs Free user may need different paths |
| MetaLearner | ❌ Non-LLM | Learns from past routing decisions — "last 50 tickets like this were simple and resolved correctly" | Improves routing accuracy over time without extra LLM calls |

**Output**:
```python
{
    "ticket_id": "tkt_123",
    "ticket_type": "refund_request",
    "complexity": "simple",
    "required_action": "execute_refund",
    "action_details": {"amount": 30, "currency": "USD"},
    "confidence": 0.93,
    "customer_context": {...},
    "routing_suggestion": "simple_medium_path"
}
```

**LLM Cost**: 1 call (UoT only)

---

### NODE 2: SMART ROUTE

**Purpose**: Match the classified ticket to the right variant tier and route it to the correct pipeline path.

**Question it answers**: WHO handles this ticket + WHERE does it go?

| Component | What It Does |
|-----------|-------------|
| Variant Registry | Stores which variants the user has purchased |
| Quota Tracker | Tracks how many tickets remain per variant per billing cycle |
| Capability Matrix | Maps what each variant tier CAN and CANNOT do |
| Route Decision | Applies the lowest eligible tier and routes to the right path |

**Three-Dimensional Routing Logic**:

1. **Capability Check**: Can this tier HANDLE this ticket type?
2. **Quota Check**: Does this tier still have tickets remaining?
3. **Efficiency Check**: Use the LOWEST tier that can handle it (preserve higher quotas for harder tickets)

**Routing Decision Table**:

| Ticket Need | Mini Can? | PARWA Can? | High Can? | Route To |
|-------------|-----------|------------|-----------|----------|
| Simple info only | ✅ | ✅ | ✅ | Node 7 (use Mini quota first) |
| Recommend refund/credit | ✅ | ✅ | ✅ | Node 7 (use Mini quota first) |
| Execute refund ≤ $500 | ❌ | ✅ | ✅ | Node 4 (use PARWA quota first) |
| Execute refund > $500 | ❌ | ❌ | ✅ | Node 4 (use High quota) |
| Execute credit ≤ $200 | ❌ | ✅ | ✅ | Node 4 (use PARWA quota first) |
| Execute credit > $200 | ❌ | ❌ | ✅ | Node 4 (use High quota) |
| Account change (limited) | ❌ | ✅ | ✅ | Node 4 (use PARWA quota first) |
| Account change (full) | ❌ | ❌ | ✅ | Node 4 (use High quota) |
| Any ticket, Mini quota exhausted | ❌ | depends | depends | Use next available tier |

**Additional Input from Jarvis**: Jarvis Node 3 (NOTIFY) feeds real-time quota and variant status information to Node 2, ensuring routing decisions account for the most current state.

**LLM Cost**: 0 calls (pure logic, database reads only)

---

### NODE 3: KNOWLEDGE FETCH + AI WIKI

**Purpose**: Gather ALL relevant knowledge — from docs, AI Wiki, past tickets, compressed context. This is the EVIDENCE node.

**Question it answers**: What do we KNOW about this problem?

**CRITICAL**: Every ticket — simple or complex — goes through this node. You cannot answer any ticket without knowledge.

| Technique | LLM? | What It Does Here | Why Here |
|-----------|------|-------------------|----------|
| CLARA | ✅ LLM | **GATEKEEPER** — decides WHAT knowledge is needed, WHERE to find it, WHETHER we have enough | Bad knowledge = bad reasoning. CLARA is the quality gate for evidence |
| HyDE | ✅ LLM | Generates a hypothetical answer, uses it as a search query to find real docs | Finds docs that match the ANSWER space, not just the question keywords |
| Multi-Query | ✅ LLM | Rewrites the user's question 3 different ways | Same question, different phrasings in docs — maximizes recall |
| Step-Back | ✅ LLM | Steps back to find broader principles | "Why can't I refund?" → general refund policy, not just edge cases |
| ContextualCompression | ❌ Non-LLM | Compresses retrieved docs — removes irrelevant paragraphs | Prevents reasoning overload |
| DynamicContext | ❌ Non-LLM | Pulls conversation history + customer-specific context | Different customers may need different knowledge |

**CLARA as Gatekeeper** (3 questions before knowledge passes through):

```
1. "Is this knowledge RELEVANT to the ticket?" → Filter irrelevant docs
2. "Do we have ENOUGH knowledge to answer?" → If no, search again or flag gap
3. "Is this knowledge CONTRADICTORY?" → If yes, keep both versions for Node 4
```

**AI Wiki 3-Section Access** (per client, isolated):

| Section | What PARWA Does | Access by Tier |
|---------|----------------|----------------|
| Section A: Ticket Patterns | Reads similar patterns, writes new patterns on resolution | Mini: Read, PARWA: Read+Learn, High: Read+Write+Learn |
| Section B: Admin Behavior | Reads admin preferences for tone/style | All tiers: Read |
| Section C: Company Knowledge | Reads policies, refund rules, company info | All tiers: Read |

**Policy Sync Check**: Before knowledge fetch, Node 3 checks if Section C policies are current (version tracking). If a policy was recently updated, it flags the new version for use in this ticket's reasoning.

**CRM Data Fetch via UCB**: Node 3 also reaches out through the Unified Connector Bus to fetch relevant CRM data (customer's subscription status, recent interactions, account tier) from the client's connected tools (HubSpot, Salesforce, etc.). This data is scoped to the current tenant only.

**LLM Cost**: 3-4 calls (CLARA + HyDE + Multi-Query + Step-Back)

---

### NODE 4: REASONING ENGINE

**Purpose**: Think through the problem using all available evidence and techniques. The BRAIN of the pipeline.

**Question it answers**: What is the RIGHT answer?

**4-Layer Architecture**:

#### Layer 1: DECOMPOSE (Break the problem down)

| Technique | LLM? | Role | Why Here |
|-----------|------|------|----------|
| GSD | ❌ Non-LLM | Breaks complex problem into sub-problems | Free decomposition |
| Least-to-Most | ✅ LLM | Orders sub-problems from easiest to hardest | Solving easy ones first gives context |

#### Layer 2: SOLVE (Solve each sub-problem)

| Technique | LLM? | Role | Why Here |
|-----------|------|------|----------|
| CoT | ✅ LLM | Step-by-step reasoning for each sub-problem | Core reasoning |
| MAKER | ❌ Non-LLM | Bridges knowledge gaps between sub-problems | Finds connections |
| ToT | ✅ LLM | Explores multiple solution paths for hard sub-problems | When CoT hits a wall |

**MAKER + Least-to-Most as 3-Layer Stack**:
```
Layer A: Least-to-Most orders sub-problems (easiest → hardest)
Layer B: MAKER bridges knowledge gaps between sub-problems
Layer C: CoT solves each bridged sub-problem step by step
```

#### Layer 3: VALIDATE (Check each solution)

| Technique | LLM? | Role | Why Here |
|-----------|------|------|----------|
| Reverse Thinking | ✅ LLM | Works backward from answer to validate | Forward reasoning can look right but be wrong |
| ZeroShotValidator | ❌ Non-LLM | Flags statistically unusual solutions | Free safety net |
| UoT | ✅ LLM | Measures uncertainty | Quantifies confidence |

**ToT + Reverse Thinking as Forward+Backward Validation**:
```
ToT: Explores multiple paths FORWARD
Reverse Thinking: Validates the best path BACKWARD
Both together = double-checked reasoning
```

#### Layer 4: COMBINE (Merge all solutions into one answer)

| Technique | LLM? | Role | Why Here |
|-----------|------|------|----------|
| ThoT | ❌ Non-LLM | Threads multiple solutions together coherently | No contradictions |
| FederatedReasoning | ❌ Non-LLM | Aggregates solutions like a voting ensemble | Majority rules |
| MetaLearner | ❌ Non-LLM | Adjusts combination weights based on past success | Learns which techniques are most reliable |

**LLM Cost**: 3-4 calls (CoT + Least-to-Most + ToT + Reverse Thinking + UoT)

---

### NODE 5: ACT + VERIFY

**Purpose**: Execute actions (refunds, credits, account changes) and verify they were done correctly.

**Question it answers**: Did we DO the right thing?

| Technique | LLM? | What It Does Here | Why Here |
|-----------|------|-------------------|----------|
| Rule-based actions | ❌ Non-LLM | For simple actions: "refund < $50 → auto-approve" | No LLM needed for deterministic actions |
| ReAct | ✅ LLM | Think-Act-Observe loop for complex actions | Complex actions need observation and adaptation |
| MAKER | ❌ Non-LLM | Bridges action knowledge gaps | Free knowledge bridging during execution |
| GSD | ❌ Non-LLM | Decomposes multi-step actions into individual steps | Step-by-step tracking |
| Reverse Thinking | ✅ LLM | After action: "If I reverse this, do I get back to original?" | Validates by checking reversibility |
| ZeroShotValidator | ❌ Non-LLM | Flags wrong actions — "refund of $10,000 on a $5 order?" | Free anomaly detection |

**Variant-Aware Action Execution**:

| Action | Mini | PARWA | High |
|--------|------|-------|------|
| Refund ≤ $500 | Recommend only | Execute | Execute |
| Refund > $500 | Recommend only | Recommend only | Execute |
| Credit ≤ $200 | Recommend only | Execute | Execute |
| Credit > $200 | Recommend only | Recommend only | Execute |
| Account change (basic) | Recommend only | Execute | Execute |
| Account change (full) | Recommend only | Recommend only | Execute |

**UCB Action Execution**: When Node 5 needs to execute an action (send email reply, process refund through CRM, update account), it goes through the Unified Connector Bus. The UCB uses the current tenant's stored credentials to make the API call through the correct integration (HubSpot, Salesforce, SendGrid, etc.). This ensures actions go through the right channel with the right credentials.

**LLM Cost**: 1-2 calls (ReAct + Reverse Thinking, only for complex actions)

---

### NODE 6: QUALITY + FORMAT

**Purpose**: Final quality gate — is this answer good enough to send to the customer?

**Question it answers**: Is this answer GOOD ENOUGH?

| Technique | LLM? | What It Does Here | Why Here |
|-----------|------|-------------------|----------|
| Reflexion | ✅ LLM | Self-reflection — "Is this answer actually good?" | LLM critiques its own output |
| CRP | ✅ LLM | Chain-of-Revision — rewrites for clarity and accuracy | Improves quality through revision |
| ZeroShotValidator | ❌ Non-LLM | Final statistical check | Free quality signal |
| GSD | ❌ Non-LLM | Checks each part of multi-part answers separately | Per-part quality |
| ThoT | ❌ Non-LLM | Threads the final answer coherently | No contradictions |
| ContextualCompression | ❌ Non-LLM | Compresses the final response — removes filler | Concise, actionable response |
| FederatedReasoning | ❌ Non-LLM | Aggregates quality signals from all validators | Combined quality score |

**Quality Scoring**:
```python
quality_score = weighted_average([
    reflexion_score * 0.30,       # LLM self-critique (most trusted)
    crp_score * 0.25,             # Revision quality
    zero_shot_score * 0.20,       # Statistical validity
    thot_coherence * 0.15,        # Logical coherence
    gsd_part_scores * 0.10        # Per-part quality
])
```

**LLM Cost**: 2 calls (Reflexion + CRP)

---

### NODE 7: SIMPLE/MEDIUM RESOLVER

**Purpose**: Handle simple and medium tickets using ONLY non-LLM techniques. Fast, cheap, still accurate.

**Question it answers**: Can we solve this WITHOUT LLM calls?

**CRITICAL**: This node receives knowledge from Node 3. It does NOT skip knowledge fetch. Every ticket needs evidence.

**3-Layer Architecture** (mirror of Nodes 4+5+6):

#### Layer 1: THINK (mirror of Node 4 — Reasoning)

| Technique | LLM? | Role |
|-----------|------|------|
| GSD | ❌ | Decompose the question into parts |
| MAKER | ❌ | Bridge knowledge gaps from what Node 3 fetched |
| ThoT | ❌ | Thread solutions together coherently |
| FederatedReasoning | ❌ | Combine signals from multiple non-LLM techniques |
| MetaLearner | ❌ | Use past patterns — "tickets like this were answered this way 500 times" |
| ZeroShotValidator | ❌ | Flag anything that looks statistically off |

**Why these work without LLM**: Simple tickets don't need deep reasoning. They need pattern matching and knowledge bridging. MetaLearner is especially powerful here — it has seen thousands of similar simple tickets and knows the right answer pattern.

#### Layer 2: ACT (mirror of Node 5 — Action)

| Technique | LLM? | Role |
|-----------|------|------|
| Rule-based actions | ❌ | Auto-approve simple refunds/credits within variant limits |
| MAKER | ❌ | Bridge action knowledge gaps |
| GSD | ❌ | Break multi-step actions into steps |
| ZeroShotValidator | ❌ | Flag wrong actions — "refund of $10,000?" |

**Variant restrictions still apply**: Even in Node 7, if the user only has Mini, we can only recommend — not execute.

#### Layer 3: CHECK (mirror of Node 6 — Quality)

| Technique | LLM? | Role |
|-----------|------|------|
| ZeroShotValidator | ❌ | Final quality check |
| GSD | ❌ | Check each part of multi-part answers |
| ThoT | ❌ | Ensure answer is coherent |
| ContextualCompression | ❌ | Remove filler |
| TurboCompress | ❌ | Ultra-fast compression for simple tickets |
| FederatedReasoning | ❌ | Aggregate quality signals |

**Safety Net** (critical):

```
IF Layer 3 ZeroShotValidator confidence < 80%:
    → Auto-upgrade to Complex path (Node 4)
    → Ticket enters full LLM pipeline
    → This catches the 5-10% of "simple" tickets that are actually tricky
```

**LLM Cost**: 0 calls

---

### NODE 8: SUPER NODE

**Purpose**: After 2 failed quality loops, throw EVERYTHING at the problem. Last resort before human escalation.

**Question it answers**: Can the MOST POWERFUL approach solve this?

**Activation Conditions**:
- Ticket went through Node 4 → Node 5 → Node 6 → FAIL (loop 1)
- Ticket went through Node 4 → Node 5 → Node 6 → FAIL (loop 2)
- Both attempts failed → Super Node activates

**NOT for simple tickets. NOT for first attempts. Only for genuinely hard cases that failed twice.**

| Technique | LLM? | What It Does Here | Why Here |
|-----------|------|-------------------|----------|
| Self-Consistency | ✅ LLM | 3 independent reasoning attempts, majority vote wins | Catches hallucinations |
| ToT | ✅ LLM | Explores ALL possible solution paths deeply | Maximum exploration |
| Reverse Thinking | ✅ LLM | Forward AND backward reasoning simultaneously | Double validation |
| Reflexion | ✅ LLM | Deep self-reflection on WHY previous attempts failed | Learns from failures |
| CRP | ✅ LLM | Revision with full context of what went wrong | Better answer from failure analysis |
| CoT | ✅ LLM | Step-by-step with maximum detail | Full reasoning chain |
| ALL 11 non-LLM techniques | ❌ | Every amplifier active simultaneously | Maximum signal |

**Super Node Execution Order**:
```
1. Reflexion: "WHY did the previous 2 attempts fail?"
2. Self-Consistency: 3 independent solutions using different approaches
3. ToT: Explore the most promising path deeply
4. Reverse Thinking: Validate the best solution backward
5. CRP: Rewrite the final answer incorporating all insights
6. ZeroShotValidator + FederatedReasoning: Final quality check
```

**Super Node Decision**:
```
IF Super Node quality > 85%:
    → SEND (we solved it!)
ELIF Super Node quality <= 85%:
    → ESCALATE TO HUMAN
    → Include: original ticket + all 3 failed attempts + analysis
    → Notification Center alerts admin with unique key
    → Jarvis SENSE tracks this as stuck problem
```

**LLM Cost**: 5-6 calls (Self-Consistency = 3, plus ToT + Reverse Thinking + Reflexion)

---

## 5. Jarvis 3-Node Pipeline — Complete Detail

### Architecture Overview

Jarvis is the awareness engine, notification system, and admin chatbot. It follows the **OpenClaw pattern**: Observe → Think → Act → Verify. Jarvis does NOT auto-heal or take autonomous actions. It watches, evaluates, notifies, and answers admin questions.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   NODE 1     │────▶│   NODE 2     │────▶│   NODE 3     │
│   SENSE      │     │   EVALUATE   │     │   NOTIFY     │
│              │     │              │     │              │
│  Observe     │     │  Think       │     │  Act + Verify│
└──────────────┘     └──────────────┘     └──────────────┘
```

### Jarvis Techniques: 15 Total (11 Non-LLM + 4 LLM)

**11 Non-LLM Techniques** (used for fast monitoring and pattern detection):

| # | Technique | Role in Jarvis |
|---|-----------|---------------|
| 1 | SmartRouter | Classify admin questions and notification types |
| 2 | GSD | Break complex admin queries into sub-questions |
| 3 | MAKER | Bridge information gaps between monitoring domains |
| 4 | ThoT | Thread multiple awareness signals into coherent story |
| 5 | FederatedReasoning | Aggregate signals from multiple monitoring domains |
| 6 | ZeroShotValidator | Flag unusual patterns in variant health or ticket flow |
| 7 | MetaLearner | Learn admin preferences and common queries over time |
| 8 | DynamicContext | Pull current variant state, quota, integration status |
| 9 | ContextualCompression | Compress long monitoring reports for admin readability |
| 10 | TurboCompress | Ultra-fast summary for chat responses |
| 11 | AdaptiveBudget | Monitor Jarvis's own resource usage |

**4 LLM Techniques** (used for complex admin questions and deep evaluation):

| # | Technique | Role in Jarvis | When Used |
|---|-----------|---------------|-----------|
| 1 | CoT | Step-by-step reasoning for complex admin queries | "Why is refund resolution rate dropping?" |
| 2 | CLARA | Clarify ambiguous admin questions before answering | "How's my variant doing?" → which aspect? |
| 3 | Step-Back | Zoom out to broader context for strategic questions | "Should I upgrade my tier?" → analyze overall usage |
| 4 | Reflexion | Self-critique on notification decisions before sending | "Is this notification worth sending? Could it be noise?" |

---

### NODE 1: SENSE (Observe)

**Purpose**: Monitor everything. Collect signals from PARWA pipeline, variants, integrations, and knowledge base.

**Question it answers**: What is happening RIGHT NOW?

| What It Monitors | Source | Signal Type |
|-----------------|--------|-------------|
| PARWA node states | Pipeline state (all 8 nodes) | Health, throughput, error rate |
| Ticket flow | Node 1, Node 2, Node 7, Node 4 | Volume, complexity split, stuck tickets |
| Quota usage | Variant registry | Remaining quota, burn rate, projected exhaustion |
| Stuck/unsolved problems | Node 7 (safety net), Node 8 (Super Node fail) | Ticket ID, failure reason, escalation |
| Integration health | UCB | Tool connectivity, API errors, sync delays |
| Policy changes | AI Wiki Section C | New policy version, updated rules |
| Admin behavior | AI Wiki Section B | Recent admin commands, common questions |
| Variant performance | Per-tenant metrics | Accuracy, resolution time, LLM cost |

**Output**:
```python
{
    "timestamp": "2026-06-16T10:30:00Z",
    "tenant_id": "tenant_abc123",
    "signals": {
        "stuck_tickets": [
            {"ticket_id": "tkt_456", "reason": "super_node_failed", "key": "PARWA-NFY-001"},
            {"ticket_id": "tkt_789", "reason": "quality_loop_exhausted", "key": "PARWA-NFY-002"}
        ],
        "quota_status": {"mini": 47, "parwa": 234, "high": 1856},
        "integration_health": {"hubspot": "healthy", "sendgrid": "degraded"},
        "policy_version": {"refund_policy": "v2.3", "updated_at": "2026-06-15"},
        "accuracy_trend": "stable_92_percent"
    }
}
```

**LLM Cost**: 0 calls (pure monitoring, data collection only)

---

### NODE 2: EVALUATE (Think)

**Purpose**: Make sense of the signals. Decide what needs attention, what's noise, and what action to recommend.

**Question it answers**: Does this MATTER? What should we DO about it?

| Technique | LLM? | Role | When Active |
|-----------|------|------|-------------|
| CoT | ✅ LLM | Step-by-step reasoning for complex evaluations | Multiple stuck tickets, accuracy drops, quota projections |
| CLARA | ✅ LLM | Clarify ambiguous signals before deciding | Is this a real problem or normal fluctuation? |
| Step-Back | ✅ LLM | Zoom out to broader context | "3 stuck tickets today" → is that normal for this client? |
| Reflexion | ✅ LLM | Self-critique on evaluation before sending | "Is this really worth notifying? Or is it noise?" |
| SmartRouter | ❌ | Classify signal type and priority | Route to correct evaluation path |
| GSD | ❌ | Break complex situations into sub-problems | Multiple issues simultaneously |
| MAKER | ❌ | Bridge information gaps | Connect quota status with accuracy trend |
| FederatedReasoning | ❌ | Aggregate signals from multiple domains | Combine stuck tickets + quota + integration health |
| ZeroShotValidator | ❌ | Flag unusual patterns | "5 stuck tickets in 1 hour = abnormal" |
| MetaLearner | ❌ | Learn from past evaluations | "Admin usually ignores these types of notifications" |
| DynamicContext | ❌ | Pull current state for context | What variant, what quota, what time of day |

**Priority Scoring**:

```python
priority_score = weighted_average([
    impact_score * 0.30,      # How many customers affected?
    urgency_score * 0.25,     # Time-sensitivity
    trend_score * 0.20,       # Getting worse or stable?
    admin_preference * 0.15,  # MetaLearner: does admin care about this?
    frequency_score * 0.10    # Is this a one-off or recurring?
])

# Priority levels:
# CRITICAL (> 0.85): Send immediately, push notification
# HIGH (0.65-0.85): Send in next batch, show prominently
# MEDIUM (0.40-0.65): Batch with similar, show in feed
# LOW (< 0.40): Log only, don't notify
```

**LLM Cost**: 1-2 calls (CoT or CLARA for complex evaluations, Reflexion before sending)

---

### NODE 3: NOTIFY (Act + Verify)

**Purpose**: Deliver the right information to the right place. Push notifications, answer chat questions, update wiki, feed data back to PARWA.

**Question it answers**: HOW do we communicate this?

| Action | Target | Technique |
|--------|--------|-----------|
| Push notification | Notification Center | Unique key + batching |
| Answer admin chat | Jarvis chat interface | CoT + DynamicContext + knowledge retrieval |
| Feed quota info | PARWA Node 2 | DynamicContext + quota state |
| Update AI Wiki Section B | AI Wiki | MetaLearner patterns on admin behavior |
| Alert on stuck tickets | Admin via Notification Center | Priority-based batching with unique keys |

**Notification Delivery Rules**:

```
1. UNSOLVED/STUCK ONLY — never notify on resolved tickets
2. UNIQUE KEY per notification: PARWA-NFY-XXX
   → Admin can copy key and ask Jarvis: "What's PARWA-NFY-001?"
3. BATCH SIMILAR ISSUES:
   → "3 refund tickets stuck in Super Node" (not 3 separate notifications)
   → Batch window: 5 minutes for similar issues
4. PRIORITY-BASED DELIVERY:
   → CRITICAL: Push immediately (WebSocket + email)
   → HIGH: Next batch cycle (1 min)
   → MEDIUM: Digest (5 min)
   → LOW: Daily summary only
```

**Jarvis Chat Answers** (admin asks questions via chat):

```
Admin: "How many refunds did we process today?"
Jarvis: Uses DynamicContext + AI Wiki + quota data
       → "Today: 23 refund tickets resolved. 18 auto-approved (≤$500), 
          5 required complex reasoning. 2 stuck — keys: PARWA-NFY-007, 
          PARWA-NFY-008. Want details?"

Admin: "What's PARWA-NFY-007?"
Jarvis: Looks up notification by unique key
       → "Ticket tkt_456: Customer wants refund of $1,200. High variant 
          attempted but quality score was 78% after 2 loops. Super Node 
          also failed (82%). Needs your manual review. Customer: 
          Pro plan, 2-year member. Suggested action: Approve with 
          manager override."

Admin: "Should I upgrade from PARWA to High tier?"
Jarvis: Uses Step-Back + CoT
       → "Based on your last 30 days: 68% of tickets are simple (handled 
          by Mini/PARWA). 22% are complex (PARWA handles up to $500 
          refunds). The remaining 10% need High capabilities. You've 
          had 8 tickets this month that exceeded PARWA limits and were 
          recommended-only. If those 8 were worth > $500 each in 
          customer satisfaction, upgrading makes sense. Current cost: 
          $2,499/mo. High would be $4,999/mo. That's $2,500 more for 
          8 tickets = ~$313/ticket. Worth it if those are high-value 
          customers."
```

**LLM Cost**: 1-2 calls (for chat answers that need reasoning)

---

## 6. Notification Center

### Design Principles

1. **Unsolved/Stuck ONLY** — Resolved tickets never appear in notifications
2. **Unique Keys** — Every notification has a key like `PARWA-NFY-XXX` that admin can reference in Jarvis chat
3. **Batching** — Similar issues grouped together to reduce noise
4. **No noise** — Low-priority signals logged but not pushed

### Notification Schema

```sql
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    notification_key VARCHAR(20) NOT NULL UNIQUE,  -- PARWA-NFY-XXX
    type            VARCHAR(30) NOT NULL,  -- stuck_ticket, quota_low, integration_down, policy_change, accuracy_drop
    priority        VARCHAR(10) NOT NULL,  -- CRITICAL, HIGH, MEDIUM, LOW
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    related_tickets JSONB,           -- Array of ticket_ids if batched
    batch_key       VARCHAR(50),      -- For grouping similar notifications
    is_read         BOOLEAN DEFAULT FALSE,
    is_resolved     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    
    INDEX idx_notifications_tenant_id (tenant_id),
    INDEX idx_notifications_key (notification_key),
    INDEX idx_notifications_batch_key (batch_key)
);
```

### Notification Flow

```
PARWA Node 7/8 fails ──▶ Jarvis SENSE detects ──▶ Jarvis EVALUATE scores priority
    │
    ▼
┌──────────────────────────────────────────────────┐
│  NOTIFICATION CENTER                             │
│                                                  │
│  🔴 CRITICAL                                     │
│  ┌────────────────────────────────────────────┐  │
│  │ PARWA-NFY-042 | HubSpot API down          │  │
│  │ 3 tickets can't fetch CRM data            │  │
│  │ [Ask Jarvis] [Mark Resolved]              │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  🟡 HIGH                                         │
│  ┌────────────────────────────────────────────┐  │
│  │ PARWA-NFY-043 | 2 tickets stuck in Super  │  │
│  │ Node (batched)                             │  │
│  │ • tkt_301: Refund $800 failed quality     │  │
│  │ • tkt_305: Account change failed verify   │  │
│  │ [Ask Jarvis] [Mark Resolved]              │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  🔵 MEDIUM                                       │
│  ┌────────────────────────────────────────────┐  │
│  │ PARWA-NFY-044 | Mini quota at 12%         │  │
│  │ 47 remaining of 500 this month            │  │
│  │ [Ask Jarvis] [Dismiss]                    │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 7. AI Wiki — 3-Section Per-Client Design

### Architecture

Each client gets their OWN AI Wiki with 3 sections. No data leaks between clients. Cross-read happens ONLY within the same client's wiki.

```
┌──────────────────────────────────────────────────────────┐
│  AI Wiki for Client A (tenant_id: tenant_abc123)         │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  SECTION A: TICKET PATTERNS                        │  │
│  │  • Who writes: PARWA (on ticket resolution)        │  │
│  │  • Who reads: PARWA Node 3, Jarvis SENSE           │  │
│  │  • What's stored:                                  │  │
│  │    - Question → Answer patterns                    │  │
│  │    - Which techniques worked for which ticket type  │  │
│  │    - Common customer issues and solutions           │  │
│  │    - Failure patterns (what didn't work)            │  │
│  │  • Updated: Every time a ticket is resolved        │  │
│  │  • Access: Mini=Read, PARWA=Read+Learn,            │  │
│  │            High=Read+Write+Learn                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  SECTION B: ADMIN BEHAVIOR                         │  │
│  │  • Who writes: Jarvis (on admin interactions)      │  │
│  │  • Who reads: Jarvis EVALUATE, PARWA Node 3        │  │
│  │  • What's stored:                                  │  │
│  │    - Admin's preferred response tone               │  │
│  │    - Common questions admin asks                   │  │
│  │    - Which notifications admin ignores vs. acts on │  │
│  │    - Manual overrides admin makes                  │  │
│  │    - Time-of-day activity patterns                 │  │
│  │  • Updated: Every admin-Jarvis interaction         │  │
│  │  • Access: All tiers read, Jarvis writes           │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  SECTION C: COMPANY KNOWLEDGE                      │  │
│  │  • Who writes: Admin (manually via dashboard)      │  │
│  │  • Who reads: PARWA Node 3, Jarvis SENSE           │  │
│  │  • What's stored:                                  │  │
│  │    - Company policies (refund, return, exchange)    │  │
│  │    - Product/service information                   │  │
│  │    - Pricing tiers and features                    │  │
│  │    - Business hours and escalation rules            │  │
│  │    - Brand voice guidelines                        │  │
│  │    - Restricted actions list                       │  │
│  │  • Updated: Admin edits via dashboard              │  │
│  │  • Version tracking: Each policy has version #     │  │
│  │  • Access: All tiers read, Admin writes            │  │
│  │  • Auto-detect: Jarvis SENSE detects policy changes│  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘

🔒 Client B has a COMPLETELY SEPARATE wiki. Zero cross-read.
🔒 Client C has a COMPLETELY SEPARATE wiki. Zero cross-read.
```

### AI Wiki Database Schema

```sql
CREATE TABLE ai_wiki_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    section         VARCHAR(1) NOT NULL,  -- 'A', 'B', or 'C'
    entry_key       VARCHAR(100) NOT NULL,  -- e.g., "refund_policy", "admin_tone_preference"
    title           TEXT NOT NULL,
    content         JSONB NOT NULL,
    version         INTEGER DEFAULT 1,
    tags            TEXT[],
    created_by      VARCHAR(20) NOT NULL,  -- 'parwa', 'jarvis', 'admin'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, section, entry_key),
    INDEX idx_wiki_tenant_section (tenant_id, section),
    INDEX idx_wiki_tags (tenant_id, tags)
);
```

---

## 8. Integration Layer — Unified Connector Bus (UCB)

### Purpose

Variants need to CONNECT with real channels — Email, SMS, Calls, Chat, CRM, Helpdesk, Docs. Without this, PARWA can't receive tickets or send responses through the right channels. The UCB normalizes all these into a single interface.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              UNIFIED CONNECTOR BUS (UCB)                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  CHANNEL ADAPTERS (Inbound — tickets come IN)           │    │
│  │                                                         │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │    │
│  │  │  Email   │ │   SMS    │ │  Calls   │ │  Chat    │  │    │
│  │  │SendGrid  │ │ Twilio   │ │ Twilio   │ │WhatsApp  │  │    │
│  │  │Mailgun   │ │MSG91    │ │ Vonage   │ │Intercom  │  │    │
│  │  │Gmail API │ │SNS      │ │Aircall   │ │Crisp     │  │    │
│  │  └──────────┘ └──────────┘ └──────────┘ │Slack     │  │    │
│  │                                           └──────────┘  │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  NORMALIZATION ENGINE                                   │    │
│  │                                                         │    │
│  │  • All incoming formats → Standard Ticket Format        │    │
│  │  • Email subject+body → ticket title+description        │    │
│  │  • SMS text → ticket description                        │    │
│  │  • Call transcript → ticket description                 │    │
│  │  • Chat message → ticket description                    │    │
│  │  • Attach metadata: channel_type, sender, timestamp     │    │
│  │  • Per-tenant credential vault (encrypted, isolated)    │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│                            ▼                                     │
│                    Standardized Ticket                           │
│                    (goes to PARWA Node 1)                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ACTION ADAPTERS (Outbound — responses go OUT)          │    │
│  │                                                         │    │
│  │  • Reply via same channel (email reply, SMS reply, etc) │    │
│  │  • Execute actions in CRM (refund in HubSpot, etc)      │    │
│  │  • Update customer records in connected tools           │    │
│  │  • Uses tenant's own credentials for all actions        │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│  ┌─────────────────────────┴───────────────────────────────┐    │
│  │  SYNC ADAPTERS (Context — data pulled FOR context)      │    │
│  │                                                         │    │
│  │  • Fetch customer data from CRM (PARWA Node 3 uses)     │    │
│  │  • Pull recent interactions from helpdesk               │    │
│  │  • Sync knowledge docs from Notion/Confluence/Drive     │    │
│  │  • Uses tenant's own credentials — zero cross-tenant    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  INFRASTRUCTURE                                         │    │
│  │                                                         │    │
│  │  • Health checks: Every 60s per integration             │    │
│  │  • Retry logic: 3 retries with exponential backoff      │    │
│  │  • Rate limiting: Per-integration, per-tenant           │    │
│  │  • Credential vault: AES-256 encrypted per tenant       │    │
│  │  • Webhook management: Register + verify per tenant     │    │
│  │  • Error reporting: Feed to Jarvis SENSE on failure     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### UCB Connection Points to PARWA

| PARWA Node | UCB Direction | What Happens |
|-----------|--------------|-------------|
| Node 1 (Ingest) | INBOUND | Normalized tickets arrive from UCB channel adapters |
| Node 3 (Knowledge) | SYNC | Fetch CRM data, customer history from connected tools |
| Node 5 (Act+Verify) | OUTBOUND | Execute actions (send reply, process refund) via UCB action adapters |
| Jarvis SENSE | MONITOR | UCB health status feeds into Jarvis monitoring |

### Integration Registry Schema

```sql
CREATE TABLE integrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    integration_type VARCHAR(30) NOT NULL,  -- 'email', 'sms', 'calls', 'chat', 'crm', 'helpdesk', 'docs'
    provider        VARCHAR(30) NOT NULL,  -- 'sendgrid', 'twilio', 'hubspot', etc.
    credentials     JSONB NOT NULL,        -- Encrypted API keys, OAuth tokens
    config          JSONB NOT NULL,        -- Channel settings, sync preferences
    is_active       BOOLEAN DEFAULT TRUE,
    last_sync_at    TIMESTAMPTZ,
    health_status   VARCHAR(10) DEFAULT 'healthy',  -- 'healthy', 'degraded', 'down'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_integrations_tenant_id (tenant_id),
    INDEX idx_integrations_type_provider (integration_type, provider)
);
```

---

## 9. Multi-Tenant Data Isolation

### Isolation Strategy

Every data layer uses `tenant_id` as a MANDATORY filter. This is enforced at the database level, not just application level, to guarantee zero data leakage.

### Database Level

```sql
-- Row-Level Security (RLS) on EVERY table
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tickets
    USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE ai_wiki_entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON ai_wiki_entries
    USING (tenant_id = current_setting('app.tenant_id')::UUID);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON notifications
    USING (tenant_id = current_setting('app.tenant_id')::UUID);

-- Same for: knowledge_base, quota_tracking, integrations,
-- access_keys, variant_registry, key_usage_audit, etc.
```

### Vector Store Level

```
• Each tenant = separate namespace/collection
• Embeddings scoped to tenant_id
• Search queries auto-filter by tenant
• 🔒 Client A's tickets NEVER appear in Client B's AI Wiki search results
```

### Credential Isolation

```
• Each client's API keys in encrypted vault (AES-256)
• HubSpot key of Client A ≠ accessible by Client B
• OAuth tokens scoped per tenant
• 🔒 When PARWA Node 5 acts, it uses ONLY the current ticket's tenant credentials
```

### Variant Instance Isolation

```
Client A buys "Medium" → Medium Agent A (scoped to tenant_id A)
Client B buys "Medium" → Medium Agent B (scoped to tenant_id B)

Same tier, DIFFERENT:
• Knowledge base (Client A's products ≠ B's)
• AI Wiki (Client A's patterns ≠ B's)
• Connected tools (Client A's HubSpot ≠ B's)
• Policies (Client A's refund rules ≠ B's)
• Quota pool (Client A's 500/mo ≠ B's 500/mo)

🔒 ONE agent codebase, MANY isolated instances
```

### Shared vs Isolated Data

| Data | Shared? | Why |
|------|---------|-----|
| Agent codebase | ✅ Shared | Same 8-node pipeline code for all |
| Technique library | ✅ Shared | Same 25 techniques for all |
| LLM models | ✅ Shared | Same API endpoints for all |
| Tenant data | ❌ Isolated | Each client's data is their own |
| AI Wiki | ❌ Isolated | Per-client wiki with 3 sections |
| Knowledge base | ❌ Isolated | Per-client docs and policies |
| Integration creds | ❌ Isolated | Per-client API keys |
| Quota tracking | ❌ Isolated | Per-client usage counters |
| Notifications | ❌ Isolated | Per-client alerts |
| Access keys | ❌ Isolated | Per-client key management |

---

## 10. Policy Change Detection

### Flow

When a company changes policies (refund rules, pricing, etc.), the system must ensure PARWA doesn't act on stale data.

```
┌─────────────────────────────────────────────────────────────────┐
│              POLICY CHANGE DETECTION FLOW                        │
│                                                                 │
│  1. Admin updates policy in AI Wiki Section C                   │
│     → Via dashboard → Edit policy → Save                        │
│     → Version increments (v2.2 → v2.3)                          │
│     → updated_at timestamp changes                              │
│                                                                 │
│  2. Jarvis SENSE detects the change                             │
│     → Monitors Section C for version changes                    │
│     → Compares: "refund_policy changed from v2.2 to v2.3"      │
│     → Creates awareness signal                                  │
│                                                                 │
│  3. Jarvis EVALUATE assesses impact                             │
│     → "Refund policy changed. Current active tickets may        │
│        be using old policy. Priority: HIGH"                     │
│     → CoT reasoning: which nodes are affected?                  │
│                                                                 │
│  4. Jarvis NOTIFY informs relevant systems                      │
│     → Feeds updated policy to PARWA Node 2 (quota/routing)     │
│     → Notification Center: "Policy updated: Refund v2.3"       │
│     → PARWA Node 3: Next knowledge fetch pulls fresh policy    │
│                                                                 │
│  5. PARWA Node 3 picks up fresh policy                          │
│     → Policy Sync Check on every ticket: is Section C current? │
│     → If version changed since last fetch → re-fetch            │
│     → All subsequent tickets use new policy                     │
│                                                                 │
│  6. In-flight tickets                                           │
│     → Tickets already past Node 3 use the policy they fetched  │
│     → Only tickets that haven't reached Node 3 yet get new one │
│     → This prevents mid-pipeline inconsistency                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. 25 Techniques — LLM vs Non-LLM Classification

### 11 Non-LLM Techniques (Free, Instant)

| # | Technique | Full Name | What It Does |
|---|-----------|-----------|-------------|
| 1 | SmartRouter | Smart Router | Classifies ticket type and complexity using rule-based patterns |
| 2 | GSD | Goal Sub-Goal Decomposition | Breaks complex problems into sub-problems |
| 3 | MAKER | Multi-Agent Knowledge Extraction & Reasoning | Bridges knowledge gaps by finding connections |
| 4 | ThoT | Thread of Thought | Threads multiple reasoning paths together coherently |
| 5 | FederatedReasoning | Federated Reasoning | Aggregates solutions from multiple techniques like voting |
| 6 | ZeroShotValidator | Zero-Shot Validator | Flags outputs that look statistically unusual |
| 7 | MetaLearner | Meta Learner | Learns from past decisions to improve future routing/reasoning |
| 8 | DynamicContext | Dynamic Context | Pulls relevant context (customer history, account info, etc.) |
| 9 | ContextualCompression | Contextual Compression | Removes irrelevant content from knowledge/context |
| 10 | TurboCompress | Turbo Compression | Ultra-fast compression optimized for simple content |
| 11 | AdaptiveBudget | Adaptive Budget | Monitors and optimizes resource usage within nodes |

### 14 LLM Techniques (Require API Calls)

| # | Technique | Full Name | What It Does | API Calls |
|---|-----------|-----------|-------------|-----------|
| 1 | CoT | Chain of Thought | Step-by-step reasoning | 1 |
| 2 | ReAct | Reasoning + Acting | Think-Act-Observe loop for actions | 1-3 |
| 3 | ToT | Tree of Thought | Explores multiple reasoning paths | 2-3 |
| 4 | Reverse Thinking | Reverse Thinking | Works backward from answer to validate | 1 |
| 5 | UoT | Uncertainty of Thought | Measures confidence/uncertainty | 1 |
| 6 | GST | Goal State Tracking | Tracks progress toward solution | 1 |
| 7 | HyDE | Hypothetical Document Embedding | Generates hypothetical answer for search | 1 |
| 8 | CLARA | Contextual Learning and Adaptive Retrieval Architecture | Gatekeeper for knowledge quality | 1 |
| 9 | Multi-Query | Multi-Query | Rewrites question in multiple ways | 1 |
| 10 | Step-Back | Step-Back Prompting | Zooms out to broader principles | 1 |
| 11 | Reflexion | Reflexion | Self-critique of output quality | 1 |
| 12 | Self-Consistency | Self-Consistency | Multiple solutions, majority vote | 3 |
| 13 | CRP | Chain of Revision Prompting | Structured answer revision | 1 |
| 14 | Least-to-Most | Least-to-Most Prompting | Solves easy sub-problems first for context | 1 |

---

## 12. Technique-to-Node Mapping (PARWA + Jarvis)

### PARWA Nodes (8)

| Technique | LLM? | Node 1 | Node 2 | Node 3 | Node 4 | Node 5 | Node 6 | Node 7 | Node 8 |
|-----------|------|--------|--------|--------|--------|--------|--------|--------|--------|
| SmartRouter | ❌ | ✅ classify | | | | | | | |
| UoT | ✅ | ✅ confidence | | | ✅ confidence | | | | |
| DynamicContext | ❌ | ✅ context | | ✅ knowledge | | | | ✅ simple | |
| MetaLearner | ❌ | ✅ routing | | | ✅ weights | | | ✅ patterns | |
| CLARA | ✅ | | | ✅ gatekeeper | | | | | |
| HyDE | ✅ | | | ✅ search | | | | | |
| Multi-Query | ✅ | | | ✅ multi-angle | | | | | |
| Step-Back | ✅ | | | ✅ broad search | | | | | |
| ContextualCompression | ❌ | | | ✅ compress | | | ✅ response | ✅ simple | ✅ super |
| GSD | ❌ | | | | ✅ decompose | ✅ actions | ✅ check | ✅ simple | ✅ super |
| Least-to-Most | ✅ | | | | ✅ order | | | | |
| CoT | ✅ | | | | ✅ solve | | | | ✅ max detail |
| MAKER | ❌ | | | | ✅ bridge | ✅ action gap | | ✅ simple | ✅ super |
| ToT | ✅ | | | | ✅ explore | | | | ✅ all paths |
| Reverse Thinking | ✅ | | | | ✅ validate | ✅ validate | | | ✅ double |
| ZeroShotValidator | ❌ | | | | ✅ flag | ✅ flag | ✅ check | ✅ simple | ✅ super |
| ThoT | ❌ | | | | ✅ thread | | ✅ thread | ✅ simple | ✅ super |
| FederatedReasoning | ❌ | | | | ✅ combine | | ✅ aggregate | ✅ simple | ✅ super |
| ReAct | ✅ | | | | | ✅ act-observe | | | |
| Reflexion | ✅ | | | | | | ✅ critique | | ✅ deep |
| CRP | ✅ | | | | | | ✅ revise | | ✅ revise |
| Self-Consistency | ✅ | | | | | | | | ✅ 3-vote |
| TurboCompress | ❌ | | | | | | | ✅ fast | |
| AdaptiveBudget | ❌ | | | | | | | ✅ budget | |
| GST | ✅ | | | | ✅ track | | | | |

### Jarvis Nodes (3) — 15 Techniques (11 Non-LLM + 4 LLM)

| Technique | LLM? | Jarvis Node 1 (SENSE) | Jarvis Node 2 (EVALUATE) | Jarvis Node 3 (NOTIFY) |
|-----------|------|----------------------|--------------------------|----------------------|
| SmartRouter | ❌ | ✅ classify signals | | |
| GSD | ❌ | | ✅ break complex eval | |
| MAKER | ❌ | | ✅ bridge info gaps | |
| ThoT | ❌ | | ✅ thread signals | |
| FederatedReasoning | ❌ | | ✅ aggregate signals | |
| ZeroShotValidator | ❌ | ✅ flag unusual patterns | ✅ flag unusual evals | |
| MetaLearner | ❌ | | ✅ learn admin preferences | ✅ personalize delivery |
| DynamicContext | ❌ | ✅ pull current state | ✅ context for eval | ✅ context for answers |
| ContextualCompression | ❌ | | | ✅ compress reports |
| TurboCompress | ❌ | | | ✅ fast chat summary |
| AdaptiveBudget | ❌ | | | ✅ monitor Jarvis usage |
| CoT | ✅ | | ✅ step-by-step reasoning | ✅ complex chat answers |
| CLARA | ✅ | | ✅ clarify ambiguity | |
| Step-Back | ✅ | | ✅ broader context | ✅ strategic answers |
| Reflexion | ✅ | | ✅ self-critique evals | ✅ critique before send |

---

## 13. Dual Pipeline Flow

### Path 1: Simple/Medium Tickets (Non-LLM Fast Track)

```
Node 1 (Classify) → Node 2 (Smart Route) → Node 3 (Knowledge Fetch)
→ Node 7 (Simple/Medium Resolver)
    → Layer 1: THINK (non-LLM reasoning)
    → Layer 2: ACT (non-LLM actions)
    → Layer 3: CHECK (non-LLM quality)
        → PASS → Response Output (via UCB)
        → FAIL (< 80% confidence) → Auto-upgrade to Complex Path (Node 4)
```

**Total LLM calls**: 0 in Node 7 (Node 1 has 1, Node 3 has 3-4)
**Expected accuracy**: 88-90% (with safety net upgrade for tricky tickets)

### Path 2: Complex/Hard Tickets (Full LLM Pipeline)

```
Node 1 (Classify) → Node 2 (Smart Route) → Node 3 (Knowledge Fetch)
→ Node 4 (Reasoning) → Node 5 (Act + Verify) → Node 6 (Quality)
    → PASS → Response Output (via UCB)
    → FAIL (loop 1) → Back to Node 4
        → Node 4 → Node 5 → Node 6
            → PASS → Response Output (via UCB)
            → FAIL (loop 2) → Node 8 (Super Node)
                → PASS → Response Output (via UCB)
                → FAIL → Human Escalation + Notification Center
```

**Total LLM calls**: 10-13 (1st pass), 16-20 (with 1 loop), 21-26 (with Super Node)
**Expected accuracy**: 92-94% (1st pass), 94-96% (with loops), 95-97% (with Super Node)

### Cost Per Ticket Type Summary

| Ticket Type | Path | Avg Total LLM Calls | Est. Accuracy |
|-------------|------|---------------------|---------------|
| Simple | Nodes 1→2→3→7 | 4-5 (Node 1 + Node 3 only) | 88-90% |
| Medium | Nodes 1→2→3→7 (with safety net) | 4-8 | 90-92% |
| Complex (1st pass) | Nodes 1→2→3→4→5→6 | 10-13 | 92-94% |
| Complex (1 loop) | Above + 4→5→6 again | 16-20 | 94-96% |
| Complex (Super Node) | Above + Node 8 | 21-26 | 95-97% |

---

## 14. Variant System & Quota Management

### Variant Tiers

| Feature | Mini ($999/mo) | PARWA ($2,499/mo) | High ($4,999/mo) |
|---------|----------------|--------------------|--------------------|
| Ticket Quota | 500/month | TBD/month | TBD/month |
| Simple tickets | ✅ | ✅ | ✅ |
| Medium tickets | ✅ | ✅ | ✅ |
| Complex reasoning | ❌ | ✅ | ✅ |
| Execute refunds | ❌ (recommend only) | ✅ (≤ $500) | ✅ (unlimited) |
| Execute credits | ❌ (recommend only) | ✅ (≤ $200) | ✅ (unlimited) |
| Account changes | ❌ (recommend only) | ✅ (limited) | ✅ (full) |
| Super Node | ❌ | ✅ | ✅ |
| Quality loops | 0 | Max 2 | Max 2 |
| AI Wiki access | Read only | Read + Learn | Read + Write + Learn |
| Priority queue | Standard | Standard | High |
| Integrations | 2 channels | 5 channels | Unlimited |

### One Agent, Dynamic Restrictions

**Core Principle**: Mini, PARWA, and High are NOT separate agents. They are the SAME agent with different RESTRICTIONS. One agent instance handles all tickets for a user, applying the correct restriction set per ticket based on Node 2's routing decision.

```python
variant_registry = {
    "tenant_id": "tenant_abc123",
    "user_id": "user_123",
    "variants": {
        "mini": {
            "purchased": True,
            "quota_total": 500,
            "quota_remaining": 347,
            "capabilities": ["recommend", "simple_info", "medium_info"]
        },
        "parwa": {
            "purchased": False
        },
        "high": {
            "purchased": True,
            "quota_total": 2000,
            "quota_remaining": 1856,
            "capabilities": ["everything"]
        }
    }
}
```

### Node 2 Routing Examples

**"What's your pricing?" (simple, no execution)**:
```
Needs: simple_info
Mini can handle? YES + has quota? YES → Use Mini quota
```

**"Refund $30" (needs execution)**:
```
Needs: execute_refund_30
Mini can handle? NO (can't execute refunds)
High can handle? YES + has quota? YES → Use High quota
```

**"What's your pricing?" BUT Mini quota = 0**:
```
Needs: simple_info
Mini can handle? YES but quota = 0
High can handle? YES + has quota? YES → Use High quota (expensive for simple ticket)
```

---

## 15. Quality Loop & Super Node

### Quality Loop Flow

```
Node 4 (Reason) → Node 5 (Act) → Node 6 (Quality Check)
                                           │
                                    quality_score > 90%?
                                           │
                                     YES → SEND
                                     NO  → Loop back to Node 4
                                           │
                                    (2nd attempt)
                                    Node 4 → Node 5 → Node 6
                                                           │
                                                    quality_score > 90%?
                                                           │
                                                     YES → SEND
                                                     NO  → Node 8 (Super Node)
```

### Quality Scoring Formula

```python
quality_score = weighted_average([
    reflexion_score * 0.30,       # LLM self-critique (most trusted)
    crp_score * 0.25,             # Revision quality
    zero_shot_score * 0.20,       # Statistical validity
    thot_coherence * 0.15,        # Logical coherence
    gsd_part_scores * 0.10        # Per-part quality
])
```

### Super Node Escalation

```
IF quality_score > 90% → PASS → Format and send
IF quality_score 70-90% AND loop_count < 2 → Loop back to Node 4
IF loop_count >= 2 → Activate Node 8 (Super Node)

Super Node:
  IF quality > 85% → PASS → Format and send
  IF quality <= 85% → ESCALATE TO HUMAN
     → Notification Center alerts admin (unique key)
     → Jarvis tracks as stuck problem
     → Include: original ticket + all failed attempts + analysis
```

---

## 16. MAKER Hallucination Prevention

### 3 Safeguards

**Safeguard 1: Confidence Scoring**
```
MAKER assigns a confidence score to each bridge connection:
- High confidence (> 85%): "Pro plan refund → 30-day policy" (direct match)
- Medium confidence (60-85%): "Pro plan refund → similar to Business plan" (inferred)
- Low confidence (< 60%): "Pro plan refund → maybe related to annual billing" (weak)

Only high + medium confidence bridges enter reasoning.
Low confidence bridges are flagged but NOT used.
```

**Safeguard 2: ZeroShotValidator Gate**
```
Before MAKER's output enters reasoning:
ZeroShotValidator checks:
- Are the bridge connections logically consistent with knowledge from Node 3?
- Does any bridge contradict known facts?
- Are there alternative bridges that are more likely?

If ZeroShotValidator flags a bridge → it's removed before reasoning uses it.
```

**Safeguard 3: Reverse Thinking Check**
```
After reasoning uses MAKER's bridges:
Reverse Thinking verifies:
- Does the final conclusion DEPEND on low-confidence bridges?
- If we remove MAKER's bridges, does the answer change significantly?
- If the answer depends on a low-confidence bridge → flag for quality loop
```

---

## 17. Implementation Phases

---

### Phase 1: Foundation — Core Pipeline (Days 1-4)

**Goal**: Core pipeline skeleton — all 8 nodes connected, basic flow working, key-based access

**Tasks**:
- [ ] Create new `graph_v2.py` with 8-node structure (replace 23-node + subgraphs)
- [ ] Create `state_v2.py` with updated pipeline state (including tenant_id)
- [ ] Implement Node 1: Ingest + Classify (SmartRouter + basic UoT + DynamicContext)
- [ ] Implement Node 2: Smart Route (variant registry + quota tracker + basic routing)
- [ ] Implement Node 3: Knowledge Fetch (basic RAG without CLARA yet)
- [ ] Implement Node 4: Reasoning Engine (basic CoT only, no 4-layer yet)
- [ ] Implement Node 5: Act + Verify (rule-based actions only)
- [ ] Implement Node 6: Quality + Format (basic quality check, no Reflexion/CRP yet)
- [ ] Implement Node 7: Simple/Medium Resolver (basic non-LLM layers)
- [ ] Implement Node 8: Super Node (stub — just escalate to human for now)
- [ ] Wire up dual pipeline: simple path vs. complex path
- [ ] Wire up quality loop (Node 6 → Node 4, max 2 loops)
- [ ] **Key-based access system**:
  - [ ] Database schema: `tenants`, `users`, `access_keys`, `key_usage_audit`
  - [ ] Key generation endpoint: `POST /api/auth/generate-key`
  - [ ] Key validation middleware: verify key hash on every request
  - [ ] Session management: JWT with tenant_id + session_id
  - [ ] Admin-only endpoints: key regeneration, billing access
  - [ ] Rate limiting: 5 failed attempts → 15-min lockout
- [ ] **Multi-tenant isolation**:
  - [ ] Add `tenant_id` to ALL data tables
  - [ ] Enable Row-Level Security on ALL tables
  - [ ] Set `app.tenant_id` session variable on each request
- [ ] Test: 8 test tickets through full pipeline, verify flow is correct
- [ ] Test: Key-based access — generate key, access dashboard, verify tenant isolation

**Deliverable**: Working pipeline with all 8 nodes, key-based access, tenant isolation

---

### Phase 2: Intelligence — LLM Techniques (Days 5-8)

**Goal**: Add all 14 LLM techniques to the correct nodes

**Tasks**:
- [ ] Node 1: Full UoT with confidence scoring
- [ ] Node 3: CLARA as gatekeeper (3-question filter), HyDE, Multi-Query, Step-Back
- [ ] Node 4: Full 4-layer architecture
  - [ ] Layer 1: GSD + Least-to-Most
  - [ ] Layer 2: CoT + MAKER + ToT
  - [ ] Layer 3: Reverse Thinking + ZeroShotValidator + UoT
  - [ ] Layer 4: ThoT + FederatedReasoning + MetaLearner
- [ ] Node 5: ReAct for complex actions, Reverse Thinking for action validation
- [ ] Node 6: Reflexion + CRP quality scoring
- [ ] Node 8: Self-Consistency + ToT + Reverse Thinking + Reflexion + CRP + CoT
- [ ] Test: Same 8 tickets, compare with Phase 1 results

**Deliverable**: Full LLM technique integration, all 14 techniques active

---

### Phase 3: Optimization — Non-LLM Path (Days 9-11)

**Goal**: Make Node 7 (Simple/Medium Resolver) fully functional with all 11 non-LLM techniques

**Tasks**:
- [ ] Node 7 Layer 1 (THINK): GSD + MAKER + ThoT + FederatedReasoning + MetaLearner + ZeroShotValidator
- [ ] Node 7 Layer 2 (ACT): Rule-based actions + MAKER + GSD + ZeroShotValidator
- [ ] Node 7 Layer 3 (CHECK): ZeroShotValidator + GSD + ThoT + ContextualCompression + TurboCompress + FederatedReasoning
- [ ] Implement safety net: ZeroShotValidator < 80% → auto-upgrade to Node 4
- [ ] Test: 4 simple tickets through Node 7, verify 0 LLM calls + good accuracy
- [ ] Test: 1 tricky "simple" ticket, verify safety net catches it and upgrades

**Deliverable**: Non-LLM fast track working, simple tickets resolved with 0 LLM calls

---

### Phase 4: Business Logic — Variants & Quotas (Days 12-14)

**Goal**: Full variant system with quota management

**Tasks**:
- [ ] Node 2: Full variant registry with database storage
- [ ] Node 2: Quota tracker with real-time countdown
- [ ] Node 2: Capability matrix for all 3 tiers
- [ ] Node 2: Three-dimensional routing (capability + quota + efficiency)
- [ ] Node 5: Variant-aware action execution (restrictions applied from Node 2)
- [ ] Node 7: Variant-aware simple ticket handling (Mini = recommend only)
- [ ] AI Wiki access levels per variant (read / read+learn / read+write+learn)
- [ ] Integration count limits per variant tier
- [ ] Test: Same ticket through Mini vs. High → verify different restrictions
- [ ] Test: Quota exhaustion → verify fallback to next tier
- [ ] Test: Refund > $500 through PARWA → verify recommend-only behavior

**Deliverable**: Complete variant system, quota management, variant-aware pipeline

---

### Phase 5: Quality & Safety (Days 15-17)

**Goal**: Quality loop, Super Node, MAKER hallucination prevention

**Tasks**:
- [ ] Node 6: Full quality scoring formula (Reflexion + CRP + ZeroShotValidator + ThoT + GSD)
- [ ] Quality loop: Node 6 → Node 4, max 2 loops
- [ ] Node 8: Full Super Node implementation
  - [ ] Reflexion: Analyze why previous 2 attempts failed
  - [ ] Self-Consistency: 3 independent solutions with majority vote
  - [ ] ToT: Deep path exploration
  - [ ] Reverse Thinking: Backward validation
  - [ ] CRP: Revision with failure context
- [ ] Node 8: Escalation to human with full context
- [ ] MAKER safeguards:
  - [ ] Confidence scoring on bridge connections
  - [ ] ZeroShotValidator gate before bridges enter reasoning
  - [ ] Reverse Thinking check after reasoning uses bridges
- [ ] Test: Hard ticket that fails quality loop → verify Super Node activates
- [ ] Test: Impossible ticket → verify human escalation with context
- [ ] Test: MAKER low-confidence bridge → verify it's caught and removed

**Deliverable**: Quality loop, Super Node, MAKER safety — full safety net

---

### Phase 6: AI Wiki & Learning (Days 18-20)

**Goal**: AI Wiki 3-section integration across all nodes

**Tasks**:
- [ ] AI Wiki database schema: `ai_wiki_entries` with section A/B/C
- [ ] Section A: Ticket Patterns — PARWA writes on resolution, reads on Node 3 fetch
- [ ] Section B: Admin Behavior — Jarvis writes on interactions, PARWA reads
- [ ] Section C: Company Knowledge — Admin writes via dashboard, both read
- [ ] Node 1: Read Wiki Section A for classification patterns
- [ ] Node 3: Search Wiki for evidence, add new patterns (PARWA+)
- [ ] Node 3: Policy sync check — compare Section C version before fetch
- [ ] Node 4: Check Wiki for reasoning patterns that worked
- [ ] Node 7: MetaLearner uses Wiki patterns for simple resolution
- [ ] Node 8: Reflexion checks Wiki for similar hard tickets
- [ ] Variant-based access control (read / read+learn / read+write+learn)
- [ ] Vector store: Tenant-scoped namespaces for wiki embeddings
- [ ] Test: Resolve ticket → verify Wiki Section A entry created → next similar ticket uses Wiki
- [ ] Test: Mini user → verify read-only Wiki access

**Deliverable**: AI Wiki fully integrated, 3-section design, learning loop active

---

### Phase 7: Integration Layer — UCB (Days 21-24)

**Goal**: Unified Connector Bus — connect variants to Email, SMS, Calls, Chat, CRM, Helpdesk

**Tasks**:
- [ ] UCB core framework:
  - [ ] Normalization engine: all incoming → standard ticket format
  - [ ] Action adapters: outbound replies/actions through correct channel
  - [ ] Sync adapters: fetch CRM data for context
  - [ ] Health check system: monitor integration status every 60s
  - [ ] Retry logic: 3 retries with exponential backoff
  - [ ] Rate limiting: per-integration, per-tenant
- [ ] Channel adapters (inbound):
  - [ ] Email: SendGrid webhook → ticket
  - [ ] SMS: Twilio webhook → ticket
  - [ ] Calls: Twilio/Vonage transcript → ticket
  - [ ] Chat: WhatsApp/Intercom/Crisp webhook → ticket
- [ ] CRM adapters (sync + action):
  - [ ] HubSpot: fetch customer data, execute refunds/credits
  - [ ] Salesforce: fetch customer data, execute actions
- [ ] Helpdesk adapters:
  - [ ] Zendesk: sync tickets, update status
  - [ ] Freshdesk: sync tickets, update status
- [ ] Credential vault:
  - [ ] AES-256 encryption per tenant
  - [ ] OAuth token management
  - [ ] API key rotation support
- [ ] Integration registry database schema
- [ ] PARWA Node 1: Receive tickets from UCB
- [ ] PARWA Node 3: Fetch CRM data via UCB
- [ ] PARWA Node 5: Execute actions via UCB
- [ ] Jarvis SENSE: Monitor UCB health
- [ ] Test: Email ticket comes in → PARWA processes → reply via email
- [ ] Test: HubSpot customer data fetched in Node 3
- [ ] Test: Integration goes down → Jarvis detects → Notification Center alerts

**Deliverable**: Full UCB with all adapters, per-tenant credentials, health monitoring

---

### Phase 8: Jarvis — 3-Node Pipeline (Days 25-28)

**Goal**: Jarvis SENSE, EVALUATE, NOTIFY — awareness + notification + chat

**Tasks**:
- [ ] Jarvis Node 1 (SENSE):
  - [ ] Monitor PARWA pipeline states (all 8 nodes)
  - [ ] Track quota usage and burn rate
  - [ ] Watch for stuck/unsolved tickets (from Node 7 safety net, Node 8 failures)
  - [ ] Monitor integration health (from UCB)
  - [ ] Detect policy changes in AI Wiki Section C
  - [ ] Track admin behavior patterns
- [ ] Jarvis Node 2 (EVALUATE):
  - [ ] CoT reasoning for complex evaluations
  - [ ] CLARA for clarifying ambiguous signals
  - [ ] Step-Back for broader context
  - [ ] Reflexion for self-critique before notifying
  - [ ] Priority scoring formula (impact, urgency, trend, admin preference, frequency)
  - [ ] All 11 non-LLM techniques for fast evaluations
- [ ] Jarvis Node 3 (NOTIFY):
  - [ ] Push notifications to Notification Center
  - [ ] Unique key generation: PARWA-NFY-XXX
  - [ ] Batch similar notifications (5-min window)
  - [ ] Answer admin chat questions (using AI Wiki + quota + variant data)
  - [ ] Feed quota/variant info back to PARWA Node 2
  - [ ] Update AI Wiki Section B (admin behavior patterns)
- [ ] Notification Center:
  - [ ] Database schema: `notifications` table
  - [ ] Dashboard widget: priority-grouped notification feed
  - [ ] Copy key → ask Jarvis integration
  - [ ] Mark resolved / dismiss actions
- [ ] Jarvis ↔ PARWA connections:
  - [ ] SENSE reads PARWA pipeline state
  - [ ] NOTIFY feeds quota data to PARWA Node 2
  - [ ] Stuck tickets flow from PARWA to Jarvis
- [ ] Test: Ticket stuck in Super Node → Jarvis detects → Notification with unique key
- [ ] Test: Admin copies key → asks Jarvis → gets full details
- [ ] Test: Policy changes in Section C → Jarvis detects → informs PARWA Node 3
- [ ] Test: Admin asks "How many refunds today?" → Jarvis answers with real data

**Deliverable**: Full Jarvis pipeline, Notification Center, Jarvis ↔ PARWA connections

---

### Phase 9: Onboarding Flow (Days 29-32)

**Goal**: 6-step onboarding wizard with key delivery and dashboard wiring

**Tasks**:
- [ ] Onboarding Step 1: Account Setup
  - [ ] Company name, admin email, master password
  - [ ] Industry category, company size
  - [ ] Creates tenant_id, admin user, empty AI Wiki
- [ ] Onboarding Step 2: Variant Selection
  - [ ] Interactive tier comparison
  - [ ] Monthly/Annual billing toggle
  - [ ] Creates variant_registry entry, sets initial quota
- [ ] Onboarding Step 3: Integration Setup
  - [ ] OAuth flows or API key inputs for each tool
  - [ ] Test connection button per integration
  - [ ] Registers in UCB, stores encrypted credentials
  - [ ] Dashboard shows connected tools with status
- [ ] Onboarding Step 4: Knowledge Base Upload
  - [ ] File upload (PDF, DOCX) + URL import
  - [ ] Policy entry forms
  - [ ] Auto-parse, chunk, embed
  - [ ] Stores in tenant-scoped vector store + AI Wiki Section C
- [ ] Onboarding Step 5: Policy Configuration
  - [ ] Refund/credit rules, escalation triggers
  - [ ] Response tone selector
  - [ ] Business hours, restricted actions
  - [ ] Stores in AI Wiki Section C with version tracking
- [ ] Onboarding Step 6: Key Generation + First Victory
  - [ ] Generate access key: `pk_live_XXXX`
  - [ ] Display once with copy/download buttons
  - [ ] Send test ticket through pipeline
  - [ ] Verify first ticket resolves correctly
  - [ ] Dashboard activates fully
- [ ] Onboarding ↔ Dashboard wiring:
  - [ ] Each step updates dashboard in real-time
  - [ ] Progress indicator (0/6 → 6/6)
  - [ ] Integration status panel live-updates on Step 3
  - [ ] Knowledge base stats update on Step 4
  - [ ] Policy config summary shows on Step 5
  - [ ] Full dashboard activates on Step 6
- [ ] Parallel access support:
  - [ ] Multiple sessions with same key
  - [ ] WebSocket per session for real-time updates
  - [ ] Independent chat sessions with Jarvis
- [ ] Test: Complete onboarding flow end-to-end
- [ ] Test: Key works for dashboard access
- [ ] Test: Multiple team members use same key simultaneously
- [ ] Test: Admin can regenerate key, old key invalidated

**Deliverable**: Complete onboarding flow with key delivery and dashboard wiring

---

### Phase 10: Integration Testing (Days 33-36)

**Goal**: End-to-end testing with real LLM calls, strict evaluation

**Tasks**:
- [ ] Test with 8 diverse tickets (real LLM, strict eval)
  - [ ] 2 simple tickets (should go through Node 7, 0 LLM in Node 7)
  - [ ] 2 medium tickets (should go through Node 7 with safety net possible)
  - [ ] 2 complex tickets (should go through Nodes 4-5-6)
  - [ ] 1 hard ticket (should trigger quality loop + possibly Super Node)
  - [ ] 1 impossible ticket (should escalate to human)
- [ ] Test all 3 variants with same tickets → verify different behavior
- [ ] Test quota exhaustion scenario
- [ ] Test multi-tenant isolation:
  - [ ] Client A data NOT visible to Client B
  - [ ] AI Wiki search scoped to tenant
  - [ ] Integration credentials isolated
- [ ] Test Jarvis end-to-end:
  - [ ] Stuck ticket → notification with unique key
  - [ ] Admin chat → accurate answers
  - [ ] Policy change → PARWA picks up new policy
- [ ] Test UCB integrations:
  - [ ] Email ticket in → reply via email out
  - [ ] SMS ticket in → reply via SMS out
  - [ ] CRM data fetch in Node 3
- [ ] Test onboarding → first victory flow
- [ ] Test key-based access: multiple sessions, admin key regeneration
- [ ] Measure: accuracy, LLM calls per ticket, latency, cost per resolution
- [ ] Compare with old 23-node pipeline results

**Deliverable**: Honest test results, comparison with old pipeline

---

### Phase 11: Production Hardening (Days 37-40)

**Goal**: Make it production-ready — monitoring, error handling, rate limits, full dashboard

**Tasks**:
- [ ] Error handling: What happens when LLM API fails mid-pipeline?
- [ ] Rate limit management: NVIDIA API + ZAI SDK rotation (~50 RPM combined)
- [ ] Monitoring: Log every node's input/output/confidence/score
- [ ] Alerting: Super Node activation rate, human escalation rate, accuracy drift
- [ ] Caching: Cache Node 3 knowledge results for similar tickets
- [ ] Fallback: If Node 3 fails, can we still answer from AI Wiki alone?
- [ ] Cost tracking per ticket, per variant, per node, per tenant
- [ ] Load testing: 50 RPM sustained, verify pipeline doesn't break
- [ ] Dashboard polish:
  - [ ] PARWA pipeline status (Node 1-8 health)
  - [ ] Jarvis chat + awareness feed
  - [ ] Notification Center (unsolved/stuck only)
  - [ ] AI Wiki viewer (Sections A, B, C)
  - [ ] Integration status panel
  - [ ] Quota meters per variant
  - [ ] Key management (admin only)
- [ ] Security audit:
  - [ ] Key storage (hashed, not plaintext)
  - [ ] Tenant isolation verification
  - [ ] Credential vault encryption
  - [ ] Rate limiting on auth endpoints
  - [ ] Audit logging for all key usage
- [ ] Push to GitHub with clean README

**Deliverable**: Production-ready platform, deployed and monitored

---

## 18. Production Readiness Checklist

### Access & Authentication

- [ ] Key-based access system implemented
- [ ] Keys generated during onboarding before first victory
- [ ] Admin can change/retrieve keys
- [ ] Multiple users can access with same key simultaneously
- [ ] Key hashed in storage (SHA-256)
- [ ] Rate limiting on key validation attempts
- [ ] Session management with JWT (tenant_id + session_id)
- [ ] Audit logging for all key usage

### Multi-Tenant Isolation

- [ ] tenant_id on ALL data tables
- [ ] Row-Level Security enabled on all tables
- [ ] Vector store namespaces scoped per tenant
- [ ] Integration credentials isolated per tenant
- [ ] AI Wiki fully isolated per client
- [ ] No cross-tenant data access possible

### Onboarding

- [ ] 6-step onboarding wizard complete
- [ ] Each step wired to dashboard
- [ ] Key delivered at Step 6 (before first victory)
- [ ] First test ticket validates pipeline
- [ ] Dashboard activates progressively during onboarding

### PARWA Pipeline (8 Nodes)

- [ ] All 8 nodes implemented and connected
- [ ] All 25 techniques mapped to correct nodes
- [ ] Dual pipeline working (simple/medium vs. complex)
- [ ] Quality loop with max 2 loops before Super Node
- [ ] Super Node activates only after 2 failed loops
- [ ] Human escalation with full context after Super Node fails
- [ ] MAKER hallucination prevention (3 safeguards)
- [ ] Safety net: Node 7 < 80% confidence → auto-upgrade to Node 4

### Jarvis Pipeline (3 Nodes)

- [ ] SENSE: monitors PARWA, quotas, integrations, policies
- [ ] EVALUATE: CoT, CLARA, Step-Back, Reflexion for evaluation
- [ ] NOTIFY: pushes notifications, answers chat, feeds PARWA Node 2
- [ ] 15 techniques mapped (11 non-LLM + 4 LLM)

### Notification Center

- [ ] Unsolved/stuck problems only
- [ ] Unique keys per notification (PARWA-NFY-XXX)
- [ ] Batching of similar notifications
- [ ] Copy key → ask Jarvis integration works
- [ ] Priority-based delivery (CRITICAL/HIGH/MEDIUM/LOW)

### AI Wiki (3 Sections Per Client)

- [ ] Section A: Ticket Patterns (PARWA writes, Jarvis reads)
- [ ] Section B: Admin Behavior (Jarvis writes, PARWA reads)
- [ ] Section C: Company Knowledge (Admin writes, both read)
- [ ] Policy change detection working
- [ ] Version tracking on Section C entries
- [ ] Variant-based access levels enforced

### Integration Layer (UCB)

- [ ] Email adapter (SendGrid/Mailgun/Gmail)
- [ ] SMS adapter (Twilio/MSG91)
- [ ] Calls adapter (Twilio Voice/Vonage)
- [ ] Chat adapter (WhatsApp/Intercom/Crisp)
- [ ] CRM adapter (HubSpot/Salesforce)
- [ ] Helpdesk adapter (Zendesk/Freshdesk)
- [ ] Docs adapter (Notion/Confluence/Google Drive)
- [ ] Credential vault with AES-256 encryption
- [ ] Health checks every 60s
- [ ] Retry logic with exponential backoff
- [ ] Per-tenant rate limiting

### Business Logic

- [ ] Variant registry (Mini, PARWA, High)
- [ ] Quota tracking with real-time countdown
- [ ] Three-dimensional routing (capability + quota + efficiency)
- [ ] Variant-aware action execution (restrictions applied per ticket)
- [ ] One agent instance, dynamic restriction sets

### Quality Targets

- [ ] Simple tickets: 88-90% accuracy, 0 LLM calls in Node 7
- [ ] Complex tickets: 92-94% accuracy (1st pass), 94-96% (with loops)
- [ ] Super Node tickets: 95-97% accuracy
- [ ] Overall target: 90%+ across all ticket types

### Operational Requirements

- [ ] Rate limit management (NVIDIA API + ZAI SDK, ~50 RPM)
- [ ] Error handling for API failures mid-pipeline
- [ ] Monitoring and alerting for all nodes
- [ ] Cost tracking per ticket, per variant, per node, per tenant
- [ ] Caching for knowledge fetch results
- [ ] Fallback when knowledge base is unavailable
- [ ] Load tested at 50 RPM sustained

### Testing Requirements

- [ ] 8 diverse test tickets with real LLM calls
- [ ] All 3 variants tested with same tickets
- [ ] Quota exhaustion scenario tested
- [ ] Quality loop + Super Node tested
- [ ] MAKER hallucination prevention tested
- [ ] Safety net auto-upgrade tested
- [ ] Multi-tenant isolation tested (zero leakage)
- [ ] Jarvis end-to-end tested (stuck → notify → chat)
- [ ] UCB integrations tested (email/SMS/CRM)
- [ ] Onboarding → first victory flow tested
- [ ] Key-based access tested (multi-session, regeneration)
- [ ] Comparison with old 23-node pipeline

---

## 19. Dashboard Production Readiness

### 19.1 Strategic Positioning

**The positioning is fixed: PARWA is a headcount replacement platform.**

This is the bold CFO-facing version, not the soft CSM-facing version. Every dashboard element, every metric, every notification must reinforce this positioning. The buyer is the CFO/VP Support/COO — they are buying PARWA to eliminate headcount cost, not to "make their team more productive."

The moment PARWA's dashboard starts showing "your team is more productive" framing, we lose the differentiation against every other CX tool on the market. The competitive moat is the **headcount cost elimination** narrative, backed by the ROI Calculator showing real dollars saved.

The softer "CSM superpowers" positioning is reserved for **internal champions** during the sales discovery process — once the CFO has approved the budget based on headcount savings, the internal champion (often a CS Ops lead) gets the "this makes your team 5x more effective" pitch to drive adoption. But the dashboard itself never softens — it always shows replacement dollars.

### 19.2 Dashboard Removals — Delete These Features

The current dashboard has features that contradict the headcount-replacement positioning or that expose internal architecture to end users. These must be removed before production.

#### 19.2.1 Remove: Agent Builder (`/dashboard/agents/new`)

**Current state:** Dead UI page with no backend wiring. Shows a fake "create new agent" form that does nothing.

**Why remove entirely:**
- The architecture is **one agent per variant** with dynamic restrictions applied at runtime. There is no concept of "creating an agent" — the agent IS the variant.
- Exposing an agent builder implies PARWA is a "build your own AI agent" platform (AgentGPT, AutoGen, etc.) — that's a different market with different buyers and a worse unit economics.
- The agent builder creates the false impression that PARWA requires configuration work from the customer. It does not — PARWA works out of the box with the 6-step onboarding.

**Action:** Delete the page, remove from navigation, remove from any internal links. Update sidebar nav to show only "Variants" (which already exists and works).

**Files to delete:**
- `src/app/dashboard/agents/new/page.tsx`
- `src/app/dashboard/agents/page.tsx` (listing page — also unused)
- `src/components/dashboard/agent-builder/*` (entire folder if exists)
- Any Zustand store or hook referencing `agentBuilder`

#### 19.2.2 Remove: Pipeline Visualization Page

**Current state:** Mock page showing the 8 PARWA nodes with fake status indicators.

**Why remove:**
- The 8-node PARWA pipeline is **internal architecture**. Showing it to end users is like Stripe showing their internal payment routing diagram to merchants. Customers don't care HOW the sausage is made — they care that tickets get resolved.
- Showing the pipeline invites the question "can I configure individual nodes?" — and the answer is no, which frustrates users.
- The pipeline visualization creates a false perception that PARWA requires monitoring. It does not — Jarvis monitors itself and surfaces only actionable issues via the Notification Center.

**What replaces it:** A simple **System Health** indicator in the dashboard header (green/yellow/red dot) that reflects overall platform status. If green, no user action needed. If yellow/red, click to see Jarvis's diagnosis. No 8-node diagram, no per-node status, no technical jargon.

**Action:** Delete the pipeline page, replace with a single status chip in the top nav.

**Files to delete:**
- `src/app/dashboard/pipeline/page.tsx`
- Any pipeline visualization component folder
- Update sidebar nav to remove "Pipeline" entry

#### 19.2.3 Remove: AI Wiki Viewer (Backend-Only Asset)

**Current state:** Planned but not yet built. Some wireframes show a "View AI Wiki" page in the dashboard.

**Why NOT to build it:**
- The AI Wiki is **food for the agents, not content for humans**. It's structured data (ticket patterns, admin behaviors, company knowledge) that the Reasoning Engine retrieves during ticket resolution.
- A human reading the AI Wiki would see something like: "PATTERN-4823: When user reports 'login failed' + tenant=AcmeCorp + time=09:00-11:00 EST → 87% probability of Okta sync issue. Action: check Okta connector, escalate to admin if persists." This is unreadable noise for a human but gold for an LLM.
- Showing the AI Wiki implies the customer needs to "review" or "approve" what the AI knows. They do not. The customer approved everything during the 6-step onboarding; thereafter PARWA manages the Wiki autonomously.

**Exception — what the customer CAN see:**
- A **read-only "Knowledge Sources" panel** showing what documents they've uploaded (Section C — Company Knowledge). They can add/remove documents here. This is content management, not Wiki viewing.
- They do NOT see Section A (Ticket Patterns — PARWA writes) or Section B (Admin Behavior — Jarvis writes).

**Action:** Do NOT build an AI Wiki viewer. Build a "Knowledge Sources" file manager only (for Section C content the admin uploads). Sections A and B remain backend-only.

#### 19.2.4 Remove: Shadow Mode Page

**Current state:** Silently 404s. No backend route.

**Why remove:** Shadow mode (PARWA resolving tickets in parallel with humans for benchmarking) is a **sales/demo feature**, not a production feature. It belongs in a separate internal tool, not the customer dashboard.

**Action:** Delete the nav entry. If shadow benchmarking is needed for a specific deal, build it as a one-off internal script, not a dashboard feature.

#### 19.2.5 Remove: All Mock/Hardcoded Pages

**Current state:** Billing page (hardcoded numbers), Notifications page (mock array), Profile page (stale localStorage).

**Why remove:** These are broken. Either wire them to real backend data or remove them. There is no middle ground for production.

**Action:** See Section 19.4 (Wiring Tasks) for what each must connect to.

### 19.3 Dashboard Additions — New Features to Build

These are the four Jarvis-powered features plus the ROI Calculator that close the "replace the CSM" pitch. Without these, the headcount-replacement story has gaps. With these, the pitch is airtight.

#### 19.3.1 ADD: SLA Tracking (Jarvis Pre-Breach Alerts)

**What it does:** Jarvis actively monitors every ticket's response-time SLA against the contracted SLA tier. When a ticket is approaching breach (configurable threshold: default 80% of SLA window elapsed), Jarvis fires a notification to the admin BEFORE the breach happens — not after.

**Why this matters:** CSMs currently maintain SLA compliance by manually watching dashboards. PARWA replaces that manual monitoring with continuous Jarvis surveillance. This is one of the 8 PARWA-replaceable CSM duties.

**Data flow:**
1. Each ticket ingested via Node 1 (Ingest+Classify) is tagged with the customer's SLA tier (e.g., "Critical: 1hr response, 4hr resolution")
2. Jarvis SENSE continuously polls ticket state every 30 seconds
3. Jarvis EVALUATE computes remaining SLA window per ticket
4. At 80% elapsed → Jarvis NOTIFY sends "SLA at risk" alert to admin (and assigned human if any)
5. At 100% elapsed → Jarvis NOTIFY sends "SLA breached" alert with auto-generated postmortem

**Dashboard UI:**
- **SLA Dashboard page** with three sections:
  - **At-risk tickets** (red, 80-100% elapsed) — sortable by time remaining
  - **Breached tickets** (last 7 days, with root-cause analysis from Jarvis)
  - **SLA compliance trend** (line chart, last 30 days, per SLA tier)
- Per-ticket detail: SLA clock, time elapsed, time remaining, who Jarvis alerted, when

**Backend requirements:**
- New table: `sla_policies` (per tenant, per customer tier)
- New table: `sla_events` (every SLA at-risk + breach event, with Jarvis analysis)
- New Jarvis polling job (every 30s per tenant)
- New API routes: `GET /api/v1/sla/at-risk`, `GET /api/v1/sla/breaches`, `GET /api/v1/sla/compliance`

**Positioning in pitch:** *"Your CSM job posting says 'maintain SLA compliance.' That's a $95K/year human watching a clock. PARWA watches the clock in real time and alerts you before the breach — not after."*

#### 19.3.2 ADD: Customer Health Scores (Jarvis-Computed)

**What it does:** Jarvis computes a real-time health score (0-100) for every customer/account in the system, based on a weighted formula across multiple signals. CSMs currently do this manually in spreadsheets.

**Why this matters:** Customer health scoring is the second-most-cited CSM duty in job postings. Without this feature, the "replace the CSM" pitch has a visible hole. With it, PARWA covers the entire CS operational stack.

**Health score formula (default, admin-configurable per tenant):**
- **Ticket volume trend** (25%): decreasing = healthy, increasing = unhealthy
- **Sentiment trend** (20%): aggregated sentiment across all customer tickets (Node 6 Quality+Format produces sentiment score per ticket)
- **Resolution rate** (20%): % of tickets resolved by PARWA without human escalation
- **Time-to-resolution** (15%): trend vs. customer's historical baseline
- **Reopen rate** (10%): % of tickets reopened by customer after "resolved"
- **Product usage** (10%): pulled from customer's product analytics (via UCB integration to Segment/Amplitude/Mixpanel)

**Data flow:**
1. Jarvis SENSE ingests all 6 signals continuously (or nightly for usage data)
2. Jarvis EVALUATE computes weighted score per account, stores in `customer_health` table
3. Jarvis EVALUATE detects score drops >10 points in 7 days → flags for proactive outreach (see 19.3.4)
4. Dashboard queries `customer_health` table for display

**Dashboard UI:**
- **Customer Health page** with:
  - **Health matrix**: all accounts on a 0-100 color-coded grid (red <40, yellow 40-70, green >70)
  - **Trend chart**: per-account 90-day health trend
  - **Signal breakdown**: which signals are dragging the score down
  - **Drill-down**: click any account → see ticket history, sentiment trend, usage trend, last 5 Jarvis evaluations

**Backend requirements:**
- New table: `customer_health` (account_id, score, signal_breakdown_json, updated_at)
- New table: `health_signals` (per-signal raw values per account per day)
- New Jarvis EVALUATE job (hourly per tenant)
- New API routes: `GET /api/v1/health/accounts`, `GET /api/v1/health/accounts/:id`, `GET /api/v1/health/accounts/:id/trend`
- UCB connectors for Segment, Amplitude, Mixpanel (for usage signal)

**Positioning in pitch:** *"Your CSM maintains a customer health spreadsheet. PARWA computes it continuously from 6 live signals — and tells you which signal is dragging the score down. No spreadsheet updates, no quarterly review panic."*

#### 19.3.3 ADD: QBR / Report Generator (One-Click)

**What it does:** A single button — "Generate Quarterly Report" — that compiles everything Jarvis knows about a customer into a polished PDF executive summary. CSMs spend days on these; PARWA generates in 5 seconds.

**Why this matters:** QBR generation is one of the most-cited CSM time-sinks in job postings. It's also a high-leverage moment — the QBR is often where renewals are won or lost. Automating it removes busywork AND improves quality (Jarvis sees more than any human CSM could).

**Report contents (auto-compiled):**
1. **Executive summary** (1 paragraph, LLM-generated from ticket + health data)
2. **Ticket metrics** (volume, resolution rate, avg time-to-resolve, top 5 categories)
3. **SLA performance** (compliance %, breaches with root cause)
4. **Customer health trend** (chart + commentary)
5. **Sentiment trend** (chart + notable moments)
6. **Top resolved issues** (5 most impactful resolutions, with PARWA credit)
7. **Open risks** (Jarvis-flagged concerns going into next quarter)
8. **Recommendations** (LLM-generated next-quarter action items)
9. **ROI summary** (dollars saved this quarter vs. PARWA cost — pulled from ROI Calculator)

**Data flow:**
1. Admin clicks "Generate QBR" button on any account page
2. Backend pulls all relevant data from `tickets`, `sla_events`, `customer_health`, `roi_events` tables for the selected quarter
3. LLM generates executive summary + recommendations (single LLM call, ~2k tokens)
4. ReportLab renders PDF with charts (matplotlib PNGs embedded)
5. PDF saved to tenant's S3 bucket, signed URL returned to dashboard
6. User downloads PDF or schedules auto-send to customer

**Dashboard UI:**
- "Generate QBR" button on every account page
- QBR history list (last 12 reports per account)
- Optional: schedule auto-generation (e.g., generate first day of each quarter, email to admin)

**Backend requirements:**
- New endpoint: `POST /api/v1/reports/qbr` (input: account_id, quarter)
- New endpoint: `GET /api/v1/reports/qbr/:id/download`
- LLM call: GPT-4-class model, structured prompt with all data injected
- PDF generation via ReportLab (existing pattern from PDF skill)
- Charts via matplotlib (existing pattern)
- S3 storage for generated PDFs

**Positioning in pitch:** *"Your CSM spends 3 days per quarter per account building QBR decks. PARWA generates them in 5 seconds with more data than any human could compile. Your CSM reviews, edits, and presents — the busywork is gone."*

#### 19.3.4 ADD: Proactive Outreach Suggestions (Jarvis-Initiated)

**What it does:** Jarvis continuously analyzes every account for "reach out" signals and surfaces specific, actionable suggestions to the admin: "Customer X hasn't opened a ticket in 60 days but their product usage dropped 40% — reach out." CSMs do this from gut feel today; PARWA does it from data.

**Why this matters:** This is the proactive-retention muscle that justifies the CSM salary. Without it, PARWA is reactive (resolves tickets well) but not proactive (prevents churn). Adding this closes the loop and makes the CSM replacement airtight.

**Signal categories Jarvis watches for:**
- **Usage drop**: product usage down >30% in 30 days (via UCB → Segment/Amplitude)
- **Silence anomaly**: no tickets in 60+ days when historical avg is 5+/month (could mean churned silently or gave up)
- **Sentiment decline**: rolling 30-day sentiment down >15 points vs. previous 30 days
- **Ticket spike**: 2x normal ticket volume in 7 days (frustration building)
- **Reopen spike**: reopen rate >20% in last 14 days (resolutions not sticking)
- **SLA breach cluster**: 2+ SLA breaches in 30 days for same account
- **Admin policy change**: admin updated a policy that affects this account (Jarvis detects via Policy Change Detection — see Section 10)
- **Billing event**: failed payment, downgrade, or renewal approaching (via UCB → Stripe/billing system)

**How Jarvis surfaces suggestions:**
- New dashboard widget: **Outreach Suggestions** (top of main dashboard, can't miss it)
- Each suggestion card shows: account name, signal type, severity (low/med/high), suggested action (LLM-generated email draft included), "Send" or "Dismiss" buttons
- Admin can: send the drafted email as-is, edit then send, dismiss (with reason — feeds back into Jarvis learning), or assign to a human teammate
- All outreach actions logged in `outreach_log` table for audit

**Data flow:**
1. Jarvis EVALUATE runs nightly per tenant, scans every account for all 8 signal categories
2. New signals → inserted into `outreach_suggestions` table
3. Jarvis generates suggested email draft via LLM (single call per suggestion, ~500 tokens)
4. Dashboard polls `outreach_suggestions` table on page load + every 60s
5. Admin action updates suggestion status → feeds back into AI Wiki Section B (admin behavior)

**Dashboard UI:**
- **Outreach Queue** page (full list, filterable by severity, signal type, account)
- **Outreach widget** on main dashboard (top 3 highest-severity, click to expand)
- Per-suggestion card: account, signal, suggested action, draft email, action buttons
- **History view**: all past suggestions with outcome (sent, dismissed, converted to ticket, etc.)

**Backend requirements:**
- New table: `outreach_suggestions` (account_id, signal_type, severity, draft_email, status, created_at, resolved_at)
- New table: `outreach_log` (every send/dismiss/assign action)
- New Jarvis EVALUATE job (nightly per tenant)
- New API routes: `GET /api/v1/outreach/suggestions`, `POST /api/v1/outreach/suggestions/:id/send`, `POST /api/v1/outreach/suggestions/:id/dismiss`

**Positioning in pitch:** *"Your CSM's gut says 'I should check in on Customer X.' PARWA's data says 'Customer X's usage dropped 40%, no tickets in 60 days, last sentiment score was 45/100 — here's a draft email, want me to send it?' That's not a CSM replacement. That's a CSM upgrade."*

#### 19.3.5 ADD: ROI Calculator (Wire Already-Coded UI to Live Data)

**Current state:** UI is already coded. Currently shows static/demo numbers. Needs to be wired to live backend data so the numbers reflect the actual tenant's real savings.

**What it does:** Every time the admin logs in, the dashboard header shows a live counter: "PARWA has saved you $X this month by replacing Y hours of CSM/CSR work." Click to expand → full ROI breakdown page.

**Why this matters:** This is the single highest-converting sales asset in the entire platform. Every login reminds the buyer why they're paying for PARWA. It makes the value visceral — not abstract, not promised, but realized and counted.

**What "savings" are computed (per tenant, per month):**

| Cost Category | Computation | Source Data |
|---------------|-------------|-------------|
| Tier 1 Support hours saved | (Tickets auto-resolved by PARWA) × (avg 12 min per ticket × $23/hr loaded Tier 1 cost) | `tickets` table where `resolved_by='parwa'` and `complexity='tier1'` |
| CSR hours saved | (Tickets auto-resolved) × (avg 8 min × $20/hr) | `tickets` table where `resolved_by='parwa'` and `complexity='basic'` |
| CSM hours saved | (Outreach suggestions auto-generated) × (avg 20 min × $45/hr) + (QBRs auto-generated × 24 hrs × $45/hr) | `outreach_suggestions` + `reports` tables |
| SLA breach cost avoided | (Breaches prevented by Jarvis pre-alert) × (avg breach penalty $500) | `sla_events` where `prevented=true` |
| Onboarding hours saved | (Customers onboarded via 6-step flow) × (avg 8 hrs × $45/hr) | `onboarding_events` table |

**Total monthly savings** = sum of all 5 categories, minus PARWA's monthly cost (transparently shown).

**Dashboard UI:**
- **Live counter in top nav** (next to notifications bell): "Saved $X this month" — updates on every page load
- **ROI page** (`/dashboard/roi`): 
  - Big number: total saved YTD
  - Breakdown chart: 5 cost categories as stacked bar chart, monthly
  - Trend line: savings over last 12 months
  - Comparison: "PARWA cost: $X/mo. Savings: $Y/mo. Net ROI: Zx"
  - "Share with my CFO" button → generates PDF executive summary of ROI

**Backend requirements:**
- New table: `roi_events` (every savings-eligible event logged with $ value)
- New materialized view: `roi_monthly` (rolled-up monthly savings per tenant)
- New API routes: `GET /api/v1/roi/summary`, `GET /api/v1/roi/breakdown`, `GET /api/v1/roi/trend`, `POST /api/v1/roi/cfo-report`
- Event hooks: every ticket resolution, every outreach suggestion, every QBR generation, every SLA prevention → insert row into `roi_events`

**Action items (since UI is coded):**
1. Identify the existing ROI Calculator component in the dashboard
2. Replace static/demo data with API calls to `/api/v1/roi/*`
3. Implement the 5 backend event hooks to populate `roi_events`
4. Build the materialized view for monthly rollup
5. Test with real tenant data (must show non-zero savings within first 24 hours of tenant using PARWA)

**Positioning in pitch:** *"Every time your CFO logs in, the first thing they see is how much money PARWA saved this month. Not 'tickets resolved' — actual dollars. That's the conversation you want to have with your CFO every month, not the 'how do we justify the AI tool spend' conversation."*

### 19.4 Dashboard Wiring Tasks — Fix the Broken Pages

Beyond the additions above, the following existing pages must be wired to real backend data before production. These were identified in the dashboard audit.

#### 19.4.1 Tickets Page → Wire to `/api/v1/tickets/*`

**Current:** Uses localStorage only. Tickets created in dashboard never reach backend.

**Required:**
- Replace localStorage reads with `GET /api/v1/tickets` (with pagination, filtering)
- Replace localStorage writes with `POST /api/v1/tickets` (create), `PATCH /api/v1/tickets/:id` (update)
- Real-time updates via Socket.io (already in stack) — listen for `ticket:created`, `ticket:resolved`, `ticket:escalated` events
- Show ticket count badge in sidebar with live updates

#### 19.4.2 Billing Page → Wire to `/api/billing/*`

**Current:** All hardcoded numbers.

**Required:**
- Pull current plan from `GET /api/billing/subscription`
- Pull usage this cycle from `GET /api/billing/usage`
- Pull invoice history from `GET /api/billing/invoices`
- Upgrade/downgrade flow via `POST /api/billing/subscription/change`
- Paddle integration already exists in backend — ensure webhook events update dashboard in real-time

#### 19.4.3 Notifications Page → Wire to `/api/v1/notifications`

**Current:** Mock array of fake notifications.

**Required:**
- Pull from `GET /api/v1/notifications` (with filter for unread)
- Mark as read via `PATCH /api/v1/notifications/:id/read`
- Real-time push via Socket.io — `notification:new` event
- Notification types: SLA at-risk, SLA breached, outreach suggestion, QBR ready, policy change detected, ROI milestone reached

#### 19.4.4 Profile Page → Wire to `/api/v1/auth/me`

**Current:** Reads stale localStorage.

**Required:**
- On page load, fetch fresh profile from `GET /api/v1/auth/me`
- Allow update via `PATCH /api/v1/auth/me` (name, avatar, preferences)
- Show last login, sessions list, API key regeneration (with admin-only permission check)
- 2FA setup flow if not yet enabled

#### 19.4.5 Integrations Page → Wire to UCB Connector Status

**Current:** Shows static list of integrations with no live status.

**Required:**
- Pull connected integrations from `GET /api/v1/integrations`
- Per-integration health status (last sync time, errors, credentials valid)
- Add/remove integration flow (OAuth for SaaS, API key for others)
- Test integration button (sends a ping, verifies 200 response)

### 19.5 Dashboard Cleanup — Delete Dead Code

~30 dead code files identified in audit. These must be deleted before production to reduce maintenance surface and avoid confusing future developers.

**Cleanup process:**
1. Run dead code analysis: `npx ts-prune` to find unused exports
2. Cross-reference with file dependency tree (Next.js build output)
3. Manually verify each flagged file is truly unused (grep for imports)
4. Delete in batches: components → hooks → stores → utils → types
5. Run full test suite after each batch
6. Update sidebar nav, route definitions, and any dynamic imports

**Expected outcome:** ~30 files deleted, bundle size reduced ~15-20%, build time reduced ~30%.

### 19.6 Final Dashboard Information Architecture

After all removals and additions, the production dashboard sidebar should be:

```
DASHBOARD
├── Overview (main dashboard with ROI counter, outreach widget, SLA widget)
├── Tickets (live ticket queue, real-time)
├── Customer Health (health score matrix + trends)
├── SLA Tracking (at-risk, breaches, compliance trend)
├── Outreach Suggestions (Jarvis-proactive queue)
├── Reports (QBR generator, ROI report, history)

VARIANT
├── Variants (list, create, manage)
├── Knowledge Sources (Section C file manager only)

INTEGRATIONS
├── Connectors (UCB status, add/remove)
├── Notifications (Jarvis alerts, real-time)

ACCOUNT
├── Billing (real subscription, usage, invoices)
├── Profile (fresh from /auth/me)
├── Settings (tenant preferences, SLA policy config)
├── API Keys (admin-only, generate/revoke)
```

**What is NOT in the sidebar:**
- ❌ Agent Builder (removed — see 19.2.1)
- ❌ Pipeline visualization (removed — see 19.2.2)
- ❌ AI Wiki viewer (not built — see 19.2.3)
- ❌ Shadow Mode (removed — see 19.2.4)

### 19.7 Dashboard Production Readiness Checklist

Before declaring the dashboard production-ready, every item below must be verified:

**Removals complete:**
- [ ] Agent Builder page deleted, no remaining references in codebase
- [ ] Pipeline visualization page deleted, replaced with status chip in top nav
- [ ] AI Wiki viewer NOT built (only Knowledge Sources file manager built)
- [ ] Shadow Mode nav entry removed
- [ ] All mock/hardcoded data removed from Billing, Notifications, Profile

**Additions complete:**
- [ ] SLA Tracking page live, wired to Jarvis SENSE/EVALUATE/NOTIFY
- [ ] Customer Health page live, showing real scores from `customer_health` table
- [ ] QBR Generator page live, producing downloadable PDFs
- [ ] Outreach Suggestions page live, Jarvis generating nightly suggestions
- [ ] ROI Calculator wired to live `roi_events` data (counter in top nav showing real $)
- [ ] ROI "Share with CFO" PDF report generator working

**Wiring complete:**
- [ ] Tickets page reads/writes via `/api/v1/tickets/*`, real-time via Socket.io
- [ ] Billing page reads from `/api/billing/*`, Paddle webhooks updating in real-time
- [ ] Notifications page reads from `/api/v1/notifications`, real-time push working
- [ ] Profile page fetches fresh from `/api/v1/auth/me` on every load
- [ ] Integrations page shows live UCB connector status with test button

**Cleanup complete:**
- [ ] `npx ts-prune` run, all unused exports removed
- [ ] ~30 dead files deleted (verify with grep before deletion)
- [ ] Bundle size reduced (measure before/after)
- [ ] Build time reduced (measure before/after)
- [ ] Full E2E test suite passes on cleaned codebase

**Positioning verification:**
- [ ] No "make your team more productive" language anywhere in dashboard
- [ ] ROI counter visible on every page (top nav)
- [ ] Every dashboard widget ties back to a dollar savings or a headcount cost
- [ ] Headcount replacement language consistent across dashboard, onboarding, and docs

---

## Appendix A: Node-by-Node LLM Call Summary (PARWA)

| Node | Name | LLM Calls (avg) | LLM Techniques | Non-LLM Techniques |
|------|------|-----------------|----------------|---------------------|
| 1 | Ingest + Classify | 1 | UoT | SmartRouter, DynamicContext, MetaLearner |
| 2 | Smart Route | 0 | — | Variant Registry, Quota Tracker, Capability Matrix |
| 3 | Knowledge + AI Wiki | 3-4 | CLARA, HyDE, Multi-Query, Step-Back | ContextualCompression, DynamicContext |
| 4 | Reasoning Engine | 3-4 | CoT, ToT, Least-to-Most, Reverse Thinking, UoT, GST | GSD, MAKER, ZeroShotValidator, ThoT, FederatedReasoning, MetaLearner |
| 5 | Act + Verify | 1-2 | ReAct, Reverse Thinking | MAKER, GSD, ZeroShotValidator, Rule-based |
| 6 | Quality + Format | 2 | Reflexion, CRP | ZeroShotValidator, GSD, ThoT, ContextualCompression, FederatedReasoning |
| 7 | Simple/Medium | 0 | — | ALL 11 non-LLM techniques |
| 8 | Super Node | 5-6 | Self-Consistency, ToT, Reverse Thinking, Reflexion, CRP, CoT | ALL 11 non-LLM techniques |

## Appendix B: Jarvis Node LLM Call Summary

| Node | Name | LLM Calls (avg) | LLM Techniques | Non-LLM Techniques |
|------|------|-----------------|----------------|---------------------|
| SENSE | Observe | 0 | — | DynamicContext, SmartRouter, ZeroShotValidator |
| EVALUATE | Think | 1-2 | CoT, CLARA, Step-Back, Reflexion | GSD, MAKER, ThoT, FederatedReasoning, ZeroShotValidator, MetaLearner, DynamicContext |
| NOTIFY | Act + Verify | 1-2 | CoT, Step-Back, Reflexion | DynamicContext, MetaLearner, ContextualCompression, TurboCompress, AdaptiveBudget |

## Appendix C: Complete System Data Flow

```
1. CUSTOMER sends email/sms/chat/call
       │
2. UCB normalizes → creates ticket with tenant_id
       │
3. NODE 1 (Ingest+Classify) — Pattern match, intent parse, key extract
       │
4. NODE 2 (Smart Route) — Check tier, quota, efficiency → pick path
       │
5. NODE 3 (Knowledge Fetch + AI Wiki) — RAG search WITHIN tenant scope
       │                                    Fetch CRM data via UCB
       │                                    Policy sync check (Section C)
       │
6. SPLIT based on complexity
       │
   ┌───┴──────────────────────────┐
   │                              │
   Simple/Medium                Complex
   │                              │
7a. NODE 7 (Non-LLM Resolver)  7b. NODE 4 (Reasoning Engine)
    • Pattern match                • CoT, ToT, ReAct
    • Rule engine                  • Deep analysis
    • Template fill                • Multiple technique combo
    │                              │
    │                              ▼
    │                           8. NODE 5 (Act + Verify)
    │                              • Execute via UCB (reply email/SMS/etc)
    │                              • Verify result
    │                              │
    │                              ▼
    │                           9. NODE 6 (Quality + Format)
    │                              • Accuracy > 90%?
    │                              • Tone check
    │                              • Policy compliance (Section C)
    │                              │
    │                        ┌─────┴─────┐
    │                        │ PASS      │ FAIL (loop count < 2)
    │                        │           │ → Back to Node 4
    │                        │           │
    │                        │           │ FAIL (loop count = 2)
    │                        │           │ → Node 8 (Super Node)
    │                        ▼           ▼
   ┌──────────────────────────────────────────┐
   │              OUTCOME                      │
   │                                           │
   │  ✅ Resolved → Send reply via UCB         │
   │             → Update AI Wiki Section A    │
   │             → Deduct from quota           │
   │                                           │
   │  ❌ Stuck   → Jarvis SENSE detects        │
   │             → Notification Center alerts  │
   │             → Admin sees unique key       │
   │             → Admin can ask Jarvis        │
   │             → Admin gives manual command  │
   └──────────────────────────────────────────┘
```

## Appendix D: Timeline Summary

| Phase | Name | Days | Key Deliverable |
|-------|------|------|----------------|
| 1 | Foundation | 1-4 | 8-node pipeline + key access + tenant isolation |
| 2 | Intelligence | 5-8 | All 14 LLM techniques active |
| 3 | Optimization | 9-11 | Node 7 non-LLM path working |
| 4 | Business Logic | 12-14 | Variants + quotas + restrictions |
| 5 | Quality & Safety | 15-17 | Quality loop + Super Node + MAKER safety |
| 6 | AI Wiki | 18-20 | 3-section Wiki + learning loop |
| 7 | Integration Layer | 21-24 | UCB + Email/SMS/CRM/Chat adapters |
| 8 | Jarvis | 25-28 | 3-node Jarvis + Notification Center |
| 9 | Onboarding | 29-32 | 6-step wizard + key delivery + dashboard wiring |
| 10 | Integration Testing | 33-36 | End-to-end testing, multi-tenant verification |
| 11 | Production Hardening | 37-40 | Monitoring, security, load testing, dashboard polish |

**Total**: ~40 days from foundation to production-ready

---

*Document generated: 2026-06-16*
*Architecture version: Ultimate v1.0*
*Systems: PARWA 8-Node + Jarvis 3-Node + Notification Center + AI Wiki + UCB + Key Access + Onboarding*
*Status: Complete architecture, ready for implementation*
