# PARWA Tier 2: Custom Agent Builder — Complete Production Roadmap

**Status:** Approved Architecture  
**Date:** 2026-07-01  
**Estimated Build Time:** 22 Days (3 Weeks)

---

## 1. Executive Summary

This document outlines the complete architecture and build plan for PARWA's Tier 2 Custom Agent Builder. 

PARWA's agents are strictly **Customer Care Agents**. They exist to resolve customer support tickets, answer product questions, and automate onboarding. They do not write code or marketing copy. 

By enforcing this strict scope, every agent created—whether pre-built or custom—fits perfectly into our existing 8-node ticket pipeline at Node 2. The Builder itself is an AI agent (using Llama 3.1 8B + our 25 reasoning techniques) that chats with the user to design the perfect agent config in seconds.

---

## 2. Core Architectural Decisions (Locked)

### 2.1 The "Customer Care Only" Rule
The Builder Agent will refuse any request that falls outside customer support, success, and onboarding. This ensures every agent created attaches cleanly to the 8-node pipeline.

### 2.2 The 25 Techniques Rule (No Artificial Limits)
**All agents use ALL 25 reasoning techniques.** We do not artificially limit techniques based on tier. The variant tier (`mini_parwa`, `parwa`, `parwa_high`) dictates **which LLM models** execute the techniques and **what custom features** are allowed, not the intelligence of the routing.

### 2.3 The 4-Model Tiers (11 Models Total)
Our pipeline uses 4 tiers with automatic failover:
- **LIGHT (90% of calls):** Cerebras Llama 3.1 8B → Groq Llama 3.1 8B → Google Gemma 3 27B
- **MEDIUM (8%):** Google Gemini Flash-Lite → Gemini 2.5 Flash → Groq Llama 3.3 70B
- **HEAVY (2%):** Groq GPT-OSS 120B → Cerebras GPT-OSS 120B → Groq Llama 4 Scout
- **GUARDRAIL:** Groq Llama Guard 4 12B

### 2.4 The 4-Stage Builder Pipeline
The Builder Agent uses a 4-stage mini-pipeline to create agents via chat. It uses 34 LLM calls across all 4 model tiers to guarantee ~97% config accuracy.
1. **EXPLORE:** Understand the user's real intent (LIGHT models).
2. **DESIGN:** Generate 3 candidate configs, synthesize 1 (MEDIUM models).
3. **VERIFY:** Vote, self-reflect, and safety check (LIGHT + MEDIUM + GUARDRAIL).
4. **REFINE:** Learn from gaps, regenerate using Reflexion loops (HEAVY model).

---

## 3. Pricing & Access Strategy (Locked)

Agent features are gated by the tenant's subscription tier:

| Variant Tier | Agent Capability | Cost | Business Logic |
|---|---|---|---|
| **mini_parwa** | ❌ No agents (generic AI only) | Base | Forces upgrade if they want specialization. |
| **parwa** | ✅ Pre-built agents only (free) | Base | Zero LLM cost to us. Huge value to user. Makes `parwa` the no-brainer tier. |
| **parwa_high** | ✅✅ Custom agents ($5/mo each) | Base + $5/agent | Power users pay for customization. High margin. |

**ROI Logic:** A human agent costs $4,000/month. We charge $5/month for a custom AI agent. The customer's ROI is insane, ensuring zero churn.

---

## 4. Infrastructure Audit (What We Have vs What We Need)

### Already Have (70% infrastructure exists):
- ✅ Tool registry in Node 5 (`app/core/react_tools/`)
- ✅ Credential storage (Integration table with `credentials_encrypted`)
- ✅ Vector store with pgvector (`PgVectorStore`)
- ✅ Celery Beat scheduler (`app/tasks/celery_app.py`)
- ✅ Drag-drop library (`@dnd-kit` installed)
- ✅ `call_lifecycle.py` has a `GUARDRAILS_CHECK` stage (placeholder)
- ✅ Multi-model `smart_router.py` (needs wiring to `llm_client.py`)
- ✅ Conversation session models (JarvisSession, ChatWidgetSession)

### Need to Build:
- ❌ Wire `smart_router` into `llm_client.py` (Phase 0)
- ❌ Custom action config UI + DB table (Phase 1)
- ❌ Web crawler for knowledge ingestion (Phase 2)
- ❌ Guardrail rule engine + DB table (Phase 3)
- ❌ Topic change detector + context transfer (Phase 4)
- ❌ 4-stage Builder pipeline + chat UI (Phase 5)
- ❌ Dashboard integration (Phase 6)

---

## 5. Pipeline Attachment (Where Agents Live)

Because all agents are Customer Care Agents, they attach to the 8-node pipeline at **Node 2**.

