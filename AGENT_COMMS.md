# AGENT_COMMS.md — Week 34 Day 1-6
# Last updated by: Manager Agent
# Current status: WEEK 34 — FRONTEND V2 (REACT QUERY + PWA)

═══════════════════════════════════════════════════════════════════════════════
## MANAGER → WEEK 34 PLAN
═══════════════════════════════════════════════════════════════════════════════
Written by: Manager Agent
Date: 2026-03-27

> **Phase: Phase 8 — Enterprise Preparation (Weeks 28-40)**
>
> **Week 34 Goals (Per Roadmap):**
> - Day 1: React Query Setup & Migration
> - Day 2: Optimistic Updates & Cache Management
> - Day 3: PWA Foundation & Service Worker
> - Day 4: Offline Support & Sync
> - Day 5: PWA Features & Performance Optimization + Tests
> - Day 6: Tester runs full validation
>
> **CRITICAL RULES:**
> 1. All 5 days run in PARALLEL — no cross-day dependencies
> 2. React Query replaces existing Zustand data fetching
> 3. PWA must work offline for core features
> 4. **Maintain existing functionality during migration**
> 5. **All features tested against 30 clients**
> 6. **Lighthouse PWA score ≥90**
> 7. **Maintain 91%+ Agent Lightning accuracy**

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 1 (DAY 1) — React Query Setup & Migration
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/lib/react-query/provider.tsx`
2. `frontend/lib/react-query/client.ts`
3. `frontend/lib/react-query/hooks/useTickets.ts`
4. `frontend/lib/react-query/hooks/useApprovals.ts`
5. `frontend/lib/react-query/hooks/useAnalytics.ts`
6. `tests/frontend/test_react_query_setup.test.ts`

### Field 2: What is each file?
1. `frontend/lib/react-query/provider.tsx` — React Query provider
2. `frontend/lib/react-query/client.ts` — Query client configuration
3. `frontend/lib/react-query/hooks/useTickets.ts` — Tickets query hooks
4. `frontend/lib/react-query/hooks/useApprovals.ts` — Approvals query hooks
5. `frontend/lib/react-query/hooks/useAnalytics.ts` — Analytics query hooks
6. `tests/frontend/test_react_query_setup.test.ts` — Setup tests

### Field 3: Responsibilities

**frontend/lib/react-query/provider.tsx:**
- React Query provider with:
  - QueryClientProvider setup
  - DevTools integration (dev only)
  - Error boundary integration
  - Hydration support for SSR
  - Client-side query persistence
  - **Test: Provider wraps app correctly**

**frontend/lib/react-query/client.ts:**
- Query client with:
  - Default staleTime configuration
  - Default cacheTime configuration
  - Retry configuration
  - Error handling setup
  - Mutation defaults
  - Query invalidation helpers
  - **Test: Client initializes correctly**
  - **Test: Default options applied**

**frontend/lib/react-query/hooks/useTickets.ts:**
- Tickets hooks with:
  - useTickets (list query)
  - useTicket (single query)
  - useCreateTicket (mutation)
  - useUpdateTicket (mutation)
  - useTicketFilters (query with params)
  - Automatic cache invalidation
  - **Test: useTickets fetches correctly**
  - **Test: useCreateTicket works**
  - **Test: Cache invalidates on mutation**

**frontend/lib/react-query/hooks/useApprovals.ts:**
- Approvals hooks with:
  - useApprovals (list query)
  - useApproval (single query)
  - useApproveAction (mutation)
  - useRejectAction (mutation)
  - useApprovalQueue (filtered query)
  - Automatic cache invalidation
  - **Test: useApprovals fetches correctly**
  - **Test: useApproveAction works**
  - **Test: Paddle called exactly once**

**frontend/lib/react-query/hooks/useAnalytics.ts:**
- Analytics hooks with:
  - useAnalytics (dashboard data)
  - useMetrics (performance metrics)
  - useChartData (chart-specific)
  - useExportData (mutation)
  - Real-time subscription support
  - **Test: useAnalytics fetches correctly**
  - **Test: useExportData works**
  - **Test: Real-time updates work**

**tests/frontend/test_react_query_setup.test.ts:**
- Setup tests with:
  - Test: Provider renders
  - Test: Client configuration correct
  - Test: Hooks work with mocked data
  - Test: Error handling works
  - Test: Cache invalidation works
  - **CRITICAL: All React Query setup tests pass**

### Field 4: Depends On
- Existing frontend (Weeks 15-18)
- API client service
- Existing Zustand stores (for migration)

### Field 5: Expected Output
- React Query fully configured
- Core data hooks migrated

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- Data fetching uses React Query instead of manual fetching

### Field 8: Error Handling
- Query error boundaries
- Retry logic for failed queries
- Graceful degradation

### Field 9: Security Requirements
- Auth token in query headers
- Secure query key management
- No sensitive data in query cache

### Field 10: Integration Points
- API client
- Existing Zustand stores (migration)
- Error boundary

### Field 11: Code Quality
- Type-safe query keys
- Consistent hook patterns
- Proper TypeScript types

### Field 12: GitHub CI Requirements
- All tests pass
- npm run build succeeds
- No TypeScript errors

### Field 13: Pass Criteria
Builder 1 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: React Query setup works**
- **CRITICAL: Hooks fetch data correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 2 (DAY 2) — Optimistic Updates & Cache Management
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/lib/react-query/mutations/approvals.ts`
2. `frontend/lib/react-query/mutations/tickets.ts`
3. `frontend/lib/react-query/mutations/settings.ts`
4. `frontend/lib/react-query/cache/invalidation.ts`
5. `frontend/lib/react-query/cache/prefetch.ts`
6. `tests/frontend/test_optimistic_updates.test.ts`

