# AGENT_COMMS.md — Week 25 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 25 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 25 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-25

> **Phase: Phase 7 — Scale to 20 Clients (Weeks 21-27)**
>
> **Week 25 Goals (Per Roadmap):**
> - Day 1: Financial Services Config + Compliance Foundation
> - Day 2: Financial Services Agents
> - Day 3: Financial Services Tools + Workflows
> - Day 4: Financial Services Tasks + Integration
> - Day 5: Financial Services Frontend + Reports
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Financial Services Vertical per roadmap
> 3. Build `variants/financial_services/` module
> 4. Regulatory compliance (SOX, FINRA, PCI DSS)
> 5. **Security: Enhanced encryption + audit trails**
> 6. **Compliance: Financial regulatory requirements**
> 7. **Audit: Complete transaction logging**
> 8. **Data Protection: PII/PCI data handling**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Financial Services Config + Compliance Foundation
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `variants/financial_services/__init__.py`
2. `variants/financial_services/config.py`
3. `variants/financial_services/compliance/__init__.py`
4. `variants/financial_services/compliance/sox_compliance.py`
5. `variants/financial_services/compliance/finra_rules.py`
6. `tests/unit/test_financial_config.py`

### Field 2: What is each file?
1. `variants/financial_services/__init__.py` — Module init
2. `variants/financial_services/config.py` — Financial services configuration
3. `variants/financial_services/compliance/__init__.py` — Compliance module init
4. `variants/financial_services/compliance/sox_compliance.py` — SOX compliance rules
5. `variants/financial_services/compliance/finra_rules.py` — FINRA regulatory rules
6. `tests/unit/test_financial_config.py` — Config tests

### Field 3: Responsibilities

**variants/financial_services/config.py:**
- Financial services config with:
  - Higher refund limits ($500 for financial)
  - Stricter approval thresholds (>$100 requires approval)
  - Enhanced audit logging enabled
  - Encryption at rest required
  - Session timeout: 15 minutes (financial regulation)
  - Max concurrent sessions: 1 per user
  - Data retention: 7 years (regulatory requirement)
  - **Test: Config loads with financial settings**

**variants/financial_services/compliance/sox_compliance.py:**
- SOX compliance with:
  - Sarbanes-Oxley Act compliance checks
  - Internal control documentation
  - Audit trail requirements
  - Segregation of duties checks
  - Financial reporting accuracy
  - **Test: SOX compliance validates**

**variants/financial_services/compliance/finra_rules.py:**
- FINRA rules with:
  - FINRA Rule 3110 (supervision)
  - FINRA Rule 4511 (books and records)
  - Communication retention requirements
  - Customer complaint handling
  - Suitability determinations
  - **Test: FINRA rules enforced**

**tests/unit/test_financial_config.py:**
- Config tests with:
  - Test: Financial config loads correctly
  - Test: Higher limits enforced
  - Test: Compliance settings correct
  - **CRITICAL: Config validates for financial vertical**

### Field 4: Depends On
- Week 9-11 variant infrastructure
- Compliance layer (Week 7)

### Field 5: Expected Output
- Financial services config operational
- SOX/FINRA compliance foundation

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Financial services client configures with regulatory settings

### Field 8: Error Handling
- Missing config fallbacks
- Compliance violation alerts

### Field 9: Security Requirements
- Enhanced encryption required
- Audit logging enabled

### Field 10: Integration Points
- Client management system
- Compliance services
- Audit trail system

### Field 11: Code Quality
- Typed configuration
- Regulatory requirement comments

### Field 12: GitHub CI Requirements
- Config tests pass
- Compliance validation

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Financial config loads with regulatory settings**
- **CRITICAL: SOX compliance validates**
- **CRITICAL: FINRA rules enforced**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Financial Services Agents
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `variants/financial_services/agents/__init__.py`
2. `variants/financial_services/agents/account_inquiry_agent.py`
3. `variants/financial_services/agents/transaction_agent.py`
4. `variants/financial_services/agents/compliance_agent.py`
5. `variants/financial_services/agents/fraud_detection_agent.py`
6. `tests/unit/test_financial_agents.py`

