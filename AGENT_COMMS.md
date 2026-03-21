# AGENT_COMMS.md — Week 9+ PARALLEL EXECUTION ROADMAP
# Last updated: Manager Agent
# Status: READY FOR PARALLEL EXECUTION

═══════════════════════════════════════════════════════════════════════════════
## PARALLEL EXECUTION RULES
═══════════════════════════════════════════════════════════════════════════════

```
+-----------------------------------------------------------------------+
| PARALLEL RULE (STRICT):                                               |
|                                                                       |
| ✅ Within a DAY: files CAN depend on each other (sequential build)    |
|    One builder builds files in order, top to bottom                   |
|                                                                       |
| ❌ Across DAYS of same WEEK: files CANNOT depend on each other        |
|    All 5 builders run in PARALLEL (Day 1-5 simultaneously)            |
|                                                                       |
| ✅ Across WEEKS: files CAN depend on any file from previous weeks     |
|    (already built and available)                                      |
|                                                                       |
| TOOL: Zai agent (builder)                                             |
|                                                                       |
| TESTING: Tester Agent runs ONCE at end of week (Day 6)                |
|                                                                       |
| GIT: Agent commits and pushes each file after its unit test passes    |
+-----------------------------------------------------------------------+
```

═══════════════════════════════════════════════════════════════════════════════
## COMPLETE ROADMAP LOCATION
═══════════════════════════════════════════════════════════════════════════════

**Full roadmap from Week 9 to Week 60:**
`/home/z/my-project/agentpayv2/docs/WEEK9_TO_WEEK60_COMPLETE_ROADMAP.md`

**This file contains:**
- Every week from 9 to 60
- Every file to be created
- All dependencies clearly marked
- Tester commands and pass criteria

═══════════════════════════════════════════════════════════════════════════════
## PHASE OVERVIEW
═══════════════════════════════════════════════════════════════════════════════

| Phase | Weeks | Goal | Status |
|-------|-------|------|--------|
| 1-2 | 1-4 | Foundation | ✅ COMPLETE |
| 2 | 5-8 | Core AI Engine | ✅ COMPLETE |
| **3** | **9-14** | **Variants & Integrations** | 🔵 IN PROGRESS |
| 4 | 15-18 | Frontend Foundation | ⬜ Pending |
| 5 | 19-20 | First Clients | ⬜ Pending |
| 6 | 21-22 | Scale to 10 clients | ⬜ Pending |
| 7 | 23-27 | Polish & Advanced Features | ⬜ Pending |
| 8 | 28-40 | Enterprise Preparation | ⬜ Pending |
| 9 | 41-44 | Cloud Migration | ⬜ Pending |
| 10 | 45-46 | Billing System | ⬜ Pending |
| 11 | 47-49 | Mobile App | ⬜ Pending |
| 12 | 50-52 | Enterprise SSO | ⬜ Pending |
| 13 | 53-55 | High Availability | ⬜ Pending |
| 14 | 56-60 | SOC 2 Compliance | ⬜ Pending |

═══════════════════════════════════════════════════════════════════════════════
## CURRENT WEEK: WEEK 9 — MINI PARWA VARIANT
═══════════════════════════════════════════════════════════════════════════════

**Execution Model: FULLY PARALLEL (5 BUILDERS)**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WEEK 9 - ALL BUILDERS PARALLEL                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │   BUILDER 1     │  │   BUILDER 2     │  │   BUILDER 3     │         │
│  │   (Day 1)       │  │   (Day 2)       │  │   (Day 3)       │         │
│  │                 │  │                 │  │                 │         │
│  │ Base Agents     │  │ Refund + Config │  │ Mini Agents     │         │
│  │ (11 files)      │  │ (5 files)       │  │ (5 files)       │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐                              │
│  │   BUILDER 4     │  │   BUILDER 5     │                              │
│  │   (Day 4)       │  │   (Day 5)       │                              │
│  │                 │  │                 │                              │
│  │ Mini Agents     │  │ Tools + WF      │                              │
│  │ (5 files)       │  │ (14 files)      │                              │
│  └─────────────────┘  └─────────────────┘                              │
│                                                                         │
│  ALL builders import from shared/ ONLY (Weeks 1-8)                     │
│  NO inter-builder dependencies                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### BUILDER 1 (Day 1) — Base Agent Abstract + Core Base Agents

**Files (in order):**
```
1.  variants/__init__.py
2.  variants/base_agents/__init__.py
3.  variants/base_agents/base_agent.py
4.  variants/base_agents/base_faq_agent.py
5.  variants/base_agents/base_email_agent.py
6.  variants/base_agents/base_chat_agent.py
7.  variants/base_agents/base_sms_agent.py
8.  variants/base_agents/base_voice_agent.py
9.  variants/base_agents/base_ticket_agent.py
10. variants/base_agents/base_escalation_agent.py
11. tests/unit/test_base_agents.py
```

---

