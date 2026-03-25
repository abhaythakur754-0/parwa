# AGENT_COMMS.md — Week 23 Day 1-6
# Last updated: Manager Agent
# Current status: WEEK 23 TASKS WRITTEN — AWAITING BUILDERS

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 23 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-25

> **Phase: Phase 7 — Scale to 20 Clients (Weeks 21-27)**
>
> **Week 23 Goals:**
> - **Roadmap Week 23:** Frontend Polish (A11y, Mobile, Dark Mode)
> - **Catch-Up Week 22:** Clients 6-10 Onboarding
>
> **Combined Focus:**
> - Day 1: Accessibility (A11y) + Client 006 Setup
> - Day 2: Mobile Responsive + Client 007 Setup
> - Day 3: Dark Mode + Client 008 Setup
> - Day 4: Frontend Performance + Clients 009-010 Setup
> - Day 5: Testing + Docs + 10-Client Validation
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. Each builder does BOTH Week 23 task AND catch-up task
> 3. WCAG 2.1 AA compliance required
> 4. Mobile-first responsive design
> 5. Dark mode with system preference detection
> 6. **WCAG 2.1 AA: 100% compliance**
> 7. **Mobile: All pages responsive**
> 8. **Dark Mode: Full support with toggle**
> 9. **Clients 6-10: All onboarded**
> 10. **10-client isolation: 0 data leaks**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Accessibility + Client 006
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)

**Week 23 - Accessibility:**
1. `frontend/src/lib/a11y.ts`
2. `frontend/src/components/ui/focus-trap.tsx`
3. `frontend/src/components/ui/skip-link.tsx`

**Catch-Up Week 22 - Client 006:**
4. `clients/client_006/__init__.py`
5. `clients/client_006/config.py`
6. `clients/client_006/knowledge_base/faq.json`

### Field 2: What is each file?
1. `frontend/src/lib/a11y.ts` — Accessibility utility functions
2. `frontend/src/components/ui/focus-trap.tsx` — Focus trap for modals
3. `frontend/src/components/ui/skip-link.tsx` — Skip to main content link
4. `clients/client_006/__init__.py` — Client 006 module init
5. `clients/client_006/config.py` — Retail client configuration
6. `clients/client_006/knowledge_base/faq.json` — Client 006 FAQ knowledge

### Field 3: Responsibilities

**frontend/src/lib/a11y.ts:**
- Accessibility utilities with:
  - ARIA attribute helpers
  - Keyboard navigation utilities
  - Focus management functions
  - Color contrast validators
  - **Test: All utilities work correctly**

**frontend/src/components/ui/focus-trap.tsx:**
- Focus trap with:
  - Trap focus within modals
  - Escape key handling
  - Tab cycling
  - **Test: Focus trapped correctly**

**frontend/src/components/ui/skip-link.tsx:**
- Skip link with:
  - Skip to main content
  - Visible on focus
  - Smooth scrolling
  - **Test: Skip link works**

**clients/client_006/config.py:**
- Retail client config with:
  - Client ID: "client_006"
  - Client name: "ShopMax Retail"
  - Industry: "retail"
  - Variant: "mini"
  - Timezone: "America/Chicago"
  - Business hours: 9am-9pm CST
  - **Test: Config loads correctly**

**clients/client_006/knowledge_base/faq.json:**
- Retail FAQ with:
  - 20+ FAQ entries (retail-specific)
  - Categories: Orders, Returns, Shipping, Products, Payment
  - Question/Answer pairs
  - **Test: FAQ loads and is searchable**

### Field 4: Depends On
- Week 15 frontend foundation
- Week 21 client setup patterns

### Field 5: Expected Output
- Accessibility components ready
- Client 006 fully configured

### Field 6: Unit Test Files
- `tests/frontend/a11y.test.ts`
- `tests/clients/test_client_006.py`

### Field 7: BDD Scenario
- Pages accessible + Client 006 operational

### Field 8: Error Handling
- Graceful A11y degradation
- Client config validation

### Field 9: Security Requirements
- Secure focus management
- Client isolation for client_006

### Field 10: Integration Points
- All UI components
- Client management system

### Field 11: Code Quality
- axe-core integration
- Typed client config

### Field 12: GitHub CI Requirements
- A11y tests pass
- Client 006 config loads

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Accessibility components work**
- **CRITICAL: Client 006 loads correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Mobile Responsive + Client 007
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)