### Field 2: What is each file?
1. `frontend/lib/react-query/mutations/approvals.ts` — Approval mutations
2. `frontend/lib/react-query/mutations/tickets.ts` — Ticket mutations
3. `frontend/lib/react-query/mutations/settings.ts` — Settings mutations
4. `frontend/lib/react-query/cache/invalidation.ts` — Cache invalidation
5. `frontend/lib/react-query/cache/prefetch.ts` — Data prefetching
6. `tests/frontend/test_optimistic_updates.test.ts` — Optimistic update tests

### Field 3: Responsibilities

**frontend/lib/react-query/mutations/approvals.ts:**
- Approval mutations with:
  - Optimistic update on approve
  - Rollback on error
  - Success toast notification
  - Error handling with retry option
  - Related cache invalidation
  - **Test: Optimistic update applies immediately**
  - **Test: Rollback on API error**
  - **Test: Success notification shows**

**frontend/lib/react-query/mutations/tickets.ts:**
- Ticket mutations with:
  - Optimistic create/update
  - Status change handling
  - Assignment change handling
  - Bulk operations support
  - Related data refresh
  - **Test: Optimistic ticket create**
  - **Test: Optimistic ticket update**
  - **Test: Bulk operations work**

**frontend/lib/react-query/mutations/settings.ts:**
- Settings mutations with:
  - Profile update optimistic
  - Settings change tracking
  - Form dirty state handling
  - Conflict detection
  - Revert capability
  - **Test: Settings update optimistically**
  - **Test: Conflict detection works**
  - **Test: Revert functionality works**

**frontend/lib/react-query/cache/invalidation.ts:**
- Cache invalidation with:
  - Smart invalidation strategies
  - Partial cache updates
  - Related query invalidation
  - Tag-based invalidation
  - Time-based invalidation
  - Manual refresh triggers
  - **Test: Invalidates related queries**
  - **Test: Partial updates work**
  - **Test: Tag-based invalidation works**

