# AGENT_COMMS.md — Week 19 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 19 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 19 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-23

> **Phase: Phase 5 — First Clients (Client Onboarding + Real Validation)**
>
> **Week 19 Goals:**
> - Day 1: Client 001 Setup Files (6 files)
> - Day 2: Shadow Mode Validation (5 files)
> - Day 3: Bug Fixes from Real Usage (4 files)
> - Day 4: Performance Optimisation (5 files)
> - Day 5: Reports + Baseline Metrics (6 files)
> - Day 6: Tester runs real validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Real client data handling — security paramount
> 3. Shadow mode processes WITHOUT affecting real customers
> 4. All PII must be handled per GDPR/HIPAA
> 5. **50 tickets processed in Shadow Mode without critical errors**
> 6. **Accuracy baseline established (target >72%)**
> 7. **P95 <500ms on real client data**
> 8. **No cross-tenant data leaks**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Client 001 Setup Files
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `clients/client_001/__init__.py`
2. `clients/client_001/config.py`
3. `clients/client_001/knowledge_base/faq.json`
4. `clients/client_001/knowledge_base/products.json`
5. `clients/client_001/knowledge_base/policies.json`
6. `monitoring/dashboards/client_001_dashboard.json`

### Field 2: What is each file?
1. `clients/client_001/__init__.py` — Client module init
2. `clients/client_001/config.py` — Client-specific configuration
3. `clients/client_001/knowledge_base/faq.json` — Client FAQ knowledge
4. `clients/client_001/knowledge_base/products.json` — Client product catalog
5. `clients/client_001/knowledge_base/policies.json` — Client policies (refund, shipping, etc.)
6. `monitoring/dashboards/client_001_dashboard.json` — Client-specific Grafana dashboard

### Field 3: Responsibilities

**clients/client_001/config.py:**
- Client config with:
  - Client ID: "client_001"
  - Client name: "Acme E-commerce"
  - Industry: "ecommerce"
  - Variant: "parwa" (PARWA Junior)
  - Timezone: "America/New_York"
  - Business hours: 9am-6pm EST
  - Escalation contacts: email, slack webhook
  - Paddle account ID
  - Feature flags for this client
  - **Test: Config loads correctly**

**clients/client_001/knowledge_base/faq.json:**
- FAQ knowledge with:
  - 20+ FAQ entries
  - Categories: Orders, Shipping, Returns, Products, Account
  - Question/Answer pairs
  - Keywords for search
  - Last updated timestamp
  - **Test: FAQ loads and is searchable**

**clients/client_001/knowledge_base/products.json:**
- Product catalog with:
  - Product IDs and names
  - Categories
  - Price ranges
  - Availability status
  - Common issues per product
  - **Test: Products load correctly**

**clients/client_001/knowledge_base/policies.json:**
- Policies with:
  - Refund policy (30 days, conditions)
  - Shipping policy (regions, times)
  - Return policy (process, exceptions)
  - Exchange policy
  - Warranty information
  - **Test: Policies load correctly**

**monitoring/dashboards/client_001_dashboard.json:**
- Client dashboard with:
  - Ticket volume graph
  - Resolution time chart
  - CSAT score gauge
  - Agent accuracy metric
  - Escalation rate
  - Paddle transaction count
  - **Test: Dashboard loads in Grafana**

### Field 4: Depends On
- Week 1 config system
- Week 5 knowledge base
- Week 14 monitoring

### Field 5: Expected Output
- Client 001 fully configured
- Knowledge base loaded
- Dashboard accessible

### Field 6: Unit Test Files
- `tests/clients/test_client_001.py`

### Field 7: BDD Scenario
- `docs/bdd_scenarios/client_onboarding_bdd.md`

### Field 8: Error Handling
- Invalid config fallbacks
- Missing KB graceful degradation
- Dashboard error states

### Field 9: Security Requirements
- Client ID isolation
- PII in KB encrypted at rest
- Access logging

### Field 10: Integration Points
- Knowledge base manager
- Variant system
- Monitoring stack