**Week 23 - Mobile Responsive:**
1. `frontend/src/lib/responsive.ts`
2. `frontend/src/hooks/useMediaQuery.ts`
3. `frontend/src/components/ui/mobile-nav.tsx`

**Catch-Up Week 22 - Client 007:**
4. `clients/client_007/__init__.py`
5. `clients/client_007/config.py`
6. `clients/client_007/knowledge_base/faq.json`

### Field 2: What is each file?
1. `frontend/src/lib/responsive.ts` — Responsive utilities
2. `frontend/src/hooks/useMediaQuery.ts` — Media query hook
3. `frontend/src/components/ui/mobile-nav.tsx` — Mobile navigation
4. `clients/client_007/__init__.py` — Client 007 module init
5. `clients/client_007/config.py` — Education client configuration
6. `clients/client_007/knowledge_base/faq.json` — Client 007 FAQ knowledge

### Field 3: Responsibilities

**frontend/src/lib/responsive.ts:**
- Responsive utilities with:
  - Breakpoint definitions (sm, md, lg, xl, 2xl)
  - Container query support
  - Touch detection
  - **Test: Utilities work correctly**

**frontend/src/hooks/useMediaQuery.ts:**
- Media query hook with:
  - Breakpoint detection
  - Touch device detection
  - Prefers-reduced-motion
  - **Test: Hook responds to breakpoints**

**frontend/src/components/ui/mobile-nav.tsx:**
- Mobile nav with:
  - Hamburger menu
  - Slide-out drawer
  - Touch-friendly targets (min 44px)
  - **Test: Navigation works on mobile**

**clients/client_007/config.py:**
- Education client config with:
  - Client ID: "client_007"
  - Client name: "EduLearn Academy"
  - Industry: "education"
  - Variant: "parwa_junior"
  - Timezone: "America/New_York"
  - FERPA compliance enabled
  - **Test: Config loads correctly**

**clients/client_007/knowledge_base/faq.json:**
- Education FAQ with:
  - 20+ FAQ entries (education-specific)
  - Categories: Enrollment, Courses, Payments, Certificates, Support
  - **Test: FAQ loads correctly**

### Field 4: Depends On
- Week 15 frontend foundation
- Week 21 client setup patterns

### Field 5: Expected Output
- Mobile responsive components ready
- Client 007 fully configured

### Field 6: Unit Test Files
- `tests/frontend/responsive.test.ts`
- `tests/clients/test_client_007.py`

### Field 7: BDD Scenario
- App usable on mobile + Client 007 operational

### Field 8: Error Handling
- Graceful degradation on small screens
- Client config validation

### Field 9: Security Requirements
- Secure touch interactions
- FERPA compliance for client_007

### Field 10: Integration Points
- All page components
- Client management system

### Field 11: Code Quality
- Mobile-first CSS
- Typed client config

### Field 12: GitHub CI Requirements
- Responsive tests pass
- Client 007 config loads

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Mobile navigation works**
- **CRITICAL: Client 007 loads correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Dark Mode + Client 008
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)

**Week 23 - Dark Mode:**
1. `frontend/src/lib/theme.ts`
2. `frontend/src/hooks/useTheme.ts`
3. `frontend/src/components/ui/theme-toggle.tsx`

**Catch-Up Week 22 - Client 008:**
4. `clients/client_008/__init__.py`
5. `clients/client_008/config.py`
6. `clients/client_008/knowledge_base/faq.json`

### Field 2: What is each file?
1. `frontend/src/lib/theme.ts` — Theme utilities
2. `frontend/src/hooks/useTheme.ts` — Theme hook
3. `frontend/src/components/ui/theme-toggle.tsx` — Theme toggle button
4. `clients/client_008/__init__.py` — Client 008 module init
5. `clients/client_008/config.py` — Travel client configuration
6. `clients/client_008/knowledge_base/faq.json` — Client 008 FAQ knowledge

### Field 3: Responsibilities

**frontend/src/lib/theme.ts:**
- Theme utilities with:
  - Theme definitions (light, dark, system)
  - CSS variable helpers
  - Local storage persistence
  - **Test: Utilities work correctly**

**frontend/src/hooks/useTheme.ts:**
- Theme hook with:
  - Current theme state
  - Theme switching function
  - System preference sync
  - **Test: Hook manages theme state**

**frontend/src/components/ui/theme-toggle.tsx:**
- Theme toggle with:
  - Sun/Moon icons
  - Keyboard accessible
  - ARIA label
  - **Test: Toggle switches theme**