### BUILDER 2 (Day 2) — Base Refund Agent + Mini Config

**Files (in order):**
```
1. variants/base_agents/base_refund_agent.py
2. variants/mini/__init__.py
3. variants/mini/config.py
4. variants/mini/anti_arbitrage_config.py
5. tests/unit/test_mini_config.py
```

---

### BUILDER 3 (Day 3) — Mini FAQ + Email + Chat + SMS Agents

**Files (in order):**
```
1. variants/mini/agents/__init__.py
2. variants/mini/agents/faq_agent.py
3. variants/mini/agents/email_agent.py
4. variants/mini/agents/chat_agent.py
5. variants/mini/agents/sms_agent.py
```

---

### BUILDER 4 (Day 4) — Mini Voice + Ticket + Escalation + Refund Agents

**Files (in order):**
```
1. variants/mini/agents/voice_agent.py
2. variants/mini/agents/ticket_agent.py
3. variants/mini/agents/escalation_agent.py
4. variants/mini/agents/refund_agent.py
5. tests/unit/test_mini_agents.py
```

---

### BUILDER 5 (Day 5) — Mini Tools + Workflows

**Files (in order):**
```
1.  variants/mini/tools/__init__.py
2.  variants/mini/tools/faq_search.py
3.  variants/mini/tools/order_lookup.py
4.  variants/mini/tools/ticket_create.py
5.  variants/mini/tools/notification.py
6.  variants/mini/tools/refund_verification_tools.py
7.  variants/mini/workflows/__init__.py
8.  variants/mini/workflows/inquiry.py
9.  variants/mini/workflows/ticket_creation.py
10. variants/mini/workflows/escalation.py
11. variants/mini/workflows/order_status.py
12. variants/mini/workflows/refund_verification.py
13. tests/unit/test_mini_workflows.py
14. tests/unit/test_base_refund_agent.py
```

