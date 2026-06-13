# Phase 13 & 14 Backend API Wiring — Work Record

## Summary
Wired Phase 13 (API Key System) and Phase 14 (Variants & AI Tools) backend APIs into the PARWA frontend.

## Files Changed

### 1. `/home/z/my-project/src/lib/config.ts` (NEW)
- Created missing module that BFF routes were importing (`BACKEND_URL` from `@/lib/config`)
- Re-exports `BACKEND_URL` from `@/lib/backend-url`'s `getBackendUrl()`

### 2. `/home/z/my-project/src/components/onboarding/IntegrationStep.tsx` (MODIFIED)
- **Phase 13 API Key integration**: After `integrationsApi.create()`, now also calls `/api/api-keys/store` to store credentials with AES-256-GCM encryption
- **Key Management section**: Added to each expanded integration card showing:
  - Masked key display (e.g., "••••••••5678") with auth type badge
  - "Rotate Key" button → calls `/api/api-keys/rotate`
  - "Test Key" button → calls `/api/api-keys/test`
  - "Revoke Key" button → calls `/api/api-keys/revoke`
- **API key fetching**: On mount, fetches `/api/api-keys/list` to display masked values
- Added icons: `KeyRound`, `RefreshCw`, `Ban`, `FlaskConical`
- Key storage failure is non-critical — integration still succeeds, just shows a warning toast

### 3. `/home/z/my-project/src/app/dashboard/variants/page.tsx` (MODIFIED)
- **Phase 14 Variant Router section**: Shows active variants from `/api/variants/list`
- **Add Variant button**: Calls `/api/variants/add` with variant type selector
- **Remove Variant button**: Per-variant, calls `/api/variants/remove`
- **Route Ticket test panel**: Enter intent + complexity score (1-10 slider), calls `/api/variants/route-ticket`, shows result
- **Variant Usage section**: Table showing ticket count, avg quality, avg latency per variant from `/api/variants/usage`
- Preserved all existing Phase 5 functionality (instances, escalation, rebalance, shadow mode, tier comparison)

### 4. `/home/z/my-project/src/app/dashboard/ai-tools/page.tsx` (NEW)
- **Available Tools section**: Shows tools from `/api/ai-tools/available`, grouped by category
- **Select Tool panel**: Enter ticket intent, calls `/api/ai-tools/select`, shows selected tools
- **System Prompt section**: Displays generated prompt from `/api/ai-tools/prompt` with copy button
- Summary metrics: Available Tools count, Enabled count, Categories count

### 5. `/home/z/my-project/src/components/dashboard/DashboardSidebar.tsx` (MODIFIED)
- Added `aiTools` icon (wrench SVG)
- Added "AI Tools" nav item pointing to `/dashboard/ai-tools`

### 6. Pre-existing build fixes (not requested but needed for build):
- `/home/z/my-project/src/app/globals.css`: Fixed `@config "../../tailwind.config.mts"` → `@config "../../tailwind.config.ts"` (file was .ts, not .mts)
- `/home/z/my-project/tailwind.config.ts`: Added missing `gold` and `error` and `navy` color definitions that were referenced but undefined

## Build Verification
- `npx next build` compiles successfully with no errors
- `/dashboard/ai-tools` route appears in build output
