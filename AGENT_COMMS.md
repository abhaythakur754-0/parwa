# AGENT_COMMS.md — Week 29 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 29 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 29 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-26

> **Phase: Phase 8 — Enterprise Preparation (Weeks 28-40)**
>
> **Week 29 Goals (Per Roadmap):**
> - Day 1: EU Region Infrastructure
> - Day 2: US Region Infrastructure
> - Day 3: APAC Region Infrastructure
> - Day 4: Data Residency Enforcer
> - Day 5: Cross-Region Replication
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Multi-Region Data Residency per roadmap
> 3. Build `infra/terraform/regions/eu/`, `us/`, `apac/`
> 4. **EU client data absent from US region DB**
> 5. **Cross-region isolation: 0 leaks**
> 6. **DB replication lag <500ms**
> 7. **GDPR export: only data from client's assigned region**
> 8. **Data sovereignty compliance**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — EU Region Infrastructure
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `infra/terraform/regions/eu/__init__.py`
2. `infra/terraform/regions/eu/main.tf`
3. `infra/terraform/regions/eu/database.tf`
4. `infra/terraform/regions/eu/redis.tf`
5. `infra/terraform/regions/eu/variables.tf`
6. `tests/infrastructure/test_eu_region.py`

### Field 2: What is each file?
1. `infra/terraform/regions/eu/__init__.py` — Module init
2. `infra/terraform/regions/eu/main.tf` — EU region main config
3. `infra/terraform/regions/eu/database.tf` — EU database config
4. `infra/terraform/regions/eu/redis.tf` — EU Redis config
5. `infra/terraform/regions/eu/variables.tf` — EU variables
6. `tests/infrastructure/test_eu_region.py` — EU region tests

### Field 3: Responsibilities

**infra/terraform/regions/eu/main.tf:**
- EU region main with:
  - Provider: AWS eu-west-1 (Ireland)
  - VPC configuration for EU
  - Subnets for EU region
  - Security groups (GDPR compliant)
  - NAT gateway for EU
  - **Test: Terraform plan succeeds**

**infra/terraform/regions/eu/database.tf:**
- EU database with:
  - PostgreSQL instance in eu-west-1
  - Encryption at rest (GDPR requirement)
  - Automated backups in EU
  - Point-in-time recovery
  - Read replicas in EU only
  - **Test: DB instance configured**

**infra/terraform/regions/eu/redis.tf:**
- EU Redis with:
  - ElastiCache cluster in eu-west-1
  - Encryption in transit
  - Encryption at rest
  - EU-only replication
  - Automatic failover
  - **Test: Redis configured**

**infra/terraform/regions/eu/variables.tf:**
- EU variables with:
  - Region: eu-west-1
  - Instance types
  - Database settings
  - Redis settings
  - Backup retention
  - **Test: Variables validate**

**tests/infrastructure/test_eu_region.py:**
- EU region tests with:
  - Test: Terraform validates
  - Test: EU region resources defined
  - Test: Database in EU only
  - Test: Redis in EU only
  - **CRITICAL: EU region infrastructure works**

### Field 4: Depends On
- Terraform infrastructure
- AWS provider configuration

### Field 5: Expected Output
- EU region infrastructure defined
- GDPR-compliant setup

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- EU clients have data stored only in EU region

### Field 8: Error Handling
- Terraform validation errors
- Resource conflicts

### Field 9: Security Requirements
- Encryption at rest
- Encryption in transit
- EU data sovereignty

### Field 10: Integration Points
- Terraform
- AWS provider
- Global infrastructure

### Field 11: Code Quality
- Terraform best practices
- Clear documentation

### Field 12: GitHub CI Requirements
- Terraform validate passes
- EU region tests pass

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: EU region infrastructure defined**
- **CRITICAL: Terraform validates**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — US Region Infrastructure
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `infra/terraform/regions/us/__init__.py`
2. `infra/terraform/regions/us/main.tf`
3. `infra/terraform/regions/us/database.tf`
4. `infra/terraform/regions/us/redis.tf`
5. `infra/terraform/regions/us/variables.tf`
6. `tests/infrastructure/test_us_region.py`

