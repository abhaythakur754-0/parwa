# AGENT_COMMS.md — Week 37 Day 1-6
# Last updated by: Manager Agent
# Current status: WEEK 37 — 50-CLIENT SCALE + AUTOSCALING

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 37 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-28

> **Phase: Phase 8 — Enterprise Preparation (Weeks 28-40)**
>
> **Week 37 Goals (Per Roadmap):**
> - Day 1: Clients 31-50 Configs (20 new clients)
> - Day 2: 50-Client Test Infrastructure
> - Day 3: K8s HPA + KEDA + PgBouncer + VPA (chain)
> - Day 4: Cost Optimisation
> - Day 5: Documentation + Integration Tests
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Scale from 30 clients to 50 clients
> 3. **500 cross-tenant isolation tests: 0 leaks**
> 4. **2000 concurrent users P95 <300ms**
> 5. **K8s HPA: backend scales to 10+ pods**
> 6. **KEDA: workers scale with queue depth**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Clients 31-50 Configs
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `tests/clients/test_clients_031_035.py`
2. `tests/clients/test_clients_036_040.py`
3. `tests/clients/test_clients_041_045.py`
4. `tests/clients/test_clients_046_050.py`
5. `backend/seeds/seed_clients_031_050.py`
6. `tests/clients/__init__.py` (update)

### Field 2: What is each file?
1. `test_clients_031_035.py` — Tests for clients 31-35 (varied industries)
2. `test_clients_036_040.py` — Tests for clients 36-40 (varied industries)
3. `test_clients_041_045.py` — Tests for clients 41-45 (varied industries)
4. `test_clients_046_050.py` — Tests for clients 46-50 (varied industries)
5. `seed_clients_031_050.py` — Seed data for clients 31-50
6. `__init__.py` — Update exports

### Field 3: Responsibilities

**test_clients_031_035.py:**
- Client 031: EduTech (SaaS variant)
- Client 032: FoodDelivery (E-commerce variant)
- Client 033: InsureTech (Financial variant)
- Client 034: TeleHealth (Healthcare variant)
- Client 035: FreightCo (Logistics variant)
- **Test: All 5 clients initialize correctly**
- **Test: Cross-tenant isolation verified**

**test_clients_036_040.py:**
- Client 036: RealEstate (SaaS variant)
- Client 037: Gaming (E-commerce variant)
- Client 038: CryptoExchange (Financial variant)
- Client 039: DentalCare (Healthcare variant)
- Client 040: ShippingCo (Logistics variant)
- **Test: All 5 clients initialize correctly**
- **Test: Cross-tenant isolation verified**

**test_clients_041_045.py:**
- Client 041: HRPlatform (SaaS variant)
- Client 042: FashionRetail (E-commerce variant)
- Client 043: WealthMgmt (Financial variant)
- Client 044: VetClinic (Healthcare variant)
- Client 045: CourierX (Logistics variant)
- **Test: All 5 clients initialize correctly**
- **Test: Cross-tenant isolation verified**

**test_clients_046_050.py:**
- Client 046: LegalTech (SaaS variant)
- Client 047: Electronics (E-commerce variant)
- Client 048: PaymentGateway (Financial variant)
- Client 049: MentalHealth (Healthcare variant)
- Client 050: GlobalShip (Logistics variant)
- **Test: All 5 clients initialize correctly**
- **Test: Cross-tenant isolation verified**

**seed_clients_031_050.py:**
- Seed data for all 20 new clients
- Industry-specific configurations
- Variant assignments
- **Test: All 20 clients seeded correctly**

### Field 4: Depends On
- Existing client infrastructure (Weeks 21-30)
- Test patterns from test_clients_026_030.py
- Company model (backend/models/company.py)

