**PARWA**

**Parallel Agent Roadmap --- Version 8.0**

*Zai Single-Agent-Per-Day · Files CAN depend within day · Days run in
parallel · Tester runs end of week*

+-----------------------------------------------------------------------+
| NEW PARALLEL RULE (v8.0):                                             |
|                                                                       |
| ✅ Within a day: files CAN depend on each other --- one agent builds  |
| them sequentially top-to-bottom                                       |
|                                                                       |
| ❌ Across days of same week: files CANNOT depend on each other ---    |
| agents run in parallel                                                |
|                                                                       |
| ✅ Across weeks: files CAN depend on any file from previous weeks     |
| (already built)                                                       |
|                                                                       |
| TOOL: Zai agent (not Antigravity)                                     |
|                                                                       |
| TESTING: Tester Agent runs ONCE at end of week --- all unit tests +   |
| all integration tests + full week validation                          |
|                                                                       |
| GIT: Agent commits and pushes each file after its unit test passes.   |
| GitHub CI runs automatically on every push.                           |
|                                                                       |
| DOCKER: Not used in Zai. GitHub CI pipeline handles all testing and   |
| deployment.                                                           |
|                                                                       |
| COMMS: AGENT_COMMS.md stored in GitHub repo --- all agents read/write |
| from there                                                            |
+-----------------------------------------------------------------------+

**Phases 1-4 (Weeks 1-4) --- COMPLETE**

+-----------------------------------------------------------------------+
| Phase 1 (Weeks 1-4) is already complete. This roadmap covers Weeks    |
| 5-60 only.                                                            |
|                                                                       |
| All files from Weeks 1-4 are built and available as dependencies.     |
+-----------------------------------------------------------------------+

**Week 5 --- Phase 2 --- Core AI Engine**

**Build the GSD State Engine, Smart Router, Knowledge Base, an\...**

Build the GSD State Engine, Smart Router, Knowledge Base, and MCP
Client. Each day is a self-contained chain. Days run in parallel --- no
cross-day dependencies within this week.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- GSD State Engine chain**

  ------- ------------------------------------- ---------------------- ------------------
  **DAY   **Files to Build (in order)**         **Depends On**         **Unit Test /
  1**                                                                  Notes**

  **1**   shared/gsd_engine/state_schema.py     config.py (Wk1)        Test: state schema
                                                                       validates
                                                                       correctly

  **2**   shared/gsd_engine/state_engine.py     state_schema.py (same  Test: 20-msg convo
                                                day above)             compresses to
                                                                       \<200 tokens

  **3**   shared/gsd_engine/context_health.py   state_schema.py (same  Test: health
                                                day above)             returns correct
                                                                       warning/critical
                                                                       flags

  **4**   shared/gsd_engine/compression.py      state_engine.py,       Test: token
                                                state_schema.py (same  reduction \>85% on
                                                day above)             simple queries

  **5**   tests/unit/test_gsd_engine.py         All GSD files above    PUSH ONLY AFTER
                                                (same day)             THIS PASSES
  ------- ------------------------------------- ---------------------- ------------------

**Day 2 --- Smart Router chain**

  ------- ------------------------------------------ ---------------------- -----------------
  **DAY   **Files to Build (in order)**              **Depends On**         **Unit Test /
  2**                                                                       Notes**

  **1**   shared/smart_router/tier_config.py         config.py (Wk1)        Test: tier IDs
                                                                            valid OpenRouter
                                                                            format

  **2**   shared/smart_router/failover.py            config.py, logger.py   Test: failover
                                                     (Wk1)                  activates on rate
                                                                            limit

  **3**   shared/smart_router/complexity_scorer.py   tier_config.py (same   Test: FAQ scores
                                                     day above)             0-2, refund
                                                                            scores 9+

  **4**   shared/smart_router/router.py              tier_config.py,        Test: FAQ→Light,
                                                     complexity_scorer.py   refund→Heavy
                                                     (same day above)       

  **5**   tests/unit/test_smart_router.py            All router files above PUSH ONLY AFTER
                                                     (same day)             THIS PASSES
  ------- ------------------------------------------ ---------------------- -----------------

**Day 3 --- Knowledge Base chain**

  ------- --------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**           **Depends On**         **Unit Test /
  3**                                                                    Notes**

  **1**   shared/knowledge_base/vector_store.py   config.py, database.py Test: embeddings
                                                  (Wks 1-2)              stored and
                                                                         retrieved

  **2**   shared/knowledge_base/kb_manager.py     config.py (Wk1)        Test: KB manager
                                                                         initialises

  **3**   shared/knowledge_base/hyde.py           config.py (Wk1)        Test: HyDE
                                                                         generates
                                                                         hypothetical doc

  **4**   shared/knowledge_base/multi_query.py    config.py (Wk1)        Test: generates 3
                                                                         query variants

  **5**   shared/knowledge_base/rag_pipeline.py   vector_store, hyde,    Test: ingest +
                                                  multi_query (above)    retrieve round
                                                                         trip works

  **6**   tests/unit/test_knowledge_base.py       All KB files above     PUSH ONLY AFTER
                                                  (same day)             THIS PASSES
  ------- --------------------------------------- ---------------------- -----------------

**Day 4 --- MCP Client chain**

  ------- ------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**   **Depends On**         **Unit Test /
  4**                                                            Notes**

  **1**   shared/mcp_client/client.py     config.py (Wk1)        Test: client
                                                                 initialises

  **2**   shared/mcp_client/auth.py       config.py, security.py Test: auth tokens
                                          (Wks 1-3)              generated

  **3**   shared/mcp_client/registry.py   config.py (Wk1)        Test: registry
                                                                 connects

  **4**   tests/unit/test_mcp_client.py   All MCP files above    PUSH ONLY AFTER
                                          (same day)             THIS PASSES
  ------- ------------------------------- ---------------------- -----------------

**Day 5 --- Pricing + docs (independent extras)**

  ------- ----------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                   **Depends On**         **Unit Test /
  5**                                                                            Notes**

  **1**   tests/unit/test_pricing_optimizer.py            pricing_optimizer.py   Test:
                                                          (Wk1)                  anti-arbitrage
                                                                                 formula correct

  **2**   docs/architecture_decisions/003_openrouter.md   None                   Doc only --- no
                                                                                 test required

  **3**   backend/api/webhook_malformation_handler.py     webhooks/shopify.py,   Test:
                                                          stripe.py (Wk4)        half-corrupt
                                                                                 webhook handled
  ------- ----------------------------------------------- ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_week5_gsd_kb.py -v             |
|                                                                       |
| • GSD: 20-message conversation compresses to under 200 tokens         |
|                                                                       |
| • Smart Router: FAQ routes to Light tier, refund routes to Heavy tier |
|                                                                       |
| • Failover: simulated rate limit triggers secondary model switch      |
|                                                                       |
| • KB: document ingest and retrieve round trip works                   |
|                                                                       |
| • MCP client: initialises and connects to registry                    |
|                                                                       |
| • Integration: GSD → Smart Router → KB work as unified pipeline       |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. GSD compression: 20-msg conversation → \<200 tokens               |
|                                                                       |
| 2\. Smart Router: FAQ→Light, refund→Heavy, failover working           |
|                                                                       |
| 3\. KB: ingest + retrieve round trip passes                           |
|                                                                       |
| 4\. MCP client: connects without errors                               |
|                                                                       |
| 5\. All unit tests pass before push                                   |
|                                                                       |
| 6\. GitHub CI pipeline green on all pushes                            |
+-----------------------------------------------------------------------+

**Week 6 --- Phase 2 --- Core AI Engine**

**Build TRIVYA Tier 1, Tier 2 techniques, confidence scoring, \...**

Build TRIVYA Tier 1, Tier 2 techniques, confidence scoring, and
sentiment. Each day is a self-contained chain --- days run in parallel.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- TRIVYA Tier 1 chain**

  ------- --------------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                       **Depends On**         **Unit Test /
  1**                                                                                Notes**

  **1**   shared/trivya_techniques/tier1/clara.py             rag_pipeline.py,       Test: CLARA
                                                              hyde.py (Wk5)          retrieves
                                                                                     relevant context

  **2**   shared/trivya_techniques/tier1/crp.py               gsd_engine (Wk5)       Test: CRP
                                                                                     compresses
                                                                                     correctly

  **3**   shared/trivya_techniques/tier1/gsd_integration.py   state_engine.py (Wk5)  Test: GSD state
                                                                                     integrates with
                                                                                     T1

  **4**   shared/trivya_techniques/orchestrator.py            config.py, router.py   Test: T1 always
                                                              (Wks 1-5), clara.py,   fires on every
                                                              crp.py (above)         query

  **5**   tests/unit/test_trivya_tier1.py                     All T1 files above     PUSH ONLY AFTER
                                                                                     THIS PASSES
  ------- --------------------------------------------------- ---------------------- -----------------

**Day 2 --- TRIVYA Tier 2 chain**

  ------- ----------------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                         **Depends On**         **Unit Test /
  2**                                                                                  Notes**

  **1**   shared/trivya_techniques/tier2/trigger_detector.py    config.py (Wk1)        Test: detects
                                                                                       decision_needed
                                                                                       queries

  **2**   shared/trivya_techniques/tier2/chain_of_thought.py    config.py (Wk1)        Test: produces
                                                                                       step-by-step
                                                                                       reasoning

  **3**   shared/trivya_techniques/tier2/react.py               config.py (Wk1)        Test: reason+act
                                                                                       loop runs

  **4**   shared/trivya_techniques/tier2/reverse_thinking.py    config.py (Wk1)        Test: reverse
                                                                                       approach produces
                                                                                       output

  **5**   shared/trivya_techniques/tier2/step_back.py           config.py (Wk1)        Test: abstracts
                                                                                       question
                                                                                       correctly

  **6**   shared/trivya_techniques/tier2/thread_of_thought.py   gsd_engine (Wk5)       Test: thread
                                                                                       maintains context

  **7**   tests/unit/test_trivya_tier2.py                       All T2 files above     PUSH ONLY AFTER
                                                                                       THIS PASSES
  ------- ----------------------------------------------------- ---------------------- -----------------

**Day 3 --- Confidence + Compliance tests chain**

  ------- -------------------------------------- ---------------------- ------------------
  **DAY   **Files to Build (in order)**          **Depends On**         **Unit Test /
  3**                                                                   Notes**

  **1**   shared/confidence/thresholds.py        config.py (Wk1)        Test:
                                                                        GRADUATE=95%,
                                                                        ESCALATE=70%

  **2**   shared/confidence/scorer.py            thresholds.py (same    Test: weighted avg
                                                 day above)             40+30+20+10=100%

  **3**   tests/unit/test_confidence_scorer.py   scorer.py,             PUSH ONLY AFTER
                                                 thresholds.py (same    THIS PASSES
                                                 day above)             

  **4**   tests/unit/test_compliance.py          compliance.py (Wk1)    PUSH ONLY AFTER
                                                                        THIS PASSES

  **5**   tests/unit/test_audit_trail.py         audit_trail.py (Wk1)   PUSH ONLY AFTER
                                                                        THIS PASSES
  ------- -------------------------------------- ---------------------- ------------------

**Day 4 --- Sentiment chain**

  ------- ----------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**       **Depends On**         **Unit Test /
  4**                                                                Notes**

  **1**   shared/sentiment/analyzer.py        router.py (Wk5)        Test: anger score
                                                                     routes to High
                                                                     pathway

  **2**   shared/sentiment/routing_rules.py   thresholds.py (Wk6     Test: routing
                                              D3), analyzer.py       rules apply
                                              (above)                correctly

  **3**   tests/unit/test_sentiment.py        analyzer.py,           PUSH ONLY AFTER
                                              routing_rules.py       THIS PASSES
                                              (above)                
  ------- ----------------------------------- ---------------------- -----------------

