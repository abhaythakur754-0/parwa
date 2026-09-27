# PARWA Onboarding System Specification

> **Document Version:** 2.1  
> **Last Updated:** Day 38  
> **Status:** Updated - Added Sections 16-18: Provider-Agnostic Integration Architecture, API Key Auto-Detection, Jarvis Integration Setup Flow

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
16. [Provider-Agnostic Integration Architecture](#16-provider-agnostic-integration-architecture)
17. [API Key Auto-Detection System](#17-api-key-auto-detection-system)
18. [Integration Setup via Jarvis — Conversation Flow](#18-integration-setup-via-jarvis--conversation-flow)

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

### 2.3 Landing Page Structure (Home Page)

> **Added in Version 2.0** - Detailed landing page layout with psychological design

The landing page is structured to psychologically attract customers, following a Netflix/Prime Video style carousel approach.

#### 2.3.1 Navigation Bar

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🤖 PARWA              Home    Models    ROI    Jarvis Chatbot    [Login]  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Navigation Items:**
| Item | Position | Link | Notes |
|------|----------|------|-------|
| Logo | Left | `/` | PARWA branding |
| Home | Center | `/` | Landing page |
| Models | Center | `/models` | Pricing/variants page |
| ROI | Center | `/roi` | ROI calculator |
| Jarvis Chatbot | Center | Opens Jarvis Chat | AI chat interface |
| Login | Right | `/login` | Contains signup option inside |

**Important:** No separate Signup button - signup is included inside the Login page.

#### 2.3.2 Page Section Order (By Psychology)

The landing page sections are ordered based on psychological impact:

| Order | Section | Purpose | Psychology |
|-------|---------|---------|------------|
| 1 | Feature Carousel | First impression, grab attention | Instant engagement |
| 2 | Hero Section | Cost/Time comparison | Value realization |
| 3 | Why Choose PARWA | WHAT Jarvis does | Benefit understanding |
| 4 | How It Works | HOW Jarvis works | Trust building |
| 5 | Footer | Links & copyright | Navigation |

#### 2.3.3 Section 1: Feature Carousel (Netflix/Prime Style)

**Position:** Immediately below Navigation Bar (FIRST thing users see)

5-slide carousel with psychological triggers:

| Slide | Title | Content | Psychological Trigger |
|-------|-------|---------|----------------------|
| 1 | **Control Everything by Chat** | Just type and control - no complex dashboards. No training needed. Just talk. | **SIMPLICITY** - Removes overwhelm |
| 2 | **No Tech Skills Needed** | Not technical? Never done customer care? Perfect. Jarvis handles everything. You just focus on your business. | **FEAR REMOVAL** - Anyone can use it |
| 3 | **Self-Learning AI** | Upload your docs. Jarvis learns. Every question makes it smarter. Zero manual training needed. | **EFFORT REDUCTION** - No manual training |
| 4 | **Eliminates 90% Daily Work** | 90% of support tickets are repetitive. Jarvis handles them all. You get 40+ hours back every week. | **TIME FREEDOM** - Direct benefit |
| 5 | **Your Iron Man Jarvis** | Like Tony Stark's Jarvis, but for your business. Your personal AI officer that never sleeps, never complains, and always delivers. | **ASPIRATION** - Emotional connection |

**Visual Structure:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  < ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ >              │
│    │ 💬 Control     │ │ 🎯 No Tech     │ │ 🧠 Self        │              │
│    │ Everything     │ │ Skills Needed  │ │ Learning       │              │
│    │ by Chat        │ │                │ │                │              │
│    └────────────────┘ └────────────────┘ └────────────────┘              │
│                                                                             │
│  < ┌────────────────┐ ┌────────────────┐ >                                 │
│    │ ⚡ Eliminates  │ │ 🦾 Your Iron   │                                  │
│    │ 90% Daily Work │ │ Man Jarvis     │                                  │
│    └────────────────┘ └────────────────┘                                   │
│                          ● ○ ○ ○ ○ (dots indicator)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 2.3.4 Section 2: Hero Section

**Position:** Below Feature Carousel

**Purpose:** Cost/Time comparison - show value without fake statistics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│     ┌────────────────────────────┐  ┌────────────────────────────┐        │
│     │  ❌ Traditional Support    │  │  ✅ PARWA AI               │        │
│     │                            │  │                            │        │
│     │  $50,000/year per agent    │  │  Starting at $999/month    │        │
│     │  8 hours/day only          │  │  24/7/365 availability     │        │
│     │  Training costs            │  │  Learns automatically      │        │
│     │  Sick days & turnover      │  │  Never takes a day off     │        │
│     │  Inconsistent responses    │  │  Always consistent         │        │
│     └────────────────────────────┘  └────────────────────────────┘        │
│                                                                             │
│     🤖 JARVIS PREVIEW - Chat with your AI Employee                         │
│     ┌────────────────────────────────────────────────────────────────┐    │
│     │ 🤖 Jarvis: Hi! I'm your AI customer care officer. I handle    │    │
│     │            tickets, answer questions, and learn from your     │    │
│     │            knowledge base. What would you like to know?       │    │
│     │                                                                │    │
│     │ [Type your message...]                              [Send]    │    │
│     └────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│     [Get Started with Jarvis]                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- Starting price: $999/month (not fake stats)
- No misleading response time claims
- Show real cost comparison
- Include interactive Jarvis chat preview

#### 2.3.5 Section 3: Why Choose PARWA

**Position:** Below Hero Section

**Purpose:** Show WHAT Jarvis does (people care about WHAT before HOW)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│     ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│     │ 💡 Smart            │  │ 🔮 Predictive       │  │ 🎯 Industry         │
│     │ Recommendations     │  │ Support             │  │ Specific            │
│     │                     │  │                     │  │                     │
│     │ Suggests best       │  │ Anticipates         │  │ E-commerce, SaaS,   │
│     │ solutions, not      │  │ customer needs      │  │ Logistics & more    │
│     │ just answers        │  │ before they ask     │  │ tailored for you    │
│     └─────────────────────┘  └─────────────────────┘  └─────────────────────┘
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Features (with animated cards):**

| Feature | Description | Animation |
|---------|-------------|-----------|
| Smart Recommendations | Jarvis suggests best solutions, not just answers | Card hover effect |
| Predictive Support | Anticipates customer needs before they ask | Subtle glow effect |
| Industry Specific | E-commerce, SaaS, Logistics & more - tailored for you | Industry icons animation |

#### 2.3.6 Section 4: How It Works

**Position:** Below Why Choose PARWA

**Purpose:** Show HOW Jarvis works (people care about HOW after understanding WHAT)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          HOW JARVIS WORKS                                   │
│                                                                             │
│       📩              🧠              💡              ✅                   │
│    Customer         Jarvis          Smart           Happy                 │
│    Message          Analyzes        Response        Client                │
│    (envelope        (brain          (lightbulb      (checkmark            │
│     flying)          pulsing)        glowing)        celebration)         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Animated Steps:**

| Step | Icon | Description | Animation |
|------|------|-------------|-----------|
| 1 | 📩 Envelope | Customer Message | Envelope flying in |
| 2 | 🧠 Brain | Jarvis Analyzes | Brain pulsing |
| 3 | 💡 Lightbulb | Smart Response | Lightbulb glowing |
| 4 | ✅ Checkmark | Happy Client | Celebration effect |

#### 2.3.7 Section 5: Footer

**Position:** Bottom of page

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  🤖 PARWA                                                                   │
│                                                                             │
│  Product          Resources         Company          Legal                 │
│  Features         Blog              About Us         Privacy Policy        │
│  Models           Documentation     Careers          Terms of Service      │
│  ROI Calculator   API Reference     Contact          Cookie Policy         │
│                                                                             │
│  © 2026 PARWA. All rights reserved.    🔗 LinkedIn  Twitter  GitHub        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Changes:**
- Year: 2026 (not 2024)
- "Pricing" renamed to "Models"

#### 2.3.8 Important Clarifications

> **⚠️ CRITICAL:** Understanding who Jarvis is for

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PARWA USER STRUCTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  YOUR CLIENT (Business Owner)                                               │
│  ─────────────────────────────                                              │
│  • Takes subscription from PARWA                                            │
│  • Gets JARVIS - the AI employee that handles their support                 │
│  • Jarvis works FOR the business owner                                      │
│                                                                             │
│  YOUR CLIENT'S CUSTOMERS (End Users)                                        │
│  ─────────────────────────────────                                          │
│  • They interact with a NORMAL chatbot on the client's website              │
│  • They don't see Jarvis - they see a branded support chat                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Jarvis is for YOUR clients (business owners), NOT their end customers.**

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
| 2.1 | Day 38 | Added: Section 16-18 Provider-Agnostic Integration Architecture, API Key Auto-Detection, Jarvis Integration Setup Flow (not built until Jarvis is complete) |

---

*This document will be updated as decisions are made and implementation progresses.*

---

## 16. Provider-Agnostic Integration Architecture

> **Added in Version 2.1** — This section documents the provider-agnostic integration onboarding design discussed between founder and engineering. This will be built AFTER Jarvis is completely built.

### 16.1 Design Philosophy

The fundamental principle: **clients connect THEIR own providers, not ours.** Parwa does NOT hardcode any email, SMS, or payment provider. Instead, clients bring whatever provider they already use (or want to use), and Parwa integrates with it through a unified abstraction layer. This makes Parwa flexible and provider-neutral.

**What this means in practice:**
- If a client uses Brevo for email, they connect Brevo with their API key.
- If a client uses SendGrid for email, they connect SendGrid with their API key.
- If a client uses AWS SES, they connect AWS SES with their credentials.
- The same applies to SMS providers, payment providers, CRM, e-commerce platforms, helpdesk tools, and any other third-party service.
- Parwa provides adapter implementations for popular providers, but any provider with a REST API can be connected via Custom API integration.

### 16.2 What is INTERNAL vs What is CLIENT-CONFIGURABLE

This distinction is critical and was established by the founder:

| Channel / Service | Who Provides It? | Client Configurable? | Why |
|---|---|---|---|
| **AI Voice (Twilio)** | Parwa provides | NO | Parwa replaces call centers. Voice is our internal infrastructure we provide to clients. Clients do NOT bring their own voice provider. |
| **Chat Widget** | Built into Parwa | NO | Parwa's own chat interface for the client's website. No external provider needed. |
| **Email** | Client brings their own | YES | Client uses Brevo, SendGrid, AWS SES, Mailgun, Postmark, or Custom SMTP. Parwa sends/receives through their provider. |
| **SMS** | Client brings their own | YES | Client uses Twilio, Vonage, MessageBird, AWS SNS, Plivo, etc. Parwa sends SMS through their provider. |
| **Payment** | Client brings their own | YES | Client uses Paddle, Stripe, Razorpay, PayPal, Braintree, etc. Parwa processes through their payment gateway. |
| **CRM** | Client connects optionally | YES | HubSpot, Salesforce, Zoho — for syncing customer data. Optional. |
| **E-commerce** | Client connects optionally | YES | Shopify, WooCommerce — for order/product sync. Optional. |
| **Helpdesk** | Client connects optionally | YES | Zendesk, Freshdesk, Intercom — for ticket sync. Optional. |
| **Communication** | Client connects optionally | YES | Slack, Gmail, Teams — for notifications and team collaboration. Optional. |
| **Custom API** | Client connects optionally | YES | Any REST API / Webhook — universal connector. Optional. |

### 16.3 Integration Categories

All integrations fall into these categories. Each category has multiple provider options:

**Core Channel Providers (Client-Configurable):**

| Category | Available Providers |
|---|---|
| **Email Providers** | Brevo, SendGrid, AWS SES, Mailgun, Postmark, Custom SMTP |
| **SMS Providers** | Twilio, Vonage (Nexmo), MessageBird, AWS SNS, Plivo |
| **Payment Providers** | Paddle, Stripe, Razorpay, PayPal, Braintree |

**Optional Third-Party Integrations:**

| Category | Available Providers |
|---|---|
| **E-commerce** | Shopify, WooCommerce, BigCommerce |
| **Helpdesk** | Zendesk, Freshdesk, Intercom, Help Scout |
| **CRM** | HubSpot, Salesforce, Zoho CRM |
| **Communication** | Slack, Gmail, Microsoft Teams |
| **Custom API** | Any REST API / Webhook (universal connector) |

### 16.4 Provider Abstraction Layer

Behind every category, there is a protocol/interface that all providers must implement. This way, the rest of Parwa's code never needs to know WHICH provider is being used — it just calls the protocol.

```
┌────────────────────────────────────────────────────────────────────┐
│                    PARWA CORE ENGINE                               │
│                                                                    │
│  EmailService  ←→  EmailProvider Protocol                          │
│  SMSService    ←→  SMSProvider Protocol                            │
│  PaymentService ←→  PaymentProvider Protocol                       │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ProviderRegistry (maps category + name → adapter class)           │
│  ProviderFactory  (creates provider instance from ServiceConfig)    │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│                     ADAPTER IMPLEMENTATIONS                         │
│                                                                    │
│  Email:  BrevoAdapter | SendGridAdapter | SESAdapter | ...         │
│  SMS:    TwilioAdapter | VonageAdapter | SNSAdapter | ...           │
│  Payment: PaddleAdapter | StripeAdapter | RazorpayAdapter | ...     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 16.5 Database Foundation (Already Exists)

The existing Parwa database already has the tables needed to support provider-agnostic integrations:

| Table | Purpose |
|---|---|
| `APIProvider` | Global registry of all known providers (name, category, auth type, endpoint URLs) |
| `ServiceConfig` | Per-company credentials for each connected provider (encrypted API keys, tokens) |
| `Integration` | Tracks which integrations a company has connected (status, provider reference) |
| `RESTConnector` | For Custom API integrations — stores URL, method, headers, auth config |
| `WebhookIntegration` | For webhook-based integrations — stores webhook URL, events subscribed |
| `MCPConnection` | For MCP (Model Context Protocol) based integrations |

No new database tables are needed for the provider-agnostic architecture. The foundation is already there.

### 16.6 Key Design Rules

1. **No hardcoded SDK imports** — Services never import Brevo SDK, Twilio SDK, or Stripe SDK directly. They go through the provider protocol.
2. **Credentials are encrypted** — All API keys and tokens stored in `ServiceConfig` are encrypted at rest.
3. **Connection testing** — After connecting any provider, Jarvis tests the connection live to confirm it works.
4. **Every integration is skippable** — Clients can skip any integration during onboarding and set it up later from the dashboard.
5. **Industry-aware suggestions** — Jarvis suggests popular providers based on the client's industry (e.g., Shopify for E-commerce, Intercom for SaaS).

---

## 17. API Key Auto-Detection System

> **Added in Version 2.1** — This section documents the API key auto-detection capability that Jarvis uses during integration setup.

### 17.1 Why Auto-Detection?

When clients are setting up integrations through Jarvis, they may not know which provider their API key belongs to. For example, a client might paste an API key and say "here's my email key" without specifying whether it's Brevo, SendGrid, or something else. The API Key Auto-Detection system identifies the provider automatically from the key format, saving the client from having to figure it out.

### 17.2 Known Provider Key Patterns

Each provider has a distinctive API key format. The detector uses these patterns to identify providers:

| Provider | Key Pattern | Detection Method | Confidence |
|---|---|---|---|
| **Brevo** | Starts with `xkeysib-` followed by 64 chars | Prefix match | HIGH (99%) |
| **SendGrid** | Starts with `SG.` followed by encoded string | Prefix match | HIGH (99%) |
| **AWS SES** | Starts with `AKIA` followed by 16 chars | Prefix match | HIGH (95%) |
| **Mailgun** | Starts with `key-` followed by 32 hex chars | Prefix match | HIGH (95%) |
| **Postmark** | 32 hex chars, no prefix | Length + charset | MEDIUM (80%) |
| **Twilio** | Starts with `SK` followed by 32 hex chars | Prefix match | HIGH (99%) |
| **Vonage** | Starts with `basic_` or `Bearer` | Prefix match | HIGH (90%) |
| **Paddle** | Starts with `pdl_ntf` or `pdl_box` | Prefix match | HIGH (95%) |
| **Stripe** | Starts with `sk_live_` or `pk_live_` | Prefix match | HIGH (99%) |
| **Razorpay** | Starts with `rzp_live_` or `rzp_test_` | Prefix match | HIGH (99%) |
| **PayPal** | Starts with `EE` followed by long string | Prefix match | MEDIUM (85%) |
| **Shopify** | Starts with `shpat_` or `shpca_` | Prefix match | HIGH (95%) |
| **Slack** | Starts with `xoxb-` or `xoxp-` | Prefix match | HIGH (99%) |
| **Zendesk** | Starts with `Basic` or email:token format | Format detection | MEDIUM (80%) |
| **HubSpot** | Starts with `pat-` or `Bearer` | Prefix match | MEDIUM (85%) |

### 17.3 Detection Logic

The `ApiKeyDetector` runs through these steps when a client provides an API key:

```
INPUT: API key string + optional category hint from Jarvis

Step 1: PREFIX MATCHING
  → Check key against all known provider prefixes
  → If exactly ONE match found → return provider (HIGH confidence)

Step 2: FORMAT MATCHING  
  → Check key length, character set, structure
  → If pattern matches a provider → return provider (MEDIUM confidence)

Step 3: CATEGORY FILTERING (if category hint provided)
  → Filter candidates to only providers in the given category
  → e.g., if Jarvis says "this is for email", only check email providers

Step 4: MULTIPLE MATCHES
  → If multiple providers match → present options to client
  → "This looks like it could be Brevo or SendGrid. Which one?"

Step 5: NO MATCH
  → "I couldn't identify the provider from this key.
     Could you tell me which service it's for?"
  → User selects from provider list

OUTPUT: Detected provider name + confidence score
```

### 17.4 Confidence Scoring

| Confidence Level | Score | Behavior |
|---|---|---|
| **HIGH** | 90-100% | Auto-select provider. Show "I detected this is [Provider]. Correct?" |
| **MEDIUM** | 70-89% | Show "This looks like [Provider]. Is that right?" with option to change |
| **LOW** | Below 70% | Ask user to manually select from provider list |

### 17.5 Jarvis Integration During Onboarding

When a client provides an API key during integration setup, Jarvis automatically calls the detector:

```
Jarvis: "Great, paste your email API key here."

User: "xkeysib-a1b2c3d4e5f6...64chars..."

Jarvis: "I detected this is a Brevo API key. Let me test the
         connection... ✅ Connected! Your Brevo email is ready."
```

If the detection is uncertain:

```
Jarvis: "I think this might be a Brevo or SendGrid key. 
         Which email provider are you using?"
         
[Brevo] [SendGrid] [Something else]
```

If no match found:

```
Jarvis: "I couldn't identify the provider from this key. 
         Which email service is this for?"
         
[Brevo] [SendGrid] [AWS SES] [Mailgun] [Postmark] [Custom SMTP]
```

---

## 18. Integration Setup via Jarvis — Conversation Flow

> **Added in Version 2.1** — This section documents how integration setup works as a conversational flow inside Jarvis, happening AFTER the HANDOFF stage. This will be built AFTER Jarvis is completely built.

### 18.1 Why Jarvis for Integration Setup?

Integration setup is NOT a separate settings page or form wizard. It happens inside the Jarvis chat conversation, right after the HANDOFF from Onboarding Jarvis to Customer Care Jarvis. This approach has several advantages:

- **It IS the product demo** — The client is experiencing Jarvis doing exactly what it would do for their customers: handling a complex multi-step process conversationally.
- **No context switching** — The client stays in the same chat window they've been using throughout onboarding.
- **Conversational error handling** — If an API key doesn't work, Jarvis explains the error in plain language and helps troubleshoot.
- **Smart suggestions** — Based on the client's industry, Jarvis suggests the most popular providers.
- **Skippable** — Every integration can be skipped and set up later from the dashboard. This reduces onboarding friction.

### 18.2 New Conversation Stages (After HANDOFF)

The existing Jarvis conversation stages go up to HANDOFF. After HANDOFF, new stages are added for integration setup:

```
EXISTING STAGES (Before Payment):
WELCOME → DISCOVERY → DEMO → PRICING → BILL_REVIEW → VERIFICATION → PAYMENT → HANDOFF

NEW STAGES (After Payment, via Customer Care Jarvis):
HANDOFF → INTEGRATION_EMAIL → INTEGRATION_SMS → INTEGRATION_PAYMENT → INTEGRATION_THIRD_PARTY → FIRST_VICTORY
```

### 18.3 Complete Integration Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              POST-HANDOFF INTEGRATION FLOW (Inside Jarvis Chat)            │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌───────────────┐
                        │    HANDOFF    │
                        │ (Onboarding → │
                        │ Customer Care │
                        │   Jarvis)     │
                        └───────┬───────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ INTEGRATION_EMAIL     │
                    │                       │
                    │ "Which email provider │
                    │  do you use?"         │
                    │                       │
                    │ [Select] [Paste Key]  │
                    │ [Skip for now]        │
                    └───────────┬───────────┘
                                │
                    ┌───────────┼───────────┐
                    │ Connected │  Skipped   │
                    ▼           ▼            │
                    ✅ ──────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ INTEGRATION_SMS       │
                    │                       │
                    │ "Which SMS provider   │
                    │  do you use?"         │
                    │                       │
                    │ [Select] [Paste Key]  │
                    │ [Skip for now]        │
                    └───────────┬───────────┘
                                │
                    ┌───────────┼───────────┐
                    │ Connected │  Skipped   │
                    ▼           ▼            │
                    ✅ ──────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ INTEGRATION_PAYMENT  │
                    │                       │
                    │ "Which payment       │
                    │  provider do you     │
                    │  use?"                │
                    │                       │
                    │ [Select] [Paste Key]  │
                    │ [Skip for now]        │
                    └───────────┬───────────┘
                                │
                    ┌───────────┼───────────┐
                    │ Connected │  Skipped   │
                    ▼           ▼            │
                    ✅ ──────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ INTEGRATION_THIRD_    │
                    │ PARTY                 │
                    │                       │
                    │ "Any other tools?     │
                    │  (Shopify, Zendesk,   │
                    │   Slack, HubSpot...)" │
                    │                       │
                    │ [Browse Categories]   │
                    │ [Skip for now]        │
                    └───────────┬───────────┘
                                │
                    ┌───────────┼───────────┐
                    │ Connected │  Skipped   │
                    ▼           ▼            │
                    ✅ ──────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   FIRST VICTORY       │
                    │                       │
                    │ "All set! Let's get   │
                    │  your AI agents       │
                    │  ready."              │
                    │                       │
                    │ → Knowledge Base      │
                    │   Upload              │
                    │ → AI Activation       │
                    │ → Celebration!        │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │     DASHBOARD         │
                    │                       │
                    │ (Integrations can be  │
                    │  configured later     │
                    │  from Settings)       │
                    └───────────────────────┘
```

### 18.4 Detailed Conversation Scripts Per Stage

#### 18.4.1 INTEGRATION_EMAIL Stage

```
Customer Care Jarvis:
"Before we can start handling your customers' emails, we need to
 connect your email provider. Which email service do you use?"

[ProviderSelectorCard: Brevo | SendGrid | AWS SES | Mailgun | Postmark | Custom SMTP]

User selects: [Brevo]

Jarvis: "Great choice! Please paste your Brevo API key.
         You can find it in your Brevo dashboard under
         Settings → API Keys."

[ApiKeyInputCard with Brevo branding]

User pastes key: "xkeysib-a1b2c3d4..."

Jarvis: [ApiKeyDetector runs] "I detected this is a Brevo key.
         Testing connection... ✅ Connected successfully!

[ConnectionStatusCard: ✅ Brevo Email — Connected]

Jarvis: "Your Brevo email is ready. Customers' email tickets
         will now be sent and received through your Brevo account."
```

#### 18.4.2 INTEGRATION_SMS Stage

```
Jarvis: "Now let's set up SMS. Which SMS provider do you use?"

[ProviderSelectorCard: Twilio | Vonage | MessageBird | AWS SNS | Plivo]

User: "We use Twilio but I don't have the key handy."

Jarvis: "No problem! You can set up SMS later from your dashboard
         settings. Let's move on to payment."

[Skip — marked as pending, reminder added to dashboard]
```

#### 18.4.3 INTEGRATION_PAYMENT Stage

```
Jarvis: "For processing refunds and payment-related queries from
         your customers, which payment provider do you use?"

[ProviderSelectorCard: Paddle | Stripe | Razorpay | PayPal | Braintree]

User: "Stripe"

Jarvis: "Please paste your Stripe API key (starts with sk_live_)."

User pastes key.

Jarvis: [Auto-detected as Stripe] "Testing connection... ✅
         Connected! Your Stripe payment is ready.

[ConnectionStatusCard: ✅ Stripe Payment — Connected]
```

#### 18.4.4 INTEGRATION_THIRD_PARTY Stage

```
Jarvis: "Almost done! Do you use any other tools you'd like
         me to connect with? For example:"
- Shopify (E-commerce)
- Zendesk / Freshdesk / Intercom (Helpdesk)
- HubSpot / Salesforce (CRM)
- Slack / Teams (Communication)

[IntegrationSummaryCard showing what's connected + categories to browse]

User: "We use Shopify."

Jarvis: "Let's connect Shopify. You'll need to authorize Parwa
         through Shopify OAuth. Click below to start."

[OAuth authorization card — opens Shopify OAuth flow]

After OAuth completes:

Jarvis: "✅ Shopify connected! I can now sync orders, products,
         and customer data from your Shopify store."
```

### 18.5 Skip / Defer Behavior

Every integration stage can be skipped. When skipped:

1. **The stage is marked as "deferred"** in the onboarding state.
2. **A reminder is added to the dashboard** — a persistent banner saying "Connect your email provider to enable email ticket handling."
3. **Jarvis moves to the next stage** without blocking.
4. **The client can set it up anytime** from Dashboard → Settings → Integrations.

**Skip script:**
```
User clicks [Skip for now]

Jarvis: "No problem! You can set this up anytime from your
         dashboard settings. I'll remind you about it.
         Let's move on to the next one."
```

### 18.6 Error Handling During Setup

If a connection test fails, Jarvis provides troubleshooting guidance:

```
Jarvis: "❌ Connection failed. Here's what might be wrong:
- Check if the API key is correct and hasn't expired
- Make sure the key has the right permissions
- Verify your account is active with [Provider]

[ConnectionErrorCard with specific troubleshooting steps for the provider]

Would you like to try a different key or skip for now?"
[Try Again] [Use Different Key] [Skip for now]
```

### 18.7 Smart Defaults and Industry Suggestions

Jarvis uses the client's industry (collected during details) to suggest popular providers:

| Industry | Suggested Email | Suggested SMS | Suggested E-commerce | Suggested Helpdesk |
|---|---|---|---|---|
| **E-commerce** | Brevo, SendGrid | Twilio | Shopify, WooCommerce | Zendesk |
| **SaaS** | SendGrid, AWS SES | Twilio | — | Intercom, Zendesk |
| **Logistics** | Brevo, AWS SES | Twilio, Vonage | — | Freshdesk |
| **Others** | Brevo, SendGrid | Twilio | — | Zendesk, Freshdesk |

```
Jarvis: "Since you're in E-commerce, most of our clients use
         Shopify + Brevo. Would you like to connect those?"
```

### 18.8 Rich Cards Used During Integration Setup

These are the card components rendered inline in the Jarvis chat during integration stages:

| Card Component | When Shown | What It Displays |
|---|---|---|
| `ProviderSelectorCard` | When choosing a provider | List of providers in the category with logos and names |
| `ApiKeyInputCard` | When entering credentials | API key input field with auto-detection indicator |
| `ConnectionStatusCard` | After connection test | ✅ Connected or ❌ Failed with provider name |
| `ConnectionErrorCard` | On connection failure | Error message + provider-specific troubleshooting steps |
| `IntegrationSummaryCard` | At THIRD_PARTY stage | All connected/skipped providers + remaining categories |
| `IndustrySuggestionCard` | First provider in category | "Popular in your industry" suggestions |
| `OAuthCard` | When provider uses OAuth | "Connect with [Provider]" button opening OAuth flow |

### 18.9 Backend APIs for Integration Setup

These are the API endpoints that the integration cards call during the Jarvis-led setup:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/jarvis/integrations/providers/:category` | List available providers for a category |
| `POST` | `/api/jarvis/integrations/detect-key` | Auto-detect provider from API key |
| `POST` | `/api/jarvis/integrations/connect` | Connect a provider with credentials |
| `POST` | `/api/jarvis/integrations/test` | Test a provider connection |
| `GET` | `/api/jarvis/integrations/status` | Get all integration statuses for the session |
| `DELETE` | `/api/jarvis/integrations/:id` | Disconnect a provider |

### 18.10 Backend Services for Integration Setup

| Service | Purpose |
|---|---|
| `ProviderRegistry` | Maps provider category + name → adapter class |
| `ProviderFactory` | Creates provider instances from ServiceConfig |
| `ApiKeyDetector` | Auto-detects provider from API key pattern |
| `EmailProvider` protocol + adapters | Brevo, SendGrid, SES, Mailgun, Postmark |
| `SMSProvider` protocol + adapters | Twilio, Vonage, MessageBird, SNS, Plivo |
| `PaymentProvider` protocol + adapters | Paddle, Stripe, Razorpay, PayPal |

### 18.11 Knowledge Base File for Jarvis

A dedicated knowledge file gives Jarvis the information it needs to guide clients through integration setup:

**File:** `backend/app/data/jarvis_knowledge/11_integration_providers.json`

This file contains:
- All provider names, categories, and descriptions
- Setup instructions for each provider (where to find API keys)
- Common troubleshooting steps per provider
- Industry-specific recommendations
- OAuth flow descriptions for providers that use OAuth

### 18.12 Timing Note

> **IMPORTANT:** All integration setup functionality documented in Sections 16-18 will be built ONLY AFTER Jarvis is completely built. The current priority is finishing Jarvis first (all existing stages: WELCOME through HANDOFF). Integration stages (INTEGRATION_EMAIL through FIRST_VICTORY) come after Jarvis is production-ready.