```
Ticket arrives: "I want a refund for order #12345"
  ↓
[Node 1] Ingest + Classify (category = billing_payments)
  ↓
[Node 2] Smart Route
  ├── Picks Variant: parwa
  ├── Picks Agent: "Refund Specialist" (matches category)
  └── Injects Agent Config (personality, knowledge, tools) into state
  ↓
[Node 3] Knowledge Fetch
  ├── RAG: Reads ONLY docs attached to "Refund Specialist"
  └── CLARA: Is this knowledge sufficient?
  ↓
[Phase 3 PRE-CHECK] Guardrail: $600 > $500 limit → flag
  ↓
[Node 4] Reasoning Engine (Uses all 25 techniques)
  ├── CRP: "Act as Refund Specialist (empathetic, precise)"
  ├── CoT: Reason through refund policy
  └── Draft Response
  ↓
[Phase 3 POST-CHECK] Llama Guard: Scan response for safety
  ↓
[Node 5] Act + Verify (ReAct)
  └── Calls custom API: POST https://api.store.com/refund (Phase 1)
  ↓
[Node 6] Quality Check + Deliver + CRM Push
  ↓
[Node 7] Resolve
```

---

## 6. The 25 Techniques Map (How They Are Used)

Every agent uses all 25 techniques. Here is how they map to the 4-Group Ensemble architecture:

### Group 1: EXPLORE (Node 1)
- **Intent Classification:** What does user want?
- **Sentiment Analysis:** Is user angry?
- **Theory of Mind:** What's the REAL intent?
- **Step-Back:** What's the bigger context?
- **Thread of Thought:** Link to previous messages
- **PII Redaction:** Remove sensitive data early

### Group 2: REASON (Node 4)
- **GSD:** Decompose into sub-tasks
- **MAd:** Break each sub-task further
- **CoT:** Reason step by step
- **CRP:** Generate candidate #1 as the agent persona
- **Reverse Thinking:** Generate candidate #2 backwards
- **Draft Response:** Generate candidate #3
- **RAG:** Pull from agent's specific knowledge
- **CLARA:** Gatekeep: do we have enough info?
- **Federated Reasoning:** Combine 3 candidates into 1

### Group 3: VERIFY (Node 6)
- **Theory of Mind:** Does config serve user's REAL intent?
- **Reverse Thinking:** What bad outcomes could this cause?
- **Step-Back:** Does whole config make sense?
- **Fake Voting:** 3 voters rate the config
- **Consensus Analysis:** Find what voters agree on
- **Self-Reflection:** Did I include everything?
- **Maker:** Is reasoning chain valid?
- **Guardrail Check:** Llama Guard safety scan
- **ReAct:** "Do I need to ask user more?"

### Group 4: REFINE (Node 4/6 Loop)
- **Reflexion:** Learn from verify failure, regenerate
- **Quality Loop:** Score 0-1, regen if < 0.8
- **Self-Reflection:** Reflect on refined config
- **Meta-Learner:** Adjust based on past agent creations
- **Theory of Mind:** Will user be happy with this?
- **CoT:** Walk through final config step by step
- **Thread of Thought:** Ensure consistency across all parts
- **Escalate to Human:** If Builder can't make good config

---

## 7. Build Phases (22 Days)

### Phase 0: Wire Smart Router (1 Day)
**Goal:** Pipeline uses all 11 models with failover.
- Modify `llm_client.py` to call `smart_router.route()` instead of hardcoded NVIDIA
- Add `tier` parameter to `llm_call()`
- Failover: if SmartRouter fails, fall back to NVIDIA direct
- **Verify:** Pipeline tests still pass, but now use Cerebras/Groq/Google/Guard models

### Phase 0.5: Expose Pre-Built Agents + Semantic Routing (1 Day)
**Goal:** Users on `parwa` tier can install 20 industry templates instantly. Node 1 supports semantic description matching.
- Take the 20 industry variants from `02_industry_variants.json`
- Add `GET /api/v1/agents/templates` endpoint
- Add `is_template: Boolean` to Agent model
- UI: "Instant Setup" section in Builder showing pre-built agents
- **NEW: Semantic Description Matching in Node 1:**
  - When standard category classification doesn't match any agent, Node 1 falls back to semantic matching
  - Generate embedding of ticket query → compare against agent descriptions (embeddings)
  - If similarity > 0.85 → route to that agent
  - This is Decagon's approach — we combine it with our category routing for best of both worlds
- **Verify:** User clicks "Order Management" → agent created instantly (0 LLM cost)
- **Verify:** Ticket with no category match still routes to right agent via semantic matching

### Phase 1: Custom API Actions (3 Days)
**Goal:** Agents can call tenant's own APIs.
- New DB table: `custom_actions`
- New API: `POST/GET/PUT/DELETE /api/v1/agents/{id}/actions`
- SSRF protection (block localhost, private IPs)
- Rate limiter (max 10 calls/action/minute)
- Extend Node 5's ReAct tool registry
- UI: "Custom Actions" tab in agent detail page

### Phase 2: Auto Knowledge Ingestion (3 Days)
**Goal:** Paste a URL → system crawls + indexes all articles.
- New DB table: `knowledge_sources`
- Web crawler (fetch pages, extract text, follow links)
- Chunking logic (1000-char chunks with 200-char overlap)
- Embedding generator → store in `document_chunks`
- New API: `POST /api/v1/knowledge/sources`
- Celery Beat task: re-crawl every 24h
- UI: "Connect Help Center" button on Knowledge page

