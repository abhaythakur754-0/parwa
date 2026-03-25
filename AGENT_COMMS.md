# AGENT_COMMS.md — Week 24 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 24 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 24 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-25

> **Phase: Phase 7 — Scale to 20 Clients (Weeks 21-27)**
>
> **Week 24 Goals (Per Roadmap):**
> - Day 1: Client Health Monitoring System
> - Day 2: Client Onboarding Analytics
> - Day 3: Churn Prediction & Prevention
> - Day 4: Client Communication Hub
> - Day 5: Success Metrics Dashboard + Reports
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Client Success Tooling per roadmap
> 3. Help managers track and improve client outcomes
> 4. Proactive churn prevention
> 5. **Client Health Score: All 10 clients tracked**
> 6. **Churn Prediction: Active for all clients**
> 7. **Onboarding Analytics: Track completion rates**
> 8. **Communication Hub: Centralized client comms**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Client Health Monitoring System
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/services/client_success/__init__.py`
2. `backend/services/client_success/health_monitor.py`
3. `backend/services/client_success/health_scorer.py`
4. `backend/services/client_success/alert_manager.py`
5. `backend/models/client_health.py`
6. `tests/services/test_health_monitor.py`

### Field 2: What is each file?
1. `backend/services/client_success/__init__.py` — Module init
2. `backend/services/client_success/health_monitor.py` — Monitor client health
3. `backend/services/client_success/health_scorer.py` — Calculate health scores
4. `backend/services/client_success/alert_manager.py` — Health alerts
5. `backend/models/client_health.py` — Health model definitions
6. `tests/services/test_health_monitor.py` — Health monitor tests

### Field 3: Responsibilities

**backend/services/client_success/health_monitor.py:**
- Health monitor with:
  - Track client activity levels
  - Monitor ticket volumes
  - Track response times
  - Monitor accuracy metrics
  - Daily health snapshots
  - **Test: Monitor runs for all clients**

**backend/services/client_success/health_scorer.py:**
- Health scorer with:
  - Calculate health score (0-100)
  - Weighted scoring factors:
    - Activity level (20%)
    - Accuracy (30%)
    - Response time (20%)
    - Ticket resolution (20%)
    - Engagement (10%)
  - Trend analysis
  - **Test: Scorer produces valid scores**

**backend/services/client_success/alert_manager.py:**
- Alert manager with:
  - Health score drop alerts
  - Inactivity alerts
  - Accuracy drop alerts
  - Configurable thresholds
  - Multi-channel notifications
  - **Test: Alerts trigger correctly**

**backend/models/client_health.py:**
- Health models with:
  - ClientHealthScore model
  - HealthMetric model
  - HealthAlert model
  - HealthTrend model
  - **Test: Models validate correctly**

**tests/services/test_health_monitor.py:**
- Health tests with:
  - Test: Health scores calculated for all 10 clients
  - Test: Alerts trigger on threshold breach
  - Test: Trends detected correctly
  - **CRITICAL: All 10 clients tracked**

### Field 4: Depends On
- Week 21-22 client systems
- Monitoring infrastructure

### Field 5: Expected Output
- Client health monitoring operational
- All 10 clients tracked

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Manager can see health scores for all clients

### Field 8: Error Handling
- Missing data handling
- Graceful degradation

### Field 9: Security Requirements
- Client isolation in health data
- Access control for health views

### Field 10: Integration Points
- Client management system
- Monitoring stack
- Notification system

### Field 11: Code Quality
- Typed models
- Clear scoring logic

### Field 12: GitHub CI Requirements
- Health monitor tests pass
- All clients tracked

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All 10 clients have health scores**
- Alerts work correctly
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Client Onboarding Analytics
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/services/client_success/onboarding_tracker.py`
2. `backend/services/client_success/onboarding_analytics.py`
3. `backend/services/client_success/milestone_manager.py`
4. `backend/api/client_success.py`
5. `backend/schemas/onboarding.py`
6. `tests/services/test_onboarding_analytics.py`

