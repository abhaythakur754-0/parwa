# PARWA — Architecture Design Document (ADD)

**Document Version:** 1.0  
**Date:** May 5, 2026  
**SDLC Phase:** Phase 2 — Architecture Design  
**Strategy:** Hybrid Agile (10 Sprints, 20 Weeks)  
**Architecture Style:** Multi-Agent Agentic System with LangGraph Orchestration  
**Companion Documents:** SRS v2.1, DMD v6.0, Building Codes v1

---

## Table of Contents

1. Introduction & Architecture Principles
2. High-Level System Architecture
3. Multi-Agent Architecture & LangGraph Orchestration
4. Agent Roster & Specifications
5. LangGraph State Graph & Flow Definitions
6. Framework Pipeline Architecture (Smart Router → Technique Router → MAKER → Control → Guardrails)
7. Variant Tier Architecture (Mini / Pro / High)
8. Jarvis Architecture (Command Center + Onboarding)
9. Channel Architecture (Chat / Email / SMS / Voice / Video)
10. Data Architecture (90+ Tables, Schema Design, Vector Store)
11. API Architecture (150+ Endpoints, REST + WebSocket + MCP)
12. Security Architecture (PII, Encryption, Compliance, Audit)
13. Agent Lightning & Training Pipeline Architecture
14. Deployment Architecture (Docker Compose, CI/CD, Environments)
15. Infrastructure Architecture (Supabase, Redis, Celery, S3)
16. Monitoring & Observability Architecture
17. Scalability & Performance Architecture
18. Technology Stack & Rationale
19. Appendix A — Building Codes Mapping
20. Appendix B — External Service Integration Matrix

---

## 1. Introduction & Architecture Principles

### 1.1 Purpose

This Architecture Design Document (ADD) defines the complete technical blueprint for PARWA — a SaaS AI customer care workforce system. PARWA is not a chatbot or an AI tool; it is a multi-agent agentic system where specialized AI agents work together under LangGraph orchestration to handle customer care operations across Chat, Email, SMS, Voice, and Video channels. Every architectural decision in this document is driven by the SRS v2.1 requirements and the 14 Building Codes (BC-001 through BC-014).

### 1.2 Architecture Style — Agentic Multi-Agent System

PARWA adopts a **Multi-Agent Agentic Architecture** orchestrated by **LangGraph**. In this model, the system is composed of specialized agents (each a self-contained unit with its own system prompt, tools, model tier, and technique configuration) that collaborate through a shared state graph. LangGraph manages the flow of execution, conditional routing, human-in-the-loop interruptions, and state persistence across the entire customer request lifecycle.

**Why Multi-Agent + LangGraph (not a monolithic LLM call):**

| Reason | Explanation |
|--------|-------------|
| Error Isolation | If the Refund Agent has a bug, the FAQ Agent still works. Debug the broken agent independently without affecting the rest of the system |
| Independent Training | Agent Lightning trains each agent type separately. The Refund Agent improves at refunds without degrading the Technical Agent |
| Independent Scaling | Voice Agent needs more compute? Scale just that agent. FAQ Agent handles 80% of traffic? Scale it up without touching others |
| Variant Tier Gating | Each agent has a `min_tier` property. Voice Agent = "pro", Video Agent = "high". Simple decorator enforcement |
| Human-in-the-Loop | LangGraph supports `interrupt_before` — the Control System node can pause, wait for manager approval, then resume the graph |
| Testability | Each agent can be unit tested independently with mock inputs and expected state transitions |
| Observability | Jarvis Terminal shows exactly which node is executing: "ROUTER → REFUND_AGENT → MAKER → WAITING_APPROVAL" |
| State Persistence | If a node fails mid-execution, LangGraph checkpoints allow resuming from the last successful state |

### 1.3 Core Architecture Principles

**P-01: Agents Communicate Through State, Not Direct Calls**

Agents NEVER call other agents directly. They read from and write to the shared `ParwaGraphState`. LangGraph reads the state and routes to the next node. This eliminates coupling — any agent can be replaced, upgraded, or removed without affecting others.

```
❌ BAD:  RefundAgent.call(TechnicalAgent, data)
✅ GOOD: RefundAgent → writes to state → LangGraph routes → TechnicalAgent reads from state
```

**P-02: Safety Nodes Are Independent Gates in the Graph**

MAKER Validator, Control System, and Guardrails are NOT libraries called by agents — they are independent nodes in the LangGraph graph. This means they execute regardless of which domain agent produced the output, and they cannot be bypassed or skipped by any agent.

**P-03: Every Request Follows the Same Pipeline**

Whether a customer sends a chat message, email, SMS, or makes a voice call — the request enters the same LangGraph pipeline. Channel Adapters normalize the input, but the processing pipeline is identical. This ensures consistent safety, quality, and auditability.

**P-04: Variant Tier Gates at the Agent Level**

Each agent declares its minimum variant tier. The LangGraph Router Node checks the tenant's tier before routing to any agent. If the tier doesn't match, the request is routed to a lower-tier alternative or returns an upgrade prompt. This is enforced at the orchestration layer, not sprinkled throughout business logic.

**P-05: Hard-Coded Rules Are Immutable**

Building Code BC-007 specifies that certain values (50-mistake training threshold, Money Rule, VIP Rule) are hard-coded in source code — NOT configurable via database, environment variable, or admin override. CI must fail if these values are modified. The architecture respects this by placing these checks in dedicated, protected nodes.

**P-06: State in Redis, Truth in PostgreSQL**

Redis is the fast, primary store for GSD state, sessions, and caching. PostgreSQL is the source of truth for all persistent data. Every Redis write has a corresponding PostgreSQL write (async via Celery). If Redis crashes, PostgreSQL can rebuild the state (BC-008).

**P-07: Fail-Safe Defaults**

When in doubt, the system defaults to the safest option: escalate to human, deny the action, pause the agent. No autonomous action is taken when confidence is ambiguous. The Control System node enforces this with the "Newness Rule" — confidence below 70% always triggers ASK_HUMAN.

**P-08: Observable by Design**

Every node in the LangGraph graph emits structured events to the Jarvis Live Activity Feed. Every decision is logged to the audit trail. Every model call logs input, output, latency, tokens, and model used. Managers can see exactly what happened, why, and when.

**P-09: Multi-Tenant Isolation via RLS**

All data is stored in a shared PostgreSQL database with Row-Level Security (RLS) policies. Each tenant can only access their own data. This is enforced at the database level, not just the application level, providing defense-in-depth against data leakage between tenants.

**P-10: Progressive Enhancement by Tier**

The base experience (Mini PARWA) is fully functional and production-ready. Higher tiers add capabilities through additional agents, advanced techniques, more agent instances, and premium features — but they never remove or degrade base functionality.

---

## 2. High-Level System Architecture

### 2.1 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL ACTORS                                │
│                                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│  │ Customer  │   │ Manager  │   │ Prospect │   │ Admin    │               │
│  │ (Chat/   │   │ (Jarvis) │   │(Onboard) │   │ (System) │               │
│  │ Email/   │   │          │   │          │   │          │               │
│  │ SMS/     │   │          │   │          │   │          │               │
│  │ Voice)   │   │          │   │          │   │          │               │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘               │
│       │              │              │              │                        │
└───────┼──────────────┼──────────────┼──────────────┼────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  Next.js 16      │  │  Next.js 16      │  │  Next.js 16      │         │
│  │  Customer Widget │  │  Jarvis Dashboard│  │  Onboarding Page │         │
│  │  (Chat/Email/    │  │  (Manager Portal)│  │  (/onboarding)   │         │
│  │   SMS/Voice UI)  │  │                  │  │                  │         │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘         │
│           │                     │                     │                     │
│  ┌────────┴─────────────────────┴─────────────────────┴──────────┐        │
│  │                    Landing Page + Pricing Page                 │        │
│  └───────────────────────────────────────────────────────────────┘        │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────┐        │
│  │              Shared UI Components (Radix + Tailwind)          │        │
│  │  Rich Cards | Terminal Feed | Live Activity | Status Panels   │        │
│  └───────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────┐        │
│  │                     FastAPI Application                        │        │
│  │                                                               │        │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐         │        │
│  │  │ REST APIs   │  │ WebSocket    │  │ SSE Streams  │         │        │
│  │  │ (150+       │  │ (Socket.io)  │  │ (Real-time   │         │        │
│  │  │  endpoints) │  │              │  │  updates)    │         │        │
│  │  └─────────────┘  └──────────────┘  └──────────────┘         │        │
│  │                                                               │        │
│  │  ┌─────────────────────────────────────────────────────┐     │        │
│  │  │              Middleware Stack                        │     │        │
│  │  │  Auth → Variant Resolver → Rate Limiter → Logger    │     │        │
│  │  └─────────────────────────────────────────────────────┘     │        │
│  └───────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATION LAYER                                 │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────┐        │
│  │                  LANGGRAPH STATE GRAPH                         │        │
│  │                                                               │        │
│  │  PII Redaction → Empathy Engine → Router Agent → Domain      │        │
│  │  Agent → MAKER Validator → Control System → DSPy →           │        │
│  │  Guardrails → Channel Delivery → State Update                │        │
│  │                                                               │        │
│  │  Conditional edges based on: intent, sentiment, tier,        │        │
│  │  confidence, red-flags, variant tier, approval decision      │        │
│  │                                                               │        │
│  │  Human-in-the-loop: interrupt_before Control System           │        │
│  │  for manager approval, resume after decision                 │        │
│  │                                                               │        │
│  │  State persistence: PostgreSQL checkpointer                   │        │
│  └───────────────────────────────────────────────────────────────┘        │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────┐        │
│  │                    AGENT POOL                                  │        │
│  │                                                               │        │
│  │  18 Specialized Agent Types × Dynamic Instances per Tier     │        │
│  │  Each agent: own prompt + tools + model tier + techniques    │        │
│  └───────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER                                     │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Smart Router │  │ Technique    │  │ GSD State    │  │ Ticket       │  │
│  │ (LiteLLM +   │  │ Router       │  │ Engine       │  │ Service      │  │
│  │  Own API Keys│  │ (10 signals) │  │ (Redis+PG)   │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Agent        │  │ Knowledge    │  │ Channel      │  │ Billing      │  │
│  │ Lightning    │  │ Base Service │  │ Adapters     │  │ Service      │  │
│  │ (Training)   │  │ (RAG+pgvector│  │ (Twilio/     │  │ (Paddle)     │  │
│  │              │  │  + KB)       │  │  Brevo/WS)   │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Empathy      │  │ DSPy Prompt  │  │ Guardrails   │  │ MAKER        │  │
│  │ Engine       │  │ Optimizer    │  │ AI           │  │ Framework    │  │
│  │ (Sentiment)  │  │              │  │              │  │ (MAD+FAKE+RF)│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Onboarding   │  │ Integrations │  │ Safety       │  │ Analytics    │  │
│  │ Service      │  │ Service      │  │ Systems      │  │ Service      │  │
│  │ (Jarvis)     │  │ (MCP+Webhook)│  │ (VoiceGuard  │  │ (Metrics+    │  │
│  │              │  │              │  │  Fairness+   │  │  ROI+Drift)  │  │
│  │              │  │              │  │  HNTN+AARM)  │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                       │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  PostgreSQL      │  │  Redis           │  │  S3-Compatible   │         │
│  │  (Supabase)      │  │  (Cache + Queue) │  │  (File Storage)  │         │
│  │                  │  │                  │  │                  │         │
│  │  - 90+ Tables    │  │  - GSD State     │  │  - KB Documents  │         │
│  │  - pgvector      │  │  - Sessions      │  │  - Training Data │         │
│  │  - RLS Policies  │  │  - Rate Limits   │  │  - Exports       │         │
│  │  - Audit Trail   │  │  - Pub/Sub       │  │  - Attachments   │         │
│  │  - Checkpoints   │  │  - Celery Broker │  │                  │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                               │
│  │  Celery Workers  │  │  LangGraph       │                               │
│  │  (Async Tasks)   │  │  Checkpointer    │                               │
│  │                  │  │  (PG-backed)     │                               │
│  │  - Email sending │  │                  │                               │
│  │  - Voice calls   │  │  - Graph state   │                               │
│  │  - Training jobs │  │    persistence   │                               │
│  │  - Report export │  │  - Resume on     │                               │
│  │  - KB ingestion  │  │    failure       │                               │
│  └──────────────────┘  └──────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                                    │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ LLM Providers│  │ Twilio       │  │ Brevo        │  │ Paddle       │  │
│  │ (via LiteLLM │  │ (Voice + SMS │  │ (Email       │  │ (Payments +  │  │
│  │  + Own Keys) │  │  + IVR)      │  │  In/Out)     │  │  Billing)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │ Google Colab │  │ RunPod       │  │ Client       │                     │
│  │ (Training -  │  │ (Training -  │  │ Integrations │                     │
│  │  Free Tier)  │  │  Paid Auto)  │  │ (REST/WS/DB) │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Architectural Layers Summary

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| **Presentation** | Next.js 16 + Tailwind CSS 4 + Radix UI | Customer widget, Jarvis dashboard, Onboarding, Landing, Pricing |
| **API** | FastAPI + Socket.io + SSE | REST endpoints, WebSocket real-time, Server-Sent Events |
| **Orchestration** | LangGraph | State graph, conditional routing, human-in-the-loop, state persistence |
| **Agent Pool** | 18 Specialized Agent Types | Domain-specific AI workers with own prompts, tools, models |
| **Services** | Python (FastAPI sub-modules) | Smart Router, Technique Router, GSD, Tickets, Billing, KB, etc. |
| **Data** | PostgreSQL (Supabase) + Redis + S3 | Persistent storage, caching/queue, file storage |
| **Async Workers** | Celery + Redis | Email sending, voice calls, training, exports, KB ingestion |
| **External** | LiteLLM, Twilio, Brevo, Paddle, Colab/RunPod | LLM inference, voice/SMS, email, payments, training GPU |

---

## 3. Multi-Agent Architecture & LangGraph Orchestration

### 3.1 Why Multi-Agent — The Core Paradigm

PARWA's multi-agent architecture is the fundamental design decision that shapes every other aspect of the system. Instead of a single monolithic LLM call that handles everything, PARWA deploys specialized agents that collaborate through LangGraph's state graph. Each agent is a self-contained unit responsible for a specific domain, and the orchestration layer manages the flow between them.

The multi-agent approach directly supports PARWA's key requirements in ways that a monolithic approach cannot:

**Error Isolation and Recovery:** When the Refund Agent encounters an error, the FAQ Agent, Billing Agent, and all other agents continue operating normally. The error is contained to a single agent, making debugging straightforward and system resilience high. In a monolithic approach, a single bug can corrupt the entire response generation pipeline.

**Independent Training via Agent Lightning:** Each agent type has its own training data accumulation and fine-tuning cycle. The Refund Agent learns from refund-specific manager corrections without affecting how the Technical Agent troubleshoots issues. This is critical because mixing training signals across domains would degrade quality in all domains simultaneously.

**Variant Tier Enforcement at the Agent Level:** Each agent declares a minimum variant tier, and the LangGraph Router Node checks this before routing. A Mini PARWA tenant simply never reaches the Voice Agent or Billing Agent — the graph routes them to the agents available at their tier. This is far cleaner than sprinkling if-statements throughout monolithic code.

**Dynamic Scaling by Agent Type:** When FAQ traffic spikes during a sale event, PARWA can provision additional FAQ Agent instances without touching the Refund Agent or Complaint Agent. The agent pool scales independently based on demand per agent type, which is both cost-efficient and performance-optimal.

**Human-in-the-Loop at Precise Points:** LangGraph's `interrupt_before` mechanism allows the graph to pause execution at the Control System node, wait for a manager's approval decision, and then resume exactly where it left off. This is architecturally clean — the graph doesn't need to implement its own approval queue or callback system.

### 3.2 Agent Communication Model — State-Based, Not Direct

Agents in PARWA NEVER communicate directly with each other. They read from and write to the shared `ParwaGraphState` object, and LangGraph determines which agent to invoke next based on the current state. This has profound implications for the system's maintainability and extensibility.

```
┌──────────────────────────────────────────────────────────────────┐
│                AGENT COMMUNICATION MODEL                         │
│                                                                  │
│  ❌ FORBIDDEN: Agent A directly calls Agent B                   │
│     This creates tight coupling and hidden dependencies          │
│                                                                  │
│  ✅ CORRECT: Agent A writes to State → LangGraph reads State    │
│     → LangGraph routes to Agent B → Agent B reads from State    │
│                                                                  │
│  Example Flow:                                                   │
│                                                                  │
│  1. Router Agent reads: {message, channel, customer_id}         │
│     Router Agent writes: {intent: "refund", target_agent:       │
│       "refund_agent", complexity: 8, model_tier: "heavy"}       │
│                                                                  │
│  2. LangGraph reads state, sees target_agent="refund_agent"     │
│     LangGraph routes execution to Refund Agent node             │
│                                                                  │
│  3. Refund Agent reads: {message, intent, gsd_state, tier}      │
│     Refund Agent writes: {agent_response, proposed_action,       │
│       action_type: "refund", agent_confidence: 0.82}            │
│                                                                  │
│  4. LangGraph reads state, sees action_type="refund"            │
│     LangGraph routes to MAKER Validator node (safety gate)      │
│                                                                  │
│  5. MAKER Validator reads: {agent_response, proposed_action}    │
│     MAKER Validator writes: {k_solutions, selected_solution,     │
│       red_flag: null}                                            │
│                                                                  │
│  Result: Zero coupling. Any agent can be replaced without        │
│  affecting others. New agents can be added by simply             │
│  adding a new node to the LangGraph and updating routing logic.  │
└──────────────────────────────────────────────────────────────────┘
```

The state-based communication model also enables powerful debugging: at any point, a developer or manager can inspect the full `ParwaGraphState` to see exactly what every agent contributed, what decisions were made, and why. This is impossible in a system where agents call each other through hidden function calls.

### 3.3 LangGraph Orchestration — How the Graph Works

LangGraph serves as the central orchestrator for all agent interactions. It defines the execution graph as a series of nodes (agents/functions) connected by edges (conditional routing logic). The graph is compiled once at application startup and reused for every customer request.

**Key LangGraph Features Used:**

| Feature | PARWA Usage |
|---------|-------------|
| **StateGraph** | The core graph type. Takes `ParwaGraphState` as its schema |
| **add_node** | Each specialized agent is registered as a node |
| **add_edge** | Defines unconditional transitions (START → PII Redaction) |
| **add_conditional_edges** | Defines conditional routing (Router → which domain agent?) |
| **interrupt_before** | Pauses graph at Control System for manager approval |
| **PostgresSaver (Checkpointer)** | Persists graph state to PostgreSQL for resume-on-failure |
| **Command** | Used for human-in-the-loop resume after approval |

**Graph Compilation (at startup):**

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

# Build the graph
graph = StateGraph(ParwaGraphState)

# Register all nodes
graph.add_node("pii_redaction", pii_redaction_node)
graph.add_node("empathy_engine", empathy_engine_node)
graph.add_node("router", router_node)
graph.add_node("faq_agent", faq_agent_node)
graph.add_node("refund_agent", refund_agent_node)
graph.add_node("technical_agent", technical_agent_node)
graph.add_node("billing_agent", billing_agent_node)
graph.add_node("complaint_agent", complaint_agent_node)
graph.add_node("escalation_agent", escalation_agent_node)
graph.add_node("maker_validator", maker_validator_node)
graph.add_node("control_system", control_system_node)
graph.add_node("dspy_optimizer", dspy_optimizer_node)
graph.add_node("guardrails", guardrails_node)
graph.add_node("channel_delivery", channel_delivery_node)
graph.add_node("state_update", state_update_node)

# Define entry point
graph.set_entry_point("pii_redaction")

# Define unconditional edges
graph.add_edge("pii_redaction", "empathy_engine")
graph.add_edge("empathy_engine", "router")

# Define conditional routing from Router to Domain Agents
graph.add_conditional_edges("router", route_to_agent)

# All domain agents route to MAKER
graph.add_edge("faq_agent", "maker_validator")
graph.add_edge("refund_agent", "maker_validator")
graph.add_edge("technical_agent", "maker_validator")
graph.add_edge("billing_agent", "maker_validator")
graph.add_edge("complaint_agent", "maker_validator")
graph.add_edge("escalation_agent", "state_update")  # Escalation skips MAKER

# MAKER conditional: red-flagged → escalation, clear → Control System
graph.add_conditional_edges("maker_validator", maker_route)

# Control System: interrupt before for approval
graph.add_conditional_edges("control_system", control_route)

# DSPy optimization (Pro/High only, conditional)
graph.add_conditional_edges("dspy_optimizer", dspy_route)

# Guardrails: pass → deliver, block → blocked response manager
graph.add_conditional_edges("guardrails", guardrails_route)

# Channel delivery → state update → END
graph.add_edge("channel_delivery", "state_update")
graph.add_edge("state_update", END)

# Compile with PostgreSQL checkpointer
checkpointer = PostgresSaver(conn_string=DATABASE_URL)
compiled_graph = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["control_system"]  # Pause for manager approval
)
```

### 3.4 Human-in-the-Loop — Manager Approval Flow

The most critical feature of the LangGraph orchestration is the human-in-the-loop mechanism at the Control System node. When a customer request requires manager approval (Money Rule, VIP Rule, low confidence), the graph pauses execution and waits for the manager's decision.

```
┌──────────────────────────────────────────────────────────────────┐
│           HUMAN-IN-THE-LOOP APPROVAL FLOW                        │
│                                                                  │
│  1. Graph executes: PII → Empathy → Router → Refund Agent       │
│     → MAKER Validator → reaches Control System node              │
│                                                                  │
│  2. Graph PAUSES (interrupt_before=["control_system"])           │
│     State is persisted to PostgreSQL checkpointer                │
│                                                                  │
│  3. Manager receives notification via Jarvis:                    │
│     "Refund request for $85.00 — Approve/Reject?"               │
│     Shows: confidence score, MAKER analysis, red-flag status     │
│                                                                  │
│  4. Manager makes decision:                                      │
│     - APPROVE → Graph resumes, routes to DSPy → Guardrails      │
│     - REJECT → Graph resumes, routes to state_update with       │
│       rejection reason, feeds negative reward to Agent Lightning │
│     - MODIFY → Graph resumes with modified action, routes back  │
│       through MAKER for re-validation                            │
│                                                                  │
│  5. Graph continues to completion                                │
│                                                                  │
│  Timeout handling: If no manager response within 15 minutes,     │
│  the Stuck Approval Escalation Ladder activates:                 │
│  Level 1: Remind assigned manager (5 min)                        │
│  Level 2: Alert supervisor (10 min)                              │
│  Level 3: Auto-escalate to any available manager (15 min)        │
└──────────────────────────────────────────────────────────────────┘
```

### 3.5 Agent Instance Management — Dynamic Provisioning

PARWA supports dynamic agent provisioning — managers can create or remove agent instances through Jarvis commands or the dashboard. The agent pool is managed in the `agent_pool` database table and reflected in the LangGraph routing logic.

```
┌──────────────────────────────────────────────────────────────────┐
│           DYNAMIC AGENT PROVISIONING                             │
│                                                                  │
│  agent_pool table:                                               │
│  ┌──────────┬────────────┬──────────┬────────┬──────────┐      │
│  │ agent_id │ agent_type │ tenant_id│ status │ capacity │      │
│  ├──────────┼────────────┼──────────┼────────┼──────────┤      │
│  │ ag_001   │ faq        │ comp_1   │ active │ 100/hr   │      │
│  │ ag_002   │ faq        │ comp_1   │ active │ 100/hr   │      │
│  │ ag_003   │ refund     │ comp_1   │ active │ 50/hr    │      │
│  │ ag_004   │ technical  │ comp_1   │ active │ 50/hr    │      │
│  │ ag_005   │ voice      │ comp_2   │ active │ 30/hr    │      │
│  └──────────┴────────────┴──────────┴────────┴──────────┘      │
│                                                                  │
│  Jarvis: "Add 3 more FAQ agents"                                 │
│  → Provisioning API creates 3 new agent_pool entries             │
│  → Router Node load-balances across all active FAQ agents        │
│  → New instances immediately available for routing                │
│                                                                  │
│  Jarvis: "Remove 2 FAQ agents"                                   │
│  → Deactivate 2 FAQ agent instances (drain first, then stop)    │
│  → Remaining agents handle the load                              │
│  → Hard limit enforced: cannot go below 1 instance per type      │
│                                                                  │
│  Tier limits (hard):                                             │
│  Mini PARWA:  max 5 agent instances total                        │
│  PARWA Pro:   max 15 agent instances total                       │
│  PARWA High:  max 50 agent instances total                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Agent Roster & Specifications

