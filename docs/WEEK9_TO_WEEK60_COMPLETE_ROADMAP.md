# PARWA Complete Roadmap: Week 9 to Week 60
# ===========================================

## PARALLEL EXECUTION RULES

```
+-----------------------------------------------------------------------+
| PARALLEL RULE (STRICT):                                               |
|                                                                       |
| ✅ Within a DAY: files CAN depend on each other (sequential build)    |
|                                                                       |
| ❌ Across DAYS of same WEEK: files CANNOT depend on each other        |
|    (all 5 builders run in PARALLEL)                                   |
|                                                                       |
| ✅ Across WEEKS: files CAN depend on any file from previous weeks     |
|    (already built)                                                    |
|                                                                       |
| TOOL: Zai agent (builder)                                             |
|                                                                       |
| TESTING: Tester Agent runs ONCE at end of week (Day 6)                |
|                                                                       |
| GIT: Agent commits and pushes each file after its unit test passes    |
+-----------------------------------------------------------------------+
```

---

# PHASE 3: VARIANTS & INTEGRATIONS (Weeks 9-14)

---

## WEEK 9 — Mini PARWA Variant

**Goal:** Build all base agents and Mini PARWA variant

**Dependency Rule:** All 5 days run in PARALLEL. Each day's files only depend on previous weeks or earlier files within the same day.

### BUILDER 1 (Day 1) — Base Agent Abstract + Core Base Agents

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/__init__.py` | None | N/A |
| 2 | `variants/base_agents/__init__.py` | None | N/A |
| 3 | `variants/base_agents/base_agent.py` | confidence/scorer.py, security.py (Wks 3-6) | Test: base agent initialises |
| 4 | `variants/base_agents/base_faq_agent.py` | base_agent.py (same day) | Test: FAQ agent inherits correctly |
| 5 | `variants/base_agents/base_email_agent.py` | base_agent.py (same day) | Test: email agent inherits |
| 6 | `variants/base_agents/base_chat_agent.py` | base_agent.py (same day) | Test: chat agent inherits |
| 7 | `variants/base_agents/base_sms_agent.py` | base_agent.py (same day) | Test: SMS agent inherits |
| 8 | `variants/base_agents/base_voice_agent.py` | base_agent.py (same day) | Test: voice agent inherits |
| 9 | `variants/base_agents/base_ticket_agent.py` | base_agent.py (same day) | Test: ticket agent inherits |
| 10 | `variants/base_agents/base_escalation_agent.py` | base_agent.py (same day) | Test: escalation agent inherits |
| 11 | `tests/unit/test_base_agents.py` | All base agents above | PUSH ONLY AFTER THIS PASSES |

### BUILDER 2 (Day 2) — Base Refund Agent + Mini Config

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/base_agents/base_refund_agent.py` | base_agent.py (Wk9 D1), approval gates (Wks 3-4) | Test: refund gate enforced — Stripe NOT called |
| 2 | `variants/mini/__init__.py` | None | N/A |
| 3 | `variants/mini/config.py` | config.py (Wk1) | Test: Mini config loads |
| 4 | `variants/mini/anti_arbitrage_config.py` | pricing_optimizer.py (Wk1) | Test: anti-arbitrage formula correct |
| 5 | `tests/unit/test_mini_config.py` | All config files above | PUSH ONLY AFTER THIS PASSES |

### BUILDER 3 (Day 3) — Mini FAQ + Email + Chat + SMS Agents

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/mini/agents/__init__.py` | None | N/A |
| 2 | `variants/mini/agents/faq_agent.py` | base_faq_agent.py (Wk9 D1) | Test: FAQ agent routes to Light tier |
| 3 | `variants/mini/agents/email_agent.py` | base_email_agent.py (Wk9 D1) | Test: email agent processes correctly |
| 4 | `variants/mini/agents/chat_agent.py` | base_chat_agent.py (Wk9 D1) | Test: chat agent responds |
| 5 | `variants/mini/agents/sms_agent.py` | base_sms_agent.py (Wk9 D1) | Test: SMS agent sends |

### BUILDER 4 (Day 4) — Mini Voice + Ticket + Escalation + Refund Agents

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/mini/agents/voice_agent.py` | base_voice_agent.py (Wk9 D1) | Test: voice agent handles call (max 2 concurrent) |
| 2 | `variants/mini/agents/ticket_agent.py` | base_ticket_agent.py (Wk9 D1) | Test: ticket created correctly |
| 3 | `variants/mini/agents/escalation_agent.py` | base_escalation_agent.py (Wk9 D1) | Test: escalation triggers human handoff |
| 4 | `variants/mini/agents/refund_agent.py` | base_refund_agent.py (Wk9 D2) | Test: pending_approval created, Stripe NOT called |
| 5 | `tests/unit/test_mini_agents.py` | All mini agents (D3-D4) | PUSH ONLY AFTER THIS PASSES |

### BUILDER 5 (Day 5) — Mini Tools + Workflows

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/mini/tools/__init__.py` | None | N/A |
| 2 | `variants/mini/tools/faq_search.py` | shopify_client.py (Wk7) | Test: FAQ search returns results |
| 3 | `variants/mini/tools/order_lookup.py` | shopify_client.py (Wk7) | Test: order found by ID |
| 4 | `variants/mini/tools/ticket_create.py` | support API (Wk4) | Test: ticket created |
| 5 | `variants/mini/tools/notification.py` | twilio_client.py (Wk7) | Test: notification sent |
| 6 | `variants/mini/tools/refund_verification_tools.py` | stripe_client.py (Wk7) | Test: refund verified, NOT executed |
| 7 | `variants/mini/workflows/__init__.py` | None | N/A |
| 8 | `variants/mini/workflows/inquiry.py` | Mini agents (D3-D4) | Test: inquiry workflow completes |
| 9 | `variants/mini/workflows/ticket_creation.py` | Mini agents (D3-D4) | Test: ticket workflow completes |
| 10 | `variants/mini/workflows/escalation.py` | Mini agents (D3-D4) | Test: escalation workflow fires |
| 11 | `variants/mini/workflows/order_status.py` | Mini agents (D3-D4) | Test: order status returned |
| 12 | `variants/mini/workflows/refund_verification.py` | Mini agents (D3-D4) | Test: refund workflow creates pending_approval |
| 13 | `tests/unit/test_mini_workflows.py` | All workflows above | PUSH ONLY AFTER THIS PASSES |
| 14 | `tests/unit/test_base_refund_agent.py` | base_refund_agent.py (D2) | Test: refund gate tests |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_week9_mini_variant.py -v`

**Pass Criteria:**
- Mini PARWA: FAQ query routes to Light tier
- Mini PARWA: refund request creates pending_approval — Stripe NOT called
- Mini PARWA: escalation triggers human handoff
- All 8 base agents initialise without errors
- Refund gate: CRITICAL — Stripe must not be called without approval

---

## WEEK 10 — Mini Tasks + PARWA Junior Variant

**Goal:** Build Mini tasks and PARWA Junior variant

