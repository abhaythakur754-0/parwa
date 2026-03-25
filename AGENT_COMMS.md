# AGENT_COMMS.md — Week 23 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 23 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 23 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-25

> **Phase: Phase 7 — Scale to 20 Clients**
>
> **Week 23 Goals:**
> - Day 1: Clients 006-010 Batch Onboarding
> - Day 2: Automated Client Provisioning System
> - Day 3: Auto-Scaling Infrastructure
> - Day 4: Load Balancer + Traffic Management
> - Day 5: Monitoring at Scale + Reports
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Scale from 5 clients to 10 clients this week
> 3. Automated provisioning for rapid onboarding
> 4. Infrastructure must auto-scale with demand
> 5. **10-client isolation: 0 data leaks in 100 tests**
> 6. **Auto-provisioning: <5 minutes per client**
> 7. **P95 <400ms at 300 concurrent users**
> 8. **Auto-scaling: handles 2x traffic spike**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Clients 006-010 Batch Onboarding
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `clients/client_006/config.py`
2. `clients/client_007/config.py`
3. `clients/client_008/config.py`
4. `clients/client_009/config.py`
5. `clients/client_010/config.py`
6. `clients/client_006-010/knowledge_base/` (batch)

### Field 2: What is each file?
1. `clients/client_006/config.py` — Retail client configuration
2. `clients/client_007/config.py` — Education client configuration
3. `clients/client_008/config.py` — Travel client configuration
4. `clients/client_009/config.py` — Real Estate client configuration
5. `clients/client_010/config.py` — Entertainment client configuration
6. `clients/client_006-010/knowledge_base/` — Knowledge bases for all 5 clients

### Field 3: Responsibilities

**clients/client_006/config.py:**
- Retail client config with:
  - Client ID: "client_006"
  - Client name: "ShopMax Retail"
  - Industry: "retail"
  - Variant: "mini" (cost-effective)
  - Timezone: "America/Chicago"
  - Business hours: 9am-9pm CST
  - Seasonal scaling enabled
  - Product catalog integration
  - **Test: Config loads correctly**

**clients/client_007/config.py:**
- Education client config with:
  - Client ID: "client_007"
  - Client name: "EduLearn Academy"
  - Industry: "education"
  - Variant: "parwa_junior"
  - Timezone: "America/New_York"
  - Business hours: 8am-8pm EST (extended for students)
  - FERPA compliance enabled
  - LMS integration
  - **Test: Config loads correctly**

**clients/client_008/config.py:**
- Travel client config with:
  - Client ID: "client_008"
  - Client name: "TravelEase"
  - Industry: "travel"
  - Variant: "parwa_high"
  - Timezone: "UTC" (global operations)
  - Business hours: 24/7
  - Multi-language support
  - Booking system integration
  - **Test: Config loads correctly**

**clients/client_009/config.py:**
- Real Estate client config with:
  - Client ID: "client_009"
  - Client name: "HomeFind Realty"
  - Industry: "real_estate"
  - Variant: "parwa_junior"
  - Timezone: "America/Los_Angeles"
  - Business hours: 8am-7pm PST
  - Property listing integration
  - Lead qualification enabled
  - **Test: Config loads correctly**

**clients/client_010/config.py:**
- Entertainment client config with:
  - Client ID: "client_010"
  - Client name: "StreamPlus Media"
  - Industry: "entertainment"
  - Variant: "parwa_high"
  - Timezone: "America/Los_Angeles"
  - Business hours: 24/7
  - Streaming platform integration
  - Content recommendation support
  - **Test: Config loads correctly**

**Knowledge Bases (client_006-010):**
- Create knowledge bases for each:
  - FAQ JSON files (20+ entries each)
  - Product/service catalogs
  - Policies specific to industry
  - Industry terminology
  - **Test: All knowledge bases load**

### Field 4: Depends On
- Weeks 19-22 client patterns
- Week 21 batch setup script
- All variant systems

### Field 5: Expected Output
- 5 new clients configured
- Total: 10 clients operational
- Knowledge bases loaded

### Field 6: Unit Test Files
- `tests/clients/test_client_006.py`
- `tests/clients/test_client_007.py`
- `tests/clients/test_client_008.py`
- `tests/clients/test_client_009.py`
- `tests/clients/test_client_010.py`

### Field 7: BDD Scenario
- 5 new clients onboarded successfully

### Field 8: Error Handling
- Individual client failure isolation
- Rollback on critical errors
- Validation before activation

