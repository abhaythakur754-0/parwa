# AGENT_COMMS.md — Week 38 Day 6 (Tester Phase)
# Last updated by: Auto-Update
# Current status: WEEK 38 — TESTER PHASE (Builders 1-5 COMPLETE)

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 38 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-28

> **Phase: Phase 8 — Enterprise Preparation (Weeks 28-40)**
>
> **Week 38 Goals (Per Roadmap):**
> - Day 1: SSO + SCIM stubs + enterprise billing + onboarding
> - Day 2: Security hardening
> - Day 3: Enterprise compliance docs
> - Day 4: Enterprise frontend
> - Day 5: Tests
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. SSO stub returns correct SAML placeholder
> 3. Audit log CSV has all required fields
> 4. Enterprise billing generates contract invoice
> 5. IP allowlist blocks non-whitelisted IPs

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — SSO + SCIM Stubs + Enterprise Billing + Onboarding
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/sso/sso_provider.py`
2. `backend/sso/sp_metadata.py`
3. `backend/sso/scim_stub.py`
4. `backend/billing/enterprise_billing.py`
5. `backend/onboarding/enterprise_onboarding.py`
6. `tests/unit/test_sso_stub.py`

### Field 2: What is each file?
1. `sso_provider.py` — SSO provider stub with SAML placeholder
2. `sp_metadata.py` — Service Provider metadata for SAML
3. `scim_stub.py` — SCIM provisioning stub
4. `enterprise_billing.py` — Enterprise billing with contract invoice generation
5. `enterprise_onboarding.py` — Enterprise client onboarding flow
6. `test_sso_stub.py` — Unit tests for SSO stub

### Field 3: Responsibilities

**sso_provider.py:**
- SSO provider stub implementation
- Returns correct SAML placeholder
- Supports SAML 2.0 protocol structure
- **Test: SSO stub returns correct SAML placeholder**

**sp_metadata.py:**
- Service Provider metadata generation
- Valid XML parseable by Okta/Azure
- Entity ID and assertion consumer service URL
- **Test: SP metadata valid XML**

**scim_stub.py:**
- SCIM 2.0 provisioning stub
- User create/update/delete endpoints
- Group management stub
- **Test: SCIM stub responds correctly**

**enterprise_billing.py:**
- Contract-based billing
- Invoice generation for enterprise
- Custom pricing tiers
- **Test: Enterprise billing generates contract invoice**

**enterprise_onboarding.py:**
- Enterprise-specific onboarding flow
- Contract signing workflow
- SSO configuration wizard
- **Test: Enterprise onboarding completes**

### Field 4: Depends On
- Existing billing infrastructure (Weeks 1-37)
- Company model (backend/models/company.py)
- Auth infrastructure (backend/core/auth.py)

### Field 5: Expected Output
- SSO stub working with SAML placeholder
- SCIM stub for user provisioning
- Enterprise billing with contract invoices
- Enterprise onboarding flow

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: SSO stub returns correct SAML placeholder**
- **CRITICAL: Audit log CSV has all required fields**
- **CRITICAL: Enterprise billing generates contract invoice**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Security Hardening
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `backend/security/ip_allowlist.py`
2. `backend/security/rate_limiter_advanced.py`
3. `backend/security/session_manager.py`
4. `backend/security/api_key_manager.py`
5. `tests/unit/test_ip_allowlist.py`
6. `tests/unit/test_audit_export.py`

### Field 2: What is each file?
1. `ip_allowlist.py` — IP allowlist enforcement
2. `rate_limiter_advanced.py` — Advanced rate limiting with tiers
3. `session_manager.py` — Enterprise session management
4. `api_key_manager.py` — API key management for enterprise
5. `test_ip_allowlist.py` — Tests for IP allowlist
6. `test_audit_export.py` — Tests for audit log export

### Field 3: Responsibilities

**ip_allowlist.py:**
- IP allowlist enforcement
- Block non-whitelisted IPs
- Enterprise tenant-specific allowlists
- **Test: Non-whitelisted IP blocked**

**rate_limiter_advanced.py:**
- Tiered rate limiting
- Per-tenant limits
- Burst handling
- **Test: Rate limiting works correctly**

**session_manager.py:**
- Enterprise session management
- Concurrent session limits
- Session timeout policies
- **Test: Session management works**

**api_key_manager.py:**
- API key generation and rotation
- Key scopes and permissions
- Enterprise API key management
- **Test: API key management works**

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Non-whitelisted IP blocked**
- **CRITICAL: Audit log CSV has all required fields**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Enterprise Compliance Docs
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `legal/enterprise_data_processing_agreement.md`
2. `legal/enterprise_sla.md`
3. `docs/enterprise_security_guide.md`
4. `docs/enterprise_onboarding_guide.md`
5. `backend/compliance/audit_export.py`
6. `tests/unit/test_enterprise_compliance.py`

### Field 2: What is each file?
1. `enterprise_data_processing_agreement.md` — DPA for enterprise clients
2. `enterprise_sla.md` — SLA terms for enterprise
3. `enterprise_security_guide.md` — Security documentation for enterprise
4. `enterprise_onboarding_guide.md` — Onboarding documentation
5. `audit_export.py` — Audit log export functionality
6. `test_enterprise_compliance.py` — Enterprise compliance tests

### Field 3: Responsibilities

**enterprise_data_processing_agreement.md:**
- GDPR-compliant DPA
- Data processing terms
- Sub-processor list
- **Test: Document complete**

**enterprise_sla.md:**
- 99.9% uptime guarantee
- Response time SLAs
- Support tiers
- **Test: Document complete**

**enterprise_security_guide.md:**
- Security architecture overview
- Encryption details
- Compliance certifications
- **Test: Document complete**

**audit_export.py:**
- CSV export of audit logs
- All required fields
- Date range filtering
- **Test: Audit log CSV has all required fields**

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All enterprise docs complete**
- **CRITICAL: Audit log CSV has all required fields**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Enterprise Frontend
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/app/dashboard/enterprise/page.tsx`
2. `frontend/app/dashboard/enterprise/sso/page.tsx`
3. `frontend/app/dashboard/enterprise/billing/page.tsx`
4. `frontend/components/enterprise/SSOConfigWizard.tsx`
5. `frontend/components/enterprise/ContractViewer.tsx`
6. `tests/integration/test_enterprise_security.py`