### BUILDER 1 (Day 1) — Mini Tasks

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/mini/tasks/__init__.py` | None | N/A |
| 2 | `variants/mini/tasks/answer_faq.py` | Mini agents (Wk9) | Test: FAQ answered correctly |
| 3 | `variants/mini/tasks/process_email.py` | Mini agents (Wk9) | Test: email processed |
| 4 | `variants/mini/tasks/handle_chat.py` | Mini agents (Wk9) | Test: chat handled |
| 5 | `variants/mini/tasks/make_call.py` | Mini agents (Wk9) | Test: call initiated |
| 6 | `variants/mini/tasks/create_ticket.py` | Mini agents (Wk9) | Test: ticket created |
| 7 | `variants/mini/tasks/escalate.py` | Mini agents (Wk9) | Test: escalation fires |
| 8 | `variants/mini/tasks/verify_refund.py` | Mini agents (Wk9) | Test: refund verified not executed |
| 9 | `tests/unit/test_mini_tasks.py` | All mini tasks above | PUSH ONLY AFTER THIS PASSES |

### BUILDER 2 (Day 2) — PARWA Config + Core Agents

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/parwa/__init__.py` | None | N/A |
| 2 | `variants/parwa/config.py` | config.py (Wk1) | Test: PARWA config loads |
| 3 | `variants/parwa/anti_arbitrage_config.py` | pricing_optimizer.py (Wk1) | Test: 1x PARWA shows 0.5 hrs/day |
| 4 | `variants/parwa/agents/__init__.py` | None | N/A |
| 5 | `variants/parwa/agents/faq_agent.py` | base_faq_agent.py (Wk9) | Test: PARWA FAQ routes to Light |
| 6 | `variants/parwa/agents/email_agent.py` | base_email_agent.py (Wk9) | Test: PARWA email processes |
| 7 | `variants/parwa/agents/chat_agent.py` | base_chat_agent.py (Wk9) | Test: PARWA chat responds |
| 8 | `variants/parwa/agents/sms_agent.py` | base_sms_agent.py (Wk9) | Test: PARWA SMS sends |
| 9 | `variants/parwa/agents/voice_agent.py` | base_voice_agent.py (Wk9) | Test: PARWA voice handles call |
| 10 | `variants/parwa/agents/ticket_agent.py` | base_ticket_agent.py (Wk9) | Test: PARWA ticket created |
| 11 | `variants/parwa/agents/escalation_agent.py` | base_escalation_agent.py (Wk9) | Test: PARWA escalates correctly |
| 12 | `variants/parwa/agents/refund_agent.py` | base_refund_agent.py (Wk9) | Test: PARWA refund → APPROVE/REVIEW/DENY |

### BUILDER 3 (Day 3) — PARWA Unique Agents + Tools

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/parwa/agents/learning_agent.py` | base_agent.py, training_data model (Wks 3-9) | Test: negative_reward created on rejection |
| 2 | `variants/parwa/agents/safety_agent.py` | ai_safety.py, base_agent.py (Wks 1-9) | Test: competitor mention blocked |
| 3 | `variants/parwa/tools/__init__.py` | None | N/A |
| 4 | `variants/parwa/tools/knowledge_update.py` | kb_manager.py (Wk5) | Test: KB updated correctly |
| 5 | `variants/parwa/tools/refund_recommendation_tools.py` | stripe_client.py (Wk7) | Test: APPROVE/REVIEW/DENY with reasoning |
| 6 | `variants/parwa/tools/safety_tools.py` | ai_safety.py (Wk1) | Test: safety check runs |

### BUILDER 4 (Day 4) — PARWA Workflows + Tasks

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/parwa/workflows/__init__.py` | None | N/A |
| 2 | `variants/parwa/workflows/refund_recommendation.py` | PARWA agents (D2-D3) | Test: recommendation includes reasoning |
| 3 | `variants/parwa/workflows/knowledge_update.py` | PARWA agents (D2-D3) | Test: KB updated after resolution |
| 4 | `variants/parwa/workflows/safety_workflow.py` | PARWA agents (D2-D3) | Test: safety check runs before response |
| 5 | `variants/parwa/tasks/__init__.py` | None | N/A |
| 6 | `variants/parwa/tasks/recommend_refund.py` | PARWA agents (D2-D3) | Test: APPROVE/REVIEW/DENY returned |
| 7 | `variants/parwa/tasks/update_knowledge.py` | PARWA agents (D2-D3) | Test: KB entry added |
| 8 | `variants/parwa/tasks/compliance_check.py` | compliance.py (Wk1) | Test: compliance check runs |

### BUILDER 5 (Day 5) — PARWA Tests + Manager Time

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/unit/test_parwa_agents.py` | All PARWA agents (D2-D3) | PUSH ONLY AFTER THIS PASSES |
| 2 | `tests/unit/test_parwa_workflows.py` | PARWA workflows (D4) | PUSH ONLY AFTER THIS PASSES |
| 3 | `backend/services/manager_time_calculator.py` | pricing_optimizer.py (Wk1) | Test: manager time formula correct |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_week10_parwa_variant.py -v`

**Pass Criteria:**
- PARWA recommendation: includes APPROVE/REVIEW/DENY with full reasoning
- PARWA learning agent: negative_reward record created on rejection
- PARWA safety agent: competitor mention blocked
- Mini still works correctly alongside PARWA (no conflicts)
- Manager time calculator: 1x PARWA shows 0.5 hrs/day correctly

---

## WEEK 11 — PARWA High Variant

**Goal:** Build PARWA High variant and verify all 3 variants coexist

### BUILDER 1 (Day 1) — PARWA High Config + Core Advanced Agents

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/parwa_high/__init__.py` | None | N/A |
| 2 | `variants/parwa_high/config.py` | config.py (Wk1) | Test: High config loads |
| 3 | `variants/parwa_high/anti_arbitrage_config.py` | pricing_optimizer.py (Wk1) | Test: High anti-arbitrage correct |
| 4 | `variants/parwa_high/agents/__init__.py` | None | N/A |
| 5 | `variants/parwa_high/agents/video_agent.py` | base_agent.py (Wk9) | Test: video agent initialises |
| 6 | `variants/parwa_high/agents/analytics_agent.py` | base_agent.py (Wk9) | Test: analytics agent runs |
| 7 | `variants/parwa_high/agents/coordination_agent.py` | base_agent.py (Wk9) | Test: coordination agent manages 5 concurrent |

### BUILDER 2 (Day 2) — PARWA High Customer Success + Compliance Agents

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/parwa_high/agents/customer_success_agent.py` | base_agent.py (Wk9) | Test: churn prediction contains risk score |
| 2 | `variants/parwa_high/agents/sla_agent.py` | base_agent.py, sla_calculator.py (Wks 7-9) | Test: SLA breach detected |
| 3 | `variants/parwa_high/agents/compliance_agent.py` | base_agent.py, healthcare_guard.py (Wks 7-9) | Test: HIPAA compliance enforced |
| 4 | `variants/parwa_high/agents/learning_agent.py` | base_agent.py (Wk9) | Test: learning records training data |
| 5 | `variants/parwa_high/agents/safety_agent.py` | base_agent.py (Wk9) | Test: safety check blocks unsafe responses |

### BUILDER 3 (Day 3) — PARWA High Tools + Workflows

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/parwa_high/tools/__init__.py` | None | N/A |
| 2 | `variants/parwa_high/tools/analytics_engine.py` | analytics_service.py (Wk4) | Test: insights generated |
| 3 | `variants/parwa_high/tools/team_coordination.py` | base_agent.py (Wk9) | Test: team coordinated correctly |
| 4 | `variants/parwa_high/tools/customer_success_tools.py` | base_agent.py (Wk9) | Test: success tools run |
| 5 | `variants/parwa_high/workflows/__init__.py` | None | N/A |
| 6 | `variants/parwa_high/workflows/video_support.py` | High agents (D1-D2) | Test: video workflow starts |
| 7 | `variants/parwa_high/workflows/analytics.py` | High agents (D1-D2) | Test: analytics workflow runs |
| 8 | `variants/parwa_high/workflows/coordination.py` | High agents (D1-D2) | Test: coordination workflow manages load |
| 9 | `variants/parwa_high/workflows/customer_success.py` | High agents (D1-D2) | Test: success workflow runs |

### BUILDER 4 (Day 4) — PARWA High Tasks + DB Migration

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/parwa_high/tasks/__init__.py` | None | N/A |
| 2 | `variants/parwa_high/tasks/video_call.py` | High agents (D1-D2) | Test: video call task runs |
| 3 | `variants/parwa_high/tasks/generate_insights.py` | High agents (D1-D2) | Test: insights generated with risk score |
| 4 | `variants/parwa_high/tasks/coordinate_teams.py` | High agents (D1-D2) | Test: teams coordinated |
| 5 | `variants/parwa_high/tasks/customer_success.py` | High agents (D1-D2) | Test: success tasks complete |
| 6 | `tests/unit/test_parwa_high_agents.py` | High agents (D1-D2) | PUSH ONLY AFTER THIS PASSES |
| 7 | `tests/unit/test_parwa_high_workflows.py` | High workflows (D3) | PUSH ONLY AFTER THIS PASSES |
| 8 | `database/migrations/versions/006_multi_region.py` | 001_initial_schema.py (Wk2) | Test: migration runs without errors |

