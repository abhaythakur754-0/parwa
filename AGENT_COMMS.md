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
> - Day 1: Accessibility (A11y) Compliance
> - Day 2: Mobile Responsive Design
> - Day 3: Dark Mode Implementation
> - Day 4: Frontend Performance Optimization
> - Day 5: Frontend Testing + Documentation
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. WCAG 2.1 AA compliance required
> 3. Mobile-first responsive design
> 4. Dark mode with system preference detection
> 5. **WCAG 2.1 AA: 100% compliance**
> 6. **Mobile: All pages responsive**
> 7. **Dark Mode: Full support with toggle**
> 8. **Lighthouse Score: >90**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — Accessibility (A11y) Compliance
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/src/lib/a11y.ts`
2. `frontend/src/components/ui/focus-trap.tsx`
3. `frontend/src/components/ui/skip-link.tsx`
4. `frontend/src/components/ui/announcer.tsx`
5. `frontend/src/hooks/useA11y.ts`
6. `tests/frontend/a11y.test.ts`

### Field 2: What is each file?
1. `frontend/src/lib/a11y.ts` — Accessibility utility functions
2. `frontend/src/components/ui/focus-trap.tsx` — Focus trap component for modals
3. `frontend/src/components/ui/skip-link.tsx` — Skip to main content link
4. `frontend/src/components/ui/announcer.tsx` — Screen reader announcer
5. `frontend/src/hooks/useA11y.ts` — Accessibility hook
6. `tests/frontend/a11y.test.ts` — Accessibility tests

### Field 3: Responsibilities

**frontend/src/lib/a11y.ts:**
- Accessibility utilities with:
  - ARIA attribute helpers
  - Keyboard navigation utilities
  - Focus management functions
  - Color contrast validators
  - Screen reader text helpers
  - **Test: All utilities work correctly**

**frontend/src/components/ui/focus-trap.tsx:**
- Focus trap with:
  - Trap focus within modals
  - Escape key handling
  - Tab cycling
  - Initial focus setting
  - Return focus on close
  - **Test: Focus trapped correctly**

**frontend/src/components/ui/skip-link.tsx:**
- Skip link with:
  - Skip to main content
  - Skip to navigation
  - Visible on focus
  - Smooth scrolling
  - **Test: Skip link works**

**frontend/src/components/ui/announcer.tsx:**
- Announcer with:
  - ARIA live region
  - Polite and assertive modes
  - Message queuing
  - Screen reader notifications
  - **Test: Announcements work**

**frontend/src/hooks/useA11y.ts:**
- A11y hook with:
  - useFocusManagement
  - useKeyboardNavigation
  - useAriaLive
  - useReducedMotion
  - **Test: All hooks work**

**tests/frontend/a11y.test.ts:**
- A11y tests with:
  - Test: All buttons have accessible names
  - Test: All images have alt text
  - Test: All forms have labels
  - Test: Color contrast meets WCAG AA
  - Test: Keyboard navigation works
  - **CRITICAL: 100% WCAG 2.1 AA compliance**

### Field 4: Depends On
- Week 15 frontend foundation
- shadcn/ui components

### Field 5: Expected Output
- WCAG 2.1 AA compliant components
- Screen reader support
- Keyboard navigation

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- All pages accessible to screen readers

### Field 8: Error Handling
- Graceful degradation for A11y
- Fallback for assistive tech

### Field 9: Security Requirements
- No sensitive data in ARIA labels
- Secure focus management

### Field 10: Integration Points
- All UI components
- Navigation system
- Form components

### Field 11: Code Quality
- axe-core integration
- A11y linting rules

### Field 12: GitHub CI Requirements
- axe-core tests pass
- Lighthouse A11y >90

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: WCAG 2.1 AA compliance 100%**
- **CRITICAL: Lighthouse A11y score >90**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Mobile Responsive Design
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/src/lib/responsive.ts`
2. `frontend/src/hooks/useMediaQuery.ts`
3. `frontend/src/components/ui/mobile-nav.tsx`
4. `frontend/src/components/ui/bottom-sheet.tsx`
5. `frontend/src/components/layout/mobile-header.tsx`
6. `tests/frontend/responsive.test.ts`