### Field 11: Code Quality
- Typed config classes
- Validated JSON schemas
- Clear documentation

### Field 12: GitHub CI Requirements
- Config loads without errors
- JSON schemas valid
- Dashboard valid JSON

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Client config loads correctly**
- Knowledge base ingestible
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Shadow Mode Validation
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `tests/integration/test_shadow_mode.py`
2. `scripts/run_shadow_mode.py`
3. `scripts/validate_shadow.py`
4. `clients/shadow_mode_handler.py`
5. `tests/integration/__init__.py`

### Field 2: What is each file?
1. `tests/integration/test_shadow_mode.py` — Shadow mode integration tests
2. `scripts/run_shadow_mode.py` — Script to run shadow mode processing
3. `scripts/validate_shadow.py` — Validation script for shadow results
4. `clients/shadow_mode_handler.py` — Shadow mode processing handler
5. `tests/integration/__init__.py` — Module init

### Field 3: Responsibilities

**clients/shadow_mode_handler.py:**
- Shadow mode handler with:
  - Process incoming tickets WITHOUT sending responses
  - Log AI responses for comparison
  - Track accuracy vs human decisions
  - No customer-facing impact
  - Detailed logging
  - Configurable ticket count
  - **CRITICAL: Never sends real responses to customers**
  - **Test: Shadow mode processes correctly**

**tests/integration/test_shadow_mode.py:**
- Shadow mode tests with:
  - Test: Process 50 tickets in shadow mode
  - Test: No real responses sent
  - Test: All decisions logged
  - Test: Accuracy calculated correctly
  - Test: Cross-tenant isolation maintained
  - Test: PII handled correctly
  - **Test: All shadow tests pass**

**scripts/run_shadow_mode.py:**
- Shadow runner with:
  - CLI interface for running shadow mode
  - Ticket count parameter
  - Client selection parameter
  - Progress reporting
  - Results output to JSON
  - **Test: Script runs correctly**

**scripts/validate_shadow.py:**
- Validation script with:
  - Validate shadow mode results
  - Check accuracy threshold (>72%)
  - Check response times (<500ms)
  - Check for errors
  - Generate validation report
  - **Test: Validation runs correctly**

### Field 4: Depends On
- Client 001 setup (Day 1)
- All backend services
- Week 13 Agent Lightning

### Field 5: Expected Output
- Shadow mode runs without errors
- 50+ tickets processed
- Accuracy baseline established

### Field 6: Unit Test Files
- Files are tests themselves

### Field 7: BDD Scenario
- Shadow mode processes tickets without customer impact

### Field 8: Error Handling
- Shadow errors don't affect production
- Detailed error logging
- Graceful failure modes

### Field 9: Security Requirements
- Shadow responses NEVER sent to customers
- PII protected in shadow logs
- Audit trail maintained

### Field 10: Integration Points
- Ticket processing pipeline
- Knowledge base
- Decision logging

### Field 11: Code Quality
- Clean separation from production
- Thorough logging
- Safe defaults

### Field 12: GitHub CI Requirements
- Shadow tests pass
- No real responses sent
- Logs captured

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 5 files built and pushed
- **CRITICAL: 50 tickets processed without errors**
- **CRITICAL: No real responses sent**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Bug Fixes from Real Usage
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `tests/integration/test_real_usage_fixes.py`
2. `clients/error_tracker.py`
3. `scripts/collect_bug_reports.py`
4. `docs/known_issues.md`

### Field 2: What is each file?
1. `tests/integration/test_real_usage_fixes.py` — Tests for real usage bug fixes
2. `clients/error_tracker.py` — Error tracking and categorization
3. `scripts/collect_bug_reports.py` — Script to collect bug reports from logs
4. `docs/known_issues.md` — Documentation of known issues and fixes

### Field 3: Responsibilities

**clients/error_tracker.py:**
- Error tracker with:
  - Categorize errors by type
  - Track error frequency
  - Alert on critical errors
  - Error trends over time
  - Integration with monitoring
  - **Test: Error tracker works**

