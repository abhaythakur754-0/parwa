# PARWA - AI Customer Service Platform

## Project Overview
PARWA is an AI-powered customer service platform with 3 variants (Mini PARWA, PARWA, PARWA High).
All variants share the SAME brain (22 nodes, 6 agents, 7 frameworks, DSPy). The only differences
are volume, channels, concurrent capacity, and action permissions.

## Architecture: Same Brain, Different Capacity
- 22 Nodes traversed on EVERY ticket on EVERY variant
- 6 Agents work SIMULTANEOUSLY on every ticket
- 7 AI Frameworks available on all nodes for all variants
- DSPy auto-optimizes prompts on all 22 nodes
- Think vs Act split: All variants THINK identically, ACTING is permission-gated

## Tech Stack
- Python 3.12+
- LangGraph (orchestration framework - routes, does NOT think)
- LangChain (LLM interface)
- Pydantic (state schemas)
- pytest (testing)

## Project Structure
```
parwa/
├── parwa/
│   ├── state.py              # Shared state schema (TicketState)
│   ├── config.py             # Variant configurations (Mini/PARWA/High)
│   ├── graph.py              # Main LangGraph StateGraph definition
│   ├── nodes/                # 22 node implementations
│   ├── agents/               # 6 agent definitions
│   ├── frameworks/           # 7 AI framework implementations
│   ├── permissions/          # Action permission matrix
│   └── utils/                # Shared utilities (LLM client, etc.)
├── tests/
│   ├── test_nodes/           # Unit tests per node
│   ├── test_agents/          # Unit tests per agent
│   ├── test_graph.py         # Integration test for full graph
│   └── test_variants.py      # Variant differentiation tests
└── CLAUDE.md                 # This file
```

## 22-Node Architecture (in pipeline order)
1. INGEST → 2. INTENT_CLASSIFIER → 18. SENTIMENT_ANALYZER
3. Then branching: ESCALATION_DECISION / FAQ_MATCHER / INTEGRATION_LOOKUP
4. KB_RETRIEVER → CONTEXT_MANAGER → REASONING_ENGINE
5. REVERSE_THINKER / TREE_OF_THOUGHTS / STRATEGY_PLANNER (parallel)
6. ACTION_PLANNER → ACTION_EXECUTOR → ACTION_VERIFIER
7. PROACTIVE_CHECKER / PREDICTION_ENGINE / FEEDBACK_LOOP (parallel)
8. PII_COMPLIANCE_GUARD → AUDIT_LOGGER → QUALITY_SCORER
9. RESPONSE_FORMATTER (if quality >= 80, else loop back)

## 6 Agents (node ownership)
- Router Agent: Nodes 1, 2, 18, 20
- Knowledge Agent: Nodes 3, 4, 19, 5
- Reasoning Agent: Nodes 6, 10, 12, 11
- Action Agent: Nodes 7, 8, 9
- Compliance Agent: Nodes 15, 16, 21, 17
- Proactive Agent: Nodes 13, 14, 22

## Variant Configuration
- Mini PARWA: $999/mo, 500 tickets, Email+Chat, 3 concurrent, limited actions
- PARWA: $2,499/mo, 2000 tickets, Email+Chat+Social, 4 concurrent, full actions
- PARWA High: $4,999/mo, 5000 tickets, All channels, 6 concurrent, full+ actions

## Key Rules
- Accuracy FIRST, tokens are a side effect
- All 22 nodes on ALL variants - no skipping
- Think vs Act: Mini can THINK everything, but ACT only on basics + RECOMMEND the rest
- LangGraph ROUTES only - it does NOT think
- DSPy OPTIMIZES prompts - it does NOT replace frameworks
- Frameworks provide THINKING STYLES - activated based on ticket complexity

## Testing Requirements
- Every node must have a unit test
- The full graph must be tested end-to-end
- Variant differentiation must be tested (same thinking, different actions)
- Mini PARWA recommendation flow must be tested
- Quality score loop-back must be tested