### Field 5: Expected Output
- 20 new client configurations (31-50)
- 50 total clients ready for testing

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All 20 clients (31-50) initialize correctly**
- **CRITICAL: Cross-tenant isolation verified for all**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — 50-Client Test Infrastructure
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `tests/integration/test_50_client_isolation.py`
2. `tests/performance/test_50_client_load.py`
3. `tests/integration/test_50_client_operations.py`
4. `scripts/validate_50_tenant.py`
5. `tests/performance/__init__.py`
6. `reports/week37_50_client_report.md`

### Field 2: What is each file?
1. `test_50_client_isolation.py` — Cross-tenant isolation tests for 50 clients
2. `test_50_client_load.py` — Load testing for 50 clients (2000 concurrent)
3. `test_50_client_operations.py` — Operations test for all 50 clients
4. `validate_50_tenant.py` — Validation script for 50-tenant setup
5. `__init__.py` — Module init
6. `week37_50_client_report.md` — Week 37 50-client report

### Field 3: Responsibilities

**test_50_client_isolation.py:**
- 500 cross-tenant isolation tests
- Data leak detection across all 50 clients
- RLS policy verification
- **Test: 0 data leaks in 500 tests**
- **Test: Each client only sees their own data**

**test_50_client_load.py:**
- Load test with 2000 concurrent users
- P95 latency measurement
- Throughput measurement
- **Test: P95 <300ms at 2000 users**
- **Test: No timeouts or errors**

**test_50_client_operations.py:**
- Ticket creation for all 50 clients
- Refund workflow for all 50 clients
- Knowledge base operations
- **Test: All operations work for all 50 clients**

**validate_50_tenant.py:**
- Script to validate 50-tenant configuration
- Database connectivity check
- RLS policy check
- **Test: All 50 tenants validated**

**week37_50_client_report.md:**
- Summary of 50-client validation
- Performance metrics
- Known issues
- Next steps

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: 500 cross-tenant tests: 0 leaks**
- **CRITICAL: 2000 concurrent users P95 <300ms**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — K8s HPA + KEDA + PgBouncer + VPA
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `infra/k8s/hpa.yaml`
2. `infra/k8s/keda-scaler.yaml`
3. `infra/k8s/pgbouncer.yaml`
4. `infra/k8s/vpa.yaml`
5. `tests/k8s/test_autoscaling.py`
6. `infra/k8s/autoscaling-readme.md`

### Field 2: What is each file?
1. `hpa.yaml` — Horizontal Pod Autoscaler for backend
2. `keda-scaler.yaml` — KEDA scaler for workers
3. `pgbouncer.yaml` — PgBouncer connection pooler
4. `vpa.yaml` — Vertical Pod Autoscaler
5. `test_autoscaling.py` — Autoscaling tests
6. `autoscaling-readme.md` — Autoscaling documentation

### Field 3: Responsibilities

**hpa.yaml:**
- HPA for backend deployment
- Min replicas: 2, Max replicas: 20
- CPU target: 70%
- Memory target: 80%
- **Test: Scales to 10+ pods under load**

**keda-scaler.yaml:**
- KEDA ScaledObject for workers
- Redis queue depth trigger
- Scale on pending jobs
- **Test: Workers scale with queue depth**

**pgbouncer.yaml:**
- PgBouncer deployment
- Transaction mode pooling
- Max connections: 500
- **Test: Connection pooling works**

**vpa.yaml:**
- VPA for backend and workers
- Auto resource recommendations
- Update mode: Auto
- **Test: VPA recommendations generated**

**test_autoscaling.py:**
- HPA scaling test
- KEDA scaling test
- PgBouncer connection test
- VPA recommendation test
- **Test: All autoscaling components work**

