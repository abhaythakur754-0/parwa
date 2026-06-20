# PARWA — Software Requirements Specification (SRS)

**Document Version:** 2.1  
**Date:** May 4, 2026  
**SDLC Phase:** Phase 1 — Requirements  
**Strategy:** Hybrid Agile (10 Sprints, 20 Weeks)  
**Source Documents:** PARWA Complete Master Document v6.0, Feature Specs Batches 1-10, Jarvis Specification v3.0, Onboarding Spec v2.0, AI Technique Framework, Build Agent Prompt, Build Roadmap v1, Building Codes v1, Backend/Frontend/Infrastructure Docs, Gap Analysis  

---

## Table of Contents

1. Purpose & Scope
2. Functional Requirements
3. Non-Functional Requirements
4. User Classes & Roles
5. External Interfaces
6. Data Requirements
7. Constraints & Assumptions
8. Use Cases
9. Acceptance Criteria

---

## 1. Purpose & Scope

### 1.1 Purpose

This Software Requirements Specification (SRS) defines the complete, testable requirements for **PARWA** — a SaaS AI workforce system for customer care. PARWA is not a chatbot or an AI tool; it is a complete AI workforce system that assists human teams, learns from interactions, and earns autonomy under persistent human control. The system enforces a "Safety-First" principle where AI never executes irreversible actions without human approval, all decisions are auditable, and the system can be paused instantly. This document serves as the authoritative reference for design, development, testing, and validation throughout the Hybrid Agile SDLC (10 sprints, 20 weeks).

### 1.2 Scope

PARWA provides an AI-powered customer care workforce that operates across five channels (Chat, Email, SMS, Voice, Video), handles industry-specific workflows (E-commerce, SaaS, Logistics, Healthcare), and continuously learns through a self-improving feedback loop called Agent Lightning. The system implements the MAKER Framework for near-zero error rates, a 3-Tier Hybrid AI Technique Optimization architecture, a complete Ticket Management system, Voice-First call handling, an onboarding Jarvis that IS the product demo, and comprehensive analytics and reporting dashboards.

**In Scope:**
- Multi-channel customer support (Chat, Email, SMS, Voice, Video)
- Custom GSD (Get Shit Done) State Engine for structured conversation management
- Smart Router with multi-model dynamic routing (Light/Medium/Heavy tiers via Own API Keys)
- MAKER Framework (Maximal Agentic Decomposition with First-to-ahead-by-K Error Correction and Red-Flagging)
- 3-Tier Hybrid AI Technique Optimization Framework (CLARA, CRP, CoT, ReAct, GST, UoT, ToT, Self-Consistency, Reflexion, Least-to-Most)
- Agent Lightning continuous learning loop (weekly fine-tuning from manager corrections)
- Collective Intelligence Network (V1: Local; V2: Federated — future)
- Jarvis Command Center (natural language control interface for managers)
- Jarvis Onboarding System (chat-based onboarding that IS the product demo, with Demo Pack, Action Tickets, Rich Cards)
- The Control System (software-enforced approval gates, confidence scoring, audit trails)
- Complete Ticket Management System (creation, classification, assignment, search, omnichannel sessions, bulk actions, intent classification, SLA management)
- Voice-First Call Handling (incoming IVR, outbound proactive calls, demo calls, warm transfers, post-call summaries)
- SMS Handling (Twilio integration, TCPA compliance, opt-in/opt-out management)
- Batch Approval System with Semantic Clustering
- Empathy Engine (sentiment-based routing with multi-layer analysis)
- Quality Coach (PARWA High exclusive — performance analysis, training suggestions)
- Three subscription tiers: Mini PARWA ($999/mo), PARWA ($2,499/mo), PARWA High ($3,999/mo) — USD
- Dynamic Instruction Workflow (natural language skill creation with version control and A/B testing)
- Niche Specialization Layers (E-commerce, SaaS, Logistics, Healthcare)
- Refund Execution Workflow (3-step AI→Manager→Backend)
- Self-Service Refund Portal
- Stuck Approval Escalation Ladder
- Drift Detection & Auto-Correction
- ROI Calculator and Anti-Arbitrage Matrix
- Rate Limiting, DDOS Protection, and Circuit Breakers
- Cold Start Problem Resolution
- Non-Financial Undo / Error Correction (Recall, Correction, Void, Rage Quit)
- Webhook Malformation Handler
- Data Retention & GDPR Compliance (3-tiered architecture: Hot/Cold/Deleted)
- Legal Safeguards & Compliance (GDPR, HIPAA, PCI-DSS, SOC 2, CASL, TCPA)
- DSPy Prompt Optimization (automatic prompt engineering with A/B testing)
- Guardrails AI (output validation for hallucination, competitor mention, data leaks)
- MCP Integration Layer (Model Context Protocol for standardized client tool connections)
- LangGraph Agentic Workflow Engine
- PII Redaction Layer
- VoiceGuard Deepfake Detection
- Fairness Engine (Bias Detection, Name-Blind Processing)
- Hybrid Neural Translation Network (HNTN)
- Universal Access Protocol (Screen Reader, TTS, Simplified Language)
- Adaptive Accent Recognition Module (AARM)
- Post-Interaction QA Rating System
- Training Pipeline (Agent Lightning Training Loop, Dataset Preparation, Local GPU Training)
- Analytics Dashboard (Overview, Metrics, Trends, ROI, Confidence, Drift Detection, Export)
- Landing Page with Industry Selector
- Pricing Page with Smart Bundle Visualizer
- Complete Authentication System (Registration, Login, MFA, Google OAuth, Password Reset, Email Verification)
- Billing & Payments (Paddle integration, subscription management, overage charging, cancellation flow)
- Onboarding Wizard (5-step: Welcome, Legal, Integrations, KB Upload, AI Activation + First Victory)
- Integrations (Pre-built connectors, Custom REST/GraphQL/Webhook/MCP/Database, Integration Health Monitor)
- Agent Management (Dashboard, Performance Metrics, Scaling, Provisioning, Deprovisioning)
- Emergency Controls (Pause All, Selective Pause, Mode Changes)
- Undo System (Action Undo, Email Recall)
- System Status Panel (Real-time health for all subsystems)
- Error Management (Last 5 Errors Panel, Train from Error)
- 14 Building Codes (BC-001 through BC-014)
- Complete Backend (FastAPI + PostgreSQL + Redis + Celery + Socket.io)
- Complete Frontend (Next.js + Tailwind CSS + Radix UI + Zustand)
- Mobile Responsive Design
- Progressive Web App Support

**Out of Scope (V1):**
- Federated learning across clients (planned for V2 of Collective Intelligence)
- Native mobile applications (mobile-responsive web only for V1)
- Video channel (PARWA High only — deferred)
- Enterprise SSO (SAML/LDAP — future)
- Healthcare HIPAA full compliance (requires BAA, deferred to enterprise tier)
- **Social Media Integration (F-130)** — Twitter/X, Instagram, Facebook as support channels are explicitly NOT in V1 per product decision

### 1.3 Definitions & Acronyms

| Term | Definition |
|------|-----------|
| GSD | Get Shit Done — PARWA's custom state engine that replaces raw chat history with structured JSON state |
| Agent Lightning | Self-learning feedback loop that fine-tunes models weekly from manager corrections |
| Jarvis | The Command Center UI where managers interact with The Control System via natural language; also the onboarding AI assistant |
| The Control System | Software layer enforcing safety rules, approval gates, and audit trails |
| Smart Router | Dynamic multi-model routing engine that selects Light/Medium/Heavy LLM tiers |
| Technique Router | Selects the AI reasoning technique (separate from Smart Router which selects the model) |
| MAKER | Maximal Agentic Decomposition with First-to-ahead-by-K Error Correction and Red-Flagging |
| MAD | Maximal Agentic Decomposition — first pillar of MAKER |
| FAKE | First-to-Ahead-by-K Error Correction — second pillar of MAKER |
| Shadow Mode | AI observes and simulates decisions without executing real actions |
| Supervised Mode | AI handles safe tasks autonomously, asks approval for irreversible actions |
| Graduated Mode | AI handles proven tasks autonomously after earning trust via KPIs |
| DND Rules | "Do Not Disturb" — tasks AI handles without manager approval |
| RAG | Retrieval-Augmented Generation using vector database for knowledge retrieval |
| MCP | Model Context Protocol for standardized data integration ports |
| DSPy | Declarative Self-improving Python for automatic prompt optimization |
| CLARA | Contextual Late-Augmented Retrieval Architecture — quality gate pipeline |
| CRP | Concise Response Protocol — 30-40% token reduction |
| CoT | Chain of Thought prompting |
| ToT | Tree of Thoughts prompting |
| UoT | Universe of Thoughts — multi-solution evaluation |
| GST | Graph Spatial Thinking — multi-factor analysis |
| ReAct | Reasoning + Acting framework for tool/API calls |
| RLS | Row-Level Security for multi-tenant data isolation |
| PII | Personally Identifiable Information |
| HMAC | Hash-based Message Authentication Code for webhook verification |
| BC | Building Code — PARWA's 14 mandatory development rules |
| HNTN | Hybrid Neural Translation Network |
| AARM | Adaptive Accent Recognition Module |
| IVR | Interactive Voice Response |
| CSAT | Customer Satisfaction Score |

---

## 2. Functional Requirements

### 2.1 Custom GSD State Engine

**FR-2.1.1:** The system SHALL maintain a structured JSON state object for each active conversation instead of raw chat history, containing fields: customer_name, current_issue, order_id, policy_status, sentiment, last_action, and any additional client-specific fields.

**FR-2.1.2:** The system SHALL send only the current structured state + new message to the LLM, NOT the entire conversation history, achieving approximately 98% reduction in token usage compared to standard chat history approaches.

**FR-2.1.3:** The system SHALL implement a GSD State Machine with the following states: NEW → GREETING → DIAGNOSIS → RESOLUTION → FOLLOW-UP → CLOSED, with an ESCALATE → HUMAN HANDOFF branch.

**FR-2.1.4:** The system SHALL track a Complexity Score for each conversation and trigger Dynamic Context Compression when the complexity score spikes or when chat sessions exceed 50 messages, compressing the last 20 interactions into a concise summary.

**FR-2.1.5:** The system SHALL display a Context Health Meter in Jarvis showing context usage percentage (0-100%) for each active conversation with color coding: Green (0-70%), Yellow (70-90%), Red (90-100%).

**FR-2.1.6:** The system SHALL present a popup at 90% context capacity offering "Start New Chat", "Compress", or "Escalate" to prevent accuracy degradation.

**FR-2.1.7:** The system SHALL store GSD state in Redis as primary with PostgreSQL as fallback (BC-008). Redis keys SHALL use format: `parwa:{company_id}:gsd:{ticket_id}`.

**FR-2.1.8:** The system SHALL provide a GSD State Terminal in Jarvis for live debugging: showing current step, next step, state variables, and transition history. Admin users can force-transition states.

**FR-2.1.9:** The system SHALL preserve all compressed context in the audit trail even after starting a new conversation segment.

### 2.2 Smart Router (Multi-Model Routing)

**FR-2.2.1:** The system SHALL dynamically route customer requests to three LLM tiers based on task complexity: Light Tier (FAQs, greetings, order status — Complexity Score 0-4), Medium Tier (drafting, summarizing, sentiment analysis — Complexity Score 5-9), Heavy Tier (refunds, fraud detection, complex logic — Complexity Score 10+).

**FR-2.2.2:** The system SHALL use Own API Keys (client-provided or system-managed keys) for all LLM inference. OpenRouter is NOT used. The system SHALL use LiteLLM as unified proxy for routing, retries, and provider management.

**FR-2.2.3:** The system SHALL implement automatic failover: if a model at any tier hits a rate limit or fails, the router SHALL automatically try the next available model in that tier (Safety Failover Loop). Target: 99.9% uptime.

**FR-2.2.4:** The system SHALL implement Smart Promotion (Dynamic Escalation): automatic tier upgrade when hallucination risk or rate limit is detected on the current tier.

**FR-2.2.5:** The system SHALL mask PII (credit card numbers, SSNs, bank account info) via a local Python layer BEFORE sending any data to any LLM.

**FR-2.2.6:** The system SHALL log all routing decisions including model selected, complexity score, latency, and failover events.

**FR-2.2.7:** The system SHALL implement Free-First Routing: default to free/subsidized models for 95% of tasks to maximize cost efficiency.

**FR-2.2.8:** The system SHALL include a Complexity Scorer component that evaluates each query and outputs a numerical complexity score used for routing decisions.

**FR-2.2.9:** Model selection for voice calls SHALL follow: Initial greeting (pre-generated, no AI), Intent classification (Light Tier), Conversation (Medium Tier), Complex decisions (Heavy Tier).

### 2.3 Technique Router (AI Technique Selection)

**FR-2.3.1:** The system SHALL implement a Technique Router (BC-013) SEPARATE from the Smart Router. Smart Router selects the MODEL; Technique Router selects the REASONING TECHNIQUE. Both execute on every query.

**FR-2.3.2:** The Technique Router SHALL evaluate 10 input signals: Query Complexity Score, Confidence Score, Sentiment Score, Customer Tier, Monetary Value, Conversation Turn Count, Intent Type, Previous Response Status, Reasoning Loop Detection, Resolution Path Count.

**FR-2.3.3:** The Technique Router SHALL apply the following master trigger rules at minimum: Complexity >0.4 → CoT; Confidence <0.7 → Reverse Thinking + Step-Back; VIP → UoT + Reflexion; Sentiment <0.3 → UoT + Step-Back; Monetary >$100 → Self-Consistency; >5 turns → Thread of Thought; External data needed → ReAct; ≥3 paths → ToT; Strategic decision → GST; Complexity >0.7 → Least-to-Most; Response rejected → Reflexion; Reasoning loop → Step-Back; Billing/Financial intent → Self-Consistency; Technical troubleshooting → CoT + ReAct.

**FR-2.3.4:** The Technique Router SHALL output technique + tier level. Cross-reference with variant tier access check. Add tier filter fallback to Tier 1 equivalent if tenant doesn't have access to higher-tier techniques.