### Field 2: What is each file?
1. `backend/services/client_success/onboarding_tracker.py` — Track onboarding progress
2. `backend/services/client_success/onboarding_analytics.py` — Analytics for onboarding
3. `backend/services/client_success/milestone_manager.py` — Manage milestones
4. `backend/api/client_success.py` — Client success API endpoints
5. `backend/schemas/onboarding.py` — Onboarding schemas
6. `tests/services/test_onboarding_analytics.py` — Onboarding analytics tests

### Field 3: Responsibilities

**backend/services/client_success/onboarding_tracker.py:**
- Onboarding tracker with:
  - Track onboarding steps
  - Step completion tracking
  - Time-to-complete metrics
  - Stuck step detection
  - Onboarding completion rate
  - **Test: Tracker works for clients**

**backend/services/client_success/onboarding_analytics.py:**
- Onboarding analytics with:
  - Average onboarding time
  - Completion rate by industry
  - Completion rate by variant
  - Bottleneck identification
  - Trend analysis
  - **Test: Analytics produce insights**

**backend/services/client_success/milestone_manager.py:**
- Milestone manager with:
  - Define onboarding milestones
  - Track milestone completion
  - Milestone notifications
  - Custom milestone support
  - **Test: Milestones tracked**

**backend/api/client_success.py:**
- API endpoints with:
  - GET /client-success/health/{client_id}
  - GET /client-success/onboarding/{client_id}
  - GET /client-success/analytics
  - POST /client-success/milestones
  - **Test: API endpoints work**

**backend/schemas/onboarding.py:**
- Onboarding schemas with:
  - OnboardingProgress schema
  - OnboardingMilestone schema
  - OnboardingAnalytics schema
  - **Test: Schemas validate**

**tests/services/test_onboarding_analytics.py:**
- Onboarding tests with:
  - Test: Onboarding progress tracked
  - Test: Completion rates calculated
  - Test: Bottlenecks identified
  - **CRITICAL: Analytics work for all clients**

### Field 4: Depends On
- Week 15-18 frontend onboarding
- Client management system

### Field 5: Expected Output
- Onboarding analytics operational
- Progress tracking active

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Manager can see onboarding progress for all clients

### Field 8: Error Handling
- Missing data handling
- Partial onboarding handling

### Field 9: Security Requirements
- Client isolation in analytics
- Read-only for most users

### Field 10: Integration Points
- Frontend onboarding flow
- Client management
- Reporting system

### Field 11: Code Quality
- Clear analytics logic
- Well-defined milestones