### Field 2: What is each file?
1. `variants/financial_services/agents/__init__.py` — Agents module init
2. `variants/financial_services/agents/account_inquiry_agent.py` — Account inquiry handling
3. `variants/financial_services/agents/transaction_agent.py` — Transaction processing
4. `variants/financial_services/agents/compliance_agent.py` — Compliance enforcement
5. `variants/financial_services/agents/fraud_detection_agent.py` — Fraud detection
6. `tests/unit/test_financial_agents.py` — Agent tests

### Field 3: Responsibilities

**variants/financial_services/agents/account_inquiry_agent.py:**
- Account inquiry agent with:
  - Balance inquiries (limited info for security)
  - Account status checks
  - Statement requests
  - Account verification
  - PII masking in responses
  - **Test: Agent handles account inquiries safely**

**variants/financial_services/agents/transaction_agent.py:**
- Transaction agent with:
  - Transaction status inquiries
  - Transaction history (limited)
  - Payment status checks
  - Transfer status inquiries
  - NO transaction initiation (security)
  - **Test: Agent handles transaction inquiries**

**variants/financial_services/agents/compliance_agent.py:**
- Compliance agent with:
  - Real-time compliance monitoring
  - Regulatory requirement checks
  - Suspicious activity flagging
  - Audit trail generation
  - Compliance violation alerts
  - **Test: Compliance agent monitors correctly**

**variants/financial_services/agents/fraud_detection_agent.py:**
- Fraud detection agent with:
  - Transaction pattern analysis
  - Anomaly detection
  - Risk scoring
  - Suspicious behavior flagging
  - Alert generation
  - **Test: Fraud detection works**

**tests/unit/test_financial_agents.py:**
- Agent tests with:
  - Test: All 4 agents initialize
  - Test: Account inquiry handles requests
  - Test: Transaction inquiry works
  - Test: Compliance monitoring active
  - Test: Fraud detection flags issues
  - **CRITICAL: All agents work with financial config**

### Field 4: Depends On
- Financial services config (Day 1)
- Base agents (Week 9)

### Field 5: Expected Output
- All 4 financial agents operational
- Compliance and fraud detection active

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Financial client ticket handled by specialized agents

### Field 8: Error Handling
- PII protection on errors
- Compliance violation handling

### Field 9: Security Requirements
- PII masking enforced
- No sensitive data in logs

### Field 10: Integration Points
- Financial services config
- Compliance system
- Audit trail

### Field 11: Code Quality
- Secure coding practices
- Financial domain terminology

### Field 12: GitHub CI Requirements
- All agent tests pass
- No sensitive data exposure

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All 4 agents initialize**
- **CRITICAL: Fraud detection works**
- **CRITICAL: Compliance agent monitors**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Financial Services Tools + Workflows
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `variants/financial_services/tools/__init__.py`
2. `variants/financial_services/tools/account_tools.py`
3. `variants/financial_services/tools/transaction_tools.py`
4. `variants/financial_services/workflows/__init__.py`
5. `variants/financial_services/workflows/compliance_workflow.py`
6. `tests/unit/test_financial_tools.py`

### Field 2: What is each file?
1. `variants/financial_services/tools/__init__.py` — Tools module init
2. `variants/financial_services/tools/account_tools.py` — Account inquiry tools
3. `variants/financial_services/tools/transaction_tools.py` — Transaction tools
4. `variants/financial_services/workflows/__init__.py` — Workflows module init
5. `variants/financial_services/workflows/compliance_workflow.py` — Compliance workflow
6. `tests/unit/test_financial_tools.py` — Tools tests

### Field 3: Responsibilities

**variants/financial_services/tools/account_tools.py:**
- Account tools with:
  - get_account_summary() — Limited info, PII masked
  - verify_account_status() — Account status check
  - request_statement() — Statement request tool
  - check_account_eligibility() — Eligibility verification
  - All tools with audit logging
  - **Test: Tools execute with audit trail**

**variants/financial_services/tools/transaction_tools.py:**
- Transaction tools with:
  - get_transaction_status() — Status inquiry only
  - search_transactions() — Limited search
  - verify_payment() — Payment verification
  - get_transfer_status() — Transfer status check
  - NO initiation tools (security)
  - **Test: Transaction tools work safely**