**clients/client_008/config.py:**
- Travel client config with:
  - Client ID: "client_008"
  - Client name: "TravelEase"
  - Industry: "travel"
  - Variant: "parwa_high"
  - Timezone: "UTC" (global)
  - Business hours: 24/7
  - **Test: Config loads correctly**

**clients/client_008/knowledge_base/faq.json:**
- Travel FAQ with:
  - 20+ FAQ entries (travel-specific)
  - Categories: Bookings, Flights, Hotels, Cancellations, Refunds
  - **Test: FAQ loads correctly**

### Field 4: Depends On
- Week 15 frontend foundation
- Week 21 client setup patterns

### Field 5: Expected Output
- Dark mode fully functional
- Client 008 fully configured

### Field 6: Unit Test Files
- `tests/frontend/theme.test.ts`
- `tests/clients/test_client_008.py`

### Field 7: BDD Scenario
- Theme switching works + Client 008 operational

### Field 8: Error Handling
- Fallback to light mode
- Client config validation

### Field 9: Security Requirements
- Secure theme storage
- Client isolation for client_008

### Field 10: Integration Points
- All UI components
- Client management system

### Field 11: Code Quality
- CSS variables for theming
- Typed client config

### Field 12: GitHub CI Requirements
- Theme tests pass
- Client 008 config loads

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Dark mode fully functional**
- **CRITICAL: Client 008 loads correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Performance + Clients 009-010
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)

**Week 23 - Performance:**
1. `frontend/src/lib/performance.ts`
2. `frontend/src/hooks/useLazyLoad.ts`
3. `frontend/src/components/ui/skeleton.tsx`

**Catch-Up Week 22 - Clients 009-010:**
4. `clients/client_009/config.py`
5. `clients/client_010/config.py`
6. `clients/client_009/knowledge_base/faq.json`
7. `clients/client_010/knowledge_base/faq.json`

### Field 2: What is each file?
1. `frontend/src/lib/performance.ts` — Performance utilities
2. `frontend/src/hooks/useLazyLoad.ts` — Lazy loading hook
3. `frontend/src/components/ui/skeleton.tsx` — Skeleton loader
4. `clients/client_009/config.py` — Real Estate client configuration
5. `clients/client_010/config.py` — Entertainment client configuration
6. `clients/client_009/knowledge_base/faq.json` — Client 009 FAQ
7. `clients/client_010/knowledge_base/faq.json` — Client 010 FAQ

### Field 3: Responsibilities

**frontend/src/lib/performance.ts:**
- Performance utilities with:
  - Bundle size analyzer
  - Image optimization helpers
  - Performance metrics collection
  - **Test: Utilities work correctly**

**frontend/src/hooks/useLazyLoad.ts:**
- Lazy load hook with:
  - Intersection observer
  - Image lazy loading
  - Priority loading
  - **Test: Lazy loading works**

**frontend/src/components/ui/skeleton.tsx:**
- Skeleton loader with:
  - Multiple skeleton variants
  - Animated shimmer
  - Dark mode support
  - **Test: Skeleton renders correctly**

**clients/client_009/config.py:**
- Real Estate client config with:
  - Client ID: "client_009"
  - Client name: "HomeFind Realty"
  - Industry: "real_estate"
  - Variant: "parwa_junior"
  - Timezone: "America/Los_Angeles"
  - **Test: Config loads correctly**

**clients/client_010/config.py:**
- Entertainment client config with:
  - Client ID: "client_010"
  - Client name: "StreamPlus Media"
  - Industry: "entertainment"
  - Variant: "parwa_high"
  - Timezone: "America/Los_Angeles"
  - Business hours: 24/7
  - **Test: Config loads correctly**

**clients/client_009/knowledge_base/faq.json:**
- Real Estate FAQ with:
  - 20+ FAQ entries
  - Categories: Listings, Buying, Selling, Rentals, Agents
  - **Test: FAQ loads correctly**

**clients/client_010/knowledge_base/faq.json:**
- Entertainment FAQ with:
  - 20+ FAQ entries
  - Categories: Streaming, Subscriptions, Content, Technical
  - **Test: FAQ loads correctly**

### Field 4: Depends On
- Week 15 frontend foundation
- Week 21 client setup patterns

### Field 5: Expected Output
- Performance optimizations ready
- Clients 009-010 fully configured

### Field 6: Unit Test Files
- `tests/frontend/performance.test.ts`
- `tests/clients/test_client_009.py`
- `tests/clients/test_client_010.py`

### Field 7: BDD Scenario
- App performs well + Clients 009-010 operational