**frontend/lib/react-query/cache/prefetch.ts:**
- Data prefetching with:
  - Route-based prefetching
  - Hover prefetching
  - Background data refresh
  - Critical data prioritization
  - Prefetch queue management
  - **Test: Prefetch on hover**
  - **Test: Route prefetching works**
  - **Test: Background refresh works**

**tests/frontend/test_optimistic_updates.test.ts:**
- Optimistic update tests with:
  - Test: Approvals update optimistically
  - Test: Tickets update optimistically
  - Test: Settings update optimistically
  - Test: Rollback on error
  - Test: Cache consistency
  - **CRITICAL: All optimistic update tests pass**

### Field 4: Depends On
- React Query setup (Day 1)
- Existing mutation handlers
- Notification system

### Field 5: Expected Output
- Optimistic updates for all mutations
- Smart cache management

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- User sees immediate feedback on actions before API confirms

### Field 8: Error Handling
- Rollback on failure
- Retry mechanisms
- User notification on error

### Field 9: Security Requirements
- No sensitive data in optimistic updates
- Secure mutation payloads

### Field 10: Integration Points
- API mutations
- Notification system
- Error boundary

### Field 11: Code Quality
- Type-safe mutations
- Consistent error handling
- Comprehensive logging

### Field 12: GitHub CI Requirements
- All tests pass
- No TypeScript errors

### Field 13: Pass Criteria
Builder 2 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Optimistic updates work**
- **CRITICAL: Rollback on error works**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 3 (DAY 3) — PWA Foundation & Service Worker
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/public/manifest.json`
2. `frontend/lib/pwa/service-worker.ts`
3. `frontend/lib/pwa/register.ts`
4. `frontend/lib/pwa/cache-strategies.ts`
5. `frontend/components/pwa/install-prompt.tsx`
6. `tests/frontend/test_pwa_foundation.test.ts`

### Field 2: What is each file?
1. `frontend/public/manifest.json` — PWA manifest
2. `frontend/lib/pwa/service-worker.ts` — Service worker
3. `frontend/lib/pwa/register.ts` — SW registration
4. `frontend/lib/pwa/cache-strategies.ts` — Caching strategies
5. `frontend/components/pwa/install-prompt.tsx` — Install prompt
6. `tests/frontend/test_pwa_foundation.test.ts` — PWA foundation tests

### Field 3: Responsibilities

**frontend/public/manifest.json:**
- PWA manifest with:
  - App name and short name
  - Icons (all sizes: 72, 96, 128, 144, 152, 192, 384, 512)
  - Start URL
  - Display mode (standalone)
  - Theme color
  - Background color
  - Orientation
  - Shortcuts for quick actions
  - **Test: Manifest valid JSON**
  - **Test: All icons referenced**
  - **Test: Lighthouse manifest check passes**

**frontend/lib/pwa/service-worker.ts:**
- Service worker with:
  - Install event handling
  - Activate event handling
  - Fetch event interception
  - Cache versioning
  - Skip waiting support
  - Background sync registration
  - **Test: Service worker installs**
  - **Test: Cache versioning works**
  - **Test: Skip waiting works**

**frontend/lib/pwa/register.ts:**
- SW registration with:
  - Service worker registration
  - Update detection
  - Update notification
  - Error handling
  - Development mode handling
  - **Test: Registration succeeds**
  - **Test: Update detection works**
  - **Test: Dev mode skips registration**

**frontend/lib/pwa/cache-strategies.ts:**
- Cache strategies with:
  - Cache-first for static assets
  - Network-first for API calls
  - Stale-while-revalidate for data
  - Cache versioning
  - Cache size limits
  - **Test: Cache-first works**
  - **Test: Network-first works**
  - **Test: Stale-while-revalidate works**

**frontend/components/pwa/install-prompt.tsx:**
- Install prompt with:
  - Beforeinstallprompt event handling
  - Custom install UI
  - Install button display
  - Install analytics
  - Post-install welcome
  - **Test: Prompt shows on eligible browsers**
  - **Test: Install triggers correctly**
  - **Test: Analytics fires on install**

**tests/frontend/test_pwa_foundation.test.ts:**
- PWA foundation tests with:
  - Test: Manifest valid
  - Test: Service worker registers
  - Test: Cache strategies work
  - Test: Install prompt shows
  - Test: Lighthouse PWA checks pass
  - **CRITICAL: All PWA foundation tests pass**
  - **CRITICAL: Lighthouse PWA score ≥90**

### Field 4: Depends On
- Next.js configuration
- Build configuration
- Asset generation

### Field 5: Expected Output
- PWA manifest and service worker
- Install prompt component

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- User can install PARWA as a native-like app

### Field 8: Error Handling
- Graceful fallback for unsupported browsers
- Service worker error recovery

### Field 9: Security Requirements
- Service worker scope limited
- HTTPS only
- Secure cache handling

### Field 10: Integration Points
- Next.js build
- Static assets
- Update notification system

### Field 11: Code Quality
- TypeScript for service worker
- Clear cache strategy documentation
- Version management

### Field 12: GitHub CI Requirements
- All tests pass
- Lighthouse PWA audit passes
- Manifest validates

### Field 13: Pass Criteria
Builder 3 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: PWA installable**
- **CRITICAL: Lighthouse PWA ≥90**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 4 (DAY 4) — Offline Support & Sync
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/lib/pwa/offline-storage.ts`
2. `frontend/lib/pwa/offline-queue.ts`
3. `frontend/lib/pwa/sync-manager.ts`
4. `frontend/components/pwa/offline-indicator.tsx`
5. `frontend/hooks/useOfflineStatus.ts`
6. `tests/frontend/test_offline_support.test.ts`