### Field 9: Security Requirements
- Client isolation for all 10
- Industry-specific compliance
- Access logging

### Field 10: Integration Points
- Client management system
- Knowledge base manager
- Billing system

### Field 11: Code Quality
- Consistent client structure
- Industry-specific presets
- Validation utilities

### Field 12: GitHub CI Requirements
- All 5 client configs load
- Knowledge bases validate
- No conflicts with existing clients

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 5 clients configured
- **CRITICAL: All 10 clients load correctly**
- Knowledge bases operational
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Automated Client Provisioning System
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `provisioning/__init__.py`
2. `provisioning/client_provisioner.py`
3. `provisioning/config_generator.py`
4. `provisioning/kb_initializer.py`
5. `provisioning/dashboard_creator.py`
6. `scripts/provision_client.py`

### Field 2: What is each file?
1. `provisioning/__init__.py` — Module init
2. `provisioning/client_provisioner.py` — Main provisioning orchestrator
3. `provisioning/config_generator.py` — Generate client configurations
4. `provisioning/kb_initializer.py` — Initialize knowledge bases
5. `provisioning/dashboard_creator.py` — Create monitoring dashboards
6. `scripts/provision_client.py` — CLI provisioning tool

### Field 3: Responsibilities

**provisioning/client_provisioner.py:**
- Client provisioner with:
  - Full provisioning pipeline
  - Validate client requirements
  - Create client directory structure
  - Generate configuration
  - Initialize knowledge base
  - Create dashboard
  - Run validation
  - **CRITICAL: Provisioning <5 minutes**
  - **Test: Provisioning works end-to-end**

**provisioning/config_generator.py:**
- Config generator with:
  - Template-based config generation
  - Industry-specific defaults
  - Variant selection
  - Feature flag configuration
  - Integration settings
  - Validation rules
  - **Test: Generates valid configs**

**provisioning/kb_initializer.py:**
- KB initializer with:
  - Create knowledge base structure
  - Import industry templates
  - Initialize FAQ categories
  - Set up product catalogs
  - Configure policies
  - **Test: KB initializes correctly**

**provisioning/dashboard_creator.py:**
- Dashboard creator with:
  - Create Grafana dashboard
  - Client-specific metrics
  - Industry-specific panels
  - Alert rules setup
  - Access permissions
  - **Test: Dashboard creates correctly**

**scripts/provision_client.py:**
- CLI tool with:
  - `--name` Client name
  - `--industry` Industry type
  - `--variant` PARWA variant
  - `--timezone` Timezone
  - `--dry-run` Test without creating
  - Progress reporting
  - **Test: CLI tool works**

### Field 4: Depends On
- Week 21 batch setup patterns
- All client configurations
- Monitoring system

### Field 5: Expected Output
- Automated provisioning system
- <5 minutes per client
- CLI tool operational

### Field 6: Unit Test Files
- `tests/provisioning/test_client_provisioner.py`

### Field 7: BDD Scenario
- New client provisioned in <5 minutes

### Field 8: Error Handling
- Provisioning failure rollback
- Partial provisioning recovery
- Clear error messages

### Field 9: Security Requirements
- Secure credential generation
- Access control setup
- Audit logging

### Field 10: Integration Points
- Client management system
- Knowledge base manager
- Monitoring stack
- Billing system

### Field 11: Code Quality
- Idempotent operations
- Progress tracking
- Comprehensive logging

### Field 12: GitHub CI Requirements
- Provisioning scripts run
- Test client provisions correctly
- No conflicts

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Provisioning completes <5 minutes**
- **CRITICAL: CLI tool works**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Auto-Scaling Infrastructure
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `scaling/__init__.py`
2. `scaling/auto_scaler.py`
3. `scaling/metrics_collector.py`
4. `scaling/scaling_policies.py`
5. `scaling/resource_manager.py`
6. `tests/scaling/test_auto_scaler.py`

### Field 2: What is each file?
1. `scaling/__init__.py` — Module init
2. `scaling/auto_scaler.py` — Auto-scaling controller
3. `scaling/metrics_collector.py` — Collect scaling metrics
4. `scaling/scaling_policies.py` — Define scaling policies
5. `scaling/resource_manager.py` — Manage cloud resources
6. `tests/scaling/test_auto_scaler.py` — Scaling tests

### Field 3: Responsibilities

