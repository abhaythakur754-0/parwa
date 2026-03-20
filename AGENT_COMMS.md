# AGENT_COMMS.md — Week 7 Day 1-5
# Last updated: Builder 4
# Current status: WEEK 7 DAY 1 & DAY 4 COMPLETE ✅

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 7 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent

> **Phase: Phase 2 — Core AI Engine (TRIVYA Tier 3 + Integrations + Compliance)**
>
> **Week 7 Goals:**
> - Day 1: TRIVYA Tier 3 chain (7 advanced reasoning techniques)
> - Day 2: E-commerce + comms integration clients (Shopify, Paddle, Twilio, Email, Zendesk)
> - Day 3: Dev + logistics + compliance integration clients
> - Day 4: Compliance layer (jurisdiction, SLA, GDPR, healthcare)
> - Day 5: Integration tests for T1+T2+T3 pipeline
> - Day 6: Tester Agent runs full week integration test
>
> **PAYMENT PROCESSOR: PADDLE** (Merchant of Record)
> - Handles: Tax compliance, Payment processing, Subscriptions, Chargebacks
> - No Stripe needed - Paddle is the complete solution for SaaS
>
> **CRITICAL RULES:**
> 1. Within-day files CAN depend on each other — build in order listed
> 2. Across-day files CANNOT depend on each other — days run in parallel
> 3. No Docker — use mocked sessions in tests
> 4. Build → Unit Test passes → THEN push (ONE push per file)
> 5. Type hints on ALL functions, docstrings on ALL classes/functions
> 6. TRIVYA T3 only fires on high-stakes scenarios (VIP + amount>$100 + anger>80%)

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — TRIVYA Tier 3 Chain
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/trivya_techniques/tier3/trigger_detector.py` — Detects when T3 should fire
2. `shared/trivya_techniques/tier3/gst.py` — Generated Step-by-step Thought
3. `shared/trivya_techniques/tier3/universe_of_thoughts.py` — Multiple solution paths
4. `shared/trivya_techniques/tier3/tree_of_thoughts.py` — Tree structure reasoning
5. `shared/trivya_techniques/tier3/self_consistency.py` — Majority vote across paths
6. `shared/trivya_techniques/tier3/reflexion.py` — Reflection loop
7. `shared/trivya_techniques/tier3/least_to_most.py` — Decomposes complex queries
8. `tests/unit/test_trivya_tier3.py`

**Dependencies:**
- `shared/confidence/scorer.py` (Wk6)
- `shared/core_functions/config.py` (Wk1)

**Tests Required:**
- T3 only fires on VIP/amount>$100/anger>80%
- GST produces structured thought output
- Tree structure generated correctly
- Majority vote across paths works
- Reflection loop runs
- Complex query decomposition works

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — E-commerce + Comms Integration Clients
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/integrations/shopify_client.py` — E-commerce store integration
2. `shared/integrations/paddle_client.py` — **Payment processor (MoR)**
3. `shared/integrations/twilio_client.py` — SMS + Voice communication
4. `shared/integrations/email_client.py` — Email sending (Brevo/SendGrid)
5. `shared/integrations/zendesk_client.py` — Ticketing system

**Dependencies:**
- `shared/core_functions/config.py` (Wk1)
- `shared/core_functions/logger.py` (Wk1)

### PADDLE CLIENT SPECIFICATION

**Purpose:** Paddle is a Merchant of Record (MoR) for SaaS. Handles:
- Payment processing (one-time & subscriptions)
- Tax compliance (VAT, sales tax globally)
- Chargeback management
- Subscription management
- Localized checkouts

**API Configuration:**
- Read credentials from environment variables only
- `PADDLE_CLIENT_TOKEN` — Client token from .env
- `PADDLE_API_KEY` — API key from .env
- Webhook will be added at deployment time

**Key Methods to Implement:**
- `create_subscription(customer_id, plan_id)` — Create new subscription
- `cancel_subscription(subscription_id)` — Cancel subscription
- `get_subscription(subscription_id)` — Get subscription details
- `process_refund(transaction_id, amount)` — Process refund (with HITL gate)
- `get_customer(customer_id)` — Get customer details
- `webhook_verify(signature, payload)` — Verify webhook authenticity