**Day 5 --- Cold start + T1+T2 tests**

  ------- --------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**           **Depends On**         **Unit Test /
  5**                                                                    Notes**

  **1**   shared/knowledge_base/cold_start.py     kb_manager.py (Wk5)    Test: bootstraps
                                                                         with industry
                                                                         FAQs

  **2**   tests/unit/test_trivya_tier1_tier2.py   All T1+T2 files (Wks   PUSH ONLY AFTER
                                                  5-6)                   THIS PASSES
  ------- --------------------------------------- ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_week6_trivya.py -v             |
|                                                                       |
| • TRIVYA orchestrator: Tier 1 fires on every query                    |
|                                                                       |
| • Tier 2 trigger: only activates on decision_needed or multi_step     |
|                                                                       |
| • Confidence: 95%+ → GRADUATE, \<70% → ESCALATE                       |
|                                                                       |
| • Sentiment: high anger score routes to PARWA High pathway            |
|                                                                       |
| • All 6 Tier 2 techniques produce meaningfully different outputs      |
|                                                                       |
| • Cold start: bootstraps new client KB correctly                      |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. TRIVYA T1+T2 pipeline functional end-to-end                       |
|                                                                       |
| 2\. Confidence scoring correct at all thresholds                      |
|                                                                       |
| 3\. Sentiment routing working                                         |
|                                                                       |
| 4\. All unit tests pass before push                                   |
|                                                                       |
| 5\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 7 --- Phase 2 --- Core AI Engine**

**Build TRIVYA Tier 3 techniques, all integration API clients,\...**

Build TRIVYA Tier 3 techniques, all integration API clients, and
compliance layer. Each day is independent.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- TRIVYA Tier 3 chain**

  ------- -------------------------------------------------------- ---------------------- ------------------------------
  **DAY   **Files to Build (in order)**                            **Depends On**         **Unit Test / Notes**
  1**                                                                                     

  **1**   shared/trivya_techniques/tier3/trigger_detector.py       confidence/scorer.py   Test: only fires on
                                                                   (Wk6)                  VIP/amount\>\$100/anger\>80%

  **2**   shared/trivya_techniques/tier3/gst.py                    config.py (Wk1)        Test: structured thought
                                                                                          output

  **3**   shared/trivya_techniques/tier3/universe_of_thoughts.py   config.py (Wk1)        Test: multiple solution paths

  **4**   shared/trivya_techniques/tier3/tree_of_thoughts.py       config.py (Wk1)        Test: tree structure generated

  **5**   shared/trivya_techniques/tier3/self_consistency.py       config.py (Wk1)        Test: majority vote across
                                                                                          paths

  **6**   shared/trivya_techniques/tier3/reflexion.py              config.py (Wk1)        Test: reflection loop runs

  **7**   shared/trivya_techniques/tier3/least_to_most.py          config.py (Wk1)        Test: decomposes complex query

  **8**   tests/unit/test_trivya_tier3.py                          All T3 files above     PUSH ONLY AFTER THIS PASSES
  ------- -------------------------------------------------------- ---------------------- ------------------------------

**Day 2 --- E-commerce + comms integration clients**

  ------- --------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**           **Depends On**         **Unit Test /
  2**                                                                    Notes**

  **1**   shared/integrations/shopify_client.py   config.py, logger.py   Test: mock
                                                  (Wk1)                  connection
                                                                         initialises

  **2**   shared/integrations/stripe_client.py    config.py, logger.py   Test: refund gate
                                                  (Wk1)                  enforced

  **3**   shared/integrations/twilio_client.py    config.py, logger.py   Test: SMS + voice
                                                  (Wk1)                  mock works

  **4**   shared/integrations/email_client.py     config.py, logger.py   Test: email send
                                                  (Wk1)                  mocked

  **5**   shared/integrations/zendesk_client.py   config.py, logger.py   Test: ticket
                                                  (Wk1)                  create mocked
  ------- --------------------------------------- ---------------------- -----------------

**Day 3 --- Dev + logistics + compliance integration clients**

  ------- ----------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**             **Depends On**         **Unit Test /
  3**                                                                      Notes**

  **1**   shared/integrations/github_client.py      config.py (Wk1)        Test: repo access
                                                                           mocked

  **2**   shared/integrations/aftership_client.py   config.py (Wk1)        Test: tracking
                                                                           mocked

  **3**   shared/integrations/epic_ehr_client.py    config.py (Wk1)        Test: read-only
                                                                           EHR access

  **4**   tests/unit/test_integration_clients.py    All clients above + D2 PUSH ONLY AFTER
                                                    clients                THIS PASSES
  ------- ----------------------------------------- ---------------------- -----------------

**Day 4 --- Compliance layer chain**

  ------- --------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**           **Depends On**         **Unit Test /
  4**                                                                    Notes**

  **1**   shared/compliance/jurisdiction.py       config.py (Wk1)        Test: IN
                                                                         client→TCPA rules

  **2**   shared/compliance/sla_calculator.py     config.py (Wk1)        Test: SLA breach
                                                                         calculated

  **3**   shared/compliance/gdpr_engine.py        compliance.py (Wk1)    Test: export
                                                                         complete,
                                                                         soft-delete masks
                                                                         PII

  **4**   shared/compliance/healthcare_guard.py   compliance.py (Wk1)    Test: BAA check
                                                                         enforced, PHI not
                                                                         logged
  ------- --------------------------------------- ---------------------- -----------------

**Day 5 --- Integration tests for T3 + clients**

  ------- --------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**           **Depends On**         **Unit Test /
  5**                                                                    Notes**

  **1**   tests/unit/test_trivya_tier1_tier2.py   Full T1+T2+T3 pipeline PUSH ONLY AFTER
          (update)                                                       THIS PASSES
  ------- --------------------------------------- ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_week7_trivya_complete.py -v    |
|                                                                       |
| • Full TRIVYA T1+T2+T3: all fire correctly on correct triggers        |
|                                                                       |
| • Tier 3 does NOT activate on simple FAQ queries                      |
|                                                                       |
| • Tier 3 DOES activate on VIP + amount\>\$100 + anger\>80% scenario   |
|                                                                       |
| • All integration clients initialise without credential errors        |
| (mocked)                                                              |
|                                                                       |
| • GDPR engine: export and soft-delete both work correctly             |
|                                                                       |
| • Healthcare guard: BAA check enforced, no PHI in logs                |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. Full TRIVYA pipeline T1+T2+T3 functional                          |
|                                                                       |
| 2\. All integration clients connect (mocked)                          |
|                                                                       |
| 3\. GDPR + healthcare compliance layer working                        |
|                                                                       |
| 4\. All unit tests pass before push                                   |
|                                                                       |
| 5\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 8 --- Phase 2 --- Core AI Engine**

**Build all 11 MCP servers plus guardrails. Day 1 builds base\_\...**

Build all 11 MCP servers plus guardrails. Day 1 builds base_server first
then knowledge servers. Days 2-5 build integration/tool servers
independently.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- Base server + knowledge MCP servers (sequential --- base
first)**

  ------- ------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**         **Depends On**         **Unit Test /
  1**                                                                  Notes**

  **1**   mcp_servers/base_server.py            config.py, security.py Test: base server
                                                (Wks 1-3)              starts

  **2**   mcp_servers/knowledge/faq_server.py   base_server.py (same   Test: FAQ tool
                                                day above)             responds

  **3**   mcp_servers/knowledge/rag_server.py   base_server.py         Test: RAG round
                                                (above),               trip
                                                rag_pipeline.py (Wk5)  

  **4**   mcp_servers/knowledge/kb_server.py    base_server.py         Test: KB tool
                                                (above), kb_manager.py responds
                                                (Wk5)                  

  **5**   tests/unit/test_mcp_knowledge.py      All above              PUSH ONLY AFTER
                                                                       THIS PASSES
  ------- ------------------------------------- ---------------------- -----------------

**Day 2 --- Voice + chat + ticketing MCP servers**

  ------- ---------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                  **Depends On**         **Unit Test /
  2**                                                                           Notes**

  **1**   mcp_servers/integrations/email_server.py       base_server.py (Wk8    Test: email tool
                                                         D1), email_client.py   responds in \<2s
                                                         (Wk7)                  

  **2**   mcp_servers/integrations/voice_server.py       base_server.py (Wk8    Test: voice tool
                                                         D1), twilio_client.py  responds in \<2s
                                                         (Wk7)                  

  **3**   mcp_servers/integrations/chat_server.py        base_server.py (Wk8    Test: chat tool
                                                         D1)                    responds in \<2s

  **4**   mcp_servers/integrations/ticketing_server.py   base_server.py (Wk8    Test: ticketing
                                                         D1)                    tool responds in
                                                                                \<2s
  ------- ---------------------------------------------- ---------------------- -----------------

**Day 3 --- E-commerce + CRM + analytics MCP servers**

  ------- ---------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                  **Depends On**         **Unit Test /
  3**                                                                           Notes**

  **1**   mcp_servers/integrations/ecommerce_server.py   base_server.py (Wk8    Test: ecommerce
                                                         D1), shopify_client.py tool responds
                                                         (Wk7)                  

  **2**   mcp_servers/integrations/crm_server.py         base_server.py (Wk8    Test: CRM tool
                                                         D1)                    responds

  **3**   mcp_servers/tools/analytics_server.py          base_server.py (Wk8    Test: analytics
                                                         D1)                    tool responds

  **4**   mcp_servers/tools/monitoring_server.py         base_server.py (Wk8    Test: monitoring
                                                         D1)                    tool responds
  ------- ---------------------------------------------- ---------------------- -----------------

**Day 4 --- Notification + compliance + SLA MCPs + guardrails chain**

  ------- ------------------------------------------ ------------------------- -----------------
  **DAY   **Files to Build (in order)**              **Depends On**            **Unit Test /
  4**                                                                          Notes**

  **1**   mcp_servers/tools/notification_server.py   base_server.py (Wk8 D1),  Test:
                                                     notification_service.py   notification tool
                                                     (Wk4)                     responds

  **2**   mcp_servers/tools/compliance_server.py     base_server.py (Wk8 D1),  Test: compliance
                                                     gdpr_engine.py (Wk7)      tool responds

  **3**   mcp_servers/tools/sla_server.py            base_server.py (Wk8 D1)   Test: SLA tool
                                                                               responds

  **4**   shared/guardrails/guardrails.py            smart_router.py (Wk7),    Test:
                                                     trivya_techniques/ (Wk6)  hallucination
                                                                               blocked,
                                                                               competitor
                                                                               blocked

  **5**   shared/guardrails/approval_enforcer.py     guardrails.py (same day   Test: refund
                                                     above)                    bypass attempt
                                                                               blocked

  **6**   tests/unit/test_mcp_servers.py             All MCP files (Wk8 D1-D4) PUSH ONLY AFTER
                                                                               THIS PASSES
  ------- ------------------------------------------ ------------------------- -----------------

**Day 5 --- Monitoring setup + integration test files**

  ------- ------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**               **Depends On**         **Unit Test /
  5**                                                                        Notes**

  **1**   monitoring/prometheus.yml                   None --- config only   Verify: scrapes
                                                                             all services

  **2**   tests/integration/test_week3_workflows.py   All MCP servers (Wk8   MCP round-trip
                                                      D1-D4)                 integration test

  **3**   tests/integration/test_week2_gsd_kb.py      GSD+KB+TRIVYA+MCP all  Full AI pipeline
                                                      complete               test
  ------- ------------------------------------------- ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_week8_mcp.py -v                |
|                                                                       |
| • All 11 MCP servers start without errors                             |
|                                                                       |
| • MCP client connects to all servers via registry                     |
|                                                                       |
| • Each MCP server responds to test tool call within 2 seconds         |
|                                                                       |
| • Full chain: GSD → TRIVYA → MCP → integration client completes       |
|                                                                       |
| • Guardrails: hallucination and competitor mention blocked            |
|                                                                       |
| • Approval enforcer: refund bypass attempt intercepted                |
|                                                                       |
| • prometheus.yml scrapes all services                                 |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. All 11 MCP servers running and responding                         |
|                                                                       |
| 2\. Full AI engine: GSD → TRIVYA → MCP functional                     |
|                                                                       |
| 3\. Guardrails protecting all AI outputs                              |
|                                                                       |
| 4\. All unit tests pass before push                                   |
|                                                                       |
| 5\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 9 --- Phase 3 --- Variants & Integrations**