### 4.1 Complete Agent Roster

PARWA defines 18 specialized agent types. Each agent type is a LangGraph node with its own system prompt, tool set, model tier preference, technique configuration, and variant tier requirement. At runtime, multiple instances of each agent type may exist per tenant based on their tier and provisioning decisions.

#### 4.1.1 Core Agents (Domain-Specific)

**FAQ Agent**

| Property | Value |
|----------|-------|
| Agent Type | `faq` |
| Min Tier | `mini` |
| Model Tier | Light |
| Technique Stack | Tier 1 only (CLARA + CRP + GSD) |
| System Prompt | "You are a knowledgeable FAQ agent. Answer customer questions from the knowledge base accurately and concisely. If the answer is not in the KB, say so and offer to escalate." |
| Tools | `rag_search`, `kb_lookup`, `order_status`, `tracking_url`, `product_info` |
| MAKER Mode | Efficiency (K=3) |
| Control System | FAQ answers are DND (auto-execute, no approval needed) |
| Capacity | ~100 queries/hour per instance |

**Refund Agent**

| Property | Value |
|----------|-------|
| Agent Type | `refund` |
| Min Tier | `mini` |
| Model Tier | Heavy |
| Technique Stack | Tier 1 + CoT + Reverse Thinking + Self-Consistency |
| System Prompt | "You are a careful refund processing agent. Decompose refund requests into verification steps. Never execute a refund without manager approval. Always check refund eligibility, order status, and payment method before proposing action." |
| Tools | `verify_customer`, `check_refund_eligibility`, `calculate_refund_amount`, `verify_payment_method`, `request_approval`, `execute_refund`, `send_confirmation`, `update_records` |
| MAKER Mode | Balanced (K=5) for Pro, Conservative (K=7) for High |
| Control System | ALWAYS requires approval (Money Rule hard-coded). Confidence irrelevant. |
| Capacity | ~50 queries/hour per instance |

**Technical Agent**

| Property | Value |
|----------|-------|
| Agent Type | `technical` |
| Min Tier | `mini` |
| Model Tier | Medium |
| Technique Stack | Tier 1 + CoT + ReAct |
| System Prompt | "You are a technical troubleshooting agent. Use step-by-step reasoning to diagnose issues. Use available tools to check system status, retrieve documentation, and create bug reports. Escalate to human if issue requires code changes." |
| Tools | `rag_search`, `diagnostic_tools`, `api_status_check`, `create_bug_report`, `kb_search`, `system_diagnostics` |
| MAKER Mode | Efficiency (K=3) |
| Control System | Auto-execute for information queries. ASK_HUMAN for actions that modify systems. |
| Capacity | ~60 queries/hour per instance |

**Billing Agent**

| Property | Value |
|----------|-------|
| Agent Type | `billing` |
| Min Tier | `pro` |
| Model Tier | Heavy |
| Technique Stack | Tier 1 + Self-Consistency |
| System Prompt | "You are a billing specialist agent. Handle subscription changes, payment issues, invoice requests, and billing disputes with precision. Always verify identity before discussing account details. Any financial change requires manager approval." |
| Tools | `subscription_lookup`, `payment_history`, `invoice_generator`, `payment_processor`, `subscription_modifier`, `identity_verification` |
| MAKER Mode | Balanced (K=5) |
| Control System | ALWAYS requires approval for financial changes (Money Rule). |
| Capacity | ~40 queries/hour per instance |

**Complaint Agent**

| Property | Value |
|----------|-------|
| Agent Type | `complaint` |
| Min Tier | `pro` |
| Model Tier | Heavy |
| Technique Stack | Tier 1 + UoT + Reflexion |
| System Prompt | "You are an empathetic complaint handling agent. Customers reaching you are frustrated. Prioritize de-escalation, acknowledge their frustration, and propose fair resolutions. Always flag legal threats for immediate human escalation." |
| Tools | `escalation_path`, `sentiment_tracker`, `legal_flag_detector`, `vip_handler`, `de_escalation_protocol`, `compensation_calculator` |
| MAKER Mode | Balanced (K=5) |
| Control System | Auto-escalate on legal threats. ASK_HUMAN for compensation above $50. |
| Capacity | ~30 queries/hour per instance |

**Escalation Agent**

| Property | Value |
|----------|-------|
| Agent Type | `escalation` |
| Min Tier | `mini` |
| Model Tier | Light |
| Technique Stack | Tier 1 only |
| System Prompt | "You are an escalation coordination agent. Your job is to package context, notify the right human agent, and facilitate warm transfer. Do not attempt to resolve the issue yourself — your role is to make the handoff as smooth as possible." |
| Tools | `human_notifier`, `context_packager`, `transfer_protocol`, `supervisor_alert`, `escalation_ladder` |
| MAKER Mode | Not applicable (escalation skips MAKER) |
| Control System | Not applicable (already at human level) |
| Capacity | ~80 escalations/hour per instance |

#### 4.1.2 Channel-Specific Agents

**Email Agent**

| Property | Value |
|----------|-------|
| Agent Type | `email` |
| Min Tier | `mini` |
| Model Tier | Medium |
| Technique Stack | Tier 1 + CRP (concise email formatting) |
| System Prompt | "You are an email composition agent. Draft professional, concise email responses using Brevo templates. Respect rate limits: 5 replies per thread per 24 hours, 100 emails per company per day. Always include unsubscribe links. Detect and ignore out-of-office auto-replies." |
| Tools | `email_composer`, `template_selector`, `brevo_send`, `ooo_detector`, `unsubscribe_handler`, `jinja2_renderer` |
| Constraints | 5 replies/thread/24h hard cap, 100 emails/company/day, no raw PII in subjects |
| Capacity | ~200 emails/hour per instance |

**SMS Agent**

| Property | Value |
|----------|-------|
| Agent Type | `sms` |
| Min Tier | `pro` |
| Model Tier | Light |
| Technique Stack | Tier 1 + CRP (SMS requires conciseness) |
| System Prompt | "You are an SMS communication agent. Handle customer conversations via text message. Keep responses concise and within character limits. Ensure TCPA compliance — never message customers who have opted out. Include opt-out instructions when required." |
| Tools | `sms_sender`, `opt_in_manager`, `tcpa_compliance_check`, `sms_composer`, `character_limiter` |
| Constraints | TCPA compliance, opt-in/opt-out management, 160 char segments |
| Capacity | ~300 messages/hour per instance |

**Voice Agent**

| Property | Value |
|----------|-------|
| Agent Type | `voice` |
| Min Tier | `pro` |
| Model Tier | Medium (conversation), Heavy (complex decisions) |
| Technique Stack | Tier 1 + CoT + Step-Back |
| System Prompt | "You are a voice conversation agent. Handle phone calls via Twilio with clear, natural speech. Follow the Voice-First Rule — always answer with voice, never redirect to text-only initially. Manage IVR flows, warm transfers, and post-call summaries. Detect sentiment from speech patterns." |
| Tools | `ivr_handler`, `speech_to_text`, `text_to_speech`, `call_transfer`, `post_call_summary`, `live_sentiment`, `recording_manager` |
| Constraints | Voice-First Rule (hard-coded), IVR flow, TCPA for outbound, compliance recording |
| Capacity | ~30 concurrent calls per instance |

**Video Agent**

| Property | Value |
|----------|-------|
| Agent Type | `video` |
| Min Tier | `high` |
| Model Tier | Heavy |
| Technique Stack | Tier 1 + CoT + UoT |
| System Prompt | "You are a video call agent. Handle face-to-face customer interactions with professional composure. Use visual context when available. Manage screen sharing, document display, and real-time transcription." |
| Tools | `video_call_manager`, `screen_share`, `visual_context_analyzer`, `real_time_transcription` |
| Constraints | PARWA High only, limited concurrent sessions |
| Capacity | ~10 concurrent calls per instance |

#### 4.1.3 Safety & Quality Agents

**PII Redaction Agent**