### BUILDER 5 (Day 5) — All 3 Variants Coexistence + BDD Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_week11_parwa_high.py` | All 3 variants (Wks 9-11) | Test: same ticket through all 3 variants |
| 2 | `tests/integration/test_full_system.py` | All variants (Wks 9-11) | Skeleton full system test |
| 3 | `tests/bdd/test_mini_scenarios.py` | Mini variant (Wk9) | BDD: all Mini scenarios pass |
| 4 | `tests/bdd/test_parwa_scenarios.py` | PARWA variant (Wk10) | BDD: all PARWA scenarios pass |
| 5 | `tests/bdd/test_parwa_high_scenarios.py` | PARWA High (Wk11 D1-D4) | BDD: all High scenarios pass |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_week11_parwa_high.py -v`

**Pass Criteria:**
- All 3 variants import simultaneously with zero conflicts
- PARWA High: churn prediction output contains risk score
- PARWA High: video agent initialises correctly
- Same ticket through all 3: Mini collects, PARWA recommends, High executes on approval
- BDD scenarios: all pass for all 3 variants
- DB migration 006: runs without errors

---

## WEEK 12 — Backend Services Complete

**Goal:** Build all backend services: approval, escalation, industry configs, Jarvis, webhooks, E2E tests

### BUILDER 1 (Day 1) — Industry Configs + Jarvis Commands

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `backend/core/__init__.py` | None | N/A |
| 2 | `backend/core/jarvis_commands.py` | cache.py, security.py (Wks 1-3) | Test: pause_refunds Redis key set within 500ms |
| 3 | `backend/core/industry_configs/__init__.py` | None | N/A |
| 4 | `backend/core/industry_configs/ecommerce.py` | config.py (Wk1) | Test: ecommerce config loads |
| 5 | `backend/core/industry_configs/saas.py` | config.py (Wk1) | Test: saas config loads |
| 6 | `backend/core/industry_configs/healthcare.py` | config.py, healthcare_guard.py (Wks 1-7) | Test: healthcare config + BAA check |
| 7 | `backend/core/industry_configs/logistics.py` | config.py (Wk1) | Test: logistics config loads |
| 8 | `backend/api/incoming_calls.py` | config.py (Wk1) | Test: call answered in <6s, never IVR-only |
| 9 | `backend/services/voice_handler.py` | incoming_calls.py (same day) | Test: 5-step call flow runs |

### BUILDER 2 (Day 2) — Approval + Escalation Services

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `backend/services/__init__.py` | None | N/A |
| 2 | `backend/services/approval_service.py` | support_ticket model, stripe_client.py (Wks 3-7) | Test: pending_approval created, Stripe NOT called |
| 3 | `backend/services/escalation_ladder.py` | approval_service.py (same day) | Test: 4-phase escalation fires at correct hours |
| 4 | `backend/services/escalation_service.py` | support_ticket model (Wk3) | Test: escalation service runs |
| 5 | `backend/services/license_service.py` | license model (Wk3) | Test: license checked correctly |
| 6 | `backend/services/sla_service.py` | sla_breach model (Wk3) | Test: SLA breach detected |

### BUILDER 3 (Day 3) — Webhook Handlers + Automation + NLP

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `backend/api/webhooks/twilio.py` | hmac_verification.py (Wk3) | Test: bad HMAC returns 401 |
| 2 | `backend/api/automation.py` | all agents (Wks 9-11) | Test: automation endpoint works |
| 3 | `backend/services/manager_time_calculator.py` | pricing_optimizer.py (Wk1) | Test: formula correct |
| 4 | `backend/services/non_financial_undo.py` | audit_trail.py (Wk2), Redis (Wk1) | Test: non-money action undone, logged |
| 5 | `backend/nlp/__init__.py` | None | N/A |
| 6 | `backend/nlp/command_parser.py` | config.py (Wk1) | Test: Add 2 Mini → {action:provision,count:2,type:mini} |

### BUILDER 4 (Day 4) — E2E Test Files

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/e2e/__init__.py` | None | N/A |
| 2 | `tests/e2e/test_onboarding_flow.py` | All backend services (Wks 4-12) | E2E: signup→onboarding→live |
| 3 | `tests/e2e/test_refund_workflow.py` | approval_service.py (D2) | E2E: Stripe called EXACTLY once after approval |
| 4 | `tests/e2e/test_jarvis_commands.py` | jarvis_commands.py (D1) | E2E: pause_refunds Redis key within 500ms |
| 5 | `tests/e2e/test_stuck_ticket_escalation.py` | escalation_service.py (D2) | E2E: 4-phase fires at 24h/48h/72h thresholds |

### BUILDER 5 (Day 5) — More E2E + NLP Provisioner + Voice Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/e2e/test_agent_lightning.py` | training_data model (Wk3) | E2E: full training cycle |
| 2 | `tests/e2e/test_gdpr_compliance.py` | gdpr_engine.py (Wk7) | E2E: PII anonymised, row preserved |
| 3 | `backend/nlp/provisioner.py` | command_parser.py (D3) | Test: agents spun up, billing updated |
| 4 | `backend/nlp/intent_classifier.py` | command_parser.py (D3) | Test: intent classified correctly |
| 5 | `tests/voice/__init__.py` | None | N/A |
| 6 | `tests/voice/test_incoming_calls.py` | incoming_calls.py, voice_handler.py (D1) | Test: answer <6s, recording disclosure fires |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/e2e/test_refund_workflow.py tests/e2e/test_jarvis_commands.py tests/integration/test_week12_backend.py -v`

**Pass Criteria:**
- Refund E2E: Stripe called exactly once — after approval, NEVER before
- Audit trail: hash chain validates after approval event
- Stuck ticket: 4-phase escalation fires at exact 24h/48h/72h thresholds
- Jarvis: pause_refunds Redis key set within 500ms
- GDPR: export complete, deletion anonymises PII, row preserved
- Incoming calls: answered in <6 seconds, never IVR-only

---

## WEEK 13 — Agent Lightning Training System

**Goal:** Build Agent Lightning training system and all background workers

### BUILDER 1 (Day 1) — Data Export + Model Registry

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `agent_lightning/__init__.py` | None | N/A |
| 2 | `agent_lightning/data/__init__.py` | None | N/A |
| 3 | `agent_lightning/data/export_mistakes.py` | training_data model (Wk3) | Test: mistakes exported in correct format |
| 4 | `agent_lightning/data/export_approvals.py` | training_data model (Wk3) | Test: approvals exported |
| 5 | `agent_lightning/data/dataset_builder.py` | export_mistakes.py, export_approvals.py (same day) | Test: JSONL dataset built correctly |
| 6 | `agent_lightning/deployment/__init__.py` | None | N/A |
| 7 | `agent_lightning/deployment/model_registry.py` | config.py (Wk1) | Test: model version registered |

### BUILDER 2 (Day 2) — Training Pipeline

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `agent_lightning/training/__init__.py` | None | N/A |
| 2 | `agent_lightning/training/trainer.py` | config.py (Wk1) — uses Unsloth+Colab FREE | Test: trainer initialises |
| 3 | `agent_lightning/training/unsloth_optimizer.py` | trainer.py (same day) | Test: Unsloth optimiser applies |
| 4 | `agent_lightning/deployment/deploy_model.py` | model_registry.py (D1) | Test: model deployed to registry |
| 5 | `agent_lightning/deployment/rollback.py` | model_registry.py (D1) | Test: rollback restores previous version |

### BUILDER 3 (Day 3) — Fine Tune + Validation + Monitoring

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `agent_lightning/training/fine_tune.py` | trainer.py, unsloth_optimizer.py (D2) | Test: fine tune runs on test dataset |
| 2 | `agent_lightning/training/validate.py` | trainer.py (D2) | Test: blocks deployment at 89%, allows at 91% |
| 3 | `agent_lightning/monitoring/__init__.py` | None | N/A |
| 4 | `agent_lightning/monitoring/drift_detector.py` | model_registry.py (D1) | Test: drift detected after model change |
| 5 | `agent_lightning/monitoring/accuracy_tracker.py` | model_registry.py (D1) | Test: accuracy tracked per category |

### BUILDER 4 (Day 4) — Background Workers

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `workers/__init__.py` | None | N/A |
| 2 | `workers/worker.py` | config.py, message_queue.py (Wks 1-2) | Test: ARQ worker registers |
| 3 | `workers/batch_approval.py` | escalation_service.py (Wk12) | Test: batch processes correctly |
| 4 | `workers/training_job.py` | fine_tune.py (D3) | Test: training job triggered |
| 5 | `workers/cleanup.py` | gdpr_engine.py (Wk7) | Test: cleanup runs, PII anonymised |
| 6 | `backend/services/burst_mode.py` | billing_service.py (Wk4), feature_flags/ (Wk1) | Test: burst mode activates, billing updated |

### BUILDER 5 (Day 5) — Remaining Workers + Quality Coach

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `workers/recall_handler.py` | cache.py (Wk2) | Test: recall stops non-money actions |
| 2 | `workers/proactive_outreach.py` | notification_service.py (Wk4) | Test: outreach sent proactively |
| 3 | `workers/report_generator.py` | analytics_service.py (Wk4) | Test: report generated |
| 4 | `workers/kb_indexer.py` | rag_pipeline.py (Wk5) | Test: KB indexed correctly |
| 5 | `backend/quality_coach/__init__.py` | None | N/A |
| 6 | `backend/quality_coach/analyzer.py` | config.py (Wk1) | Test: scores accuracy/empathy/efficiency |
| 7 | `backend/quality_coach/reporter.py` | analyzer.py (same day) | Test: weekly report generated |
| 8 | `backend/quality_coach/notifier.py` | analyzer.py (same day) | Test: real-time alert fires |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/e2e/test_agent_lightning.py tests/integration/test_week13_workers.py -v`