**Build all base agents and Mini PARWA variant. Day 1 builds b\...**

Build all base agents and Mini PARWA variant. Day 1 builds base_agent
first, then dependents. Days run in parallel.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- Base agent abstract + core base agents (sequential)**

  ------- ----------------------------------------------- ----------------------- -----------------
  **DAY   **Files to Build (in order)**                   **Depends On**          **Unit Test /
  1**                                                                             Notes**

  **1**   variants/base_agents/base_agent.py              confidence/scorer.py,   Test: base agent
                                                          security.py (Wks 3-6)   initialises

  **2**   variants/base_agents/base_faq_agent.py          base_agent.py (same day Test: FAQ agent
                                                          above)                  inherits
                                                                                  correctly

  **3**   variants/base_agents/base_email_agent.py        base_agent.py (same day Test: email agent
                                                          above)                  inherits

  **4**   variants/base_agents/base_chat_agent.py         base_agent.py (same day Test: chat agent
                                                          above)                  inherits

  **5**   variants/base_agents/base_sms_agent.py          base_agent.py (same day Test: SMS agent
                                                          above)                  inherits

  **6**   variants/base_agents/base_voice_agent.py        base_agent.py (same day Test: voice agent
                                                          above)                  inherits

  **7**   variants/base_agents/base_ticket_agent.py       base_agent.py (same day Test: ticket
                                                          above)                  agent inherits

  **8**   variants/base_agents/base_escalation_agent.py   base_agent.py (same day Test: escalation
                                                          above)                  agent inherits

  **9**   tests/unit/test_base_agents.py                  All base agents above   PUSH ONLY AFTER
                                                                                  THIS PASSES
  ------- ----------------------------------------------- ----------------------- -----------------

**Day 2 --- Base refund agent + Mini config chain**

  ------- ------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**               **Depends On**         **Unit Test /
  2**                                                                        Notes**

  **1**   variants/base_agents/base_refund_agent.py   base_agent.py (Wk9     Test: refund gate
                                                      D1), approval gates    enforced ---
                                                      (Wks 3-4)              Stripe NOT called

  **2**   variants/mini/config.py                     config.py (Wk1)        Test: Mini config
                                                                             loads

  **3**   variants/mini/anti_arbitrage_config.py      pricing_optimizer.py   Test:
                                                      (Wk1)                  anti-arbitrage
                                                                             formula correct
  ------- ------------------------------------------- ---------------------- -----------------

**Day 3 --- Mini FAQ + Email + Chat + SMS agents**

  ------- ------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**         **Depends On**         **Unit Test /
  3**                                                                  Notes**

  **1**   variants/mini/agents/faq_agent.py     base_faq_agent.py (Wk9 Test: FAQ agent
                                                D1)                    routes to Light
                                                                       tier

  **2**   variants/mini/agents/email_agent.py   base_email_agent.py    Test: email agent
                                                (Wk9 D1)               processes
                                                                       correctly

  **3**   variants/mini/agents/chat_agent.py    base_chat_agent.py     Test: chat agent
                                                (Wk9 D1)               responds

  **4**   variants/mini/agents/sms_agent.py     base_sms_agent.py (Wk9 Test: SMS agent
                                                D1)                    sends
  ------- ------------------------------------- ---------------------- -----------------

**Day 4 --- Mini voice + ticket + escalation + refund agents**

  ------- ------------------------------------------ -------------------------- ------------------
  **DAY   **Files to Build (in order)**              **Depends On**             **Unit Test /
  4**                                                                           Notes**

  **1**   variants/mini/agents/voice_agent.py        base_voice_agent.py (Wk9   Test: voice agent
                                                     D1)                        handles call

  **2**   variants/mini/agents/ticket_agent.py       base_ticket_agent.py (Wk9  Test: ticket
                                                     D1)                        created correctly

  **3**   variants/mini/agents/escalation_agent.py   base_escalation_agent.py   Test: escalation
                                                     (Wk9 D1)                   triggers human
                                                                                handoff

  **4**   variants/mini/agents/refund_agent.py       base_refund_agent.py (Wk9  Test:
                                                     D2)                        pending_approval
                                                                                created, Stripe
                                                                                NOT called
  ------- ------------------------------------------ -------------------------- ------------------

**Day 5 --- Mini tools + workflows chain**

  -------- -------------------------------------------------- ---------------------- ------------------
  **DAY    **Files to Build (in order)**                      **Depends On**         **Unit Test /
  5**                                                                                Notes**

  **1**    variants/mini/tools/faq_search.py                  shopify_client.py      Test: FAQ search
                                                              (Wk7)                  returns results

  **2**    variants/mini/tools/order_lookup.py                shopify_client.py      Test: order found
                                                              (Wk7)                  by ID

  **3**    variants/mini/tools/ticket_create.py               support API (Wk4)      Test: ticket
                                                                                     created

  **4**    variants/mini/tools/notification.py                twilio_client.py (Wk7) Test: notification
                                                                                     sent

  **5**    variants/mini/tools/refund_verification_tools.py   stripe_client.py (Wk7) Test: refund
                                                                                     verified, NOT
                                                                                     executed

  **6**    variants/mini/workflows/inquiry.py                 Mini agents (D3-D4     Test: inquiry
                                                              above)                 workflow completes

  **7**    variants/mini/workflows/ticket_creation.py         Mini agents (D3-D4     Test: ticket
                                                              above)                 workflow completes

  **8**    variants/mini/workflows/escalation.py              Mini agents (D3-D4     Test: escalation
                                                              above)                 workflow fires

  **9**    variants/mini/workflows/order_status.py            Mini agents (D3-D4     Test: order status
                                                              above)                 returned

  **10**   variants/mini/workflows/refund_verification.py     Mini agents (D3-D4     Test: refund
                                                              above)                 workflow creates
                                                                                     pending_approval
  -------- -------------------------------------------------- ---------------------- ------------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_week9_mini_variant.py -v       |
|                                                                       |
| • Mini PARWA: FAQ query routes to Light tier                          |
|                                                                       |
| • Mini PARWA: refund request creates pending_approval --- Stripe NOT  |
| called                                                                |
|                                                                       |
| • Mini PARWA: escalation triggers human handoff                       |
|                                                                       |
| • All 8 base agents initialise without errors                         |
|                                                                       |
| • Refund gate: CRITICAL --- Stripe must not be called without         |
| approval                                                              |
|                                                                       |
| • Mini anti-arbitrage: 2x Mini cost shows manager time correctly      |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. Mini PARWA variant fully functional                               |
|                                                                       |
| 2\. Refund gate verified: Stripe NOT called without approval          |
|                                                                       |
| 3\. All base agents working                                           |
|                                                                       |
| 4\. All unit tests pass before push                                   |
|                                                                       |
| 5\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 10 --- Phase 3 --- Variants & Integrations**

**Build Mini tasks and PARWA Junior variant. Each day is self-\...**

Build Mini tasks and PARWA Junior variant. Each day is self-contained.
Days run in parallel.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- Mini tasks chain**

  ------- -------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**          **Depends On**         **Unit Test /
  1**                                                                   Notes**

  **1**   variants/mini/tasks/answer_faq.py      Mini agents (Wk9)      Test: FAQ
                                                                        answered
                                                                        correctly

  **2**   variants/mini/tasks/process_email.py   Mini agents (Wk9)      Test: email
                                                                        processed

  **3**   variants/mini/tasks/handle_chat.py     Mini agents (Wk9)      Test: chat
                                                                        handled

  **4**   variants/mini/tasks/make_call.py       Mini agents (Wk9)      Test: call
                                                                        initiated

  **5**   variants/mini/tasks/create_ticket.py   Mini agents (Wk9)      Test: ticket
                                                                        created

  **6**   variants/mini/tasks/escalate.py        Mini agents (Wk9)      Test: escalation
                                                                        fires

  **7**   variants/mini/tasks/verify_refund.py   Mini agents (Wk9)      Test: refund
                                                                        verified not
                                                                        executed

  **8**   tests/unit/test_mini_tasks.py          All mini tasks above   PUSH ONLY AFTER
                                                                        THIS PASSES
  ------- -------------------------------------- ---------------------- -----------------

**Day 2 --- PARWA config + core agents chain**

  -------- ------------------------------------------- -------------------------- ---------------------
  **DAY    **Files to Build (in order)**               **Depends On**             **Unit Test / Notes**
  2**                                                                             

  **1**    variants/parwa/config.py                    config.py (Wk1)            Test: PARWA config
                                                                                  loads

  **2**    variants/parwa/anti_arbitrage_config.py     pricing_optimizer.py (Wk1) Test: 1x PARWA shows
                                                                                  0.5 hrs/day

  **3**    variants/parwa/agents/faq_agent.py          base_faq_agent.py (Wk9)    Test: PARWA FAQ
                                                                                  routes to Light

  **4**    variants/parwa/agents/email_agent.py        base_email_agent.py (Wk9)  Test: PARWA email
                                                                                  processes

  **5**    variants/parwa/agents/chat_agent.py         base_chat_agent.py (Wk9)   Test: PARWA chat
                                                                                  responds

  **6**    variants/parwa/agents/sms_agent.py          base_sms_agent.py (Wk9)    Test: PARWA SMS sends

  **7**    variants/parwa/agents/voice_agent.py        base_voice_agent.py (Wk9)  Test: PARWA voice
                                                                                  handles call

  **8**    variants/parwa/agents/ticket_agent.py       base_ticket_agent.py (Wk9) Test: PARWA ticket
                                                                                  created

  **9**    variants/parwa/agents/escalation_agent.py   base_escalation_agent.py   Test: PARWA escalates
                                                       (Wk9)                      correctly

  **10**   variants/parwa/agents/refund_agent.py       base_refund_agent.py (Wk9) Test: PARWA refund →
                                                                                  APPROVE/REVIEW/DENY
  -------- ------------------------------------------- -------------------------- ---------------------

**Day 3 --- PARWA unique agents + tools chain**

  ------- ----------------------------------------------------- ---------------------- ---------------------
  **DAY   **Files to Build (in order)**                         **Depends On**         **Unit Test / Notes**
  3**                                                                                  

  **1**   variants/parwa/agents/learning_agent.py               base_agent.py,         Test: negative_reward
                                                                training_data model    created on rejection
                                                                (Wks 3-9)              

  **2**   variants/parwa/agents/safety_agent.py                 ai_safety.py,          Test: competitor
                                                                base_agent.py (Wks     mention blocked
                                                                1-9)                   

  **3**   variants/parwa/tools/knowledge_update.py              kb_manager.py (Wk5)    Test: KB updated
                                                                                       correctly

  **4**   variants/parwa/tools/refund_recommendation_tools.py   stripe_client.py (Wk7) Test:
                                                                                       APPROVE/REVIEW/DENY
                                                                                       with reasoning

  **5**   variants/parwa/tools/safety_tools.py                  ai_safety.py (Wk1)     Test: safety check
                                                                                       runs
  ------- ----------------------------------------------------- ---------------------- ---------------------

**Day 4 --- PARWA workflows + tasks chain**

  ------- --------------------------------------------------- ---------------------- ---------------------
  **DAY   **Files to Build (in order)**                       **Depends On**         **Unit Test / Notes**
  4**                                                                                

  **1**   variants/parwa/workflows/refund_recommendation.py   PARWA agents (D2-D3    Test: recommendation
                                                              above)                 includes reasoning

  **2**   variants/parwa/workflows/knowledge_update.py        PARWA agents (D2-D3    Test: KB updated
                                                              above)                 after resolution

  **3**   variants/parwa/workflows/safety_workflow.py         PARWA agents (D2-D3    Test: safety check
                                                              above)                 runs before response

  **4**   variants/parwa/tasks/recommend_refund.py            PARWA agents (D2-D3    Test:
                                                              above)                 APPROVE/REVIEW/DENY
                                                                                     returned

  **5**   variants/parwa/tasks/update_knowledge.py            PARWA agents (D2-D3    Test: KB entry added
                                                              above)                 

  **6**   variants/parwa/tasks/compliance_check.py            compliance.py (Wk1)    Test: compliance
                                                                                     check runs
  ------- --------------------------------------------------- ---------------------- ---------------------