| Property | Value |
|----------|-------|
| Agent Type | `pii_redaction` |
| Min Tier | `mini` |
| Model Tier | None (local Python, no LLM) |
| Technique Stack | Not applicable |
| System Prompt | N/A — deterministic Python function |
| Tools | `cc_detector`, `ssn_detector`, `bank_account_detector`, `email_detector`, `phone_detector`, `redactor`, `masker` |
| Position | First node in the graph — strips PII BEFORE any LLM call |
| Capacity | ~10,000 messages/hour (no LLM overhead) |

**MAKER Validator Agent**

| Property | Value |
|----------|-------|
| Agent Type | `maker_validator` |
| Min Tier | `mini` |
| Model Tier | Same as requesting agent (inherits from state) |
| Technique Stack | MAKER Framework (MAD + FAKE + Red-Flagging) |
| System Prompt | "You are the MAKER validation agent. Decompose the proposed action into atomic steps, generate K alternative solutions, evaluate each for policy compliance and risk, and select the best solution. Flag any anomalies." |
| Tools | `solution_generator`, `solution_evaluator`, `comparator`, `red_flag_detector`, `k_value_resolver` |
| K-Values | Mini: K=3, Pro: K=3-5, High: K=5-7 |
| Capacity | Depends on K-value and model tier |

**Guardrails Agent**

| Property | Value |
|----------|-------|
| Agent Type | `guardrails` |
| Min Tier | `mini` |
| Model Tier | Light (validation is simpler than generation) |
| Technique Stack | Not applicable (validation, not generation) |
| System Prompt | "You are the final output validation agent. Check every AI response for: hallucination, competitor mentions, PII leaks, brand voice compliance, and factual accuracy. Block responses that fail any check and route to Blocked Response Manager." |
| Tools | `hallucination_detector`, `competitor_blocker`, `pii_leak_checker`, `brand_voice_checker`, `factual_accuracy_verifier`, `custom_rule_engine` |
| Position | Last gate before channel delivery |
| Variant | Mini: basic (hallucination only), Pro: full, High: full + custom rules |
| Capacity | ~500 validations/hour per instance |

**DSPy Optimizer Agent**

| Property | Value |
|----------|-------|
| Agent Type | `dspy_optimizer` |
| Min Tier | `pro` |
| Model Tier | Medium |
| Technique Stack | DSPy (BootstrapFewShot, MIPROv2) |
| System Prompt | "You are the DSPy prompt optimization agent. Run A/B tests on prompt variants, optimize signatures using BootstrapFewShot, and refine prompts based on outcome data. Run in background — never block customer-facing requests." |
| Tools | `ab_test_runner`, `bootstrap_fewshot`, `signature_refiner`, `miprov2_optimizer`, `evaluation_scorer` |
| Execution | Background Celery task, not in critical path |
| Capacity | Runs on schedule, not per-request |

#### 4.1.4 Manager-Facing Agents

**Jarvis Command Agent**

| Property | Value |
|----------|-------|
| Agent Type | `jarvis_command` |
| Min Tier | `mini` |
| Model Tier | Light |
| Technique Stack | Tier 1 only |
| System Prompt | "You are Jarvis, the command center AI. Parse manager natural language commands into structured actions. Support commands like: pause refunds, show ticket details, add agents, call customer, check system health, export reports. If a command is ambiguous, ask for clarification before executing." |
| Tools | `command_parser`, `command_validator`, `command_executor`, `terminal_formatter`, `co_pilot_drafter`, `quick_command_resolver` |
| Variant | Mini: basic commands, Pro: +Co-Pilot +provisioning +policy training, High: +Self-Healing |
| Capacity | ~200 commands/hour |

**Analytics Agent**

| Property | Value |
|----------|-------|
| Agent Type | `analytics` |
| Min Tier | `mini` |
| Model Tier | Light |
| Technique Stack | Not applicable (data aggregation) |
| System Prompt | "You are the analytics agent. Generate reports, dashboards, ROI calculations, and trend analyses based on tenant data. Support natural language queries like 'show me this week's refund rate'." |
| Tools | `metrics_aggregator`, `trend_analyzer`, `roi_calculator`, `export_generator`, `drift_detector`, `confidence_analyzer` |
| Variant | Mini: overview + metrics, Pro: +trends +ROI, High: +drift +Quality Coach |
| Capacity | ~50 report generations/hour |

**Quality Coach Agent**

| Property | Value |
|----------|-------|
| Agent Type | `quality_coach` |
| Min Tier | `high` |
| Model Tier | Medium |
| Technique Stack | Tier 1 + Reflexion |
| System Prompt | "You are the Quality Coach agent (PARWA High exclusive). Analyze agent performance metrics, identify patterns of errors or inefficiencies, and suggest specific training improvements. Generate weekly performance reports with actionable recommendations." |
| Tools | `performance_analyzer`, `training_suggester`, `benchmark_comparator`, `feedback_generator`, `weekly_report_builder` |
| Execution | Weekly scheduled analysis + on-demand |
| Capacity | ~20 analyses/hour |

#### 4.1.5 Onboarding Agents

**Onboarding Jarvis Agent**

| Property | Value |
|----------|-------|
| Agent Type | `onboarding_jarvis` |
| Min Tier | N/A (pre-purchase, no tenant yet) |
| Model Tier | Light/Medium |
| Technique Stack | Tier 1 + CRP |
| System Prompt | Built dynamically from 7-Layer System Prompt Builder: Base Persona, Product Knowledge (10 JSON files), Industry Knowledge, Session Context, Relevant Knowledge, Stage Behavior, Information Boundary |
| Tools | `knowledge_service` (11 functions), `rich_card_builder`, `stage_detector`, `demo_call_handler`, `otp_handler`, `payment_handler`, `handoff_manager`, `message_counter` |
| Special | 20 msgs/day free, $1 Demo Pack (500 msgs + 3-min call), 8 conversation stages, 9 action ticket types, 12 rich card types |
| Capacity | ~100 concurrent sessions |

**Handoff Agent**

| Property | Value |
|----------|-------|
| Agent Type | `handoff` |
| Min Tier | N/A (internal transition) |
| Model Tier | None (deterministic logic) |
| Technique Stack | Not applicable |
| System Prompt | N/A — deterministic transition logic |
| Tools | `context_filter`, `session_creator`, `archive_manager`, `farewell_generator` |
| Behavior | Selective context transfer: hired_variants + business_info + industry → Customer Care Jarvis. Onboarding chat preserved read-only. NO chat history transferred. |
| Capacity | ~50 handoffs/hour |

#### 4.1.6 Router Agent

**Router Agent (Orchestration Entry Point)**

| Property | Value |
|----------|-------|
| Agent Type | `router` |
| Min Tier | `mini` |
| Model Tier | Light |
| Technique Stack | Tier 1 only |
| System Prompt | "You are the Router Agent — the first point of contact for every customer message. Classify the intent, calculate the complexity score, check the tenant's variant tier, and determine which specialist agent should handle this request. Output: intent, complexity, target_agent, model_tier, technique_stack." |
| Tools | `intent_classifier`, `complexity_scorer`, `tier_checker`, `agent_availability_checker`, `technique_mapper` |
| Output | Writes to state: intent, complexity_score, target_agent, model_tier, technique_stack |
| Capacity | ~500 classifications/hour per instance |

### 4.2 Agent Type to Tier Mapping

| Agent Type | Mini ($999) | Pro ($2,499) | High ($3,999) |
|-----------|:-----------:|:------------:|:-------------:|
| Router | ✅ | ✅ | ✅ |
| FAQ | ✅ | ✅ | ✅ |
| Refund | ✅ | ✅ | ✅ |
| Technical | ✅ | ✅ | ✅ |
| Email | ✅ | ✅ | ✅ |
| Escalation | ✅ | ✅ | ✅ |
| PII Redaction | ✅ | ✅ | ✅ |
| MAKER Validator | ✅ | ✅ | ✅ |
| Guardrails | ✅ (basic) | ✅ (full) | ✅ (full+custom) |
| Jarvis Command | ✅ (basic) | ✅ (+Co-Pilot) | ✅ (+Self-Heal) |
| Analytics | ✅ (basic) | ✅ (full) | ✅ (+Coach) |
| Billing | ❌ | ✅ | ✅ |
| Complaint | ❌ | ✅ | ✅ |
| SMS | ❌ | ✅ | ✅ |
| Voice | ❌ | ✅ | ✅ |
| DSPy Optimizer | ❌ | ✅ | ✅ |
| Video | ❌ | ❌ | ✅ |
| Quality Coach | ❌ | ❌ | ✅ |
| Onboarding Jarvis | ✅ (shared) | ✅ (shared) | ✅ (shared) |
| Handoff | ✅ (shared) | ✅ (shared) | ✅ (shared) |

Note: Onboarding Jarvis and Handoff Agent are shared resources — they serve pre-purchase prospects before a tenant exists, so they are not counted against any tier's agent instance limit.

### 4.3 Agent Instance Pool per Tier

| Tier | Max Instances | Typical Distribution |
|------|:------------:|---------------------|
| Mini | 5 | 1×Router, 1×FAQ, 1×Refund, 1×Technical, 1×Email |
| Pro | 15 | 2×Router, 3×FAQ, 2×Refund, 2×Technical, 1×Billing, 1×Complaint, 1×SMS, 1×Voice, 1×Email, 1×Escalation |
| High | 50 | 3×Router, 8×FAQ, 5×Refund, 5×Technical, 3×Billing, 3×Complaint, 3×Voice, 3×SMS, 2×Video, 2×Email, 2×Escalation, 2×Analytics, 1×Quality Coach, 1×DSPy, 1×Jarvis, 1×Guardrails, 1×Handoff, 1×PII, 1×MAKER, 1×Onboarding |

---

## 5. LangGraph State Graph & Flow Definitions

### 5.1 ParwaGraphState — The Shared State Schema

The `ParwaGraphState` is the single most important data structure in the system. It flows through every node in the LangGraph graph, carrying all context needed for decision-making. Every agent reads from and writes to this state — agents never access databases directly during graph execution (database updates happen in the `state_update` node at the end of the graph).

```python
from typing import TypedDict, Optional, Literal
from typing_extensions import Annotated

class ParwaGraphState(TypedDict):
    # ─── Input Fields (set by Channel Adapter before graph invocation) ───
    message: str                           # Original customer message
    channel: Literal["chat", "email", "sms", "voice", "video"]
    customer_id: str                       # Customer identifier
    tenant_id: str                         # Company/tenant ID
    variant_tier: Literal["mini", "pro", "high"]
    conversation_id: str                   # GSD conversation identifier
    ticket_id: Optional[str]               # Existing ticket ID (if continuation)

    # ─── PII Redaction Node Output ───
    pii_redacted_message: str              # Message with PII masked/replaced
    pii_entities_found: list               # List of PII types detected & masked

    # ─── Empathy Engine Node Output ───
    sentiment_score: float                 # -1.0 to +1.0
    sentiment_intensity: Literal["neutral", "frustrated", "angry"]
    legal_threat_detected: bool            # Legal keyword detected?
    urgency: Literal["urgent", "routine", "informational"]
    sentiment_trend: Literal["improving", "stable", "declining"]

    # ─── Router Agent Node Output ───
    intent: Literal["refund", "technical", "billing", "complaint",
                    "faq", "feature_request", "general"]
    complexity_score: float                # 0-10+
    target_agent: str                      # Which specialist agent to route to
    model_tier: Literal["light", "medium", "heavy"]
    technique_stack: list                  # Techniques to apply for this request

    # ─── Domain Agent Node Output ───
    agent_response: str                    # The specialist's draft response
    agent_confidence: float                # 0-100%
    proposed_action: Optional[dict]        # Any action the agent wants to take
    action_type: Optional[Literal["refund", "credit", "info",
                                   "escalation", "modification", "none"]]
    agent_reasoning: str                   # Why the agent chose this response

    # ─── MAKER Validator Node Output ───
    k_solutions: list                      # K generated alternative solutions
    selected_solution: dict                # Best solution selected by FAKE
    red_flag: Optional[dict]               # Red flag if detected {category, reason, details}
    maker_mode: Literal["efficiency", "balanced", "conservative"]
    k_value_used: int                      # Actual K used for this request

    # ─── Control System Node Output ───
    approval_decision: Literal["EXECUTE", "BATCH", "ASK_HUMAN", "DENY"]
    confidence_breakdown: dict             # {pattern: %, policy: %, history: %, risk: %}
    system_mode: Literal["shadow", "supervised", "graduated"]
    dnd_applies: bool                      # Does DND rule allow auto-execution?
    money_rule_triggered: bool             # Was the Money Rule applied?
    vip_rule_triggered: bool               # Was the VIP Rule applied?

    # ─── DSPy Optimizer Node Output (Pro/High only) ───
    prompt_optimized: bool                 # Was DSPy applied?
    optimized_prompt_version: Optional[str] # Version ID of optimized prompt

    # ─── Guardrails Node Output ───
    guardrails_passed: bool                # Did the response pass all checks?
    guardrails_flags: list                 # Any issues detected [{type, severity, detail}]
    guardrails_blocked_reason: Optional[str] # Why blocked (if blocked)

    # ─── GSD State (loaded at start, updated at end) ───
    gsd_state: dict                        # Full GSD state object from Redis
    gsd_step: str                          # Current step in GSD state machine
    context_health: float                  # 0-100% context usage
    context_compressed: bool               # Was context compressed this turn?

    # ─── Metadata (tracked throughout) ───
    processing_start_time: float           # Unix timestamp of request start
    model_used: str                        # Which LLM was actually used
    tokens_consumed: int                   # Total token usage across all LLM calls
    total_llm_calls: int                   # Number of LLM API calls made
    node_execution_log: list               # Log of nodes executed [{node, timestamp, duration_ms}]
    error: Optional[str]                   # Any error that occurred
```

### 5.2 Complete LangGraph Flow — Node-by-Node

The following defines the complete execution flow of the LangGraph state graph for a standard customer request:

