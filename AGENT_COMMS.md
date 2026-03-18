# AGENT_COMMS.md — Week 6 Day 1-5
# Last updated: Manager Agent
# Current status: WEEK 6 READY TO START

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

**Dependencies:** rag_pipeline.py, hyde.py (Wk5), gsd_engine (Wk5), router.py (Wk5)

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
1. `shared/trivya_techniques/tier2/trigger_detector.py` — Detects decision_needed
2. `shared/trivya_techniques/tier2/chain_of_thought.py` — Step-by-step reasoning
3. `shared/trivya_techniques/tier2/react.py` — Reason+act loop
4. `shared/trivya_techniques/tier2/reverse_thinking.py` — Reverse approach
5. `shared/trivya_techniques/tier2/step_back.py` — Abstract question
6. `shared/trivya_techniques/tier2/thread_of_thought.py` — Thread context
7. `tests/unit/test_trivya_tier2.py`

**Dependencies:** config.py (Wk1), gsd_engine (Wk5)

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

**Dependencies:** config.py (Wk1), compliance.py (Wk1), audit_trail.py (Wk1)

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

**Dependencies:** router.py (Wk5), thresholds.py (Wk6 D3)

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

**Dependencies:** kb_manager.py (Wk5), all TRIVYA T1+T2 files

**Tests Required:**
- Bootstraps with industry FAQs
- T1+T2 pipeline works end-to-end

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests |
|---------|-----|--------|-------|-------|
| Builder 1 | Day 1 | PENDING | T1 chain | NOT RUN |
| Builder 2 | Day 2 | PENDING | T2 chain | NOT RUN |
| Builder 3 | Day 3 | PENDING | Confidence | NOT RUN |
| Builder 4 | Day 4 | PENDING | Sentiment | NOT RUN |
| Builder 5 | Day 5 | PENDING | Cold start | NOT RUN |

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING

**Test Command:** `pytest tests/integration/test_week6_trivya.py -v`

**Verification:**
- TRIVYA T1 fires on every query
- T2 only on decision_needed/multi_step
- Confidence: 95%+ GRADUATE, <70% ESCALATE
- Sentiment: high anger → PARWA High
- Cold start bootstraps correctly

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

1. Within-day dependencies OK — build in order
2. Across-day dependencies FORBIDDEN
3. No Docker — mock everything
4. One push per file after tests pass
5. Type hints + docstrings required
