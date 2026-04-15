# PARWA Week 6 - Onboarding System Implementation Plan

> **Document Version:** 2.0  
> **Created:** Day 33 (Week 5)  
> **Updated:** Day 35 (Week 6)  
> **Scope:** COMPLETE Onboarding System (Corrected Flow)

---

## ⚠️ IMPORTANT: Day Renaming

> **Days are now ordered by the ACTUAL user flow, not by when components were built.**
> Old Day 1-2 work (User Details API + Frontend) is marked as DONE and positioned at its correct place in the flow (after payment).

---

## Corrected User Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PARWA COMPLETE USER JOURNEY                          │
└─────────────────────────────────────────────────────────────────────────────┘

  Step 1: LANDING PAGE           Day 1-2   🔲 TODO
          ↓
  Step 2: SIGNUP/LOGIN           Day 3-5   🔲 TODO
          ↓
  Step 3: PRICING + VARIANTS     Day 6-7   🔲 TODO
          ↓
  Step 4: JARVIS CHAT            Day 8-9   🔲 TODO
          ↓
  Step 5: BUSINESS EMAIL OTP     Day 10-11 🔲 TODO
          ↓
  Step 6: PAYMENT (PADDLE)       Day 12-13 🔲 TODO
          ↓
  ─────────────────────────────────────────────────────────
  Step 7: DETAILS COLLECTION     Day 14    ✅ DONE (Old Day 1-2)
  ─────────────────────────────────────────────────────────
          ↓
  Step 8: INTEGRATIONS           Day 15    🔲 TODO
          ↓
  Step 9: DASHBOARD              Day 16    🔲 TODO
          ↓
  Step 10: TESTING + POLISH      Day 17-18 🔲 TODO
