# PARWA Onboarding System Specification

> **Document Version:** 1.0  
> **Last Updated:** Day 33 (Week 5)  
> **Status:** Planning Phase - Subject to Changes

---

## Table of Contents

1. [Overview](#1-overview)
2. [User Journey Map](#2-user-journey-map)
3. [Free vs Protected Features](#3-free-vs-protected-features)
4. [Jarvis AI Assistant Experience](#4-jarvis-ai-assistant-experience)
5. [Demo Chat Flow](#5-demo-chat-flow)
6. [Demo Call Flow](#6-demo-call-flow)
7. [Subscription Flow](#7-subscription-flow)
8. [Post-Payment Details Collection](#8-post-payment-details-collection)
9. [Onboarding Wizard](#9-onboarding-wizard)
10. [Frontend Requirements](#10-frontend-requirements)
11. [Backend Requirements](#11-backend-requirements)
12. [Database Schema Changes](#12-database-schema-changes)
13. [API Endpoints](#13-api-endpoints)
14. [Third-Party Integrations](#14-third-party-integrations)
15. [Implementation Phases](#15-implementation-phases)

---

## 1. Overview

### 1.1 Purpose

The onboarding system is the FIRST touchpoint for potential customers. It must:
- Showcase PARWA's AI capabilities immediately
- Create a memorable, futuristic experience
- Convert visitors into paying customers
- Collect necessary business information after payment

### 1.2 Core Philosophy

> **"Show, Don't Tell"** - Users experience the product quality during demo itself.

The entire demo experience is powered by **Jarvis**, an AI assistant that represents what customers will get after subscription.

### 1.3 Key Differentiator

Unlike traditional SaaS onboarding:
- No static forms
- Conversational interface throughout
- AI-powered interactions from first contact
- "Jarvis" personality creates emotional connection

---

## 2. User Journey Map

### 2.1 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PARWA USER JOURNEY                                   │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐
                    │  LANDING PAGE   │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │  Browse   │      │   View    │      │    ROI    │
   │  Website  │      │   Plans   │      │ Calculator│
   │  (FREE)   │      │  (FREE)   │      │   (FREE)  │
   └───────────┘      └───────────┘      └───────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │ Try Demo │      │ Book Demo │      │ Subscribe │
   │   Chat   │      │   Call    │      │           │
   └─────┬─────┘      └─────┬─────┘      └─────┬─────┘
         │                  │                  │
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │   SIGNUP OR   │
                    │    LOGIN      │
                    └───────┬───────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
   ┌───────────┐      ┌───────────┐      ┌───────────┐
   │   Demo    │      │   Demo    │      │   Plan    │
   │   Chat    │      │   Call    │      │ Selection │
   │ (FREE)    │      │  ($1/3min)│      │           │
   └───────────┘      └───────────┘      └─────┬─────┘
                                               │
                                               ▼
                                       ┌───────────────┐
                                       │    PADDLE     │
                                       │   CHECKOUT    │
                                       └───────┬───────┘
                                               │
                                               ▼
                                       ┌───────────────┐
                                       │   PAYMENT     │
                                       │   SUCCESS     │
                                       └───────┬───────┘
                                               │
                                               ▼
                                       ┌───────────────┐
                                       │   COLLECT     │
                                       │   DETAILS     │
                                       │ (Name,Company,│
                                       │ Industry)     │
                                       └───────┬───────┘
                                               │
                                               ▼
                                       ┌───────────────┐
                                       │  ONBOARDING   │
                                       │   WIZARD      │
                                       └───────┬───────┘
                                               │
                                               ▼
                                       ┌───────────────┐
                                       │  DASHBOARD    │
                                       └───────────────┘
```

### 2.2 Decision Points

| Decision Point | User Action | System Response |
|----------------|-------------|-----------------|
| Landing Page | Browse only | No signup required |
| Landing Page | Click demo/subscribe | Redirect to Signup/Login |
| Signup Page | New user | Create account (email/password or Gmail) |
| Login Page | Existing user | Authenticate, check subscription |
| After Demo | Interested | CTA to View Plans |
| After Payment | Success | Collect details → Onboarding |

---

## 3. Free vs Protected Features

### 3.1 Feature Access Matrix

| Feature | Signup Required? | Cost | Notes |
|---------|------------------|------|-------|
| Browse Website | ❌ No | FREE | All pages accessible |
| View Plans Page | ❌ No | FREE | Pricing displayed |
| ROI Calculator | ❌ No | FREE | Interactive calculator |
| Watch Demo Video | ❌ No | FREE | Embedded video |
| Demo Chat | ✅ Yes | FREE | Limited conversations |
| Demo Call | ✅ Yes | $1 | 3 minutes via Paddle |
| Full Subscription | ✅ Yes | Plan Price | Based on selected tier |

### 3.2 Rationale

**Why Some Features are FREE:**
- Reduces friction for initial engagement
- Allows users to evaluate value proposition
- Creates trust before asking for commitment
- SEO benefits (more indexed content)

**Why Demo Requires Signup:**
- Captures lead information
- Prevents abuse of AI resources
- Enables follow-up marketing
- Creates accountability

---

## 4. Jarvis AI Assistant Experience

### 4.1 What is Jarvis?

Jarvis is PARWA's AI assistant persona that:
- Powers all demo interactions
- Represents the product quality users will get
- Creates a memorable, futuristic experience
- Acts as the "face" of PARWA AI

### 4.2 Jarvis Personality

**Character Traits:**
- Professional yet friendly
- Intelligent and helpful
- Slightly futuristic (like Iron Man's Jarvis)
- Proactive in offering assistance
- Clear and concise in communication

**Sample Interactions:**

```
User: Hi
Jarvis: Hello! I'm Jarvis, your AI assistant from PARWA. 
       I'm here to help you experience what our AI can do 
       for your business. Would you like to try a demo chat 
       or book a demo call?

User: I want to know about pricing
Jarvis: Great question! Our plans start from $49/month for 
       the Starter tier. We have three plans designed for 
       different business sizes. Would you like me to show 
       you a detailed comparison, or would you prefer to 
       experience a demo first?

User: I'll try the demo chat
Jarvis: Excellent choice! Let's start. You can ask me 
       anything about customer support, and I'll show you 
       how I handle real customer queries. What would you 
       like to know?
```

### 4.3 Visual Representation

**Chat Interface:**
```
┌─────────────────────────────────────────────────────────┐
│  🤖 Jarvis                                    [-] [X]   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────┐       │
│  │ 🤖 Jarvis                                    │       │
│  │ Hello! I'm Jarvis, your AI assistant...     │       │
│  └─────────────────────────────────────────────┘       │
│                                                         │
│                        ┌───────────────────────────┐   │
│                        │ 👤 You                    │   │
│                        │ I want to try demo chat   │   │
│                        └───────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────┐       │
│  │ 🤖 Jarvis                                    │       │
│  │ Excellent choice! Let's begin...            │       │
│  └─────────────────────────────────────────────┘       │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [Type your message here...]              [Send] 📤    │
└─────────────────────────────────────────────────────────┘
```

**Visual Elements:**
- 🤖 Robot emoji as Jarvis avatar (universal, clean)
- Different bubble colors for Jarvis vs User
- Typing indicator when Jarvis is "thinking"
- Smooth animations for messages

### 4.4 AI Provider Configuration

| Environment | AI Provider | Configuration |
|-------------|-------------|---------------|
| Development | z-ai-web-dev-sdk | Default setup |
| Production | OpenAI / Anthropic / Gemini | Environment-based config |

**System Prompt:**
```
You are Jarvis, a sophisticated AI assistant for PARWA, 
an AI-powered customer support platform. Your personality:
- Professional, intelligent, and helpful
- Slightly futuristic and impressive
- Proactive in guiding users
- Clear and concise in responses

Your goals:
1. Help users experience PARWA's AI capabilities
2. Guide them through demo chat and demo call booking
3. Answer questions about features and pricing
4. Encourage users to subscribe to full access

Always maintain the Jarvis persona. Be helpful but not pushy.
```

---

## 5. Demo Chat Flow

### 5.1 Flow Diagram

```
┌─────────────────┐
│ User clicks     │
│ "Try Demo Chat" │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Check if       │     │  Create Guest   │
│  Signed Up?     │────►│  Session        │
└────────┬────────┘     └────────┬────────┘
         │                       │
         │ YES                   │ NO (Prompt Signup)
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌─────────────────────┐
         │  JARVIS CHAT UI     │
         │  OPENS              │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Free Limited Chat  │
         │  (5-10 messages)    │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Limit Reached      │
         │  CTA: Subscribe     │
         └─────────────────────┘
```

### 5.2 Detailed Steps

**Step 1: User Initiates Demo**
- User clicks "Try Demo Chat" button
- System checks authentication status
- If not authenticated, prompt Signup/Login
- If authenticated, open Jarvis chat interface

**Step 2: Chat Experience**
- Jarvis welcomes user
- User can ask any questions
- Jarvis demonstrates AI capabilities
- Limited to X messages per session (configurable)

**Step 3: Limit Reached**
- After limit, show CTA
- "You've experienced our AI! Ready for full access?"
- Button: "View Plans"

### 5.3 Technical Requirements

**Frontend:**
- Chat UI component (React)
- WebSocket connection for real-time messages
- Message history display
- Typing indicator animation
- Mobile responsive design

**Backend:**
- WebSocket endpoint for chat
- AI integration (configurable provider)
- Rate limiting per user
- Session management
- Message logging for analytics

### 5.4 Conversation Limits

| User Type | Message Limit | Reset Period |
|-----------|---------------|--------------|
| New Signup | 10 messages | Per day |
| Returning Demo User | 5 messages | Per day |
| Paid Subscriber | Unlimited | N/A |

---

## 6. Demo Call Flow

### 6.1 Flow Diagram

```
┌─────────────────┐
│ User clicks     │
│ "Book Demo Call"│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Check if       │
│  Signed Up?     │
└────────┬────────┘
         │
         │ YES (via Jarvis Chat)
         ▼
┌─────────────────────────────────────────────────────────┐
│              JARVIS CONVERSATIONAL FLOW                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🤖 Jarvis: Great! I'll set up a demo call.            │
│            What's your phone number?                    │
│                                                         │
│  👤 User: +91 98765 43210                               │
│                                                         │
│  🤖 Jarvis: Perfect! I've sent an OTP to your number.  │
│            Please enter the 4-digit code.               │
│                                                         │
│  👤 User: 4281                                          │
│                                                         │
│  🤖 Jarvis: ✅ Verified! To confirm your demo call,     │
│            there's a $1 fee for 3 minutes.              │
│            [Pay $1 with Paddle]                         │
│                                                         │
│  👤 User: [Clicks Pay]                                  │
│                                                         │
│  🤖 Jarvis: Payment successful! 🎉                      │
│            I'm initiating your call now...              │
│            📞 Calling +91 98765 43210...                │
│                                                         │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  ACTUAL CALL    │
│  (3 minutes)    │
│  AI Voice Call  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  🤖 Jarvis: Your demo call has ended! 🎉               │
│            Ready to get full access for your business?  │
│            [View Plans] [Share Feedback]                │
└─────────────────────────────────────────────────────────┘
```

### 6.2 Detailed Steps

**Step 1: Phone Number Collection**
- Jarvis asks for phone number in chat
- Validate phone format
- Support international numbers

**Step 2: OTP Verification**
- Send OTP via SMS (Twilio Verify)
- 4-digit code, 5-minute expiry
- Resend option available
- Max 3 attempts

**Step 3: Payment**
- Display: "$1 for 3-minute demo call"
- Paddle checkout (embedded or redirect)
- Handle payment success/failure

**Step 4: Call Initiation**
- Use Twilio to make outbound call
- AI voice agent handles conversation
- 3-minute timer
- End with CTA in voice

**Step 5: Post-Call**
- Update chat with call status
- Show CTA for subscription
- Log call details for analytics

### 6.3 Call Script (AI Voice)

```
[Call Connected]

"Hello! This is Jarvis from PARWA. Thank you for 
scheduling this demo call. I'm excited to show you 
how our AI can transform your customer support.

[1 minute: Introduction and capabilities overview]

Let me demonstrate how I handle a typical customer 
query... [Simulate customer interaction]

[1 minute: Demo scenario]

[Final 30 seconds]

You've just experienced a glimpse of what PARWA can 
do for your business. To get full access with 
unlimited AI support, visit our website and choose 
a plan that fits your needs. Thank you for your time, 
and have a wonderful day!"

[Call Ends]
```

### 6.4 Technical Requirements

**Frontend:**
- Jarvis chat interface (shared with demo chat)
- Phone number input validation
- OTP input field
- Paddle payment integration
- Call status display

**Backend:**
- OTP generation and verification (Twilio)
- Payment processing (Paddle webhook)
- Call initiation (Twilio Voice API)
- Call status tracking
- Call duration monitoring

---

## 7. Subscription Flow

### 7.1 Flow Diagram

```
┌─────────────────┐
│ User clicks     │
│ "Subscribe"     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Check if       │
│  Signed Up?     │
└────────┬────────┘
         │
         │ YES
         ▼
┌─────────────────┐
│  PLAN SELECTION │
│  ┌───────────┐  │
│  │ Starter   │  │
│  │ $49/mo    │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │ Growth    │  │
│  │ $149/mo   │  │
│  └───────────┘  │
│  ┌───────────┐  │
│  │ Enterprise│  │
│  │ Custom    │  │
│  └───────────┘  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PADDLE         │
│  CHECKOUT       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Payment        │
│  Success/Fail   │
└────────┬────────┘
         │ SUCCESS
         ▼
┌─────────────────┐
│  Redirect to    │
│  Details Form   │
└─────────────────┘
```

### 7.2 Plan Details (To Be Finalized)

| Plan | Price | Features | Limits |
|------|-------|----------|--------|
| Starter | $49/mo | Basic AI chat, Email support | 1000 tickets/mo |
| Growth | $149/mo | Advanced AI, Voice, Priority support | 5000 tickets/mo |
| Enterprise | Custom | Full features, Dedicated support | Unlimited |

---

## 8. Post-Payment Details Collection

### 8.1 Overview

After successful payment, collect business details that were NOT collected during signup.

### 8.2 Information to Collect

| Field | Required | Validation | Notes |
|-------|----------|------------|-------|
| Full Name | ✅ Yes | Min 2 chars | Account owner name |
| Company Name | ✅ Yes | Min 2 chars | Business name |
| Work Email | ✅ Yes | Valid email | For business communications |
| Industry | ✅ Yes | Dropdown | For AI customization |
| Company Size | ⬜ Optional | Dropdown | For analytics |
| Website | ⬜ Optional | Valid URL | For company context |

### 8.3 Flow

```
┌─────────────────────────────────────────────────────────┐
│           WELCOME TO PARWA! 🎉                          │
│                                                         │
│  Your payment was successful. Let's complete your      │
│  profile to personalize your experience.               │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Full Name                                        │   │
│  │ [_______________________________]                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Company Name                                     │   │
│  │ [_______________________________]                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Work Email (for business communications)        │   │
│  │ [_______________________________]                │   │
│  │ [Send Verification]                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Industry                                         │   │
│  │ [Select Industry ▼]                              │   │
│  │   - E-commerce                                   │   │
│  │   - SaaS                                         │   │
│  │   - Healthcare                                   │   │
│  │   - Finance                                      │   │
│  │   - Education                                    │   │
│  │   - Other                                        │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│                    [Continue to Setup →]               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 8.4 Work Email Verification

**Why Separate Verification:**
- Initial signup may use personal email
- Work email is for business communications
- Can be same as signup email (auto-verified)

**Flow:**
1. User enters work email
2. If same as signup email → Auto-verified
3. If different → Send verification link
4. User clicks link → Verified
5. Continue to onboarding

---

## 9. Onboarding Wizard

### 9.1 Overview

5-step wizard to get users to their "First Victory" - a working AI support system.

### 9.2 Wizard Steps

**Step 1: Welcome & Overview**
```
┌─────────────────────────────────────────────────────────┐
│  Welcome to PARWA! 🚀                                   │
│                                                         │
│  You're just 5 steps away from AI-powered support!     │
│                                                         │
│  Here's what we'll set up:                              │
│  ✓ Legal agreements                                     │
│  ✓ Your integrations                                    │
│  ✓ Knowledge base                                       │
│  ✓ AI personality                                       │
│  ✓ Your first test ticket                               │
│                                                         │
│  Estimated time: 10 minutes                             │
│                                                         │
│              [Let's Get Started →]                      │
└─────────────────────────────────────────────────────────┘
```

**Step 2: Legal Consent**
```
┌─────────────────────────────────────────────────────────┐
│  Step 2 of 5: Legal Agreements                          │
│                                                         │
│  Please review and accept:                              │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ☐ I accept the Terms of Service                 │   │
│  │    [Read Terms]                                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ☐ I accept the Privacy Policy                   │   │
│  │    [Read Policy]                                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ☐ I accept the AI Data Processing Agreement     │   │
│  │    [Read Agreement]                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│              [← Back]    [Continue →]                   │
└─────────────────────────────────────────────────────────┘
```

**Step 3: Integrations**
```
┌─────────────────────────────────────────────────────────┐
│  Step 3 of 5: Connect Your Channels                     │
│                                                         │
│  Choose how customers will reach you:                   │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   📧 Email  │  │   💬 Chat   │  │   📱 WhatsApp│    │
│  │   [Setup]   │  │   [Setup]   │  │   [Setup]   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ 📞 Voice    │  │ 📘 Facebook │  │ 📸 Instagram │    │
│  │   [Setup]   │  │   [Setup]   │  │   [Setup]   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│  💡 You can skip this and set up later                  │
│                                                         │
│              [← Back]    [Skip] [Continue →]            │
└─────────────────────────────────────────────────────────┘
```

**Step 4: Knowledge Base**
```
┌─────────────────────────────────────────────────────────┐
│  Step 4 of 5: Train Your AI                             │
│                                                         │
│  Upload documents to train your AI assistant:           │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │         📁 Drag & Drop Files Here               │   │
│  │                                                 │   │
│  │    Supported: PDF, DOCX, TXT, CSV              │   │
│  │    Max: 10MB per file                          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Or add content manually:                               │
│  [+ Add FAQ] [+ Add Product Info] [+ Add Policy]       │
│                                                         │
│  Uploaded Files:                                        │
│  📄 product_manual.pdf (2.3 MB) [Remove]               │
│  📄 faq.docx (156 KB) [Remove]                          │
│                                                         │
│              [← Back]    [Skip] [Continue →]            │
└─────────────────────────────────────────────────────────┘
```

**Step 5: AI Personality**
```
┌─────────────────────────────────────────────────────────┐
│  Step 5 of 5: Customize Your AI                         │
│                                                         │
│  Choose your AI assistant's personality:                │
│                                                         │
│  Name your AI:                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Jarvis                                           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Tone:                                                  │
│  ○ Professional    ○ Friendly    ○ Casual              │
│                                                         │
│  Response Style:                                        │
│  ○ Concise    ○ Detailed                               │
│                                                         │
│  Greeting Message:                                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Hello! How can I help you today?                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│              [← Back]           [Complete Setup →]      │
└─────────────────────────────────────────────────────────┘
```

**Step 6: First Victory**
```
┌─────────────────────────────────────────────────────────┐
│  🎉 Congratulations! Your AI is Ready!                  │
│                                                         │
│  Let's test it with your first ticket:                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Test Ticket                                      │   │
│  │ Customer: "What are your business hours?"       │   │
│  │                                                 │   │
│  │ AI Response:                                     │   │
│  │ "Hello! Our business hours are Monday to        │   │
│  │  Friday, 9 AM to 6 PM EST. How else can I      │   │
│  │  help you today?"                               │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ✅ Your AI is working!                                 │
│                                                         │
│              [Go to Dashboard →]                        │
└─────────────────────────────────────────────────────────┘
```

---

## 10. Frontend Requirements

### 10.1 Pages Required

| Page | Route | Description |
|------|-------|-------------|
| Landing Page | `/` | Main marketing page |
| Plans Page | `/plans` | Pricing display |
| ROI Calculator | `/roi` | Interactive calculator |
| Signup Page | `/signup` | New user registration |
| Login Page | `/login` | User authentication |
| Demo Chat | `/demo/chat` | Jarvis chat interface |
| Demo Call | `/demo/call` | Call booking flow |
| Plan Selection | `/subscribe` | Choose plan |
| Post-Payment | `/welcome/details` | Collect business info |
| Onboarding | `/onboarding` | 5-step wizard |
| Dashboard | `/dashboard` | Main app (after onboarding) |

### 10.2 Components Required

**Chat Components:**
- `JarvisChat` - Main chat interface
- `ChatMessage` - Individual message bubble
- `ChatInput` - Message input with send button
- `TypingIndicator` - Animated typing dots

**Form Components:**
- `PhoneInput` - International phone number input
- `OTPInput` - 4-digit OTP input
- `IndustrySelect` - Dropdown for industries
- `FileUpload` - Drag & drop file upload

**Wizard Components:**
- `OnboardingWizard` - Main wizard container
- `WizardStep` - Individual step component
- `ProgressBar` - Step progress indicator
- `IntegrationCard` - Integration setup card

### 10.3 UI/UX Requirements

**Design Principles:**
- Modern, clean aesthetic
- Consistent with landing page design
- Mobile-first responsive design
- Dark mode support (optional)

**Animations:**
- Smooth page transitions
- Chat message animations (slide in)
- Typing indicator animation
- Progress bar animation

---

## 11. Backend Requirements

### 11.1 Services Required

| Service | Purpose |
|---------|---------|
| `JarvisService` | Handle AI conversations |
| `DemoService` | Manage demo sessions |
| `OTPService` | Generate and verify OTPs |
| `CallService` | Initiate and manage calls |
| `OnboardingService` | Handle onboarding flow |
| `DetailsService` | Collect user details |

### 11.2 Background Tasks

| Task | Schedule | Purpose |
|------|----------|---------|
| Demo session cleanup | Hourly | Remove expired sessions |
| Call status check | Real-time | Monitor active calls |
| Onboarding reminders | Daily | Email users who didn't complete |

---

## 12. Database Schema Changes

### 12.1 New Tables

**demo_sessions**
```sql
CREATE TABLE demo_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_type VARCHAR(20) CHECK (session_type IN ('chat', 'call')),
    status VARCHAR(20) DEFAULT 'active',
    message_count INTEGER DEFAULT 0,
    message_limit INTEGER DEFAULT 10,
    phone_number VARCHAR(20),
    otp_code VARCHAR(6),
    otp_verified BOOLEAN DEFAULT FALSE,
    payment_id VARCHAR(100),
    call_sid VARCHAR(100),
    call_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);
```

**demo_messages**
```sql
CREATE TABLE demo_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES demo_sessions(id),
    role VARCHAR(20) CHECK (role IN ('user', 'assistant')),
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**user_details**
```sql
CREATE TABLE user_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) UNIQUE,
    full_name VARCHAR(100),
    company_name VARCHAR(100),
    work_email VARCHAR(255),
    work_email_verified BOOLEAN DEFAULT FALSE,
    industry VARCHAR(50),
    company_size VARCHAR(20),
    website VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**onboarding_state**
```sql
CREATE TABLE onboarding_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) UNIQUE,
    current_step INTEGER DEFAULT 1,
    legal_accepted BOOLEAN DEFAULT FALSE,
    terms_accepted_at TIMESTAMP,
    privacy_accepted_at TIMESTAMP,
    ai_data_accepted_at TIMESTAMP,
    integrations JSONB DEFAULT '{}',
    knowledge_base_files JSONB DEFAULT '[]',
    ai_name VARCHAR(50) DEFAULT 'Jarvis',
    ai_tone VARCHAR(20) DEFAULT 'professional',
    ai_response_style VARCHAR(20) DEFAULT 'concise',
    ai_greeting TEXT,
    first_victory_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 12.2 Modified Tables

**users** - Add fields:
```sql
ALTER TABLE users ADD COLUMN signup_method VARCHAR(20) DEFAULT 'email';
ALTER TABLE users ADD COLUMN gmail_id VARCHAR(100);
ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE;
```

**companies** - Modify for new flow:
```sql
-- Ensure these fields exist or are added during post-payment
ALTER TABLE companies ADD COLUMN industry VARCHAR(50);
ALTER TABLE companies ADD COLUMN company_size VARCHAR(20);
ALTER TABLE companies ADD COLUMN website VARCHAR(255);
```

---

## 13. API Endpoints

### 13.1 Demo Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/demo/chat/start` | Start demo chat session |
| POST | `/api/demo/chat/message` | Send message in demo |
| GET | `/api/demo/chat/history` | Get chat history |
| POST | `/api/demo/call/request` | Request demo call |
| POST | `/api/demo/call/verify-otp` | Verify phone OTP |
| POST | `/api/demo/call/confirm-payment` | Confirm call payment |
| GET | `/api/demo/call/status` | Get call status |

### 13.2 User Details Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/user/details` | Get user details |
| POST | `/api/user/details` | Submit user details |
| POST | `/api/user/verify-work-email` | Verify work email |

### 13.3 Onboarding Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/onboarding/state` | Get onboarding state |
| POST | `/api/onboarding/step/{n}` | Complete step n |
| POST | `/api/onboarding/legal` | Accept legal agreements |
| POST | `/api/onboarding/integrations` | Save integrations |
| POST | `/api/onboarding/knowledge` | Upload knowledge files |
| POST | `/api/onboarding/ai-config` | Save AI configuration |
| POST | `/api/onboarding/complete` | Complete onboarding |

### 13.4 WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `ws://host/ws/demo/chat/{session_id}` | Demo chat real-time connection |

---

## 14. Third-Party Integrations

### 14.1 Required Integrations

| Service | Purpose | Implementation |
|---------|---------|----------------|
| Paddle | Payment processing | Webhooks for events |
| Twilio | SMS OTP, Voice calls | Verify API, Voice API |
| OpenAI/Anthropic | AI responses | Configurable provider |
| Gmail OAuth | Social login | Google OAuth 2.0 |
| File Storage | KB uploads | S3/Cloudflare R2 |

### 14.2 Paddle Webhooks to Handle

| Event | Action |
|-------|--------|
| `transaction.completed` | Mark payment successful, trigger details collection |
| `transaction.payment_failed` | Notify user, offer retry |
| `subscription.created` | Create company, assign plan |
| `subscription.updated` | Update company plan |
| `subscription.cancelled` | Handle cancellation |
| `subscription.renewed` | Update billing dates |

### 14.3 Twilio Configuration

**SMS OTP:**
- Use Twilio Verify API
- 4-digit code, 5-minute expiry
- Max 3 attempts

**Voice Calls:**
- Use Twilio Voice API
- TwiML for call flow
- Recording for quality (optional)

---

## 15. Implementation Phases

### 15.1 Phase 1: Foundation (Week 6)

**Day 1 (W6D1):**
- [ ] Post-payment details collection
- [ ] Database schema changes
- [ ] Basic API endpoints

**Day 2 (W6D2):**
- [ ] Jarvis chat UI (frontend)
- [ ] Demo chat backend
- [ ] WebSocket integration

**Day 3 (W6D3):**
- [ ] Demo call flow (phone → OTP → payment)
- [ ] Twilio integration
- [ ] Call status tracking

**Day 4 (W6D4):**
- [ ] Onboarding wizard frontend
- [ ] Onboarding backend APIs
- [ ] Legal consent handling

**Day 5 (W6D5):**
- [ ] AI configuration in onboarding
- [ ] First Victory experience
- [ ] End-to-end testing

### 15.2 Phase 2: Enhancement (Future)

- [ ] Multiple AI personality templates
- [ ] Advanced knowledge base training
- [ ] Integration-specific setup wizards
- [ ] Onboarding analytics dashboard
- [ ] A/B testing for conversion optimization

---

## Appendix A: Industry Options

```json
[
  "E-commerce",
  "SaaS / Technology",
  "Healthcare",
  "Finance & Banking",
  "Education",
  "Real Estate",
  "Travel & Hospitality",
  "Food & Restaurant",
  "Media & Entertainment",
  "Professional Services",
  "Manufacturing",
  "Retail",
  "Non-profit",
  "Government",
  "Other"
]
```

---

## Appendix B: Company Size Options

```json
[
  "1-10 employees",
  "11-50 employees",
  "51-200 employees",
  "201-500 employees",
  "501-1000 employees",
  "1000+ employees"
]
```

---

## Appendix C: Open Questions

> These items need stakeholder decision before implementation.

1. **Demo Chat Limit**: How many messages per session? (Current: 10)
2. **Demo Call Pricing**: Confirm $1 for 3 minutes?
3. **Plan Pricing**: Finalize Starter/Growth/Enterprise pricing
4. **Work Email Verification**: Required or optional?
5. **Integration Setup**: Which integrations in Phase 1?
6. **Knowledge Base File Limit**: Max file size and count?
7. **AI Provider**: Production choice (OpenAI/Anthropic/Gemini)?

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Day 33 | Initial specification created |

---

*This document will be updated as decisions are made and implementation progresses.*