**variants/financial_services/workflows/compliance_workflow.py:**
- Compliance workflow with:
  - Pre-action compliance check
  - Real-time monitoring during action
  - Post-action compliance verification
  - Automatic logging and audit
  - Violation escalation
  - **Test: Compliance workflow runs**

**tests/unit/test_financial_tools.py:**
- Tools tests with:
  - Test: Account tools execute with audit
  - Test: Transaction tools work safely
  - Test: Compliance workflow monitors
  - Test: All tools log to audit trail
  - **CRITICAL: All tools have audit logging**

### Field 4: Depends On
- Financial agents (Day 2)
- Audit trail system (Week 1)

### Field 5: Expected Output
- Financial tools operational
- Compliance workflow active
- Audit logging enabled

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Financial tools execute with full audit trail

### Field 8: Error Handling
- Tool failure logging
- Compliance violation handling

### Field 9: Security Requirements
- All tool calls logged
- PII protection enforced

### Field 10: Integration Points
- Financial agents
- Audit trail system
- Compliance services

### Field 11: Code Quality
- Comprehensive logging
- Error documentation

### Field 12: GitHub CI Requirements
- All tools tests pass
- Audit trail verified

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All tools execute with audit logging**
- **CRITICAL: Compliance workflow runs**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Financial Services Tasks + Integration
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `variants/financial_services/tasks/__init__.py`
2. `variants/financial_services/tasks/handle_inquiry.py`
3. `variants/financial_services/tasks/process_complaint.py`
4. `variants/financial_services/tasks/fraud_alert.py`
5. `database/migrations/versions/008_financial_services.py`
6. `tests/integration/test_financial_integration.py`

### Field 2: What is each file?
1. `variants/financial_services/tasks/__init__.py` — Tasks module init
2. `variants/financial_services/tasks/handle_inquiry.py` — Handle financial inquiry
3. `variants/financial_services/tasks/process_complaint.py` — Process complaint task
4. `variants/financial_services/tasks/fraud_alert.py` — Fraud alert task
5. `database/migrations/versions/008_financial_services.py` — DB migration
6. `tests/integration/test_financial_integration.py` — Integration tests

### Field 3: Responsibilities

**variants/financial_services/tasks/handle_inquiry.py:**
- Handle inquiry task with:
  - Route to appropriate agent
  - Execute with compliance checks
  - Generate audit trail
  - Mask PII in response
  - Escalate if needed
  - **Test: Inquiry handled with full audit**

**variants/financial_services/tasks/process_complaint.py:**
- Process complaint task with:
  - FINRA-compliant complaint handling
  - Timeline tracking (FINRA rules)
  - Documentation requirements
  - Escalation to compliance
  - Customer notification
  - **Test: Complaint processed per FINRA**

**variants/financial_services/tasks/fraud_alert.py:**
- Fraud alert task with:
  - Alert generation
  - Priority classification
  - Automatic escalation
  - Notification to compliance team
  - Audit trail generation
  - **Test: Fraud alert triggers correctly**

**database/migrations/versions/008_financial_services.py:**
- DB migration with:
  - Financial audit trail tables
  - Compliance record tables
  - Fraud alert tables
  - Complaint tracking tables
  - Enhanced logging tables
  - **Test: Migration runs successfully**

**tests/integration/test_financial_integration.py:**
- Integration tests with:
  - Test: Full inquiry flow works
  - Test: Complaint processing complete
  - Test: Fraud alert flow works
  - Test: All financial data isolated
  - **CRITICAL: Full financial vertical integrates**

### Field 4: Depends On
- Financial tools (Day 3)
- Database migrations (Week 2)

### Field 5: Expected Output
- All financial tasks operational
- DB migration complete
- Integration validated

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Financial client ticket processed end-to-end

### Field 8: Error Handling
- Task failure handling
- Compliance violation escalation

### Field 9: Security Requirements
- Full audit trail on all tasks
- PII protection enforced

### Field 10: Integration Points
- All financial services components
- Audit system
- Compliance services