### Field 2: What is each file?
1. `infra/terraform/regions/us/__init__.py` — Module init
2. `infra/terraform/regions/us/main.tf` — US region main config
3. `infra/terraform/regions/us/database.tf` — US database config
4. `infra/terraform/regions/us/redis.tf` — US Redis config
5. `infra/terraform/regions/us/variables.tf` — US variables
6. `tests/infrastructure/test_us_region.py` — US region tests

### Field 3: Responsibilities

**infra/terraform/regions/us/main.tf:**
- US region main with:
  - Provider: AWS us-east-1 (N. Virginia)
  - VPC configuration for US
  - Subnets for US region
  - Security groups
  - NAT gateway for US
  - **Test: Terraform plan succeeds**

**infra/terraform/regions/us/database.tf:**
- US database with:
  - PostgreSQL instance in us-east-1
  - Encryption at rest
  - Automated backups in US
  - Point-in-time recovery
  - Read replicas in US only
  - **Test: DB instance configured**

**infra/terraform/regions/us/redis.tf:**
- US Redis with:
  - ElastiCache cluster in us-east-1
  - Encryption in transit
  - Encryption at rest
  - US-only replication
  - Automatic failover
  - **Test: Redis configured**

**infra/terraform/regions/us/variables.tf:**
- US variables with:
  - Region: us-east-1
  - Instance types
  - Database settings
  - Redis settings
  - Backup retention
  - **Test: Variables validate**

**tests/infrastructure/test_us_region.py:**
- US region tests with:
  - Test: Terraform validates
  - Test: US region resources defined
  - Test: Database in US only
  - Test: Redis in US only
  - **CRITICAL: US region infrastructure works**

### Field 4: Depends On
- Terraform infrastructure
- AWS provider configuration

### Field 5: Expected Output
- US region infrastructure defined
- CCPA-compliant setup

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- US clients have data stored only in US region

### Field 8: Error Handling
- Terraform validation errors
- Resource conflicts

### Field 9: Security Requirements
- Encryption at rest
- Encryption in transit
- US data sovereignty

### Field 10: Integration Points
- Terraform
- AWS provider
- Global infrastructure

### Field 11: Code Quality
- Terraform best practices
- Clear documentation

### Field 12: GitHub CI Requirements
- Terraform validate passes
- US region tests pass

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: US region infrastructure defined**
- **CRITICAL: Terraform validates**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — APAC Region Infrastructure
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `infra/terraform/regions/apac/__init__.py`
2. `infra/terraform/regions/apac/main.tf`
3. `infra/terraform/regions/apac/database.tf`
4. `infra/terraform/regions/apac/redis.tf`
5. `infra/terraform/regions/apac/variables.tf`
6. `tests/infrastructure/test_apac_region.py`

### Field 2: What is each file?
1. `infra/terraform/regions/apac/__init__.py` — Module init
2. `infra/terraform/regions/apac/main.tf` — APAC region main config
3. `infra/terraform/regions/apac/database.tf` — APAC database config
4. `infra/terraform/regions/apac/redis.tf` — APAC Redis config
5. `infra/terraform/regions/apac/variables.tf` — APAC variables
6. `tests/infrastructure/test_apac_region.py` — APAC region tests

### Field 3: Responsibilities

**infra/terraform/regions/apac/main.tf:**
- APAC region main with:
  - Provider: AWS ap-southeast-1 (Singapore)
  - VPC configuration for APAC
  - Subnets for APAC region
  - Security groups
  - NAT gateway for APAC
  - **Test: Terraform plan succeeds**

**infra/terraform/regions/apac/database.tf:**
- APAC database with:
  - PostgreSQL instance in ap-southeast-1
  - Encryption at rest
  - Automated backups in APAC
  - Point-in-time recovery
  - Read replicas in APAC only
  - **Test: DB instance configured**

**infra/terraform/regions/apac/redis.tf:**
- APAC Redis with:
  - ElastiCache cluster in ap-southeast-1
  - Encryption in transit
  - Encryption at rest
  - APAC-only replication
  - Automatic failover
  - **Test: Redis configured**