**FR-2.3.5:** Technique stacking SHALL be sequential within each tier: Tier 1 always first (CLARA → CRP → GSD), Tier 2 next in trigger table order, Tier 3 last in trigger table order. Deduplication if same technique triggered by multiple rules.

### 2.4 3-Tier Hybrid AI Technique Optimization

**FR-2.4.1 — Tier 1 (Always Active):** The following techniques SHALL run continuously on EVERY query: CLARA (Quality Gate Pipeline: Raw → Structure Check → Logic Check → Brand Check → Tone Check → Delivery, per-tenant brand voice config), CRP (Concise Response Protocol — 30-40% token reduction via filler elimination, compression, redundancy removal, token budget enforcement, runs BEFORE Guardrails), GSD State Engine (Structured state management — 98% token reduction), Smart Router (Model selection — cheapest sufficient model).

**FR-2.4.2 — Tier 2 (Auto-Triggered):** The following techniques SHALL activate when specific conditions are detected: Reverse Thinking (triggered on any decision action or confidence <0.7, ~300 tokens overhead), Chain of Thought (triggered on multi-step queries, complexity >0.4, 3+ sub-questions, ~150-500 tokens), ReAct (triggered when external data/API call needed or order IDs/account numbers detected, Thought→Action→Observation loop with 5 tool integrations, ~150-450 tokens), Step-Back Prompting (triggered on narrow query, reasoning loop, or stalled diagnosis, ~300 tokens), Thread of Thought (triggered on multi-turn, >5 messages, or references to previous points, ~150 tokens).

**FR-2.4.3 — Tier 3 (Selective Application):** The following techniques SHALL activate only for high-value/complex scenarios: GST (triggered on strategic decisions, multi-party impact, policy change, 5 checkpoints: Stakeholder Impact → Policy Alignment → Risk Assessment → Financial Impact → Recommendation, ~1,000-1,200 tokens), Universe of Thoughts (triggered on VIP tier, sentiment <0.3, monetary >$100, or Urgent Attention Panel, 3-5 solutions evaluated on CSAT/Cost/Policy/Speed/Long-term, ~1,100-1,700 tokens), Tree of Thoughts (triggered on 3+ resolution paths or branching analysis, tree generation → branch evaluation → pruning → search, ~800-1,500 tokens), Self-Consistency (triggered on monetary >$100, refund/credit action, or financial compliance, generate 3-5 answers with majority vote, ~750-1,150 tokens), Reflexion (triggered on previous response rejected, confidence drops, or customer dissatisfaction, failure detection → self-reflection → strategy adjustment, ~400 tokens), Least-to-Most Decomposition (triggered on complexity >0.7, 5+ sub-steps, or multi-department coordination, decompose → dependency order → sequential solve → combine, ~800-1,300 tokens).

**FR-2.4.4:** The Smart Router SHALL include tier-aware routing logic, dynamically adjusting technique activation thresholds based on system load. Conservative mode raises thresholds during high load; aggressive mode lowers thresholds during low load.

**FR-2.4.5:** The Jarvis Dashboard SHALL display real-time technique activation status and historical patterns per client.

**FR-2.4.6:** Agent Lightning SHALL incorporate technique activation patterns into training data, learning which technique combinations produce the best outcomes for specific query types.

**FR-2.4.7:** The system SHALL apply the following functionality-to-technique mappings: FAQ Queries → Tier 1 only; Order Status → Tier 1 + ReAct; Simple Refunds → Tier 1 + Reverse Thinking; Complex Refunds → Tier 1 + CoT + Reverse Thinking + Self-Consistency; VIP Handling → Tier 1 + CoT + Step-Back + UoT + Reflexion; Fraud Detection → Tier 1 + Reverse Thinking + Self-Consistency + GST; Dispute Resolution → Full spectrum (all tiers); Technical Troubleshooting → CoT + ReAct; Billing → Self-Consistency; Feature Requests → Least-to-Most.

### 2.5 MAKER Framework (Zero-Error LLM Execution)

**FR-2.5.1:** The system SHALL implement the MAKER Framework (Maximal Agentic Decomposition with First-to-ahead-by-K Error correction and Red-flagging) for near-zero error rates on complex multi-step operations.

**FR-2.5.2 — Maximal Agentic Decomposition (MAD):** The system SHALL decompose complex tasks into the smallest possible atomic operations, each handled by a specialized agent. For example, a refund SHALL be decomposed into: verify customer identity → retrieve order details → check refund eligibility → calculate refund amount → verify payment method → request approval → execute refund → send confirmation → update records.

**FR-2.5.3 — First-to-Ahead-by-K Error Correction (FAKE):** The system SHALL generate K possible solutions in parallel before execution. Default K values: K=3 for standard queries, K=5 for high-stakes financial decisions, K=7 for critical irreversible actions. The system SHALL select the first solution that demonstrates clear superiority in: policy compliance, customer satisfaction prediction, risk assessment alignment, and factual accuracy verification.

**FR-2.5.4 — Red-Flagging System:** The system SHALL implement real-time anomaly detection with three categories: Category A (Immediate Halt) — confidence <60%, contradictions with KB, severe customer dissatisfaction, policy violations; Category B (Enhanced Review) — unusual patterns, high-value transactions, VIP customers, new query types; Category C (Log and Monitor) — slight deviations and edge cases.

**FR-2.5.5:** The system SHALL offer three MAKER configurations: Conservative Mode (K=7, 75% threshold) for healthcare/finance, Balanced Mode (K=3-5, 60% threshold) for e-commerce/SaaS, and Efficiency Mode (K=3, 50% threshold) for high-volume low-risk queries.

**FR-2.5.6:** MAKER SHALL integrate at three levels: Input Processing (decompose queries into intent atoms with parallel hypothesis generation), Decision Generation (create multiple solution paths with first-to-ahead-by-K selection), and Execution Layer (atomic operations with rollback capabilities and complete audit trails).

**FR-2.5.7:** MAKER performance targets: Error rate 3-5% → 0.3-0.8%, Escalation rate 8-12% → 2-4%, Resolution accuracy 94% → 99.2% (6-16x improvement).

**FR-2.5.8:** MAKER SHALL integrate with the 3-Tier Technique System through K-value selection and red-flagging integration. Smart Router includes tier-aware routing. Jarvis displays real-time technique activation.

### 2.6 Agent Lightning (Self-Learning Loop)

**FR-2.6.1:** The system SHALL log every manager "Approve" action as a Positive Reward signal and every "Reject" action as a Negative Reward signal in the training_data table.

**FR-2.6.2:** The system SHALL capture training data in the format: {Prompt, AI_Response, Human_Correction, Outcome: Positive_Reward or Negative_Reward} with additional fields: timestamp, decision_type, ai_recommendation, manager_action, manager_reason, context, pattern_id.

**FR-2.6.3:** The system SHALL trigger a fine-tuning job when 50 or more Negative Reward signals (mistakes) have been accumulated for a client. The 50-mistake threshold is HARD-CODED (BC-007 Rule 10), not configurable via DB, env var, or admin override. CI must fail if modified.

**FR-2.6.4:** The system SHALL execute fine-tuning using PyTorch Lightning with Unsloth optimization on Llama-3-8B models via Google Colab Free Tier (primary) or RunPod (paid automation).

**FR-2.6.5:** The system SHALL deploy a new model version after each successful fine-tuning run, replacing the previous version with automatic rollback on failure.

**FR-2.6.6:** The system SHALL learn Skills (logic, reasoning patterns) from client data but NEVER learn Secrets (client data, prices, private policies, financial data). Data SHALL be anonymized before training via SHA-256 hashing with salt.

**FR-2.6.7:** The system SHALL maintain a private encrypted vector store per client; client data SHALL never be exposed to any global training process.

**FR-2.6.8:** The system SHALL implement Pattern Learning Rules: e.g., "Always check for replacement orders before approving refunds". Automatic integration: rules added to system prompt for relevant decision types. Known patterns increase confidence scores.

**FR-2.6.9:** The system SHALL implement a weekly training loop: export mistakes → train Llama-3-8B → validate against test set → deploy new model.

**FR-2.6.10:** Agent Lightning impact targets: 72% accuracy improvement, 94% manager review time reduction (4.2→1.1 min/ticket), 3% repeat mistakes (from 23%).

**FR-2.6.11:** The system SHALL implement the Training Pipeline with: Agent Lightning Training Loop, 50-Mistake Threshold Trigger, Training Run Execution (Google Colab/RunPod), Training Dataset Preparation (clean, deduplicate, PII strip, quality scoring), Training Evaluation & Validation, Training Versioning & Rollback, Drift Alert integration, and Time-Based Fallback Training (every 2 weeks).

### 2.7 Collective Intelligence Network

**FR-2.7.1:** V1 (Local): The system SHALL implement client-specific continuous learning where Agent Lightning trains from each client's own Audit Logs (masked/anonymized).

**FR-2.7.2:** The system SHALL implement "Skills vs. Secrets" separation: learns logic (how to reason), never secrets (client data/prices). What is shared: decision patterns, fraud indicators, resolution strategies, communication styles. What is NEVER shared: customer data, business specifics, conversation content, financial data.

**FR-2.7.3:** New clients SHALL receive pre-trained industry intelligence ("Instant Expertise") from the collective knowledge base without accessing any individual client's data.

**FR-2.7.4:** V2 (Future — Federated Learning): The system SHALL support federated learning where only model weight updates are shared across clients, not raw data.

### 2.8 Jarvis Command Center

**FR-2.8.1:** The system SHALL provide a conversational interface (Jarvis) where managers can control all AI workforce operations through natural language commands.

**FR-2.8.2:** The system SHALL support the following natural language commands at minimum: pause refunds, resume refunds, handle all email tickets, pause all AI activity, show ticket details, disable last rule, add agents (provision), call customer, show me today's errors, check system health, export weekly report, escalate all urgent tickets.

**FR-2.8.3:** The system SHALL execute backend commands within 2 seconds of receiving a validated Jarvis command.

**FR-2.8.4:** The system SHALL display a Terminal/CLI-style interface showing GSD execution steps: INIT, INPUT, THINKING, TOOL, SUCCESS, STATE UPDATE, DRAFTING.

**FR-2.8.5:** The system SHALL always display the current system mode (Shadow, Supervised, Graduated) in the Jarvis header.

**FR-2.8.6:** The system SHALL provide Co-Pilot Mode where Jarvis drafts text using Medium Tier for manager review, saving approximately 90% of typing time.

**FR-2.8.7:** The system SHALL provide proactive self-healing: detect API errors and DDOS attacks automatically and fix them without human intervention.

**FR-2.8.8:** The system SHALL allow clients to convey new instructions through Jarvis, which the AI SHALL integrate into its workflow. If the AI identifies loopholes or knowledge gaps, it SHALL ask for clarification before executing.

**FR-2.8.9:** The system SHALL allow Jarvis to create new agents from the chat interface (dynamic provisioning) with proper authorization and budget checks.

**FR-2.8.10:** The system SHALL provide an Emergency Brake: "Jarvis, undo my last rule" with preview and confirmation before execution.

**FR-2.8.11:** The system SHALL support Real-Time Policy Training: "Always Auto-Approve This Type" → DSPy updates core instructions immediately.

**FR-2.8.12:** Jarvis SHALL provide a Live Activity Feed (color-coded: green=auto-handled, yellow=batched, red=escalated).

**FR-2.8.13:** The system SHALL provide Quick Command Buttons (Presets) alongside Jarvis chat: "pause all agents", "export weekly report", "check system health", "escalate all urgent tickets", plus tenant-customizable presets (max 50 per tenant).

**FR-2.8.14:** The system SHALL provide a System Status Panel showing real-time health for all subsystems (LLM, Celery, Redis, Postgres, integrations, agents). 3 consecutive failures confirm "down" status.

**FR-2.8.15:** The system SHALL provide a Last 5 Errors Panel with truncated stack trace, affected ticket, "Investigate" deep-link, and error grouping.

**FR-2.8.16:** The system SHALL provide a "Train from Error" button on error entries that packages error context + ticket data + correct outcome into training data points for Agent Lightning.

### 2.9 Jarvis Onboarding System

**FR-2.9.1:** The system SHALL implement a chat-based onboarding system at `/onboarding` where Jarvis serves as Guide, Salesman, and Demo — the onboarding itself IS the product demonstration.

**FR-2.9.2:** There SHALL be one Jarvis per account with two types: Onboarding Jarvis (pre-purchase, remembers everything) and Customer Care Jarvis (post-purchase, knows only variants/KB/business info — NO onboarding chat history).

**FR-2.9.3 — Message Limits:** Free Tier: 20 messages/day, resets at midnight (user timezone), context persists across resets. When limit reached: Jarvis offers "Come back tomorrow" OR unlock Demo Pack for $1.

**FR-2.9.4 — $1 Demo Pack:** One-time $1 payment via Paddle provides: 500 chat messages, 3-minute AI voice call, 24-hour validity from purchase.

**FR-2.9.5 — Conversation Stages:** The system SHALL detect and transition through 8 stages: WELCOME → DISCOVERY → DEMO → PRICING → BILL_REVIEW → VERIFICATION → PAYMENT → HANDOFF. Stages are non-linear until buy decision; after that, flow is systematic and fixed.

**FR-2.9.6 — Action Ticket System:** Every Jarvis action SHALL be treated as a ticket with status (pending/in_progress/completed/failed). 9 ticket types: otp_verification, otp_verified, payment_demo_pack, payment_variant, payment_variant_completed, demo_call, demo_call_completed, roi_import, handoff. Each displayed with status indicator (gray circle=pending, amber spinning=in_progress, green checkmark=completed, red X=failed).

**FR-2.9.7 — In-Chat Rich Cards:** The system SHALL render special card components within Jarvis chat: BillSummaryCard, PaymentCard, OtpVerificationCard, HandoffCard, DemoCallCard, MessageCounter, DemoPackCTA, LimitReachedCard, PackExpiredCard, ActionTicketCard, PostCallSummaryCard, RechargeCTACard.