### Field 4: Depends On
- Existing K8s infrastructure (Week 18)
- backend-deployment.yaml
- worker-deployment.yaml

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: HPA scales to 10+ pods**
- **CRITICAL: KEDA scales workers with queue depth**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Cost Optimisation
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/optimization/cost_monitor.py`
2. `backend/optimization/resource_optimizer.py`
3. `infra/terraform/cost_estimation.tf`
4. `scripts/cost_report.py`
5. `tests/optimization/test_cost.py`
6. `reports/cost_optimization_report.md`

### Field 2: What is each file?
1. `cost_monitor.py` — Cost monitoring service
2. `resource_optimizer.py` — Resource optimization logic
3. `cost_estimation.tf` — Terraform cost estimation
4. `cost_report.py` — Cost report generation script
5. `test_cost.py` — Cost optimization tests
6. `cost_optimization_report.md` — Cost optimization documentation

### Field 3: Responsibilities

**cost_monitor.py:**
- Monitor resource costs
- Track API usage costs
- Alert on cost thresholds
- **Test: Cost monitoring works**

**resource_optimizer.py:**
- Optimize resource allocation
- Right-size recommendations
- Unused resource detection
- **Test: Optimization recommendations generated**

**cost_estimation.tf:**
- Terraform cost estimation
- Resource tagging
- Budget alerts
- **Test: Terraform plan shows costs**

**cost_report.py:**
- Generate cost reports
- Cost trend analysis
- Savings opportunities
- **Test: Report generated successfully**

**test_cost.py:**
- Cost monitoring tests
- Optimization tests
- Report tests
- **Test: All cost features work**

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Cost monitoring works**
- **CRITICAL: Optimization recommendations generated**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Documentation + Integration Tests
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `docs/week37_50_client_guide.md`
2. `docs/autoscaling_guide.md`
3. `tests/integration/test_week37_complete.py`
4. `reports/week37_summary.md`
5. `docs/phase8_completion_checklist.md`
6. `docs/api-documentation.md` (update)

### Field 2: What is each file?
1. `week37_50_client_guide.md` — 50-client setup guide
2. `autoscaling_guide.md` — Autoscaling documentation
3. `test_week37_complete.py` — Week 37 integration tests
4. `week37_summary.md` — Week 37 summary report
5. `phase8_completion_checklist.md` — Phase 8 checklist
6. `api-documentation.md` — Update API docs

### Field 3: Responsibilities

**week37_50_client_guide.md:**
- How to add new clients
- Client configuration options
- Industry-specific settings
- **Test: Documentation complete**

**autoscaling_guide.md:**
- HPA configuration
- KEDA setup
- PgBouncer configuration
- VPA recommendations
- **Test: Documentation complete**

**test_week37_complete.py:**
- Full Week 37 integration test
- 50-client validation
- Autoscaling validation
- **CRITICAL: All Week 37 tests pass**

**week37_summary.md:**
- Week 37 summary
- Files built
- Tests passing
- Known issues

**phase8_completion_checklist.md:**
- Phase 8 progress
- Weeks 28-37 completion status
- Remaining work
- **Test: Checklist accurate**

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All integration tests pass**
- **CRITICAL: Documentation complete**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 37 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. Client Tests (31-50)
```bash
pytest tests/clients/test_clients_031_035.py tests/clients/test_clients_036_040.py tests/clients/test_clients_041_045.py tests/clients/test_clients_046_050.py -v
```

#### 2. 50-Client Isolation Tests
```bash
pytest tests/integration/test_50_client_isolation.py -v
```

#### 3. Performance Tests
```bash
pytest tests/performance/test_50_client_load.py -v
```

#### 4. Autoscaling Tests
```bash
pytest tests/k8s/test_autoscaling.py -v
```

#### 5. Full Week 37 Integration
```bash
pytest tests/integration/test_week37_complete.py -v
```

#### 6. Complete Test Suite
```bash
pytest tests/ -v --tb=short
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | 50 clients configured | All 50 operational |
| 2 | Cross-tenant isolation | 500 tests, 0 leaks |
| 3 | Load test 2000 users | P95 <300ms |
| 4 | HPA scaling | 10+ pods under load |
| 5 | KEDA scaling | Workers scale with queue |
| 6 | PgBouncer | Connection pooling works |
| 7 | VPA | Recommendations generated |
| 8 | Cost monitoring | Works correctly |
| 9 | Documentation | Complete and accurate |
| 10 | Full test suite | 100% pass rate |