### Field 8: Error Handling
- Graceful loading states
- Client config validation

### Field 9: Security Requirements
- Secure performance metrics
- Client isolation for clients 009-010

### Field 10: Integration Points
- All pages
- Client management system

### Field 11: Code Quality
- Performance monitoring
- Typed client configs

### Field 12: GitHub CI Requirements
- Performance tests pass
- Client 009-010 configs load

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 7 files built and pushed
- **CRITICAL: Performance optimizations work**
- **CRITICAL: Clients 009 and 010 load correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Testing + Docs + 10-Client Validation
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)

**Week 23 - Testing + Docs:**
1. `tests/frontend/e2e/accessibility.spec.ts`
2. `tests/frontend/e2e/theme.spec.ts`
3. `docs/frontend/accessibility-guide.md`

**Catch-Up Week 22 - 10-Client Validation:**
4. `tests/integration/test_10_client_isolation.py`
5. `scripts/validate_10_tenant.py`
6. `reports/week22_catchup_report.md`

### Field 2: What is each file?
1. `tests/frontend/e2e/accessibility.spec.ts` — E2E accessibility tests
2. `tests/frontend/e2e/theme.spec.ts` — E2E theme tests
3. `docs/frontend/accessibility-guide.md` — A11y documentation
4. `tests/integration/test_10_client_isolation.py` — 10-client isolation tests
5. `scripts/validate_10_tenant.py` — 10-tenant validation script
6. `reports/week22_catchup_report.md` — Catch-up completion report

### Field 3: Responsibilities

**tests/frontend/e2e/accessibility.spec.ts:**
- E2E A11y tests with:
  - Test: Landing page accessible
  - Test: Dashboard accessible
  - Test: Forms accessible
  - **Test: All E2E A11y tests pass**

**tests/frontend/e2e/theme.spec.ts:**
- E2E theme tests with:
  - Test: Theme toggle works
  - Test: Theme persists
  - Test: Dark mode renders correctly
  - **Test: All E2E theme tests pass**

**docs/frontend/accessibility-guide.md:**
- A11y guide with:
  - WCAG 2.1 AA requirements
  - Component accessibility patterns
  - Testing checklist
  - **Content: Complete A11y guide**

**tests/integration/test_10_client_isolation.py:**
- 10-client isolation tests with:
  - Test: Each client isolated (100 tests)
  - Test: Cross-tenant queries return 0 rows
  - Test: API isolation for all 10 clients
  - **CRITICAL: 0 data leaks in 100 tests**

**scripts/validate_10_tenant.py:**
- Validation script with:
  - Run all 10-client isolation tests
  - Check data segregation
  - Verify access controls
  - Generate validation report
  - **Test: Validation runs**

**reports/week22_catchup_report.md:**
- Catch-up report with:
  - Clients 6-10 onboarding summary
  - 10-client isolation results
  - Accuracy metrics
  - **Content: Complete catch-up report**

### Field 4: Depends On
- All Week 23 work
- All clients 6-10

### Field 5: Expected Output
- E2E tests complete
- Documentation complete
- 10-client isolation verified

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- All features tested + 10 clients validated

### Field 8: Error Handling
- Test failure reporting
- Isolation failure alerts

### Field 9: Security Requirements
- No sensitive data in docs
- 10-client isolation enforced

### Field 10: Integration Points
- All frontend components
- All 10 clients

### Field 11: Code Quality
- Comprehensive test coverage
- Clear documentation

### Field 12: GitHub CI Requirements
- All E2E tests pass
- 10-client isolation tests pass

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All E2E tests pass**
- **CRITICAL: 0 data leaks in 100 isolation tests**
- Documentation complete
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 23 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. Accessibility Tests
```bash
npm run test:a11y
npx lighthouse http://localhost:3000 --only-categories=accessibility
```

#### 2. Mobile + Theme Tests
```bash
npx playwright test tests/frontend/e2e/mobile.spec.ts
npx playwright test tests/frontend/e2e/theme.spec.ts
```

#### 3. Performance Tests
```bash
npm run lighthouse
npx lighthouse http://localhost:3000 --output=json
```

#### 4. 10-Client Isolation Tests
```bash
pytest tests/integration/test_10_client_isolation.py -v
python scripts/validate_10_tenant.py
```