### Field 2: What is each file?
1. `frontend/src/lib/responsive.ts` — Responsive utilities
2. `frontend/src/hooks/useMediaQuery.ts` — Media query hook
3. `frontend/src/components/ui/mobile-nav.tsx` — Mobile navigation
4. `frontend/src/components/ui/bottom-sheet.tsx` — Bottom sheet component
5. `frontend/src/components/layout/mobile-header.tsx` — Mobile header
6. `tests/frontend/responsive.test.ts` — Responsive tests

### Field 3: Responsibilities

**frontend/src/lib/responsive.ts:**
- Responsive utilities with:
  - Breakpoint definitions (sm, md, lg, xl, 2xl)
  - Responsive value helpers
  - Container query support
  - Device detection helpers
  - Touch detection
  - **Test: Utilities work correctly**

**frontend/src/hooks/useMediaQuery.ts:**
- Media query hook with:
  - Breakpoint detection
  - Screen size tracking
  - Orientation detection
  - Touch device detection
  - Prefers-reduced-motion
  - **Test: Hook responds to breakpoints**

**frontend/src/components/ui/mobile-nav.tsx:**
- Mobile nav with:
  - Hamburger menu
  - Slide-out drawer
  - Nested navigation support
  - Touch-friendly targets (min 44px)
  - Swipe to close
  - **Test: Navigation works on mobile**

**frontend/src/components/ui/bottom-sheet.tsx:**
- Bottom sheet with:
  - Drag to dismiss
  - Snap points
  - Backdrop blur
  - Handle indicator
  - A11y compliant
  - **Test: Bottom sheet works**

**frontend/src/components/layout/mobile-header.tsx:**
- Mobile header with:
  - Collapsible search
  - User menu
  - Notification bell
  - Quick actions
  - Sticky positioning
  - **Test: Header works on mobile**

**tests/frontend/responsive.test.ts:**
- Responsive tests with:
  - Test: All breakpoints work
  - Test: Touch targets ≥44px
  - Test: Text readable on mobile
  - Test: No horizontal scroll
  - Test: Forms usable on mobile
  - **CRITICAL: All pages responsive**

### Field 4: Depends On
- Week 15 frontend foundation
- Tailwind CSS breakpoints

### Field 5: Expected Output
- Mobile-first responsive design
- Touch-friendly interface
- All breakpoints working

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Full app usable on mobile devices

### Field 8: Error Handling
- Graceful degradation on small screens
- Offline support considerations

### Field 9: Security Requirements
- Secure touch interactions
- No data exposure on mobile

### Field 10: Integration Points
- All page components
- Navigation system
- Dashboard layout

### Field 11: Code Quality
- Mobile-first CSS
- Touch-friendly interactions