```
┌──────────────────────────────────────────────────────────────────────┐
│               COMPLETE LANGGRAPH FLOW                                │
│                                                                      │
│  START                                                               │
│    │                                                                 │
│    ▼                                                                 │
│  ┌────────────────────────┐                                         │
│  │ NODE 1: PII Redaction  │  Input: message                         │
│  │ (Deterministic Python)  │  Output: pii_redacted_message,          │
│  │                         │          pii_entities_found              │
│  │ Scans for: CC#, SSN,   │  No LLM call — pure regex + NER         │
│  │ bank accounts, phone#   │  Runs locally in <5ms                   │
│  └──────────┬─────────────┘                                         │
│             │ (unconditional edge)                                    │
│             ▼                                                        │
│  ┌────────────────────────┐                                         │
│  │ NODE 2: Empathy Engine │  Input: pii_redacted_message             │
│  │ (2-Layer Sentiment)    │  Output: sentiment_score,                │
│  │                        │          sentiment_intensity,            │
│  │ Layer 1: Keyword Lexicon│         legal_threat_detected,          │
│  │  (fast, local)         │          urgency                         │
│  │ Layer 2: NLP Sentiment │  Layer 1: <1ms (local lookup)           │
│  │  (Medium Tier LLM)     │  Layer 2: ~200ms (LLM call)             │
│  └──────────┬─────────────┘                                         │
│             │ (unconditional edge)                                    │
│             ▼                                                        │
│  ┌────────────────────────┐                                         │
│  │ NODE 3: Router Agent   │  Input: pii_redacted_message,           │
│  │ (Light Tier LLM)       │         sentiment_score, variant_tier   │
│  │                        │  Output: intent, complexity_score,       │
│  │ Classifies intent and  │          target_agent, model_tier,       │
│  │ calculates complexity  │          technique_stack                  │
│  │                        │  Also checks: variant_tier >=            │
│  │ Variant gate: checks   │          agent's min_tier                │
│  │ target_agent min_tier  │  ~300ms (Light Tier LLM)                │
│  └──────────┬─────────────┘                                         │
│             │ (conditional edge based on target_agent)                │
│             ▼                                                        │
│  ┌─────────────────────────────────────────────────┐                │
│  │ NODE 4: Domain Agent (one of 6 specialists)     │                │
│  │                                                   │                │
│  │  faq_agent       │  refund_agent                  │                │
│  │  technical_agent │  billing_agent                 │                │
│  │  complaint_agent │  escalation_agent              │                │
│  │                                                   │                │
│  │  Input: full state (message, intent, gsd_state,  │                │
│  │         technique_stack, model_tier)              │                │
│  │  Output: agent_response, agent_confidence,        │                │
│  │          proposed_action, action_type              │                │
│  │  Model: per agent spec (Light/Medium/Heavy)      │                │
│  │  Techniques: per technique_stack from Router     │                │
│  │  Tools: per agent tool set                        │                │
│  │  Duration: 500ms-3s depending on complexity      │                │
│  └──────────┬──────────────────────────────────────┘                │
│             │ (unconditional — all domain agents → MAKER)            │
│             │ (exception: escalation_agent → state_update → END)     │
│             ▼                                                        │
│  ┌────────────────────────┐                                         │
│  │ NODE 5: MAKER Validator│  Input: agent_response,                  │
│  │ (MAD + FAKE + Red-Flag)│         proposed_action,                 │
│  │                        │         action_type, variant_tier         │
│  │                        │  Output: k_solutions,                     │
│  │ MAD: Decompose action  │          selected_solution,               │
│  │  into atomic steps     │          red_flag, k_value_used           │
│  │ FAKE: Generate K       │                                         │
│  │  parallel solutions    │  K-Values: Mini=3, Pro=3-5, High=5-7    │
│  │ Red-Flag: Check for    │  Duration: 1-5s (K parallel LLM calls)  │
│  │  anomalies             │                                         │
│  └──────────┬─────────────┘                                         │
│             │ (conditional edge)                                     │
│             ├─ red_flag.category == "A" → escalation_agent           │
│             └─ no red_flag OR category B/C → Control System         │
│             ▼                                                        │
│  ┌────────────────────────┐                                         │
│  │ NODE 6: Control System │  *** INTERRUPT_BEFORE THIS NODE ***      │
│  │ (Approval Gates)       │                                         │
│  │                        │  Input: agent_response,                  │
│  │ Confidence Calculation:│         proposed_action,                 │
│  │  Pattern Match: 40%    │         agent_confidence,                │
│  │  Policy Alignment: 30% │         red_flag                         │
│  │  Historical Success:20%│  Output: approval_decision,              │
│  │  Risk Signals: 10%     │          confidence_breakdown,            │
│  │                        │          system_mode                      │
│  │ Decision Rules:        │                                         │
│  │  >95% → EXECUTE        │  Hard Rules (always ASK_HUMAN):         │
│  │  85-95% → BATCH        │  - Money Rule: refund/credit             │
│  │  70-84% → ASK_HUMAN    │  - VIP Rule: VIP customer               │
│  │  <70% → ESCALATE       │  - Newness Rule: confidence < 0.70      │
│  └──────────┬─────────────┘                                         │
│             │ (conditional edge based on approval_decision)           │
│             ├─ EXECUTE → DSPy Optimizer (or Guardrails if no DSPy)   │
│             ├─ BATCH → Batch Approval Queue (separate flow)          │
│             ├─ ASK_HUMAN → PAUSE (wait for manager via Jarvis)       │
│             │   └─ Manager Approves → DSPy → Guardrails              │
│             │   └─ Manager Rejects → state_update (negative reward)  │
│             │   └─ Manager Modifies → back to MAKER for re-validation│
│             └─ DENY → state_update (log denial reason)               │
│             ▼                                                        │
│  ┌────────────────────────┐                                         │
│  │ NODE 7: DSPy Optimizer │  Input: agent_response, intent,          │
│  │ (Pro/High only)        │         technique_stack                  │
│  │                        │  Output: prompt_optimized,                │
│  │ Runs prompt optimization│         optimized_prompt_version         │
│  │ in background if       │  Mini: SKIPPED (no-op node)             │
│  │ variant allows         │  Pro/High: runs if optimization due      │
│  │                        │  Duration: 0ms (Mini) or 500ms (Pro/High)│
│  └──────────┬─────────────┘                                         │
│             │ (unconditional edge)                                    │
│             ▼                                                        │
│  ┌────────────────────────┐                                         │
│  │ NODE 8: Guardrails     │  Input: agent_response (or MAKER's       │
│  │ (Output Validation)    │         selected_solution)               │
│  │                        │  Output: guardrails_passed,               │
│  │ Checks:                │          guardrails_flags,                │
│  │  - Hallucination       │          guardrails_blocked_reason        │
│  │  - Competitor mentions │                                         │
│  │  - PII leaks           │  Mini: hallucination only                │
│  │  - Brand voice         │  Pro: all checks                        │
│  │  - Factual accuracy    │  High: all checks + custom rules         │
│  │  - Custom rules (High) │  Duration: ~200ms (Light Tier validation)│
│  └──────────┬─────────────┘                                         │
│             │ (conditional edge)                                     │
│             ├─ PASSED → Channel Delivery                             │
│             └─ BLOCKED → Blocked Response Manager → state_update     │
│             ▼                                                        │
│  ┌────────────────────────┐                                         │
│  │ NODE 9: Channel        │  Input: final_response, channel          │
│  │ Delivery               │  Output: delivery_confirmation           │
│  │                        │                                         │
│  │ Formats and sends the  │  Chat: WebSocket push to customer widget │
│  │ response through the   │  Email: Celery task → Brevo API          │
│  │ appropriate channel    │  SMS: Celery task → Twilio API            │
│  │ adapter                │  Voice: TTS → Twilio Media Stream        │
│  │                        │  Video: TTS + visual → video stream       │
│  └──────────┬─────────────┘                                         │
│             │ (unconditional edge)                                    │
│             ▼                                                        │
│  ┌────────────────────────────────────────────────────┐             │
│  │ NODE 10: State Update (Final Node)                 │             │
│  │                                                    │             │
│  │  1. Update GSD state in Redis + PostgreSQL         │             │
│  │  2. Log full audit trail (state + decisions)       │             │
│  │  3. Feed reward signal to Agent Lightning:         │             │
│  │     - Approved → positive reward                   │             │
│  │     - Rejected → negative reward                   │             │
│  │  4. Create or update ticket in PostgreSQL          │             │
│  │  5. Push event to Jarvis Live Activity Feed (WS)   │             │
│  │  6. Update ticket metrics (response time, etc.)    │             │
│  │  7. Check 50-mistake threshold for Agent Lightning │             │
│  │  8. Log node_execution_log for observability       │             │
│  │                                                    │             │
│  └──────────┬─────────────────────────────────────────┘             │
│             │                                                        │
│             ▼                                                        │
│           END                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.3 Conditional Edge Functions

The routing logic between nodes is implemented as conditional edge functions that read the current state and return the name of the next node:

**route_to_agent (Router → Domain Agent):**
```python
def route_to_agent(state: ParwaGraphState) -> str:
    target = state["target_agent"]

    # Variant tier gate: check if tenant has access to this agent type
    agent_min_tier = AGENT_TIER_MAP[target]
    tier_order = {"mini": 0, "pro": 1, "high": 2}

    if tier_order[state["variant_tier"]] < tier_order[agent_min_tier]:
        # Tenant doesn't have access — downgrade or explain
        if target == "billing":
            return "escalation_agent"  # Route to human for billing
        if target == "complaint":
            return "escalation_agent"  # Route to human for complaints
        return "faq_agent"  # Default fallback

    # Legal threat → immediate escalation regardless of intent
    if state["legal_threat_detected"]:
        return "escalation_agent"

    # Extreme anger → human escalation
    if state["sentiment_intensity"] == "angry" and state["sentiment_score"] < -0.6:
        return "escalation_agent"

    return f"{target}_agent"
```

**maker_route (MAKER → Control or Escalation):**
```python
def maker_route(state: ParwaGraphState) -> str:
    red_flag = state.get("red_flag")

    if red_flag and red_flag["category"] == "A":
        return "escalation_agent"  # Immediate halt

    return "control_system"  # Proceed to approval gates
```

**control_route (Control System → next step):**
```python
def control_route(state: ParwaGraphState) -> str:
    decision = state["approval_decision"]

    if decision == "EXECUTE":
        if state["variant_tier"] in ("pro", "high"):
            return "dspy_optimizer"
        return "guardrails"

    if decision == "BATCH":
        return "state_update"  # Queue for batch approval (separate flow)

    if decision == "ASK_HUMAN":
        return "state_update"  # Pause + notify manager (LangGraph interrupt)

    if decision == "DENY":
        return "state_update"  # Log denial

    return "state_update"
```

**guardrails_route (Guardrails → deliver or block):**
```python
def guardrails_route(state: ParwaGraphState) -> str:
    if state["guardrails_passed"]:
        return "channel_delivery"
    return "state_update"  # Log blocked response, route to Blocked Response Manager
