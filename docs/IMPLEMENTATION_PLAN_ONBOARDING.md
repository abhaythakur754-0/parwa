# PARWA Implementation Plan - Onboarding & Public Pages

> **Document Version:** 1.0  
> **Created:** Day 33 (Week 5)  
> **Scope:** Complete Frontend + Backend for Onboarding System

---

## Overview

This plan covers the complete implementation of:
1. Public-facing pages (Landing, Pricing, ROI Calculator)
2. Demo system (Jarvis Chat, Jarvis Call)
3. Post-payment flow (Details Collection)
4. Onboarding Wizard (5-step)
5. All supporting backend APIs

**Timeline:** 15-18 days (realistic estimate)

---

## Phase 1: Public Pages (3 days)

### Day 1: Landing Page + Navigation

**Backend:**
- [ ] Static content API endpoints
- [ ] Feature highlights data
- [ ] Industry themes configuration

**Frontend:**
- [ ] `frontend/src/app/page.tsx` - Landing page
- [ ] `frontend/src/components/landing/HeroSection.tsx`
- [ ] `frontend/src/components/landing/IndustrySelector.tsx`
- [ ] `frontend/src/components/landing/DogfoodingBanner.tsx`
- [ ] `frontend/src/components/landing/FeaturesSection.tsx`
- [ ] `frontend/src/components/landing/NavigationBar.tsx`
- [ ] `frontend/src/components/landing/Footer.tsx`

**Files:** ~8 components, ~2 API endpoints

---

### Day 2: Pricing Page + ROI Calculator

**Backend:**
- [ ] `/api/public/pricing` - Plan data
- [ ] `/api/public/roi/calculate` - ROI calculation
- [ ] `/api/public/roi/lead` - Lead capture

**Frontend:**
- [ ] `frontend/src/app/pricing/page.tsx`
- [ ] `frontend/src/components/pricing/PlanCard.tsx` (x3)
- [ ] `frontend/src/components/pricing/FeatureComparison.tsx`
- [ ] `frontend/src/app/calculator/page.tsx`
- [ ] `frontend/src/components/calculator/InputSection.tsx`
- [ ] `frontend/src/components/calculator/ResultsDashboard.tsx`

**Files:** ~7 components, ~3 API endpoints

---

### Day 3: Auth Pages (Signup/Login)

**Backend:**
- [ ] `/api/auth/register` - Email/password signup
- [ ] `/api/auth/google` - Google OAuth
- [ ] `/api/auth/login` - Login
- [ ] `/api/auth/verify-email` - Email verification

**Frontend:**
- [ ] `frontend/src/app/(auth)/signup/page.tsx`
- [ ] `frontend/src/app/(auth)/login/page.tsx`
- [ ] `frontend/src/app/(auth)/verify-email/page.tsx`
- [ ] `frontend/src/components/auth/SignupForm.tsx`
- [ ] `frontend/src/components/auth/LoginForm.tsx`
- [ ] `frontend/src/components/auth/SocialLogin.tsx`

**Files:** ~6 components, ~4 API endpoints

---

## Phase 2: Demo System (4 days)

### Day 4: Jarvis Chat Demo - Backend

**Backend:**
- [ ] `demo_sessions` table migration
- [ ] `demo_messages` table migration
- [ ] `/api/demo/chat/start` - Start session
- [ ] `/api/demo/chat/message` - Send message
- [ ] `/api/demo/chat/history` - Get history
- [ ] WebSocket endpoint for real-time chat
- [ ] AI integration (configurable provider)
- [ ] Message rate limiting (10 per session)

**Files:** ~2 migrations, ~1 service, ~1 API file

---

### Day 5: Jarvis Chat Demo - Frontend

**Frontend:**
- [ ] `frontend/src/app/demo/page.tsx`
- [ ] `frontend/src/components/demo/JarvisChat.tsx`
- [ ] `frontend/src/components/demo/ChatMessage.tsx`
- [ ] `frontend/src/components/demo/ChatInput.tsx`
- [ ] `frontend/src/components/demo/TypingIndicator.tsx`
- [ ] `frontend/src/components/demo/MessageLimit.tsx`
- [ ] WebSocket client integration

**Files:** ~6 components

---

### Day 6: Jarvis Demo Call - Backend