### Field 2: What is each file?
1. `frontend/lib/pwa/offline-storage.ts` — Offline data storage
2. `frontend/lib/pwa/offline-queue.ts` — Offline action queue
3. `frontend/lib/pwa/sync-manager.ts` — Sync manager
4. `frontend/components/pwa/offline-indicator.tsx` — Offline indicator
5. `frontend/hooks/useOfflineStatus.ts` — Offline status hook
6. `tests/frontend/test_offline_support.test.ts` — Offline support tests

### Field 3: Responsibilities

**frontend/lib/pwa/offline-storage.ts:**
- Offline storage with:
  - IndexedDB wrapper
  - Data persistence
  - Storage quota management
  - Data versioning
  - Cleanup strategies
  - Encryption for sensitive data
  - **Test: Data persists offline**
  - **Test: Storage quota managed**
  - **Test: Data encrypted correctly**

**frontend/lib/pwa/offline-queue.ts:**
- Offline queue with:
  - Action queueing
  - Priority handling
  - Conflict detection
  - Retry logic
  - Queue persistence
  - Queue status tracking
  - **Test: Actions queue offline**
  - **Test: Priority ordering works**
  - **Test: Queue persists across sessions**

**frontend/lib/pwa/sync-manager.ts:**
- Sync manager with:
  - Background sync API
  - Periodic sync
  - Conflict resolution
  - Sync status tracking
  - Failed sync handling
  - Manual sync trigger
  - **Test: Background sync works**
  - **Test: Conflicts resolved**
  - **Test: Manual sync triggers**

**frontend/components/pwa/offline-indicator.tsx:**
- Offline indicator with:
  - Connection status display
  - Offline mode banner
  - Pending actions count
  - Sync status
  - Retry button
  - **Test: Indicator shows offline**
  - **Test: Pending count accurate**
  - **Test: Retry button works**

**frontend/hooks/useOfflineStatus.ts:**
- Offline status hook with:
  - Online/offline detection
  - Connection quality
  - Pending actions count
  - Sync status
  - Last sync timestamp
  - **Test: Detects online/offline**
  - **Test: Tracks pending actions**
  - **Test: Updates sync status**