**infra/terraform/regions/apac/variables.tf:**
- APAC variables with:
  - Region: ap-southeast-1
  - Instance types
  - Database settings
  - Redis settings
  - Backup retention
  - **Test: Variables validate**

**tests/infrastructure/test_apac_region.py:**
- APAC region tests with:
  - Test: Terraform validates
  - Test: APAC region resources defined
  - Test: Database in APAC only
  - Test: Redis in APAC only
  - **CRITICAL: APAC region infrastructure works**

### Field 4: Depends On
- Terraform infrastructure
- AWS provider configuration

### Field 5: Expected Output
- APAC region infrastructure defined
- Asian data compliance ready

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- APAC clients have data stored only in APAC region

### Field 8: Error Handling
- Terraform validation errors
- Resource conflicts

### Field 9: Security Requirements
- Encryption at rest
- Encryption in transit
- APAC data sovereignty

### Field 10: Integration Points
- Terraform
- AWS provider
- Global infrastructure

### Field 11: Code Quality
- Terraform best practices
- Clear documentation

### Field 12: GitHub CI Requirements
- Terraform validate passes
- APAC region tests pass

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: APAC region infrastructure defined**
- **CRITICAL: Terraform validates**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Data Residency Enforcer
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/compliance/residency/__init__.py`
2. `backend/compliance/residency/residency_enforcer.py`
3. `backend/compliance/residency/region_router.py`
4. `backend/compliance/residency/sovereignty_checker.py`
5. `backend/compliance/residency/gdpr_export.py`
6. `tests/compliance/test_residency.py`

### Field 2: What is each file?
1. `backend/compliance/residency/__init__.py` — Module init
2. `backend/compliance/residency/residency_enforcer.py` — Residency enforcement
3. `backend/compliance/residency/region_router.py` — Region routing
4. `backend/compliance/residency/sovereignty_checker.py` — Sovereignty checking
5. `backend/compliance/residency/gdpr_export.py` — GDPR export handler
6. `tests/compliance/test_residency.py` — Residency tests

### Field 3: Responsibilities

**backend/compliance/residency/residency_enforcer.py:**
- Residency enforcer with:
  - Enforce data stays in assigned region
  - Block cross-region data access
  - Validate region assignment on read/write
  - Log all cross-region attempts
  - Alert on violations
  - **Test: Enforcer blocks cross-region access**

**backend/compliance/residency/region_router.py:**
- Region router with:
  - Route requests to correct region
  - Client-to-region mapping
  - Dynamic region selection
  - Failover handling
  - Latency optimization
  - **Test: Router routes correctly**

**backend/compliance/residency/sovereignty_checker.py:**
- Sovereignty checker with:
  - Check data sovereignty requirements
  - Validate client region assignment
  - Check compliance per region
  - Audit sovereignty status
  - Report violations
  - **Test: Checker validates sovereignty**

**backend/compliance/residency/gdpr_export.py:**
- GDPR export with:
  - Export all client data from assigned region
  - Only data from client's region
  - Portable format (JSON)
  - Complete data inventory
  - Right to erasure support
  - **Test: Export only assigned region data**

**tests/compliance/test_residency.py:**
- Residency tests with:
  - Test: Enforcer blocks cross-region
  - Test: Router routes correctly
  - Test: Sovereignty checker works
  - Test: GDPR export from correct region
  - **CRITICAL: Data residency enforced**

### Field 4: Depends On
- Region infrastructure (Day 1-3)
- Compliance layer (Week 7)

### Field 5: Expected Output
- Data residency enforcement operational
- Cross-region access blocked

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- EU client data cannot be accessed from US region

### Field 8: Error Handling
- Cross-region access attempts
- Region unavailability

### Field 9: Security Requirements
- Strict region isolation
- Audit all access

### Field 10: Integration Points
- Database layer
- API layer
- Client management

### Field 11: Code Quality
- Clear enforcement rules
- Comprehensive logging

### Field 12: GitHub CI Requirements
- Residency tests pass
- Cross-region blocked

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Cross-region access blocked**
- **CRITICAL: GDPR export works**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Cross-Region Replication
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/compliance/replication/__init__.py`
2. `backend/compliance/replication/cross_region_replication.py`
3. `backend/compliance/replication/replication_monitor.py`
4. `backend/compliance/replication/conflict_resolver.py`
5. `backend/compliance/replication/latency_tracker.py`
6. `tests/compliance/test_replication.py`

