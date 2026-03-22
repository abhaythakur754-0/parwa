# WEEK 9 PARALLEL EXECUTION ROADMAP
# ================================

## REALITY CHECK: Import Dependencies

```python
# Mini agents import from:
from variants.base_agents.base_faq_agent import BaseFAQAgent  # Builder 1
from variants.mini.config import MiniConfig                   # Builder 2

# Tools import from:
from variants.mini.agents import *                            # Builder 3

# Workflows import from:
from variants.mini.tools import *                             # Builder 4
```

## TWO OPTIONS FOR PARALLELISM

### OPTION A: PRACTICAL (2 Phases, Maximum Parallelism)

```
PHASE 1 (2 builders PARALLEL):
├── Builder 1: Base Agents (12 files) ← NO DEPS
└── Builder 2: Mini Config (4 files)  ← NO DEPS
    ⏱️ Time: ~30 min (parallel)

PHASE 2 (2 builders PARALLEL):
├── Builder 3: Mini Agents (9 files)  ← Depends on Phase 1
└── Builder 4: Mini Tools (7 files)   ← Depends on Phase 1
    ⏱️ Time: ~30 min (parallel)

PHASE 3 (1 builder):
└── Builder 5: Workflows (8 files)    ← Depends on Phase 2
    ⏱️ Time: ~20 min

TOTAL: ~80 min with parallelism vs ~150 min sequential
```

### OPTION B: FULL PARALLEL (Requires Code Changes)

Each builder creates SELF-CONTAINED files with NO cross-imports:

```
ALL 5 BUILDERS PARALLEL:
├── Builder 1: Creates base_agents/ (12 files)
├── Builder 2: Creates mini_config/ (4 files) 
├── Builder 3: Creates mini_agents/ (9 files) - INCLUDES base class code
├── Builder 4: Creates mini_tools/ (7 files) - STANDALONE
└── Builder 5: Creates mini_workflows/ (8 files) - STANDALONE

⚠️ Tradeoff: Code duplication, larger files, harder maintenance
```

---

## RECOMMENDED: OPTION A (Practical Parallelism)

**Why:** 
- Minimal code duplication
- Clear ownership
- Still achieves 50% time savings
- Easy to maintain

**Execution Flow:**
```
Start Phase 1 ─────► Builder 1 ─────► Done
                  └─► Builder 2 ─────► Done
                        │
                        ▼
Start Phase 2 ─────► Builder 3 ─────► Done
                  └─► Builder 4 ─────► Done
                        │
                        ▼
Start Phase 3 ─────► Builder 5 ─────► Done
```

---

## FILE OWNERSHIP (NO OVERLAPS)

### Builder 1: Base Agents
```
variants/__init__.py
variants/base_agents/__init__.py
variants/base_agents/base_agent.py
variants/base_agents/base_faq_agent.py
variants/base_agents/base_email_agent.py
variants/base_agents/base_chat_agent.py
variants/base_agents/base_sms_agent.py
variants/base_agents/base_voice_agent.py
variants/base_agents/base_ticket_agent.py
variants/base_agents/base_escalation_agent.py
variants/base_agents/base_refund_agent.py
tests/unit/test_base_agents.py
```

### Builder 2: Mini Config
```
variants/mini/__init__.py
variants/mini/config.py
variants/mini/anti_arbitrage_config.py
tests/unit/test_mini_config.py
```

### Builder 3: Mini Agents
```
variants/mini/agents/__init__.py
variants/mini/agents/faq_agent.py
variants/mini/agents/email_agent.py
variants/mini/agents/chat_agent.py
variants/mini/agents/sms_agent.py
variants/mini/agents/voice_agent.py
variants/mini/agents/ticket_agent.py
variants/mini/agents/escalation_agent.py
variants/mini/agents/refund_agent.py
tests/unit/test_mini_agents.py (shared ownership with Builder 4)
```

### Builder 4: Mini Tools
```
variants/mini/tools/__init__.py
variants/mini/tools/faq_search.py
variants/mini/tools/order_lookup.py
variants/mini/tools/ticket_create.py
variants/mini/tools/notification.py
variants/mini/tools/refund_verification_tools.py
tests/unit/test_base_refund_agent.py
```

### Builder 5: Mini Workflows
```
variants/mini/workflows/__init__.py
variants/mini/workflows/inquiry.py
variants/mini/workflows/ticket_creation.py
variants/mini/workflows/escalation.py
variants/mini/workflows/order_status.py
variants/mini/workflows/refund_verification.py
tests/unit/test_mini_workflows.py
```

---

## CRITICAL TESTS BY BUILDER

| Test | Builder | File |
|------|---------|------|
| BaseAgent inheritance | 1 | test_base_agents.py |
| AgentResponse fields | 1 | test_base_agents.py |
| MiniConfig defaults | 2 | test_mini_config.py |
| Mini agents tier=light | 3 | test_mini_agents.py |
| Mini agents variant=mini | 3 | test_mini_agents.py |
| Voice 2-call limit | 3 | test_mini_agents.py |
| **Paddle NOT called** | 3,4,5 | multiple |
| Refund $50 limit | 3 | test_mini_agents.py |
| Human handoff trigger | 3 | test_mini_agents.py |
| Tools work standalone | 4 | test_base_refund_agent.py |
| Workflows complete | 5 | test_mini_workflows.py |

---

## SUMMARY

| Metric | Value |
|--------|-------|
| Total Files | 40 |
| Total Tests | 230+ |
| Builders | 5 |
| Phases | 3 |
| Max Parallelism | 2 builders at once |
| Time Savings | ~50% vs sequential |
| Code Duplication | None |

**Status:** ✅ WEEK 9 COMPLETE