**tests/frontend/test_offline_support.test.ts:**
- Offline support tests with:
  - Test: Offline storage works
  - Test: Action queue works
  - Test: Sync manager works
  - Test: Indicator displays correctly
  - Test: Offline-first data access
  - **CRITICAL: All offline support tests pass**
  - **CRITICAL: Core features work offline**

### Field 4: Depends On
- PWA foundation (Day 3)
- React Query (Days 1-2)
- IndexedDB

### Field 5: Expected Output
- Complete offline support
- Action synchronization

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- User can work offline and sync when back online

### Field 8: Error Handling
- Conflict resolution
- Failed sync retry
- Storage quota exceeded handling

### Field 9: Security Requirements
- Encrypted offline storage
- Secure sync protocols
- No sensitive data in queue

### Field 10: Integration Points
- React Query cache
- Service worker
- API sync endpoints

### Field 11: Code Quality
- Type-safe queue items
- Clear sync states
- Comprehensive error handling

### Field 12: GitHub CI Requirements
- All tests pass
- Offline scenarios work

### Field 13: Pass Criteria
Builder 4 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Offline support works**
- **CRITICAL: Sync works correctly**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER 5 (DAY 5) — PWA Features & Performance Optimization + Tests
═══════════════════════════════════════════════════════════════════════════════

### Field 1: Files to Build (in order)
1. `frontend/lib/pwa/push-notifications.ts`
2. `frontend/components/pwa/notification-handler.tsx`
3. `frontend/lib/pwa/performance.ts`
4. `tests/frontend/test_pwa_features.test.ts`
5. `tests/frontend/test_pwa_lighthouse.test.ts`
6. `reports/week34_frontend_v2_report.md`

### Field 2: What is each file?
1. `frontend/lib/pwa/push-notifications.ts` — Push notifications
2. `frontend/components/pwa/notification-handler.tsx` — Notification handler
3. `frontend/lib/pwa/performance.ts` — Performance optimization
4. `tests/frontend/test_pwa_features.test.ts` — PWA features tests
5. `tests/frontend/test_pwa_lighthouse.test.ts` — Lighthouse tests
6. `reports/week34_frontend_v2_report.md` — Week 34 report

### Field 3: Responsibilities

**frontend/lib/pwa/push-notifications.ts:**
- Push notifications with:
  - Push subscription management
  - Notification permission handling
  - Notification display
  - Action button handling
  - Deep linking
  - Notification analytics
  - **Test: Permission request works**
  - **Test: Notification displays**
  - **Test: Deep linking works**

**frontend/components/pwa/notification-handler.tsx:**
- Notification handler with:
  - Permission request UI
  - Notification preferences
  - Notification history
  - Notification actions
  - Quiet hours support
  - **Test: Permission UI renders**
  - **Test: Preferences save**
  - **Test: Quiet hours work**

**frontend/lib/pwa/performance.ts:**
- Performance optimization with:
  - Code splitting configuration
  - Lazy loading setup
  - Image optimization
  - Font loading optimization
  - Bundle analysis
  - Performance monitoring
  - **Test: Code splitting works**
  - **Test: Images optimized**
  - **Test: Bundle size acceptable**

**tests/frontend/test_pwa_features.test.ts:**
- PWA features tests with:
  - Test: Push notifications work
  - Test: Notification handler works
  - Test: Performance optimizations applied
  - Test: All PWA features integrated
  - **CRITICAL: All PWA feature tests pass**

**tests/frontend/test_pwa_lighthouse.test.ts:**
- Lighthouse tests with:
  - Test: PWA score ≥90
  - Test: Performance score ≥80
  - Test: Accessibility score ≥90
  - Test: Best practices score ≥90
  - Test: SEO score ≥90
  - **CRITICAL: All Lighthouse thresholds met**

**reports/week34_frontend_v2_report.md:**
- Week 34 report with:
  - React Query migration summary
  - PWA implementation summary
  - Lighthouse scores
  - Performance metrics
  - Known issues and resolutions
  - Next steps
  - **Content: Week 34 completion report**