### Field 12: GitHub CI Requirements
- Responsive tests pass
- Visual regression tests

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All pages responsive**
- **CRITICAL: Touch targets ≥44px**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — Dark Mode Implementation
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/src/lib/theme.ts`
2. `frontend/src/hooks/useTheme.ts`
3. `frontend/src/components/ui/theme-toggle.tsx`
4. `frontend/src/components/ui/theme-provider.tsx`
5. `frontend/src/styles/dark-mode.css`
6. `tests/frontend/theme.test.ts`

### Field 2: What is each file?
1. `frontend/src/lib/theme.ts` — Theme utilities
2. `frontend/src/hooks/useTheme.ts` — Theme hook
3. `frontend/src/components/ui/theme-toggle.tsx` — Theme toggle button
4. `frontend/src/components/ui/theme-provider.tsx` — Theme context provider
5. `frontend/src/styles/dark-mode.css` — Dark mode styles
6. `tests/frontend/theme.test.ts` — Theme tests

### Field 3: Responsibilities

**frontend/src/lib/theme.ts:**
- Theme utilities with:
  - Theme definitions (light, dark, system)
  - Color palette for dark mode
  - CSS variable helpers
  - Local storage persistence
  - System preference detection
  - **Test: Utilities work correctly**

**frontend/src/hooks/useTheme.ts:**
- Theme hook with:
  - Current theme state
  - Theme switching function
  - System preference sync
  - Persistence handling
  - Theme change callbacks
  - **Test: Hook manages theme state**

**frontend/src/components/ui/theme-toggle.tsx:**
- Theme toggle with:
  - Sun/Moon icons
  - System preference option
  - Keyboard accessible
  - ARIA label
  - Smooth transition
  - **Test: Toggle switches theme**

**frontend/src/components/ui/theme-provider.tsx:**
- Theme provider with:
  - React context for theme
  - Theme injection to DOM
  - Flash prevention (SSR)
  - Default theme handling
  - **Test: Provider wraps app correctly**

**frontend/src/styles/dark-mode.css:**
- Dark mode CSS with:
  - CSS custom properties
  - Color scheme definitions
  - Component dark variants
  - Transition effects
  - Print styles
  - **Test: Styles apply correctly**

**tests/frontend/theme.test.ts:**
- Theme tests with:
  - Test: Theme persists across reloads
  - Test: System preference detected
  - Test: Toggle works
  - Test: No flash on load
  - Test: All components styled in dark mode
  - **CRITICAL: Full dark mode support**

### Field 4: Depends On
- Week 15 frontend foundation
- Tailwind CSS dark mode

### Field 5: Expected Output
- Complete dark mode support
- Theme persistence
- System preference sync

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- User can switch between light/dark/system themes

### Field 8: Error Handling
- Fallback to light mode
- Handle localStorage unavailable

### Field 9: Security Requirements
- No sensitive data in theme prefs
- Secure storage

### Field 10: Integration Points
- All UI components
- Layout components
- Charts and data viz

### Field 11: Code Quality
- CSS variables for theming
- No hardcoded colors

### Field 12: GitHub CI Requirements
- Theme tests pass
- Dark mode screenshots match

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Dark mode fully functional**
- **CRITICAL: System preference detection works**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Frontend Performance Optimization
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/src/lib/performance.ts`
2. `frontend/src/hooks/useLazyLoad.ts`
3. `frontend/src/components/ui/skeleton.tsx`
4. `frontend/next.config.optimized.ts`
5. `tests/frontend/performance.test.ts`

### Field 2: What is each file?
1. `frontend/src/lib/performance.ts` — Performance utilities
2. `frontend/src/hooks/useLazyLoad.ts` — Lazy loading hook
3. `frontend/src/components/ui/skeleton.tsx` — Skeleton loader
4. `frontend/next.config.optimized.ts` — Optimized Next.js config
5. `tests/frontend/performance.test.ts` — Performance tests

### Field 3: Responsibilities

**frontend/src/lib/performance.ts:**
- Performance utilities with:
  - Bundle size analyzer
  - Image optimization helpers
  - Code splitting helpers
  - Cache strategies
  - Performance metrics collection
  - **Test: Utilities work correctly**

**frontend/src/hooks/useLazyLoad.ts:**
- Lazy load hook with:
  - Intersection observer
  - Image lazy loading
  - Component lazy loading
  - Placeholder support
  - Priority loading
  - **Test: Lazy loading works**

**frontend/src/components/ui/skeleton.tsx:**
- Skeleton loader with:
  - Multiple skeleton variants
  - Animated shimmer
  - Accessible (aria-busy)
  - Responsive sizes
  - Dark mode support
  - **Test: Skeleton renders correctly**

**frontend/next.config.optimized.ts:**
- Optimized config with:
  - Image optimization settings
  - Bundle analyzer config
  - Compression settings
  - Cache headers
  - Production optimizations
  - **Test: Config builds successfully**

**tests/frontend/performance.test.ts:**
- Performance tests with:
  - Test: First Contentful Paint <1.8s
  - Test: Largest Contentful Paint <2.5s
  - Test: Time to Interactive <3.8s
  - Test: Cumulative Layout Shift <0.1
  - Test: Total Blocking Time <200ms
  - **CRITICAL: Lighthouse score >90**

### Field 4: Depends On
- Week 15 frontend foundation
- Next.js optimization features

### Field 5: Expected Output
- Optimized bundle size
- Fast page loads
- High Lighthouse scores

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- App loads quickly on slow connections

### Field 8: Error Handling
- Graceful loading states
- Error boundaries

### Field 9: Security Requirements
- Secure headers in config
- CSP compliance

### Field 10: Integration Points
- All pages
- Image components
- Route handlers

### Field 11: Code Quality
- Tree shaking enabled
- Dead code elimination