**tests/integration/test_real_usage_fixes.py:**
- Bug fix tests with:
  - Test: Common error scenarios handled
  - Test: Edge cases from real usage
  - Test: Error recovery works
  - Test: Graceful degradation
  - **Test: All bug fix tests pass**

**scripts/collect_bug_reports.py:**
- Bug collection with:
  - Parse logs for errors
  - Group similar errors
  - Generate bug report
  - Export to GitHub issues format
  - **Test: Collection works**

**docs/known_issues.md:**
- Known issues doc with:
  - List of known issues
  - Workarounds
  - Fix timeline
  - Severity ratings
  - **Content: Complete issue list**

### Field 4: Depends On
- Shadow mode results (Day 2)
- Error logs from real usage

### Field 5: Expected Output
- Error tracking functional
- Bug fixes identified
- Tests for fixes passing

### Field 6: Unit Test Files
- Tests built into deliverables

### Field 7: BDD Scenario
- Real usage errors tracked and fixed

### Field 8: Error Handling
- Comprehensive error categorization
- Recovery procedures documented

### Field 9: Security Requirements
- No sensitive data in bug reports
- Sanitized logs

### Field 10: Integration Points
- Logging system
- Monitoring alerts

### Field 11: Code Quality
- Clear error messages
- Documented fixes

### Field 12: GitHub CI Requirements
- Bug fix tests pass
- All tests still green

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 4 files built and pushed
- Error tracking works
- Known issues documented
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Performance Optimisation
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `tests/performance/test_real_client_load.py`
2. `scripts/optimize_performance.py`
3. `scripts/benchmark_real_data.py`
4. `monitoring/alerts/performance_alerts.yml`
5. `docs/performance_tuning.md`

### Field 2: What is each file?
1. `tests/performance/test_real_client_load.py` — Performance tests with real data patterns
2. `scripts/optimize_performance.py` — Performance optimization script
3. `scripts/benchmark_real_data.py` — Benchmark script for real client data
4. `monitoring/alerts/performance_alerts.yml` — Performance-specific alert rules
5. `docs/performance_tuning.md` — Performance tuning documentation

### Field 3: Responsibilities

**tests/performance/test_real_client_load.py:**
- Real load tests with:
  - Test: P95 < 500ms with real data patterns
  - Test: Concurrent user simulation
  - Test: Peak load handling
  - Test: Database query performance
  - Test: API response times
  - **CRITICAL: P95 < 500ms on real data**
  - **Test: Performance tests pass**

**scripts/optimize_performance.py:**
- Optimization script with:
  - Identify slow queries
  - Suggest indexes
  - Cache optimization
  - Connection pooling tune
  - **Test: Optimization runs**

**scripts/benchmark_real_data.py:**
- Benchmark script with:
  - Run benchmarks on real data
  - Compare to baseline
  - Generate report
  - Track trends
  - **Test: Benchmark runs**

**monitoring/alerts/performance_alerts.yml:**
- Performance alerts with:
  - P95 latency > 500ms alert
  - Error rate > 1% alert
  - Queue depth alert
  - Database connection pool alert
  - Memory usage alert
  - **Test: Alerts valid YAML**

**docs/performance_tuning.md:**
- Tuning doc with:
  - Database optimization tips
  - Caching strategies
  - Connection pooling config
  - Known bottlenecks
  - **Content: Complete tuning guide**

### Field 4: Depends On
- Real client data
- Shadow mode results
- Week 14 performance tests

### Field 5: Expected Output
- P95 < 500ms achieved
- Benchmarks established
- Alerts configured

### Field 6: Unit Test Files
- Performance tests in deliverables

### Field 7: BDD Scenario
- System performs within SLA

### Field 8: Error Handling
- Performance degradation alerts
- Automatic scaling triggers

### Field 9: Security Requirements
- No sensitive data in benchmarks
- Safe performance testing

### Field 10: Integration Points
- Monitoring stack
- Database
- Cache layer