**Backend:**
- [ ] Twilio Verify API integration
- [ ] `/api/demo/call/request` - Request call
- [ ] `/api/demo/call/send-otp` - Send OTP
- [ ] `/api/demo/call/verify-otp` - Verify OTP
- [ ] `/api/demo/call/confirm-payment` - $1 payment via Paddle
- [ ] `/api/demo/call/status` - Call status
- [ ] Twilio Voice webhook handler
- [ ] Call initiation logic

**Files:** ~2 services, ~1 API file

---

### Day 7: Jarvis Demo Call - Frontend

**Frontend:**
- [ ] `frontend/src/components/demo/DemoCallFlow.tsx`
- [ ] `frontend/src/components/demo/PhoneInput.tsx`
- [ ] `frontend/src/components/demo/OTPInput.tsx`
- [ ] `frontend/src/components/demo/CallPayment.tsx`
- [ ] `frontend/src/components/demo/CallStatus.tsx`
- [ ] Post-call CTA component

**Files:** ~6 components

---

## Phase 3: Post-Payment Flow (2 days)

### Day 8: User Details Collection - Backend

**Backend:**
- [ ] `user_details` table migration
- [ ] `onboarding_state` table migration
- [ ] `/api/user/details` GET/POST
- [ ] `/api/user/verify-work-email` - Verification
- [ ] Industry options API
- [ ] Company size options API

**Files:** ~2 migrations, ~1 service, ~1 API file

---

### Day 9: User Details Collection - Frontend

**Frontend:**
- [ ] `frontend/src/app/welcome/details/page.tsx`
- [ ] `frontend/src/components/onboarding/DetailsForm.tsx`
- [ ] `frontend/src/components/onboarding/IndustrySelect.tsx`
- [ ] `frontend/src/components/onboarding/WorkEmailVerification.tsx`
- [ ] Form validation
- [ ] Progress indicator

**Files:** ~5 components

---

## Phase 4: Onboarding Wizard (5 days)

### Day 10: Wizard Infrastructure + Step 1-2

**Backend:**
- [ ] `/api/onboarding/state` GET - Get current state
- [ ] `/api/onboarding/start` POST - Initialize
- [ ] `/api/onboarding/legal` POST - Save consents
- [ ] Consent storage in `consent_records` table

**Frontend:**
- [ ] `frontend/src/app/onboarding/page.tsx`
- [ ] `frontend/src/components/onboarding/OnboardingWizard.tsx`
- [ ] `frontend/src/components/onboarding/ProgressIndicator.tsx`
- [ ] `frontend/src/components/onboarding/WelcomeScreen.tsx`
- [ ] `frontend/src/components/onboarding/LegalCompliance.tsx`

**Files:** ~5 components, ~1 API file

---

### Day 11: Integration Setup (F-030)

**Backend:**
- [ ] Pre-built integration configs
- [ ] `/api/integrations` CRUD
- [ ] `/api/integrations/:id/test` - Test connection
- [ ] OAuth flow handlers (Shopify, Slack, etc.)

**Frontend:**
- [ ] `frontend/src/components/onboarding/IntegrationSetup.tsx`
- [ ] `frontend/src/components/onboarding/IntegrationCard.tsx`
- [ ] `frontend/src/components/onboarding/OAuthButton.tsx`

**Files:** ~3 components, ~1 API file

---

### Day 12: Custom Integration Builder (F-031)

**Backend:**
- [ ] Custom integration config storage
- [ ] Connection test endpoints
- [ ] Credential encryption

**Frontend:**
- [ ] `frontend/src/components/onboarding/CustomIntegrationBuilder.tsx`
- [ ] `frontend/src/components/onboarding/AuthConfig.tsx`
- [ ] `frontend/src/components/onboarding/TestConnection.tsx`

**Files:** ~3 components, ~1 API file

---

### Day 13: Knowledge Base Upload (F-032)

**Backend:**
- [ ] File upload endpoint
- [ ] S3/R2 storage integration
- [ ] File validation (PDF, DOCX, TXT, CSV)
- [ ] Document metadata storage

**Frontend:**
- [ ] `frontend/src/components/onboarding/KnowledgeUpload.tsx`
- [ ] `frontend/src/components/onboarding/FileDropZone.tsx`
- [ ] `frontend/src/components/onboarding/FileList.tsx`
- [ ] `frontend/src/components/onboarding/UploadProgress.tsx`