### Field 12: GitHub CI Requirements
- Onboarding tests pass
- API endpoints work

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Onboarding analytics work**
- **CRITICAL: All clients tracked**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Churn Prediction & Prevention
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/services/client_success/churn_predictor.py`
2. `backend/services/client_success/risk_scorer.py`
3. `backend/services/client_success/retention_manager.py`
4. `backend/services/client_success/intervention_engine.py`
5. `backend/models/churn.py`
6. `tests/services/test_churn_prediction.py`

### Field 2: What is each file?
1. `backend/services/client_success/churn_predictor.py` — Predict client churn
2. `backend/services/client_success/risk_scorer.py` — Calculate churn risk
3. `backend/services/client_success/retention_manager.py` — Manage retention actions
4. `backend/services/client_success/intervention_engine.py` — Automated interventions
5. `backend/models/churn.py` — Churn models
6. `tests/services/test_churn_prediction.py` — Churn prediction tests

### Field 3: Responsibilities

**backend/services/client_success/churn_predictor.py:**
- Churn predictor with:
  - Predict churn probability (0-100%)
  - Risk factors identification
  - Prediction model (rule-based + ML-ready)
  - Weekly predictions
  - Historical accuracy tracking
  - **Test: Predictions generated for all clients**

**backend/services/client_success/risk_scorer.py:**
- Risk scorer with:
  - Risk level: LOW/MEDIUM/HIGH/CRITICAL
  - Risk factors:
    - Declining usage (25%)
    - Low accuracy (25%)
    - Support tickets (20%)
    - Payment issues (15%)
    - Low engagement (15%)
  - Risk trend analysis
  - **Test: Risk scores accurate**

**backend/services/client_success/retention_manager.py:**
- Retention manager with:
  - Define retention actions
  - Action priority queue
  - Action tracking
  - Success rate tracking
  - Recommended actions
  - **Test: Retention actions work**

**backend/services/client_success/intervention_engine.py:**
- Intervention engine with:
  - Automated check-ins
  - Proactive support offers
  - Feature adoption nudges
  - Success manager alerts
  - Intervention templates
  - **Test: Interventions trigger correctly**

**backend/models/churn.py:**
- Churn models with:
  - ChurnPrediction model
  - RiskScore model
  - RetentionAction model
  - Intervention model
  - **Test: Models validate**

**tests/services/test_churn_prediction.py:**
- Churn tests with:
  - Test: Predictions for all 10 clients
  - Test: Risk levels assigned correctly
  - Test: Interventions trigger on high risk
  - **CRITICAL: Churn prediction active for all clients**

### Field 4: Depends On
- Client health system (Day 1)
- Analytics data

### Field 5: Expected Output
- Churn prediction operational
- Risk scoring active
- Interventions automated

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- High-risk clients flagged automatically

### Field 8: Error Handling
- Missing data handling
- Prediction confidence thresholds

### Field 9: Security Requirements
- Client isolation in predictions
- Sensitive data protection

### Field 10: Integration Points
- Health monitor
- Notification system
- Client management

### Field 11: Code Quality
- Explainable predictions
- Configurable thresholds

### Field 12: GitHub CI Requirements
- Churn prediction tests pass
- All clients have predictions

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Churn prediction for all 10 clients**
- **CRITICAL: Interventions trigger on high risk**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Client Communication Hub
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/services/client_success/communication_hub.py`
2. `backend/services/client_success/message_templates.py`
3. `backend/services/client_success/notification_scheduler.py`
4. `backend/api/communication.py`
5. `backend/models/communication.py`
6. `tests/services/test_communication_hub.py`

### Field 2: What is each file?
1. `backend/services/client_success/communication_hub.py` — Central communication
2. `backend/services/client_success/message_templates.py` — Message templates
3. `backend/services/client_success/notification_scheduler.py` — Schedule notifications
4. `backend/api/communication.py` — Communication API endpoints
5. `backend/models/communication.py` — Communication models
6. `tests/services/test_communication_hub.py` — Communication tests

### Field 3: Responsibilities

**backend/services/client_success/communication_hub.py:**
- Communication hub with:
  - Centralized client messaging
  - Multi-channel support (email, in-app, SMS)
  - Message history
  - Read status tracking
  - Client preferences
  - **Test: Hub sends messages**

**backend/services/client_success/message_templates.py:**
- Message templates with:
  - Onboarding templates
  - Check-in templates
  - Feature announcement templates
  - Retention templates
  - Custom template support
  - Variable interpolation
  - **Test: Templates render correctly**

**backend/services/client_success/notification_scheduler.py:**
- Notification scheduler with:
  - Schedule future messages
  - Recurring notifications
  - Timezone-aware scheduling
  - Optimal send time calculation
  - Batch scheduling
  - **Test: Scheduling works**

**backend/api/communication.py:**
- API endpoints with:
  - GET /communication/messages/{client_id}
  - POST /communication/send
  - POST /communication/schedule
  - GET /communication/templates
  - **Test: API works**

**backend/models/communication.py:**
- Communication models with:
  - ClientMessage model
  - MessageTemplate model
  - ScheduledNotification model
  - CommunicationPreference model
  - **Test: Models validate**

**tests/services/test_communication_hub.py:**
- Communication tests with:
  - Test: Messages sent correctly
  - Test: Templates render with variables
  - Test: Scheduling works
  - **CRITICAL: Communication hub operational**