**Pass Criteria:**
- Dataset builder: exports correct JSONL format with 50+ mistakes
- validate.py: blocks deployment at <90% accuracy
- validate.py: allows deployment at 91%+ accuracy
- New model version registered in model_registry after deployment
- All 8 workers start and register with ARQ without errors
- Burst mode: activates instantly, billing updated, auto-expires

---

## WEEK 14 — Monitoring + Phase 1-3 Validation

**Goal:** Build all monitoring dashboards, alerts, performance tests, and complete Phase 1-3 validation

### BUILDER 1 (Day 1) — Grafana Dashboards

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `monitoring/grafana-dashboards/__init__.py` | None | N/A |
| 2 | `monitoring/grafana-dashboards/main-dashboard.json` | None — config only | Verify: loads in Grafana without errors |
| 3 | `monitoring/grafana-dashboards/mcp-dashboard.json` | None — config only | Verify: MCP metrics shown |
| 4 | `monitoring/grafana-dashboards/compliance-dashboard.json` | None — config only | Verify: compliance metrics shown |
| 5 | `monitoring/grafana-dashboards/sla-dashboard.json` | None — config only | Verify: SLA metrics shown |
| 6 | `monitoring/grafana-dashboards/quality.json` | None — config only | Verify: quality coach metrics shown |

### BUILDER 2 (Day 2) — Alert Rules + Logging Config

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `monitoring/alerts.yml` | prometheus.yml (Wk8) | Test: all 6 alerts fire on simulated conditions |
| 2 | `monitoring/grafana-config.yml` | None — config only | Verify: Grafana config valid |
| 3 | `monitoring/logs/__init__.py` | None | N/A |
| 4 | `monitoring/logs/structured-logging-config.yml` | logger.py (Wk1) | Verify: logs in JSON format |
| 5 | `docs/runbook.md` | None | Doc only |

### BUILDER 3 (Day 3) — Performance + BDD + Integration Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/performance/__init__.py` | None | N/A |
| 2 | `tests/performance/test_load.py` | All backend APIs (Wks 4-12) | Test: P95 <500ms at 50 concurrent users |
| 3 | `tests/ui/__init__.py` | None | N/A |
| 4 | `tests/ui/test_approval_queue.py` | None — UI test | Test: approval queue renders |
| 5 | `tests/ui/test_roi_calculator.py` | None — UI test | Test: ROI calculator correct |
| 6 | `tests/ui/test_jarvis_terminal.py` | None — UI test | Test: Jarvis terminal works |
| 7 | `tests/bdd/__init__.py` | None | N/A |
| 8 | `tests/bdd/test_mini_scenarios.py` (complete) | Mini variant (Wk9) | BDD: complete scenario suite |
| 9 | `tests/integration/test_week4_backend_api.py` | All APIs (Wks 4-12) | Integration: full API layer tested |

### BUILDER 4 (Day 4) — Industry-Specific Integration Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_ecommerce_industry.py` | ecommerce config (Wk12) | Integration: ecommerce flow works |
| 2 | `tests/integration/test_saas_industry.py` | saas config (Wk12) | Integration: SaaS flow works |
| 3 | `tests/integration/test_healthcare_industry.py` | healthcare config (Wk12) | Integration: HIPAA enforced |
| 4 | `tests/integration/test_logistics_industry.py` | logistics config (Wk12) | Integration: logistics flow works |

### BUILDER 5 (Day 5) — Full System Test + Dockerfiles + PROJECT_STATE

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_full_system.py` (complete) | Everything (Wks 1-13) | Full system: all 3 variants + backend + workers |
| 2 | `infra/docker/frontend.Dockerfile` | None — Docker config | Test: builds under 500MB |
| 3 | `docker-compose.prod.yml` (update) | All Dockerfiles | Test: all services start healthy |
| 4 | `PROJECT_STATE.md` (Phase 1-3 complete marker) | None | State: marks Phases 1-3 complete |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_full_system.py tests/performance/test_load.py -v`

**Pass Criteria:**
- pytest tests/integration/test_full_system.py: all tests pass
- P95 latency <500ms at 50 concurrent users (Locust)
- All 6 monitoring alerts fire correctly on simulated conditions
- All 4 industry configurations work without errors
- docker-compose.prod.yml starts all services healthy
- BDD: all Mini scenarios pass completely
- Safety: guardrails.py blocks hallucination, competitor mention, PII

---

# PHASE 4: FRONTEND FOUNDATION (Weeks 15-18)

---

## WEEK 15 — Frontend Foundation

**Goal:** Build Next.js frontend foundation

### BUILDER 1 (Day 1) — Next.js Config → Layout → Landing Page → UI Primitives

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/next.config.js` | None | Verify: Next.js config valid |
| 2 | `frontend/tailwind.config.js` | None | Verify: Tailwind config valid |
| 3 | `frontend/app/layout.tsx` | None | Test: layout renders |
| 4 | `frontend/app/page.tsx` | None | Test: landing page renders |
| 5 | `frontend/components/ui/button.tsx` | None | Test: button renders |
| 6 | `frontend/components/ui/input.tsx` | None | Test: input renders |
| 7 | `frontend/components/ui/card.tsx` | None | Test: card renders |

### BUILDER 2 (Day 2) — Common UI + Auth Pages

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/components/common/header.tsx` | None | Test: header renders |
| 2 | `frontend/components/common/sidebar.tsx` | None | Test: sidebar renders |
| 3 | `frontend/app/auth/login/page.tsx` | None | Test: login page renders |
| 4 | `frontend/app/auth/signup/page.tsx` | None | Test: signup page renders |
| 5 | `frontend/app/auth/forgot-password/page.tsx` | None | Test: forgot password renders |