### Field 2: What is each file?
1. `backend/compliance/replication/__init__.py` — Module init
2. `backend/compliance/replication/cross_region_replication.py` — Replication service
3. `backend/compliance/replication/replication_monitor.py` — Replication monitoring
4. `backend/compliance/replication/conflict_resolver.py` — Conflict resolution
5. `backend/compliance/replication/latency_tracker.py` — Latency tracking
6. `tests/compliance/test_replication.py` — Replication tests

### Field 3: Responsibilities

**backend/compliance/replication/cross_region_replication.py:**
- Replication service with:
  - Async replication between regions
  - Event-driven replication
  - Selective replication (metadata only)
  - Replication lag tracking
  - Automatic retry on failure
  - **Test: Replication works <500ms lag**

**backend/compliance/replication/replication_monitor.py:**
- Replication monitor with:
  - Monitor replication status
  - Alert on replication lag >500ms
  - Track replication queue depth
  - Monitor replication errors
  - Health dashboard
  - **Test: Monitor detects lag**

**backend/compliance/replication/conflict_resolver.py:**
- Conflict resolver with:
  - Last-write-wins strategy
  - Conflict detection
  - Conflict resolution logging
  - Manual resolution support
  - Conflict reporting
  - **Test: Conflicts resolved correctly**

**backend/compliance/replication/latency_tracker.py:**
- Latency tracker with:
  - Track cross-region latency
  - P50/P95/P99 latency metrics
  - Latency alerts
  - Historical tracking
  - Prometheus export
  - **Test: Latency tracked**

**tests/compliance/test_replication.py:**
- Replication tests with:
  - Test: Replication works
  - Test: Lag <500ms
  - Test: Conflicts resolved
  - Test: Latency tracked
  - **CRITICAL: Replication lag <500ms**

### Field 4: Depends On
- Region infrastructure (Day 1-3)
- Residency enforcer (Day 4)

### Field 5: Expected Output
- Cross-region replication operational
- Replication lag <500ms

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Data replicates across regions with <500ms lag

### Field 8: Error Handling
- Replication failures
- Conflict resolution

### Field 9: Security Requirements
- Encrypted replication
- Data integrity checks

### Field 10: Integration Points
- Database layer
- Monitoring system
- Alert system

### Field 11: Code Quality
- Documented replication strategy
- Clear conflict resolution

### Field 12: GitHub CI Requirements
- Replication tests pass
- Lag threshold verified

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Replication works**
- **CRITICAL: Replication lag <500ms**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 29 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. Region Infrastructure Tests
```bash
pytest tests/infrastructure/test_eu_region.py tests/infrastructure/test_us_region.py tests/infrastructure/test_apac_region.py -v
```

#### 2. Terraform Validation
```bash
cd infra/terraform/regions/eu && terraform validate
cd infra/terraform/regions/us && terraform validate
cd infra/terraform/regions/apac && terraform validate
```

#### 3. Residency Tests
```bash
pytest tests/compliance/test_residency.py -v
```

#### 4. Replication Tests
```bash
pytest tests/compliance/test_replication.py -v
```