---

### Week 37 PASS Criteria

1. ✅ **50 Clients: All operational**
2. ✅ **500 Cross-tenant Tests: 0 leaks**
3. ✅ **2000 Concurrent Users: P95 <300ms**
4. ✅ **HPA: Scales to 10+ pods**
5. ✅ **KEDA: Workers scale with queue depth**
6. ✅ **PgBouncer: Connection pooling works**
7. ✅ **VPA: Recommendations generated**
8. ✅ **Cost Monitoring: Works correctly**
9. ✅ **Documentation: Complete**
10. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Focus | Files | Status |
|---------|-----|-------|-------|--------|
| Builder 1 | Day 1 | Clients 31-50 Configs | 6 | ⏳ Pending |
| Builder 2 | Day 2 | 50-Client Test Infrastructure | 6 | ⏳ Pending |
| Builder 3 | Day 3 | K8s HPA + KEDA + PgBouncer + VPA | 6 | ⏳ Pending |
| Builder 4 | Day 4 | Cost Optimisation | 6 | ⏳ Pending |
| Builder 5 | Day 5 | Documentation + Integration Tests | 6 | ⏳ Pending |
| Tester | Day 6 | Full Validation | - | ⏳ Pending |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. **50 clients must be fully operational**
3. **500 cross-tenant isolation tests: 0 leaks (MANDATORY)**
4. **2000 concurrent users P95 <300ms (MANDATORY)**
5. **HPA must scale to 10+ pods under load**
6. **KEDA must scale workers based on queue depth**

**WEEK 37 TARGETS:**

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Clients | 30 | 50 | 🎯 +20 clients |
| Cross-tenant Tests | ~300 | 500 | 🎯 Target |
| Concurrent Users | 500 | 2000 | 🎯 Target |
| HPA Pods | 3 | 10+ | 🎯 Target |
| KEDA Workers | 2 | Auto | 🎯 Target |
| P95 Latency | ~250ms | <300ms | ✅ Maintain |

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 37 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | Clients 31-50 Configs |
| Day 2 | 6 | 50-Client Test Infrastructure |
| Day 3 | 6 | K8s Autoscaling Stack |
| Day 4 | 6 | Cost Optimisation |
| Day 5 | 6 | Documentation + Tests |
| **Total** | **30** | **50-Client Scale + Autoscaling** |

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 8 PROGRESS
═══════════════════════════════════════════════════════════════════════════════

**Phase 8: Enterprise Preparation (Weeks 28-40)**

| Week | Roadmap Goal | Status |
|------|--------------|--------|
| 28 | Agent Lightning 90% Milestone | ✅ COMPLETE |
| 29 | Multi-Region Data Residency | ✅ COMPLETE |
| 30 | 30-Client Milestone | ✅ COMPLETE |
| 31 | E-commerce Advanced | ✅ COMPLETE |
| 32 | SaaS Advanced | ✅ COMPLETE |
| 33 | Healthcare HIPAA + Logistics | ✅ COMPLETE |
| 34 | Frontend v2 (React Query + PWA) | ✅ COMPLETE |
| 35 | Smart Router 92%+ | ✅ COMPLETE |
| 36 | Agent Lightning 94% | ✅ COMPLETE |
| **37** | **50-Client Scale + Autoscaling** | **🔄 IN PROGRESS** |
| 38 | Enterprise Pre-Preparation | ⏳ Pending |
| 39 | Final Production Readiness | ⏳ Pending |
| 40 | Weeks 1-40 Final Validation | ⏳ Pending |

**Week 37 Deliverables:**
- 20 new clients (31-50) 🎯 Target
- 50-client test infrastructure 🎯 Target
- K8s autoscaling stack 🎯 Target
- Cost optimisation 🎯 Target
- **50-CLIENT SCALE + AUTOSCALING COMPLETE!**