### Field 11: Code Quality
- Reproducible benchmarks
- Clear documentation

### Field 12: GitHub CI Requirements
- Performance tests pass
- P95 threshold met

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 5 files built and pushed
- **CRITICAL: P95 < 500ms on real data**
- Benchmarks documented
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Reports + Baseline Metrics
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `reports/client_001_week1.md`
2. `tests/performance/baseline_metrics.py`
3. `scripts/generate_client_report.py`
4. `clients/metrics_collector.py`
5. `reports/baseline_accuracy.json`
6. `reports/baseline_performance.json`

### Field 2: What is each file?
1. `reports/client_001_week1.md` — Week 1 report for client 001
2. `tests/performance/baseline_metrics.py` — Baseline metrics test
3. `scripts/generate_client_report.py` — Client report generator
4. `clients/metrics_collector.py` — Metrics collection service
5. `reports/baseline_accuracy.json` — Accuracy baseline data
6. `reports/baseline_performance.json` — Performance baseline data

### Field 3: Responsibilities

**reports/client_001_week1.md:**
- Client report with:
  - Tickets processed: count
  - Average response time
  - Accuracy score
  - CSAT (if available)
  - Escalation rate
  - Top issues handled
  - Recommendations
  - **Content: Complete week 1 report**

**tests/performance/baseline_metrics.py:**
- Baseline tests with:
  - Test: Baseline accuracy > 72%
  - Test: Baseline P95 < 500ms
  - Test: Baseline error rate < 1%
  - Test: All metrics captured
  - **CRITICAL: Accuracy baseline > 72%**
  - **Test: Baseline tests pass**

**scripts/generate_client_report.py:**
- Report generator with:
  - Generate PDF/Markdown reports
  - Include charts and graphs
  - Automated scheduling support
  - Email delivery option
  - **Test: Report generates**

**clients/metrics_collector.py:**
- Metrics collector with:
  - Collect accuracy metrics
  - Collect performance metrics
  - Collect satisfaction metrics
  - Store for trending
  - Export to monitoring
  - **Test: Collection works**

**reports/baseline_accuracy.json:**
- Accuracy baseline with:
  - Overall accuracy percentage
  - Accuracy by category
  - Accuracy by agent
  - Common mistakes
  - **Content: Accuracy baseline data**

**reports/baseline_performance.json:**
- Performance baseline with:
  - P50, P95, P99 latencies
  - Throughput metrics
  - Resource utilization
  - Error rates
  - **Content: Performance baseline data**

### Field 4: Depends On
- All Week 19 work
- Real usage data

### Field 5: Expected Output
- Week 1 report complete
- Baselines established
- Metrics collection working

### Field 6: Unit Test Files
- Baseline metrics test included

### Field 7: BDD Scenario
- Client receives actionable report

### Field 8: Error Handling
- Report generation failures logged
- Partial data handling

### Field 9: Security Requirements
- No sensitive data in reports
- Client isolation in metrics

### Field 10: Integration Points
- Monitoring stack
- Reporting services
- Client dashboard

### Field 11: Code Quality
- Automated report generation
- Clear metrics definitions

### Field 12: GitHub CI Requirements
- Baseline tests pass
- Reports generate

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Accuracy baseline > 72%**
- Week 1 report complete
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 19 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. Client Setup Validation
```bash
pytest tests/clients/test_client_001.py -v
```

#### 2. Shadow Mode Tests
```bash
pytest tests/integration/test_shadow_mode.py -v
python scripts/run_shadow_mode.py --client client_001 --count 50
python scripts/validate_shadow.py --client client_001
```

#### 3. Performance Tests
```bash
pytest tests/performance/test_real_client_load.py -v
python scripts/benchmark_real_data.py --client client_001
```