```

---

## 6. Framework Pipeline Architecture

### 6.1 Pipeline Overview — How All Frameworks Chain Together

The framework pipeline is the sequence of processing stages that every customer request passes through. These are NOT independent systems that can be optionally applied — they form a mandatory chain where each stage's output feeds into the next stage's input. The pipeline is implemented as the LangGraph state graph described in Section 5, with each framework corresponding to one or more nodes.

```
┌──────────────────────────────────────────────────────────────────────┐
│              FRAMEWORK PIPELINE — FULL CHAIN                         │
│                                                                      │
│  Customer Message                                                    │
│       │                                                              │
│       ▼                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ 1. PII   │──→│ 2. Empa- │──→│ 3. Smart │──→│ 4. Tech- │        │
│  │ Redaction│   │ thy      │   │ Router   │   │ nique    │        │
│  │          │   │ Engine   │   │ (Model)  │   │ Router   │        │
│  │ Local    │   │ (2-Layer)│   │ LiteLLM  │   │ (10 Sig- │        │
│  │ Python   │   │          │   │ Own Keys │   │  nals)   │        │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘        │
│                                                      │              │
│                                                      ▼              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ 8. Guard-│←──│ 7. DSPy  │←──│ 6. Control│←──│ 5. MAKER │        │
│  │ rails AI │   │ Prompt   │   │ System   │   │ Frame-   │        │
│  │          │   │ Optim.   │   │ (Approval│   │ work     │        │
│  │ Output   │   │          │   │  Gates)  │   │ MAD+FAKE │        │
│  │ Valid.   │   │ Pro/High │   │          │   │ +Red-Flag│        │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘        │
│       │                                                              │
│       ▼                                                              │
│  ┌──────────┐   ┌──────────┐                                        │
│  │ 9. Channel│──→│10. State │──→ END                                │
│  │ Delivery │   │ Update   │                                        │
│  │          │   │ (Audit + │                                        │
│  │ Format + │   │ Agent    │                                        │
│  │ Send     │   │ Lightning│                                        │
│  └──────────┘   └──────────┘                                        │
└──────────────────────────────────────────────────────────────────────┘

Note: The Domain Agent executes BETWEEN the Technique Router (4)
and MAKER (5). The agent uses the model and techniques selected
by the Smart Router and Technique Router to produce its response.
```

### 6.2 Smart Router Architecture (Model Selection)

The Smart Router is responsible for selecting which LLM model to use based on the complexity and nature of the customer request. It uses LiteLLM as a unified proxy layer and Own API Keys (client-provided or system-managed) for all LLM inference. OpenRouter is explicitly NOT used.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    SMART ROUTER ARCHITECTURE                         │
│                                                                      │
│  Input: complexity_score, intent, sentiment, channel, variant_tier  │
│  Output: model_tier, model_name, api_key_reference                  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                 TIER SELECTION LOGIC                      │       │
│  │                                                          │       │
│  │  Complexity 0-4 (Light Tier):                            │       │
│  │  ├── GPT-4o-mini (primary)                               │       │
│  │  ├── Claude-3-Haiku (fallback 1)                         │       │
│  │  └── Gemini-1.5-Flash (fallback 2)                       │       │
│  │                                                          │       │
│  │  Complexity 5-9 (Medium Tier):                           │       │
│  │  ├── GPT-4o (primary)                                    │       │
│  │  ├── Claude-3.5-Sonnet (fallback 1)                      │       │
│  │  └── Gemini-1.5-Pro (fallback 2)                         │       │
│  │                                                          │       │
│  │  Complexity 10+ (Heavy Tier):                            │       │
│  │  ├── Claude-3.5-Sonnet (primary)                         │       │
│  │  ├── GPT-4o (fallback 1)                                 │       │
│  │  └── GPT-4-Turbo (fallback 2)                            │       │
│  │                                                          │       │
│  │  Variant Gate:                                           │       │
│  │  Mini: Light + Medium only (Heavy → Medium fallback)     │       │
│  │  Pro/High: All 3 tiers                                   │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                 SAFETY FAILOVER LOOP                      │       │
│  │                                                          │       │
│  │  Try primary model →                                     │       │
│  │    Rate limit? → Try fallback 1 →                        │       │
│  │      Rate limit? → Try fallback 2 →                      │       │
│  │        All failed? → Log critical alert →                │       │
│  │          Return cached/template response + escalate       │       │
│  │                                                          │       │
│  │  Target: 99.9% uptime across all model providers         │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                 FREE-FIRST ROUTING                        │       │
│  │                                                          │       │
│  │  Default: Route to free/subsidized models for 95% tasks  │       │
│  │  Override: Only use paid models when:                     │       │
│  │    - Complexity > 7                                      │       │
│  │    - Financial actions                                   │       │
│  │    - VIP customers (PARWA High)                          │       │
│  │    - Explicit Heavy Tier requirement                     │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  LiteLLM Integration:                                                │
│  - Unified API for all providers                                     │
│  - Automatic retry + fallback                                        │
│  - Token counting + cost tracking                                    │
│  - Rate limit management                                             │
│  - PII masking (in addition to PII Redaction Agent)                  │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.3 Technique Router Architecture (Reasoning Technique Selection)

The Technique Router is a SEPARATE system from the Smart Router. The Smart Router selects the MODEL; the Technique Router selects the REASONING TECHNIQUE. Both execute on every query, and their outputs combine to determine how the domain agent processes the request.

```
┌──────────────────────────────────────────────────────────────────────┐
│                 TECHNIQUE ROUTER ARCHITECTURE                        │
│                                                                      │
│  Input: 10 signals from ParwaGraphState                              │
│  Output: technique_stack (ordered list of techniques to apply)       │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                 10 INPUT SIGNALS                          │       │
│  │                                                          │       │
│  │  1. Query Complexity Score (0-1.0)                       │       │
│  │  2. Confidence Score (0-1.0)                             │       │
│  │  3. Sentiment Score (-1.0 to +1.0)                      │       │
│  │  4. Customer Tier (standard/VIP/enterprise)              │       │
│  │  5. Monetary Value ($0-$1000+)                           │       │
│  │  6. Conversation Turn Count                              │       │
│  │  7. Intent Type (refund/tech/billing/...)                │       │
│  │  8. Previous Response Status (accepted/rejected/none)    │       │
│  │  9. Reasoning Loop Detection (boolean)                   │       │
│  │ 10. Resolution Path Count (1/2/3+)                       │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                 TRIGGER RULES TABLE                       │       │
│  │                                                          │       │
│  │  Signal Condition          → Technique                   │       │
│  │  ──────────────────────────────────────────────          │       │
│  │  Complexity > 0.4          → Chain of Thought            │       │
│  │  Confidence < 0.7          → Reverse Thinking + Step-Back│       │
│  │  VIP customer              → Universe of Thoughts + Reflex│      │
│  │  Sentiment < 0.3           → Universe of Thoughts + Step │       │
│  │  Monetary > $100           → Self-Consistency            │       │
│  │  Turn count > 5            → Thread of Thought           │       │
│  │  External data needed      → ReAct                      │       │
│  │  Resolution paths ≥ 3      → Tree of Thoughts           │       │
│  │  Strategic decision        → GST (Graph Spatial Thinking)│       │
│  │  Complexity > 0.7          → Least-to-Most              │       │
│  │  Previous response rejected→ Reflexion                  │       │
│  │  Reasoning loop detected   → Step-Back Prompting        │       │
│  │  Billing/Financial intent  → Self-Consistency            │       │
│  │  Technical troubleshooting  → CoT + ReAct               │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                 TIER FILTER (Variant Gate)                │       │
│  │                                                          │       │
│  │  Mini PARWA:                                             │       │
│  │    Only Tier 1 techniques: CLARA, CRP, GSD              │       │
│  │    All Tier 2/3 triggers → ignored, only T1 applied      │       │
│  │                                                          │       │
│  │  PARWA Pro:                                              │       │
│  │    Tier 1 + Tier 2: +CoT, ReAct, Step-Back,             │       │
│  │    Reverse Thinking, Thread of Thought                   │       │
│  │    Tier 3 triggers → ignored                             │       │
│  │                                                          │       │
│  │  PARWA High:                                             │       │
│  │    All Tiers: +GST, UoT, ToT, Self-Consistency,          │       │
│  │    Reflexion, Least-to-Most                              │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │                 TECHNIQUE STACKING ORDER                  │       │
│  │                                                          │       │
│  │  Execution is sequential within each tier:               │       │
│  │                                                          │       │
│  │  Tier 1 (always first):                                  │       │
│  │    CLARA → CRP → GSD State                               │       │
│  │                                                          │       │
│  │  Tier 2 (in trigger table order):                        │       │
│  │    Reverse Thinking → CoT → ReAct → Step-Back →         │       │
│  │    Thread of Thought                                      │       │
│  │                                                          │       │
│  │  Tier 3 (in trigger table order):                        │       │
│  │    GST → UoT → ToT → Self-Consistency →                 │       │
│  │    Reflexion → Least-to-Most                              │       │
│  │                                                          │       │
│  │  Deduplication: If same technique triggered by multiple  │       │
│  │  rules, it appears only once in the stack.               │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Technique Stacking Token Budget:                                    │
│  Tier 1: ~0 tokens overhead (built into base processing)            │
│  Tier 2: ~150-500 tokens per technique                               │
│  Tier 3: ~400-1,700 tokens per technique                             │
│  Total budget: Smart Router factors technique tokens into            │
│  model selection (higher techniques → higher model tier)             │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.4 MAKER Framework Architecture (Zero-Error Execution)

The MAKER Framework implements three pillars that work together to achieve near-zero error rates on complex multi-step operations. It is implemented as the `maker_validator` node in the LangGraph graph.

```
┌──────────────────────────────────────────────────────────────────────┐
│                 MAKER FRAMEWORK ARCHITECTURE                         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  PILLAR 1: MAD (Maximal Agentic Decomposition)           │       │
│  │                                                          │       │
│  │  Input: proposed_action from Domain Agent                 │       │
│  │  Output: list of atomic sub-operations                   │       │
│  │                                                          │       │
│  │  Example — Refund Decomposition:                         │       │
│  │  1. Verify customer identity                             │       │
│  │  2. Retrieve order details                               │       │
│  │  3. Check refund eligibility                             │       │
│  │  4. Calculate refund amount                              │       │
│  │  5. Verify payment method                                │       │
│  │  6. Request approval (Control System)                    │       │
│  │  7. Execute refund                                       │       │
│  │  8. Send confirmation                                    │       │
│  │  9. Update records                                       │       │
│  │                                                          │       │
│  │  Each sub-operation has:                                 │       │
│  │  - Pre-conditions (what must be true before)             │       │
│  │  - Post-conditions (what must be true after)             │       │
│  │  - Rollback action (how to undo if later step fails)     │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  PILLAR 2: FAKE (First-to-Ahead-by-K Error Correction)   │       │
│  │                                                          │       │
│  │  Input: decomposed sub-operations + agent_response        │       │
│  │  Output: k_solutions + selected_solution                  │       │
│  │                                                          │       │
│  │  Process:                                                │       │
│  │  1. Generate K alternative solutions IN PARALLEL          │       │
│  │     (each is a complete path through the sub-operations)  │       │
│  │  2. Evaluate each solution on 4 dimensions:              │       │
│  │     - Policy compliance (0-100%)                         │       │
│  │     - Customer satisfaction prediction (0-100%)          │       │
│  │     - Risk assessment alignment (0-100%)                 │       │
│  │     - Factual accuracy verification (0-100%)            │       │
│  │  3. Select FIRST solution that demonstrates clear        │       │
│  │     superiority across all dimensions                     │       │
│  │  4. If no clear winner → escalate to human               │       │
│  │                                                          │       │
│  │  K-Values by Variant Tier:                               │       │
│  │  Mini: K=3 (Efficiency Mode)                             │       │
│  │  Pro: K=3-5 (Balanced Mode)                              │       │
│  │  High: K=5-7 (Conservative Mode)                         │       │
│  │                                                          │       │
│  │  K-Value by Action Type (overrides tier default):        │       │
│  │  Standard queries: K=3                                   │       │
│  │  High-stakes financial: K=5                              │       │
│  │  Critical irreversible: K=7                              │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  PILLAR 3: Red-Flagging System                           │       │
│  │                                                          │       │
│  │  Real-time anomaly detection on the selected solution:   │       │
│  │                                                          │       │
│  │  Category A (Immediate Halt):                            │       │
│  │  - Confidence < 60%                                      │       │
│  │  - Contradictions with Knowledge Base                    │       │
│  │  - Severe customer dissatisfaction risk                  │       │
│  │  - Policy violations detected                            │       │
│  │  → Action: Route to Escalation Agent immediately         │       │
│  │                                                          │       │
│  │  Category B (Enhanced Review):                           │       │
│  │  - Unusual patterns detected                             │       │
│  │  - High-value transactions                               │       │
│  │  - VIP customers                                         │       │
│  │  - New query types never seen before                     │       │
│  │  → Action: Force ASK_HUMAN in Control System             │       │
│  │                                                          │       │
│  │  Category C (Log and Monitor):                           │       │
│  │  - Slight deviations from expected patterns              │       │
│  │  - Edge cases not covered by KB                          │       │
│  │  → Action: Log to audit trail, proceed normally          │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Performance Targets:                                                │
│  Error rate: 3-5% → 0.3-0.8% (6-16x improvement)                   │
│  Escalation rate: 8-12% → 2-4%                                      │
│  Resolution accuracy: 94% → 99.2%                                   │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.5 Control System Architecture (Approval Gates)

The Control System is the safety gate that determines whether an AI action can be executed autonomously, needs batching, requires individual manager approval, or must be escalated. It implements hard-coded rules (Money Rule, VIP Rule, Newness Rule) that CANNOT be overridden by configuration.

```
┌──────────────────────────────────────────────────────────────────────┐
│                 CONTROL SYSTEM ARCHITECTURE                          │
│                                                                      │
│  Input: agent_confidence, action_type, customer_tier, red_flag,     │
│         dnd_rules, system_mode                                       │
│  Output: approval_decision, confidence_breakdown, system_mode        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  STEP 1: Check DND Rules (Auto-Execute List)             │       │
│  │                                                          │       │
│  │  If action_type in DND_LIST → EXECUTE immediately        │       │
│  │  DND_LIST: FAQ answers, order status, tracking links,    │       │
│  │  product info, password reset links, ticket routing      │       │
│  │  (No approval needed, just log and execute)               │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │ (not DND)                                  │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  STEP 2: Check Hard-Coded Rules (BC-007 Immutable)       │       │
│  │                                                          │       │
│  │  Money Rule: action_type in [REFUND, CREDIT]             │       │
│  │    → ASK_HUMAN (always, no exception)                    │       │
│  │                                                          │       │
│  │  VIP Rule: customer_tier == VIP                          │       │
│  │    → ASK_HUMAN (always, no exception)                    │       │
│  │                                                          │       │
│  │  Newness Rule: agent_confidence < 0.70                   │       │
│  │    → ASK_HUMAN (always, no exception)                    │       │
│  │                                                          │       │
│  │  These rules are HARD-CODED in source. CI fails if       │       │
│  │  modified. NOT configurable via DB, env, or admin.       │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │ (no hard rule triggered)                   │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  STEP 3: Calculate Confidence Score                      │       │
│  │                                                          │       │
│  │  confidence = (pattern_match * 0.40) +                   │       │
│  │              (policy_alignment * 0.30) +                  │       │
│  │              (historical_success * 0.20) +                │       │
│  │              (risk_signals * 0.10)                        │       │
│  │                                                          │       │
│  │  Signal Expiration: fraud signals > 180 days → ignored   │       │
│  │  Pattern Match: Has this exact pattern been seen?        │       │
│  │  Policy Alignment: Does action comply with tenant rules? │       │
│  │  Historical Success: What % of similar actions worked?   │       │
│  │  Risk Signals: Any fraud/abuse indicators?               │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  STEP 4: Decision Based on Confidence                    │       │
│  │                                                          │       │
│  │  >95% → EXECUTE (auto-handle with logging)              │       │
│  │  85-95% → BATCH (group with similar requests)           │       │
│  │  70-84% → ASK_HUMAN (individual manager review)         │       │
│  │  <70% → ESCALATE (immediate human judgment)             │       │
│  │                                                          │       │
│  │  Red-Flag Override:                                      │       │
│  │  Cat B red-flag → forces ASK_HUMAN regardless           │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  STEP 5: System Mode Check                               │       │
│  │                                                          │       │
│  │  Shadow Mode: AI observes, takes NO real-world action    │       │
│  │    → All decisions become ASK_HUMAN                      │       │
│  │    → Used for initial deployment and testing             │       │
│  │                                                          │       │
│  │  Supervised Mode: AI acts but stops at Approval Gates    │       │
│  │    → Normal operation for most tenants                   │       │
│  │                                                          │       │
│  │  Graduated Mode: AI acts autonomously on proven tasks    │       │
│  │    → EXECUTE allowed for tasks with >95% confidence      │       │
│  │    → NEVER auto-executes money/VIP actions               │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Batch Approval Integration:                                         │
│  When decision = BATCH, the request is added to the Batch Approval  │
│  Queue. Semantic clustering groups similar requests. Managers see    │
│  batches with: confidence range, risk indicator, reason summary,    │
│  common pattern. Batch commands: Approve Selected, Reject Batch,    │
│  Automate This Rule, Simulate (Shadow New Type).                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.6 Framework Cross-Cutting Interactions

The frameworks do not operate in isolation. They interact in specific ways that are architecturally significant:

| From Framework | To Framework | Interaction | Implementation |
|---------------|-------------|-------------|----------------|
| Empathy Engine | Smart Router | High anger forces Heavy Tier even for simple queries | `sentiment_score < -0.5` → override `model_tier` to "heavy" |
| Empathy Engine | Technique Router | Sentiment < 0.3 triggers UoT + Step-Back | Technique Router reads `sentiment_score` as input signal |
| Smart Router | Technique Router | Model selected determines technique token budget | Heavy Tier → allow all techniques; Light Tier → Tier 1 only |
| Technique Router | MAKER | Technique stacking feeds into K-value selection | If Self-Consistency in stack → K += 2 |
| MAKER | Control System | Red-flag Cat A auto-sets confidence < 60% | Red-flag Cat A → bypass Control System → escalate |
| MAKER | Control System | Red-flag Cat B forces ASK_HUMAN | Cat B → `approval_decision = ASK_HUMAN` |
| Control System | Agent Lightning | Every approve/reject → reward signal | Approved → positive_reward, Rejected → negative_reward |
| Agent Lightning | Smart Router | Trained model replaces default in tier | New model version → update LiteLLM config for that agent type |
| Agent Lightning | Technique Router | Learns which techniques work best per query type | Pattern rules → update trigger thresholds |
| DSPy | Technique Router | Optimized prompts may change technique triggers | New prompt version → re-evaluate trigger rules |
| Guardrails | Blocked Response Mgr | Blocked responses → admin review queue | Guardrails block → create `blocked_responses` table entry |
| Variant Tier | Everything | Tier gates which frameworks/techniques available | Variant Resolver middleware sets `variant_tier` in state |

---

## 7. Variant Tier Architecture

### 7.1 Variant Enforcement Architecture

The variant tier system is enforced at three levels: API middleware, LangGraph orchestration, and frontend feature flags. This three-layer enforcement ensures that no variant-restricted feature can be accessed regardless of the entry point.

```
┌──────────────────────────────────────────────────────────────────────┐
│              VARIANT ENFORCEMENT — THREE LAYERS                      │
│                                                                      │
│  LAYER 1: API Middleware (Backend)                                   │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  @require_tier("pro")                                    │       │
│  │  async def create_voice_call(...):                        │       │
│  │      # This endpoint returns 403 + upgrade CTA           │       │
│  │      # if tenant variant_tier < "pro"                    │       │
│  │      ...                                                  │       │
│  │                                                          │       │
│  │  Implementation:                                          │       │
│  │  - Variant Resolver middleware loads tenant tier from     │       │
│  │    companies table on every request                       │       │
│  │  - @require_tier decorator checks tier before handler     │       │
│  │  - Returns 403 with upgrade CTA if insufficient tier      │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  LAYER 2: LangGraph Orchestration (Agent Level)                     │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Router Agent checks variant_tier before routing:         │       │
│  │  - Voice Agent requires "pro" → Mini tenants skip         │       │
│  │  - Billing Agent requires "pro" → Mini tenants escalate   │       │
│  │  - Video Agent requires "high" → Pro tenants skip         │       │
│  │  - Quality Coach requires "high" → Pro tenants skip       │       │
│  │                                                          │       │
│  │  Technique Router filters by tier:                        │       │
│  │  - Mini: Tier 1 techniques only                          │       │
│  │  - Pro: Tier 1 + Tier 2 techniques                       │       │
│  │  - High: All techniques                                  │       │
│  │                                                          │       │
│  │  MAKER K-values by tier:                                  │       │
│  │  - Mini: K=3, Pro: K=3-5, High: K=5-7                   │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  LAYER 3: Frontend Feature Flags (UI Level)                         │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  useVariant() hook returns current tier + feature map     │       │
│  │  Components conditionally render based on tier:           │       │
│  │                                                          │       │
│  │  {variant.tier >= "pro" && <VoiceCallButton />}          │       │
│  │  {variant.tier >= "high" && <QualityCoachPanel />}       │       │
│  │                                                          │       │
│  │  Locked features show:                                   │       │
│  │  <LockedFeature requiredTier="pro">                      │       │
│  │    <UpgradeCTA />                                        │       │
│  │  </LockedFeature>                                        │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

### 7.2 Complete Variant Feature Matrix

| Feature / Capability | Mini PARWA ($999/mo) | PARWA Pro ($2,499/mo) | PARWA High ($3,999/mo) |
|---------------------|:--------------------:|:---------------------:|:----------------------:|
| **Channels** | Chat + Email | + SMS + Voice | + Video |
| **AI Agent Instances** | 5 max | 15 max | 50 max |
| **Smart Router Tiers** | Light + Medium | All 3 | All 3 + Priority |
| **Technique Router** | Tier 1 only | Tier 1 + Tier 2 | All Tiers |
| **MAKER K-Values** | K=3 (Efficiency) | K=3-5 (Balanced) | K=5-7 (Conservative) |
| **Agent Lightning** | Weekly training | Weekly training | Weekly + Quality Coach |
| **Jarvis Command Center** | Basic commands | + Co-Pilot + Provisioning | + Self-Healing |
| **Voice Calls** | — | Incoming + Outbound + Demo | + Advanced (VoiceGuard, AARM) |
| **Ticket Management** | Basic (create, assign, status) | Full (search, bulk, intent) | Full + AI Draft + Blocked Mgr |
| **Batch Approval** | — | Basic clustering | + Auto-approve rules |
| **Analytics** | Overview + Metrics | + Trends + ROI | + Drift + Quality Coach |
| **Empathy Engine** | Basic sentiment badge | Full sentiment routing | Full + De-escalation |
| **Integrations** | 3 pre-built | 10 + Custom REST | Unlimited + MCP + Webhook + DB |
| **Knowledge Base** | 1,000 docs | 10,000 docs | Unlimited + Auto-ingestion |
| **DSPy Optimization** | — | Yes | Yes + A/B Testing |
| **Guardrails AI** | Basic (hallucination) | Full | Full + Custom rules |
| **Safety Systems** | PII Redaction | + VoiceGuard + Fairness | + HNTN + AARM + Universal Access |
| **Data Retention** | Hot:30d / Cold:90d | Hot:90d / Cold:1yr | Hot:1yr / Cold:3yr |
| **API Rate Limits** | 100 req/min | 500 req/min | 2,000 req/min |
| **File Storage** | 5 GB | 50 GB | 500 GB |
| **Support** | Standard (email) | Priority (chat) | Dedicated (chat + voice) |

### 7.3 Hard Limits vs Soft Limits

| Resource | Type | Mini | Pro | High | Enforcement |
|----------|------|------|-----|------|-------------|
| Agent instances | Hard | 5 | 15 | 50 | DB check + API 403 |
| File storage | Hard | 5 GB | 50 GB | 500 GB | S3 quota + API 403 |
| Knowledge base docs | Hard | 1,000 | 10,000 | Unlimited | DB count check |
| API rate limit | Soft | 100/min | 500/min | 2,000/min | Redis counter + 429 |
| Data retention | Soft | 30/90d | 90/365d | 365/1095d | Celery cleanup job |
| Voice concurrent calls | Hard | 0 | 5 | 20 | Redis semaphore |

### 7.4 Overage Policy

Overage is NOT allowed by default. When a tenant hits a hard limit, the system returns a clear error with an upgrade CTA. The only exception is API rate limits (soft limit) where requests above the limit receive a 429 response with a Retry-After header, but are not charged extra.

---

## 8. Jarvis Architecture

### 8.1 Jarvis System Overview — Two Separate Systems

Jarvis is actually TWO architecturally distinct systems that share the same name and visual design language but operate on completely different data, contexts, and lifecycle stages:

```
┌──────────────────────────────────────────────────────────────────────┐
│              JARVIS — TWO SYSTEMS, ONE NAME                          │
│                                                                      │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐  │
│  │  JARVIS COMMAND CENTER      │  │  JARVIS ONBOARDING SYSTEM   │  │
│  │  (Post-Purchase)            │  │  (Pre-Purchase)             │  │
│  │                             │  │                             │  │
│  │  Purpose: Manager control   │  │  Purpose: Sales + Demo      │  │
│  │  Users: Tenant managers     │  │  Users: Prospects           │  │
│  │  Auth: Tenant JWT           │  │  Auth: Session cookie       │  │
│  │  LLM: Tenant's Smart Router│  │  LLM: Dedicated Light/Med   │  │
│  │  Data: Tenant's data only   │  │  Data: Product knowledge    │  │
│  │  Scope: Own tenant only     │  │  Scope: Public + session    │  │
│  │  Session: Persistent        │  │  Session: Ephemeral         │  │
│  │  Agent: jarvis_command      │  │  Agent: onboarding_jarvis   │  │
│  │  Route: /dashboard/jarvis   │  │  Route: /onboarding         │  │
│  └─────────────────────────────┘  └─────────────────────────────┘  │
│                                                                      │
│  After purchase, Onboarding Jarvis hands off to Command Center:     │
│  Onboarding Jarvis → Handoff Agent → Customer Care Jarvis           │
│  (Selectively transfers: variants, business info, industry)         │
│  (Does NOT transfer: chat history, onboarding conversations)        │
└──────────────────────────────────────────────────────────────────────┘
```

### 8.2 Jarvis Command Center Architecture

The Jarvis Command Center is the manager's primary interface for controlling the AI workforce. It is implemented as a WebSocket-based chat interface backed by the Jarvis Command Agent.

```
┌──────────────────────────────────────────────────────────────────────┐
│              JARVIS COMMAND CENTER — INTERNALS                        │
│                                                                      │
│  Frontend (Next.js):                                                │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  ┌────────────────┐  ┌────────────────┐                  │       │
│  │  │ Chat Input     │  │ Terminal Feed  │                  │       │
│  │  │ (natural lang) │  │ (GSD steps)    │                  │       │
│  │  └───────┬────────┘  └───────┬────────┘                  │       │
│  │          │                   │                            │       │
│  │  ┌───────┴───────────────────┴────────┐                  │       │
│  │  │      WebSocket Connection          │                  │       │
│  │  └───────────────┬────────────────────┘                  │       │
│  │                  │                                         │       │
│  │  ┌───────────────┴────────────────────┐                  │       │
│  │  │    Quick Command Buttons           │                  │       │
│  │  │  "Pause All" | "Export" | "Health" │                  │       │
│  │  │  + Tenant-customizable (max 50)    │                  │       │
│  │  └────────────────────────────────────┘                  │       │
│  │                                                          │       │
│  │  ┌──────────┐ ┌──────────────┐ ┌─────────────────┐     │       │
│  │  │ Live     │ │ System Status│ │ Last 5 Errors   │     │       │
│  │  │ Activity │ │ Panel        │ │ Panel           │     │       │
│  │  │ Feed     │ │ (subsystems) │ │ + Train from    │     │       │
│  │  │ (color)  │ │              │ │   Error btn     │     │       │
│  │  └──────────┘ └──────────────┘ └─────────────────┘     │       │
│  │                                                          │       │
│  │  System Mode Badge: [Shadow] / [Supervised] / [Graduated]│     │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼ WebSocket                                  │
│  Backend (FastAPI):                                                 │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Jarvis Command Agent (Light Tier LLM)                    │       │
│  │                                                          │       │
│  │  1. Parse natural language → structured command           │       │
│  │     "pause refunds" → {action: pause, target: refunds}    │       │
│  │                                                          │       │
│  │  2. Validate command                                     │       │
│  │     - Is user a manager? (auth check)                    │       │
│  │     - Does tenant tier support this command? (variant)    │       │
│  │     - Is command within tenant scope? (RLS)              │       │
│  │                                                          │       │
│  │  3. Execute command                                      │       │
│  │     Map to backend service function                       │       │
│  │                                                          │       │
│  │  4. Format response                                      │       │
│  │     Chat message + Terminal steps + UI updates            │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Command Registry:                                                   │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Command          │ Handler Service     │ Min Tier        │       │
│  │  ─────────────────────────────────────────────────        │       │
│  │  pause refunds    │ control_service     │ mini            │       │
│  │  resume refunds   │ control_service     │ mini            │       │
│  │  pause all AI     │ control_service     │ mini            │       │
│  │  show ticket      │ ticket_service      │ mini            │       │
│  │  check health     │ system_service      │ mini            │       │
│  │  export report    │ analytics_service   │ mini            │       │
│  │  escalate urgent  │ ticket_service      │ mini            │       │
│  │  add agents       │ agent_service       │ pro             │       │
│  │  call customer    │ voice_service       │ pro             │       │
│  │  co-pilot draft   │ jarvis_service      │ pro             │       │
│  │  auto-approve     │ control_service     │ pro             │       │
│  │  undo last rule   │ control_service     │ pro             │       │
│  │  train from error │ agent_lightning     │ pro             │       │
│  │  self-heal        │ system_service      │ high            │       │
│  │  quality report   │ quality_coach       │ high            │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

### 8.3 Jarvis Onboarding System Architecture

The Jarvis Onboarding System serves as the pre-purchase sales demo and onboarding guide. It is architecturally isolated from the Command Center — it has its own session management, knowledge base, and agent configuration.

```
┌──────────────────────────────────────────────────────────────────────┐
│              JARVIS ONBOARDING SYSTEM — INTERNALS                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │              5 ENTRY PATHS                                │       │
│  │                                                          │       │
│  │  1. Direct Chat      → /onboarding (fresh session)       │       │
│  │  2. Demo Booking     → /onboarding?entry=demo_booking    │       │
│  │  3. ROI Calculator   → /onboarding?entry=roi             │       │
│  │  4. Pricing Page     → /onboarding?entry=pricing         │       │
│  │  5. Demo Pack Active → /onboarding?pack=active           │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         CONVERSATION STATE MACHINE (8 stages)             │       │
│  │                                                          │       │
│  │  WELCOME → DISCOVERY → DEMO → PRICING → BILL_REVIEW     │       │
│  │      → VERIFICATION → PAYMENT → HANDOFF                  │       │
│  │                                                          │       │
│  │  Pre-buy: Non-linear (user can jump between stages)      │       │
│  │  Post-buy: Linear and fixed (verification → payment →    │       │
│  │            handoff in order)                              │       │
│  │                                                          │       │
│  │  Stage detection: Onboarding Jarvis detects stage         │       │
│  │  from conversation context, not explicit user action      │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         7-LAYER SYSTEM PROMPT BUILDER                     │       │
│  │                                                          │       │
│  │  Layer 1: Base Persona (friendly, knowledgeable guide)   │       │
│  │  Layer 2: Product Knowledge (10 JSON files)              │       │
│  │           pricing_tiers, industry_variants,              │       │
│  │           variant_details, integrations, capabilities,   │       │
│  │           demo_scenarios, objection_handling, faq,       │       │
│  │           competitor_comparisons, edge_cases             │       │
│  │  Layer 3: Industry-Specific Knowledge                    │       │
│  │  Layer 4: Session Context (current stage, entry path)    │       │
│  │  Layer 5: Relevant Knowledge (based on current query)    │       │
│  │  Layer 6: Stage Behavior Instructions                    │       │
│  │  Layer 7: Information Boundary Rules                     │       │
│  │           CAN reveal: features, how-it-works, pricing    │       │
│  │           CANNOT reveal: GSD internals, models, RAG,     │       │
│  │           prompt engineering, other clients' data        │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         MESSAGE LIMITING & DEMO PACK                      │       │
│  │                                                          │       │
│  │  Free Tier:                                              │       │
│  │  - 20 messages/day, resets at midnight (user timezone)   │       │
│  │  - Context persists across resets                        │       │
│  │  - Limit reached → "Come back tomorrow" OR Demo Pack CTA │       │
│  │                                                          │       │
│  │  Demo Pack ($1 via Paddle):                              │       │
│  │  - One-time $1 payment                                   │       │
│  │  - 500 chat messages                                     │       │
│  │  - 3-minute AI voice call                                │       │
│  │  - 24-hour validity from purchase                        │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         ACTION TICKET SYSTEM (9 types)                    │       │
│  │                                                          │       │
│  │  otp_verification    → OtpVerificationCard               │       │
│  │  otp_verified        → Status update                     │       │
│  │  payment_demo_pack   → PaymentCard ($1)                  │       │
│  │  payment_variant     → PaymentCard (variant price)       │       │
│  │  payment_variant_completed → BillSummaryCard             │       │
│  │  demo_call           → DemoCallCard                      │       │
│  │  demo_call_completed → PostCallSummaryCard               │       │
│  │  roi_import          → BillSummaryCard                    │       │
│  │  handoff             → HandoffCard                       │       │
│  │                                                          │       │
│  │  Status indicators:                                      │       │
│  │  gray circle = pending                                   │       │
│  │  amber spinning = in_progress                            │       │
│  │  green checkmark = completed                             │       │
│  │  red X = failed                                          │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         RICH CARD RENDERER (12 card types)                │       │
│  │                                                          │       │
│  │  BillSummaryCard | PaymentCard | OtpVerificationCard     │       │
│  │  DemoCallCard | HandoffCard | MessageCounter             │       │
│  │  DemoPackCTA | LimitReachedCard | PackExpiredCard        │       │
│  │  ActionTicketCard | PostCallSummaryCard | RechargeCTA    │       │
│  │                                                          │       │
│  │  These are React components rendered INSIDE the chat      │       │
│  │  stream. Not plain text — interactive UI elements.        │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         DEMO CALL FLOW (12 steps)                         │       │
│  │                                                          │       │
│  │  1. User agrees to demo call                             │       │
│  │  2. User provides phone number                           │       │
│  │  3. OtpVerificationCard renders (Twilio, 4-digit, 5-min) │       │
│  │  4. User enters OTP (max 3 attempts)                     │       │
│  │  5. OTP verified                                         │       │
│  │  6. PaymentCard renders ($1 for 3 min, via Paddle)       │       │
│  │  7. Payment confirmed                                    │       │
│  │  8. Call initiated (Twilio Voice API)                    │       │
│  │  9. Live timer card renders                              │       │
│  │  10. Call ends                                           │       │
│  │  11. PostCallSummaryCard renders                         │       │
│  │  12. ROI info card + RechargeCTA                         │       │
│  │                                                          │       │
│  │  Entire flow happens INSIDE /onboarding chat             │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │                                            │
│                         ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │         HANDOFF TO CUSTOMER CARE                          │       │
│  │                                                          │       │
│  │  After successful variant payment:                       │       │
│  │  1. Onboarding Jarvis delivers personalized farewell     │       │
│  │  2. Introduces Customer Care Jarvis                      │       │
│  │  3. New customer_care session created                    │       │
│  │  4. Selective context transfer:                          │       │
│  │     Transferred: hired_variants, business_info, industry │       │
│  │     NOT transferred: chat history, onboarding convos     │       │
│  │  5. Onboarding chat preserved as read-only archive       │       │
│  │  6. Customer Care Jarvis has no memory of onboarding     │       │
│  │                                                          │       │
│  │  Session Persistence:                                    │       │
│  │  - Close/reopen browser → previous chat loads            │       │
│  │  - Two devices → same session (API sync)                 │       │
│  │  - 30+ days inactive → auto-archived                     │       │
│  │  - Payment page refresh → session preserved              │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Channel Architecture

### 9.1 Channel Adapter Pattern

All customer-facing channels use a unified Channel Adapter pattern that normalizes input to a standard format before entering the LangGraph pipeline. This ensures the same processing pipeline handles every channel consistently.

```
┌──────────────────────────────────────────────────────────────────────┐
│              CHANNEL ADAPTER PATTERN                                  │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  Chat    │  │  Email   │  │   SMS    │  │  Voice   │           │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │  │ Adapter  │           │
│  │          │  │          │  │          │  │          │           │
│  │WebSocket │  │Brevo     │  │Twilio    │  │Twilio    │           │
│  │Socket.io │  │Inbound   │  │SMS       │  │Voice     │           │
│  │          │  │Webhook   │  │Webhook   │  │WebSocket │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘           │
│       │             │             │             │                   │
│       ▼             ▼             ▼             ▼                   │
│  ┌─────────────────────────────────────────────────────────┐       │
│  │              STANDARDIZED REQUEST FORMAT                 │       │
│  │                                                          │       │
│  │  {                                                       │       │
│  │    channel: "chat" | "email" | "sms" | "voice" | "video"│       │
│  │    message: str,                                         │       │
│  │    customer_id: str,                                     │       │
│  │    tenant_id: str,                                       │       │
│  │    metadata: {                                           │       │
│  │      email_subject, from_address, thread_id,             │       │
│  │      phone_number, call_sid, media_urls,                 │       │
│  │      ... channel-specific fields                         │       │
│  │    }                                                     │       │
│  │  }                                                       │       │
│  └─────────────────────────────────────────────────────────┘       │
│       │                                                             │
│       ▼                                                             │
│  LANGGRAPH PIPELINE (same for all channels)                        │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  Chat    │  │  Email   │  │   SMS    │  │  Voice   │           │
│  │ Delivery │  │ Delivery │  │ Delivery │  │ Delivery │           │
│  │          │  │          │  │          │  │          │           │
│  │WebSocket │  │Celery→   │  │Celery→   │  │TTS→Twilio│           │
│  │push      │  │Brevo API │  │Twilio API│  │Media Strm│           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
└──────────────────────────────────────────────────────────────────────┘
```

### 9.2 Channel-Specific Architecture

**Chat Channel:** Real-time bidirectional communication via Socket.io. Messages are pushed instantly to the customer widget. The chat adapter handles connection management, reconnection, and message ordering. Customer widget is embedded in the tenant's website via a JavaScript snippet. Supports rich messages (images, buttons, quick replies). Typing indicators show when the AI is processing.

**Email Channel:** Inbound emails are received via Brevo Inbound Parse webhook, which forwards raw email data to a FastAPI endpoint. The Email Adapter parses headers, extracts body text, handles HTML stripping, and normalizes attachments. Outbound emails use Celery tasks to call Brevo API with Jinja2 templates. Rate limits: 5 replies per thread per 24 hours (hard cap), 100 emails per company per day. Out-of-office and auto-reply detection prevents AI from treating automated responses as customer inquiries.

**SMS Channel:** Inbound SMS arrives via Twilio SMS webhook. The SMS Adapter parses the message body, handles multipart messages, and checks opt-in/opt-out status before processing. Outbound SMS is sent via Celery tasks calling Twilio API. TCPA compliance is enforced: no messages to opted-out numbers, opt-out keywords (STOP, UNSUBSCRIBE) are processed immediately, opt-in records are maintained with timestamps. Character limits are respected (160 chars per segment, with proper segmentation for longer messages).

**Voice Channel:** Voice calls use Twilio Voice API with WebSocket media streams for real-time audio. The Voice Adapter handles IVR menus, speech-to-text (STT) transcription, and text-to-speech (TTS) synthesis. The Voice-First Rule (hard-coded) ensures that incoming calls are always answered with voice first. Model selection for voice follows a specific pattern: initial greeting is pre-generated (no AI), intent classification uses Light Tier, conversation uses Medium Tier, and complex decisions use Heavy Tier. Post-call summaries are generated and stored. Warm transfers coordinate between AI and human agents. Demo calls (Onboarding Jarvis) follow the 12-step flow with OTP verification and payment via Paddle.

**Video Channel (PARWA High only):** Video calls extend the voice architecture with real-time video streams, screen sharing, and visual context analysis. Limited concurrent sessions due to compute intensity. Uses WebRTC for peer-to-peer video with a Twilio Video signaling server.

### 9.3 Channel Availability by Variant Tier

| Channel | Mini PARWA | PARWA Pro | PARWA High |
|---------|:----------:|:---------:|:----------:|
| Chat | ✅ | ✅ | ✅ |
| Email | ✅ | ✅ | ✅ |
| SMS | — | ✅ | ✅ |
| Voice | — | ✅ | ✅ |
| Video | — | — | ✅ |

---

## 10. Data Architecture

### 10.1 Database Strategy

PARWA uses a shared PostgreSQL database (via Supabase) with Row-Level Security (RLS) for multi-tenant data isolation. This approach provides the best balance of cost-efficiency, operational simplicity, and data isolation for V1.

```
┌──────────────────────────────────────────────────────────────────────┐
│              DATABASE STRATEGY                                        │
│                                                                      │
│  Primary Database: PostgreSQL (Supabase)                             │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  - 90+ tables                                            │       │
│  │  - pgvector extension for vector embeddings              │       │
│  │  - RLS policies on every tenant-scoped table             │       │
│  │  - Full-text search (tsvector + trigram)                 │       │
│  │  - JSONB columns for flexible metadata                  │       │
│  │  - Migration system (Alembic)                            │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Cache Layer: Redis                                                  │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  - GSD state (primary, PG fallback per BC-008)           │       │
│  │  - Session management                                    │       │
│  │  - Rate limiting counters                                │       │
│  │  - Pub/Sub for real-time events                          │       │
│  │  - Celery task broker                                    │       │
│  │  - Key format: parwa:{company_id}:{resource}:{id}        │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  File Storage: S3-Compatible (Supabase Storage)                     │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  - Knowledge base documents                              │       │
│  │  - Training data exports                                 │       │
│  │  - Report exports                                        │       │
│  │  - Email attachments                                     │       │
│  │  - Voice call recordings                                 │       │
│  │  - Per-tenant bucket isolation                           │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

### 10.2 Core Data Domains (Table Groups)

The 90+ tables are organized into logical domains:

| Domain | Key Tables | Purpose |
|--------|-----------|---------|
| **Auth & Users** | companies, users, roles, permissions, mfa_secrets, sessions | Authentication, authorization, multi-tenant management |
| **Variant & Billing** | subscriptions, plans, invoices, payments, usage_records, api_keys | Variant tiers, Paddle integration, usage tracking |
| **GSD State** | conversations, gsd_states, conversation_messages, context_compressions | Conversation state, GSD engine data |
| **Tickets** | tickets, ticket_comments, ticket_assignments, ticket_tags, ticket_history | Complete ticket lifecycle |
| **Agent Pool** | agent_pool, agent_configs, agent_metrics, training_data, model_versions | Agent instances, config, performance, training |
| **Knowledge Base** | knowledge_bases, kb_documents, kb_chunks, embeddings | KB documents, chunking, vector embeddings |
| **Integrations** | integrations, integration_configs, webhook_events, mcp_servers | Third-party integrations, webhooks, MCP |
| **Control System** | approval_requests, approval_decisions, batch_clusters, auto_approve_rules, dnd_rules | Approval gates, confidence scores, DND rules |
| **Audit** | audit_logs, decision_logs, action_logs, error_logs | Complete audit trail for compliance |
| **Analytics** | metrics_daily, metrics_hourly, trend_data, roi_calculations | Aggregated metrics and reporting |
| **Voice** | calls, call_recordings, call_transcripts, ivr_menus | Voice call handling and records |
| **SMS** | sms_messages, sms_opt_ins, sms_templates | SMS conversation records |
| **Email** | email_threads, email_messages, email_templates | Email conversation records |
| **Onboarding** | onboarding_sessions, onboarding_action_tickets, demo_packs | Pre-purchase onboarding data |
| **Safety** | blocked_responses, guardrails_rules, red_flags, pii_redaction_log | Safety system records |
| **System** | system_health, celery_task_results, langgraph_checkpoints, building_codes | System-level data |

### 10.3 Key Table Schemas

**companies table:**
```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    variant_tier VARCHAR(20) NOT NULL DEFAULT 'mini',  -- mini | pro | high
    industry VARCHAR(50),
    onboarding_status VARCHAR(50) DEFAULT 'pending',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**tickets table:**
```sql
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    ticket_number VARCHAR(20) UNIQUE NOT NULL,  -- e.g., TK-000001
    channel VARCHAR(20) NOT NULL,  -- chat | email | sms | voice | video
    customer_id UUID REFERENCES customers(id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending_approval',
    ticket_type VARCHAR(50),  -- refund | technical | billing | complaint | faq | feature_request | general
    intent VARCHAR(50),
    urgency VARCHAR(20),  -- urgent | routine | informational
    assigned_agent_id UUID REFERENCES agent_pool(id),
    ai_confidence FLOAT,
    ai_reasoning TEXT,
    sentiment_score FLOAT,
    complexity_score FLOAT,
    title TEXT,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
```

**agent_pool table:**
```sql
CREATE TABLE agent_pool (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    agent_type VARCHAR(50) NOT NULL,  -- faq | refund | technical | billing | ...
    status VARCHAR(20) DEFAULT 'active',  -- active | draining | inactive
    model_tier VARCHAR(20),  -- light | medium | heavy
    system_prompt_version VARCHAR(50),
    config JSONB DEFAULT '{}',
    current_load INT DEFAULT 0,
    max_capacity INT DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**training_data table:**
```sql
CREATE TABLE training_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    agent_type VARCHAR(50) NOT NULL,
    prompt TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    human_correction TEXT,
    reward_signal VARCHAR(20) NOT NULL,  -- positive | negative
    decision_type VARCHAR(50),
    ai_recommendation TEXT,
    manager_action VARCHAR(50),
    manager_reason TEXT,
    context JSONB DEFAULT '{}',
    pattern_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 10.4 Row-Level Security (RLS)

Every tenant-scoped table has RLS policies ensuring that tenants can only access their own data:

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_pool ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_data ENABLE ROW LEVEL SECURITY;
-- ... all 90+ tables

-- Standard tenant isolation policy
CREATE POLICY tenant_isolation ON tickets
    USING (company_id = current_setting('app.current_tenant')::UUID);

-- Service role bypass (for system-level operations)
CREATE POLICY service_role_bypass ON tickets
    FOR ALL TO service_role USING (true);
```

Application-level enforcement: The Variant Resolver middleware sets `app.current_tenant` on every database connection based on the authenticated user's company_id. This ensures that even if application code forgets to filter by company_id, the database enforces isolation.

### 10.5 Vector Store Architecture (pgvector)

PARWA uses pgvector for knowledge base semantic search, ticket clustering, and batch approval similarity matching:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Knowledge base chunks with embeddings
CREATE TABLE kb_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id),
    document_id UUID NOT NULL REFERENCES kb_documents(id),
    chunk_text TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding vector(1536),  -- OpenAI ada-002 dimensions
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vector similarity search index
CREATE INDEX ON kb_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Ticket clustering for batch approval
CREATE TABLE ticket_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id),
    embedding vector(1536),
    cluster_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 10.6 Data Retention Architecture

Data retention follows a 3-tiered architecture per Building Code requirements:

| Tier | Mini | Pro | High | Storage | Access |
|------|------|-----|------|---------|--------|
| **Hot** | 30 days | 90 days | 1 year | PostgreSQL | Full query + search |
| **Cold** | 90 days | 1 year | 3 years | S3 (Parquet) | Export + restore on demand |
| **Deleted** | After cold expires | After cold expires | After cold expires | Gone (GDPR) | Irrecoverable |

Celery jobs run nightly to move data between tiers based on age and tenant variant. GDPR deletion requests are processed within 72 hours and permanently remove all PII from all tiers.

---

## 11. API Architecture

### 11.1 API Design Overview

PARWA's API layer is built on FastAPI with three communication patterns: REST for standard CRUD operations, WebSocket (Socket.io) for real-time bidirectional communication, and Server-Sent Events (SSE) for one-way real-time streaming. The API follows a consistent design language across all endpoints.

### 11.2 API Route Organization

| Route Group | Prefix | Purpose | Auth |
|------------|--------|---------|------|
| Auth | `/api/v1/auth/` | Registration, login, MFA, OAuth, password reset | Public + JWT |
| Onboarding | `/api/v1/onboarding/` | Jarvis onboarding sessions, demo packs, handoff | Session cookie |
| Tickets | `/api/v1/tickets/` | CRUD, search, bulk actions, intent classification | JWT + RLS |
| Conversations | `/api/v1/conversations/` | GSD state, messages, context health | JWT + RLS |
| Agents | `/api/v1/agents/` | Agent pool management, provisioning, metrics | JWT + RLS + @require_tier |
| Jarvis | `/api/v1/jarvis/` | Command center chat, commands, terminal feed | JWT + RLS |
| Voice | `/api/v1/voice/` | Call initiation, IVR, Twilio webhooks | JWT + HMAC (webhooks) |
| SMS | `/api/v1/sms/` | Send/receive, opt-in/out, TCPA compliance | JWT + HMAC (webhooks) |
| Email | `/api/v1/email/` | Send/receive, templates, OOO detection | JWT + HMAC (webhooks) |
| Knowledge Base | `/api/v1/kb/` | Upload, manage, search, RAG queries | JWT + RLS |
| Integrations | `/api/v1/integrations/` | Configure, health check, webhooks, MCP | JWT + RLS + @require_tier |
| Analytics | `/api/v1/analytics/` | Metrics, trends, ROI, export | JWT + RLS |
| Billing | `/api/v1/billing/` | Subscription, invoices, Paddle webhooks | JWT + HMAC (webhooks) |
| Control | `/api/v1/control/` | Approval gates, confidence, DND rules | JWT + RLS + Manager role |
| System | `/api/v1/system/` | Health, errors, building codes, status | JWT + Admin role |
| MCP | `/mcp/` | Model Context Protocol servers (10 servers) | JWT + RLS |

### 11.3 Middleware Stack

Every API request passes through the following middleware stack in order:

1. **CORS Middleware** — Allows tenant domains + PARWA dashboard domain
2. **Rate Limiting Middleware** — Redis-based counter, returns 429 on limit exceeded
3. **Auth Middleware** — JWT validation for authenticated routes, session cookie for onboarding
4. **Variant Resolver Middleware** — Loads tenant's variant_tier from companies table, sets `app.current_tenant` on DB connection
5. **Request Logger Middleware** — Logs request method, path, tenant_id, user_id, latency
6. **Error Handler Middleware** — Catches all exceptions, returns structured error responses

### 11.4 WebSocket Architecture

Socket.io is used for all real-time communication:

| Channel | Event Name | Direction | Purpose |
|---------|-----------|-----------|---------|
| Customer Chat | `customer:message` | Client → Server | Customer sends message |
| Customer Chat | `customer:response` | Server → Client | AI response (streaming) |
| Customer Chat | `customer:typing` | Server → Client | Typing indicator |
| Jarvis | `jarvis:command` | Client → Server | Manager sends command |
| Jarvis | `jarvis:response` | Server → Client | Command result |
| Jarvis | `jarvis:terminal` | Server → Client | GSD step execution |
| Jarvis | `jarvis:activity` | Server → Client | Live activity feed |
| Jarvis | `jarvis:approval` | Server → Client | Approval request notification |
| Onboarding | `onboarding:message` | Client → Server | Prospect message |
| Onboarding | `onboarding:response` | Server → Client | Jarvis response + rich cards |
| Co-Pilot | `copilot:draft` | Server → Client | AI draft suggestion |
| System | `system:health` | Server → Client | Subsystem status update |
| System | `system:error` | Server → Client | New error notification |

### 11.5 MCP Server Architecture

PARWA provides 10 Model Context Protocol (MCP) servers for standardized tool access by agents:

| Server | Port | Tools | Purpose |
|--------|------|-------|---------|
| FAQ | 5001 | search_faq, get_faq, suggest_faq | FAQ knowledge retrieval |
| RAG | 5002 | semantic_search, hybrid_search, get_context | Vector-based retrieval |
| KB | 5003 | list_documents, get_document, upload_document | Knowledge base management |
| Email | 5101 | send_email, get_thread, detect_ooo | Email operations |
| Voice | 5102 | initiate_call, transfer_call, get_recording | Voice call operations |
| Chat | 5103 | send_message, get_history, update_typing | Chat operations |
| Ticketing | 5104 | create_ticket, update_ticket, search_tickets, bulk_action | Ticket operations |
| Notification | 5201 | send_notification, get_preferences | Push/email notifications |
| Compliance | 5202 | check_compliance, redact_pii, audit_log | Compliance checks |
| SLA | 5203 | check_sla, get_breaches, escalate | SLA management |

---

## 12. Security Architecture

### 12.1 Security Layers

PARWA implements defense-in-depth with multiple security layers:

**Layer 1: Network Security**
- TLS 1.3 for all connections (API, WebSocket, database)
- IP allowlisting for webhook endpoints (Twilio, Brevo, Paddle)
- DDoS protection via Cloudflare (or similar CDN)
- Rate limiting at Redis level (per tenant, per endpoint)

**Layer 2: Authentication & Authorization**
- JWT tokens with RS256 signing (access + refresh token pair)
- Google OAuth 2.0 for social login
- Multi-factor authentication (TOTP-based, e.g., Google Authenticator)
- Role-based access control: Admin, Manager, Agent, Viewer
- Session-based auth for onboarding (no JWT — prospect has no account)

**Layer 3: Multi-Tenant Isolation**
- Row-Level Security (RLS) on all tenant-scoped tables
- Application-level tenant_id filtering on every query
- Redis key namespacing: `parwa:{company_id}:*`
- S3 bucket isolation per tenant
- Separate LangGraph thread_id per tenant per conversation

**Layer 4: Data Protection**
- PII Redaction Agent strips CC#, SSN, bank info before any LLM call
- AES-256 encryption for API keys stored in database
- HMAC-SHA256 verification on all incoming webhooks
- PII data encrypted at rest in PostgreSQL (pgcrypto extension)
- Anonymization of training data (SHA-256 with salt) before Agent Lightning processing

**Layer 5: AI Safety**
- MAKER Framework prevents AI from executing without validation
- Control System enforces Money Rule, VIP Rule, Newness Rule (hard-coded, immutable)
- Guardrails AI blocks hallucinations, competitor mentions, PII leaks
- Blocked Response Manager captures and reviews blocked outputs
- System modes (Shadow/Supervised/Graduated) limit AI autonomy

**Layer 6: Compliance**
- GDPR: Data subject access requests, right to deletion, data portability
- HIPAA: BAA for healthcare tenants (deferred to enterprise tier)
- PCI-DSS: No credit card data stored — handled by Paddle
- SOC 2: Audit trails, access logs, encryption at rest and in transit
- TCPA: SMS opt-in/out management, consent records
- CASL: Canadian anti-spam compliance for email

### 12.2 Hard-Coded Security Rules (BC-007)

The following rules are hard-coded in the source code and CANNOT be modified via database, environment variable, or admin override. CI must fail if these values are changed:

- 50-mistake threshold for Agent Lightning training trigger
- Money Rule: refund/credit actions always require ASK_HUMAN
- VIP Rule: VIP customer actions always require ASK_HUMAN
- Newness Rule: confidence below 70% always requires ASK_HUMAN
- Voice-First Rule: incoming calls must be answered with voice
- Signal expiration: fraud signals older than 180 days are ignored
- Webhook HMAC verification is always-on for all external webhooks

---

## 13. Agent Lightning & Training Pipeline Architecture

### 13.1 Training Pipeline Overview

Agent Lightning is the self-learning feedback loop that continuously improves PARWA's AI agents from manager corrections. The training pipeline is a background system that runs independently of the customer-facing LangGraph pipeline.

```
┌──────────────────────────────────────────────────────────────────────┐
│              AGENT LIGHTNING TRAINING PIPELINE                        │
│                                                                      │
│  Real-Time Phase (during LangGraph execution):                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  1. Manager APPROVE → positive_reward in training_data   │       │
│  │  2. Manager REJECT → negative_reward in training_data    │       │
│  │  3. After each reward, check:                            │       │
│  │     SELECT COUNT(*) FROM training_data                    │       │
│  │     WHERE company_id = ? AND reward_signal = 'negative'  │       │
│  │     AND agent_type = ? AND created_at > last_training_at │       │
│  │                                                          │       │
│  │  4. If count >= 50 → trigger training pipeline           │       │
│  └──────────────────────────────────────────────────────────┘       │
│                         │ (50 negative rewards reached)             │
│                         ▼                                           │
│  Training Phase (Celery background task):                           │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  1. Export training data                                  │       │
│  │     - Filter by company_id and agent_type                │       │
│  │     - Clean: remove duplicates, strip PII (SHA-256)      │       │
│  │     - Deduplicate: exact match on prompt+response        │       │
│  │     - Quality score: filter out low-quality entries       │       │
│  │                                                          │       │
│  │  2. Format for fine-tuning                                │       │
│  │     {prompt, completion, reward_signal}                   │       │
│  │     Positive rewards = correct examples                   │       │
│  │     Negative rewards = what NOT to do (with correction)   │       │
│  │                                                          │       │
│  │  3. Upload to training infrastructure                     │       │
│  │     Primary: Google Colab Free Tier (Llama-3-8B)         │       │
│  │     Secondary: RunPod (paid, automated)                   │       │
│  │                                                          │       │
│  │  4. Fine-tune using PyTorch Lightning + Unsloth          │       │
│  │     - Base model: Llama-3-8B                             │       │
│  │     - LoRA adapters for efficient fine-tuning            │       │
│  │     - Validate against held-out test set                 │       │
│  │                                                          │       │
│  │  5. Deploy new model version                              │       │
│  │     - Update LiteLLM config with new model endpoint      │       │
│  │     - Automatic rollback if validation fails             │       │
│  │     - Version tracked in model_versions table            │       │
│  │                                                          │       │
│  │  6. Log training results to analytics                    │       │
│  │     - Accuracy delta, error rate change, new patterns    │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Pattern Learning (continuous):                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Agent Lightning also learns decision patterns:           │       │
│  │  - "Always check for replacement orders before refunds"  │       │
│  │  - "Never auto-approve orders over $500 from new cust."  │       │
│  │  - Pattern rules → added to agent system prompts         │       │
│  │  - Known patterns increase confidence scores             │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                      │
│  Time-Based Fallback: Fine-tune every 2 weeks even if 50-mistake    │
│  threshold hasn't been reached (prevents model drift)               │
│                                                                      │
│  Skills vs Secrets Separation:                                       │
│  Skills (shared): decision patterns, resolution strategies           │
│  Secrets (never shared): customer data, prices, policies, financials │
│  Anonymization: SHA-256 hashing with salt before any cross-tenant   │
│  data processing                                                     │
└──────────────────────────────────────────────────────────────────────┘
```

### 13.2 Collective Intelligence Network

V1 implements Local Collective Intelligence: each client's Agent Lightning trains from their own Audit Logs (masked and anonymized). New clients receive "Instant Expertise" from pre-trained industry intelligence without accessing any individual client's data. V2 (future) will implement Federated Learning where only model weight updates are shared across clients, never raw data.

---

## 14. Deployment Architecture

### 14.1 Deployment Strategy — Docker Compose for V1

PARWA V1 uses Docker Compose for deployment. This provides a good balance of operational simplicity, reproducibility, and the ability to migrate to Kubernetes later when scaling demands it.

```
┌──────────────────────────────────────────────────────────────────────┐
│              DOCKER COMPOSE DEPLOYMENT                                │
│                                                                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │ nextjs-app │ │ fastapi    │ │ celery-    │ │ celery-    │      │
│  │            │ │ (API)      │ │ worker     │ │ beat       │      │
│  │ Next.js 16 │ │ FastAPI    │ │ (async     │ │ (scheduler)│      │
│  │ Port 3000  │ │ + Socket.io│ │  tasks)    │ │            │      │
│  │            │ │ Port 8000  │ │            │ │            │      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
│                                                                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │ postgres   │ │ redis      │ │ nginx      │ │ prometheus │      │
│  │ (Supabase  │ │ (Cache +   │ │ (Reverse   │ │ + grafana  │      │
│  │  or self-  │ │  Queue)    │ │  Proxy +   │ │ (Monitor-  │      │
│  │  hosted)   │ │            │ │  SSL)      │ │  ing)      │      │
│  │ Port 5432  │ │ Port 6379  │ │ Port 80/443│ │            │      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
└──────────────────────────────────────────────────────────────────────┘
```

### 14.2 Environment Strategy

| Environment | Purpose | Database | LLM | Data |
|-------------|---------|----------|-----|------|
| **Local Development** | Individual developer testing | Docker PostgreSQL | Real API keys (dev) | Seed data |
| **Staging** | Integration testing, QA | Supabase staging project | Real API keys (staging) | Anonymized prod copy |
| **Production** | Live system | Supabase production project | Real API keys (prod) | Real data |

### 14.3 CI/CD Pipeline

```
GitHub Push → GitHub Actions → Lint + Type Check → Unit Tests → Integration Tests
→ Build Docker Images → Push to Container Registry → Deploy to Staging → Smoke Tests
→ Manual Approval → Deploy to Production → Health Check → Rollback on Failure
```

CI must also verify BC-007 hard-coded rules: a dedicated test suite checks that the 50-mistake threshold, Money Rule, VIP Rule, and Newness Rule values have not been modified. If any hard-coded value is changed, CI fails.

---

## 15. Infrastructure Architecture

### 15.1 Infrastructure Components

| Component | Technology | Purpose | Scaling |
|-----------|-----------|---------|---------|
| **Application Server** | Docker on VPS (Hetzner/DigitalOcean) | FastAPI + Next.js | Vertical → add more VPS |
| **Database** | Supabase (managed PostgreSQL) | Primary data store | Managed scaling |
| **Cache** | Redis (managed or self-hosted) | GSD state, sessions, rate limits | Managed scaling |
| **Task Queue** | Celery + Redis | Async tasks (email, voice, training) | Add more workers |
| **File Storage** | Supabase Storage (S3-compatible) | KB docs, recordings, exports | Unlimited |
| **CDN** | Cloudflare | Static assets, DDoS protection | Auto-scaling |
| **Vector DB** | pgvector (Supabase) | Embeddings, similarity search | Managed scaling |
| **LLM Proxy** | LiteLLM (self-hosted) | Unified API for all LLM providers | Add more instances |
| **Monitoring** | Prometheus + Grafana | Metrics, dashboards, alerts | Single instance |
| **Logging** | Loki + Grafana | Centralized log aggregation | Single instance |

### 15.2 Redis Key Architecture

| Key Pattern | TTL | Purpose |
|------------|-----|---------|
| `parwa:{company_id}:gsd:{ticket_id}` | 24h | GSD state for active conversation |
| `parwa:{company_id}:session:{session_id}` | 30d | User session data |
| `parwa:{company_id}:rate:{endpoint}` | 60s sliding | API rate limiting counter |
| `parwa:{company_id}:agents:{agent_type}:load` | 5m | Agent load balancing data |
| `parwa:{company_id}:voice:calls` | During call | Concurrent voice call semaphore |
| `parwa:onboarding:{session_id}` | 24h | Onboarding session state |
| `parwa:system:health` | 30s | Subsystem health status |

---

## 16. Monitoring & Observability Architecture

### 16.1 Observability Stack

PARWA uses a three-pillar observability approach: metrics, logs, and traces.

**Metrics (Prometheus + Grafana):**
- Request latency (p50, p95, p99) per endpoint
- LLM call latency, tokens consumed, cost per request
- Agent utilization (load per agent instance)
- Ticket throughput (created, resolved, escalated per hour)
- Approval queue depth and wait time
- Error rates by type and agent
- Redis/PostgreSQL connection pool utilization
- Celery task queue depth and processing time

**Logs (Loki + Grafana):**
- Structured JSON logging from all services
- Request/response logs (with PII redacted)
- LLM call logs (input, output, model, tokens, latency)
- Audit trail logs (every approval decision with full context)
- Error logs with stack traces (truncated)

**Traces (LangGraph execution logs):**
- Node execution log from `ParwaGraphState.node_execution_log`
- Shows: which nodes executed, duration per node, routing decisions
- Available in Jarvis Terminal in real-time and in audit trail historically

### 16.2 Jarvis System Status Panel

The System Status Panel in Jarvis provides real-time health for all subsystems. Health checks run every 10 seconds via Celery beat. A subsystem is marked "down" after 3 consecutive failures.

| Subsystem | Health Check Method | Alert Threshold |
|-----------|-------------------|-----------------|
| PostgreSQL | `SELECT 1` query | >2s response or 3 failures |
| Redis | `PING` command | >500ms response or 3 failures |
| Celery | Queue depth check | >1,000 pending tasks |
| LLM (each provider) | LiteLLM health endpoint | >5s response or 3 failures |
| Twilio | API status page check | Service degradation |
| Brevo | API status page check | Service degradation |
| Paddle | API status page check | Service degradation |
| Socket.io | Connection test | >1s latency or 3 failures |

---

## 17. Scalability & Performance Architecture

### 17.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| API response time (non-LLM) | <200ms p95 | Prometheus |
| Chat message end-to-end | <3s p95 (FAQ), <5s p95 (complex) | LangGraph timing |
| Email processing | <10s from receipt to queue | Celery task timing |
| Voice call connection | <2s from dial to answer | Twilio metrics |
| SMS delivery | <5s from send to delivery | Twilio metrics |
| Jarvis command execution | <2s from command to result | WebSocket timing |
| Knowledge base search | <500ms for semantic search | pgvector query timing |
| Agent Lightning training | <4 hours per training run | Colab/RunPod timing |

### 17.2 Scalability Strategy

**Vertical Scaling (V1):** Start with a single VPS (8 cores, 32GB RAM) running Docker Compose. This handles up to ~50 concurrent tenants.

**Horizontal Scaling (V2+):** When vertical limits are reached, migrate to Kubernetes with separate pods for each service. Key scaling points:
- FastAPI: Scale to multiple pods behind a load balancer
- Celery: Add more worker pods for different queue priorities
- Redis: Migrate to Redis Cluster for sharding
- PostgreSQL: Add read replicas for analytics queries
- LangGraph: Stateless — can run multiple instances

### 17.3 Performance Optimizations

- **GSD State in Redis**: Eliminates database reads during conversation processing
- **CLARA Quality Gate Pipeline**: Runs BEFORE full processing to reject low-quality inputs early
- **CRP Concise Response Protocol**: 30-40% token reduction saves LLM cost and latency
- **Smart Router Free-First Routing**: 95% of queries handled by cheap/fast models
- **pgvector IVFFlat Index**: Fast approximate nearest neighbor search for RAG
- **Celery Task Priority**: Voice calls > chat > email > training in queue priority
- **Redis Connection Pooling**: Reuse connections, avoid connection setup overhead
- **LangGraph Checkpointing**: Resume failed graphs without re-processing completed nodes

---

## 18. Technology Stack & Rationale

| Category | Technology | Rationale |
|----------|-----------|-----------|
| **Frontend** | Next.js 16 | React-based, SSR, App Router, excellent DX |
| **Frontend Styling** | Tailwind CSS 4 | Utility-first, fast iteration, consistent design |
| **UI Components** | Radix UI + shadcn/ui | Accessible, unstyled primitives, customizable |
| **State Management** | Zustand | Lightweight, TypeScript-friendly, no boilerplate |
| **Backend** | FastAPI | Async, typed, fast, WebSocket support, OpenAPI docs |
| **AI Orchestration** | LangGraph | State graph, human-in-the-loop, checkpointing |
| **LLM Proxy** | LiteLLM | Unified API for 100+ models, retries, fallbacks |
| **Database** | PostgreSQL (Supabase) | Managed, RLS, pgvector, real-time subscriptions |
| **Cache** | Redis | Sub-millisecond reads, pub/sub, rate limiting |
| **Task Queue** | Celery + Redis | Battle-tested, priority queues, scheduled tasks |
| **Real-Time** | Socket.io | Reliable WebSocket with fallback, rooms, namespacing |
| **Vector Search** | pgvector | Embedded in PostgreSQL, no separate vector DB needed |
| **Voice** | Twilio Voice API | Industry standard, IVR, recording, transcription |
| **SMS** | Twilio SMS API | TCPA compliance tools, delivery tracking |
| **Email** | Brevo | Inbound parse, templates, high deliverability |
| **Payments** | Paddle | Merchant of Record, tax handling, subscriptions |
| **Training** | PyTorch Lightning + Unsloth | Efficient fine-tuning, Llama-3-8B support |
| **Training Infra** | Google Colab Free / RunPod | Free GPU access / paid automation |
| **Prompt Optimization** | DSPy | Declarative self-improving prompts, A/B testing |
| **Safety Validation** | Guardrails AI | Hallucination detection, PII blocking, custom rules |
| **MCP** | Model Context Protocol | Standardized tool access for agents |
| **Monitoring** | Prometheus + Grafana | Industry standard metrics and dashboards |
| **Logging** | Loki + Grafana | Lightweight log aggregation, integrates with Grafana |
| **Containerization** | Docker + Docker Compose | Reproducible environments, easy deployment |
| **CI/CD** | GitHub Actions | Integrated with repository, matrix builds |
| **Migrations** | Alembic | PostgreSQL schema migrations, version tracking |
| **CDN** | Cloudflare | DDoS protection, static asset caching, SSL |

---

## 19. Appendix A — Building Codes Mapping

The 14 Building Codes (BC-001 through BC-014) are PARWA's mandatory development rules. This appendix maps each Building Code to its architectural implementation:

| Building Code | Description | Architectural Implementation |
|--------------|-------------|------------------------------|
| BC-001 | State Over Chat History | GSD State Engine (Section 6), Redis + PostgreSQL dual storage |
| BC-002 | Zero Trust AI | Control System approval gates (Section 6.5), MAKER Framework (Section 6.4) |
| BC-003 | Human-First Safety | LangGraph `interrupt_before` at Control System (Section 5.2) |
| BC-004 | Multi-Model Fallback | Smart Router failover loop (Section 6.2), LiteLLM integration |
| BC-005 | Fail-Safe Defaults | Control System default to ASK_HUMAN (Section 6.5), Shadow Mode |
| BC-006 | Token Efficiency | CRP protocol (30-40% reduction), GSD state (98% reduction) |
| BC-007 | Hard-Coded Rules | 50-mistake threshold, Money/VIP/Newness Rules in source code with CI check |
| BC-008 | Redis + PG Dual Write | GSD state in Redis (primary) + PostgreSQL (fallback) (Section 10.1) |
| BC-009 | Idempotent Webhooks | HMAC verification + idempotency key in webhook_events table |
| BC-010 | Skill vs Secret Separation | Agent Lightning anonymization, Collective Intelligence (Section 13) |
| BC-011 | Variant Tier Gating | Three-layer enforcement: API + LangGraph + Frontend (Section 7.1) |
| BC-012 | Progressive Enhancement | Base Mini is fully functional, higher tiers add capabilities |
| BC-013 | Technique Router | Separate from Smart Router (Section 6.3), 10 signals, variant-filtered |
| BC-014 | Voice-First Rule | Hard-coded in Voice Agent, IVR before any text option (Section 9.2) |

---

## 20. Appendix B — External Service Integration Matrix

| Service | Integration Type | Auth Method | Rate Limits | Failure Handling |
|---------|-----------------|-------------|-------------|------------------|
| OpenAI (GPT-4o, GPT-4o-mini) | LiteLLM proxy | API Key (Own Keys) | Tier-dependent | Fallback to Claude/Gemini |
| Anthropic (Claude-3.5-Sonnet, Haiku) | LiteLLM proxy | API Key (Own Keys) | Tier-dependent | Fallback to GPT-4o |
| Google (Gemini-1.5-Pro, Flash) | LiteLLM proxy | API Key (Own Keys) | Tier-dependent | Fallback to GPT/Claude |
| Twilio Voice | REST API + WebSocket | Account SID + Auth Token | 1 call/sec (default) | Queue + retry with backoff |
| Twilio SMS | REST API + Webhook | Account SID + Auth Token | 1 msg/sec (default) | Queue + retry with backoff |
| Brevo (Email) | REST API + Webhook | API Key | 300 req/min | Queue + retry with backoff |
| Paddle (Billing) | REST API + Webhook | API Key + HMAC | 1000 req/min | Queue + retry + manual review |
| Supabase (Database) | PostgreSQL + REST | Connection string + JWT | Connection pool | Read replica + retry |
| Google Colab (Training) | Notebook API | OAuth token | GPU quota | Fallback to RunPod |
| RunPod (Training) | REST API | API Key | Pay-per-GPU | Queue + retry |
| Cloudflare (CDN) | DNS + Proxy | API Token | Unlimited | Automatic failover |

---

*End of Architecture Design Document*