### Field 4: Depends On
- Notification service (Week 4)
- Client management system

### Field 5: Expected Output
- Communication hub operational
- Templates ready
- Scheduling active

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Manager can send messages to clients from dashboard

### Field 8: Error Handling
- Failed delivery handling
- Retry logic

### Field 9: Security Requirements
- Secure message storage
- Client preference respect

### Field 10: Integration Points
- Email service
- In-app notifications
- Client dashboard

### Field 11: Code Quality
- Template validation
- Message queuing

### Field 12: GitHub CI Requirements
- Communication tests pass
- Templates render correctly

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Communication hub works**
- **CRITICAL: Templates render correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Success Metrics Dashboard + Reports
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/services/client_success/metrics_aggregator.py`
2. `backend/services/client_success/report_generator.py`
3. `monitoring/dashboards/client_success_dashboard.json`
4. `frontend/src/app/dashboard/client-success/page.tsx`
5. `reports/client_success_weekly.md`
6. `tests/services/test_success_metrics.py`

### Field 2: What is each file?
1. `backend/services/client_success/metrics_aggregator.py` — Aggregate success metrics
2. `backend/services/client_success/report_generator.py` — Generate reports
3. `monitoring/dashboards/client_success_dashboard.json` — Grafana dashboard
4. `frontend/src/app/dashboard/client-success/page.tsx` — Frontend page
5. `reports/client_success_weekly.md` — Weekly report template
6. `tests/services/test_success_metrics.py` — Metrics tests

### Field 3: Responsibilities

**backend/services/client_success/metrics_aggregator.py:**
- Metrics aggregator with:
  - Aggregate health scores across clients
  - Aggregate churn predictions
  - Onboarding completion rates
  - Engagement metrics
  - Response time averages
  - **Test: Aggregation works**

**backend/services/client_success/report_generator.py:**
- Report generator with:
  - Weekly client success report
  - Per-client detailed reports
  - Executive summary
  - Trend analysis
  - Recommendations
  - PDF export option
  - **Test: Reports generate correctly**

**monitoring/dashboards/client_success_dashboard.json:**
- Grafana dashboard with:
  - Health score gauge per client
  - Churn risk panel
  - Onboarding progress chart
  - Communication activity graph
  - Intervention success rate
  - **Test: Dashboard loads**

**frontend/src/app/dashboard/client-success/page.tsx:**
- Frontend page with:
  - Client health overview
  - At-risk clients panel
  - Onboarding pipeline
  - Recent communications
  - Quick actions
  - **Test: Page renders**

**reports/client_success_weekly.md:**
- Weekly report with:
  - Overall client health average
  - At-risk clients list
  - Intervention summary
  - Recommendations
  - Trend analysis
  - **Content: Report template**

**tests/services/test_success_metrics.py:**
- Metrics tests with:
  - Test: Aggregation produces valid metrics
  - Test: Reports generate
  - Test: Dashboard loads
  - **CRITICAL: All metrics tracked**

### Field 4: Depends On
- All Week 24 services
- Frontend dashboard (Week 16)

### Field 5: Expected Output
- Success metrics dashboard
- Report generation
- All metrics visible

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Manager can view client success dashboard

### Field 8: Error Handling
- Missing data handling
- Report generation fallbacks

### Field 9: Security Requirements
- Client isolation in metrics
- Report access control

### Field 10: Integration Points
- All client success services
- Monitoring stack
- Frontend

### Field 11: Code Quality
- Clear metric definitions
- Comprehensive reports

### Field 12: GitHub CI Requirements
- Metrics tests pass
- Dashboard loads
- Reports generate

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Dashboard shows all 10 clients**
- **CRITICAL: Reports generate correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 24 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. Health Monitor Tests
```bash
pytest tests/services/test_health_monitor.py -v
pytest tests/services/test_onboarding_analytics.py -v
```

#### 2. Churn Prediction Tests
```bash
pytest tests/services/test_churn_prediction.py -v
```

#### 3. Communication Hub Tests
```bash
pytest tests/services/test_communication_hub.py -v
```

#### 4. Success Metrics Tests
```bash
pytest tests/services/test_success_metrics.py -v
```

#### 5. API Tests
```bash
pytest tests/api/test_client_success_api.py -v
```

#### 6. Integration Tests
```bash
pytest tests/integration/test_client_success_flow.py -v
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | Health scores | All 10 clients scored |
| 2 | Churn prediction | All 10 clients predicted |
| 3 | Onboarding analytics | All clients tracked |
| 4 | Communication hub | Sends messages |
| 5 | Dashboard | Loads in Grafana |
| 6 | Reports | Generate correctly |
| 7 | Interventions | Trigger on high risk |
| 8 | Templates | Render with variables |