**Day 5 --- PARWA tests + manager time**

  ------- --------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                 **Depends On**         **Unit Test /
  5**                                                                          Notes**

  **1**   tests/unit/test_parwa_agents.py               All PARWA agents       PUSH ONLY AFTER
                                                        (D2-D3)                THIS PASSES

  **2**   tests/unit/test_parwa_workflows.py            PARWA workflows (D4)   PUSH ONLY AFTER
                                                                               THIS PASSES

  **3**   backend/services/manager_time_calculator.py   pricing_optimizer.py   Test: manager
                                                        (Wk1)                  time formula
                                                                               correct
  ------- --------------------------------------------- ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_week5_parwa_variant.py -v      |
|                                                                       |
| • PARWA recommendation: includes APPROVE/REVIEW/DENY with full        |
| reasoning                                                             |
|                                                                       |
| • PARWA learning agent: negative_reward record created on rejection   |
|                                                                       |
| • PARWA safety agent: competitor mention blocked                      |
|                                                                       |
| • Mini still works correctly alongside PARWA (no conflicts)           |
|                                                                       |
| • Manager time calculator: 1x PARWA shows 0.5 hrs/day correctly       |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. PARWA Junior variant fully functional                             |
|                                                                       |
| 2\. Learning and safety agents working                                |
|                                                                       |
| 3\. Mini and PARWA coexist without conflicts                          |
|                                                                       |
| 4\. All unit tests pass before push                                   |
|                                                                       |
| 5\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 11 --- Phase 3 --- Variants & Integrations**

**Build PARWA High variant and verify all 3 variants coexist. \...**

Build PARWA High variant and verify all 3 variants coexist. Days run in
parallel.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- PARWA High config + core advanced agents chain**

  ------- -------------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                      **Depends On**         **Unit Test /
  1**                                                                               Notes**

  **1**   variants/parwa_high/config.py                      config.py (Wk1)        Test: High config
                                                                                    loads

  **2**   variants/parwa_high/anti_arbitrage_config.py       pricing_optimizer.py   Test: High
                                                             (Wk1)                  anti-arbitrage
                                                                                    correct

  **3**   variants/parwa_high/agents/video_agent.py          base_agent.py (Wk9)    Test: video agent
                                                                                    initialises

  **4**   variants/parwa_high/agents/analytics_agent.py      base_agent.py (Wk9)    Test: analytics
                                                                                    agent runs

  **5**   variants/parwa_high/agents/coordination_agent.py   base_agent.py (Wk9)    Test:
                                                                                    coordination
                                                                                    agent manages 5
                                                                                    concurrent
  ------- -------------------------------------------------- ---------------------- -----------------

**Day 2 --- PARWA High customer success + compliance agents**

  ------- ------------------------------------------------------ ---------------------- -----------------
  **DAY   **Files to Build (in order)**                          **Depends On**         **Unit Test /
  2**                                                                                   Notes**

  **1**   variants/parwa_high/agents/customer_success_agent.py   base_agent.py (Wk9)    Test: churn
                                                                                        prediction
                                                                                        contains risk
                                                                                        score

  **2**   variants/parwa_high/agents/sla_agent.py                base_agent.py,         Test: SLA breach
                                                                 sla_calculator.py (Wks detected
                                                                 7-9)                   

  **3**   variants/parwa_high/agents/compliance_agent.py         base_agent.py,         Test: HIPAA
                                                                 healthcare_guard.py    compliance
                                                                 (Wks 7-9)              enforced

  **4**   variants/parwa_high/agents/learning_agent.py           base_agent.py (Wk9)    Test: learning
                                                                                        records training
                                                                                        data

  **5**   variants/parwa_high/agents/safety_agent.py             base_agent.py (Wk9)    Test: safety
                                                                                        check blocks
                                                                                        unsafe responses
  ------- ------------------------------------------------------ ---------------------- -----------------

**Day 3 --- PARWA High tools + workflows chain**

  ------- ----------------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                         **Depends On**         **Unit Test /
  3**                                                                                  Notes**

  **1**   variants/parwa_high/tools/analytics_engine.py         analytics_service.py   Test: insights
                                                                (Wk4)                  generated

  **2**   variants/parwa_high/tools/team_coordination.py        base_agent.py (Wk9)    Test: team
                                                                                       coordinated
                                                                                       correctly

  **3**   variants/parwa_high/tools/customer_success_tools.py   base_agent.py (Wk9)    Test: success
                                                                                       tools run

  **4**   variants/parwa_high/workflows/video_support.py        High agents (D1-D2     Test: video
                                                                above)                 workflow starts

  **5**   variants/parwa_high/workflows/analytics.py            High agents (D1-D2     Test: analytics
                                                                above)                 workflow runs

  **6**   variants/parwa_high/workflows/coordination.py         High agents (D1-D2     Test:
                                                                above)                 coordination
                                                                                       workflow manages
                                                                                       load

  **7**   variants/parwa_high/workflows/customer_success.py     High agents (D1-D2     Test: success
                                                                above)                 workflow runs
  ------- ----------------------------------------------------- ---------------------- -----------------

**Day 4 --- PARWA High tasks + DB migration**

  ------- -------------------------------------------------- ----------------------- -----------------
  **DAY   **Files to Build (in order)**                      **Depends On**          **Unit Test /
  4**                                                                                Notes**

  **1**   variants/parwa_high/tasks/video_call.py            High agents (D1-D2)     Test: video call
                                                                                     task runs

  **2**   variants/parwa_high/tasks/generate_insights.py     High agents (D1-D2)     Test: insights
                                                                                     generated with
                                                                                     risk score

  **3**   variants/parwa_high/tasks/coordinate_teams.py      High agents (D1-D2)     Test: teams
                                                                                     coordinated

  **4**   variants/parwa_high/tasks/customer_success.py      High agents (D1-D2)     Test: success
                                                                                     tasks complete

  **5**   tests/unit/test_parwa_high_agents.py               High agents (D1-D2      PUSH ONLY AFTER
                                                             above)                  THIS PASSES

  **6**   tests/unit/test_parwa_high_workflows.py            High workflows (D3      PUSH ONLY AFTER
                                                             above)                  THIS PASSES

  **7**   database/migrations/versions/006_multi_region.py   001_initial_schema.py   Test: migration
                                                             (Wk2)                   runs without
                                                                                     errors
  ------- -------------------------------------------------- ----------------------- -----------------

**Day 5 --- All 3 variants coexistence + BDD tests**

  ------- -------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                **Depends On**         **Unit Test /
  5**                                                                         Notes**

  **1**   tests/integration/test_week6_parwa_high.py   All 3 variants (Wks    Test: same ticket
                                                       9-11)                  through all 3
                                                                              variants

  **2**   tests/integration/test_full_system.py        All variants (Wks      Skeleton full
                                                       9-11)                  system test

  **3**   tests/bdd/test_mini_scenarios.py             Mini variant (Wk9)     BDD: all Mini
                                                                              scenarios pass

  **4**   tests/bdd/test_parwa_scenarios.py            PARWA variant (Wk10)   BDD: all PARWA
                                                                              scenarios pass

  **5**   tests/bdd/test_parwa_high_scenarios.py       PARWA High (Wk11       BDD: all High
                                                       D1-D4)                 scenarios pass
  ------- -------------------------------------------- ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_week6_parwa_high.py -v         |
|                                                                       |
| • All 3 variants import simultaneously with zero conflicts            |
|                                                                       |
| • PARWA High: churn prediction output contains risk score             |
|                                                                       |
| • PARWA High: video agent initialises correctly                       |
|                                                                       |
| • Same ticket through all 3: Mini collects, PARWA recommends, High    |
| executes on approval                                                  |
|                                                                       |
| • BDD scenarios: all pass for all 3 variants                          |
|                                                                       |
| • DB migration 006: runs without errors                               |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. All 3 variants (Mini, PARWA, PARWA High) coexist and function     |
|                                                                       |
| 2\. BDD scenarios pass for all 3 variants                             |
|                                                                       |
| 3\. All unit tests pass before push                                   |
|                                                                       |
| 4\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 12 --- Phase 3 --- Variants & Integrations**

**Build all backend services: approval, escalation, industry c\...**

Build all backend services: approval, escalation, industry configs,
Jarvis, webhooks, E2E tests. Days run in parallel.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- Industry configs + Jarvis commands chain**

  ------- --------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                 **Depends On**         **Unit Test /
  1**                                                                          Notes**

  **1**   backend/core/jarvis_commands.py               cache.py, security.py  Test:
                                                        (Wks 1-3)              pause_refunds
                                                                               Redis key set
                                                                               within 500ms

  **2**   backend/core/industry_configs/ecommerce.py    config.py (Wk1)        Test: ecommerce
                                                                               config loads

  **3**   backend/core/industry_configs/saas.py         config.py (Wk1)        Test: saas config
                                                                               loads

  **4**   backend/core/industry_configs/healthcare.py   config.py,             Test: healthcare
                                                        healthcare_guard.py    config + BAA
                                                        (Wks 1-7)              check

  **5**   backend/core/industry_configs/logistics.py    config.py (Wk1)        Test: logistics
                                                                               config loads

  **6**   backend/api/incoming_calls.py                 config.py (Wk1)        Test: call
                                                                               answered in \<6s,
                                                                               never IVR-only

  **7**   backend/services/voice_handler.py             incoming_calls.py      Test: 5-step call
                                                        (same day above)       flow runs
  ------- --------------------------------------------- ---------------------- -----------------

**Day 2 --- Approval + escalation services chain**

  ------- ---------------------------------------- ---------------------- ------------------
  **DAY   **Files to Build (in order)**            **Depends On**         **Unit Test /
  2**                                                                     Notes**

  **1**   backend/services/approval_service.py     support_ticket model,  Test:
                                                   stripe_client.py (Wks  pending_approval
                                                   3-7)                   created, Stripe
                                                                          NOT called

  **2**   backend/services/escalation_ladder.py    approval_service.py    Test: 4-phase
                                                   (same day above)       escalation fires
                                                                          at correct hours

  **3**   backend/services/escalation_service.py   support_ticket model   Test: escalation
                                                   (Wk3)                  service runs

  **4**   backend/services/license_service.py      license model (Wk3)    Test: license
                                                                          checked correctly

  **5**   backend/services/sla_service.py          sla_breach model (Wk3) Test: SLA breach
                                                                          detected
  ------- ---------------------------------------- ---------------------- ------------------

**Day 3 --- Webhook handlers + automation + NLP chain**

  ------- --------------------------------------------- ---------------------- --------------------------------------
  **DAY   **Files to Build (in order)**                 **Depends On**         **Unit Test / Notes**
  3**                                                                          

  **1**   backend/api/webhooks/twilio.py                hmac_verification.py   Test: bad HMAC returns 401
                                                        (Wk3)                  

  **2**   backend/api/automation.py                     all agents (Wks 9-11)  Test: automation endpoint works

  **3**   backend/services/manager_time_calculator.py   pricing_optimizer.py   Test: formula correct
                                                        (Wk1)                  

  **4**   backend/services/non_financial_undo.py        audit_trail.py (Wk2),  Test: non-money action undone, logged
                                                        Redis (Wk1)            

  **5**   backend/nlp/command_parser.py                 config.py (Wk1)        Test: Add 2 Mini →
                                                                               {action:provision,count:2,type:mini}
  ------- --------------------------------------------- ---------------------- --------------------------------------

**Day 4 --- E2E test files chain**

  ------- ------------------------------------------- ----------------------- ------------------------
  **DAY   **Files to Build (in order)**               **Depends On**          **Unit Test / Notes**
  4**                                                                         

  **1**   tests/e2e/test_onboarding_flow.py           All backend services    E2E:
                                                      (Wks 4-12)              signup→onboarding→live

  **2**   tests/e2e/test_refund_workflow.py           approval_service.py (D2 E2E: Stripe called
                                                      above)                  EXACTLY once after
                                                                              approval

  **3**   tests/e2e/test_jarvis_commands.py           jarvis_commands.py (D1  E2E: pause_refunds Redis
                                                      above)                  key within 500ms

  **4**   tests/e2e/test_stuck_ticket_escalation.py   escalation_service.py   E2E: 4-phase fires at
                                                      (D2 above)              24h/48h/72h thresholds
  ------- ------------------------------------------- ----------------------- ------------------------