### Field 12: GitHub CI Requirements
- Lighthouse CI passes
- Bundle size within limits

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 5 files built and pushed
- **CRITICAL: Lighthouse score >90**
- **CRITICAL: LCP <2.5s**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — Frontend Testing + Documentation
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `tests/frontend/e2e/accessibility.spec.ts`
2. `tests/frontend/e2e/mobile.spec.ts`
3. `tests/frontend/e2e/theme.spec.ts`
4. `docs/frontend/accessibility-guide.md`
5. `docs/frontend/responsive-design.md`
6. `docs/frontend/dark-mode.md`

### Field 2: What is each file?
1. `tests/frontend/e2e/accessibility.spec.ts` — E2E accessibility tests
2. `tests/frontend/e2e/mobile.spec.ts` — E2E mobile tests
3. `tests/frontend/e2e/theme.spec.ts` — E2E theme tests
4. `docs/frontend/accessibility-guide.md` — A11y documentation
5. `docs/frontend/responsive-design.md` — Responsive design docs
6. `docs/frontend/dark-mode.md` — Dark mode documentation

### Field 3: Responsibilities

**tests/frontend/e2e/accessibility.spec.ts:**
- E2E A11y tests with:
  - Test: Landing page accessible
  - Test: Dashboard accessible
  - Test: Forms accessible
  - Test: Navigation accessible
  - Test: Modals accessible
  - **Test: All E2E A11y tests pass**

**tests/frontend/e2e/mobile.spec.ts:**
- E2E mobile tests with:
  - Test: Mobile navigation works
  - Test: Touch interactions work
  - Test: Forms submit on mobile
  - Test: No horizontal scroll
  - Test: Bottom sheets work
  - **Test: All E2E mobile tests pass**

**tests/frontend/e2e/theme.spec.ts:**
- E2E theme tests with:
  - Test: Theme toggle works
  - Test: Theme persists
  - Test: Dark mode renders correctly
  - Test: System preference respected
  - Test: All components themed
  - **Test: All E2E theme tests pass**

**docs/frontend/accessibility-guide.md:**
- A11y guide with:
  - WCAG 2.1 AA requirements
  - Component accessibility patterns
  - Keyboard navigation guide
  - Screen reader testing
  - A11y testing checklist
  - **Content: Complete A11y guide**

**docs/frontend/responsive-design.md:**
- Responsive docs with:
  - Breakpoint system
  - Mobile-first approach
  - Touch target guidelines
  - Responsive component patterns
  - Testing on devices
  - **Content: Complete responsive guide**

**docs/frontend/dark-mode.md:**
- Dark mode docs with:
  - Theme system architecture
  - Color palette reference
  - Implementation guide
  - Testing dark mode
  - Best practices
  - **Content: Complete dark mode guide**

### Field 4: Depends On
- All Week 23 frontend work
- Playwright E2E setup

### Field 5: Expected Output
- Complete E2E test coverage
- Documentation complete

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- All frontend features tested and documented

### Field 8: Error Handling
- Test failure reporting
- Documentation versioning

### Field 9: Security Requirements
- No sensitive data in docs
- Secure test data

### Field 10: Integration Points
- All frontend components
- CI/CD pipeline

### Field 11: Code Quality
- Comprehensive test coverage
- Clear documentation

### Field 12: GitHub CI Requirements
- All E2E tests pass
- Docs build successfully

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: All E2E tests pass**
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
npx axe-core frontend/src
npx lighthouse http://localhost:3000 --only-categories=accessibility
```

#### 2. Responsive Tests
```bash
npm run test:responsive
npx playwright test tests/frontend/e2e/mobile.spec.ts
```

#### 3. Theme Tests
```bash
npm run test:theme
npx playwright test tests/frontend/e2e/theme.spec.ts
```

#### 4. Performance Tests
```bash
npm run lighthouse
npx lighthouse http://localhost:3000 --output=json
```

#### 5. Full E2E Suite
```bash
npx playwright test
npm run test:coverage
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | WCAG 2.1 AA | 100% compliance |
| 2 | Lighthouse A11y | Score >90 |
| 3 | Touch targets | All ≥44px |
| 4 | Dark mode | Fully functional |
| 5 | Theme persistence | Works correctly |
| 6 | System preference | Detected correctly |
| 7 | LCP | <2.5s |
| 8 | CLS | <0.1 |
| 9 | Lighthouse Overall | >90 |
| 10 | Mobile navigation | Works correctly |