### Field 2: What is each file?
1. `enterprise/page.tsx` — Enterprise dashboard landing page
2. `sso/page.tsx` — SSO configuration page
3. `billing/page.tsx` — Enterprise billing page
4. `SSOConfigWizard.tsx` — SSO configuration wizard component
5. `ContractViewer.tsx` — Contract document viewer
6. `test_enterprise_security.py` — Enterprise security tests

### Field 3: Responsibilities

**enterprise/page.tsx:**
- Enterprise dashboard overview
- Quick actions for enterprise admins
- Usage metrics
- **Test: Page renders correctly**

**sso/page.tsx:**
- SSO configuration interface
- Identity provider setup
- SCIM provisioning settings
- **Test: SSO config saves correctly**

**billing/page.tsx:**
- Enterprise billing overview
- Contract details
- Invoice history
- **Test: Billing page loads**

**SSOConfigWizard.tsx:**
- Step-by-step SSO setup
- Okta/Azure AD integration
- Metadata upload
- **Test: Wizard completes**

**ContractViewer.tsx:**
- Contract document display
- Signature status
- Renewal tracking
- **Test: Contract viewer loads**

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All enterprise frontend pages render**
- **CRITICAL: SSO config wizard functional**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Tests
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `tests/unit/test_sso_stub.py` (update with full coverage)
2. `tests/unit/test_audit_export.py` (update with full coverage)
3. `tests/integration/test_enterprise_security.py` (update)
4. `tests/e2e/test_enterprise_onboarding.py`
5. `reports/week38_enterprise_report.md`
6. `docs/week38_completion_checklist.md`

### Field 2: What is each file?
1. `test_sso_stub.py` — Full SSO stub tests
2. `test_audit_export.py` — Full audit export tests
3. `test_enterprise_security.py` — Enterprise security integration tests
4. `test_enterprise_onboarding.py` — E2E enterprise onboarding tests
5. `week38_enterprise_report.md` — Week 38 enterprise report
6. `week38_completion_checklist.md` — Week 38 completion checklist