**FR-2.9.8 — Knowledge Base:** Jarvis SHALL have 10 knowledge JSON files: pricing_tiers, industry_variants, variant_details, integrations, capabilities, demo_scenarios, objection_handling, faq, competitor_comparisons, edge_cases. Knowledge service provides 11 functions for loading, searching, and building context-aware knowledge.

**FR-2.9.9 — System Prompt (7 Layers):** The system SHALL construct Jarvis's system prompt from: Base persona, Product knowledge, Industry-specific knowledge, Session context, Relevant knowledge for query, Stage behavior instructions, Information boundary rules.

**FR-2.9.10 — Information Boundary:** Jarvis CAN reveal: features, how things work, benefits, industry solutions, pricing, ROI, integration partners, security. CANNOT reveal: internal strategy (GSD, prompt engineering), technical implementation (models, embeddings, RAG), tools/technologies, other clients' data, AI configuration details.

**FR-2.9.11 — Non-Linear Entry:** The system SHALL support 5 entry paths: Direct Chat (fresh session), Demo Booking (immediately proceed to call flow), ROI Calculator (chat with ROI context), Pricing Page (skip discovery, show bill summary), Demo Pack Purchase (welcome back, offer voice call). URL parameters: `?entry=demo_booking`, `?entry=roi`, `?variants=returns:3,faq:2`, `?pack=active`.

**FR-2.9.12 — Demo Call Flow:** Available only after purchasing $1 Demo Pack. 12-step flow entirely inside `/onboarding` chat: User agrees → Phone number → OTP card (Twilio, 4-digit, 5-min expiry) → Enter OTP (max 3 attempts) → Verified → Paddle payment ($1 for 3 min) → Payment confirmed → Call initiated (Twilio Voice API) → Live timer card → Post-call summary card → ROI info card → Recharge CTA.

**FR-2.9.13 — Post-Call Summary:** Card shows: Duration, Topics Discussed, Key Moments (with timestamps), Impressions (queries handled, response time, human interventions), ROI mapping (if ROI calculated).

**FR-2.9.14 — Handoff:** After successful variant payment: Onboarding Jarvis delivers personalized farewell → introduces Customer Care Jarvis → New `customer_care` session created with selective context transfer (hired_variants, business_info, industry — NOT chat history) → Onboarding chat preserved read-only.

**FR-2.9.15 — Session Persistence:** Close/reopen browser → previous chat loads. Two devices → same session (API sync). 30+ days inactive → auto-archived. Payment page refresh → session preserved.

### 2.10 The Control System (Approval Gates)

**FR-2.10.1:** The system SHALL enforce approval gates on ALL of the following action types: refunds (any type, any amount), returns (any item), account changes (billing, security, email, password), policy exceptions, new decision types, VIP customer actions, and financial transactions (credits, adjustments, discounts >$10).

**FR-2.10.2:** The system SHALL allow the following action types to be handled autonomously (DND Rules): FAQ answers from knowledge base, order status checks, tracking link retrieval, product information/details, password reset links, and categorizing/routing tickets.

**FR-2.10.3:** The system SHALL calculate a Confidence Score (0-100%) for every AI action based on: Pattern Match (40%), Policy Alignment (30%), Historical Success (20%), Risk Signals (10%). Signal Expiration: fraud signals older than 180 days SHALL be ignored.

**FR-2.10.4:** Decision rules based on confidence: >95% GRADUATE (auto-handle with logging), 85-95% BATCH (group similar requests), 70-84% ASK (individual manager review), <70% ESCALATE (immediate human judgment required).

**FR-2.10.5:** The system SHALL enforce a "Money Rule": if action.type is REFUND or CREDIT, always return ASK_HUMAN regardless of confidence score.

**FR-2.10.6:** The system SHALL enforce a "VIP Rule": if customer_tier is VIP, always return ASK_HUMAN.

**FR-2.10.7:** The system SHALL enforce a "Newness Rule": if confidence < 0.70, always return ASK_HUMAN.

**FR-2.10.8:** The system SHALL implement 3-mode operation: Shadow Mode (AI observes, takes NO real-world action), Supervised Mode (AI acts but stops at Approval Gates), Graduated Autonomy (AI acts autonomously on proven tasks, never touches money/VIPs).

**FR-2.10.9:** The system SHALL support one-click system overrides: managers can pause all refund processing, redirect channels, or execute emergency shutdown via Jarvis or dashboard buttons.

**FR-2.10.10:** The system SHALL implement an approval gate check function that runs on EVERY AI action BEFORE execution, returning one of: EXECUTE, ASK_HUMAN, or DENY.

**FR-2.10.11:** The system SHALL provide a Confidence Score Breakdown drill-down interface showing component scores (retrieval, intent, sentiment, history) composing the overall confidence, with per-component trend indicators and configurable thresholds per company.

**FR-2.10.12:** The system SHALL monitor Confidence Drift: tracks daily average confidence per client, alerts on >5% drop for 3+ days.

### 2.11 Batch Approval System

**FR-2.11.1:** The system SHALL use Semantic Clustering (embedding-based similarity) to group similar approval requests into batches instead of showing individual requests.

**FR-2.11.2:** Each batch SHALL display: Confidence Range, Risk Indicator (Low/Medium/High), Reason Summary, and Common Pattern.

**FR-2.11.3:** The system SHALL support 4-command batch operations: Approve Selected, Reject Batch, Automate This Rule, Simulate (Shadow New Type).

**FR-2.11.4:** The system SHALL support partial approval within a batch — managers can select individual tickets to approve while rejecting others.

**FR-2.11.5:** The system SHALL support "Always Auto-Approve This Type" rule creation from batch approval, which programmatically updates the AI's core instructions via DSPy.

**FR-2.11.6:** Auto-approve rules SHALL still require approval if: address change to new country, multiple changes in short period (fraud signal), high-value VIP customer, or incomplete information.

**FR-2.11.7:** The system SHALL reduce approval fatigue by approximately 80% through batch processing.

**FR-2.11.8:** Clusters SHALL automatically dissolve after 72 hours of inactivity.

**FR-2.11.9:** Mixed refund/non-refund items in a cluster SHALL be split into sub-clusters.

### 2.12 Empathy Engine (Sentiment Routing)

**FR-2.12.1:** The system SHALL perform a two-layer sentiment analysis on every incoming ticket: Layer 1 — Keyword Lexicon (fast check for anger/legal keywords), Layer 2 — NLP Sentiment Analysis via Medium Tier model (score from -1.0 to +1.0).

**FR-2.12.2:** The system SHALL route tickets based on Sentiment Intensity: 0-60% (Neutral) → AI (Standard), 60-80% (Frustrated) → PARWA High (Warning), 80-100% (Angry/Crisis) → Human immediately (Danger).

**FR-2.12.3:** The system SHALL automatically detect keywords indicating legal threats and immediately escalate to human regardless of sentiment score.

**FR-2.12.4:** The system SHALL implement De-Escalation Logic: if a customer's anger score drops from >70% to <40% after human intervention, the system SHALL log "RECOVERED" and may route subsequent messages back to AI.

**FR-2.12.5:** The system SHALL display a Sentiment Badge on every ticket card in the Jarvis dashboard.

**FR-2.12.6:** The system SHALL implement sentiment smoothing across conversation turns using exponential moving average: smoothed_score = 0.7 * current + 0.3 * previous_avg, with sentiment_trend signal.

**FR-2.12.7:** The system SHALL apply a 60-second per-conversation cooldown on sentiment technique override triggers, max 3 triggers per session.

### 2.13 Ticket Management System

**FR-2.13.1:** The system SHALL create a ticket for every customer interaction across all channels (Chat, Email, SMS, Voice, Video) with a unique ticket ID, channel type, customer ID, and timestamp.

**FR-2.13.2:** Each ticket SHALL track: status (pending_approval/escalated_to_human/auto_handled/refunded/refund_failed/deleted_archived/paused_security/forced_close), ticket type, assigned agent ID, AI confidence score, AI reasoning, human override reason, sentiment score, complexity score, escalation reason, and resolution timestamp.

**FR-2.13.3 — Ticket Intent Classification (F-049):** The system SHALL auto-categorize tickets by intent (refund, technical, billing, feature_request, complaint, general) and urgency (urgent, routine, informational) using Smart Router Light-tier LLM. Classification in <3s with ≥70% confidence. Low confidence tickets flagged for review. Corrections logged. Model rotation at 50-mistake threshold.

**FR-2.13.4 — Technique-Intent Mapping (BC-013):** The system SHALL map intents to techniques: Refund→Self-Consistency, Technical→CoT+ReAct, Complaint→UoT+Reflexion, Billing→Self-Consistency, Feature Request→Least-to-Most.

**FR-2.13.5 — Ticket Assignment (F-050):** The system SHALL provide AI-powered auto-routing based on classification, workload, and skill matching. Round-robin rules per intent. Manual override for supervisors. Escalation paths. Failed auto-assign → unassigned queue with supervisor alert. Agent offline → excluded from future assignments.

**FR-2.13.6 — Ticket Search (F-048):** The system SHALL provide full-text search with PostgreSQL tsvector + trigram similarity for fuzzy matching. Faceted filter counts by status/channel/assignee. Autocomplete type-ahead suggestions. "Did you mean?" for typos.

**FR-2.13.7 — Omnichannel Sessions (F-052):** The system SHALL consolidate all channels (email, chat, SMS, voice) into unified ticket thread. Channel switch mid-conversation → stitched in same thread. Duplicate webhook → idempotency handling.

**FR-2.13.8 — Ticket Bulk Actions (F-051):** The system SHALL support bulk operations on tickets: status change, assignment, categorization.

**FR-2.13.9 — Customer Identity Resolution (F-070):** The system SHALL provide cross-channel customer identity matching. Links same customer across email, phone, and other profile signals. Handles deduplication and merging with audit trail.

**FR-2.13.10 — Auto-Response Generation (F-065):** The system SHALL auto-generate response drafts for tickets. Confidence-based auto-send vs. draft-only mode. Per-customer rate limit: max 20/hour, max 100/day. If exceeded, switch to template responses only. Before auto-response, check for existing human draft in progress.

**FR-2.13.11 — AI Draft Composer / Co-Pilot Mode (F-066):** The system SHALL provide a side-by-side AI co-pilot that suggests response drafts while agents type. Real-time suggestions, tone adjustment, context-aware completions. Token-by-token streaming via WebSocket. Debounce on regenerate button (2s).

**FR-2.13.12 — Blocked Response Manager (F-058):** The system SHALL capture AI responses blocked by Guardrails AI. Admin review queue with edit/approve/dismiss/ban options. Second Guardrails check before delivery. Banned patterns → auto-blocked in future.

**FR-2.13.13:** The system SHALL support ticket routing based on: ticket type, customer tier, sentiment score, confidence score, variant tier capabilities, and DND rules.

**FR-2.13.14:** The system SHALL maintain complete ticket history in the audit trail even after resolution or closure.

**FR-2.13.15 — Ticket MCP Server:** The system SHALL provide a ticketing_server.py MCP server for standardized ticket operations.

### 2.14 Voice Call Handling System

**FR-2.14.1 — Voice-First Rule (HARD-CODED):** When an incoming call is detected, PARWA MUST answer with voice first. No option to redirect to text-only or IVR-only for initial response.

**FR-2.14.2:** The system SHALL answer incoming calls within 2 rings (<6 seconds) with a natural language greeting in the client's brand voice.

**FR-2.14.3 — Incoming Call Flow (4 Steps):** Step 1 (Call Detection) — Twilio webhook triggers, identify client by phone number, load brand settings + customer history. Step 2 (Voice Greeting) — personalized, brand voice, VIP special treatment, GSD State initiation. Step 3 (Intent Recognition) — classify Refund/Status/Complaint/Question/VIP/Emergency. Step 4 (Conversation Management) — voice for standard, SMS links for complex, human transfer for legal/angry/VIP.

**FR-2.14.4 — Mandatory Voice Response Rules (5 HARD-CODED):** First response MUST be voice. Never ask customer to press buttons. Never say "visit website" first. Say "All agents busy" not "System down". Always offer callback if wait >2 minutes.

**FR-2.14.5 — Response Time Requirements:** Initial greeting <6s, subsequent <3s, human transfer <10s, SMS follow-up <30s.

**FR-2.14.6 — IVR System (F-128):** The system SHALL provide full IVR with self-service routing, AI intent recognition, priority queue management, callback scheduling. DTMF + speech recognition. Configurable menu trees (JSONB). Queue status updates every 5s via Socket.io. 20+ in queue → wait time + callback option. "Representative" keyword → bypass IVR.

**FR-2.14.7 — Voice Call Handling (F-127):** Bi-directional voice calls with AI voice agent integration. Full event tracking, recording, transcription, warm transfers AI→human. All agents busy → queue + wait music + callback. Call drop → follow-up. Recording consent not given → proceed without recording. DNC list → outbound blocked.

**FR-2.14.8 — Outbound / Proactive Voice (F-129):** Abandoned Cart Alert: Jarvis detects → Manager approves script → Jarvis calls. No outbound without manager script approval.

**FR-2.14.9 — Live Call Features:** 2-5 concurrent calls per variant (Mini: 2, PARWA: 3, High: 5). Emergency Intervention / Live Takeover: Manager can listen live and take over instantly. Post-Call Learning: AI flags incorrect info, Manager provides correction, AI learns.

**FR-2.14.10 — Call Sentiment Analysis:** Detect anger from tone/words, confusion from hesitation, urgency from speaking speed. Auto-escalate to human if sentiment <30%.

**FR-2.14.11 — Call Compliance:** Recording disclosure at call start. Consent capture before data processing. Jurisdiction-aware disclosure (two-party consent states). Audit log of all voice interactions. Voice data default 90-day retention.

**FR-2.14.12 — Voice Demo ($1/call via Paddle):** Max 5 minutes. Medium Tier (Gemini-Flash). Net margin ~$0.75/call.

**FR-2.14.13 — Failure Handling:** Reconnect once → SMS callback → log failure → never leave without response. Circuit breaker: 5 consecutive voice failures → auto-pause voice channel.

### 2.15 SMS Handling (Twilio)