### BUILDER 3 (Day 3) — Variant Cards

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/components/pricing/mini-card.tsx` | None | Test: Mini card renders |
| 2 | `frontend/components/pricing/parwa-card.tsx` | None | Test: PARWA card renders |
| 3 | `frontend/components/pricing/parwa-high-card.tsx` | None | Test: PARWA High card renders |
| 4 | `frontend/components/pricing/comparison-table.tsx` | All cards | Test: comparison renders |

### BUILDER 4 (Day 4) — Stores + API Service

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/stores/auth-store.ts` | None | Test: auth store initialises |
| 2 | `frontend/stores/tenant-store.ts` | None | Test: tenant store initialises |
| 3 | `frontend/stores/approval-store.ts` | None | Test: approval store initialises |
| 4 | `frontend/lib/api-client.ts` | None | Test: API client works |
| 5 | `frontend/lib/auth.ts` | None | Test: auth lib works |

### BUILDER 5 (Day 5) — Onboarding Components

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/components/onboarding/step-1.tsx` | None | Test: step 1 renders |
| 2 | `frontend/components/onboarding/step-2.tsx` | None | Test: step 2 renders |
| 3 | `frontend/components/onboarding/step-3.tsx` | None | Test: step 3 renders |
| 4 | `frontend/components/onboarding/step-4.tsx` | None | Test: step 4 renders |
| 5 | `frontend/components/onboarding/step-5.tsx` | None | Test: step 5 renders |
| 6 | `frontend/components/onboarding/wizard.tsx` | All steps | Test: wizard flow works |

### TESTER AGENT (Day 6)

**Command:** `npm run test -- tests/ui/ && pytest tests/integration/test_week15_frontend.py`

**Pass Criteria:**
- Next.js dev server starts without errors
- All 3 variant cards render correctly
- Auth pages render and validate
- Onboarding wizard 5-step flow works
- All Zustand stores initialise

---

## WEEK 16 — Dashboard Pages + Hooks

**Goal:** Build all dashboard pages and hooks

### BUILDER 1 (Day 1) — Dashboard Layout + Home Page

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/app/dashboard/layout.tsx` | None | Test: dashboard layout renders |
| 2 | `frontend/app/dashboard/page.tsx` | None | Test: home page loads real API data |
| 3 | `frontend/components/dashboard/stats-card.tsx` | None | Test: stats card renders |

### BUILDER 2 (Day 2) — Tickets + Approvals + Agents + Analytics Pages

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/app/dashboard/tickets/page.tsx` | None | Test: tickets page renders |
| 2 | `frontend/app/dashboard/approvals/page.tsx` | None | Test: approvals queue renders and approve action works |
| 3 | `frontend/app/dashboard/agents/page.tsx` | None | Test: agents page renders |
| 4 | `frontend/app/dashboard/analytics/page.tsx` | None | Test: analytics page renders |

### BUILDER 3 (Day 3) — Dashboard Components

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/components/dashboard/ticket-list.tsx` | None | Test: ticket list renders |
| 2 | `frontend/components/dashboard/approval-queue.tsx` | None | Test: approval queue renders |
| 3 | `frontend/components/dashboard/jarvis-terminal.tsx` | None | Test: Jarvis terminal streams response |
| 4 | `frontend/components/dashboard/agent-status.tsx` | None | Test: agent status renders |

### BUILDER 4 (Day 4) — All Hooks

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/hooks/use-auth.ts` | None | Test: use-auth hook works |
| 2 | `frontend/hooks/use-approvals.ts` | None | Test: use-approvals hook updates store |
| 3 | `frontend/hooks/use-tickets.ts` | None | Test: use-tickets hook works |
| 4 | `frontend/hooks/use-analytics.ts` | None | Test: use-analytics hook works |
| 5 | `frontend/hooks/use-jarvis.ts` | None | Test: use-jarvis hook works |

### BUILDER 5 (Day 5) — Settings Pages

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/app/dashboard/settings/page.tsx` | None | Test: settings page renders |
| 2 | `frontend/app/dashboard/settings/profile/page.tsx` | None | Test: profile settings renders |
| 3 | `frontend/app/dashboard/settings/billing/page.tsx` | None | Test: billing settings renders |
| 4 | `frontend/app/dashboard/settings/team/page.tsx` | None | Test: team settings renders |
| 5 | `frontend/app/dashboard/settings/integrations/page.tsx` | None | Test: integrations settings renders |

### TESTER AGENT (Day 6)

**Command:** `npm run test && pytest tests/integration/test_week16_dashboard.py`

**Pass Criteria:**
- Dashboard home loads real API data
- Approvals queue renders and approve action works
- Jarvis terminal streams response
- All 5 hooks update stores correctly

---

## WEEK 17 — Onboarding + Analytics + Frontend Wiring

**Goal:** Complete onboarding, analytics, and frontend-backend wiring

### BUILDER 1 (Day 1) — Onboarding + Pricing + Analytics Components

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/components/onboarding/knowledge-upload.tsx` | None | Test: KB upload works |
| 2 | `frontend/components/onboarding/industry-select.tsx` | None | Test: industry select works |
| 3 | `frontend/components/pricing/calculator.tsx` | None | Test: pricing calculator works |
| 4 | `frontend/components/analytics/chart.tsx` | None | Test: chart renders |

### BUILDER 2 (Day 2) — Settings Sub-Pages

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/app/dashboard/settings/notifications/page.tsx` | None | Test: notification settings renders |
| 2 | `frontend/app/dashboard/settings/security/page.tsx` | None | Test: security settings renders |
| 3 | `frontend/app/dashboard/settings/api-keys/page.tsx` | None | Test: API keys settings renders |

### BUILDER 3 (Day 3) — Frontend Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/ui/test_onboarding_flow.py` | All onboarding components | Test: full onboarding flow |
| 2 | `tests/ui/test_dashboard_flow.py` | All dashboard components | Test: full dashboard flow |
| 3 | `tests/ui/test_settings_flow.py` | All settings components | Test: full settings flow |

### BUILDER 4 (Day 4) — Frontend → Backend Service Wiring

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/lib/services/approval-service.ts` | API client | Test: approval service works |
| 2 | `frontend/lib/services/ticket-service.ts` | API client | Test: ticket service works |
| 3 | `frontend/lib/services/analytics-service.ts` | API client | Test: analytics service works |
| 4 | `frontend/lib/services/jarvis-service.ts` | API client | Test: Jarvis service works |

### BUILDER 5 (Day 5) — E2E Frontend Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/e2e/test_frontend_full_flow.py` | All frontend + backend | Test: full UI flow |
| 2 | `tests/e2e/test_ui_approval_flow.py` | Approval UI + backend | Test: approve refund through UI |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/e2e/test_frontend_full_flow.py`

**Pass Criteria:**
- Full UI: login→onboarding→dashboard works
- Approve refund through UI: Stripe called exactly once
- Analytics page loads real backend data
- Lighthouse score >80

---

## WEEK 18 — Production Hardening + Kubernetes

**Goal:** Production hardening and Kubernetes deployment

### BUILDER 1 (Day 1) — Full Test Suite

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/reports/coverage-report.py` | All tests | Generate coverage report |
| 2 | Run full test suite | All tests | All tests pass |

### BUILDER 2 (Day 2) — Security + Performance Scans

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `security/owasp-scan.py` | None | OWASP: all 10 checks pass |
| 2 | `security/cve-scan.py` | All Docker images | Zero critical CVEs |
| 3 | `tests/security/rls-isolation-test.py` | All DB | RLS: 10 cross-tenant isolation tests |

### BUILDER 3 (Day 3) — Prod Docker Builds

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `infra/docker/backend.Dockerfile` (prod) | None | Test: builds under 500MB |
| 2 | `infra/docker/worker.Dockerfile` (prod) | None | Test: builds under 300MB |
| 3 | `infra/docker/mcp.Dockerfile` (prod) | None | Test: builds under 300MB |