### Field 3: Responsibilities

**test_sso_stub.py:**
- SAML placeholder validation
- SSO flow tests
- SCIM provisioning tests
- **Test: All SSO tests pass**

**test_audit_export.py:**
- CSV export validation
- All required fields present
- Date filtering tests
- **Test: Audit export tests pass**

**test_enterprise_security.py:**
- IP allowlist tests
- Rate limiting tests
- Session management tests
- **Test: Enterprise security tests pass**

**test_enterprise_onboarding.py:**
- Full onboarding flow
- Contract signing
- SSO configuration
- **Test: E2E onboarding passes**

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All tests pass**
- **CRITICAL: Documentation complete**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 38 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. SSO Stub Tests
```bash
pytest tests/unit/test_sso_stub.py -v
```

#### 2. Audit Export Tests
```bash
pytest tests/unit/test_audit_export.py -v
```

#### 3. Enterprise Security Tests
```bash
pytest tests/integration/test_enterprise_security.py -v
```

#### 4. Enterprise Onboarding E2E
```bash
pytest tests/e2e/test_enterprise_onboarding.py -v
```

#### 5. Complete Test Suite
```bash
pytest tests/ -v --tb=short
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | SSO stub: returns correct SAML placeholder | ✅ PASS |
| 2 | Audit log CSV: all required fields exported | ✅ PASS |
| 3 | Enterprise billing: contract invoice generated | ✅ PASS |
| 4 | IP allowlist: non-whitelisted IP blocked | ✅ PASS |

---

### Week 38 PASS Criteria

1. ✅ **SSO Stub: Returns correct SAML placeholder**
2. ✅ **Audit Log CSV: All required fields exported**
3. ✅ **Enterprise Billing: Contract invoice generated**
4. ✅ **IP Allowlist: Non-whitelisted IP blocked**
5. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Focus | Files | Status |
|---------|-----|-------|-------|--------|
| Builder 1 | Day 1 | SSO + SCIM + Billing + Onboarding | 6 | ✅ COMPLETE |
| Builder 2 | Day 2 | Security Hardening | 6 | ✅ COMPLETE |
| Builder 3 | Day 3 | Enterprise Compliance Docs | 6 | ✅ COMPLETE |
| Builder 4 | Day 4 | Enterprise Frontend | 6 | ✅ COMPLETE |
| Builder 5 | Day 5 | Tests | 6 | ✅ COMPLETE |
| Tester | Day 6 | Full Validation | - | 🔄 RUNNING |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. **SSO stub must return correct SAML placeholder**
3. **Audit log CSV must have all required fields**
4. **Enterprise billing must generate contract invoice**
5. **IP allowlist must block non-whitelisted IPs**

**WEEK 38 TARGETS:**

| Metric | Target | Status |
|--------|--------|--------|
| SSO Stub | SAML placeholder works | 🎯 Target |
| Audit Export | CSV all fields | 🎯 Target |
| Enterprise Billing | Contract invoice | 🎯 Target |
| IP Allowlist | Blocks non-whitelist | 🎯 Target |
| Tests | All pass | 🎯 Target |

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 38 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | SSO + SCIM + Billing + Onboarding |
| Day 2 | 6 | Security Hardening |
| Day 3 | 6 | Enterprise Compliance Docs |
| Day 4 | 6 | Enterprise Frontend |
| Day 5 | 6 | Tests |
| **Total** | **30** | **Enterprise Pre-Preparation** |

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
| 37 | 50-Client Scale + Autoscaling | ✅ COMPLETE |
| **38** | **Enterprise Pre-Preparation** | **🔄 IN PROGRESS** |
| 39 | Final Production Readiness | ⏳ Pending |
| 40 | Weeks 1-40 Final Validation | ⏳ Pending |

**Week 38 Deliverables:**
- SSO + SCIM stubs 🎯 Target
- Enterprise billing 🎯 Target
- Security hardening 🎯 Target
- Enterprise compliance docs 🎯 Target
- **ENTERPRISE PRE-PREPARATION COMPLETE!**