**Day 5 --- More E2E + NLP provisioner + voice tests**

  ------- ------------------------------------ ---------------------- -----------------
  **DAY   **Files to Build (in order)**        **Depends On**         **Unit Test /
  5**                                                                 Notes**

  **1**   tests/e2e/test_agent_lightning.py    training_data model    E2E: full
                                               (Wk3)                  training cycle

  **2**   tests/e2e/test_gdpr_compliance.py    gdpr_engine.py (Wk7)   E2E: PII
                                                                      anonymised, row
                                                                      preserved

  **3**   backend/nlp/provisioner.py           command_parser.py (D3  Test: agents spun
                                               above)                 up, billing
                                                                      updated

  **4**   backend/nlp/intent_classifier.py     command_parser.py (D3  Test: intent
                                               above)                 classified
                                                                      correctly

  **5**   tests/voice/test_incoming_calls.py   incoming_calls.py,     Test: answer
                                               voice_handler.py (D1)  \<6s, recording
                                                                      disclosure fires
  ------- ------------------------------------ ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/e2e/test_refund_workflow.py                     |
| tests/e2e/test_jarvis_commands.py                                     |
| tests/integration/test_week12_backend.py -v                           |
|                                                                       |
| • Refund E2E: Stripe called exactly once --- after approval, NEVER    |
| before                                                                |
|                                                                       |
| • Audit trail: hash chain validates after approval event              |
|                                                                       |
| • Stuck ticket: 4-phase escalation fires at exact 24h/48h/72h         |
| thresholds                                                            |
|                                                                       |
| • Jarvis: pause_refunds Redis key set within 500ms                    |
|                                                                       |
| • GDPR: export complete, deletion anonymises PII, row preserved       |
|                                                                       |
| • Incoming calls: answered in \<6 seconds, never IVR-only             |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. Full approval + escalation system functional                      |
|                                                                       |
| 2\. Refund gate verified: Stripe called EXACTLY once after approval   |
|                                                                       |
| 3\. Jarvis commands working                                           |
|                                                                       |
| 4\. GDPR compliance working                                           |
|                                                                       |
| 5\. All unit tests pass before push                                   |
|                                                                       |
| 6\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 13 --- Phase 3 --- Variants & Integrations**

**Build Agent Lightning training system and all background wor\...**

Build Agent Lightning training system and all background workers. Days
run in parallel.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- Data export + model registry chain**

  ------- ---------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                  **Depends On**         **Unit Test /
  1**                                                                           Notes**

  **1**   agent_lightning/data/export_mistakes.py        training_data model    Test: mistakes
                                                         (Wk3)                  exported in
                                                                                correct format

  **2**   agent_lightning/data/export_approvals.py       training_data model    Test: approvals
                                                         (Wk3)                  exported

  **3**   agent_lightning/data/dataset_builder.py        export_mistakes.py,    Test: JSONL
                                                         export_approvals.py    dataset built
                                                         (same day above)       correctly

  **4**   agent_lightning/deployment/model_registry.py   config.py (Wk1)        Test: model
                                                                                version
                                                                                registered
  ------- ---------------------------------------------- ---------------------- -----------------

**Day 2 --- Training pipeline chain**

  ------- ----------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                   **Depends On**         **Unit Test /
  2**                                                                            Notes**

  **1**   agent_lightning/training/trainer.py             config.py (Wk1) ---    Test: trainer
                                                          uses Unsloth+Colab     initialises
                                                          FREE                   

  **2**   agent_lightning/training/unsloth_optimizer.py   trainer.py (same day   Test: Unsloth
                                                          above)                 optimiser applies

  **3**   agent_lightning/deployment/deploy_model.py      model_registry.py      Test: model
                                                          (Wk13 D1)              deployed to
                                                                                 registry

  **4**   agent_lightning/deployment/rollback.py          model_registry.py      Test: rollback
                                                          (Wk13 D1)              restores previous
                                                                                 version
  ------- ----------------------------------------------- ---------------------- -----------------

**Day 3 --- Fine tune + validation + monitoring chain**

  ------- ------------------------------------------------ ---------------------- -----------------
  **DAY   **Files to Build (in order)**                    **Depends On**         **Unit Test /
  3**                                                                             Notes**

  **1**   agent_lightning/training/fine_tune.py            trainer.py,            Test: fine tune
                                                           unsloth_optimizer.py   runs on test
                                                           (D2 above)             dataset

  **2**   agent_lightning/training/validate.py             trainer.py (D2 above)  Test: blocks
                                                                                  deployment at
                                                                                  89%, allows at
                                                                                  91%

  **3**   agent_lightning/monitoring/drift_detector.py     model_registry.py (D1  Test: drift
                                                           above)                 detected after
                                                                                  model change

  **4**   agent_lightning/monitoring/accuracy_tracker.py   model_registry.py (D1  Test: accuracy
                                                           above)                 tracked per
                                                                                  category
  ------- ------------------------------------------------ ---------------------- -----------------

**Day 4 --- Background workers chain**

  ------- -------------------------------- ----------------------- -----------------
  **DAY   **Files to Build (in order)**    **Depends On**          **Unit Test /
  4**                                                              Notes**

  **1**   workers/worker.py                config.py,              Test: ARQ worker
                                           message_queue.py (Wks   registers
                                           1-2)                    

  **2**   workers/batch_approval.py        escalation_service.py   Test: batch
                                           (Wk12)                  processes
                                                                   correctly

  **3**   workers/training_job.py          fine_tune.py (D3 above) Test: training
                                                                   job triggered

  **4**   workers/cleanup.py               gdpr_engine.py (Wk7)    Test: cleanup
                                                                   runs, PII
                                                                   anonymised

  **5**   backend/services/burst_mode.py   billing_service.py      Test: burst mode
                                           (Wk4), feature_flags/   activates,
                                           (Wk1)                   billing updated
  ------- -------------------------------- ----------------------- -----------------

**Day 5 --- Remaining workers + Quality Coach chain**

  ------- ----------------------------------- ------------------------- -----------------------------
  **DAY   **Files to Build (in order)**       **Depends On**            **Unit Test / Notes**
  5**                                                                   

  **1**   workers/recall_handler.py           cache.py (Wk2)            Test: recall stops non-money
                                                                        actions

  **2**   workers/proactive_outreach.py       notification_service.py   Test: outreach sent
                                              (Wk4)                     proactively

  **3**   workers/report_generator.py         analytics_service.py      Test: report generated
                                              (Wk4)                     

  **4**   workers/kb_indexer.py               rag_pipeline.py (Wk5)     Test: KB indexed correctly

  **5**   backend/quality_coach/analyzer.py   config.py (Wk1)           Test: scores
                                                                        accuracy/empathy/efficiency

  **6**   backend/quality_coach/reporter.py   analyzer.py (same day     Test: weekly report generated
                                              above)                    

  **7**   backend/quality_coach/notifier.py   analyzer.py (same day     Test: real-time alert fires
                                              above)                    
  ------- ----------------------------------- ------------------------- -----------------------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/e2e/test_agent_lightning.py                     |
| tests/integration/test_week13_workers.py -v                           |
|                                                                       |
| • Dataset builder: exports correct JSONL format with 50+ mistakes     |
|                                                                       |
| • validate.py: blocks deployment at \<90% accuracy                    |
|                                                                       |
| • validate.py: allows deployment at 91%+ accuracy                     |
|                                                                       |
| • New model version registered in model_registry after deployment     |
|                                                                       |
| • All 8 workers start and register with ARQ without errors            |
|                                                                       |
| • Burst mode: activates instantly, billing updated, auto-expires      |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. Full Agent Lightning training cycle works end-to-end              |
|                                                                       |
| 2\. All background workers running                                    |
|                                                                       |
| 3\. Quality Coach scoring conversations                               |
|                                                                       |
| 4\. All unit tests pass before push                                   |
|                                                                       |
| 5\. GitHub CI pipeline green                                          |
+-----------------------------------------------------------------------+

**Week 14 --- Phase 3 --- Variants & Integrations**

**Build all monitoring dashboards, alerts, performance tests, \...**

Build all monitoring dashboards, alerts, performance tests, and complete
Phase 1-3 validation. Days run in parallel.

+-----------------------------------------------------------------------+
| PARALLEL RULE: All 5 days run simultaneously. Each day\'s files only  |
| depend on previous weeks or earlier files within the same day.        |
|                                                                       |
| Each Zai agent gets one day\'s task. Agent builds files sequentially  |
| in the order listed. Commits each file after its unit test passes.    |
+-----------------------------------------------------------------------+

**Day 1 --- Grafana dashboards (all independent --- no cross-day deps)**

  ------- --------------------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                             **Depends On**         **Unit Test /
  1**                                                                                      Notes**

  **1**   monitoring/grafana-dashboards/main-dashboard.json         None --- config only   Verify: loads in
                                                                                           Grafana without
                                                                                           errors

  **2**   monitoring/grafana-dashboards/mcp-dashboard.json          None --- config only   Verify: MCP
                                                                                           metrics shown

  **3**   monitoring/grafana-dashboards/compliance-dashboard.json   None --- config only   Verify:
                                                                                           compliance
                                                                                           metrics shown

  **4**   monitoring/grafana-dashboards/sla-dashboard.json          None --- config only   Verify: SLA
                                                                                           metrics shown

  **5**   monitoring/grafana-dashboards/quality.json                None --- config only   Verify: quality
                                                                                           coach metrics
                                                                                           shown
  ------- --------------------------------------------------------- ---------------------- -----------------

**Day 2 --- Alert rules + logging config (independent)**

  ------- ----------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                   **Depends On**         **Unit Test /
  2**                                                                            Notes**

  **1**   monitoring/alerts.yml                           prometheus.yml (Wk8)   Test: all 6
                                                                                 alerts fire on
                                                                                 simulated
                                                                                 conditions

  **2**   monitoring/grafana-config.yml                   None --- config only   Verify: Grafana
                                                                                 config valid

  **3**   monitoring/logs/structured-logging-config.yml   logger.py (Wk1)        Verify: logs in
                                                                                 JSON format

  **4**   docs/runbook.md                                 None                   Doc only
  ------- ----------------------------------------------- ---------------------- -----------------

**Day 3 --- Performance + BDD + integration test files**

  ------- --------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                 **Depends On**         **Unit Test /
  3**                                                                          Notes**

  **1**   tests/performance/test_load.py                All backend APIs (Wks  Test: P95 \<500ms
                                                        4-12)                  at 50 concurrent
                                                                               users

  **2**   tests/ui/test_approval_queue.py               None --- UI test       Test: approval
                                                                               queue renders

  **3**   tests/ui/test_roi_calculator.py               None --- UI test       Test: ROI
                                                                               calculator
                                                                               correct

  **4**   tests/ui/test_jarvis_terminal.py              None --- UI test       Test: Jarvis
                                                                               terminal works

  **5**   tests/bdd/test_mini_scenarios.py (complete)   Mini variant (Wk9)     BDD: complete
                                                                               scenario suite

  **6**   tests/integration/test_week4_backend_api.py   All APIs (Wks 4-12)    Integration: full
                                                                               API layer tested
  ------- --------------------------------------------- ---------------------- -----------------

**Day 4 --- Industry-specific integration tests (independent)**

  ------- ----------------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**                   **Depends On**         **Unit Test /
  4**                                                                            Notes**

  **1**   tests/integration/test_ecommerce_industry.py    ecommerce config       Integration:
                                                          (Wk12)                 ecommerce flow
                                                                                 works

  **2**   tests/integration/test_saas_industry.py         saas config (Wk12)     Integration: SaaS
                                                                                 flow works

  **3**   tests/integration/test_healthcare_industry.py   healthcare config      Integration:
                                                          (Wk12)                 HIPAA enforced

  **4**   tests/integration/test_logistics_industry.py    logistics config       Integration:
                                                          (Wk12)                 logistics flow
                                                                                 works
  ------- ----------------------------------------------- ---------------------- -----------------

