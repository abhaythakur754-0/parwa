---
Task ID: 1
Agent: Main Agent
Task: Fix all onboarding flow issues identified by user

Work Log:
- Read all onboarding step components and API routes to understand current state
- Removed Step 1 (IndustryVariantStep) from onboarding wizard — users already select variants on models page
- Updated ONBOARDING_STEPS in types/onboarding.ts from 7 steps to 6 steps (removed "Plan" step)
- Rewrote OnboardingWizard.tsx to use 6-step flow: Legal → Integrations → Knowledge → AI Setup → Review → Launch
- Added backend API call to ModelsPage confirm modal to save industry-variant selection to backend
- Fixed KnowledgeUpload.tsx to gracefully handle backend unavailability — files are now "queued" instead of "failed" with retry support
- Fixed IntegrationStep.tsx to be truly universal — added custom test URL field for unknown platforms with HTTP method selector
- Fixed AIConfig.tsx to save config to localStorage as fallback when backend is down, shows proper toast messages
- Added CloudOff icon for queued documents, RefreshCw for retry button
- Fixed VariantData interface in ModelsPage to include keyAdvantage and smartDecisions optional fields
- Fixed OnboardingWizard fallback OnboardingState to include all required fields
- Verified build passes with no new errors

Stage Summary:
- Onboarding is now 6 steps (removed redundant variant selection)
- Knowledge upload no longer shows errors when backend is down — shows "queued" status
- AI Setup no longer shows "something went wrong" — saves locally when backend unavailable
- Integration step is now universal — any platform with any API keys can be connected
- Custom test URL field added for platforms not in the catalog
- Phone number field already existed in AIConfig (verified)
- Pricing confirmed at $3,999 for High (no ₹4999 found in codebase)
- All backend connections properly handle 503/unavailable with graceful fallback