---

### Week 24 PASS Criteria

1. ✅ Client Health Monitor: All 10 clients tracked
2. ✅ Health Scores: 0-100 for all clients
3. ✅ Onboarding Analytics: Completion rates calculated
4. ✅ Churn Prediction: Active for all clients
5. ✅ Risk Scoring: LOW/MEDIUM/HIGH/CRITICAL levels
6. ✅ Interventions: Trigger on high risk
7. ✅ Communication Hub: Operational
8. ✅ Message Templates: Render correctly
9. ✅ Success Dashboard: Shows all metrics
10. ✅ Reports: Generate correctly
11. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Focus | Files | Status |
|---------|-----|-------|-------|--------|
| Builder 1 | Day 1 | Health Monitoring | 6 | ⏳ PENDING |
| Builder 2 | Day 2 | Onboarding Analytics | 6 | ⏳ PENDING |
| Builder 3 | Day 3 | Churn Prediction | 6 | ⏳ PENDING |
| Builder 4 | Day 4 | Communication Hub | 6 | ⏳ PENDING |
| Builder 5 | Day 5 | Success Dashboard | 6 | ⏳ PENDING |
| Tester | Day 6 | Full Validation | - | ⏳ PENDING |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. Client Success Tooling per roadmap
3. All 10 clients must be tracked
4. Proactive churn prevention required
5. **Health Scores: All 10 clients**
6. **Churn Prediction: All 10 clients**
7. **Interventions: Automated on high risk**
8. **Dashboard: Shows all metrics**

**CLIENT SUCCESS METRICS:**

| Metric | Description | Target |
|--------|-------------|--------|
| Health Score | Overall client health (0-100) | >70 avg |
| Churn Risk | LOW/MEDIUM/HIGH/CRITICAL | <20% HIGH |
| Onboarding Completion | % completing onboarding | >90% |
| Response Time | Avg response to client issues | <4 hours |

**ASSUMPTIONS:**
- Week 23 completed (10 clients, frontend polish)
- All clients 001-010 configured
- Frontend dashboard ready

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 24 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | Health Monitoring |
| Day 2 | 6 | Onboarding Analytics |
| Day 3 | 6 | Churn Prediction |
| Day 4 | 6 | Communication Hub |
| Day 5 | 6 | Success Dashboard |
| **Total** | **30** | **Client Success Tooling** |

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 7 PROGRESS
═══════════════════════════════════════════════════════════════════════════════

**Phase 7: Scale to 20 Clients (Weeks 21-27)**

| Week | Roadmap Goal | Status |
|------|--------------|--------|
| 21 | Clients 3-5 + Collective Intelligence | ✅ COMPLETE |
| 22 | Clients 6-10 + 85% Accuracy | ✅ COMPLETE (catch-up in W23) |
| 23 | Frontend Polish (A11y, Mobile, Dark Mode) | ✅ COMPLETE |
| 24 | Client Success Tooling | 🔄 In Progress |
| 25 | Financial Services Vertical | ⏳ Next |
| 26 | Performance Optimization | ⏳ Pending |
| 27 | 20-Client Validation | ⏳ Pending |

**Assuming Week 23 Complete:**
- Clients: 10 ✅
- Frontend: Polished ✅
- On Track for Phase 7!