**scaling/auto_scaler.py:**
- Auto-scaler with:
  - Monitor system load
  - Scale up when CPU >70%
  - Scale down when CPU <30%
  - Handle traffic spikes
  - Predictive scaling
  - Cost optimization
  - **CRITICAL: Scale in <60 seconds**
  - **Test: Auto-scaling works**

**scaling/metrics_collector.py:**
- Metrics collector with:
  - CPU utilization tracking
  - Memory usage tracking
  - Request queue depth
  - Response time tracking
  - Client-specific metrics
  - Historical data analysis
  - **Test: Metrics collected correctly**

**scaling/scaling_policies.py:**
- Scaling policies with:
  - CPU-based scaling rules
  - Memory-based scaling rules
  - Request rate scaling
  - Time-based scaling (peak hours)
  - Client priority scaling
  - Min/max instance limits
  - **Test: Policies applied correctly**

**scaling/resource_manager.py:**
- Resource manager with:
  - Provision new instances
  - Terminate idle instances
  - Load balancer integration
  - Health checks
  - Resource tagging
  - Cost tracking
  - **Test: Resource management works**

**tests/scaling/test_auto_scaler.py:**
- Scaling tests with:
  - Test: Scale up on high load
  - Test: Scale down on low load
  - Test: Handle traffic spike (2x)
  - Test: Min/max limits respected
  - Test: Scaling completes in time
  - **CRITICAL: All scaling tests pass**

### Field 4: Depends On
- Week 18 Kubernetes infrastructure
- Monitoring system
- All 10 clients

### Field 5: Expected Output
- Auto-scaling operational
- Handles 2x traffic spike
- <60 seconds scale time

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- System auto-scales with traffic

### Field 8: Error Handling
- Scaling failure recovery
- Resource exhaustion handling
- Graceful degradation

### Field 9: Security Requirements
- Secure instance provisioning
- Network isolation
- Access control

### Field 10: Integration Points
- Kubernetes cluster
- Monitoring system
- Load balancer

### Field 11: Code Quality
- Idempotent scaling
- Clear policies
- Comprehensive monitoring

### Field 12: GitHub CI Requirements
- Scaling tests pass
- No resource leaks
- Policies validated

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Auto-scaling works**
- **CRITICAL: Handles 2x traffic spike**
- **CRITICAL: Scale time <60 seconds**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Load Balancer + Traffic Management
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `loadbalancer/__init__.py`
2. `loadbalancer/traffic_router.py`
3. `loadbalancer/client_sharding.py`
4. `loadbalancer/health_checker.py`
5. `tests/performance/test_300_concurrent.py`

### Field 2: What is each file?
1. `loadbalancer/__init__.py` — Module init
2. `loadbalancer/traffic_router.py` — Route traffic to instances
3. `loadbalancer/client_sharding.py` — Client-based sharding
4. `loadbalancer/health_checker.py` — Health check system
5. `tests/performance/test_300_concurrent.py` — 300 concurrent user test

### Field 3: Responsibilities

**loadbalancer/traffic_router.py:**
- Traffic router with:
  - Round-robin load balancing
  - Weighted distribution by client tier
  - Session affinity support
  - Failover handling
  - Geographic routing
  - Rate limiting per client
  - **Test: Routing works correctly**

**loadbalancer/client_sharding.py:**
- Client sharding with:
  - Shard clients across instances
  - Isolate high-traffic clients
  - Balance resource usage
  - Client affinity options
  - Shard rebalancing
  - **Test: Sharding works**

**loadbalancer/health_checker.py:**
- Health checker with:
  - Active health checks (every 10s)
  - Passive health monitoring
  - Unhealthy instance removal
  - Automatic recovery detection
  - Health score calculation
  - **Test: Health checks work**

**tests/performance/test_300_concurrent.py:**
- Performance test with:
  - Test: 300 concurrent users across 10 clients
  - Test: P95 <400ms (improved)
  - Test: P99 <700ms
  - Test: No errors under load
  - Test: Fair resource distribution
  - Test: Graceful degradation
  - **CRITICAL: P95 <400ms at 300 users**
  - **Test: Performance tests pass**

### Field 4: Depends On
- Week 18 Kubernetes infrastructure
- Day 3 auto-scaling
- All 10 clients

### Field 5: Expected Output
- Load balancing operational
- Client sharding active
- P95 <400ms at 300 users

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- System handles 300 concurrent users

### Field 8: Error Handling
- Instance failure handling
- Traffic rerouting
- Graceful degradation

