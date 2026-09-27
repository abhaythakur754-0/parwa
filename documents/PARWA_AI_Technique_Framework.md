# PARWA AI Technique Framework v1.0

> **Document Classification:** Architecture & Engineering Specification
> **Version:** 1.0
> **Date:** 2025
> **Author:** PARWA Engineering — AI Architecture Team
> **Status:** Active Specification
> **Parent Framework:** TRIVYA Optimization Framework

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram (Conceptual)](#architecture-diagram-conceptual)
3. [Tier 1: Base Techniques (Always Active)](#tier-1-base-techniques-always-active)
4. [Tier 2: Conditional Techniques (Auto-Triggered)](#tier-2-conditional-techniques-auto-triggered)
5. [Tier 3: Premium Techniques (Selective)](#tier-3-premium-techniques-selective)
6. [Auto-Trigger Detection Logic](#auto-trigger-detection-logic)
7. [Technique vs Model Routing (Critical Distinction)](#technique-vs-model-routing-critical-distinction)
8. [Integration with Existing PARWA Features](#integration-with-existing-parwa-features)
9. [New Features Added](#new-features-added)
10. [Implementation Notes](#implementation-notes)
11. [Token Budget & Cost Management](#token-budget--cost-management)
12. [Performance Metrics & Monitoring](#performance-metrics--monitoring)
13. [Appendix: Technique Decision Flowchart](#appendix-technique-decision-flowchart)

---

## Overview

PARWA's AI engine employs a **3-tier technique architecture** for reasoning optimization. This framework defines how the system selects, composes, and executes reasoning techniques on a per-query basis to maximize response quality, accuracy, and efficiency.

### The Technique Router (BC-013)

The **Technique Router** is a dedicated subsystem within PARWA's AI pipeline that analyzes incoming queries and determines which reasoning technique(s) should be applied. It operates as a classification and orchestration layer that sits between query intake and response generation.

### Critical Distinction: Technique Router vs Smart Router

It is essential to understand that the **Technique Router** is fundamentally different from—and complementary to—the **Smart Router (F-054)**:

| Aspect | Smart Router (F-054) | Technique Router (BC-013) |
|--------|---------------------|--------------------------|
| **Selects** | Which AI MODEL to use | Which REASONING TECHNIQUE to apply |
| **Options** | Light / Medium / Heavy | CoT, ToT, UoT, ReAct, etc. |
| **Signal Basis** | Query size, intent priority, SLA tier | Complexity, confidence, sentiment, customer tier |
| **Analogy** | Choosing which ENGINE to use | Choosing which DRIVING STRATEGY to apply |
| **Independence** | Can run without Technique Router | Can run without Smart Router |
| **Combined** | Both work together on every query | Both work together on every query |

**Key Principle:** On any given query, the Smart Router might select the **Medium model** while the Technique Router selects **Reverse Thinking + Step-Back**. These decisions are made independently but execute together within the LangGraph workflow.

### How the Two Routers Work Together

1. **Query arrives** → Intent Classification (F-062) + Sentiment Analysis (F-063) extract signals
2. **Smart Router (F-054)** reads signals → selects model tier (Light/Medium/Heavy)
3. **Technique Router (BC-013)** reads signals → selects reasoning technique(s) per tier
4. **LangGraph Workflow (F-060)** orchestrates both: model × technique = final execution
5. **Response generated** → CLARA (Tier 1) quality gate validates output before delivery

---

## Architecture Diagram (Conceptual)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INCOMING QUERY                                   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
              ┌────────────────────────────────────────┐
              │  Signal Extraction Layer               │
              │  • Intent Classification (F-062)       │
              │  • Sentiment Analysis (F-063)          │
              │  • Confidence Scoring (F-059)          │
              │  • Customer Tier Lookup                │
              │  • Monetary Value Detection            │
              │  • Conversation History Analysis       │
              └──────────┬─────────────┬──────────────┘
                         │             │
                    ┌────▼────┐  ┌─────▼──────────┐
                    │  SMART  │  │  TECHNIQUE     │
                    │  ROUTER │  │  ROUTER        │
                    │ (F-054) │  │  (BC-013)      │
                    │         │  │                 │
                    │ Model:  │  │ T1: CLARA,CRP, │
                    │ Light/  │  │     GSD         │
                    │ Medium/ │  │ T2: CoT,ReAct, │
                    │ Heavy   │  │     ThoT,etc.   │
                    └────┬────┘  │ T3: ToT,UoT,   │
                         │       │     GST,etc.    │
                         │       └──────┬──────────┘
                         │              │
                         ▼              ▼
              ┌────────────────────────────────────────┐
              │  LangGraph Workflow (F-060)            │
              │  Executes: MODEL × TECHNIQUE(S)        │
              │  ├── Tier 1 Techniques (always)        │
              │  ├── Tier 2 Techniques (conditional)   │
              │  └── Tier 3 Techniques (selective)     │
              └──────────────────┬─────────────────────┘
                                 │
                                 ▼
              ┌────────────────────────────────────────┐
              │  CLARA Quality Gate                    │
              │  Validate → Sanitize → Deliver         │
              └────────────────────────────────────────┘
```

---

## Tier 1: Base Techniques (Always Active)

Tier 1 techniques run on **every single query** processed by PARWA's AI engine. They require no conditions, no thresholds, and no trigger signals. They form the foundational layer that ensures baseline quality, efficiency, and state management for all interactions.

---

### CLARA — Concise Logical Adaptive Response Architecture

**Status:** Always Active | **Feature Mapping:** Guardrails AI (F-057), Auto-Response Generation (F-065)

#### Purpose
CLARA is PARWA's always-active response quality framework. It ensures that every AI-generated output meets structured, logical, and brand-aligned quality standards before it reaches the customer. CLARA acts as the final quality gate in the response pipeline.

#### How It Works
1. **Structure Enforcement:** Every response follows a logical structure — context acknowledgment, solution/explanation, action items, closing
2. **Logic Validation:** Response reasoning is checked for internal consistency and logical coherence
3. **Brand Alignment:** Tone, language, and terminology are validated against tenant-specific brand guidelines
4. **Quality Gates:** Responses pass through multiple validation checkpoints before delivery

#### Quality Gate Pipeline
```
Raw LLM Output → Structure Check → Logic Check → Brand Check → Tone Check → Delivery
                     │                │            │            │
                  ❌ Retry       ❌ Retry      ⚠️ Adjust    ⚠️ Adjust
```

#### Configuration Per Tenant
- Brand voice profile (formal/casual/technical)
- Allowed terminology dictionary
- Forbidden phrases list
- Response structure templates per intent type

---

### CRP — Concise Response Protocol

**Status:** Always Active | **Feature Mapping:** NEW — F-140

#### Purpose
CRP minimizes token waste by eliminating unnecessary filler words, verbose explanations, and redundant information from AI responses. It is a cost optimization technique that directly reduces LLM API costs.

#### How It Works
1. **Filler Elimination:** Removes phrases like "I'd be happy to help you with that," "Certainly, I can assist," "Let me look into that for you"
2. **Compression:** Reduces multi-sentence explanations to their essential information content
3. **Redundancy Removal:** Detects and removes repeated information across response sections
4. **Token Budget Enforcement:** Each response has a target token count based on query complexity

#### Performance Targets
| Metric | Target | Measurement |
|--------|--------|-------------|
| Response Length Reduction | 30-40% fewer tokens | Avg tokens per response vs baseline |
| Information Retention | > 95% of key facts preserved | Customer satisfaction score |
| Response Time | No increase (or faster) | Avg response latency |
| Customer Satisfaction | No degradation | CSAT score comparison |

#### CRP vs Guardrails (F-057) — Critical Distinction
- **CRP** is about **efficiency** — reducing token waste while preserving information
- **Guardrails** is about **safety** — preventing harmful, off-brand, or policy-violating content
- Both are always active but serve completely different purposes
- CRP runs BEFORE Guardrails in the pipeline

---

### GSD State Engine — Guided Support Dialogue

**Status:** Always Active | **Feature Mapping:** F-053

#### Purpose
GSD orchestrates multi-step conversation state management. Every ticket flows through the GSD state machine, which tracks conversation progress, manages handoffs, and ensures resolution continuity.

#### How It Works
1. **State Tracking:** Maintains current conversation state (greeting → diagnosis → resolution → follow-up)
2. **Transition Management:** Handles state transitions based on conversation flow
3. **Context Preservation:** Carries forward relevant context across state transitions
4. **Escalation Triggering:** Detects when conversation needs human escalation

#### State Machine Diagram
```
[NEW] → [GREETING] → [DIAGNOSIS] → [RESOLUTION] → [FOLLOW-UP] → [CLOSED]
                │            │              │            │
                └──[ESCALATE]┘──┘              └────────────┘
                            ▼
                      [HUMAN HANDOFF]
```

#### Integration with Techniques
- GSD state is passed as context to ALL Tier 2 and Tier 3 techniques
- Technique selection may change based on current GSD state (e.g., ESCALATE state always triggers Step-Back)
- State transitions are logged for Agent Performance Analytics (F-098)

---

### Technique Selection Router

**Status:** Always Active | **Feature Mapping:** BC-013

#### Purpose
The Technique Selection Router is the core intelligence that analyzes query characteristics and determines which Tier 2 and/or Tier 3 techniques should activate for the current query.

#### Input Signals
The router ingests the following signals to make technique selection decisions:

| Signal | Source | Data Type | Range |
|--------|--------|-----------|-------|
| Query Complexity Score | F-062 (Intent Classification) | Float | 0.0 – 1.0 |
| Confidence Score | F-059 | Float | 0.0 – 1.0 |
| Sentiment Score | F-063 | Float | 0.0 – 1.0 |
| Customer Tier | Account Database | Enum | Free / Pro / Enterprise / VIP |
| Monetary Value | Query Analysis + CRM | Float | $0.00+ |
| Conversation Turn Count | Conversation History | Integer | 0+ |
| Intent Type | F-062 | Enum | billing, technical, general, etc. |
| Previous Response Status | Conversation History | Enum | accepted / rejected / corrected |
| Reasoning Loop Detection | LangGraph Monitor | Boolean | true / false |
| Resolution Path Count | Query Analysis | Integer | 1+ |

#### Decision Process
1. Extract all signals for the current query
2. Evaluate each trigger rule (see [Auto-Trigger Detection Logic](#auto-trigger-detection-logic))
3. Compile list of activated techniques
4. Apply technique stacking order (Tier 1 → Tier 2 → Tier 3)
5. Check token budget (see [Token Budget & Cost Management](#token-budget--cost-management))
6. Execute technique pipeline via LangGraph

---

## Tier 2: Conditional Techniques (Auto-Triggered)

Tier 2 techniques activate **automatically** when specific query conditions are met. They do not require manual intervention, admin configuration, or explicit user requests. The Technique Router evaluates trigger conditions on every query and activates the appropriate techniques.

---

### Reverse Thinking

**Feature Mapping:** NEW — F-141
**Tier:** 2 (Conditional)

#### Trigger Conditions
- Confidence score < 0.7, OR
- Query contains negation/disagreement patterns (e.g., "that's wrong," "I disagree," "not what I asked")

#### Process
1. **Problem Statement:** AI formulates the core question or issue from the query
2. **Inversion Generation:** AI generates what a WRONG answer would look like — identifying common mistakes, misconceptions, and incorrect assumptions
3. **Error Analysis:** AI analyzes WHY the wrong answer is wrong, identifying failure modes
4. **Inversion:** AI inverts the wrong answer's logic to derive the correct answer
5. **Validation:** Correct answer is validated against known facts and policies

#### Example Flow
```
Query: "Can I get a refund for my annual subscription purchased 45 days ago?"

Step 1 — Problem: Refund eligibility for 45-day-old annual subscription
Step 2 — Wrong Answer: "Yes, you can get a full refund" (ignores 30-day policy)
Step 3 — Error Analysis: Annual subscriptions have a 30-day refund window; 45 days exceeds this
Step 4 — Inversion: Since the wrong answer assumed unlimited refund window,
                the correct answer must enforce the 30-day policy limitation
Step 5 — Validation: Policy confirms 30-day window → Correct answer: No full refund,
                but partial credit may be available
```

#### Use Cases
- Ambiguous refund eligibility determinations
- Edge-case billing questions with overlapping policies
- Dispute resolution where multiple interpretations exist
- Policy interpretation with conflicting clauses

#### Token Cost
- Base: ~200 tokens for inversion generation
- Validation: ~100 tokens
- **Total estimated overhead:** ~300 tokens per activation

---

### Chain of Thought (CoT)

**Feature Mapping:** Partially covered by F-054 (Smart Router Medium tier), formalized here
**Tier:** 2 (Conditional)

#### Trigger Conditions
- Query complexity score > 0.4, OR
- Multi-step reasoning required (detected by intent classification), OR
- Query contains 3+ distinct sub-questions

#### Process
1. **Decomposition:** Break the query into sequential logical steps
2. **Step-by-Step Reasoning:** Process each step explicitly, showing the reasoning chain
3. **Intermediate Validation:** Check each step's output before proceeding
4. **Synthesis:** Combine step outputs into a coherent final response

#### Example Flow
```
Query: "I was charged $49.99 on March 1 and $59.99 on March 15. My plan is $29.99/month.
        Why was I charged extra?"

Step 1 — Identify charges: $49.99 (Mar 1) + $59.99 (Mar 15) = $109.98 total
Step 2 — Identify expected charge: $29.99/month × 1 month = $29.99
Step 3 — Calculate discrepancy: $109.98 - $29.99 = $79.99 overcharged
Step 4 — Investigate Mar 1 charge ($49.99): Likely annual plan renewal or add-on
Step 5 — Investigate Mar 15 charge ($59.99): Likely mid-cycle plan upgrade
Step 6 — Synthesis: Two separate actions caused the charges — plan renewal + upgrade
```

#### Use Cases
- Technical troubleshooting with sequential diagnostic steps
- Multi-product billing calculations
- Policy interpretation requiring logical deduction
- Configuration explanations with dependencies

#### Token Cost
- Per reasoning step: ~50-100 tokens
- Average activation: 3-5 steps
- **Total estimated overhead:** ~150-500 tokens per activation

---

### ReAct (Reasoning + Acting)

**Feature Mapping:** Partially covered by RAG (F-064), formalized here
**Tier:** 2 (Conditional)

#### Trigger Conditions
- Query requires external tool/API call, OR
- Real-time data lookup needed (detected by intent classification), OR
- Query references specific order IDs, account numbers, or transaction records

#### Process
1. **Thought:** AI reasons about what information is needed
2. **Action:** AI calls external tool/API (RAG, database, integration)
3. **Observation:** AI receives and processes the tool response
4. **Thought:** AI reasons about the observation in context
5. **Action/Observation Loop:** Repeat steps 2-4 as needed
6. **Final Answer:** AI synthesizes observations into a coherent response

#### Example Flow
```
Query: "What's the status of order #ORD-2025-78432?"

Thought 1: I need to look up the order status for #ORD-2025-78432
Action 1:  [Call Order Status API with order ID]
Observation 1: {"status": "shipped", "carrier": "FedEx", "tracking": "7489237104",
               "estimated_delivery": "2025-01-18"}
Thought 2: I have the order status. Let me provide a comprehensive response.
Final Answer: "Your order #ORD-2025-78432 has been shipped via FedEx.
             Tracking: 7489237104. Estimated delivery: January 18, 2025."
```

#### Supported Tool Integrations
| Tool | Data Retrieved | Latency |
|------|---------------|---------|
| RAG Knowledge Base (F-064) | Documentation, policies, FAQs | ~200ms |
| Order Management API | Order status, tracking, history | ~300ms |
| Billing System API | Account balance, invoices, charges | ~250ms |
| CRM Integration | Customer profile, tier, history | ~200ms |
| Ticket System | Previous tickets, resolution history | ~150ms |

#### Token Cost
- Per thought-action-observation cycle: ~150 tokens
- Average activation: 1-3 cycles
- **Total estimated overhead:** ~150-450 tokens per activation

---

### Step-Back Prompting

**Feature Mapping:** NEW — F-142
**Tier:** 2 (Conditional)

#### Trigger Conditions
- Query is too specific/narrow (detected by low breadth score), OR
- AI reasoning loop detected (circular reasoning in previous turn), OR
- GSD state indicates diagnosis is stalled

#### Process
1. **Detection:** System identifies that the current query context is too narrow or reasoning is stuck
2. **Step-Back:** AI generates broader contextual questions to expand understanding
3. **Broader Analysis:** AI answers the broader question first, then narrows back to the original query
4. **Refined Response:** Original query is answered with the benefit of broader context

#### Example Flow
```
Query: "Why doesn't the API return data for endpoint /v2/users?"

Step-Back Question: "What is the overall API behavior pattern for v2 endpoints,
                    and what authentication/authorization requirements exist?"

Broader Analysis: v2 endpoints require OAuth 2.0 bearer tokens. Unauthenticated
                 requests receive empty responses (not errors).

Refined Response: "The /v2/users endpoint requires an OAuth 2.0 bearer token in
                 the Authorization header. Without it, the API returns an empty
                 response rather than an error. Please check that your request
                 includes a valid Bearer token."
```

#### Use Cases
- Vague or unclear technical issues
- First-time customer queries with limited context
- Unclear ticket descriptions that need clarification
- Troubleshooting where initial approach is failing

#### Token Cost
- Step-back question generation: ~100 tokens
- Broader analysis: ~200 tokens
- **Total estimated overhead:** ~300 tokens per activation

---

### Thread of Thought (ThoT)

**Feature Mapping:** Related to Context Health (F-068), formalized here
**Tier:** 2 (Conditional)

#### Trigger Conditions
- Multi-turn conversation detected, OR
- Conversation has > 5 messages, OR
- Customer references previous conversation points

#### Process
1. **Thread Extraction:** AI extracts the reasoning thread from all previous conversation turns
2. **Continuity Check:** AI verifies that current reasoning is consistent with previous turns
3. **Build-on-Previous:** Current response builds upon established reasoning rather than starting fresh
4. **Thread Update:** Updated reasoning thread is stored for future turns

#### Thread Structure
```
Turn 1: [Reasoning Thread A] — Initial diagnosis of billing issue
Turn 2: [Reasoning Thread A → B] — Narrowed down to specific charge
Turn 3: [Reasoning Thread A → B → C] — Identified charge as plan upgrade
Turn 4: [Reasoning Thread A → B → C → D] — Confirmed upgrade was unauthorized
Turn 5: [Reasoning Thread A → B → C → D → E] — Processing refund
Turn 6: [Reasoning Thread A → B → C → D → E → F] — Confirming refund status
```

#### Use Cases
- Long support threads requiring continuity
- Escalating issues where context from earlier turns is critical
- Follow-up conversations where previous reasoning must be preserved
- Cross-department coordination threads

#### Token Cost
- Thread extraction per turn: ~50 tokens
- Continuity check: ~100 tokens
- **Total estimated overhead:** ~150 tokens per activation

---

## Tier 3: Premium Techniques (Selective)

Tier 3 techniques activate only for **high-value, high-risk, or highly complex** scenarios. They consume significantly more tokens and compute resources but deliver superior reasoning quality for critical interactions.

**Activation Principle:** Tier 3 techniques are reserved for situations where the cost of an incorrect or suboptimal response outweighs the additional token/compute cost.

---

### GST — Guided Sequential Thinking

**Feature Mapping:** NEW — F-143
**Tier:** 3 (Premium)

#### Trigger Conditions
- Query involves strategic decisions, OR
- Multi-party impact detected (affects > 1 customer/account), OR
- Policy change or exception request

#### Process
1. **Goal Definition:** AI clearly defines the strategic goal and success criteria
2. **Sequential Analysis:** AI follows a guided framework with explicit checkpoints:
   - **Checkpoint 1 — Stakeholder Impact:** Who is affected and how?
   - **Checkpoint 2 — Policy Alignment:** Does this align with or require policy exception?
   - **Checkpoint 3 — Risk Assessment:** What are the risks of each approach?
   - **Checkpoint 4 — Financial Impact:** What is the cost/benefit analysis?
   - **Checkpoint 5 — Recommendation:** What is the recommended path?
3. **Checkpoint Validation:** Each checkpoint must pass before proceeding
4. **Final Synthesis:** All checkpoint outputs are synthesized into a strategic recommendation

#### Example Flow
```
Query: "We need to downgrade from Enterprise to Pro plan but keep 3 of our 5
        integrations active. Can we do this?"

Checkpoint 1 — Stakeholder Impact: 12 team members lose Enterprise features,
              3 integrations must remain active
Checkpoint 2 — Policy Alignment: Pro plan supports max 2 integrations;
              exception needed for 3rd integration
Checkpoint 3 — Risk Assessment: Downgrading mid-contract has early termination
              implications; 3rd integration requires exception approval
Checkpoint 4 — Financial Impact: Savings of $200/month but potential $150
              integration override fee
Checkpoint 5 — Recommendation: Submit plan downgrade with integration exception
              request; net savings of $50/month after fees
```

#### Use Cases
- Contract modifications and amendments
- Service level agreement changes
- Enterprise account plan adjustments
- Multi-department policy exception requests

#### Token Cost
- Per checkpoint: ~200 tokens
- 5 checkpoints + synthesis
- **Total estimated overhead:** ~1,000-1,200 tokens per activation

---

### Universe of Thoughts (UoT)

**Feature Mapping:** NEW — F-144
**Tier:** 3 (Premium)

#### Trigger Conditions
- Customer is VIP tier, OR
- Sentiment score < 0.3 (angry/frustrated customer), OR
- Query involves > $100 monetary value, OR
- Query flagged by Urgent Attention Panel (F-080)

#### Process
1. **Solution Space Generation:** AI generates 3-5 diverse solution approaches to the problem
2. **Evaluation Matrix:** Each solution is evaluated against multiple criteria:
   - Customer satisfaction impact
   - Financial cost to company
   - Policy compliance
   - Resolution speed
   - Long-term relationship impact
3. **Scoring:** Solutions are scored and ranked
4. **Optimal Selection:** Highest-scoring solution is selected
5. **Presentation:** Solution is presented with rationale for why it was chosen over alternatives

#### Evaluation Matrix Example
```
                    | CSAT | Cost | Policy | Speed | Long-Term | TOTAL |
--------------------|------|------|--------|-------|-----------|-------|
Solution A: Full Refund  | 9   | -100 | Yes    | Fast  | Neutral    | 7.5  |
Solution B: Partial Credit| 6   | -40  | Yes    | Fast  | Positive   | 7.0  |
Solution C: Free Month    | 8   | -30  | Yes    | Fast  | Positive   | 8.5  ← SELECTED
Solution D: Upgrade       | 5   | +20  | Yes    | Slow  | Positive   | 6.0  |
```

#### Use Cases
- VIP complaint handling requiring white-glove treatment
- High-value refund decisions with financial implications
- Customer retention scenarios where relationship is at risk
- Escalated issues requiring creative problem-solving

#### Token Cost
- Per solution generated: ~300 tokens
- Evaluation matrix: ~200 tokens
- 3-5 solutions typical
- **Total estimated overhead:** ~1,100-1,700 tokens per activation

---

### Tree of Thoughts (ToT)

**Feature Mapping:** NEW — F-145
**Tier:** 3 (Premium)

#### Trigger Conditions
- Query has 3+ possible resolution paths, OR
- Requires branching decision analysis, OR
- Multi-system integration issue with interdependent components

#### Process
1. **Tree Generation:** AI generates a tree of possible reasoning paths
2. **Branch Evaluation:** Each branch is evaluated independently for viability
3. **Pruning:** Suboptimal or dead-end branches are pruned
4. **Depth-First or Breadth-First Search:** AI searches through the tree using the most appropriate strategy
5. **Path Selection:** Best path through the tree is selected
6. **Execution:** Selected path is executed with full reasoning trace

#### Tree Structure Example
```
[Customer reports API returning 500 errors]
├── Branch 1: Server-side issue
│   ├── Check server status → [Servers healthy] → PRUNE
│   └── Check deployment logs → [Recent deploy] → Investigate
│       └── Found breaking change → Rollback recommended
├── Branch 2: Client-side issue
│   ├── Check request format → [Valid format] → PRUNE
│   └── Check authentication → [Expired token] → Renew token
└── Branch 3: Network issue
    └── Check CDN/firewall → [Rate limit hit] → Increase limit
```

#### Use Cases
- Complex technical troubleshooting with multiple possible causes
- Multi-system integration issues with cascading dependencies
- Escalation decisions requiring evaluation of multiple options
- Root cause analysis for recurring issues

#### Token Cost
- Per branch: ~200 tokens
- 3-5 branches typical, with sub-branches
- **Total estimated overhead:** ~800-1,500 tokens per activation

---

### Self-Consistency

**Feature Mapping:** NEW — F-146
**Tier:** 3 (Premium)

#### Trigger Conditions
- Monetary amount > $100 in the query, OR
- Refund/credit action explicitly requested, OR
- Query involves financial compliance or regulatory implications, OR
- Billing/financial query detected by intent classification

#### Process
1. **Multi-Answer Generation:** AI generates 3-5 independent answers to the same query, each using a slightly different reasoning approach
2. **Consistency Check:** AI compares all answers for agreement on key facts and conclusions
3. **Majority Vote:** If all/most answers agree → high confidence in result
4. **Disagreement Analysis:** If answers disagree → identify the source of disagreement, investigate further
5. **Final Response:** Most consistent answer is delivered, with confidence indicator

#### Consistency Check Example
```
Query: "What is the prorated refund for cancelling my $120/year plan after 4 months?"

Answer 1: $80 refund (8 months remaining ÷ 12 × $120)
Answer 2: $80 refund (remaining value calculation)
Answer 3: $80 refund (standard proration formula)
Answer 4: $76 refund (with 5% early cancellation fee)
Answer 5: $80 refund (prorated calculation)

Consistency: 4/5 agree on $80, 1/5 suggests $76 (with fee)
→ Analysis: Early cancellation fee applies per policy
→ Final Answer: $76 refund (with 5% early cancellation fee applied)
```

#### Use Cases
- Refund amount verification to prevent over/under-refunding
- Billing dispute resolution requiring precise calculations
- Financial quote generation for customers
- Compliance-sensitive financial responses

#### Token Cost
- Per independent answer: ~200 tokens
- Consistency analysis: ~150 tokens
- 3-5 answers typical
- **Total estimated overhead:** ~750-1,150 tokens per activation

---

### Reflexion

**Feature Mapping:** NEW — F-147
**Tier:** 3 (Premium)

#### Trigger Conditions
- Previous response was rejected or corrected by the customer, OR
- AI confidence score drops mid-conversation (compared to previous turn), OR
- Customer explicitly states dissatisfaction with previous answer

#### Process
1. **Failure Detection:** AI identifies that the previous response was unsatisfactory
2. **Self-Reflection:** AI analyzes what went wrong:
   - Did I misunderstand the query?
   - Did I provide incorrect information?
   - Was my tone inappropriate?
   - Did I miss important context?
3. **Strategy Adjustment:** AI modifies its approach based on reflection
4. **Improved Generation:** AI generates a new response with adjusted strategy
5. **Meta-Reasoning Trace:** The reflection process is logged for continuous improvement

#### Reflexion Trace Example
```
[Previous Response Rejected]
Customer: "That's not what I'm asking. I want to know why I was double-charged,
           not how to view my invoice."

Reflection:
- Failure Mode: Misunderstood query intent
- What I did: Provided invoice viewing instructions
- What I should have done: Investigated the double charge
- Strategy Change: Switch from informational to investigative approach
- Context Update: Customer has a billing dispute, not a navigation question

[Improved Response Generated with investigative approach]
```

#### Use Cases
- Failed resolution attempts requiring course correction
- Customer corrections of AI-provided information
- Learning from rejection patterns across conversations
- Building improvement feedback loops

#### Token Cost
- Reflection analysis: ~200 tokens
- Strategy adjustment: ~100 tokens
- Improved generation: ~100 tokens additional
- **Total estimated overhead:** ~400 tokens per activation

---

### Least-to-Most Decomposition

**Feature Mapping:** NEW — F-148
**Tier:** 3 (Premium)

#### Trigger Conditions
- Query complexity score > 0.7, OR
- Task has 5+ identifiable sub-steps, OR
- Multi-department coordination required, OR
- Enterprise-scale request with multiple components

#### Process
1. **Decomposition:** AI breaks the complex query into the simplest possible sub-queries
2. **Dependency Ordering:** Sub-queries are ordered by dependency (some must be solved before others)
3. **Sequential Solving:** Each sub-query is solved independently, feeding results into dependent sub-queries
4. **Result Combination:** All sub-query results are combined into a comprehensive answer
5. **Completeness Check:** AI verifies that all original query components have been addressed

#### Decomposition Example
```
Query: "We're onboarding 50 new employees across 3 departments. Each needs access
        to our platform, email integration, and Slack integration. Some are managers
        who need admin access. How do we set this up?"

Sub-query 1: How many employees per department?
Sub-query 2: Which employees are managers?
Sub-query 3: What are the platform access requirements for regular users vs managers?
Sub-query 4: How to set up email integration for bulk users?
Sub-query 5: How to set up Slack integration for bulk users?
Sub-query 6: What is the recommended onboarding sequence?
Sub-query 7: Are there bulk import tools available?

Dependency Chain: 1 → 2 → 3 → 6 → [parallel: 4, 5, 7] → Final Plan
```

#### Use Cases
- Enterprise onboarding requests with multiple components
- Multi-product troubleshooting requiring system-by-system analysis
- Complex billing reconciliation across multiple accounts
- Bulk operation requests affecting multiple users/resources

#### Token Cost
- Per sub-query generation: ~50 tokens
- Per sub-query solving: ~100 tokens
- Result combination: ~150 tokens
- Average: 5-8 sub-queries
- **Total estimated overhead:** ~800-1,300 tokens per activation

---

## Auto-Trigger Detection Logic

The Technique Router evaluates the following trigger rules on every incoming query. Multiple techniques can activate simultaneously based on the combination of signals present.

### Master Trigger Rules Table

| # | Signal | Threshold | Technique(s) Activated | Tier | Example Trigger |
|---|--------|-----------|----------------------|------|-----------------|
| 1 | Query Complexity Score | > 0.4 | Chain of Thought (CoT) | 2 | Multi-step billing question |
| 2 | Confidence Score | < 0.7 | Reverse Thinking + Step-Back | 2 | AI unsure about policy interpretation |
| 3 | Customer Tier | VIP | Universe of Thoughts (UoT) + Reflexion | 3 | VIP customer submits any query |
| 4 | Sentiment Score | < 0.3 | Universe of Thoughts (UoT) + Step-Back | 3, 2 | Angry/frustrated customer message |
| 5 | Monetary Value | > $100 | Self-Consistency | 3 | Refund request for $150 |
| 6 | Conversation Turn Count | > 5 messages | Thread of Thought (ThoT) | 2 | 6th message in support thread |
| 7 | External Data Required | Boolean: true | ReAct | 2 | Query references order ID or account number |
| 8 | Resolution Path Count | ≥ 3 possible paths | Tree of Thoughts (ToT) | 3 | Technical issue with multiple causes |
| 9 | Strategic Decision | Boolean: true | GST (Guided Sequential Thinking) | 3 | Contract modification request |
| 10 | Query Complexity Score | > 0.7 | Least-to-Most Decomposition | 3 | Complex multi-component enterprise query |
| 11 | Previous Response Status | Rejected/Corrected | Reflexion | 3 | Customer says "that's wrong" |
| 12 | Reasoning Loop Detection | Boolean: true | Step-Back | 2 | AI caught in circular reasoning |
| 13 | Intent Type | Billing/Financial | Self-Consistency | 3 | Any billing or payment query |
| 14 | Intent Type | Technical Troubleshooting | CoT + ReAct | 2 | Bug report or technical issue |

### Technique Stacking Rules

#### Multiple Technique Activation
Multiple techniques can and will activate simultaneously when multiple trigger conditions are met. Example scenarios:

**Scenario A — VIP + Angry Customer:**
```
Signals: Customer Tier = VIP, Sentiment Score = 0.2
Activated: UoT (Tier 3, rule #3) + UoT again (Tier 3, rule #4, deduplicated)
           + Step-Back (Tier 2, rule #4) + Reflexion (Tier 3, rule #3)
Execution Order: CLARA (T1) → CRP (T1) → GSD (T1) → Step-Back (T2) → UoT (T3) → Reflexion (T3)
```

**Scenario B — Technical Issue with Order Reference:**
```
Signals: Intent = Technical Troubleshooting, Order ID present in query
Activated: CoT (Tier 2, rule #14) + ReAct (Tier 2, rule #7 + rule #14)
Execution Order: CLARA (T1) → CRP (T1) → GSD (T1) → CoT (T2) → ReAct (T2)
```

**Scenario C — $200 Refund Request from Pro Customer:**
```
Signals: Monetary Value = $200, Intent = Billing, Customer Tier = Pro
Activated: Self-Consistency (Tier 3, rule #5) + Self-Consistency (Tier 3, rule #13, deduplicated)
           + CoT (Tier 2, rule #1, if complexity > 0.4)
Execution Order: CLARA (T1) → CRP (T1) → GSD (T1) → CoT (T2) → Self-Consistency (T3)
```

#### Execution Order
1. **Tier 1 techniques** ALWAYS execute first — CLARA, CRP, GSD (in that order)
2. **Tier 2 techniques** execute next — in the order they appear in the trigger table
3. **Tier 3 techniques** execute last — in the order they appear in the trigger table
4. Within each tier, techniques execute sequentially (not in parallel) to maintain reasoning coherence

#### Deduplication
If the same technique is triggered by multiple rules, it executes only once. For example, if Self-Consistency is triggered by both rule #5 (amount > $100) and rule #13 (billing query), it runs once.

---

## Technique vs Model Routing (Critical Distinction)

This section exists because the distinction between Technique Routing and Model Routing is frequently confused. They are **fundamentally different systems** that serve complementary purposes.

### Smart Router (F-054) — Model Selection

| Aspect | Detail |
|--------|--------|
| **What it selects** | Which AI MODEL to use |
| **Options** | Light (GPT-4o-mini) / Medium (GPT-4o) / Heavy (GPT-4o + fine-tuned) |
| **When it decides** | Before technique execution |
| **Signals used** | Query size, intent priority, SLA tier, response urgency |
| **Can change mid-query** | Yes, via Model Failover (F-055) |

### Technique Router (BC-013) — Technique Selection

| Aspect | Detail |
|--------|--------|
| **What it selects** | Which REASONING TECHNIQUE to apply |
| **Options** | CoT, ToT, UoT, ReAct, GST, Reverse Thinking, Step-Back, etc. |
| **When it decides** | Before technique execution |
| **Signals used** | Complexity, confidence, sentiment, customer tier, monetary value |
| **Can change mid-query** | Yes, if new signals emerge (e.g., Reflexion triggers) |

### Why Both Must Exist

```
Scenario: A VIP customer reports a $500 billing discrepancy with an angry tone.

Smart Router Decision:    → Heavy model (high value + VIP + complex)
Technique Router Decision: → UoT + Self-Consistency + Reflexion (VIP + amount + sentiment)

Without Smart Router:   Techniques run on default model (insufficient capability)
Without Technique Router: Heavy model runs with basic reasoning (underutilizes model capability)
With Both:              Heavy model + advanced techniques = optimal response quality
```

### Interaction Matrix

| Query Type | Smart Router Model | Technique Router Selection |
|-----------|-------------------|--------------------------|
| Simple FAQ | Light | CLARA + CRP only |
| Order status check | Medium | ReAct |
| Complex billing dispute ($50) | Medium | CoT + Self-Consistency |
| VIP complaint ($500) | Heavy | UoT + Reflexion + Self-Consistency |
| Enterprise onboarding | Heavy | Least-to-Most + GST |
| Technical issue (known solution) | Light | ReAct |
| Technical issue (unknown cause) | Medium | CoT + ToT + ReAct |

---

## Integration with Existing PARWA Features

The AI Technique Framework integrates with numerous existing PARWA features. Each integration point is critical for the system to function correctly.

### Feature Integration Mapping Table

| PARWA Feature | Feature ID | Technique Integration | Integration Type |
|---------------|-----------|----------------------|-----------------|
| GSD State Engine | F-053 | Tier 1 — always active; provides conversation state context for all techniques | Dependency |
| Smart Router | F-054 | Works alongside Technique Router — model selection + technique selection = full routing | Parallel |
| Model Failover | F-055 | Also handles technique fallback if a technique-specific model call fails | Fallback |
| Confidence Scoring | F-059 | Primary trigger signal for Reverse Thinking (Tier 2), Step-Back (Tier 2) | Signal Source |
| LangGraph Workflow | F-060 | Orchestrates technique execution within workflow nodes; each technique is a node | Orchestration |
| Intent Classification | F-062 | Determines which techniques are relevant per intent type; feeds complexity score | Signal Source |
| Sentiment Analysis | F-063 | Primary trigger signal for UoT (Tier 3), Step-Back (Tier 2) | Signal Source |
| RAG Knowledge Base | F-064 | Provides factual data for ReAct technique execution | Data Source |
| Auto-Response Generation | F-065 | Output channel for technique-processed responses | Output |
| Context Compression | F-067 | Manages token budget across all active techniques; prevents token overflow | Resource Mgmt |
| Context Health | F-068 | Monitors thread health for ThoT activation; detects context degradation | Signal Source |
| Urgent Attention Panel | F-080 | VIP/Legal flags directly trigger Tier 3 techniques (UoT, Reflexion) | Trigger |
| Self-Healing System | F-093 | If technique execution fails (timeout, error), auto-recovers with fallback technique | Recovery |
| Agent Performance Analytics | F-098 | Technique performance metrics (accuracy, latency, token cost) feed into analytics | Analytics |
| DSPy Optimization | F-061 | Techniques are versioned and can be A/B tested via DSPy framework | Optimization |
| Guardrails AI | F-057 | Post-technique validation; ensures technique output passes safety/brand gates | Validation |

### Integration Flow Detail

```
[Query] → F-062 (Intent) ─────┐
        → F-063 (Sentiment) ───┤
        → F-059 (Confidence) ──┤──→ Technique Router (BC-013)
        → F-080 (Urgent) ──────┤         │
        → F-053 (GSD State) ───┤         ▼
        → F-068 (Context) ─────┘    [Technique Selection]
                                             │
        ┌────────────────────────────────────┤
        │                                    ▼
        │                         F-060 (LangGraph)
        │                         ├── Technique Node 1
        │                         ├── Technique Node 2
        │                         └── Technique Node N
        │                                    │
        │                                    ▼
        │                         F-067 (Context Compression)
        │                         [Token Budget Management]
        │                                    │
        │                                    ▼
        │                         F-057 (Guardrails)
        │                         [Safety & Brand Validation]
        │                                    │
        │                                    ▼
        │                         F-065 (Auto-Response)
        │                         [Response Delivery]
        │
        └──→ F-093 (Self-Healing) [Monitors for failures, triggers recovery]
              F-098 (Analytics)    [Logs technique metrics]
              F-061 (DSPy)         [A/B tests technique variants]
```

---

## New Features Added

The following new features are introduced by this framework to support the AI Technique Routing system:

### New Feature Summary Table

| Feature ID | Name | Tier | Description | Priority | Est. Effort |
|-----------|------|------|-------------|----------|-------------|
| **F-140** | CRP (Concise Response Protocol) | Tier 1 | Token-efficient response generation; reduces response length by 30-40% while maintaining accuracy | High | 2 weeks |
| **F-141** | Reverse Thinking Engine | Tier 2 | Inversion-based reasoning for low-confidence queries; generates wrong answers then inverts | Medium | 3 weeks |
| **F-142** | Step-Back Prompting | Tier 2 | Broader context seeking for narrow queries or stuck reasoning loops | Medium | 2 weeks |
| **F-143** | GST (Guided Sequential Thinking) | Tier 3 | Strategic decision reasoning with explicit checkpoints and validation gates | Medium | 4 weeks |
| **F-144** | Universe of Thoughts (UoT) | Tier 3 | Multi-solution generation with evaluation matrix for VIP/critical scenarios | High | 4 weeks |
| **F-145** | Tree of Thoughts (ToT) | Tier 3 | Branching decision tree exploration with pruning for complex troubleshooting | Medium | 4 weeks |
| **F-146** | Self-Consistency | Tier 3 | Multi-answer verification for financial actions; majority voting mechanism | High | 3 weeks |
| **F-147** | Reflexion | Tier 3 | Self-correction engine for rejected/failed responses; meta-reasoning capability | Medium | 3 weeks |
| **F-148** | Least-to-Most Decomposition | Tier 3 | Complex query breakdown into ordered sub-queries with dependency resolution | Medium | 4 weeks |

### Feature Dependency Graph

```
F-140 (CRP)           ← No dependencies (Tier 1, standalone)
F-141 (Reverse Think) ← Depends on F-059 (Confidence Scoring)
F-142 (Step-Back)     ← Depends on F-053 (GSD State), F-068 (Context Health)
F-143 (GST)           ← Depends on F-060 (LangGraph Workflow)
F-144 (UoT)           ← Depends on F-080 (Urgent Attention), F-063 (Sentiment)
F-145 (ToT)           ← Depends on F-060 (LangGraph Workflow)
F-146 (Self-Consist)  ← Depends on F-062 (Intent Classification)
F-147 (Reflexion)     ← Depends on F-068 (Context Health), conversation history
F-148 (Least-to-Most) ← Depends on F-062 (Intent Classification), F-060 (LangGraph)
```

### Recommended Implementation Order

**Phase 1 — Foundation (Weeks 1-4):**
1. F-140 (CRP) — Immediate cost savings, no dependencies
2. F-142 (Step-Back) — Improves reasoning quality for stuck queries
3. F-141 (Reverse Thinking) — Improves accuracy for low-confidence queries

**Phase 2 — Core Advanced (Weeks 5-8):**
4. F-146 (Self-Consistency) — Critical for financial accuracy
5. F-147 (Reflexion) — Critical for self-improvement
6. F-144 (UoT) — Critical for VIP handling

**Phase 3 — Complex Reasoning (Weeks 9-12):**
7. F-145 (ToT) — Advanced troubleshooting support
8. F-143 (GST) — Strategic decision support
9. F-148 (Least-to-Most) — Enterprise-grade complex query handling

---

## Implementation Notes

### LangGraph Implementation

All techniques must be implemented as **LangGraph nodes/workflows** within the existing PARWA LangGraph pipeline (F-060). Each technique follows this pattern:

```python
# Conceptual implementation pattern (not production code)
class TechniqueNode:
    def __init__(self, technique_id, token_budget, time_budget):
        self.technique_id = technique_id
        self.token_budget = token_budget
        self.time_budget = time_budget

    async def execute(self, state: ConversationState) -> ConversationState:
        # 1. Check if technique should activate
        if not self.should_activate(state):
            return state

        # 2. Check token budget
        if state.token_usage > self.token_budget:
            return self.fallback(state)

        # 3. Execute technique logic
        result = await self.run_technique(state)

        # 4. Update state with technique output
        state.technique_results[self.technique_id] = result
        state.token_usage += result.tokens_used

        return state
```

### Token Cost Budgeting

Each technique has a defined token cost that is tracked and managed:

| Technique | Estimated Token Cost | Time Budget |
|-----------|---------------------|-------------|
| CLARA (T1) | ~50 tokens | 100ms |
| CRP (T1) | ~30 tokens (savings) | 50ms |
| GSD (T1) | ~20 tokens | 30ms |
| Reverse Thinking (T2) | ~300 tokens | 2s |
| CoT (T2) | ~150-500 tokens | 1-3s |
| ReAct (T2) | ~150-450 tokens | 1-5s (API dependent) |
| Step-Back (T2) | ~300 tokens | 1s |
| ThoT (T2) | ~150 tokens | 500ms |
| GST (T3) | ~1,000-1,200 tokens | 5-8s |
| UoT (T3) | ~1,100-1,700 tokens | 5-10s |
| ToT (T3) | ~800-1,500 tokens | 5-8s |
| Self-Consistency (T3) | ~750-1,150 tokens | 4-7s |
| Reflexion (T3) | ~400 tokens | 2-3s |
| Least-to-Most (T3) | ~800-1,300 tokens | 5-8s |

### Token Budget Management Rules

1. **Total technique token budget** is managed by Context Compression (F-067)
2. **Tier 1 techniques** have guaranteed budget — never skipped
3. **Tier 2 techniques** share a pooled budget — if one exceeds, others may be limited
4. **Tier 3 techniques** have highest token cost — if total exceeds budget, fall back to Tier 2 equivalent
5. **Fallback mapping:**
   - GST (T3) → CoT (T2)
   - UoT (T3) → CoT (T2) + Step-Back (T2)
   - ToT (T3) → CoT (T2)
   - Self-Consistency (T3) → CoT (T2)
   - Reflexion (T3) → Step-Back (T2)
   - Least-to-Most (T3) → CoT (T2) + ThoT (T2)

### Versioning & A/B Testing

- Each technique implementation is **versioned** (e.g., `cot-v1`, `cot-v2`, `uot-v1`)
- Versions can be **A/B tested** via DSPy (F-061) optimization framework
- Performance metrics determine which version becomes the default
- Rollback capability exists for any technique version

### Per-Tenant Configuration

- Tenant admins can **enable/disable** specific techniques via admin panel
- Default technique set is applied based on tenant's PARWA plan (Free/Pro/Enterprise)
- Enterprise tenants can create **custom technique configurations**
- Technique enable/disable does NOT affect Tier 1 (CLARA, CRP, GSD are always on)

| Tenant Plan | Available Techniques |
|-------------|---------------------|
| Free | Tier 1 only |
| Pro | Tier 1 + Tier 2 |
| Enterprise | Tier 1 + Tier 2 + Tier 3 (full) |
| Custom | All + custom technique configurations |

### Performance Monitoring

Technique performance metrics feed into Agent Performance Analytics (F-098):

| Metric | Description | Target |
|--------|-------------|--------|
| Technique Activation Rate | % of queries that trigger each technique | Baseline establishment |
| Technique Accuracy Lift | Accuracy improvement when technique is active vs inactive | > 5% improvement |
| Token Cost per Technique | Average tokens consumed per technique activation | Within budget |
| Latency Impact | Additional latency per technique | < 2s for T2, < 5s for T3 |
| Fallback Rate | % of times T3 falls back to T2 equivalent | < 10% |
| Customer Satisfaction Delta | CSAT difference for technique-active vs inactive queries | Positive correlation |

---

## Token Budget & Cost Management

### Budget Allocation Strategy

The total token budget for technique processing is allocated dynamically based on the query's model tier:

```
Light Model Query:    Total technique budget = 500 tokens
Medium Model Query:   Total technique budget = 1,500 tokens
Heavy Model Query:    Total technique budget = 3,000 tokens
```

### Budget Consumption Order

1. **Reserve Tier 1 budget first:** ~100 tokens (CLARA 50 + CRP 30 + GSD 20)
2. **Allocate Tier 2 budget:** Remaining after Tier 1, up to 50% of total
3. **Allocate Tier 3 budget:** Remaining after Tier 2, up to 100% of total
4. **Overflow handling:** If total exceeds budget, Tier 3 techniques are reduced first, then Tier 2

### Cost Optimization Features

- **CRP (F-140)** actively reduces output tokens by 30-40%
- **Context Compression (F-067)** manages input context to stay within model limits
- **Technique caching:** If the same technique runs on similar queries, partial results may be cached
- **Early termination:** If a technique's reasoning reaches high confidence early, remaining steps are skipped

---

## Performance Metrics & Monitoring

### Dashboard Metrics

The following metrics should be displayed in the PARWA admin dashboard:

1. **Technique Activation Heatmap:** Which techniques activate most frequently, by intent type and time of day
2. **Accuracy by Technique:** Accuracy rate for each technique when active
3. **Token Cost Trend:** Token consumption trends per technique over time
4. **Fallback Frequency:** How often Tier 3 falls back to Tier 2, with reasons
5. **Customer Satisfaction Correlation:** CSAT scores segmented by active technique combination
6. **Latency Distribution:** Response latency by technique combination

### Alerting Rules

| Condition | Alert Level | Action |
|-----------|------------|--------|
| Technique fallback rate > 20% for 1 hour | Warning | Review token budgets |
| Any technique accuracy drops > 10% | Critical | Investigate technique logic |
| Technique latency > 10s consistently | Warning | Optimize or reduce technique |
| Tier 3 activation rate < 5% (should be higher) | Info | Review trigger thresholds |

---

## Appendix: Technique Decision Flowchart

```
START: New Query Received
  │
  ▼
┌─────────────────────────┐
│ ALWAYS ACTIVATE:        │
│ • CLARA (T1)           │
│ • CRP (T1)             │
│ • GSD State (T1)       │
│ • Technique Router     │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ EVALUATE SIGNALS:       │
│ • Complexity Score      │
│ • Confidence Score      │
│ • Sentiment Score       │
│ • Customer Tier         │
│ • Monetary Value        │
│ • Turn Count            │
│ • Intent Type           │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐     NO
│ COMPLEXITY > 0.4? ──────┼────────────→ Skip CoT
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE CoT]
          │
          ▼
┌─────────────────────────┐     NO
│ CONFIDENCE < 0.7? ──────┼────────────→ Skip Reverse Thinking
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE Reverse Thinking + Step-Back]
          │
          ▼
┌─────────────────────────┐     NO
│ CUSTOMER = VIP? ────────┼────────────→ Skip VIP Techniques
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE UoT + Reflexion]
          │
          ▼
┌─────────────────────────┐     NO
│ SENTIMENT < 0.3? ───────┼────────────→ Skip Sentiment Techniques
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE UoT + Step-Back]
          │
          ▼
┌─────────────────────────┐     NO
│ AMOUNT > $100? ─────────┼────────────→ Skip Financial Techniques
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE Self-Consistency]
          │
          ▼
┌─────────────────────────┐     NO
│ TURNS > 5? ─────────────┼────────────→ Skip ThoT
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE ThoT]
          │
          ▼
┌─────────────────────────┐     NO
│ EXTERNAL DATA NEEDED? ──┼────────────→ Skip ReAct
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE ReAct]
          │
          ▼
┌─────────────────────────┐     NO
│ COMPLEXITY > 0.7? ──────┼────────────→ Skip Complex Techniques
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE Least-to-Most Decomposition]
          │
          ▼
┌─────────────────────────┐     NO
│ ≥ 3 RESOLUTION PATHS? ──┼────────────→ Skip ToT
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE Tree of Thoughts]
          │
          ▼
┌─────────────────────────┐     NO
│ STRATEGIC DECISION? ────┼────────────→ Skip GST
└─────────┬───────────────┘
          │ YES
          ▼
    [ACTIVATE GST]
          │
          ▼
┌─────────────────────────┐
│ DEDUPLICATE & ORDER:    │
│ • Remove duplicate tech │
│ • Order: T1 → T2 → T3  │
│ • Check token budget    │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐     OVER BUDGET
│ TOKEN BUDGET OK? ───────┼────────────→ Fallback T3 → T2
└─────────┬───────────────┘
          │ WITHIN BUDGET
          ▼
    [EXECUTE TECHNIQUE PIPELINE]
          │
          ▼
    [CLARA QUALITY GATE]
          │
          ▼
    [RESPONSE DELIVERED]
          │
          ▼
    [LOG METRICS → F-098]
```

---

## Document Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025 | Initial framework specification |

---

*This document is part of the PARWA AI Architecture specification series. For related documents, refer to the PARWA Context Bible and individual Feature Specification documents.*
