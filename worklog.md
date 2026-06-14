---
Task ID: 1
Agent: main
Task: Connect all onboarding steps to dashboard with full E2E wiring

Work Log:
- Rewrote IntegrationStep.tsx to use the full INTEGRATION_CATALOG with 25+ tools organized by category
- Added industry-based recommendations (shows tools relevant to the user's industry)
- Added search functionality across all integrations
- Added category expand/collapse with "X more in Category" links
- Added CatalogCard, CatalogIntegrationForm, and CustomIntegrationForm sub-components
- Added stats row (Verified/Failed/Not Tested) for connected integrations
- Added localStorage persistence for integrations (parwa_integrations_summary)
- Added localStorage persistence for knowledge base (parwa_kb_summary) in KnowledgeUpload.tsx
- Added aiConfig state to dashboard page (reads parwa_ai_config from localStorage)
- Added integrationsSummary state to dashboard page (reads parwa_integrations_summary from localStorage)
- Added kbSummary state to dashboard page (reads parwa_kb_summary from localStorage)
- Added Onboarding Summary section to dashboard with 3 cards: AI Assistant Config, Connected Integrations, Knowledge Base
- Updated Jarvis CC section to use dynamic AI name from onboarding config
- Updated WelcomeCard to accept and use aiName prop instead of hardcoded "Jarvis"
- Updated FirstVictory to set parwa_onboarding_completed in localStorage on dashboard redirect
- Build passes successfully

Stage Summary:
- IntegrationStep now shows ALL 25+ catalog tools with industry recommendations and search
- Dashboard now shows full onboarding data: AI config, integrations summary, KB status
- All onboarding steps are connected to dashboard via localStorage
- Build passes with no new errors