**Files:** ~4 components, ~1 API file

---

### Day 14: AI Activation + First Victory (F-034, F-035)

**Backend:**
- [ ] `/api/onboarding/activate` - Activation
- [ ] Prerequisites validation
- [ ] AI configuration setup
- [ ] First victory tracking
- [ ] Celebration event emission

**Frontend:**
- [ ] `frontend/src/components/onboarding/AIConfig.tsx`
- [ ] `frontend/src/components/onboarding/ActivationButton.tsx`
- [ ] `frontend/src/components/onboarding/FirstVictory.tsx`
- [ ] Celebration animation

**Files:** ~4 components, ~1 API file

---

## Phase 5: KB Processing + Testing (2-3 days)

### Day 15: KB Processing + Indexing (F-033)

**Backend:**
- [ ] Text extraction service
- [ ] Chunking logic
- [ ] Vector embedding generation
- [ ] pgvector storage
- [ ] Processing status tracking

**Celery Tasks:**
- [ ] `process_knowledge_document` task
- [ ] `generate_embeddings` task

**Files:** ~2 services, ~2 tasks

---

### Day 16-17: Integration Testing + Polish

**Testing:**
- [ ] End-to-end tests for complete flow
- [ ] Landing → Signup → Demo → Subscribe → Onboarding
- [ ] Error handling tests
- [ ] Edge case tests

**Polish:**
- [ ] Animation refinements
- [ ] Mobile responsiveness
- [ ] Accessibility (a11y) checks
- [ ] Performance optimization

---

### Day 18: Final Integration + Deployment Prep

- [ ] Full flow testing
- [ ] Documentation updates
- [ ] Environment configuration
- [ ] Production readiness checklist

---

## Summary

| Phase | Days | Backend | Frontend |
|-------|------|---------|----------|
| Phase 1: Public Pages | 3 | 9 APIs | 21 components |
| Phase 2: Demo System | 4 | 10 APIs | 12 components |
| Phase 3: Post-Payment | 2 | 6 APIs | 5 components |
| Phase 4: Onboarding Wizard | 5 | 8 APIs | 19 components |
| Phase 5: KB + Testing | 3-4 | 2 APIs + Tasks | 0 components |
| **Total** | **17-18 days** | **35 APIs** | **57 components** |

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| Twilio | SMS OTP, Voice calls |
| Paddle | Payments ($1 demo, subscriptions) |
| OpenAI/Anthropic | AI responses (configurable) |
| S3/R2 | File storage |
| pgvector | Vector embeddings |

---

## File Structure (Planned)

```
frontend/src/
├── app/
│   ├── page.tsx                    # Landing
│   ├── pricing/page.tsx            # Pricing
│   ├── calculator/page.tsx         # ROI Calculator
│   ├── demo/page.tsx               # Demo hub
│   ├── (auth)/
│   │   ├── signup/page.tsx
│   │   ├── login/page.tsx
│   │   └── verify-email/page.tsx
│   ├── welcome/
│   │   └── details/page.tsx        # Post-payment
│   └── onboarding/page.tsx         # 5-step wizard
├── components/
│   ├── landing/
│   ├── pricing/
│   ├── calculator/
│   ├── auth/
│   ├── demo/
│   └── onboarding/

backend/app/
├── api/
│   ├── public.py                   # Public endpoints
│   ├── demo.py                     # Demo chat/call
│   ├── auth.py                     # Auth endpoints
│   ├── user_details.py             # Details collection
│   └── onboarding.py               # Onboarding APIs
├── services/
│   ├── demo_service.py
│   ├── jarvis_service.py
│   ├── onboarding_service.py
│   └── knowledge_service.py
└── tasks/
    └── knowledge_tasks.py
```

---

## Open Questions for User

1. **AI Provider for Production**: OpenAI, Anthropic, or Google Gemini?
2. **Demo Chat Limit**: Confirm 10 messages per session?
3. **Demo Call Pricing**: Confirm $1 for 3 minutes?
4. **Plan Pricing**: Finalize Starter/Growth/High prices?
5. **Pre-built Integrations**: Which ones for Phase 1? (Shopify, Slack, Zendesk?)

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Day 33 | Initial implementation plan |

---

*This plan will be updated as implementation progresses.*
