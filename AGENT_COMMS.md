# AGENT_COMMS.md — Week 6 Day 1-5
# Last updated: Manager Agent
# Current status: WEEK 6 DAY 1 READY TO START

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 6 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent

> **Phase: Phase 2 — Core AI Engine (TRIVYA Techniques + Confidence + Sentiment)**
>
> **Week 6 Goals:**
> - Day 1: TRIVYA Tier 1 chain (CLARA, CRP, GSD Integration, Orchestrator)
> - Day 2: TRIVYA Tier 2 chain (6 techniques)
> - Day 3: Confidence scoring + Compliance tests
> - Day 4: Sentiment analyzer + routing rules
> - Day 5: Cold start + T1+T2 integration tests
> - Day 6: Tester Agent runs full week integration test
>
> **CRITICAL RULES:**
> 1. Within-day files CAN depend on each other — build in order listed
> 2. Across-day files CANNOT depend on each other — days run in parallel
> 3. No Docker — use mocked sessions in tests
> 4. Build → Unit Test passes → THEN push (ONE push per file)
> 5. Type hints on ALL functions, docstrings on ALL classes/functions
> 6. TRIVYA T1 always fires — T2 conditional on complexity

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — TRIVYA Tier 1 Chain
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/trivya_techniques/tier1/clara.py` — Context-Aware Retrieval
2. `shared/trivya_techniques/tier1/crp.py` — Compressed Response Protocol
3. `shared/trivya_techniques/tier1/gsd_integration.py` — GSD State integration
4. `shared/trivya_techniques/orchestrator.py` — Main orchestrator
5. `tests/unit/test_trivya_tier1.py`

**Dependencies:** 
- `shared/knowledge_base/rag_pipeline.py` (Wk5)
- `shared/knowledge_base/hyde.py` (Wk5)
- `shared/gsd_engine/state_engine.py` (Wk5)
- `shared/smart_router/router.py` (Wk5)
- `shared/core_functions/config.py` (Wk1)

**Tests Required:**
- CLARA retrieves relevant context
- CRP compresses correctly
- GSD state integrates with T1
- T1 always fires on every query

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — TRIVYA Tier 2 Chain
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/trivya_techniques/tier2/trigger_detector.py`
2. `shared/trivya_techniques/tier2/chain_of_thought.py`
3. `shared/trivya_techniques/tier2/react.py`
4. `shared/trivya_techniques/tier2/reverse_thinking.py`
5. `shared/trivya_techniques/tier2/step_back.py`
6. `shared/trivya_techniques/tier2/thread_of_thought.py`
7. `tests/unit/test_trivya_tier2.py`

**Dependencies:**
- `shared/core_functions/config.py` (Wk1)
- `shared/gsd_engine/state_engine.py` (Wk5)

**Tests Required:**
- Detects decision_needed queries
- Produces step-by-step reasoning
- Reason+act loop runs
- All 6 techniques produce different outputs

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Confidence + Compliance Tests
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/confidence/thresholds.py` — GRADUATE=95%, ESCALATE=70%
2. `shared/confidence/scorer.py` — Weighted avg scoring
3. `tests/unit/test_confidence_scorer.py`
4. `tests/unit/test_compliance.py`
5. `tests/unit/test_audit_trail.py`

**Dependencies:**
- `shared/core_functions/config.py` (Wk1)
- `shared/core_functions/compliance.py` (Wk1)
- `shared/core_functions/audit_trail.py` (Wk1)

**Tests Required:**
- Thresholds correct (95% GRADUATE, 70% ESCALATE)
- Weighted avg 40+30+20+10=100%

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Sentiment Chain
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/sentiment/analyzer.py` — Detect anger, frustration, etc.
2. `shared/sentiment/routing_rules.py` — Route to appropriate pathway
3. `tests/unit/test_sentiment.py`

**Dependencies:**
- `shared/smart_router/router.py` (Wk5)
- `shared/confidence/thresholds.py` (Wk6 D3)

**Tests Required:**
- Anger score routes to High pathway
- Routing rules apply correctly

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Cold Start + Integration Tests
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/knowledge_base/cold_start.py` — Bootstrap new client KB
2. `tests/unit/test_trivya_tier1_tier2.py` — Full T1+T2 integration

**Dependencies:**
- `shared/knowledge_base/kb_manager.py` (Wk5)
- All TRIVYA T1+T2 files (Wk6 D1-D2)

**Tests Required:**
- Bootstraps with industry FAQs
- T1+T2 pipeline works end-to-end

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests | Pushed |
|---------|-----|--------|-------|-------|--------|
| Builder 1 | Day 1 | PENDING | T1 chain (4 files) | NOT RUN | NO |
| Builder 2 | Day 2 | PENDING | T2 chain (6 files) | NOT RUN | NO |
| Builder 3 | Day 3 | PENDING | Confidence (2 files) | NOT RUN | NO |
| Builder 4 | Day 4 | PENDING | Sentiment (2 files) | NOT RUN | NO |
| Builder 5 | Day 5 | PENDING | Cold start (2 files) | NOT RUN | NO |

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

**Test Command:** `pytest tests/integration/test_week6_trivya.py -v`

**Verification Criteria:**
- TRIVYA T1 fires on every query
- T2 only on decision_needed/multi_step
- Confidence: 95%+ GRADUATE, <70% ESCALATE
- Sentiment: high anger → PARWA High
- Cold start bootstraps correctly

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. Within-day dependencies OK — build files in order listed
2. Across-day dependencies FORBIDDEN — don't import from other days
3. No Docker — mock everything in tests
4. One push per file — only after tests pass
5. Type hints + docstrings required on all functions
6. TRIVYA T1 ALWAYS fires on every query
7. TRIVYA T2 only fires on complex/decision queries