---

### Week 23 PASS Criteria

1. ✅ WCAG 2.1 AA: 100% compliance
2. ✅ Lighthouse Accessibility: >90
3. ✅ All pages responsive
4. ✅ Touch targets ≥44px
5. ✅ Dark mode fully functional
6. ✅ Theme toggle with system preference
7. ✅ Lighthouse Performance >90
8. ✅ LCP <2.5s
9. ✅ CLS <0.1
10. ✅ All E2E tests pass
11. ✅ Documentation complete
12. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Status | Files | Tests | Pushed |
|---------|-----|--------|-------|-------|--------|
| Builder 1 | Day 1 | ⏳ PENDING | Accessibility (6 files) | - | NO |
| Builder 2 | Day 2 | ⏳ PENDING | Mobile Responsive (6 files) | - | NO |
| Builder 3 | Day 3 | ⏳ PENDING | Dark Mode (6 files) | - | NO |
| Builder 4 | Day 4 | ⏳ PENDING | Performance (5 files) | - | NO |
| Builder 5 | Day 5 | ⏳ PENDING | Testing + Docs (6 files) | - | NO |
| Tester | Day 6 | ⏳ PENDING | Full validation | - | NO |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. WCAG 2.1 AA compliance is MANDATORY
3. Mobile-first approach for all new components
4. Dark mode must support system preference
5. **WCAG 2.1 AA: 100% compliance**
6. **Lighthouse Accessibility: >90**
7. **All pages responsive**
8. **Dark mode fully functional**
9. **Lighthouse Performance: >90**
10. All features must be tested and documented

**ACCESSIBILITY CHECKLIST:**
- [ ] All images have alt text
- [ ] All forms have labels
- [ ] Color contrast ≥4.5:1
- [ ] Keyboard navigation works
- [ ] Focus indicators visible
- [ ] Skip links present
- [ ] ARIA labels correct

**MOBILE CHECKLIST:**
- [ ] Touch targets ≥44px
- [ ] No horizontal scroll
- [ ] Readable text (16px min)
- [ ] Forms usable on mobile
- [ ] Navigation accessible

**DARK MODE CHECKLIST:**
- [ ] All components styled
- [ ] Theme toggle works
- [ ] System preference detected
- [ ] Theme persists on reload
- [ ] No flash on load

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 23 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | Accessibility (A11y) |
| Day 2 | 6 | Mobile Responsive |
| Day 3 | 6 | Dark Mode |
| Day 4 | 5 | Performance |
| Day 5 | 6 | Testing + Docs |
| **Total** | **29** | **Frontend Polish** |

---

═══════════════════════════════════════════════════════════════════════════════
## EXECUTION ORDER
═══════════════════════════════════════════════════════════════════════════════

```
Week 23 FULLY PARALLEL Execution:

Day 1-5: ALL BUILDERS RUN SIMULTANEOUSLY
├── Builder 1: Accessibility (A11y) Compliance (6 files)
├── Builder 2: Mobile Responsive Design (6 files)
├── Builder 3: Dark Mode Implementation (6 files)
├── Builder 4: Frontend Performance (5 files)
└── Builder 5: Testing + Documentation (6 files)

Day 6: Tester → A11y + Mobile + Dark Mode + Performance validation
```

**ALL Builders can start NOW. No waiting required.**

---

═══════════════════════════════════════════════════════════════════════════════
## PHASE 7 PROGRESS
═══════════════════════════════════════════════════════════════════════════════

**Phase 7: Scale to 20 Clients (Weeks 21-27)**

| Week | Goal | Status |
|------|------|--------|
| 21 | Clients 3-5 + Collective Intelligence | ✅ COMPLETE |
| 22 | Clients 6-10 + 85% Accuracy | ⚠️ PARTIAL (training done, clients pending) |
| 23 | Frontend Polish (A11y, Mobile, Dark Mode) | 🔄 In Progress |
| 24 | Client Success Tooling | ⏳ Pending |
| 25 | Financial Services Vertical | ⏳ Pending |
| 26 | Performance Optimization | ⏳ Pending |
| 27 | 20-Client Validation | ⏳ Pending |

**Note:** Week 22 deviated from roadmap (focused on Agent Lightning v2 instead of client scaling).
Week 23 follows roadmap: Frontend Polish.
