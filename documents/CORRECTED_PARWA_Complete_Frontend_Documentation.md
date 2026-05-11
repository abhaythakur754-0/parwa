# PARWA COMPLETE FRONTEND DOCUMENTATION

> **⚠️ CORRECTION NOTICE — This document has been corrected per the loopwholws.md decisions.**
> The following corrections were applied (Decision references in parentheses):
> - **D12:** Pricing names corrected (Mini → Starter, Junior → Growth) and prices ($1,000→$999, $2,500→$2,499, $4,000→$3,999)
> - **D13:** Cancellation & Refund Policy - Netflix style (no refunds, cancel anytime, access until month end, no free trials, payment fails = stop immediately)
> - **D1:** Stripe → Paddle for all payment references
> - **D11:** Microsoft OAuth removed (Email + Google OAuth only)
> - **D2/D3:** Supabase → PostgreSQL on GCP VM, Socket.io (not Supabase Realtime), GCP Cloud Storage
> - **D3:** Railway removed; Vercel (frontend) + GCP VM (backend)
> - **D14:** Phone number requirement added for voice demo
> - **D17:** Billing History page added to Settings
> - **D19:** Notification Preferences page added to Settings
> - **D4:** BullMQ/Bull → Celery + Redis
> - All variant names (Mini/Junior) corrected throughout

---

## Version 3.0 - Customer Journey Edition
### 271+ Components | Every Page | Every Interaction | Every UI Element

---

# OUR AGREEMENTS (From Chat Discussion)

| Topic | Decision |
|-------|----------|
| **Payment** | Paddle (NOT Stripe) |
| **LLM Providers** | OpenRouter, Google AI, Cerebras, Groq - ALL configurable |
| **Admin Flexibility** | Admin can add/remove/modify ANY provider through UI |
| **Client Integrations** | Clients can connect ANY API - not just pre-built connectors |
| **Integration Methods** | Pre-built, Custom REST API, Webhooks, MCP, GraphQL, Database |
| **Industry Themes** | E-commerce (Teal/Gold), SaaS (Navy/Silver), Logistics (Charcoal/Orange) |
| **NO HARDCODING** | Everything is configurable through UI |

---

# CUSTOMER JOURNEY OVERVIEW

## Phase 1: Discovery (Public Pages)
**Customer Experience:** Visitor lands on PARWA website → Explores features → Checks pricing → Uses ROI calculator → Tries demo → Decides to sign up

**What They See:**
- Professional landing page with industry selector
- Trust indicators (Dogfooding banner, live AI demo)
- Clear pricing with 3 variants (Starter $999, Growth $2,499, High $3,999)
- ROI calculator proving value
- Free chat demo (20 messages) or paid voice demo ($1)

## Phase 2: Signup & Activation
**Customer Experience:** Signs up → Verifies email → Selects plan → Pays via Paddle → Completes onboarding wizard → Activates AI

**What They See:**
- Simple signup form with social login options
- Email verification screen
- Paddle checkout (NOT Stripe)
- Step-by-step onboarding wizard
- First Victory Celebration when AI resolves first ticket

## Phase 3: Daily Operations
**Customer Experience:** Logs in → Sees dashboard → Reviews approvals → Interacts with Jarvis → Checks analytics → Manages settings

**What They See:**
- Dashboard with real-time activity feed
- Approval queue with batch processing
- Jarvis command interface
- Analytics and ROI tracking
- Settings for profile, team, billing, compliance

## Phase 4: Growth & Optimization
**Customer Experience:** Connects more integrations → Uploads knowledge base → Reviews performance → Upgrades tier

**What They See:**
- Integration marketplace
- Knowledge base upload interface
- Quality coaching (PARWA High)
- Performance reports
- Upgrade prompts and ROI projections

---

# SECTION A: PUBLIC PAGES (Before Login)

## A1. LANDING PAGE (/)