### Field 9: Security Requirements
- DDoS protection
- Rate limiting
- Access control

### Field 10: Integration Points
- Kubernetes services
- Auto-scaler
- Monitoring

### Field 11: Code Quality
- Efficient routing
- Low latency
- High availability

### Field 12: GitHub CI Requirements
- Load balancing tests pass
- Performance tests pass
- Health checks validated

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 5 files built and pushed
- **CRITICAL: P95 <400ms at 300 users**
- **CRITICAL: Load balancing works**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Monitoring at Scale + Reports
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `monitoring/dashboards/scale_dashboard.json`
2. `tests/integration/test_10_client_isolation.py`
3. `reports/week23_scaling_report.md`
4. `reports/client_distribution.md`
5. `PROJECT_STATE.md` (Phase 7 week 1 update)
6. `docs/scaling_architecture.md`

### Field 2: What is each file?
1. `monitoring/dashboards/scale_dashboard.json` — Scale monitoring dashboard
2. `tests/integration/test_10_client_isolation.py` — 10-client isolation tests
3. `reports/week23_scaling_report.md` — Week 23 scaling report
4. `reports/client_distribution.md` — Client distribution report
5. `PROJECT_STATE.md` — Updated with 10 clients
6. `docs/scaling_architecture.md` — Scaling architecture documentation

### Field 3: Responsibilities

**monitoring/dashboards/scale_dashboard.json:**
- Scale dashboard with:
  - All 10 client metrics
  - Instance count graph
  - CPU/Memory utilization
  - Request rate per client
  - Response time distribution
  - Auto-scaling events
  - Cost metrics
  - **Test: Dashboard loads in Grafana**

**tests/integration/test_10_client_isolation.py:**
- 10-client isolation tests with:
  - Test: Each client isolated (100 tests)
  - Test: Cross-tenant queries return 0 rows
  - Test: API isolation for all 10
  - Test: Database RLS enforced
  - Test: Healthcare (client_003) HIPAA
  - Test: FinTech (client_005) PCI DSS
  - Test: Education (client_007) FERPA
  - **CRITICAL: 0 data leaks in 100 tests**
  - **Test: All isolation tests pass**

**reports/week23_scaling_report.md:**
- Scaling report with:
  - Clients: 5 → 10 (doubled)
  - Provisioning time: <5 minutes
  - Performance: P95 <400ms at 300 users
  - Auto-scaling: Operational
  - Key achievements
  - **Content: Complete scaling report**

**reports/client_distribution.md:**
- Client distribution with:
  - All 10 clients listed
  - Industry breakdown
  - Variant distribution
  - Resource allocation
  - Geographic distribution
  - Growth trajectory
  - **Content: Complete distribution report**

**PROJECT_STATE.md:**
- State update with:
  - Phase 7 in progress
  - Week 23 summary
  - 10 clients active
  - Next: Week 24 (clients 11-20)
  - **Updated correctly**

**docs/scaling_architecture.md:**
- Architecture doc with:
  - Multi-tenant architecture
  - Auto-scaling design
  - Load balancing strategy
  - Client sharding approach
  - Monitoring at scale
  - Future scaling roadmap
  - **Content: Complete architecture doc**

### Field 4: Depends On
- All Week 23 work
- All 10 clients
- Auto-scaling system

### Field 5: Expected Output
- Monitoring at scale
- 10-client isolation verified
- Reports complete

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- 10 clients operational with isolation

### Field 8: Error Handling
- Report generation fallbacks
- Missing data handling

### Field 9: Security Requirements
- No sensitive data in reports
- Client isolation in metrics

### Field 10: Integration Points
- All monitoring systems
- All 10 clients

### Field 11: Code Quality
- Comprehensive monitoring
- Clear documentation

### Field 12: GitHub CI Requirements
- Isolation tests pass
- Reports generate
- Dashboard loads

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: 0 data leaks in 100 isolation tests**
- All reports generated
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 23 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. New Client Validation
```bash
pytest tests/clients/test_client_006.py -v
pytest tests/clients/test_client_007.py -v
pytest tests/clients/test_client_008.py -v
pytest tests/clients/test_client_009.py -v
pytest tests/clients/test_client_010.py -v
```

#### 2. Provisioning System Tests
```bash
pytest tests/provisioning/test_client_provisioner.py -v
python scripts/provision_client.py --dry-run --name "Test Client" --industry "test"
```