**FR-2.15.1:** The system SHALL implement end-to-end SMS via Twilio. Inbound creates/links tickets, AI generates responses, outbound sends.

**FR-2.15.2 — TCPA Compliance:** Full opt-in/opt-out management. STOP/HELP keywords → TCPA auto-processing. Opted-out number → message logged, no auto-response. 7-year TCPA retention.

**FR-2.15.3 — Rate Limiting:** Max 5 SMS per thread per 24 hours per customer (hard cap, non-configurable). Plus 5 SMS/customer/hour.

**FR-2.15.4:** Duplicate MessageSid → idempotency handling. >160 chars → auto-segment. >72hr gap → re-engagement message.

### 2.16 Quality Coach (PARWA High Exclusive)

**FR-2.16.1:** The Quality Coach SHALL analyze Mini/PARWA tickets and suggest improvements to AI performance.

**FR-2.16.2 — Core Analysis Functions:** analyze_conversation_quality() (scores accuracy, empathy, efficiency per interaction), detect_improvement_patterns() (identifies recurring mistakes), generate_training_suggestions() (creates specific training recommendations), calculate_agent_health_score() (overall AI agent performance metric).

**FR-2.16.3 — Reporting Functions:** Weekly quality report, mistake analysis by type, training priority list, export for Agent Lightning, and weekly summary email.

**FR-2.16.4 — Alert Functions:** Real-time alert on performance degradation, alert when same mistake occurs 3+ times, real-time dashboard notifications.

**FR-2.16.5 — Dashboard Components:** QualityScoreCard, MistakeTrendChart, TrainingRecommendationsList, ComparisonWidget, AlertCard, AlertHistory, EscalationButton, SnoozeOption.

**FR-2.16.6 — Agent Lightning Integration:** Quality scores below threshold → training data export. Recurring mistakes → prioritized in training queue. Positive patterns → reinforced in model updates.

**FR-2.16.7 — Post-Interaction QA Rating (F-119):** Auto QA scoring on accuracy, tone, completeness, compliance for every AI-resolved ticket. Score <40 → auto-flagged for review + added to training dataset.

### 2.17 Variant Tiers

**FR-2.17.1 — Mini PARWA ($999/mo):** "The 24/7 Trainee" — Answers FAQs from KB, checks order status, tracks shipments, collects refund requests (NEVER executes), handles up to 200 tickets/day, 2 concurrent phone calls, uses Light Tier primarily, provides basic confidence scores. CANNOT: make decisions, execute refunds, detect fraud patterns, do pattern learning, strategic intelligence. Overage: +$0.10/ticket over threshold. Voice extras: +$75 per additional call slot.