### Field 11: Code Quality
- Task documentation
- Error handling coverage

### Field 12: GitHub CI Requirements
- All task tests pass
- DB migration succeeds
- Integration tests pass

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All tasks work with audit trail**
- **CRITICAL: DB migration runs**
- **CRITICAL: Integration tests pass**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Financial Services Frontend + Reports
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/src/app/dashboard/financial/page.tsx`
2. `frontend/src/components/financial/CompliancePanel.tsx`
3. `frontend/src/components/financial/FraudAlertsPanel.tsx`
4. `reports/financial_services_compliance.md`
5. `monitoring/dashboards/financial_services.json`
6. `tests/e2e/test_financial_e2e.py`

### Field 2: What is each file?
1. `frontend/src/app/dashboard/financial/page.tsx` — Financial dashboard page
2. `frontend/src/components/financial/CompliancePanel.tsx` — Compliance panel component
3. `frontend/src/components/financial/FraudAlertsPanel.tsx` — Fraud alerts panel
4. `reports/financial_services_compliance.md` — Compliance report template
5. `monitoring/dashboards/financial_services.json` — Grafana dashboard
6. `tests/e2e/test_financial_e2e.py` — E2E tests

### Field 3: Responsibilities

**frontend/src/app/dashboard/financial/page.tsx:**
- Financial dashboard with:
  - Compliance status overview
  - Active fraud alerts
  - Recent transactions (limited view)
  - Audit trail viewer
  - Regulatory reports access
  - **Test: Dashboard renders with data**

**frontend/src/components/financial/CompliancePanel.tsx:**
- Compliance panel with:
  - Real-time compliance status
  - Violation count
  - Recent compliance events
  - Audit trail access
  - Compliance report generation
  - **Test: Panel shows compliance data**

**frontend/src/components/financial/FraudAlertsPanel.tsx:**
- Fraud alerts panel with:
  - Active alerts list
  - Alert severity indicators
  - Quick actions (escalate, resolve)
  - Alert history
  - Notification settings
  - **Test: Panel shows fraud alerts**

**reports/financial_services_compliance.md:**
- Compliance report with:
  - SOX compliance summary
  - FINRA compliance status
  - Audit trail summary
  - Violation count
  - Remediation status
  - **Content: Report template**

**monitoring/dashboards/financial_services.json:**
- Grafana dashboard with:
  - Compliance metrics
  - Fraud detection metrics
  - Transaction volume
  - Audit trail activity
  - Alert frequency
  - **Test: Dashboard loads**

**tests/e2e/test_financial_e2e.py:**
- E2E tests with:
  - Test: Financial inquiry end-to-end
  - Test: Complaint processing flow
  - Test: Fraud alert handling
  - Test: Compliance dashboard access
  - **CRITICAL: E2E financial flow works**

### Field 4: Depends On
- Financial tasks (Day 4)
- Frontend infrastructure (Week 15-18)

### Field 5: Expected Output
- Financial frontend operational
- Reports generated
- Monitoring dashboard ready

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Manager views financial services dashboard

### Field 8: Error Handling
- Frontend error boundaries
- Data loading fallbacks

### Field 9: Security Requirements
- Secure dashboard access
- PII masking in frontend

### Field 10: Integration Points
- Financial backend services
- Monitoring stack
- Report generation

### Field 11: Code Quality
- Component documentation
- Accessibility compliance

### Field 12: GitHub CI Requirements
- Frontend builds successfully
- E2E tests pass
- Dashboard loads

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Financial dashboard renders**
- **CRITICAL: E2E tests pass**
- **CRITICAL: Monitoring dashboard loads**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 25 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. Config + Compliance Tests
```bash
pytest tests/unit/test_financial_config.py -v
```

#### 2. Agent Tests
```bash
pytest tests/unit/test_financial_agents.py -v
```

#### 3. Tools + Workflows Tests
```bash
pytest tests/unit/test_financial_tools.py -v
```

#### 4. Integration Tests
```bash
pytest tests/integration/test_financial_integration.py -v
```

#### 5. E2E Tests
```bash
pytest tests/e2e/test_financial_e2e.py -v
```

#### 6. DB Migration Test
```bash
alembic upgrade head
pytest tests/integration/test_financial_integration.py -v
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | Financial config loads | Correct regulatory settings |
| 2 | SOX compliance | Validates correctly |
| 3 | FINRA rules | Enforced |
| 4 | All 4 agents initialize | Agents work |
| 5 | Fraud detection | Flags issues |
| 6 | Audit trail | Logs all actions |
| 7 | Tools execute | With audit logging |
| 8 | Compliance workflow | Monitors correctly |
| 9 | Tasks work | With full audit |
| 10 | DB migration | Runs successfully |
| 11 | Frontend dashboard | Renders |
| 12 | E2E flow | Complete financial flow |