### BUILDER 4 (Day 4) — K8s Manifests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `infra/k8s/namespace.yaml` | None | Verify: namespace valid |
| 2 | `infra/k8s/backend-deployment.yaml` | None | Verify: deployment valid |
| 3 | `infra/k8s/frontend-deployment.yaml` | None | Verify: deployment valid |
| 4 | `infra/k8s/worker-deployment.yaml` | None | Verify: deployment valid |
| 5 | `infra/k8s/ingress.yaml` | None | Verify: ingress valid |

### BUILDER 5 (Day 5) — Final Docs

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `docs/deployment-guide.md` | None | Doc only |
| 2 | `docs/operations-runbook.md` | None | Doc only |
| 3 | `PROJECT_STATE.md` (Phase 4 complete) | None | State: marks Phase 4 complete |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/ && snyk test && locust -f tests/performance/test_load.py --headless -u 100`

**Pass Criteria:**
- pytest tests/: 100% pass rate
- Zero critical CVEs on all Docker images
- OWASP: all 10 checks pass
- RLS: 10 cross-tenant isolation tests all return 0 rows
- P95 <500ms at 100 concurrent users
- Full client journey: signup→onboarding→ticket→approval works

---

# PHASE 5: FIRST CLIENTS (Weeks 19-20)

---

## WEEK 19 — First Client Onboarding + Real Validation

**Goal:** Onboard first real client and validate in production

### BUILDER 1 (Day 1) — Client Setup Files

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `clients/client_001/config.py` | config.py (Wk1) | Test: client config loads |
| 2 | `clients/client_001/knowledge_base/` | kb_manager.py (Wk5) | Test: KB ingested |
| 3 | `monitoring/client_001_dashboard.json` | None | Verify: dashboard loads |

### BUILDER 2 (Day 2) — Shadow Mode Validation

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_shadow_mode.py` | All systems | Test: shadow mode works |
| 2 | `scripts/validate_shadow.py` | None | Test: validation runs |

### BUILDER 3 (Day 3) — Bug Fixes from Real Usage

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Bug fixes as needed | Real usage | All tests still pass |

### BUILDER 4 (Day 4) — Optimisation

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Performance optimisations | Real usage | P95 <500ms on real data |

### BUILDER 5 (Day 5) — Reports

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `reports/client_001_week1.md` | None | Report: baseline metrics |
| 2 | `tests/performance/baseline_metrics.py` | None | Test: baseline established |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_shadow_mode.py tests/performance/baseline_metrics.py`

**Pass Criteria:**
- 50 tickets processed in Shadow Mode without critical errors
- Accuracy baseline established (target >72%)
- P95 <500ms on real client data
- No cross-tenant data leaks in real usage

---

## WEEK 20 — Second Client + Agent Lightning First Run

**Goal:** Onboard second client and run first Agent Lightning training

### BUILDER 1 (Day 1) — Client 2 Setup

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `clients/client_002/config.py` | config.py (Wk1) | Test: client config loads |
| 2 | `clients/client_002/knowledge_base/` | kb_manager.py (Wk5) | Test: KB ingested |

### BUILDER 2 (Day 2) — Agent Lightning First Real Training

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Run export_mistakes.py | training_data | Test: mistakes exported |
| 2 | Run fine_tune.py | export_mistakes | Test: fine tune runs |
| 3 | Run validate.py | fine_tune | Test: validation passes |
| 4 | Run deploy_model.py | validate | Test: model deployed |

### BUILDER 3 (Day 3) — Post-Training Validation

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_post_training.py` | New model | Test: new model works |
| 2 | `agent_lightning/monitoring/regression_tests.py` | New model | Test: no regressions |

### BUILDER 4 (Day 4) — Scaling Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_multi_client_isolation.py` | All clients | Test: 2-client isolation |

### BUILDER 5 (Day 5) — Reports

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `reports/agent_lightning_week1.md` | None | Report: accuracy improved |
| 2 | `reports/client_002_week1.md` | None | Report: client 2 baseline |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_multi_client_isolation.py && pytest tests/`

**Pass Criteria:**
- 2-client cross-tenant isolation: 0 data leaks in 20 tests
- Agent Lightning: accuracy improved ≥3% from baseline
- New model passes all regression tests
- P95 <500ms at 100 concurrent users

---

# PHASE 6: SCALE (Weeks 21-22)

---

## WEEK 21 — Clients 3-5 + Collective Intelligence

**Goal:** Scale to 5 clients with collective intelligence improvements

### BUILDER 1 (Day 1) — Clients 3-5 Configs

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `clients/client_003/config.py` | config.py (Wk1) | Test: config loads |
| 2 | `clients/client_004/config.py` | config.py (Wk1) | Test: config loads |
| 3 | `clients/client_005/config.py` | config.py (Wk1) | Test: config loads |
| 4 | All KB directories | kb_manager.py (Wk5) | Test: KBs ingested |

### BUILDER 2 (Day 2) — Agent Lightning Week 3 Run

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Run full training cycle | All training data | Test: accuracy ≥77% |

### BUILDER 3 (Day 3) — Collective Intelligence Improvements

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `agent_lightning/collective/pattern_extractor.py` | None | Test: patterns extracted |
| 2 | `agent_lightning/collective/logic_transfer.py` | pattern_extractor | Test: logic transferred |
| 3 | `agent_lightning/collective/privacy_filter.py` | None | Test: no PII in transfer |

### BUILDER 4 (Day 4) — Performance Optimisation

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `shared/utils/cache_optimisation.py` | cache.py (Wk2) | Test: cache hit >70% |
| 2 | `shared/smart_router/tier_optimisation.py` | router.py (Wk5) | Test: Light tier >88% |

### BUILDER 5 (Day 5) — New Industry Verticals

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `backend/core/industry_configs/financial_services.py` | config.py (Wk1) | Test: FS config loads |
| 2 | `tests/integration/test_financial_services.py` | FS config | Test: FS flow works |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_5_client_isolation.py`

**Pass Criteria:**
- 5-client isolation: 0 data leaks across 50 cross-tenant tests
- Agent Lightning accuracy ≥77%
- Redis cache hit rate >70%
- Light tier >88% of queries

---

## WEEK 22 — Clients 6-10 + 85% Accuracy Milestone

**Goal:** Scale to 10 clients with 85% accuracy

### BUILDER 1 (Day 1) — Clients 6-10 Configs

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `clients/client_006/` through `clients/client_010/` | config.py (Wk1) | Test: all configs load |

### BUILDER 2 (Day 2) — Agent Lightning Week 6 Run (Target 85%)

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Run full training cycle with 85% target | All training data | Test: accuracy ≥85% |

### BUILDER 3 (Day 3) — Platform Hardening Scans

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Security re-scan | All systems | Zero critical issues |
| 2 | Performance re-scan | All systems | P95 <300ms |

### BUILDER 4 (Day 4) — 10-Client Performance Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_10_client_isolation.py` | All clients | Test: 10-client isolation |
| 2 | `tests/performance/test_10_client_load.py` | All clients | Test: 500 concurrent users |

### BUILDER 5 (Day 5) — Milestone Docs

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `docs/milestones/85_percent_accuracy.md` | None | Milestone documentation |
| 2 | `PROJECT_STATE.md` (Phase 6 complete) | None | State update |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_10_client_isolation.py && locust -u 500`

**Pass Criteria:**
- 10-client isolation: 0 data leaks in 100 tests
- Agent Lightning ≥85% accuracy
- 500 concurrent users P95 <500ms
- Horizontal scaling: 2nd backend pod handles traffic

---

# PHASE 7: POLISH & ADVANCED FEATURES (Weeks 23-27)

---

## WEEK 23 — Frontend Polish (A11y + Mobile + Dark Mode)

### BUILDER 1 (Day 1) — Accessibility + Mobile + Dark Mode

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/styles/dark-mode.css` | None | Test: dark mode works |
| 2 | `frontend/styles/mobile.css` | None | Test: mobile responsive |
| 3 | `frontend/lib/accessibility.ts` | None | Test: axe-core passes |