### Field 4: Depends On
- All Week 34 components (Days 1-4)
- Frontend infrastructure
- Lighthouse CI

### Field 5: Expected Output
- Push notification support
- Performance optimization
- Week 34 completion report

### Field 6: Unit Test Files
- Tests in deliverables

### Field 7: BDD Scenario
- User receives push notifications and app performs well

### Field 8: Error Handling
- Notification permission denied handling
- Performance fallbacks

### Field 9: Security Requirements
- Secure push subscription
- VAPID key management
- Notification content filtering

### Field 10: Integration Points
- Push notification service
- Analytics
- Performance monitoring

### Field 11: Code Quality
- Performance budgeting
- Bundle size monitoring
- Clear notification UX

### Field 12: GitHub CI Requirements
- All tests pass
- Lighthouse CI passes
- Bundle size within budget

### Field 13: Pass Criteria
Builder 5 reports DONE when:
- All 6 files built and pushed
- **CRITICAL: Push notifications work**
- **CRITICAL: Lighthouse PWA ≥90**
- **CRITICAL: Performance optimized**
- GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## TESTER → WEEK 34 INSTRUCTIONS (DAY 6)
═══════════════════════════════════════════════════════════════════════════════

**Run AFTER all Builders 1-5 report DONE**

### Test Commands

#### 1. React Query Setup Tests
```bash
npm run test -- tests/frontend/test_react_query_setup.test.ts
```

#### 2. Optimistic Update Tests
```bash
npm run test -- tests/frontend/test_optimistic_updates.test.ts
```

#### 3. PWA Foundation Tests
```bash
npm run test -- tests/frontend/test_pwa_foundation.test.ts
```

#### 4. Offline Support Tests
```bash
npm run test -- tests/frontend/test_offline_support.test.ts
```

#### 5. PWA Features Tests
```bash
npm run test -- tests/frontend/test_pwa_features.test.ts
npm run test -- tests/frontend/test_pwa_lighthouse.test.ts
```

#### 6. Build and Lighthouse
```bash
npm run build
npm run lighthouse
```

#### 7. Full Regression
```bash
./scripts/run_full_regression.sh
```

---

### Critical Tests Verification

| # | Test | Expected |
|---|------|----------|
| 1 | React Query setup | Works correctly |
| 2 | Data hooks | Fetch correctly |
| 3 | Optimistic updates | Apply immediately |
| 4 | Rollback on error | Works correctly |
| 5 | PWA manifest | Valid and complete |
| 6 | Service worker | Installs correctly |
| 7 | Install prompt | Shows correctly |
| 8 | Offline storage | Persists data |
| 9 | Offline queue | Queues actions |
| 10 | Sync manager | Syncs when online |
| 11 | Push notifications | Work correctly |
| 12 | **Lighthouse PWA** | **≥90 (CRITICAL)** |
| 13 | **Lighthouse Performance** | **≥80** |
| 14 | **Lighthouse Accessibility** | **≥90** |
| 15 | Offline core features | Work offline |
| 16 | Agent Lightning | ≥91% accuracy maintained |

---

### Week 34 PASS Criteria

1. ✅ **React Query: Fully integrated**
2. ✅ **Data Hooks: All migrated**
3. ✅ **Optimistic Updates: Working correctly**
4. ✅ **Cache Management: Smart invalidation**
5. ✅ **PWA Manifest: Valid and complete**
6. ✅ **Service Worker: Installed and working**
7. ✅ **Install Prompt: Shows correctly**
8. ✅ **Offline Storage: Data persists**
9. ✅ **Offline Queue: Actions queued**
10. ✅ **Sync Manager: Syncs correctly**
11. ✅ **Push Notifications: Working**
12. ✅ **Lighthouse PWA: ≥90 (CRITICAL)**
13. ✅ **Performance Optimized**
14. ✅ **All 30 Clients: Validated**
15. ✅ **Agent Lightning: ≥91% accuracy maintained**
16. ✅ GitHub CI GREEN