**Tests Required:**
- Shopify mock connection initialises
- Paddle refund gate enforced (no direct refunds without approval)
- Twilio SMS + voice mock works
- Email send mocked
- Zendesk ticket create mocked

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Dev + Logistics + Compliance Integration Clients
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/integrations/github_client.py` — Repository access
2. `shared/integrations/aftership_client.py` — Shipment tracking
3. `shared/integrations/epic_ehr_client.py` — Healthcare EHR (read-only)
4. `tests/unit/test_integration_clients.py` — All D2+D3 clients

**Dependencies:**
- `shared/core_functions/config.py` (Wk1)

**Tests Required:**
- GitHub repo access mocked
- Tracking mock works
- EHR read-only access enforced

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Compliance Layer Chain
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `shared/compliance/jurisdiction.py` — Jurisdiction-based rules (e.g., IN→TCPA)
2. `shared/compliance/sla_calculator.py` — SLA breach calculation
3. `shared/compliance/gdpr_engine.py` — GDPR export & soft-delete
4. `shared/compliance/healthcare_guard.py` — BAA check, PHI protection

**Dependencies:**
- `shared/core_functions/config.py` (Wk1)
- `shared/core_functions/compliance.py` (Wk1)

**Tests Required:**
- IN client → TCPA rules applied
- SLA breach calculated correctly
- GDPR export complete, soft-delete masks PII
- BAA check enforced, PHI not logged

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Integration Tests for T1+T2+T3
═══════════════════════════════════════════════════════════════════════════════

**Files to Build (in order):**
1. `tests/unit/test_trivya_tier1_tier2.py` (update) — Full T1+T2+T3 pipeline

**Dependencies:**
- All TRIVYA T1+T2+T3 files (Wk6-7)

**Tests Required:**
- Full pipeline T1→T2→T3 works end-to-end
- T3 activates on correct triggers
- All techniques produce expected outputs

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests | Pushed |
|---------|-----|--------|-------|-------|--------|
| Builder 1 | Day 1 | ✅ DONE | T3 chain (7 files) | PASS (73 tests) | YES |
| Builder 2 | Day 2 | PENDING | Integrations (5 files) | NOT RUN | NO |
| Builder 3 | Day 3 | PENDING | Dev/logistics (4 files) | NOT RUN | NO |
| Builder 4 | Day 4 | ✅ DONE | Compliance (5 files) | PASS (49 tests) | YES |
| Builder 5 | Day 5 | PENDING | Tests (1 file) | NOT RUN | NO |

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 → DAY 4 STATUS
═══════════════════════════════════════════════════════════════════════════════

Date: 2026-03-21
Zai Session: Builder 4 - Week 7 Day 4

**File 1:** `shared/compliance/jurisdiction.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: JurisdictionManager with 10 jurisdictions (US/TCPA, IN/DPDPA, EU/GDPR, etc.)

**File 2:** `shared/compliance/sla_calculator.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: SLACalculator with 4-tier policies (Critical/High/Standard/Low)

**File 3:** `shared/compliance/gdpr_engine.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: GDPREngine with export/erasure/masking/anonymization

**File 4:** `shared/compliance/healthcare_guard.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: HealthcareGuard with BAA verification + PHI protection

**File 5:** `shared/compliance/__init__.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: Module init with all exports

**File 6:** `tests/unit/test_compliance_layer.py`
- Status: ✅ DONE
- Unit Test: 49 tests PASS
- Notes: Complete test coverage for all compliance modules + integration tests

**Overall Day Status:** ✅ DONE — All files built, 49 tests passing

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 → DAY 1 STATUS
═══════════════════════════════════════════════════════════════════════════════

Date: 2026-03-21
Zai Session: Builder 1 - Week 7 Day 1

**File 1:** `shared/trivya_techniques/tier3/trigger_detector.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: T3TriggerDetector with VIP/amount/anger thresholds + risk factors

**File 2:** `shared/trivya_techniques/tier3/gst.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: GeneratedStepByStepThought with procedural/decision/diagnostic steps

**File 3:** `shared/trivya_techniques/tier3/universe_of_thoughts.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: UniverseOfThoughts with 6 path types + cross-pollination

**File 4:** `shared/trivya_techniques/tier3/tree_of_thoughts.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: TreeOfThoughts with BFS/DFS/Best-First/Beam search strategies

**File 5:** `shared/trivya_techniques/tier3/self_consistency.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: SelfConsistency with majority/weighted/unanimous/supermajority voting

**File 6:** `shared/trivya_techniques/tier3/reflexion.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: Reflexion with iterative critique/improve/reflect loops

**File 7:** `shared/trivya_techniques/tier3/least_to_most.py`
- Status: ✅ DONE
- Unit Test: PASS
- Notes: LeastToMost with query decomposition + difficulty ordering

**File 8:** `tests/unit/test_trivya_tier3.py`
- Status: ✅ DONE
- Unit Test: 73 tests PASS
- Notes: Complete test coverage for all T3 techniques + integration tests

**Overall Day Status:** ✅ DONE — All files built, 73 tests passing

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER AGENT (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Status:** PENDING — Waiting for all builders to complete

**Test Command:** `pytest tests/integration/test_week7_trivya_complete.py -v`

**Verification Criteria:**
- Full TRIVYA T1+T2+T3: all fire correctly on correct triggers
- T3 does NOT activate on simple FAQ queries
- T3 DOES activate on VIP + amount>$100 + anger>80% scenario
- All integration clients initialise without credential errors (mocked)
- GDPR engine: export and soft-delete both work correctly
- Healthcare guard: BAA check enforced, no PHI in logs

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
6. **Paddle is Merchant of Record** — handles tax, payments, subscriptions, chargebacks
7. **No direct refunds** — always require HITL approval for refunds
8. **PHI protection** — never log PHI data
9. **API Keys in env vars** — never hardcode credentials

---

═══════════════════════════════════════════════════════════════════════════════
## API CREDENTIALS (Store in .env, Never Hardcode)
═══════════════════════════════════════════════════════════════════════════════

| Service | Env Var Name |
|---------|--------------|
| Paddle Client Token | `PADDLE_CLIENT_TOKEN` |
| Paddle API Key | `PADDLE_API_KEY` |
| Twilio SID | `TWILIO_ACCOUNT_SID` |
| Twilio Token | `TWILIO_AUTH_TOKEN` |
| Twilio API Key | `TWILIO_API_KEY` |
| Google AI | `GOOGLE_AI_KEY` |
| Cerebras | `CEREBRAS_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Brevo | `BREVO_API_KEY` |
| GitHub | `GITHUB_TOKEN` |