```

---

## Implementation Status

### ✅ ALREADY COMPLETED (Old Day 1-2):

| Component | Status | Files |
|-----------|--------|-------|
| **User Details Migration** | ✅ DONE | `database/alembic/versions/010_onboarding_extended.py` |
| **User Details Model** | ✅ DONE | `database/models/user_details.py` |
| **User Details API** | ✅ DONE | `backend/app/api/user_details.py` |
| **User Details Service** | ✅ DONE | `backend/app/services/user_details_service.py` |
| **Onboarding Schemas** | ✅ DONE | `backend/app/schemas/onboarding.py` |
| **Onboarding Service** | ✅ DONE | `backend/app/services/onboarding_service.py` |
| **Details Page** | ✅ DONE | `frontend/src/app/welcome/details/page.tsx` |
| **DetailsForm Component** | ✅ DONE | `frontend/src/components/onboarding/DetailsForm.tsx` |
| **IndustrySelect Component** | ✅ DONE | `frontend/src/components/onboarding/IndustrySelect.tsx` |
| **WorkEmailVerification Component** | ✅ DONE | `frontend/src/components/onboarding/WorkEmailVerification.tsx` |

**Note:** These components need to be integrated INTO Jarvis Chat after payment.

---

## Day-by-Day Roadmap (Corrected Flow)

### 🔲 Day 1-2: Landing Page + Navigation (Phase 1)

**Position in Flow:** Step 1 (First thing users see)

**Frontend Components:**

| # | Component | Path | Description |
|---|-----------|------|-------------|
| 1 | NavigationBar | `components/landing/NavigationBar.tsx` | Logo + Home/Models/ROI/Jarvis Chatbot + Login |
| 2 | FeatureCarousel | `components/landing/FeatureCarousel.tsx` | Netflix-style 5-slide carousel |
| 3 | HeroSection | `components/landing/HeroSection.tsx` | Cost comparison + Jarvis preview |
| 4 | WhyChooseUs | `components/landing/WhyChooseUs.tsx` | 3 feature cards (WHAT Jarvis does) |
| 5 | HowItWorks | `components/landing/HowItWorks.tsx` | 4 animated steps (HOW Jarvis works) |
| 6 | Footer | `components/landing/Footer.tsx` | © 2026, Models link |
| 7 | Landing Page | `app/page.tsx` | Main landing page |

**Backend APIs (Optional):**
- [ ] `GET /api/public/features` - Feature highlights

**Files to Create:**
```
frontend/src/app/page.tsx
frontend/src/components/landing/NavigationBar.tsx
frontend/src/components/landing/FeatureCarousel.tsx
frontend/src/components/landing/HeroSection.tsx
frontend/src/components/landing/WhyChooseUs.tsx
frontend/src/components/landing/HowItWorks.tsx
frontend/src/components/landing/Footer.tsx
backend/app/api/public.py (optional)
```

---

### 🔲 Day 3: Auth System - Backend (Phase 2)

**Position in Flow:** Step 2 (Signup/Login)

**Database:**
- [ ] `users` table (extend if needed)
- [ ] `sessions` table for JWT sessions
- [ ] `email_otps` table for OTP verification

**Backend APIs:**
- [ ] `POST /api/auth/register` - Email/password signup
- [ ] `POST /api/auth/login` - Login
- [ ] `POST /api/auth/logout` - Logout
- [ ] `POST /api/auth/google` - Google OAuth
- [ ] `POST /api/auth/verify-email` - Email verification
- [ ] `POST /api/auth/forgot-password` - Password reset

**Services:**
- [ ] `AuthService` - Authentication logic
- [ ] `OAuthService` - Google OAuth handling
- [ ] JWT token generation/validation

**Files to Create:**
```
backend/app/services/auth_service.py
backend/app/services/oauth_service.py
backend/app/schemas/auth.py
database/alembic/versions/011_auth_system.py
tests/unit/test_auth.py
```

---

### 🔲 Day 4-5: Auth System - Frontend (Phase 2)

**Position in Flow:** Step 2 (Signup/Login)

**Frontend:**
- [ ] `frontend/src/app/(auth)/signup/page.tsx`
- [ ] `frontend/src/app/(auth)/login/page.tsx`
- [ ] `frontend/src/components/auth/SignupForm.tsx`
- [ ] `frontend/src/components/auth/LoginForm.tsx`
- [ ] `frontend/src/components/auth/SocialLogin.tsx`
- [ ] `frontend/src/contexts/AuthContext.tsx`

**Files to Create:**
```
frontend/src/app/(auth)/signup/page.tsx
frontend/src/app/(auth)/login/page.tsx
frontend/src/components/auth/SignupForm.tsx
frontend/src/components/auth/LoginForm.tsx
frontend/src/components/auth/SocialLogin.tsx
frontend/src/contexts/AuthContext.tsx
frontend/src/hooks/useAuth.ts
```

---

### 🔲 Day 6-7: Pricing Page + Industry Selector + Variants (Phase 3)

**Position in Flow:** Step 3 (Pricing + Variants)

**Frontend:**
- [ ] `frontend/src/app/pricing/page.tsx`
- [ ] `frontend/src/components/pricing/IndustrySelector.tsx` (4 industries only)
- [ ] `frontend/src/components/pricing/VariantCard.tsx`
- [ ] `frontend/src/components/pricing/QuantitySelector.tsx` ([-] N [+])
- [ ] `frontend/src/components/pricing/TotalSummary.tsx`

**Backend:**
- [ ] `GET /api/pricing/industries` - Get 4 industries
- [ ] `GET /api/pricing/variants/:industry` - Get variants by industry
- [ ] `POST /api/pricing/calculate` - Calculate total

**Database:**
- [ ] `industry_variants` table
- [ ] `pricing_variants` table

**Files to Create:**
```
frontend/src/app/pricing/page.tsx
frontend/src/components/pricing/IndustrySelector.tsx
frontend/src/components/pricing/VariantCard.tsx
frontend/src/components/pricing/QuantitySelector.tsx
frontend/src/components/pricing/TotalSummary.tsx
backend/app/api/pricing.py
backend/app/services/pricing_service.py
database/alembic/versions/012_pricing_variants.py
```

---

### 🔲 Day 8-9: Jarvis Chat System (Phase 4)

**Position in Flow:** Step 4 (Jarvis Chat with Bill Summary)

**Database:**
- [ ] `jarvis_sessions` table migration
- [ ] `jarvis_messages` table migration

**Backend APIs:**
- [ ] `POST /api/jarvis/session` - Start/continue session
- [ ] `POST /api/jarvis/message` - Send message
- [ ] `GET /api/jarvis/history` - Get chat history
- [ ] WebSocket endpoint for real-time chat
- [ ] AI integration (z-ai-web-dev-sdk)

**Services:**
- [ ] `JarvisService` - AI chat handling
- [ ] Bill summary generation

**Frontend:**
- [ ] `frontend/src/components/jarvis/JarvisChat.tsx`
- [ ] `frontend/src/components/jarvis/ChatWindow.tsx`
- [ ] `frontend/src/components/jarvis/ChatMessage.tsx`
- [ ] `frontend/src/components/jarvis/ChatInput.tsx`
- [ ] `frontend/src/components/jarvis/BillSummary.tsx`
- [ ] `frontend/src/components/jarvis/TypingIndicator.tsx`

**Files to Create:**
```
database/alembic/versions/013_jarvis_system.py
database/models/jarvis.py
backend/app/api/jarvis.py
backend/app/services/jarvis_service.py
backend/app/schemas/jarvis.py
frontend/src/components/jarvis/JarvisChat.tsx
frontend/src/components/jarvis/ChatWindow.tsx
frontend/src/components/jarvis/ChatMessage.tsx
frontend/src/components/jarvis/ChatInput.tsx
frontend/src/components/jarvis/BillSummary.tsx
frontend/src/components/jarvis/TypingIndicator.tsx
frontend/src/hooks/useJarvisChat.ts
tests/unit/test_jarvis_service.py
```

---

### 🔲 Day 10-11: Business Email OTP Verification (Phase 5)

**Position in Flow:** Step 5 (Anti-scam verification)

**Database:**
- [ ] `business_email_otps` table

**Backend APIs:**
- [ ] `POST /api/verification/send-otp` - Send OTP to business email
- [ ] `POST /api/verification/verify-otp` - Verify OTP
- [ ] Rate limiting for OTP requests

**Services:**
- [ ] `OTPService` - OTP generation and verification
- [ ] Email sending (Brevo/SendGrid)

**Frontend:**
- [ ] `frontend/src/components/verification/BusinessEmailInput.tsx`
- [ ] `frontend/src/components/verification/OTPInput.tsx`
- [ ] `frontend/src/components/verification/OTPCounter.tsx` (60s countdown)
- [ ] Integrate into Jarvis Chat flow

**Files to Create:**
```
database/alembic/versions/014_email_verification.py
backend/app/services/otp_service.py
backend/app/api/verification.py
frontend/src/components/verification/BusinessEmailInput.tsx
frontend/src/components/verification/OTPInput.tsx
frontend/src/components/verification/OTPCounter.tsx
frontend/src/hooks/useOTPVerification.ts
tests/unit/test_otp_service.py
```

---

### 🔲 Day 12-13: Payment Integration (Phase 6)

**Position in Flow:** Step 6 (Payment via Paddle)

**Backend APIs:**
- [ ] `POST /api/payments/create-session` - Create Paddle checkout
- [ ] `POST /api/payments/webhook` - Handle Paddle webhooks
- [ ] `GET /api/payments/status` - Check payment status
- [ ] `POST /api/payments/confirm` - Confirm payment

**Services:**
- [ ] `PaddleService` - Paddle SDK integration
- [ ] Payment verification logic

**Frontend:**
- [ ] `frontend/src/components/payment/PaddleCheckout.tsx`
- [ ] `frontend/src/components/payment/PaymentSuccess.tsx`
- [ ] `frontend/src/components/payment/PaymentFailed.tsx`
- [ ] Integrate into Jarvis Chat

**Files to Create:**
```
backend/app/services/paddle_service.py
backend/app/api/payments.py
backend/app/schemas/payment.py
frontend/src/components/payment/PaddleCheckout.tsx
frontend/src/components/payment/PaymentSuccess.tsx
frontend/src/components/payment/PaymentFailed.tsx
frontend/src/hooks/usePayment.ts
tests/unit/test_paddle_service.py
```

---

### ✅ Day 14: Details Collection (Phase 7) - ALREADY DONE

**Position in Flow:** Step 7 (After Payment)

**Status:** ✅ Backend DONE, ⚠️ Frontend needs integration into Jarvis Chat

**Already Completed:**
- [x] `user_details` table migration
- [x] `GET /api/onboarding/state` - Get onboarding state
- [x] `GET /api/user/details` - Get current user details
- [x] `POST /api/user/details` - Submit user details
- [x] `PATCH /api/user/details` - Update user details
- [x] `POST /api/user/verify-work-email` - Send verification email
- [x] `UserDetailsService` - CRUD for user details
- [x] `DetailsForm.tsx` component (needs integration)
- [x] `IndustrySelect.tsx` component (can reuse)
- [x] `WorkEmailVerification.tsx` component (can reuse)

**Remaining Tasks:**
- [ ] Move DetailsForm INTO Jarvis Chat
- [ ] Pre-fill known data (email, industry)
- [ ] Collect remaining: User Name
- [ ] If "Others" industry: collect industry name, company, website

**Files to Update:**
```
frontend/src/components/jarvis/JarvisDetailsForm.tsx (new)
frontend/src/components/onboarding/DetailsForm.tsx (reuse/modify)
```

---

### 🔲 Day 15: Integrations Setup (Phase 8)

**Position in Flow:** Step 8 (After Details)

**Backend APIs:**
- [ ] `GET /api/integrations/available` - List available integrations
- [ ] `POST /api/integrations` - Create integration
- [ ] `GET /api/integrations` - List user integrations
- [ ] `POST /api/integrations/:id/test` - Test connection

**Frontend:**
- [ ] `frontend/src/components/onboarding/IntegrationSetup.tsx`
- [ ] `frontend/src/components/onboarding/IntegrationCard.tsx`

**Files to Create:**
```
backend/app/api/integrations.py
backend/app/services/integration_service.py
frontend/src/components/onboarding/IntegrationSetup.tsx
frontend/src/components/onboarding/IntegrationCard.tsx
```

---

### 🔲 Day 16: Dashboard + Redirect (Phase 8)

**Position in Flow:** Step 9 (Final Destination)

**Frontend:**
- [ ] `frontend/src/app/dashboard/page.tsx`
- [ ] `frontend/src/components/dashboard/DashboardLayout.tsx`
- [ ] Redirect logic after payment + details + integrations

**Files to Create:**
```
frontend/src/app/dashboard/page.tsx
frontend/src/components/dashboard/DashboardLayout.tsx
frontend/src/components/dashboard/WelcomeCard.tsx
```

---

### 🔲 Day 17-18: Testing + Polish (Phase 9)

**Testing:**
- [ ] Test: Landing → Signup → Pricing → Variants → Jarvis → OTP → Payment → Details → Dashboard
- [ ] Test each industry flow (E-commerce, SaaS, Logistics, Others)
- [ ] Test variant quantity selection
- [ ] Test OTP verification
- [ ] Test payment success/failure
- [ ] Mobile responsiveness tests

**Files to Create:**
```
tests/e2e/test_complete_flow.py
tests/e2e/test_industry_flows.py
tests/e2e/test_payment_flow.py
```

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Days** | 18 |
| **Completed Days** | 2 (Old Day 1-2 - Details Collection) ✅ |
| **Days in Correct Position** | Phase 7 (After Payment) |
| **Days BEFORE Details** | 13 days (Day 1-13) 🔲 TODO |
| **Days AFTER Details** | 4 days (Day 15-18) 🔲 TODO |
| **Total Backend APIs** | ~25 |
| **Completed APIs** | 5 ✅ (User Details APIs) |
| **Total Frontend Components** | ~40 |
| **Completed Components** | 4 ✅ (needs integration into Jarvis) |
| **Total Database Tables** | ~10 |
| **Completed Tables** | 5 ✅ |

---

## Industry Variants Reference

### E-commerce Variants

| Variant | Description | Tickets/Month | Price/Month |
|---------|-------------|---------------|-------------|
| **Order Management** | Order status, tracking, modifications | 500 | $99 |
| **Returns & Refunds** | Return requests, refund processing | 200 | $49 |
| **Product FAQ** | Product questions, specifications | 1000 | $79 |
| **Shipping Inquiries** | Delivery status, shipping options | 300 | $59 |
| **Payment Issues** | Failed payments, billing questions | 150 | $39 |

### SaaS Variants

| Variant | Description | Tickets/Month | Price/Month |
|---------|-------------|---------------|-------------|
| **Technical Support** | Bug reports, troubleshooting | 400 | $129 |
| **Billing Support** | Subscription, invoice questions | 200 | $69 |
| **Feature Requests** | Feature questions, roadmap | 300 | $89 |
| **API Support** | API documentation, integration help | 250 | $99 |
| **Account Issues** | Login, permissions, settings | 350 | $79 |

### Logistics Variants

| Variant | Description | Tickets/Month | Price/Month |
|---------|-------------|---------------|-------------|
| **Tracking** | Shipment tracking, status updates | 800 | $89 |
| **Delivery Issues** | Missed deliveries, rescheduling | 400 | $69 |
| **Warehouse Queries** | Inventory, storage questions | 300 | $59 |
| **Fleet Management** | Driver coordination, vehicle issues | 200 | $79 |
| **Customs & Documentation** | Import/export, paperwork | 150 | $99 |

### Others Industry Flow

When user selects "Others":
1. Jarvis asks for industry details
2. Collect: Industry name, Company Name, Company Website
3. Show generic variants or suggest based on industry input

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Day 33 | Initial plan (too broad) |
| 1.1 | Day 33 | Focused to Week 6 only (F-028 to F-035) |
| 1.2 | Day 34 | Added database status (what exists/missing) |
| 2.0 | Day 35 | Complete restructure - days ordered by actual user flow, Old Day 1-2 marked as DONE |

---

*This plan follows the CORRECTED user flow from ONBOARDING_SPEC.md v2.0*