---

═══════════════════════════════════════════════════════════════════════════════
## BUILDER STATUS
═══════════════════════════════════════════════════════════════════════════════

| Builder | Day | Focus | Files | Status |
|---------|-----|-------|-------|--------|
| Builder 1 | Day 1 | React Query Setup & Migration | 6 | ⏳ Pending |
| Builder 2 | Day 2 | Optimistic Updates & Cache | 6 | ⏳ Pending |
| Builder 3 | Day 3 | PWA Foundation & Service Worker | 6 | ⏳ Pending |
| Builder 4 | Day 4 | Offline Support & Sync | 6 | ⏳ Pending |
| Builder 5 | Day 5 | PWA Features & Performance | 6 | ⏳ Pending |
| Tester | Day 6 | Full Validation | - | ⏳ Pending |

---

═══════════════════════════════════════════════════════════════════════════════
## MANAGER ADVICE
═══════════════════════════════════════════════════════════════════════════════

**CRITICAL REMINDERS:**

1. All 5 days run in PARALLEL — no cross-day dependencies
2. **Maintain existing functionality during migration**
3. **Lighthouse PWA score ≥90 (MANDATORY)**
4. **Core features must work offline**
5. **No performance regression**
6. **All features must work for all 30 clients**
7. **Zero cross-tenant data leaks (mandatory)**

**WEEK 34 TARGETS:**

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Clients | 30 | 30 | ✅ Maintain |
| Accuracy | 91%+ | ≥91% | ✅ Maintain |
| Lighthouse PWA | - | ≥90 | 🎯 Target |
| Lighthouse Perf | - | ≥80 | 🎯 Target |
| Offline Support | - | Core features | 🎯 Target |

**FRONTEND V2 MODULES:**

| Module | Purpose | Priority |
|--------|---------|----------|
| React Query | Data fetching layer | HIGH |
| Optimistic Updates | Immediate feedback | HIGH |
| PWA Manifest | Install capability | HIGH |
| Service Worker | Offline support | HIGH |
| Offline Queue | Action persistence | MEDIUM |
| Push Notifications | Engagement | MEDIUM |

**MIGRATION NOTES:**

- Replace manual fetch with React Query hooks
- Migrate Zustand data to React Query cache
- Keep Zustand for UI state only
- Test offline scenarios thoroughly
- Verify all existing features still work

**ASSUMPTIONS:**
- Week 33 complete (Healthcare + Logistics)
- Next.js frontend exists
- Lighthouse CI configured
- Agent Lightning at 91%+ accuracy

---

═══════════════════════════════════════════════════════════════════════════════
## WEEK 34 FILE SUMMARY
═══════════════════════════════════════════════════════════════════════════════

| Day | Files | Focus |
|-----|-------|-------|
| Day 1 | 6 | React Query Setup & Migration |
| Day 2 | 6 | Optimistic Updates & Cache |
| Day 3 | 6 | PWA Foundation & Service Worker |
| Day 4 | 6 | Offline Support & Sync |
| Day 5 | 6 | PWA Features & Performance |
| **Total** | **30** | **Frontend v2** |

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
| **34** | **Frontend v2 (React Query + PWA)** | **🔄 IN PROGRESS** |
| 35 | Smart Router 92%+ | ⏳ Pending |
| 36 | Agent Lightning 94% | ⏳ Pending |
| 37 | 50-Client Scale + Autoscaling | ⏳ Pending |
| 38 | Enterprise Pre-Preparation | ⏳ Pending |
| 39 | Final Production Readiness | ⏳ Pending |
| 40 | Weeks 1-40 Final Validation | ⏳ Pending |

**Week 34 Deliverables:**
- React Query: Complete migration 🎯 Target
- Optimistic Updates: All mutations 🎯 Target
- PWA: Installable app 🎯 Target
- Offline Support: Core features 🎯 Target
- Push Notifications: Working 🎯 Target
- **FRONTEND V2 COMPLETE!**
