---
Task ID: 1
Agent: Main Agent
Task: Fix TDZ errors on onboarding page and E2E test before pushing

Work Log:
- Analyzed OnboardingWizard.tsx and found ALL 6 step components were statically imported
- Identified that integration-catalog (992 lines) was also statically imported
- Rewrote OnboardingWizard.tsx to lazy-load ALL step components with next/dynamic(ssr:false)
- Lazy-loaded integration-catalog dynamically via useEffect
- Duplicated ParwaVariant/ParwaIndustry types locally to avoid static type imports
- Added webpack fallback config for Node.js modules (fs, net, tls) in next.config.mjs
- Removed duplicate next.config.ts (was conflicting with next.config.mjs)
- Built production bundle successfully
- E2E tested with agent-browser: page loads, no TDZ errors, redirects to login correctly
- HTTP tests: root page 200, onboarding page 200, no error strings in HTML
- Verified code-splitting: each step component is in its own JS chunk
- Pushed to GitHub: commit 5e4df186

Stage Summary:
- TDZ errors FIXED - "Cannot access 'X' before initialization" is gone
- All 6 onboarding step components now load lazily in separate chunks
- Page renders correctly, auth redirect works, back-navigation present
- Code pushed to GitHub main branch