#### 4. Baseline Metrics
```bash
pytest tests/performance/baseline_metrics.py -v
python scripts/generate_client_report.py --client client_001 --week 1
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | Client 001 config | Loads correctly |
| 2 | Knowledge base | Ingested and searchable |
| 3 | Shadow mode | 50 tickets processed |
| 4 | Shadow mode | No real responses sent |
| 5 | Performance P95 | <500ms on real data |
| 6 | Accuracy baseline | >72% |
| 7 | Cross-tenant | No data leaks |
| 8 | Client dashboard | Loads in Grafana |
| 9 | Week 1 report | Generated successfully |
| 10 | All tests | Pass |

---

### Week 19 PASS Criteria

1. ✅ 50 tickets processed in Shadow Mode without critical errors
2. ✅ Accuracy baseline established (target >72%)
3. ✅ P95 <500ms on real client data
4. ✅ No cross-tenant data leaks in real usage
5. ✅ Client 001 fully configured
6. ✅ Knowledge base loaded
7. ✅ Week 1 report generated
8. ✅ GitHub CI pipeline GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests | Pushed |
|---------|-----|--------|-------|-------|--------|
| Builder 1 | Day 1 | ⏳ PENDING | Client 001 Setup (6 files) | - | NO |
| Builder 2 | Day 2 | ⏳ PENDING | Shadow Mode (5 files) | - | NO |
| Builder 3 | Day 3 | ⏳ PENDING | Bug Fixes (4 files) | - | NO |
| Builder 4 | Day 4 | ⏳ PENDING | Optimisation (5 files) | - | NO |
| Builder 5 | Day 5 | ⏳ PENDING | Reports + Metrics (6 files) | - | NO |
| Tester | Day 6 | ⏳ PENDING | Full validation | - | NO |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. Real client data — security is paramount
3. Shadow mode NEVER sends real responses
4. All PII handled per GDPR/HIPAA
5. **50 tickets in Shadow Mode without errors**
6. **Accuracy baseline > 72%**
7. **P95 < 500ms on real data**
8. **No cross-tenant data leaks**
9. Document all findings
10. Prepare for Agent Lightning training (Week 20)

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 19 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | Client 001 Setup |
| Day 2 | 5 | Shadow Mode Validation |
| Day 3 | 4 | Bug Fixes from Real Usage |
| Day 4 | 5 | Performance Optimisation |
| Day 5 | 6 | Reports + Baseline Metrics |
| **Total** | **26** | **First Client Onboarding** |

---

═══════════════════════════════════════════════════════════════════════════════
## EXECUTION ORDER
═══════════════════════════════════════════════════════════════════════════════

```
Week 19 FULLY PARALLEL Execution:

Day 1-5: ALL BUILDERS RUN SIMULTANEOUSLY
├── Builder 1: Client 001 Setup Files (6 files)
├── Builder 2: Shadow Mode Validation (5 files)
├── Builder 3: Bug Fixes from Real Usage (4 files)
├── Builder 4: Performance Optimisation (5 files)
└── Builder 5: Reports + Baseline Metrics (6 files)

Day 6: Tester → Shadow mode + Performance + Baseline validation
```

**ALL Builders can start NOW. No waiting required.**

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 4 COMPLETION SUMMARY
═══════════════════════════════════════════════════════════════════════════════

**Phase 4 COMPLETE ✅**

| Week | Status | Key Deliverable |
|------|--------|-----------------|
| Week 15 | ✅ | Frontend Foundation |
| Week 16 | ✅ | Dashboard Pages + Hooks |
| Week 17 | ✅ | Onboarding + Analytics + Wiring |
| Week 18 | ✅ | Production Hardening + Kubernetes |

**Phase 4 Total:**
- Frontend Files: 169 files
- Tests: All passing
- K8s: Production ready
- Documentation: Complete

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 5: FIRST CLIENTS (WEEKS 19-20)
═══════════════════════════════════════════════════════════════════════════════

**Phase 5 Goals:**
- Week 19: First Client Onboarding + Real Validation 🔄
- Week 20: Second Client + Agent Lightning First Run

**Phase 5 Success Criteria:**
- 2 clients onboarded successfully
- Agent Lightning training completed
- Real accuracy >72%
- P95 <500ms on real data
- Zero cross-tenant data leaks