### BUILDER 2 (Day 2) — Loading/Empty States

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/components/common/loading.tsx` | None | Test: loading renders |
| 2 | `frontend/components/common/empty-state.tsx` | None | Test: empty state renders |
| 3 | `frontend/components/common/toast.tsx` | None | Test: toast renders |
| 4 | `frontend/components/common/form-validation.tsx` | None | Test: validation works |

### BUILDER 3 (Day 3) — Dashboard Component Improvements

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Dashboard improvements | Real usage | All tests pass |

### BUILDER 4 (Day 4) — Performance Optimisation

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Frontend bundle optimisation | All frontend | Lighthouse >90 |

### BUILDER 5 (Day 5) — Frontend Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | All frontend tests | All frontend | All tests pass |

### TESTER AGENT (Day 6)

**Command:** `npm run test && lighthouse --output json`

**Pass Criteria:**
- Lighthouse score >90 on all key pages
- axe-core: zero accessibility violations
- Responsive: correct at mobile/tablet/desktop
- Dark mode: all pages switch correctly

---

## WEEK 24 — Client Success Tooling

### BUILDER 1 (Day 1) — Success Services

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `backend/services/health_score_service.py` | None | Test: health score calculates |
| 2 | `backend/services/churn_prediction_service.py` | None | Test: churn alert fires |
| 3 | `backend/services/nps_service.py` | None | Test: NPS survey sends |
| 4 | `backend/services/success_metrics_service.py` | None | Test: metrics calculate |

### BUILDER 2 (Day 2) — API Endpoints

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `backend/api/health_score.py` | health_score_service | Test: API works |
| 2 | `backend/api/churn.py` | churn_service | Test: API works |
| 3 | `backend/api/nps.py` | nps_service | Test: API works |

### BUILDER 3 (Day 3) — Frontend Success Widgets

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `frontend/components/dashboard/health-widget.tsx` | None | Test: widget renders |
| 2 | `frontend/components/dashboard/churn-widget.tsx` | None | Test: widget renders |
| 3 | `frontend/components/dashboard/nps-widget.tsx` | None | Test: widget renders |

### BUILDER 4 (Day 4) — Workers + Alert Rules

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `workers/health_check.py` | health_score_service | Test: worker runs |
| 2 | `workers/churn_alert.py` | churn_service | Test: worker runs |
| 3 | `monitoring/alerts/client_success.yml` | None | Test: alerts fire |

### BUILDER 5 (Day 5) — Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_client_success.py` | All success services | All tests pass |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_client_success.py`

**Pass Criteria:**
- Health score calculates correctly
- Churn alert fires when score drops
- NPS survey sends after ticket resolution
- Monday report includes health scores

---

## WEEK 25 — Financial Services Industry Vertical

### BUILDER 1 (Day 1) — FS Config + Compliance + Feature Flags + BDD

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `backend/core/industry_configs/financial_services.py` | config.py (Wk1) | Test: FS config loads |
| 2 | `backend/compliance/aml_check.py` | compliance.py (Wk1) | Test: AML check runs |
| 3 | `feature_flags/fs_flags.json` | None | Test: flags load |
| 4 | `tests/bdd/test_financial_services.py` | FS config | BDD: all scenarios pass |

### BUILDER 2 (Day 2) — FS Integrations

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `shared/integrations/plaid_client.py` | config.py (Wk1) | Test: Plaid mock connects |
| 2 | `shared/integrations/salesforce_client.py` | config.py (Wk1) | Test: Salesforce mock connects |
| 3 | `shared/integrations/bloomberg_client.py` | config.py (Wk1) | Test: Bloomberg mock connects |

### BUILDER 3 (Day 3) — FS Agents + Workflows

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `variants/financial_services/agents/fraud_agent.py` | base_agent.py (Wk9) | Test: fraud detection works |
| 2 | `variants/financial_services/agents/compliance_agent.py` | base_agent.py (Wk9) | Test: compliance works |
| 3 | `variants/financial_services/workflows/transaction_review.py` | FS agents | Test: workflow runs |

### BUILDER 4 (Day 4) — FS Monitoring + AML

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `monitoring/grafana-dashboards/fs-dashboard.json` | None | Verify: dashboard loads |
| 2 | `backend/compliance/enhanced_review.py` | aml_check.py | Test: enhanced review triggers |

### BUILDER 5 (Day 5) — FS Tests

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_financial_services.py` | All FS | All tests pass |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_financial_services.py`

**Pass Criteria:**
- FS onboarding: industry config loads correctly
- AML: high-value transaction triggers enhanced review
- FS compliance rules: correct jurisdiction applied
- Plaid client: mock connection initialises

---

## WEEK 26 — Performance Deep Optimisation (P95 <300ms)

### BUILDER 1 (Day 1) — Multi-Level Redis Caching

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `shared/utils/response_cache.py` | cache.py (Wk2) | Test: response cache works |
| 2 | `shared/utils/query_cache.py` | cache.py (Wk2) | Test: query cache works |
| 3 | `shared/utils/kb_cache.py` | cache.py (Wk2) | Test: KB cache works |

### BUILDER 2 (Day 2) — DB Indexes + Slow Query + Pool Tuning

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `database/indexes/performance_indexes.sql` | None | Test: indexes created |
| 2 | `database/config/pool_tuning.py` | None | Test: pool tuned |
| 3 | `database/monitoring/slow_query_log.py` | None | Test: slow queries logged |

### BUILDER 3 (Day 3) — AI Routing Optimisation

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `shared/smart_router/ml_classifier.py` | router.py (Wk5) | Test: ML classifier >85% accuracy |
| 2 | `shared/smart_router/query_fingerprint.py` | None | Test: fingerprinting works |
| 3 | `shared/smart_router/tier_budget.py` | None | Test: budget enforced |

### BUILDER 4 (Day 4) — Worker Concurrency + Async + Batch

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `workers/concurrency_config.py` | None | Test: concurrency tuned |
| 2 | `workers/async_processors.py` | None | Test: async works |
| 3 | `workers/batch_processors.py` | None | Test: batching works |

### BUILDER 5 (Day 5) — Performance Benchmarks

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/performance/benchmarks/p95_benchmark.py` | All systems | Test: P95 <300ms |
| 2 | `tests/performance/benchmarks/cache_benchmark.py` | All caches | Test: hit rate >75% |

### TESTER AGENT (Day 6)

**Command:** `locust -u 200 && pytest tests/performance/`

**Pass Criteria:**
- P95 <300ms at 200 concurrent users
- Cache hit rate >75%
- Light tier routing >90%
- Zero DB queries >100ms

---

## WEEK 27 — 20-Client Scale Validation

### BUILDER 1 (Day 1) — Clients 11-20 Configs

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `clients/client_011/` through `clients/client_020/` | config.py (Wk1) | Test: all configs load |

### BUILDER 2 (Day 2) — 20-Client Test Infrastructure

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `tests/integration/test_20_client_isolation.py` | All clients | Test: 20-client isolation |
| 2 | `tests/performance/test_20_client_load.py` | All clients | Test: 500 concurrent users |

### BUILDER 3 (Day 3) — Agent Lightning Week 12 Run

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Run full training cycle | All training data | Test: accuracy ≥88% |

### BUILDER 4 (Day 4) — Infrastructure Scaling

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `infra/k8s/hpa-config.yaml` | None | Test: HPA scales |
| 2 | `infra/k8s/redis-ha.yaml` | None | Test: Redis HA works |

### BUILDER 5 (Day 5) — Reports

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `reports/20_client_milestone.md` | None | Milestone report |
| 2 | `PROJECT_STATE.md` (Phase 7 complete) | None | State update |

### TESTER AGENT (Day 6)

**Command:** `pytest tests/integration/test_20_client_isolation.py && pytest tests/performance/test_20_client_load.py`