**Day 5 --- Full system test + Dockerfiles + PROJECT_STATE**

  ------- --------------------------------------- ---------------------- -----------------
  **DAY   **Files to Build (in order)**           **Depends On**         **Unit Test /
  5**                                                                    Notes**

  **1**   tests/integration/test_full_system.py   Everything (Wks 1-13)  Full system: all
          (complete)                                                     3 variants +
                                                                         backend + workers

  **2**   infra/docker/frontend.Dockerfile        None --- Docker config Test: builds
                                                                         under 500MB

  **3**   docker-compose.prod.yml (update)        All Dockerfiles        Test: all
                                                                         services start
                                                                         healthy

  **4**   PROJECT_STATE.md (Phase 1-3 complete    None                   State: marks
          marker)                                                        Phases 1-3
                                                                         complete
  ------- --------------------------------------- ---------------------- -----------------

+-----------------------------------------------------------------------+
| **🧪 DAY 6 --- TESTER AGENT --- FULL WEEK TEST**                      |
|                                                                       |
| Command: pytest tests/integration/test_full_system.py                 |
| tests/performance/test_load.py -v                                     |
|                                                                       |
| • pytest tests/integration/test_full_system.py: all tests pass        |
|                                                                       |
| • P95 latency \<500ms at 50 concurrent users (Locust)                 |
|                                                                       |
| • All 6 monitoring alerts fire correctly on simulated conditions      |
|                                                                       |
| • All 4 industry configurations work without errors                   |
|                                                                       |
| • docker-compose.prod.yml starts all services healthy                 |
|                                                                       |
| • BDD: all Mini scenarios pass completely                             |
|                                                                       |
| • Safety: guardrails.py blocks hallucination, competitor mention, PII |
+-----------------------------------------------------------------------+

+-----------------------------------------------------------------------+
| **✅ WEEK COMPLETE WHEN ALL PASS:**                                   |
|                                                                       |
| 1\. Phases 1-3 complete: full system validated                        |
|                                                                       |
| 2\. P95 \<500ms at 50 concurrent users                                |
|                                                                       |
| 3\. All monitoring alerts firing correctly                            |
|                                                                       |
| 4\. All unit tests pass before push                                   |
|                                                                       |
| 5\. GitHub CI pipeline green --- Phase 1-3 gate PASSED                |
+-----------------------------------------------------------------------+

**Weeks 15-60 --- Compact Roadmap**

Weeks 15-60 follow the same parallel-agent structure. Each week shows:
the goal, how files are grouped across 5 days, the Tester Agent\'s
week-end test command, and pass criteria.

**Week 15 --- Frontend Foundation (Phase 4)**

Build Next.js config → layout → landing page → UI primitives (Day 1
chain). Common UI + auth pages (Day 2 chain). Variant cards (Day 3
chain). Stores + API service (Day 4 chain). Onboarding components (Day 5
chain).

  ------------- ---------------------------------------------------------
  **Tester      npm run test \-- tests/ui/ && pytest
  Command**     tests/integration/test_week15_frontend.py

  **Pass 1**    Next.js dev server starts without errors

  **Pass 2**    All 3 variant cards render correctly

  **Pass 3**    Auth pages render and validate

  **Pass 4**    Onboarding wizard 5-step flow works

  **Pass 5**    All Zustand stores initialise
  ------------- ---------------------------------------------------------

**Week 16 --- Dashboard Pages + Hooks (Phase 4)**

Dashboard layout → home page (Day 1 chain). Tickets + approvals +
agents + analytics pages (Day 2 chain). Dashboard components (Day 3
chain). All hooks (Day 4 chain). Remaining settings pages (Day 5 chain).

  ------------- ---------------------------------------------------------
  **Tester      npm run test && pytest
  Command**     tests/integration/test_week16_dashboard.py

  **Pass 1**    Dashboard home loads real API data

  **Pass 2**    Approvals queue renders and approve action works

  **Pass 3**    Jarvis terminal streams response

  **Pass 4**    All 5 hooks update stores correctly
  ------------- ---------------------------------------------------------

**Week 17 --- Onboarding + Analytics + Frontend Wiring (Phase 4)**

Onboarding + pricing + analytics components (Day 1 chain). Settings
sub-pages (Day 2 chain). Frontend tests (Day 3 chain). Frontend →
backend service wiring (Day 4 chain). E2E frontend tests (Day 5 chain).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/e2e/test_frontend_full_flow.py
  Command**     

  **Pass 1**    Full UI: login→onboarding→dashboard works

  **Pass 2**    Approve refund through UI: Stripe called exactly once

  **Pass 3**    Analytics page loads real backend data

  **Pass 4**    Lighthouse score \>80
  ------------- ---------------------------------------------------------

**Week 18 --- Production Hardening + Kubernetes (Phase 4)**

Full test suite runs (Day 1 parallel: unit/integration/E2E/BDD).
Security + performance scans (Day 2 parallel). Prod Docker builds (Day 3
parallel). K8s manifests (Day 4 parallel). Final docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/ && snyk test && locust -f
  Command**     tests/performance/test_load.py \--headless -u 100

  **Pass 1**    pytest tests/: 100% pass rate

  **Pass 2**    Zero critical CVEs on all Docker images

  **Pass 3**    OWASP: all 10 checks pass

  **Pass 4**    RLS: 10 cross-tenant isolation tests all return 0 rows

  **Pass 5**    P95 \<500ms at 100 concurrent users

  **Pass 6**    Full client journey: signup→onboarding→ticket→approval
                works
  ------------- ---------------------------------------------------------

**Week 19 --- First Client Onboarding + Real Validation (Phase 5)**