---

### Week 25 PASS Criteria

1. ✅ Financial Services Config: Loads with regulatory settings
2. ✅ SOX Compliance: Validates correctly
3. ✅ FINRA Rules: Enforced
4. ✅ All 4 Financial Agents: Initialize and work
5. ✅ Fraud Detection: Active and flagging
6. ✅ Audit Trail: Logging all actions
7. ✅ Financial Tools: Execute with audit
8. ✅ Compliance Workflow: Monitoring
9. ✅ Financial Tasks: Complete with audit
10. ✅ DB Migration 008: Runs successfully
11. ✅ Financial Dashboard: Renders
12. ✅ E2E Tests: Pass
13. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Focus | Files | Status |
|---------|-----|-------|-------|--------|
| Builder 1 | Day 1 | Config + Compliance | 6 | ⏳ PENDING |
| Builder 2 | Day 2 | Financial Agents | 6 | ⏳ PENDING |
| Builder 3 | Day 3 | Tools + Workflows | 6 | ⏳ PENDING |
| Builder 4 | Day 4 | Tasks + Integration | 6 | ⏳ PENDING |
| Builder 5 | Day 5 | Frontend + Reports | 6 | ⏳ PENDING |
| Tester | Day 6 | Full Validation | - | ⏳ PENDING |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. Financial Services Vertical per roadmap
3. **Regulatory compliance is NON-NEGOTIABLE**
4. SOX and FINRA rules must be enforced
5. **Audit Trail: Every action logged**
6. **PII Protection: All sensitive data masked**
7. **Security: Enhanced encryption required**
8. **No transaction initiation (security)**

**FINANCIAL SERVICES METRICS:**

| Metric | Description | Target |
|--------|-------------|--------|
| Audit Trail | % actions logged | 100% |
| PII Masking | % sensitive data masked | 100% |
| Compliance Rate | % compliant actions | 100% |
| Fraud Detection | Detection rate | >95% |
| Response Time | P95 latency | <500ms |

**ASSUMPTIONS:**
- Week 24 completed (Client Success Tooling)
- 10 clients operational
- Frontend dashboard ready
- Compliance infrastructure available

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 25 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | Config + Compliance Foundation |
| Day 2 | 6 | Financial Agents |
| Day 3 | 6 | Tools + Workflows |
| Day 4 | 6 | Tasks + Integration |
| Day 5 | 6 | Frontend + Reports |
| **Total** | **30** | **Financial Services Vertical** |

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 7 PROGRESS
═══════════════════════════════════════════════════════════════════════════════

**Phase 7: Scale to 20 Clients (Weeks 21-27)**

| Week | Roadmap Goal | Status |
|------|--------------|--------|
| 21 | Clients 3-5 + Collective Intelligence | ✅ COMPLETE |
| 22 | Agent Lightning v2 + 77% Accuracy | ✅ COMPLETE |
| 23 | Frontend Polish (A11y, Mobile, Dark Mode) | ✅ COMPLETE |
| 24 | Client Success Tooling | ✅ COMPLETE |
| 25 | Financial Services Vertical | 🔄 IN PROGRESS |
| 26 | Performance Optimization | ⏳ Pending |
| 27 | 20-Client Validation | ⏳ Pending |

**Week 25 Deliverables:**
- Clients: 10 (continuing)
- Financial Services Vertical: 🔄 Building
- SOX/FINRA Compliance: 🔄 Building
- Fraud Detection: 🔄 Building
- On Track for Phase 7!