#### 5. All Client Configs
```bash
pytest tests/clients/test_client_006.py tests/clients/test_client_007.py tests/clients/test_client_008.py tests/clients/test_client_009.py tests/clients/test_client_010.py -v
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | WCAG 2.1 AA | 100% compliance |
| 2 | Lighthouse A11y | Score >90 |
| 3 | Touch targets | All ≥44px |
| 4 | Dark mode | Fully functional |
| 5 | Client 006-010 | All load correctly |
| 6 | Total clients | 10 active |
| 7 | 10-client isolation | 0 data leaks in 100 tests |
| 8 | Lighthouse Performance | >90 |
| 9 | LCP | <2.5s |
| 10 | All E2E tests | Pass |

---

### Week 23 PASS Criteria

1. ✅ WCAG 2.1 AA: 100% compliance
2. ✅ Lighthouse Accessibility: >90
3. ✅ All pages responsive
4. ✅ Dark mode fully functional
5. ✅ **Clients 6-10: All onboarded (CATCH-UP COMPLETE)**
6. ✅ **Total clients: 10 active**
7. ✅ **10-client isolation: 0 data leaks**
8. ✅ Lighthouse Performance: >90
9. ✅ All E2E tests pass
10. ✅ Documentation complete
11. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Week 23 Task | Catch-Up Task | Status |
|---------|-----|--------------|---------------|--------|
| Builder 1 | Day 1 | Accessibility | Client 006 | ⏳ PENDING |
| Builder 2 | Day 2 | Mobile Responsive | Client 007 | ⏳ PENDING |
| Builder 3 | Day 3 | Dark Mode | Client 008 | ⏳ PENDING |
| Builder 4 | Day 4 | Performance | Clients 009-010 | ⏳ PENDING |
| Builder 5 | Day 5 | Testing + Docs | 10-Client Validation | ⏳ PENDING |
| Tester | Day 6 | Full validation | 10-Client Isolation | ⏳ PENDING |

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 23 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Week 23 Files | Catch-Up Files | Total |
|-----|---------------|----------------|-------|
| Day 1 | 3 (A11y) | 3 (Client 006) | 6 |
| Day 2 | 3 (Mobile) | 3 (Client 007) | 6 |
| Day 3 | 3 (Dark Mode) | 3 (Client 008) | 6 |
| Day 4 | 3 (Performance) | 4 (Clients 009-010) | 7 |
| Day 5 | 3 (Tests/Docs) | 3 (Validation) | 6 |
| **Total** | **15** | **16** | **31** |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. **EACH BUILDER DOES BOTH TASKS** — Week 23 + Catch-up
3. WCAG 2.1 AA compliance is MANDATORY
4. All 5 new clients must be configured correctly
5. **WCAG 2.1 AA: 100% compliance**
6. **Dark Mode: Full support**
7. **Clients 6-10: All onboarded**
8. **10-client isolation: 0 data leaks**

**NEW CLIENTS SUMMARY:**

| Client | Name | Industry | Variant |
|--------|------|----------|---------|
| 006 | ShopMax Retail | Retail | Mini |
| 007 | EduLearn Academy | Education | Junior (FERPA) |
| 008 | TravelEase | Travel | High |
| 009 | HomeFind Realty | Real Estate | Junior |
| 010 | StreamPlus Media | Entertainment | High |

**WEEK 22 CATCH-UP COMPLETE CRITERIA:**
- [ ] 5 new clients configured
- [ ] Total: 10 clients active
- [ ] 10-client isolation: 0 leaks
- [ ] Catch-up report generated

**WEEK 23 COMPLETE CRITERIA:**
- [ ] WCAG 2.1 AA compliant
- [ ] Mobile responsive
- [ ] Dark mode functional
- [ ] Lighthouse >90
- [ ] All E2E tests pass

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 7 PROGRESS AFTER WEEK 23
═══════════════════════════════════════════════════════════════════════════════

| Week | Roadmap Goal | Status After Week 23 |
|------|--------------|----------------------|
| 21 | Clients 3-5 + CI | ✅ COMPLETE |
| 22 | Clients 6-10 + 85% Accuracy | ✅ **COMPLETE (catch-up done)** |
| 23 | Frontend Polish | ✅ **COMPLETE** |
| 24 | Client Success Tooling | ⏳ Next |
| 25 | Financial Services Vertical | ⏳ Pending |
| 26 | Performance Optimization | ⏳ Pending |
| 27 | 20-Client Validation | ⏳ Pending |

**After Week 23:**
- Clients: 10 ✅
- Accuracy: 77.3% (target 85% - still gap)
- Frontend: Polished ✅
- **BACK ON ROADMAP!**