### Customer Perspective
When a visitor arrives at parwa.ai, they immediately see a clean, professional landing page. The hero section presents the value proposition clearly. They can select their industry (E-commerce, SaaS, or Logistics) which changes the color theme and messaging. A gold banner at the top shows "Our support is powered by PARWA AI" - a trust signal. A live chat widget in the bottom-right corner lets them interact with the actual AI they would be using.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| A1.1 | Hero Section | Main headline with value proposition | Headline text (H1), Sub-headline paragraph, Industry selector buttons (3), Primary CTA "Get Started", Secondary CTA "Watch Demo" |
| A1.2 | Industry Selector | E-commerce / SaaS / Logistics buttons | 3 large tappable buttons with icons, Hover descriptions, Industry-specific color themes (Teal, Navy, Charcoal) |
| A1.3 | Dogfooding Banner | Trust indicator at top of page | Gold (#FFD700) banner bar, "Our support is powered by PARWA AI" text, Link to open demo widget |
| A1.4 | Features Section | Product capabilities showcase | 4 feature cards: GSD Engine, Agent Lightning, Jarvis OS, Safety-First; Each with icon, title, description |
| A1.5 | Live AI Demo Widget | Floating chat to try AI | Bottom-right chat bubble (clickable), Welcome message "Hi! I'm PARWA...", Chat input field, Message bubbles, Send button, Close button |
| A1.6 | Navigation Bar | Top navigation | PARWA logo (left), Features link, Pricing link, ROI Calculator link, Login button (secondary), Signup button (primary) |
| A1.7 | Footer | Bottom section with links | Product links column, Company links column, Legal links (Privacy, Terms), Social media icons, Copyright text, Newsletter signup |

### File Structure
```
frontend/src/app/page.tsx
frontend/src/components/landing/
├── HeroSection.tsx
├── IndustrySelector.tsx
├── DogfoodingBanner.tsx
├── FeaturesSection.tsx
├── LiveDemoWidget.tsx
├── NavigationBar.tsx
└── Footer.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/demo/chat | POST | Handle demo chat messages (guest mode) |
| /api/demo/limits | GET | Check guest message count (20 limit) |

---

## A2. VARIANTS/PRICING PAGE (/pricing)

### Customer Perspective
The pricing page presents three clear options. PARWA Starter ($999/mo) on the left for basic FAQ handling. PARWA Growth ($2,499/mo) in the center with a "Recommended" badge - this is the sweet spot. PARWA High ($3,999/mo) on the right for enterprises needing quality coaching. Each card shows key features, and clicking "See Details" opens a modal with full comparison. The Smart Bundle Visualizer helps customers choose based on ticket volume.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| A2.1 | Page Header | Pricing headline section | Title "Simple, Transparent Pricing", Subtitle explaining value |
| A2.2 | PARWA Starter Card | Left pricing card | Variant name "PARWA Starter", Price "$999/mo", Feature list (5 items), "See Details" link, "Get Started" CTA button |
| A2.3 | PARWA Growth Card | Center pricing card (highlighted) | Variant name "PARWA Growth", Price "$2,499/mo", "Recommended" badge, Feature list (8 items), "See Details" link, "Get Started" CTA button |
| A2.4 | PARWA High Card | Right pricing card | Variant name "PARWA High", Price "$3,999/mo", Feature list (12 items), "See Details" link, "Get Started" CTA button |
| A2.5 | Variant Detail Modal | Popup with full comparison | Full feature comparison table, What AI does section, Hidden cost breakdown, Anti-arbitrage matrix |
| A2.6 | Smart Bundle Visualizer | Interactive tier recommender | Ticket volume slider (50-1000), Recommended tier display, Monthly cost calculation, "Why this tier?" explanation |
| A2.7 | Anti-Arbitrage Matrix | Hidden cost comparison | Starter vs PARWA comparison table, Manager time tax row, "Why PARWA is better" section, ROI calculation |

### File Structure
```
frontend/src/app/pricing/page.tsx
frontend/src/components/variants/
├── ParwaStarterCard.tsx
├── ParwaGrowthCard.tsx
├── ParwaHighCard.tsx
├── VariantDetailModal.tsx
├── SmartBundleVisualizer.tsx
└── AntiArbitrageMatrix.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/pricing/calculate | POST | Calculate recommended tier based on inputs |
| /api/pricing/compare | GET | Get feature comparison data |

---

## A3. ROI CALCULATOR PAGE (/calculator)

### Customer Perspective
The ROI calculator is the key conversion tool. Customers input their current situation: monthly labor cost, daily ticket volume, and time distribution across task types. The calculator then shows immediate value projection. An anti-arbitrage alert appears if they're considering the wrong tier. Results include labor cost saved, manager time saved, ROI percentage, and net profit projection.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| A3.1 | Page Header | Calculator headline | Title "Calculate Your ROI", Subtitle "See how much PARWA can save you" |
| A3.2 | Input Section | Data collection form | Monthly labor cost input ($), Daily tickets slider, Time split sliders (FAQs, Decisions, Complex), Industry dropdown |
| A3.3 | Results Dashboard | Calculation display | Current situation panel, PARWA projected panel, Labor cost saved ($), Manager time saved (hrs), Total monthly value, ROI percentage, Net profit |
| A3.4 | Anti-Arbitrage Alert | Smart tier recommendation | Toast notification style, Tier recommendation text, "See Comparison" button, Dismiss option |
| A3.5 | CTA Section | Conversion buttons | "Get Custom Quote" button (secondary), "Start Free Trial" button (primary) |

### File Structure
```
frontend/src/app/calculator/page.tsx
frontend/src/components/calculator/
├── InputSection.tsx
├── ResultsDashboard.tsx
├── AntiArbitrageAlert.tsx
└── CTASection.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/calculator/roi | POST | Calculate ROI based on inputs |
| /api/calculator/recommend | POST | Get tier recommendation |

---

## A4. DEMO PAGE (/demo) - v6.0 NEW

### Customer Perspective
The demo page offers two experiences. The free chat demo lets visitors send up to 20 messages to the AI without creating an account. For voice demo, there's a $1 paywall (processed via Paddle one-time payment). This ensures serious leads while still providing a low-friction way to experience the product.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| A4.1 | Demo Chat Widget | Free chat interface | Chat bubbles (user/AI), Input field, Send button, Message counter "X/20 free messages", Guest mode indicator, "Sign up for unlimited" link |
| A4.2 | Voice Demo Paywall | Paid voice demo section | Phone number input (required), Price display "$1 for voice demo", "Pay & Call" button, Paddle checkout, Call status indicator, Payment confirmation |
| A4.3 | Demo Landing Page | Full demo experience wrapper | Hero section, Feature highlights grid, CTA buttons to signup |

### File Structure
```
frontend/src/app/demo/page.tsx
frontend/src/components/demo/
├── DemoChatWidget.tsx
├── VoiceDemoPaywall.tsx
└── DemoLandingPage.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/demo/chat | POST | Process demo chat message |
| /api/demo/voice/init | POST | Initialize voice demo session |
| /api/demo/voice/status | GET | Check voice demo call status |

---

# SECTION B: AUTHENTICATION PAGES

## B1. SIGNUP PAGE (/signup)

### Customer Perspective
The signup form is designed to be simple yet complete. Users provide their full name, company name, work email, password (with strength meter), and select their industry. Social login options (Google OAuth) are prominently displayed for faster signup. A "Already have an account?" link redirects to login.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| B1.1 | Signup Form | Main registration form | Full name input, Company name input, Work email input, Password input, Password strength meter (weak/medium/strong), Industry dropdown (E-commerce/SaaS/Logistics), Terms checkbox, "Create Account" button |
| B1.2 | Form Validation | Real-time validation | Field error messages (red text), Border color changes (red on error), Validation icons (checkmark/X), Email format validation, Password requirements checklist |
| B1.3 | Social Login | Alternative authentication | "Continue with Google" button, Divider "or", OAuth popup handling |
| B1.4 | Login Link | Existing account redirect | "Already have an account?" text, "Log in" link (accent color) |

### File Structure
```
frontend/src/app/(auth)/signup/page.tsx
frontend/src/components/auth/
├── SignupForm.tsx
├── FormValidation.tsx
├── SocialLogin.tsx
└── PasswordStrengthMeter.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/auth/register | POST | Create new user account |
| /api/auth/google | GET | Google OAuth callback |
| /api/auth/check-email | POST | Check if email exists |

---

## B2. LOGIN PAGE (/login)

### Customer Perspective
Returning users see a clean login form with email and password fields. A "Forgot password?" link is available for recovery. Social login options match the signup page. After successful login, users are redirected to their dashboard.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| B2.1 | Login Form | Authentication form | Email input, Password input with show/hide toggle, "Remember me" checkbox, "Sign In" button with loading state |
| B2.2 | Forgot Password Link | Password recovery | "Forgot password?" link (below password field) |
| B2.3 | Submit Button | Login action | "Sign In" button, Loading spinner on click, Disabled state during processing |
| B2.4 | Social Login | Alternative authentication | "Continue with Google" button |
| B2.5 | Signup Link | New account redirect | "Don't have an account?" text, "Sign up" link (accent color) |

### File Structure
```
frontend/src/app/(auth)/login/page.tsx
frontend/src/components/auth/LoginForm.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/auth/login | POST | Authenticate user |
| /api/auth/me | GET | Get current user session |

---

## B3. FORGOT PASSWORD PAGE (/forgot-password)

### Customer Perspective
Users who forgot their password enter their email address. Upon submission, they see a success message telling them to check their inbox. A resend link is available if the email doesn't arrive.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| B3.1 | Email Input | Email entry | Email input field with @ icon, Placeholder "Enter your email" |
| B3.2 | Submit Button | Send reset link | "Send Reset Link" button, Loading state |
| B3.3 | Success Message | Confirmation | "Check your email" message, Email sent confirmation, "Resend link" button, Countdown timer (60s) |

### File Structure
```
frontend/src/app/(auth)/forgot-password/page.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/auth/forgot-password | POST | Send password reset email |
| /api/auth/resend-reset | POST | Resend reset email |

---

## B4. RESET PASSWORD PAGE (/reset-password)

### Customer Perspective
Users arrive here from the reset email link. They see fields for new password and confirm password. A strength meter shows password quality. After successful reset, they're redirected to login.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| B4.1 | Password Inputs | New password entry | New password input, Confirm password input, Show/hide toggles, Strength meter |
| B4.2 | Submit Button | Reset action | "Reset Password" button, Loading state |
| B4.3 | Success Message | Confirmation | "Password updated successfully" message, Redirect to login link, Auto-redirect countdown (3s) |

### File Structure
```
frontend/src/app/(auth)/reset-password/page.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/auth/reset-password | POST | Reset password with token |

---

## B5. MFA SETUP PAGE (/two-factor) - v6.0 NEW

### Customer Perspective
For security-conscious users, MFA setup displays a QR code to scan with an authenticator app. Users enter a 6-digit code to verify setup. Backup codes are generated for account recovery.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| B5.1 | QR Code Display | Authenticator setup | Large QR code image, Manual code display (copyable), "Scan with Google Authenticator" instruction |
| B5.2 | Verification Input | Code entry | 6-digit code input (separate boxes), Verify button, Error message on invalid code |
| B5.3 | Backup Codes | Recovery codes | Grid of 8 backup codes, "Download codes" button, "Print codes" button, "I've saved these codes" checkbox |

### File Structure
```
frontend/src/app/(auth)/two-factor/page.tsx
frontend/src/components/auth/MFASetup.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/auth/mfa/setup | POST | Initialize MFA setup |
| /api/auth/mfa/verify | POST | Verify MFA code |
| /api/auth/mfa/backup-codes | GET | Generate backup codes |

---

## B6. EMAIL VERIFICATION PAGE (/verify-email)

### Customer Perspective
After signup, users see a pending verification screen. They can resend the verification email or continue once verified. The page auto-refreshes to check verification status.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| B6.1 | Verification Status | Status display | "Verify your email" heading, Pending spinner, "Check your inbox" message, Resend button, "Continue" button (disabled until verified) |

### File Structure
```
frontend/src/app/(auth)/verify-email/page.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/auth/verify-email | POST | Verify email with token |
| /api/auth/resend-verification | POST | Resend verification email |

---

# SECTION C: PAYMENT & ONBOARDING

## C1. PAYMENT PAGE (/checkout)

### Customer Perspective
Users select their plan and proceed to checkout. The Paddle checkout (NOT Stripe) handles payment processing. Order summary shows the selected plan, billing cycle, and total. After successful payment, users are redirected to onboarding.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| C1.1 | Plan Summary | Selected plan display | Plan name (Starter/Growth/High), Price, Billing cycle (monthly), Feature list |
| C1.2 | Paddle Checkout | Payment form | Paddle-hosted checkout overlay, Card input, Billing information, Coupon/promo code field, Country selection for tax |
| C1.3 | Order Summary | Final details | Subtotal, Tax (if applicable), Total amount, Terms of service checkbox |
| C1.4 | Payment Processing | Loading state | Spinner, "Processing your payment..." text, Progress indicator |
| C1.5 | Payment Confirmation | Success screen | "Payment successful!" message, Order ID, "Continue to Setup" button |

### File Structure
```
frontend/src/app/checkout/page.tsx
frontend/src/components/checkout/
├── PlanSummary.tsx
├── PaddleCheckout.tsx
├── OrderSummary.tsx
└── PaymentConfirmation.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/checkout/session | POST | Create checkout session |
| /api/webhooks/paddle | POST | Handle Paddle webhooks |
| /api/checkout/verify | GET | Verify payment status |

### API Keys Required
| Provider | Key Type | Environment Variable |
|----------|----------|---------------------|
| Paddle | Client Token | PADDLE_CLIENT_TOKEN |
| Paddle | API Key | PADDLE_API_KEY |
| Paddle | Webhook Secret | PADDLE_WEBHOOK_SECRET |

---

## C2. ONBOARDING WIZARD (/onboarding)

### Customer Perspective
The onboarding wizard guides new users through setup in 5 steps: Welcome → Legal Compliance → Integration Setup → Knowledge Upload → Activation. Progress indicator shows current step. Users can skip optional steps. Voice activation ("PARWA, go live") triggers AI activation. A "First Victory Celebration" appears when AI resolves its first ticket.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| C2.1 | Welcome Screen | Introduction | Company name pre-filled (editable), Industry confirmation, "Welcome to PARWA" message, "Let's get started" button |
| C2.2 | Legal Compliance | Consent forms | TCPA consent checkbox with disclosure, GDPR consent checkbox, Call recording disclosure, Mode selection (Shadow/Supervised), "I agree" button |
| C2.3 | Integration Setup | Connect tools | Integration type selector, Big logo buttons (Shopify, GitHub, TMS, etc.), "Connect" buttons for each, "Skip for now" link, Custom API builder button |
| C2.4 | Custom Integration Builder | Any API connector | Integration name input, Type dropdown (REST/GraphQL/Webhook/Database), Base URL input, Auth type selector (API Key/Bearer/OAuth/Basic), Credentials fields, Test connection button |
| C2.5 | Knowledge Upload | Document upload | Drag-drop zone, Supported formats display (.pdf, .docx, .txt, .md), Upload progress bars, File list with delete buttons, Camera upload button (mobile only) |
| C2.6 | Progress Indicator | Step tracker | Step dots (5), Current step highlight, Progress bar percentage, Step labels |
| C2.7 | Voice Activation | Optional trigger | Microphone icon, "Say 'PARWA, go live' to activate" text, Audio waveform visualization, Activation status |
| C2.8 | Activation Button | Final setup | "Activate Automation" button with glow animation, Confirmation modal, Success confetti |

### File Structure
```
frontend/src/app/onboarding/page.tsx
frontend/src/components/onboarding/
├── WelcomeScreen.tsx
├── LegalCompliance.tsx
├── IntegrationSetup.tsx
├── CustomIntegrationBuilder.tsx
├── KnowledgeUpload.tsx
├── ProgressIndicator.tsx
├── VoiceActivation.tsx
└── ActivationButton.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/onboarding/start | POST | Initialize onboarding session |
| /api/onboarding/consent | POST | Save legal consents |
| /api/integrations | POST | Create integration |
| /api/integrations/:id/test | POST | Test integration connection |
| /api/knowledge/upload | POST | Upload knowledge documents |
| /api/onboarding/activate | POST | Activate AI system |

---

# SECTION D: CLIENT DASHBOARD

## D1. DASHBOARD HOME (/dashboard)

### Customer Perspective
After login, users land on the main dashboard. The header shows their company name, current system mode badge (Shadow/Supervised/Graduated), notification bell, and user avatar menu. Key metrics are displayed prominently. Activity feed shows real-time AI actions. Special celebratory UI appears for first victory. Growth nudges alert when usage approaches limits.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D1.1 | Header | Top navigation bar | Company logo/name, System mode badge (Shadow/Supervised/Graduated), Notification bell with badge count, User avatar dropdown (Profile, Settings, Logout) |
| D1.2 | First Victory Celebration | Onboarding milestone | Confetti animation, "Your AI just resolved its first ticket!" message, Ticket details card, Animated savings counter, ROI projection tooltip |
| D1.3 | Adaptation Tracker | Learning progress | "Day X / 30" progress bar, Weekly wins banner, Milestone indicators (checkmarks), "View learning log" link |
| D1.4 | Activity Feed | Real-time updates | Activity cards (ticket resolved, approval requested, etc.), Filter buttons (All, Approvals, Resolved), Auto-refresh indicator, Expand/collapse toggles, Timestamp display |
| D1.5 | Metrics Overview | Key numbers | Tickets handled (count + trend), Resolution rate (%), Average response time, Trend indicators (up/down arrows) |
| D1.6 | Running Total Widget | Cumulative savings | Savings counter ($X,XXX), "At this rate, you'll save $X,XXX this month" message, Animated number |
| D1.7 | Workforce Allocation Map | Agent distribution | Visual map/graph of tasks per agent, Agent names, Capacity meters |
| D1.8 | Growth Nudge Alert | Usage warning | "You're growing faster than expected" banner, Current capacity indicator, "Add capacity" button, Dismiss option |
| D1.9 | Feature Discovery Teaser | Upgrade prompt | Time savings calculator, "Unlock with PARWA High" text, Upgrade button |
| D1.10 | Seasonal Spike Forecast | Volume prediction | Expected volume display (based on historical data), "Prepare for X% increase" message, Recommendation buttons |
| D1.11 | Contextual Help System | Help widget | Persistent [?] button (bottom-right), Hover text, GIF demo popup, AI trainer chat option |

### File Structure
```
frontend/src/app/dashboard/page.tsx
frontend/src/components/dashboard/
├── Header.tsx
├── FirstVictoryCelebration.tsx
├── AdaptationTracker.tsx
├── ActivityFeed.tsx
├── MetricsOverview.tsx
├── RunningTotalWidget.tsx
├── WorkforceAllocationMap.tsx
├── GrowthNudgeAlert.tsx
├── FeatureDiscoveryTeaser.tsx
├── SeasonalSpikeForecast.tsx
└── ContextualHelpSystem.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/dashboard/overview | GET | Get dashboard summary |
| /api/dashboard/activity | GET | Get recent activity feed |
| /api/dashboard/metrics | GET | Get key metrics |
| /api/dashboard/first-victory | GET | Check first victory status |
| /api/dashboard/forecast | GET | Get volume forecast |

---

## D2. TICKETS PAGE (/dashboard/tickets)

### Customer Perspective
The tickets page shows all customer tickets in a filterable, sortable table. Users can search by customer name, ticket ID, or content. Clicking a ticket opens a detail modal with full conversation, AI analysis, and recommended actions. Bulk actions allow processing multiple tickets at once.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D2.1 | Ticket List | All tickets table | Table with columns (ID, Customer, Status, Channel, Created, Preview), Status badges (Open/Pending/Resolved), Sort headers, Pagination controls |
| D2.2 | Ticket Card | Individual ticket | Ticket ID link, Customer name, Status badge, Timestamp, Preview text (first 100 chars), Channel icon |
| D2.3 | Ticket Detail Modal | Full view | Full conversation thread, AI analysis section, Recommended action, Confidence score, Approve/Reject buttons, Assign dropdown |
| D2.4 | Search Bar | Find tickets | Search input, Filter chips (Status, Channel, Date range), Clear filters button |
| D2.5 | Bulk Actions | Multi-select actions | Select all checkbox, Individual checkboxes, Bulk approve button, Bulk reject button, Bulk assign dropdown |

### File Structure
```
frontend/src/app/dashboard/tickets/page.tsx
frontend/src/components/tickets/
├── TicketList.tsx
├── TicketCard.tsx
├── TicketDetailModal.tsx
├── SearchBar.tsx
└── BulkActions.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/tickets | GET | List tickets with filters |
| /api/tickets/:id | GET | Get ticket details |
| /api/tickets/:id | PUT | Update ticket |
| /api/tickets/bulk | POST | Bulk ticket actions |

---

## D3. APPROVALS PAGE (/dashboard/approvals)

### Customer Perspective
The approvals page is where managers review AI recommendations. Tickets are grouped into batches by similarity (semantic clustering). Each batch shows confidence range, risk level, and total value. Managers can approve entire batches or review individually. Swipe gestures on mobile allow quick approve/reject. Voice confirmation enables hands-free operation.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D3.1 | Batch Approval Cards | Grouped requests | Batch title (e.g., "5 address changes"), Confidence range (e.g., "92-97%"), Risk indicator (Low/Medium/High), Total amount, Ticket count, Expand arrow |
| D3.2 | Individual Ticket View | Expanded items | Checkbox, Ticket ID link, Customer info, Request summary, Amount, Confidence score, "New Type" badge (if applicable) |
| D3.3 | Action Buttons | Manager actions | "Approve Selected" button (green), "Reject Batch" button (red), "Shadow This Type" button, "Automate This Rule" button |
| D3.4 | Urgent Attention Panel | Priority items | VIP customer alerts (gold border), Legal question cards (red border), Strategic analysis cards, Quick action buttons |
| D3.5 | Confidence Score Breakdown | Detailed analysis | Pattern Match %, Policy Alignment %, Historical Success %, Risk Signals % |
| D3.6 | Auto-Handle Toggle | Automation control | "Enable Auto-Handle" toggle switch, Consecutive correct count display, Threshold setting input |
| D3.7 | Swipe Gestures (Mobile) | Touch actions | Swipe right = Approve (green animation), Swipe left = Reject (red animation), Hold = Details popup |
| D3.8 | Voice Confirmation | Hands-free | Microphone button, Voice command indicator, "Say 'Approve' or 'Reject'" text |

### File Structure
```
frontend/src/app/dashboard/approvals/page.tsx
frontend/src/components/approvals/
├── BatchApprovalCards.tsx
├── IndividualTicketView.tsx
├── ActionButtons.tsx
├── UrgentAttentionPanel.tsx
├── ConfidenceScoreBreakdown.tsx
├── AutoHandleToggle.tsx
├── SwipeGestures.tsx
└── VoiceConfirmation.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/approvals | GET | Get pending approvals |
| /api/approvals/batches | GET | Get batched approvals |
| /api/approvals/:id/approve | POST | Approve single item |
| /api/approvals/:id/reject | POST | Reject single item |
| /api/approvals/batch/:id/approve | POST | Approve entire batch |
| /api/approvals/auto-rule | POST | Create auto-handle rule |

---

## D4. JARVIS PAGE (/dashboard/jarvis)

### Customer Perspective
Jarvis is the command center for controlling the AI system. The chat panel allows natural language commands ("Pause refunds", "Show errors"). The GSD State Terminal shows real-time execution steps. Context Health Meter warns when approaching capacity. Emergency controls provide instant AI shutdown. System status shows all service health.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D4.1 | System Status Header | Overview display | Mode badge (Shadow/Supervised/Graduated), Active agents count, Uptime display, Health indicator dot |
| D4.2 | Jarvis Chat Panel | Command interface | Chat history (user commands + Jarvis responses), Input field, Send button, Quick command buttons (preset) |
| D4.3 | GSD State Terminal | Execution display | Real-time step display (animated), Status indicators (running/complete/error), Action logs (expandable), Timestamp column |
| D4.4 | Context Health Meter | Context usage | Visual bar (0-100%), Color coding (green <70%, yellow 70-90%, red >90%), "90% capacity" warning popup |
| D4.5 | System Status Panel | Health overview | All services status grid (LLM, Database, Email, SMS, etc.), Error rate, Response times |
| D4.6 | Quick Commands | Preset actions | "Pause Refunds" button, "Undo Last" button, "Show Errors" button, "Enable Auto" button, Command shortcut hints |
| D4.7 | Emergency Controls | Panic buttons | "Pause All AI Activity" button (red, prominent), Confirmation modal, Channel-specific pause toggles |
| D4.8 | Last 5 Errors Panel | Mistake display | Error cards with timestamp, Correction status, "View Details" buttons, "Train from this" button |

### File Structure
```
frontend/src/app/dashboard/jarvis/page.tsx
frontend/src/components/jarvis/
├── SystemStatusHeader.tsx
├── JarvisChatPanel.tsx
├── GSDStateTerminal.tsx
├── ContextHealthMeter.tsx
├── SystemStatusPanel.tsx
├── QuickCommands.tsx
├── EmergencyControls.tsx
└── Last5ErrorsPanel.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/jarvis/command | POST | Process Jarvis command |
| /api/jarvis/status | GET | Get system status |
| /api/jarvis/pause | POST | Pause AI system |
| /api/jarvis/undo | POST | Undo last action |
| /api/jarvis/errors | GET | Get recent errors |

---

## D5. AGENTS PAGE (/dashboard/agents)

### Customer Perspective
The agents page shows all AI agents (variants) the customer has. Each agent card displays status, capacity, and performance metrics. Users can add new agents (which increases their subscription cost). Agent details modal shows full statistics and learning progress.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D5.1 | Agent Cards | Variant display | Agent name, Status badge (Active/Training/Paused), Capacity meter (0-100%), Tasks handled count, Efficiency score |
| D5.2 | Agent Performance | Metrics | Accuracy rate (%), Confidence trend (chart), Tickets resolved (count), Average response time |
| D5.3 | Add Agent Button | Scale up | "Add Agent" button, Tier selector (Starter/Growth/High), Pricing display, Confirmation modal |
| D5.4 | Agent Details Modal | Full info | Full statistics dashboard, Recent decisions list, Learning progress chart, Configuration options |

### File Structure
```
frontend/src/app/dashboard/agents/page.tsx
frontend/src/components/agents/
├── AgentCards.tsx
├── AgentPerformance.tsx
├── AddAgentButton.tsx
└── AgentDetailsModal.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/agents | GET | List all agents |
| /api/agents/:id | GET | Get agent details |
| /api/agents | POST | Add new agent |
| /api/agents/:id/performance | GET | Get agent performance |

---

## D6. ANALYTICS PAGE (/dashboard/analytics)

### Customer Perspective
The analytics page provides comprehensive performance insights. Users select a time range and see key metrics, trend charts, ROI dashboard, and performance comparisons. Drift detection alerts when AI performance starts degrading. All data is exportable.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D6.1 | Time Range Selector | Period filter | Dropdown (Last 7 days, 30 days, 90 days, Custom), Date picker for custom range |
| D6.2 | Key Metrics Cards | Summary numbers | Tickets handled (count), Resolution rate (%), Average response time, Savings total ($) |
| D6.3 | Trend Charts | Visual graphs | Line graphs (tickets over time), Period comparison bars, Percentage change badges |
| D6.4 | ROI Dashboard | Value display | Time saved calculator (hours), Cost savings breakdown, Payback progress bar, Projected annual savings |
| D6.5 | Performance Comparison | Before/after | Metric comparison table, Improvement indicators, Highlighted gains |
| D6.6 | Confidence Trend Chart | AI performance | Trend line (confidence over time), Threshold markers, Warning zones |
| D6.7 | Drift Detection Report | Health card | "Avg Confidence: 92% → 84%" display, Trigger info, Root cause analysis, Training recommendation |

### File Structure
```
frontend/src/app/dashboard/analytics/page.tsx
frontend/src/components/analytics/
├── TimeRangeSelector.tsx
├── KeyMetricsCards.tsx
├── TrendCharts.tsx
├── ROIDashboard.tsx
├── PerformanceComparison.tsx
├── ConfidenceTrendChart.tsx
└── DriftDetectionReport.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/analytics/overview | GET | Get analytics overview |
| /api/analytics/trends | GET | Get trend data |
| /api/analytics/roi | GET | Get ROI calculations |
| /api/analytics/performance | GET | Get performance comparison |
| /api/analytics/drift | GET | Get drift detection report |
| /api/analytics/export | GET | Export analytics data |

---

## D7. KNOWLEDGE BASE PAGE (/dashboard/knowledge)

### Customer Perspective
The knowledge base page lets users upload documents that train their AI. A drag-drop zone accepts PDFs, Word docs, and text files. Progress animation shows "Teaching your AI..." during processing. Documents can be organized into categories. Camera upload is available on mobile.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D7.1 | Document Upload Zone | File upload | Drag-drop area, Supported formats display, Progress animation, "Browse files" button |
| D7.2 | Progress Seduction Animation | Upload feedback | "Teaching your AI..." text, Percentage bar, Checkmark list (Extracting, Processing, Indexing) |
| D7.3 | Document List | Uploaded files | File cards, Category tags, Last updated timestamps, Delete buttons, Re-process button |
| D7.4 | Document Preview | Content view | Side panel, Extracted text, Edit capability, Save button |
| D7.5 | Category Manager | Organization | Tag list, Filter by category dropdown, Search documents, Add category button |
| D7.6 | Camera Upload Button | Mobile capture | "Take photo" button (mobile only), Camera interface, Crop tool |

### File Structure
```
frontend/src/app/dashboard/knowledge/page.tsx
frontend/src/components/knowledge/
├── DocumentUploadZone.tsx
├── ProgressAnimation.tsx
├── DocumentList.tsx
├── DocumentPreview.tsx
├── CategoryManager.tsx
└── CameraUploadButton.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/knowledge/upload | POST | Upload document |
| /api/knowledge | GET | List documents |
| /api/knowledge/:id | GET | Get document details |
| /api/knowledge/:id | DELETE | Delete document |
| /api/knowledge/:id/reprocess | POST | Reprocess document |

---

## D8. AUDIT LOG PAGE (/dashboard/audit-log)

### Customer Perspective
The audit log provides a complete record of all actions for compliance and debugging. Users can filter by date, actor, action type, and outcome. Detail view shows full context of each action. Export options allow downloading as CSV or PDF.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| D8.1 | Filter Panel | Search controls | Date range picker, Actor dropdown (AI/Human/System), Action type dropdown, Outcome filter (Success/Failed) |
| D8.2 | Log Table | Audit entries | Timestamp column, Actor column, Action column, Details column, IP address column, Status badge |
| D8.3 | Detail View | Expanded log | Full action context, Reasoning display (for AI actions), Related ticket link, Duration |
| D8.4 | Export Buttons | Data export | "Export CSV" button, "Export PDF" button, Date range selection for export |

### File Structure
```
frontend/src/app/dashboard/audit-log/page.tsx
frontend/src/components/audit-log/
├── FilterPanel.tsx
├── LogTable.tsx
├── DetailView.tsx
└── ExportButtons.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/audit-log | GET | Get audit log entries |
| /api/audit-log/:id | GET | Get audit log detail |
| /api/audit-log/export | GET | Export audit log |

---

# SECTION E: INTEGRATIONS

## E1. INTEGRATIONS PAGE (/dashboard/settings/integrations)

### Customer Perspective
The integrations page shows all connected services in a grid layout. Each integration card shows connection status, last sync time, and quick actions. Users can add new integrations from the marketplace. Error alerts appear when integrations fail. The health monitor shows real-time status of all connections.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| E1.1 | Integration Status Grid | All connections | Connection cards with logos, Status badges (Connected/Error/Syncing), Last sync indicators, Quick action buttons |
| E1.2 | Add Integration Button | New connection | "Add Integration" button (primary), Opens integration marketplace modal |
| E1.3 | Error Alerts | Failure notices | Integration failure banner (red), Error message, Retry button, "View logs" link |
| E1.4 | Integration Health Monitor | Real-time status | Live status display, Uptime percentage, Error count, Response time |

### File Structure
```
frontend/src/app/dashboard/settings/integrations/page.tsx
frontend/src/components/integrations/
├── IntegrationStatusGrid.tsx
├── AddIntegrationButton.tsx
├── ErrorAlerts.tsx
└── IntegrationHealthMonitor.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/integrations | GET | List all integrations |
| /api/integrations/:id/health | GET | Get integration health |
| /api/integrations/:id/sync | POST | Trigger manual sync |

---

## E2. PRE-BUILT CONNECTORS

### Customer Perspective
Pre-built connectors provide one-click integration with popular platforms. Each connector has a specific setup flow - some use OAuth (Shopify, GitHub), others require API keys (WooCommerce). Permission scopes are clearly displayed before authorization.

### Component Table

| ID | Connector Name | UI Elements |
|----|----------------|-------------|
| E2.1 | Shopify | Store URL input, "Connect with Shopify" OAuth button, Permission scopes display, Webhook setup status, Test connection button, Disconnect button |
| E2.2 | WooCommerce | Store URL input, Consumer Key input, Consumer Secret input, "Connect" button, Test button |
| E2.3 | Magento | Base URL input, Access Token input, Store Code dropdown, "Connect" button |
| E2.4 | BigCommerce | "Connect with BigCommerce" OAuth button, Store selection dropdown |
| E2.5 | Amazon Seller | SP-API OAuth flow, Seller Central login popup, Authorization confirmation |
| E2.6 | eBay | OAuth 2.0 flow, eBay login popup, Authorization confirmation |
| E2.7 | Paddle (Client's Account) | "Connect with Paddle" button, Vendor ID input, API key input, Webhook config, Environment toggle (Live/Sandbox), Subscription management |
| E2.8 | PayPal | OAuth 2.0 flow, PayPal login popup, Permission confirmation |
| E2.9 | Square | OAuth flow, Square login popup, Location selection |
| E2.10 | Adyen | API key input, Merchant account input, Environment selector (Live/Test) |
| E2.11 | HubSpot | "Connect with HubSpot" OAuth button, Portal selection, Sync settings checkboxes, Field mapping interface |
| E2.12 | Salesforce | OAuth flow, Environment selector (Production/Sandbox), Object mapping interface, Sync frequency dropdown |
| E2.13 | Zendesk | Subdomain input, API token input, Ticket/user config checkboxes, "Connect" button |
| E2.14 | Intercom | OAuth flow, Workspace selection |
| E2.15 | GitHub | OAuth flow, Repository multi-select, Permission scope checkboxes, "Connect" button |
| E2.16 | GitLab | OAuth flow, Self-hosted URL option (for GitLab self-managed), Project selection |

### File Structure
```
frontend/src/components/integrations/connectors/
├── ShopifyConnector.tsx
├── WooCommerceConnector.tsx
├── MagentoConnector.tsx
├── BigCommerceConnector.tsx
├── AmazonSellerConnector.tsx
├── eBayConnector.tsx
├── PaddleConnector.tsx
├── PayPalConnector.tsx
├── SquareConnector.tsx
├── AdyenConnector.tsx
├── HubSpotConnector.tsx
├── SalesforceConnector.tsx
├── ZendeskConnector.tsx
├── IntercomConnector.tsx
├── GitHubConnector.tsx
└── GitLabConnector.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/integrations/:provider/connect | POST | Initiate OAuth flow |
| /api/integrations/:provider/callback | GET | Handle OAuth callback |
| /api/integrations/:provider/test | POST | Test connection |
| /api/webhooks/:provider | POST | Handle provider webhooks |

---

## E3. CUSTOM API INTEGRATION BUILDER

### Customer Perspective
For platforms without pre-built connectors, users can build custom integrations. They provide a name, select the integration type (REST/GraphQL/Webhook/Database), enter the base URL, configure authentication, and define endpoints. The AI context field helps PARWA understand when to use this integration.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| E3.1 | Integration Name | Label | Custom name input (e.g., "My ERP System") |
| E3.2 | Integration Type | Method selector | Dropdown: REST API, GraphQL, Webhook Receiver, Database Connection |
| E3.3 | Base URL | Endpoint root | URL input with validation, Environment variable support checkbox |
| E3.4 | Authentication | Auth config | Type dropdown (API Key, Bearer Token, Basic Auth, OAuth 2.0, Custom Headers), Credentials fields (dynamic based on type) |
| E3.5 | Endpoints Configuration | Define endpoints | Endpoint name input, HTTP method selector (GET/POST/PUT/DELETE), Path input, Headers editor (key-value), Parameters builder, Response schema editor, AI context field (when to use) |
| E3.6 | Request Mapping | Body template | JSON editor with syntax highlighting, Variable placeholders {{variable}} |
| E3.7 | Response Mapping | Parse response | Field extraction config, Data transformation rules |
| E3.8 | Error Handling | Failure rules | Retry logic config (count, delay), Fallback behavior dropdown |
| E3.9 | Test Suite | Verification | "Test Connection" button, "Test Endpoint" button, Test results display, Request/Response viewer |

### File Structure
```
frontend/src/components/integrations/
├── CustomIntegrationBuilder.tsx
├── AuthConfig.tsx
├── EndpointsConfig.tsx
├── RequestMapping.tsx
├── ResponseMapping.tsx
├── ErrorHandling.tsx
└── TestSuite.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/integrations/custom | POST | Create custom integration |
| /api/integrations/:id | PUT | Update integration |
| /api/integrations/:id/test | POST | Test integration |
| /api/integrations/:id/endpoints | POST | Add endpoint |

---

## E4. WEBHOOK INTEGRATION

### Customer Perspective
Webhook integrations allow receiving events from external systems and sending events to external systems. Incoming webhooks get a unique URL. Outgoing webhooks can be configured for specific events (ticket created, refund processed, etc.).

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| E4.1 | Incoming Webhooks | Receive events | Auto-generated URL display (copy button), Source name input, Payload format dropdown (JSON/XML/Form), Signature verification toggle, Secret key display, Event mapping editor, Transform rules |
| E4.2 | Outgoing Webhooks | Send events | Destination URL input, Event subscription checkboxes, Payload template editor, Secret key display (for signing), Retry policy config, Delivery logs table |

### File Structure
```
frontend/src/components/integrations/
├── IncomingWebhooks.tsx
├── OutgoingWebhooks.tsx
└── WebhookLogs.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/webhooks/incoming | POST | Create incoming webhook |
| /api/webhooks/incoming/:id | GET | Get webhook details |
| /api/webhooks/outgoing | POST | Create outgoing webhook |
| /api/webhooks/outgoing/:id/logs | GET | Get delivery logs |
| /api/webhooks/custom/:id | POST | Handle incoming webhook |

---

## E5. MCP INTEGRATION

### Customer Perspective
MCP (Model Context Protocol) integration allows PARWA to use external AI tools. Users provide the MCP server URL, and PARWA automatically discovers available tools. Permissions can be configured per tool.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| E5.1 | MCP Server URL | Endpoint | URL input, "Discover Tools" button |
| E5.2 | Transport Type | Protocol | Dropdown: HTTP, WebSocket, Stdio |
| E5.3 | Available Tools | Auto-discovered | Tools list with descriptions, Permission toggles per tool |
| E5.4 | Context Limits | Data exposure | Limit configuration inputs, Data type filters |

### File Structure
```
frontend/src/components/integrations/MCPIntegration.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/integrations/mcp | POST | Create MCP integration |
| /api/integrations/mcp/:id/discover | GET | Discover available tools |

---

## E6. DATABASE CONNECTION

### Customer Perspective
For direct database access, users can connect PostgreSQL, MySQL, or MongoDB databases. Connection is read-only by default for safety. Schema selection lets users choose which tables/collections PARWA can access.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| E6.1 | Database Type | Engine | Dropdown: PostgreSQL, MySQL, MongoDB |
| E6.2 | Connection String | Credentials | Host input, Port input, Database name input, User input, Password input (masked), SSL toggle |
| E6.3 | Access Mode | Permissions | Toggle: Read-only (default), Read-write |
| E6.4 | Schema Selection | Tables | Multi-select table list, Preview button, Row count display |

### File Structure
```
frontend/src/components/integrations/DatabaseConnection.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/integrations/database | POST | Create database connection |
| /api/integrations/database/:id/test | POST | Test connection |
| /api/integrations/database/:id/schema | GET | Get available tables |

---

# SECTION F: SETTINGS PAGES

## F1. PROFILE SETTINGS (/dashboard/settings/profile)

### Customer Perspective
Profile settings allow users to update their personal information. Avatar upload supports cropping. Name fields are editable. Email is read-only with a change link that triggers email verification. Phone number includes country code selector.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F1.1 | Avatar Upload | Profile image | Current avatar display, "Upload Photo" button, Crop tool modal, Remove button |
| F1.2 | Name Fields | Personal info | First name input, Last name input |
| F1.3 | Email Display | Account email | Read-only email display, "Change Email" link (triggers verification flow) |
| F1.4 | Phone Input | Contact number | Phone input with country code dropdown, SMS verification button |
| F1.5 | Timezone Selector | Time zone | Dropdown with search, Auto-detect button |
| F1.6 | Save Button | Update action | "Save Changes" button, Success toast |

### File Structure
```
frontend/src/app/dashboard/settings/profile/page.tsx
frontend/src/components/settings/
├── AvatarUpload.tsx
├── ProfileForm.tsx
└── TimezoneSelector.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/profile | GET | Get profile |
| /api/client/profile | PUT | Update profile |
| /api/client/avatar | POST | Upload avatar |

---

## F2. SECURITY SETTINGS (/dashboard/settings/security)

### Customer Perspective
Security settings provide password management, MFA setup, active session management, and API key management. Users can see all devices logged into their account and revoke access.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F2.1 | Password Change | Update password | Current password input, New password input, Strength meter, Requirements checklist, "Update Password" button |
| F2.2 | MFA Management | 2FA control | Enable/disable toggle, QR code display (for setup), Backup codes grid, "Regenerate codes" button |
| F2.3 | Active Sessions | Logged devices | Device list (browser, OS, location), Last active time, "Revoke" button per device, "Revoke all other sessions" button |
| F2.4 | API Keys | Integration keys | Key list with name and created date, "Create new key" button, Copy button, Revoke button, Last used display |

### File Structure
```
frontend/src/app/dashboard/settings/security/page.tsx
frontend/src/components/settings/
├── PasswordChange.tsx
├── MFAManagement.tsx
├── ActiveSessions.tsx
└── APIKeys.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/password | PUT | Change password |
| /api/client/mfa | POST | Enable/disable MFA |
| /api/client/sessions | GET | List active sessions |
| /api/client/sessions/:id | DELETE | Revoke session |
| /api/client/api-keys | GET | List API keys |
| /api/client/api-keys | POST | Create API key |
| /api/client/api-keys/:id | DELETE | Revoke API key |

---

## F3. BILLING SETTINGS (/dashboard/settings/billing)

### Customer Perspective
Billing settings show current plan, usage meter, and payment method. Users can upgrade/downgrade with prorated pricing shown. Invoice history allows downloading past bills. The cancellation flow is "graceful" - showing ROI summary and offering alternatives before allowing cancellation.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F3.1 | Current Plan | Subscription | Plan name card, Feature list, Usage meter, Renewal date |
| F3.2 | Usage Meter | Capacity | Visual bar (current/limit), Percentage display, "Upgrade for more capacity" link |
| F3.3 | Upgrade/Downgrade | Change plan | "Change Plan" button, Plan comparison modal, Prorated pricing display, "Confirm Change" button |
| F3.4 | Payment Method | Card info | Card display (masked number, expiry), "Update Payment Method" button, Paddle redirect |
| F3.5 | Invoice History | Past bills | Invoice table (Date, Amount, Status), Download PDF buttons, "View in Paddle" link (Paddle billing portal) |
| F3.6 | Graceful Cancellation Flow | Cancel process | "Cancel Subscription" button (small, gray), Reason checkboxes (4 options: Cost, Not using, Missing features, Other), ROI summary display, "We'll miss you" message, Training offer modal, Integrations roadmap, "Pause 30 Days" button, "Get Help" button, "Cancel Anyway" button (final, red) |

### File Structure
```
frontend/src/app/dashboard/settings/billing/page.tsx
frontend/src/components/settings/
├── CurrentPlan.tsx
├── UsageMeter.tsx
├── PlanChange.tsx
├── PaymentMethod.tsx
├── InvoiceHistory.tsx
└── CancellationFlow.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/subscription | GET | Get subscription details |
| /api/client/subscription | PUT | Change subscription |
| /api/client/subscription/cancel | POST | Cancel subscription |
| /api/client/invoices | GET | List invoices |

---

## F4. TEAM SETTINGS (/dashboard/settings/team)

### Customer Perspective
Team settings allow inviting team members with different roles (Admin, Manager, Viewer). Each member's access level is clearly displayed. Pending invitations are shown separately.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F4.1 | Team Members | User list | Member cards with avatar, Name and email, Role badge, "Edit role" button, "Remove" button |
| F4.2 | Role Assignment | Permissions | Role dropdown (Admin/Manager/Viewer), Permission checkboxes per role, "Save" button |
| F4.3 | Invite Form | Add member | Email input, Role selector, "Send Invite" button |
| F4.4 | Pending Invitations | Outstanding invites | Invitation list with email, Resend button, Cancel button |

### File Structure
```
frontend/src/app/dashboard/settings/team/page.tsx
frontend/src/components/settings/
├── TeamMembers.tsx
├── RoleAssignment.tsx
├── InviteForm.tsx
└── PendingInvitations.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/team | GET | List team members |
| /api/client/team/invite | POST | Invite member |
| /api/client/team/:id | PUT | Update member role |
| /api/client/team/:id | DELETE | Remove member |

---

## F5. POLICIES SETTINGS (/dashboard/settings/policies)

### Customer Perspective
Policies settings let users configure refund rules, approval thresholds, and VIP handling. These rules directly affect how PARWA operates. Changes are versioned and logged.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F5.1 | Refund Policy | Rules config | Policy editor (rich text), Return window input (days), Condition requirements checkboxes, Auto-approve rules toggle, Threshold amount input |
| F5.2 | Approval Thresholds | Limits | Max auto-approve amount input, Category-specific rules table, Holiday multipliers |
| F5.3 | VIP Rules | Special handling | VIP customer list (add/remove), Priority rules checkboxes, Dedicated agent toggle |

### File Structure
```
frontend/src/app/dashboard/settings/policies/page.tsx
frontend/src/components/settings/
├── RefundPolicy.tsx
├── ApprovalThresholds.tsx
└── VIPRules.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/policies | GET | Get policies |
| /api/client/policies | PUT | Update policies |
| /api/client/vip | GET | Get VIP list |
| /api/client/vip | POST | Add VIP customer |

---

## F6. COMPLIANCE SETTINGS (/dashboard/settings/compliance)

### Customer Perspective
Compliance settings show GDPR status, TCPA compliance, and sub-processor list. Users can export or delete all data for GDPR compliance. Data residency can be selected for regulatory requirements.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F6.1 | GDPR Status | Compliance display | Data retention config (days), Right-to-delete status, Consent records link |
| F6.2 | TCPA Compliance | Call recording | Disclosure text editor, Opt-out tracking display, Recording consent status |
| F6.3 | Sub-Processor List | Data processors | Dynamic list from PARWA, Location indicators, Purpose display |
| F6.4 | Export/Delete Tools | Data actions | "Export All Data" button (creates zip), "Delete All Data" button (red, requires confirmation) |

### File Structure
```
frontend/src/app/dashboard/settings/compliance/page.tsx
frontend/src/components/settings/
├── GDPRStatus.tsx
├── TCPACompliance.tsx
├── SubProcessorList.tsx
└── DataTools.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/compliance | GET | Get compliance status |
| /api/client/compliance | PUT | Update compliance settings |
| /api/client/data/export | POST | Export all data |
| /api/client/data/delete | POST | Delete all data |

---

## F7. DATA RESIDENCY (/dashboard/settings/data-residency)

### Customer Perspective
Data residency settings allow selecting where data is stored (US, EU, etc.) for regulatory compliance. Migration status shows progress if data is being moved between regions.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F7.1 | Region Selector | Data location | Region dropdown (US-East, EU-West, APAC), Compliance info per region, Pricing impact display |
| F7.2 | Migration Status | Transfer state | Progress indicator (if migrating), Estimated completion time, Migration history |

### File Structure
```
frontend/src/app/dashboard/settings/data-residency/page.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/residency | GET | Get data residency status |
| /api/client/residency | PUT | Request region change |

---

## F8. NOTIFICATION SETTINGS (/dashboard/settings/notifications)

### Customer Perspective
Notification settings control how and when users receive alerts. Email notifications can be toggled per type (approvals, errors, summaries). Push notifications work in supported browsers. Alert thresholds can be customized.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F8.1 | Email Notifications | Email prefs | Toggle switches per type (Approvals, Errors, Weekly Summary, New Features), Digest mode toggle |
| F8.2 | Push Notifications | Browser prefs | Enable/disable toggle, Permission request button, Test notification button |
| F8.3 | Alert Thresholds | Trigger levels | Threshold inputs per type (Error rate %, Response time ms, etc.), Alert frequency dropdown |

### File Structure
```
frontend/src/app/dashboard/settings/notifications/page.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/notifications | GET | Get notification settings |
| /api/client/notifications | PUT | Update settings |
| /api/client/notifications/test | POST | Send test notification |

---



---

## F9. BILLING HISTORY PAGE (/dashboard/settings/billing-history)

### Customer Perspective
The billing history page provides a detailed view of all past transactions, including monthly subscription charges, daily overage charges ($0.10/ticket), add-on charges, and refunds. Users can filter by date range and export statements as PDF or CSV. Each charge shows the breakdown of base subscription vs. overage costs.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F9.1 | Transaction Table | All charges | Date column, Description column, Amount column, Status badge (Paid/Pending/Refunded), Sort by date |
| F9.2 | Overage Breakdown | Daily charges | Daily overage amount ($0.10/ticket), Ticket count over limit, Date of charge, Subtotal |
| F9.3 | Add-on Charges | Extra services | Managed Training charges, Extra Agent charges, Voice Demo charges, SMS Pack charges |
| F9.4 | Summary Cards | Monthly totals | Current month total, Previous month total, Average monthly spend, Projected next month |
| F9.5 | Export Buttons | Download | "Export as PDF" button, "Export as CSV" button, Date range selector for export |
| F9.6 | Refund History | Refund records | Refund date, Original charge reference, Refund amount, Reason, Status |

### File Structure
```
frontend/src/app/dashboard/settings/billing-history/page.tsx
frontend/src/components/settings/
├── TransactionTable.tsx
├── OverageBreakdown.tsx
├── AddOnCharges.tsx
├── SummaryCards.tsx
├── ExportButtons.tsx
└── RefundHistory.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/billing/history | GET | Get billing history |
| /api/client/billing/overages | GET | Get overage charges |
| /api/client/billing/export | GET | Export billing data (PDF/CSV) |

---



---

## F10. NOTIFICATION PREFERENCES PAGE (/dashboard/settings/notification-preferences)

### Customer Perspective
The notification preferences page provides granular control over all notification channels and types. Users can configure email, push, and in-app notifications independently. Each notification type (approvals, errors, weekly summaries, billing alerts, new features) has individual toggle controls. Quiet hours can be set to suppress non-urgent notifications during specific times. Emergency notifications (AI pause alerts, critical errors) always bypass quiet hours.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| F10.1 | Channel Toggles | Enable/disable channels | Email notifications toggle, Push notifications toggle, In-app notifications toggle, SMS notifications toggle (for urgent alerts) |
| F10.2 | Notification Type Matrix | Per-type control | Grid with notification types (rows) × channels (columns), Individual toggles per cell, "All/None" quick buttons per row |
| F10.3 | Quiet Hours | Time-based suppression | Start time picker, End time picker, Days of week checkboxes, "Bypass for emergencies" checkbox |
| F10.4 | Digest Settings | Batched emails | Digest frequency dropdown (Instant/Daily/Weekly), Digest time picker, Included types checkboxes |
| F10.5 | Alert Priority Rules | Urgency control | Priority levels (Critical/High/Medium/Low), Channel routing per priority, Escalation rules |
| F10.6 | Test Notification | Verify setup | "Send Test Email" button, "Send Test Push" button, Last sent timestamp |

### File Structure
```
frontend/src/app/dashboard/settings/notification-preferences/page.tsx
frontend/src/components/settings/
├── ChannelToggles.tsx
├── NotificationTypeMatrix.tsx
├── QuietHours.tsx
├── DigestSettings.tsx
├── AlertPriorityRules.tsx
└── TestNotification.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/notification-preferences | GET | Get notification preferences |
| /api/client/notification-preferences | PUT | Update preferences |
| /api/client/notification-preferences/test | POST | Send test notification |

---

# SECTION G: ADMIN DASHBOARD (PARWA Team Only)

## G1. ADMIN HOME (/admin)

### Customer Perspective
PARWA admins see a dashboard with all clients, system health, and revenue metrics. Client list shows subscription tier, usage, and status. System health shows all services. Revenue dashboard tracks MRR and churn.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| G1.1 | Client List | All clients | Table with search, Status indicators (Active/Paused/Churned), Subscription tier column, Usage metrics column, Action buttons |
| G1.2 | System Health | Platform status | Service status cards (green/yellow/red), Uptime percentages, Error rates, Response times |
| G1.3 | Revenue Dashboard | Financial metrics | MRR display, Churn rate, Revenue trends chart, New signups count |

### File Structure
```
frontend/src/app/admin/page.tsx
frontend/src/components/admin/
├── ClientList.tsx
├── SystemHealth.tsx
└── RevenueDashboard.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/admin/clients | GET | List all clients |
| /api/admin/health | GET | Get system health |
| /api/admin/revenue | GET | Get revenue metrics |

---

## G2. SERVICE PROVIDER MANAGEMENT (/admin/services)

### Customer Perspective
Admins have FULL FLEXIBILITY to manage all service providers. They can add new LLM providers, payment gateways, SMS/voice providers, and email services. Each provider has detailed configuration options. Custom services can be added for any API.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| G2.1 | Provider List | All services | Provider cards with status, Service type badge, Priority order (drag to reorder), Status indicators |
| G2.2 | Add Provider Form | New service | Provider name input, Service type dropdown (LLM/Payment/SMS/Email/Custom), Base URL input, Auth type selector, Credentials fields (dynamic), Custom headers editor, Rate limit config, Priority input, Test connection button |
| G2.3 | LLM Provider Config | AI settings | API endpoint input, API key input (masked, reveal button), Model selection multi-select, Tier assignment (Light/Medium/Heavy), Cost per token input, Rate limits input, Fallback priority input, Custom parameters JSON editor |
| G2.4 | Payment Gateway Config | Payment settings | Provider selector (Paddle), Client token input, API key input, Webhook secret input, Environment toggle (Live/Test), Currencies multi-select, Product mapping editor |
| G2.5 | SMS/Voice Config | Communication | Provider card, Phone number pool editor, Usage dashboard link, Cost tracking display |
| G2.6 | Email Config | Email settings | Provider card, Template manager link, Domain config editor |
| G2.7 | Custom Service Builder | Any API | Full configuration form (same as Add Provider Form) |

### File Structure
```
frontend/src/app/admin/services/page.tsx
frontend/src/components/admin/
├── ProviderList.tsx
├── AddProviderForm.tsx
├── LLMProviderConfig.tsx
├── PaymentGatewayConfig.tsx
├── SMSVoiceConfig.tsx
├── EmailConfig.tsx
└── CustomServiceBuilder.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/admin/services | GET | List all services |
| /api/admin/services | POST | Add new service |
| /api/admin/services/:id | PUT | Update service |
| /api/admin/services/:id | DELETE | Delete service |
| /api/admin/services/:id/test | POST | Test service connection |

---

## G3. CLIENT MANAGEMENT (/admin/clients)

### Customer Perspective
Admins can view individual client details, manage subscriptions, and monitor usage. Subscription controls allow upgrades, downgrades, pauses, and cancellations.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| G3.1 | Client Detail View | Single client | Configuration display, Metrics dashboard, Subscription management section, Recent activity |
| G3.2 | Subscription Controls | Plan changes | Upgrade/downgrade buttons, Pause/resume buttons, Cancel button (with confirmation), Refund options |
| G3.3 | Usage Monitoring | Capacity | Capacity utilization chart, Growth trends, Alert thresholds, "Approaching limit" warnings |

### File Structure
```
frontend/src/app/admin/clients/[id]/page.tsx
frontend/src/components/admin/
├── ClientDetailView.tsx
├── SubscriptionControls.tsx
└── UsageMonitoring.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/admin/clients/:id | GET | Get client details |
| /api/admin/clients/:id | PUT | Update client |
| /api/admin/clients/:id/subscription | PUT | Change subscription |
| /api/admin/clients/:id/usage | GET | Get usage data |

---

## G4. SYSTEM MONITORING (/admin/monitoring)

### Customer Perspective
System monitoring provides real-time visibility into all services. API performance metrics help identify bottlenecks. Cost tracking shows per-provider expenses with optimization recommendations.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| G4.1 | Service Status Dashboard | Health overview | All services with status indicators, Real-time updates, Historical uptime chart |
| G4.2 | API Performance | Response metrics | Response times chart, Error rates chart, Rate limit status per provider |
| G4.3 | Cost Tracking | Provider costs | Per-provider costs table, Optimization recommendations, Budget vs actual chart |
| G4.4 | Incident Management | Issues | Alert config editor, Escalation rules editor, Incident log table |

### File Structure
```
frontend/src/app/admin/monitoring/page.tsx
frontend/src/components/admin/
├── ServiceStatusDashboard.tsx
├── APIPerformance.tsx
├── CostTracking.tsx
└── IncidentManagement.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/admin/monitoring/status | GET | Get service status |
| /api/admin/monitoring/performance | GET | Get performance metrics |
| /api/admin/monitoring/costs | GET | Get cost tracking |
| /api/admin/incidents | GET | List incidents |

---

# SECTION H: QUALITY & PERFORMANCE MONITORS

## H1. QUALITY COACH DASHBOARD (PARWA High Only)

### Customer Perspective
PARWA High clients have access to the Quality Coach. Quality score cards show accuracy, empathy, and efficiency per conversation. Trend charts track improvement over time. Training recommendations suggest specific actions.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| H1.1 | Quality Score Cards | Per conversation | Accuracy score (0-100), Empathy score (0-100), Efficiency score (0-100), Overall rating |
| H1.2 | Trend Charts | Over time | Score trends line chart, Improvement indicators, Benchmark comparison |
| H1.3 | Training Recommendations | Suggestions | Priority list (high/medium/low), Action items with checkboxes, "Mark as done" buttons |
| H1.4 | Quality Alerts | Notifications | Alert cards with severity, Escalate button, Snooze button, Dismiss button |

### File Structure
```
frontend/src/components/quality/
├── QualityScoreCards.tsx
├── TrendCharts.tsx
├── TrainingRecommendations.tsx
└── QualityAlerts.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/quality/scores | GET | Get quality scores |
| /api/quality/trends | GET | Get quality trends |
| /api/quality/recommendations | GET | Get training recommendations |

---

## H2. PERFORMANCE TRACKING

### Customer Perspective
Performance tracking provides weekly summaries, performance reviews, and adaptive thresholds. The system automatically adjusts based on historical performance.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| H2.1 | Weekly Summary Email | Reports | Email preview, Subscription toggle, Delivery time config |
| H2.2 | Performance Review Dashboard | Trends | Weekly reports grid, Accuracy trends chart, Time saved metrics |
| H2.3 | Adaptive Thresholds UI | Dynamic rules | Threshold changes display, Performance triggers config, Override toggles |

### File Structure
```
frontend/src/components/performance/
├── WeeklySummary.tsx
├── PerformanceReviewDashboard.tsx
└── AdaptiveThresholds.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/performance/weekly | GET | Get weekly summary |
| /api/performance/review | GET | Get performance review |
| /api/performance/thresholds | GET | Get adaptive thresholds |

---

## H3. PEER REVIEW INTERFACE

### Customer Perspective
PARWA Starter agents can request help from PARWA High agents (peer review). The interface shows help requests and allows senior agents to provide guidance.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| H3.1 | Help Request Card | From Starter | Requesting agent name, Issue summary, Context preview, "Accept Help Request" button |
| H3.2 | Response Form | From PARWA High | Reasoning input (textarea), Suggestion input (textarea), Reference docs link, "Send Response" button |

### File Structure
```
frontend/src/components/peer-review/
├── HelpRequestCard.tsx
└── ResponseForm.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/peer-review/requests | GET | Get help requests |
| /api/peer-review/respond | POST | Submit response |

---

# SECTION I: EMERGENCY & SAFETY CONTROLS

## I1. EMERGENCY CONTROLS PANEL

### Customer Perspective
Emergency controls provide immediate shutdown capability. The panic button stops all AI activity. Channel-specific pauses allow selective control. Emergency override routes all tickets to humans.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| I1.1 | Panic Button | Emergency stop | "Pause All AI Activity" button (large, red, prominent), Confirmation modal with countdown, Resume button (when paused) |
| I1.2 | Channel Pause | Selective stop | Channel toggles (Email, Chat, SMS, Voice), Individual status indicators, Pause reason input |
| I1.3 | Emergency Override | Crisis mode | Override button, Alert routing config, Human escalation toggle |

### File Structure
```
frontend/src/components/emergency/
├── PanicButton.tsx
├── ChannelPause.tsx
└── EmergencyOverride.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/emergency/pause | POST | Pause all activity |
| /api/emergency/channel | POST | Pause specific channel |
| /api/emergency/override | POST | Enable emergency override |

---

## I2. NON-FINANCIAL UNDO

### Customer Perspective
Non-financial undo allows recalling emails and voiding actions. This doesn't work for financial transactions (refunds) which require reversal flows.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| I2.1 | Recall Emails | Email undo | Email list with status, "Recall" button per email, Time limit display (30s window) |
| I2.2 | Void Last Action | Generic undo | "Void Last Action" button, Confirmation modal, Action details display |

### File Structure
```
frontend/src/components/emergency/
├── RecallEmails.tsx
└── VoidLastAction.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/undo/email | POST | Recall email |
| /api/undo/action | POST | Void last action |

---

## I3. RATE LIMITING DISPLAY

### Customer Perspective
Rate limiting display shows DDoS protection status and blocked requests. This helps users understand when their system is under attack or experiencing unusual traffic.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| I3.1 | DDoS Shield Status | Protection | Active/inactive indicator, Blocked requests count, Traffic chart, Whitelist editor |

### File Structure
```
frontend/src/components/emergency/DDoSShieldStatus.tsx
```

### Backend APIs Needed
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/security/shield | GET | Get shield status |
| /api/security/whitelist | PUT | Update whitelist |

---

# SECTION J: MOBILE-SPECIFIC UI

## J1. MOBILE LAYOUT ELEMENTS

### Customer Perspective
Mobile UI is optimized for touch and small screens. Stacked cards replace side-by-side layouts. Bottom navigation provides quick access. Full-width modals maximize screen real estate. CTAs are placed in thumb-friendly zones.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| J1.1 | Stacked Cards | Card layout | Full-width cards, Carousel swipe for comparisons, Card shadows |
| J1.2 | Bottom Navigation | Mobile nav | Nav bar with 5 icons (Home, Approvals, Jarvis, Analytics, More), Active indicator dot, Labels on active |
| J1.3 | Full-width Modals | Modal display | Max-width modals (100%), Swipe down to dismiss, Header with close button |
| J1.4 | Thumb-Zone CTA | Button placement | Primary buttons in bottom 40% of screen, Floating action button (FAB) for main actions |
| J1.5 | Pull-to-Refresh | Update gesture | Pull indicator, Refresh animation, Last updated timestamp |

### File Structure
```
frontend/src/components/mobile/
├── StackedCards.tsx
├── BottomNavigation.tsx
├── FullWidthModal.tsx
├── ThumbZoneCTA.tsx
└── PullToRefresh.tsx
```

---

## J2. TOUCH GESTURES

### Customer Perspective
Touch gestures enable efficient mobile operation. Swipe right approves, swipe left rejects. Long press shows details. Haptic feedback confirms actions.

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| J2.1 | Swipe Right | Approve | Gesture area (full card), Green checkmark animation, Confirmation toast |
| J2.2 | Swipe Left | Reject | Gesture area (full card), Red X animation, Reason selector popup |
| J2.3 | Hold | Details | Long-press detection (500ms), Detail popup modal, Quick action buttons |
| J2.4 | Haptic Feedback | Vibration | Vibration on actions (useHaptic hook), Intensity config |

### File Structure
```
frontend/src/hooks/useHaptic.ts
frontend/src/components/mobile/
├── SwipeGesture.tsx
└── LongPressHandler.tsx
```

---

# SECTION K: COMMON UI COMPONENTS (Reusable)

## K1. BUTTONS

### Component Table

| ID | Component Name | Description | Props/States |
|----|----------------|-------------|--------------|
| K1.1 | Primary Button | Main CTA | Industry accent color, white text, 8px radius, hover darker, active press state |
| K1.2 | Secondary Button | Alternative action | Transparent background, accent border, accent text, hover fill |
| K1.3 | Danger Button | Destructive action | Red (#EF4444), white text, confirmation required |
| K1.4 | Icon Button | Compact action | 40x40px circle, icon centered, tooltip on hover, disabled state |
| K1.5 | Loading Button | Processing state | Spinner icon, disabled, "Processing..." text optional |
| K1.6 | Disabled Button | Unavailable | Grayed out (#9CA3AF), no pointer events, tooltip explains why |

### File Structure
```
frontend/src/components/ui/
├── Button.tsx
├── IconButton.tsx
└── LoadingButton.tsx
```

---

## K2. FORM INPUTS

### Component Table

| ID | Component Name | Description | Props/States |
|----|----------------|-------------|--------------|
| K2.1 | Text Input | Basic text | Border, radius, focus state (accent), error state (red), placeholder, helper text |
| K2.2 | Password Input | Secure entry | Show/hide toggle, strength meter, requirements checklist |
| K2.3 | Select/Dropdown | Single/multi | Search input, multi-select tags, selected indicator, group support |
| K2.4 | Toggle/Switch | Boolean | 48x24px, accent when on, smooth animation, label |
| K2.5 | Checkbox | Multi-option | 20x20px, accent when checked, label, indeterminate state |
| K2.6 | Radio Button | Single option | Group with labels, selected indicator, disabled state |
| K2.7 | Textarea | Multi-line | Auto-resize option, character count, max length |
| K2.8 | Date Picker | Date selection | Calendar popup, range selection, time support |
| K2.9 | File Upload | File handling | Drag-drop zone, progress bar, file list, accept filter |

### File Structure
```
frontend/src/components/ui/
├── Input.tsx
├── PasswordInput.tsx
├── Select.tsx
├── Toggle.tsx
├── Checkbox.tsx
├── Radio.tsx
├── Textarea.tsx
├── DatePicker.tsx
└── FileUpload.tsx
```

---

## K3. NOTIFICATIONS

### Component Table

| ID | Component Name | Description | Props/States |
|----|----------------|-------------|--------------|
| K3.1 | Toast | Quick feedback | Top-right position, auto-dismiss 5s, success/error/warning/info variants, close button |
| K3.2 | Alert Banner | Page-level | Top of page, requires dismissal, icon + message + action button |
| K3.3 | Modal | Blocking overlay | Centered, backdrop click dismissible option, close button, action buttons |

### File Structure
```
frontend/src/components/ui/
├── Toast.tsx
├── AlertBanner.tsx
└── Modal.tsx
```

---

## K4. BADGES & INDICATORS

### Component Table

| ID | Component Name | Description | Props/States |
|----|----------------|-------------|--------------|
| K4.1 | Status Badge | State indicator | Active (green #22C55E), Warning (yellow #EAB308), Error (red #EF4444), Neutral (gray #6B7280) |
| K4.2 | Confidence Score Badge | AI confidence | Color-coded by % (high >90% green, medium 70-90% yellow, low <70% red) |
| K4.3 | Mode Indicator | System mode | Shadow/Supervised/Graduated with icons, color coding |
| K4.4 | Provider Status | Integration status | Active/Inactive/Error/Rate Limited with colors |

### File Structure
```
frontend/src/components/ui/
├── Badge.tsx
├── ConfidenceBadge.tsx
├── ModeIndicator.tsx
└── ProviderStatus.tsx
```

---

## K5. DATA DISPLAY

### Component Table

| ID | Component Name | Description | Props/States |
|----|----------------|-------------|--------------|
| K5.1 | Table | Data grid | Sortable columns, paginated, row actions, responsive scroll |
| K5.2 | Card | Content container | Title, content area, actions footer, status badge |
| K5.3 | List | Virtualized list | Infinite scroll, virtualization for performance, loading placeholders |
| K5.4 | Progress Bar | Completion | Filled percentage, label, animated |
| K5.5 | Skeleton | Loading placeholder | Pulse animation, matches content shape |
| K5.6 | Empty State | No data | Illustration, message, CTA button |

### File Structure
```
frontend/src/components/ui/
├── Table.tsx
├── Card.tsx
├── List.tsx
├── ProgressBar.tsx
├── Skeleton.tsx
└── EmptyState.tsx
```

---

## K6. NAVIGATION

### Component Table

| ID | Component Name | Description | Props/States |
|----|----------------|-------------|--------------|
| K6.1 | Sidebar | Main navigation | Collapsible, section headers, active indicator, nested items |
| K6.2 | Breadcrumb | Path display | Clickable links, current page indicator |
| K6.3 | Tabs | Content switching | Tab list, active indicator, panel content |
| K6.4 | Pagination | Page navigation | Page numbers, prev/next, items per page |
| K6.5 | Command Palette | Quick actions | Keyboard shortcut (Cmd+K), search, quick actions list |

### File Structure
```
frontend/src/components/ui/
├── Sidebar.tsx
├── Breadcrumb.tsx
├── Tabs.tsx
├── Pagination.tsx
└── CommandPalette.tsx
```

---

# SECTION L: INDUSTRY-SPECIFIC COMPONENTS

## L1. E-COMMERCE MODULE

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| L1.1 | Cart Recovery Widget | Abandoned cart alerts | Alert cards with cart value, Recovery action buttons, Email preview |
| L1.2 | Inventory Monitor | Stock alerts | Low stock indicators, Sync status, Reorder recommendations |
| L1.3 | Revenue Analytics | Sales charts | Daily/weekly/monthly revenue, Conversion rates, Top products |
| L1.4 | E-commerce Settings Page | Store configuration | Store connection status, Product sync settings, Return policy editor |

### File Structure
```
frontend/src/components/industry/ecommerce/
├── CartRecoveryWidget.tsx
├── InventoryMonitor.tsx
├── RevenueAnalytics.tsx
└── EcommerceSettingsPage.tsx
```

---

## L2. SAAS MODULE

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| L2.1 | Bug Tracker | Issue cards | Issue cards with severity, Priority badges, Status workflow |
| L2.2 | Deployment Timeline | Release tracking | Timeline view, Status indicators, Rollback button |
| L2.3 | SaaS Settings Page | API configuration | API key management, Webhook config, Feature flags |

### File Structure
```
frontend/src/components/industry/saas/
├── BugTracker.tsx
├── DeploymentTimeline.tsx
└── SaaSSettingsPage.tsx
```

---

## L3. LOGISTICS MODULE

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| L3.1 | GPS Tracking Widget | Live map | Live map with driver locations, ETA display, Route lines |
| L3.2 | Delivery Status Board | Shipment cards | Shipment cards with status, ETA countdown, Delay alerts |
| L3.3 | Router Analytics | Route metrics | Route optimization score, Fuel savings, Time metrics |
| L3.4 | Logistics Settings Page | Carrier config | Carrier connections, TMS integration, Service area config |

### File Structure
```
frontend/src/components/industry/logistics/
├── GPSTrackingWidget.tsx
├── DeliveryStatusBoard.tsx
├── RouterAnalytics.tsx
└── LogisticsSettingsPage.tsx
```

---

# SECTION M: PWA & OFFLINE FEATURES

## M1. PROGRESSIVE WEB APP

### Component Table

| ID | Component Name | Description | Implementation |
|----|----------------|-------------|----------------|
| M1.1 | manifest.json | PWA config | App name, icons, theme color, start URL |
| M1.2 | Service Worker | Offline support | Cache strategies, background sync |
| M1.3 | Offline Queue | Action queue | IndexedDB storage, sync on reconnect |

### File Structure
```
frontend/public/manifest.json
frontend/public/service-worker.js
frontend/src/lib/offlineQueue.ts
```

---

## M2. OFFLINE INDICATORS

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| M2.1 | Connection Status | Online/offline | Badge in header, Color coding (green/gray) |
| M2.2 | Sync Pending | Queued actions | Count badge, "X actions pending sync" message |
| M2.3 | Retry Button | Manual sync | "Retry Sync" button, Progress indicator |

### File Structure
```
frontend/src/components/pwa/
├── ConnectionStatus.tsx
├── SyncPending.tsx
└── RetryButton.tsx
```

---

# SECTION N: DARK MODE

## N1. DARK MODE COMPONENTS

### Component Table

| ID | Component Name | Description | UI Elements |
|----|----------------|-------------|-------------|
| N1.1 | Theme Toggle | Light/dark/auto | Toggle switch with sun/moon icons, Auto option |
| N1.2 | Dark Color Scheme | Inverted colors | Background: #0F172A, Text: #F1F5F9, Accent: #0EA5E9 |
| N1.3 | Dark Mode Charts | Reversed colors | Chart color scheme adapts to dark background |

### File Structure
```
frontend/src/components/ui/ThemeToggle.tsx
frontend/src/styles/darkMode.ts
```

---

# SECTION O: ACCESSIBILITY (A11Y)

## O1. A11Y COMPONENTS

### Component Table

| ID | Component Name | Description | Implementation |
|----|----------------|-------------|----------------|
| O1.1 | Aria Labels | Screen reader | aria-label on all interactive elements, aria-describedby for help |
| O1.2 | Focus Indicators | Keyboard nav | Visible focus rings (2px accent outline), Focus trap in modals |
| O1.3 | Screen Reader Support | Semantic HTML | Proper heading hierarchy, role attributes, live regions |
| O1.4 | Keyboard Navigation | Tab order | Logical tab order, Skip links, Keyboard shortcuts |
| O1.5 | High Contrast Mode | Enhanced visibility | Increased contrast ratios, Bold text option |

### File Structure
```
frontend/src/styles/accessibility.css
frontend/src/hooks/useA11y.ts
```

---

# SUMMARY COUNT

| Category | Component Count |
|----------|-----------------|
| Section A: Public Pages | 23 |
| Section B: Authentication | 18 |
| Section C: Payment & Onboarding | 24 |
| Section D: Client Dashboard | 52 |
| Section E: Integrations | 35 |
| Section F: Settings | 40 |
| Section G: Admin Dashboard | 18 |
| Section H: Quality & Performance | 12 |
| Section I: Emergency Controls | 8 |
| Section J: Mobile UI | 12 |
| Section K: Common Components | 35 |
| Section L: Industry Modules | 12 |
| Section M: PWA & Offline | 6 |
| Section N: Dark Mode | 3 |
| Section O: Accessibility | 5 |
| **TOTAL** | **283+** |

---

# COMPLETE FILE STRUCTURE

```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx                          # Landing Page
│   │   ├── pricing/page.tsx                  # Pricing Page
│   │   ├── calculator/page.tsx               # ROI Calculator
│   │   ├── demo/page.tsx                     # Demo Page
│   │   ├── checkout/page.tsx                 # Payment Checkout
│   │   ├── onboarding/page.tsx               # Onboarding Wizard
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   ├── signup/page.tsx
│   │   │   ├── forgot-password/page.tsx
│   │   │   ├── reset-password/page.tsx
│   │   │   ├── verify-email/page.tsx
│   │   │   └── two-factor/page.tsx
│   │   └── dashboard/
│   │       ├── layout.tsx                    # Dashboard Layout
│   │       ├── page.tsx                      # Dashboard Home
│   │       ├── tickets/page.tsx
│   │       ├── approvals/page.tsx
│   │       ├── jarvis/page.tsx
│   │       ├── agents/page.tsx
│   │       ├── analytics/page.tsx
│   │       ├── knowledge/page.tsx
│   │       ├── audit-log/page.tsx
│   │       └── settings/
│   │           ├── profile/page.tsx
│   │           ├── security/page.tsx
│   │           ├── billing/page.tsx
│   │           ├── team/page.tsx
│   │           ├── policies/page.tsx
│   │           ├── compliance/page.tsx
│   │           ├── notifications/page.tsx
│   │           ├── integrations/page.tsx
│   │           └── data-residency/page.tsx
│   ├── components/
│   │   ├── ui/                               # Reusable UI Components
│   │   ├── common/                           # Header, Footer, Loading, etc.
│   │   ├── landing/                          # Landing Page Components
│   │   ├── variants/                         # Pricing Cards
│   │   ├── auth/                             # Authentication Components
│   │   ├── checkout/                         # Payment Components
│   │   ├── onboarding/                       # Onboarding Components
│   │   ├── dashboard/                        # Dashboard Components
│   │   ├── tickets/                          # Ticket Components
│   │   ├── approvals/                        # Approval Components
│   │   ├── jarvis/                           # Jarvis Components
│   │   ├── agents/                           # Agent Components
│   │   ├── analytics/                        # Analytics Components
│   │   ├── knowledge/                        # Knowledge Base Components
│   │   ├── audit-log/                        # Audit Log Components
│   │   ├── integrations/                     # Integration Components
│   │   ├── settings/                         # Settings Components
│   │   ├── admin/                            # Admin Components
│   │   ├── quality/                          # Quality Components
│   │   ├── emergency/                        # Emergency Components
│   │   ├── mobile/                           # Mobile Components
│   │   ├── industry/                         # Industry-specific Components
│   │   ├── pwa/                              # PWA Components
│   │   └── help/                             # Help Components
│   ├── hooks/                                # Custom React Hooks
│   ├── stores/                               # State Management (Zustand)
│   ├── services/                             # API Services
│   ├── lib/                                  # Utility Functions
│   ├── data/                                 # Static Data
│   └── styles/                               # Global Styles
├── public/
│   ├── manifest.json                         # PWA Manifest
│   ├── service-worker.js                     # Service Worker
│   └── help-gifs/                            # Help GIF Animations
└── next.config.js                            # Next.js Config
```

---

# BACKEND API ENDPOINTS (Complete List)

## Authentication APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/auth/register | POST | Create new user |
| /api/auth/login | POST | Authenticate user |
| /api/auth/logout | POST | End session |
| /api/auth/forgot-password | POST | Send reset email |
| /api/auth/reset-password | POST | Reset with token |
| /api/auth/verify-email | POST | Verify email |
| /api/auth/resend-verification | POST | Resend verification |
| /api/auth/me | GET | Get current user |
| /api/auth/mfa/setup | POST | Setup MFA |
| /api/auth/mfa/verify | POST | Verify MFA code |
| /api/auth/google | GET | Google OAuth |

## Client APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/client/profile | GET | Get profile |
| /api/client/profile | PUT | Update profile |
| /api/client/avatar | POST | Upload avatar |
| /api/client/password | PUT | Change password |
| /api/client/mfa | POST | Toggle MFA |
| /api/client/sessions | GET | List sessions |
| /api/client/sessions/:id | DELETE | Revoke session |
| /api/client/api-keys | GET/POST/DELETE | Manage API keys |
| /api/client/subscription | GET/PUT | Manage subscription |
| /api/client/invoices | GET | List invoices |
| /api/client/team | GET | List team |
| /api/client/team/invite | POST | Invite member |
| /api/client/team/:id | PUT/DELETE | Manage member |
| /api/client/policies | GET/PUT | Manage policies |
| /api/client/compliance | GET/PUT | Manage compliance |
| /api/client/notifications | GET/PUT | Manage notifications |

## Dashboard APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/dashboard/overview | GET | Dashboard summary |
| /api/dashboard/activity | GET | Activity feed |
| /api/dashboard/metrics | GET | Key metrics |
| /api/dashboard/first-victory | GET | First victory status |
| /api/dashboard/forecast | GET | Volume forecast |

## Ticket APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/tickets | GET | List tickets |
| /api/tickets/:id | GET | Get ticket |
| /api/tickets/:id | PUT | Update ticket |
| /api/tickets/bulk | POST | Bulk actions |

## Approval APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/approvals | GET | List approvals |
| /api/approvals/batches | GET | Get batches |
| /api/approvals/:id/approve | POST | Approve |
| /api/approvals/:id/reject | POST | Reject |
| /api/approvals/batch/:id/approve | POST | Approve batch |
| /api/approvals/auto-rule | POST | Create auto rule |

## Jarvis APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/jarvis/command | POST | Execute command |
| /api/jarvis/status | GET | System status |
| /api/jarvis/pause | POST | Pause AI |
| /api/jarvis/undo | POST | Undo action |
| /api/jarvis/errors | GET | Recent errors |

## Agent APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/agents | GET | List agents |
| /api/agents | POST | Add agent |
| /api/agents/:id | GET | Get agent |
| /api/agents/:id/performance | GET | Performance |

## Analytics APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/analytics/overview | GET | Overview |
| /api/analytics/trends | GET | Trend data |
| /api/analytics/roi | GET | ROI data |
| /api/analytics/performance | GET | Performance |
| /api/analytics/drift | GET | Drift report |
| /api/analytics/export | GET | Export data |

## Knowledge APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/knowledge | GET | List documents |
| /api/knowledge/upload | POST | Upload document |
| /api/knowledge/:id | GET | Get document |
| /api/knowledge/:id | DELETE | Delete document |
| /api/knowledge/:id/reprocess | POST | Reprocess |

## Audit Log APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/audit-log | GET | List entries |
| /api/audit-log/:id | GET | Get detail |
| /api/audit-log/export | GET | Export |

## Integration APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/integrations | GET | List all |
| /api/integrations | POST | Create |
| /api/integrations/:id | PUT | Update |
| /api/integrations/:id | DELETE | Delete |
| /api/integrations/:id/test | POST | Test connection |
| /api/integrations/:id/health | GET | Health status |
| /api/integrations/:provider/connect | POST | OAuth connect |
| /api/integrations/:provider/callback | GET | OAuth callback |
| /api/integrations/custom | POST | Create custom |
| /api/integrations/mcp | POST | Create MCP |
| /api/integrations/database | POST | Create DB connection |

## Webhook APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/webhooks/shopify | POST | Shopify webhook |
| /api/webhooks/twilio | POST | Twilio webhook |
| /api/webhooks/paddle | POST | Paddle webhook |
| /api/webhooks/custom/:id | POST | Custom webhook |

## Admin APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/admin/clients | GET | List clients |
| /api/admin/clients/:id | GET | Get client |
| /api/admin/clients/:id | PUT | Update client |
| /api/admin/clients/:id/subscription | PUT | Change subscription |
| /api/admin/services | GET | List services |
| /api/admin/services | POST | Add service |
| /api/admin/services/:id | PUT | Update service |
| /api/admin/services/:id | DELETE | Delete service |
| /api/admin/health | GET | System health |
| /api/admin/monitoring/status | GET | Service status |
| /api/admin/monitoring/performance | GET | Performance |
| /api/admin/monitoring/costs | GET | Cost tracking |
| /api/admin/incidents | GET | List incidents |

## Demo APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/demo/chat | POST | Demo chat |
| /api/demo/voice/init | POST | Init voice demo |
| /api/demo/voice/status | GET | Call status |

## Emergency APIs
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/emergency/pause | POST | Pause all |
| /api/emergency/channel | POST | Pause channel |
| /api/emergency/override | POST | Emergency override |
| /api/undo/email | POST | Recall email |
| /api/undo/action | POST | Void action |
| /api/security/shield | GET | Shield status |

---

# API KEYS (All Configurable via Admin UI)

## LLM Providers
| Provider | Key Type | Purpose | Configurable |
|----------|----------|---------|--------------|
| OpenRouter | API Key | Multi-model access | Yes |
| Google AI | API Key | Gemini models | Yes |
| Cerebras | API Key | Fast inference | Yes |
| Groq | API Key | Fast inference | Yes |
| LiteLLM | API Key | Unified proxy | Yes |

## Payment Providers
| Provider | Key Type | Purpose | Configurable |
|----------|----------|---------|--------------|
| Paddle | Client Token | Checkout | Yes |
| Paddle | API Key | Management | Yes |
| Paddle | Webhook Secret | Verification | Yes |

## Communication Providers
| Provider | Key Type | Purpose | Configurable |
|----------|----------|---------|--------------|
| Twilio | Account SID | SMS/Voice | Yes |
| Twilio | Auth Token | Authentication | Yes |
| Twilio | API Key | Programmable | Yes |
| Brevo | API Key | Email sending | Yes |

## Version Control
| Provider | Key Type | Purpose | Configurable |
|----------|----------|---------|--------------|
| GitHub | Personal Access Token | Repository access | Yes |

## Database
| Service | Key Type | Purpose | Configurable |
|---------|----------|---------|--------------|
| PostgreSQL | Connection String | Database | Yes |

## Hosting
| Service | Key Type | Purpose | Configurable |
|---------|----------|---------|--------------|
| Vercel | API Token | Frontend deployment | Yes |
| GCP Compute Engine | Service Account Key | Backend hosting | Yes |

---

# INDUSTRY THEMES

## E-commerce Theme
- **Primary Color:** Teal (#0D9488)
- **Accent Color:** Gold (#F59E0B)
- **Background:** Off-white (#FAFAFA)

## SaaS Theme
- **Primary Color:** Navy (#1E3A5F)
- **Accent Color:** Silver (#94A3B8)
- **Background:** Light gray (#F8FAFC)

## Logistics Theme
- **Primary Color:** Charcoal (#374151)
- **Accent Color:** Orange (#F97316)
- **Background:** Warm gray (#F5F5F4)

---

# NOTES FOR BACKEND DEVELOPMENT

1. **Authentication:** Use NextAuth.js with multiple providers (credentials, Google OAuth)

2. **Database:** PostgreSQL on GCP VM (self-hosted) with application-level row-level security via middleware

3. **Real-time:** Socket.io for live updates (activity feed, Jarvis)

4. **File Storage:** GCP Cloud Storage for knowledge documents

5. **Queue System:** Celery + Redis for background jobs (training, sync)

6. **Caching:** Redis for session cache and API response caching

7. **Webhooks:** Dedicated endpoints per provider with signature verification

8. **Rate Limiting:** Implement per-endpoint and per-user rate limits

9. **Audit Logging:** Log all actions with actor, action, details, IP

10. **GDPR Compliance:** Implement data export and deletion endpoints

---

END OF DOCUMENT