**FR-2.17.2 — PARWA ($2,499/mo):** "The Junior Agent" — All Mini capabilities PLUS: makes intelligent refund recommendations (doesn't execute), troubleshoots technical issues step-by-step, detects patterns and suggests KB updates, 3 concurrent phone calls, self-heals minor errors, generates detailed case summaries, provides confidence scores with reasoning, supports Peer Review (can ask PARWA High for help), drafts responses for manager review, handles up to 300 tickets/day. Overage: +$0.10/ticket.

**FR-2.17.3 — PARWA High ($3,999/mo):** "The Senior Agent" — All PARWA capabilities PLUS: advanced fraud detection (behavioral analysis), 5 concurrent phone calls + video support, coordinates with internal teams, predicts churn risk and triggers retention workflows, provides strategic business intelligence, manages VIP relationships, acts as Quality Coach, handles 500+ tickets/day, approves refunds up to $50 (with limits).

**FR-2.17.4:** All variants SHALL follow the same approval gate rules. Variants differ in: speed, depth of analysis, confidence accuracy, concurrent channel capacity, strategic intelligence level, peer review ability, and sentiment handling capability.

**FR-2.17.5:** "Iron Man" workflow orchestration: when a client subscribes to multiple variants, the Control System routes — FAQs/Order Status → Mini, Logic/Returns → PARWA, VIP/Legal/Crises → PARWA High.

**FR-2.17.6:** Cancellation: anytime, access until billing period ends. No refunds for partial months. No free trials. Payment failure: STOP service immediately (Netflix-style). All pricing in USD.

**FR-2.17.7 — Anti-Arbitrage Matrix (F-006):** The system SHALL detect and prevent subscription tier gaming with 7 signal types: volume_spike, usage_pattern_mismatch, plan_underuse, overage_approaching, burst_pattern, tier_gaming, sharing_suspicion. Risk score 0-100. Rapid plan cycling → tier_gaming signal (+30 risk). Account sharing detection: max 5 sessions (BC-011 Rule 6).

### 2.18 Refund Execution Workflow

**FR-2.18.1:** 3-Step execution: Step 1 (AI Recommendation) — AI queries DB via MCP, checks policy/eligibility/fraud, generates JSON proposal, sets pending_approval. Step 2 (Manager Approve) — Manager clicks "Approve & Refund" in dashboard. Step 3 (Backend Execution) — Backend verifies RLS authorization, executes via Paddle/Stripe with secrets from Doppler, logs audit trail.

**FR-2.18.2:** API keys SHALL NEVER be exposed to frontend or AI.

**FR-2.18.3:** Sequential processing: if one refund in batch fails, others still succeed.

**FR-2.18.4 — Undo System (F-084):** The system SHALL reverse AI-executed actions + recall emails via Brevo API within recall window. Only for AI/auto-approved actions, not manually approved. Partial failure logged.

### 2.19 Self-Service Refunds

**FR-2.19.1:** 3-check Verification Funnel: Email Match → Fraud Score (blocks if >5 refunds in 30 days, account <30 days old, or fraud flag) → Policy Compliance (item returnable, within window).

**FR-2.19.2:** Secure one-time token link sent to customer's email for confirmation.

**FR-2.19.3:** Backend double-checks all 3 verifications before executing via Paddle.

**FR-2.19.4:** Links to Batch Approval auto-approve rules: if "Standard Returns < $50" auto-approved → skip manager, generate self-service token.

### 2.20 Stuck Approval Escalation Ladder

**FR-2.20.1 — 4-Phase Escalation:** Phase 1 (0-24h): Soft reminder every 12h. Phase 2 (24-48h): Backup admin notified, ticket RED. Phase 3 (48-72h): Forced Decision — Auto-Reject OR Auto-Approve (if confidence >95%). Phase 4 (>72h): CEO/Owner crisis alert.

**FR-2.20.2:** "On Hold" option for up to 7 days per ticket (pauses escalation).

**FR-2.20.3:** Escalation check runs hourly via Celery Beat.

**FR-2.20.4 — Approval Reminders (F-081):** Level 1 (2h)=in-app; Level 2 (4h)=in-app+email; Level 3 (8h)=+push; Level 4 (24h)=all channels+cc admin.

**FR-2.20.5 — Approval Timeout (F-082):** Auto-reject after 72h. Reinstate up to 3 times. Financial actions rejected not executed.

### 2.21 Drift Detection & Auto-Correction

**FR-2.21.1:** Three drift metrics daily: Confidence Drift (avg confidence drops >5% for 3 days), Accuracy Drift (approval rate <90% for 3 days), Error Clustering (same error >3 times in 1 day).

**FR-2.21.2 — Auto-Response Scenarios:** Confidence Drift → Downgrade Mode + notify. Accuracy Drift → Revert to Shadow. Error Clustering → Rollback/Vector Cleanup.

**FR-2.21.3:** "System Health" card in Jarvis: Overall Status, Avg Confidence trend, Approval Rate trend, CSAT trend, Root Cause Analysis, Auto-Actions Taken.

**FR-2.21.4 — Drift Detection Report (F-116):** Auto-detects AI performance drift (confidence, errors, topics, resolution). Recommends retraining when drift >70 score. Daily Celery task. Feeds into DSPy and Training Pipeline.

### 2.22 Dynamic Instruction Workflow

**FR-2.22.1:** Clients can create new skills via natural language instructions to Jarvis.

**FR-2.22.2:** System parses NL instructions into step-by-step JSON workflow, detects missing logic gaps, presents draft for confirmation.

**FR-2.22.3:** Tier limits: Mini (max 5 steps, no external APIs), PARWA (max 15 steps, external APIs), High (unlimited).

**FR-2.22.4 — Version Control & A/B Testing (F-096):** The system SHALL support version-controlled instruction sets with A/B testing. Traffic split configurable. Auto-completion when p<0.05 + 100 tickets/variant. One A/B test per agent at a time.

**FR-2.22.5:** Once confirmed, new skill immediately available for next matching customer request.

### 2.23 Dynamic Agent Provisioning

**FR-2.23.1:** Managers can provision new AI agents via Jarvis natural language commands.

**FR-2.23.2:** System parses commands extracting: action, count, variant type, scope (temporary/permanent).

**FR-2.23.3:** Authorization (ADMIN/OWNER/SUPERVISOR only) + budget feasibility checks before provisioning.

**FR-2.23.4:** Single-provision cap: 20 agents max to prevent accidental scaling.

**FR-2.23.5:** Temporary provisions: prorated costs calculated, expiry dates set automatically.

**FR-2.23.6:** New agents immediately inherit client's Brand Voice, FAQ categories, and greeting style.

**FR-2.23.7 — Temp Agent Expiry & Deprovisioning (F-073):** Temporary agents SHALL automatically expire and be deprovisioned at the set date.

### 2.24 Cold Start Handling

**FR-2.24.1:** Synthetic Warm-Up: generates dummy Q&A pairs from uploaded documents using Heavy Tier models.

**FR-2.24.2:** RAG_ONLY strategy for clients <3 days old. RAG_PLUS_FINETUNE after day 3.

**FR-2.24.3:** Honest "I'm still learning" response with low confidence (0.30) when KB doesn't contain answer.

**FR-2.24.4:** Adaptation Messaging: Day 1 (60% accuracy), Day 2 (75%), Day 3+ (90%+).

### 2.25 Non-Financial Undo / Error Correction

**FR-2.25.1 — Recall Protocol:** Stop all AI agents from sending messages about a specific topic immediately via Redis broadcast.

**FR-2.25.2 — Correction Protocol:** Rewrite incorrect drafts. DSPy compiles correction into optimized prompt.

**FR-2.25.3 — Void Protocol:** Flag messages in outbox as voided before delivery.

**FR-2.25.4 — Rage Quit (Emergency Stop):** Channel-specific or global AI activity pause.

**FR-2.25.5:** All corrections feed into Agent Lightning as Negative Reward signals.

### 2.26 Webhook Malformation Handler

**FR-2.26.1:** HMAC signature verification on ALL incoming webhooks; unverified → rejected entirely.

**FR-2.26.2:** Partial Processing: valid signature but missing non-critical fields → save clean data, flag dirty, trigger background re-sync.

**FR-2.26.3:** Idempotency: duplicate webhook within 60s → ignored.

**FR-2.26.4:** Alert when malformation rates exceed 25%/day.

### 2.27 Rate Limiting & DDOS Protection

**FR-2.27.1 — 3-Tier Rate Limiting:** Layer 1 (IP Throttle): 5 req/min/IP via SlowAPI. Layer 2 (Account Throttle): 50 req/hour/user_id via Redis. Layer 3 (Bot Detection): CAPTCHA if >10 complex requests in <60s.

**FR-2.27.2:** Financial endpoints: 5 req/min/IP (stricter).

**FR-2.27.3 — Global Circuit Breaker:** CEO/Owner can trigger global pause. Circuit breaker after 5 consecutive failures on any subsystem.

**FR-2.27.4:** Security-paused users' tickets skipped in batch processing, marked "paused_security".

### 2.28 ROI Calculator & Pricing

**FR-2.28.1:** Interactive ROI Calculator: inputs (monthly labor cost, daily ticket volume, task time split). Outputs: Labor Cost Saved, Manager Time Saved, Total ROI%, Net Profit.

**FR-2.28.2 — Anti-Arbitrage:** Detect multiple Mini purchases instead of PARWA (show hidden cost: manager review time). Detect over-buying (PARWA High for 150 daily tickets → recommend downgrade).

**FR-2.28.3 — Smart Bundle Visualizer (F-005):** Interactive pricing page with toggleable add-on modules (voice AI, multilingual, advanced analytics, custom integrations, priority support). Instant recalculation. Paddle checkout integration.

**FR-2.28.4:** Pricing in USD: Mini $999/mo, PARWA $2,499/mo, PARWA High $3,999/mo. Add-ons: Extra Agent $200/mo, Extra Voice Slot $100/mo, SMS Pack $15/mo.

### 2.29 Omnichannel Memory & RAG

**FR-2.29.1:** Omnichannel memory: customer starts on chat, continues on phone, finishes on email — AI remembers everything via pgvector.

**FR-2.29.2 — RAG Retrieval (F-064):** Every pgvector query MUST include WHERE company_id = :company_id (cross-tenant leakage = critical bug). Shared vector_search.py with mandatory company_id parameter. Configurable similarity threshold per variant: Mini=0.85, PARWA=0.75, High=0.65. Recency boost: ORDER BY (similarity * 0.7 + recency_score * 0.3).

**FR-2.29.3:** MCP (Model Context Protocol) for standardized data integration ports.

**FR-2.29.4 — RAG Re-Indexing (F-153):** Redis lock per document_id (SET NX with 60s TTL). Celery task dedup based on hash(document_id + updated_at). Prevents duplicate re-embedding tasks.

**FR-2.29.5:** Document processing pipeline: text extraction → chunking → vector embedding generation → pgvector storage. Processing status tracking.

### 2.30 DSPy Prompt Optimization (F-061)

**FR-2.30.1:** Automated prompt engineering pipeline using DSPy compiler. Iterative optimization against historical data.

**FR-2.30.2:** A/B testing before promotion. Promotion requires supervisor+ approval.

**FR-2.30.3:** Optimization history tracked per tenant.

### 2.31 Guardrails AI (F-057)

**FR-2.31.1:** Output validation preventing: hallucination, competitor mentions, data leaks, inappropriate content.

**FR-2.31.2:** Second Guardrails check mandatory before delivery (BC-007 Rule 7).

**FR-2.31.3:** Banned patterns stored per tenant for auto-blocking.

### 2.32 Niche Specialization Layer

**FR-2.32.1 — E-commerce:** Shopify/Magento/BigCommerce/WooCommerce APIs, Visual damage verification, Cart recovery workflows, Proactive shipping delay alerts, Product recommendation engine, Handles "Item not received", "Wrong size", "Defective item".

**FR-2.32.2 — SaaS:** GitHub/Stripe/Chargebee/Zendesk/Intercom/Slack/Discord integrations, In-app guidance, Churn prediction based on usage drops, Technical troubleshooting flows, Handles "API errors", "Subscription cancellation", "Feature requests".

**FR-2.32.3 — Logistics:** TMS/WMS integration, Carrier APIs (FedEx, UPS, DHL), GPS tracking, Driver coordination, Proof of delivery automation.

**FR-2.32.4 — Healthcare:** Epic EHR, scheduling platforms, Appointment scheduling, Prescription status, Insurance verification, HIPAA/HITECH compliance awareness, NO PHI in training data, BAA required.

### 2.33 Data Retention & GDPR Compliance

**FR-2.33.1 — 3-Tiered Architecture:** Active Tables (Hot): 30 days after account closure, soft delete PII. Anonymized Logs (Cold): 5 years, hashed PII, admin-only. Deleted: hard delete via background job.

**FR-2.33.2 — Right to be Forgotten (GDPR Art. 17):** Settings → Delete Account → Soft Delete → Hard Delete (async).

**FR-2.33.3 — Data Export (GDPR Art. 15):** JSON/CSV export uploaded to S3, email download link.

**FR-2.33.4:** Automated weekly cron job for inactive users (>6 months).

**FR-2.33.5:** Anonymization via SHA-256 hashing with salt.

### 2.34 Legal Safeguards & Compliance

**FR-2.34.1 — Liability Cap Enforcer:** 1x monthly fees (except gross negligence).

**FR-2.34.2 — SLA Calculator:** 99.5% target, 10% credit per 1% downtime.

**FR-2.34.3 — Immutable Audit Trails:** Append-only, write-once trigger prevents updates. Blockchain-style hashing.

**FR-2.34.4 — Compliance Frameworks:** GDPR, HIPAA, PCI-DSS, SOC 2, CASL, TCPA.

**FR-2.34.5 — KYC/AML Checks:** External KYC provider risk scoring, AML transaction monitoring.

### 2.35 Specialized Detection & Safety Systems

**FR-2.35.1 — VoiceGuard Deepfake Detection:** Voice Print Analysis, Liveness Detection, Risk Score per Call, Auto-Escalation on high risk.

**FR-2.35.2 — Fairness Engine:** Bias Detection Audit, Name-Blind Processing, Equal Treatment Verification, Bias Reporting Dashboard.

**FR-2.35.3 — Hybrid Neural Translation Network (HNTN):** Multi-language translation with error correction.

**FR-2.35.4 — Universal Access Protocol:** Screen Reader support, Real-Time Transcription, TTS, Simplified Language mode, Extended Time for responses.

**FR-2.35.5 — Adaptive Accent Recognition Module (AARM):** Dialect/accent recognition to prevent discrimination.

**FR-2.35.6 — AI Safety Redirects:** AI encouraging self-harm or giving mental health advice → Redirect to professional resources.

**FR-2.35.7 — Graduated Autonomy Demotion:** Error rate >5% over 7 days → automatic revert to Supervised Mode.

### 2.36 Incoming Call Handling (Voice-First)

(Covered in FR-2.14 above)

### 2.37 Proactive Outbound Voice

(Covered in FR-2.14.8 above)

### 2.38 Instant Demo Experience System

(Covered in FR-2.9 Jarvis Onboarding System above)

### 2.39 Performance Tracking, Analytics & Reporting

**FR-2.39.1 — Dashboard Home Overview (F-036):** Primary landing page with unified card-based layout. Personalizes based on user role (agent/supervisor/admin) and tenant plan tier.

**FR-2.39.2 — Activity Feed (F-037):** Live-updating event stream via Socket.io with infinite-scroll pagination and event-type filtering. Events delivered within 500ms. REST fallback when Socket.io down.

**FR-2.39.3 — Key Metrics Cards (F-111):** 6 KPI cards: total tickets, auto-resolved %, avg resolution time, CSAT, avg AI confidence, approval queue depth. Sparklines + period comparison.

**FR-2.39.4 — Trend Charts (F-112):** Interactive line/bar charts for volume, resolution rate, confidence, escalation. Zoom, pan, tooltips, drill-down. CSV/PDF export.

**FR-2.39.5 — ROI Dashboard (F-113):** AI automation cost savings vs human-agent costs. Per-period + cumulative savings. Projected annual savings. Human cost default $12.50/ticket.

**FR-2.39.6 — Confidence Trend Chart (F-115):** Distribution + trends with anomaly highlighting. Percentile bands (P10-P90). Anomaly = >15% below 7-day rolling average.

**FR-2.39.7 — Analytics Data Export (F-117):** CSV and PDF export of analytics data.

**FR-2.39.8 — Performance Comparison (F-114):** Before/after performance comparison dashboard for AI agent changes.

**FR-2.39.9 — Weekly "Wins" Report:** Auto-generated every Monday: tickets handled, money saved, new skills learned, next week prediction.

**FR-2.39.10 — ROI Dashboard (Integrated):** Monthly labor cost, PARWA savings, net result, ROI%. Real-time cost tracker, monthly projection, cost alerts.

### 2.40 Onboarding Wizard (Post-Payment)

**FR-2.40.1 — 5-Step Wizard:** Step 1: Welcome & Overview. Step 2: Legal Consent (Terms, Privacy, AI Data Processing, TCPA, GDPR, call recording disclosure). Step 3: Integration Setup (pre-built connectors + Custom Integration Builder, OAuth flows, test connectivity). Step 4: Knowledge Base Upload (drag-and-drop PDF/DOCX/TXT/CSV, manual FAQ entry, Camera Upload for mobile). Step 5: AI Activation (Name, Tone, Response Style, Greeting Message) + Voice Confirmation + First Victory.

**FR-2.40.2 — First Victory (F-035):** Test ticket → AI responds → confetti celebration → animated savings counter → "Go to Dashboard".

**FR-2.40.3 — Adaptation Tracker (F-039):** 30-Day progress bar, day counter with phase labels, weekly wins banner.

### 2.41 Authentication & Security

**FR-2.41.1 — Registration:** Email/password + Google OAuth. Full name, company name, industry dropdown. Terms checkbox.

**FR-2.41.2 — Login:** Email/password, show/hide toggle, "Remember me", Google OAuth.

**FR-2.41.3 — MFA (F-014):** Password + TOTP (Authy/Google Authenticator), backup codes, 24h re-auth for Control System.

**FR-2.41.4 — Password Management:** Forgot password, reset password, strength meter.

**FR-2.41.5 — Email Verification:** Pending spinner, resend button, auto-refresh.

**FR-2.41.6 — Session Management:** JWT 15min access + 7d refresh tokens. Max 5 concurrent sessions per user.

### 2.42 Billing & Payments

**FR-2.42.1 — Paddle Integration:** Sole payment provider. Webhook handling for: transaction.completed, transaction.payment_failed, subscription.created/updated/cancelled/renewed.

**FR-2.42.2 — Overage Charging (D10):** Daily $0.10/ticket over plan limit, billed via Celery Beat.

**FR-2.42.3 — Subscription Change Proration (F-072):** Paddle subscription changes with proration. All monetary values DECIMAL(10,2).

**FR-2.42.4 — Cancellation Request Tracking (F-026):** Cancellation reason taxonomy, retention offers (discount, feature upgrade, extension, custom plan, freeze), interactions tracking, churn analytics. >$50/month discount → supervisor approval + Jarvis revenue impact.

**FR-2.42.5 — Graceful Cancellation Flow:** 4 options: too expensive→show ROI, not using→free training, integration issues→roadmap, mistakes→reduce autonomy. Pause/Cancel/Get Help buttons.

**FR-2.42.6:** Netflix-style cancellation: no refunds, cancel anytime, access until month end, no partial refunds. Only billing error by PARWA gets full refund.

### 2.43 Integrations

**FR-2.43.1 — Pre-built Connectors:** Shopify, Zendesk, Slack, Freshdesk, Intercom, Help Scout, Custom API, Email, WhatsApp.

**FR-2.43.2 — Custom REST API Connector (F-132):** User-configurable REST integration builder. Arbitrary endpoints, auth (API key, OAuth2, Basic, Bearer), request/response mapping, test connectivity.

**FR-2.43.3 — GraphQL Integration (F-133):** GraphQL API layer for external data querying.

**FR-2.43.4 — Webhook Integration (F-134):** Incoming HTTP POST receiver with HMAC verification, configurable payload mapping, idempotency.

**FR-2.43.5 — MCP Integration (F-135):** Model Context Protocol support. AI agents discover and invoke external tools via standardized MCP server connections. Tool invocation is part of GSD state machine.

**FR-2.43.6 — Database Connection Integration (F-136):** Direct database connection for querying external data sources.

**FR-2.43.7 — Outgoing Webhooks (F-138):** Configurable outgoing webhooks for event-driven integrations.

**FR-2.43.8 — Integration Health Monitor (F-137):** Per-connector status, last sync, error tracking.

**FR-2.43.9 — MCP Server Inventory:** 10 servers: Knowledge (FAQ 5001, RAG 5002, KB 5003), Integration (Email 5101, Voice 5102, Chat 5103, Ticketing 5104), Tools (Notification 5201, Compliance 5202, SLA 5203).

### 2.44 Email Handling

**FR-2.44.1 — Inbound:** Brevo Inbound Parse webhook for receiving customer emails.

**FR-2.44.2 — Outbound:** Brevo templates, Jinja2, 5 replies/thread/24h (hard cap), 100 emails/company/day. No raw PII in subjects. Unsubscribe links.

**FR-2.44.3 — OOO/Auto-Reply Detection (F-122):** Detect out-of-office and auto-reply emails. Prevent AI from treating OOO as customer inquiry.

**FR-2.44.4 — Bounce & Complaint Handling (F-124):** Process bounce webhooks from Brevo. Update customer email status (active/soft_bounced/hard_bounced/complained/suppressed). Alert on deliverability risk. 3 soft bounces in 7 days → auto-suppressed.

**FR-2.44.5 — Email Rate Limiting (F-123):** Hard cap: 5 automated emails per thread per 24h per customer. Non-configurable. Rolling window.

### 2.45 Landing Page & Public Pages

**FR-2.45.1 — Landing Page (F-001):** Dynamic marketing page with industry-specific content (e-commerce, SaaS, healthcare, fintech, education, real estate, logistics). Feature Carousel (5 slides). Hero Section with interactive Jarvis preview. "Why Choose PARWA" section. "How It Works" 4-step animation. Dogfooding Banner. Footer with newsletter signup.

**FR-2.45.2 — Pricing Page:** 3 variant cards (Mini $999, PARWA $2,499, High $3,999). Variant Detail Modal. Smart Bundle Visualizer. Anti-Arbitrage Matrix.

**FR-2.45.3 — ROI Calculator (/calculator):** Input Section, Results Dashboard, Anti-Arbitrage Alert, CTA Section.

### 2.46 Notification System

**FR-2.46.1 — Notification Types:** Soft reminder emails (pending approvals), backup admin notification, crisis override alert, angry customer alert, weekly wins report, drift detection alerts, webhook health alerts, security alerts, external system alerts, graduated autonomy unlock, seasonal spike forecast, growth nudge (>90% plan usage for 3 days), quality drop notification, recurring pattern alert, batch ready notification, VIP customer alert, first victory celebration, proactive shipping delay alerts, abandoned cart alerts, SMS follow-ups, callback offers, data deletion warnings, SLA credit notifications, provisioning status, context limit popup.

**FR-2.46.2 — Notification Preferences (D19):** Per-user, per-channel (email/SMS/in_app/push), per-event-type enable/disable.

**FR-2.46.3 — Outgoing Webhooks (D22):** Configurable outgoing webhooks for event-driven integrations to external systems.

### 2.47 Trust Preservation Protocol

**FR-2.47.1:** When external systems (Shopify, Stripe, LLM providers) fail, implement two-layer response: Customer-facing (graceful, informative, alternative options) + Manager-facing (detailed error, root cause, resolution timeline).

**FR-2.47.2:** Auto-suggested by System Status Panel when all LLM providers degraded. Gracefully reduces AI automation level. Maintains cached responses for common queries.

### 2.48 Answer Consistency Engine

**FR-2.48.1:** Fingerprinting of answers to detect inconsistent responses to same/similar questions across conversations.

**FR-2.48.2:** Checker validates consistency. Deviation alert triggered on inconsistencies. Versioning for answer updates.

### 2.49 Multi-Agent Orchestration

**FR-2.49.1:** Task Decomposer breaks complex tasks into sub-tasks.

**FR-2.49.2:** Specialist Agents handle different domains.

**FR-2.49.3:** Coordinator Agent orchestrates multi-agent workflows.

**FR-2.49.4:** Workflow Templates for common multi-agent scenarios.

### 2.50 Live AI Demo Widget (F-003)

**FR-2.50.1:** The system SHALL provide an embedded chat widget on public pages for anonymous visitors to interact with live AI. 20 messages per session, then sign-up CTA.

**FR-2.50.2:** Anonymous session via `widget_token` (no account required). Smart Router Light tier with PII redaction. Socket.io real-time streaming.

**FR-2.50.3:** IP-hash rate limit: 60 messages per 5 minutes. 30-minute session expiry.

**FR-2.50.4:** LLM failure = cached sample Q&A + "temporarily unavailable" message. PII in messages redacted as `[REDACTED]`.

### 2.51 Pricing Page with Variant Cards (F-004)

**FR-2.51.1:** Three plan cards: Starter ($999), Growth ($2,499), High ($3,999). Annual toggle with 20% discount. Growth highlighted as "Most Popular".

**FR-2.51.2:** Feature comparison matrix (12 features). "Get Started" triggers Paddle checkout (F-020). Responsive: 3-col → stacked mobile.

**FR-2.51.3:** Paddle SDK load failure = graceful fallback. Legacy names ("trivya", "mini", "junior") forbidden in UI or code.

### 2.52 Ticket List — Filterable, Sortable (F-046)

**FR-2.52.1:** Paginated, multi-column ticket table with real-time Socket.io updates. Filters: status, channel, assignee, priority, date range, full-text search.

**FR-2.52.2:** Sort by any column, default created_at DESC. Page sizes: 25/50/100. Row hover preview (150 chars).

**FR-2.52.3:** Real-time new-ticket animation via Socket.io. VIP/Legal tickets highlighted. Sub-500ms response target. Cross-tenant isolation enforced.

### 2.53 Ticket Detail Modal (F-047)

**FR-2.53.1:** 60% screen width slide-in panel showing full conversation, metadata sidebar, pending actions, and internal notes.

**FR-2.53.2:** Conversation thread: customer (blue/left), AI/agent (gray/right), notes (yellow). Metadata sidebar: classification, confidence breakdown, sentiment, customer profile.

**FR-2.53.3:** Action bar: Approve/Reject/Edit for pending actions. Internal notes with optimistic update. Attachments with download links. Long conversations paginated (50 messages). Cross-tenant access = 404.

### 2.54 Model Failover & Rate Limit Handling (F-055)

**FR-2.54.1:** Circuit breaker per model: CLOSED → OPEN (5 failures) → HALF_OPEN (60s cooldown) → probe → CLOSED/OPEN.

**FR-2.54.2:** Failover chain: same-tier next model → escalate tier → queue → graceful degradation.

**FR-2.54.3:** Per-model health monitoring (Redis 1-min rolling windows). Health snapshots aggregated by Celery beat. Manual circuit reset API.

**FR-2.54.4:** Permanent disable on auth errors (401/403) with ops alert. Health dashboard data feeds System Status Panel.

### 2.55 PII Redaction Engine (F-056)

**FR-2.55.1 — Dual-Direction Redaction:** Ingress: regex scan → replace with placeholders (`[EMAIL_1]`, `[PHONE_2]`) → store in encrypted vault. Egress: restore original values from vault for authorized agents.

**FR-2.55.2 — Patterns:** email, SSN, credit card, phone, IP, DOB, address, ZIP, driver's license, bank account, passport. Context-required matching for bank account/passport (near banking keywords).

**FR-2.55.3:** GDPR vault purge endpoint. PII never stored unredacted in DB. Session-scoped vault with TTL.

### 2.56 LangGraph Workflow Engine (F-060)

**FR-2.56.1:** Stateful graph execution with conditional branching. Workflow nodes: classify → collect_info → verify → execute → confirm.

**FR-2.56.2:** Integration with GSD State Engine (F-053) for state persistence. Human-in-the-loop handoff nodes.

**FR-2.56.3:** Workflow templates per intent category. Error recovery with retry nodes. Real-time workflow progress visible to agents.

### 2.57 Approval Queue Dashboard (F-074)

**FR-2.57.1:** Centralized command center for AI-initiated actions requiring human review. Summary bar: Pending, Approved Today, Rejected Today, Overdue counts.

**FR-2.57.2:** Default sort: VIP → confidence ascending → age ascending. Filters: action type, confidence range, date range, VIP toggle.

**FR-2.57.3:** Batch approve/reject with confirmation dialog. Real-time count updates via Socket.io.

### 2.58 Individual Ticket Approval/Reject (F-076)

**FR-2.58.1:** Full ticket context + AI-proposed action detail. Confidence breakdown (retrieval, intent_match, history, sentiment).

**FR-2.58.2:** "Approve", "Reject", "Edit & Approve" actions. Edit allows modifying amount/details before approval.

**FR-2.58.3:** All decisions audit-logged with reason. Auto-approve rules (F-078) bypass if threshold met.

### 2.59 Auto-Approve Confirmation Flow (F-078)

**FR-2.59.1:** Displays impact: "X tickets/day will be auto-approved". Requires explicit enable confirmation.

**FR-2.59.2:** Per-action-type rules (refund, subscription_change, etc.). Confidence threshold configuration per rule. Consequence preview shows financial totals. Rule changes logged for audit.

### 2.60 Proactive Self-Healing (F-093)

**FR-2.60.1:** Retry with exponential backoff (2s, 4s, 8s) per provider. Fallback chains: LLM (next model → next tier → queue), Brevo (backup key → delayed Celery), Shopify (cached data → queue), Paddle (queue → alert).

**FR-2.60.2:** Circuit breaker integration. Trust Preservation Protocol: reassuring messages while healing.

**FR-2.60.3:** Human escalation after 15 min of failed retries. Technique failure recovery: Tier 3→2→1 fallback (no skipping). Per-technique health monitoring. All events logged.

### 2.61 Model Validation — Post-Training (F-104)

**FR-2.61.1:** Quality gate between training and deployment. Test batteries: accuracy, confidence calibration, regression (200 golden cases), edge-case (100 adversarial), latency, safety (50 guardrails tests).

**FR-2.61.2:** Pass thresholds: accuracy ≥85%, F1 ≥80%, regression ≤5%, safety 100%. Weighted overall score must be ≥80%. Holdout dataset: 20% stratified split.

**FR-2.61.3:** Celery task with 30-min timeout. Manual override possible (supervisor+ with documented reason). Insufficient data (<100 samples) = auto-fail.

### 2.62 Model Deployment with Auto-Rollback (F-105)

**FR-2.62.1:** Zero-downtime canary deployments. Canary stages: 5% (15 min) → 25% (5 min) → 50% (5 min) → 100%.

**FR-2.62.2:** Rollback triggers: error rate >10%, confidence <70%, escalation >2x, CSAT <3.0, P95 latency >3000ms. Auto-rollback instantly redirects to previous model.

**FR-2.62.3:** Pre-deployment snapshot for rollback reference. Manual rollback and force-promote APIs. 24-hour post-deployment monitoring at 100%.

### 2.63 Email Handling — Detailed (F-120, F-121)

**FR-2.63.1 — Outbound (F-120):** Brevo SMTP API for outbound emails. Templates per notification type. Rate limiting: 5 emails per thread per 24h. PII redaction in outbound emails. Delivery status tracking (sent, delivered, bounced). Queue via Celery on Brevo failure.

**FR-2.63.2 — Inbound (F-121):** Brevo Parse webhook receives incoming emails. HMAC-SHA256 verification. Email → ticket creation or append to existing thread (by In-Reply-To/References headers). Attachment handling and storage. HTML stripping for AI processing (preserve for agent view). Async Celery processing, respond within 3s.

### 2.64 Pre-built Connectors (F-131)

**FR-2.64.1:** Library of pre-built connectors: Shopify, GitHub, Zendesk, Freshdesk, Slack, Intercom, Help Scout, WhatsApp.

**FR-2.64.2:** Per-connector configuration (OAuth or API key). Test connectivity validation. Data sync via Celery beat schedules. Webhook ingestion for real-time events.

**FR-2.64.3:** Credentials encrypted at rest (AES-256). OAuth token auto-refresh on expiry. Rate limiting per connector. Error handling with retry logic.

### 2.65 Circuit Breaker (F-139)

**FR-2.65.1:** Per-provider circuit state: CLOSED → OPEN (5 failures/60s) → HALF_OPEN (60s cooldown) → probe → CLOSED/OPEN.

**FR-2.65.2:** Applies to: LLM providers, Brevo, Twilio, Paddle, Shopify, all integrations. Global provider outage = single aggregated alert.

**FR-2.65.3:** Circuit state persisted and recoverable. Manual circuit reset API. Integration with Self-Healing (F-093). Circuit state dashboard in System Status Panel.

### 2.66 Authentication — Detailed (F-010 to F-019)

**FR-2.66.1 — User Registration (F-010):** Secure registration with full name, email, company name, password. Real-time validation (email availability, password strength). Creates companies + users records linked by company_id. Password: bcrypt cost 12, min 8 chars + uppercase + lowercase + number + special. Rate limit: 5 registrations/IP/hour.

**FR-2.66.2 — Google OAuth (F-011):** OpenID Connect with PKCE. New user → auto-create account → redirect to onboarding. Existing user → issue JWT pair, rotate refresh token. Google Workspace domain auto-detection. Cross-company email rejection. Reused refresh token → invalidate ALL tokens → force re-auth.

**FR-2.66.3 — Login System (F-013):** JWT: access (15 min) + refresh (7 days, rotated). HTTP-only, Secure, SameSite=Strict cookies. 5 failed attempts → 15-min lockout. Max 5 concurrent sessions (oldest terminated). Unverified users blocked. Refresh token replay = invalidate ALL user tokens.

**FR-2.66.4 — MFA Setup (F-015):** Generates TOTP secret, QR code data URL, 10 backup codes. Temp secret stored in Redis (10-min TTL) until verified. Secret promoted to AES-256 encrypted mfa_secret. 30-second clock drift tolerance. 5 failed MFA codes → 15-min lockout + email alert.

**FR-2.66.5 — Backup Codes (F-016):** 10 single-use codes per set (10-char alphanumeric). Stored as SHA-256 hashes; plaintext shown exactly once. Regeneration requires current TOTP + invalidates all existing codes. Used code triggers MFA re-setup prompt. All codes used = must contact support.

**FR-2.66.6 — Session Management (F-017):** View all active sessions: device, browser, masked IP, location, last activity. Revoke individual sessions or "Sign out all other devices". Current session cannot be self-revoked. Max 5 concurrent sessions. Celery beat cleans expired sessions daily.

**FR-2.66.7 — Advanced Rate Limiting (F-018):** Redis-backed sliding-window rate limiter with progressive lockout. Auth: 10 req/min per email, 15-min lockout after 5 failures. Password recovery: 3 req/hour per email. General GET: 100 req/min per IP. Financial POST: 20 req/min per user. Integration: 60 req/min per API key. Demo chat: 60 req/5min per IP hash. Progressive delays: 0s→2s→4s→8s→lockout. Rate limit headers on every response. Redis down = fail-open with warning log.

**FR-2.66.8 — API Key Management (F-019):** Key format: `parwa_live_<32-char>` or `parwa_test_<32-char>`. Full key shown only at creation/rotation; stored as SHA-256 hash. Scopes: read, write, admin, approval. Rotation: 24-hour grace period for old key. Max 10 keys per tenant. All key operations audit-logged.

### 2.67 Billing — Detailed (F-020 to F-027)

**FR-2.67.1 — Paddle Checkout (F-020):** Paddle.js SDK loaded from CDN. `Paddle.Checkout.open()` with price ID + custom data (company_id, user_id). Unauthenticated users redirected to register first. Success redirect → verification. Cancel redirect → cancelled page. Paddle SDK load failure = graceful fallback.

**FR-2.67.2 — Paddle Webhooks (F-022):** HMAC-SHA256 signature verification (constant-time compare). Idempotency via UNIQUE (provider, event_id). Async Celery processing (respond within 3s). Event types: subscription.created/updated/cancelled/past_due/paused/resumed, payment.succeeded/failed, transaction.completed. Retry 3x (60s, 300s, 900s backoff). DLQ alert on exhaustion.

**FR-2.67.3 — Subscription Management (F-021):** Plan changes delegated to Paddle API for proration. Downgrade: features continue until period end; agent deprovisioning scheduled via Celery. Upgrade: features activated immediately. Confirmation dialog showing feature loss/agent impact on downgrade. Atomic transactions; Paddle failure = rollback.

**FR-2.67.4 — Invoice History (F-023):** Paginated, searchable list of all invoices synced from Paddle. Filters: status, date range. PDF redirect to Paddle-hosted files. Cross-tenant isolation.

**FR-2.67.5 — Daily Overage Charging (F-024):** Celery beat cron at 02:00 UTC. Overage = tickets beyond plan limit × $0.10. Idempotency: UNIQUE (company_id, charge_date). DECIMAL(10,2) amounts. Paddle charge with 3 retries. Email notification if charge >$10. Skip non-active subscriptions.

**FR-2.67.6 — Payment Confirmation (F-027):** Polls GET /api/billing/verify-checkout every 3s (max 60s). Checks if webhook processed → updates company plan/status → redirects to onboarding. Welcome email via Brevo. Cross-tenant session check (403). Timeout = "Check email" message.

### 2.68 Onboarding — Detailed (F-028 to F-035)

**FR-2.68.1 — Onboarding Wizard (F-028):** 5-step wizard: Company Profile → Legal Consent → Integration → Knowledge Base → AI Activation. Steps 2 and 5 mandatory (cannot skip). Steps 1, 3, 4 skippable with reason. Auto-save after each step; resume on return. Incomplete onboarding = redirect to wizard from dashboard.

**FR-2.68.2 — Custom Integration Builder (F-031):** Integration types: REST, GraphQL, Webhook In, Webhook Out, Database. Config per type (URL, headers, auth, templates, mapping). Test connectivity with response preview + latency. Limits: 5 custom (PARWA), 20 (High). AES-256 encrypted credentials. Parameterized query templates only (no raw SQL). Webhook HMAC verification. 3 consecutive sync failures = error status.

**FR-2.68.3 — KB Processing & Indexing (F-033):** 4-stage pipeline: extract (using `unstructured` library) → chunk (512 tokens, 64 overlap) → embed (Smart Router Light tier) → index (pgvector VECTOR(1536)). Per-document progress tracking. Retry from failed stage (not from scratch). SHA-256 duplicate detection. 10-min timeout per document, max 3 retries. Corrupted PDF = failed with descriptive error.

**FR-2.68.4 — AI Activation (F-034):** 3 prerequisites: legal consent, integration active, KB indexed (≥1 chunk). Readiness check endpoint with pass/fail per prerequisite. Activation sets ai_active=true, initializes confidence thresholds, starts 30-day adaptation. Brevo welcome email. Admin/owner role required. Idempotent (double-activation = no-op).

---

## 3. Non-Functional Requirements

### 3.1 Performance

**NFR-3.1.1:** Initial voice greeting response <6 seconds.

**NFR-3.1.2:** Subsequent voice responses <3 seconds.

**NFR-3.1.3:** Chat API response <2 seconds for Light Tier queries.

**NFR-3.1.4:** Ticket classification <3 seconds with ≥70% confidence.

**NFR-3.1.5:** Socket.io event delivery within 500ms.

**NFR-3.1.6:** Dashboard page load <2 seconds.

**NFR-3.7:** Jarvis command execution <2 seconds.

**NFR-3.1.8:** Full-text search results <1 second.

**NFR-3.1.9:** System SHALL handle 500+ tickets/day per tenant (PARWA High tier).

### 3.2 Availability & Reliability

**NFR-3.2.1:** 99.5% uptime SLA target.

**NFR-3.2.2:** Safety Failover Loop: try/except through available models until success (99.9% AI uptime target).

**NFR-3.2.3:** RTO: 1 hour, RPO: 1 hour for disaster recovery.

**NFR-3.2.4:** PostgreSQL: daily full + continuous WAL archiving, 30-day retention + PITR.

**NFR-3.2.5:** Redis: hourly RDB + real-time AOF, 7-day retention.

### 3.3 Security

**NFR-3.3.1 — Multi-Tenancy Isolation:** Row-Level Security on all client data tables. Every DB query scoped by company_id (BC-001). Cross-tenant leakage = critical bug.

**NFR-3.3.2 — Webhook Security:** HMAC-SHA256 verification, constant-time compare to prevent timing attacks.

**NFR-3.3.3 — PII Redaction:** Local Python layer masks credit cards, SSNs, bank account info before any LLM call. PII detection accuracy target: 90%+.

**NFR-3.3.4 — Input Validation:** Pydantic models + bleach HTML sanitization, type enforcement. XSS sanitization on all template variables.

**NFR-3.3.5 — Secrets Management:** Doppler (NOT .env files). Git policies enforced.

**NFR-3.3.6 — MFA:** Password + TOTP (Authy/Google Authenticator), backup codes, 24h re-auth for Control System.

**NFR-3.3.7 — Immutable Audit Trails:** Append-only, write-once trigger, blockchain-style hashing.

**NFR-3.3.8 — Rate Limiting:** SlowAPI + Redis (3-tier: IP, Account, Bot).

**NFR-3.3.9 — Zero Trust:** System doesn't trust itself, users, or external APIs without verification.

**NFR-3.3.10 — Prompt Injection Detection:** Target 95%+ detection rate for SQL injection, XSS, command injection, role-playing attacks. Multi-turn attack detection.

**NFR-3.3.11 — Circuit Breakers:** On all subsystems. 3 consecutive failures confirm "down" status. 5 consecutive failures → circuit breaker open.

**NFR-3.3.12 — RLS Tests on Every Commit** (from Week 3 of build).

**NFR-3.3.13 — Semgrep Static Analysis** on every CI run.

### 3.4 Scalability

**NFR-3.4.1:** Kubernetes HPA: 3-50 replicas, CPU 70%, memory 80% thresholds.

**NFR-3.4.2:** PgBouncer connection pooling for PostgreSQL.

**NFR-3.4.3:** SQLAlchemy QueuePool for backend connection pooling.

**NFR-3.4.4:** Redis maxmemory 2GB, allkeys-lru eviction.

**NFR-3.4.5:** Celery worker concurrency configurable per queue.

### 3.5 Maintainability

**NFR-3.5.1:** All code SHALL follow the 14 Building Codes (BC-001 through BC-014).

**NFR-3.5.2:** Python: type hints, Google-style docstrings, PEP 8, max 40 lines/function, no magic numbers.

**NFR-3.5.3:** TypeScript: strict: true, no `any`, PascalCase components, max 50 lines/component.

**NFR-3.5.4:** Database: Alembic migrations, forward-only, every table has company_id column.

**NFR-3.5.5:** Test coverage: 80% for services, 100% for financial/auth.

**NFR-3.5.6:** 10-step CI/CD pipeline: Checkout → Setup → Install → Lint → Test → Build → Security Scan → Deploy → Verify → Notify.

### 3.6 Compliance

**NFR-3.6.1:** GDPR (Articles 15, 17), TCPA (call recording, consent), CASL (Canada), PCI-DSS (payment data), SOC 2 (audit controls).

**NFR-3.6.2:** Data residency options: US, EU (AWS EU regions), APAC (Singapore/Tokyo).

**NFR-3.6.3:** Call recording disclosure, consent capture, jurisdiction-aware compliance.

**NFR-3.6.4:** 7-year TCPA retention for SMS records.

### 3.7 Observability

**NFR-3.7.1:** Prometheus + Grafana monitoring with 9 scrape targets and 9 dashboards.

**NFR-3.7.2:** Sentry error tracking.

**NFR-3.7.3:** PostHog analytics.

**NFR-3.7.4:** Statuspage.io for incident communication.

**NFR-3.7.5:** Structured logging with correlation IDs.

---

## 4. User Classes & Roles

### 4.1 Client / Business Owner
- Hires AI workforce (selects variants)
- Sets initial mode (Shadow/Supervised)
- Views ROI dashboard
- Can cancel subscription
- Configures legal compliance settings
- Views audit trails
- Approves/denies AI recommendations
- Creates auto-approve rules
- Manages onboarding/integration
- Receives Crisis Override alerts (>72h stuck tickets)

### 4.2 Manager / Admin
- Reviews and approves/denies AI recommendations (Approve, Deny, Request More Info, Shadow This Type)
- Batch approves similar requests
- Creates "Always Auto-Approve This Type" rules
- Uses Jarvis natural language commands
- Emergency pause controls (Pause All AI, Pause Refunds, Pause Account Changes, Pause Phone)
- Mode changes (Return to Shadow, Switch to Supervised)
- Live takeover of phone calls
- Draft review (AI writes, Manager edits/sends)
- Views real-time activity feed
- Views performance reports
- Receives escalation notifications
- Provisions new agents via Jarvis
- MFA required (24h re-auth for Control System)
- Quick command presets (max 50 per tenant)

### 4.3 Backup Admin
- Receives notifications when primary manager is unresponsive (>24h)
- Can approve/deny tickets when primary is unavailable

### 4.4 CEO / Owner
- Receives Crisis Override alerts (>72h stuck tickets)
- Can trigger global emergency pause (DDOS shield)
- Can authorize global circuit breaker

### 4.5 Human Agent (Team Member)
- Handles escalated tickets (VIP, legal, complex)
- Takes over live calls
- Reviews AI drafts and sends
- Views assigned tickets

### 4.6 Customer / End User
- Interacts via supported channels
- Can trigger self-service refunds (via secure portal)
- Can request data export (GDPR Art. 15)
- Can delete account (GDPR Art. 17)

### 4.7 System Administrator (PARWA Internal)
- Admin dashboard: client list, health monitoring, service status, cost tracking, incidents
- API provider management
- System health monitoring

---

## 5. External Interfaces

### 5.1 AI/ML Services
| Service | Purpose | Integration |
|---------|---------|------------|
| Own API Keys (LiteLLM) | LLM inference (Light/Medium/Heavy tiers) | REST API via LiteLLM proxy |
| Unsloth + Google Colab | Model fine-tuning (free tier) | Python API |
| RunPod | Model fine-tuning (paid automation) | REST API |
| pgvector | Vector database for RAG | PostgreSQL extension |
| Guardrails AI | Output validation | Python library |
| DSPy | Automatic prompt optimization | Python library |
| LangGraph | Agentic workflow engine | Python library |
| LangChain | LLM wrapper | Python library |

### 5.2 Communication Services
| Service | Purpose | Integration |
|---------|---------|------------|
| Twilio | Voice calls, SMS, OTP verification | REST API + Webhooks |
| Brevo | Email sending + inbound parsing | REST API + Webhooks |
| Socket.io | Real-time dashboard updates | WebSocket |

### 5.3 Payment Services
| Service | Purpose | Integration |
|---------|---------|------------|
| Paddle | Subscription billing, payments, webhooks | REST API + Webhooks |

### 5.4 Infrastructure Services
| Service | Purpose | Integration |
|---------|---------|------------|
| Google Cloud Platform | Compute Engine VM, Cloud Storage | REST API |
| Vercel | Frontend hosting | Git-based deployment |
| AWS S3 + CloudFront | Static assets, CDN | REST API |
| Doppler | Secrets management | CLI + API |
| Redis | Caching, message queue, rate limiting, pub/sub | TCP |
| PostgreSQL | Primary database + pgvector | TCP |
| Celery | Background job processing | Redis broker |

### 5.5 E-commerce Integrations
| Service | Purpose |
|---------|---------|
| Shopify API | Orders, products, customers |
| Magento API | Orders, products, customers |
| BigCommerce API | Orders, products, customers |
| WooCommerce | Orders, products, customers |
| AfterShip | Shipment tracking |
| 17Track | Shipment tracking |
| Klaviyo | Email marketing |

### 5.6 SaaS Integrations
| Service | Purpose |
|---------|---------|
| GitHub / GitLab | Technical support |
| Stripe / Chargebee | Billing support |
| HubSpot / Salesforce | CRM |
| Intercom / Zendesk / Help Scout | Support desk |
| Slack / Discord | Communication |

### 5.7 Logistics Integrations
| Service | Purpose |
|---------|---------|
| FedEx / UPS / DHL APIs | Carrier tracking |
| TMS / WMS | Transportation/Warehouse management |
| GPS Tracking APIs | Real-time tracking |

### 5.8 Monitoring & Analytics
| Service | Purpose |
|---------|---------|
| Prometheus | Metrics collection |
| Grafana | Dashboard visualization |
| Sentry | Error tracking |
| PostHog | Product analytics |
| Statuspage.io | Incident communication |

---

## 6. Data Requirements

### 6.1 Database Architecture

**NFR-6.1.1:** PostgreSQL 15+ on GCP VM with pgvector extension. Self-hosted (NOT Supabase).

**NFR-6.1.2:** PgBouncer connection pooling, SSL encryption.

**NFR-6.1.3:** Alembic migrations, forward-only.

**NFR-6.1.4:** Application-level row-level security via middleware (company_id on every table, every query scoped).

**NFR-6.1.5:** Financial values: Numeric(19,4), NEVER FLOAT. Python: decimal.Decimal.

### 6.2 Core Database Tables (90+)

**User & Auth:** users, companies, api_keys, user_notification_preferences  
**Subscriptions:** subscriptions, overage_charges, cancellation_requests, newsletter_subscribers  
**Tickets & Support:** support_tickets, ticket_messages, ticket_intents, classification_corrections, ticket_assignments, assignment_rules, customers, sessions, interactions, customers_channels, channel_configs, identity_match_log, customer_merge_audit  
**AI & Knowledge:** knowledge_documents, document_chunks (VECTOR 1536), agents, training_runs, training_datasets, training_samples, training_data_points, agent_mistakes, prompt_templates, optimization_runs, optimization_iterations, prompt_ab_tests, instruction_sets, instruction_versions, instruction_ab_tests, instruction_ab_assignments  
**Approval & Control:** approval_queues, approval_records, approval_reminder_log, approval_reminder_preferences, semantic_clusters, cluster_tickets, confidence_scores, confidence_thresholds, emergency_states, executed_actions, undo_log  
**Quality & Analytics:** quality_scores, quality_alerts, training_suggestions, qa_scores, metric_aggregates, analytics_cache, analytics_time_series, roi_snapshots, agent_cost_tracking, confidence_snapshots, drift_reports  
**Communication:** sms_messages, sms_consent, sms_opt_log, voice_calls, voice_call_events, voice_transcripts, ivr_configs, ivr_sessions, call_queue, scheduled_callbacks, email_bounces, customer_email_status, email_deliverability_alerts, email_logs, email_rate_limits, chat_sessions, chat_messages, copilot_suggestions, context_compressions  
**Integrations:** integrations, rest_connectors, connector_usage_logs, webhook_integrations, webhook_events, mcp_connections, mcp_invocation_logs, outgoing_webhooks  
**Jarvis:** jarvis_sessions, jarvis_messages, jarvis_knowledge_used, jarvis_action_tickets, demo_sessions  
**Billing:** pricing_add_ons, pricing_bundle_discounts, saved_bundles, pricing_tiers, anti_arbitrage_assessments, anti_arbitrage_signals, anti_arbitrage_nudges, usage_snapshots  
**Onboarding:** user_details, onboarding_state, consent_records, demo_sessions, demo_messages, business_email_otps, industry_variants, pricing_variants  
**Audit & Compliance:** audit_trail (append-only, immutable trigger), compliance_requests  
**Error & Health:** error_log, system_health_snapshots, system_incidents, guardrails_blocked_queue, guardrails_banned_patterns, guardrails_audit_log  
**Sentiment:** sentiment_scores, sentiment_thresholds  
**Demo:** voice_demo_sessions, voice_demo_payments, voice_demo_analytics, landing_industries, landing_testimonials, landing_use_cases, landing_page_analytics, demo_requests  
**Command Presets:** command_presets, command_executions  
**Landing:** landing_industries, landing_testimonials, landing_use_cases, landing_page_analytics, demo_requests

### 6.3 Redis Architecture

**NFR-6.3.1:** Redis 7+ for caching, message queue, rate limiting, real-time pub/sub, session management.

**NFR-6.3.2:** Key patterns: `parwa:{company_id}:gsd:{ticket_id}` (GSD state), `parwa:{company_id}:recent_errors` (error log), `parwa:health:{subsystem}` (health checks), `signal_cache:{company_id}:{variant_type}:{query_hash}` (signal cache).

**NFR-6.3.3:** maxmemory 2GB, allkeys-lru eviction. AOF persistence.

### 6.4 Data Migration

**NFR-6.4.1:** Alembic migration groups: 11+ groups covering all table categories.

**NFR-6.4.2:** Forward-only migrations. No rollback scripts.

**NFR-6.4.3:** Every table: company_id column (indexed, NOT NULL), FK ON DELETE CASCADE.

**NFR-6.4.4:** Soft deletes: deleted_at TIMESTAMP.

---

## 7. Constraints & Assumptions

### 7.1 Technical Constraints

**C-7.1.1:** Backend: FastAPI (Python 3.11+) only. No other backend framework.

**C-7.1.2:** Frontend: Next.js 15+ with TypeScript. No other frontend framework.

**C-7.1.3:** Database: PostgreSQL only (self-hosted on GCP VM). No Supabase, no MySQL, no MongoDB.

**C-7.1.4:** Cache/Queue: Redis + Celery only. No BullMQ, no RabbitMQ.

**C-7.1.5:** Real-time: Socket.io only. No Supabase Realtime.

**C-7.1.6:** Payment: Paddle only. No Stripe for billing (Stripe removed per D1).

**C-7.1.7:** Auth: Self-built JWT + Google OAuth only. Microsoft OAuth removed (D11). No Supabase Auth.

**C-7.1.8:** Email: Brevo only for sending + inbound. No SendGrid for transactional.

**C-7.1.9:** SMS/Voice: Twilio only.

**C-7.1.10:** Secrets: Doppler only. No .env files in production.

**C-7.1.11:** File Storage: GCP Cloud Storage or S3/Cloudflare R2.

**C-7.1.12:** No GPU training until revenue (Locked Decision #19).

**C-7.1.13:** 50-mistake threshold is HARD-CODED (Locked Decision #20). CI must fail if modified.

### 7.2 Business Constraints

**C-7.2.1:** Pricing fixed in USD: Mini $999, PARWA $2,499, PARWA High $3,999.

**C-7.2.2:** No free trials. No partial month refunds. Netflix-style cancellation.

**C-7.2.3:** Overage rate: $0.10/ticket/day.

**C-7.2.4:** Payment failure = immediate service stop (no grace period).

**C-7.2.5:** Infrastructure target: ~$25-30/mo (free first 10-12 months with GCP credits), >95% gross margins.

### 7.3 Building Codes (14 Mandatory Rules)

| Code | Name | Priority |
|------|------|----------|
| BC-001 | Multi-Tenant Isolation | 1 (Highest) |
| BC-002 | Financial Actions (DECIMAL, atomic, idempotent, audit-logged) | 2 |
| BC-011 | Auth & Security (OAuth 2.0, MFA, JWT) | 3 |
| BC-010 | Data Lifecycle (GDPR, PII encryption) | 4 |
| BC-012 | Error Handling (circuit breakers, graceful degradation) | 5 |
| BC-009 | Approval Workflow (supervisor+ for financial, audit-logged) | 6 |
| BC-003 | Webhook Handling (HMAC, idempotency, async, <3s) | 7 |
| BC-004 | Background Jobs (Celery, company_id first, retry+DLQ) | 8 |
| BC-005 | Real-Time (Socket.io, room-based, event buffering) | 9 |
| BC-006 | Email/SMS (Brevo, 5/thread/24h, templates) | 10 |
| BC-007 | AI Model Interaction (Smart Router, PII redaction, 50-mistake) | 11 |
| BC-008 | State Management (GSD Engine, Redis+PostgreSQL) | 12 |
| BC-013 | AI Technique Routing (3-tier technique architecture) | 13 |
| BC-014 | Task Decomposition (decompose before building, atomic units) | 14 |

### 7.4 Assumptions

**A-7.4.1:** Clients have stable internet connectivity for web dashboard access.

**A-7.4.2:** Clients provide Own API Keys for LLM inference or use system-managed keys.

**A-7.4.3:** Twilio account provisioned for each client requiring voice/SMS.

**A-7.4.4:** Paddle account configured for payment processing.

**A-7.4.5:** Google Cloud Platform credits available for first 10-12 months of infrastructure costs.

**A-7.4.6:** Brevo account provisioned for email sending and inbound parsing.

**A-7.4.7:** Client knowledge base documents provided in supported formats (PDF, DOCX, TXT, CSV).

---

## 8. Use Cases

### UC-01: Customer Submits Refund Request via Chat
**Actor:** Customer, AI Agent, Manager  
**Preconditions:** Customer has active order, client uses PARWA variant  
**Flow:** Customer sends refund request → AI classifies intent as "refund" → Smart Router routes to Heavy Tier → MAKER decomposes into atomic steps → AI checks eligibility and generates proposal → Confidence score calculated → If <95%, ticket enters approval queue → Manager reviews and approves/rejects → If approved, backend executes refund via Paddle → Customer receives confirmation  
**Postconditions:** Refund processed or rejected, all actions logged in audit trail, Agent Lightning captures reward signal

### UC-02: Manager Uses Jarvis to Pause Refunds
**Actor:** Manager  
**Preconditions:** Manager authenticated with MFA  
**Flow:** Manager types "Jarvis, pause all refunds" → Chat-to-Code Parser converts to backend command → Authorization check (ADMIN/SUPERVISOR) → Backend sets emergency_state for refund channel → All pending refund tickets moved to "paused" status → Activity Feed shows red banner → Manager sees confirmation in terminal  
**Postconditions:** Refund processing paused, only resume via Jarvis or dashboard

### UC-03: Angry Customer Calls In
**Actor:** Customer, AI Voice Agent, Human Agent  
**Preconditions:** Client has voice channel active  
**Flow:** Twilio webhook → AI answers within 2 rings (<6s) → Voice greeting in brand voice → Customer speaks → Sentiment analysis detects anger (>80%) → Auto-escalate to human → Warm transfer (<10s) → Human handles call → Post-call: AI flags any incorrect info → Manager reviews → Agent Lightning learns  
**Postconditions:** Customer served by human, sentiment shift logged, AI learns from interaction

### UC-04: New Client Onboards via Jarvis
**Actor:** Potential Client, Onboarding Jarvis  
**Preconditions:** User visits PARWA website  
**Flow:** User lands on /onboarding → Jarvis welcomes → User explores features (DISCOVERY stage) → User tries demo (DEMO stage) → User views pricing (PRICING stage) → User selects variants → Bill summary card shown → Business email OTP verification → Paddle payment → Handoff to Customer Care Jarvis → 5-step onboarding wizard → First Victory celebration → Dashboard  
**Postconditions:** Client subscribed, AI agents active, knowledge base uploaded

### UC-05: Batch Approval of Similar Refund Requests
**Actor:** Manager  
**Preconditions:** Multiple pending refund requests exist  
**Flow:** System groups similar requests via semantic clustering → Batch card shown with confidence range and risk level → Manager reviews batch → Can approve all, approve selected, reject batch, or create auto-approve rule → If auto-approve rule created, DSPy updates core instructions → Future similar requests auto-handled  
**Postconditions:** Refunds processed, auto-approve rule created (if chosen), Agent Lightning captures signals

### UC-06: AI Performance Drift Detected
**Actor:** System (automated), Manager  
**Preconditions:** System in Graduated Mode  
**Flow:** Daily drift check → Confidence drops >5% for 3 days → Drift alert fired → Auto-downgrade to "high sensitivity" (asks for approval on more things) → Manager notified → Root cause analysis displayed in Jarvis → If accuracy also drops below 85%, auto-revert to Shadow Mode → Manager investigates → Retraining triggered if needed  
**Postconditions:** AI performance restored, root cause documented

### UC-07: Dynamic Agent Provisioning via Jarvis
**Actor:** Manager  
**Preconditions:** Manager has ADMIN/SUPERVISOR role  
**Flow:** Manager types "Jarvis, add 2 PARWA agents for the weekend" → Jarvis parses command → Authorization check → Budget feasibility check → Paddle subscription modification (prorated) → New agents provisioned → Brand Voice, FAQ, greeting style cloned → Confirmation in terminal  
**Postconditions:** 2 temporary PARWA agents active, prorated billing applied, auto-expiry set

### UC-08: Customer Self-Service Refund
**Actor:** Customer  
**Preconditions:** Auto-approve rule exists for standard returns < $50  
**Flow:** Customer receives email → Clicks refund link → Email match verification → Fraud score check → Policy compliance check → All checks pass → Secure one-time token sent → Customer confirms → Backend double-checks → Paddle refund executed → Confirmation email sent  
**Postconditions:** Refund processed without manager involvement, logged in audit trail

### UC-09: Outbound Proactive Call (Abandoned Cart)
**Actor:** Jarvis, Manager, Customer  
**Preconditions:** Proactive voice feature enabled  
**Flow:** Jarvis detects abandoned cart → Generates call script → Presents to Manager for approval → Manager approves → Twilio Voice API initiates call → Customer answers → AI delivers script → Post-call summary card in Jarvis → ROI mapping shown  
**Postconditions:** Customer re-engaged (or not), call logged, outcome tracked

### UC-10: Training Pipeline Execution
**Actor:** System (automated), Manager  
**Preconditions:** 50+ mistakes accumulated  
**Flow:** 50-mistake threshold triggered → Auto-queue training run → Dataset preparation (clean, deduplicate, PII strip, quality score) → Training execution on Google Colab/RunPod → Validation against test set → If pass: deploy new model version → If fail: rollback to previous version → Manager notified of results  
**Postconditions:** New model version deployed (or rollback), training metrics logged, future accuracy expected to improve

---

## 9. Acceptance Criteria

### 9.1 Functional Acceptance

**AC-9.1.1:** GSD State Engine reduces token usage by ≥90% compared to full chat history approach.

**AC-9.1.2:** Smart Router correctly routes ≥95% of queries to appropriate LLM tier based on complexity score.

**AC-9.1.3:** Agent Lightning improves accuracy by ≥50% after 3 training cycles.

**AC-9.1.4:** MAKER Framework reduces error rate to <1% for financial operations.

**AC-9.1.5:** Batch Approval reduces manager review time by ≥80%.

**AC-9.1.6:** Empathy Engine correctly routes ≥90% of angry customers to human agents.

**AC-9.1.7:** Voice calls answered within 6 seconds with appropriate brand voice greeting.

**AC-9.1.8:** Ticket classification achieves ≥70% confidence within 3 seconds.

**AC-9.1.9:** Jarvis onboarding converts ≥15% of demo users to paid subscribers.

**AC-9.1.10:** Quality Coach identifies ≥80% of recurring AI mistakes.

**AC-9.1.11:** Approval escalation ladder triggers correctly at each phase boundary.

**AC-9.1.12:** Drift detection alerts within 24 hours of threshold breach.

**AC-9.1.13:** DSPy prompt optimization improves response quality by ≥10% after A/B testing.

**AC-9.1.14:** Guardrails AI blocks 100% of competitor mentions and data leaks.

**AC-9.1.15:** All 14 Building Codes enforced in CI/CD pipeline.

### 9.2 Non-Functional Acceptance

**AC-9.2.1:** System achieves 99.5% uptime over 30-day measurement period.

**AC-9.2.2:** No cross-tenant data leakage detected in penetration testing.

**AC-9.2.3:** PII detection accuracy ≥90% on test dataset.

**AC-9.2.4:** Prompt injection detection rate ≥95%.

**AC-9.2.5:** Dashboard page load <2 seconds on standard connection.

**AC-9.2.6:** Socket.io events delivered within 500ms.

**AC-9.2.7:** All financial values stored as Numeric(19,4), no FLOAT usage detected.

**AC-9.2.8:** RLS tests pass on every commit (0 failures).

**AC-9.2.9:** Test coverage ≥80% for services, 100% for financial/auth.

**AC-9.2.10:** GDPR right-to-erasure completes within 72 hours of request.

**AC-9.2.11:** Disaster recovery RTO ≤1 hour, RPO ≤1 hour.

**AC-9.2.12:** Circuit breakers activate within 30 seconds of 5 consecutive failures.

### 9.3 Build Roadmap Acceptance (5 Phases, 21 Weeks)

**AC-9.3.1 — Phase 1 (Weeks 1-3):** Project skeleton, database (50+ tables), authentication (F-010 to F-019), background jobs + real-time + middleware. All 14 Building Codes enforced.

**AC-9.3.2 — Phase 2 (Weeks 4-7):** Ticket system (F-046 to F-052, F-070) + 62 gap items, billing (F-020 to F-027), onboarding (F-028 to F-035), approval system (F-074 to F-086).

**AC-9.3.3 — Phase 3 (Weeks 8-12):** Smart Router, model failover, PII redaction, Guardrails, confidence scoring, intent classification, sentiment, RAG, auto-response, draft composer, ticket assignment, GSD engine, LangGraph, context compression, DSPy, AI technique framework (F-140 to F-148), semantic clustering.

**AC-9.3.4 — Phase 4 (Weeks 13-17):** Communication channels (email, chat, SMS, voice), Jarvis Command Center, dashboard + analytics, integrations + mobile.

**AC-9.3.5 — Phase 5 (Weeks 18-21):** Public pages, training pipeline, polish (contextual help, feature discovery, test suite, load testing, security audit, GDPR verification, documentation).

### 9.4 Feature Coverage Acceptance

**AC-9.4.1:** All 148+ features from the Feature Catalog (Batches 1-10) SHALL be implemented or explicitly deferred with documented rationale.

**AC-9.4.2:** All 6 CRITICAL gaps from Week 9 Gap Analysis SHALL be resolved: Intent x Technique variant-aware fallback (W9-GAP-001), CLARA pipeline timeout (W9-GAP-002), RAG pgvector company_id filter (W9-GAP-003), ReAct tool timeout (W9-GAP-004), Re-indexing dedup/concurrency (W9-GAP-005), Token budget atomicity (W9-GAP-006).

**AC-9.4.3:** All 10 HIGH gaps from Week 9 Gap Analysis SHALL be resolved (W9-GAP-007 through W9-GAP-016).

**AC-9.4.4:** All 7 production gaps from Day 27 Gap Analysis SHALL be resolved: PII detection accuracy (GAP-1), prompt injection detection (GAP-2), missing injection patterns (GAP-3), risk scoring (GAP-4), multi-turn attack detection (GAP-5), tenant context (GAP-6), financial proration (GAP-7).

**AC-9.4.5:** All 28 gaps from Week 9 analysis (6 CRITICAL, 10 HIGH, 12 MEDIUM) SHALL be tracked with resolution status.

---

*End of PARWA Software Requirements Specification v2.0*