**Pass Criteria:**
- 20-client isolation: 0 data leaks in 200 tests
- 500 concurrent users P95 <300ms
- Agent Lightning ≥88% accuracy
- Redis HA: failover in <10 seconds

---

# PHASE 8: ENTERPRISE PREP (Weeks 28-40)

---

## WEEK 28 — Agent Lightning 90% Milestone

### BUILDER 1-5 — Training Pipeline Optimisations

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `agent_lightning/training/category_specialists.py` | trainer.py | Test: specialists work |
| 2 | `agent_lightning/training/active_learning.py` | None | Test: active learning works |
| 3 | `agent_lightning/monitoring/ab_testing.py` | None | Test: A/B test works |
| 4 | `agent_lightning/deployment/auto_rollback.py` | None | Test: rollback triggers |
| 5 | Training run with 90% target | All training | Test: accuracy ≥90% |

### TESTER AGENT (Day 6)

**Pass Criteria:**
- Agent Lightning accuracy ≥90%
- A/B test: new model serves 10% of traffic correctly
- Auto-rollback: fires within 60 seconds of drift
- Collective intelligence: no PII in cross-client data

---

## WEEK 29 — Multi-Region Data Residency

### BUILDER 1-5 — Multi-Region Infrastructure

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | `infra/terraform/regions/eu/` | None | Test: EU region works |
| 2 | `infra/terraform/regions/us/` | None | Test: US region works |
| 3 | `infra/terraform/regions/apac/` | None | Test: APAC region works |
| 4 | `backend/compliance/residency_enforcer.py` | None | Test: residency enforced |
| 5 | `backend/compliance/cross_region_replication.py` | None | Test: replication works |

### TESTER AGENT (Day 6)

**Pass Criteria:**
- EU client data absent from US region DB
- Cross-region isolation: 0 leaks in 50 tests
- DB replication lag <500ms
- GDPR export: only data from client's assigned region

---

## WEEK 30 — 30-Client Milestone

### BUILDER 1-5 — Scale Validation

| # | File to Build | Depends On | Test |
|---|---------------|------------|------|
| 1 | Clients 21-30 configs | config.py (Wk1) | Test: all configs load |
| 2 | Full regression all test suites | All tests | 100% pass rate |
| 3 | Security re-audit | All systems | Zero critical issues |
| 4 | Agent Lightning week 15 run | All training | ≥91% accuracy |
| 5 | 30-client load test | All clients | 1000 users P95 <300ms |

### TESTER AGENT (Day 6)

**Pass Criteria:**
- 300 cross-tenant isolation tests: 0 data leaks
- 1000 concurrent users P95 <300ms
- Agent Lightning ≥91%
- Full regression: 100% pass rate
- OWASP clean, CVEs zero critical

---

## WEEKS 31-40 — Enterprise Preparation (Compact)

| Week | Goal | Key Files |
|------|------|-----------|
| 31 | E-commerce Advanced | `variants/ecommerce/advanced/` |
| 32 | SaaS Advanced | `variants/saas/advanced/` |
| 33 | Healthcare HIPAA + Logistics | `variants/healthcare/`, `variants/logistics/` |
| 34 | Frontend v2 (React Query + PWA) | `frontend/v2/` |
| 35 | Smart Router 92%+ | `shared/smart_router/ml_classifier.py` |
| 36 | Agent Lightning 94% | `agent_lightning/training/category_specialists.py` |
| 37 | 50-Client Scale + Autoscaling | `clients/` + `infra/k8s/hpa/` |
| 38 | Enterprise Pre-Preparation | `backend/sso/`, `backend/enterprise/` |
| 39 | Final Production Readiness | Security hardening, docs |
| 40 | Weeks 1-40 Final Validation | Full test suite, enterprise demo |

---

# PHASE 9: CLOUD MIGRATION (Weeks 41-44)

---

## WEEKS 41-44 — Cloud Migration

| Week | Goal | Key Files |
|------|------|-----------|
| 41 | Cloud Foundation | `infra/terraform/providers.tf`, `networking.tf`, `iam.tf` |
| 42 | Deploy Services | K8s deployment manifests, Docker images |
| 43 | Frontend + CDN + Environments | `frontend/cloud/`, CDN config, 3 environments |
| 44 | Storage + Logging + Backups | `infra/terraform/storage.tf`, `logging.tf`, `backup.tf` |

---

# PHASE 10: BILLING (Weeks 45-46)

---

## WEEKS 45-46 — Billing System

| Week | Goal | Key Files |
|------|------|-----------|
| 45 | Razorpay + Multi-Currency | `shared/integrations/razorpay_client.py`, multi-currency pricing |
| 46 | Tax + Dunning + PDF Invoices | `backend/services/tax_service.py`, `dunning_service.py` |

---

# PHASE 11: MOBILE (Weeks 47-49)

---

## WEEKS 47-49 — Mobile App

| Week | Goal | Key Files |
|------|------|-----------|
| 47 | Mobile Foundation (React Native + Expo) | `mobile/` setup, navigation |
| 48 | Mobile Core Screens | Dashboard, approvals, Jarvis |
| 49 | Remaining Screens + App Store | All screens, EAS build, submission |

---

# PHASE 12: ENTERPRISE SSO (Weeks 50-52)

---

## WEEKS 50-52 — Enterprise SSO

| Week | Goal | Key Files |
|------|------|-----------|
| 50 | SAML 2.0 Foundation | `backend/sso/saml_provider.py`, DB migration 012 |
| 51 | Okta + Azure AD + SCIM | Provider-specific implementations |
| 52 | MFA + SSO Audit | `backend/sso/mfa_enforcer.py`, audit logging |

---

# PHASE 13: HIGH AVAILABILITY (Weeks 53-55)

---

## WEEKS 53-55 — Multi-Region HA

| Week | Goal | Key Files |
|------|------|-----------|
| 53 | Multi-Region + Circuit Breakers | `infra/terraform/regions/`, `shared/utils/circuit_breaker.py` |
| 54 | Zero-Downtime Deploys + Network Policies | K8s PDBs, network policies, OpenTelemetry |
| 55 | Chaos Engineering + SLA Verification | Chaos experiments, 99.99% SLA verification |

---

# PHASE 14: SOC 2 COMPLIANCE (Weeks 56-60)

---

## WEEKS 56-60 — SOC 2 Type II

| Week | Goal | Key Files |
|------|------|-----------|
| 56 | Gap Assessment + All 6 Policies | `docs/compliance/policies/` |
| 57 | Vulnerability Scanning + TLS Hardening | Security scans, TLS config |
| 58 | Evidence Collection + Change Management | Automated evidence collection |
| 59 | Final Audit Preparation | Mock audit, documentation |
| 60 | SOC 2 Type II Complete + Production Ready | Final validation, all 60 weeks complete |

---

## WEEK 60 FINAL TESTER AGENT

**Command:** `pytest tests/ && snyk test && locust -u 100`

**Pass Criteria:**
- Full test suite: 100% pass rate
- Zero critical CVEs
- OWASP: clean
- P95 <300ms at 100 concurrent users
- SOC 2 Type II: observation period complete, auditor engaged
- Agent Lightning: ≥94% accuracy
- **ALL 60 WEEKS COMPLETE — PRODUCTION READY**

---

# SUMMARY

| Phase | Weeks | Goal |
|-------|-------|------|
| 3 | 9-14 | Variants & Integrations |
| 4 | 15-18 | Frontend Foundation |
| 5 | 19-20 | First Clients |
| 6 | 21-22 | Scale to 10 clients |
| 7 | 23-27 | Polish & Advanced Features |
| 8 | 28-40 | Enterprise Preparation |
| 9 | 41-44 | Cloud Migration |
| 10 | 45-46 | Billing System |
| 11 | 47-49 | Mobile App |
| 12 | 50-52 | Enterprise SSO |
| 13 | 53-55 | High Availability |
| 14 | 56-60 | SOC 2 Compliance |

**Total: 60 Weeks — 5 Parallel Builders Per Week — No Files Missed**