#### 5. Integration Tests
```bash
pytest tests/integration/ -v --tb=short
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | EU region infrastructure | Terraform validates |
| 2 | US region infrastructure | Terraform validates |
| 3 | APAC region infrastructure | Terraform validates |
| 4 | Cross-region access | Blocked |
| 5 | GDPR export | Only assigned region |
| 6 | Replication lag | <500ms |
| 7 | Region isolation | 0 leaks |
| 8 | Data sovereignty | Enforced |
| 9 | Region routing | Correct |
| 10 | Conflict resolution | Works |

---

### Week 29 PASS Criteria

1. ✅ EU Region: Terraform validates
2. ✅ US Region: Terraform validates
3. ✅ APAC Region: Terraform validates
4. ✅ **Cross-Region Isolation: 0 data leaks (CRITICAL)**
5. ✅ **EU client data absent from US DB (CRITICAL)**
6. ✅ **Replication Lag: <500ms (CRITICAL)**
7. ✅ GDPR Export: Only assigned region data
8. ✅ Data Sovereignty: Enforced
9. ✅ Region Routing: Correct
10. ✅ Conflict Resolution: Works
11. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Focus | Files | Status |
|---------|-----|-------|-------|--------|
| Builder 1 | Day 1 | EU Region Infrastructure | 6 | ⏳ PENDING |
| Builder 2 | Day 2 | US Region Infrastructure | 6 | ⏳ PENDING |
| Builder 3 | Day 3 | APAC Region Infrastructure | 6 | ⏳ PENDING |
| Builder 4 | Day 4 | Data Residency Enforcer | 6 | ⏳ PENDING |
| Builder 5 | Day 5 | Cross-Region Replication | 6 | ⏳ PENDING |
| Tester | Day 6 | Full Validation | - | ⏳ PENDING |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. Multi-Region Data Residency per roadmap
3. **EU client data MUST NOT be in US region (CRITICAL)**
4. **Cross-region isolation: 0 leaks (MANDATORY)**
5. **Replication lag <500ms (MANDATORY)**
6. **GDPR export only from assigned region**
7. Data sovereignty compliance
8. Three regions: EU, US, APAC

**WEEK 29 TARGETS:**

| Metric | Target | Status |
|--------|--------|--------|
| Regions | 3 (EU, US, APAC) | 🎯 Target |
| Cross-Region Leaks | 0 | 🎯 Mandatory |
| Replication Lag | <500ms | 🎯 Mandatory |
| GDPR Export | Region-specific | 🎯 Target |
| Terraform Validation | All pass | 🎯 Target |

**REGION ASSIGNMENTS:**

| Region | Location | Compliance |
|--------|----------|------------|
| EU | eu-west-1 (Ireland) | GDPR |
| US | us-east-1 (N. Virginia) | CCPA |
| APAC | ap-southeast-1 (Singapore) | Local laws |

**ASSUMPTIONS:**
- Week 28 complete (90% accuracy)
- Terraform installed
- AWS provider configured
- Existing infrastructure for 20 clients

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 29 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | EU Region Infrastructure |
| Day 2 | 6 | US Region Infrastructure |
| Day 3 | 6 | APAC Region Infrastructure |
| Day 4 | 6 | Data Residency Enforcer |
| Day 5 | 6 | Cross-Region Replication |
| **Total** | **30** | **Multi-Region Data Residency** |

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 8 PROGRESS
═══════════════════════════════════════════════════════════════════════════════

**Phase 8: Enterprise Preparation (Weeks 28-40)**

| Week | Roadmap Goal | Status |
|------|--------------|--------|
| 28 | Agent Lightning 90% Milestone | ✅ COMPLETE |
| **29** | **Multi-Region Data Residency** | **🔄 IN PROGRESS** |
| 30 | 30-Client Milestone | ⏳ Pending |
| 31 | E-commerce Advanced | ⏳ Pending |
| 32 | SaaS Advanced | ⏳ Pending |
| 33 | Healthcare HIPAA + Logistics | ⏳ Pending |
| 34 | Frontend v2 (React Query + PWA) | ⏳ Pending |
| 35 | Smart Router 92%+ | ⏳ Pending |
| 36 | Agent Lightning 94% | ⏳ Pending |
| 37 | 50-Client Scale + Autoscaling | ⏳ Pending |
| 38 | Enterprise Pre-Preparation | ⏳ Pending |
| 39 | Final Production Readiness | ⏳ Pending |
| 40 | Weeks 1-40 Final Validation | ⏳ Pending |

**Week 29 Deliverables:**
- Regions: 3 (EU, US, APAC) 🎯 Target
- Data Residency: Enforced
- Replication: <500ms lag
- GDPR: Region-specific export
- **Multi-Region Complete!**