### Phase 3: Hard Guardrails (3 Days)
**Goal:** Rules that CANNOT be broken.
- New DB table: `guardrails`
- New API: `POST/GET/PUT/DELETE /api/v1/agents/{id}/guardrails`
- Pre-check function (before Node 4): block dangerous requests
- Post-check function (after Node 4): scan response, regenerate if violated
- Rule types: `max_refund_amount`, `blocked_keywords`, `required_escalation_triggers`
- UI: "Guardrails" tab in agent detail page (simple form)

### Phase 4: Multi-Agent Handoff (4 Days)
**Goal:** Agent transfers mid-conversation when topic changes.
- Add `conversation_history` to `PipelineV2State`
- Topic change detector (LLM call: "Did this message change topic?")
- Agent switch logic (re-run Node 2)
- Context transfer (pass history to new agent)
- Handoff notification ("Transferring you to [Agent Name]...")
- UI: Handoff indicator in ticket detail view

### Phase 5: Builder Agent (5 Days)
**Goal:** User creates agents by chatting, not filling forms. Builder decides attachment method automatically.
- New directory: `backend/app/core/builder_agent/`
- `builder_pipeline.py` (runs 4 stages: Explore → Design → Verify → Refine)
- `builder_llm.py` (calls smart_router with correct tier per stage)
- `builder_state.py` (tracks chat history + collected config)
- New API: `POST /api/v1/agents/builder/chat` (multi-turn)
- New API: `POST /api/v1/agents/builder/finalize` (create agent)
- Builder auto-suggests: knowledge sources, guardrails, custom actions
- Builder enforces "Customer Care Only" rule
- **NEW: AI Suggests Attachment Method (Builder decides):**
  - Method 1: Map to existing category (billing_payments, shipping_delivery, etc.)
  - Method 2: Create custom category + trigger keywords (Builder generates keywords automatically)
  - Method 3: Keyword trigger (agent activates when specific words appear in ticket)
  - Builder picks the best method based on user's description + confirms with user
- **NEW: Custom Categories + Keywords:**
  - New DB table: `custom_categories` (id, company_id, name, keywords JSON)
  - Builder creates custom categories automatically during chat
  - Node 1 checks custom categories + keywords during classification
  - Node 2 routes to agent based on custom category match
- UI: Chat interface (left = chat, right = live config preview)
- UI: "Approve & Create" button
- UI: Test playground after creation
- **Verify:** Builder asks "How should tickets reach this agent?" and suggests best method
- **Verify:** Custom categories created by Builder appear in Node 1 classification

### Phase 6: Dashboard Integration (3 Days)
**Goal:** Everything wired to dashboard, production-ready.
- New API: `GET /api/v1/agents/{id}/metrics`
- Update ticket response to include `agent_name`
- UI: Agents list page with metrics
- UI: Agent detail page (tabs: Config, Actions, Guardrails, Knowledge, Metrics)
- UI: "Agent Activity" widget on main dashboard
- UI: Ticket detail shows which agent handled it + handoffs
- UI: Variant distribution chart on dashboard

---

## 8. Final Verification Checklist

Before pushing to main, verify:
- [ ] `tsc --noEmit`: 0 errors
- [ ] `next build`: Compiles successfully
- [ ] Pipeline uses Smart Router (all 4 tiers reachable)
- [ ] Pre-built agents install instantly (0 LLM cost)
- [ ] Custom agent creation uses 34 LLM calls across 4 stages
- [ ] Agents attach to Node 2 and inject config into Node 3/4/5
- [ ] Guardrails block dangerous requests before Node 4
- [ ] Custom API actions execute via Node 5 ReAct loop
- [ ] Auto knowledge ingestion crawls URLs and stores embeddings
- [ ] Multi-agent handoff re-routes mid-conversation
- [ ] Builder enforces "Customer Care Only" scope
- [ ] Pricing gates: `mini_parwa` (no agents), `parwa` (pre-built), `parwa_high` (custom $5/mo)
- [ ] **Semantic description matching works (Node 1 falls back to embeddings when no category match)**
- [ ] **Builder suggests attachment method (existing category, custom category, or keyword trigger)**
- [ ] **Custom categories + keywords created by Builder appear in Node 1 classification**

---

## 9. Competitive Feature Matrix (Verified)

All features from the rival comparison table are now included in the roadmap:

| Feature | PARWA (planned) | Best Rival | Phase |
|---|---|---|---|
| Existing category mapping | ✅ | Sierra, Zendesk, Salesforce | Phase 0.5 |
| Custom categories + keywords | ✅ (Builder creates automatically) | Zendesk (manual), Salesforce (manual) | Phase 5 |
| Semantic description matching | ✅ (via Node 1 classification) | Decagon (only method) | Phase 0.5 |
| AI suggests attachment method | ✅ (Builder decides) | ❌ No rival does this | Phase 5 |
| Chat-based builder | ✅ (34 LLM calls, 25 techniques) | Sierra (basic Ghostwriter) | Phase 5 |
| 11 models with failover | ✅ | ❌ (rivals use 1-3 models) | Phase 0 |
| 25 reasoning techniques | ✅ | ❌ (rivals don't disclose techniques) | All phases |