#### 3. 10-Client Isolation Tests
```bash
pytest tests/integration/test_10_client_isolation.py -v
```

#### 4. Scaling Tests
```bash
pytest tests/scaling/test_auto_scaler.py -v
```

#### 5. Performance Tests
```bash
pytest tests/performance/test_300_concurrent.py -v
```

#### 6. Load Balancer Tests
```bash
pytest tests/loadbalancer/ -v
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | Clients 006-010 | All load correctly |
| 2 | Total clients | 10 active |
| 3 | Provisioning time | <5 minutes |
| 4 | 10-client isolation | 0 data leaks in 100 tests |
| 5 | Auto-scaling | Works in <60 seconds |
| 6 | Traffic spike handling | 2x spike handled |
| 7 | Performance P95 | <400ms at 300 users |
| 8 | Load balancing | Works correctly |
| 9 | Health checks | Active and working |
| 10 | Dashboard | Loads in Grafana |

---

### Week 23 PASS Criteria

1. ✅ 10 clients active (5 new onboarded)
2. ✅ Provisioning completes <5 minutes
3. ✅ 10-client isolation: 0 data leaks in 100 tests
4. ✅ Auto-scaling works in <60 seconds
5. ✅ Handles 2x traffic spike
6. ✅ P95 <400ms at 300 concurrent users
7. ✅ Load balancing operational
8. ✅ Health checks working
9. ✅ All reports generated
10. ✅ GitHub CI pipeline GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests | Pushed |
|---------|-----|--------|-------|-------|--------|
| Builder 1 | Day 1 | ⏳ PENDING | Clients 006-010 (6 files) | - | NO |
| Builder 2 | Day 2 | ⏳ PENDING | Provisioning System (6 files) | - | NO |
| Builder 3 | Day 3 | ⏳ PENDING | Auto-Scaling (6 files) | - | NO |
| Builder 4 | Day 4 | ⏳ PENDING | Load Balancer (5 files) | - | NO |
| Builder 5 | Day 5 | ⏳ PENDING | Monitoring + Reports (6 files) | - | NO |
| Tester | Day 6 | ⏳ PENDING | Full validation | - | NO |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. Scale from 5 to 10 clients this week
3. Automated provisioning is key for scaling
4. Auto-scaling must handle traffic spikes
5. **10-client isolation: 0 data leaks in 100 tests**
6. **Provisioning: <5 minutes per client**
7. **P95: <400ms at 300 users**
8. **Auto-scaling: <60 seconds to scale**
9. **Traffic spike: handles 2x**

**SCALING MILESTONES:**
- Phase 6: 5 clients ✅
- Week 23: 10 clients (2x)
- Week 24: 20 clients (4x)
- Phase 8: 50 clients

**NEW INDUSTRIES ADDED:**
- Retail (client_006)
- Education (client_007) - FERPA
- Travel (client_008)
- Real Estate (client_009)
- Entertainment (client_010)

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 23 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | Clients 006-010 |
| Day 2 | 6 | Provisioning System |
| Day 3 | 6 | Auto-Scaling |
| Day 4 | 5 | Load Balancer |
| Day 5 | 6 | Monitoring + Reports |
| **Total** | **29** | **Scale to 10 Clients** |

---

═══════════════════════════════════════════════════════════════════════════════
## EXECUTION ORDER
═══════════════════════════════════════════════════════════════════════════════

```
Week 23 FULLY PARALLEL Execution:

Day 1-5: ALL BUILDERS RUN SIMULTANEOUSLY
├── Builder 1: Clients 006-010 (6 files)
├── Builder 2: Provisioning System (6 files)
├── Builder 3: Auto-Scaling (6 files)
├── Builder 4: Load Balancer (5 files)
└── Builder 5: Monitoring + Reports (6 files)

Day 6: Tester → 10-Client + Scaling + Performance validation
```

**ALL Builders can start NOW. No waiting required.**

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 7 PROGRESS
═══════════════════════════════════════════════════════════════════════════════

**Phase 7: Scale to 20 Clients**

| Week | Goal | Status |
|------|------|--------|
| Week 23 | 5→10 Clients + Infrastructure | 🔄 In Progress |
| Week 24 | 10→20 Clients + Optimization | ⏳ Pending |

**Phase 7 Targets:**
- [ ] 20 clients operational
- [ ] <5 minute provisioning
- [ ] P95 <350ms at 500 users
- [ ] Auto-scaling operational
- [ ] Global load balancing
- [ ] Multi-region support