Client setup files --- config + KB ingestion + monitoring (Day 1
parallel). Shadow mode validation (Day 2 parallel). Bug fixes from real
usage (Day 3 parallel). Optimisation (Day 4 parallel). Reports (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_shadow_mode.py
  Command**     tests/performance/baseline_metrics.py

  **Pass 1**    50 tickets processed in Shadow Mode without critical
                errors

  **Pass 2**    Accuracy baseline established (target \>72%)

  **Pass 3**    P95 \<500ms on real client data

  **Pass 4**    No cross-tenant data leaks in real usage
  ------------- ---------------------------------------------------------

**Week 20 --- Second Client + Agent Lightning First Run (Phase 5)**

Client 2 setup (Day 1 parallel). Agent Lightning first real training run
--- export→fine_tune→validate→deploy (Day 2 chain). Post-training
validation (Day 3 parallel). Scaling tests (Day 4 parallel). Reports
(Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_multi_client_isolation.py
  Command**     && pytest tests/

  **Pass 1**    2-client cross-tenant isolation: 0 data leaks in 20 tests

  **Pass 2**    Agent Lightning: accuracy improved ≥3% from baseline

  **Pass 3**    New model passes all regression tests

  **Pass 4**    P95 \<500ms at 100 concurrent users
  ------------- ---------------------------------------------------------

**Week 21 --- Clients 3-5 + Collective Intelligence (Phase 6)**

Clients 3-5 configs + KB (Day 1 parallel). Agent Lightning week 3 run
(Day 2 chain). Collective intelligence improvements (Day 3 chain).
Performance optimisation (Day 4 parallel). New industry verticals (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_5_client_isolation.py
  Command**     

  **Pass 1**    5-client isolation: 0 data leaks across 50 cross-tenant
                tests

  **Pass 2**    Agent Lightning accuracy ≥77%

  **Pass 3**    Redis cache hit rate \>70%

  **Pass 4**    Light tier \>88% of queries
  ------------- ---------------------------------------------------------

**Week 22 --- Clients 6-10 + 85% Accuracy Milestone (Phase 6)**

Clients 6-10 configs (Day 1 parallel). Agent Lightning week 6 run
targeting 85% (Day 2 chain). Platform hardening scans (Day 3 parallel).
10-client performance tests (Day 4 parallel). Milestone docs (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_10_client_isolation.py &&
  Command**     locust -u 500

  **Pass 1**    10-client isolation: 0 data leaks in 100 tests

  **Pass 2**    Agent Lightning ≥85% accuracy

  **Pass 3**    500 concurrent users P95 \<500ms

  **Pass 4**    Horizontal scaling: 2nd backend pod handles traffic
  ------------- ---------------------------------------------------------

**Week 23 --- Frontend Polish --- A11y + Mobile + Dark Mode (Phase 7)**

A11y + mobile + dark mode + error states (Day 1 parallel, diff
components). Loading/empty states/toast/form validation (Day 2
parallel). Dashboard component improvements (Day 3 parallel).
Performance optimisation (Day 4 parallel). Frontend tests (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      npm run test && lighthouse \--output json
  Command**     

  **Pass 1**    Lighthouse score \>90 on all key pages

  **Pass 2**    axe-core: zero accessibility violations

  **Pass 3**    Responsive: correct at mobile/tablet/desktop

  **Pass 4**    Dark mode: all pages switch correctly
  ------------- ---------------------------------------------------------

**Week 24 --- Client Success Tooling (Phase 7)**

Health score + churn + NPS + success metrics services (Day 1 parallel).
API endpoints for new services (Day 2 parallel). Frontend success
widgets (Day 3 parallel). Workers + alert rules (Day 4 parallel). Tests
(Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_client_success.py
  Command**     

  **Pass 1**    Health score calculates correctly

  **Pass 2**    Churn alert fires when score drops

  **Pass 3**    NPS survey sends after ticket resolution

  **Pass 4**    Monday report includes health scores
  ------------- ---------------------------------------------------------

**Week 25 --- Financial Services Industry Vertical (Phase 7)**

FS config + compliance + feature flags + BDD (Day 1 parallel). FS
integrations (Plaid, Salesforce, Bloomberg) (Day 2 parallel). FS
agents + workflows (Day 3 chain). FS monitoring + AML (Day 4 parallel).
FS tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_financial_services.py
  Command**     

  **Pass 1**    FS onboarding: industry config loads correctly

  **Pass 2**    AML: high-value transaction triggers enhanced review

  **Pass 3**    FS compliance rules: correct jurisdiction applied

  **Pass 4**    Plaid client: mock connection initialises
  ------------- ---------------------------------------------------------

**Week 26 --- Performance Deep Optimisation --- P95 \<300ms (Phase 7)**

Multi-level Redis caching + response/query/KB cache (Day 1 chain). DB
indexes + slow query + pool tuning (Day 2 chain). AI routing
optimisation (Day 3 chain). Worker concurrency + async + batch (Day 4
chain). Performance benchmarks (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      locust -u 200 && pytest tests/performance/
  Command**     

  **Pass 1**    P95 \<300ms at 200 concurrent users

  **Pass 2**    Cache hit rate \>75%

  **Pass 3**    Light tier routing \>90%

  **Pass 4**    Zero DB queries \>100ms
  ------------- ---------------------------------------------------------

**Week 27 --- 20-Client Scale Validation (Phase 7)**

Clients 11-20 configs (Day 1 parallel). 20-client test infrastructure
(Day 2 parallel). Agent Lightning week 12 run (Day 3 chain).
Infrastructure scaling (Day 4 parallel). Reports (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_20_client_isolation.py &&
  Command**     pytest tests/performance/test_20_client_load.py

  **Pass 1**    20-client isolation: 0 data leaks in 200 tests

  **Pass 2**    500 concurrent users P95 \<300ms

  **Pass 3**    Agent Lightning ≥88% accuracy

  **Pass 4**    Redis HA: failover in \<10 seconds
  ------------- ---------------------------------------------------------

**Week 28 --- Agent Lightning 90% Milestone (Phase 8)**

Training pipeline optimisations (Day 1 parallel). Collective
intelligence improvements (Day 2 parallel). Model versioning + A/B
testing + auto-rollback (Day 3 chain). 90% accuracy target training run
(Day 4 chain). Tests + docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/unit/test_training_pipeline.py && pytest
  Command**     tests/integration/test_ab_testing.py

  **Pass 1**    Agent Lightning accuracy ≥90%

  **Pass 2**    A/B test: new model serves 10% of traffic correctly

  **Pass 3**    Auto-rollback: fires within 60 seconds of drift

  **Pass 4**    Collective intelligence: no PII in cross-client data
  ------------- ---------------------------------------------------------

**Week 29 --- Multi-Region Data Residency (Phase 8)**

Terraform per region --- EU/US/APAC + config (Day 1 parallel). App-layer
residency enforcement (Day 2 chain). Cross-region replication (Day 3
parallel). Compliance docs (Day 4 parallel). Region tests (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_eu_data_residency.py
  Command**     tests/integration/test_cross_region_isolation.py

  **Pass 1**    EU client data absent from US region DB

  **Pass 2**    Cross-region isolation: 0 leaks in 50 tests

  **Pass 3**    DB replication lag \<500ms

  **Pass 4**    GDPR export: only data from client\'s assigned region
  ------------- ---------------------------------------------------------

**Week 30 --- 30-Client Milestone (Phase 8)**

Clients 21-30 configs (Day 1 parallel). Full regression all test suites
(Day 2 parallel). Security re-audit (Day 3 parallel). Agent Lightning
week 15 run + 30-client load test (Day 4 parallel). Docs (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/ && locust -u 1000
  Command**     

  **Pass 1**    300 cross-tenant isolation tests: 0 data leaks

  **Pass 2**    1000 concurrent users P95 \<300ms

  **Pass 3**    Agent Lightning ≥91%

  **Pass 4**    Full regression: 100% pass rate

  **Pass 5**    OWASP clean, CVEs zero critical
  ------------- ---------------------------------------------------------

**Week 31 --- E-commerce Advanced Features (Phase 8)**

Shopify v2 + cart recovery agent + inventory agent + worker (Day 1
parallel). Cart+inventory workflows + WooCommerce + Magento clients (Day
2 parallel). E-commerce MCPs (Day 3 parallel). E-commerce frontend (Day
4 parallel). Tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_ecommerce_advanced.py
  Command**     

  **Pass 1**    Cart recovery: email sent within 1 hour of abandonment

  **Pass 2**    Inventory: out-of-stock proactive notification

  **Pass 3**    WooCommerce client: mock connection initialises
  ------------- ---------------------------------------------------------

**Week 32 --- SaaS Advanced Features (Phase 8)**

GitHub v2 + Zendesk v2 + Intercom + PagerDuty clients (Day 1 parallel).
Bug triage + deployment agents + workflows (Day 2 chain). SaaS MCPs +
monitoring (Day 3 parallel). SaaS frontend + DB migration (Day 4
parallel). Tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_saas_advanced.py
  Command**     

  **Pass 1**    Deployment event: customer notification in 2 minutes

  **Pass 2**    Bug triage: P0 triggers PagerDuty

  **Pass 3**    Zendesk: ticket auto-created from GitHub issue
  ------------- ---------------------------------------------------------

**Week 33 --- Healthcare HIPAA + Logistics (Phase 8)**

HIPAA audit + Epic EHR v2 + AfterShip v2 + Freight client (Day 1
parallel). Healthcare + logistics agents (Day 2 parallel). Workflows +
logistics MCP (Day 3 chain). BAA + compliance docs (Day 4 parallel).
Tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_hipaa_compliance.py
  Command**     tests/integration/test_logistics_advanced.py

  **Pass 1**    HIPAA: PHI absent from all log files

  **Pass 2**    BAA check: healthcare client without BAA blocked

  **Pass 3**    Shipment: real-time update triggers notification
  ------------- ---------------------------------------------------------

**Week 34 --- Frontend v2 --- React Query + PWA + UX (Phase 8)**

React Query + optimistic UI + infinite scroll + command palette (Day 1
parallel). New dashboard widgets (Day 2 parallel). Auth improvements +
onboarding v2 (Day 3 parallel). PWA + touch gestures + offline support
(Day 4 parallel). Tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      npm run test && lighthouse
  Command**     

  **Pass 1**    Lighthouse: all pages \>92

  **Pass 2**    PWA: offline action queued and syncs

  **Pass 3**    Approval swipe: gesture triggers API

  **Pass 4**    Command palette: finds any page in \<100ms
  ------------- ---------------------------------------------------------

**Week 35 --- Smart Router 92%+ Optimisation (Phase 8)**

Router ML model + query fingerprinting + tier budget + analytics (Day 1
chain). TRIVYA optimisations (Day 2 parallel). Collective intelligence
improvements (Day 3 chain). Tests + benchmarks (Day 4 parallel). Reports
(Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/unit/test_smart_router.py
  Command**     tests/performance/test_token_usage.py

  **Pass 1**    Light tier routing: \>92% of 1000 test queries

  **Pass 2**    Token budget: enforced across all clients

  **Pass 3**    CLARA latency: \<200ms

  **Pass 4**    ML classifier: \>85% accuracy
  ------------- ---------------------------------------------------------

**Week 36 --- Agent Lightning 94% Accuracy Milestone (Phase 8)**

Per-category specialist models --- refund/VIP/technical + category
router (Day 1 chain). Training data improvements (Day 2 parallel). 94%
accuracy run --- build dataset→fine tune→validate→deploy (Day 3 chain).
Monitoring + reports (Day 4 parallel). Tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/unit/test_category_specialists.py && pytest
  Command**     tests/

  **Pass 1**    Refund specialist: ≥94% on refund test set

  **Pass 2**    VIP specialist: ≥94% on VIP test set

  **Pass 3**    Technical specialist: ≥94% on technical test set

  **Pass 4**    Category router: correct specialist \>97%
  ------------- ---------------------------------------------------------

**Week 37 --- 50-Client Scale + Autoscaling (Phase 8)**

Clients 31-50 configs (Day 1 parallel). 50-client test infrastructure
(Day 2 parallel). K8s HPA + KEDA + PgBouncer + VPA (Day 3 chain). Cost
optimisation (Day 4 parallel). Docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_50_client_isolation.py
  Command**     tests/performance/test_50_client_load.py

  **Pass 1**    500 cross-tenant isolation: 0 leaks

  **Pass 2**    2000 concurrent users P95 \<300ms

  **Pass 3**    K8s HPA: backend scales to 10+ pods

  **Pass 4**    KEDA: workers scale with queue depth
  ------------- ---------------------------------------------------------

**Week 38 --- Enterprise Pre-Preparation (Phase 8)**

SSO + SCIM stubs + enterprise billing + onboarding (Day 1 parallel).
Security hardening (Day 2 parallel). Enterprise compliance docs (Day 3
parallel). Enterprise frontend (Day 4 parallel). Tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/unit/test_sso_stub.py
  Command**     tests/unit/test_audit_export.py
                tests/integration/test_enterprise_security.py

  **Pass 1**    SSO stub: returns correct SAML placeholder

  **Pass 2**    Audit log CSV: all required fields exported

  **Pass 3**    Enterprise billing: contract invoice generated

  **Pass 4**    IP allowlist: non-whitelisted IP blocked
  ------------- ---------------------------------------------------------

**Week 39 --- Final Production Readiness Preparation (Phase 8)**

Outstanding issue fixes (Day 1 parallel). Final documentation (Day 2
parallel). Final security audit (Day 3 parallel). Final performance
benchmarks (Day 4 parallel). Production readiness checklists (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/ && snyk test && locust -u 100
  Command**     

  **Pass 1**    OWASP clean, CVEs zero critical

  **Pass 2**    RLS: 500 cross-tenant tests --- 0 leaks

  **Pass 3**    P95 \<300ms at 100 concurrent

  **Pass 4**    Agent Lightning ≥94%

  **Pass 5**    Full test suite: 100% pass rate
  ------------- ---------------------------------------------------------

**Week 40 --- Weeks 1-40 Final Validation + Enterprise Demo (Phase 8)**

Full test suite run (Day 1 parallel). Demo environment setup (Day 2
parallel). Staging environment validation (Day 3 parallel). Enterprise
demo dry run (Day 4 parallel). Completion docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/ against staging && lighthouse && locust -u
  Command**     100 against staging

  **Pass 1**    Staging: all E2E tests pass

  **Pass 2**    Staging: P95 \<300ms under load

  **Pass 3**    Demo: all 4 scenarios run without errors

  **Pass 4**    All production checklists: 100% complete

  **Pass 5**    Weeks 1-40 FINAL gate PASSED --- enterprise ready
  ------------- ---------------------------------------------------------

**Week 41 --- Cloud Migration Week 1 --- Foundation (Phase 9)**

providers.tf + networking.tf + iam.tf + registry.tf (Day 1 parallel).
K8s cluster + managed DB + Redis (Day 2 chain on networking). K8s
namespace + ingress + cert-manager + secrets (Day 3 chain on cluster).
GitHub Actions Terraform CI + deploy workflows (Day 4 parallel).
Validation + docs (Day 5 chain).

  ------------- ---------------------------------------------------------
  **Tester      terraform validate && pytest
  Command**     tests/integration/test_cloud_connectivity.py

  **Pass 1**    terraform apply: K8s cluster created

  **Pass 2**    Managed PostgreSQL: accessible from K8s pod

  **Pass 3**    Managed Redis: accessible from K8s pod

  **Pass 4**    Cert manager: TLS certificate issued
  ------------- ---------------------------------------------------------

**Week 42 --- Cloud Migration Week 2 --- Deploy Services (Phase 9)**

K8s deployment manifests per service (Day 1 parallel). HPA + KEDA +
ingress + updated Dockerfiles (Day 2 chain). Build + push Docker images
(Day 3 parallel). Run migration job → deploy backend → worker → MCP (Day
4 chain). Cloud validation tests (Day 5 chain).

  ------------- ---------------------------------------------------------
  **Tester      kubectl get pods && pytest
  Command**     tests/integration/test_cloud_backend_health.py && locust
                -u 100

  **Pass 1**    All K8s pods in Running state

  **Pass 2**    Cloud /health returns 200

  **Pass 3**    Cloud E2E tests all pass

  **Pass 4**    Cloud load test P95 \<500ms

  **Pass 5**    HPA scales under load
  ------------- ---------------------------------------------------------

**Week 43 --- Cloud Migration Week 3 --- Frontend + CDN + Environments
(Phase 9)**

Frontend deployment + ingress + build + CDN config (Day 1 chain).
3-environment namespaces + setup script (Day 2 chain). Next.js cloud
config + CDN + deploy workflow + env vars (Day 3 chain). PR preview +
staging auto-deploy + prod gate (Day 4 parallel). Cloud tests (Day 5
chain).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/e2e/test_frontend_cloud.py
  Command**     tests/integration/test_environments.py

  **Pass 1**    Frontend: served from cloud CDN with TLS

  **Pass 2**    CDN cache hit rate \>80%

  **Pass 3**    3 environments: dev/staging/prod all isolated

  **Pass 4**    PR preview: new URL on every PR
  ------------- ---------------------------------------------------------

**Week 44 --- Cloud Migration Week 4 --- Storage + Logging + Backups
(Phase 9)**

storage.tf + logging.tf + alerting.tf + backup.tf (Day 1 parallel).
FluentD + PG backup CronJob + storage client update (Day 2 chain).
Backup verification tests (Day 3 parallel). Full cloud E2E + OWASP +
cost review (Day 4 parallel). Migration completion docs (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_backup_restore.py && pytest
  Command**     tests/ against cloud

  **Pass 1**    FluentD: logs in cloud within 30 seconds

  **Pass 2**    Backup: PG backup restores successfully

  **Pass 3**    Object storage: client isolation confirmed

  **Pass 4**    Full E2E: all tests pass against cloud URLs

  **Pass 5**    Phase 9 COMPLETE
  ------------- ---------------------------------------------------------

**Week 45 --- Razorpay + Multi-Currency Billing (Phase 10)**

razorpay_client + currency utility + DB migration 011 + Terraform (Day 1
parallel). Razorpay webhook + billing service update + multi-currency
pricing + billing API (Day 2 chain). Frontend billing UI updates (Day 3
parallel). Razorpay MCP + tests (Day 4 parallel). Integration tests (Day
5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_razorpay_webhook.py
  Command**     tests/e2e/test_multi_currency_billing.py

  **Pass 1**    Razorpay: subscription flow works end-to-end (mocked)

  **Pass 2**    Razorpay webhook: HMAC verification works

  **Pass 3**    INR pricing: correct price calculated

  **Pass 4**    Currency cache: refreshes every 1 hour
  ------------- ---------------------------------------------------------

**Week 46 --- Tax + Dunning + PDF Invoices (Phase 10)**

Tax service + dunning service + invoice service + dunning worker (Day 1
chain). Tax API + invoice API + dunning notifications + invoice email
(Day 2 chain). Frontend tax/invoice/dunning UI (Day 3 parallel). Tests
(Day 4 parallel). E2E tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/e2e/test_gst_billing.py
  Command**     tests/e2e/test_dunning_flow.py

  **Pass 1**    GST: Indian invoice shows 18% correctly

  **Pass 2**    VAT: UK invoice shows 20% correctly

  **Pass 3**    Dunning: all 4 retry stages fire at correct intervals

  **Pass 4**    PDF invoice: correct tax entity details

  **Pass 5**    Phase 10 COMPLETE
  ------------- ---------------------------------------------------------

**Week 47 --- Mobile Foundation --- React Native + Expo (Phase 11)**

Expo config → navigators (App/Auth/Main) (Day 1 chain). UI primitives +
API client (Day 2 parallel). Auth screens + Zustand stores (Day 3
parallel). All hooks (Day 4 parallel). Navigation + auth tests + EAS
Build workflow (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      cd mobile && npm test && eas build \--platform all
  Command**     \--non-interactive

  **Pass 1**    Login screen: connects to backend, JWT received

  **Pass 2**    Navigation: all 5 tabs accessible

  **Pass 3**    All Zustand stores initialise

  **Pass 4**    EAS Build: workflow triggers successfully
  ------------- ---------------------------------------------------------

**Week 48 --- Mobile Core Screens (Phase 11)**

Dashboard + approvals + ticket detail + swipeable card (Day 1 parallel).
Jarvis + voice button + agents screens (Day 2 parallel). Additional
approval + Jarvis components (Day 3 parallel). Push notification backend
chain (Day 4 chain). Core screen tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      cd mobile && npm test && pytest
  Command**     tests/unit/test_push_notifications.py

  **Pass 1**    Swipe approval: API called correctly on swipe right

  **Pass 2**    Voice command: Jarvis response streams back

  **Pass 3**    Push notification: approve from lock screen works

  **Pass 4**    Batch approval: all 5 tickets in one API call
  ------------- ---------------------------------------------------------

**Week 49 --- Mobile Remaining Screens + App Store Submission (Phase
11)**

Analytics + knowledge + settings + billing screens (Day 1 parallel).
Expo notifications → hook → background (Day 2 chain). App Store assets
per platform (Day 3 parallel). EAS build → submit iOS + Android (Day 4
chain). Final mobile tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      cd mobile && npm test
  Command**     

  **Pass 1**    iOS app: submitted to TestFlight

  **Pass 2**    Android app: submitted to internal track

  **Pass 3**    Push notifications: end-to-end on real device

  **Pass 4**    Camera upload: document sent to backend KB

  **Pass 5**    Phase 11 COMPLETE
  ------------- ---------------------------------------------------------

**Week 50 --- Enterprise SSO --- SAML 2.0 Foundation (Phase 12)**

SAML provider + SP metadata + SSO config model + DB migration 012 (Day 1
parallel). SSO service → SSO API + security update + schema (Day 2
chain). Frontend SSO pages + docs (Day 3 parallel). Unit tests (Day 4
parallel). Integration + E2E tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_saml_flow.py
  Command**     tests/integration/test_sso_security.py

  **Pass 1**    SAML flow: mock IdP → JWT issued

  **Pass 2**    JIT provisioning: new user created on first SSO login

  **Pass 3**    Replay attack: duplicate SAMLResponse rejected

  **Pass 4**    SP metadata: valid XML parseable by Okta/Azure
  ------------- ---------------------------------------------------------

**Week 51 --- Okta + Azure AD + SCIM Provisioning (Phase 12)**

Okta + Azure AD + Google Workspace providers + SCIM token model (Day 1
parallel). SCIM service → SCIM API + provider guides (Day 2 chain).
Provider-specific tests (Day 3 parallel). SCIM integration tests (Day 4
parallel). SCIM complete tests + docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_okta_scim.py
  Command**     tests/e2e/test_scim_lifecycle.py

  **Pass 1**    Okta OIDC: mock login → JWT issued

  **Pass 2**    Azure AD: mock login → JWT issued

  **Pass 3**    SCIM: user lifecycle create→update→delete complete

  **Pass 4**    SCIM deprovisioning: access revoked immediately
  ------------- ---------------------------------------------------------

**Week 52 --- MFA + SSO Audit + Enterprise Admin (Phase 12)**

MFA enforcer + MFA API + SSO audit service + access review service (Day
1 parallel). SSO audit API + access review worker + audit UI +
enterprise guide (Day 2 chain). Security + compliance docs (Day 3
parallel). Tests (Day 4 parallel). E2E tests + PROJECT_STATE (Day 5
parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/e2e/test_mfa_enforcement.py
  Command**     tests/integration/test_sso_audit_export.py

  **Pass 1**    MFA: user without MFA blocked from enterprise tenant

  **Pass 2**    SSO audit: every login logged with IP + result

  **Pass 3**    Audit CSV: all required fields

  **Pass 4**    Access review: 90+ day inactive flagged

  **Pass 5**    Phase 12 COMPLETE
  ------------- ---------------------------------------------------------

**Week 53 --- Multi-Region Deployment + Circuit Breakers (Phase 13)**

Primary + secondary region Terraform + global LB + health checks (Day 1
parallel). DB + Redis replication + secondary/primary K8s stacks (Day 2
chain). App-layer circuit breakers --- utility → Shopify → Stripe →
OpenRouter (Day 3 chain). Multi-region tests (Day 4 parallel). Docs (Day
5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_regional_failover.py
  Command**     tests/unit/test_circuit_breaker.py

  **Pass 1**    Regional failover: traffic moves to secondary in \<30
                seconds

  **Pass 2**    DB replication lag \<500ms

  **Pass 3**    Circuit breaker: Shopify failure opens circuit

  **Pass 4**    Both regions: health checks passing
  ------------- ---------------------------------------------------------

**Week 54 --- Zero-Downtime Deploys + Network Policies + Tracing (Phase
13)**

PDBs + network policy default-deny → allow rules (Day 1 chain). Rolling
deploy configs for all services + readiness probes (Day 2 chain).
OpenTelemetry + Terraform tracing + dashboard + alert updates (Day 3
chain). SLA + deploy + network tests (Day 4 parallel). Tests + main.py
graceful shutdown (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_zero_downtime_deploy.py
  Command**     tests/integration/test_network_policies.py

  **Pass 1**    Rolling deploy: zero dropped requests during deployment

  **Pass 2**    PDB: minimum 1 pod always available

  **Pass 3**    Network policy: cross-namespace blocked

  **Pass 4**    OpenTelemetry: traces visible in dashboard
  ------------- ---------------------------------------------------------

**Week 55 --- Chaos Engineering + SLA Verification (Phase 13)**

Chaos experiment manifests --- pod kill + network delay + DB
connection + chaos schedule (Day 1 parallel). Run each experiment on
staging (Day 2 parallel). Results docs + SLA calculation (Day 3
parallel). Fix findings per experiment (Day 4 parallel). Tests + 99.99%
certification (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/integration/test_sla_99_99.py
  Command**     tests/integration/test_chaos_schedule.py

  **Pass 1**    Pod kill: system recovers in \<60 seconds

  **Pass 2**    DB failure: circuit breaker opens, fallback served

  **Pass 3**    Network delay: P95 \<1 second with 300ms injected

  **Pass 4**    SLA: ≥99.99% uptime verified

  **Pass 5**    Phase 13 COMPLETE
  ------------- ---------------------------------------------------------

**Week 56 --- SOC 2 --- Gap Assessment + All 6 Policies (Phase 14)**

Gap assessment + Vanta/Drata setup + SOC 2 README + tooling doc (Day 1
parallel). InfoSec + Access Control + Change Management + Incident
Response policies (Day 2 parallel). Vendor Management + Business
Continuity + sub-processors + security scanning Terraform (Day 3
parallel). Snyk GitHub Action + KMS config (Day 4 chain). SOC 2 Week 1
tests (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/compliance/test_policy_completeness.py
  Command**     tests/integration/test_kms_encryption.py

  **Pass 1**    All 6 SOC 2 policies written and reviewed

  **Pass 2**    Gap assessment complete with remediation plan

  **Pass 3**    Vanta/Drata collecting evidence automatically

  **Pass 4**    Snyk: blocks PR with critical CVE

  **Pass 5**    Observation period begins
  ------------- ---------------------------------------------------------

**Week 57 --- SOC 2 --- Vulnerability Scanning + TLS Hardening (Phase
14)**

Snyk weekly scan + OWASP ZAP + TLS hardening + network segmentation (Day
1 parallel). Evidence collection for each control area (Day 2 parallel).
SOC 2 control tests (Day 3 parallel). Penetration test scope + findings
(Day 4 parallel). SOC 2 Week 2 docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      snyk test && pytest
  Command**     tests/compliance/test_soc2_controls.py

  **Pass 1**    Snyk: zero critical CVEs

  **Pass 2**    TLS: SSL Labs A+ rating

  **Pass 3**    Network segmentation: controls documented

  **Pass 4**    Penetration test scope defined
  ------------- ---------------------------------------------------------

**Week 58 --- SOC 2 --- Evidence Collection + Change Management (Phase
14)**

Evidence collection automation for all controls (Day 1 parallel). Change
management evidence --- all PRs through CI (Day 2 parallel). Access
review evidence (Day 3 parallel). Incident response drill (Day 4
parallel). SOC 2 Week 3 docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/compliance/test_change_management.py
  Command**     tests/compliance/test_access_review.py

  **Pass 1**    Evidence collection: automated for all controls

  **Pass 2**    Change management: every change through CI verified

  **Pass 3**    Access review: quarterly review completed

  **Pass 4**    Incident response drill: completed and documented
  ------------- ---------------------------------------------------------

**Week 59 --- SOC 2 --- Final Audit Preparation (Phase 14)**

Mock audit --- all questions answered with evidence (Day 1 parallel).
Management assertion + auditor engagement (Day 2 parallel). Final
compliance scans (Day 3 parallel). SOC 2 documentation complete review
(Day 4 parallel). Observation period completion docs (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/compliance/ && snyk test
  Command**     

  **Pass 1**    Mock audit: all questions answered within 5 minutes

  **Pass 2**    Management assertion signed

  **Pass 3**    Auditor: engagement confirmed, observation start date set

  **Pass 4**    All SOC 2 controls: green in Vanta/Drata
  ------------- ---------------------------------------------------------

**Week 60 --- SOC 2 Type II Complete + Production Ready (Phase 14)**

Final full test suite (Day 1 parallel). Final security + compliance
scans (Day 2 parallel). Final performance validation (Day 3 parallel).
Production readiness final checklist (Day 4 parallel). Phase 14
completion + investor update (Day 5 parallel).

  ------------- ---------------------------------------------------------
  **Tester      pytest tests/ && snyk test && locust -u 100
  Command**     

  **Pass 1**    Full test suite: 100% pass rate

  **Pass 2**    Zero critical CVEs

  **Pass 3**    OWASP: clean

  **Pass 4**    P95 \<300ms at 100 concurrent users

  **Pass 5**    SOC 2 Type II: observation period complete, auditor
                engaged

  **Pass 6**    Agent Lightning: ≥94% accuracy

  **Pass 7**    ALL 60 WEEKS COMPLETE --- PRODUCTION READY
  ------------- ---------------------------------------------------------