---

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_week9_mini_variant.py -v`

**Pass Criteria:**
- Mini PARWA: FAQ query routes to Light tier
- Mini PARWA: refund request creates pending_approval — Stripe NOT called
- Mini PARWA: escalation triggers human handoff
- All 8 base agents initialise without errors
- Refund gate: CRITICAL — Stripe must not be called without approval

---

═══════════════════════════════════════════════════════════════════════════════
## FILE OWNERSHIP MATRIX (WEEK 9)
═══════════════════════════════════════════════════════════════════════════════

| Builder | Owns Files | Test File | Est. Tests |
|---------|------------|-----------|------------|
| **Builder 1** | 11 | test_base_agents.py | 50 |
| **Builder 2** | 5 | test_mini_config.py | 28 |
| **Builder 3** | 5 | (shared with Builder 4) | - |
| **Builder 4** | 5 | test_mini_agents.py | 82 |
| **Builder 5** | 14 | test_mini_workflows.py, test_base_refund_agent.py | 70 |

**Total Week 9: 40 files, 230+ tests**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS (WEEK 9)
═══════════════════════════════════════════════════════════════════════════════

| Builder | Files | Tests | Status |
|---------|-------|-------|--------|
| Builder 1 | 11 | 50 | ⬜ Pending |
| Builder 2 | 5 | 28 | ⬜ Pending |
| Builder 3 | 5 | - | ⬜ Pending |
| Builder 4 | 5 | 82 | ⬜ Pending |
| Builder 5 | 14 | 70 | ⬜ Pending |

**WEEK 9 STATUS: ⬜ READY TO START**

---

═══════════════════════════════════════════════════════════════════════════════
## CRITICAL RULES
═══════════════════════════════════════════════════════════════════════════════

1. **REFUND GATE IS SACRED** — Paddle/Stripe must NEVER be called without `pending_approval`
2. Type hints on ALL functions
3. Docstrings on ALL classes and public methods (Google style)
4. PEP 8 compliant
5. Max 40 lines per function
6. Each file = one commit
7. Tests must pass before commit
8. Never push if CI is red
9. **NO cross-day dependencies within same week**
10. **ALL builders can run in PARALLEL**

---

═══════════════════════════════════════════════════════════════════════════════
## HOW TO RUN BUILDERS IN PARALLEL
═══════════════════════════════════════════════════════════════════════════════

1. **Assign each builder to a separate agent:**
   - Agent 1 → Builder 1 (Day 1 files)
   - Agent 2 → Builder 2 (Day 2 files)
   - Agent 3 → Builder 3 (Day 3 files)
   - Agent 4 → Builder 4 (Day 4 files)
   - Agent 5 → Builder 5 (Day 5 files)

2. **All agents work simultaneously:**
   - Each builds files sequentially within their day
   - No waiting for other builders
   - All import from `shared/` (already built in Weeks 1-8)

3. **After all builders complete:**
   - Tester Agent runs Day 6 tests
   - Validates all files work together
   - Week marked complete when all tests pass

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT REPORT — WEEK 9 (Day 6)
═══════════════════════════════════════════════════════════════════════════════

**Date:** 2026-03-21
**Tester Agent:** Zai (Super Z)
**Week:** 9 — Mini PARWA Variant

---

### 1. TEST EXECUTION SUMMARY

| Test Suite | Tests | Status |
|------------|-------|--------|
| test_base_agents.py | 50 | ✅ PASS |
| test_mini_config.py | 28 | ✅ PASS |
| test_mini_agents.py | 82 | ✅ PASS |
| test_mini_workflows.py | 51 | ✅ PASS |
| test_base_refund_agent.py | 19 | ✅ PASS |
| **TOTAL WEEK 9** | **230** | **✅ PASS** |

---

### 2. CRITICAL TESTS VERIFICATION

| Test | Result | Notes |
|------|--------|-------|
| RLS Cross-Tenant Isolation | ✅ PASS | 2 tests passed |
| Refund Approval Gate | ✅ PASS | Payment processor NOT called without approval |
| Audit Trail Immutability | ✅ PASS | 22 tests passed |
| Human Handoff Trigger | ✅ PASS | Escalation triggers correctly |
| Voice Agent 2-Call Limit | ✅ PASS | Concurrent call limit enforced |
| $50 Refund Limit | ✅ PASS | Amount validation enforced |

---

### 3. PASS CRITERIA VERIFICATION

| Criteria | Status |
|----------|--------|
| Mini PARWA: FAQ query routes to Light tier | ✅ PASS |
| Mini PARWA: refund request creates pending_approval — Paddle NOT called | ✅ PASS |
| Mini PARWA: escalation triggers human handoff | ✅ PASS |
| All 8 base agents initialise without errors | ✅ PASS |
| Refund gate: CRITICAL — Paddle must not be called without approval | ✅ PASS |

---

### 4. GITHUB CI STATUS

```
CI Pipeline | completed | success | main | 2026-03-21T05:08:57Z
```

**CI Status:** ✅ GREEN (All checks passing)

---

### 5. FILES VERIFIED

**Base Agents (Builder 1):**
- ✅ variants/__init__.py
- ✅ variants/base_agents/__init__.py
- ✅ variants/base_agents/base_agent.py
- ✅ variants/base_agents/base_faq_agent.py
- ✅ variants/base_agents/base_email_agent.py
- ✅ variants/base_agents/base_chat_agent.py
- ✅ variants/base_agents/base_sms_agent.py
- ✅ variants/base_agents/base_voice_agent.py
- ✅ variants/base_agents/base_ticket_agent.py
- ✅ variants/base_agents/base_escalation_agent.py
- ✅ variants/base_agents/base_refund_agent.py

**Mini Config (Builder 2):**
- ✅ variants/mini/__init__.py
- ✅ variants/mini/config.py
- ✅ variants/mini/anti_arbitrage_config.py

**Mini Agents (Builders 3-4):**
- ✅ variants/mini/agents/__init__.py
- ✅ variants/mini/agents/faq_agent.py
- ✅ variants/mini/agents/email_agent.py
- ✅ variants/mini/agents/chat_agent.py
- ✅ variants/mini/agents/sms_agent.py
- ✅ variants/mini/agents/voice_agent.py
- ✅ variants/mini/agents/ticket_agent.py
- ✅ variants/mini/agents/escalation_agent.py
- ✅ variants/mini/agents/refund_agent.py

**Mini Tools + Workflows (Builder 5):**
- ✅ variants/mini/tools/__init__.py
- ✅ variants/mini/tools/faq_search.py
- ✅ variants/mini/tools/order_lookup.py
- ✅ variants/mini/tools/ticket_create.py
- ✅ variants/mini/tools/notification.py
- ✅ variants/mini/tools/refund_verification_tools.py
- ✅ variants/mini/workflows/__init__.py
- ✅ variants/mini/workflows/inquiry.py
- ✅ variants/mini/workflows/ticket_creation.py
- ✅ variants/mini/workflows/escalation.py
- ✅ variants/mini/workflows/order_status.py
- ✅ variants/mini/workflows/refund_verification.py

---

### 6. BUILDER STATUS UPDATE

| Builder | Files | Tests | Status |
|---------|-------|-------|--------|
| Builder 1 | 11 | 50 | ✅ DONE |
| Builder 2 | 5 | 28 | ✅ DONE |
| Builder 3 | 5 | - | ✅ DONE |
| Builder 4 | 5 | 82 | ✅ DONE |
| Builder 5 | 14 | 70 | ✅ DONE |

---

### 7. FINAL VERDICT

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ✅ WEEK 9 — PASS                                            ║
║                                                               ║
║   All 230 tests passed                                        ║
║   All critical tests verified                                 ║
║   GitHub CI: GREEN                                            ║
║   All 40 files verified                                       ║
║                                                               ║
║   Mini PARWA Variant: COMPLETE                                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

**Tester Agent Commit:** `chore: tester - Week 9 report - PASS`
**Timestamp:** 2026-03-21
